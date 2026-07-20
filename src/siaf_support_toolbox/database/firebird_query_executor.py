from __future__ import annotations

import socket
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from siaf_support_toolbox.database.firebird_probe import (
    load_api_library,
    runtime_compatibility_issue,
    translate_connection_error,
)
from siaf_support_toolbox.database.sql_validator import validate_read_only_sql
from siaf_support_toolbox.discovery.architecture import pe_architecture, process_architecture

_DEFAULT_BATCH_SIZE = 200


@dataclass(frozen=True, slots=True)
class QueryExecutionResult:
    success: bool
    columns: tuple[str, ...] = ()
    records_processed: int = 0
    duration_ms: int = 0
    canceled: bool = False
    error_code: str | None = None
    message: str | None = None


def execute_query_read_only(
    *,
    dsn: str,
    username: str,
    password: str,
    client_library: str | Path,
    sql: str,
    parameters: tuple[object, ...],
    on_batch: Callable[[tuple[tuple[object, ...], ...]], None],
    cancel_event: Event,
    charset: str = "WIN1252",
    host: str | None = None,
    port: int | None = None,
    connect_timeout: float = 3.0,
    batch_size: int = _DEFAULT_BATCH_SIZE,
) -> QueryExecutionResult:
    """Executa uma consulta validada em conexão temporária e envia resultados em lotes."""
    started = time.monotonic()
    validation = validate_read_only_sql(sql)
    if not validation.valid:
        return _result_error(started, validation.error_code, validation.message)
    if batch_size < 1:
        return _result_error(started, "invalid_batch_size", "O lote deve conter registros")
    if cancel_event.is_set():
        return QueryExecutionResult(False, canceled=True, duration_ms=_elapsed(started))

    library_path = Path(client_library)
    if pe_architecture(library_path) != process_architecture():
        return _result_error(
            started,
            "architecture_mismatch",
            "A DLL Firebird é incompatível com a arquitetura do aplicativo",
        )
    try:
        import fdb
    except ImportError:
        return _result_error(started, "dependency_missing", "fdb não instalado")
    if host and port and not _port_reachable(host, port, connect_timeout):
        return _result_error(
            started,
            "port_unavailable",
            "Não foi possível alcançar automaticamente o serviço Firebird",
        )

    connection = None
    cursor = None
    records = 0
    columns: tuple[str, ...] = ()
    try:
        loaded_library = load_api_library(fdb, library_path)
        if loaded_library is not None:
            return _result_error(
                started,
                "client_library_already_loaded",
                "Outra DLL Firebird já está carregada. Reinicie o aplicativo para trocá-la",
            )
        connection = fdb.connect(dsn=dsn, user=username, password=password, charset=charset)
        read_only_tpb = getattr(fdb, "ISOLATION_LEVEL_READ_COMMITED_RO", None)
        if read_only_tpb is None:
            return _result_error(
                started,
                "readonly_unavailable",
                "O driver não expõe o modo de transação somente leitura esperado",
            )
        connection.begin(tpb=read_only_tpb)
        compatibility = runtime_compatibility_issue(
            _attribute(connection, "version") or _attribute(connection, "engine_version"),
            _attribute(connection, "ods"),
        )
        if compatibility is not None:
            return _result_error(started, compatibility[0], compatibility[1])
        if cancel_event.is_set():
            return QueryExecutionResult(False, canceled=True, duration_ms=_elapsed(started))

        cursor = connection.cursor()
        cursor.execute(validation.compiled_sql, parameters)
        columns = tuple(str(item[0]).strip() for item in (cursor.description or ()))
        while not cancel_event.is_set():
            raw_batch = cursor.fetchmany(batch_size)
            if not raw_batch:
                break
            batch = tuple(tuple(row) for row in raw_batch)
            on_batch(batch)
            records += len(batch)
        connection.rollback()
        if cancel_event.is_set():
            return QueryExecutionResult(
                False,
                columns,
                records,
                _elapsed(started),
                canceled=True,
                error_code="canceled",
                message="Consulta cancelada pelo usuário",
            )
        return QueryExecutionResult(True, columns, records, _elapsed(started))
    except Exception as exc:
        return QueryExecutionResult(
            False,
            columns,
            records,
            _elapsed(started),
            error_code="query_failed",
            message=translate_connection_error(exc),
        )
    finally:
        if cursor is not None:
            with suppress(Exception):
                cursor.close()
        if connection is not None:
            with suppress(Exception):
                connection.rollback()
            with suppress(Exception):
                connection.close()


def _result_error(started: float, code: str | None, message: str | None) -> QueryExecutionResult:
    return QueryExecutionResult(
        False, duration_ms=_elapsed(started), error_code=code, message=message
    )


def _elapsed(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _attribute(value: object, name: str) -> str | None:
    attribute = getattr(value, name, None)
    return str(attribute) if attribute not in (None, "") else None


def _port_reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=max(0.1, timeout)):
            return True
    except OSError:
        return False
