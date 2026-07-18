from siaf_support_toolbox.discovery.bounded_scan import find_exact_names


def test_searches_exact_names_without_crossing_depth(tmp_path):
    near = tmp_path / "one" / "two"
    near.mkdir(parents=True)
    expected = near / "SIAFW.FDB"
    expected.write_bytes(b"test")
    too_deep = near / "three" / "four"
    too_deep.mkdir(parents=True)
    (too_deep / "SIAFLOJA.FDB").write_bytes(b"test")

    found, errors = find_exact_names(tmp_path.iterdir(), {"siafw.fdb", "siafloja.fdb"}, max_depth=1)

    assert found == [expected]
    assert errors == []


def test_ignores_similar_names(tmp_path):
    (tmp_path / "SIAFW.FDB.backup").write_bytes(b"test")
    found, _ = find_exact_names([tmp_path], {"siafw.fdb"})
    assert found == []
