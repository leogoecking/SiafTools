from siaf_support_toolbox.discovery.models import Architecture, DiscoveryReport, MachineMode


def test_report_serializes_enums_for_json():
    report = DiscoveryReport(
        process_architecture=Architecture.X86,
        process_bits=32,
        mode=MachineMode.ASSISTED,
    )
    payload = report.to_dict()
    assert payload["process_architecture"] == "x86"
    assert payload["mode"] == "assistido"
