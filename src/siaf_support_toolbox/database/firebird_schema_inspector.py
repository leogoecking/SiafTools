from __future__ import annotations

import hashlib
import json
import socket
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from siaf_support_toolbox.database.firebird_probe import (
    load_api_library,
    runtime_compatibility_issue,
    translate_connection_error,
)
from siaf_support_toolbox.discovery.architecture import pe_architecture, process_architecture
from siaf_support_toolbox.repositories.models import SchemaField

_BATCH_SIZE = 200


@dataclass(frozen=True, slots=True)
class RelationInfo:
    name: str
    is_view: bool
    definition_hash: str | None = None


@dataclass(frozen=True, slots=True)
class IndexInfo:
    name: str
    relation_name: str
    fields: tuple[str, ...]
    unique: bool
    descending: bool
    primary_key: bool
    expression_hash: str | None = None


@dataclass(frozen=True, slots=True)
class TriggerInfo:
    name: str
    relation_name: str | None
    trigger_type: int | None
    sequence: int | None
    active: bool
    source_hash: str | None = None


@dataclass(frozen=True, slots=True)
class ProcedureInfo:
    name: str
    input_count: int
    output_count: int
    procedure_type: int | None = None
    source_hash: str | None = None
    parameters_hash: str | None = None


@dataclass(frozen=True, slots=True)
class GeneratorInfo:
    name: str


@dataclass(frozen=True, slots=True)
class SchemaSnapshot:
    checked_at: str
    server_version: str
    ods_version: str
    relations: tuple[RelationInfo, ...]
    fields: tuple[SchemaField, ...]
    indexes: tuple[IndexInfo, ...]
    triggers: tuple[TriggerInfo, ...]
    procedures: tuple[ProcedureInfo, ...]
    generators: tuple[GeneratorInfo, ...]


@dataclass(frozen=True, slots=True)
class SchemaInspectionResult:
    success: bool
    snapshot: SchemaSnapshot | None = None
    error_code: str | None = None
    message: str | None = None


def inspect_schema_read_only(
    *,
    dsn: str,
    username: str,
    password: str,
    client_library: str | Path,
    charset: str = "WIN1252",
    host: str | None = None,
    port: int | None = None,
    connect_timeout: float = 3.0,
) -> SchemaInspectionResult:
    """Lê apenas o catálogo Firebird em uma conexão temporária e transação read-only."""
    library_path = Path(client_library)
    if pe_architecture(library_path) != process_architecture():
        return SchemaInspectionResult(
            False,
            error_code="architecture_mismatch",
            message="A DLL Firebird é incompatível com a arquitetura do aplicativo",
        )

    try:
        import fdb
    except ImportError:
        return SchemaInspectionResult(
            False, error_code="dependency_missing", message="fdb não instalado"
        )

    if host and port and not _port_reachable(host, port, connect_timeout):
        return SchemaInspectionResult(
            False,
            error_code="port_unavailable",
            message="Não foi possível alcançar automaticamente o serviço Firebird",
        )

    connection = None
    cursor = None
    try:
        loaded_library = load_api_library(fdb, library_path)
        if loaded_library is not None:
            return SchemaInspectionResult(
                False,
                error_code="client_library_already_loaded",
                message=(
                    "Outra DLL Firebird já está carregada nesta sessão. "
                    "Reinicie o aplicativo para trocar a biblioteca cliente"
                ),
            )
        connection = fdb.connect(dsn=dsn, user=username, password=password, charset=charset)
        read_only_tpb = getattr(fdb, "ISOLATION_LEVEL_READ_COMMITED_RO", None)
        if read_only_tpb is None:
            return SchemaInspectionResult(
                False,
                error_code="readonly_unavailable",
                message="O driver não expõe o modo de transação somente leitura esperado",
            )
        connection.begin(tpb=read_only_tpb)
        server_version = _string_attribute(connection, "version") or _string_attribute(
            connection, "engine_version"
        )
        ods_version = _string_attribute(connection, "ods")
        compatibility_issue = runtime_compatibility_issue(server_version, ods_version)
        if compatibility_issue is not None:
            return SchemaInspectionResult(
                False,
                error_code=compatibility_issue[0],
                message=compatibility_issue[1],
            )

        cursor = connection.cursor()
        checked_at = datetime.now(UTC).isoformat(timespec="seconds")
        relations = _read_relations(cursor)
        raw_fields = _read_fields(cursor)
        indexes = _read_indexes(cursor)
        fields = _merge_field_indexes(raw_fields, indexes, checked_at)
        procedure_parameters = _read_procedure_parameters(cursor)
        snapshot = SchemaSnapshot(
            checked_at=checked_at,
            server_version=server_version or "",
            ods_version=ods_version or "",
            relations=relations,
            fields=fields,
            indexes=indexes,
            triggers=_read_triggers(cursor),
            procedures=_read_procedures(cursor, procedure_parameters),
            generators=_read_generators(cursor),
        )
        return SchemaInspectionResult(True, snapshot=snapshot)
    except Exception as exc:
        return SchemaInspectionResult(
            False,
            error_code="inspection_failed",
            message=translate_connection_error(exc),
        )
    finally:
        if cursor is not None:
            with suppress(Exception):
                cursor.close()
        if connection is not None:
            with suppress(Exception):
                connection.rollback()
            with suppress(Exception):
                connection.close()


def _read_relations(cursor: object) -> tuple[RelationInfo, ...]:
    rows = _query_batches(
        cursor,
        """
        SELECT TRIM(RDB$RELATION_NAME), RDB$VIEW_BLR, RDB$VIEW_SOURCE
        FROM RDB$RELATIONS
        WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0
        ORDER BY RDB$RELATION_NAME
        """,
    )
    return tuple(
        RelationInfo(_name(row[0]), row[1] is not None, _source_hash(row[2])) for row in rows
    )


def _read_fields(cursor: object) -> tuple[tuple[object, ...], ...]:
    return _query_batches(
        cursor,
        """
        SELECT TRIM(RF.RDB$RELATION_NAME), TRIM(RF.RDB$FIELD_NAME),
               F.RDB$FIELD_TYPE, F.RDB$FIELD_SUB_TYPE, F.RDB$FIELD_LENGTH,
               F.RDB$FIELD_SCALE,
               COALESCE(RF.RDB$NULL_FLAG, F.RDB$NULL_FLAG), RF.RDB$FIELD_POSITION,
               F.RDB$FIELD_PRECISION, F.RDB$CHARACTER_LENGTH,
               TRIM(CS.RDB$CHARACTER_SET_NAME), TRIM(CO.RDB$COLLATION_NAME)
        FROM RDB$RELATION_FIELDS RF
        JOIN RDB$FIELDS F ON F.RDB$FIELD_NAME = RF.RDB$FIELD_SOURCE
        JOIN RDB$RELATIONS R ON R.RDB$RELATION_NAME = RF.RDB$RELATION_NAME
        LEFT JOIN RDB$CHARACTER_SETS CS
          ON CS.RDB$CHARACTER_SET_ID = F.RDB$CHARACTER_SET_ID
        LEFT JOIN RDB$COLLATIONS CO
          ON CO.RDB$CHARACTER_SET_ID = F.RDB$CHARACTER_SET_ID
         AND CO.RDB$COLLATION_ID = COALESCE(RF.RDB$COLLATION_ID, F.RDB$COLLATION_ID)
        WHERE COALESCE(R.RDB$SYSTEM_FLAG, 0) = 0
        ORDER BY RF.RDB$RELATION_NAME, RF.RDB$FIELD_POSITION
        """,
    )


def _read_indexes(cursor: object) -> tuple[IndexInfo, ...]:
    rows = _query_batches(
        cursor,
        """
        SELECT TRIM(I.RDB$INDEX_NAME), TRIM(I.RDB$RELATION_NAME),
               TRIM(S.RDB$FIELD_NAME), I.RDB$UNIQUE_FLAG, I.RDB$INDEX_TYPE,
               RC.RDB$CONSTRAINT_TYPE, S.RDB$FIELD_POSITION, I.RDB$EXPRESSION_SOURCE
        FROM RDB$INDICES I
        LEFT JOIN RDB$INDEX_SEGMENTS S ON S.RDB$INDEX_NAME = I.RDB$INDEX_NAME
        LEFT JOIN RDB$RELATION_CONSTRAINTS RC ON RC.RDB$INDEX_NAME = I.RDB$INDEX_NAME
        WHERE COALESCE(I.RDB$SYSTEM_FLAG, 0) = 0
        ORDER BY I.RDB$RELATION_NAME, I.RDB$INDEX_NAME, S.RDB$FIELD_POSITION
        """,
    )
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        name = _name(row[0])
        relation = _name(row[1])
        item = grouped.setdefault(
            (relation, name),
            {
                "fields": [],
                "unique": bool(row[3]),
                "descending": bool(row[4]),
                "primary_key": _name(row[5]).casefold() == "primary key" if row[5] else False,
                "expression_hash": _source_hash(row[7]),
            },
        )
        fields = item["fields"]
        assert isinstance(fields, list)
        if row[2] is not None:
            fields.append(_name(row[2]))
    return tuple(
        IndexInfo(
            name=name,
            relation_name=relation,
            fields=tuple(item["fields"]),
            unique=bool(item["unique"]),
            descending=bool(item["descending"]),
            primary_key=bool(item["primary_key"]),
            expression_hash=(
                str(item["expression_hash"]) if item["expression_hash"] is not None else None
            ),
        )
        for (relation, name), item in grouped.items()
    )


def _read_triggers(cursor: object) -> tuple[TriggerInfo, ...]:
    rows = _query_batches(
        cursor,
        """
        SELECT TRIM(RDB$TRIGGER_NAME), TRIM(RDB$RELATION_NAME), RDB$TRIGGER_TYPE,
               RDB$TRIGGER_SEQUENCE, RDB$TRIGGER_INACTIVE, RDB$TRIGGER_SOURCE
        FROM RDB$TRIGGERS
        WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0
        ORDER BY RDB$TRIGGER_NAME
        """,
    )
    return tuple(
        TriggerInfo(
            _name(row[0]),
            _name(row[1]) if row[1] else None,
            _integer(row[2]),
            _integer(row[3]),
            not bool(row[4]),
            _source_hash(row[5]),
        )
        for row in rows
    )


def _read_procedures(
    cursor: object,
    parameter_hashes: dict[str, str],
) -> tuple[ProcedureInfo, ...]:
    rows = _query_batches(
        cursor,
        """
        SELECT TRIM(RDB$PROCEDURE_NAME), RDB$PROCEDURE_INPUTS, RDB$PROCEDURE_OUTPUTS,
               RDB$PROCEDURE_TYPE, RDB$PROCEDURE_SOURCE
        FROM RDB$PROCEDURES
        WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0
        ORDER BY RDB$PROCEDURE_NAME
        """,
    )
    return tuple(
        ProcedureInfo(
            _name(row[0]),
            _integer(row[1]) or 0,
            _integer(row[2]) or 0,
            _integer(row[3]),
            _source_hash(row[4]),
            parameter_hashes.get(_name(row[0])),
        )
        for row in rows
    )


def _read_procedure_parameters(cursor: object) -> dict[str, str]:
    rows = _query_batches(
        cursor,
        """
        SELECT TRIM(P.RDB$PROCEDURE_NAME), TRIM(P.RDB$PARAMETER_NAME),
               P.RDB$PARAMETER_TYPE, P.RDB$PARAMETER_NUMBER,
               F.RDB$FIELD_TYPE, F.RDB$FIELD_SUB_TYPE, F.RDB$FIELD_LENGTH,
               F.RDB$FIELD_SCALE, F.RDB$FIELD_PRECISION, F.RDB$CHARACTER_LENGTH,
               COALESCE(P.RDB$NULL_FLAG, F.RDB$NULL_FLAG),
               TRIM(CS.RDB$CHARACTER_SET_NAME),
               TRIM(CO.RDB$COLLATION_NAME), P.RDB$PARAMETER_MECHANISM,
               TRIM(P.RDB$RELATION_NAME), TRIM(P.RDB$FIELD_NAME)
        FROM RDB$PROCEDURE_PARAMETERS P
        JOIN RDB$FIELDS F ON F.RDB$FIELD_NAME = P.RDB$FIELD_SOURCE
        LEFT JOIN RDB$CHARACTER_SETS CS
          ON CS.RDB$CHARACTER_SET_ID = F.RDB$CHARACTER_SET_ID
        LEFT JOIN RDB$COLLATIONS CO
          ON CO.RDB$CHARACTER_SET_ID = F.RDB$CHARACTER_SET_ID
         AND CO.RDB$COLLATION_ID = COALESCE(P.RDB$COLLATION_ID, F.RDB$COLLATION_ID)
        ORDER BY P.RDB$PROCEDURE_NAME, P.RDB$PARAMETER_TYPE, P.RDB$PARAMETER_NUMBER
        """,
    )
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        procedure_name = _name(row[0])
        grouped.setdefault(procedure_name, []).append(
            {
                "name": _name(row[1]),
                "direction": _integer(row[2]),
                "position": _integer(row[3]),
                "field_type": _field_type(_integer(row[4]), _integer(row[5])),
                "field_length": _integer(row[6]),
                "field_scale": _integer(row[7]),
                "field_precision": _integer(row[8]),
                "character_length": _integer(row[9]),
                "nullable": _integer(row[10]) != 1,
                "character_set": _optional_name(row[11]),
                "collation": _optional_name(row[12]),
                "mechanism": _integer(row[13]),
                "relation": _optional_name(row[14]),
                "field": _optional_name(row[15]),
            }
        )
    return {name: _payload_hash(parameters) for name, parameters in grouped.items()}


def _read_generators(cursor: object) -> tuple[GeneratorInfo, ...]:
    rows = _query_batches(
        cursor,
        """
        SELECT TRIM(RDB$GENERATOR_NAME)
        FROM RDB$GENERATORS
        WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0
        ORDER BY RDB$GENERATOR_NAME
        """,
    )
    return tuple(GeneratorInfo(_name(row[0])) for row in rows)


def _merge_field_indexes(
    rows: Iterable[tuple[object, ...]],
    indexes: tuple[IndexInfo, ...],
    checked_at: str,
) -> tuple[SchemaField, ...]:
    by_field: dict[tuple[str, str], list[IndexInfo]] = {}
    for index in indexes:
        for field_name in index.fields:
            by_field.setdefault((index.relation_name, field_name), []).append(index)
    return tuple(
        SchemaField(
            relation_name=_name(row[0]),
            field_name=_name(row[1]),
            field_type=_field_type(_integer(row[2]), _integer(row[3])),
            nullable=_integer(row[6]) != 1,
            field_length=_integer(row[4]),
            field_scale=_integer(row[5]),
            field_precision=_integer(row[8]),
            character_length=_integer(row[9]),
            character_set_name=_optional_name(row[10]),
            collation_name=_optional_name(row[11]),
            primary_key=any(
                item.primary_key for item in by_field.get((_name(row[0]), _name(row[1])), [])
            ),
            index_names=tuple(
                item.name for item in by_field.get((_name(row[0]), _name(row[1])), [])
            ),
            checked_at=checked_at,
        )
        for row in rows
    )


def _query_batches(cursor: object, sql: str) -> tuple[tuple[object, ...], ...]:
    cursor.execute(sql)  # type: ignore[attr-defined]
    rows: list[tuple[object, ...]] = []
    while True:
        batch = cursor.fetchmany(_BATCH_SIZE)  # type: ignore[attr-defined]
        if not batch:
            return tuple(rows)
        rows.extend(tuple(row) for row in batch)


def _field_type(type_code: int | None, subtype: int | None) -> str:
    if type_code in {7, 8, 16} and subtype in {1, 2}:
        return "NUMERIC" if subtype == 1 else "DECIMAL"
    return {
        7: "SMALLINT",
        8: "INTEGER",
        10: "FLOAT",
        12: "DATE",
        13: "TIME",
        14: "CHAR",
        16: "BIGINT",
        27: "DOUBLE PRECISION",
        35: "TIMESTAMP",
        37: "VARCHAR",
        40: "CSTRING",
        261: "BLOB",
    }.get(type_code, f"TYPE_{type_code}" if type_code is not None else "UNKNOWN")


def _name(value: object) -> str:
    return str(value).strip()


def _optional_name(value: object) -> str | None:
    return _name(value) if value is not None else None


def _integer(value: object) -> int | None:
    return int(value) if value is not None else None


def _string_attribute(value: object, name: str) -> str | None:
    attribute = getattr(value, name, None)
    return str(attribute) if attribute not in (None, "") else None


def _source_hash(value: object) -> str | None:
    if value is None:
        return None
    read = getattr(value, "read", None)
    if callable(read):
        value = read()
    if isinstance(value, bytes):
        try:
            source = value.decode("utf-8")
        except UnicodeDecodeError:
            source = value.decode("cp1252", errors="replace")
    else:
        source = str(value)
    normalized = source.replace("\r\n", "\n").replace("\r", "\n").strip()
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _payload_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _port_reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=max(0.1, timeout)):
            return True
    except OSError:
        return False
