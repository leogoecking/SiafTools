from siaf_support_toolbox.discovery.mode_classifier import classify_machine
from siaf_support_toolbox.discovery.models import (
    ConnectionReferenceFinding,
    DatabaseCandidate,
    DiscoveryReport,
    Evidence,
    MachineMode,
    NetworkFinding,
    ProcessFinding,
    ServiceFinding,
)


def test_local_service_and_database_indicate_server():
    report = DiscoveryReport(
        services=[ServiceFinding("fb", "Firebird", "running")],
        databases=[DatabaseCandidate("C:/SIAF/SIAFW.FDB", "SIAFW", 100, 20)],
    )
    mode, confidence, _ = classify_machine(report)
    assert mode == MachineMode.LOCAL_SERVER
    assert confidence >= 45


def test_siaf_remote_connection_indicates_terminal():
    report = DiscoveryReport(
        siaf_processes=[ProcessFinding(10, "SIAFW.EXE", "C:/SIAF/SIAFW.EXE")],
        network_connections=[NetworkFinding(10, "192.168.1.10", 50000, "192.168.1.2", 3050)],
    )
    mode, confidence, _ = classify_machine(report)
    assert mode == MachineMode.TERMINAL
    assert confidence >= 45


def test_insufficient_evidence_uses_assisted_mode():
    mode, _, _ = classify_machine(DiscoveryReport())
    assert mode == MachineMode.ASSISTED


def test_service_and_process_without_database_are_not_local_server():
    report = DiscoveryReport(
        services=[ServiceFinding("fb", "Firebird", "running")],
        firebird_processes=[ProcessFinding(11, "fbserver.exe")],
    )
    mode, confidence, _ = classify_machine(report)
    assert mode == MachineMode.ASSISTED
    assert confidence <= 40


def test_unrelated_remote_connection_is_not_firebird_terminal():
    report = DiscoveryReport(
        siaf_processes=[ProcessFinding(10, "SIAFW.EXE")],
        network_connections=[NetworkFinding(10, "192.168.1.10", 50000, "8.8.8.8", 443)],
        detected_ports=[3050],
    )
    mode, confidence, _ = classify_machine(report)
    assert mode == MachineMode.ASSISTED
    assert confidence <= 40


def test_terminal_can_be_classified_from_siaf_installation_and_remote_configuration():
    report = DiscoveryReport(
        evidence=[Evidence("busca_limitada_siaf", "C:/SIAF/SIAFW.EXE", 25)],
        connection_references=[
            ConnectionReferenceFinding("servidor", 3050, "LOJA01", "C:/SIAF/siaf.ini")
        ],
    )

    mode, confidence, evidence = classify_machine(report)

    assert mode == MachineMode.TERMINAL
    assert confidence >= 60
    assert any(item.source == "configuracao_remota_firebird" for item in evidence)
