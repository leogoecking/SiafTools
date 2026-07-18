from __future__ import annotations

from collections.abc import Iterable

from siaf_support_toolbox.core.constants import (
    FIREBIRD_PROCESS_NAMES,
    SIAF_EXECUTABLE_NAMES,
)
from siaf_support_toolbox.discovery.models import DetectionIssue, ProcessFinding

try:
    import psutil
except ImportError:  # pragma: no cover - validado em ambiente sem dependência
    psutil = None  # type: ignore[assignment]


def detect_named_processes(
    names: Iterable[str], detector_name: str
) -> tuple[list[ProcessFinding], list[DetectionIssue]]:
    if psutil is None:
        return [], [
            DetectionIssue(detector_name, "psutil não está instalado", "dependency_missing")
        ]

    expected = {name.casefold() for name in names}
    findings: list[ProcessFinding] = []
    issues: list[DetectionIssue] = []
    try:
        for process in psutil.process_iter(["pid", "name", "exe"]):
            try:
                name = (process.info.get("name") or "").casefold()
                if name in expected:
                    findings.append(
                        ProcessFinding(
                            pid=int(process.info["pid"]),
                            name=process.info.get("name") or "desconhecido",
                            executable=process.info.get("exe"),
                        )
                    )
            except (psutil.AccessDenied, psutil.NoSuchProcess) as exc:
                issues.append(DetectionIssue(detector_name, str(exc), "access_denied"))
    except (OSError, RuntimeError) as exc:
        issues.append(DetectionIssue(detector_name, str(exc)))
    return findings, issues


def detect_siaf_processes() -> tuple[list[ProcessFinding], list[DetectionIssue]]:
    return detect_named_processes(SIAF_EXECUTABLE_NAMES, "processos_siaf")


def detect_firebird_processes() -> tuple[list[ProcessFinding], list[DetectionIssue]]:
    return detect_named_processes(FIREBIRD_PROCESS_NAMES, "processos_firebird")
