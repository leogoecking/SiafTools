from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from siaf_support_toolbox.database.sqlite_connection import SQLiteDatabase
from siaf_support_toolbox.discovery.models import (
    Architecture,
    ClientLibraryFinding,
    DatabaseCandidate,
    DiscoveryReport,
    MachineMode,
    NetworkFinding,
    ProcessFinding,
    ServiceFinding,
)
from siaf_support_toolbox.repositories.local_repository import LocalRepository
from siaf_support_toolbox.repositories.models import (
    ExecutionRecord,
    KnowledgeEntry,
    ManualConnectionProfile,
    QueryTemplate,
    SchemaField,
)

EXPECTED_TABLES = {
    "connection_profiles",
    "detected_environments",
    "discovered_databases",
    "execution_history",
    "knowledge_entries",
    "operation_audit",
    "query_templates",
    "schema_cache",
    "schema_migrations",
}


def make_store(tmp_path) -> tuple[SQLiteDatabase, LocalRepository]:
    database = SQLiteDatabase(tmp_path / "data" / "toolbox.sqlite3")
    database.initialize()
    return database, LocalRepository(database)


def make_report(database_path: str, *, score: int = 80) -> DiscoveryReport:
    return DiscoveryReport(
        process_architecture=Architecture.X86,
        process_bits=32,
        siaf_processes=[ProcessFinding(10, "SIAFW.EXE", "C:/SIAF/SIAFW.EXE")],
        firebird_processes=[ProcessFinding(20, "fbserver.exe", "C:/Firebird/fbserver.exe")],
        services=[ServiceFinding("Firebird25", "Firebird 2.5", "running")],
        client_libraries=[
            ClientLibraryFinding("C:/SIAF/fbclient.dll", "fbclient.dll", Architecture.X86, True)
        ],
        databases=[DatabaseCandidate(database_path, "SIAFLOJA", 512, score)],
        network_connections=[NetworkFinding(10, "10.0.0.2", 50000, "10.0.0.10", 3050)],
        detected_ports=[3050],
        mode=MachineMode.TERMINAL,
        confidence=88,
    )


def test_initialize_creates_all_tables_and_is_idempotent(tmp_path):
    database, _repository = make_store(tmp_path)

    database.initialize()

    with database.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        migrations = connection.execute("SELECT version, name FROM schema_migrations").fetchall()

    assert tables >= EXPECTED_TABLES
    assert [(row["version"], row["name"]) for row in migrations] == [(1, "initial_local_store")]


def test_initialize_is_safe_for_concurrent_application_starts(tmp_path):
    database = SQLiteDatabase(tmp_path / "toolbox.sqlite3")

    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(lambda _index: database.initialize(), range(12)))

    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_schema_has_no_field_for_password_or_secret(tmp_path):
    database, _repository = make_store(tmp_path)
    forbidden = ("password", "passwd", "senha", "secret", "token", "credential", "csc")

    with database.connect() as connection:
        columns = {
            (table, row["name"].casefold())
            for table in EXPECTED_TABLES
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }

    assert not [column for column in columns if any(item in column[1] for item in forbidden)]


def test_discovery_upsert_preserves_validation_and_reuses_it(tmp_path):
    database_path = tmp_path / "SIAFLOJA.FDB"
    database_path.write_bytes(b"database")
    database, repository = make_store(tmp_path)
    report = make_report(str(database_path))

    environment_id = repository.record_discovery("CAIXA-01", report)
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM discovered_databases WHERE environment_id = ?", (environment_id,)
        ).fetchone()
    assert row is not None
    database_id = int(row["id"])
    repository.mark_database_validated(
        database_id,
        schema_signature="sha256:abc",
        compatibility_status="compatible",
        selected=True,
    )

    repository.record_discovery("CAIXA-01", make_report(str(database_path), score=95))
    reusable = repository.latest_validated_discovery("CAIXA-01")

    with database.connect() as connection:
        rows = connection.execute("SELECT * FROM discovered_databases").fetchall()
        environments = connection.execute("SELECT * FROM detected_environments").fetchall()
    assert len(rows) == 1
    assert len(environments) == 1
    assert rows[0]["confidence_score"] == 95
    assert rows[0]["schema_signature"] == "sha256:abc"
    assert rows[0]["selected"] == 1
    assert reusable is not None
    assert reusable["id"] == environment_id
    assert reusable["databases"][0]["id"] == database_id


def test_manual_profile_never_accepts_or_returns_a_password_field(tmp_path):
    _database, repository = make_store(tmp_path)
    profile_id = repository.save_manual_profile(
        ManualConnectionProfile(
            name="Fallback loja",
            host="10.0.0.10",
            port=3050,
            database_path="D:/Dados/SIAFLOJA.FDB",
            database_type="SIAFLOJA",
            username="SUPORTE",
        )
    )

    profiles = repository.list_active_profiles()

    assert profiles[0]["id"] == profile_id
    assert profiles[0]["host"] == "10.0.0.10"
    assert not any("pass" in key.casefold() or "senha" in key.casefold() for key in profiles[0])


def test_phase_three_catalogs_and_history_are_persisted(tmp_path):
    database_file = tmp_path / "SIAFW.FDB"
    database_file.write_bytes(b"database")
    database, repository = make_store(tmp_path)
    environment_id = repository.record_discovery("SERVIDOR", make_report(str(database_file)))
    with database.connect() as connection:
        database_id = int(
            connection.execute("SELECT id FROM discovered_databases").fetchone()["id"]
        )

    template_id = repository.upsert_query_template(
        QueryTemplate(
            name="Teste interno",
            module="infraestrutura",
            description="Template sem dependência do esquema SIAF",
            sql_template="SELECT 1 FROM RDB$DATABASE",
            required_tables=("RDB$DATABASE",),
            required_fields={},
            parameters_schema={},
            risk_level="baixo",
            version="1",
        )
    )
    history_id = repository.add_execution_history(
        ExecutionRecord(
            action_name="teste",
            action_type="diagnostico",
            started_at="2026-07-18T12:00:00+00:00",
            success=False,
            app_version="test",
            environment_id=environment_id,
            database_id=database_id,
            error_message="password=segredo",
        )
    )
    repository.replace_schema_cache(
        database_id,
        [
            SchemaField(
                "RDB$DATABASE",
                "RDB$DESCRIPTION",
                "VARCHAR",
                True,
                field_length=80,
                checked_at="2026-07-18T12:00:01+00:00",
            )
        ],
    )
    knowledge_id = repository.upsert_knowledge_entry(
        KnowledgeEntry(
            category="infraestrutura",
            module="firebird",
            problem="Exemplo de teste",
            solution=("Validar o ambiente",),
            validations=("Confirmar resultado",),
            keywords=("teste",),
            confidence_level=50,
            version="1",
        )
    )

    with database.connect() as connection:
        template = connection.execute(
            "SELECT * FROM query_templates WHERE id = ?", (template_id,)
        ).fetchone()
        history = connection.execute(
            "SELECT * FROM execution_history WHERE id = ?", (history_id,)
        ).fetchone()
        cache = connection.execute("SELECT * FROM schema_cache").fetchone()
        knowledge = connection.execute(
            "SELECT * FROM knowledge_entries WHERE id = ?", (knowledge_id,)
        ).fetchone()

    assert json.loads(template["required_tables"]) == ["RDB$DATABASE"]
    assert history["error_message"] == "password=[REDACTED]"
    assert json.loads(cache["index_names"]) == []
    assert json.loads(knowledge["solution_json"]) == ["Validar o ambiente"]
