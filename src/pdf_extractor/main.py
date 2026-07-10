"""Application entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from pdf_extractor.app.main_window import MainWindow
from pdf_extractor.utils.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Create the Qt application and start its event loop."""
    configure_logging()
    LOGGER.info("Iniciando Visual PDF Data Extractor")

    application = QApplication(sys.argv)
    application.setApplicationName("Visual PDF Data Extractor")
    application.setOrganizationName("Visual PDF Data Extractor")

    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
