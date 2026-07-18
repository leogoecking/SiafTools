from __future__ import annotations

from types import SimpleNamespace

from siaf_support_toolbox.discovery import network_detector


def address(ip: str, port: int):
    return SimpleNamespace(ip=ip, port=port)


def test_filters_connections_by_pid_remote_address_and_status(monkeypatch):
    connections = [
        SimpleNamespace(
            pid=10,
            laddr=address("10.0.0.5", 50000),
            raddr=address("10.0.0.2", 3050),
            status="ESTABLISHED",
        ),
        SimpleNamespace(
            pid=11,
            laddr=address("10.0.0.5", 50001),
            raddr=address("10.0.0.3", 3050),
            status="ESTABLISHED",
        ),
        SimpleNamespace(
            pid=10,
            laddr=address("10.0.0.5", 50002),
            raddr=(),
            status="LISTEN",
        ),
    ]
    fake_psutil = SimpleNamespace(
        CONN_ESTABLISHED="ESTABLISHED",
        AccessDenied=PermissionError,
        net_connections=lambda **_kwargs: connections,
    )
    monkeypatch.setattr(network_detector, "psutil", fake_psutil)

    findings, issues = network_detector.detect_process_connections([10])

    assert issues == []
    assert len(findings) == 1
    assert findings[0].remote_address == "10.0.0.2"
    assert findings[0].remote_port == 3050
