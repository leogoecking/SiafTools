from __future__ import annotations

from decimal import Decimal

from siaf_support_toolbox.fiscal.nfe_xml_reader import NFeField, NFeItem
from siaf_support_toolbox.services.supplier_return_diagnostic_service import (
    ComparisonStatus,
    FieldComparison,
)
from siaf_support_toolbox.ui.pages.supplier_return_page import (
    format_item_details,
    item_row,
)


def _item() -> NFeItem:
    return NFeItem(
        number=3,
        product_code="FOR-123",
        barcode="7891234567890",
        description="Produto para devolução",
        ncm="12345678",
        cest="1234567",
        cfop="6102",
        unit="UN",
        quantity=Decimal("2.0000"),
        unit_value=Decimal("50.000000"),
        product_value=Decimal("100.00"),
        discount=Decimal("5.00"),
        freight=None,
        insurance=None,
        other_expenses=None,
        tax_fields=(
            NFeField(
                "imposto.ICMS.ICMS00.pICMS",
                "Alíquota de ICMS",
                "12.0000",
            ),
        ),
    )


def test_item_row_formats_values_for_brazilian_display():
    row = item_row(_item())

    assert row == (
        3,
        "FOR-123",
        "Produto para devolução",
        "12345678",
        "6102",
        "UN",
        "2,0000",
        "100,00",
    )


def test_item_details_preserves_xml_field_path_and_value():
    details = format_item_details(_item())

    assert "Quantidade: 2,0000" in details
    assert "Frete: não informado" in details
    assert "imposto.ICMS.ICMS00.pICMS: 12.0000" in details


def test_item_details_highlights_manual_mirror_difference():
    difference = FieldComparison(
        item_number=3,
        path="imposto.ICMS.ICMS00.pICMS",
        label="Alíquota de ICMS",
        original_value="12.0000",
        mirror_value="18.00",
        status=ComparisonStatus.DIFFERENT,
    )

    details = format_item_details(_item(), (difference,))

    assert "Diferenças informadas no espelho" in details
    assert "XML=12.0000 | Espelho=18.00" in details
