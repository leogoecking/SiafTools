from __future__ import annotations

import getpass
import logging
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from siaf_support_toolbox.core.version import __version__
from siaf_support_toolbox.database.firebird_query_executor import (
    QueryExecutionResult,
    execute_query_read_only,
)
from siaf_support_toolbox.database.sql_validator import (
    SQLParameterError,
    bind_parameters,
    validate_read_only_sql,
)
from siaf_support_toolbox.repositories.local_repository import LocalRepository
from siaf_support_toolbox.repositories.models import ExecutionRecord, QueryTemplate
from siaf_support_toolbox.services.connection_service import ConnectionTarget, SessionCredentials
from siaf_support_toolbox.services.query_export_service import (
    QueryExportResult,
    export_query_result,
)
from siaf_support_toolbox.services.query_result_store import QueryResultPage, QueryResultStore
from siaf_support_toolbox.services.schema_inspection_service import SchemaInspectionService

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QueryExecutionSummary:
    template_id: int
    template_name: str
    success: bool
    columns: tuple[str, ...] = ()
    records_processed: int = 0
    duration_ms: int = 0
    result_id: str | None = None
    canceled: bool = False
    error_code: str | None = None
    message: str | None = None
    truncated: bool = False


class _LimitedResultWriter:
    def __init__(self, store: QueryResultStore, limit: int | None) -> None:
        self.store = store
        self.limit = limit
        self.records_stored = 0
        self.truncated = False

    def append_batch(self, batch: tuple[tuple[object, ...], ...]) -> None:
        if self.limit is None:
            self.store.append_batch(batch)
            self.records_stored += len(batch)
            return
        remaining = max(0, self.limit - self.records_stored)
        accepted = batch[:remaining]
        if accepted:
            self.store.append_batch(accepted)
            self.records_stored += len(accepted)
        if len(batch) > len(accepted):
            self.truncated = True


class QueryExecutionService:
    def __init__(
        self,
        repository: LocalRepository,
        schema_inspector: SchemaInspectionService,
        cache_directory: Path,
        export_directory: Path | None = None,
        *,
        executor: Callable[..., QueryExecutionResult] = execute_query_read_only,
    ) -> None:
        self.repository = repository
        self.schema_inspector = schema_inspector
        self.cache_directory = cache_directory
        self.export_directory = export_directory or cache_directory / "exports"
        self._executor = executor
        self._stores: dict[str, QueryResultStore] = {}
        self._lock = threading.Lock()
        self._closed = False
        cache_directory.mkdir(parents=True, exist_ok=True)
        for stale in cache_directory.glob("query-*.sqlite3"):
            with suppress(OSError):
                stale.unlink()
        self._seed_templates()

    def list_templates(self) -> list[QueryTemplate]:
        return self.repository.list_query_templates()

    def execute(
        self,
        *,
        template_id: int,
        target: ConnectionTarget,
        database_id: int,
        credentials: SessionCredentials,
        parameters: dict[str, object],
        cancel_event: threading.Event,
    ) -> QueryExecutionSummary:
        try:
            return self._execute(
                template_id=template_id,
                target=target,
                database_id=database_id,
                credentials=credentials,
                parameters=parameters,
                cancel_event=cancel_event,
            )
        finally:
            credentials.clear()

    def _execute(
        self,
        *,
        template_id: int,
        target: ConnectionTarget,
        database_id: int,
        credentials: SessionCredentials,
        parameters: dict[str, object],
        cancel_event: threading.Event,
    ) -> QueryExecutionSummary:
        started_at = datetime.now(UTC)
        started = time.monotonic()
        template = self.repository.query_template(template_id)
        if template is None or not template.enabled:
            return self._blocked(
                template_id,
                "Template indisponível",
                target,
                database_id,
                started_at,
                started,
                "template_unavailable",
            )
        if not template.read_only:
            return self._blocked(
                template_id,
                template.name,
                target,
                database_id,
                started_at,
                started,
                "template_not_read_only",
                "O template não está marcado como somente leitura",
            )

        parameters = _normalized_parameters(parameters)

        validation = validate_read_only_sql(template.sql_template)
        if not validation.valid:
            return self._blocked(
                template_id,
                template.name,
                target,
                database_id,
                started_at,
                started,
                validation.error_code or "invalid_sql",
                validation.message,
            )
        dependency_issue = _template_dependency_issue(
            template.required_tables,
            template.required_fields,
            validation.relation_names,
        )
        if dependency_issue is not None:
            return self._blocked(
                template_id,
                template.name,
                target,
                database_id,
                started_at,
                started,
                "template_dependency_mismatch",
                dependency_issue,
            )
        parameter_group_issue = _required_parameter_group_issue(
            template.parameters_schema, parameters
        )
        if parameter_group_issue is not None:
            return self._blocked(
                template_id,
                template.name,
                target,
                database_id,
                started_at,
                started,
                "invalid_parameters",
                parameter_group_issue,
            )
        requirements = self.schema_inspector.validate_requirements(
            database_id,
            required_tables=template.required_tables,
            required_fields=template.required_fields,
        )
        if not requirements.allowed:
            details = requirements.reason
            if requirements.missing_relations:
                details = "Tabelas ausentes: " + ", ".join(requirements.missing_relations)
            elif requirements.missing_fields:
                details = "Campos ausentes: " + ", ".join(requirements.missing_fields)
            return self._blocked(
                template_id,
                template.name,
                target,
                database_id,
                started_at,
                started,
                "schema_requirements_failed",
                details or "A estrutura da base não atende ao template",
            )
        try:
            bound_parameters = bind_parameters(
                validation, parameters, template.parameters_schema
            )
        except SQLParameterError as exc:
            return self._blocked(
                template_id,
                template.name,
                target,
                database_id,
                started_at,
                started,
                "invalid_parameters",
                str(exc),
            )

        store = QueryResultStore(self.cache_directory)
        writer = _LimitedResultWriter(store, template.result_limit)
        try:
            result = self._executor(
                dsn=target.dsn,
                username=credentials.username,
                password=credentials.password,
                client_library=target.client_library,
                charset=credentials.charset,
                host=target.host,
                port=target.port,
                connect_timeout=3.0,
                sql=template.sql_template,
                parameters=bound_parameters,
                on_batch=writer.append_batch,
                cancel_event=cancel_event,
                batch_size=200,
            )
        except Exception:
            LOGGER.exception("Executor Firebird de consulta falhou")
            store.close()
            result = QueryExecutionResult(
                False,
                duration_ms=int((time.monotonic() - started) * 1000),
                error_code="query_worker_failed",
                message="A consulta encontrou um erro interno; consulte errors.log",
            )

        result_id = None
        if (result.success or result.canceled) and result.columns:
            result_id = uuid.uuid4().hex
            with self._lock:
                if self._closed:
                    result_id = None
                else:
                    self._stores[result_id] = store
            if result_id is None:
                store.close()
        else:
            store.close()
        summary = QueryExecutionSummary(
            template_id=template_id,
            template_name=template.name,
            success=result.success,
            columns=result.columns,
            records_processed=writer.records_stored,
            duration_ms=result.duration_ms,
            result_id=result_id,
            canceled=result.canceled,
            error_code=result.error_code,
            message=result.message,
            truncated=result.success and writer.truncated,
        )
        try:
            self._record(summary, target, database_id, started_at)
        except Exception:
            self.close_result(result_id)
            raise
        return summary

    def read_page(
        self, result_id: str, number: int, page_size: int = 100
    ) -> QueryResultPage:
        with self._lock:
            store = self._stores.get(result_id)
        if store is None:
            raise LookupError("O resultado temporário não está mais disponível")
        return store.read_page(number, page_size)

    def export_result(
        self,
        *,
        result_id: str,
        columns: tuple[str, ...],
        template_name: str,
        file_format: str,
        cancel_event: threading.Event,
        on_progress: Callable[[int], None] | None = None,
    ) -> QueryExportResult:
        if not columns:
            raise ValueError("O resultado não possui colunas para exportação")
        with self._lock:
            store = self._stores.get(result_id)
        if store is None:
            raise LookupError("O resultado temporário não está mais disponível")
        return export_query_result(
            columns=columns,
            batches=store.iter_batches(500),
            output_directory=self.export_directory,
            base_name=template_name,
            file_format=file_format,
            cancel_event=cancel_event,
            on_progress=on_progress,
        )

    def close_result(self, result_id: str | None) -> None:
        if result_id is None:
            return
        with self._lock:
            store = self._stores.pop(result_id, None)
        if store is not None:
            store.close()

    def close(self) -> None:
        with self._lock:
            stores = tuple(self._stores.values())
            self._stores.clear()
            self._closed = True
        for store in stores:
            store.close()

    def _blocked(
        self,
        template_id: int,
        template_name: str,
        target: ConnectionTarget,
        database_id: int,
        started_at: datetime,
        started: float,
        error_code: str,
        message: str | None = None,
    ) -> QueryExecutionSummary:
        summary = QueryExecutionSummary(
            template_id=template_id,
            template_name=template_name,
            success=False,
            duration_ms=int((time.monotonic() - started) * 1000),
            error_code=error_code,
            message=message,
        )
        self._record(summary, target, database_id, started_at)
        return summary

    def _record(
        self,
        summary: QueryExecutionSummary,
        target: ConnectionTarget,
        database_id: int,
        started_at: datetime,
    ) -> None:
        self.repository.add_execution_history(
            ExecutionRecord(
                environment_id=target.environment_id,
                database_id=database_id,
                action_name=summary.template_name,
                action_type="read_only_query",
                started_at=started_at.isoformat(timespec="seconds"),
                finished_at=datetime.now(UTC).isoformat(timespec="seconds"),
                success=summary.success,
                records_processed=summary.records_processed,
                truncated=summary.truncated,
                duration_ms=summary.duration_ms,
                error_code=summary.error_code,
                error_message=summary.message,
                app_version=__version__,
                windows_user=getpass.getuser(),
            )
        )

    def _seed_templates(self) -> None:
        self.repository.upsert_query_template(
            QueryTemplate(
                name="Data e hora do servidor",
                module="Sistema",
                description=(
                    "Consulta segura do relógio do servidor Firebird para validar o motor."
                ),
                sql_template=(
                    "SELECT CURRENT_TIMESTAMP AS MOMENTO_SERVIDOR FROM RDB$DATABASE"
                ),
                required_tables=("RDB$DATABASE",),
                required_fields={},
                parameters_schema={},
                risk_level="baixo",
                version="1.0",
                source_reference="Catálogo padrão Firebird 2.5",
            )
        )
        for template in _phase_seven_templates():
            self.repository.upsert_query_template(template)
        for template in _phase_eight_templates():
            self.repository.upsert_query_template(template)
        for template in _phase_nine_templates():
            self.repository.upsert_query_template(template)
        self.repository.upsert_query_template(
            QueryTemplate(
                name="Pesquisar relações do catálogo",
                module="Sistema",
                description=(
                    "Lista tabelas e views de usuário cujo nome corresponde ao filtro informado."
                ),
                sql_template=(
                    "SELECT TRIM(RDB$RELATION_NAME) AS RELACAO, "
                    "CASE WHEN RDB$VIEW_BLR IS NULL THEN 'TABELA' ELSE 'VIEW' END AS TIPO "
                    "FROM RDB$RELATIONS "
                    "WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0 "
                    "AND UPPER(TRIM(RDB$RELATION_NAME)) LIKE UPPER(:nome) "
                    "ORDER BY 1"
                ),
                required_tables=("RDB$RELATIONS",),
                required_fields={},
                parameters_schema={
                    "nome": {
                        "label": "Nome da relação (use % como curinga)",
                        "type": "text",
                        "required": True,
                        "default": "%",
                    }
                },
                risk_level="baixo",
                version="1.0",
                source_reference="Catálogo padrão Firebird 2.5",
            )
        )


def _template_dependency_issue(
    required_tables: tuple[str, ...],
    required_fields: dict[str, tuple[str, ...]],
    sql_relations: tuple[str, ...],
) -> str | None:
    declared = {name.casefold() for name in required_tables}
    actual = {name.casefold() for name in sql_relations}
    field_relations = {name.casefold() for name in required_fields}
    if actual != declared:
        return "As relações declaradas pelo template não correspondem ao SQL validado"
    if not field_relations.issubset(declared):
        return "Há campos obrigatórios associados a relações não declaradas"
    return None


def _required_parameter_group_issue(
    schema: dict[str, object], supplied: dict[str, object]
) -> str | None:
    supplied_by_key = {key.casefold(): value for key, value in supplied.items()}
    groups: dict[str, list[str]] = {}
    for name, raw_definition in schema.items():
        definition = raw_definition if isinstance(raw_definition, dict) else {}
        group = definition.get("require_one_of")
        if group:
            groups.setdefault(str(group), []).append(name)
    for names in groups.values():
        if not any(_has_parameter_value(supplied_by_key.get(name.casefold())) for name in names):
            return "Informe pelo menos um filtro para limitar a consulta"
    return None


def _normalized_parameters(supplied: dict[str, object]) -> dict[str, object]:
    return {
        key: value.strip() if isinstance(value, str) else value
        for key, value in supplied.items()
    }


def _has_parameter_value(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def _phase_seven_templates() -> tuple[QueryTemplate, ...]:
    source = "Snapshot real SIAFLOJA.FDB inspecionado em 2026-07-19"
    return (
        QueryTemplate(
            name="Produtos — busca e detalhes",
            module="Cadastros",
            description=(
                "Pesquisa até 500 produtos por código, nome, código de barras, referência "
                "e fornecedor vinculado."
            ),
            sql_template="""
                SELECT FIRST 500
                    P.PRO_COD AS CODIGO,
                    P.PRO_NOME AS NOME,
                    P.PRO_BARRA AS CODIGO_BARRAS,
                    P.PRO_REF AS REFERENCIA,
                    P.PRO_UNI AS UNIDADE,
                    P.PRO_VENDA AS PRECO_VENDA,
                    P.PRO_CUSTO AS CUSTO,
                    P.PRO_EST AS ESTOQUE,
                    P.PRO_DESAT AS DESATIVADO,
                    P.GRU_COD AS GRUPO,
                    P.FAM_COD AS FAMILIA,
                    P.PRO_CAD AS CADASTRO
                FROM DSIAF006 P
                WHERE (CAST(:codigo AS INTEGER) IS NULL OR P.PRO_COD = :codigo)
                  AND (CAST(:nome AS VARCHAR(120)) IS NULL OR P.PRO_NOME CONTAINING :nome)
                  AND (CAST(:barra AS VARCHAR(80)) IS NULL OR P.PRO_BARRA = :barra)
                  AND (CAST(:referencia AS VARCHAR(80)) IS NULL
                       OR P.PRO_REF CONTAINING :referencia)
                  AND (CAST(:fornecedor AS INTEGER) IS NULL OR EXISTS (
                      SELECT 1
                      FROM DSIAF030 PF
                      WHERE PF.PRO_COD = P.PRO_COD AND PF.FOR_COD = :fornecedor
                  ))
                ORDER BY P.PRO_NOME
            """.strip(),
            required_tables=("DSIAF006", "DSIAF030"),
            required_fields={
                "DSIAF006": (
                    "PRO_COD",
                    "PRO_NOME",
                    "PRO_BARRA",
                    "PRO_REF",
                    "PRO_UNI",
                    "PRO_VENDA",
                    "PRO_CUSTO",
                    "PRO_EST",
                    "PRO_DESAT",
                    "GRU_COD",
                    "FAM_COD",
                    "PRO_CAD",
                ),
                "DSIAF030": ("PRO_COD", "FOR_COD"),
            },
            parameters_schema={
                "codigo": _optional_parameter("Código", "integer"),
                "nome": _optional_parameter("Nome contém"),
                "barra": _optional_parameter("Código de barras"),
                "referencia": _optional_parameter("Referência contém"),
                "fornecedor": _optional_parameter("Código do fornecedor", "integer"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=source,
        ),
        QueryTemplate(
            name="Clientes — busca e detalhes",
            module="Cadastros",
            description="Pesquisa até 500 clientes por código, nome ou CPF/CNPJ.",
            sql_template="""
                SELECT FIRST 500
                    C.CLI_COD AS CODIGO,
                    C.CLI_NOME AS NOME,
                    C.CLI_FANT AS FANTASIA,
                    C.CLI_CPF AS CPF,
                    C.CLI_CGC AS CNPJ,
                    C.CLI_FONE AS TELEFONE,
                    C.CLI_CEL AS CELULAR,
                    C.CLI_MAIL AS EMAIL,
                    C.CLI_CID AS CIDADE,
                    C.CLI_EST AS UF,
                    C.CLI_SIT AS SITUACAO,
                    C.CLI_CRED AS LIMITE_CREDITO,
                    C.CLI_CAD AS CADASTRO
                FROM DSIAF010 C
                WHERE (CAST(:codigo AS INTEGER) IS NULL OR C.CLI_COD = :codigo)
                  AND (CAST(:nome AS VARCHAR(120)) IS NULL OR C.CLI_NOME CONTAINING :nome)
                  AND (CAST(:documento AS VARCHAR(30)) IS NULL OR
                    REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(C.CLI_CPF, ''), '.', ''),
                      '-', ''), '/', ''), ' ', '') =
                    REPLACE(REPLACE(REPLACE(REPLACE(CAST(:documento AS VARCHAR(30)), '.', ''),
                      '-', ''), '/', ''), ' ', '') OR
                    REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(C.CLI_CGC, ''), '.', ''),
                      '-', ''), '/', ''), ' ', '') =
                    REPLACE(REPLACE(REPLACE(REPLACE(CAST(:documento AS VARCHAR(30)), '.', ''),
                      '-', ''), '/', ''), ' ', ''))
                ORDER BY C.CLI_NOME
            """.strip(),
            required_tables=("DSIAF010",),
            required_fields={
                "DSIAF010": (
                    "CLI_COD",
                    "CLI_NOME",
                    "CLI_FANT",
                    "CLI_CPF",
                    "CLI_CGC",
                    "CLI_FONE",
                    "CLI_CEL",
                    "CLI_MAIL",
                    "CLI_CID",
                    "CLI_EST",
                    "CLI_SIT",
                    "CLI_CRED",
                    "CLI_CAD",
                )
            },
            parameters_schema={
                "codigo": _optional_parameter("Código", "integer"),
                "nome": _optional_parameter("Nome contém"),
                "documento": _optional_parameter("CPF/CNPJ"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=source,
        ),
        QueryTemplate(
            name="Fornecedores — busca e detalhes",
            module="Cadastros",
            description="Pesquisa até 500 fornecedores por código, nome, razão ou CPF/CNPJ.",
            sql_template="""
                SELECT FIRST 500
                    F.FOR_COD AS CODIGO,
                    F.FOR_NOME AS NOME,
                    F.FOR_RAZAO AS RAZAO_SOCIAL,
                    F.FOR_CPF AS CPF,
                    F.FOR_CGC AS CNPJ,
                    F.FOR_FONE AS TELEFONE,
                    F.FOR_CEL AS CELULAR,
                    F.FOR_MAIL AS EMAIL,
                    F.FOR_CID AS CIDADE,
                    F.FOR_EST AS UF,
                    F.FOR_CAD AS CADASTRO
                FROM DSIAF009 F
                WHERE (CAST(:codigo AS INTEGER) IS NULL OR F.FOR_COD = :codigo)
                  AND (CAST(:nome AS VARCHAR(120)) IS NULL OR F.FOR_NOME CONTAINING :nome
                       OR F.FOR_RAZAO CONTAINING :nome)
                  AND (CAST(:documento AS VARCHAR(30)) IS NULL OR
                    REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(F.FOR_CPF, ''), '.', ''),
                      '-', ''), '/', ''), ' ', '') =
                    REPLACE(REPLACE(REPLACE(REPLACE(CAST(:documento AS VARCHAR(30)), '.', ''),
                      '-', ''), '/', ''), ' ', '') OR
                    REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(F.FOR_CGC, ''), '.', ''),
                      '-', ''), '/', ''), ' ', '') =
                    REPLACE(REPLACE(REPLACE(REPLACE(CAST(:documento AS VARCHAR(30)), '.', ''),
                      '-', ''), '/', ''), ' ', ''))
                ORDER BY F.FOR_NOME
            """.strip(),
            required_tables=("DSIAF009",),
            required_fields={
                "DSIAF009": (
                    "FOR_COD",
                    "FOR_NOME",
                    "FOR_RAZAO",
                    "FOR_CPF",
                    "FOR_CGC",
                    "FOR_FONE",
                    "FOR_CEL",
                    "FOR_MAIL",
                    "FOR_CID",
                    "FOR_EST",
                    "FOR_CAD",
                )
            },
            parameters_schema={
                "codigo": _optional_parameter("Código", "integer"),
                "nome": _optional_parameter("Nome ou razão contém"),
                "documento": _optional_parameter("CPF/CNPJ"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=source,
        ),
    )


def _phase_eight_templates() -> tuple[QueryTemplate, ...]:
    source = "Snapshot real SIAFLOJA.FDB e índices inspecionados em 2026-07-19"
    return (
        QueryTemplate(
            name="NF-e — saídas e indicadores",
            module="Fiscal",
            description=(
                "Pesquisa até 500 notas de saída por série, número, chave, cliente ou período; "
                "os códigos de situação são exibidos sem interpretação automática."
            ),
            sql_template="""
                SELECT FIRST 501
                    N.SAI_SER AS SERIE,
                    N.SAI_PED AS NUMERO,
                    N.SAI_DATA AS DATA,
                    N.SAI_HORA AS HORA,
                    N.SAI_MOD AS MODELO,
                    N.CFOP_COD AS CFOP,
                    N.CLI_COD AS CLIENTE_CODIGO,
                    N.CLI_NOME AS CLIENTE_NOME,
                    N.CLI_CPF AS CPF,
                    N.CLI_CGC AS CNPJ,
                    N.SAI_MERC AS MERCADORIAS,
                    N.SAI_DESC AS DESCONTO,
                    N.SAI_TOTAL AS TOTAL,
                    N.SAI_RECEB AS RECEBIDO,
                    N.SAI_TROCO AS TROCO,
                    N.SAI_CHAVE AS CHAVE,
                    N.SAI_PROTOC AS PROTOCOLO,
                    N.SAI_AUTORI AS AUTORIZACAO,
                    N.SAI_CANCEL AS CANCELADA,
                    N.SAI_DENEGADO AS DENEGADA,
                    N.SAI_DPECPEND AS CONTINGENCIA_PENDENTE,
                    N.SAI_PROCESSAMENTO AS PROCESSAMENTO,
                    N.SAI_MOTCANC AS MOTIVO_CANCELAMENTO
                FROM DSIAF036 N
                WHERE (CAST(:serie AS VARCHAR(3)) IS NULL OR N.SAI_SER = :serie)
                  AND (CAST(:numero AS INTEGER) IS NULL OR N.SAI_PED = :numero)
                  AND (CAST(:chave AS VARCHAR(44)) IS NULL OR N.SAI_CHAVE = :chave)
                  AND (CAST(:cliente AS INTEGER) IS NULL OR N.CLI_COD = :cliente)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR N.SAI_DATA >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR N.SAI_DATA <= :data_final)
                ORDER BY N.SAI_DATA DESC, N.SAI_SER, N.SAI_PED DESC
            """.strip(),
            required_tables=("DSIAF036",),
            required_fields={
                "DSIAF036": (
                    "SAI_SER",
                    "SAI_PED",
                    "SAI_DATA",
                    "SAI_HORA",
                    "SAI_MOD",
                    "CFOP_COD",
                    "CLI_COD",
                    "CLI_NOME",
                    "CLI_CPF",
                    "CLI_CGC",
                    "SAI_MERC",
                    "SAI_DESC",
                    "SAI_TOTAL",
                    "SAI_RECEB",
                    "SAI_TROCO",
                    "SAI_CHAVE",
                    "SAI_PROTOC",
                    "SAI_AUTORI",
                    "SAI_CANCEL",
                    "SAI_DENEGADO",
                    "SAI_DPECPEND",
                    "SAI_PROCESSAMENTO",
                    "SAI_MOTCANC",
                )
            },
            parameters_schema={
                "serie": _search_parameter("Série"),
                "numero": _search_parameter("Número", "integer"),
                "chave": _search_parameter("Chave da NF-e"),
                "cliente": _search_parameter("Código do cliente", "integer"),
                "data_inicial": _period_parameter("Data inicial (DD/MM/AAAA)", "start"),
                "data_final": _period_parameter("Data final (DD/MM/AAAA)", "end"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=source,
            result_limit=500,
        ),
        QueryTemplate(
            name="NF-e — itens da saída",
            module="Fiscal",
            description=(
                "Pesquisa até 500 itens de saída vinculados ao cabeçalho real por série e número."
            ),
            sql_template="""
                SELECT FIRST 501
                    I.SAI_SER AS SERIE,
                    I.SAI_PED AS NUMERO,
                    N.SAI_DATA AS DATA,
                    N.SAI_CHAVE AS CHAVE,
                    N.CLI_COD AS CLIENTE_CODIGO,
                    N.CLI_NOME AS CLIENTE_NOME,
                    I.LIS_COD AS ITEM,
                    I.PRO_COD AS PRODUTO_CODIGO,
                    I.PRO_BARRA AS CODIGO_BARRAS,
                    I.PRO_NOME AS PRODUTO_NOME,
                    I.PRO_UNI AS UNIDADE,
                    I.PRO_SAI AS PRO_SAI,
                    I.PRO_VENDAITEM AS PRECO_ITEM,
                    I.PRO_DESCITEM AS DESCONTO_ITEM,
                    I.PRO_VDESC AS VALOR_DESCONTO,
                    I.CFOP_COD AS CFOP,
                    I.PRO_CSOSN AS CSOSN,
                    I.PRO_ST2 AS CST_ICMS,
                    I.PRO_STPIS2 AS CST_PIS,
                    I.PRO_STCOFINS2 AS CST_COFINS,
                    I.PRO_CEST AS CEST,
                    I.SAI_CANCEL AS ITEM_CANCELADO,
                    I.SAI_DENEGADO AS ITEM_DENEGADO
                FROM DSIAF037 I
                JOIN DSIAF036 N
                  ON N.SAI_SER = I.SAI_SER AND N.SAI_PED = I.SAI_PED
                WHERE (CAST(:serie AS VARCHAR(3)) IS NULL OR I.SAI_SER = :serie)
                  AND (CAST(:numero AS INTEGER) IS NULL OR I.SAI_PED = :numero)
                  AND (CAST(:produto AS INTEGER) IS NULL OR I.PRO_COD = :produto)
                  AND (CAST(:barra AS VARCHAR(20)) IS NULL OR I.PRO_BARRA = :barra)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR I.SAI_DATA >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR I.SAI_DATA <= :data_final)
                ORDER BY I.SAI_DATA DESC, I.SAI_SER, I.SAI_PED DESC, I.LIS_COD
            """.strip(),
            required_tables=("DSIAF037", "DSIAF036"),
            required_fields={
                "DSIAF036": (
                    "SAI_SER",
                    "SAI_PED",
                    "SAI_DATA",
                    "SAI_CHAVE",
                    "CLI_COD",
                    "CLI_NOME",
                ),
                "DSIAF037": (
                    "SAI_SER",
                    "SAI_PED",
                    "SAI_DATA",
                    "LIS_COD",
                    "PRO_COD",
                    "PRO_BARRA",
                    "PRO_NOME",
                    "PRO_UNI",
                    "PRO_SAI",
                    "PRO_VENDAITEM",
                    "PRO_DESCITEM",
                    "PRO_VDESC",
                    "CFOP_COD",
                    "PRO_CSOSN",
                    "PRO_ST2",
                    "PRO_STPIS2",
                    "PRO_STCOFINS2",
                    "PRO_CEST",
                    "SAI_CANCEL",
                    "SAI_DENEGADO",
                ),
            },
            parameters_schema={
                "serie": _search_parameter("Série"),
                "numero": _search_parameter("Número", "integer"),
                "produto": _search_parameter("Código do produto", "integer"),
                "barra": _search_parameter("Código de barras"),
                "data_inicial": _period_parameter("Data inicial (DD/MM/AAAA)", "start"),
                "data_final": _period_parameter("Data final (DD/MM/AAAA)", "end"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=source,
            result_limit=500,
        ),
        QueryTemplate(
            name="Entradas — notas de fornecedor",
            module="Entradas",
            description=(
                "Pesquisa até 500 entradas por nota, fornecedor, série, chave ou período."
            ),
            sql_template="""
                SELECT FIRST 501
                    E.ENT_NOTA AS NOTA,
                    E.FOR_COD AS FORNECEDOR_CODIGO,
                    E.ENT_SER AS SERIE,
                    E.ENT_EMIS AS EMISSAO,
                    E.ENT_DATA AS ENTRADA,
                    E.ENT_HORA AS HORA,
                    E.ENT_MOD AS MODELO,
                    E.CFOP_COD AS CFOP,
                    E.ENT_TOT AS TOTAL,
                    E.ENT_CHAVE AS CHAVE,
                    E.ENT_NC AS ENT_NC,
                    E.ENT_CONTA AS ENT_CONTA,
                    E.ENT_PREST AS PRESTACOES,
                    E.ENT_CAD AS CADASTRO
                FROM DSIAF011 E
                WHERE (CAST(:nota AS INTEGER) IS NULL OR E.ENT_NOTA = :nota)
                  AND (CAST(:fornecedor AS INTEGER) IS NULL OR E.FOR_COD = :fornecedor)
                  AND (CAST(:serie AS VARCHAR(3)) IS NULL OR E.ENT_SER = :serie)
                  AND (CAST(:chave AS VARCHAR(44)) IS NULL OR E.ENT_CHAVE = :chave)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR E.ENT_DATA >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR E.ENT_DATA <= :data_final)
                ORDER BY E.ENT_DATA DESC, E.ENT_NOTA DESC, E.FOR_COD
            """.strip(),
            required_tables=("DSIAF011",),
            required_fields={
                "DSIAF011": (
                    "ENT_NOTA",
                    "FOR_COD",
                    "ENT_SER",
                    "ENT_EMIS",
                    "ENT_DATA",
                    "ENT_HORA",
                    "ENT_MOD",
                    "CFOP_COD",
                    "ENT_TOT",
                    "ENT_CHAVE",
                    "ENT_NC",
                    "ENT_CONTA",
                    "ENT_PREST",
                    "ENT_CAD",
                )
            },
            parameters_schema={
                "nota": _search_parameter("Número da nota", "integer"),
                "fornecedor": _search_parameter("Código do fornecedor", "integer"),
                "serie": _search_parameter("Série"),
                "chave": _search_parameter("Chave da NF-e"),
                "data_inicial": _period_parameter("Data inicial (DD/MM/AAAA)", "start"),
                "data_final": _period_parameter("Data final (DD/MM/AAAA)", "end"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=source,
            result_limit=500,
        ),
        QueryTemplate(
            name="Entradas — itens da nota",
            module="Entradas",
            description=(
                "Pesquisa até 500 itens vinculados à entrada por nota e fornecedor."
            ),
            sql_template="""
                SELECT FIRST 501
                    I.ENT_NOTA AS NOTA,
                    I.FOR_COD AS FORNECEDOR_CODIGO,
                    E.ENT_SER AS SERIE,
                    E.ENT_CHAVE AS CHAVE,
                    I.ENT_DATA AS ENTRADA,
                    I.LIS_COD AS ITEM,
                    I.PRO_COD AS PRODUTO_CODIGO,
                    I.PRO_REF AS REFERENCIA,
                    I.PRO_BARRA AS CODIGO_BARRAS,
                    I.PRO_NOME AS PRODUTO_NOME,
                    I.PRO_UNI AS UNIDADE,
                    I.PRO_ENT AS PRO_ENT,
                    I.PRO_COMPRA AS PRECO_COMPRA,
                    I.PRO_COMPRAITEM AS PRECO_ITEM,
                    I.PRO_DESCITEM AS DESCONTO_ITEM,
                    I.PRO_CUSTOANT AS CUSTO_ANTERIOR,
                    I.PRO_CUSTO AS CUSTO,
                    I.PRO_MEDIO AS CUSTO_MEDIO,
                    I.PRO_ATUAL AS PRO_ATUAL,
                    I.CFOP_COD AS CFOP,
                    I.PRO_NCM AS NCM,
                    I.PRO_CSOSN AS CSOSN,
                    I.PRO_ST2 AS CST_ICMS
                FROM DSIAF012 I
                JOIN DSIAF011 E
                  ON E.ENT_NOTA = I.ENT_NOTA AND E.FOR_COD = I.FOR_COD
                WHERE (CAST(:nota AS INTEGER) IS NULL OR I.ENT_NOTA = :nota)
                  AND (CAST(:fornecedor AS INTEGER) IS NULL OR I.FOR_COD = :fornecedor)
                  AND (CAST(:produto AS INTEGER) IS NULL OR I.PRO_COD = :produto)
                  AND (CAST(:barra AS VARCHAR(20)) IS NULL OR I.PRO_BARRA = :barra)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR I.ENT_DATA >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR I.ENT_DATA <= :data_final)
                ORDER BY I.ENT_DATA DESC, I.ENT_NOTA DESC, I.FOR_COD, I.LIS_COD
            """.strip(),
            required_tables=("DSIAF012", "DSIAF011"),
            required_fields={
                "DSIAF011": ("ENT_NOTA", "FOR_COD", "ENT_SER", "ENT_CHAVE"),
                "DSIAF012": (
                    "ENT_NOTA",
                    "FOR_COD",
                    "ENT_DATA",
                    "LIS_COD",
                    "PRO_COD",
                    "PRO_REF",
                    "PRO_BARRA",
                    "PRO_NOME",
                    "PRO_UNI",
                    "PRO_ENT",
                    "PRO_COMPRA",
                    "PRO_COMPRAITEM",
                    "PRO_DESCITEM",
                    "PRO_CUSTOANT",
                    "PRO_CUSTO",
                    "PRO_MEDIO",
                    "PRO_ATUAL",
                    "CFOP_COD",
                    "PRO_NCM",
                    "PRO_CSOSN",
                    "PRO_ST2",
                ),
            },
            parameters_schema={
                "nota": _search_parameter("Número da nota", "integer"),
                "fornecedor": _search_parameter("Código do fornecedor", "integer"),
                "produto": _search_parameter("Código do produto", "integer"),
                "barra": _search_parameter("Código de barras"),
                "data_inicial": _period_parameter("Data inicial (DD/MM/AAAA)", "start"),
                "data_final": _period_parameter("Data final (DD/MM/AAAA)", "end"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=source,
            result_limit=500,
        ),
        QueryTemplate(
            name="PDV — vendas e NFC-e",
            module="PDV",
            description=(
                "Pesquisa até 500 vendas de PDV por ID, chave, cliente, terminal, "
                "status ou período."
            ),
            sql_template="""
                SELECT FIRST 501
                    V.ID AS PDV_ID,
                    V.PDV_DATA AS DATA,
                    V.PDV_HORA AS HORA,
                    V.TERMINAL AS TERMINAL,
                    V.PDV_STATUS AS STATUS,
                    V.SAI_CANCEL AS CANCELADA,
                    V.PDV_CHAVE AS CHAVE,
                    V.CLI_COD AS CLIENTE_CODIGO,
                    V.CLI_NOME AS CLIENTE_NOME,
                    V.PDV_MERC AS MERCADORIAS,
                    V.PDV_DESC AS DESCONTO,
                    V.PDV_TOTAL AS TOTAL,
                    V.PDV_RECEB AS RECEBIDO,
                    V.PDV_TROCO AS TROCO,
                    V.CAI_COD AS CAIXA,
                    V.USU_COD AS USUARIO,
                    V.VEN_COD AS VENDEDOR,
                    V.SAI_SERIE AS SERIE_SAIDA,
                    V.SAI_NOTA AS NOTA_SAIDA,
                    V.PDV_IMPORTADO AS IMPORTADO,
                    V.PDV_INFO AS INFORMACAO
                FROM DSIAF400 V
                WHERE (CAST(:pdv_id AS INTEGER) IS NULL OR V.ID = :pdv_id)
                  AND (CAST(:chave AS VARCHAR(200)) IS NULL OR V.PDV_CHAVE CONTAINING :chave)
                  AND (CAST(:cliente AS INTEGER) IS NULL OR V.CLI_COD = :cliente)
                  AND (CAST(:terminal AS VARCHAR(200)) IS NULL OR V.TERMINAL = :terminal)
                  AND (CAST(:status AS VARCHAR(1)) IS NULL OR V.PDV_STATUS = :status)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR V.PDV_DATA >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR V.PDV_DATA <= :data_final)
                ORDER BY V.ID DESC
            """.strip(),
            required_tables=("DSIAF400",),
            required_fields={
                "DSIAF400": (
                    "ID",
                    "PDV_DATA",
                    "PDV_HORA",
                    "TERMINAL",
                    "PDV_STATUS",
                    "SAI_CANCEL",
                    "PDV_CHAVE",
                    "CLI_COD",
                    "CLI_NOME",
                    "PDV_MERC",
                    "PDV_DESC",
                    "PDV_TOTAL",
                    "PDV_RECEB",
                    "PDV_TROCO",
                    "CAI_COD",
                    "USU_COD",
                    "VEN_COD",
                    "SAI_SERIE",
                    "SAI_NOTA",
                    "PDV_IMPORTADO",
                    "PDV_INFO",
                )
            },
            parameters_schema={
                "pdv_id": _search_parameter("ID do PDV", "integer"),
                "chave": _search_parameter("Chave da NFC-e contém"),
                "cliente": _search_parameter("Código do cliente", "integer"),
                "terminal": _search_parameter("Terminal"),
                "status": _search_parameter("Status armazenado"),
                "data_inicial": _period_parameter(
                    "Data inicial (DD/MM/AAAA)",
                    "start",
                    require_complete=True,
                ),
                "data_final": _period_parameter(
                    "Data final (DD/MM/AAAA)",
                    "end",
                    require_complete=True,
                ),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=source,
            result_limit=500,
        ),
        QueryTemplate(
            name="PDV — itens da venda",
            module="PDV",
            description="Pesquisa até 500 itens vinculados ao cabeçalho do PDV por ID/PDV_COD.",
            sql_template="""
                SELECT FIRST 501
                    V.ID AS PDV_ID,
                    V.PDV_DATA AS DATA,
                    V.PDV_HORA AS HORA,
                    V.TERMINAL AS TERMINAL,
                    V.PDV_STATUS AS STATUS,
                    V.PDV_CHAVE AS CHAVE,
                    I.ID AS ITEM_ID,
                    I.PDV_ITEM_ORDER AS ORDEM_ITEM,
                    I.PRO_COD AS PRODUTO_CODIGO,
                    I.PRO_BARRA AS CODIGO_BARRAS,
                    I.PRO_NOME AS PRODUTO_NOME,
                    I.PRO_UNI AS UNIDADE,
                    I.PDV_ITEM_QUANT AS QUANTIDADE,
                    I.PRO_VENDAITEM AS PRECO_ITEM,
                    I.PRO_DESCITEM AS DESCONTO_ITEM,
                    I.PRO_VDESC AS VALOR_DESCONTO,
                    I.CFOP_COD AS CFOP,
                    I.PRO_CSOSN AS CSOSN,
                    I.PRO_ST2 AS CST_ICMS,
                    I.PDV_ITEM_CANCELADO AS ITEM_CANCELADO
                FROM DSIAF401 I
                JOIN DSIAF400 V ON V.ID = I.PDV_COD
                WHERE (CAST(:pdv_id AS INTEGER) IS NULL OR V.ID = :pdv_id)
                  AND (CAST(:produto AS INTEGER) IS NULL OR I.PRO_COD = :produto)
                  AND (CAST(:barra AS VARCHAR(20)) IS NULL OR I.PRO_BARRA = :barra)
                  AND (CAST(:terminal AS VARCHAR(200)) IS NULL OR V.TERMINAL = :terminal)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR V.PDV_DATA >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR V.PDV_DATA <= :data_final)
                ORDER BY V.ID DESC, I.PDV_ITEM_ORDER, I.ID
            """.strip(),
            required_tables=("DSIAF401", "DSIAF400"),
            required_fields={
                "DSIAF400": (
                    "ID",
                    "PDV_DATA",
                    "PDV_HORA",
                    "TERMINAL",
                    "PDV_STATUS",
                    "PDV_CHAVE",
                ),
                "DSIAF401": (
                    "ID",
                    "PDV_COD",
                    "PDV_ITEM_ORDER",
                    "PRO_COD",
                    "PRO_BARRA",
                    "PRO_NOME",
                    "PRO_UNI",
                    "PDV_ITEM_QUANT",
                    "PRO_VENDAITEM",
                    "PRO_DESCITEM",
                    "PRO_VDESC",
                    "CFOP_COD",
                    "PRO_CSOSN",
                    "PRO_ST2",
                    "PDV_ITEM_CANCELADO",
                ),
            },
            parameters_schema={
                "pdv_id": _search_parameter("ID do PDV", "integer"),
                "produto": _search_parameter("Código do produto", "integer"),
                "barra": _search_parameter("Código de barras"),
                "terminal": _search_parameter("Terminal"),
                "data_inicial": _period_parameter(
                    "Data inicial (DD/MM/AAAA)",
                    "start",
                    require_complete=True,
                ),
                "data_final": _period_parameter(
                    "Data final (DD/MM/AAAA)",
                    "end",
                    require_complete=True,
                ),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=source,
            result_limit=500,
        ),
        QueryTemplate(
            name="PDV — pagamentos da venda",
            module="PDV",
            description=(
                "Pesquisa até 500 registros financeiros vinculados ao PDV por ID/PDV_COD."
            ),
            sql_template="""
                SELECT FIRST 501
                    V.ID AS PDV_ID,
                    V.PDV_DATA AS DATA_VENDA,
                    V.TERMINAL AS TERMINAL,
                    V.PDV_STATUS AS STATUS,
                    V.PDV_TOTAL AS TOTAL_VENDA,
                    P.ID AS PAGAMENTO_ID,
                    P.PDV_PREST_DATA AS DATA_PAGAMENTO,
                    P.PDV_PREST_VAL AS VALOR,
                    P.CLI_COD AS CLIENTE_CODIGO,
                    P.TIP_COD AS TIPO_CODIGO,
                    P.BAN_COD AS BANCO_CODIGO,
                    P.PDV_PREST_TEFAUT AS AUTORIZACAO_TEF,
                    P.REC_TEF AS REC_TEF,
                    P.TEF_CONFIRMADO AS TEF_CONFIRMADO,
                    P.TEF_CONTROLE AS TEF_CONTROLE,
                    P.PRA_IDPAGTO AS IDENTIFICADOR_PAGAMENTO,
                    P.PRA_BANDCARTAO AS BANDEIRA_CARTAO,
                    P.CAI_COD AS CAIXA,
                    P.USU_COD AS USUARIO,
                    P.VEN_COD AS VENDEDOR,
                    P.PDV_PREST_ALTERADO AS PAGAMENTO_ALTERADO
                FROM DSIAF402 P
                JOIN DSIAF400 V ON V.ID = P.PDV_COD
                WHERE (CAST(:pdv_id AS INTEGER) IS NULL OR V.ID = :pdv_id)
                  AND (CAST(:tipo AS INTEGER) IS NULL OR P.TIP_COD = :tipo)
                  AND (CAST(:tef_confirmado AS VARCHAR(1)) IS NULL
                       OR P.TEF_CONFIRMADO = :tef_confirmado)
                  AND (CAST(:terminal AS VARCHAR(200)) IS NULL OR V.TERMINAL = :terminal)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR P.PDV_PREST_DATA >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL
                       OR P.PDV_PREST_DATA <= :data_final)
                ORDER BY P.ID DESC
            """.strip(),
            required_tables=("DSIAF402", "DSIAF400"),
            required_fields={
                "DSIAF400": (
                    "ID",
                    "PDV_DATA",
                    "TERMINAL",
                    "PDV_STATUS",
                    "PDV_TOTAL",
                ),
                "DSIAF402": (
                    "ID",
                    "PDV_COD",
                    "PDV_PREST_DATA",
                    "PDV_PREST_VAL",
                    "CLI_COD",
                    "TIP_COD",
                    "BAN_COD",
                    "PDV_PREST_TEFAUT",
                    "REC_TEF",
                    "TEF_CONFIRMADO",
                    "TEF_CONTROLE",
                    "PRA_IDPAGTO",
                    "PRA_BANDCARTAO",
                    "CAI_COD",
                    "USU_COD",
                    "VEN_COD",
                    "PDV_PREST_ALTERADO",
                ),
            },
            parameters_schema={
                "pdv_id": _search_parameter("ID do PDV", "integer"),
                "tipo": _search_parameter("Código do tipo", "integer"),
                "tef_confirmado": _search_parameter("TEF confirmado (valor armazenado)"),
                "terminal": _search_parameter("Terminal"),
                "data_inicial": _period_parameter(
                    "Data inicial do pagamento (DD/MM/AAAA)",
                    "start",
                    require_complete=True,
                ),
                "data_final": _period_parameter(
                    "Data final do pagamento (DD/MM/AAAA)",
                    "end",
                    require_complete=True,
                ),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=source,
            result_limit=500,
        ),
    )


def _phase_nine_templates() -> tuple[QueryTemplate, ...]:
    loja_source = "Snapshot real SIAFLOJA.FDB e índices inspecionados em 2026-07-19"
    siafw_source = "Snapshot real SIAFW.FDB e índices inspecionados em 2026-07-19"
    return (
        QueryTemplate(
            name="Contas a receber — títulos e baixas",
            module="Financeiro",
            description=(
                "Pesquisa até 500 títulos a receber pelos valores armazenados, sem inferir "
                "situação financeira automaticamente."
            ),
            sql_template="""
                SELECT FIRST 501
                    R.REC_DUP AS DUPLICATA,
                    R.REC_BAN AS BANCO_DOCUMENTO,
                    R.CLI_COD AS CLIENTE_CODIGO,
                    R.CLI_NOME AS CLIENTE_NOME,
                    R.REC_HIST AS HISTORICO,
                    R.REC_LANC AS LANCAMENTO,
                    R.REC_VENC AS VENCIMENTO,
                    R.REC_BRUTO AS VALOR_BRUTO,
                    R.REC_DESC AS DESCONTO,
                    R.REC_VAL AS VALOR,
                    R.REC_DPAG AS DATA_PAGAMENTO,
                    R.REC_DIAS AS DIAS,
                    R.REC_JUROS AS JUROS,
                    R.REC_MULTA AS MULTA,
                    R.REC_PAG AS VALOR_PAGO,
                    R.REC_RECEB AS RECEBIDO,
                    R.REC_TROCO AS TROCO,
                    R.SAI_SER AS SERIE_SAIDA,
                    R.SAI_NOTA AS NOTA_SAIDA,
                    R.PRA_COD AS TIPO_VENDA,
                    R.TIP_COD AS TIPO_PAGAMENTO,
                    R.CAI_COD AS CAIXA,
                    R.ATU_USUA AS ATUALIZADO_POR
                FROM DSIAF015 R
                WHERE (CAST(:duplicata AS VARCHAR(16)) IS NULL OR R.REC_DUP = :duplicata)
                  AND (CAST(:cliente AS INTEGER) IS NULL OR R.CLI_COD = :cliente)
                  AND (CAST(:serie AS VARCHAR(3)) IS NULL OR R.SAI_SER = :serie)
                  AND (CAST(:nota AS INTEGER) IS NULL OR R.SAI_NOTA = :nota)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR R.REC_VENC >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR R.REC_VENC <= :data_final)
                ORDER BY R.REC_DUP DESC
            """.strip(),
            required_tables=("DSIAF015",),
            required_fields={
                "DSIAF015": (
                    "REC_DUP",
                    "REC_BAN",
                    "CLI_COD",
                    "CLI_NOME",
                    "REC_HIST",
                    "REC_LANC",
                    "REC_VENC",
                    "REC_BRUTO",
                    "REC_DESC",
                    "REC_VAL",
                    "REC_DPAG",
                    "REC_DIAS",
                    "REC_JUROS",
                    "REC_MULTA",
                    "REC_PAG",
                    "REC_RECEB",
                    "REC_TROCO",
                    "SAI_SER",
                    "SAI_NOTA",
                    "PRA_COD",
                    "TIP_COD",
                    "CAI_COD",
                    "ATU_USUA",
                )
            },
            parameters_schema={
                "duplicata": _search_parameter("Duplicata"),
                "cliente": _search_parameter("Código do cliente", "integer"),
                "serie": _search_parameter("Série da saída"),
                "nota": _search_parameter("Número da saída", "integer"),
                "data_inicial": _period_parameter(
                    "Vencimento inicial (DD/MM/AAAA)", "start"
                ),
                "data_final": _period_parameter(
                    "Vencimento final (DD/MM/AAAA)", "end"
                ),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=loja_source,
            result_limit=500,
        ),
        QueryTemplate(
            name="Contas a pagar — títulos e baixas",
            module="Financeiro",
            description=(
                "Pesquisa até 500 títulos a pagar pelos valores armazenados, sem inferir "
                "situação financeira automaticamente."
            ),
            sql_template="""
                SELECT FIRST 501
                    P.PAG_NUM AS PAGAMENTO_NUMERO,
                    P.PAG_DUP AS DUPLICATA,
                    P.PAG_TIPO AS TIPO_REGISTRO,
                    P.FOR_COD AS FORNECEDOR_CODIGO,
                    P.CEN_COD AS CENTRO_CUSTO,
                    P.PAG_HIST AS HISTORICO,
                    P.PAG_LANC AS LANCAMENTO,
                    P.PAG_VENC AS VENCIMENTO,
                    P.PAG_BRUTO AS VALOR_BRUTO,
                    P.PAG_DESC AS DESCONTO,
                    P.PAG_VAL AS VALOR,
                    P.PAG_DPAG AS DATA_PAGAMENTO,
                    P.PAG_JUROS AS JUROS,
                    P.PAG_PAG AS VALOR_PAGO,
                    P.ENT_NOTA AS NOTA_ENTRADA,
                    P.ENT_FOR AS FORNECEDOR_ENTRADA,
                    P.PRA_COD AS PRA_COD,
                    P.CAI_COD AS CAIXA,
                    P.ATU_USUA AS ATUALIZADO_POR
                FROM DSIAF016 P
                WHERE (CAST(:numero AS INTEGER) IS NULL OR P.PAG_NUM = :numero)
                  AND (CAST(:duplicata AS VARCHAR(16)) IS NULL OR P.PAG_DUP = :duplicata)
                  AND (CAST(:fornecedor AS INTEGER) IS NULL OR P.FOR_COD = :fornecedor)
                  AND (CAST(:entrada AS INTEGER) IS NULL OR P.ENT_NOTA = :entrada)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR P.PAG_VENC >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR P.PAG_VENC <= :data_final)
                ORDER BY P.PAG_NUM DESC
            """.strip(),
            required_tables=("DSIAF016",),
            required_fields={
                "DSIAF016": (
                    "PAG_NUM",
                    "PAG_DUP",
                    "PAG_TIPO",
                    "FOR_COD",
                    "CEN_COD",
                    "PAG_HIST",
                    "PAG_LANC",
                    "PAG_VENC",
                    "PAG_BRUTO",
                    "PAG_DESC",
                    "PAG_VAL",
                    "PAG_DPAG",
                    "PAG_JUROS",
                    "PAG_PAG",
                    "ENT_NOTA",
                    "ENT_FOR",
                    "PRA_COD",
                    "CAI_COD",
                    "ATU_USUA",
                )
            },
            parameters_schema={
                "numero": _search_parameter("Número interno", "integer"),
                "duplicata": _search_parameter("Duplicata"),
                "fornecedor": _search_parameter("Código do fornecedor", "integer"),
                "entrada": _search_parameter("Número da entrada", "integer"),
                "data_inicial": _period_parameter(
                    "Vencimento inicial (DD/MM/AAAA)", "start"
                ),
                "data_final": _period_parameter(
                    "Vencimento final (DD/MM/AAAA)", "end"
                ),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=loja_source,
            result_limit=500,
        ),
        QueryTemplate(
            name="Caixa diário — cabeçalhos",
            module="Caixa",
            description="Pesquisa até 500 posições diárias de caixa por caixa, turno ou período.",
            sql_template="""
                SELECT FIRST 501
                    C.CAI_DATA AS DATA,
                    C.CAI_COD AS CAIXA,
                    C.CAI_TURNO AS TURNO,
                    C.CAI_ANT AS SALDO_ANTERIOR,
                    C.CAI_ATU AS SALDO_ATUAL,
                    C.CAI_FEC AS FECHAMENTO,
                    C.CAI_CAD AS CADASTRO,
                    C.ATU_USUA AS ATUALIZADO_POR
                FROM DSIAF017 C
                WHERE (CAST(:caixa AS INTEGER) IS NULL OR C.CAI_COD = :caixa)
                  AND (CAST(:turno AS VARCHAR(1)) IS NULL OR C.CAI_TURNO = :turno)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR C.CAI_DATA >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR C.CAI_DATA <= :data_final)
                ORDER BY C.CAI_DATA DESC, C.CAI_COD, C.CAI_TURNO
            """.strip(),
            required_tables=("DSIAF017",),
            required_fields={
                "DSIAF017": (
                    "CAI_DATA",
                    "CAI_COD",
                    "CAI_TURNO",
                    "CAI_ANT",
                    "CAI_ATU",
                    "CAI_FEC",
                    "CAI_CAD",
                    "ATU_USUA",
                )
            },
            parameters_schema={
                "caixa": _search_parameter("Código do caixa", "integer"),
                "turno": _search_parameter("Turno armazenado"),
                "data_inicial": _period_parameter("Data inicial (DD/MM/AAAA)", "start"),
                "data_final": _period_parameter("Data final (DD/MM/AAAA)", "end"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=loja_source,
            result_limit=500,
        ),
        QueryTemplate(
            name="Caixa diário — lançamentos",
            module="Caixa",
            description=(
                "Pesquisa até 500 lançamentos de caixa e exibe seus vínculos armazenados."
            ),
            sql_template="""
                SELECT FIRST 501
                    L.CAI_DATA AS DATA,
                    L.CAI_COD AS CAIXA,
                    L.CAI_TURNO AS TURNO,
                    L.LIS_COD AS ITEM,
                    L.CAI_HIST AS HISTORICO,
                    L.CAI_ENT AS ENTRADA,
                    L.CAI_SAI AS SAIDA,
                    L.CEN_COD AS CENTRO_CUSTO,
                    L.REC_DUP2 AS DUPLICATA_RECEBER,
                    L.PAG_NUM2 AS PAGAMENTO_NUMERO,
                    L.TRANS_COD AS TRANSFERENCIA,
                    L.VEN_COD AS VENDEDOR,
                    L.VEN_NUM AS VENDA,
                    L.PROF_COD AS PROFISSIONAL,
                    L.CAI_NUM AS NUMERO_CAIXA,
                    L.ATU_USUA AS ATUALIZADO_POR
                FROM DSIAF018 L
                WHERE (CAST(:caixa AS INTEGER) IS NULL OR L.CAI_COD = :caixa)
                  AND (CAST(:turno AS VARCHAR(1)) IS NULL OR L.CAI_TURNO = :turno)
                  AND (CAST(:duplicata AS VARCHAR(16)) IS NULL
                       OR L.REC_DUP2 = :duplicata)
                  AND (CAST(:pagamento AS INTEGER) IS NULL OR L.PAG_NUM2 = :pagamento)
                  AND (CAST(:transferencia AS INTEGER) IS NULL
                       OR L.TRANS_COD = :transferencia)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR L.CAI_DATA >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR L.CAI_DATA <= :data_final)
                ORDER BY L.CAI_DATA DESC, L.CAI_COD, L.CAI_TURNO, L.LIS_COD
            """.strip(),
            required_tables=("DSIAF018",),
            required_fields={
                "DSIAF018": (
                    "CAI_DATA",
                    "CAI_COD",
                    "CAI_TURNO",
                    "LIS_COD",
                    "CAI_HIST",
                    "CAI_ENT",
                    "CAI_SAI",
                    "CEN_COD",
                    "REC_DUP2",
                    "PAG_NUM2",
                    "TRANS_COD",
                    "VEN_COD",
                    "VEN_NUM",
                    "PROF_COD",
                    "CAI_NUM",
                    "ATU_USUA",
                )
            },
            parameters_schema={
                "caixa": _search_parameter("Código do caixa", "integer"),
                "turno": _search_parameter("Turno armazenado"),
                "duplicata": _search_parameter("Duplicata a receber"),
                "pagamento": _search_parameter("Número a pagar", "integer"),
                "transferencia": _search_parameter("Código da transferência", "integer"),
                "data_inicial": _period_parameter("Data inicial (DD/MM/AAAA)", "start"),
                "data_final": _period_parameter("Data final (DD/MM/AAAA)", "end"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=loja_source,
            result_limit=500,
        ),
        QueryTemplate(
            name="Caixa diário — transferências",
            module="Caixa",
            description=(
                "Pesquisa até 500 transferências entre caixas pelos valores armazenados."
            ),
            sql_template="""
                SELECT FIRST 501
                    T.TRANS_COD AS TRANSFERENCIA,
                    T.CAI_COD AS CAIXA_ORIGEM,
                    T.CAI_DATA AS DATA_ORIGEM,
                    T.CAI_HIST AS HISTORICO_ORIGEM,
                    T.CAI_VAL AS VALOR,
                    T.CEN_COD AS CENTRO_CUSTO,
                    T.CAI_COD2 AS CAIXA_DESTINO,
                    T.CAI_DATA2 AS DATA_DESTINO,
                    T.CAI_HIST2 AS HISTORICO_DESTINO,
                    T.ATU_USUA AS ATUALIZADO_POR
                FROM DSIAF136 T
                WHERE (CAST(:transferencia AS INTEGER) IS NULL
                       OR T.TRANS_COD = :transferencia)
                  AND (CAST(:caixa_origem AS INTEGER) IS NULL
                       OR T.CAI_COD = :caixa_origem)
                  AND (CAST(:caixa_destino AS INTEGER) IS NULL
                       OR T.CAI_COD2 = :caixa_destino)
                  AND (CAST(:usuario AS VARCHAR(80)) IS NULL
                       OR T.ATU_USUA CONTAINING :usuario)
                  AND (CAST(:data_inicial AS DATE) IS NULL
                       OR T.CAI_DATA >= :data_inicial)
                  AND (CAST(:data_final AS DATE) IS NULL OR T.CAI_DATA <= :data_final)
                ORDER BY T.TRANS_COD DESC
            """.strip(),
            required_tables=("DSIAF136",),
            required_fields={
                "DSIAF136": (
                    "TRANS_COD",
                    "CAI_COD",
                    "CAI_DATA",
                    "CAI_HIST",
                    "CAI_VAL",
                    "CEN_COD",
                    "CAI_COD2",
                    "CAI_DATA2",
                    "CAI_HIST2",
                    "ATU_USUA",
                )
            },
            parameters_schema={
                "transferencia": _search_parameter("Código da transferência", "integer"),
                "caixa_origem": _search_parameter("Caixa de origem", "integer"),
                "caixa_destino": _search_parameter("Caixa de destino", "integer"),
                "usuario": _search_parameter("Usuário contém"),
                "data_inicial": _period_parameter("Data inicial (DD/MM/AAAA)", "start"),
                "data_final": _period_parameter("Data final (DD/MM/AAAA)", "end"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=loja_source,
            result_limit=500,
        ),
        QueryTemplate(
            name="Tipos de venda",
            module="Financeiro",
            description=(
                "Pesquisa os tipos de venda e mostra o tipo de pagamento vinculado quando existe."
            ),
            sql_template="""
                SELECT FIRST 501
                    V.PRA_COD AS TIPO_VENDA_CODIGO,
                    V.PRA_DESC AS TIPO_VENDA_DESCRICAO,
                    V.PRA_PRES AS PRESTACOES,
                    V.PRA_PER AS PERIODICIDADE,
                    V.PRA_ENT AS ENTRADA,
                    V.PRA_JUR AS JUROS,
                    V.PRA_TEF AS TEF,
                    V.PRA_CARTAO AS CARTAO,
                    V.PRA_TPAGNFE AS PAGAMENTO_NFE,
                    V.TIP_COD AS TIPO_PAGAMENTO_CODIGO,
                    P.TIP_DESC AS TIPO_PAGAMENTO_DESCRICAO,
                    P.TIP_REC AS RECEBIMENTO,
                    P.TIP_QUI AS QUITACAO,
                    P.TIP_CHE AS CHEQUE,
                    P.TIP_BOL AS BOLETO,
                    P.TIP_EST AS ESTOQUE,
                    P.TIP_COMIS AS COMISSAO,
                    P.TIP_PROMIS AS PROMISSORIA,
                    P.TIP_LCRED AS LIMITE_CREDITO,
                    P.TIP_CARNE AS CARNE,
                    P.BAN_COD AS BANCO
                FROM DSIAF025 V
                LEFT JOIN DSIAF026 P ON P.TIP_COD = V.TIP_COD
                WHERE (CAST(:venda AS INTEGER) IS NULL OR V.PRA_COD = :venda)
                  AND (CAST(:venda_descricao AS VARCHAR(20)) IS NULL
                       OR V.PRA_DESC CONTAINING :venda_descricao)
                  AND (CAST(:pagamento AS INTEGER) IS NULL OR V.TIP_COD = :pagamento)
                ORDER BY V.PRA_COD
            """.strip(),
            required_tables=("DSIAF025", "DSIAF026"),
            required_fields={
                "DSIAF025": (
                    "PRA_COD",
                    "PRA_DESC",
                    "PRA_PRES",
                    "PRA_PER",
                    "PRA_ENT",
                    "PRA_JUR",
                    "PRA_TEF",
                    "PRA_CARTAO",
                    "PRA_TPAGNFE",
                    "TIP_COD",
                ),
                "DSIAF026": (
                    "TIP_COD",
                    "TIP_DESC",
                    "TIP_REC",
                    "TIP_QUI",
                    "TIP_CHE",
                    "TIP_BOL",
                    "TIP_EST",
                    "TIP_COMIS",
                    "TIP_PROMIS",
                    "TIP_LCRED",
                    "TIP_CARNE",
                    "BAN_COD",
                ),
            },
            parameters_schema={
                "venda": _search_parameter("Código do tipo de venda", "integer"),
                "venda_descricao": _search_parameter("Descrição da venda contém"),
                "pagamento": _search_parameter("Código do pagamento", "integer"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=loja_source,
            result_limit=500,
        ),
        QueryTemplate(
            name="Tipos de pagamento",
            module="Financeiro",
            description=(
                "Pesquisa o cadastro completo de tipos de pagamento pelos valores armazenados."
            ),
            sql_template="""
                SELECT FIRST 501
                    P.TIP_COD AS TIPO_PAGAMENTO_CODIGO,
                    P.TIP_DESC AS TIPO_PAGAMENTO_DESCRICAO,
                    P.TIP_REC AS RECEBIMENTO,
                    P.TIP_QUI AS QUITACAO,
                    P.TIP_QUI2 AS QUITACAO_2,
                    P.TIP_CHE AS CHEQUE,
                    P.TIP_BOL AS BOLETO,
                    P.TIP_EST AS ESTOQUE,
                    P.TIP_COMIS AS COMISSAO,
                    P.TIP_PROMIS AS PROMISSORIA,
                    P.TIP_LCRED AS LIMITE_CREDITO,
                    P.TIP_CARNE AS CARNE,
                    P.CEN_COD AS CENTRO_CUSTO,
                    P.CAI_COD AS CAIXA,
                    P.BAN_COD AS BANCO,
                    P.TIP_CAD AS CADASTRO,
                    P.ATU_USUA AS ATUALIZADO_POR
                FROM DSIAF026 P
                WHERE (CAST(:pagamento AS INTEGER) IS NULL OR P.TIP_COD = :pagamento)
                  AND (CAST(:descricao AS VARCHAR(20)) IS NULL
                       OR P.TIP_DESC CONTAINING :descricao)
                ORDER BY P.TIP_COD
            """.strip(),
            required_tables=("DSIAF026",),
            required_fields={
                "DSIAF026": (
                    "TIP_COD",
                    "TIP_DESC",
                    "TIP_REC",
                    "TIP_QUI",
                    "TIP_QUI2",
                    "TIP_CHE",
                    "TIP_BOL",
                    "TIP_EST",
                    "TIP_COMIS",
                    "TIP_PROMIS",
                    "TIP_LCRED",
                    "TIP_CARNE",
                    "CEN_COD",
                    "CAI_COD",
                    "BAN_COD",
                    "TIP_CAD",
                    "ATU_USUA",
                )
            },
            parameters_schema={
                "pagamento": _search_parameter("Código do pagamento", "integer"),
                "descricao": _search_parameter("Descrição do pagamento contém"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=loja_source,
            result_limit=500,
        ),
        QueryTemplate(
            name="Usuários e grupos",
            module="Permissões",
            description=(
                "Pesquisa usuários e seus grupos sem selecionar ou expor o campo de senha."
            ),
            sql_template="""
                SELECT FIRST 501
                    U.USU_COD AS USUARIO_CODIGO,
                    U.USU_NOME AS USUARIO_NOME,
                    U.GRU_USU AS GRUPO_CODIGO,
                    G.GRU_DUSU AS GRUPO_DESCRICAO,
                    U.USU_CAD AS USUARIO_CADASTRO,
                    U.ATU_USUA AS USUARIO_ATUALIZADO_POR,
                    G.GRU_CAD AS GRUPO_CADASTRO,
                    G.ATU_USUA AS GRUPO_ATUALIZADO_POR
                FROM DSIAF050 U
                LEFT JOIN DSIAF053 G ON G.GRU_USU = U.GRU_USU
                WHERE (CAST(:usuario AS INTEGER) IS NULL OR U.USU_COD = :usuario)
                  AND (CAST(:nome AS VARCHAR(30)) IS NULL OR U.USU_NOME CONTAINING :nome)
                  AND (CAST(:grupo AS INTEGER) IS NULL OR U.GRU_USU = :grupo)
                  AND (CAST(:grupo_descricao AS VARCHAR(30)) IS NULL
                       OR G.GRU_DUSU CONTAINING :grupo_descricao)
                ORDER BY U.USU_COD
            """.strip(),
            required_tables=("DSIAF050", "DSIAF053"),
            required_fields={
                "DSIAF050": (
                    "USU_COD",
                    "USU_NOME",
                    "GRU_USU",
                    "USU_CAD",
                    "ATU_USUA",
                ),
                "DSIAF053": ("GRU_USU", "GRU_DUSU", "GRU_CAD", "ATU_USUA"),
            },
            parameters_schema={
                "usuario": _search_parameter("Código do usuário", "integer"),
                "nome": _search_parameter("Nome do usuário contém"),
                "grupo": _search_parameter("Código do grupo", "integer"),
                "grupo_descricao": _search_parameter("Descrição do grupo contém"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=siafw_source,
            result_limit=500,
        ),
        QueryTemplate(
            name="Permissões — diagnóstico por usuário, grupo e programa",
            module="Permissões",
            description=(
                "Exibe acesso, inclusão, alteração, exclusão e impressão exatamente como "
                "armazenados, sem interpretar os códigos automaticamente. O filtro é "
                "obrigatório e o resultado não possui corte fixo de registros."
            ),
            sql_template="""
                SELECT
                    U.USU_COD AS USUARIO_CODIGO,
                    U.USU_NOME AS USUARIO_NOME,
                    P.GRU_USU AS GRUPO_CODIGO,
                    G.GRU_DUSU AS GRUPO_DESCRICAO,
                    P.PROG_MOD AS PROGRAMA_MODULO,
                    P.PROG_IND AS PROGRAMA_INDICE,
                    P.PROG_DESC AS PROGRAMA_DESCRICAO,
                    P.PROG_ACE AS ACESSO,
                    P.PROG_INC AS INCLUSAO,
                    P.PROG_ALT AS ALTERACAO,
                    P.PROG_EXC AS EXCLUSAO,
                    P.PROG_IMP AS IMPRESSAO
                FROM DSIAF051 P
                LEFT JOIN DSIAF053 G ON G.GRU_USU = P.GRU_USU
                LEFT JOIN DSIAF050 U
                  ON U.GRU_USU = P.GRU_USU
                 AND (
                     CAST(:usuario AS INTEGER) IS NOT NULL
                     OR CAST(:nome AS VARCHAR(30)) IS NOT NULL
                 )
                WHERE (CAST(:usuario AS INTEGER) IS NULL OR U.USU_COD = :usuario)
                  AND (CAST(:nome AS VARCHAR(30)) IS NULL OR U.USU_NOME CONTAINING :nome)
                  AND (CAST(:grupo AS INTEGER) IS NULL OR P.GRU_USU = :grupo)
                  AND (CAST(:programa AS VARCHAR(60)) IS NULL
                       OR P.PROG_DESC CONTAINING :programa)
                  AND (CAST(:modulo AS VARCHAR(2)) IS NULL OR P.PROG_MOD = :modulo)
                  AND (CAST(:indice AS INTEGER) IS NULL OR P.PROG_IND = :indice)
                ORDER BY P.GRU_USU, P.PROG_MOD, P.PROG_DESC, U.USU_COD
            """.strip(),
            required_tables=("DSIAF051", "DSIAF053", "DSIAF050"),
            required_fields={
                "DSIAF050": ("USU_COD", "USU_NOME", "GRU_USU"),
                "DSIAF051": (
                    "GRU_USU",
                    "PROG_DESC",
                    "PROG_ACE",
                    "PROG_INC",
                    "PROG_ALT",
                    "PROG_EXC",
                    "PROG_IMP",
                    "PROG_IND",
                    "PROG_MOD",
                ),
                "DSIAF053": ("GRU_USU", "GRU_DUSU"),
            },
            parameters_schema={
                "usuario": _search_parameter("Código do usuário", "integer"),
                "nome": _search_parameter("Nome do usuário contém"),
                "grupo": _search_parameter("Código do grupo", "integer"),
                "programa": _search_parameter("Programa contém"),
                "modulo": _search_parameter("Módulo armazenado"),
                "indice": _search_parameter("Índice do programa", "integer"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=siafw_source,
            result_limit=None,
        ),
        QueryTemplate(
            name="Permissões — catálogo de programas",
            module="Permissões",
            description=(
                "Pesquisa o catálogo real de programas por descrição ou módulo armazenado."
            ),
            sql_template="""
                SELECT FIRST 501
                    C.PROG_DESC AS PROGRAMA_DESCRICAO,
                    C.PROG_MOD AS PROGRAMA_MODULO
                FROM DSIAF052 C
                WHERE (CAST(:programa AS VARCHAR(60)) IS NULL
                       OR C.PROG_DESC CONTAINING :programa)
                  AND (CAST(:modulo AS VARCHAR(2)) IS NULL OR C.PROG_MOD = :modulo)
                ORDER BY C.PROG_DESC
            """.strip(),
            required_tables=("DSIAF052",),
            required_fields={"DSIAF052": ("PROG_DESC", "PROG_MOD")},
            parameters_schema={
                "programa": _search_parameter("Programa contém"),
                "modulo": _search_parameter("Módulo armazenado"),
            },
            risk_level="baixo",
            version="1.0",
            source_reference=siafw_source,
            result_limit=500,
        ),
    )


def _optional_parameter(label: str, kind: str = "text") -> dict[str, object]:
    return {"label": label, "type": kind, "required": False, "default": ""}


def _search_parameter(label: str, kind: str = "text") -> dict[str, object]:
    definition = _optional_parameter(label, kind)
    definition["require_one_of"] = "filtros"
    return definition


def _period_parameter(
    label: str,
    bound: str,
    *,
    require_complete: bool = False,
) -> dict[str, object]:
    definition = _search_parameter(label, "date")
    definition["range_group"] = "periodo"
    definition["range_bound"] = bound
    if require_complete:
        definition["range_require_complete"] = True
    return definition
