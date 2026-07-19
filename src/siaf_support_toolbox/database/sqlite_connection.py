from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class SQLiteDatabase:
    """Fábrica de conexões curtas para o banco interno da aplicação."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        from siaf_support_toolbox.database.migrations import apply_migrations

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            apply_migrations(connection)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
