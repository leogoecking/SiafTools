from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from siaf_support_toolbox.discovery.models import DiscoveryReport
from siaf_support_toolbox.services.connection_service import ConnectionSummary, ConnectionTarget

_PATH_KEYS = {
    "binary_path",
    "client_library_path",
    "config_file",
    "database",
    "database_path",
    "executable",
    "path",
    "root",
    "source_file",
    "target_path",
    "working_directory",
}
_EMBEDDED_PATH = re.compile(
    r"(?i)(?P<path>(?:[a-z]:[\\/]|\\\\|%[a-z0-9_()]+%[\\/])"
    r"[^\"'\r\n;|<>\[\]{}]*)"
)


class DiagnosticExportService:
    def __init__(self, exports_path: Path) -> None:
        self.exports_path = exports_path

    def export(
        self,
        report: DiscoveryReport,
        *,
        targets: tuple[ConnectionTarget, ...] = (),
        summary: ConnectionSummary | None = None,
        mask_paths: bool = True,
    ) -> Path:
        self.exports_path.mkdir(parents=True, exist_ok=True)
        payload = {
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "credentials_persisted": False,
            "paths_masked": mask_paths,
            "discovery": report.to_dict(),
            "connection_targets": [_target_payload(item) for item in targets],
            "connection_results": [
                {
                    "target": _target_payload(item.target),
                    "success": item.result.success,
                    "database_type": (
                        str(item.result.classification.database_type)
                        if item.result.classification
                        else None
                    ),
                    "confidence": (
                        item.result.classification.confidence
                        if item.result.classification
                        else None
                    ),
                    "server_version": item.result.server_version,
                    "ods_version": item.result.ods_version,
                    "error_code": item.result.error_code,
                    "message": item.result.message,
                    "duration_ms": item.duration_ms,
                }
                for item in (summary.validations if summary else ())
            ],
        }
        if mask_paths:
            payload = _mask_payload(payload)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        destination = (
            self.exports_path / f"diagnostico_descoberta_{timestamp}_{uuid.uuid4().hex[:8]}.json"
        )
        temporary = destination.with_suffix(".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination


def _target_payload(target: ConnectionTarget) -> dict[str, object]:
    return {
        "host": target.host,
        "port": target.port,
        "database_path": target.database_path,
        "database_type_hint": target.database_type_hint,
        "client_library_path": target.client_library,
        "source": target.source,
        "confidence": target.confidence,
    }


def _mask_payload(value: object, key: str | None = None) -> object:
    if isinstance(value, dict):
        return {name: _mask_payload(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_mask_payload(item, key) for item in value]
    if isinstance(value, str):
        if key in _PATH_KEYS or _looks_like_path(value):
            return _masked_path(value)
        return _mask_embedded_paths(value)
    return value


def _looks_like_path(value: str) -> bool:
    return bool(
        re.match(
            r"(?i)^(?:[a-z]:[\\/]|\\\\|%[a-z0-9_()]+%[\\/])",
            value.strip(),
        )
    )


def _mask_embedded_paths(value: str) -> str:
    return _EMBEDDED_PATH.sub(lambda match: _masked_path(match.group("path").rstrip()), value)


def _masked_path(value: str) -> str:
    name = Path(value).name or "local"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"<mascarado>/{name} [id:{digest}]"
