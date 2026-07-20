from __future__ import annotations

import sqlite3

from siaf_support_toolbox import main as main_module
from siaf_support_toolbox.services.environment_discovery_service import (
    PersistentDiscoveryService,
)
from siaf_support_toolbox.services.schema_inspection_service import SchemaInspectionService


def test_main_creates_internal_database_before_opening_window(monkeypatch, tmp_path):
    captured = {}

    class FakeWindow:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def mainloop(self):
            captured["mainloop"] = True

    monkeypatch.setenv("SIAF_TOOLBOX_HOME", str(tmp_path))
    monkeypatch.setattr(main_module, "configure_logging", lambda _paths: None)
    monkeypatch.setattr(main_module, "MainWindow", FakeWindow)

    main_module.main()

    assert (tmp_path / "data" / "siaf-support-toolbox.sqlite3").is_file()
    assert isinstance(captured["orchestrator"], PersistentDiscoveryService)
    assert isinstance(captured["schema_inspector"], SchemaInspectionService)
    assert captured["paths"].root == tmp_path
    assert captured["mainloop"] is True


def test_main_reports_database_failure_without_opening_main_window(monkeypatch, tmp_path, caplog):
    captured = {}

    def fail_initialize(_database):
        raise sqlite3.DatabaseError("file is not a database")

    def fail_window(**_kwargs):
        raise AssertionError("A janela principal não deveria ser aberta")

    monkeypatch.setenv("SIAF_TOOLBOX_HOME", str(tmp_path))
    monkeypatch.setattr(main_module, "configure_logging", lambda _paths: None)
    monkeypatch.setattr(main_module.SQLiteDatabase, "initialize", fail_initialize)
    monkeypatch.setattr(
        main_module,
        "show_database_startup_error",
        lambda path: captured.setdefault("database_path", path),
    )
    monkeypatch.setattr(main_module, "MainWindow", fail_window)

    main_module.main()

    assert captured["database_path"] == tmp_path / "data" / "siaf-support-toolbox.sqlite3"
    assert "banco interno não pôde ser inicializado" in caplog.text
