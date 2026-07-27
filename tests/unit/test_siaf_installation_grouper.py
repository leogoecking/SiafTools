from siaf_support_toolbox.discovery.models import (
    ConnectionReferenceFinding,
    DatabaseCandidate,
    ProcessFinding,
)
from siaf_support_toolbox.discovery.siaf_installation_grouper import (
    group_siaf_installations,
    installation_for_database,
)


def test_groups_databases_and_configuration_by_nearest_siaf_root(tmp_path):
    first = tmp_path / "SIAF-A"
    second = tmp_path / "SIAF-B"
    first.mkdir()
    second.mkdir()
    first_executable = first / "SIAFW.EXE"
    second_executable = second / "SIAFW.EXE"
    first_database = first / "Dados" / "SIAFLOJA.FDB"
    second_database = second / "Dados" / "SIAFLOJA.FDB"
    first_config = first / "Config" / "siaf.ini"

    findings = group_siaf_installations(
        [first_executable, second_executable],
        [ProcessFinding(10, "SIAFW.EXE", str(second_executable))],
        [
            DatabaseCandidate(str(first_database), "SIAFLOJA", 100, 80),
            DatabaseCandidate(str(second_database), "SIAFLOJA", 100, 85),
        ],
        [ConnectionReferenceFinding("server", 3050, "LOJA01", str(first_config))],
    )

    assert findings[0].root == str(second)
    assert findings[0].active
    by_root = {item.root: item for item in findings}
    assert by_root[str(first)].database_paths == (str(first_database),)
    assert by_root[str(first)].reference_sources == (str(first_config),)
    assert installation_for_database(str(second_database), findings) == str(second)
