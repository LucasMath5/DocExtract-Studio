"""Widget used to display a rendered PDF page."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pdf_extractor.app.pdf_page_canvas import PdfPageCanvas
from pdf_extractor.models.field_region import FieldRegion


class PdfViewer(QWidget):
    """Display the current file name and one rendered PDF page."""

    previous_page_requested = Signal()
    next_page_requested = Signal()
    zoom_out_requested = Signal()
    zoom_in_requested = Signal()
    reset_zoom_requested = Signal()
    region_selected = Signal(object)
    selection_clear_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.file_name_label = QLabel()
        self.file_name_label.setObjectName("fileNameLabel")
        self.file_name_label.setStyleSheet("font-weight: 600; padding: 8px;")
        self.file_name_label.setMaximumWidth(280)

        self.previous_button = QPushButton("Anterior")
        self.previous_button.setToolTip("Exibir a página anterior (seta para esquerda)")
        self.previous_button.clicked.connect(self.previous_page_requested.emit)

        self.page_indicator = QLabel("Página 0 de 0")
        self.page_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_indicator.setMinimumWidth(105)

        self.next_button = QPushButton("Próxima")
        self.next_button.setToolTip("Exibir a próxima página (seta para direita)")
        self.next_button.clicked.connect(self.next_page_requested.emit)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)

        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.setToolTip("Diminuir zoom (Ctrl+-)")
        self.zoom_out_button.setFixedWidth(36)
        self.zoom_out_button.clicked.connect(self.zoom_out_requested.emit)

        self.zoom_indicator = QLabel("100%")
        self.zoom_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_indicator.setMinimumWidth(52)

        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setToolTip("Aumentar zoom (Ctrl++)")
        self.zoom_in_button.setFixedWidth(36)
        self.zoom_in_button.clicked.connect(self.zoom_in_requested.emit)

        self.reset_zoom_button = QPushButton("Redefinir")
        self.reset_zoom_button.setToolTip("Restaurar zoom para 100%")
        self.reset_zoom_button.clicked.connect(self.reset_zoom_requested.emit)

        selection_separator = QFrame()
        selection_separator.setFrameShape(QFrame.Shape.VLine)
        selection_separator.setFrameShadow(QFrame.Shadow.Sunken)

        self.clear_selection_button = QPushButton("Limpar seleção")
        self.clear_selection_button.setToolTip("Excluir a seleção atual (Delete)")
        self.clear_selection_button.setEnabled(False)
        self.clear_selection_button.clicked.connect(
            self.selection_clear_requested.emit
        )

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(8, 6, 8, 6)
        controls_layout.addWidget(self.file_name_label)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.previous_button)
        controls_layout.addWidget(self.page_indicator)
        controls_layout.addWidget(self.next_button)
        controls_layout.addWidget(separator)
        controls_layout.addWidget(self.zoom_out_button)
        controls_layout.addWidget(self.zoom_indicator)
        controls_layout.addWidget(self.zoom_in_button)
        controls_layout.addWidget(self.reset_zoom_button)
        controls_layout.addWidget(selection_separator)
        controls_layout.addWidget(self.clear_selection_button)

        self.page_canvas = PdfPageCanvas()
        self.page_canvas.region_selected.connect(self.region_selected.emit)
        self.page_canvas.selection_clear_requested.connect(
            self.selection_clear_requested.emit
        )

        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.page_canvas)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(controls_layout)
        layout.addWidget(self.scroll_area, 1)

        self.show_empty_state()

    def show_empty_state(self) -> None:
        """Show instructions while no document is loaded."""
        self.file_name_label.clear()
        self.page_canvas.clear_page(
            "Nenhum documento carregado.\n\n"
            "Use Arquivo > Abrir PDF para começar."
        )
        self.set_selected_region(None)
        self.update_controls(0, 0, 100, 50, 300)

    def show_page(
        self,
        file_name: str,
        png_data: bytes,
        page_index: int,
        pdf_width: float,
        pdf_height: float,
    ) -> None:
        """Decode and show a rendered PNG page."""
        pixmap = QPixmap()
        if not pixmap.loadFromData(png_data, "PNG"):
            raise ValueError("A imagem renderizada do PDF é inválida.")

        displayed_name = self.file_name_label.fontMetrics().elidedText(
            file_name,
            Qt.TextElideMode.ElideMiddle,
            250,
        )
        self.file_name_label.setText(displayed_name)
        self.file_name_label.setToolTip(file_name)
        self.page_canvas.set_page(pixmap, page_index, pdf_width, pdf_height)
        self._scroll_to_page_start()

    def set_selected_region(self, region: FieldRegion | None) -> None:
        """Display the selected region and synchronize its delete control."""
        self.page_canvas.set_region(region)
        self.clear_selection_button.setEnabled(region is not None)

    def update_controls(
        self,
        page_index: int,
        page_count: int,
        zoom_percent: int,
        minimum_zoom: int,
        maximum_zoom: int,
    ) -> None:
        """Update indicators and enable only controls that can be used."""
        has_document = page_count > 0
        page_number = page_index + 1 if has_document else 0

        self.page_indicator.setText(f"Página {page_number} de {page_count}")
        self.zoom_indicator.setText(f"{zoom_percent}%")
        self.previous_button.setEnabled(has_document and page_index > 0)
        self.next_button.setEnabled(has_document and page_index < page_count - 1)
        self.zoom_out_button.setEnabled(
            has_document and zoom_percent > minimum_zoom
        )
        self.zoom_in_button.setEnabled(has_document and zoom_percent < maximum_zoom)
        self.reset_zoom_button.setEnabled(has_document and zoom_percent != 100)

    def _scroll_to_page_start(self) -> None:
        """Move the viewport to the top-left after rendering a page."""
        self.scroll_area.horizontalScrollBar().setValue(0)
        self.scroll_area.verticalScrollBar().setValue(0)
