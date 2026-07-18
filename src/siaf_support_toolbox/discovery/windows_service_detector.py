from __future__ import annotations

import sys

from siaf_support_toolbox.discovery.models import DetectionIssue, ServiceFinding

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]


def detect_firebird_services() -> tuple[list[ServiceFinding], list[DetectionIssue]]:
    detector = "servicos_windows"
    if sys.platform != "win32":
        return [], [
            DetectionIssue(detector, "Detector disponível somente no Windows", "unsupported")
        ]
    if psutil is None:
        return [], [DetectionIssue(detector, "psutil não está instalado", "dependency_missing")]

    findings: list[ServiceFinding] = []
    issues: list[DetectionIssue] = []
    try:
        for service in psutil.win_service_iter():
            try:
                data = service.as_dict()
                searchable = " ".join(
                    str(data.get(key) or "")
                    for key in ("name", "display_name", "description", "binpath")
                ).casefold()
                if "firebird" in searchable or "interbase" in searchable:
                    findings.append(
                        ServiceFinding(
                            name=str(data.get("name") or "desconhecido"),
                            display_name=str(data.get("display_name") or data.get("name") or ""),
                            status=str(data.get("status") or "desconhecido"),
                            binary_path=data.get("binpath"),
                        )
                    )
            except psutil.AccessDenied as exc:
                issues.append(DetectionIssue(detector, str(exc), "service_query_failed"))
            except OSError as exc:
                if getattr(exc, "winerror", None) == 2 or getattr(exc, "errno", None) == 2:
                    continue
                issues.append(DetectionIssue(detector, str(exc), "service_query_failed"))
    except (OSError, RuntimeError) as exc:
        issues.append(DetectionIssue(detector, str(exc)))
    return findings, issues
