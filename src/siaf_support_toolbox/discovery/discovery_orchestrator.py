from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from siaf_support_toolbox.core.constants import DEFAULT_FIREBIRD_PORT
from siaf_support_toolbox.discovery.architecture import (
    is_process_admin,
    process_architecture,
    process_bits,
)
from siaf_support_toolbox.discovery.config_detector import detect_firebird_configurations
from siaf_support_toolbox.discovery.database_locator import locate_databases
from siaf_support_toolbox.discovery.firebird_client_detector import detect_client_libraries
from siaf_support_toolbox.discovery.mode_classifier import classify_machine
from siaf_support_toolbox.discovery.models import DetectionIssue, DiscoveryReport, Evidence
from siaf_support_toolbox.discovery.network_detector import detect_process_connections
from siaf_support_toolbox.discovery.process_detector import (
    detect_firebird_processes,
    detect_siaf_processes,
)
from siaf_support_toolbox.discovery.registry_detector import detect_registry
from siaf_support_toolbox.discovery.shortcut_detector import detect_siaf_shortcuts
from siaf_support_toolbox.discovery.siaf_install_detector import detect_siaf_installations
from siaf_support_toolbox.discovery.windows_service_detector import detect_firebird_services

LOGGER = logging.getLogger(__name__)


class DiscoveryOrchestrator:
    """Executa detectores independentes e preserva falhas parciais no relatório."""

    def __init__(self, configured_roots: list[Path] | None = None) -> None:
        self.configured_roots = configured_roots or []

    def discover(self) -> DiscoveryReport:
        report = DiscoveryReport(
            process_architecture=process_architecture(),
            process_bits=process_bits(),
            is_admin=is_process_admin(),
        )
        report.evidence.append(
            Evidence(
                "arquitetura_processo",
                f"{report.process_architecture} ({report.process_bits} bits)",
                10,
            )
        )

        report.siaf_processes, issues = self._safe("processos_siaf", detect_siaf_processes, ([],))
        report.issues.extend(issues)
        shortcuts, issues = self._safe("atalhos_siaf", detect_siaf_shortcuts, ([],))
        report.siaf_shortcuts = shortcuts
        report.issues.extend(issues)
        report.evidence.extend(
            Evidence("atalho_siaf", shortcut.path, 15) for shortcut in report.siaf_shortcuts
        )
        report.firebird_processes, issues = self._safe(
            "processos_firebird", detect_firebird_processes, ([],)
        )
        report.issues.extend(issues)
        report.services, issues = self._safe("servicos_windows", detect_firebird_services, ([],))
        report.issues.extend(issues)
        report.registry, issues = self._safe("registro_windows", detect_registry, ([],))
        report.issues.extend(issues)

        roots = self._seed_roots(report)
        installations, evidence, issues = self._safe(
            "instalacao_siaf",
            lambda: detect_siaf_installations(report.siaf_processes, roots),
            ([], []),
        )
        report.evidence.extend(evidence)
        report.issues.extend(issues)
        roots.extend(item.parent if item.is_file() else item for item in installations)
        roots = self._unique_existing(roots)

        report.firebird_configurations, issues = self._safe(
            "config_firebird",
            lambda: detect_firebird_configurations(roots),
            ([],),
        )
        report.issues.extend(issues)
        report.aliases = [
            alias
            for configuration in report.firebird_configurations
            for alias in configuration.aliases
        ]
        report.detected_ports = sorted(
            {configuration.port for configuration in report.firebird_configurations}
        ) or [DEFAULT_FIREBIRD_PORT]
        alias_paths = [Path(item.database) for item in report.aliases]

        report.client_libraries, issues = self._safe(
            "cliente_firebird", lambda: detect_client_libraries(roots), ([],)
        )
        report.issues.extend(issues)
        report.databases, issues = self._safe(
            "localizador_bases",
            lambda: locate_databases(roots, installations, alias_paths),
            ([],),
        )
        report.issues.extend(issues)
        report.network_connections, issues = self._safe(
            "conexoes_tcp_siaf",
            lambda: detect_process_connections(item.pid for item in report.siaf_processes),
            ([],),
        )
        report.issues.extend(issues)

        report.mode, report.confidence, mode_evidence = classify_machine(report)
        report.evidence.extend(mode_evidence)
        LOGGER.info(
            "Descoberta concluída: modo=%s confiança=%s bases=%s avisos=%s",
            report.mode,
            report.confidence,
            len(report.databases),
            len(report.issues),
        )
        return report

    def _seed_roots(self, report: DiscoveryReport) -> list[Path]:
        roots = list(self.configured_roots)
        for shortcut in report.siaf_shortcuts:
            if shortcut.target_path:
                target = Path(shortcut.target_path)
                roots.append(target.parent if target.suffix else target)
            if shortcut.working_directory:
                roots.append(Path(shortcut.working_directory))
        for process in report.siaf_processes + report.firebird_processes:
            if process.executable:
                roots.append(Path(process.executable).parent)
        for service in report.services:
            if service.binary_path:
                executable = self._path_from_command(service.binary_path)
                if executable:
                    roots.append(executable.parent)
        for finding in report.registry:
            candidate = self._path_from_command(finding.value)
            if candidate:
                roots.append(candidate if candidate.is_dir() else candidate.parent)

        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(variable)
            if base:
                roots.extend(Path(base) / name for name in ("Firebird", "InterBase"))
        roots.extend((Path("C:/Firebird"), Path("C:/Program Files/Firebird")))
        return self._unique_existing(roots)

    @staticmethod
    def _path_from_command(value: str) -> Path | None:
        clean = os.path.expandvars(value.strip())
        if clean.startswith('"'):
            end = clean.find('"', 1)
            clean = clean[1:end] if end > 1 else clean.strip('"')
        else:
            lower = clean.casefold()
            for extension in (".exe", ".dll"):
                index = lower.find(extension)
                if index >= 0:
                    clean = clean[: index + len(extension)]
                    break
        path = Path(clean)
        return path if path.exists() else None

    @staticmethod
    def _unique_existing(paths: list[Path]) -> list[Path]:
        unique: dict[str, Path] = {}
        for path in paths:
            if path.exists():
                unique[os.path.normcase(str(path.resolve(strict=False)))] = path
        return list(unique.values())

    @staticmethod
    def _safe(
        name: str,
        function: Callable[[], tuple[Any, ...]],
        fallback_values: tuple[Any, ...],
    ) -> tuple[Any, ...]:
        try:
            return function()
        except Exception as exc:  # detector não pode derrubar a descoberta completa
            LOGGER.exception("Detector %s falhou", name)
            issue = DetectionIssue(name, str(exc), "unexpected_error")
            return (*fallback_values, [issue])
