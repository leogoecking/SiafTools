from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollableSidebar(ttk.Frame):
    def __init__(self, parent: tk.Misc, width: int = 220) -> None:
        super().__init__(parent, width=width, style="Sidebar.TFrame")
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self,
            width=width,
            background="#172033",
            borderwidth=0,
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.content = ttk.Frame(self.canvas, padding=(10, 14), style="Sidebar.TFrame")
        self._content_window = self.canvas.create_window(
            (0, 0),
            anchor="nw",
            window=self.content,
        )
        self.content.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_content)
        self.bind_mousewheel(self.canvas)
        self.bind_mousewheel(self.content)

    def bind_mousewheel(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")

    def set_background(self, color: str) -> None:
        self.canvas.configure(background=color)

    def scroll_to(self, widget: tk.Misc) -> None:
        self.update_idletasks()
        content_height = self.content.winfo_reqheight()
        viewport_height = self.canvas.winfo_height()
        if content_height <= viewport_height or viewport_height <= 1:
            return

        widget_top = widget.winfo_y()
        widget_bottom = widget_top + widget.winfo_height()
        visible_top = self.canvas.canvasy(0)
        visible_bottom = visible_top + viewport_height
        if widget_top < visible_top:
            self.canvas.yview_moveto(widget_top / content_height)
        elif widget_bottom > visible_bottom:
            target_top = max(0, widget_bottom - viewport_height)
            self.canvas.yview_moveto(target_top / content_height)

    def _update_scroll_region(self, _event: tk.Event[tk.Misc]) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_content(self, event: tk.Event[tk.Misc]) -> None:
        self.canvas.itemconfigure(self._content_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event[tk.Misc]) -> str:
        direction = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(direction, "units")
        return "break"
