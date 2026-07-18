from __future__ import annotations

from pathlib import Path

from siaf_support_toolbox.core.constants import FIREBIRD_CLIENT_NAMES
from siaf_support_toolbox.discovery.architecture import pe_architecture, process_architecture
from siaf_support_toolbox.discovery.bounded_scan import find_exact_names
from siaf_support_toolbox.discovery.models import (
    ClientLibraryFinding,
    DetectionIssue,
)


def detect_client_libraries(
    roots: list[Path],
) -> tuple[list[ClientLibraryFinding], list[DetectionIssue]]:
    matches, scan_errors = find_exact_names(roots, FIREBIRD_CLIENT_NAMES, max_depth=3)
    current_arch = process_architecture()
    findings = [
        ClientLibraryFinding(
            path=str(path),
            name=path.name,
            architecture=pe_architecture(path),
            compatible_with_process=pe_architecture(path) == current_arch,
        )
        for path in matches
    ]
    issues: list[DetectionIssue] = []
    if scan_errors:
        issues.append(
            DetectionIssue(
                "cliente_firebird",
                f"{len(scan_errors)} diretório(s) não puderam ser inspecionados",
                "access_denied",
            )
        )
    return findings, issues
