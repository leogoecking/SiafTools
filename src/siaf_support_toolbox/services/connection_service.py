from __future__ import annotations

import getpass
import hashlib
import platform
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from siaf_support_toolbox.core.constants import DEFAULT_FIREBIRD_PORT
from siaf_support_toolbox.core.version import __version__
from siaf_support_toolbox.database.firebird_probe import (
    FirebirdProbeResult,
    probe_read_only,
    runtime_compatibility_issue,
)
from siaf_support_toolbox.discovery.firebird_client_detector import rank_client_libraries
from siaf_support_toolbox.discovery.models import DiscoveryReport, MachineMode
from siaf_support_toolbox.discovery.network_candidates import (
    correlated_connections_for_reference,
)
from siaf_support_toolbox.discovery.siaf_installation_grouper import (
    installation_for_database,
)
from siaf_support_toolbox.repositories.local_repository import LocalRepository
from siaf_support_toolbox.repositories.models import ExecutionRecord, ManualConnectionProfile


@dataclass(slots=True)
class SessionCredentials:
    username: str
    password: str = field(repr=False)
    charset: str = "WIN1252"

    def clear(self) -> None:
        self.password = ""


@dataclass(frozen=True, slots=True)
class ManualConnectionInput:
    database_path: str
    client_library: str
    host: str = "localhost"
    port: int = DEFAULT_FIREBIRD_PORT
    database_type: str = "DESCONHECIDA"
    profile_name: str = "Fallback manual"
    save_profile: bool = False


@dataclass(frozen=True, slots=True)
class ConnectionTarget:
    environment_id: int
    database_id: int | None
    host: str
    port: int
    database_path: str
    database_type_hint: str
    client_library: str
    source: str
    confidence: int
    manual: bool = False
    fallback_client_libraries: tuple[str, ...] = ()
    installation_root: str | None = None

    @property
    def dsn(self) -> str:
        endpoint = self.host if self.port == DEFAULT_FIREBIRD_PORT else f"{self.host}/{self.port}"
        return f"{endpoint}:{self.database_path}"


@dataclass(frozen=True, slots=True)
class ConnectionPlan:
    targets: tuple[ConnectionTarget, ...]
    issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConnectionValidation:
    target: ConnectionTarget
    result: FirebirdProbeResult
    database_id: int | None
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ConnectionSummary:
    validations: tuple[ConnectionValidation, ...]

    @property
    def successful(self) -> tuple[ConnectionValidation, ...]:
        return tuple(item for item in self.validations if item.result.success)


class FirebirdConnectionService:
    def __init__(
        self,
        repository: LocalRepository,
        *,
        machine_name: str | None = None,
        probe: Callable[..., FirebirdProbeResult] = probe_read_only,
    ) -> None:
        self.repository = repository
        self.machine_name = machine_name or platform.node() or "desconhecido"
        self._probe = probe

    def build_plan(
        self,
        report: DiscoveryReport,
        manual: ManualConnectionInput | None = None,
        *,
        installation_root: str | None = None,
    ) -> ConnectionPlan:
        environment = self.repository.active_environment(self.machine_name)
        if environment is None:
            return ConnectionPlan((), ("A descoberta atual ainda não foi persistida.",))

        compatible_libraries = [
            item.path for item in rank_client_libraries(report.client_libraries) if item.ready
        ]
        library = manual.client_library if manual else next(iter(compatible_libraries), None)
        if not library:
            library = environment.get("client_library_path")
        if not library:
            return ConnectionPlan(
                (),
                ("Nenhuma biblioteca Firebird x86 compatível foi encontrada.",),
            )

        targets: list[ConnectionTarget] = []
        fallback_libraries = (
            ()
            if manual
            else tuple(
                item
                for item in compatible_libraries
                if item.casefold() != str(library).casefold()
            )
        )
        selected_installation = next(
            (
                item
                for item in report.installations
                if _path_key(item.root) == _path_key(installation_root or "")
            ),
            None,
        )
        selected_database_paths = (
            {_path_key(item) for item in selected_installation.database_paths}
            if selected_installation
            else None
        )
        port = int(environment.get("detected_port") or DEFAULT_FIREBIRD_PORT)
        host = str(environment.get("detected_host") or "localhost")
        databases_by_endpoint = {
            (
                _path_key(str(item["database_path"])),
                int(item.get("database_port") or port),
            ): item
            for item in environment["databases"]
        }
        ports_by_database: dict[str, set[int]] = {}
        configured_aliases: set[tuple[str, str, str]] = set()
        for configuration in report.firebird_configurations:
            for alias in configuration.aliases:
                ports_by_database.setdefault(_path_key(alias.database), set()).add(
                    configuration.port
                )
                configured_aliases.add(_alias_key(alias.alias, alias.database, alias.source_file))

        if report.mode != MachineMode.TERMINAL:
            for candidate in report.databases:
                if (
                    selected_database_paths is not None
                    and _path_key(candidate.path) not in selected_database_paths
                ):
                    continue
                candidate_ports = ports_by_database.get(_path_key(candidate.path), {port})
                for candidate_port in sorted(candidate_ports):
                    stored = databases_by_endpoint.get((_path_key(candidate.path), candidate_port))
                    targets.append(
                        ConnectionTarget(
                            int(environment["id"]),
                            int(stored["id"]) if stored else None,
                            "localhost",
                            candidate_port,
                            candidate.path,
                            candidate.kind_hint,
                            library,
                            (
                                "descoberta_validada"
                                if stored and stored.get("compatibility_status") == "compatible"
                                else "descoberta_local"
                            ),
                            max(candidate.score, int(stored.get("confidence_score") or 0))
                            if stored
                            else candidate.score,
                        )
                    )

        alias_host = host if report.mode == MachineMode.TERMINAL else "localhost"
        for configuration in report.firebird_configurations:
            for alias in configuration.aliases:
                if selected_installation and not _belongs_to_installation(
                    alias.database,
                    alias.source_file,
                    selected_installation.root,
                    selected_database_paths or set(),
                ):
                    continue
                targets.append(
                    ConnectionTarget(
                        int(environment["id"]),
                        None,
                        alias_host,
                        configuration.port,
                        alias.alias,
                        "DESCONHECIDA",
                        library,
                        "alias_firebird_instancia",
                        75,
                    )
                )
        for alias in report.aliases:
            if _alias_key(alias.alias, alias.database, alias.source_file) in configured_aliases:
                continue
            if selected_installation and not _belongs_to_installation(
                alias.database,
                alias.source_file,
                selected_installation.root,
                selected_database_paths or set(),
            ):
                continue
            targets.append(
                ConnectionTarget(
                    int(environment["id"]),
                    None,
                    alias_host,
                    port,
                    alias.alias,
                    "DESCONHECIDA",
                    library,
                    "alias_firebird",
                    70,
                )
            )

        for reference in report.connection_references:
            if selected_installation and not _path_is_within(
                reference.source_file, selected_installation.root
            ):
                continue
            reference_host = reference.host or (
                host if report.mode == MachineMode.TERMINAL else "localhost"
            )
            endpoints = {(reference_host, reference.port, "configuracao_siaf")}
            endpoints.update(
                (item.remote_address, item.remote_port, "configuracao_siaf_tcp")
                for item in correlated_connections_for_reference(
                    reference,
                    report.connection_references,
                    report.network_connections,
                )
            )
            for endpoint_host, endpoint_port, source in endpoints:
                targets.append(
                    ConnectionTarget(
                        int(environment["id"]),
                        None,
                        endpoint_host,
                        endpoint_port,
                        reference.database,
                        "DESCONHECIDA",
                        library,
                        source,
                        90 if source == "configuracao_siaf_tcp" else 80 if reference.host else 60,
                    )
                )

        historical = self.repository.latest_validated_discovery(self.machine_name)
        if historical and not targets and selected_installation is None:
            historical_host = str(historical.get("detected_host") or "localhost")
            historical_port = int(historical.get("detected_port") or DEFAULT_FIREBIRD_PORT)
            historical_library = str(historical.get("client_library_path") or library)
            for database in historical["databases"]:
                targets.append(
                    ConnectionTarget(
                        int(historical["id"]),
                        int(database["id"]),
                        str(database.get("database_host") or historical_host),
                        int(database.get("database_port") or historical_port),
                        str(database["database_path"]),
                        str(database.get("database_type") or "DESCONHECIDA"),
                        historical_library,
                        "historico_validado",
                        int(database.get("confidence_score") or 80),
                    )
                )

        if manual:
            targets = [
                ConnectionTarget(
                    int(environment["id"]),
                    None,
                    manual.host.strip() or "localhost",
                    manual.port,
                    manual.database_path,
                    manual.database_type,
                    manual.client_library,
                    "fallback_manual",
                    50,
                    True,
                )
            ]

        targets = [
            replace(
                target,
                fallback_client_libraries=fallback_libraries if not target.manual else (),
                installation_root=(
                    selected_installation.root
                    if selected_installation
                    else installation_for_database(target.database_path, report.installations)
                ),
            )
            for target in targets
        ]
        unique: dict[tuple[str, int, str, str], ConnectionTarget] = {}
        for target in targets:
            key = (
                target.host.casefold(),
                target.port,
                target.database_path.casefold(),
                target.client_library.casefold(),
            )
            existing = unique.get(key)
            if existing is None or target.confidence > existing.confidence:
                unique[key] = target
        ordered = tuple(sorted(unique.values(), key=lambda item: (-item.confidence, item.source)))
        issues = () if ordered else ("Nenhuma base fundamentada está disponível para conexão.",)
        return ConnectionPlan(ordered, issues)

    def validate(
        self,
        plan: ConnectionPlan,
        credentials: SessionCredentials,
        manual: ManualConnectionInput | None = None,
    ) -> ConnectionSummary:
        validations: list[ConnectionValidation] = []
        selected = False
        try:
            for target in plan.targets:
                started_at = datetime.now(UTC)
                started = time.monotonic()
                target, result = self._probe_with_fallback(target, credentials)
                if result.success:
                    compatibility_issue = runtime_compatibility_issue(
                        result.server_version, result.ods_version
                    )
                    if compatibility_issue is not None:
                        result = replace(
                            result,
                            success=False,
                            error_code=compatibility_issue[0],
                            message=compatibility_issue[1],
                        )
                duration_ms = int((time.monotonic() - started) * 1000)
                database_id = target.database_id
                if result.classification is not None:
                    if database_id is None:
                        storage_host = (
                            None if target.host.casefold() == "localhost" else target.host
                        )
                        database_id = self.repository.ensure_connection_candidate(
                            target.environment_id,
                            database_path=target.database_path,
                            database_host=storage_host,
                            database_port=target.port,
                            database_type=str(result.classification.database_type),
                            confidence_score=result.classification.confidence,
                        )
                    signature = _schema_signature(result)
                    compatible = result.success and result.classification.is_accepted
                    self.repository.mark_database_validated(
                        database_id,
                        schema_signature=signature,
                        compatibility_status="compatible" if compatible else "incompatible",
                        selected=compatible and not selected,
                    )
                    selected = selected or compatible
                self.repository.update_environment_firebird_version(
                    target.environment_id, result.server_version
                )
                self.repository.add_execution_history(
                    ExecutionRecord(
                        environment_id=target.environment_id,
                        database_id=database_id,
                        action_name="Validação de conexão Firebird",
                        action_type="connection_validation",
                        started_at=started_at.isoformat(timespec="seconds"),
                        finished_at=datetime.now(UTC).isoformat(timespec="seconds"),
                        success=result.success,
                        records_processed=1 if result.success else 0,
                        duration_ms=duration_ms,
                        error_code=result.error_code,
                        error_message=result.message,
                        app_version=__version__,
                        windows_user=getpass.getuser(),
                    )
                )
                validations.append(ConnectionValidation(target, result, database_id, duration_ms))

            if (
                manual
                and manual.save_profile
                and any(item.result.success and item.target.manual for item in validations)
            ):
                self.repository.save_manual_profile(
                    ManualConnectionProfile(
                        name=manual.profile_name,
                        environment_id=validations[0].target.environment_id,
                        host=manual.host,
                        port=manual.port,
                        database_path=manual.database_path,
                        database_type=manual.database_type,
                        username=credentials.username,
                        charset=credentials.charset,
                        fbclient_path=manual.client_library,
                    )
                )
            return ConnectionSummary(tuple(validations))
        finally:
            credentials.clear()

    def _probe_with_fallback(
        self,
        target: ConnectionTarget,
        credentials: SessionCredentials,
    ) -> tuple[ConnectionTarget, FirebirdProbeResult]:
        candidates = (target.client_library, *target.fallback_client_libraries)
        current_target = target
        result: FirebirdProbeResult | None = None
        for library in candidates:
            current_target = replace(
                target,
                client_library=library,
                fallback_client_libraries=(),
            )
            result = self._probe(
                dsn=current_target.dsn,
                username=credentials.username,
                password=credentials.password,
                client_library=current_target.client_library,
                charset=credentials.charset,
                host=current_target.host,
                port=current_target.port,
                connect_timeout=3.0,
            )
            if result.success or result.error_code not in {
                "client_library_incompatible",
                "client_library_load_failed",
            }:
                break
        if result is None:
            raise RuntimeError("O plano de conexão não possui biblioteca cliente")
        return current_target, result


def _schema_signature(result: FirebirdProbeResult) -> str:
    classification = result.classification
    if classification is None:
        raise ValueError("A classificação é necessária para gerar a assinatura")
    payload = "|".join(
        [str(classification.database_type), *sorted(classification.matched_tables)]
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _path_key(value: str) -> str:
    return value.replace("/", "\\").casefold()


def _alias_key(alias: str, database: str, source_file: str) -> tuple[str, str, str]:
    return alias.casefold(), _path_key(database), _path_key(source_file)


def _path_is_within(path: str, root: str) -> bool:
    normalized_path = _path_key(path).rstrip("\\")
    normalized_root = _path_key(root).rstrip("\\")
    return normalized_path == normalized_root or normalized_path.startswith(
        normalized_root + "\\"
    )


def _belongs_to_installation(
    database: str,
    source_file: str,
    root: str,
    database_paths: set[str],
) -> bool:
    return _path_key(database) in database_paths or _path_is_within(source_file, root)
