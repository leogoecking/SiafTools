from __future__ import annotations

from collections.abc import Iterable

from siaf_support_toolbox.discovery.models import DetectionIssue, NetworkFinding

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]


def detect_process_connections(
    process_ids: Iterable[int],
) -> tuple[list[NetworkFinding], list[DetectionIssue]]:
    detector = "conexoes_tcp_siaf"
    if psutil is None:
        return [], [DetectionIssue(detector, "psutil não está instalado", "dependency_missing")]
    pids = set(process_ids)
    if not pids:
        return [], []

    findings: list[NetworkFinding] = []
    issues: list[DetectionIssue] = []
    try:
        for connection in psutil.net_connections(kind="tcp"):
            if connection.pid not in pids or not connection.raddr:
                continue
            if connection.status != psutil.CONN_ESTABLISHED:
                continue
            findings.append(
                NetworkFinding(
                    pid=int(connection.pid),
                    local_address=str(connection.laddr.ip),
                    local_port=int(connection.laddr.port),
                    remote_address=str(connection.raddr.ip),
                    remote_port=int(connection.raddr.port),
                )
            )
    except (psutil.AccessDenied, OSError) as exc:
        issues.append(DetectionIssue(detector, str(exc), "access_denied"))
    return findings, issues
