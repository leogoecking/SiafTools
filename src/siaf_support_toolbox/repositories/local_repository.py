from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from siaf_support_toolbox.core.logging_config import redact_text
from siaf_support_toolbox.database.sqlite_connection import SQLiteDatabase
from siaf_support_toolbox.discovery.models import DatabaseCandidate, DiscoveryReport
from siaf_support_toolbox.repositories.models import (
    ExecutionRecord,
    KnowledgeEntry,
    ManualConnectionProfile,
    QueryTemplate,
    SchemaField,
)


class LocalRepository:
    """Persistência SQLite interna; não contém consultas às bases Firebird."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def record_discovery(self, machine_name: str, report: DiscoveryReport) -> int:
        now = _utc_now()
        endpoint_host, endpoint_port = _endpoint(report)
        siaf_path = next(
            (item.executable for item in report.siaf_processes if item.executable),
            next(
                (item.target_path for item in report.siaf_shortcuts if item.target_path),
                None,
            ),
        )
        service = report.services[0] if report.services else None
        server_path = service.binary_path if service else None
        if not server_path:
            server_path = next(
                (item.executable for item in report.firebird_processes if item.executable), None
            )
        client = next(
            (item for item in report.client_libraries if item.compatible_with_process),
            report.client_libraries[0] if report.client_libraries else None,
        )
        machine_name = _text(machine_name)
        siaf_path = _optional_text(siaf_path)
        server_path = _optional_text(server_path)
        endpoint_host = _optional_text(endpoint_host)

        with self.database.connect() as connection, connection:
            connection.execute(
                "UPDATE detected_environments SET active = 0 WHERE machine_name = ?",
                (machine_name,),
            )
            existing = self._find_environment(
                connection,
                machine_name,
                str(report.mode),
                endpoint_host,
                endpoint_port,
                server_path,
            )
            values = (
                siaf_path,
                _optional_text(service.name if service else None),
                server_path,
                _optional_text(report.firebird_version),
                str(client.architecture) if client else None,
                _optional_text(client.path if client else None),
                _optional_text(client.name if client else None),
                endpoint_host,
                endpoint_port,
                report.confidence,
                now,
                now,
            )
            if existing:
                environment_id = int(existing["id"])
                connection.execute(
                    """
                    UPDATE detected_environments SET
                        siaf_executable_path = ?, firebird_service_name = ?,
                        firebird_server_path = ?, firebird_version = ?,
                        firebird_architecture = ?, client_library_path = ?,
                        client_library_name = ?, detected_host = ?, detected_port = ?,
                        confidence_level = ?, last_scan = ?, last_success = ?, active = 1
                    WHERE id = ?
                    """,
                    (*values, environment_id),
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO detected_environments (
                        machine_name, detection_mode, siaf_executable_path,
                        firebird_service_name, firebird_server_path, firebird_version,
                        firebird_architecture, client_library_path, client_library_name,
                        detected_host, detected_port, confidence_level, last_scan,
                        last_success, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (machine_name, str(report.mode), *values),
                )
                environment_id = int(cursor.lastrowid)

            for candidate in report.databases:
                candidate_ports = _candidate_ports(report, candidate.path, endpoint_port)
                for candidate_port in candidate_ports:
                    self._upsert_database(
                        connection,
                        environment_id,
                        candidate,
                        endpoint_host,
                        candidate_port,
                        now,
                    )
            return environment_id

    @staticmethod
    def _find_environment(
        connection: sqlite3.Connection,
        machine_name: str,
        detection_mode: str,
        host: str | None,
        port: int | None,
        server_path: str | None,
    ) -> sqlite3.Row | None:
        identity_sql = "detected_host = ? COLLATE NOCASE"
        identity_value = host
        if host is None and server_path is not None:
            identity_sql = "firebird_server_path = ? COLLATE NOCASE"
            identity_value = server_path
        elif host is None:
            identity_sql = "detected_host IS NULL AND firebird_server_path IS NULL"

        parameters: list[object] = [machine_name, detection_mode]
        if identity_value is not None:
            parameters.append(identity_value)
        parameters.append(port)
        return connection.execute(
            f"""
            SELECT id FROM detected_environments
            WHERE machine_name = ? AND detection_mode = ?
              AND {identity_sql}
              AND COALESCE(detected_port, -1) = COALESCE(?, -1)
            ORDER BY last_scan DESC LIMIT 1
            """,
            parameters,
        ).fetchone()

    def _upsert_database(
        self,
        connection: sqlite3.Connection,
        environment_id: int,
        candidate: DatabaseCandidate,
        host: str | None,
        port: int | None,
        now: str,
    ) -> None:
        safe_path = _text(candidate.path)
        safe_host = _optional_text(host)
        existing = connection.execute(
            """
            SELECT id FROM discovered_databases
            WHERE environment_id = ? AND database_path = ? COLLATE NOCASE
              AND COALESCE(database_host, '') = COALESCE(?, '')
              AND COALESCE(database_port, -1) = COALESCE(?, -1)
            LIMIT 1
            """,
            (environment_id, safe_path, safe_host, port),
        ).fetchone()
        modified_at = _file_modified_at(candidate.path)
        if existing:
            connection.execute(
                """
                UPDATE discovered_databases SET database_type = ?, file_size = ?,
                    modified_at = ?, confidence_score = ?, last_seen = ?
                WHERE id = ?
                """,
                (
                    _text(candidate.kind_hint),
                    candidate.size_bytes,
                    modified_at,
                    candidate.score,
                    now,
                    existing["id"],
                ),
            )
            return
        connection.execute(
            """
            INSERT INTO discovered_databases (
                environment_id, database_type, database_path, database_host,
                database_port, file_size, modified_at, schema_signature,
                compatibility_status, confidence_score, selected, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'candidate', ?, 0, ?, ?)
            """,
            (
                environment_id,
                _text(candidate.kind_hint),
                safe_path,
                safe_host,
                port,
                candidate.size_bytes,
                modified_at,
                candidate.score,
                now,
                now,
            ),
        )

    def mark_database_validated(
        self,
        database_id: int,
        *,
        schema_signature: str,
        compatibility_status: str,
        selected: bool = False,
    ) -> None:
        if not schema_signature.strip():
            raise ValueError("A assinatura de esquema validada não pode ser vazia")
        if compatibility_status not in {"compatible", "incompatible"}:
            raise ValueError("Status de compatibilidade inválido")
        if selected and compatibility_status != "compatible":
            raise ValueError("Uma base incompatível não pode ser selecionada")
        now = _utc_now()
        with self.database.connect() as connection, connection:
            row = connection.execute(
                "SELECT environment_id FROM discovered_databases WHERE id = ?", (database_id,)
            ).fetchone()
            if row is None:
                raise LookupError(f"Base interna inexistente: {database_id}")
            if selected:
                connection.execute(
                    "UPDATE discovered_databases SET selected = 0 WHERE environment_id = ?",
                    (row["environment_id"],),
                )
            connection.execute(
                """
                UPDATE discovered_databases
                SET schema_signature = ?, compatibility_status = ?, selected = ?, last_seen = ?
                WHERE id = ?
                """,
                (_text(schema_signature), compatibility_status, int(selected), now, database_id),
            )
            connection.execute(
                "UPDATE detected_environments SET last_success = ? WHERE id = ?",
                (now, row["environment_id"]),
            )

    def latest_validated_discovery(self, machine_name: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            environment = connection.execute(
                """
                SELECT * FROM detected_environments AS environment
                WHERE machine_name = ? AND EXISTS (
                    SELECT 1 FROM discovered_databases AS database
                    WHERE database.environment_id = environment.id
                      AND database.schema_signature IS NOT NULL
                      AND database.compatibility_status = 'compatible'
                )
                ORDER BY active DESC, last_success DESC LIMIT 1
                """,
                (_text(machine_name),),
            ).fetchone()
            if environment is None:
                return None
            result = dict(environment)
            result["databases"] = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM discovered_databases
                    WHERE environment_id = ? AND schema_signature IS NOT NULL
                      AND compatibility_status = 'compatible'
                    ORDER BY selected DESC, last_seen DESC
                    """,
                    (environment["id"],),
                ).fetchall()
            ]
            return result

    def active_environment(self, machine_name: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            environment = connection.execute(
                """
                SELECT * FROM detected_environments
                WHERE machine_name = ? AND active = 1
                ORDER BY last_scan DESC LIMIT 1
                """,
                (_text(machine_name),),
            ).fetchone()
            if environment is None:
                return None
            result = dict(environment)
            result["databases"] = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM discovered_databases
                    WHERE environment_id = ? ORDER BY confidence_score DESC, database_path
                    """,
                    (environment["id"],),
                ).fetchall()
            ]
            return result

    def ensure_connection_candidate(
        self,
        environment_id: int,
        *,
        database_path: str,
        database_host: str | None,
        database_port: int | None,
        database_type: str = "DESCONHECIDA",
        confidence_score: int = 50,
    ) -> int:
        now = _utc_now()
        candidate = DatabaseCandidate(
            database_path,
            database_type,
            None,
            max(0, min(confidence_score, 100)),
        )
        with self.database.connect() as connection, connection:
            self._upsert_database(
                connection,
                environment_id,
                candidate,
                database_host,
                database_port,
                now,
            )
            row = connection.execute(
                """
                SELECT id FROM discovered_databases
                WHERE environment_id = ? AND database_path = ? COLLATE NOCASE
                  AND COALESCE(database_host, '') = COALESCE(?, '')
                  AND COALESCE(database_port, -1) = COALESCE(?, -1)
                ORDER BY id DESC LIMIT 1
                """,
                (
                    environment_id,
                    _text(database_path),
                    _optional_text(database_host),
                    database_port,
                ),
            ).fetchone()
            if row is None:  # pragma: no cover - protegido pelo upsert na mesma transação
                raise RuntimeError("O candidato de conexão não pôde ser persistido")
            return int(row["id"])

    def update_environment_firebird_version(
        self,
        environment_id: int,
        firebird_version: str | None,
    ) -> None:
        if not firebird_version:
            return
        with self.database.connect() as connection, connection:
            connection.execute(
                "UPDATE detected_environments SET firebird_version = ? WHERE id = ?",
                (_text(firebird_version), environment_id),
            )

    def save_manual_profile(self, profile: ManualConnectionProfile) -> int:
        now = _utc_now()
        values = (
            _text(profile.name),
            profile.environment_id,
            _optional_text(profile.host),
            profile.port,
            _text(profile.database_path),
            _optional_text(profile.database_type),
            _optional_text(profile.username),
            _optional_text(profile.charset),
            _optional_text(profile.fbclient_path),
            int(profile.favorite),
            int(profile.active),
        )
        with self.database.connect() as connection, connection:
            if profile.id is not None:
                cursor = connection.execute(
                    """
                    UPDATE connection_profiles SET name = ?, environment_id = ?, host = ?,
                        port = ?, database_path = ?, database_type = ?, username = ?,
                        charset = ?, fbclient_path = ?, favorite = ?, active = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (*values, now, profile.id),
                )
                if cursor.rowcount == 0:
                    raise LookupError(f"Perfil interno inexistente: {profile.id}")
                return profile.id
            cursor = connection.execute(
                """
                INSERT INTO connection_profiles (
                    name, environment_id, host, port, database_path, database_type,
                    username, charset, fbclient_path, favorite, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*values, now, now),
            )
            return int(cursor.lastrowid)

    def list_active_profiles(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM connection_profiles
                    WHERE active = 1 ORDER BY favorite DESC, name
                    """
                ).fetchall()
            ]

    def upsert_query_template(self, template: QueryTemplate) -> int:
        values = (
            _text(template.module),
            _text(template.description),
            _text(template.sql_template),
            _json(template.required_tables),
            _json(template.required_fields),
            _json(template.parameters_schema),
            int(template.read_only),
            _text(template.risk_level),
            int(template.enabled),
            _optional_text(template.source_reference),
        )
        with self.database.connect() as connection, connection:
            existing = connection.execute(
                "SELECT id FROM query_templates WHERE name = ? AND version = ?",
                (_text(template.name), _text(template.version)),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE query_templates SET module = ?, description = ?, sql_template = ?,
                        required_tables = ?, required_fields = ?, parameters_schema = ?,
                        read_only = ?, risk_level = ?, enabled = ?, source_reference = ?
                    WHERE id = ?
                    """,
                    (*values, existing["id"]),
                )
                return int(existing["id"])
            cursor = connection.execute(
                """
                INSERT INTO query_templates (
                    name, module, description, sql_template, required_tables, required_fields,
                    parameters_schema, read_only, risk_level, enabled, version, source_reference
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (_text(template.name), *values[:-1], _text(template.version), values[-1]),
            )
            return int(cursor.lastrowid)

    def add_execution_history(self, record: ExecutionRecord) -> int:
        with self.database.connect() as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO execution_history (
                    environment_id, database_id, action_name, action_type, started_at,
                    finished_at, success, records_processed, duration_ms, error_code,
                    error_message, output_file, app_version, windows_user
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.environment_id,
                    record.database_id,
                    _text(record.action_name),
                    _text(record.action_type),
                    _text(record.started_at),
                    _optional_text(record.finished_at),
                    int(record.success),
                    record.records_processed,
                    record.duration_ms,
                    _optional_text(record.error_code),
                    _optional_text(record.error_message),
                    _optional_text(record.output_file),
                    _text(record.app_version),
                    _optional_text(record.windows_user),
                ),
            )
            return int(cursor.lastrowid)

    def replace_schema_cache(self, database_id: int, fields: list[SchemaField]) -> None:
        with self.database.connect() as connection, connection:
            connection.execute("DELETE FROM schema_cache WHERE database_id = ?", (database_id,))
            connection.executemany(
                """
                INSERT INTO schema_cache (
                    database_id, relation_name, field_name, field_type, field_length,
                    field_scale, nullable, primary_key, index_names, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        database_id,
                        _text(field.relation_name),
                        _text(field.field_name),
                        _text(field.field_type),
                        field.field_length,
                        field.field_scale,
                        int(field.nullable),
                        int(field.primary_key),
                        _json(field.index_names),
                        _text(field.checked_at) if field.checked_at else _utc_now(),
                    )
                    for field in fields
                ],
            )

    def upsert_knowledge_entry(self, entry: KnowledgeEntry) -> int:
        values = (
            _json(entry.symptoms),
            _json(entry.causes),
            _json(entry.solution),
            _optional_text(entry.system_path),
            _json(entry.validations),
            _optional_text(entry.observations),
            _json(entry.keywords),
            entry.confidence_level,
            _optional_text(entry.source),
            int(entry.active),
        )
        with self.database.connect() as connection, connection:
            existing = connection.execute(
                """
                SELECT id FROM knowledge_entries
                WHERE category = ? AND module = ? AND problem = ? AND version = ?
                """,
                (
                    _text(entry.category),
                    _text(entry.module),
                    _text(entry.problem),
                    _text(entry.version),
                ),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE knowledge_entries SET symptoms_json = ?, causes_json = ?,
                        solution_json = ?, system_path = ?, validations_json = ?,
                        observations = ?, keywords_json = ?, confidence_level = ?,
                        source = ?, active = ? WHERE id = ?
                    """,
                    (*values, existing["id"]),
                )
                return int(existing["id"])
            cursor = connection.execute(
                """
                INSERT INTO knowledge_entries (
                    category, module, problem, symptoms_json, causes_json, solution_json,
                    system_path, validations_json, observations, keywords_json,
                    confidence_level, source, version, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _text(entry.category),
                    _text(entry.module),
                    _text(entry.problem),
                    *values[:-1],
                    _text(entry.version),
                    values[-1],
                ),
            )
            return int(cursor.lastrowid)


def _endpoint(report: DiscoveryReport) -> tuple[str | None, int | None]:
    ports = set(report.detected_ports)
    remote = next(
        (
            item
            for item in report.network_connections
            if not _is_local_host(item.remote_address) and (not ports or item.remote_port in ports)
        ),
        None,
    )
    if remote:
        return remote.remote_address, remote.remote_port
    reference = next(
        (
            item
            for item in report.connection_references
            if item.host and not _is_local_host(item.host)
        ),
        None,
    )
    if reference:
        return reference.host, reference.port
    port = report.detected_ports[0] if report.detected_ports else None
    return None, port


def _candidate_ports(
    report: DiscoveryReport,
    database_path: str,
    fallback_port: int | None,
) -> list[int | None]:
    path_key = _path_key(database_path)
    ports = {
        configuration.port
        for configuration in report.firebird_configurations
        if any(_path_key(alias.database) == path_key for alias in configuration.aliases)
    }
    return sorted(ports) if ports else [fallback_port]


def _path_key(value: str) -> str:
    return value.replace("/", "\\").casefold()


def _is_local_host(host: str) -> bool:
    return host.casefold() in {"", "0.0.0.0", "127.0.0.1", "::", "::1", "localhost"}


def _file_modified_at(path: str) -> str | None:
    try:
        return datetime.fromtimestamp(Path(path).stat().st_mtime, UTC).isoformat(timespec="seconds")
    except OSError:
        return None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json(value: object) -> str:
    return json.dumps(_redact_payload(value), ensure_ascii=False, separators=(",", ":"))


def _redact_payload(value: object) -> object:
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, dict):
        return {_text(str(key)): _redact_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_payload(item) for item in value]
    return value


def _text(value: str) -> str:
    return redact_text(value)


def _optional_text(value: str | None) -> str | None:
    return _text(value) if value is not None else None
