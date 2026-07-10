"""Main application window."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox

from pdf_extractor.app.pdf_viewer import PdfViewer
from pdf_extractor.core.pdf_service import PdfService, PdfServiceError

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Provide the application's top-level window and initial file menu."""

    def __init__(self, pdf_service: PdfService | None = None) -> None:
        super().__init__()
        self.pdf_service = pdf_service or PdfService()
        self.pdf_viewer = PdfViewer()

        self.setWindowTitle("Visual PDF Data Extractor")
        self.resize(1000, 700)

        self._create_actions()
        self._create_menu()
        self.setCentralWidget(self.pdf_viewer)
        self.statusBar().showMessage("Pronto")

    def _create_actions(self) -> None:
        """Create actions used by the main menu."""
        self.open_pdf_action = QAction("Abrir PDF", self)
        self.open_pdf_action.setShortcut("Ctrl+O")
        self.open_pdf_action.setStatusTip("Abrir um documento PDF")
        self.open_pdf_action.triggered.connect(self._select_pdf)

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

    def _select_pdf(self) -> None:
        """Ask the user for a PDF and load its first page."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir PDF",
            "",
            "Documentos PDF (*.pdf)",
        )
        if not file_path:
            return

        self._load_pdf(Path(file_path))

    def _load_pdf(self, file_path: Path) -> None:
        """Load and present the first page of a selected PDF."""
        try:
            document_info = self.pdf_service.open_document(file_path)
            page_image = self.pdf_service.render_page(0)
            self.pdf_viewer.show_page(document_info.file_name, page_image)
        except (PdfServiceError, ValueError) as error:
            LOGGER.warning("Falha ao abrir PDF: %s", error)
            QMessageBox.critical(self, "Erro ao abrir PDF", str(error))
            return

        LOGGER.info("PDF carregado: %s", document_info.file_name)
        self.setWindowTitle(f"{document_info.file_name} - Visual PDF Data Extractor")
        page_word = "página" if document_info.page_count == 1 else "páginas"
        self.statusBar().showMessage(
            f"{document_info.file_name} - {document_info.page_count} {page_word}"
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Log application shutdown and accept the close event."""
        self.pdf_service.close()
        LOGGER.info("Fechando Visual PDF Data Extractor")
        event.accept()
