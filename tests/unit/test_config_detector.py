from siaf_support_toolbox.discovery.config_detector import (
    detect_firebird_configurations,
    parse_aliases,
    parse_firebird_port,
)


def test_parses_aliases_and_ignores_comments():
    aliases = parse_aliases(
        '# exemplo = C:\\ignorar.fdb\nLOJA = "C:\\SIAF\\SIAFLOJA.FDB"\n; outro\n'
    )
    assert len(aliases) == 1
    assert aliases[0].alias == "LOJA"
    assert aliases[0].database == "C:\\SIAF\\SIAFLOJA.FDB"


def test_reads_explicit_port_and_ignores_commented_default():
    assert parse_firebird_port("#RemoteServicePort = 3050\nRemoteServicePort = 3055") == 3055


def test_uses_default_port_when_not_configured():
    assert parse_firebird_port("#RemoteServicePort = 3055") == 3050


def test_keeps_multiple_firebird_instances_separate(tmp_path):
    first = tmp_path / "Firebird25"
    second = tmp_path / "Firebird30"
    first.mkdir()
    second.mkdir()
    (first / "firebird.conf").write_text("RemoteServicePort = 3050", encoding="utf-8")
    (first / "aliases.conf").write_text("LOJA = C:\\SIAF\\SIAFLOJA.FDB", encoding="utf-8")
    (second / "firebird.conf").write_text("RemoteServicePort = 3055", encoding="utf-8")

    configurations, issues = detect_firebird_configurations([tmp_path])

    assert issues == []
    assert [item.port for item in configurations] == [3050, 3055]
    assert configurations[0].aliases[0].alias == "LOJA"
    assert configurations[1].aliases == ()
