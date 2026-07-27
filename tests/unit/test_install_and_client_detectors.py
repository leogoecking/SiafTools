from __future__ import annotations

import struct

from siaf_support_toolbox.discovery import firebird_client_detector, siaf_install_detector
from siaf_support_toolbox.discovery.firebird_client_probe import ClientProbeResult
from siaf_support_toolbox.discovery.models import Architecture, ProcessFinding


def write_pe(path, machine: int) -> None:
    payload = bytearray(256)
    payload[0:2] = b"MZ"
    payload[0x3C:0x40] = struct.pack("<I", 128)
    payload[128:132] = b"PE\x00\x00"
    payload[132:134] = struct.pack("<H", machine)
    path.write_bytes(payload)


def test_install_detector_combines_process_and_limited_search(monkeypatch, tmp_path):
    process_executable = tmp_path / "running" / "SIAFW.EXE"
    process_executable.parent.mkdir()
    process_executable.write_bytes(b"exe")
    searched_executable = tmp_path / "installed" / "SIAFW.EXE"
    searched_executable.parent.mkdir()
    searched_executable.write_bytes(b"exe")
    monkeypatch.setattr(siaf_install_detector, "default_siaf_roots", lambda: [])

    findings, evidence, issues = siaf_install_detector.detect_siaf_installations(
        [ProcessFinding(10, "SIAFW.EXE", str(process_executable))],
        [searched_executable.parent],
    )

    assert issues == []
    assert set(findings) == {process_executable, searched_executable}
    assert {item.source for item in evidence} == {"processo_siaf", "busca_limitada_siaf"}


def test_client_detector_marks_matching_and_mismatching_pe_files(monkeypatch, tmp_path):
    write_pe(tmp_path / "fbclient.dll", 0x014C)
    nested = tmp_path / "other"
    nested.mkdir()
    write_pe(nested / "gds32.dll", 0x8664)

    monkeypatch.setattr(firebird_client_detector, "process_architecture", lambda: Architecture.X86)
    monkeypatch.setattr(
        firebird_client_detector,
        "probe_client_library",
        lambda _path: ClientProbeResult(True, "2.5.9.27139"),
    )

    findings, issues = firebird_client_detector.detect_client_libraries([tmp_path])

    assert issues == []
    by_name = {item.name: item for item in findings}
    assert by_name["fbclient.dll"].architecture == Architecture.X86
    assert by_name["fbclient.dll"].compatible_with_process
    assert by_name["gds32.dll"].architecture == Architecture.X64
    assert not by_name["gds32.dll"].compatible_with_process


def test_client_ranking_prefers_usable_supported_fbclient():
    findings = [
        firebird_client_detector.ClientLibraryFinding(
            "C:/Firebird/bin/gds32.dll",
            "gds32.dll",
            Architecture.X86,
            True,
            False,
            "9.0.3.437",
            "API ausente",
        ),
        firebird_client_detector.ClientLibraryFinding(
            "C:/Firebird/WOW64/fbclient.dll",
            "fbclient.dll",
            Architecture.X86,
            True,
            True,
            "2.5.9.27139",
        ),
    ]

    ranked = firebird_client_detector.rank_client_libraries(findings)

    assert ranked[0].name == "fbclient.dll"
    assert ranked[0].ready


def test_client_detector_preflights_identical_copies_only_once(monkeypatch, tmp_path):
    write_pe(tmp_path / "fbclient.dll", 0x014C)
    nested = tmp_path / "copy"
    nested.mkdir()
    write_pe(nested / "fbclient.dll", 0x014C)
    calls = []
    monkeypatch.setattr(firebird_client_detector, "process_architecture", lambda: Architecture.X86)

    def probe(path):
        calls.append(path)
        return ClientProbeResult(True, "2.5.9.27139")

    monkeypatch.setattr(firebird_client_detector, "probe_client_library", probe)

    findings, issues = firebird_client_detector.detect_client_libraries([tmp_path])

    assert issues == []
    assert len(findings) == 2
    assert len(calls) == 1
