from __future__ import annotations

import getpass
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from siaf_support_toolbox.core.version import __version__
from siaf_support_toolbox.database.firebird_schema_inspector import (
    SchemaInspectionResult,
    SchemaSnapshot,
    inspect_schema_read_only,
)
from siaf_support_toolbox.database.sql_validator import SAFE_SYSTEM_RELATIONS
from siaf_support_toolbox.repositories.local_repository import LocalRepository
from siaf_support_toolbox.repositories.models import ExecutionRecord, SchemaField, SchemaObject
from siaf_support_toolbox.services.connection_service import ConnectionTarget, SessionCredentials


@dataclass(frozen=True, slots=True)
class SchemaInspectionSummary:
    target: ConnectionTarget
    result: SchemaInspectionResult
    database_id: int
    duration_ms: int


@dataclass(frozen=True, slots=True)
class SchemaRequirementCheck:
    allowed: bool
    cache_ready: bool = False
    reason: str | None = None
    missing_relations: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SchemaComparison:
    comparable: bool = True
    reason: str | None = None
    left_only_relations: tuple[str, ...] = ()
    right_only_relations: tuple[str, ...] = ()
    left_only_fields: tuple[str, ...] = ()
    right_only_fields: tuple[str, ...] = ()
    changed_fields: tuple[str, ...] = ()
    left_only_objects: tuple[str, ...] = ()
    right_only_objects: tuple[str, ...] = ()
    changed_objects: tuple[str, ...] = ()

    @property
    def equivalent(self) -> bool:
        return self.comparable and not any(
            (
                self.left_only_relations,
                self.right_only_relations,
                self.left_only_fields,
                self.right_only_fields,
                self.changed_fields,
                self.left_only_objects,
                self.right_only_objects,
                self.changed_objects,
            )
        )


class SchemaInspectionService:
    def __init__(
        self,
        repository: LocalRepository,
        *,
        inspector: Callable[..., SchemaInspectionResult] = inspect_schema_read_only,
    ) -> None:
        self.repository = repository
        self._inspector = inspector

    def inspect(
        self,
        target: ConnectionTarget,
        database_id: int,
        credentials: SessionCredentials,
    ) -> SchemaInspectionSummary:
        try:
            return self._inspect_one(target, database_id, credentials)
        finally:
            credentials.clear()

    def inspect_many(
        self,
        targets: tuple[tuple[ConnectionTarget, int], ...],
        credentials: SessionCredentials,
    ) -> tuple[SchemaInspectionSummary, ...]:
        try:
            return tuple(
                self._inspect_one(target, database_id, credentials)
                for target, database_id in targets
            )
        finally:
            credentials.clear()

    def _inspect_one(
        self,
        target: ConnectionTarget,
        database_id: int,
        credentials: SessionCredentials,
    ) -> SchemaInspectionSummary:
        started_at = datetime.now(UTC)
        started = time.monotonic()
        result = self._inspector(
            dsn=target.dsn,
            username=credentials.username,
            password=credentials.password,
            client_library=target.client_library,
            charset=credentials.charset,
            host=target.host,
            port=target.port,
            connect_timeout=3.0,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        if result.success and result.snapshot is not None:
            self.repository.replace_schema_snapshot(
                database_id,
                list(result.snapshot.fields),
                _snapshot_objects(result.snapshot),
                server_version=result.snapshot.server_version,
                ods_version=result.snapshot.ods_version,
                checked_at=result.snapshot.checked_at,
            )
        self.repository.add_execution_history(
            ExecutionRecord(
                environment_id=target.environment_id,
                database_id=database_id,
                action_name="Inspeção do catálogo Firebird",
                action_type="schema_inspection",
                started_at=started_at.isoformat(timespec="seconds"),
                finished_at=datetime.now(UTC).isoformat(timespec="seconds"),
                success=result.success,
                records_processed=len(result.snapshot.fields) if result.snapshot else 0,
                duration_ms=duration_ms,
                error_code=result.error_code,
                error_message=result.message,
                app_version=__version__,
                windows_user=getpass.getuser(),
            )
        )
        return SchemaInspectionSummary(target, result, database_id, duration_ms)

    def validate_requirements(
        self,
        database_id: int,
        *,
        required_tables: tuple[str, ...],
        required_fields: dict[str, tuple[str, ...]],
    ) -> SchemaRequirementCheck:
        state = self.repository.schema_cache_state(database_id)
        if not state.ready:
            return SchemaRequirementCheck(False, cache_ready=False, reason=state.reason)
        fields, objects = self.repository.load_schema_cache(database_id)
        relations = {
            item.object_name.casefold() for item in objects if item.object_type == "relation"
        }
        relations.update(item.relation_name.casefold() for item in fields)
        relations.update(name.casefold() for name in SAFE_SYSTEM_RELATIONS)
        available_fields = {
            (item.relation_name.casefold(), item.field_name.casefold()) for item in fields
        }
        missing_relations = tuple(
            name for name in required_tables if name.casefold() not in relations
        )
        missing_fields = tuple(
            f"{relation}.{field}"
            for relation, field_names in required_fields.items()
            for field in field_names
            if (relation.casefold(), field.casefold()) not in available_fields
        )
        return SchemaRequirementCheck(
            allowed=not missing_relations and not missing_fields,
            cache_ready=True,
            missing_relations=missing_relations,
            missing_fields=missing_fields,
        )

    def compare_cached(self, left_database_id: int, right_database_id: int) -> SchemaComparison:
        left_state = self.repository.schema_cache_state(left_database_id)
        right_state = self.repository.schema_cache_state(right_database_id)
        if not left_state.ready or not right_state.ready:
            reasons = [
                reason
                for reason in (left_state.reason, right_state.reason)
                if reason is not None
            ]
            return SchemaComparison(comparable=False, reason="; ".join(dict.fromkeys(reasons)))
        left_fields, left_objects = self.repository.load_schema_cache(left_database_id)
        right_fields, right_objects = self.repository.load_schema_cache(right_database_id)
        return compare_schema_caches(left_fields, left_objects, right_fields, right_objects)


def compare_schema_caches(
    left_fields: list[SchemaField],
    left_objects: list[SchemaObject],
    right_fields: list[SchemaField],
    right_objects: list[SchemaObject],
) -> SchemaComparison:
    if not left_fields or not left_objects or not right_fields or not right_objects:
        return SchemaComparison(
            comparable=False,
            reason="As duas bases precisam de snapshots estruturais completos",
        )
    left_relations = _relation_names(left_fields, left_objects)
    right_relations = _relation_names(right_fields, right_objects)
    left_map = {_field_key(item): _field_signature(item) for item in left_fields}
    right_map = {_field_key(item): _field_signature(item) for item in right_fields}
    common_fields = left_map.keys() & right_map.keys()
    left_object_keys = _object_keys(left_objects)
    right_object_keys = _object_keys(right_objects)
    left_object_map = {_object_key(item): _object_signature(item) for item in left_objects}
    right_object_map = {_object_key(item): _object_signature(item) for item in right_objects}
    return SchemaComparison(
        left_only_relations=tuple(sorted(left_relations - right_relations)),
        right_only_relations=tuple(sorted(right_relations - left_relations)),
        left_only_fields=tuple(sorted(left_map.keys() - right_map.keys())),
        right_only_fields=tuple(sorted(right_map.keys() - left_map.keys())),
        changed_fields=tuple(
            sorted(key for key in common_fields if left_map[key] != right_map[key])
        ),
        left_only_objects=tuple(sorted(left_object_keys - right_object_keys)),
        right_only_objects=tuple(sorted(right_object_keys - left_object_keys)),
        changed_objects=tuple(
            sorted(
                key
                for key in left_object_map.keys() & right_object_map.keys()
                if left_object_map[key] != right_object_map[key]
            )
        ),
    )


def _snapshot_objects(snapshot: SchemaSnapshot) -> list[SchemaObject]:
    checked_at = snapshot.checked_at
    objects = [
        SchemaObject(
            "relation",
            item.name,
            {"is_view": item.is_view, "definition_hash": item.definition_hash},
            checked_at=checked_at,
        )
        for item in snapshot.relations
    ]
    objects.extend(
        SchemaObject(
            "index",
            item.name,
            {
                "fields": item.fields,
                "unique": item.unique,
                "descending": item.descending,
                "primary_key": item.primary_key,
                "expression_hash": item.expression_hash,
            },
            relation_name=item.relation_name,
            checked_at=checked_at,
        )
        for item in snapshot.indexes
    )
    objects.extend(
        SchemaObject(
            "trigger",
            item.name,
            {
                "trigger_type": item.trigger_type,
                "sequence": item.sequence,
                "active": item.active,
                "source_hash": item.source_hash,
            },
            relation_name=item.relation_name,
            checked_at=checked_at,
        )
        for item in snapshot.triggers
    )
    objects.extend(
        SchemaObject(
            "procedure",
            item.name,
            {
                "input_count": item.input_count,
                "output_count": item.output_count,
                "procedure_type": item.procedure_type,
                "source_hash": item.source_hash,
                "parameters_hash": item.parameters_hash,
            },
            checked_at=checked_at,
        )
        for item in snapshot.procedures
    )
    objects.extend(
        SchemaObject("generator", item.name, {}, checked_at=checked_at)
        for item in snapshot.generators
    )
    return objects


def _relation_names(fields: list[SchemaField], objects: list[SchemaObject]) -> set[str]:
    names = {item.relation_name.casefold() for item in fields}
    names.update(
        item.object_name.casefold() for item in objects if item.object_type == "relation"
    )
    return names


def _field_key(item: SchemaField) -> str:
    return f"{item.relation_name}.{item.field_name}".casefold()


def _field_signature(item: SchemaField) -> tuple[object, ...]:
    return (
        item.field_type.casefold(),
        item.field_length,
        item.field_scale,
        item.field_precision,
        item.character_length,
        item.character_set_name.casefold() if item.character_set_name else None,
        item.collation_name.casefold() if item.collation_name else None,
        item.nullable,
        item.primary_key,
        tuple(name.casefold() for name in item.index_names),
    )


def _object_keys(objects: list[SchemaObject]) -> set[str]:
    return {
        _object_key(item)
        for item in objects
        if item.object_type != "relation"
    }


def _object_key(item: SchemaObject) -> str:
    return f"{item.object_type}:{item.relation_name or ''}:{item.object_name}".casefold()


def _object_signature(item: SchemaObject) -> str:
    return json.dumps(item.details, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
