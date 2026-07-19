from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from siaf_support_toolbox.core.constants import DEFAULT_FIREBIRD_PORT
from siaf_support_toolbox.services.connection_service import (
    ManualConnectionInput,
    SessionCredentials,
)


class CredentialsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.result: SessionCredentials | None = None
        self.title("Validar conexão Firebird")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        frame = ttk.Frame(self, padding=20, style="Surface.TFrame")
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="Credencial somente para esta sessão",
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(frame, text="Usuário", style="Surface.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(frame, text="Senha", style="Surface.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(frame, text="Charset", style="Surface.TLabel").grid(row=3, column=0, sticky="w")
        self.username = ttk.Entry(frame, width=34)
        self.password = ttk.Entry(frame, width=34, show="•")
        self.charset = ttk.Combobox(
            frame,
            values=("WIN1252", "UTF8", "ISO8859_1", "NONE"),
            state="readonly",
            width=31,
        )
        self.charset.set("WIN1252")
        self.username.grid(row=1, column=1, padx=(12, 0), pady=4)
        self.password.grid(row=2, column=1, padx=(12, 0), pady=4)
        self.charset.grid(row=3, column=1, padx=(12, 0), pady=4)
        ttk.Label(
            frame,
            text="A senha não será salva nem incluída em logs.",
            style="Subtitle.TLabel",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 12))
        actions = ttk.Frame(frame, style="Surface.TFrame")
        actions.grid(row=5, column=0, columnspan=2, sticky="e")
        ttk.Button(actions, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(actions, text="Validar", command=self._submit).pack(side="right", padx=(0, 8))
        self.username.focus_set()
        self.grab_set()

    def _submit(self) -> None:
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            return
        self.result = SessionCredentials(username, password, self.charset.get())
        self.password.delete(0, "end")
        self.destroy()


class ManualConnectionDialog(CredentialsDialog):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.manual_result: ManualConnectionInput | None = None
        self.result = None
        self.title("Opções avançadas de conexão")
        frame = self.winfo_children()[0]
        assert isinstance(frame, ttk.Frame)
        for child in frame.winfo_children():
            child.destroy()

        fields = (
            ("Host", "host"),
            ("Porta", "port"),
            ("Base ou alias", "database_path"),
            ("Cliente Firebird x86", "client_library"),
            ("Usuário", "username"),
            ("Senha", "password"),
            ("Charset", "charset"),
        )
        ttk.Label(frame, text="Fallback manual avançado", style="Title.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )
        self.entries: dict[str, ttk.Entry] = {}
        for row, (label, name) in enumerate(fields, start=1):
            ttk.Label(frame, text=label, style="Surface.TLabel").grid(row=row, column=0, sticky="w")
            entry = ttk.Entry(frame, width=42, show="•" if name == "password" else "")
            entry.grid(row=row, column=1, padx=(12, 4), pady=3)
            self.entries[name] = entry
        self.entries["host"].insert(0, "localhost")
        self.entries["port"].insert(0, str(DEFAULT_FIREBIRD_PORT))
        self.entries["charset"].insert(0, "WIN1252")
        ttk.Button(frame, text="Selecionar base", command=self._select_database).grid(
            row=3, column=2, padx=(4, 0)
        )
        ttk.Button(frame, text="Selecionar DLL", command=self._select_library).grid(
            row=4, column=2, padx=(4, 0)
        )
        self.save_profile = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text="Salvar perfil técnico após conexão bem-sucedida (sem senha)",
            variable=self.save_profile,
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(8, 12))
        actions = ttk.Frame(frame, style="Surface.TFrame")
        actions.grid(row=9, column=0, columnspan=3, sticky="e")
        ttk.Button(actions, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(actions, text="Validar", command=self._submit_manual).pack(
            side="right", padx=(0, 8)
        )

    def _select_database(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="Selecionar base Firebird",
            filetypes=(("Base Firebird", "*.fdb"), ("Todos os arquivos", "*.*")),
        )
        if selected:
            self.entries["database_path"].delete(0, "end")
            self.entries["database_path"].insert(0, selected)

    def _select_library(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="Selecionar cliente Firebird x86",
            filetypes=(("Biblioteca Firebird", "*.dll"), ("Todos os arquivos", "*.*")),
        )
        if selected:
            self.entries["client_library"].delete(0, "end")
            self.entries["client_library"].insert(0, selected)

    def _submit_manual(self) -> None:
        values = {name: entry.get().strip() for name, entry in self.entries.items()}
        try:
            port = int(values["port"])
        except ValueError:
            return
        if not all(
            values[name]
            for name in ("host", "database_path", "client_library", "username", "password")
        ):
            return
        self.manual_result = ManualConnectionInput(
            database_path=values["database_path"],
            client_library=values["client_library"],
            host=values["host"],
            port=port,
            save_profile=self.save_profile.get(),
        )
        self.result = SessionCredentials(values["username"], values["password"], values["charset"])
        self.entries["password"].delete(0, "end")
        self.destroy()


def ask_credentials(parent: tk.Misc) -> SessionCredentials | None:
    dialog = CredentialsDialog(parent)
    parent.wait_window(dialog)
    return dialog.result


def ask_manual_connection(
    parent: tk.Misc,
) -> tuple[ManualConnectionInput, SessionCredentials] | None:
    dialog = ManualConnectionDialog(parent)
    parent.wait_window(dialog)
    if dialog.manual_result is None or dialog.result is None:
        return None
    return dialog.manual_result, dialog.result
