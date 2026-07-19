from __future__ import annotations

from siaf_support_toolbox.core.logging_config import configure_logging
from siaf_support_toolbox.core.paths import AppPaths
from siaf_support_toolbox.database.sqlite_connection import SQLiteDatabase
from siaf_support_toolbox.repositories.local_repository import LocalRepository
from siaf_support_toolbox.services.environment_discovery_service import (
    PersistentDiscoveryService,
)
from siaf_support_toolbox.ui.main_window import MainWindow


def main() -> None:
    paths = AppPaths.for_user().ensure()
    configure_logging(paths)
    database = SQLiteDatabase(paths.data / "siaf-support-toolbox.sqlite3")
    database.initialize()
    discovery_service = PersistentDiscoveryService(LocalRepository(database))
    MainWindow(paths=paths, orchestrator=discovery_service).mainloop()


if __name__ == "__main__":
    main()
