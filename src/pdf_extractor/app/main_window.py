"""Main application window."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from pdf_extractor.app.field_panel import FieldPanel
from pdf_extractor.app.extraction_result_table import ExtractionResultTable
from pdf_extractor.app.pdf_viewer import PdfViewer
from pdf_extractor.core.extraction_service import ExtractionService
from pdf_extractor.core.field_manager import FieldManager, FieldValidationError
from pdf_extractor.core.pdf_service import PdfService, PdfServiceError
from pdf_extractor.exporters.base import (
    ExportError,
    TabularExporter,
    build_export_dataset,
)
from pdf_extractor.exporters.csv_exporter import CsvExporter
from pdf_extractor.exporters.excel_exporter import ExcelExporter
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.field_region import FieldRegion
from pdf_extractor.models.extraction_result import ExtractionResult, ExtractionStatus
from pdf_extractor.utils.app_icon import load_application_icon

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
        self.extraction_service = ExtractionService(self.pdf_service)
        self.field_manager = FieldManager()
        self.pdf_viewer = PdfViewer()
        self.field_panel = FieldPanel()
        self.result_table = ExtractionResultTable()
        self._current_page_index = 0
        self._page_count = 0
        self._zoom_percent = self.DEFAULT_ZOOM
        self._selected_field_id: str | None = None
        self._extraction_results: tuple[ExtractionResult, ...] = ()

        self.setWindowTitle("Visual PDF Data Extractor")
        self.setWindowIcon(load_application_icon())
        self.resize(1100, 800)

        self._create_actions()
        self._create_menu()
        self._create_keyboard_shortcuts()
        self._connect_viewer_controls()
        self._connect_field_panel()
        self._connect_result_table()
        self._create_central_area()
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

    def _create_keyboard_shortcuts(self) -> None:
        """Register page navigation and zoom shortcuts for the window."""
        shortcut_bindings = (
            ("Left", self._show_previous_page),
            ("Right", self._show_next_page),
            ("Ctrl+-", self._zoom_out),
            ("Ctrl++", self._zoom_in),
            ("Ctrl+=", self._zoom_in),
        )
        self._keyboard_shortcuts: list[QShortcut] = []
        for key_sequence, callback in shortcut_bindings:
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(callback)
            self._keyboard_shortcuts.append(shortcut)

    def _connect_viewer_controls(self) -> None:
        """Connect page and zoom requests emitted by the PDF viewer."""
        self.pdf_viewer.previous_page_requested.connect(self._show_previous_page)
        self.pdf_viewer.next_page_requested.connect(self._show_next_page)
        self.pdf_viewer.zoom_out_requested.connect(self._zoom_out)
        self.pdf_viewer.zoom_in_requested.connect(self._zoom_in)
        self.pdf_viewer.reset_zoom_requested.connect(self._reset_zoom)
        self.pdf_viewer.region_selected.connect(self._handle_region_selected)
        self.pdf_viewer.field_delete_requested.connect(self._request_delete_field)

    def _connect_field_panel(self) -> None:
        """Connect selection and field management actions from the side panel."""
        self.field_panel.field_selected.connect(self._select_field)
        self.field_panel.rename_requested.connect(self._rename_field)
        self.field_panel.delete_requested.connect(self._request_delete_field)
        self.field_panel.extract_requested.connect(self._extract_data)

    def _connect_result_table(self) -> None:
        """Connect CSV and Excel export requests from the result area."""
        self.result_table.export_csv_requested.connect(self._export_csv)
        self.result_table.export_excel_requested.connect(self._export_excel)

    def _create_central_area(self) -> None:
        """Place the PDF viewer and field panel in a resizable splitter."""
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self.pdf_viewer)
        top_splitter.addWidget(self.field_panel)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 0)
        top_splitter.setSizes([820, 260])

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.result_table)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([590, 190])
        self.setCentralWidget(main_splitter)

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

        if self.field_manager.fields:
            answer = QMessageBox.question(
                self,
                "Descartar campos?",
                "Abrir outro PDF removerá todos os campos mapeados. Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
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
            page_size = self.pdf_service.page_size(0)
            self.pdf_viewer.show_page(
                document_info.file_name,
                page_image,
                0,
                page_size.width,
                page_size.height,
            )
        except (PdfServiceError, ValueError) as error:
            LOGGER.warning("Falha ao abrir PDF: %s", error)
            QMessageBox.critical(self, "Erro ao abrir PDF", str(error))
            return

        self._current_page_index = 0
        self._page_count = document_info.page_count
        self._zoom_percent = self.DEFAULT_ZOOM
        self.field_manager.clear()
        self._selected_field_id = None
        self._clear_extraction_results()
        self._refresh_fields()
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
            page_size = self.pdf_service.page_size(page_index)
            self.pdf_viewer.show_page(
                document_info.file_name,
                page_image,
                page_index,
                page_size.width,
                page_size.height,
            )
            self.pdf_viewer.set_fields(
                self.field_manager.fields,
                self._selected_field_id,
            )
        except (PdfServiceError, ValueError) as error:
            LOGGER.warning("Falha ao renderizar PDF: %s", error)
            QMessageBox.critical(self, "Erro ao renderizar página", str(error))
            return False
        return True

    def _handle_region_selected(self, region: object) -> None:
        """Ask for a name and convert a temporary region into a field."""
        if not isinstance(region, FieldRegion):
            return
        while True:
            name, accepted = QInputDialog.getText(
                self,
                "Novo campo",
                "Nome do campo:",
            )
            if not accepted:
                self.pdf_viewer.clear_draft_region()
                return
            try:
                field = self.field_manager.create(name, region)
            except FieldValidationError as error:
                QMessageBox.warning(self, "Nome inválido", str(error))
                continue
            self._selected_field_id = field.id
            self._clear_extraction_results()
            self._refresh_fields()
            self._update_document_state()
            return

    def _select_field(self, field_id: str) -> None:
        """Select a field and navigate to its page when necessary."""
        field = self.field_manager.get(field_id)
        if field is None:
            return
        if field.page_index != self._current_page_index:
            if not self._render_view(field.page_index, self._zoom_percent):
                return
            self._current_page_index = field.page_index
        self._selected_field_id = field.id
        self._refresh_fields()
        self._update_document_state()

    def _rename_field(self, field_id: str) -> None:
        """Prompt for a unique replacement name while preserving field data."""
        field = self.field_manager.get(field_id)
        if field is None:
            return
        while True:
            name, accepted = QInputDialog.getText(
                self,
                "Renomear campo",
                "Novo nome:",
                text=field.name,
            )
            if not accepted:
                return
            try:
                self.field_manager.rename(field_id, name)
            except FieldValidationError as error:
                QMessageBox.warning(self, "Nome inválido", str(error))
                continue
            self._selected_field_id = field_id
            self._clear_extraction_results()
            self._refresh_fields()
            return

    def _request_delete_field(self, field_id: str) -> None:
        """Confirm and delete a field without affecting the remaining fields."""
        field = self.field_manager.get(field_id)
        if field is None:
            return
        answer = QMessageBox.question(
            self,
            "Excluir campo",
            f'Excluir o campo "{field.name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.field_manager.delete(field_id)
        self._clear_extraction_results()
        remaining_fields = self.field_manager.fields
        self._selected_field_id = (
            remaining_fields[0].id if remaining_fields else None
        )
        self._refresh_fields()
        self._update_document_state()

    def _extract_data(self) -> None:
        """Extract native text for all fields and display independent results."""
        fields = self.field_manager.fields
        if not fields:
            return
        results = self.extraction_service.extract(fields)
        self._extraction_results = results
        self.result_table.set_results(results)
        success_count = sum(
            result.status == ExtractionStatus.SUCCESS for result in results
        )
        empty_count = sum(
            result.status == ExtractionStatus.EMPTY for result in results
        )
        error_count = sum(result.status == ExtractionStatus.ERROR for result in results)
        self.statusBar().showMessage(
            f"Extração concluída - {success_count} sucesso(s), "
            f"{empty_count} vazio(s), {error_count} erro(s)"
        )

    def _clear_extraction_results(self) -> None:
        """Remove stale extraction values and disable export actions."""
        self._extraction_results = ()
        self.result_table.clear_results()

    def _export_csv(self) -> None:
        """Ask for a CSV destination and export the latest extracted values."""
        self._export_results(
            CsvExporter(),
            "Exportar CSV",
            "Arquivos CSV (*.csv)",
            ".csv",
        )

    def _export_excel(self) -> None:
        """Ask for an XLSX destination and export the latest extracted values."""
        self._export_results(
            ExcelExporter(),
            "Exportar Excel",
            "Planilhas Excel (*.xlsx)",
            ".xlsx",
        )

    def _export_results(
        self,
        exporter: TabularExporter,
        dialog_title: str,
        file_filter: str,
        suffix: str,
    ) -> None:
        """Export one document row with columns ordered like the field panel."""
        document_info = self.pdf_service.document_info
        if document_info is None or not self._extraction_results:
            return
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            "",
            file_filter,
        )
        if not selected_path:
            return
        file_path = Path(selected_path)
        if file_path.suffix.lower() != suffix:
            file_path = file_path.with_suffix(suffix)
        dataset = build_export_dataset(
            document_info.file_name,
            self.field_manager.fields,
            self._extraction_results,
        )
        try:
            exporter.export(file_path, dataset)
        except ExportError as error:
            QMessageBox.critical(self, "Falha na exportação", str(error))
            return
        QMessageBox.information(
            self,
            "Exportação concluída",
            f"Arquivo salvo em:\n{file_path}",
        )

    def _refresh_fields(self) -> None:
        """Synchronize the canvas and side panel with the field manager."""
        fields = self.field_manager.fields
        self.pdf_viewer.set_fields(fields, self._selected_field_id)
        self.field_panel.set_fields(fields, self._selected_field_id)

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
            field_status = f" - {len(self.field_manager.fields)} campo(s)"
            self.statusBar().showMessage(
                f"{document_info.file_name} - "
                f"Página {self._current_page_index + 1} de {self._page_count} - "
                f"Zoom {self._zoom_percent}%{field_status}"
            )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Log application shutdown and accept the close event."""
        self.pdf_service.close()
        LOGGER.info("Fechando Visual PDF Data Extractor")
        event.accept()
