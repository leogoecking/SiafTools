from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from siaf_support_toolbox.database import firebird_probe
from siaf_support_toolbox.discovery.models import Architecture
from siaf_support_toolbox.discovery.schema_classifier import DatabaseType


class FakeCursor:
    def __init__(self, tables: list[str]) -> None:
        self.tables = tables
        self.batch_returned = False
        self.closed = False

    def execute(self, _sql: str) -> None:
        return None

    def fetchone(self):
        return ("2026-07-18 18:00:00",)

    def fetchmany(self, _size: int):
        if self.batch_returned:
            return []
        self.batch_returned = True
        return [(table,) for table in self.tables]

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, tables: list[str]) -> None:
        self.fake_cursor = FakeCursor(tables)
        self.rolled_back = False
        self.closed = False
        self.tpb = None
        self.engine_version = "2.5.7"
        self.version = "2.5.7.27050"
        self.ods = "11.2"

    def begin(self, *, tpb) -> None:
        self.tpb = tpb

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def install_fake_fdb(monkeypatch, tables: list[str]) -> FakeConnection:
    connection = FakeConnection(tables)
    fake_fdb = SimpleNamespace(
        ISOLATION_LEVEL_READ_COMMITED_RO=b"readonly",
        load_api=lambda _path: object(),
        connect=lambda **_kwargs: connection,
    )
    monkeypatch.setitem(sys.modules, "fdb", fake_fdb)
    monkeypatch.setattr(firebird_probe, "pe_architecture", lambda _path: Architecture.X86)
    monkeypatch.setattr(firebird_probe, "process_architecture", lambda: Architecture.X86)
    return connection


def call_probe():
    return firebird_probe.probe_read_only(
        dsn="localhost:C:\\SIAFW\\SIAFW.FDB",
        username="authorized",
        password="session-only",
        client_library="fbclient.dll",
    )


def test_probe_accepts_strong_schema_and_rolls_back(monkeypatch):
    connection = install_fake_fdb(
        monkeypatch,
        ["DSIAF006", "DSIAF010", "DSIAF011", "DSIAF036", "DSIAF037", "DSIAF400"],
    )

    result = call_probe()

    assert result.success
    assert result.classification.database_type == DatabaseType.SIAFLOJA
    assert connection.rolled_back
    assert connection.closed
    assert connection.tpb == b"readonly"
    assert result.server_version == "2.5.7.27050"
    assert result.ods_version == "11.2"


@pytest.mark.parametrize(
    ("server_version", "ods_version", "expected_code"),
    [
        ("4.0.5", "13.0", "unsupported_firebird_version"),
        ("2.5.7.27050", "13.0", "unsupported_ods_version"),
    ],
)
def test_probe_rejects_unsupported_firebird_runtime(
    monkeypatch, server_version, ods_version, expected_code
):
    connection = install_fake_fdb(
        monkeypatch,
        ["DSIAF006", "DSIAF010", "DSIAF011", "DSIAF036", "DSIAF037", "DSIAF400"],
    )
    connection.version = server_version
    connection.ods = ods_version

    result = call_probe()

    assert not result.success
    assert result.error_code == expected_code
    assert result.classification.is_accepted
    assert connection.rolled_back


def test_probe_rejects_low_confidence_schema(monkeypatch):
    install_fake_fdb(monkeypatch, ["DSIAF006"])

    result = call_probe()

    assert not result.success
    assert result.error_code == "low_schema_confidence"
    assert result.classification.confidence == 14


def test_probe_rejects_ambiguous_schema(monkeypatch):
    install_fake_fdb(
        monkeypatch,
        [
            "DSIAF006",
            "DSIAF010",
            "DSIAF011",
            "DSIAF036",
            "DSIAF037",
            "DSIAF400",
            "DSIAF401",
            "DSIAF001",
            "DSIAF050",
            "DSIAF051",
            "DSIAF052",
            "DSIAF053",
            "DSIAF095",
        ],
    )

    result = call_probe()

    assert not result.success
    assert result.error_code == "ambiguous_schema"


def test_probe_blocks_incompatible_library_before_import(monkeypatch):
    monkeypatch.setattr(firebird_probe, "pe_architecture", lambda _path: Architecture.X64)
    monkeypatch.setattr(firebird_probe, "process_architecture", lambda: Architecture.X86)

    result = call_probe()

    assert not result.success
    assert result.error_code == "architecture_mismatch"


@pytest.mark.parametrize(
    ("message", "translated"),
    [
        ("WinError 193", "incompatível"),
        ("unsupported ODS", "compatível"),
        ("login invalid", "credencial"),
        ("SQLCODE -902 CreateFile", "caminho"),
    ],
)
def test_translates_connection_errors_without_echoing_details(message, translated):
    output = firebird_probe._translate_error(RuntimeError(message))
    assert translated in output
    assert message not in output


def test_probe_stops_before_loading_driver_when_port_is_unavailable(monkeypatch):
    monkeypatch.setattr(firebird_probe, "pe_architecture", lambda _path: Architecture.X86)
    monkeypatch.setattr(firebird_probe, "process_architecture", lambda: Architecture.X86)
    monkeypatch.setattr(firebird_probe, "_port_reachable", lambda *_args: False)

    result = firebird_probe.probe_read_only(
        dsn="server:D:/SIAFLOJA.FDB",
        username="authorized",
        password="session-only",
        client_library="fbclient.dll",
        host="server",
        port=3050,
    )

    assert not result.success
    assert result.error_code == "port_unavailable"
    assert "serviço Firebird" in result.message


def test_probe_rejects_switching_an_already_loaded_client_library(monkeypatch):
    connection = FakeConnection(
        ["DSIAF006", "DSIAF010", "DSIAF011", "DSIAF036", "DSIAF037", "DSIAF400"]
    )
    connected = False

    def connect(**_kwargs):
        nonlocal connected
        connected = True
        return connection

    fake_fdb = SimpleNamespace(
        ISOLATION_LEVEL_READ_COMMITED_RO=b"readonly",
        load_api=lambda _path: SimpleNamespace(client_library_name="C:/Firebird/A/fbclient.dll"),
        connect=connect,
    )
    monkeypatch.setitem(sys.modules, "fdb", fake_fdb)
    monkeypatch.setattr(firebird_probe, "pe_architecture", lambda _path: Architecture.X86)
    monkeypatch.setattr(firebird_probe, "process_architecture", lambda: Architecture.X86)

    result = firebird_probe.probe_read_only(
        dsn="localhost:C:/SIAFW/SIAFW.FDB",
        username="authorized",
        password="session-only",
        client_library="C:/Firebird/B/fbclient.dll",
    )

    assert not result.success
    assert result.error_code == "client_library_already_loaded"
    assert not connected
