from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk


@dataclass(frozen=True, slots=True)
class ThemePalette:
    background: str
    surface: str
    sidebar: str
    foreground: str
    muted: str
    accent: str
    accent_hover: str
    border: str
    text_background: str


PALETTES = {
    "light": ThemePalette(
        background="#f4f6f8",
        surface="#ffffff",
        sidebar="#172033",
        foreground="#162033",
        muted="#667085",
        accent="#2563eb",
        accent_hover="#1d4ed8",
        border="#d8dee8",
        text_background="#ffffff",
    ),
    "dark": ThemePalette(
        background="#111827",
        surface="#1f2937",
        sidebar="#0b1220",
        foreground="#f3f4f6",
        muted="#aab4c4",
        accent="#60a5fa",
        accent_hover="#3b82f6",
        border="#374151",
        text_background="#111827",
    ),
}


class ThemeManager:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.style = ttk.Style(root)
        self.current = "light"

    @property
    def palette(self) -> ThemePalette:
        return PALETTES[self.current]

    def apply(self, theme: str) -> ThemePalette:
        self.current = theme if theme in PALETTES else "light"
        palette = self.palette
        self.style.theme_use("clam")
        self.root.configure(background=palette.background)

        self.style.configure("App.TFrame", background=palette.background)
        self.style.configure("Surface.TFrame", background=palette.surface)
        self.style.configure("Sidebar.TFrame", background=palette.sidebar)
        self.style.configure(
            "App.TLabel",
            background=palette.background,
            foreground=palette.foreground,
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "Surface.TLabel",
            background=palette.surface,
            foreground=palette.foreground,
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "Title.TLabel",
            background=palette.surface,
            foreground=palette.foreground,
            font=("Segoe UI", 18, "bold"),
        )
        self.style.configure(
            "Subtitle.TLabel",
            background=palette.surface,
            foreground=palette.muted,
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "TopInfo.TLabel",
            background=palette.surface,
            foreground=palette.muted,
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "SidebarTitle.TLabel",
            background=palette.sidebar,
            foreground="#ffffff",
            font=("Segoe UI", 13, "bold"),
        )
        self.style.configure(
            "Sidebar.TButton",
            anchor="w",
            padding=(14, 9),
            background=palette.sidebar,
            foreground="#dbe4f0",
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        self.style.map(
            "Sidebar.TButton",
            background=[("active", "#24324a")],
            foreground=[("active", "#ffffff")],
        )
        self.style.configure(
            "SidebarSelected.TButton",
            anchor="w",
            padding=(14, 9),
            background=palette.accent,
            foreground="#ffffff",
            borderwidth=0,
            font=("Segoe UI", 9, "bold"),
        )
        self.style.map(
            "SidebarSelected.TButton",
            background=[("active", palette.accent_hover)],
            foreground=[("active", "#ffffff")],
        )
        self.style.configure("TButton", font=("Segoe UI", 9), padding=(10, 6))
        self.style.configure(
            "TProgressbar",
            background=palette.accent,
            troughcolor=palette.border,
            bordercolor=palette.border,
        )
        self.style.configure("TSeparator", background=palette.border)
        return palette
