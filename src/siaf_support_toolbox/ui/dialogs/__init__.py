"""Diálogos reutilizáveis da interface."""

from siaf_support_toolbox.ui.dialogs.connection_dialog import (
    ask_credentials,
    ask_manual_connection,
)
from siaf_support_toolbox.ui.dialogs.message_dialog import show_message
from siaf_support_toolbox.ui.dialogs.supplier_return_mirror_dialog import (
    edit_supplier_return_mirror,
)
from siaf_support_toolbox.ui.dialogs.supplier_return_preparation_dialog import (
    edit_supplier_return_preparation,
)

__all__ = [
    "ask_credentials",
    "ask_manual_connection",
    "edit_supplier_return_mirror",
    "edit_supplier_return_preparation",
    "show_message",
]
