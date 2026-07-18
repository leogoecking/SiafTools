from siaf_support_toolbox.discovery.database_locator import locate_databases


def test_database_name_is_only_a_candidate_hint(tmp_path):
    install = tmp_path / "SIAF"
    install.mkdir()
    executable = install / "SIAFW.EXE"
    executable.write_bytes(b"exe")
    database = install / "SIAFLOJA.FDB"
    database.write_bytes(b"not a real database")

    candidates, issues = locate_databases([install], [executable])

    assert issues == []
    assert len(candidates) == 1
    assert candidates[0].kind_hint == "SIAFLOJA"
    assert candidates[0].score < 100
    assert all(item.source != "esquema_validado" for item in candidates[0].evidence)
