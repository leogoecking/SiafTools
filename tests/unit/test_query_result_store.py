from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from siaf_support_toolbox.services.query_result_store import QueryResultStore
from siaf_support_toolbox.ui.pages.query_page import _display_value


def test_result_store_paginates_and_removes_temporary_file(tmp_path):
    store = QueryResultStore(tmp_path)
    path = store.path
    store.append_batch(tuple((index, Decimal("10.25")) for index in range(205)))

    second = store.read_page(2, 100)

    assert second.total_records == 205
    assert second.total_pages == 3
    assert second.rows[0] == (100, Decimal("10.25"))
    store.close()
    assert not path.exists()


def test_result_store_preserves_typed_dates_and_normalizes_blobs(tmp_path):
    store = QueryResultStore(tmp_path)
    moment = datetime(2026, 7, 19, 12, 30)
    day = date(2026, 7, 19)
    hour = time(12, 30)
    store.append_batch(((moment, day, hour, b"abc"),))

    assert store.read_page(1).rows == ((moment, day, hour, "<BLOB 3 bytes>"),)
    assert tuple(store.iter_batches()) == (((moment, day, hour, "<BLOB 3 bytes>"),),)
    store.close()


def test_query_page_formats_dates_for_brazil():
    assert _display_value(date(2026, 7, 19)) == "19/07/2026"
    assert _display_value(datetime(2026, 7, 19, 12, 30)) == "19/07/2026 12:30:00"


def test_result_store_rejects_unbounded_page_sizes(tmp_path):
    store = QueryResultStore(tmp_path)
    with pytest.raises(ValueError, match="entre 1 e 1000"):
        store.read_page(1, 1001)
    store.close()


def test_result_store_iterates_in_bounded_batches(tmp_path):
    store = QueryResultStore(tmp_path)
    store.append_batch(tuple((index,) for index in range(5)))

    batches = tuple(store.iter_batches(2))

    assert tuple(len(batch) for batch in batches) == (2, 2, 1)
    assert batches[-1] == ((4,),)
    with pytest.raises(ValueError, match="entre 1 e 5000"):
        tuple(store.iter_batches(5001))
    store.close()
