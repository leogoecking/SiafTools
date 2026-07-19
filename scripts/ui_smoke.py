from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from siaf_support_toolbox.core.paths import AppPaths  # noqa: E402
from siaf_support_toolbox.discovery.models import (  # noqa: E402
    Architecture,
    DatabaseCandidate,
    DiscoveryReport,
    MachineMode,
    ProcessFinding,
)
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

    window.attributes("-alpha", 0.0)
    window.deiconify()
    window.tk.call("tk", "scaling", 2.0)
    window.geometry("900x600+0+0")
    window.update()
    window.navigate("settings")
    window.update()
    settings_button = window._navigation_buttons["settings"]
    canvas = window.sidebar.canvas
    settings_visible = (
        settings_button.winfo_rooty() >= canvas.winfo_rooty()
        and settings_button.winfo_rooty() + settings_button.winfo_height()
        <= canvas.winfo_rooty() + canvas.winfo_height()
    )

    report = DiscoveryReport(
        process_architecture=Architecture.X86,
        process_bits=32,
        mode=MachineMode.LOCAL_SERVER,
        firebird_processes=[ProcessFinding(1, "fbserver.exe")],
        databases=[DatabaseCandidate("C:/SIAFW/SIAFW.FDB", "SIAFW", 1, 90)],
    )
    window._render_report(report)
    window._render_error(RuntimeError("reanálise indisponível"))
    stale_header_cleared = (
        window.mode_label.cget("text") == "Modo: não confirmado"
        and window.firebird_label.cget("text") == "Firebird: não confirmado"
        and window.base_label.cget("text") == "Bases: não confirmadas"
    )
    window.close()

    print(
        json.dumps(
            {
                "visited": visited,
                "final_theme": final_theme,
                "closed": True,
                "dialog_result": dialog_result,
                "preferences_saved": store.path.is_file(),
                "settings_visible_at_high_dpi": settings_visible,
                "stale_header_cleared": stale_header_cleared,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
