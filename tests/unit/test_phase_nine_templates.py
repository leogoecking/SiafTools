from __future__ import annotations

from datetime import date

from siaf_support_toolbox.database.sql_validator import (
    bind_parameters,
    validate_read_only_sql,
)
from siaf_support_toolbox.services.query_execution_service import (
    _phase_nine_templates,
    _required_parameter_group_issue,
)


def test_phase_nine_templates_cover_finance_and_permission_relations():
    templates = _phase_nine_templates()

    assert tuple(template.name for template in templates) == (
        "Contas a receber — títulos e baixas",
        "Contas a pagar — títulos e baixas",
        "Caixa diário — cabeçalhos",
        "Caixa diário — lançamentos",
        "Caixa diário — transferências",
        "Tipos de venda",
        "Tipos de pagamento",
        "Usuários e grupos",
        "Permissões — diagnóstico por usuário, grupo e programa",
        "Permissões — catálogo de programas",
    )
    assert set().union(*(set(template.required_tables) for template in templates)) == {
        "DSIAF015",
        "DSIAF016",
        "DSIAF017",
        "DSIAF018",
        "DSIAF025",
        "DSIAF026",
        "DSIAF136",
        "DSIAF050",
        "DSIAF051",
        "DSIAF052",
        "DSIAF053",
    }


def test_phase_nine_sql_is_read_only_and_declares_exact_dependencies():
    templates = _phase_nine_templates()

    for template in templates:
        validation = validate_read_only_sql(template.sql_template)

        assert validation.valid, validation.message
        assert {name.casefold() for name in validation.relation_names} == {
            name.casefold() for name in template.required_tables
        }
        assert all(template.required_fields.values())
        assert template.read_only
        assert "FIRST 501" not in template.sql_template
        assert template.result_limit is None


def test_phase_nine_templates_require_a_filter_before_execution():
    for template in _phase_nine_templates():
        blank = {name: "" for name in template.parameters_schema}

        assert _required_parameter_group_issue(template.parameters_schema, blank) == (
            "Informe pelo menos um filtro para limitar a consulta"
        )
        first_parameter = next(iter(template.parameters_schema))
        blank[first_parameter] = "1"
        assert _required_parameter_group_issue(template.parameters_schema, blank) is None


def test_phase_nine_templates_treat_whitespace_as_an_empty_filter():
    for template in _phase_nine_templates():
        blank = {name: "   " for name in template.parameters_schema}

        assert _required_parameter_group_issue(template.parameters_schema, blank) == (
            "Informe pelo menos um filtro para limitar a consulta"
        )


def test_phase_nine_financial_period_uses_brazilian_dates_without_duration_limit():
    template = _phase_nine_templates()[0]
    validation = validate_read_only_sql(template.sql_template)
    supplied = {name: "" for name in template.parameters_schema}
    supplied["data_inicial"] = "01/01/2024"
    supplied["data_final"] = "31/12/2026"

    values = bind_parameters(validation, supplied, template.parameters_schema)

    assert date(2024, 1, 1) in values
    assert date(2026, 12, 31) in values


def test_phase_nine_never_selects_or_declares_user_password():
    permission_templates = tuple(
        template for template in _phase_nine_templates() if template.module == "Permissões"
    )

    assert permission_templates
    for template in permission_templates:
        assert "USU_SENHA" not in template.sql_template.upper()
        assert all(
            "USU_SENHA" not in fields for fields in template.required_fields.values()
        )


def test_phase_nine_permission_diagnostic_exposes_raw_permission_flags():
    diagnostic = _phase_nine_templates()[-2]

    for field in ("PROG_ACE", "PROG_INC", "PROG_ALT", "PROG_EXC", "PROG_IMP"):
        assert field in diagnostic.sql_template
    assert "LEFT JOIN DSIAF053" in diagnostic.sql_template
    assert "LEFT JOIN DSIAF050" in diagnostic.sql_template
    assert "CAST(:usuario AS INTEGER) IS NOT NULL" in diagnostic.sql_template
    assert "CAST(:nome AS VARCHAR(30)) IS NOT NULL" in diagnostic.sql_template


def test_phase_nine_payable_keeps_ambiguous_pra_cod_uninterpreted():
    payable = _phase_nine_templates()[1]

    assert "P.PRA_COD AS PRA_COD" in payable.sql_template
    assert "P.PRA_COD AS TIPO_VENDA" not in payable.sql_template
