from __future__ import annotations

from siaf_support_toolbox.core.logging_config import configure_logging
from siaf_support_toolbox.ui.main_window import MainWindow


def main() -> None:
    configure_logging()
    MainWindow().mainloop()


if __name__ == "__main__":
    main()
