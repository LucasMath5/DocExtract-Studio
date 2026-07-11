"""Application entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from pdf_extractor.app.main_window import MainWindow
from pdf_extractor.utils.app_icon import (
    configure_windows_app_user_model_id,
    load_application_icon,
)
from pdf_extractor.utils.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Create the Qt application and start its event loop."""
    configure_logging()
    LOGGER.info("Iniciando Visual PDF Data Extractor")

    configure_windows_app_user_model_id()
    application = QApplication(sys.argv)
    application.setApplicationName("Visual PDF Data Extractor")
    application.setOrganizationName("Visual PDF Data Extractor")
    application.setWindowIcon(load_application_icon())

    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
