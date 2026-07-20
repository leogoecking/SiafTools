from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from siaf_support_toolbox.database import firebird_schema_inspector
from siaf_support_toolbox.discovery.models import Architecture


class FakeCursor:
    def __init__(self) -> None:
        self.rows: list[tuple[object, ...]] = []
        self.offset = 0
        self.fetch_sizes: list[int] = []
        self.closed = False

    def execute(self, sql: str) -> None:
        self.offset = 0
        if "FROM RDB$RELATION_FIELDS" in sql:
            self.rows = [
                ("DSIAF006", "PRO_COD", 8, 1, 4, -3, 1, 0, 9, None, None, None),
                (
                    "DSIAF006", "PRO_DES", 37, 0, 80, 0, None, 1,
                    None, 80, "WIN1252", "PXW_INTL",
                ),
            ]
        elif "FROM RDB$INDICES" in sql:
            self.rows = [
                ("PK_DSIAF006", "DSIAF006", "PRO_COD", 1, 0, "PRIMARY KEY", 0, None),
                ("IDX_PRO_DES", "DSIAF006", "PRO_DES", 0, 0, None, 0, None),
                (
                    "IDX_PRO_UPPER", "DSIAF006", None, 0, 0, None, None,
                    "UPPER(PRO_DES)",
                ),
            ]
        elif "FROM RDB$TRIGGERS" in sql:
            self.rows = [("TRG_DSIAF006_BI", "DSIAF006", 1, 0, 0, "BEGIN END")]
        elif "FROM RDB$PROCEDURE_PARAMETERS" in sql:
            self.rows = [
                (
                    "PR_ATUALIZA_PRODUTO", "P_COD", 0, 0, 8, 0, 4, 0,
                    9, None, None, None, None, 0, None, None,
                )
            ]
        elif "FROM RDB$PROCEDURES" in sql:
            self.rows = [("PR_ATUALIZA_PRODUTO", 1, 0, 2, "BEGIN EXIT; END")]
        elif "FROM RDB$GENERATORS" in sql:
            self.rows = [("GEN_DSIAF006",)]
        elif "FROM RDB$RELATIONS" in sql:
            self.rows = [
                ("DSIAF006", None, None),
                ("VW_PRODUTOS", b"view", "SELECT * FROM DSIAF006"),
            ]
        else:
            raise AssertionError(f"SQL de catálogo inesperado: {sql}")

    def fetchmany(self, size: int):
        self.fetch_sizes.append(size)
        if self.offset >= len(self.rows):
            return []
        batch = self.rows[self.offset : self.offset + 1]
        self.offset += 1
        return batch

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    version = "2.5.7.27050"
    ods = "11.2"

    def __init__(self) -> None:
        self.fake_cursor = FakeCursor()
        self.tpb = None
        self.rolled_back = False
        self.closed = False

    def begin(self, *, tpb) -> None:
        self.tpb = tpb

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_inspector_reads_complete_catalog_in_batches_and_rolls_back(monkeypatch):
    connection = FakeConnection()
    fake_fdb = SimpleNamespace(
        ISOLATION_LEVEL_READ_COMMITED_RO=b"readonly",
        load_api=lambda _path: object(),
        connect=lambda **_kwargs: connection,
    )
    monkeypatch.setitem(sys.modules, "fdb", fake_fdb)
    monkeypatch.setattr(
        firebird_schema_inspector, "pe_architecture", lambda _path: Architecture.X86
    )
    monkeypatch.setattr(
        firebird_schema_inspector, "process_architecture", lambda: Architecture.X86
    )

    result = firebird_schema_inspector.inspect_schema_read_only(
        dsn="localhost:C:/SIAFLOJA.FDB",
        username="authorized",
        password="session-only",
        client_library="fbclient.dll",
    )

    assert result.success
    assert result.snapshot is not None
    assert [item.name for item in result.snapshot.relations] == ["DSIAF006", "VW_PRODUTOS"]
    assert result.snapshot.relations[1].is_view
    assert len(result.snapshot.fields) == 2
    assert result.snapshot.fields[0].field_type == "NUMERIC"
    assert result.snapshot.fields[0].field_precision == 9
    assert result.snapshot.fields[0].primary_key
    assert not result.snapshot.fields[0].nullable
    assert result.snapshot.fields[0].index_names == ("PK_DSIAF006",)
    assert result.snapshot.fields[1].field_type == "VARCHAR"
    assert result.snapshot.fields[1].character_length == 80
    assert result.snapshot.fields[1].character_set_name == "WIN1252"
    assert result.snapshot.fields[1].collation_name == "PXW_INTL"
    assert len(result.snapshot.indexes) == 3
    assert result.snapshot.indexes[2].fields == ()
    assert result.snapshot.indexes[2].expression_hash.startswith("sha256:")
    assert result.snapshot.triggers[0].active
    assert result.snapshot.triggers[0].source_hash.startswith("sha256:")
    assert result.snapshot.procedures[0].input_count == 1
    assert result.snapshot.procedures[0].source_hash.startswith("sha256:")
    assert result.snapshot.procedures[0].parameters_hash.startswith("sha256:")
    assert result.snapshot.relations[1].definition_hash.startswith("sha256:")
    assert result.snapshot.generators[0].name == "GEN_DSIAF006"
    assert connection.tpb == b"readonly"
    assert connection.rolled_back
    assert connection.closed
    assert connection.fake_cursor.closed
    assert connection.fake_cursor.fetch_sizes
    assert set(connection.fake_cursor.fetch_sizes) == {200}


def test_inspector_rejects_runtime_before_reading_catalog(monkeypatch):
    connection = FakeConnection()
    connection.version = "4.0.5"
    fake_fdb = SimpleNamespace(
        ISOLATION_LEVEL_READ_COMMITED_RO=b"readonly",
        load_api=lambda _path: object(),
        connect=lambda **_kwargs: connection,
    )
    monkeypatch.setitem(sys.modules, "fdb", fake_fdb)
    monkeypatch.setattr(
        firebird_schema_inspector, "pe_architecture", lambda _path: Architecture.X86
    )
    monkeypatch.setattr(
        firebird_schema_inspector, "process_architecture", lambda: Architecture.X86
    )

    result = firebird_schema_inspector.inspect_schema_read_only(
        dsn="localhost:C:/SIAFLOJA.FDB",
        username="authorized",
        password="session-only",
        client_library="fbclient.dll",
    )

    assert not result.success
    assert result.error_code == "unsupported_firebird_version"
    assert not connection.fake_cursor.fetch_sizes
    assert connection.rolled_back
    assert connection.closed


@pytest.mark.parametrize(
    ("type_code", "subtype", "expected"),
    [(7, 1, "NUMERIC"), (8, 2, "DECIMAL"), (16, 1, "NUMERIC")],
)
def test_numeric_subtypes_are_recognized_for_all_integer_storage_types(
    type_code, subtype, expected
):
    assert firebird_schema_inspector._field_type(type_code, subtype) == expected
