from types import SimpleNamespace

from siaf_support_toolbox.discovery import shortcut_detector
from siaf_support_toolbox.discovery.shortcut_detector import detect_siaf_shortcuts


def test_finds_only_siaf_shortcuts_in_bounded_roots(tmp_path):
    menu = tmp_path / "Programs" / "Adsoft"
    menu.mkdir(parents=True)
    expected = menu / "Abrir SIAFW.lnk"
    expected.write_bytes(b"shortcut")
    (menu / "Outro Sistema.lnk").write_bytes(b"shortcut")

    findings, issues = detect_siaf_shortcuts(
        [tmp_path],
        resolver=lambda _: ("C:\\SIAFW\\SIAFW.EXE", "C:\\SIAFW"),
    )

    assert len(findings) == 1
    assert findings[0].path == str(expected)
    assert findings[0].target_path == "C:\\SIAFW\\SIAFW.EXE"
    assert findings[0].working_directory == "C:\\SIAFW"
    assert issues == []


def test_resolves_shortcut_without_interpolating_path_into_command(monkeypatch, tmp_path):
    shortcut = tmp_path / "SIAF atendimento.lnk"
    shortcut.write_bytes(b"shortcut")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout="C:\\SIAFW\\SIAFW.EXE\nC:\\SIAFW\n",
            stderr="",
        )

    monkeypatch.setattr(shortcut_detector.subprocess, "run", fake_run)

    target, working_directory = shortcut_detector.resolve_windows_shortcut(shortcut)

    assert target == "C:\\SIAFW\\SIAFW.EXE"
    assert working_directory == "C:\\SIAFW"
    assert str(shortcut) not in " ".join(captured["command"])
    assert captured["kwargs"]["env"]["SIAF_SHORTCUT_PATH"] == str(shortcut)
    assert captured["kwargs"]["timeout"] == 3
