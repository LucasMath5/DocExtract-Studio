"""Dialog for composing and previewing PDF names from extracted fields."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pdf_extractor.core.pdf_rename_service import (
    PdfRenameService,
    RenamePattern,
    RenamePlanItem,
    RenamePlanStatus,
)
from pdf_extractor.models.batch_result import BatchDocumentResult
from pdf_extractor.models.extraction_field import ExtractionField


class PdfRenameDialog(QDialog):
    """Let the user select filename parts and inspect every proposed rename."""

    STATUS_COLORS = {
        RenamePlanStatus.READY: QColor("#1565c0"),
        RenamePlanStatus.NO_CHANGE: QColor("#616161"),
        RenamePlanStatus.INVALID: QColor("#b26a00"),
        RenamePlanStatus.CONFLICT: QColor("#c62828"),
        RenamePlanStatus.RENAMED: QColor("#2e7d32"),
        RenamePlanStatus.ERROR: QColor("#c62828"),
    }

    def __init__(
        self,
        documents: tuple[BatchDocumentResult, ...],
        fields: tuple[ExtractionField, ...],
        parent: QWidget | None = None,
        service: PdfRenameService | None = None,
    ) -> None:
        super().__init__(parent)
        self._documents = documents
        self._fields = fields
        self._service = service or PdfRenameService()
        self.plan: tuple[RenamePlanItem, ...] = ()
        self.result_items: tuple[RenamePlanItem, ...] = ()
        self.setWindowTitle("Renomear PDFs pelos campos")
        self.resize(920, 620)

        instruction = QLabel(
            "Informe um prefixo opcional, escolha os campos e organize a ordem "
            "das partes do nome. O separador utilizado será hífen (-)."
        )
        instruction.setWordWrap(True)

        prefix_label = QLabel("Prefixo opcional:")
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Exemplo: contrato")
        self.prefix_input.textChanged.connect(self._refresh_plan)

        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(prefix_label)
        prefix_layout.addWidget(self.prefix_input, 1)

        fields_label = QLabel("Campos utilizados e ordem:")
        self.field_list = QListWidget()
        self.field_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        for field in fields:
            item = QListWidgetItem(field.name)
            item.setData(Qt.ItemDataRole.UserRole, field.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.field_list.addItem(item)
        if self.field_list.count():
            self.field_list.setCurrentRow(0)
        self.field_list.itemChanged.connect(self._refresh_plan)

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

        self.example_label = QLabel()
        self.example_label.setWordWrap(True)
        self.example_label.setStyleSheet(
            "background: #eeeeee; padding: 8px; border-radius: 4px;"
        )

        preview_label = QLabel("Prévia antes de renomear")
        preview_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.preview_table = QTableWidget(0, 3)
        self.preview_table.setHorizontalHeaderLabels(
            ["Nome atual", "Novo nome", "Situação"]
        )
        self.preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.preview_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.preview_table.verticalHeader().setVisible(False)
        preview_header = self.preview_table.horizontalHeader()
        preview_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        preview_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        preview_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.rename_button = QPushButton("Renomear arquivos")
        self.rename_button.clicked.connect(self._apply_plan)
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)

        action_layout = QHBoxLayout()
        action_layout.addStretch(1)
        action_layout.addWidget(self.rename_button)
        action_layout.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(instruction)
        layout.addLayout(prefix_layout)
        layout.addWidget(fields_label)
        layout.addLayout(fields_layout, 1)
        layout.addWidget(self.example_label)
        layout.addWidget(preview_label)
        layout.addWidget(self.preview_table, 2)
        layout.addLayout(action_layout)
        self._refresh_plan()

    def selected_field_ids(self) -> tuple[str, ...]:
        """Return checked field identifiers in their current visual order."""
        return tuple(
            str(item.data(Qt.ItemDataRole.UserRole))
            for index in range(self.field_list.count())
            if (item := self.field_list.item(index)).checkState()
            == Qt.CheckState.Checked
        )

    def _move_current(self, offset: int) -> None:
        current_row = self.field_list.currentRow()
        destination_row = current_row + offset
        if current_row < 0 or not 0 <= destination_row < self.field_list.count():
            return
        self.field_list.blockSignals(True)
        item = self.field_list.takeItem(current_row)
        self.field_list.insertItem(destination_row, item)
        self.field_list.setCurrentRow(destination_row)
        self.field_list.blockSignals(False)
        self._refresh_plan()

    def _refresh_plan(self, *_args: object) -> None:
        field_ids = self.selected_field_ids()
        self._update_example(field_ids)
        if not field_ids:
            self.plan = ()
            self.preview_table.setRowCount(0)
            self.rename_button.setEnabled(False)
            return
        pattern = RenamePattern(
            prefix=self.prefix_input.text(),
            field_ids=field_ids,
        )
        self.plan = self._service.build_plan(
            self._documents,
            self._fields,
            pattern,
        )
        self._populate_preview(self.plan)
        self.rename_button.setEnabled(
            any(item.status == RenamePlanStatus.READY for item in self.plan)
        )

    def _update_example(self, field_ids: tuple[str, ...]) -> None:
        names_by_id = {field.id: field.name for field in self._fields}
        parts = []
        prefix = self.prefix_input.text().strip()
        if prefix:
            parts.append(prefix)
        parts.extend(f"{{{names_by_id[field_id]}}}" for field_id in field_ids)
        example = "-".join(parts) if parts else "Selecione ao menos um campo"
        suffix = ".pdf" if parts else ""
        self.example_label.setText(f"Formato: {example}{suffix}")

    def _populate_preview(self, items: tuple[RenamePlanItem, ...]) -> None:
        self.preview_table.setRowCount(len(items))
        for row, item in enumerate(items):
            status_item = QTableWidgetItem(item.status.value)
            status_item.setForeground(self.STATUS_COLORS[item.status])
            if item.message:
                status_item.setToolTip(item.message)
            values = (
                QTableWidgetItem(item.source_path.name),
                QTableWidgetItem(item.destination_name),
                status_item,
            )
            if item.message:
                values[1].setToolTip(item.message)
            for column, value in enumerate(values):
                self.preview_table.setItem(row, column, value)

    def _apply_plan(self) -> None:
        ready_count = sum(
            item.status == RenamePlanStatus.READY for item in self.plan
        )
        if ready_count == 0:
            return
        answer = QMessageBox.question(
            self,
            "Confirmar renomeação",
            f"Renomear {ready_count} arquivo(s)?\n\n"
            "Os PDFs não serão sobrescritos se houver conflito.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.result_items = self._service.apply(self.plan)
        renamed_count = sum(
            item.status == RenamePlanStatus.RENAMED for item in self.result_items
        )
        failure_count = sum(
            item.status in (RenamePlanStatus.ERROR, RenamePlanStatus.CONFLICT)
            for item in self.result_items
        )
        self._populate_preview(self.result_items)
        if failure_count:
            QMessageBox.warning(
                self,
                "Renomeação concluída com avisos",
                f"Renomeados: {renamed_count}. Falhas ou conflitos: {failure_count}.",
            )
        else:
            QMessageBox.information(
                self,
                "Renomeação concluída",
                f"{renamed_count} arquivo(s) renomeado(s) com sucesso.",
            )
        self.accept()
