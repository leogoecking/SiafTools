from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from siaf_support_toolbox.database.firebird_probe import probe_read_only  # noqa: E402
from siaf_support_toolbox.discovery.discovery_orchestrator import (  # noqa: E402
    DiscoveryOrchestrator,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida em modo somente leitura as bases descobertas automaticamente"
    )
    parser.add_argument("--usuario", help="Usuário Firebird autorizado")
    parser.add_argument(
        "--pausar",
        action="store_true",
        help="Mantém a janela aberta ao finalizar",
    )
    args = parser.parse_args()

    exit_code = 1
    try:
        exit_code = run_probe(args.usuario)
    except (KeyboardInterrupt, EOFError):
        print("\nValidação cancelada pelo usuário.")
        exit_code = 130
    except Exception as exc:
        print(f"Erro inesperado: {type(exc).__name__}: {exc}", file=sys.stderr)
        exit_code = 5
    finally:
        if args.pausar:
            input("\nPressione ENTER para fechar esta janela...")
    return exit_code


def run_probe(username_argument: str | None) -> int:
    report = DiscoveryOrchestrator().discover()
    libraries = [item for item in report.client_libraries if item.compatible_with_process]
    if not libraries:
        print("Nenhuma biblioteca Firebird compatível foi descoberta.", file=sys.stderr)
        return 2
    if not report.databases:
        print("Nenhuma base candidata foi descoberta.", file=sys.stderr)
        return 3

    username = username_argument or input("Usuário Firebird autorizado: ").strip()
    if not username:
        print("O usuário Firebird é obrigatório.", file=sys.stderr)
        return 4
    password = getpass.getpass("Senha Firebird (não será salva): ")
    results: list[dict[str, object]] = []

    for candidate in report.databases:
        result = probe_read_only(
            dsn=f"localhost:{candidate.path}",
            username=username,
            password=password,
            client_library=libraries[0].path,
        )
        classification = result.classification
        item = {
            "database_path": candidate.path,
            "success": result.success,
            "database_type": str(classification.database_type) if classification else None,
            "confidence": classification.confidence if classification else None,
            "current_timestamp": result.current_timestamp,
            "error_code": result.error_code,
            "message": result.message,
        }
        results.append(item)
        if result.success and classification:
            print(
                f"OK | {candidate.path} | {classification.database_type} | "
                f"confiança {classification.confidence}%"
            )
        else:
            print(f"FALHA | {candidate.path} | {result.error_code} | {result.message}")

    password = ""  # reduz o tempo de vida da referência; Python não garante limpeza da memória.
    output_path = write_report(results)
    print(f"\nRelatório salvo em: {output_path}")
    return 1 if any(not bool(item["success"]) for item in results) else 0


def write_report(results: list[dict[str, object]]) -> Path:
    exports = PROJECT_ROOT / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = exports / f"validacao_firebird_{timestamp}.json"
    payload = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "somente_leitura",
        "credentials_persisted": False,
        "results": results,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    raise SystemExit(main())
