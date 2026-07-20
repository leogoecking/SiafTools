from __future__ import annotations

from siaf_support_toolbox.database.firebird_schema_inspector import (
    GeneratorInfo,
    IndexInfo,
    ProcedureInfo,
    RelationInfo,
    SchemaInspectionResult,
    SchemaSnapshot,
    TriggerInfo,
)
from siaf_support_toolbox.database.sqlite_connection import SQLiteDatabase
from siaf_support_toolbox.repositories.local_repository import LocalRepository
from siaf_support_toolbox.repositories.models import SchemaField, SchemaObject
from siaf_support_toolbox.services.connection_service import ConnectionTarget, SessionCredentials
from siaf_support_toolbox.services.schema_inspection_service import (
    SchemaInspectionService,
    compare_schema_caches,
)


def make_repository(tmp_path) -> tuple[SQLiteDatabase, LocalRepository, int, int]:
    database = SQLiteDatabase(tmp_path / "toolbox.sqlite3")
    database.initialize()
    with database.connect() as connection, connection:
        environment_id = int(
            connection.execute(
                """
                INSERT INTO detected_environments (
                    machine_name, detection_mode, last_scan, active
                ) VALUES ('PC', 'servidor_local', '2026-07-19', 1)
                """
            ).lastrowid
        )
        database_id = int(
            connection.execute(
                """
                INSERT INTO discovered_databases (
                    environment_id, database_path, compatibility_status,
                    schema_signature, selected, first_seen, last_seen
                ) VALUES (?, 'C:/SIAFLOJA.FDB', 'compatible', 'sha256:test', 1,
                          '2026-07-19', '2026-07-19')
                """,
                (environment_id,),
            ).lastrowid
        )
    return database, LocalRepository(database), environment_id, database_id


def make_snapshot() -> SchemaSnapshot:
    checked_at = "2026-07-19T12:00:00+00:00"
    return SchemaSnapshot(
        checked_at=checked_at,
        server_version="2.5.7.27050",
        ods_version="11.2",
        relations=(RelationInfo("DSIAF006", False, "sha256:relation"),),
        fields=(
            SchemaField(
                "DSIAF006",
                "PRO_COD",
                "INTEGER",
                False,
                field_length=4,
                field_precision=9,
                primary_key=True,
                index_names=("PK_DSIAF006",),
                checked_at=checked_at,
            ),
        ),
        indexes=(
            IndexInfo(
                "PK_DSIAF006", "DSIAF006", ("PRO_COD",), True, False, True, None
            ),
        ),
        triggers=(
            TriggerInfo("TRG_DSIAF006", "DSIAF006", 1, 0, True, "sha256:trigger"),
        ),
        procedures=(
            ProcedureInfo(
                "PR_TESTE", 1, 0, 2, "sha256:procedure", "sha256:parameters"
            ),
        ),
        generators=(GeneratorInfo("GEN_DSIAF006"),),
    )


def make_target(environment_id: int, database_id: int) -> ConnectionTarget:
    return ConnectionTarget(
        environment_id=environment_id,
        database_id=database_id,
        host="localhost",
        port=3050,
        database_path="C:/SIAFLOJA.FDB",
        database_type_hint="SIAFLOJA",
        client_library="C:/Firebird/fbclient.dll",
        source="teste",
        confidence=100,
    )


def test_service_persists_snapshot_audits_and_clears_credentials(tmp_path):
    database, repository, environment_id, database_id = make_repository(tmp_path)
    captured = {}

    def inspector(**kwargs):
        captured.update(kwargs)
        return SchemaInspectionResult(True, snapshot=make_snapshot())

    service = SchemaInspectionService(repository, inspector=inspector)
    credentials = SessionCredentials("SYSDBA", "session-secret")

    summary = service.inspect(make_target(environment_id, database_id), database_id, credentials)

    fields, objects = repository.load_schema_cache(database_id)
    state = repository.schema_cache_state(database_id)
    assert summary.result.success
    assert captured["password"] == "session-secret"
    assert credentials.password == ""
    assert fields[0].primary_key
    assert fields[0].field_precision == 9
    assert state.ready
    assert state.field_count == 1
    assert {item.object_type for item in objects} == {
        "relation",
        "index",
        "trigger",
        "procedure",
        "generator",
    }
    with database.connect() as connection:
        history = connection.execute(
            "SELECT * FROM execution_history WHERE action_type = 'schema_inspection'"
        ).fetchone()
    assert history["success"] == 1
    assert history["records_processed"] == 1
    assert b"session-secret" not in database.path.read_bytes()


def test_requirements_block_missing_relations_and_fields(tmp_path):
    _database, repository, environment_id, database_id = make_repository(tmp_path)
    service = SchemaInspectionService(
        repository,
        inspector=lambda **_kwargs: SchemaInspectionResult(True, snapshot=make_snapshot()),
    )
    service.inspect(
        make_target(environment_id, database_id),
        database_id,
        SessionCredentials("SYSDBA", "temporary"),
    )

    allowed = service.validate_requirements(
        database_id,
        required_tables=("DSIAF006",),
        required_fields={"DSIAF006": ("PRO_COD",)},
    )
    blocked = service.validate_requirements(
        database_id,
        required_tables=("DSIAF006", "DSIAF999"),
        required_fields={"DSIAF006": ("PRO_COD", "PRO_INEXISTENTE")},
    )
    system_catalog = service.validate_requirements(
        database_id,
        required_tables=("RDB$DATABASE", "RDB$RELATIONS"),
        required_fields={},
    )

    assert allowed.allowed
    assert system_catalog.allowed
    assert allowed.cache_ready
    assert not blocked.allowed
    assert blocked.missing_relations == ("DSIAF999",)
    assert blocked.missing_fields == ("DSIAF006.PRO_INEXISTENTE",)


def test_requirements_fail_closed_without_a_complete_current_snapshot(tmp_path):
    _database, repository, environment_id, database_id = make_repository(tmp_path)
    service = SchemaInspectionService(repository)

    missing = service.validate_requirements(
        database_id, required_tables=(), required_fields={}
    )

    assert not missing.allowed
    assert not missing.cache_ready
    assert "não inspecionada" in missing.reason

    service = SchemaInspectionService(
        repository,
        inspector=lambda **_kwargs: SchemaInspectionResult(True, snapshot=make_snapshot()),
    )
    service.inspect(
        make_target(environment_id, database_id),
        database_id,
        SessionCredentials("SYSDBA", "temporary"),
    )
    repository.mark_database_validated(
        database_id,
        schema_signature="sha256:test",
        compatibility_status="compatible",
        selected=True,
    )

    invalidated = service.validate_requirements(
        database_id,
        required_tables=("DSIAF006",),
        required_fields={"DSIAF006": ("PRO_COD",)},
    )
    assert not invalidated.allowed
    assert not invalidated.cache_ready
    assert repository.load_schema_cache(database_id) == ([], [])


def test_requirements_reject_an_incomplete_snapshot(tmp_path):
    database, repository, environment_id, database_id = make_repository(tmp_path)
    service = SchemaInspectionService(
        repository,
        inspector=lambda **_kwargs: SchemaInspectionResult(True, snapshot=make_snapshot()),
    )
    service.inspect(
        make_target(environment_id, database_id),
        database_id,
        SessionCredentials("SYSDBA", "temporary"),
    )
    with database.connect() as connection, connection:
        connection.execute(
            "DELETE FROM schema_object_cache WHERE database_id = ? AND object_type = 'trigger'",
            (database_id,),
        )

    check = service.validate_requirements(
        database_id,
        required_tables=("DSIAF006",),
        required_fields={"DSIAF006": ("PRO_COD",)},
    )

    assert not check.allowed
    assert not check.cache_ready
    assert "incompleto" in check.reason


def test_inspect_many_keeps_credentials_until_all_bases_then_clears(tmp_path):
    _database, repository, environment_id, database_id = make_repository(tmp_path)
    received_passwords = []

    def inspector(**kwargs):
        received_passwords.append(kwargs["password"])
        return SchemaInspectionResult(True, snapshot=make_snapshot())

    service = SchemaInspectionService(repository, inspector=inspector)
    target = make_target(environment_id, database_id)
    credentials = SessionCredentials("SYSDBA", "shared-session-secret")

    summaries = service.inspect_many(
        ((target, database_id), (target, database_id)), credentials
    )

    assert len(summaries) == 2
    assert received_passwords == ["shared-session-secret", "shared-session-secret"]
    assert credentials.password == ""


def test_compare_schema_caches_reports_structural_differences():
    left_fields = [SchemaField("TAB_A", "ID", "INTEGER", False, primary_key=True)]
    right_fields = [
        SchemaField("TAB_A", "ID", "BIGINT", False, primary_key=True),
        SchemaField("TAB_B", "NOME", "VARCHAR", True),
    ]
    left_objects = [
        SchemaObject("relation", "TAB_A", {"is_view": False}),
        SchemaObject(
            "trigger",
            "TRG_TAB_A",
            {"active": True, "source_hash": "sha256:left"},
            relation_name="TAB_A",
        ),
    ]
    right_objects = [
        SchemaObject("relation", "TAB_A", {"is_view": False}),
        SchemaObject("relation", "TAB_B", {"is_view": False}),
        SchemaObject(
            "trigger",
            "TRG_TAB_A",
            {"active": True, "source_hash": "sha256:right"},
            relation_name="TAB_A",
        ),
        SchemaObject("generator", "GEN_TAB_B", {}),
    ]

    comparison = compare_schema_caches(
        left_fields, left_objects, right_fields, right_objects
    )

    assert not comparison.equivalent
    assert comparison.right_only_relations == ("tab_b",)
    assert comparison.right_only_fields == ("tab_b.nome",)
    assert comparison.changed_fields == ("tab_a.id",)
    assert comparison.right_only_objects == ("generator::gen_tab_b",)
    assert comparison.changed_objects == ("trigger:tab_a:trg_tab_a",)


def test_empty_schema_caches_are_not_equivalent():
    comparison = compare_schema_caches([], [], [], [])

    assert not comparison.comparable
    assert not comparison.equivalent
    assert "snapshots" in comparison.reason
