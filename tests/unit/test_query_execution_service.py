from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from siaf_support_toolbox.database.firebird_query_executor import QueryExecutionResult
from siaf_support_toolbox.repositories.models import QueryTemplate
from siaf_support_toolbox.services.connection_service import ConnectionTarget, SessionCredentials
from siaf_support_toolbox.services.query_execution_service import QueryExecutionService


class FakeRepository:
    def __init__(self, template: QueryTemplate) -> None:
        self.template = template
        self.history = []

    def upsert_query_template(self, template: QueryTemplate) -> int:
        if self.template.id is None:
            self.template = template
        return 1

    def list_query_templates(self):
        return [self.template]

    def query_template(self, template_id: int):
        return self.template if template_id == self.template.id else None

    def add_execution_history(self, record):
        self.history.append(record)
        return len(self.history)


class FakeSchemaInspector:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    def validate_requirements(self, *_args, **_kwargs):
        return SimpleNamespace(
            allowed=self.allowed,
            reason=None if self.allowed else "Cache estrutural incompleto",
            missing_relations=(),
            missing_fields=(),
        )


def _template(
    sql: str = "SELECT :code AS CODIGO FROM RDB$DATABASE",
    *,
    result_limit: int | None = None,
) -> QueryTemplate:
    return QueryTemplate(
        name="Teste",
        module="Teste",
        description="Teste seguro",
        sql_template=sql,
        required_tables=("RDB$DATABASE",) if "RDB$DATABASE" in sql else (),
        required_fields={},
        parameters_schema={"code": {"type": "integer"}} if ":code" in sql else {},
        risk_level="baixo",
        version="1",
        result_limit=result_limit,
        id=7,
    )


def _target() -> ConnectionTarget:
    return ConnectionTarget(
        environment_id=2,
        database_id=3,
        host="localhost",
        port=3050,
        database_path="C:/SIAFLOJA.FDB",
        database_type_hint="SIAFLOJA",
        client_library="C:/Firebird/fbclient.dll",
        source="teste",
        confidence=100,
    )


def test_service_streams_pages_records_history_and_clears_password(tmp_path):
    repository = FakeRepository(_template())

    def executor(**kwargs):
        assert kwargs["parameters"] == (42,)
        kwargs["on_batch"](((42, "A"), (43, "B")))
        return QueryExecutionResult(True, ("CODIGO", "NOME"), 2, 15)

    service = QueryExecutionService(
        repository, FakeSchemaInspector(), tmp_path, executor=executor
    )
    credentials = SessionCredentials("SYSDBA", "temporary")
    summary = service.execute(
        template_id=7,
        target=_target(),
        database_id=3,
        credentials=credentials,
        parameters={"code": "42"},
        cancel_event=threading.Event(),
    )

    assert summary.success
    assert service.read_page(summary.result_id, 1).rows == ((42, "A"), (43, "B"))
    export = service.export_result(
        result_id=summary.result_id,
        columns=summary.columns,
        template_name=summary.template_name,
        file_format="csv",
        cancel_event=threading.Event(),
    )
    assert export.success
    assert export.output_file is not None and export.output_file.is_file()
    assert credentials.password == ""
    assert repository.history[-1].action_type == "read_only_query"
    service.close()


def test_service_keeps_limit_and_marks_result_as_truncated(tmp_path):
    repository = FakeRepository(
        _template("SELECT FIRST 4 :code AS CODIGO FROM RDB$DATABASE", result_limit=3)
    )

    def executor(**kwargs):
        kwargs["on_batch"](((1,), (2,)))
        kwargs["on_batch"](((3,), (4,)))
        return QueryExecutionResult(True, ("CODIGO",), 4, 10)

    service = QueryExecutionService(
        repository, FakeSchemaInspector(), tmp_path, executor=executor
    )
    summary = service.execute(
        template_id=7,
        target=_target(),
        database_id=3,
        credentials=SessionCredentials("SYSDBA", "temporary"),
        parameters={"code": "1"},
        cancel_event=threading.Event(),
    )

    assert summary.success
    assert summary.truncated
    assert summary.records_processed == 3
    assert repository.history[-1].truncated
    assert service.read_page(summary.result_id, 1).rows == ((1,), (2,), (3,))
    service.close()


def test_service_fails_closed_before_executor_when_schema_is_not_ready(tmp_path):
    repository = FakeRepository(_template("SELECT * FROM RDB$DATABASE"))
    called = False

    def executor(**_kwargs):
        nonlocal called
        called = True
        return QueryExecutionResult(True)

    service = QueryExecutionService(
        repository, FakeSchemaInspector(False), tmp_path, executor=executor
    )
    credentials = SessionCredentials("SYSDBA", "temporary")
    summary = service.execute(
        template_id=7,
        target=_target(),
        database_id=3,
        credentials=credentials,
        parameters={},
        cancel_event=threading.Event(),
    )

    assert not summary.success
    assert summary.error_code == "schema_requirements_failed"
    assert not called
    assert credentials.password == ""
    service.close()


def test_service_discards_cancelation_without_result_columns(tmp_path):
    repository = FakeRepository(_template())
    service = QueryExecutionService(
        repository,
        FakeSchemaInspector(),
        tmp_path,
        executor=lambda **_kwargs: QueryExecutionResult(False, canceled=True),
    )

    summary = service.execute(
        template_id=7,
        target=_target(),
        database_id=3,
        credentials=SessionCredentials("SYSDBA", "temporary"),
        parameters={"code": "42"},
        cancel_event=threading.Event(),
    )

    assert summary.canceled
    assert summary.result_id is None
    assert not tuple(tmp_path.glob("query-*.sqlite3"))
    service.close()


def test_service_blocks_operational_template_without_any_search_filter(tmp_path):
    template = _template()
    template.parameters_schema["code"]["required"] = False
    template.parameters_schema["code"]["require_one_of"] = "filtros"
    repository = FakeRepository(template)
    called = False

    def executor(**_kwargs):
        nonlocal called
        called = True
        return QueryExecutionResult(True, ("CODIGO",))

    service = QueryExecutionService(
        repository, FakeSchemaInspector(), tmp_path, executor=executor
    )

    summary = service.execute(
        template_id=7,
        target=_target(),
        database_id=3,
        credentials=SessionCredentials("SYSDBA", "temporary"),
        parameters={"code": "   "},
        cancel_event=threading.Event(),
    )

    assert summary.error_code == "invalid_parameters"
    assert summary.message == "Informe pelo menos um filtro para limitar a consulta"
    assert not called
    service.close()


def test_service_strips_text_parameters_before_binding(tmp_path):
    repository = FakeRepository(
        QueryTemplate(
            name="Busca textual",
            module="Teste",
            description="Teste seguro",
            sql_template="SELECT :name AS NOME FROM RDB$DATABASE",
            required_tables=("RDB$DATABASE",),
            required_fields={},
            parameters_schema={"name": {"type": "text"}},
            risk_level="baixo",
            version="1",
            id=7,
        )
    )

    def executor(**kwargs):
        assert kwargs["parameters"] == ("Maria",)
        return QueryExecutionResult(True, ("NOME",), 0, 1)

    service = QueryExecutionService(
        repository, FakeSchemaInspector(), tmp_path, executor=executor
    )
    summary = service.execute(
        template_id=7,
        target=_target(),
        database_id=3,
        credentials=SessionCredentials("SYSDBA", "temporary"),
        parameters={"name": "  Maria  "},
        cancel_event=threading.Event(),
    )

    assert summary.success
    service.close()


def test_service_blocks_destructive_template_before_executor(tmp_path):
    repository = FakeRepository(_template("DELETE FROM RDB$DATABASE"))
    service = QueryExecutionService(
        repository,
        FakeSchemaInspector(),
        tmp_path,
        executor=lambda **_kwargs: QueryExecutionResult(True),
    )

    summary = service.execute(
        template_id=7,
        target=_target(),
        database_id=3,
        credentials=SessionCredentials("SYSDBA", "temporary"),
        parameters={},
        cancel_event=threading.Event(),
    )

    assert summary.error_code == "destructive_sql"
    service.close()


def test_service_blocks_template_with_undeclared_sql_dependency(tmp_path):
    template = _template("SELECT * FROM CLIENTES")
    repository = FakeRepository(template)
    service = QueryExecutionService(
        repository,
        FakeSchemaInspector(),
        tmp_path,
        executor=lambda **_kwargs: QueryExecutionResult(True),
    )

    summary = service.execute(
        template_id=7,
        target=_target(),
        database_id=3,
        credentials=SessionCredentials("SYSDBA", "temporary"),
        parameters={},
        cancel_event=threading.Event(),
    )

    assert summary.error_code == "template_dependency_mismatch"
    service.close()


def test_service_clears_password_when_repository_fails_before_validation(tmp_path):
    repository = FakeRepository(_template())
    service = QueryExecutionService(repository, FakeSchemaInspector(), tmp_path)
    credentials = SessionCredentials("SYSDBA", "temporary")

    def fail(_template_id):
        raise OSError("SQLite indisponível")

    repository.query_template = fail
    with pytest.raises(OSError, match="SQLite indisponível"):
        service.execute(
            template_id=7,
            target=_target(),
            database_id=3,
            credentials=credentials,
            parameters={},
            cancel_event=threading.Event(),
        )

    assert credentials.password == ""
    service.close()
