from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from siaf_support_toolbox.core.paths import AppPaths

_SENSITIVE_PATTERN = re.compile(
    r"""(?ix)
    (?P<prefix>["']?(?:password|passwd|senha|pwd|token|secret|csc)["']?\s*[:=]\s*)
    (?:
        (?P<quote>["'])(?P<quoted_value>.*?)(?P=quote)
        |
        (?P<plain_value>[^\s,;}\]]+)
    )
    """
)

_LOG_MAX_BYTES = 1_000_000
_LOG_BACKUP_COUNT = 3


def redact_text(value: str) -> str:
    return _SENSITIVE_PATTERN.sub(lambda match: f"{match.group('prefix')}[REDACTED]", value)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


def _handler(path: Path, level: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    handler.addFilter(RedactingFilter())
    return handler


def configure_logging(paths: AppPaths | None = None) -> Path:
    resolved = (paths or AppPaths.for_user()).ensure()
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    configured_roles = {getattr(handler, "_siaf_role", None) for handler in root.handlers}
    if "app" not in configured_roles:
        app_handler = _handler(resolved.logs / "app.log", logging.INFO)
        app_handler._siaf_role = "app"  # type: ignore[attr-defined]
        root.addHandler(app_handler)

    if "errors" not in configured_roles:
        error_handler = _handler(resolved.logs / "errors.log", logging.ERROR)
        error_handler._siaf_role = "errors"  # type: ignore[attr-defined]
        root.addHandler(error_handler)
    return resolved.logs
