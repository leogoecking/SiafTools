from __future__ import annotations

import logging
import sqlite3

from siaf_support_toolbox.core.logging_config import configure_logging
from siaf_support_toolbox.core.paths import AppPaths
from siaf_support_toolbox.database.sqlite_connection import SQLiteDatabase
from siaf_support_toolbox.repositories.local_repository import LocalRepository
from siaf_support_toolbox.services.connection_service import FirebirdConnectionService
from siaf_support_toolbox.services.diagnostic_export_service import DiagnosticExportService
from siaf_support_toolbox.services.environment_discovery_service import (
    PersistentDiscoveryService,
)
from siaf_support_toolbox.services.query_execution_service import QueryExecutionService
from siaf_support_toolbox.services.schema_inspection_service import SchemaInspectionService
from siaf_support_toolbox.ui.main_window import MainWindow
from siaf_support_toolbox.ui.startup_error import show_database_startup_error

LOGGER = logging.getLogger(__name__)


def main() -> None:
    paths = AppPaths.for_user().ensure()
    configure_logging(paths)
    database_path = paths.data / "siaf-support-toolbox.sqlite3"
    database = SQLiteDatabase(database_path)
    try:
        database.initialize()
    except (sqlite3.Error, OSError):
        LOGGER.exception("O banco interno não pôde ser inicializado")
        show_database_startup_error(database_path)
        return
    repository = LocalRepository(database)
    discovery_service = PersistentDiscoveryService(repository)
    connection_service = FirebirdConnectionService(repository)
    schema_inspector = SchemaInspectionService(repository)
    query_service = QueryExecutionService(
        repository, schema_inspector, paths.data / "query-cache", paths.exports
    )
    diagnostic_exporter = DiagnosticExportService(paths.exports)
    MainWindow(
        paths=paths,
        orchestrator=discovery_service,
        connection_service=connection_service,
        schema_inspector=schema_inspector,
        query_service=query_service,
        diagnostic_exporter=diagnostic_exporter,
    ).mainloop()


if __name__ == "__main__":
    main()
