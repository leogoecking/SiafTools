from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


MIGRATIONS = (
    Migration(
        1,
        "initial_local_store",
        (
            """
            CREATE TABLE IF NOT EXISTS detected_environments (
                id INTEGER PRIMARY KEY,
                machine_name TEXT NOT NULL,
                detection_mode TEXT NOT NULL,
                siaf_executable_path TEXT,
                firebird_service_name TEXT,
                firebird_server_path TEXT,
                firebird_version TEXT,
                firebird_architecture TEXT,
                client_library_path TEXT,
                client_library_name TEXT,
                detected_host TEXT,
                detected_port INTEGER,
                confidence_level INTEGER NOT NULL DEFAULT 0,
                last_scan TEXT NOT NULL,
                last_success TEXT,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS discovered_databases (
                id INTEGER PRIMARY KEY,
                environment_id INTEGER NOT NULL,
                database_type TEXT,
                database_path TEXT NOT NULL,
                database_host TEXT,
                database_port INTEGER,
                file_size INTEGER,
                modified_at TEXT,
                schema_signature TEXT,
                compatibility_status TEXT NOT NULL DEFAULT 'candidate',
                confidence_score INTEGER NOT NULL DEFAULT 0,
                selected INTEGER NOT NULL DEFAULT 0 CHECK (selected IN (0, 1)),
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                FOREIGN KEY (environment_id) REFERENCES detected_environments(id)
                    ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS connection_profiles (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                environment_id INTEGER,
                host TEXT,
                port INTEGER,
                database_path TEXT NOT NULL,
                database_type TEXT,
                username TEXT,
                charset TEXT,
                fbclient_path TEXT,
                favorite INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1)),
                last_connection TEXT,
                last_success TEXT,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (environment_id) REFERENCES detected_environments(id)
                    ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS query_templates (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                module TEXT NOT NULL,
                description TEXT,
                sql_template TEXT NOT NULL,
                required_tables TEXT NOT NULL,
                required_fields TEXT NOT NULL,
                parameters_schema TEXT NOT NULL,
                read_only INTEGER NOT NULL DEFAULT 1 CHECK (read_only IN (0, 1)),
                risk_level TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                version TEXT NOT NULL,
                source_reference TEXT,
                UNIQUE (name, version)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS execution_history (
                id INTEGER PRIMARY KEY,
                environment_id INTEGER,
                database_id INTEGER,
                action_name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                success INTEGER NOT NULL CHECK (success IN (0, 1)),
                records_processed INTEGER NOT NULL DEFAULT 0,
                duration_ms INTEGER,
                error_code TEXT,
                error_message TEXT,
                output_file TEXT,
                app_version TEXT NOT NULL,
                windows_user TEXT,
                FOREIGN KEY (environment_id) REFERENCES detected_environments(id)
                    ON DELETE SET NULL,
                FOREIGN KEY (database_id) REFERENCES discovered_databases(id)
                    ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS operation_audit (
                id INTEGER PRIMARY KEY,
                environment_id INTEGER,
                database_id INTEGER,
                operation_name TEXT NOT NULL,
                database_path_hash TEXT NOT NULL,
                preview_hash TEXT NOT NULL,
                execution_sql_hash TEXT NOT NULL,
                affected_records INTEGER,
                confirmation_text TEXT,
                backup_confirmed INTEGER NOT NULL DEFAULT 0
                    CHECK (backup_confirmed IN (0, 1)),
                backup_path TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                success INTEGER NOT NULL CHECK (success IN (0, 1)),
                rollback_executed INTEGER NOT NULL DEFAULT 0
                    CHECK (rollback_executed IN (0, 1)),
                validation_result TEXT,
                windows_user TEXT,
                FOREIGN KEY (environment_id) REFERENCES detected_environments(id)
                    ON DELETE SET NULL,
                FOREIGN KEY (database_id) REFERENCES discovered_databases(id)
                    ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS schema_cache (
                id INTEGER PRIMARY KEY,
                database_id INTEGER NOT NULL,
                relation_name TEXT NOT NULL,
                field_name TEXT NOT NULL,
                field_type TEXT NOT NULL,
                field_length INTEGER,
                field_scale INTEGER,
                nullable INTEGER NOT NULL CHECK (nullable IN (0, 1)),
                primary_key INTEGER NOT NULL DEFAULT 0 CHECK (primary_key IN (0, 1)),
                index_names TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                FOREIGN KEY (database_id) REFERENCES discovered_databases(id)
                    ON DELETE CASCADE,
                UNIQUE (database_id, relation_name, field_name)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                module TEXT NOT NULL,
                problem TEXT NOT NULL,
                symptoms_json TEXT NOT NULL,
                causes_json TEXT NOT NULL,
                solution_json TEXT NOT NULL,
                system_path TEXT,
                validations_json TEXT NOT NULL,
                observations TEXT,
                keywords_json TEXT NOT NULL,
                confidence_level INTEGER NOT NULL DEFAULT 0,
                source TEXT,
                version TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                UNIQUE (category, module, problem, version)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_environments_machine
            ON detected_environments(machine_name, active)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_databases_environment
            ON discovered_databases(environment_id, last_seen)
            """,
            "CREATE INDEX IF NOT EXISTS idx_history_started ON execution_history(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_knowledge_module ON knowledge_entries(module, active)",
        ),
    ),
    Migration(
        2,
        "enforce_database_compatibility",
        (
            """
            UPDATE discovered_databases
            SET selected = 0
            WHERE compatibility_status <> 'compatible'
               OR schema_signature IS NULL
               OR TRIM(schema_signature) = ''
            """,
            """
            UPDATE discovered_databases
            SET compatibility_status = 'candidate'
            WHERE compatibility_status NOT IN ('candidate', 'compatible', 'incompatible')
            """,
            """
            CREATE TRIGGER IF NOT EXISTS validate_database_compatibility_insert
            BEFORE INSERT ON discovered_databases
            WHEN NEW.compatibility_status NOT IN ('candidate', 'compatible', 'incompatible')
            BEGIN
                SELECT RAISE(ABORT, 'invalid database compatibility status');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS validate_database_compatibility_update
            BEFORE UPDATE OF compatibility_status ON discovered_databases
            WHEN NEW.compatibility_status NOT IN ('candidate', 'compatible', 'incompatible')
            BEGIN
                SELECT RAISE(ABORT, 'invalid database compatibility status');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS validate_database_selection_insert
            BEFORE INSERT ON discovered_databases
            WHEN NEW.selected = 1 AND (
                NEW.compatibility_status <> 'compatible'
                OR NEW.schema_signature IS NULL
                OR TRIM(NEW.schema_signature) = ''
            )
            BEGIN
                SELECT RAISE(ABORT, 'only compatible databases can be selected');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS validate_database_selection_update
            BEFORE UPDATE OF selected, compatibility_status, schema_signature
            ON discovered_databases
            WHEN NEW.selected = 1 AND (
                NEW.compatibility_status <> 'compatible'
                OR NEW.schema_signature IS NULL
                OR TRIM(NEW.schema_signature) = ''
            )
            BEGIN
                SELECT RAISE(ABORT, 'only compatible databases can be selected');
            END
            """,
        ),
    ),
    Migration(
        3,
        "add_schema_object_cache",
        (
            """
            CREATE TABLE IF NOT EXISTS schema_object_cache (
                id INTEGER PRIMARY KEY,
                database_id INTEGER NOT NULL,
                object_type TEXT NOT NULL CHECK (
                    object_type IN ('relation', 'index', 'trigger', 'procedure', 'generator')
                ),
                object_name TEXT NOT NULL,
                relation_name TEXT,
                details_json TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                FOREIGN KEY (database_id) REFERENCES discovered_databases(id)
                    ON DELETE CASCADE,
                UNIQUE (database_id, object_type, object_name)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_schema_objects_database_type
            ON schema_object_cache(database_id, object_type, object_name)
            """,
        ),
    ),
    Migration(
        4,
        "complete_schema_snapshot_metadata",
        (
            "ALTER TABLE schema_cache ADD COLUMN field_precision INTEGER",
            "ALTER TABLE schema_cache ADD COLUMN character_length INTEGER",
            "ALTER TABLE schema_cache ADD COLUMN character_set_name TEXT",
            "ALTER TABLE schema_cache ADD COLUMN collation_name TEXT",
            """
            CREATE TABLE IF NOT EXISTS schema_snapshots (
                database_id INTEGER PRIMARY KEY,
                schema_signature TEXT NOT NULL,
                server_version TEXT NOT NULL,
                ods_version TEXT NOT NULL,
                field_count INTEGER NOT NULL CHECK (field_count >= 0),
                object_count INTEGER NOT NULL CHECK (object_count >= 0),
                checked_at TEXT NOT NULL,
                FOREIGN KEY (database_id) REFERENCES discovered_databases(id)
                    ON DELETE CASCADE
            )
            """,
        ),
    ),
    Migration(
        5,
        "add_query_result_limit",
        (
            """
            ALTER TABLE query_templates
            ADD COLUMN result_limit INTEGER CHECK (result_limit IS NULL OR result_limit >= 1)
            """,
        ),
    ),
    Migration(
        6,
        "record_query_truncation",
        (
            """
            ALTER TABLE execution_history
            ADD COLUMN truncated INTEGER NOT NULL DEFAULT 0
                CHECK (truncated IN (0, 1))
            """,
        ),
    ),
)


def apply_migrations(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    connection.execute("BEGIN IMMEDIATE")
    try:
        applied = {
            row[0] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for migration in MIGRATIONS:
            if migration.version in applied:
                continue
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (migration.version, migration.name, _utc_now()),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
