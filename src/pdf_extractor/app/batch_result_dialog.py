"""Final report window for batch PDF extraction."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pdf_extractor.exporters.base import (
    ExportError,
    TabularExporter,
    build_batch_export_dataset,
)
from pdf_extractor.exporters.csv_exporter import CsvExporter
from pdf_extractor.exporters.excel_exporter import ExcelExporter
from pdf_extractor.models.batch_result import BatchDocumentStatus, BatchReport
from pdf_extractor.models.extraction_template import ExtractionTemplate


class BatchResultDialog(QDialog):
    """Display per-file errors, summary counts, and consolidated exports."""

    STATUS_COLORS = {
        BatchDocumentStatus.SUCCESS: QColor("#2e7d32"),
        BatchDocumentStatus.REVIEW_NEEDED: QColor("#b26a00"),
        BatchDocumentStatus.FAILURE: QColor("#c62828"),
    }

    def __init__(
        self,
        report: BatchReport,
        template: ExtractionTemplate,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.report = report
        self.template = template
        self.dataset = build_batch_export_dataset(
            template.fields,
            report.documents,
        )
        self.setWindowTitle("Resultado do processamento em lote")
        self.resize(900, 520)

        state = "Cancelado" if report.cancelled else "Concluído"
        self.summary_label = QLabel(
            f"{state} — Total: {report.total} | Processados: {report.processed} | "
            f"Sucesso: {report.success_count} | "
            f"Atenção: {report.review_count} | Falhas: {report.failure_count}"
        )
        self.summary_label.setStyleSheet("font-size: 14px; font-weight: 600;")

        self.preview_label = QLabel("Prévia da tabela consolidada")
        self.preview_label.setStyleSheet("font-size: 13px; font-weight: 600;")

        self.table = QTableWidget(
            len(self.dataset.rows),
            len(self.dataset.headers),
        )
        self.table.setHorizontalHeaderLabels(self.dataset.headers)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self._populate_table()

        self.export_csv_button = QPushButton("Exportar consolidado CSV")
        self.export_csv_button.setEnabled(bool(report.documents))
        self.export_csv_button.clicked.connect(self._export_csv)

        self.export_excel_button = QPushButton("Exportar consolidado Excel")
        self.export_excel_button.setEnabled(bool(report.documents))
        self.export_excel_button.clicked.connect(self._export_excel)

        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.close)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.export_csv_button)
        button_layout.addWidget(self.export_excel_button)
        button_layout.addStretch(1)
        button_layout.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.table, 1)
        layout.addLayout(button_layout)

    def _populate_table(self) -> None:
        for row, (document, values) in enumerate(
            zip(self.report.documents, self.dataset.rows, strict=True)
        ):
            items = tuple(QTableWidgetItem(value) for value in values)
            status_item = items[1]
            status_item.setForeground(self.STATUS_COLORS[document.status])
            status_item.setToolTip(document.status.value)
            if document.error_message:
                items[2].setToolTip(document.error_message)
            for column, item in enumerate(items):
                self.table.setItem(row, column, item)

    def _export_csv(self) -> None:
        self._export(
            CsvExporter(),
            "Exportar lote para CSV",
            "Arquivos CSV (*.csv)",
            ".csv",
        )

    def _export_excel(self) -> None:
        self._export(
            ExcelExporter(),
            "Exportar lote para Excel",
            "Planilhas Excel (*.xlsx)",
            ".xlsx",
        )

    def _export(
        self,
        exporter: TabularExporter,
        title: str,
        file_filter: str,
        suffix: str,
    ) -> None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            title,
            "",
            file_filter,
        )
        if not selected_path:
            return
        file_path = Path(selected_path)
        if file_path.suffix.lower() != suffix:
            file_path = file_path.with_suffix(suffix)
        try:
            exporter.export(file_path, self.dataset)
        except ExportError as error:
            QMessageBox.critical(self, "Falha na exportação", str(error))
            return
        QMessageBox.information(
            self,
            "Exportação concluída",
            f"Arquivo consolidado salvo em:\n{file_path}",
        )
