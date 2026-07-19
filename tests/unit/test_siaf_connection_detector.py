from __future__ import annotations

from siaf_support_toolbox.discovery.siaf_connection_detector import (
    detect_siaf_connection_references,
    parse_connection_references,
)


def test_parser_finds_remote_local_and_alias_references_without_credentials():
    text = """
    Database=10.0.0.10/3055:D:\\Dados\\SIAFLOJA.FDB
    Config=C:\\SIAF\\SIAFW.FDB
    Alternate=servidor:LOJA01
    password=NAO-CAPTURAR server:SEGREDO
    """

    findings = parse_connection_references(text, "siaf.ini")

    assert {(item.host, item.port, item.database) for item in findings} == {
        ("10.0.0.10", 3055, "D:\\Dados\\SIAFLOJA.FDB"),
        (None, 3050, "C:\\SIAF\\SIAFW.FDB"),
        ("servidor", 3050, "LOJA01"),
    }
    assert all("SEGREDO" not in item.database for item in findings)


def test_detector_scans_only_bounded_configuration_files(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "siaf.ini").write_text("Database=servidor:LOJA01", encoding="utf-8")
    (config / "ignored.bin").write_text("Database=outro:LOJA02", encoding="utf-8")

    findings, issues = detect_siaf_connection_references([tmp_path])

    assert issues == []
    assert [(item.host, item.database) for item in findings] == [("servidor", "LOJA01")]


def test_detector_preserves_cp1252_paths_with_accents(tmp_path):
    config = tmp_path / "siaf.ini"
    config.write_bytes("Database=servidor:C:\\Dados\\São João\\SIAFLOJA.FDB".encode("cp1252"))

    findings, issues = detect_siaf_connection_references([tmp_path])

    assert issues == []
    assert len(findings) == 1
    assert findings[0].database == "C:\\Dados\\São João\\SIAFLOJA.FDB"
