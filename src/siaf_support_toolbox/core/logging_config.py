from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from siaf_support_toolbox.core.paths import AppPaths

_SENSITIVE_PATTERN = re.compile(
    r"(?i)(password|passwd|senha|pwd|token|secret|csc)\s*([=:])\s*([^\s,;]+)"
)


def redact_text(value: str) -> str:
    return _SENSITIVE_PATTERN.sub(r"\1\2[REDACTED]", value)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


def _handler(path: Path, level: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    handler.addFilter(RedactingFilter())
    return handler


def configure_logging(paths: AppPaths | None = None) -> Path:
    resolved = (paths or AppPaths.for_user()).ensure()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(getattr(item, "_siaf_handler", False) for item in root.handlers):
        app_handler = _handler(resolved.logs / "app.log", logging.INFO)
        app_handler._siaf_handler = True  # type: ignore[attr-defined]
        root.addHandler(app_handler)

        error_handler = _handler(resolved.logs / "errors.log", logging.ERROR)
        error_handler._siaf_handler = True  # type: ignore[attr-defined]
        root.addHandler(error_handler)
    return resolved.logs
