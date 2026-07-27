from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from siaf_support_toolbox.fiscal.nfe_xml_reader import parse_nfe_xml
from siaf_support_toolbox.services.supplier_return_preparation_service import (
    GuidanceLevel,
    analyze_supplier_return_preparation,
    build_supplier_return_preparation,
    format_supplier_return_analysis,
    parse_optional_decimal,
    update_preparation_item,
    update_preparation_totals,
)
from siaf_support_toolbox.ui.dialogs.supplier_return_preparation_dialog import (
    _document_total_values,
    _is_siaf_total_editable,
    _selection_total_values,
)
from tests.unit.test_nfe_xml_reader import _nfe_xml


def _preparation():
    document = parse_nfe_xml(_nfe_xml())
    return build_supplier_return_preparation(document)


def test_build_preparation_keeps_items_unselected_and_source_values():
    preparation = _preparation()
    item = preparation.items[0]

    assert preparation.selected_items == ()
    assert item.return_quantity == Decimal("2.0000")
    assert item.unit_value == Decimal("50.0000000000")
    assert item.product_total == Decimal("100.00")


def test_select_partial_quantity_recalculates_merchandise():
    preparation = update_preparation_item(
        _preparation(),
        1,
        selected=True,
        values={"return_quantity": "1", "unit_value": "50,00"},
    )

    assert preparation.calculated_merchandise == Decimal("50.00")


def test_product_total_preserves_xml_value_and_accepts_manual_mirror_total():
    xml = (
        _nfe_xml()
        .replace(b"<qCom>2.0000</qCom>", b"<qCom>3.0000</qCom>", 1)
        .replace(
            b"<vUnCom>50.0000000000</vUnCom>",
            b"<vUnCom>33.3330000000</vUnCom>",
            1,
        )
        .replace(b"<vProd>100.00</vProd>", b"<vProd>99.99</vProd>", 1)
    )
    preparation = build_supplier_return_preparation(parse_nfe_xml(xml))
    preparation = update_preparation_item(preparation, 1, selected=True)

    assert preparation.calculated_merchandise == Decimal("99.99")

    preparation = update_preparation_item(
        preparation,
        1,
        values={"return_quantity": "2"},
    )
    assert preparation.calculated_merchandise == Decimal("66.67")

    preparation = update_preparation_item(
        preparation,
        1,
        values={
            "mirror_product_total": "66,65",
            "siaf_product_total": "66,66",
        },
    )
    assert preparation.calculated_merchandise == Decimal("66.65")


def test_quantity_above_original_is_rejected():
    with pytest.raises(ValueError, match="não pode superar"):
        update_preparation_item(
            _preparation(),
            1,
            selected=True,
            values={"return_quantity": "3"},
        )


def test_required_item_values_and_percent_limits_are_validated():
    preparation = _preparation()

    with pytest.raises(ValueError, match="obrigatório"):
        update_preparation_item(
            preparation,
            1,
            values={"return_quantity": ""},
        )
    with pytest.raises(ValueError, match="100%"):
        update_preparation_item(
            preparation,
            1,
            values={"mirror_icms_rate": "101"},
        )
    with pytest.raises(ValueError, match="100%"):
        update_preparation_totals(
            preparation,
            source="mirror",
            values={"icms_rate": "101"},
        )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e3", "-1"])
def test_manual_decimal_rejects_non_finite_exponential_or_negative(value):
    with pytest.raises(ValueError):
        parse_optional_decimal(value, label="Teste")


def test_analysis_identifies_sample_like_packaging_and_direct_differences():
    preparation = update_preparation_item(
        _preparation(),
        1,
        selected=True,
        values={
            "unit_value": "335,115",
            "mirror_icms_rate": "17,00",
            "siaf_icms_rate": "17,01",
        },
    )
    preparation = update_preparation_totals(
        preparation,
        source="mirror",
        values={
            "merchandise": "670,23",
            "packaging": "0,68",
            "icms_rate": "17,00",
            "icms_value": "114,05",
            "st_base": "839,98",
            "st_value": "28,75",
            "invoice_total": "699,66",
        },
    )
    preparation = update_preparation_totals(
        preparation,
        source="siaf",
        values={
            "merchandise": "670,23",
            "additional_expenses": "0,00",
            "increase": "0,00",
            "icms_base": "670,23",
            "icms_value": "114,00",
            "st_base": "839,12",
            "st_value": "28,65",
            "invoice_total": "698,88",
        },
    )

    analysis = analyze_supplier_return_preparation(preparation)
    titles = {item.title: item.level for item in analysis.guidance}

    assert titles["Alíquota/percentual de ICMS divergente"] is GuidanceLevel.CONFIRMED
    assert titles["Valor de ICMS divergente"] is GuidanceLevel.CONFIRMED
    assert titles["Embalagem pode não estar representada no SIAF"] is (
        GuidanceLevel.POSSIBLE_CAUSE
    )
    assert titles["Composição provável da base de ICMS identificada"] is (
        GuidanceLevel.POSSIBLE_CAUSE
    )
    assert titles["Configuração estadual pode influenciar o ICMS ST"] is (
        GuidanceLevel.POSSIBLE_CAUSE
    )
    assert titles["Totais informados reconciliam aritmeticamente"] is (
        GuidanceLevel.POSSIBLE_CAUSE
    )


def test_analysis_applies_item_reduction_before_icms_rate():
    preparation = update_preparation_item(
        _preparation(),
        1,
        selected=True,
        values={
            "mirror_icms_rate": "17",
            "mirror_reduction_rate": "10",
        },
    )
    preparation = update_preparation_totals(
        preparation,
        source="mirror",
        values={
            "merchandise": "100",
            "icms_base": "90",
            "icms_value": "15,30",
        },
    )

    analysis = analyze_supplier_return_preparation(preparation)

    assert any(
        item.title == "Composição provável da base de ICMS identificada"
        for item in analysis.guidance
    )


def test_analysis_calculates_mixed_item_rates_without_aggregating_them():
    preparation = update_preparation_item(
        _preparation(),
        1,
        selected=True,
        values={
            "mirror_icms_rate": "17",
            "mirror_product_total": "100",
        },
    )
    second_item = replace(
        preparation.items[0],
        item_number=2,
        product_code="ABC-2",
        mirror_icms_rate=Decimal("12"),
    )
    preparation = replace(
        preparation,
        items=(preparation.items[0], second_item),
    )
    preparation = update_preparation_totals(
        preparation,
        source="mirror",
        values={"merchandise": "200", "icms_value": "29"},
    )

    analysis = analyze_supplier_return_preparation(preparation)

    assert any(
        item.title == "Composição provável da base de ICMS identificada"
        for item in analysis.guidance
    )


def test_analysis_requires_explicit_expense_allocation_for_mixed_rates():
    preparation = update_preparation_item(
        _preparation(),
        1,
        selected=True,
        values={
            "mirror_icms_rate": "17",
            "mirror_product_total": "100",
        },
    )
    second_item = replace(
        preparation.items[0],
        item_number=2,
        product_code="ABC-2",
        mirror_icms_rate=Decimal("12"),
    )
    preparation = replace(
        preparation,
        items=(preparation.items[0], second_item),
    )
    preparation = update_preparation_totals(
        preparation,
        source="mirror",
        values={
            "merchandise": "200",
            "packaging": "1",
            "icms_value": "29,17",
        },
    )

    analysis = analyze_supplier_return_preparation(preparation)

    assert any(
        item.title == "Despesas exigem rateio entre alíquotas diferentes"
        and item.level is GuidanceLevel.PENDING_CONFIRMATION
        for item in analysis.guidance
    )


def test_totals_reference_separates_full_xml_from_current_selection():
    document = parse_nfe_xml(_nfe_xml())
    preparation = update_preparation_item(
        build_supplier_return_preparation(document),
        1,
        selected=True,
        values={"return_quantity": "1"},
    )

    assert _document_total_values(document)["merchandise"] == "100.00"
    assert _selection_total_values(preparation)["merchandise"] == "50,00"
    assert _is_siaf_total_editable("additional_expenses") is True
    assert _is_siaf_total_editable("packaging") is False


def test_analysis_requires_selection_and_merchandise():
    analysis = analyze_supplier_return_preparation(_preparation())

    assert analysis.count(GuidanceLevel.PENDING_CONFIRMATION) == 1
    assert "Nenhum item selecionado" in format_supplier_return_analysis(analysis)


def test_formatted_analysis_keeps_fiscal_warning():
    preparation = update_preparation_item(_preparation(), 1, selected=True)
    analysis = analyze_supplier_return_preparation(preparation)

    formatted = format_supplier_return_analysis(analysis)

    assert "Mercadoria calculada: R$ 100,00" in formatted
    assert "não confirma a correção fiscal" in formatted


def test_unknown_total_or_item_field_is_rejected():
    preparation = _preparation()

    with pytest.raises(KeyError):
        update_preparation_totals(
            preparation,
            source="mirror",
            values={"campo_inventado": "1"},
        )
    with pytest.raises(KeyError):
        update_preparation_item(
            preparation,
            1,
            values={"campo_inventado": "1"},
        )
