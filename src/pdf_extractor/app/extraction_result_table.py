"""Read-only table for native PDF extraction results."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pdf_extractor.models.extraction_result import ExtractionResult, ExtractionStatus


class ExtractionResultTable(QWidget):
    """Present extraction values and statuses without allowing edits yet."""

    export_csv_requested = Signal()
    export_excel_requested = Signal()

    STATUS_COLORS = {
        ExtractionStatus.SUCCESS: QColor("#2e7d32"),
        ExtractionStatus.EMPTY: QColor("#b26a00"),
        ExtractionStatus.ERROR: QColor("#c62828"),
    }

    def __init__(self) -> None:
        super().__init__()
        self.title_label = QLabel("Resultados da extração")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 600;")

        self.export_csv_button = QPushButton("Exportar CSV")
        self.export_csv_button.setEnabled(False)
        self.export_csv_button.clicked.connect(self.export_csv_requested.emit)

        self.export_excel_button = QPushButton("Exportar Excel")
        self.export_excel_button.setEnabled(False)
        self.export_excel_button.clicked.connect(self.export_excel_requested.emit)

        title_layout = QHBoxLayout()
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.export_csv_button)
        title_layout.addWidget(self.export_excel_button)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Campo", "Página", "Valor extraído", "Método", "Status"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.addLayout(title_layout)
        layout.addWidget(self.table)

    def set_results(self, results: tuple[ExtractionResult, ...]) -> None:
        """Replace all rows with the latest extraction results."""
        self.table.setRowCount(len(results))
        for row, result in enumerate(results):
            items = (
                QTableWidgetItem(result.field_name),
                QTableWidgetItem(str(result.page_index + 1)),
                QTableWidgetItem(result.value),
                QTableWidgetItem(result.method.value if result.method else "-"),
                QTableWidgetItem(result.status.value),
            )
            for column, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole, result.field_id)
                self.table.setItem(row, column, item)
            status_item = items[4]
            status_item.setForeground(self.STATUS_COLORS[result.status])
            if result.error_message:
                status_item.setToolTip(result.error_message)
                items[2].setToolTip(result.error_message)
        has_results = bool(results)
        self.export_csv_button.setEnabled(has_results)
        self.export_excel_button.setEnabled(has_results)

    def clear_results(self) -> None:
        """Remove stale rows after document or field changes."""
        self.table.setRowCount(0)
        self.export_csv_button.setEnabled(False)
        self.export_excel_button.setEnabled(False)
