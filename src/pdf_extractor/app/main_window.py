"""Main application window."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Provide the application's top-level window and initial file menu."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Visual PDF Data Extractor")
        self.resize(1000, 700)

        self._create_actions()
        self._create_menu()
        self._create_empty_state()
        self.statusBar().showMessage("Pronto")

    def _create_actions(self) -> None:
        """Create actions used by the main menu."""
        self.open_pdf_action = QAction("Abrir PDF", self)
        self.open_pdf_action.setShortcut("Ctrl+O")
        self.open_pdf_action.setStatusTip("Abrir um documento PDF")
        self.open_pdf_action.triggered.connect(self._show_open_pdf_placeholder)

        self.exit_action = QAction("Sair", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.setStatusTip("Fechar a aplicação")
        self.exit_action.triggered.connect(self.close)

    def _create_menu(self) -> None:
        """Build the application menu bar."""
        file_menu = self.menuBar().addMenu("Arquivo")
        file_menu.addAction(self.open_pdf_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

    def _create_empty_state(self) -> None:
        """Show the initial state before a document is loaded."""
        empty_state = QLabel(
            "Nenhum documento carregado.\n\n"
            "Use Arquivo > Abrir PDF para começar."
        )
        empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_state.setStyleSheet("color: #666666; font-size: 16px;")
        self.setCentralWidget(empty_state)

    def _show_open_pdf_placeholder(self) -> None:
        """Explain that PDF loading belongs to the next project stage."""
        LOGGER.info("Open PDF action selected")
        QMessageBox.information(
            self,
            "Abrir PDF",
            "A abertura de documentos PDF será adicionada na Etapa 2.",
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Log application shutdown and accept the close event."""
        LOGGER.info("Closing Visual PDF Data Extractor")
        event.accept()
