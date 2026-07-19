from __future__ import annotations

from siaf_support_toolbox.database.sqlite_connection import SQLiteDatabase
from siaf_support_toolbox.discovery.models import DatabaseCandidate, DiscoveryReport, MachineMode
from siaf_support_toolbox.repositories.local_repository import LocalRepository
from siaf_support_toolbox.services.environment_discovery_service import (
    PersistentDiscoveryService,
)


class CountingOrchestrator:
    def __init__(self, path: str) -> None:
        self.calls = 0
        self.path = path

    def discover(self) -> DiscoveryReport:
        self.calls += 1
        return DiscoveryReport(
            databases=[DatabaseCandidate(self.path, "SIAFLOJA", 10, 70 + self.calls)],
            mode=MachineMode.ASSISTED,
            confidence=60,
        )


def test_service_always_runs_new_analysis_while_preserving_local_result(tmp_path):
    path = str(tmp_path / "SIAFLOJA.FDB")
    database = SQLiteDatabase(tmp_path / "toolbox.sqlite3")
    database.initialize()
    repository = LocalRepository(database)
    orchestrator = CountingOrchestrator(path)
    service = PersistentDiscoveryService(repository, orchestrator, "TEST-PC")

    first = service.discover()
    second = service.discover()

    assert orchestrator.calls == 2
    assert first.databases[0].score == 71
    assert second.databases[0].score == 72
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM detected_environments").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM discovered_databases").fetchone()[0] == 1


def test_storage_failure_becomes_non_fatal_discovery_issue(tmp_path):
    database = SQLiteDatabase(tmp_path / "missing" / "toolbox.sqlite3")
    repository = LocalRepository(database)
    service = PersistentDiscoveryService(
        repository,
        CountingOrchestrator(str(tmp_path / "SIAFLOJA.FDB")),
        "TEST-PC",
    )

    report = service.discover()

    assert any(issue.code == "local_storage_error" for issue in report.issues)
