from __future__ import annotations

from siaf_support_toolbox.database.firebird_probe import FirebirdProbeResult
from siaf_support_toolbox.database.sqlite_connection import SQLiteDatabase
from siaf_support_toolbox.discovery.models import (
    Architecture,
    ClientLibraryFinding,
    DatabaseCandidate,
    DiscoveryReport,
    MachineMode,
    NetworkFinding,
)
from siaf_support_toolbox.discovery.schema_classifier import (
    DatabaseType,
    SchemaClassification,
)
from siaf_support_toolbox.repositories.local_repository import LocalRepository
from siaf_support_toolbox.services.connection_service import (
    FirebirdConnectionService,
    ManualConnectionInput,
    SessionCredentials,
)


def make_repository(tmp_path) -> tuple[SQLiteDatabase, LocalRepository]:
    database = SQLiteDatabase(tmp_path / "toolbox.sqlite3")
    database.initialize()
    return database, LocalRepository(database)


def make_report(path: str) -> DiscoveryReport:
    return DiscoveryReport(
        client_libraries=[
            ClientLibraryFinding("C:/Firebird/fbclient.dll", "fbclient.dll", Architecture.X86, True)
        ],
        databases=[DatabaseCandidate(path, "SIAFLOJA", 100, 90)],
        detected_ports=[3050],
        mode=MachineMode.LOCAL_SERVER,
        confidence=90,
    )


def accepted_result() -> FirebirdProbeResult:
    return FirebirdProbeResult(
        True,
        "2026-07-18 12:00:00",
        SchemaClassification(
            DatabaseType.SIAFLOJA,
            85,
            ("DSIAF006", "DSIAF010", "DSIAF011", "DSIAF036", "DSIAF037", "DSIAF400"),
            ("DSIAF401",),
        ),
        server_version="2.5.7",
        ods_version="11.2",
    )


def test_automatic_local_connection_is_validated_and_persisted_without_password(tmp_path):
    database, repository = make_repository(tmp_path)
    report = make_report("D:/Dados/SIAFLOJA.FDB")
    repository.record_discovery("SERVIDOR", report)
    captured = {}

    def probe(**kwargs):
        captured.update(kwargs)
        return accepted_result()

    service = FirebirdConnectionService(repository, machine_name="SERVIDOR", probe=probe)
    plan = service.build_plan(report)
    credentials = SessionCredentials("SUPORTE", "SEGREDO-DA-SESSAO")

    summary = service.validate(plan, credentials)

    assert len(plan.targets) == 1
    assert plan.targets[0].dsn == "localhost:D:/Dados/SIAFLOJA.FDB"
    assert len(summary.successful) == 1
    assert captured["password"] == "SEGREDO-DA-SESSAO"
    assert captured["host"] == "localhost"
    assert credentials.password == ""
    with database.connect() as connection:
        stored = connection.execute(
            "SELECT compatibility_status, selected FROM discovered_databases"
        ).fetchone()
        history = connection.execute("SELECT success FROM execution_history").fetchone()[0]
        version = connection.execute(
            "SELECT firebird_version FROM detected_environments"
        ).fetchone()[0]
    assert (stored["compatibility_status"], stored["selected"]) == ("compatible", 1)
    assert history == 1
    assert version == "2.5.7"
    assert b"SEGREDO-DA-SESSAO" not in database.path.read_bytes()
    assert service.build_plan(report).targets[0].source == "descoberta_validada"


def test_terminal_uses_remote_alias_and_never_combines_remote_host_with_local_file(tmp_path):
    _database, repository = make_repository(tmp_path)
    report = make_report("C:/CopiaLocal/SIAFLOJA.FDB")
    report.mode = MachineMode.TERMINAL
    report.network_connections = [NetworkFinding(10, "10.0.0.2", 50000, "10.0.0.10", 3050)]
    from siaf_support_toolbox.discovery.models import AliasFinding

    report.aliases = [AliasFinding("LOJA01", "D:/Dados/SIAFLOJA.FDB", "aliases.conf")]
    repository.record_discovery("CAIXA", report)
    service = FirebirdConnectionService(repository, machine_name="CAIXA")

    plan = service.build_plan(report)

    assert len(plan.targets) == 1
    assert plan.targets[0].dsn == "10.0.0.10:LOJA01"
    assert "CopiaLocal" not in plan.targets[0].dsn


def test_successful_manual_fallback_saves_profile_without_password(tmp_path):
    database, repository = make_repository(tmp_path)
    report = make_report("D:/Automatico/SIAFLOJA.FDB")
    repository.record_discovery("PC", report)
    service = FirebirdConnectionService(
        repository,
        machine_name="PC",
        probe=lambda **_kwargs: accepted_result(),
    )
    manual = ManualConnectionInput(
        database_path="D:/Manual/SIAFLOJA.FDB",
        client_library="C:/Firebird/fbclient.dll",
        save_profile=True,
    )
    plan = service.build_plan(report, manual)
    credentials = SessionCredentials("SUPORTE", "NAO-SALVAR")

    summary = service.validate(plan, credentials, manual)

    assert summary.validations[0].target.manual
    profiles = repository.list_active_profiles()
    assert profiles[0]["database_path"] == "D:/Manual/SIAFLOJA.FDB"
    assert "password" not in profiles[0]
    assert b"NAO-SALVAR" not in database.path.read_bytes()


def test_missing_compatible_client_returns_grounded_plan_issue(tmp_path):
    _database, repository = make_repository(tmp_path)
    report = DiscoveryReport(
        databases=[DatabaseCandidate("D:/Dados/SIAFLOJA.FDB", "SIAFLOJA", 10, 60)]
    )
    repository.record_discovery("PC", report)

    plan = FirebirdConnectionService(repository, machine_name="PC").build_plan(report)

    assert plan.targets == ()
    assert "x86" in plan.issues[0]
