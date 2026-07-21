from __future__ import annotations

from siaf_support_toolbox.database.sql_validator import (
    bind_parameters,
    validate_read_only_sql,
)
from siaf_support_toolbox.services.query_execution_service import _phase_seven_templates


def test_phase_seven_templates_are_read_only_and_declare_exact_dependencies():
    templates = _phase_seven_templates()

    assert tuple(template.name for template in templates) == (
        "Produtos — busca e detalhes",
        "Clientes — busca e detalhes",
        "Fornecedores — busca e detalhes",
    )
    for template in templates:
        validation = validate_read_only_sql(template.sql_template)
        assert validation.valid, validation.message
        assert {name.casefold() for name in validation.relation_names} == {
            name.casefold() for name in template.required_tables
        }
        assert "FIRST 500" not in template.sql_template
        assert template.result_limit is None


def test_phase_seven_optional_filters_bind_blank_values_as_null():
    for template in _phase_seven_templates():
        validation = validate_read_only_sql(template.sql_template)
        supplied = {name: "" for name in template.parameters_schema}

        bound = bind_parameters(validation, supplied, template.parameters_schema)

        assert bound
        assert set(bound) == {None}


def test_product_supplier_filter_uses_validated_relationship_table():
    product_template = _phase_seven_templates()[0]

    assert product_template.required_fields["DSIAF030"] == ("PRO_COD", "FOR_COD")
    assert "FROM DSIAF030 PF" in product_template.sql_template
    assert "PF.PRO_COD = P.PRO_COD" in product_template.sql_template
    assert "PF.FOR_COD = :fornecedor" in product_template.sql_template
