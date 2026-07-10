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

    MINIMUM_ZOOM = 50
    MAXIMUM_ZOOM = 300
    DEFAULT_ZOOM = 100
    ZOOM_STEP = 25

    def __init__(self, pdf_service: PdfService | None = None) -> None:
        super().__init__()
        self.pdf_service = pdf_service or PdfService()
        self.pdf_viewer = PdfViewer()
        self._current_page_index = 0
        self._page_count = 0
        self._zoom_percent = self.DEFAULT_ZOOM

        self.setWindowTitle("Visual PDF Data Extractor")
        self.resize(1000, 700)

        self._create_actions()
        self._create_menu()
        self._connect_viewer_controls()
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

    def _connect_viewer_controls(self) -> None:
        """Connect page and zoom requests emitted by the PDF viewer."""
        self.pdf_viewer.previous_page_requested.connect(self._show_previous_page)
        self.pdf_viewer.next_page_requested.connect(self._show_next_page)
        self.pdf_viewer.zoom_out_requested.connect(self._zoom_out)
        self.pdf_viewer.zoom_in_requested.connect(self._zoom_in)
        self.pdf_viewer.reset_zoom_requested.connect(self._reset_zoom)

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
            page_image = self.pdf_service.render_page(
                0,
                self.DEFAULT_ZOOM / 100,
            )
            self.pdf_viewer.show_page(document_info.file_name, page_image)
        except (PdfServiceError, ValueError) as error:
            LOGGER.warning("Falha ao abrir PDF: %s", error)
            QMessageBox.critical(self, "Erro ao abrir PDF", str(error))
            return

        self._current_page_index = 0
        self._page_count = document_info.page_count
        self._zoom_percent = self.DEFAULT_ZOOM
        LOGGER.info("PDF carregado: %s", document_info.file_name)
        self.setWindowTitle(f"{document_info.file_name} - Visual PDF Data Extractor")
        self._update_document_state()

    def _show_previous_page(self) -> None:
        """Render the previous page when it exists."""
        self._change_page(self._current_page_index - 1)

    def _show_next_page(self) -> None:
        """Render the next page when it exists."""
        self._change_page(self._current_page_index + 1)

    def _change_page(self, page_index: int) -> None:
        """Render and commit a page change within the document limits."""
        if not 0 <= page_index < self._page_count:
            return
        if self._render_view(page_index, self._zoom_percent):
            self._current_page_index = page_index
            self._update_document_state()

    def _zoom_out(self) -> None:
        """Decrease the zoom by one configured step."""
        self._set_zoom(self._zoom_percent - self.ZOOM_STEP)

    def _zoom_in(self) -> None:
        """Increase the zoom by one configured step."""
        self._set_zoom(self._zoom_percent + self.ZOOM_STEP)

    def _reset_zoom(self) -> None:
        """Restore the default zoom level."""
        self._set_zoom(self.DEFAULT_ZOOM)

    def _set_zoom(self, zoom_percent: int) -> None:
        """Render and commit a zoom change within the configured limits."""
        if self._page_count == 0:
            return
        limited_zoom = min(
            self.MAXIMUM_ZOOM,
            max(self.MINIMUM_ZOOM, zoom_percent),
        )
        if limited_zoom == self._zoom_percent:
            return
        if self._render_view(self._current_page_index, limited_zoom):
            self._zoom_percent = limited_zoom
            self._update_document_state()

    def _render_view(self, page_index: int, zoom_percent: int) -> bool:
        """Render a requested view without changing state on failure."""
        document_info = self.pdf_service.document_info
        if document_info is None:
            return False

        try:
            page_image = self.pdf_service.render_page(page_index, zoom_percent / 100)
            self.pdf_viewer.show_page(document_info.file_name, page_image)
        except (PdfServiceError, ValueError) as error:
            LOGGER.warning("Falha ao renderizar PDF: %s", error)
            QMessageBox.critical(self, "Erro ao renderizar página", str(error))
            return False
        return True

    def _update_document_state(self) -> None:
        """Synchronize controls and status text with page and zoom state."""
        self.pdf_viewer.update_controls(
            self._current_page_index,
            self._page_count,
            self._zoom_percent,
            self.MINIMUM_ZOOM,
            self.MAXIMUM_ZOOM,
        )
        document_info = self.pdf_service.document_info
        if document_info is not None:
            self.statusBar().showMessage(
                f"{document_info.file_name} - "
                f"Página {self._current_page_index + 1} de {self._page_count} - "
                f"Zoom {self._zoom_percent}%"
            )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Log application shutdown and accept the close event."""
        self.pdf_service.close()
        LOGGER.info("Fechando Visual PDF Data Extractor")
        event.accept()
