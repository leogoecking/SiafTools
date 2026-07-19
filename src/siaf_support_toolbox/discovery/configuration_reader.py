from __future__ import annotations

import codecs
from pathlib import Path


def read_configuration_text(path: Path) -> str:
    """Lê configurações antigas do Windows sem substituir caracteres silenciosamente."""
    content = path.read_bytes()
    if content.startswith(codecs.BOM_UTF8):
        return content.decode("utf-8-sig")
    if content.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return content.decode("utf-16")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return content.decode("cp1252")
        except UnicodeDecodeError:
            return content.decode("latin-1")
