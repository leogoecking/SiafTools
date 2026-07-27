from __future__ import annotations

from dataclasses import replace

import pytest

from siaf_support_toolbox.fiscal.nfe_xml_reader import parse_nfe_xml
from siaf_support_toolbox.services.supplier_return_diagnostic_service import (
    ComparisonStatus,
    build_supplier_return_mirror,
    compare_supplier_return_mirror,
    normalize_mirror_value,
    update_mirror_field,
)
from tests.unit.test_nfe_xml_reader import _nfe_xml


def test_prefilled_mirror_matches_original_xml():
    document = parse_nfe_xml(_nfe_xml())
    mirror = build_supplier_return_mirror(document)

    comparison = compare_supplier_return_mirror(document, mirror)

    assert comparison.matches
    assert comparison.different_count == 0
    assert mirror.items[0].product_code == "ABC-1"
    assert all(field.status is ComparisonStatus.MATCH for field in comparison.fields)
    assert {
        "produto.indDevol",
        "impostoDevol.pDevol",
        "impostoDevol.IPI.IPIDevol.vIPIDevol",
    }.issubset({field.path for field in mirror.items[0].fields})


def test_return_specific_field_absent_from_source_can_be_informed():
    document = parse_nfe_xml(_nfe_xml())
    mirror = build_supplier_return_mirror(document)
    mirror = update_mirror_field(
        mirror,
        item_number=1,
        path="impostoDevol.IPI.IPIDevol.vIPIDevol",
        value="5,00",
    )

    comparison = compare_supplier_return_mirror(document, mirror)
    returned_ipi = next(
        field
        for field in comparison.fields
        if field.path == "impostoDevol.IPI.IPIDevol.vIPIDevol"
    )

    assert returned_ipi.status is ComparisonStatus.MIRROR_ONLY
    assert returned_ipi.original_value == ""
    assert returned_ipi.mirror_value == "5.00"
    assert comparison.different_count == 1


def test_return_specific_field_present_in_source_is_prefilled_without_duplication():
    returned_tax = (
        b"<impostoDevol><pDevol>100.00</pDevol><IPI><IPIDevol>"
        b"<vIPIDevol>5.00</vIPIDevol></IPIDevol></IPI></impostoDevol>"
    )
    document = parse_nfe_xml(
        _nfe_xml().replace(b"</imposto>", b"</imposto>" + returned_tax, 1)
    )

    mirror = build_supplier_return_mirror(document)
    paths = [field.path for field in mirror.items[0].fields]
    comparison = compare_supplier_return_mirror(document, mirror)

    assert paths.count("impostoDevol.pDevol") == 1
    assert paths.count("impostoDevol.IPI.IPIDevol.vIPIDevol") == 1
    assert comparison.matches


def test_manual_mirror_change_is_reported_with_original_and_informed_values():
    document = parse_nfe_xml(_nfe_xml())
    mirror = build_supplier_return_mirror(document)
    mirror = update_mirror_field(
        mirror,
        item_number=1,
        path="imposto.ICMS.ICMS00.pICMS",
        value="18.00",
    )

    comparison = compare_supplier_return_mirror(document, mirror)
    difference = next(
        field
        for field in comparison.fields
        if field.path == "imposto.ICMS.ICMS00.pICMS"
    )

    assert not comparison.matches
    assert difference.status is ComparisonStatus.DIFFERENT
    assert difference.original_value == "12.0000"
    assert difference.mirror_value == "18.00"


def test_decimal_format_variation_does_not_create_false_difference():
    document = parse_nfe_xml(_nfe_xml())
    mirror = build_supplier_return_mirror(document)
    mirror = update_mirror_field(
        mirror,
        item_number=1,
        path="produto.qCom",
        value="2",
    )

    comparison = compare_supplier_return_mirror(document, mirror)
    quantity = next(field for field in comparison.fields if field.path == "produto.qCom")

    assert quantity.status is ComparisonStatus.MATCH


def test_brazilian_decimal_input_is_normalized_before_comparison():
    document = parse_nfe_xml(_nfe_xml())
    mirror = build_supplier_return_mirror(document)
    mirror = update_mirror_field(
        mirror,
        item_number=1,
        path="imposto.ICMS.ICMS00.pICMS",
        value="18,00",
    )

    comparison = compare_supplier_return_mirror(document, mirror)
    difference = next(
        field
        for field in comparison.fields
        if field.path == "imposto.ICMS.ICMS00.pICMS"
    )

    assert difference.mirror_value == "18.00"


def test_invalid_decimal_input_is_rejected():
    with pytest.raises(ValueError, match="número decimal"):
        normalize_mirror_value("produto.vProd", "cem reais")


def test_blank_manual_value_is_reported_as_missing():
    document = parse_nfe_xml(_nfe_xml())
    mirror = build_supplier_return_mirror(document)
    mirror = update_mirror_field(
        mirror,
        item_number=1,
        path="produto.CFOP",
        value=" ",
    )

    comparison = compare_supplier_return_mirror(document, mirror)
    cfop = next(field for field in comparison.fields if field.path == "produto.CFOP")

    assert cfop.status is ComparisonStatus.MISSING


def test_missing_item_is_not_silently_ignored():
    document = parse_nfe_xml(_nfe_xml())
    mirror = replace(build_supplier_return_mirror(document), items=())

    comparison = compare_supplier_return_mirror(document, mirror)

    assert any(
        field.status is ComparisonStatus.ITEM_MISSING for field in comparison.fields
    )


def test_mirror_from_another_xml_is_rejected():
    document = parse_nfe_xml(_nfe_xml())
    mirror = replace(build_supplier_return_mirror(document), source_access_key="0" * 44)

    with pytest.raises(ValueError, match="não pertence"):
        compare_supplier_return_mirror(document, mirror)


def test_duplicate_mirror_item_is_rejected():
    document = parse_nfe_xml(_nfe_xml())
    mirror = build_supplier_return_mirror(document)
    mirror = replace(mirror, items=mirror.items + mirror.items)

    with pytest.raises(ValueError, match="duplicado"):
        compare_supplier_return_mirror(document, mirror)


def test_updating_unknown_item_or_field_is_rejected():
    document = parse_nfe_xml(_nfe_xml())
    mirror = build_supplier_return_mirror(document)

    with pytest.raises(KeyError):
        update_mirror_field(mirror, item_number=999, path="produto.CFOP", value="5202")
    with pytest.raises(KeyError):
        update_mirror_field(mirror, item_number=1, path="produto.inexistente", value="1")
