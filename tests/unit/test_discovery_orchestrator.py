from __future__ import annotations

from siaf_support_toolbox.discovery import discovery_orchestrator as orchestrator_module
from siaf_support_toolbox.discovery.discovery_orchestrator import DiscoveryOrchestrator
from siaf_support_toolbox.discovery.models import (
    AliasFinding,
    Architecture,
    ClientLibraryFinding,
    DatabaseCandidate,
    FirebirdConfigurationFinding,
    MachineMode,
    ProcessFinding,
    RegistryFinding,
    ServiceFinding,
)


def patch_base_detectors(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator_module, "process_architecture", lambda: Architecture.X86)
    monkeypatch.setattr(orchestrator_module, "process_bits", lambda: 32)
    monkeypatch.setattr(orchestrator_module, "is_process_admin", lambda: False)
    monkeypatch.setattr(orchestrator_module, "detect_siaf_processes", lambda: ([], []))
    monkeypatch.setattr(orchestrator_module, "detect_siaf_shortcuts", lambda: ([], []))
    monkeypatch.setattr(orchestrator_module, "detect_firebird_processes", lambda: ([], []))
    monkeypatch.setattr(orchestrator_module, "detect_firebird_services", lambda: ([], []))
    monkeypatch.setattr(orchestrator_module, "detect_registry", lambda: ([], []))
    monkeypatch.setattr(
        orchestrator_module, "detect_siaf_installations", lambda _processes, _roots: ([], [], [])
    )
    monkeypatch.setattr(
        orchestrator_module, "detect_firebird_configurations", lambda _roots: ([], [])
    )
    monkeypatch.setattr(
        orchestrator_module, "detect_siaf_connection_references", lambda _roots: ([], [])
    )
    monkeypatch.setattr(orchestrator_module, "detect_client_libraries", lambda _roots: ([], []))
    monkeypatch.setattr(
        orchestrator_module,
        "locate_databases",
        lambda _roots, _installations, _aliases: ([], []),
    )
    monkeypatch.setattr(orchestrator_module, "detect_process_connections", lambda _pids: ([], []))


def test_orchestrator_combines_grouped_environment_evidence(monkeypatch, tmp_path):
    patch_base_detectors(monkeypatch)
    executable = tmp_path / "SIAFW.EXE"
    executable.write_bytes(b"exe")
    database = tmp_path / "SIAFLOJA.FDB"
    database.write_bytes(b"database")
    alias = AliasFinding("LOJA", str(database), str(tmp_path / "aliases.conf"))

    monkeypatch.setattr(
        orchestrator_module,
        "detect_firebird_processes",
        lambda: ([ProcessFinding(20, "fbserver.exe", str(tmp_path / "fbserver.exe"))], []),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "detect_firebird_services",
        lambda: ([ServiceFinding("fb", "Firebird", "running")], []),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "detect_registry",
        lambda: (
            [
                RegistryFinding(
                    "SOFTWARE/Firebird/Uninstall",
                    "DisplayVersion",
                    "2.5.7.27050",
                    "32-bit",
                )
            ],
            [],
        ),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "detect_siaf_installations",
        lambda _processes, _roots: ([executable], [], []),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "detect_firebird_configurations",
        lambda _roots: (
            [FirebirdConfigurationFinding(str(tmp_path), 3055, aliases=(alias,))],
            [],
        ),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "detect_client_libraries",
        lambda _roots: (
            [ClientLibraryFinding("fbclient.dll", "fbclient.dll", Architecture.X86, True)],
            [],
        ),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "locate_databases",
        lambda _roots, _installations, _aliases: (
            [DatabaseCandidate(str(database), "SIAFLOJA", 8, 75)],
            [],
        ),
    )

    report = DiscoveryOrchestrator([tmp_path]).discover()

    assert report.process_bits == 32
    assert report.detected_ports == [3055]
    assert report.aliases == [alias]
    assert report.mode == MachineMode.LOCAL_SERVER
    assert report.confidence >= 75
    assert report.firebird_version == "2.5.7.27050"


def test_orchestrator_turns_unexpected_detector_error_into_issue(monkeypatch):
    patch_base_detectors(monkeypatch)

    def fail(_roots):
        raise PermissionError("blocked")

    monkeypatch.setattr(orchestrator_module, "detect_client_libraries", fail)

    report = DiscoveryOrchestrator().discover()

    assert report.client_libraries == []
    assert any(
        issue.detector == "cliente_firebird" and issue.code == "unexpected_error"
        for issue in report.issues
    )
    assert report.mode == MachineMode.ASSISTED
