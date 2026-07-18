from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from siaf_support_toolbox.core.constants import (
    MINIMUM_SCHEMA_CONFIDENCE,
    SIAFLOJA_SIGNATURE,
    SIAFW_SIGNATURE,
)


class DatabaseType(StrEnum):
    SIAFLOJA = "SIAFLOJA"
    SIAFW = "SIAFW"
    NOT_SIAF = "NAO_SIAF"
    AMBIGUOUS = "AMBIGUA"


@dataclass(frozen=True, slots=True)
class SchemaClassification:
    database_type: DatabaseType
    confidence: int
    matched_tables: tuple[str, ...]
    missing_tables: tuple[str, ...]

    @property
    def is_accepted(self) -> bool:
        return (
            self.database_type in {DatabaseType.SIAFLOJA, DatabaseType.SIAFW}
            and self.confidence >= MINIMUM_SCHEMA_CONFIDENCE
        )


def classify_schema(table_names: Iterable[str]) -> SchemaClassification:
    actual = {name.strip().upper() for name in table_names}
    loja_matches = actual & SIAFLOJA_SIGNATURE
    siafw_matches = actual & SIAFW_SIGNATURE
    loja_ratio = len(loja_matches) / len(SIAFLOJA_SIGNATURE)
    siafw_ratio = len(siafw_matches) / len(SIAFW_SIGNATURE)

    if not loja_matches and not siafw_matches:
        expected_tables = tuple(sorted(SIAFLOJA_SIGNATURE | SIAFW_SIGNATURE))
        return SchemaClassification(DatabaseType.NOT_SIAF, 0, (), expected_tables)
    if loja_ratio == siafw_ratio:
        matched = loja_matches | siafw_matches
        return SchemaClassification(
            DatabaseType.AMBIGUOUS,
            int(loja_ratio * 100),
            tuple(sorted(matched)),
            (),
        )
    if loja_ratio > siafw_ratio:
        return SchemaClassification(
            DatabaseType.SIAFLOJA,
            int(loja_ratio * 100),
            tuple(sorted(loja_matches)),
            tuple(sorted(SIAFLOJA_SIGNATURE - actual)),
        )
    return SchemaClassification(
        DatabaseType.SIAFW,
        int(siafw_ratio * 100),
        tuple(sorted(siafw_matches)),
        tuple(sorted(SIAFW_SIGNATURE - actual)),
    )
