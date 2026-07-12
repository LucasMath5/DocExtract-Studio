"""Dialog for configuring, previewing, and generating split PDF files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pdf_extractor.core.pdf_split_service import (
    PdfSplitError,
    PdfSplitPlan,
    PdfSplitService,
    format_page_numbers,
    parse_excluded_pages,
)


class PdfSplitDialog(QDialog):
    """Collect split settings and show every output before writing files."""

    def __init__(
        self,
        source_path: Path,
        page_count: int,
        parent: QWidget | None = None,
        service: PdfSplitService | None = None,
    ) -> None:
        super().__init__(parent)
        self.source_path = source_path
        self.page_count = page_count
        self._service = service or PdfSplitService()
        self.plan: PdfSplitPlan | None = None
        self.result_paths: tuple[Path, ...] = ()
        self.setWindowTitle("Dividir PDF")
        self.resize(850, 560)

        source_label = QLabel(f"Arquivo: {source_path.name}")
        source_label.setToolTip(str(source_path))
        source_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        pages_label = QLabel(f"Total de páginas: {page_count}")

        self.pages_per_file_spin = QSpinBox()
        self.pages_per_file_spin.setRange(1, page_count)
        self.pages_per_file_spin.setValue(1)
        self.pages_per_file_spin.setSuffix(" página(s) por arquivo")
        self.pages_per_file_spin.valueChanged.connect(self._refresh_plan)

        self.excluded_pages_input = QLineEdit()
        self.excluded_pages_input.setPlaceholderText("Exemplo: 2, 5-7")
        self.excluded_pages_input.setToolTip(
            "Páginas que não serão incluídas em nenhum PDF gerado"
        )
        self.excluded_pages_input.textChanged.connect(self._refresh_plan)

        self.output_directory_input = QLineEdit(str(source_path.parent))
        self.output_directory_input.setReadOnly(True)
        self.output_directory_input.setToolTip(str(source_path.parent))
        self.select_directory_button = QPushButton("Escolher pasta...")
        self.select_directory_button.clicked.connect(self._select_directory)

        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_directory_input, 1)
        output_layout.addWidget(self.select_directory_button)

        form = QFormLayout()
        form.addRow("Tamanho das partes:", self.pages_per_file_spin)
        form.addRow("Excluir páginas:", self.excluded_pages_input)
        form.addRow("Pasta de destino:", output_layout)

        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("color: #c62828; padding: 4px;")

        preview_label = QLabel("Prévia dos arquivos que serão gerados")
        preview_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.preview_table = QTableWidget(0, 3)
        self.preview_table.setHorizontalHeaderLabels(
            ["Parte", "Páginas originais", "Nome do arquivo"]
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

        self.generate_button = QPushButton("Gerar PDFs")
        self.generate_button.clicked.connect(self._generate)
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.generate_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(source_label)
        layout.addWidget(pages_label)
        layout.addLayout(form)
        layout.addWidget(self.validation_label)
        layout.addWidget(preview_label)
        layout.addWidget(self.preview_table, 1)
        layout.addLayout(buttons)
        self._refresh_plan()

    def _select_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de destino",
            self.output_directory_input.text(),
        )
        if not selected:
            return
        self.output_directory_input.setText(selected)
        self.output_directory_input.setToolTip(selected)
        self._refresh_plan()

    def _refresh_plan(self, *_args: object) -> None:
        try:
            excluded_pages = parse_excluded_pages(
                self.excluded_pages_input.text(),
                self.page_count,
            )
            self.plan = self._service.build_plan(
                self.source_path,
                self.page_count,
                self.pages_per_file_spin.value(),
                excluded_pages,
                Path(self.output_directory_input.text()),
            )
        except PdfSplitError as error:
            self.plan = None
            self.validation_label.setStyleSheet("color: #c62828; padding: 4px;")
            self.validation_label.setText(str(error))
            self.preview_table.setRowCount(0)
            self.generate_button.setEnabled(False)
            return

        excluded_label = format_page_numbers(tuple(sorted(excluded_pages)))
        message = f"Serão gerados {len(self.plan.parts)} arquivo(s)."
        if excluded_label:
            message += f" Páginas excluídas: {excluded_label}."
        self.validation_label.setStyleSheet("color: #2e7d32; padding: 4px;")
        self.validation_label.setText(message)
        self.generate_button.setEnabled(True)
        self._populate_preview()

    def _populate_preview(self) -> None:
        if self.plan is None:
            self.preview_table.setRowCount(0)
            return
        self.preview_table.setRowCount(len(self.plan.parts))
        for row, part in enumerate(self.plan.parts):
            values = (
                QTableWidgetItem(str(part.part_number)),
                QTableWidgetItem(part.page_label),
                QTableWidgetItem(part.destination_path.name),
            )
            values[2].setToolTip(str(part.destination_path))
            for column, value in enumerate(values):
                self.preview_table.setItem(row, column, value)

    def _generate(self) -> None:
        if self.plan is None:
            return
        answer = QMessageBox.question(
            self,
            "Confirmar divisão",
            f"Gerar {len(self.plan.parts)} novo(s) arquivo(s) PDF?\n\n"
            "O PDF original não será alterado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.result_paths = self._service.split(self.plan)
        except PdfSplitError as error:
            QMessageBox.critical(self, "Falha ao dividir PDF", str(error))
            self._refresh_plan()
            return
        QMessageBox.information(
            self,
            "Divisão concluída",
            f"{len(self.result_paths)} arquivo(s) criado(s) em:\n"
            f"{self.plan.output_directory}",
        )
        self.accept()
