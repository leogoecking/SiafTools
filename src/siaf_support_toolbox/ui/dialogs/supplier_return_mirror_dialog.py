from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from siaf_support_toolbox.services.supplier_return_diagnostic_service import (
    FieldComparison,
    normalize_mirror_value,
)
from siaf_support_toolbox.ui.screen_geometry import format_geometry


class SupplierReturnMirrorDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        fields: tuple[FieldComparison, ...],
    ) -> None:
        super().__init__(parent)
        self.result: dict[str, str] | None = None
        self._fields = fields
        self._entries: dict[str, ttk.Entry] = {}
        self.title(title)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.minsize(700, 480)

        container = ttk.Frame(self, padding=18, style="Surface.TFrame")
        container.pack(fill="both", expand=True)
        ttk.Label(container, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            container,
            text=(
                "Os valores do XML permanecem à esquerda. Altere somente a coluna "
                "Espelho conforme a informação enviada pelo fornecedor."
            ),
            style="Subtitle.TLabel",
            wraplength=720,
        ).pack(anchor="w", pady=(4, 12))

        header = ttk.Frame(container, style="Surface.TFrame")
        header.pack(fill="x", padx=(2, 18))
        header.grid_columnconfigure(0, weight=3)
        header.grid_columnconfigure(1, weight=2)
        header.grid_columnconfigure(2, weight=2)
        ttk.Label(header, text="Campo", style="TopInfo.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, text="XML original", style="TopInfo.TLabel").grid(
            row=0, column=1, sticky="w", padx=8
        )
        ttk.Label(header, text="Espelho", style="TopInfo.TLabel").grid(
            row=0, column=2, sticky="w", padx=8
        )

        scroll_host = ttk.Frame(container, style="Surface.TFrame")
        scroll_host.pack(fill="both", expand=True, pady=(4, 8))
        scroll_host.grid_rowconfigure(0, weight=1)
        scroll_host.grid_columnconfigure(0, weight=1)
        surface = ttk.Style(self).lookup("Surface.TFrame", "background") or "#ffffff"
        self.canvas = tk.Canvas(
            scroll_host,
            borderwidth=0,
            highlightthickness=1,
            background=surface,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            scroll_host,
            orient="vertical",
            command=self.canvas.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        rows = ttk.Frame(self.canvas, padding=(4, 2), style="Surface.TFrame")
        self._window_id = self.canvas.create_window((0, 0), window=rows, anchor="nw")
        rows.grid_columnconfigure(0, weight=3)
        rows.grid_columnconfigure(1, weight=2)
        rows.grid_columnconfigure(2, weight=2)
        for row, field in enumerate(fields):
            label_frame = ttk.Frame(rows, style="Surface.TFrame")
            label_frame.grid(row=row, column=0, sticky="ew", padx=(0, 8), pady=3)
            ttk.Label(
                label_frame,
                text=field.label,
                style="Surface.TLabel",
                wraplength=250,
            ).pack(anchor="w")
            ttk.Label(
                label_frame,
                text=field.path,
                style="TopInfo.TLabel",
                wraplength=250,
            ).pack(anchor="w")
            ttk.Label(
                rows,
                text=field.original_value or "Não informado no XML",
                style="Surface.TLabel",
                wraplength=180,
            ).grid(row=row, column=1, sticky="ew", padx=8, pady=3)
            entry = ttk.Entry(rows)
            entry.insert(0, field.mirror_value or "")
            entry.grid(row=row, column=2, sticky="ew", padx=(8, 0), pady=3)
            self._entries[field.path] = entry

        rows.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_rows)
        self.bind("<MouseWheel>", self._on_mousewheel)

        self.error_var = tk.StringVar(value="")
        ttk.Label(
            container,
            textvariable=self.error_var,
            style="Subtitle.TLabel",
            wraplength=720,
        ).pack(fill="x", pady=(0, 6))
        actions = ttk.Frame(container, style="Surface.TFrame")
        actions.pack(fill="x")
        ttk.Button(actions, text="Cancelar", command=self._cancel).pack(side="right")
        ttk.Button(actions, text="Aplicar alterações", command=self._submit).pack(
            side="right", padx=(0, 8)
        )

        self.update_idletasks()
        self._center(parent)
        self.grab_set()
        if self._entries:
            next(iter(self._entries.values())).focus_set()

    def _submit(self) -> None:
        values: dict[str, str] = {}
        for field in self._fields:
            entry = self._entries[field.path]
            try:
                values[field.path] = normalize_mirror_value(field.path, entry.get())
            except ValueError as error:
                self.error_var.set(str(error))
                entry.focus_set()
                return
        self.result = values
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _update_scroll_region(self, _event: object = None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_rows(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.winfo_exists():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _center(self, parent: tk.Misc) -> None:
        width = min(820, max(700, parent.winfo_width() - 80))
        height = min(680, max(480, parent.winfo_height() - 80))
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
        self.geometry(format_geometry(width, height, x, y))


def edit_supplier_return_mirror(
    parent: tk.Misc,
    title: str,
    fields: tuple[FieldComparison, ...],
) -> dict[str, str] | None:
    dialog = SupplierReturnMirrorDialog(parent, title, fields)
    parent.wait_window(dialog)
    return dialog.result
