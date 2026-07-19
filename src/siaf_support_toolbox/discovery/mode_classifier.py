from __future__ import annotations

import ipaddress

from siaf_support_toolbox.discovery.models import DiscoveryReport, Evidence, MachineMode


def classify_machine(report: DiscoveryReport) -> tuple[MachineMode, int, list[Evidence]]:
    server_score = 0
    terminal_score = 0
    evidence: list[Evidence] = []

    if report.services:
        server_score += 35
        evidence.append(Evidence("servico_firebird", f"{len(report.services)} encontrado(s)", 35))
    if report.firebird_processes:
        server_score += 25
        evidence.append(
            Evidence("processo_firebird", f"{len(report.firebird_processes)} encontrado(s)", 25)
        )
    if report.databases:
        server_score += 20
        evidence.append(Evidence("bases_locais", f"{len(report.databases)} candidata(s)", 20))
    has_siaf = bool(
        report.siaf_processes
        or report.siaf_shortcuts
        or any(item.source in {"processo_siaf", "busca_limitada_siaf"} for item in report.evidence)
    )
    if has_siaf:
        terminal_score += 25
        evidence.append(
            Evidence(
                "siaf_localizado",
                (
                    f"{len(report.siaf_processes)} processo(s), "
                    f"{len(report.siaf_shortcuts)} atalho(s)"
                ),
                25,
            )
        )

    firebird_ports = set(report.detected_ports or [3050])
    remote_firebird_connections = [
        item
        for item in report.network_connections
        if not _is_local_address(item.remote_address) and item.remote_port in firebird_ports
    ]
    if report.siaf_processes and remote_firebird_connections:
        terminal_score += 45
        evidence.append(
            Evidence(
                "conexao_remota_firebird",
                f"{len(remote_firebird_connections)} estabelecida(s)",
                45,
            )
        )

    remote_configuration = [
        item
        for item in report.connection_references
        if item.host and not _is_local_address(item.host)
    ]
    if has_siaf and remote_configuration:
        terminal_score += 35
        evidence.append(
            Evidence(
                "configuracao_remota_firebird",
                f"{len(remote_configuration)} referência(s)",
                35,
            )
        )

    has_local_firebird = bool(report.services or report.firebird_processes)
    has_local_databases = bool(report.databases)
    if has_local_firebird and has_local_databases and server_score >= terminal_score:
        return MachineMode.LOCAL_SERVER, min(server_score, 100), evidence
    if terminal_score >= 45 and not has_local_databases:
        return MachineMode.TERMINAL, min(terminal_score, 100), evidence
    return MachineMode.ASSISTED, min(max(server_score, terminal_score, 10), 40), evidence


def _is_local_address(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
        return parsed.is_loopback or parsed.is_unspecified
    except ValueError:
        return address.casefold() in {"localhost", "::1"}
