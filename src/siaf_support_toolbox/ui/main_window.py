from __future__ import annotations

import logging
import platform
import queue
import threading
import time
import tkinter as tk
from contextlib import suppress
from tkinter import ttk
from typing import Protocol

from siaf_support_toolbox.core.paths import AppPaths
from siaf_support_toolbox.core.version import __version__
from siaf_support_toolbox.discovery.discovery_orchestrator import DiscoveryOrchestrator
from siaf_support_toolbox.discovery.models import DiscoveryReport, MachineMode
from siaf_support_toolbox.ui.dialogs import show_message
from siaf_support_toolbox.ui.navigation import NAVIGATION_ITEMS, VALID_PAGE_IDS, navigation_item
from siaf_support_toolbox.ui.pages import EnvironmentPage, PlaceholderPage
from siaf_support_toolbox.ui.preferences import (
    MINIMUM_HEIGHT,
    MINIMUM_WIDTH,
    WindowPreferences,
    WindowPreferencesStore,
)
from siaf_support_toolbox.ui.screen_geometry import detect_screen_bounds, format_geometry
from siaf_support_toolbox.ui.theme import ThemeManager
from siaf_support_toolbox.ui.widgets import ScrollableSidebar

LOGGER = logging.getLogger(__name__)

_MODE_LABELS = {
    MachineMode.LOCAL_SERVER: "Servidor local",
    MachineMode.TERMINAL: "Terminal",
    MachineMode.ASSISTED: "Assistido",
}


class DiscoveryProvider(Protocol):
    def discover(self) -> DiscoveryReport: ...


class MainWindow(tk.Tk):
    def __init__(
        self,
        orchestrator: DiscoveryProvider | None = None,
        *,
        paths: AppPaths | None = None,
        preferences_store: WindowPreferencesStore | None = None,
        auto_discover: bool = True,
    ) -> None:
        super().__init__()
        self.title(f"SIAF Support Toolbox {__version__}")
        self._paths = (paths or AppPaths.for_user()).ensure()
        self._preferences_store = preferences_store or WindowPreferencesStore(
            self._paths.data / "window-state.json"
        )
        self._screen_bounds = detect_screen_bounds(self)
        self._preferences = self._preferences_store.load().normalized(
            self._screen_bounds.width,
            self._screen_bounds.height,
            self._screen_bounds.x,
            self._screen_bounds.y,
        )
        self._restore_window()

        self._orchestrator = orchestrator or DiscoveryOrchestrator()
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._discovery_thread: threading.Thread | None = None
        self._discovery_started_at: float | None = None
        self._closing = False
        self._poll_after_id: str | None = None
        self._current_page = self._preferences.selected_page

        self._theme = ThemeManager(self)
        self._pages: dict[str, ttk.Frame] = {}
        self._navigation_buttons: dict[str, ttk.Button] = {}
        self._build_ui()
        self._apply_theme(self._preferences.theme)
        self.navigate(self._preferences.selected_page)

        self.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_after_id = self.after(100, self._poll_events)
        if self._preferences.maximized:
            self.after_idle(self._maximize)
        if auto_discover:
            self.after(150, self.start_discovery)

    @property
    def current_page(self) -> str:
        return self._current_page

    @property
    def current_theme(self) -> str:
        return self._theme.current

    def _restore_window(self) -> None:
        bounds = self._screen_bounds
        self.minsize(min(MINIMUM_WIDTH, bounds.width), min(MINIMUM_HEIGHT, bounds.height))
        preferences = self._preferences
        self.geometry(
            format_geometry(
                preferences.width,
                preferences.height,
                preferences.x if preferences.x is not None else bounds.x,
                preferences.y if preferences.y is not None else bounds.y,
            )
        )

    def _maximize(self) -> None:
        try:
            self.state("zoomed")
        except tk.TclError:
            LOGGER.debug("Estado maximizado não suportado pelo gerenciador de janelas")

    def _build_ui(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_top_bar()

        body = ttk.Frame(self, style="App.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self._build_sidebar(body)
        self._page_container = ttk.Frame(body, style="Surface.TFrame")
        self._page_container.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
        self._page_container.grid_rowconfigure(0, weight=1)
        self._page_container.grid_columnconfigure(0, weight=1)
        self._build_pages()

        self._build_bottom_bar()

    def _build_top_bar(self) -> None:
        top = ttk.Frame(self, padding=(18, 12), style="Surface.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        title_row = ttk.Frame(top, style="Surface.TFrame")
        title_row.grid(row=0, column=0, sticky="ew")
        title_row.grid_columnconfigure(0, weight=1)
        ttk.Label(title_row, text="SIAF Support Toolbox", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            title_row,
            text=f"Computador: {platform.node() or 'desconhecido'}",
            style="TopInfo.TLabel",
        ).grid(row=0, column=1, padx=(12, 8))
        ttk.Button(title_row, text="Alternar tema", command=self.toggle_theme).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(title_row, text="Sobre", command=self._show_about).grid(row=0, column=3, padx=4)

        info_row = ttk.Frame(top, style="Surface.TFrame")
        info_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.mode_label = ttk.Label(info_row, text="Modo: analisando", style="TopInfo.TLabel")
        self.firebird_label = ttk.Label(
            info_row, text="Firebird: analisando", style="TopInfo.TLabel"
        )
        self.base_label = ttk.Label(info_row, text="Bases: analisando", style="TopInfo.TLabel")
        self.connection_label = ttk.Label(
            info_row, text="Conexão: não validada", style="TopInfo.TLabel"
        )
        self.read_only_label = ttk.Label(
            info_row, text="Modo atual: somente leitura", style="TopInfo.TLabel"
        )
        self.architecture_label = ttk.Label(
            info_row, text="Arquitetura: analisando", style="TopInfo.TLabel"
        )
        self.version_label = ttk.Label(
            info_row, text=f"Versão: {__version__}", style="TopInfo.TLabel"
        )
        positions = (
            (self.mode_label, 0, 0),
            (self.firebird_label, 0, 1),
            (self.base_label, 0, 2),
            (self.connection_label, 0, 3),
            (self.read_only_label, 1, 0),
            (self.architecture_label, 1, 1),
            (self.version_label, 1, 2),
        )
        for label, row, column in positions:
            label.grid(row=row, column=column, sticky="w", padx=(0, 20), pady=1)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        self.sidebar = ScrollableSidebar(parent, width=220)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        content = self.sidebar.content
        content.grid_columnconfigure(0, weight=1)
        ttk.Label(content, text="Navegação", style="SidebarTitle.TLabel").grid(
            row=0, column=0, sticky="w", padx=8, pady=(0, 12)
        )
        for row, item in enumerate(NAVIGATION_ITEMS, start=1):
            button = ttk.Button(
                content,
                text=item.label,
                style="Sidebar.TButton",
                command=lambda page_id=item.page_id: self.navigate(page_id),
            )
            button.grid(row=row, column=0, sticky="ew", pady=1)
            self.sidebar.bind_mousewheel(button)
            self._navigation_buttons[item.page_id] = button

    def _build_pages(self) -> None:
        for item in NAVIGATION_ITEMS:
            if item.page_id == "environment":
                page: ttk.Frame = EnvironmentPage(self._page_container, self.start_discovery)
                self.environment_page = page
            else:
                page = PlaceholderPage(self._page_container, item.title, item.description)
            page.grid(row=0, column=0, sticky="nsew")
            self._pages[item.page_id] = page

    def _build_bottom_bar(self) -> None:
        footer = ttk.Frame(self, padding=(14, 8), style="Surface.TFrame")
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_columnconfigure(1, weight=1)
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=130)
        self.progress.grid(row=0, column=0, padx=(0, 10), rowspan=2)
        self.status_label = ttk.Label(
            footer, text="Aplicação pronta", style="Surface.TLabel", anchor="w"
        )
        self.status_label.grid(row=0, column=1, sticky="ew", columnspan=3)
        self.records_label = ttk.Label(footer, text="Registros: 0", style="TopInfo.TLabel")
        self.records_label.grid(row=1, column=1, sticky="w", pady=(2, 0))
        self.elapsed_label = ttk.Label(footer, text="Tempo: 00:00", style="TopInfo.TLabel")
        self.elapsed_label.grid(row=1, column=2, sticky="w", padx=16, pady=(2, 0))
        self.output_label = ttk.Label(footer, text="Arquivo: —", style="TopInfo.TLabel")
        self.output_label.grid(row=1, column=3, sticky="w", pady=(2, 0))
        self.indicator_label = ttk.Label(footer, text="Sem avisos", style="TopInfo.TLabel")
        self.indicator_label.grid(row=0, column=4, padx=12)
        self.cancel_button = ttk.Button(footer, text="Cancelar", state="disabled")
        self.cancel_button.grid(row=0, column=5, padx=(8, 0), rowspan=2)

    def navigate(self, page_id: str) -> None:
        if page_id not in VALID_PAGE_IDS:
            raise ValueError(f"Página desconhecida: {page_id}")
        self._pages[page_id].tkraise()
        self._current_page = page_id
        self._refresh_navigation_styles()
        selected_button = self._navigation_buttons[page_id]
        self.sidebar.scroll_to(selected_button)
        self.after_idle(self._ensure_current_navigation_visible)
        self.status_label.config(text=f"Página: {navigation_item(page_id).label}")

    def _ensure_current_navigation_visible(self) -> None:
        if not self._closing:
            self.sidebar.scroll_to(self._navigation_buttons[self._current_page])

    def _refresh_navigation_styles(self) -> None:
        for page_id, button in self._navigation_buttons.items():
            style = (
                "SidebarSelected.TButton" if page_id == self._current_page else "Sidebar.TButton"
            )
            button.configure(style=style)

    def toggle_theme(self) -> None:
        next_theme = "dark" if self._theme.current == "light" else "light"
        self._apply_theme(next_theme)

    def _apply_theme(self, theme: str) -> None:
        palette = self._theme.apply(theme)
        self.sidebar.set_background(palette.sidebar)
        self.environment_page.apply_palette(palette)  # type: ignore[attr-defined]
        self._refresh_navigation_styles()

    def _show_about(self) -> None:
        show_message(
            self,
            "Sobre o SIAF Support Toolbox",
            (
                f"Versão {__version__}\n\n"
                "Aplicação desktop de suporte ao ambiente SIAF/Firebird. "
                "O modo padrão é somente leitura."
            ),
        )

    def start_discovery(self) -> None:
        if self._closing or (self._discovery_thread and self._discovery_thread.is_alive()):
            return
        self._set_header_pending()
        self.environment_page.set_busy(True)  # type: ignore[attr-defined]
        self.progress.start(12)
        self.status_label.config(text="Analisando ambiente...")
        self.indicator_label.config(text="Análise em andamento")
        self.environment_page.set_details(  # type: ignore[attr-defined]
            "A descoberta está em andamento. Nenhuma credencial será solicitada.\n"
        )
        self._discovery_started_at = time.monotonic()
        self._discovery_thread = threading.Thread(
            target=self._run_discovery,
            name="discovery-worker",
            daemon=True,
        )
        self._discovery_thread.start()

    def _run_discovery(self) -> None:
        try:
            self._events.put(("report", self._orchestrator.discover()))
        except Exception as exc:
            LOGGER.exception("Descoberta falhou")
            self._events.put(("error", exc))

    def _poll_events(self) -> None:
        if self._closing:
            return
        try:
            while True:
                event, payload = self._events.get_nowait()
                if event == "report":
                    self._render_report(payload)  # type: ignore[arg-type]
                else:
                    self._render_error(payload)  # type: ignore[arg-type]
        except queue.Empty:
            pass

        if self._discovery_started_at is not None:
            elapsed = max(0, int(time.monotonic() - self._discovery_started_at))
            self.elapsed_label.config(text=f"Tempo: {elapsed // 60:02d}:{elapsed % 60:02d}")
        self._poll_after_id = self.after(100, self._poll_events)

    def _render_report(self, report: DiscoveryReport) -> None:
        self._finish_discovery()
        self.environment_page.render_report(report)  # type: ignore[attr-defined]
        mode = _MODE_LABELS.get(report.mode, str(report.mode))
        firebird_count = len(report.services) + len(report.firebird_processes)
        self.mode_label.config(text=f"Modo: {mode}")
        self.firebird_label.config(text=f"Firebird: {firebird_count} evidência(s)")
        self.base_label.config(text=f"Bases: {len(report.databases)} candidata(s)")
        self.architecture_label.config(
            text=f"Arquitetura: {report.process_architecture} / {report.process_bits} bits"
        )
        self.status_label.config(text="Análise concluída")
        self.indicator_label.config(
            text=f"{len(report.issues)} aviso(s)" if report.issues else "Sem avisos"
        )

    def _render_error(self, error: Exception) -> None:
        self._finish_discovery()
        self._set_header_unavailable()
        self.status_label.config(text="A análise encontrou um erro inesperado")
        self.indicator_label.config(text="Erro")
        self.environment_page.set_details(  # type: ignore[attr-defined]
            f"Não foi possível concluir a descoberta: {error}"
        )

    def _finish_discovery(self) -> None:
        self.progress.stop()
        self.environment_page.set_busy(False)  # type: ignore[attr-defined]
        self._discovery_started_at = None

    def _set_header_pending(self) -> None:
        self.mode_label.config(text="Modo: analisando")
        self.firebird_label.config(text="Firebird: analisando")
        self.base_label.config(text="Bases: analisando")
        self.connection_label.config(text="Conexão: não validada")
        self.architecture_label.config(text="Arquitetura: analisando")

    def _set_header_unavailable(self) -> None:
        self.mode_label.config(text="Modo: não confirmado")
        self.firebird_label.config(text="Firebird: não confirmado")
        self.base_label.config(text="Bases: não confirmadas")
        self.connection_label.config(text="Conexão: indisponível")
        self.architecture_label.config(text="Arquitetura: não confirmada")

    def _capture_preferences(self) -> WindowPreferences:
        bounds = detect_screen_bounds(self)
        return WindowPreferences(
            width=self.winfo_width(),
            height=self.winfo_height(),
            x=self.winfo_x(),
            y=self.winfo_y(),
            maximized=str(self.state()) == "zoomed",
            theme=self._theme.current,
            selected_page=self._current_page,
        ).normalized(bounds.width, bounds.height, bounds.x, bounds.y)

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            self._preferences_store.save(self._capture_preferences())
        except OSError:
            LOGGER.exception("Não foi possível salvar o estado da janela")
        if self._poll_after_id is not None:
            with suppress(tk.TclError):
                self.after_cancel(self._poll_after_id)
        self.destroy()
