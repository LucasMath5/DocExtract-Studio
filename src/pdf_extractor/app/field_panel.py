"""Side panel for selecting and managing named extraction fields."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pdf_extractor.models.extraction_field import ExtractionField


class FieldPanel(QWidget):
    """Display ordered fields and expose selection, rename, and delete actions."""

    field_selected = Signal(str)
    rename_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(240)
        self.setMaximumWidth(340)

        self.title_label = QLabel("Campos mapeados (0)")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 600;")

        self.field_list = QListWidget()
        self.field_list.setAlternatingRowColors(True)
        self.field_list.currentItemChanged.connect(self._emit_selection)

        self.rename_button = QPushButton("Renomear")
        self.rename_button.setEnabled(False)
        self.rename_button.clicked.connect(self._emit_rename)

        self.delete_button = QPushButton("Excluir")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._emit_delete)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.rename_button)
        button_layout.addWidget(self.delete_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.field_list, 1)
        layout.addLayout(button_layout)

    def set_fields(
        self,
        fields: tuple[ExtractionField, ...],
        selected_id: str | None,
    ) -> None:
        """Replace panel contents while preserving the requested selection."""
        self.field_list.blockSignals(True)
        self.field_list.clear()
        selected_item: QListWidgetItem | None = None
        for field in fields:
            item = QListWidgetItem(f"{field.name}\nPágina {field.page_index + 1}")
            item.setData(Qt.ItemDataRole.UserRole, field.id)
            self.field_list.addItem(item)
            if field.id == selected_id:
                selected_item = item
        self.field_list.setCurrentItem(selected_item)
        self.field_list.blockSignals(False)

        self.title_label.setText(f"Campos mapeados ({len(fields)})")
        has_selection = selected_item is not None
        self.rename_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _current_field_id(self) -> str | None:
        item = self.field_list.currentItem()
        if item is None:
            return None
        return str(item.data(Qt.ItemDataRole.UserRole))

    def _emit_selection(self, current: QListWidgetItem | None) -> None:
        has_selection = current is not None
        self.rename_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        if current is not None:
            self.field_selected.emit(str(current.data(Qt.ItemDataRole.UserRole)))

    def _emit_rename(self) -> None:
        field_id = self._current_field_id()
        if field_id is not None:
            self.rename_requested.emit(field_id)

    def _emit_delete(self) -> None:
        field_id = self._current_field_id()
        if field_id is not None:
            self.delete_requested.emit(field_id)
