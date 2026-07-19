from __future__ import annotations

import json

from siaf_support_toolbox.discovery.models import (
    Architecture,
    ClientLibraryFinding,
    DatabaseCandidate,
    DiscoveryReport,
    Evidence,
)
from siaf_support_toolbox.services.connection_service import ConnectionTarget
from siaf_support_toolbox.services.diagnostic_export_service import DiagnosticExportService


def test_diagnostic_export_masks_paths_and_uses_collision_safe_names(tmp_path):
    report = DiscoveryReport(
        client_libraries=[
            ClientLibraryFinding("C:/SIAF/fbclient.dll", "fbclient.dll", Architecture.X86, True)
        ],
        databases=[DatabaseCandidate("D:/Clientes/Loja01/SIAFLOJA.FDB", "SIAFLOJA", 10, 80)],
        evidence=[
            Evidence("configuração", "C:/SIAF/firebird.conf", 20),
            Evidence(
                "dsn",
                "servidor:3050:C:\\Clientes\\Loja 01\\SIAFLOJA.FDB",
                20,
            ),
            Evidence("registro", '"C:\\Program Files (x86)\\SIAF\\SIAFW.EXE" -server', 10),
            Evidence("perfil", "%LOCALAPPDATA%\\SIAF\\config.ini", 10),
            Evidence("compartilhamento", "\\\\servidor\\dados\\SIAFW.FDB", 10),
        ],
    )
    target = ConnectionTarget(
        1,
        1,
        "localhost",
        3050,
        "D:/Clientes/Loja01/SIAFLOJA.FDB",
        "SIAFLOJA",
        "C:/SIAF/fbclient.dll",
        "descoberta_local",
        80,
    )
    exporter = DiagnosticExportService(tmp_path)

    first = exporter.export(report, targets=(target,))
    second = exporter.export(report, targets=(target,))
    payload = json.loads(first.read_text(encoding="utf-8"))
    raw = first.read_text(encoding="utf-8")

    assert first != second
    assert payload["credentials_persisted"] is False
    assert payload["paths_masked"] is True
    assert "D:/Clientes" not in raw
    assert "C:/SIAF" not in raw
    assert "C:\\Clientes" not in raw
    assert "C:\\Program Files" not in raw
    assert "%LOCALAPPDATA%" not in raw
    assert "\\\\servidor\\dados" not in raw
    assert "SIAFLOJA.FDB" in raw
    assert not list(tmp_path.glob("*.tmp"))
