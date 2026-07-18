from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from siaf_support_toolbox.core.logging_config import configure_logging  # noqa: E402
from siaf_support_toolbox.discovery.discovery_orchestrator import (  # noqa: E402
    DiscoveryOrchestrator,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico local sem credenciais")
    parser.add_argument("--json", action="store_true", help="Imprime o relatório completo")
    args = parser.parse_args()
    configure_logging()
    report = DiscoveryOrchestrator().discover()
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Arquitetura: {report.process_architecture} ({report.process_bits} bits)")
        print(f"Modo: {report.mode} | confiança: {report.confidence}%")
        print(f"SIAF: {len(report.siaf_processes)} processo(s)")
        print(
            f"Firebird: {len(report.services)} serviço(s), "
            f"{len(report.firebird_processes)} processo(s)"
        )
        print(f"DLLs: {len(report.client_libraries)} | Bases: {len(report.databases)}")
        print(f"Avisos parciais: {len(report.issues)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
