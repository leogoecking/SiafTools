from __future__ import annotations

import logging
import platform
from typing import Any

from siaf_support_toolbox.discovery.discovery_orchestrator import DiscoveryOrchestrator
from siaf_support_toolbox.discovery.models import DetectionIssue, DiscoveryReport
from siaf_support_toolbox.repositories.local_repository import LocalRepository

LOGGER = logging.getLogger(__name__)


class PersistentDiscoveryService:
    """Executa sempre uma análise nova e mantém a última descoberta reutilizável."""

    def __init__(
        self,
        repository: LocalRepository,
        orchestrator: DiscoveryOrchestrator | None = None,
        machine_name: str | None = None,
    ) -> None:
        self.repository = repository
        self.orchestrator = orchestrator or DiscoveryOrchestrator()
        self.machine_name = machine_name or platform.node() or "desconhecido"

    def discover(self) -> DiscoveryReport:
        report = self.orchestrator.discover()
        try:
            self.repository.record_discovery(self.machine_name, report)
        except Exception:
            LOGGER.exception("Não foi possível persistir a descoberta no banco interno")
            report.issues.append(
                DetectionIssue(
                    "persistencia_sqlite",
                    "A análise terminou, mas o histórico local não pôde ser atualizado.",
                    "local_storage_error",
                )
            )
        return report

    def latest_validated_discovery(self) -> dict[str, Any] | None:
        return self.repository.latest_validated_discovery(self.machine_name)
