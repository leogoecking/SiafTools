from __future__ import annotations

from siaf_support_toolbox.core.logging_config import configure_logging
from siaf_support_toolbox.core.paths import AppPaths
from siaf_support_toolbox.ui.main_window import MainWindow


def main() -> None:
    paths = AppPaths.for_user().ensure()
    configure_logging(paths)
    MainWindow(paths=paths).mainloop()


if __name__ == "__main__":
    main()
