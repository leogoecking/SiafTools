from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ManualConnectionProfile:
    name: str
    database_path: str
    environment_id: int | None = None
    host: str | None = None
    port: int | None = None
    database_type: str | None = None
    username: str | None = None
    charset: str | None = None
    fbclient_path: str | None = None
    favorite: bool = False
    active: bool = True
    id: int | None = None


@dataclass(frozen=True, slots=True)
class QueryTemplate:
    name: str
    module: str
    description: str
    sql_template: str
    required_tables: tuple[str, ...]
    required_fields: dict[str, tuple[str, ...]]
    parameters_schema: dict[str, object]
    risk_level: str
    version: str
    read_only: bool = True
    enabled: bool = True
    source_reference: str | None = None
    result_limit: int | None = None
    id: int | None = None


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    action_name: str
    action_type: str
    started_at: str
    success: bool
    app_version: str
    environment_id: int | None = None
    database_id: int | None = None
    finished_at: str | None = None
    records_processed: int = 0
    truncated: bool = False
    duration_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    output_file: str | None = None
    windows_user: str | None = None


@dataclass(frozen=True, slots=True)
class SchemaField:
    relation_name: str
    field_name: str
    field_type: str
    nullable: bool
    field_length: int | None = None
    field_scale: int | None = None
    field_precision: int | None = None
    character_length: int | None = None
    character_set_name: str | None = None
    collation_name: str | None = None
    primary_key: bool = False
    index_names: tuple[str, ...] = ()
    checked_at: str = ""


@dataclass(frozen=True, slots=True)
class SchemaObject:
    object_type: str
    object_name: str
    details: dict[str, object]
    relation_name: str | None = None
    checked_at: str = ""


@dataclass(frozen=True, slots=True)
class SchemaCacheState:
    database_id: int
    ready: bool
    reason: str | None = None
    checked_at: str | None = None
    schema_signature: str | None = None
    server_version: str | None = None
    ods_version: str | None = None
    field_count: int = 0
    object_count: int = 0


@dataclass(frozen=True, slots=True)
class KnowledgeEntry:
    category: str
    module: str
    problem: str
    version: str
    symptoms: tuple[str, ...] = ()
    causes: tuple[str, ...] = ()
    solution: tuple[str, ...] = ()
    validations: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    system_path: str | None = None
    observations: str | None = None
    confidence_level: int = 0
    source: str | None = None
    active: bool = True
