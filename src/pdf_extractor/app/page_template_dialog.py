"""Workflow for extracting and generating one named PDF per source page."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QColor, QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pdf_extractor.core.page_template_service import (
    PageOutputItem,
    PageOutputStatus,
    PageTemplateError,
    PageTemplateService,
)
from pdf_extractor.core.pdf_rename_service import RenamePattern
from pdf_extractor.core.pdf_split_service import PdfSplitError, parse_excluded_pages
from pdf_extractor.models.extraction_template import ExtractionTemplate
from pdf_extractor.models.page_template_result import (
    PageTemplateReport,
    PageTemplateResult,
)


class PageTemplateWorker(QObject):
    """Run potentially slow native extraction and OCR outside the GUI thread."""

    progress = Signal(int, int, object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: PageTemplateService,
        source_path: Path,
        template: ExtractionTemplate,
        excluded_pages: frozenset[int],
        cancellation: Event,
    ) -> None:
        super().__init__()
        self._service = service
        self._source_path = source_path
        self._template = template
        self._excluded_pages = excluded_pages
        self._cancellation = cancellation

    @Slot()
    def run(self) -> None:
        try:
            report = self._service.process(
                self._source_path,
                self._template,
                self._excluded_pages,
                progress_callback=self._emit_progress,
                cancellation_requested=self._cancellation.is_set,
            )
        except PageTemplateError as error:
            self.failed.emit(str(error))
            return
        except Exception:
            self.failed.emit("Falha inesperada ao processar as páginas.")
            return
        self.completed.emit(report)

    def _emit_progress(
        self,
        current: int,
        total: int,
        page_result: PageTemplateResult,
    ) -> None:
        self.progress.emit(current, total, page_result)


class PageTemplateDialog(QDialog):
    """Configure exclusions and names, then generate one PDF for each page."""

    OUTPUT_COLORS = {
        PageOutputStatus.READY: QColor("#1565c0"),
        PageOutputStatus.INCOMPLETE: QColor("#b26a00"),
        PageOutputStatus.CONFLICT: QColor("#c62828"),
        PageOutputStatus.GENERATED: QColor("#2e7d32"),
        PageOutputStatus.ERROR: QColor("#c62828"),
    }

    def __init__(
        self,
        source_path: Path,
        page_count: int,
        template: ExtractionTemplate,
        parent: QWidget | None = None,
        service: PageTemplateService | None = None,
    ) -> None:
        super().__init__(parent)
        self.source_path = source_path
        self.page_count = page_count
        self.template = template
        self._service = service or PageTemplateService()
        self._report: PageTemplateReport | None = None
        self.output_plan: tuple[PageOutputItem, ...] = ()
        self.result_paths: tuple[Path, ...] = ()
        self._thread: QThread | None = None
        self._worker: PageTemplateWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._cancellation = Event()
        self.setWindowTitle("Aplicar template às páginas")
        self.resize(980, 700)

        title = QLabel(f"PDF: {source_path.name} ({page_count} páginas)")
        title.setToolTip(str(source_path))
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        template_label = QLabel(f"Template: {template.name}")

        self.excluded_pages_input = QLineEdit()
        self.excluded_pages_input.setPlaceholderText("Exemplo: 2, 5-7")
        self.excluded_pages_input.textChanged.connect(self._invalidate_analysis)

        self.output_directory_input = QLineEdit(str(source_path.parent))
        self.output_directory_input.setReadOnly(True)
        self.select_directory_button = QPushButton("Escolher pasta...")
        self.select_directory_button.clicked.connect(self._select_directory)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_directory_input, 1)
        output_layout.addWidget(self.select_directory_button)

        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Prefixo opcional")
        self.prefix_input.textChanged.connect(self._refresh_output_plan)

        form = QFormLayout()
        form.addRow("Excluir páginas:", self.excluded_pages_input)
        form.addRow("Pasta de destino:", output_layout)
        form.addRow("Prefixo opcional:", self.prefix_input)

        fields_label = QLabel("Campos usados no nome e ordem:")
        self.field_list = QListWidget()
        for field in template.fields:
            item = QListWidgetItem(field.name)
            item.setData(Qt.ItemDataRole.UserRole, field.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.field_list.addItem(item)
        if self.field_list.count():
            self.field_list.setCurrentRow(0)
        self.field_list.itemChanged.connect(self._refresh_output_plan)

        self.move_up_button = QPushButton("Mover para cima")
        self.move_up_button.clicked.connect(lambda: self._move_current(-1))
        self.move_down_button = QPushButton("Mover para baixo")
        self.move_down_button.clicked.connect(lambda: self._move_current(1))
        order_buttons = QVBoxLayout()
        order_buttons.addWidget(self.move_up_button)
        order_buttons.addWidget(self.move_down_button)
        order_buttons.addStretch(1)
        fields_layout = QHBoxLayout()
        fields_layout.addWidget(self.field_list, 1)
        fields_layout.addLayout(order_buttons)

        self.format_label = QLabel()
        self.format_label.setWordWrap(True)
        self.format_label.setStyleSheet(
            "background: #eeeeee; padding: 8px; border-radius: 4px;"
        )
        self.status_label = QLabel(
            "Configure as páginas e clique em Analisar páginas."
        )
        self.status_label.setWordWrap(True)

        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setHorizontalHeaderLabels(
            ["Página original", "Extração", "Novo arquivo", "Situação"]
        )
        self.preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.preview_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.preview_table.verticalHeader().setVisible(False)
        header = self.preview_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.analyze_button = QPushButton("Analisar páginas")
        self.analyze_button.clicked.connect(self._start_analysis)
        self.generate_button = QPushButton("Gerar PDFs nomeados")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self._generate)
        self.close_button = QPushButton("Fechar")
        self.close_button.clicked.connect(self._close_or_cancel)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.analyze_button)
        actions.addWidget(self.generate_button)
        actions.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(template_label)
        layout.addLayout(form)
        layout.addWidget(fields_label)
        layout.addLayout(fields_layout, 1)
        layout.addWidget(self.format_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.preview_table, 2)
        layout.addLayout(actions)
        self._update_format_label()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def selected_field_ids(self) -> tuple[str, ...]:
        return tuple(
            str(item.data(Qt.ItemDataRole.UserRole))
            for index in range(self.field_list.count())
            if (item := self.field_list.item(index)).checkState()
            == Qt.CheckState.Checked
        )

    def _select_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de destino",
            self.output_directory_input.text(),
        )
        if selected:
            self.output_directory_input.setText(selected)
            self._refresh_output_plan()

    def _move_current(self, offset: int) -> None:
        row = self.field_list.currentRow()
        destination = row + offset
        if row < 0 or not 0 <= destination < self.field_list.count():
            return
        self.field_list.blockSignals(True)
        item = self.field_list.takeItem(row)
        self.field_list.insertItem(destination, item)
        self.field_list.setCurrentRow(destination)
        self.field_list.blockSignals(False)
        self._refresh_output_plan()

    def _invalidate_analysis(self, *_args: object) -> None:
        if self.is_running:
            return
        self._report = None
        self.output_plan = ()
        self.preview_table.setRowCount(0)
        self.generate_button.setEnabled(False)
        self.status_label.setText(
            "As exclusões mudaram. Clique em Analisar páginas novamente."
        )

    def _start_analysis(self) -> None:
        if self.is_running:
            return
        try:
            excluded_pages = parse_excluded_pages(
                self.excluded_pages_input.text(),
                self.page_count,
            )
        except PdfSplitError as error:
            QMessageBox.warning(self, "Exclusão inválida", str(error))
            return
        if len(excluded_pages) == self.page_count:
            QMessageBox.warning(
                self,
                "Todas as páginas excluídas",
                "Deixe ao menos uma página para processar.",
            )
            return

        self._report = None
        self.output_plan = ()
        self.preview_table.setRowCount(0)
        self.generate_button.setEnabled(False)
        self._cancellation = Event()
        total = self.page_count - len(excluded_pages)
        self._progress_dialog = QProgressDialog(
            "Preparando análise...",
            "Cancelar",
            0,
            total,
            self,
        )
        self._progress_dialog.setWindowTitle("Aplicando template às páginas")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setAutoClose(False)
        self._progress_dialog.canceled.connect(self._cancel_analysis)

        thread = QThread(self)
        worker = PageTemplateWorker(
            self._service,
            self.source_path,
            self.template,
            excluded_pages,
            self._cancellation,
        )
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
        self._set_controls_enabled(False)
        thread.start()

    @Slot()
    def _cancel_analysis(self) -> None:
        self._cancellation.set()
        if self._progress_dialog is not None:
            self._progress_dialog.setLabelText(
                "Cancelamento solicitado; finalizando a página atual..."
            )

    @Slot(int, int, object)
    def _on_progress(self, current: int, total: int, result: object) -> None:
        if self._progress_dialog is None:
            return
        page = result if isinstance(result, PageTemplateResult) else None
        page_number = page.page_number if page else current
        self._progress_dialog.setLabelText(
            f"Página {page_number} processada ({current} de {total})"
        )
        self._progress_dialog.setValue(current)

    @Slot(object)
    def _on_completed(self, report: object) -> None:
        self._close_progress()
        if not isinstance(report, PageTemplateReport):
            self._on_failed("A análise retornou um resultado inválido.")
            return
        self._report = report
        state = "Análise cancelada" if report.cancelled else "Análise concluída"
        self.status_label.setText(f"{state}: {report.processed} página(s).")
        self._set_controls_enabled(True)
        self._refresh_output_plan()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._close_progress()
        self._set_controls_enabled(True)
        QMessageBox.critical(self, "Falha ao analisar páginas", message)

    @Slot()
    def _on_thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        self._worker = None
        if thread is not None:
            thread.deleteLater()

    def _refresh_output_plan(self, *_args: object) -> None:
        self._update_format_label()
        if self._report is None:
            return
        field_ids = self.selected_field_ids()
        if not field_ids:
            self.output_plan = ()
            self.preview_table.setRowCount(0)
            self.generate_button.setEnabled(False)
            self.status_label.setText("Selecione ao menos um campo para o nome.")
            return
        try:
            self.output_plan = self._service.build_output_plan(
                self._report,
                self.template.fields,
                RenamePattern(field_ids, self.prefix_input.text()),
                Path(self.output_directory_input.text()),
            )
        except (PageTemplateError, ValueError) as error:
            self.output_plan = ()
            self.preview_table.setRowCount(0)
            self.generate_button.setEnabled(False)
            self.status_label.setText(str(error))
            return
        self._populate_preview(self.output_plan)
        ready_count = sum(
            item.status == PageOutputStatus.READY for item in self.output_plan
        )
        self.generate_button.setEnabled(ready_count > 0)
        self.status_label.setText(
            f"Páginas analisadas: {self._report.processed}. "
            f"Arquivos prontos para gerar: {ready_count}."
        )

    def _update_format_label(self) -> None:
        names = {field.id: field.name for field in self.template.fields}
        parts = []
        if self.prefix_input.text().strip():
            parts.append(self.prefix_input.text().strip())
        parts.extend(f"{{{names[field_id]}}}" for field_id in self.selected_field_ids())
        text = "-".join(parts) if parts else "Selecione ao menos um campo"
        suffix = ".pdf" if parts else ""
        self.format_label.setText(f"Formato: {text}{suffix}")

    def _populate_preview(self, plan: tuple[PageOutputItem, ...]) -> None:
        if self._report is None:
            return
        self.preview_table.setRowCount(len(plan))
        for row, item in enumerate(plan):
            page_result = self._report.pages[item.result_index]
            situation = QTableWidgetItem(item.status.value)
            situation.setForeground(self.OUTPUT_COLORS[item.status])
            if item.message:
                situation.setToolTip(item.message)
            values = (
                QTableWidgetItem(str(item.page_index + 1)),
                QTableWidgetItem(page_result.status.value),
                QTableWidgetItem(item.destination_name),
                situation,
            )
            for column, value in enumerate(values):
                self.preview_table.setItem(row, column, value)

    def _generate(self) -> None:
        if self._report is None or not self.output_plan:
            return
        ready_count = sum(
            item.status == PageOutputStatus.READY for item in self.output_plan
        )
        answer = QMessageBox.question(
            self,
            "Confirmar geração",
            f"Gerar {ready_count} PDF(s) individual(is) já nomeado(s)?\n\n"
            "O PDF original não será alterado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.output_plan = self._service.generate(
                self._report,
                self.output_plan,
            )
        except PageTemplateError as error:
            QMessageBox.critical(self, "Falha ao gerar PDFs", str(error))
            return
        self._populate_preview(self.output_plan)
        self.result_paths = tuple(
            item.destination_path
            for item in self.output_plan
            if item.status == PageOutputStatus.GENERATED
            and item.destination_path is not None
        )
        failures = sum(
            item.status in (PageOutputStatus.ERROR, PageOutputStatus.CONFLICT)
            for item in self.output_plan
        )
        if failures:
            QMessageBox.warning(
                self,
                "Geração concluída com avisos",
                f"Gerados: {len(self.result_paths)}. Falhas ou conflitos: {failures}.",
            )
        else:
            QMessageBox.information(
                self,
                "Geração concluída",
                f"{len(self.result_paths)} PDF(s) gerado(s) com sucesso.",
            )
        self.accept()

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.excluded_pages_input.setEnabled(enabled)
        self.select_directory_button.setEnabled(enabled)
        self.prefix_input.setEnabled(enabled)
        self.field_list.setEnabled(enabled)
        self.move_up_button.setEnabled(enabled)
        self.move_down_button.setEnabled(enabled)
        self.analyze_button.setEnabled(enabled)
        self.generate_button.setEnabled(enabled and bool(self.output_plan))
        self.close_button.setText("Fechar" if enabled else "Cancelar análise")

    def _close_progress(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog.deleteLater()
            self._progress_dialog = None

    def _close_or_cancel(self) -> None:
        if self.is_running:
            self._cancel_analysis()
        else:
            self.reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Cancel active analysis before destroying the worker thread."""
        self._cancellation.set()
        if self._thread is not None and self._thread.isRunning():
            if not self._thread.wait(30_000):
                event.ignore()
                return
        event.accept()
