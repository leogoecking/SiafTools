from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from siaf_support_toolbox.core.paths import AppPaths  # noqa: E402
from siaf_support_toolbox.database.sqlite_connection import SQLiteDatabase  # noqa: E402
from siaf_support_toolbox.discovery.models import (  # noqa: E402
    Architecture,
    DatabaseCandidate,
    DiscoveryReport,
    MachineMode,
    ProcessFinding,
)
from siaf_support_toolbox.repositories.local_repository import LocalRepository  # noqa: E402
from siaf_support_toolbox.services.query_execution_service import (  # noqa: E402
    QueryExecutionService,
)
from siaf_support_toolbox.services.query_export_service import (  # noqa: E402
    QueryExportResult,
)
from siaf_support_toolbox.services.query_result_store import QueryResultPage  # noqa: E402
from siaf_support_toolbox.services.schema_inspection_service import (  # noqa: E402
    SchemaInspectionService,
)
from siaf_support_toolbox.ui.dialogs import show_message  # noqa: E402
from siaf_support_toolbox.ui.dialogs.connection_dialog import (  # noqa: E402
    CredentialsDialog,
    ManualConnectionDialog,
)
from siaf_support_toolbox.ui.dialogs.message_dialog import MessageDialog  # noqa: E402
from siaf_support_toolbox.ui.main_window import MainWindow  # noqa: E402
from siaf_support_toolbox.ui.navigation import NAVIGATION_ITEMS  # noqa: E402
from siaf_support_toolbox.ui.preferences import WindowPreferencesStore  # noqa: E402


def main() -> int:
    root = PROJECT_ROOT / ".test-artifacts" / "ui-smoke"
    paths = AppPaths(root, root / "data", root / "logs", root / "exports").ensure()
    store = WindowPreferencesStore(paths.data / "window-state.json")
    database = SQLiteDatabase(paths.data / "ui-smoke.sqlite3")
    database.initialize()
    repository = LocalRepository(database)
    query_service = QueryExecutionService(
        repository,
        SchemaInspectionService(repository),
        paths.data / "query-cache",
        paths.exports,
    )
    window = MainWindow(
        paths=paths,
        preferences_store=store,
        query_service=query_service,
        auto_discover=False,
    )
    window.withdraw()

    visited: list[str] = []
    for item in NAVIGATION_ITEMS:
        window.navigate(item.page_id)
        window.update_idletasks()
        visited.append(window.current_page)
    window.query_page.render_page(
        ("TESTE", "DATA", "VALOR"),
        QueryResultPage(
            1, 100, 1, (("resultado anterior", date(2026, 7, 19), Decimal("10.25")),)
        ),
    )
    rendered_details = window.query_page.detail_text.get("1.0", "end")
    selected_details_rendered = all(
        expected in rendered_details
        for expected in (
            "TESTE: resultado anterior",
            "DATA: 19/07/2026",
            "VALOR: 10.25",
        )
    )
    window.query_page.set_export_available(True)
    export_actions_enabled = (
        not window.query_page.csv_button.instate(["disabled"])
        and not window.query_page.xlsx_button.instate(["disabled"])
    )
    widest_template = max(
        window.query_page._templates, key=lambda item: len(item.parameters_schema)
    )
    window.query_page._render_template(widest_template)
    parameter_rows = {
        int(child.grid_info()["row"])
        for child in window.query_page.parameters.winfo_children()
    }
    operational_filters_compact = (
        len(widest_template.parameters_schema) == 7
        and len(parameter_rows) == 4
        and "exige ao menos um filtro" in window.query_page.description.cget("text")
    )
    phase_eight_limits_persisted = all(
        template.result_limit == 500
        for template in window.query_page._templates
        if template.module in {"Fiscal", "Entradas", "PDV"}
    )
    phase_nine_templates = tuple(
        template
        for template in window.query_page._templates
        if template.module in {"Financeiro", "Caixa", "Permissões"}
    )
    phase_nine_templates_ready = (
        len(phase_nine_templates) == 10
        and all(
            template.result_limit is None
            if template.name == "Permissões — diagnóstico por usuário, grupo e programa"
            else template.result_limit == 500
            for template in phase_nine_templates
        )
        and all(
            "USU_SENHA" not in template.sql_template.upper()
            for template in phase_nine_templates
        )
    )
    window.query_page.clear_results()
    stale_query_result_cleared = not window.query_page.tree.get_children()
    stale_export_actions_disabled = (
        window.query_page.csv_button.instate(["disabled"])
        and window.query_page.xlsx_button.instate(["disabled"])
    )
    window.output_label.configure(text="Arquivo: C:/exports/resultado-anterior.csv")
    window._render_query_export(QueryExportResult(False, "csv", canceled=True))
    stale_output_file_cleared = window.output_label.cget("text") == "Arquivo: —"
    window.toggle_theme()
    final_theme = window.current_theme

    def close_dialog() -> None:
        for child in window.winfo_children():
            if isinstance(child, MessageDialog):
                child._confirm()

    window.after(50, close_dialog)
    dialog_result = show_message(window, "Teste de diálogo", "Diálogo reutilizável disponível.")

    credentials_dialog = CredentialsDialog(window)
    credentials_dialog.withdraw()
    credentials_dialog.username.insert(0, "SUPORTE")
    credentials_dialog.password.insert(0, "session-only")
    credentials_dialog._submit()
    credentials_result = credentials_dialog.result
    credentials_dialog_ok = credentials_result is not None
    if credentials_result:
        credentials_result.clear()

    manual_dialog = ManualConnectionDialog(window)
    manual_dialog.withdraw()
    manual_dialog.entries["database_path"].insert(0, "D:/Dados/SIAFLOJA.FDB")
    manual_dialog.entries["client_library"].insert(0, "C:/Firebird/fbclient.dll")
    manual_dialog.entries["username"].insert(0, "SUPORTE")
    manual_dialog.entries["password"].insert(0, "session-only")
    manual_dialog._submit_manual()
    manual_dialog_ok = manual_dialog.manual_result is not None and manual_dialog.result is not None
    if manual_dialog.result:
        manual_dialog.result.clear()

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
    window.environment_page.set_actions(
        validate=True, export=True, manual=True, inspect=True
    )
    window._render_error(RuntimeError("reanálise indisponível"))
    stale_header_cleared = (
        window.mode_label.cget("text") == "Modo: não confirmado"
        and window.firebird_label.cget("text") == "Firebird: não confirmado"
        and window.base_label.cget("text") == "Bases: não confirmadas"
    )
    stale_actions_disabled = (
        window.environment_page.validate_button.instate(["disabled"])
        and window.environment_page.export_button.instate(["disabled"])
        and window.environment_page.manual_button.instate(["disabled"])
        and window.environment_page.inspect_button.instate(["disabled"])
        and window._last_report is None
        and not window._last_plan.targets
    )
    window.close()

    print(
        json.dumps(
            {
                "visited": visited,
                "final_theme": final_theme,
                "closed": True,
                "dialog_result": dialog_result,
                "credentials_dialog_ok": credentials_dialog_ok,
                "manual_dialog_ok": manual_dialog_ok,
                "preferences_saved": store.path.is_file(),
                "settings_visible_at_high_dpi": settings_visible,
                "query_templates": len(query_service.list_templates()),
                "stale_query_result_cleared": stale_query_result_cleared,
                "selected_details_rendered": selected_details_rendered,
                "export_actions_enabled": export_actions_enabled,
                "operational_filters_compact": operational_filters_compact,
                "phase_eight_limits_persisted": phase_eight_limits_persisted,
                "phase_nine_templates_ready": phase_nine_templates_ready,
                "stale_export_actions_disabled": stale_export_actions_disabled,
                "stale_output_file_cleared": stale_output_file_cleared,
                "stale_header_cleared": stale_header_cleared,
                "stale_actions_disabled": stale_actions_disabled,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
