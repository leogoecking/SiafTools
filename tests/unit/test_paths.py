from pathlib import Path

from siaf_support_toolbox.core.paths import AppPaths


def test_for_user_prefers_explicit_override(monkeypatch, tmp_path):
    custom_root = tmp_path / "custom-profile"
    monkeypatch.setenv("SIAF_TOOLBOX_HOME", str(custom_root))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "ignored"))

    paths = AppPaths.for_user()

    assert paths.root == custom_root
    assert paths.data == custom_root / "data"
    assert paths.logs == custom_root / "logs"
    assert paths.exports == custom_root / "exports"


def test_for_user_uses_windows_local_app_data(monkeypatch, tmp_path):
    monkeypatch.delenv("SIAF_TOOLBOX_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    paths = AppPaths.for_user()

    assert paths.root == tmp_path / "SIAF Support Toolbox"


def test_ensure_creates_all_user_directories(tmp_path):
    root = tmp_path / "profile"
    paths = AppPaths(root, root / "data", root / "logs", root / "exports")

    returned = paths.ensure()

    assert returned is paths
    assert all(path.is_dir() for path in (paths.root, paths.data, paths.logs, paths.exports))
    assert all(path.is_relative_to(root) for path in (paths.data, paths.logs, paths.exports))


def test_for_user_falls_back_to_home(monkeypatch, tmp_path):
    monkeypatch.delenv("SIAF_TOOLBOX_HOME", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert AppPaths.for_user().root == tmp_path / "SIAF Support Toolbox"
