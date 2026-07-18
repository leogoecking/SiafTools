from __future__ import annotations

import struct

import pytest

from siaf_support_toolbox.discovery.architecture import pe_architecture, process_bits
from siaf_support_toolbox.discovery.models import Architecture


@pytest.mark.parametrize(
    ("machine", "expected"),
    [(0x014C, Architecture.X86), (0x8664, Architecture.X64), (0xAA64, Architecture.ARM)],
)
def test_detects_pe_architecture(tmp_path, machine, expected):
    payload = bytearray(256)
    payload[0:2] = b"MZ"
    payload[0x3C:0x40] = struct.pack("<I", 128)
    payload[128:132] = b"PE\x00\x00"
    payload[132:134] = struct.pack("<H", machine)
    library = tmp_path / "fbclient.dll"
    library.write_bytes(payload)

    assert pe_architecture(library) == expected


def test_process_bitness_is_explicit():
    assert process_bits() in {32, 64}


def test_invalid_file_has_unknown_architecture(tmp_path):
    library = tmp_path / "fbclient.dll"
    library.write_text("not a PE file", encoding="utf-8")
    assert pe_architecture(library) == Architecture.UNKNOWN
