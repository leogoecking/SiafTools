from __future__ import annotations

import ipaddress

from siaf_support_toolbox.discovery.models import (
    ConnectionReferenceFinding,
    NetworkFinding,
)


def correlated_connections_for_reference(
    reference: ConnectionReferenceFinding,
    references: list[ConnectionReferenceFinding],
    connections: list[NetworkFinding],
) -> tuple[NetworkFinding, ...]:
    if not reference.host or is_local_address(reference.host):
        return ()
    remote_connections = tuple(
        item for item in connections if not is_local_address(item.remote_address)
    )
    direct = tuple(
        item
        for item in remote_connections
        if item.remote_address.casefold() == reference.host.casefold()
    )
    if direct:
        return direct
    reference_hosts = {
        item.host.casefold() for item in references if item.host and not is_local_address(item.host)
    }
    connection_hosts = {item.remote_address.casefold() for item in remote_connections}
    if len(reference_hosts) == 1 and len(connection_hosts) == 1:
        return remote_connections
    return ()


def correlated_firebird_ports(
    references: list[ConnectionReferenceFinding],
    connections: list[NetworkFinding],
) -> set[int]:
    return {
        connection.remote_port
        for reference in references
        for connection in correlated_connections_for_reference(reference, references, connections)
    }


def is_local_address(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
        return parsed.is_loopback or parsed.is_unspecified
    except ValueError:
        return address.casefold() in {"localhost", "::1"}
