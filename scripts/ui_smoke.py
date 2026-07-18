from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from siaf_support_toolbox.core.paths import AppPaths  # noqa: E402
from siaf_support_toolbox.ui.dialogs import show_message  # noqa: E402
from siaf_support_toolbox.ui.dialogs.message_dialog import MessageDialog  # noqa: E402
from siaf_support_toolbox.ui.main_window import MainWindow  # noqa: E402
from siaf_support_toolbox.ui.navigation import NAVIGATION_ITEMS  # noqa: E402
from siaf_support_toolbox.ui.preferences import WindowPreferencesStore  # noqa: E402


def main() -> int:
    root = PROJECT_ROOT / ".test-artifacts" / "ui-smoke"
    paths = AppPaths(root, root / "data", root / "logs", root / "exports").ensure()
    store = WindowPreferencesStore(paths.data / "window-state.json")
    window = MainWindow(paths=paths, preferences_store=store, auto_discover=False)
    window.withdraw()

    visited: list[str] = []
    for item in NAVIGATION_ITEMS:
        window.navigate(item.page_id)
        window.update_idletasks()
        visited.append(window.current_page)
    window.toggle_theme()
    final_theme = window.current_theme

    def close_dialog() -> None:
        for child in window.winfo_children():
            if isinstance(child, MessageDialog):
                child._confirm()

    window.after(50, close_dialog)
    dialog_result = show_message(window, "Teste de diálogo", "Diálogo reutilizável disponível.")
    window.close()

    print(
        json.dumps(
            {
                "visited": visited,
                "final_theme": final_theme,
                "closed": True,
                "dialog_result": dialog_result,
                "preferences_saved": store.path.is_file(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
