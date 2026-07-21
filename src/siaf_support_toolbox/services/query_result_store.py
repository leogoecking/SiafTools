from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from threading import Lock

_TYPE_MARKER = "__siaf_query_value_type__"
_MINIMUM_FREE_SPACE_BYTES = 256 * 1024 * 1024


class QueryResultStorageError(RuntimeError):
    """Falha segura ao criar ou ampliar o cache temporário de uma consulta."""

    error_code = "query_cache_unavailable"
    user_message = (
        "Não há espaço livre suficiente para armazenar o resultado temporário. "
        "Libere espaço em disco, refine os filtros e tente novamente."
    )


@dataclass(frozen=True, slots=True)
class QueryResultPage:
    number: int
    page_size: int
    total_records: int
    rows: tuple[tuple[object, ...], ...]

    @property
    def total_pages(self) -> int:
        return max(1, (self.total_records + self.page_size - 1) // self.page_size)


class QueryResultStore:
    """Cache SQLite descartável para paginação sem manter o resultado inteiro na memória."""

    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        _ensure_free_space(directory)
        self.path: Path | None = None
        self._lock = Lock()
        self._closed = False
        self._connection: sqlite3.Connection | None = None
        try:
            descriptor, filename = tempfile.mkstemp(
                prefix="query-", suffix=".sqlite3", dir=directory
            )
            os.close(descriptor)
            self.path = Path(filename)
            self._connection = sqlite3.connect(self.path, check_same_thread=False)
            self._connection.execute(
                "CREATE TABLE result_rows "
                "(sequence INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT)"
            )
            self._connection.commit()
        except (OSError, sqlite3.Error) as exc:
            self.close()
            raise QueryResultStorageError(QueryResultStorageError.user_message) from exc

    def append_batch(self, batch: tuple[tuple[object, ...], ...]) -> None:
        if not batch:
            return
        payloads = [_serialize_row(row) for row in batch]
        required_bytes = sum(len(payload.encode("utf-8")) + 128 for payload in payloads)
        assert self.path is not None
        _ensure_free_space(self.path.parent, required_bytes)
        values = [(payload,) for payload in payloads]
        try:
            with self._lock:
                self._ensure_open()
                assert self._connection is not None
                with self._connection:
                    self._connection.executemany(
                        "INSERT INTO result_rows (payload) VALUES (?)", values
                    )
        except (OSError, sqlite3.Error) as exc:
            raise QueryResultStorageError(QueryResultStorageError.user_message) from exc

    def read_page(self, number: int, page_size: int = 100) -> QueryResultPage:
        if page_size < 1 or page_size > 1000:
            raise ValueError("O tamanho da página deve estar entre 1 e 1000")
        with self._lock:
            self._ensure_open()
            assert self._connection is not None
            total = int(self._connection.execute("SELECT COUNT(*) FROM result_rows").fetchone()[0])
            total_pages = max(1, (total + page_size - 1) // page_size)
            safe_number = min(max(1, number), total_pages)
            rows = self._connection.execute(
                "SELECT payload FROM result_rows ORDER BY sequence LIMIT ? OFFSET ?",
                (page_size, (safe_number - 1) * page_size),
            ).fetchall()
        return QueryResultPage(
            safe_number,
            page_size,
            total,
            tuple(_deserialize_row(row[0]) for row in rows),
        )

    def iter_batches(self, batch_size: int = 500) -> Iterator[tuple[tuple[object, ...], ...]]:
        """Lê o cache em lotes usando uma conexão exclusiva e somente leitura."""
        if batch_size < 1 or batch_size > 5000:
            raise ValueError("O lote deve conter entre 1 e 5000 registros")
        with self._lock:
            self._ensure_open()
            assert self.path is not None
            path = self.path.resolve().as_posix()
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            cursor = connection.execute(
                "SELECT payload FROM result_rows ORDER BY sequence"
            )
            while raw_rows := cursor.fetchmany(batch_size):
                yield tuple(_deserialize_row(row[0]) for row in raw_rows)
        finally:
            connection.close()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._connection is not None:
                self._connection.close()
                self._connection = None
        with suppress(OSError):
            if self.path is not None:
                self.path.unlink(missing_ok=True)

    def _ensure_open(self) -> None:
        if self._closed or self._connection is None:
            raise RuntimeError("O resultado temporário já foi descartado")


def _ensure_free_space(directory: Path, required_bytes: int = 0) -> None:
    try:
        free = shutil.disk_usage(directory).free
    except OSError as exc:
        raise QueryResultStorageError(QueryResultStorageError.user_message) from exc
    if free < _MINIMUM_FREE_SPACE_BYTES + max(0, required_bytes):
        raise QueryResultStorageError(QueryResultStorageError.user_message)


def _serialize_row(row: tuple[object, ...]) -> str:
    return json.dumps([_stored_value(value) for value in row], ensure_ascii=False)


def _stored_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return {_TYPE_MARKER: "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {_TYPE_MARKER: "datetime", "value": value.isoformat(sep=" ")}
    if isinstance(value, date):
        return {_TYPE_MARKER: "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {_TYPE_MARKER: "time", "value": value.isoformat()}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<BLOB {len(value)} bytes>"
    return str(value)


def _deserialize_row(payload: str) -> tuple[object, ...]:
    return tuple(_restored_value(value) for value in json.loads(payload))


def _restored_value(value: object) -> object:
    if not isinstance(value, dict) or value.get(_TYPE_MARKER) is None:
        return value
    raw_value = str(value.get("value", ""))
    value_type = value[_TYPE_MARKER]
    if value_type == "decimal":
        return Decimal(raw_value)
    if value_type == "datetime":
        return datetime.fromisoformat(raw_value)
    if value_type == "date":
        return date.fromisoformat(raw_value)
    if value_type == "time":
        return time.fromisoformat(raw_value)
    return raw_value
