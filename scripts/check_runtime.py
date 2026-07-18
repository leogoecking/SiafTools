from __future__ import annotations

import argparse
import json
import platform
import struct
import sys


def runtime_info() -> dict[str, object]:
    bits = struct.calcsize("P") * 8
    return {
        "executable": sys.executable,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "bits": bits,
        "architecture": "x86" if bits == 32 else "x64",
        "platform": platform.platform(),
        "build_compatible": bits == 32 and sys.version_info[:2] == (3, 11),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Confirma a arquitetura do runtime do projeto")
    parser.add_argument("--require-x86", action="store_true")
    args = parser.parse_args()
    info = runtime_info()
    print(json.dumps(info, indent=2, ensure_ascii=False))
    if args.require_x86 and not info["build_compatible"]:
        print(
            "ERRO: o build homologado exige Python 3.11 x86/32 bits.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
