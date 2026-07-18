from __future__ import annotations

import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk

from siaf_support_toolbox.core.version import __version__
from siaf_support_toolbox.discovery.discovery_orchestrator import DiscoveryOrchestrator
from siaf_support_toolbox.discovery.models import DiscoveryReport


class MainWindow(tk.Tk):
    def __init__(self, orchestrator: DiscoveryOrchestrator | None = None) -> None:
        super().__init__()
        self.title(f"SIAF Support Toolbox {__version__}")
        self.geometry("900x580")
        self.minsize(760, 480)
        self._orchestrator = orchestrator or DiscoveryOrchestrator()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="discovery")
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll_events)
        self.after(150, self.start_discovery)

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(18, 14))
        header.pack(fill="x")
        ttk.Label(header, text="SIAF Support Toolbox", font=("Segoe UI", 18, "bold")).pack(
            side="left"
        )
        self.architecture_label = ttk.Label(header, text="Arquitetura: analisando...")
        self.architecture_label.pack(side="right")

        body = ttk.Frame(self, padding=(18, 8))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Ambiente detectado", font=("Segoe UI", 13, "bold")).pack(
            anchor="w", pady=(0, 8)
        )
        self.details = tk.Text(body, height=20, wrap="word", state="disabled")
        self.details.pack(fill="both", expand=True)

        footer = ttk.Frame(self, padding=(18, 12))
        footer.pack(fill="x")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=180)
        self.progress.pack(side="left")
        self.status = ttk.Label(footer, text="Preparando análise...")
        self.status.pack(side="left", padx=12)
        self.scan_button = ttk.Button(footer, text="Reanalisar", command=self.start_discovery)
        self.scan_button.pack(side="right")

    def start_discovery(self) -> None:
        self.scan_button.state(["disabled"])
        self.progress.start(12)
        self.status.config(text="Analisando ambiente...")
        self._set_details("A descoberta está em andamento. Nenhuma credencial será solicitada.\n")
        future = self._executor.submit(self._orchestrator.discover)
        future.add_done_callback(self._discovery_finished)

    def _discovery_finished(self, future) -> None:
        try:
            self._events.put(("report", future.result()))
        except Exception as exc:
            self._events.put(("error", exc))

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self._events.get_nowait()
                if event == "report":
                    self._render_report(payload)  # type: ignore[arg-type]
                else:
                    self._render_error(payload)  # type: ignore[arg-type]
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self._poll_events)

    def _render_report(self, report: DiscoveryReport) -> None:
        self.progress.stop()
        self.scan_button.state(["!disabled"])
        self.architecture_label.config(
            text=f"Arquitetura: {report.process_architecture} / {report.process_bits} bits"
        )
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
        self._set_details("\n".join(lines))
        self.status.config(text="Análise concluída")

    def _render_error(self, error: Exception) -> None:
        self.progress.stop()
        self.scan_button.state(["!disabled"])
        self.status.config(text="A análise encontrou um erro inesperado")
        self._set_details(f"Não foi possível concluir a descoberta: {error}")

    def _set_details(self, text: str) -> None:
        self.details.config(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.config(state="disabled")

    def _close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()
