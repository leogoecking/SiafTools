from __future__ import annotations

import sys
import threading
from types import SimpleNamespace

from siaf_support_toolbox.database import firebird_query_executor


class FakeCursor:
    description = (("CODIGO",), ("NOME",))

    def __init__(self, batches):
        self.batches = list(batches)
        self.fetch_sizes = []
        self.executed = None
        self.closed = False

    def execute(self, sql, parameters):
        self.executed = (sql, parameters)

    def fetchmany(self, size):
        self.fetch_sizes.append(size)
        return self.batches.pop(0) if self.batches else []

    def close(self):
        self.closed = True


class FakeConnection:
    version = "LI-V2.5.7.27050 Firebird 2.5"
    ods = "11.2"

    def __init__(self, cursor):
        self._cursor = cursor
        self.tpb = None
        self.rollback_count = 0
        self.closed = False

    def begin(self, *, tpb):
        self.tpb = tpb

    def cursor(self):
        return self._cursor

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = True


def _install_fake_driver(monkeypatch, connection):
    driver = SimpleNamespace(
        ISOLATION_LEVEL_READ_COMMITED_RO="read-only",
        connect=lambda **_kwargs: connection,
    )
    monkeypatch.setitem(sys.modules, "fdb", driver)
    monkeypatch.setattr(firebird_query_executor, "load_api_library", lambda *_args: None)
    monkeypatch.setattr(firebird_query_executor, "pe_architecture", lambda _path: "x86")
    monkeypatch.setattr(firebird_query_executor, "process_architecture", lambda: "x86")


def test_executor_uses_read_only_transaction_named_parameters_and_fetchmany(monkeypatch):
    cursor = FakeCursor([[(1, "A"), (2, "B")], [(3, "C")], []])
    connection = FakeConnection(cursor)
    _install_fake_driver(monkeypatch, connection)
    received = []
    progress = []

    result = firebird_query_executor.execute_query_read_only(
        dsn="localhost:C:/SIAFLOJA.FDB",
        username="SYSDBA",
        password="temporary",
        client_library="C:/Firebird/fbclient.dll",
        sql="SELECT CODIGO, NOME FROM TESTE WHERE CODIGO >= :minimum",
        parameters=(1,),
        on_batch=received.append,
        cancel_event=threading.Event(),
        on_progress=lambda records, _duration: progress.append(records),
    )

    assert result.success
    assert result.records_processed == 3
    assert cursor.executed == (
        "SELECT CODIGO, NOME FROM TESTE WHERE CODIGO >= ?",
        (1,),
    )
    assert cursor.fetch_sizes == [200, 200, 200]
    assert received == [((1, "A"), (2, "B")), ((3, "C"),)]
    assert progress == [2, 3]
    assert connection.tpb == "read-only"
    assert connection.rollback_count >= 1
    assert connection.closed and cursor.closed


def test_executor_cancels_between_batches(monkeypatch):
    cursor = FakeCursor([[(1, "A")], [(2, "B")]])
    connection = FakeConnection(cursor)
    _install_fake_driver(monkeypatch, connection)
    cancel = threading.Event()

    def receive(_batch):
        cancel.set()

    result = firebird_query_executor.execute_query_read_only(
        dsn="localhost:C:/SIAFLOJA.FDB",
        username="SYSDBA",
        password="temporary",
        client_library="C:/Firebird/fbclient.dll",
        sql="SELECT CODIGO, NOME FROM TESTE",
        parameters=(),
        on_batch=receive,
        cancel_event=cancel,
    )

    assert result.canceled
    assert result.records_processed == 1
    assert cursor.fetch_sizes == [200]


def test_executor_revalidates_and_blocks_destructive_sql_before_loading_driver():
    result = firebird_query_executor.execute_query_read_only(
        dsn="localhost:C:/SIAFLOJA.FDB",
        username="SYSDBA",
        password="temporary",
        client_library="missing.dll",
        sql="UPDATE TESTE SET NOME = 'X'",
        parameters=(),
        on_batch=lambda _batch: None,
        cancel_event=threading.Event(),
    )

    assert result.error_code == "destructive_sql"


def test_executor_preserves_batch_consumer_error(monkeypatch):
    cursor = FakeCursor([[(1, "A")]])
    connection = FakeConnection(cursor)
    _install_fake_driver(monkeypatch, connection)

    class CacheFailure(RuntimeError):
        error_code = "query_cache_unavailable"
        user_message = "Espaço insuficiente para o cache temporário"

    def fail(_batch):
        raise CacheFailure

    result = firebird_query_executor.execute_query_read_only(
        dsn="localhost:C:/SIAFLOJA.FDB",
        username="SYSDBA",
        password="temporary",
        client_library="C:/Firebird/fbclient.dll",
        sql="SELECT CODIGO, NOME FROM TESTE",
        parameters=(),
        on_batch=fail,
        cancel_event=threading.Event(),
    )

    assert not result.success
    assert result.error_code == "query_cache_unavailable"
    assert result.message == "Espaço insuficiente para o cache temporário"


def test_executor_interrupts_blocked_execute_when_cancel_is_requested(monkeypatch):
    execute_started = threading.Event()
    execute_released = threading.Event()
    cancel = threading.Event()

    class BlockingCursor(FakeCursor):
        def execute(self, sql, parameters):
            self.executed = (sql, parameters)
            execute_started.set()
            assert execute_released.wait(2)

    cursor = BlockingCursor([])
    connection = FakeConnection(cursor)
    _install_fake_driver(monkeypatch, connection)

    def native_cancel(_driver, _connection):
        execute_released.set()
        return True

    monkeypatch.setattr(firebird_query_executor, "_request_native_cancel", native_cancel)
    captured = []

    worker = threading.Thread(
        target=lambda: captured.append(
            firebird_query_executor.execute_query_read_only(
                dsn="localhost:C:/SIAFLOJA.FDB",
                username="SYSDBA",
                password="temporary",
                client_library="C:/Firebird/fbclient.dll",
                sql="SELECT CODIGO, NOME FROM TESTE ORDER BY NOME",
                parameters=(),
                on_batch=lambda _batch: None,
                cancel_event=cancel,
            )
        )
    )
    worker.start()
    assert execute_started.wait(1)
    cancel.set()
    worker.join(2)

    assert not worker.is_alive()
    assert captured[0].canceled
