from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, ttk

from siaf_support_toolbox.fiscal.nfe_xml_reader import (
    NFeDocument,
    NFeItem,
    NFeXmlError,
    read_nfe_xml,
)
from siaf_support_toolbox.services.supplier_return_diagnostic_service import (
    ComparisonStatus,
    FieldComparison,
    SupplierReturnComparison,
    SupplierReturnMirror,
    build_supplier_return_mirror,
    compare_supplier_return_mirror,
    update_mirror_field,
)
from siaf_support_toolbox.services.supplier_return_preparation_service import (
    SupplierReturnPreparation,
    build_supplier_return_preparation,
)
from siaf_support_toolbox.ui.dialogs.message_dialog import show_message
from siaf_support_toolbox.ui.dialogs.supplier_return_mirror_dialog import (
    edit_supplier_return_mirror,
)
from siaf_support_toolbox.ui.dialogs.supplier_return_preparation_dialog import (
    edit_supplier_return_preparation,
)
from siaf_support_toolbox.ui.theme import ThemePalette

XmlReader = Callable[[str | Path], NFeDocument]
FilePicker = Callable[[], str]
MirrorEditor = Callable[
    [tk.Misc, str, tuple[FieldComparison, ...]],
    dict[str, str] | None,
]
DiscardConfirmation = Callable[[], bool]
PreparationEditor = Callable[
    [tk.Misc, NFeDocument, SupplierReturnPreparation],
    SupplierReturnPreparation | None,
]


class SupplierReturnPage(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        xml_reader: XmlReader = read_nfe_xml,
        file_picker: FilePicker | None = None,
        mirror_editor: MirrorEditor = edit_supplier_return_mirror,
        preparation_editor: PreparationEditor = edit_supplier_return_preparation,
        confirm_discard: DiscardConfirmation | None = None,
    ) -> None:
        super().__init__(parent, padding=24, style="Surface.TFrame")
        self._xml_reader = xml_reader
        self._file_picker = file_picker or self._select_file
        self._mirror_editor = mirror_editor
        self._preparation_editor = preparation_editor
        self._confirm_discard = confirm_discard or self._ask_discard
        self._document: NFeDocument | None = None
        self._mirror: SupplierReturnMirror | None = None
        self._comparison: SupplierReturnComparison | None = None
        self._preparation: SupplierReturnPreparation | None = None
        self._dirty = False
        self._preparation_dirty = False
        self._items: dict[int, NFeItem] = {}

        heading = ttk.Frame(self, style="Surface.TFrame")
        heading.pack(fill="x")
        ttk.Label(
            heading,
            text="Diagnósticos — Devolução ao fornecedor",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            heading,
            text=(
                "Importe o XML da nota de entrada. O arquivo é processado localmente, "
                "não é alterado e não é gravado no banco."
            ),
            style="Subtitle.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(4, 0))

        actions = ttk.Frame(heading, style="Surface.TFrame")
        actions.pack(anchor="e", pady=(12, 0))
        self.select_button = ttk.Button(
            actions,
            text="Selecionar XML de entrada",
            command=self.select_xml,
        )
        self.select_button.pack(side="left", padx=2)
        self.clear_button = ttk.Button(
            actions,
            text="Limpar",
            command=self.clear,
            state="disabled",
        )
        self.clear_button.pack(side="left", padx=2)

        self.status_var = tk.StringVar(
            value="Nenhum XML selecionado. Somente NF-e modelo 55 é aceita nesta etapa."
        )
        self.status_label = ttk.Label(
            self,
            textvariable=self.status_var,
            style="Subtitle.TLabel",
            wraplength=900,
        )
        self.status_label.pack(fill="x", pady=(14, 8))

        summary = ttk.LabelFrame(self, text="Resumo da nota de entrada", padding=12)
        summary.pack(fill="x", pady=(0, 12))
        for column in range(4):
            summary.grid_columnconfigure(column, weight=1)
        self.summary_vars = {
            "file": tk.StringVar(value="—"),
            "key": tk.StringVar(value="—"),
            "number": tk.StringVar(value="—"),
            "issuer": tk.StringVar(value="—"),
            "recipient": tk.StringVar(value="—"),
            "items": tk.StringVar(value="0"),
            "protocol": tk.StringVar(value="—"),
            "mirror": tk.StringVar(value="—"),
            "preparation": tk.StringVar(value="—"),
        }
        summary_fields = (
            ("Arquivo", "file", 0, 0),
            ("NF-e", "number", 0, 2),
            ("Chave", "key", 1, 0),
            ("Itens", "items", 1, 2),
            ("Fornecedor/emitente", "issuer", 2, 0),
            ("Empresa/destinatário", "recipient", 2, 2),
            ("Protocolo SEFAZ", "protocol", 3, 0),
            ("Espelho manual", "mirror", 4, 0),
            ("Preparação guiada", "preparation", 4, 2),
        )
        for label, key, row, column in summary_fields:
            ttk.Label(summary, text=f"{label}:", style="TopInfo.TLabel").grid(
                row=row,
                column=column,
                sticky="nw",
                padx=(0, 6),
                pady=3,
            )
            ttk.Label(
                summary,
                textvariable=self.summary_vars[key],
                style="Surface.TLabel",
                wraplength=360,
            ).grid(
                row=row,
                column=column + 1,
                sticky="nw",
                padx=(0, 18),
                pady=3,
            )

        mirror_actions = ttk.Frame(self, style="Surface.TFrame")
        mirror_actions.pack(fill="x", pady=(0, 10))
        ttk.Label(
            mirror_actions,
            text="Preenchimento do espelho:",
            style="TopInfo.TLabel",
        ).pack(side="left")
        self.edit_item_button = ttk.Button(
            mirror_actions,
            text="Editar item selecionado",
            command=self.edit_selected_item,
            state="disabled",
        )
        self.edit_item_button.pack(side="left", padx=(8, 2))
        self.edit_totals_button = ttk.Button(
            mirror_actions,
            text="Editar totais",
            command=self.edit_totals,
            state="disabled",
        )
        self.edit_totals_button.pack(side="left", padx=2)
        self.reset_mirror_button = ttk.Button(
            mirror_actions,
            text="Restaurar valores do XML",
            command=self.reset_mirror,
            state="disabled",
        )
        self.reset_mirror_button.pack(side="left", padx=2)
        self.prepare_return_button = ttk.Button(
            mirror_actions,
            text="Preparar devolução",
            command=self.prepare_return,
            state="disabled",
        )
        self.prepare_return_button.pack(side="left", padx=(10, 2))

        content = ttk.Panedwindow(self, orient="vertical")
        content.pack(fill="both", expand=True)

        items_frame = ttk.LabelFrame(content, text="Itens encontrados", padding=8)
        items_frame.grid_rowconfigure(0, weight=1)
        items_frame.grid_columnconfigure(0, weight=1)
        columns = (
            "item",
            "codigo",
            "descricao",
            "ncm",
            "cfop",
            "unidade",
            "quantidade",
            "total",
            "situacao",
        )
        self.tree = ttk.Treeview(items_frame, columns=columns, show="headings", height=9)
        headings = {
            "item": ("Item", 55, "center"),
            "codigo": ("Código XML", 105, "w"),
            "descricao": ("Descrição", 260, "w"),
            "ncm": ("NCM", 90, "center"),
            "cfop": ("CFOP", 70, "center"),
            "unidade": ("Un.", 55, "center"),
            "quantidade": ("Quantidade", 95, "e"),
            "total": ("Valor produto", 105, "e"),
            "situacao": ("Espelho", 115, "center"),
        }
        for column, (label, width, anchor) in headings.items():
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=50, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky="nsew")
        item_scroll = ttk.Scrollbar(items_frame, orient="vertical", command=self.tree.yview)
        item_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=item_scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self._show_selected_item)
        content.add(items_frame, weight=3)

        details_frame = ttk.LabelFrame(content, text="Detalhes do item selecionado", padding=8)
        details_frame.grid_rowconfigure(0, weight=1)
        details_frame.grid_columnconfigure(0, weight=1)
        self.details = tk.Text(
            details_frame,
            height=7,
            wrap="word",
            state="disabled",
            borderwidth=1,
            relief="solid",
            padx=10,
            pady=8,
            font=("Consolas", 9),
        )
        self.details.grid(row=0, column=0, sticky="nsew")
        details_scroll = ttk.Scrollbar(
            details_frame,
            orient="vertical",
            command=self.details.yview,
        )
        details_scroll.grid(row=0, column=1, sticky="ns")
        self.details.configure(yscrollcommand=details_scroll.set)
        content.add(details_frame, weight=2)
        self._set_details("Selecione um XML para visualizar seus itens.")

    @property
    def document(self) -> NFeDocument | None:
        return self._document

    @property
    def mirror(self) -> SupplierReturnMirror | None:
        return self._mirror

    @property
    def comparison(self) -> SupplierReturnComparison | None:
        return self._comparison

    @property
    def preparation(self) -> SupplierReturnPreparation | None:
        return self._preparation

    @property
    def has_manual_changes(self) -> bool:
        return self._dirty or self._preparation_dirty

    def select_xml(self) -> None:
        path = self._file_picker()
        if path:
            self.load_xml(path)

    def load_xml(self, path: str | Path) -> bool:
        if self.has_manual_changes and not self._confirm_discard():
            return False
        self._reset(status="")
        try:
            document = self._xml_reader(path)
        except NFeXmlError as error:
            self.status_var.set(f"XML não carregado: {error}")
            self._set_details("Corrija a seleção e tente novamente.")
            return False
        self.render_document(document, Path(path).name)
        return True

    def render_document(self, document: NFeDocument, file_name: str) -> None:
        self._reset(status="")
        self._document = document
        self._mirror = build_supplier_return_mirror(document)
        self._preparation = build_supplier_return_preparation(document)
        self._items = {item.number: item for item in document.items}
        self.summary_vars["file"].set(file_name)
        self.summary_vars["key"].set(document.access_key)
        self.summary_vars["number"].set(
            f"{document.number} / série {document.series} / modelo {document.model}"
        )
        self.summary_vars["issuer"].set(
            _party_summary(document.issuer.name, document.issuer.document)
        )
        self.summary_vars["recipient"].set(
            _party_summary(document.recipient.name, document.recipient.document)
        )
        self.summary_vars["items"].set(str(len(document.items)))
        self.summary_vars["protocol"].set(
            f"{document.protocol_number} — autorizado (cStat {document.protocol_status})"
        )
        self.summary_vars["preparation"].set("Nenhum item selecionado")
        self.clear_button.state(["!disabled"])
        self.edit_totals_button.state(["!disabled"])
        self.prepare_return_button.state(["!disabled"])
        self._refresh_comparison()

    def clear(self, *, status: str | None = None) -> bool:
        if self.has_manual_changes and not self._confirm_discard():
            return False
        self._reset(status=status)
        return True

    def edit_selected_item(self) -> None:
        selected = self.tree.selection()
        if not selected or self._comparison is None:
            return
        item_number = int(selected[0])
        fields = tuple(
            field
            for field in self._comparison.fields
            if field.item_number == item_number
        )
        values = self._mirror_editor(
            self,
            f"Espelho do item {item_number}",
            fields,
        )
        if values is not None:
            self.apply_item_changes(item_number, values)

    def edit_totals(self) -> None:
        if self._comparison is None:
            return
        fields = tuple(
            field for field in self._comparison.fields if field.item_number is None
        )
        values = self._mirror_editor(self, "Totais do espelho", fields)
        if values is not None:
            self.apply_total_changes(values)

    def apply_item_changes(self, item_number: int, values: dict[str, str]) -> None:
        if self._mirror is None:
            raise RuntimeError("Nenhum XML foi carregado.")
        updated = self._mirror
        for path, value in values.items():
            updated = update_mirror_field(
                updated,
                item_number=item_number,
                path=path,
                value=value,
            )
        self._mirror = updated
        self._refresh_comparison(selected_item=item_number)

    def apply_total_changes(self, values: dict[str, str]) -> None:
        if self._mirror is None:
            raise RuntimeError("Nenhum XML foi carregado.")
        updated = self._mirror
        for path, value in values.items():
            updated = update_mirror_field(updated, path=path, value=value)
        self._mirror = updated
        self._refresh_comparison()

    def reset_mirror(self) -> None:
        if self._document is None:
            return
        self._mirror = build_supplier_return_mirror(self._document)
        self._refresh_comparison()

    def prepare_return(self) -> None:
        if self._document is None or self._preparation is None:
            return
        result = self._preparation_editor(
            self,
            self._document,
            self._preparation,
        )
        if result is None:
            return
        self._preparation = result
        baseline = build_supplier_return_preparation(self._document)
        self._preparation_dirty = result != baseline
        selected = result.selected_items
        if selected:
            total = f"{result.calculated_merchandise:.2f}".replace(".", ",")
            self.summary_vars["preparation"].set(
                f"{len(selected)} item(ns), mercadoria R$ {total}"
            )
            self.status_var.set(
                "Preparação manual guardada somente nesta sessão. "
                "Os resultados ainda exigem conferência fiscal."
            )
        else:
            self.summary_vars["preparation"].set("Nenhum item selecionado")

    def _reset(self, *, status: str | None = None) -> None:
        self._document = None
        self._mirror = None
        self._comparison = None
        self._preparation = None
        self._dirty = False
        self._preparation_dirty = False
        self._items.clear()
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
        for variable in self.summary_vars.values():
            variable.set("—")
        self.summary_vars["items"].set("0")
        self.clear_button.state(["disabled"])
        self.edit_item_button.state(["disabled"])
        self.edit_totals_button.state(["disabled"])
        self.reset_mirror_button.state(["disabled"])
        self.prepare_return_button.state(["disabled"])
        self._set_details("Selecione um XML para visualizar seus itens.")
        if status is None:
            self.status_var.set(
                "Nenhum XML selecionado. Somente NF-e modelo 55 é aceita nesta etapa."
            )
        else:
            self.status_var.set(status)

    def _refresh_comparison(self, *, selected_item: int | None = None) -> None:
        if self._document is None or self._mirror is None:
            return
        self._comparison = compare_supplier_return_mirror(self._document, self._mirror)
        self._dirty = not self._comparison.matches
        differences_by_item: dict[int, int] = {}
        total_differences = 0
        for field in self._comparison.fields:
            if field.status is ComparisonStatus.MATCH:
                continue
            if field.item_number is None:
                total_differences += 1
            else:
                differences_by_item[field.item_number] = (
                    differences_by_item.get(field.item_number, 0) + 1
                )

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
        for item in self._document.items:
            difference_count = differences_by_item.get(item.number, 0)
            situation = (
                "Igual ao XML"
                if difference_count == 0
                else f"{difference_count} divergência(s)"
            )
            self.tree.insert(
                "",
                "end",
                iid=str(item.number),
                values=item_row(item) + (situation,),
            )

        total = self._comparison.different_count
        if total:
            self.summary_vars["mirror"].set(
                f"{total} divergência(s), sendo {total_differences} no total da nota"
            )
            self.status_var.set(
                f"Espelho alterado: {total} divergência(s). "
                "Os valores informados ainda exigem conferência fiscal."
            )
            self.reset_mirror_button.state(["!disabled"])
        else:
            self.summary_vars["mirror"].set("Pré-preenchido, sem alterações")
            self.status_var.set(
                f"XML carregado com {len(self._document.items)} item(ns). "
                "Espelho pré-preenchido; nenhuma informação foi gravada."
            )
            self.reset_mirror_button.state(["disabled"])

        children = self.tree.get_children()
        target = str(selected_item) if selected_item in self._items else None
        if target is None and children:
            target = children[0]
        if target is not None:
            self.tree.selection_set(target)
            self.tree.focus(target)
            self._render_item_details(self._items[int(target)])
            self.edit_item_button.state(["!disabled"])
        else:
            self.edit_item_button.state(["disabled"])

    def apply_palette(self, palette: ThemePalette) -> None:
        self.details.configure(
            background=palette.text_background,
            foreground=palette.foreground,
            insertbackground=palette.foreground,
            selectbackground=palette.accent,
            highlightbackground=palette.border,
            highlightcolor=palette.accent,
        )

    def _select_file(self) -> str:
        return filedialog.askopenfilename(
            parent=self,
            title="Selecionar XML da nota de entrada",
            filetypes=(("XML da NF-e", "*.xml"), ("Todos os arquivos", "*.*")),
        )

    def _show_selected_item(self, _event: object = None) -> None:
        selected = self.tree.selection()
        if not selected:
            self._set_details("Selecione um item para visualizar seus campos.")
            self.edit_item_button.state(["disabled"])
            return
        item = self._items.get(int(selected[0]))
        if item is not None:
            self._render_item_details(item)
            self.edit_item_button.state(["!disabled"])

    def _render_item_details(self, item: NFeItem) -> None:
        comparisons = ()
        if self._comparison is not None:
            comparisons = tuple(
                field
                for field in self._comparison.fields
                if field.item_number == item.number
            )
        self._set_details(format_item_details(item, comparisons))

    def _set_details(self, text: str) -> None:
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def _ask_discard(self) -> bool:
        return show_message(
            self,
            "Descartar preparação manual?",
            (
                "O espelho ou a preparação possui valores informados manualmente. "
                "Confirme para descartá-los."
            ),
            confirm=True,
        )


def item_row(item: NFeItem) -> tuple[object, ...]:
    return (
        item.number,
        item.product_code,
        item.description,
        item.ncm,
        item.cfop,
        item.unit,
        _decimal_text(item.quantity),
        _decimal_text(item.product_value),
    )


def format_item_details(
    item: NFeItem,
    comparisons: tuple[FieldComparison, ...] = (),
) -> str:
    lines = [
        f"Item: {item.number}",
        f"Código no XML: {item.product_code}",
        f"Código de barras: {item.barcode or 'não informado'}",
        f"Descrição: {item.description}",
        f"NCM: {item.ncm}",
        f"CEST: {item.cest or 'não informado'}",
        f"CFOP: {item.cfop}",
        f"Unidade: {item.unit}",
        f"Quantidade: {_decimal_text(item.quantity)}",
        f"Valor unitário: {_decimal_text(item.unit_value)}",
        f"Valor dos produtos: {_decimal_text(item.product_value)}",
        f"Desconto: {_optional_decimal_text(item.discount)}",
        f"Frete: {_optional_decimal_text(item.freight)}",
        f"Seguro: {_optional_decimal_text(item.insurance)}",
        f"Outras despesas: {_optional_decimal_text(item.other_expenses)}",
        "",
        "Tributos informados no XML:",
    ]
    if item.tax_fields:
        lines.extend(f"{field.path}: {field.value}" for field in item.tax_fields)
    else:
        lines.append("Nenhum campo tributário encontrado.")
    differences = tuple(
        field for field in comparisons if field.status is not ComparisonStatus.MATCH
    )
    if differences:
        lines.extend(("", "Diferenças informadas no espelho:"))
        lines.extend(
            (
                f"{field.label} ({field.path}): "
                f"XML={field.original_value or 'não informado'} | "
                f"Espelho={field.mirror_value or 'não informado'}"
            )
            for field in differences
        )
    return "\n".join(lines)


def _party_summary(name: str, document: str) -> str:
    return f"{name} — {document}"


def _decimal_text(value: Decimal) -> str:
    return format(value, "f").replace(".", ",")


def _optional_decimal_text(value: Decimal | None) -> str:
    return "não informado" if value is None else _decimal_text(value)
