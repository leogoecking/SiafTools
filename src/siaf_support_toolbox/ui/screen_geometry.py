from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass

_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79


@dataclass(frozen=True, slots=True)
class ScreenBounds:
    x: int
    y: int
    width: int
    height: int


def detect_screen_bounds(
    root: tk.Misc,
    metric_reader: Callable[[int], int] | None = None,
) -> ScreenBounds:
    if sys.platform == "win32":
        try:
            read_metric = metric_reader or ctypes.windll.user32.GetSystemMetrics
            bounds = ScreenBounds(
                x=int(read_metric(_SM_XVIRTUALSCREEN)),
                y=int(read_metric(_SM_YVIRTUALSCREEN)),
                width=int(read_metric(_SM_CXVIRTUALSCREEN)),
                height=int(read_metric(_SM_CYVIRTUALSCREEN)),
            )
            if bounds.width > 0 and bounds.height > 0:
                return bounds
        except (AttributeError, OSError, TypeError, ValueError):
            pass

    width = int(root.winfo_vrootwidth() or root.winfo_screenwidth())
    height = int(root.winfo_vrootheight() or root.winfo_screenheight())
    return ScreenBounds(
        x=int(root.winfo_vrootx()),
        y=int(root.winfo_vrooty()),
        width=width,
        height=height,
    )


def format_geometry(width: int, height: int, x: int, y: int) -> str:
    horizontal = f"+{x}" if x >= 0 else str(x)
    vertical = f"+{y}" if y >= 0 else str(y)
    return f"{width}x{height}{horizontal}{vertical}"
