from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from siaf_support_toolbox.discovery.models import DiscoveryReport
from siaf_support_toolbox.ui.theme import ThemePalette


class EnvironmentPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, on_rescan: Callable[[], None]) -> None:
        super().__init__(parent, padding=24, style="Surface.TFrame")

        heading = ttk.Frame(self, style="Surface.TFrame")
        heading.pack(fill="x")
        title_group = ttk.Frame(heading, style="Surface.TFrame")
        title_group.pack(side="left", fill="x", expand=True)
        ttk.Label(title_group, text="Ambiente detectado", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_group,
            text="Descoberta automática do SIAF, Firebird e bases candidatas.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))
        self.scan_button = ttk.Button(heading, text="Reanalisar computador", command=on_rescan)
        self.scan_button.pack(side="right")

        self.details = tk.Text(
            self,
            wrap="word",
            state="disabled",
            borderwidth=1,
            relief="solid",
            padx=16,
            pady=14,
            font=("Consolas", 10),
        )
        self.details.pack(fill="both", expand=True, pady=(18, 0))
        self.set_details("Aguardando a análise automática do ambiente.\n")

    def set_busy(self, busy: bool) -> None:
        self.scan_button.state(["disabled"] if busy else ["!disabled"])

    def set_details(self, text: str) -> None:
        self.details.config(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.config(state="disabled")

    def render_report(self, report: DiscoveryReport) -> None:
        self.set_details(format_discovery_report(report))

    def apply_palette(self, palette: ThemePalette) -> None:
        self.details.configure(
            background=palette.text_background,
            foreground=palette.foreground,
            insertbackground=palette.foreground,
            selectbackground=palette.accent,
            highlightbackground=palette.border,
            highlightcolor=palette.accent,
        )


def format_discovery_report(report: DiscoveryReport) -> str:
    lines = [
        f"Modo da máquina: {report.mode}",
        f"Confiança inicial: {report.confidence}%",
        f"Privilégio administrativo: {'sim' if report.is_admin else 'não'}",
        "",
        f"SIAF em execução: {len(report.siaf_processes)}",
        f"Atalhos SIAF: {len(report.siaf_shortcuts)}",
        f"Processos Firebird/InterBase: {len(report.firebird_processes)}",
        f"Serviços Firebird/InterBase: {len(report.services)}",
        f"DLLs cliente: {len(report.client_libraries)}",
        f"Conexões TCP do SIAF: {len(report.network_connections)}",
        f"Portas Firebird detectadas: {', '.join(map(str, report.detected_ports))}",
        f"Aliases Firebird: {len(report.aliases)}",
        f"Bases candidatas: {len(report.databases)}",
    ]
    for database in report.databases:
        lines.append(f"  • {database.kind_hint}: {database.path} (pontuação {database.score})")
    if report.client_libraries:
        lines.extend(("", "Bibliotecas encontradas:"))
        for library in report.client_libraries:
            compatibility = "compatível" if library.compatible_with_process else "incompatível"
            lines.append(f"  • {library.path} — {library.architecture}, {compatibility}")
    if report.issues:
        lines.extend(("", f"Avisos parciais ({len(report.issues)}):"))
        lines.extend(f"  • {issue.detector}: {issue.message}" for issue in report.issues[:20])
    return "\n".join(lines)
