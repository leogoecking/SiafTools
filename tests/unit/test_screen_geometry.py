from siaf_support_toolbox.ui import screen_geometry
from siaf_support_toolbox.ui.screen_geometry import (
    ScreenBounds,
    detect_screen_bounds,
    format_geometry,
)


class FakeRoot:
    def winfo_vrootx(self):
        return -100

    def winfo_vrooty(self):
        return -50

    def winfo_vrootwidth(self):
        return 3000

    def winfo_vrootheight(self):
        return 1200

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080


def test_detect_screen_bounds_uses_windows_virtual_desktop(monkeypatch):
    monkeypatch.setattr(screen_geometry.sys, "platform", "win32")
    values = {76: -1920, 77: 0, 78: 3840, 79: 1080}

    bounds = detect_screen_bounds(FakeRoot(), values.__getitem__)

    assert bounds == ScreenBounds(-1920, 0, 3840, 1080)


def test_detect_screen_bounds_falls_back_to_tk_virtual_root(monkeypatch):
    monkeypatch.setattr(screen_geometry.sys, "platform", "linux")

    assert detect_screen_bounds(FakeRoot()) == ScreenBounds(-100, -50, 3000, 1200)


def test_format_geometry_supports_negative_monitor_coordinates():
    assert format_geometry(1120, 720, -1600, 80) == "1120x720-1600+80"
