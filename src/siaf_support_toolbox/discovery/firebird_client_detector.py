from __future__ import annotations

import hashlib
import re
from pathlib import Path

from siaf_support_toolbox.core.constants import FIREBIRD_CLIENT_NAMES
from siaf_support_toolbox.discovery.architecture import pe_architecture, process_architecture
from siaf_support_toolbox.discovery.bounded_scan import find_exact_names
from siaf_support_toolbox.discovery.firebird_client_probe import (
    ClientProbeResult,
    probe_client_library,
)
from siaf_support_toolbox.discovery.models import (
    ClientLibraryFinding,
    DetectionIssue,
)

_SUPPORTED_CLIENT_VERSION = re.compile(r"(?<!\d)2\.5\.[7-9](?:\.\d+)?(?!\d)")


def detect_client_libraries(
    roots: list[Path],
) -> tuple[list[ClientLibraryFinding], list[DetectionIssue]]:
    matches, scan_errors = find_exact_names(roots, FIREBIRD_CLIENT_NAMES, max_depth=3)
    current_arch = process_architecture()
    findings: list[ClientLibraryFinding] = []
    preflight_cache: dict[str, ClientProbeResult] = {}
    for path in matches:
        architecture = pe_architecture(path)
        architecture_matches = architecture == current_arch
        if architecture_matches:
            fingerprint = _library_fingerprint(path)
            preflight = preflight_cache.get(fingerprint) if fingerprint else None
            if preflight is None:
                preflight = probe_client_library(path)
                if fingerprint:
                    preflight_cache[fingerprint] = preflight
            findings.append(
                ClientLibraryFinding(
                    path=str(path),
                    name=path.name,
                    architecture=architecture,
                    compatible_with_process=True,
                    usable=preflight.usable,
                    version=preflight.version,
                    issue=preflight.issue,
                )
            )
        else:
            findings.append(
                ClientLibraryFinding(
                    path=str(path),
                    name=path.name,
                    architecture=architecture,
                    compatible_with_process=False,
                    usable=False,
                    issue="Arquitetura incompatível com o aplicativo",
                )
            )
    issues: list[DetectionIssue] = []
    if scan_errors:
        issues.append(
            DetectionIssue(
                "cliente_firebird",
                f"{len(scan_errors)} diretório(s) não puderam ser inspecionados",
                "access_denied",
            )
        )
    if findings and not any(item.ready for item in findings):
        issues.append(
            DetectionIssue(
                "cliente_firebird",
                "Nenhuma biblioteca cliente Firebird utilizável foi confirmada.",
                "client_library_unusable",
            )
        )
    return rank_client_libraries(findings), issues


def rank_client_libraries(
    findings: list[ClientLibraryFinding],
) -> list[ClientLibraryFinding]:
    return sorted(
        findings,
        key=lambda item: (
            not item.ready,
            item.name.casefold() != "fbclient.dll",
            not bool(item.version and _SUPPORTED_CLIENT_VERSION.search(item.version)),
            item.path.casefold(),
        ),
    )


def _library_fingerprint(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None
