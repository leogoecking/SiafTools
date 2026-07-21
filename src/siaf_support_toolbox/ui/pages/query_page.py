from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import date, datetime
from tkinter import ttk

from siaf_support_toolbox.database.sql_validator import (
    SQLParameterError,
    bind_parameters,
    validate_read_only_sql,
)
from siaf_support_toolbox.repositories.models import QueryTemplate
from siaf_support_toolbox.services.connection_service import ConnectionTarget, ConnectionValidation
from siaf_support_toolbox.services.query_execution_service import QueryExecutionSummary
from siaf_support_toolbox.services.query_result_store import QueryResultPage


class QueryPage(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        on_execute: Callable[[int, ConnectionTarget, int, dict[str, object]], None],
        on_export: Callable[[str], None],
        on_cancel: Callable[[], None],
        on_page: Callable[[int], None],
    ) -> None:
        super().__init__(parent, padding=20, style="App.TFrame")
        self._on_execute = on_execute
        self._on_export = on_export
        self._on_cancel = on_cancel
        self._on_page = on_page
        self._templates: list[QueryTemplate] = []
        self._databases: list[ConnectionValidation] = []
        self._parameter_vars: dict[str, tk.StringVar] = {}
        self._page_number = 1
        self._total_pages = 1
        self._current_columns: tuple[str, ...] = ()
        self._export_available = False
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        ttk.Label(self, text="Consultas somente leitura", style="PageTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            self,
            text=(
                "Escolha um template validado. A ferramenta confere a estrutura da base, "
                "executa em worker e pagina o resultado localmente."
            ),
            style="Muted.TLabel",
            wraplength=900,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 14))

        controls = ttk.Frame(self, style="Surface.TFrame", padding=14)
        controls.grid(row=2, column=0, sticky="ew")
        controls.grid_columnconfigure(1, weight=1)
        ttk.Label(controls, text="Base validada:", style="Surface.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.database_combo = ttk.Combobox(controls, state="readonly")
        self.database_combo.grid(row=0, column=1, sticky="ew")
        self.database_combo.bind("<<ComboboxSelected>>", self._database_selected)
        ttk.Label(controls, text="Template:", style="Surface.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(10, 0)
        )
        self.template_combo = ttk.Combobox(controls, state="readonly")
        self.template_combo.grid(row=1, column=1, sticky="ew", pady=(10, 0))
        self.template_combo.bind("<<ComboboxSelected>>", self._template_selected)
        self.description = ttk.Label(
            controls, text="", style="Surface.TLabel", wraplength=850, justify="left"
        )
        self.description.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.parameters = ttk.Frame(controls, style="Surface.TFrame")
        self.parameters.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.parameters.grid_columnconfigure(1, weight=1)
        self.parameters.grid_columnconfigure(3, weight=1)
        actions = ttk.Frame(controls, style="Surface.TFrame")
        actions.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        self.execute_button = ttk.Button(actions, text="Executar", command=self._execute)
        self.execute_button.grid(row=0, column=0, padx=(0, 8))
        self.csv_button = ttk.Button(
            actions,
            text="Exportar CSV",
            command=lambda: self._on_export("csv"),
            state="disabled",
        )
        self.csv_button.grid(row=0, column=1, padx=(0, 8))
        self.xlsx_button = ttk.Button(
            actions,
            text="Exportar XLSX",
            command=lambda: self._on_export("xlsx"),
            state="disabled",
        )
        self.xlsx_button.grid(row=0, column=2, padx=(0, 8))
        self.cancel_button = ttk.Button(
            actions, text="Cancelar", command=self._on_cancel, state="disabled"
        )
        self.cancel_button.grid(row=0, column=3)

        self.status = ttk.Label(self, text="Valide e inspecione uma base para consultar.")
        self.status.grid(row=3, column=0, sticky="ew", pady=(12, 6))

        result_pane = ttk.Panedwindow(self, orient="vertical")
        result_pane.grid(row=4, column=0, sticky="nsew")
        result = ttk.Frame(result_pane)
        result.grid_rowconfigure(0, weight=1)
        result.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(result, show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(result, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(result, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.bind("<<TreeviewSelect>>", self._show_selected_details)
        result_pane.add(result, weight=3)

        details = ttk.LabelFrame(
            result_pane, text="Detalhes do registro selecionado", padding=8
        )
        details.grid_rowconfigure(0, weight=1)
        details.grid_columnconfigure(0, weight=1)
        self.detail_text = tk.Text(details, height=7, wrap="word", state="disabled")
        self.detail_text.grid(row=0, column=0, sticky="nsew")
        detail_scroll = ttk.Scrollbar(
            details, orient="vertical", command=self.detail_text.yview
        )
        detail_scroll.grid(row=0, column=1, sticky="ns")
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        result_pane.add(details, weight=1)

        pager = ttk.Frame(self)
        pager.grid(row=5, column=0, sticky="e", pady=(8, 0))
        self.previous_button = ttk.Button(
            pager, text="Anterior", command=lambda: self._request_page(-1), state="disabled"
        )
        self.previous_button.grid(row=0, column=0)
        self.page_label = ttk.Label(pager, text="Página 1 de 1")
        self.page_label.grid(row=0, column=1, padx=10)
        self.next_button = ttk.Button(
            pager, text="Próxima", command=lambda: self._request_page(1), state="disabled"
        )
        self.next_button.grid(row=0, column=2)

    def set_templates(self, templates: list[QueryTemplate]) -> None:
        self._templates = templates
        self.template_combo.configure(values=[item.name for item in templates])
        if templates:
            self.template_combo.current(0)
            self._render_template(templates[0])

    def set_databases(self, databases: tuple[ConnectionValidation, ...]) -> None:
        self.clear_results()
        self._databases = [item for item in databases if item.database_id is not None]
        labels = [
            f"{item.result.classification.database_type if item.result.classification else 'SIAF'}"
            f" — {item.target.database_path}"
            for item in self._databases
        ]
        self.database_combo.configure(values=labels)
        if labels:
            self.database_combo.current(0)
            self.status.configure(text="Base pronta. Escolha um template e execute.")
        else:
            self.database_combo.set("")
            self.status.configure(text="Valide e inspecione uma base para consultar.")

    def set_busy(self, busy: bool) -> None:
        self.execute_button.configure(state="disabled" if busy else "normal")
        export_state = "normal" if self._export_available and not busy else "disabled"
        self.csv_button.configure(state=export_state)
        self.xlsx_button.configure(state=export_state)
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def set_export_available(self, available: bool) -> None:
        self._export_available = available
        state = "normal" if available else "disabled"
        self.csv_button.configure(state=state)
        self.xlsx_button.configure(state=state)

    def render_summary(self, summary: QueryExecutionSummary) -> None:
        if summary.canceled:
            text = (
                f"Consulta cancelada após {summary.records_processed} registro(s). "
                "O resultado disponível é parcial."
                if summary.partial
                else "Consulta cancelada antes do recebimento de registros."
            )
        elif summary.success and summary.truncated:
            text = (
                f"Limite atingido: exibindo os primeiros {summary.records_processed} "
                "registros. Refine os filtros para obter um resultado completo."
            )
        elif summary.success:
            text = (
                f"Consulta concluída: {summary.records_processed} registro(s) "
                f"em {summary.duration_ms} ms."
            )
        else:
            text = summary.message or "A consulta não pôde ser executada."
        self.status.configure(text=text)

    def render_progress(self, message: str) -> None:
        self.status.configure(text=message)

    def clear_results(self, message: str | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        self.tree.configure(columns=())
        self._current_columns = ()
        self.set_export_available(False)
        self._render_details(())
        self._page_number = 1
        self._total_pages = 1
        self.page_label.configure(text="Página 1 de 1")
        self.previous_button.configure(state="disabled")
        self.next_button.configure(state="disabled")
        if message is not None:
            self.status.configure(text=message)

    def render_page(self, columns: tuple[str, ...], page: QueryResultPage) -> None:
        self.tree.delete(*self.tree.get_children())
        self._current_columns = columns
        identifiers = tuple(f"column_{index}" for index in range(len(columns)))
        self.tree.configure(columns=identifiers)
        for identifier, label in zip(identifiers, columns, strict=True):
            self.tree.heading(identifier, text=label)
            self.tree.column(identifier, width=150, minwidth=70, stretch=True)
        for row in page.rows:
            self.tree.insert("", "end", values=tuple(_display_value(value) for value in row))
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
            self._show_selected_details()
        else:
            self._render_details(())
        self._page_number = page.number
        self._total_pages = page.total_pages
        self.page_label.configure(text=f"Página {page.number} de {page.total_pages}")
        self.previous_button.configure(state="normal" if page.number > 1 else "disabled")
        self.next_button.configure(
            state="normal" if page.number < page.total_pages else "disabled"
        )

    def _template_selected(self, _event: object = None) -> None:
        index = self.template_combo.current()
        if 0 <= index < len(self._templates):
            self.clear_results("Template alterado. Execute para carregar um novo resultado.")
            self._render_template(self._templates[index])

    def _database_selected(self, _event: object = None) -> None:
        self.clear_results("Base alterada. Execute para carregar um novo resultado.")

    def _render_template(self, template: QueryTemplate) -> None:
        requirements = ", ".join(template.required_tables) or "catálogo validado"
        filter_notice = (
            " · exige ao menos um filtro"
            if any(
                isinstance(definition, dict) and definition.get("require_one_of")
                for definition in template.parameters_schema.values()
            )
            else ""
        )
        self.description.configure(
            text=(
                f"{template.description}\nRequisitos: {requirements} · "
                f"Risco: {template.risk_level}{filter_notice}"
            )
        )
        for child in self.parameters.winfo_children():
            child.destroy()
        self._parameter_vars.clear()
        for index, (name, raw_definition) in enumerate(template.parameters_schema.items()):
            definition = raw_definition if isinstance(raw_definition, dict) else {}
            label = str(definition.get("label", name))
            variable = tk.StringVar(value=str(definition.get("default", "")))
            row = index // 2
            column = (index % 2) * 2
            ttk.Label(self.parameters, text=f"{label}:", style="Surface.TLabel").grid(
                row=row, column=column, sticky="w", padx=(12 if column else 0, 8), pady=3
            )
            ttk.Entry(self.parameters, textvariable=variable).grid(
                row=row, column=column + 1, sticky="ew", pady=3
            )
            self._parameter_vars[name] = variable

    def _execute(self) -> None:
        template_index = self.template_combo.current()
        database_index = self.database_combo.current()
        if not (0 <= template_index < len(self._templates)):
            self.status.configure(text="Selecione um template.")
            return
        if not (0 <= database_index < len(self._databases)):
            self.status.configure(text="Valide uma base antes de consultar.")
            return
        template = self._templates[template_index]
        database = self._databases[database_index]
        if template.id is None or database.database_id is None:
            self.status.configure(text="A seleção não possui identificador persistido.")
            return
        parameters = {
            name: variable.get().strip() for name, variable in self._parameter_vars.items()
        }
        required_groups = {
            str(definition.get("require_one_of"))
            for definition in template.parameters_schema.values()
            if isinstance(definition, dict) and definition.get("require_one_of")
        }
        for group in required_groups:
            grouped_names = {
                name
                for name, definition in template.parameters_schema.items()
                if isinstance(definition, dict)
                and str(definition.get("require_one_of")) == group
            }
            if not any(parameters.get(name) not in (None, "") for name in grouped_names):
                self.status.configure(
                    text="Informe pelo menos um filtro antes de executar a consulta."
                )
                return
        validation = validate_read_only_sql(template.sql_template)
        try:
            bind_parameters(validation, parameters, template.parameters_schema)
        except SQLParameterError as exc:
            self.status.configure(text=str(exc))
            return
        self._on_execute(
            template.id,
            database.target,
            database.database_id,
            parameters,
        )

    def _request_page(self, offset: int) -> None:
        requested = self._page_number + offset
        if 1 <= requested <= self._total_pages:
            self._on_page(requested)

    def _show_selected_details(self, _event: object = None) -> None:
        selection = self.tree.selection()
        if not selection:
            self._render_details(())
            return
        values = tuple(self.tree.item(selection[0], "values"))
        self._render_details(tuple(zip(self._current_columns, values, strict=False)))

    def _render_details(self, details: tuple[tuple[str, object], ...]) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        if details:
            self.detail_text.insert(
                "1.0", "\n".join(f"{label}: {value}" for label, value in details)
            )
        else:
            self.detail_text.insert("1.0", "Selecione um registro para ver seus campos.")
        self.detail_text.configure(state="disabled")


def _display_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return value
