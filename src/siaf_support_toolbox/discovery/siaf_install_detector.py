from __future__ import annotations

import os
from pathlib import Path

from siaf_support_toolbox.core.constants import SIAF_EXECUTABLE_NAMES
from siaf_support_toolbox.discovery.bounded_scan import find_exact_names
from siaf_support_toolbox.discovery.models import DetectionIssue, Evidence, ProcessFinding


def default_siaf_roots() -> list[Path]:
    candidates = [Path("C:/SIAF"), Path("C:/SIAFW"), Path("C:/Adsoft")]
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "PROGRAMDATA"):
        value = os.environ.get(variable)
        if not value:
            continue
        base = Path(value)
        candidates.extend(base / name for name in ("SIAF", "SIAFW", "Adsoft"))
    return _existing_unique(candidates)


def detect_siaf_installations(
    processes: list[ProcessFinding], extra_roots: list[Path] | None = None
) -> tuple[list[Path], list[Evidence], list[DetectionIssue]]:
    installations: list[Path] = []
    evidence: list[Evidence] = []
    issues: list[DetectionIssue] = []

    for process in processes:
        if process.executable:
            executable = Path(process.executable)
            installations.append(executable)
            evidence.append(Evidence("processo_siaf", str(executable), 50))

    roots = default_siaf_roots() + list(extra_roots or [])
    matches, scan_errors = find_exact_names(roots, SIAF_EXECUTABLE_NAMES, max_depth=3)
    for match in matches:
        installations.append(match)
        evidence.append(Evidence("busca_limitada_siaf", str(match), 25))
    if scan_errors:
        issues.append(
            DetectionIssue(
                "instalacao_siaf",
                f"{len(scan_errors)} diretório(s) não puderam ser inspecionados",
                "access_denied",
            )
        )
    return _existing_unique(installations), evidence, issues


def _existing_unique(paths: list[Path]) -> list[Path]:
    unique: dict[str, Path] = {}
    for path in paths:
        if path.exists():
            unique[os.path.normcase(str(path.resolve(strict=False)))] = path
    return list(unique.values())
