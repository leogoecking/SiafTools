from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path

REQUIRED_EXPORTS = ("isc_attach_database", "isc_detach_database", "fb_interpret")


@dataclass(frozen=True, slots=True)
class ClientProbeResult:
    usable: bool
    version: str | None = None
    issue: str | None = None
    missing_exports: tuple[str, ...] = ()


def inspect_client_library(path: str | Path) -> ClientProbeResult:
    library_path = Path(path)
    if not library_path.is_file():
        return ClientProbeResult(False, issue="Arquivo da biblioteca cliente não encontrado")
    try:
        library = ctypes.WinDLL(str(library_path))
    except (OSError, ValueError) as exc:
        return ClientProbeResult(
            False,
            version=_windows_file_version(library_path),
            issue=f"A biblioteca não pôde ser carregada ({type(exc).__name__})",
        )
    missing = tuple(name for name in REQUIRED_EXPORTS if not hasattr(library, name))
    if missing:
        return ClientProbeResult(
            False,
            version=_windows_file_version(library_path),
            issue="A biblioteca não oferece a API cliente Firebird esperada",
            missing_exports=missing,
        )
    return ClientProbeResult(True, version=_windows_file_version(library_path))


def probe_client_library(path: str | Path, *, timeout: float = 8.0) -> ClientProbeResult:
    output_fd, output_name = tempfile.mkstemp(prefix="siaf-fbclient-", suffix=".json")
    os.close(output_fd)
    output_path = Path(output_name)
    try:
        if getattr(sys, "frozen", False):
            command = [
                sys.executable,
                "--probe-firebird-client",
                str(path),
                str(output_path),
            ]
        else:
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                str(path),
                str(output_path),
            ]
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=timeout,
            creationflags=creation_flags,
        )
        if completed.returncode not in {0, 1} or not output_path.is_file():
            return ClientProbeResult(
                False,
                issue=f"O preflight da biblioteca terminou com código {completed.returncode}",
            )
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        return ClientProbeResult(
            bool(payload.get("usable")),
            payload.get("version"),
            payload.get("issue"),
            tuple(payload.get("missing_exports") or ()),
        )
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        return ClientProbeResult(
            False,
            issue=f"O preflight da biblioteca falhou ({type(exc).__name__})",
        )
    finally:
        with suppress(OSError):
            output_path.unlink(missing_ok=True)


def client_probe_main(arguments: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if arguments is None else arguments)
    if len(values) != 2:
        return 2
    library_path, output_name = values
    result = inspect_client_library(library_path)
    try:
        Path(output_name).write_text(
            json.dumps(asdict(result), ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        return 2
    return 0 if result.usable else 1


def _windows_file_version(path: Path) -> str | None:
    if os.name != "nt":
        return None

    class VSFixedFileInfo(ctypes.Structure):
        _fields_ = [
            ("signature", ctypes.c_uint32),
            ("struct_version", ctypes.c_uint32),
            ("file_version_ms", ctypes.c_uint32),
            ("file_version_ls", ctypes.c_uint32),
            ("product_version_ms", ctypes.c_uint32),
            ("product_version_ls", ctypes.c_uint32),
            ("file_flags_mask", ctypes.c_uint32),
            ("file_flags", ctypes.c_uint32),
            ("file_os", ctypes.c_uint32),
            ("file_type", ctypes.c_uint32),
            ("file_subtype", ctypes.c_uint32),
            ("file_date_ms", ctypes.c_uint32),
            ("file_date_ls", ctypes.c_uint32),
        ]

    version = ctypes.WinDLL("version", use_last_error=True)
    size = version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
        return None
    value = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(value), ctypes.byref(length)):
        return None
    info = ctypes.cast(value, ctypes.POINTER(VSFixedFileInfo)).contents
    return ".".join(
        str(part)
        for part in (
            info.file_version_ms >> 16,
            info.file_version_ms & 0xFFFF,
            info.file_version_ls >> 16,
            info.file_version_ls & 0xFFFF,
        )
    )


if __name__ == "__main__":
    raise SystemExit(client_probe_main())
