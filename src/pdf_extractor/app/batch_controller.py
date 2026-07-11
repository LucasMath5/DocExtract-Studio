"""Qt workflow for selecting and processing PDF files in a worker thread."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QProgressDialog

from pdf_extractor.app.batch_result_dialog import BatchResultDialog
from pdf_extractor.core.batch_service import BatchError, BatchService
from pdf_extractor.core.template_service import TemplateError, TemplateService
from pdf_extractor.models.batch_result import BatchDocumentResult, BatchReport
from pdf_extractor.models.extraction_template import ExtractionTemplate


LOGGER = logging.getLogger(__name__)


class BatchWorker(QObject):
    """Run the synchronous batch service away from the GUI thread."""

    progress = Signal(int, int, object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        file_paths: tuple[Path, ...],
        template: ExtractionTemplate,
        cancellation: Event,
        service: BatchService | None = None,
    ) -> None:
        super().__init__()
        self._file_paths = file_paths
        self._template = template
        self._cancellation = cancellation
        self._service = service or BatchService()

    @Slot()
    def run(self) -> None:
        """Process the selected files and emit one terminal signal."""
        try:
            report = self._service.process(
                self._file_paths,
                self._template,
                progress_callback=self._emit_progress,
                cancellation_requested=self._cancellation.is_set,
            )
        except BatchError as error:
            self.failed.emit(str(error))
            return
        except Exception:
            LOGGER.exception("Falha inesperada no processamento em lote")
            self.failed.emit("O processamento em lote falhou inesperadamente.")
            return
        self.completed.emit(report)

    def _emit_progress(
        self,
        processed: int,
        total: int,
        result: BatchDocumentResult,
    ) -> None:
        self.progress.emit(processed, total, result)


class BatchController(QObject):
    """Own batch actions, progress state, thread lifetime, and final report."""

    report_ready = Signal(object)

    def __init__(self, parent: QMainWindow) -> None:
        super().__init__(parent)
        self._window = parent
        self._template_service = TemplateService()
        self._thread: QThread | None = None
        self._worker: BatchWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._result_dialog: BatchResultDialog | None = None
        self._cancellation = Event()
        self._template: ExtractionTemplate | None = None
        self._create_actions()

    @property
    def is_running(self) -> bool:
        """Return whether a worker thread is currently active."""
        return self._thread is not None and self._thread.isRunning()

    @property
    def result_dialog(self) -> BatchResultDialog | None:
        """Expose the latest report window for integration tests."""
        return self._result_dialog

    def _create_actions(self) -> None:
        self.select_files_action = QAction("Processar PDFs...", self)
        self.select_files_action.setStatusTip(
            "Selecionar vários PDFs para processamento em lote"
        )
        self.select_files_action.triggered.connect(self._select_files)

        self.select_folder_action = QAction("Processar pasta...", self)
        self.select_folder_action.setStatusTip(
            "Processar todos os PDFs de uma pasta"
        )
        self.select_folder_action.triggered.connect(self._select_folder)

    def _select_files(self) -> None:
        selected_paths, _ = QFileDialog.getOpenFileNames(
            self._window,
            "Selecionar PDFs para o lote",
            "",
            "Documentos PDF (*.pdf)",
        )
        if selected_paths:
            file_paths = tuple(Path(path) for path in selected_paths)
            self._choose_template_and_start(file_paths)

    def _select_folder(self) -> None:
        selected_folder = QFileDialog.getExistingDirectory(
            self._window,
            "Selecionar pasta com PDFs",
        )
        if not selected_folder:
            return
        try:
            file_paths = self.pdfs_in_folder(Path(selected_folder))
        except OSError:
            QMessageBox.critical(
                self._window,
                "Erro ao acessar pasta",
                "Não foi possível listar os arquivos da pasta selecionada.",
            )
            return
        if not file_paths:
            QMessageBox.warning(
                self._window,
                "Nenhum PDF encontrado",
                "A pasta selecionada não contém arquivos PDF.",
            )
            return
        self._choose_template_and_start(file_paths)

    @staticmethod
    def pdfs_in_folder(folder: Path) -> tuple[Path, ...]:
        """Return top-level PDF files in stable case-insensitive name order."""
        return tuple(
            sorted(
                (
                    path
                    for path in folder.iterdir()
                    if path.is_file() and path.suffix.casefold() == ".pdf"
                ),
                key=lambda path: path.name.casefold(),
            )
        )

    def _choose_template_and_start(self, file_paths: tuple[Path, ...]) -> None:
        if self.is_running:
            QMessageBox.warning(
                self._window,
                "Lote em andamento",
                "Aguarde ou cancele o processamento atual.",
            )
            return
        selected_template, _ = QFileDialog.getOpenFileName(
            self._window,
            "Selecionar template do lote",
            "",
            "Templates JSON (*.json)",
        )
        if not selected_template:
            return
        try:
            template = self._template_service.load(Path(selected_template))
        except TemplateError as error:
            QMessageBox.critical(self._window, "Template inválido", str(error))
            return
        if not template.fields:
            QMessageBox.warning(
                self._window,
                "Template sem campos",
                "O template selecionado não possui campos para extrair.",
            )
            return
        self._start(file_paths, template)

    def _start(
        self,
        file_paths: tuple[Path, ...],
        template: ExtractionTemplate,
    ) -> None:
        self._cancellation = Event()
        self._template = template
        self._progress_dialog = QProgressDialog(
            "Preparando processamento...",
            "Cancelar",
            0,
            len(file_paths),
            self._window,
        )
        self._progress_dialog.setWindowTitle("Processamento em lote")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setAutoClose(False)
        self._progress_dialog.setValue(0)
        self._progress_dialog.canceled.connect(self._cancel)

        thread = QThread(self)
        worker = BatchWorker(file_paths, template, self._cancellation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        self.select_files_action.setEnabled(False)
        self.select_folder_action.setEnabled(False)
        thread.start()

    @Slot()
    def _cancel(self) -> None:
        self._cancellation.set()
        if self._progress_dialog is not None:
            self._progress_dialog.setLabelText(
                "Cancelamento solicitado; finalizando o PDF atual..."
            )

    @Slot(int, int, object)
    def _on_progress(
        self,
        processed: int,
        total: int,
        result_object: object,
    ) -> None:
        if self._progress_dialog is None:
            return
        result = (
            result_object
            if isinstance(result_object, BatchDocumentResult)
            else None
        )
        file_name = result.file_name if result is not None else "PDF"
        self._progress_dialog.setLabelText(
            f"Processado {processed} de {total}: {file_name}"
        )
        self._progress_dialog.setValue(processed)

    @Slot(object)
    def _on_completed(self, report_object: object) -> None:
        self._close_progress()
        if not isinstance(report_object, BatchReport) or self._template is None:
            self._on_failed("O lote retornou um resultado inválido.")
            return
        self._result_dialog = BatchResultDialog(
            report_object,
            self._template,
            self._window,
        )
        self._result_dialog.show()
        self.report_ready.emit(report_object)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._close_progress()
        QMessageBox.critical(self._window, "Falha no lote", message)

    @Slot()
    def _on_thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        self._worker = None
        self.select_files_action.setEnabled(True)
        self.select_folder_action.setEnabled(True)
        if thread is not None:
            thread.deleteLater()

    def _close_progress(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog.deleteLater()
            self._progress_dialog = None

    def shutdown(self) -> bool:
        """Cancel active work and report whether the thread stopped safely."""
        self._cancellation.set()
        if self._thread is not None and self._thread.isRunning():
            return self._thread.wait(30_000)
        return True
