"""Widget used to display a rendered PDF page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget


class PdfViewer(QWidget):
    """Display the current file name and one rendered PDF page."""

    def __init__(self) -> None:
        super().__init__()

        self.file_name_label = QLabel()
        self.file_name_label.setObjectName("fileNameLabel")
        self.file_name_label.setStyleSheet("font-weight: 600; padding: 8px;")

        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setStyleSheet("background-color: #525659; color: #eeeeee;")

        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.page_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.file_name_label)
        layout.addWidget(self.scroll_area, 1)

        self.show_empty_state()

    def show_empty_state(self) -> None:
        """Show instructions while no document is loaded."""
        self.file_name_label.clear()
        self.file_name_label.hide()
        self.page_label.clear()
        self.page_label.setMinimumSize(0, 0)
        self.page_label.setText(
            "Nenhum documento carregado.\n\n"
            "Use Arquivo > Abrir PDF para começar."
        )

    def show_page(self, file_name: str, png_data: bytes) -> None:
        """Decode and show a rendered PNG page."""
        pixmap = QPixmap()
        if not pixmap.loadFromData(png_data, "PNG"):
            raise ValueError("A imagem renderizada do PDF é inválida.")

        self.file_name_label.setText(file_name)
        self.file_name_label.show()
        self.page_label.clear()
        self.page_label.setPixmap(pixmap)
        self.page_label.setMinimumSize(pixmap.size())
