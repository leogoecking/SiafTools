from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class PlaceholderPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, title: str, description: str) -> None:
        super().__init__(parent, padding=24, style="Surface.TFrame")
        ttk.Label(self, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text=description,
            style="Subtitle.TLabel",
            wraplength=720,
        ).pack(anchor="w", pady=(6, 22))

        card = ttk.Frame(self, padding=20, style="App.TFrame")
        card.pack(fill="x")
        ttk.Label(
            card,
            text="Estrutura preparada",
            style="App.TLabel",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            card,
            text="Os recursos desta área serão implementados na fase correspondente do roadmap.",
            style="App.TLabel",
            wraplength=680,
        ).pack(anchor="w", pady=(6, 0))
