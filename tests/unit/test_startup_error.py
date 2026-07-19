from __future__ import annotations

from siaf_support_toolbox.ui import startup_error


def test_database_startup_error_preserves_file_and_explains_recovery(monkeypatch, tmp_path):
    database_path = tmp_path / "toolbox.sqlite3"
    database_path.write_bytes(b"corrupted")
    captured = {}

    class FakeRoot:
        def withdraw(self):
            captured["withdrawn"] = True

        def destroy(self):
            captured["destroyed"] = True

    monkeypatch.setattr(startup_error.tk, "Tk", FakeRoot)
    monkeypatch.setattr(
        startup_error.messagebox,
        "showerror",
        lambda title, message, parent: captured.update(title=title, message=message, parent=parent),
    )

    startup_error.show_database_startup_error(database_path)

    assert database_path.read_bytes() == b"corrupted"
    assert str(database_path) in captured["message"]
    assert "Nenhum dado foi apagado" in captured["message"]
    assert captured["withdrawn"] is True
    assert captured["destroyed"] is True
