from siaf_support_toolbox.discovery.models import (
    Architecture,
    ClientLibraryFinding,
    DatabaseCandidate,
    DetectionIssue,
    DiscoveryReport,
    MachineMode,
)
from siaf_support_toolbox.ui.pages.environment_page import format_discovery_report


def test_format_discovery_report_uses_only_detected_evidence():
    report = DiscoveryReport(
        process_architecture=Architecture.X86,
        process_bits=32,
        mode=MachineMode.LOCAL_SERVER,
        confidence=80,
        network_candidate_ports=[4050],
        databases=[DatabaseCandidate("C:/SIAFW/SIAFW.FDB", "SIAFW", 100, 90)],
        client_libraries=[
            ClientLibraryFinding(
                "C:/Firebird/fbclient.dll",
                "fbclient.dll",
                Architecture.X86,
                True,
            )
        ],
        issues=[DetectionIssue("registro", "acesso parcial")],
    )

    text = format_discovery_report(report)

    assert "Modo da máquina: servidor_local" in text
    assert "SIAFW: C:/SIAFW/SIAFW.FDB (pontuação 90)" in text
    assert "fbclient.dll — x86, compatível" in text
    assert "registro: acesso parcial" in text
    assert "Portas TCP candidatas para confirmação: 4050" in text


def test_format_discovery_report_limits_issue_details():
    report = DiscoveryReport(
        issues=[DetectionIssue(f"detector-{index}", "falha") for index in range(25)]
    )

    text = format_discovery_report(report)

    assert "Avisos parciais (25)" in text
    assert "detector-19" in text
    assert "detector-20" not in text
