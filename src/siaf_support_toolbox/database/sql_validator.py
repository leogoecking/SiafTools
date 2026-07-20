from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_FORBIDDEN_KEYWORDS = frozenset(
    {
        "ALTER",
        "COMMIT",
        "CREATE",
        "DELETE",
        "DROP",
        "EXECUTE",
        "GRANT",
        "GEN_ID",
        "INSERT",
        "MERGE",
        "POST_EVENT",
        "RECREATE",
        "REVOKE",
        "ROLLBACK",
        "RDB$SET_CONTEXT",
        "SET",
        "UPDATE",
    }
)
_WORD = re.compile(r"[A-Z_][A-Z0-9_$]*", re.IGNORECASE)
_PARAMETER = re.compile(r"(?<!:):([A-Z_][A-Z0-9_$]*)", re.IGNORECASE)
SAFE_SYSTEM_RELATIONS = frozenset({"RDB$DATABASE", "RDB$RELATIONS"})
_FROM_BOUNDARIES = frozenset(
    {"WHERE", "GROUP", "ORDER", "HAVING", "UNION", "ROWS", "PLAN", "FOR", "WITH"}
)


@dataclass(frozen=True, slots=True)
class SQLValidationResult:
    valid: bool
    compiled_sql: str = ""
    parameter_names: tuple[str, ...] = ()
    relation_names: tuple[str, ...] = ()
    error_code: str | None = None
    message: str | None = None


class SQLParameterError(ValueError):
    pass


def validate_read_only_sql(sql: str) -> SQLValidationResult:
    """Aceita uma única consulta SELECT/CTE e compila parâmetros nomeados para o driver fdb."""
    if not sql or not sql.strip():
        return _invalid("empty_sql", "O template não contém uma consulta")
    try:
        code_mask, statement_end = _code_mask(sql)
    except ValueError as exc:
        return _invalid("invalid_sql", str(exc))

    significant_semicolons = [
        index for index, char in enumerate(code_mask) if char == ";" and index != statement_end
    ]
    if significant_semicolons:
        return _invalid("multiple_statements", "O template deve conter uma única instrução")

    words = tuple(match.group(0).upper() for match in _WORD.finditer(code_mask))
    forbidden = next((word for word in words if word in _FORBIDDEN_KEYWORDS), None)
    if forbidden:
        return _invalid(
            "destructive_sql",
            f"O comando {forbidden} não é permitido no modo somente leitura",
        )
    if not words or words[0] not in {"SELECT", "WITH"}:
        return _invalid("not_read_only", "Somente consultas SELECT ou WITH são permitidas")
    if _contains_pair(words, "FOR", "UPDATE") or _contains_pair(words, "WITH", "LOCK"):
        return _invalid("locking_sql", "Consultas com bloqueio explícito não são permitidas")
    if any(
        words[index : index + 3] == ("NEXT", "VALUE", "FOR")
        for index in range(max(0, len(words) - 2))
    ):
        return _invalid("stateful_sql", "Avanço de generator não é permitido")
    if "INTO" in words:
        return _invalid("select_into", "SELECT INTO não é permitido")

    tokens = _sql_tokens(sql)
    relation_names, procedure_names = _analyze_sources(tokens)
    if procedure_names:
        return _invalid(
            "selectable_procedure",
            "Procedures selecionáveis não são permitidas em templates read-only: "
            + ", ".join(procedure_names),
        )

    parameter_names = tuple(match.group(1) for match in _PARAMETER.finditer(code_mask))
    compiled = _replace_parameters(sql, code_mask)
    return SQLValidationResult(
        True,
        compiled.rstrip().rstrip(";"),
        parameter_names,
        relation_names,
    )


def bind_parameters(
    validation: SQLValidationResult,
    supplied: dict[str, object],
    schema: dict[str, object],
) -> tuple[object, ...]:
    if not validation.valid:
        raise SQLParameterError(validation.message or "Consulta inválida")
    supplied_by_key = {key.casefold(): value for key, value in supplied.items()}
    schema_by_key = {key.casefold(): value for key, value in schema.items()}
    expected = {name.casefold() for name in validation.parameter_names}
    undeclared = expected - schema_by_key.keys()
    if undeclared:
        raise SQLParameterError(
            "Parâmetro(s) sem definição no template: " + ", ".join(sorted(undeclared))
        )
    extras = supplied_by_key.keys() - expected
    if extras:
        raise SQLParameterError("Parâmetro(s) inesperado(s): " + ", ".join(sorted(extras)))

    converted: dict[str, object] = {}
    for key in expected:
        definition = schema_by_key[key]
        settings = definition if isinstance(definition, dict) else {}
        value = supplied_by_key.get(key, settings.get("default"))
        required = bool(settings.get("required", True))
        if value in (None, ""):
            if required:
                raise SQLParameterError(f"O parâmetro {key} é obrigatório")
            converted[key] = None
        else:
            converted[key] = _convert_parameter(key, value, str(settings.get("type", "text")))
    _validate_parameter_ranges(converted, schema_by_key)
    return tuple(converted[name.casefold()] for name in validation.parameter_names)


def _convert_parameter(name: str, value: object, kind: str) -> object:
    normalized = kind.casefold()
    try:
        if normalized in {"integer", "int"}:
            return int(str(value))
        if normalized in {"decimal", "numeric", "number"}:
            return Decimal(str(value).replace(",", "."))
        if normalized in {"boolean", "bool"}:
            text = str(value).strip().casefold()
            if text in {"1", "true", "sim", "yes"}:
                return 1
            if text in {"0", "false", "não", "nao", "no"}:
                return 0
            raise ValueError
        if normalized == "date":
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            return datetime.strptime(str(value).strip(), "%d/%m/%Y").date()
    except (ValueError, InvalidOperation) as exc:
        message = f"O parâmetro {name} possui valor inválido"
        if normalized == "date":
            message += "; use DD/MM/AAAA"
        raise SQLParameterError(message) from exc
    return str(value)


def _validate_parameter_ranges(
    converted: dict[str, object], schema: dict[str, object]
) -> None:
    ranges: dict[str, dict[str, date]] = {}
    complete_ranges: set[str] = set()
    for key, raw_definition in schema.items():
        definition = raw_definition if isinstance(raw_definition, dict) else {}
        group = definition.get("range_group")
        bound = definition.get("range_bound")
        value = converted.get(key)
        if not group or bound not in {"start", "end"}:
            continue
        group_name = str(group)
        ranges.setdefault(group_name, {})
        if definition.get("range_require_complete"):
            complete_ranges.add(group_name)
        if isinstance(value, date):
            ranges[group_name][str(bound)] = value

    for group, bounds in ranges.items():
        start = bounds.get("start")
        end = bounds.get("end")
        if group in complete_ranges and (start is None) != (end is None):
            raise SQLParameterError(
                "Informe a data inicial e a data final para limitar o período"
            )
        if start is None or end is None:
            continue
        if start > end:
            raise SQLParameterError(
                "A data inicial não pode ser posterior à data final"
            )


def _code_mask(sql: str) -> tuple[str, int | None]:
    output = list(sql)
    state = "code"
    index = 0
    last_code = None
    while index < len(sql):
        char = sql[index]
        following = sql[index + 1] if index + 1 < len(sql) else ""
        if state == "code":
            if char == "'":
                state = "string"
                output[index] = " "
            elif char == '"':
                state = "identifier"
                output[index] = " "
            elif char == "-" and following == "-":
                state = "line_comment"
                output[index] = output[index + 1] = " "
                index += 1
            elif char == "/" and following == "*":
                state = "block_comment"
                output[index] = output[index + 1] = " "
                index += 1
            elif not char.isspace():
                last_code = index
        elif state in {"string", "identifier"}:
            output[index] = " "
            quote = "'" if state == "string" else '"'
            if char == quote:
                if following == quote:
                    output[index + 1] = " "
                    index += 1
                else:
                    state = "code"
        elif state == "line_comment":
            output[index] = "\n" if char == "\n" else " "
            if char == "\n":
                state = "code"
        else:
            output[index] = " "
            if char == "*" and following == "/":
                output[index + 1] = " "
                index += 1
                state = "code"
        index += 1
    if state in {"string", "identifier", "block_comment"}:
        raise ValueError("O template possui literal, identificador ou comentário não finalizado")
    trailing_semicolon = last_code if last_code is not None and sql[last_code] == ";" else None
    return "".join(output), trailing_semicolon


def _replace_parameters(sql: str, code_mask: str) -> str:
    pieces: list[str] = []
    position = 0
    for match in _PARAMETER.finditer(code_mask):
        pieces.append(sql[position : match.start()])
        pieces.append("?")
        position = match.end()
    pieces.append(sql[position:])
    return "".join(pieces)


def _contains_pair(words: tuple[str, ...], left: str, right: str) -> bool:
    return any(
        first == left and second == right
        for first, second in zip(words, words[1:], strict=False)
    )


@dataclass(frozen=True, slots=True)
class _SQLToken:
    value: str
    quoted: bool = False


def _sql_tokens(sql: str) -> tuple[_SQLToken, ...]:
    tokens: list[_SQLToken] = []
    index = 0
    while index < len(sql):
        char = sql[index]
        following = sql[index + 1] if index + 1 < len(sql) else ""
        if char.isspace():
            index += 1
            continue
        if char == "'":
            index = _skip_quoted(sql, index, "'")
            continue
        if char == '"':
            value, index = _quoted_identifier(sql, index)
            tokens.append(_SQLToken(value, True))
            continue
        if char == "-" and following == "-":
            newline = sql.find("\n", index + 2)
            index = len(sql) if newline < 0 else newline + 1
            continue
        if char == "/" and following == "*":
            end = sql.find("*/", index + 2)
            index = len(sql) if end < 0 else end + 2
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(sql) and (sql[end].isalnum() or sql[end] in {"_", "$"}):
                end += 1
            tokens.append(_SQLToken(sql[index:end].upper()))
            index = end
            continue
        if char in {"(", ")", ",", ".", ";"}:
            tokens.append(_SQLToken(char))
        index += 1
    return tuple(tokens)


def _skip_quoted(sql: str, index: int, quote: str) -> int:
    index += 1
    while index < len(sql):
        if sql[index] == quote:
            if index + 1 < len(sql) and sql[index + 1] == quote:
                index += 2
                continue
            return index + 1
        index += 1
    return index


def _quoted_identifier(sql: str, index: int) -> tuple[str, int]:
    pieces: list[str] = []
    index += 1
    while index < len(sql):
        if sql[index] == '"':
            if index + 1 < len(sql) and sql[index + 1] == '"':
                pieces.append('"')
                index += 2
                continue
            return "".join(pieces), index + 1
        pieces.append(sql[index])
        index += 1
    return "".join(pieces), index


def _analyze_sources(
    tokens: tuple[_SQLToken, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    cte_names = _cte_names(tokens)
    relations: list[str] = []
    procedures: list[str] = []
    active_from_depths: set[int] = set()
    expecting_source: set[int] = set()
    depth = 0
    for index, token in enumerate(tokens):
        value = token.value
        if value == "(":
            if depth in expecting_source:
                expecting_source.discard(depth)
            depth += 1
            continue
        if value == ")":
            active_from_depths.discard(depth)
            expecting_source.discard(depth)
            depth = max(0, depth - 1)
            continue
        if _is_keyword(token, "FROM"):
            active_from_depths.add(depth)
            expecting_source.add(depth)
            continue
        if depth in active_from_depths and (
            _is_keyword(token, "JOIN") or value == ","
        ):
            expecting_source.add(depth)
            continue
        if depth in active_from_depths and any(
            _is_keyword(token, keyword) for keyword in _FROM_BOUNDARIES
        ):
            active_from_depths.discard(depth)
            expecting_source.discard(depth)
            continue
        if depth not in expecting_source or value in {",", ".", ";"}:
            continue
        expecting_source.discard(depth)
        if _is_identifier(token):
            followed_by_call = index + 1 < len(tokens) and tokens[index + 1].value == "("
            normalized = value.casefold()
            if followed_by_call:
                procedures.append(value)
            elif normalized not in cte_names:
                relations.append(value)
    return _ordered_unique(relations), _ordered_unique(procedures)


def _cte_names(tokens: tuple[_SQLToken, ...]) -> set[str]:
    if not tokens or not _is_keyword(tokens[0], "WITH"):
        return set()
    names: set[str] = set()
    index = 1
    if index < len(tokens) and _is_keyword(tokens[index], "RECURSIVE"):
        index += 1
    while index < len(tokens) and _is_identifier(tokens[index]):
        name = tokens[index].value.casefold()
        index += 1
        if index < len(tokens) and tokens[index].value == "(":
            index = _after_balanced(tokens, index)
        if index >= len(tokens) or not _is_keyword(tokens[index], "AS"):
            break
        index += 1
        if index >= len(tokens) or tokens[index].value != "(":
            break
        names.add(name)
        index = _after_balanced(tokens, index)
        if index >= len(tokens) or tokens[index].value != ",":
            break
        index += 1
    return names


def _after_balanced(tokens: tuple[_SQLToken, ...], index: int) -> int:
    depth = 0
    while index < len(tokens):
        if tokens[index].value == "(":
            depth += 1
        elif tokens[index].value == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return index


def _is_keyword(token: _SQLToken, value: str) -> bool:
    return not token.quoted and token.value == value


def _is_identifier(token: _SQLToken) -> bool:
    return token.quoted or bool(_WORD.fullmatch(token.value))


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _invalid(code: str, message: str) -> SQLValidationResult:
    return SQLValidationResult(False, error_code=code, message=message)
