from __future__ import annotations

from datetime import date

import pytest

from siaf_support_toolbox.database.sql_validator import (
    SQLParameterError,
    bind_parameters,
    validate_read_only_sql,
)
from siaf_support_toolbox.services.query_execution_service import (
    _phase_eight_templates,
    _required_parameter_group_issue,
)


def test_phase_eight_templates_cover_validated_operational_relations():
    templates = _phase_eight_templates()

    assert tuple(template.name for template in templates) == (
        "NF-e — saídas e indicadores",
        "NF-e — itens da saída",
        "Entradas — notas de fornecedor",
        "Entradas — itens da nota",
        "PDV — vendas e NFC-e",
        "PDV — itens da venda",
        "PDV — pagamentos da venda",
    )
    assert set().union(*(set(template.required_tables) for template in templates)) == {
        "DSIAF011",
        "DSIAF012",
        "DSIAF036",
        "DSIAF037",
        "DSIAF400",
        "DSIAF401",
        "DSIAF402",
    }


def test_phase_eight_sql_is_read_only_and_declares_exact_dependencies():
    for template in _phase_eight_templates():
        validation = validate_read_only_sql(template.sql_template)

        assert validation.valid, validation.message
        assert {name.casefold() for name in validation.relation_names} == {
            name.casefold() for name in template.required_tables
        }
        assert all(template.required_fields.values())
        assert "FIRST 501" not in template.sql_template
        assert template.result_limit is None


def test_phase_eight_templates_require_a_filter_before_execution():
    for template in _phase_eight_templates():
        blank = {name: "" for name in template.parameters_schema}

        issue = _required_parameter_group_issue(template.parameters_schema, blank)

        assert issue == "Informe pelo menos um filtro para limitar a consulta"
        first_parameter = next(iter(template.parameters_schema))
        blank[first_parameter] = "1"
        assert _required_parameter_group_issue(template.parameters_schema, blank) is None


def test_phase_eight_period_parameters_bind_as_dates():
    template = _phase_eight_templates()[0]
    validation = validate_read_only_sql(template.sql_template)
    supplied = {name: "" for name in template.parameters_schema}
    supplied["data_inicial"] = "01/07/2026"
    supplied["data_final"] = "19/07/2026"

    values = bind_parameters(validation, supplied, template.parameters_schema)

    assert date(2026, 7, 1) in values
    assert date(2026, 7, 19) in values
    assert set(value for value in values if value is not None) == {
        date(2026, 7, 1),
        date(2026, 7, 19),
    }


def test_phase_eight_rejects_reversed_period():
    template = _phase_eight_templates()[0]
    validation = validate_read_only_sql(template.sql_template)
    supplied = {name: "" for name in template.parameters_schema}
    supplied["data_inicial"] = "31/07/2026"
    supplied["data_final"] = "01/07/2026"

    with pytest.raises(SQLParameterError, match="posterior"):
        bind_parameters(validation, supplied, template.parameters_schema)


def test_phase_eight_payment_period_uses_payment_date():
    payment = _phase_eight_templates()[-1]

    assert "P.PDV_PREST_DATA >= :data_inicial" in payment.sql_template
    assert "P.PDV_PREST_DATA <= :data_final" in payment.sql_template
    assert "V.PDV_DATA >= :data_inicial" not in payment.sql_template
    assert "ORDER BY P.ID DESC" in payment.sql_template


def test_phase_eight_pdv_period_requires_both_dates_without_duration_limit():
    templates = _phase_eight_templates()
    sales, items, payments = templates[-3:]
    for template in (sales, items, payments):
        validation = validate_read_only_sql(template.sql_template)
        supplied = {name: "" for name in template.parameters_schema}
        supplied["data_inicial"] = "01/07/2026"
        with pytest.raises(SQLParameterError, match="data inicial e a data final"):
            bind_parameters(validation, supplied, template.parameters_schema)

        supplied = {name: "" for name in template.parameters_schema}
        supplied["data_inicial"] = "01/06/2026"
        supplied["data_final"] = "31/07/2026"
        values = bind_parameters(validation, supplied, template.parameters_schema)
        assert date(2026, 6, 1) in values
        assert date(2026, 7, 31) in values

    assert "ORDER BY V.ID DESC" in sales.sql_template
    assert "ORDER BY V.ID DESC" in items.sql_template
    assert "ORDER BY P.ID DESC" in payments.sql_template
    assert "ORDER BY V.PDV_DATA" not in sales.sql_template + items.sql_template
