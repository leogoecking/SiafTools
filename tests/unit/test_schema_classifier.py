from siaf_support_toolbox.discovery.schema_classifier import DatabaseType, classify_schema


def test_classifies_siafloja_from_schema():
    result = classify_schema(["DSIAF006", "DSIAF010", "DSIAF036", "DSIAF037", "OTHER"])
    assert result.database_type == DatabaseType.SIAFLOJA
    assert result.confidence > 50
    assert result.is_accepted


def test_classifies_siafw_from_schema():
    result = classify_schema(["DSIAF001", "DSIAF050", "DSIAF051", "DSIAF052", "DSIAF053"])
    assert result.database_type == DatabaseType.SIAFW
    assert result.confidence >= 80


def test_rejects_file_without_siaf_schema():
    result = classify_schema(["CUSTOMERS", "PRODUCTS"])
    assert result.database_type == DatabaseType.NOT_SIAF
    assert result.confidence == 0
    assert not result.is_accepted


def test_does_not_accept_single_known_table():
    result = classify_schema(["DSIAF006"])
    assert result.database_type == DatabaseType.SIAFLOJA
    assert result.confidence == 14
    assert not result.is_accepted
