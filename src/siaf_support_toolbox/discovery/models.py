from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class MachineMode(StrEnum):
    LOCAL_SERVER = "servidor_local"
    TERMINAL = "terminal"
    ASSISTED = "assistido"


class Architecture(StrEnum):
    X86 = "x86"
    X64 = "x64"
    ARM = "arm"
    UNKNOWN = "desconhecida"


@dataclass(frozen=True, slots=True)
class Evidence:
    source: str
    detail: str
    weight: int = 0


@dataclass(frozen=True, slots=True)
class DetectionIssue:
    detector: str
    message: str
    code: str = "partial_failure"


@dataclass(frozen=True, slots=True)
class ProcessFinding:
    pid: int
    name: str
    executable: str | None = None


@dataclass(frozen=True, slots=True)
class ShortcutFinding:
    path: str
    target_path: str | None = None
    working_directory: str | None = None


@dataclass(frozen=True, slots=True)
class ServiceFinding:
    name: str
    display_name: str
    status: str
    binary_path: str | None = None


@dataclass(frozen=True, slots=True)
class RegistryFinding:
    key: str
    name: str
    value: str
    view: str


@dataclass(frozen=True, slots=True)
class ClientLibraryFinding:
    path: str
    name: str
    architecture: Architecture
    compatible_with_process: bool


@dataclass(frozen=True, slots=True)
class DatabaseCandidate:
    path: str
    kind_hint: str
    size_bytes: int | None
    score: int
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True, slots=True)
class NetworkFinding:
    pid: int
    local_address: str
    local_port: int
    remote_address: str
    remote_port: int


@dataclass(frozen=True, slots=True)
class AliasFinding:
    alias: str
    database: str
    source_file: str


@dataclass(frozen=True, slots=True)
class FirebirdConfigurationFinding:
    root: str
    port: int
    config_file: str | None = None
    aliases: tuple[AliasFinding, ...] = ()


@dataclass(frozen=True, slots=True)
class ConnectionReferenceFinding:
    host: str | None
    port: int
    database: str
    source_file: str


@dataclass(slots=True)
class DiscoveryReport:
    process_architecture: Architecture = Architecture.UNKNOWN
    process_bits: int = 0
    is_admin: bool = False
    firebird_version: str | None = None
    siaf_processes: list[ProcessFinding] = field(default_factory=list)
    siaf_shortcuts: list[ShortcutFinding] = field(default_factory=list)
    firebird_processes: list[ProcessFinding] = field(default_factory=list)
    services: list[ServiceFinding] = field(default_factory=list)
    registry: list[RegistryFinding] = field(default_factory=list)
    client_libraries: list[ClientLibraryFinding] = field(default_factory=list)
    databases: list[DatabaseCandidate] = field(default_factory=list)
    network_connections: list[NetworkFinding] = field(default_factory=list)
    aliases: list[AliasFinding] = field(default_factory=list)
    firebird_configurations: list[FirebirdConfigurationFinding] = field(default_factory=list)
    connection_references: list[ConnectionReferenceFinding] = field(default_factory=list)
    detected_ports: list[int] = field(default_factory=lambda: [3050])
    network_candidate_ports: list[int] = field(default_factory=list)
    mode: MachineMode = MachineMode.ASSISTED
    confidence: int = 0
    evidence: list[Evidence] = field(default_factory=list)
    issues: list[DetectionIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if isinstance(value, (StrEnum, Path)):
        return str(value)
    return value
