from __future__ import annotations

from siaf_support_toolbox import main as main_module
from siaf_support_toolbox.services.environment_discovery_service import (
    PersistentDiscoveryService,
)


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
    assert captured["paths"].root == tmp_path
    assert captured["mainloop"] is True
