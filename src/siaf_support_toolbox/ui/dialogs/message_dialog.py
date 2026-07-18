from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class MessageDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        message: str,
        *,
        confirm: bool = False,
    ) -> None:
        super().__init__(parent)
        self.result = False
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        container = ttk.Frame(self, padding=20, style="Surface.TFrame")
        container.pack(fill="both", expand=True)
        ttk.Label(
            container,
            text=title,
            style="Title.TLabel",
            wraplength=420,
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=message,
            style="Surface.TLabel",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(12, 20))

        actions = ttk.Frame(container, style="Surface.TFrame")
        actions.pack(fill="x")
        if confirm:
            ttk.Button(actions, text="Cancelar", command=self._cancel).pack(side="right")
            ttk.Button(actions, text="Confirmar", command=self._confirm).pack(
                side="right", padx=(0, 8)
            )
        else:
            ttk.Button(actions, text="Fechar", command=self._confirm).pack(side="right")

        self.update_idletasks()
        self._center(parent)
        self.grab_set()
        self.focus_set()

    def _center(self, parent: tk.Misc) -> None:
        width = max(460, self.winfo_reqwidth())
        height = self.winfo_reqheight()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _confirm(self) -> None:
        self.result = True
        self.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.destroy()


def show_message(
    parent: tk.Misc,
    title: str,
    message: str,
    *,
    confirm: bool = False,
) -> bool:
    dialog = MessageDialog(parent, title, message, confirm=confirm)
    parent.wait_window(dialog)
    return dialog.result
