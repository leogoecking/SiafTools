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
    SiafInstallationFinding,
)
from siaf_support_toolbox.fiscal.nfe_xml_reader import (  # noqa: E402
    NFeDocument,
    NFeField,
    NFeItem,
    NFeParty,
    NFeXmlError,
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
from siaf_support_toolbox.ui.dialogs.supplier_return_mirror_dialog import (  # noqa: E402
    SupplierReturnMirrorDialog,
)
from siaf_support_toolbox.ui.dialogs.supplier_return_preparation_dialog import (  # noqa: E402
    SupplierReturnPreparationDialog,
)
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
    phase_eight_unlimited_results = all(
        template.result_limit is None
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
        and all(template.result_limit is None for template in phase_nine_templates)
        and all(
            "USU_SENHA" not in template.sql_template.upper()
            for template in phase_nine_templates
        )
    )
    all_standard_templates_unlimited = all(
        template.result_limit is None for template in window.query_page._templates
    )
    diagnostic_document = NFeDocument(
        access_key="35260712345678000123550010000001231000001234",
        protocol_number="135260000000123",
        protocol_status="100",
        authorization_datetime="2026-07-26T10:01:00-03:00",
        model="55",
        series="1",
        number="123",
        issue_datetime="2026-07-26T10:00:00-03:00",
        issuer=NFeParty("12345678000123", "FORNECEDOR TESTE", "123", "SP"),
        recipient=NFeParty("98765432000198", "EMPRESA CLIENTE", "987", "MG"),
        items=(
            NFeItem(
                number=1,
                product_code="ABC-1",
                barcode="7891234567890",
                description="PRODUTO DE TESTE",
                ncm="12345678",
                cest="1234567",
                cfop="6102",
                unit="UN",
                quantity=Decimal("2.0000"),
                unit_value=Decimal("50.00"),
                product_value=Decimal("100.00"),
                discount=None,
                freight=None,
                insurance=None,
                other_expenses=None,
                tax_fields=(
                    NFeField(
                        "imposto.ICMS.ICMS00.pICMS",
                        "Alíquota de ICMS",
                        "12.0000",
                    ),
                ),
            ),
        ),
        total_fields=(NFeField("total.ICMSTot.vNF", "Total da NF-e", "100.00"),),
    )
    window.diagnostic_page.render_document(diagnostic_document, "entrada.xml")
    diagnostic_selection_ready = (
        window.diagnostic_page.document is diagnostic_document
        and len(window.diagnostic_page.tree.get_children()) == 1
        and window.diagnostic_page.summary_vars["file"].get() == "entrada.xml"
        and "imposto.ICMS.ICMS00.pICMS" in window.diagnostic_page.details.get("1.0", "end")
    )
    icms_comparison = next(
        field
        for field in window.diagnostic_page.comparison.fields
        if field.path == "imposto.ICMS.ICMS00.pICMS"
    )
    mirror_dialog = SupplierReturnMirrorDialog(
        window,
        "Espelho do item 1",
        (icms_comparison,),
    )
    mirror_dialog.withdraw()
    mirror_entry = mirror_dialog._entries["imposto.ICMS.ICMS00.pICMS"]
    mirror_entry.delete(0, "end")
    mirror_entry.insert(0, "18,00")
    mirror_dialog._submit()
    mirror_dialog_ok = mirror_dialog.result == {
        "imposto.ICMS.ICMS00.pICMS": "18.00"
    }
    window.diagnostic_page.apply_item_changes(1, mirror_dialog.result or {})
    diagnostic_manual_comparison_ready = (
        window.diagnostic_page.has_manual_changes
        and window.diagnostic_page.comparison.different_count == 1
        and "1 divergência(s)"
        in window.diagnostic_page.tree.item("1", "values")[-1]
        and "Espelho=18.00" in window.diagnostic_page.details.get("1.0", "end")
    )
    window.diagnostic_page.apply_total_changes({"total.ICMSTot.vNF": "105,00"})
    diagnostic_total_comparison_ready = (
        window.diagnostic_page.comparison.different_count == 2
        and any(
            field.path == "total.ICMSTot.vNF" and field.mirror_value == "105.00"
            for field in window.diagnostic_page.comparison.fields
        )
    )
    window.diagnostic_page._confirm_discard = lambda: False
    diagnostic_manual_changes_protected = (
        not window.diagnostic_page.load_xml("C:/dados/outro.xml")
        and window.diagnostic_page.document is diagnostic_document
        and window.diagnostic_page.has_manual_changes
    )
    window.diagnostic_page._confirm_discard = lambda: True
    window.diagnostic_page.reset_mirror()
    diagnostic_mirror_reset = (
        not window.diagnostic_page.has_manual_changes
        and window.diagnostic_page.comparison.matches
    )
    preparation_dialog = SupplierReturnPreparationDialog(
        window,
        diagnostic_document,
        window.diagnostic_page.preparation,
    )
    preparation_dialog.withdraw()
    preparation_dialog.tree.selection_set("1")
    preparation_dialog._toggle_selected_item()
    preparation_dialog._analyze()
    preparation_dialog_rendered = (
        preparation_dialog.preparation.selected_items[0].item_number == 1
        and "Mercadoria calculada" in preparation_dialog.analysis_text.get("1.0", "end")
    )
    analysis_was_current = preparation_dialog.analysis_is_current
    preparation_dialog._toggle_selected_item()
    preparation_analysis_invalidated = (
        analysis_was_current
        and not preparation_dialog.analysis_is_current
        and "Valores alterados"
        in preparation_dialog.analysis_text.get("1.0", "end")
    )
    preparation_dialog._toggle_selected_item()
    preparation_dialog._save()
    prepared_result = preparation_dialog.result
    window.diagnostic_page._preparation_editor = (
        lambda _parent, _document, _current: prepared_result
    )
    window.diagnostic_page.prepare_return()
    diagnostic_preparation_ready = (
        window.diagnostic_page.preparation is prepared_result
        and window.diagnostic_page.has_manual_changes
        and "1 item(ns)" in window.diagnostic_page.summary_vars["preparation"].get()
    )

    def invalid_xml_reader(_path):
        raise NFeXmlError("invalid_xml", "O arquivo não contém um XML válido.")

    window.diagnostic_page._xml_reader = invalid_xml_reader
    diagnostic_invalid_xml_clears_previous = (
        not window.diagnostic_page.load_xml("C:/dados/sensivel.xml")
        and window.diagnostic_page.document is None
        and not window.diagnostic_page.tree.get_children()
        and "sensivel.xml" not in window.diagnostic_page.status_var.get()
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
        installations=[
            SiafInstallationFinding(
                "C:/SIAFW",
                ("C:/SIAFW/SIAFW.EXE",),
                ("C:/SIAFW/SIAFW.FDB",),
                active=True,
                confidence=95,
            ),
            SiafInstallationFinding(
                "D:/SIAFW-2",
                ("D:/SIAFW-2/SIAFW.EXE",),
                ("D:/SIAFW-2/SIAFW.FDB",),
                confidence=70,
            ),
        ],
    )
    window._render_report(report)
    installation_values = tuple(window.environment_page.installation_selector.cget("values"))
    window.environment_page.installation_var.set(installation_values[1])
    multi_siaf_selection_ready = (
        len(installation_values) == 3
        and window.environment_page.selected_installation_root() == "D:/SIAFW-2"
    )
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
                "phase_eight_unlimited_results": phase_eight_unlimited_results,
                "phase_nine_templates_ready": phase_nine_templates_ready,
                "all_standard_templates_unlimited": all_standard_templates_unlimited,
                "diagnostic_selection_ready": diagnostic_selection_ready,
                "mirror_dialog_ok": mirror_dialog_ok,
                "diagnostic_manual_comparison_ready": (
                    diagnostic_manual_comparison_ready
                ),
                "diagnostic_total_comparison_ready": (
                    diagnostic_total_comparison_ready
                ),
                "diagnostic_manual_changes_protected": (
                    diagnostic_manual_changes_protected
                ),
                "diagnostic_mirror_reset": diagnostic_mirror_reset,
                "preparation_dialog_rendered": preparation_dialog_rendered,
                "preparation_analysis_invalidated": (
                    preparation_analysis_invalidated
                ),
                "diagnostic_preparation_ready": diagnostic_preparation_ready,
                "diagnostic_invalid_xml_clears_previous": (
                    diagnostic_invalid_xml_clears_previous
                ),
                "stale_export_actions_disabled": stale_export_actions_disabled,
                "stale_output_file_cleared": stale_output_file_cleared,
                "stale_header_cleared": stale_header_cleared,
                "stale_actions_disabled": stale_actions_disabled,
                "multi_siaf_selection_ready": multi_siaf_selection_ready,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
