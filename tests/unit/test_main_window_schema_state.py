from __future__ import annotations

from types import SimpleNamespace

from siaf_support_toolbox.services.connection_service import (
    ConnectionPlan,
    ConnectionTarget,
    SessionCredentials,
)
from siaf_support_toolbox.services.query_execution_service import QueryExecutionEstimate
from siaf_support_toolbox.ui import main_window
from siaf_support_toolbox.ui.main_window import MainWindow, _query_progress_message


class FakeEnvironmentPage:
    def __init__(self) -> None:
        self.busy = False
        self.actions: dict[str, bool] = {}

    def set_busy(self, value: bool) -> None:
        self.busy = value

    def set_actions(self, **values: bool) -> None:
        self.actions = values


class FakeWidget:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.started = False

    def config(self, **values: object) -> None:
        self.values.update(values)

    def start(self, _interval: int) -> None:
        self.started = True


class FakeThread:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.started = False

    def start(self) -> None:
        self.started = True

    def is_alive(self) -> bool:
        return False


def test_new_connection_validation_invalidates_previous_summary(monkeypatch):
    monkeypatch.setattr(main_window.threading, "Thread", FakeThread)
    target = ConnectionTarget(
        environment_id=1,
        database_id=1,
        host="localhost",
        port=3050,
        database_path="C:/SIAFLOJA.FDB",
        database_type_hint="SIAFLOJA",
        client_library="C:/Firebird/fbclient.dll",
        source="teste",
        confidence=100,
    )
    fake_window = SimpleNamespace(
        _connection_service=object(),
        _last_plan=ConnectionPlan(()),
        _last_summary=object(),
        environment_page=FakeEnvironmentPage(),
        progress=FakeWidget(),
        status_label=FakeWidget(),
        indicator_label=FakeWidget(),
        _discovery_started_at=None,
        _connection_thread=None,
        _run_connection=lambda *_args: None,
    )

    MainWindow._start_connection_worker(
        fake_window,
        ConnectionPlan((target,)),
        SessionCredentials("SYSDBA", "temporary"),
    )

    assert fake_window._last_summary is None
    assert fake_window.environment_page.actions == {
        "validate": False,
        "export": False,
        "manual": False,
    }
    assert fake_window._connection_thread.started


def test_query_progress_message_shows_historical_completion_estimate():
    message = _query_progress_message(
        2_000,
        100,
        QueryExecutionEstimate(
            duration_ms=10_000,
            expected_records=500,
            sample_count=3,
        ),
    )

    assert "Conclusão estimada às" in message
    assert "baseado em 3 execução(ões)" in message
    assert "Você pode cancelar" in message


def test_query_progress_message_is_honest_without_history():
    message = _query_progress_message(2_000, 0, None)

    assert "não há histórico suficiente" in message
    assert "cancelar a qualquer momento" in message
