from __future__ import annotations

import tkinter as tk
from dataclasses import fields
from decimal import Decimal
from tkinter import ttk

from siaf_support_toolbox.fiscal.nfe_xml_reader import NFeDocument
from siaf_support_toolbox.services.supplier_return_preparation_service import (
    TOTAL_FIELD_LABELS,
    ReturnItemPreparation,
    ReturnTotals,
    SupplierReturnPreparation,
    analyze_supplier_return_preparation,
    format_supplier_return_analysis,
    parse_optional_decimal,
    update_preparation_item,
    update_preparation_totals,
)
from siaf_support_toolbox.ui.screen_geometry import format_geometry


class SupplierReturnPreparationDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        document: NFeDocument,
        preparation: SupplierReturnPreparation,
    ) -> None:
        super().__init__(parent)
        if preparation.source_access_key != document.access_key:
            raise ValueError("A preparação não pertence ao XML carregado.")
        self.result: SupplierReturnPreparation | None = None
        self._document = document
        self._preparation = preparation
        self._analyzed_preparation: SupplierReturnPreparation | None = None
        self.title("Preparação manual da devolução")
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.minsize(900, 620)

        container = ttk.Frame(self, padding=16, style="Surface.TFrame")
        container.pack(fill="both", expand=True)
        ttk.Label(
            container,
            text="Preparação manual da devolução",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=(
                "Selecione os itens, informe os dados recebidos no espelho e, quando possível, "
                "copie os valores calculados na tela do SIAF. A análise não altera a nota."
            ),
            style="Subtitle.TLabel",
            wraplength=980,
        ).pack(anchor="w", pady=(4, 10))

        items_frame = ttk.LabelFrame(container, text="1. Itens que serão devolvidos", padding=8)
        items_frame.pack(fill="x")
        items_frame.grid_columnconfigure(0, weight=1)
        columns = ("selected", "item", "code", "description", "quantity", "unit", "total")
        self.tree = ttk.Treeview(
            items_frame,
            columns=columns,
            show="headings",
            height=6,
            selectmode="browse",
        )
        headings = {
            "selected": ("Devolver", 80, "center"),
            "item": ("Item", 50, "center"),
            "code": ("Código XML", 100, "w"),
            "description": ("Descrição", 270, "w"),
            "quantity": ("Quantidade", 95, "e"),
            "unit": ("Preço unit.", 95, "e"),
            "total": ("Total", 95, "e"),
        }
        for name, (label, width, anchor) in headings.items():
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, minwidth=45, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(items_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", self._edit_selected_item)

        item_actions = ttk.Frame(items_frame, style="Surface.TFrame")
        item_actions.grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            item_actions,
            text="Incluir/remover item",
            command=self._toggle_selected_item,
        ).pack(side="left")
        ttk.Button(
            item_actions,
            text="Informar quantidade e alíquotas",
            command=self._edit_selected_item,
        ).pack(side="left", padx=(8, 0))

        values_frame = ttk.LabelFrame(
            container,
            text="2. Valores manuais",
            padding=8,
        )
        values_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(
            values_frame,
            text="Preencher espelho e resultado do SIAF",
            command=self._edit_totals,
        ).pack(side="left")
        self.values_summary = tk.StringVar()
        ttk.Label(
            values_frame,
            textvariable=self.values_summary,
            style="Subtitle.TLabel",
        ).pack(side="left", padx=(12, 0))

        result_frame = ttk.LabelFrame(container, text="3. Análise orientada", padding=8)
        result_frame.pack(fill="both", expand=True, pady=(10, 0))
        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)
        surface = ttk.Style(self).lookup("Surface.TFrame", "background") or "#ffffff"
        foreground = ttk.Style(self).lookup("Surface.TLabel", "foreground") or "#202124"
        self.analysis_text = tk.Text(
            result_frame,
            height=12,
            wrap="word",
            state="disabled",
            background=surface,
            foreground=foreground,
            padx=10,
            pady=8,
        )
        self.analysis_text.grid(row=0, column=0, sticky="nsew")
        result_scroll = ttk.Scrollbar(
            result_frame,
            orient="vertical",
            command=self.analysis_text.yview,
        )
        result_scroll.grid(row=0, column=1, sticky="ns")
        self.analysis_text.configure(yscrollcommand=result_scroll.set)

        self.error_var = tk.StringVar()
        ttk.Label(
            container,
            textvariable=self.error_var,
            style="Subtitle.TLabel",
            wraplength=980,
        ).pack(fill="x", pady=(6, 0))
        actions = ttk.Frame(container, style="Surface.TFrame")
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Cancelar", command=self._cancel).pack(side="right")
        ttk.Button(
            actions,
            text="Guardar preparação e fechar",
            command=self._save,
        ).pack(side="right", padx=(0, 8))
        ttk.Button(
            actions,
            text="Analisar diferenças",
            command=self._analyze,
        ).pack(side="left")

        self._refresh_items()
        self._refresh_values_summary()
        self._set_analysis(
            "Selecione os itens e preencha os valores do espelho para iniciar a análise."
        )
        self.update_idletasks()
        self._center(parent)
        self.grab_set()

    @property
    def preparation(self) -> SupplierReturnPreparation:
        return self._preparation

    @property
    def analysis_is_current(self) -> bool:
        return self._analyzed_preparation == self._preparation

    def _toggle_selected_item(self) -> None:
        item = self._selected_item()
        if item is None:
            self.error_var.set("Selecione um item na grade.")
            return
        self._preparation = update_preparation_item(
            self._preparation,
            item.item_number,
            selected=not item.selected,
        )
        self.error_var.set("")
        self._refresh_items(selected=item.item_number)
        self._invalidate_analysis()

    def _edit_selected_item(self, _event: object = None) -> None:
        item = self._selected_item()
        if item is None:
            self.error_var.set("Selecione um item na grade.")
            return
        dialog = PreparationItemValuesDialog(self, item)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        try:
            self._preparation = update_preparation_item(
                self._preparation,
                item.item_number,
                selected=True,
                values=dialog.result,
            )
        except ValueError as error:
            self.error_var.set(str(error))
            return
        self.error_var.set("")
        self._refresh_items(selected=item.item_number)
        self._invalidate_analysis()

    def _edit_totals(self) -> None:
        dialog = PreparationTotalsDialog(
            self,
            self._document,
            self._preparation,
            self._preparation.mirror_totals,
            self._preparation.siaf_totals,
        )
        self.wait_window(dialog)
        if dialog.result is None:
            return
        mirror_values, siaf_values = dialog.result
        try:
            updated = update_preparation_totals(
                self._preparation,
                source="mirror",
                values=mirror_values,
            )
            self._preparation = update_preparation_totals(
                updated,
                source="siaf",
                values=siaf_values,
            )
        except ValueError as error:
            self.error_var.set(str(error))
            return
        self.error_var.set("")
        self._refresh_values_summary()
        self._invalidate_analysis()

    def _analyze(self) -> None:
        analysis = analyze_supplier_return_preparation(self._preparation)
        self._set_analysis(format_supplier_return_analysis(analysis))
        self._analyzed_preparation = self._preparation
        self.error_var.set("")

    def _save(self) -> None:
        self.result = self._preparation
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _selected_item(self) -> ReturnItemPreparation | None:
        selected = self.tree.selection()
        if not selected:
            return None
        item_number = int(selected[0])
        return next(
            (item for item in self._preparation.items if item.item_number == item_number),
            None,
        )

    def _refresh_items(self, *, selected: int | None = None) -> None:
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
        for item in self._preparation.items:
            self.tree.insert(
                "",
                "end",
                iid=str(item.item_number),
                values=(
                    "Sim" if item.selected else "Não",
                    item.item_number,
                    item.product_code,
                    item.description,
                    _decimal_text(item.return_quantity),
                    _money_text(item.unit_value),
                    _money_text(item.product_total),
                ),
            )
        target = str(selected) if selected is not None else None
        if target and self.tree.exists(target):
            self.tree.selection_set(target)
            self.tree.focus(target)

    def _refresh_values_summary(self) -> None:
        mirror_count = _filled_total_count(self._preparation.mirror_totals)
        siaf_count = _filled_total_count(self._preparation.siaf_totals)
        self.values_summary.set(
            f"{mirror_count} campo(s) do espelho e {siaf_count} campo(s) do SIAF informados"
        )

    def _set_analysis(self, text: str) -> None:
        self.analysis_text.configure(state="normal")
        self.analysis_text.delete("1.0", "end")
        self.analysis_text.insert("1.0", text)
        self.analysis_text.configure(state="disabled")

    def _invalidate_analysis(self) -> None:
        self._analyzed_preparation = None
        self._set_analysis(
            "Valores alterados. Clique em “Analisar diferenças” para atualizar o resultado."
        )

    def _center(self, parent: tk.Misc) -> None:
        width = min(1120, max(900, parent.winfo_width() - 50))
        height = min(820, max(620, parent.winfo_height() - 40))
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
        self.geometry(format_geometry(width, height, x, y))


class PreparationItemValuesDialog(tk.Toplevel):
    _ROWS = (
        ("return_quantity", "Quantidade devolvida", "original_quantity", None),
        ("unit_value", "Preço unitário", "original_unit_value", None),
        (
            "mirror_product_total",
            "Total do item",
            "original_product_value",
            "siaf_product_total",
        ),
        ("mirror_icms_rate", "% ICMS", "original_icms_rate", "siaf_icms_rate"),
        (
            "mirror_reduction_rate",
            "% Redução ICMS",
            "original_reduction_rate",
            "siaf_reduction_rate",
        ),
        ("mirror_ipi_rate", "% IPI", "original_ipi_rate", "siaf_ipi_rate"),
    )

    def __init__(self, parent: tk.Misc, item: ReturnItemPreparation) -> None:
        super().__init__(parent)
        self.result: dict[str, str] | None = None
        self._item = item
        self._entries: dict[str, ttk.Entry] = {}
        self.title(f"Valores do item {item.item_number}")
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        container = ttk.Frame(self, padding=16, style="Surface.TFrame")
        container.pack(fill="both", expand=True)
        ttk.Label(
            container,
            text=f"Item {item.item_number} — {item.description}",
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        for column, label in enumerate(("Campo", "XML de entrada", "Espelho", "SIAF atual")):
            ttk.Label(container, text=label, style="TopInfo.TLabel").grid(
                row=1,
                column=column,
                sticky="w",
                padx=5,
            )
        for row, (mirror_name, label, original_name, siaf_name) in enumerate(
            self._ROWS,
            start=2,
        ):
            ttk.Label(container, text=label, style="Surface.TLabel").grid(
                row=row, column=0, sticky="w", padx=5, pady=4
            )
            ttk.Label(
                container,
                text=_optional_decimal_text(getattr(item, original_name)),
                style="Surface.TLabel",
            ).grid(row=row, column=1, sticky="ew", padx=5, pady=4)
            mirror_entry = ttk.Entry(container, width=18)
            mirror_entry.insert(0, _entry_text(getattr(item, mirror_name)))
            mirror_entry.grid(row=row, column=2, sticky="ew", padx=5, pady=4)
            self._entries[mirror_name] = mirror_entry
            if siaf_name is not None:
                siaf_entry = ttk.Entry(container, width=18)
                siaf_entry.insert(0, _entry_text(getattr(item, siaf_name)))
                siaf_entry.grid(row=row, column=3, sticky="ew", padx=5, pady=4)
                self._entries[siaf_name] = siaf_entry
            else:
                ttk.Label(container, text="—", style="Surface.TLabel").grid(
                    row=row, column=3, sticky="w", padx=5, pady=4
                )
        self.error_var = tk.StringVar()
        ttk.Label(
            container,
            textvariable=self.error_var,
            style="Subtitle.TLabel",
        ).grid(row=8, column=0, columnspan=4, sticky="ew", pady=(8, 4))
        actions = ttk.Frame(container, style="Surface.TFrame")
        actions.grid(row=9, column=0, columnspan=4, sticky="e")
        ttk.Button(actions, text="Cancelar", command=self._cancel).pack(side="right")
        ttk.Button(actions, text="Aplicar", command=self._submit).pack(
            side="right", padx=(0, 8)
        )
        self.update_idletasks()
        self._center(parent, 720, 390)
        self.grab_set()

    def _submit(self) -> None:
        result: dict[str, str] = {}
        parsed_values: dict[str, Decimal | None] = {}
        labels = {
            mirror_name: label for mirror_name, label, _original, _siaf in self._ROWS
        }
        labels.update(
            {
                siaf_name: f"{label} no SIAF"
                for _mirror, label, _original, siaf_name in self._ROWS
                if siaf_name is not None
            }
        )
        for name, entry in self._entries.items():
            try:
                parsed = parse_optional_decimal(entry.get(), label=labels[name])
            except ValueError as error:
                self.error_var.set(str(error))
                entry.focus_set()
                return
            if name in {"return_quantity", "unit_value"} and parsed is None:
                self.error_var.set(f"{labels[name]} é obrigatório.")
                entry.focus_set()
                return
            if name.endswith("_rate") and parsed is not None and parsed > 100:
                self.error_var.set(f"{labels[name]} não pode superar 100%.")
                entry.focus_set()
                return
            parsed_values[name] = parsed
            result[name] = "" if parsed is None else str(parsed)
        quantity = parsed_values["return_quantity"]
        if quantity is not None and quantity > self._item.original_quantity:
            self.error_var.set(
                "A quantidade devolvida não pode superar a quantidade da nota de entrada."
            )
            self._entries["return_quantity"].focus_set()
            return
        self.result = result
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _center(self, parent: tk.Misc, width: int, height: int) -> None:
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
        self.geometry(format_geometry(width, height, x, y))


class PreparationTotalsDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        document: NFeDocument,
        preparation: SupplierReturnPreparation,
        mirror: ReturnTotals,
        siaf: ReturnTotals,
    ) -> None:
        super().__init__(parent)
        self.result: tuple[dict[str, str], dict[str, str]] | None = None
        self._entries: dict[tuple[str, str], ttk.Entry] = {}
        self.title("Totais do espelho e do SIAF")
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.minsize(760, 520)
        container = ttk.Frame(self, padding=16, style="Surface.TFrame")
        container.pack(fill="both", expand=True)
        ttk.Label(
            container,
            text="Valores totais da devolução",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=(
                "Preencha o que estiver visível. Campos do SIAF podem ficar vazios quando "
                "a nota ainda não tiver sido montada."
            ),
            style="Subtitle.TLabel",
            wraplength=820,
        ).pack(anchor="w", pady=(4, 10))

        host = ttk.Frame(container, style="Surface.TFrame")
        host.pack(fill="both", expand=True)
        host.grid_rowconfigure(0, weight=1)
        host.grid_columnconfigure(0, weight=1)
        surface = ttk.Style(self).lookup("Surface.TFrame", "background") or "#ffffff"
        canvas = tk.Canvas(host, borderwidth=0, highlightthickness=0, background=surface)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(host, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        rows = ttk.Frame(canvas, padding=(2, 2), style="Surface.TFrame")
        window_id = canvas.create_window((0, 0), window=rows, anchor="nw")
        for column, label in enumerate(
            ("Campo", "XML completo", "Seleção atual", "Espelho", "SIAF atual")
        ):
            ttk.Label(rows, text=label, style="TopInfo.TLabel").grid(
                row=0, column=column, sticky="w", padx=5, pady=(0, 4)
            )
            rows.grid_columnconfigure(column, weight=1)
        xml_values = _document_total_values(document)
        selection_values = _selection_total_values(preparation)
        for row, (name, label) in enumerate(TOTAL_FIELD_LABELS.items(), start=1):
            ttk.Label(rows, text=label, style="Surface.TLabel").grid(
                row=row, column=0, sticky="w", padx=5, pady=3
            )
            ttk.Label(
                rows,
                text=xml_values.get(name, "—"),
                style="Surface.TLabel",
            ).grid(row=row, column=1, sticky="ew", padx=5, pady=3)
            ttk.Label(
                rows,
                text=selection_values.get(name, "—"),
                style="Surface.TLabel",
            ).grid(row=row, column=2, sticky="ew", padx=5, pady=3)
            for column, (source, totals) in enumerate(
                (("mirror", mirror), ("siaf", siaf)),
                start=3,
            ):
                if source == "siaf" and not _is_siaf_total_editable(name):
                    ttk.Label(
                        rows,
                        text="Use Desp.Acess. ou Acréscimo",
                        style="Subtitle.TLabel",
                        wraplength=170,
                    ).grid(row=row, column=column, sticky="ew", padx=5, pady=3)
                    continue
                entry = ttk.Entry(rows, width=18)
                entry.insert(0, _entry_text(getattr(totals, name)))
                entry.grid(row=row, column=column, sticky="ew", padx=5, pady=3)
                self._entries[(source, name)] = entry
        rows.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )

        self.error_var = tk.StringVar()
        ttk.Label(
            container,
            textvariable=self.error_var,
            style="Subtitle.TLabel",
        ).pack(fill="x", pady=(6, 2))
        actions = ttk.Frame(container, style="Surface.TFrame")
        actions.pack(fill="x")
        ttk.Button(actions, text="Cancelar", command=self._cancel).pack(side="right")
        ttk.Button(actions, text="Aplicar valores", command=self._submit).pack(
            side="right", padx=(0, 8)
        )
        self.update_idletasks()
        self._center(parent)
        self.grab_set()

    def _submit(self) -> None:
        result = {"mirror": {}, "siaf": {"packaging": ""}}
        for (source, name), entry in self._entries.items():
            try:
                parsed = parse_optional_decimal(
                    entry.get(),
                    label=TOTAL_FIELD_LABELS[name],
                )
            except ValueError as error:
                self.error_var.set(str(error))
                entry.focus_set()
                return
            if (
                name in {"icms_rate", "icms_reduction_rate", "ipi_rate"}
                and parsed is not None
                and parsed > 100
            ):
                self.error_var.set(f"{TOTAL_FIELD_LABELS[name]} não pode superar 100%.")
                entry.focus_set()
                return
            result[source][name] = "" if parsed is None else str(parsed)
        self.result = result["mirror"], result["siaf"]
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _center(self, parent: tk.Misc) -> None:
        width = min(900, max(760, parent.winfo_width() - 100))
        height = min(720, max(520, parent.winfo_height() - 80))
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
        self.geometry(format_geometry(width, height, x, y))


def edit_supplier_return_preparation(
    parent: tk.Misc,
    document: NFeDocument,
    preparation: SupplierReturnPreparation,
) -> SupplierReturnPreparation | None:
    dialog = SupplierReturnPreparationDialog(parent, document, preparation)
    parent.wait_window(dialog)
    return dialog.result


def _document_total_values(document: NFeDocument) -> dict[str, str]:
    xml_names = {
        "merchandise": "vProd",
        "discount": "vDesc",
        "freight": "vFrete",
        "insurance": "vSeg",
        "additional_expenses": "vOutro",
        "icms_base": "vBC",
        "icms_value": "vICMS",
        "ipi_value": "vIPI",
        "st_base": "vBCST",
        "st_value": "vST",
        "invoice_total": "vNF",
    }
    values: dict[str, str] = {}
    for target, xml_name in xml_names.items():
        field = next(
            (
                field
                for field in document.total_fields
                if field.path.rsplit(".", 1)[-1] == xml_name
            ),
            None,
        )
        if field is not None:
            values[target] = field.value
    return values


def _selection_total_values(
    preparation: SupplierReturnPreparation,
) -> dict[str, str]:
    return {
        "merchandise": _money_text(preparation.calculated_merchandise),
    }


def _is_siaf_total_editable(name: str) -> bool:
    return name != "packaging"


def _filled_total_count(totals: ReturnTotals) -> int:
    return sum(getattr(totals, field.name) is not None for field in fields(ReturnTotals))


def _entry_text(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f").replace(".", ",")


def _optional_decimal_text(value: Decimal | None) -> str:
    return "não informado" if value is None else _decimal_text(value)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f").replace(".", ",")


def _money_text(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",")
