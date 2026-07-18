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
        "(?:\\.|[^"\\])*"
        |
        '(?:\\.|[^'\\])*'
        |
        [^\s,;}\]]+
    )
    """
)

_LOG_MAX_BYTES = 1_000_000
_LOG_BACKUP_COUNT = 3


def redact_text(value: str) -> str:
    return _SENSITIVE_PATTERN.sub(lambda match: f"{match.group('prefix')}[REDACTED]", value)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))


def _handler(path: Path, level: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(RedactingFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    return handler


def _configure_handler(
    root: logging.Logger,
    role: str,
    target: Path,
    level: int,
) -> None:
    expected = target.resolve()
    active_handler: logging.Handler | None = None

    for handler in list(root.handlers):
        if getattr(handler, "_siaf_role", None) != role:
            continue
        current_file = getattr(handler, "baseFilename", None)
        if active_handler is None and current_file and Path(current_file).resolve() == expected:
            active_handler = handler
            continue
        root.removeHandler(handler)
        handler.close()

    if active_handler is None:
        active_handler = _handler(target, level)
        active_handler._siaf_role = role  # type: ignore[attr-defined]
        root.addHandler(active_handler)


def configure_logging(paths: AppPaths | None = None) -> Path:
    resolved = (paths or AppPaths.for_user()).ensure()
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    _configure_handler(root, "app", resolved.logs / "app.log", logging.INFO)
    _configure_handler(root, "errors", resolved.logs / "errors.log", logging.ERROR)
    return resolved.logs
