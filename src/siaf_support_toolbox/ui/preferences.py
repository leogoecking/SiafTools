from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from siaf_support_toolbox.ui.navigation import DEFAULT_PAGE_ID, VALID_PAGE_IDS

LOGGER = logging.getLogger(__name__)

DEFAULT_WIDTH = 1120
DEFAULT_HEIGHT = 720
MINIMUM_WIDTH = 900
MINIMUM_HEIGHT = 600
VALID_THEMES = frozenset({"light", "dark"})


@dataclass(frozen=True, slots=True)
class WindowPreferences:
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    x: int | None = None
    y: int | None = None
    maximized: bool = False
    theme: str = "light"
    selected_page: str = DEFAULT_PAGE_ID

    def normalized(
        self,
        screen_width: int | None = None,
        screen_height: int | None = None,
    ) -> WindowPreferences:
        width = max(MINIMUM_WIDTH, self.width)
        height = max(MINIMUM_HEIGHT, self.height)
        if screen_width:
            width = min(width, screen_width)
        if screen_height:
            height = min(height, screen_height)

        x = self.x
        y = self.y
        if screen_width:
            x = x if x is not None else max(0, (screen_width - width) // 2)
            x = max(0, min(x, max(0, screen_width - width)))
        if screen_height:
            y = y if y is not None else max(0, (screen_height - height) // 2)
            y = max(0, min(y, max(0, screen_height - height)))

        theme = self.theme if self.theme in VALID_THEMES else "light"
        selected_page = (
            self.selected_page if self.selected_page in VALID_PAGE_IDS else DEFAULT_PAGE_ID
        )
        return WindowPreferences(
            width=width,
            height=height,
            x=x,
            y=y,
            maximized=self.maximized,
            theme=theme,
            selected_page=selected_page,
        )


class WindowPreferencesStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> WindowPreferences:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("estado da janela precisa ser um objeto JSON")
            return _preferences_from_payload(payload)
        except FileNotFoundError:
            return WindowPreferences()
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            LOGGER.warning("Estado da janela ignorado: %s", exc)
            return WindowPreferences()

    def save(self, preferences: WindowPreferences) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(asdict(preferences), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def _preferences_from_payload(payload: dict[str, Any]) -> WindowPreferences:
    return WindowPreferences(
        width=_integer(payload.get("width"), DEFAULT_WIDTH),
        height=_integer(payload.get("height"), DEFAULT_HEIGHT),
        x=_optional_integer(payload.get("x")),
        y=_optional_integer(payload.get("y")),
        maximized=payload.get("maximized") is True,
        theme=str(payload.get("theme", "light")),
        selected_page=str(payload.get("selected_page", DEFAULT_PAGE_ID)),
    ).normalized()


def _integer(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _optional_integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
