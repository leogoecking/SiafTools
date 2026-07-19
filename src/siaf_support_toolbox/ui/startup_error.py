from __future__ import annotations

import logging
import tkinter as tk
from contextlib import suppress
from pathlib import Path
from tkinter import messagebox

LOGGER = logging.getLogger(__name__)


def show_database_startup_error(database_path: Path) -> None:
    """Exibe uma falha de bootstrap sem alterar ou remover o banco existente."""

    root: tk.Tk | None = None
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "SIAF Support Toolbox — banco interno indisponível",
            (
                "O banco interno não pôde ser aberto. Nenhum dado foi apagado.\n\n"
                f"Arquivo: {database_path}\n\n"
                "Feche o programa e preserve esse arquivo para diagnóstico. "
                "Consulte o log de erros ou acione o suporte."
            ),
            parent=root,
        )
    except tk.TclError:
        LOGGER.exception("Não foi possível exibir o aviso de falha do banco interno")
    finally:
        if root is not None:
            with suppress(tk.TclError):
                root.destroy()
