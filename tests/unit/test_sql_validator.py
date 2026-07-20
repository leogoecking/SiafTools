from __future__ import annotations

from datetime import date

import pytest

from siaf_support_toolbox.database.sql_validator import (
    SQLParameterError,
    bind_parameters,
    validate_read_only_sql,
)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE CLIENTES SET NOME = 'X'",
        "DELETE FROM CLIENTES",
        "SELECT * FROM CLIENTES FOR UPDATE",
        "SELECT * FROM CLIENTES WITH LOCK",
        "SELECT 1 FROM RDB$DATABASE; DROP TABLE CLIENTES",
        "WITH X AS (DELETE FROM CLIENTES) SELECT * FROM X",
        "SELECT GEN_ID(MEU_GENERATOR, 1) FROM RDB$DATABASE",
        "SELECT NEXT VALUE FOR MEU_GENERATOR FROM RDB$DATABASE",
        "SELECT RDB$SET_CONTEXT('USER_SESSION', 'X', 'Y') FROM RDB$DATABASE",
    ],
)
def test_blocks_destructive_or_locking_sql(sql):
    assert not validate_read_only_sql(sql).valid


def test_ignores_keywords_and_parameters_inside_literals_and_comments():
    result = validate_read_only_sql(
        "SELECT 'DELETE :ignored' AS TEXT_VALUE /* UPDATE X */ "
        "FROM RDB$DATABASE -- DROP X\nWHERE 1 = :value;"
    )

    assert result.valid
    assert result.parameter_names == ("value",)
    assert "'DELETE :ignored'" in result.compiled_sql
    assert "1 = ?" in result.compiled_sql


def test_binds_repeated_typed_named_parameters_in_driver_order():
    validation = validate_read_only_sql(
        "SELECT * FROM TESTE WHERE CODIGO = :code OR OUTRO = :code AND ATIVO = :active"
    )

    values = bind_parameters(
        validation,
        {"code": "42", "active": "sim"},
        {
            "code": {"type": "integer", "required": True},
            "active": {"type": "boolean", "required": True},
        },
    )

    assert values == (42, 42, 1)


def test_binds_brazilian_date_and_rejects_other_formats():
    validation = validate_read_only_sql(
        "SELECT * FROM TESTE WHERE DATA >= :data AND DATA <= :data"
    )
    schema = {"data": {"type": "date", "required": True}}

    values = bind_parameters(validation, {"data": "19/07/2026"}, schema)

    assert values == (date(2026, 7, 19), date(2026, 7, 19))
    with pytest.raises(SQLParameterError, match="use DD/MM/AAAA"):
        bind_parameters(validation, {"data": "2026-07-19"}, schema)


def test_rejects_reversed_date_range():
    validation = validate_read_only_sql(
        "SELECT * FROM TESTE WHERE DATA >= :inicio AND DATA <= :fim"
    )
    schema = {
        "inicio": {
            "type": "date",
            "range_group": "periodo",
            "range_bound": "start",
        },
        "fim": {
            "type": "date",
            "range_group": "periodo",
            "range_bound": "end",
        },
    }

    with pytest.raises(SQLParameterError, match="posterior"):
        bind_parameters(
            validation,
            {"inicio": "31/07/2026", "fim": "01/07/2026"},
            schema,
        )


def test_rejects_missing_and_undeclared_parameters():
    validation = validate_read_only_sql("SELECT * FROM TESTE WHERE CODIGO = :code")

    with pytest.raises(SQLParameterError, match="sem definição"):
        bind_parameters(validation, {"code": "1"}, {})
    with pytest.raises(SQLParameterError, match="obrigatório"):
        bind_parameters(validation, {}, {"code": {"type": "integer"}})


def test_extracts_real_relations_and_ignores_cte_aliases():
    result = validate_read_only_sql(
        "WITH ITENS AS (SELECT ID FROM DSIAF001) "
        "SELECT I.ID FROM ITENS I JOIN DSIAF002 D ON D.ID = I.ID, DSIAF003 X"
    )

    assert result.valid
    assert result.relation_names == ("DSIAF001", "DSIAF002", "DSIAF003")


def test_blocks_selectable_procedure_sources():
    result = validate_read_only_sql(
        "SELECT * FROM PROCEDURE_COM_EFEITO(:codigo)"
    )

    assert not result.valid
    assert result.error_code == "selectable_procedure"
