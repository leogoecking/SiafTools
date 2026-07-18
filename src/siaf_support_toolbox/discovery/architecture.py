from __future__ import annotations

import ctypes
import struct
from pathlib import Path

from siaf_support_toolbox.discovery.models import Architecture

_PE_MACHINES = {
    0x014C: Architecture.X86,
    0x8664: Architecture.X64,
    0x01C0: Architecture.ARM,
    0xAA64: Architecture.ARM,
}


def process_bits() -> int:
    return struct.calcsize("P") * 8


def process_architecture() -> Architecture:
    return Architecture.X86 if process_bits() == 32 else Architecture.X64


def is_process_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def pe_architecture(path: str | Path) -> Architecture:
    try:
        with Path(path).open("rb") as handle:
            if handle.read(2) != b"MZ":
                return Architecture.UNKNOWN
            handle.seek(0x3C)
            pe_offset_data = handle.read(4)
            if len(pe_offset_data) != 4:
                return Architecture.UNKNOWN
            pe_offset = struct.unpack("<I", pe_offset_data)[0]
            handle.seek(pe_offset)
            if handle.read(4) != b"PE\x00\x00":
                return Architecture.UNKNOWN
            machine_data = handle.read(2)
            if len(machine_data) != 2:
                return Architecture.UNKNOWN
            return _PE_MACHINES.get(struct.unpack("<H", machine_data)[0], Architecture.UNKNOWN)
    except (OSError, ValueError):
        return Architecture.UNKNOWN
