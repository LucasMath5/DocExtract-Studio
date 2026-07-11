"""Interactive canvas for a rendered PDF page and one selected region."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from pdf_extractor.models.field_region import FieldRegion


class PdfPageCanvas(QWidget):
    """Render a PDF page and let the user draw one rectangular region."""

    region_selected = Signal(object)
    selection_clear_requested = Signal()
    MINIMUM_DRAG_SIZE = 4.0

    def __init__(self) -> None:
        super().__init__()
        self._pixmap: QPixmap | None = None
        self._empty_message = ""
        self._page_index = 0
        self._pdf_width = 0.0
        self._pdf_height = 0.0
        self._selected_region: FieldRegion | None = None
        self._drag_start: QPointF | None = None
        self._drag_current: QPointF | None = None

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    def pixmap(self) -> QPixmap | None:
        """Return the currently displayed pixmap for UI tests and inspection."""
        return self._pixmap

    def text(self) -> str:
        """Return the empty-state text when no page is displayed."""
        return self._empty_message

    def clear_page(self, message: str) -> None:
        """Remove the rendered page and show an empty-state message."""
        self._pixmap = None
        self._empty_message = message
        self._page_index = 0
        self._pdf_width = 0.0
        self._pdf_height = 0.0
        self._drag_start = None
        self._drag_current = None
        self.setMinimumSize(0, 0)
        self.unsetCursor()
        self.update()

    def set_page(
        self,
        pixmap: QPixmap,
        page_index: int,
        pdf_width: float,
        pdf_height: float,
    ) -> None:
        """Display a rendered page with its native PDF dimensions."""
        if pixmap.isNull() or pdf_width <= 0 or pdf_height <= 0:
            raise ValueError("A página renderizada possui dimensões inválidas.")

        self._pixmap = pixmap
        self._empty_message = ""
        self._page_index = page_index
        self._pdf_width = pdf_width
        self._pdf_height = pdf_height
        self._drag_start = None
        self._drag_current = None
        self.setMinimumSize(pixmap.size())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    def set_region(self, region: FieldRegion | None) -> None:
        """Set the domain region that should be drawn over its page."""
        self._selected_region = region
        self.update()

    def page_display_rect(self) -> QRectF:
        """Return the rendered page rectangle in canvas coordinates."""
        if self._pixmap is None:
            return QRectF()
        left = max(0.0, (self.width() - self._pixmap.width()) / 2)
        top = max(0.0, (self.height() - self._pixmap.height()) / 2)
        return QRectF(left, top, self._pixmap.width(), self._pixmap.height())

    def selection_display_rect(self) -> QRectF | None:
        """Return the selected region in canvas coordinates when visible."""
        if (
            self._selected_region is None
            or self._selected_region.page_index != self._page_index
            or self._pixmap is None
        ):
            return None

        page_rect = self.page_display_rect()
        region = self._selected_region
        return QRectF(
            page_rect.left() + region.x * page_rect.width() / self._pdf_width,
            page_rect.top() + region.y * page_rect.height() / self._pdf_height,
            region.width * page_rect.width() / self._pdf_width,
            region.height * page_rect.height() / self._pdf_height,
        )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint the page, empty state, and current selection overlay."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#525659"))

        if self._pixmap is None:
            painter.setPen(QColor("#eeeeee"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._empty_message,
            )
            return

        page_rect = self.page_display_rect()
        painter.drawPixmap(page_rect.topLeft(), self._pixmap)

        selection_rect = self._active_selection_rect()
        if selection_rect is not None:
            painter.setPen(QPen(QColor("#0078d4"), 2, Qt.PenStyle.SolidLine))
            painter.setBrush(QColor(0, 120, 212, 55))
            painter.drawRect(selection_rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Start a rectangular selection inside the rendered page."""
        if event.button() != Qt.MouseButton.LeftButton or self._pixmap is None:
            super().mousePressEvent(event)
            return

        page_rect = self.page_display_rect()
        if not page_rect.contains(event.position()):
            return

        self.setFocus()
        page_position = self._clamped_page_position(event.position())
        self._drag_start = page_position
        self._drag_current = page_position
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Update the temporary selection while dragging."""
        if self._drag_start is None:
            super().mouseMoveEvent(event)
            return
        self._drag_current = self._clamped_page_position(event.position())
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Finish the drag and emit a region in native PDF coordinates."""
        if event.button() != Qt.MouseButton.LeftButton or self._drag_start is None:
            super().mouseReleaseEvent(event)
            return

        self._drag_current = self._clamped_page_position(event.position())
        page_pixel_rect = QRectF(self._drag_start, self._drag_current).normalized()
        self._drag_start = None
        self._drag_current = None

        if (
            page_pixel_rect.width() < self.MINIMUM_DRAG_SIZE
            or page_pixel_rect.height() < self.MINIMUM_DRAG_SIZE
        ):
            self.update()
            return

        region = self._page_pixels_to_region(page_pixel_rect)
        self._selected_region = region
        self.region_selected.emit(region)
        self.update()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Cancel an active drag or request deletion of the saved selection."""
        if event.key() == Qt.Key.Key_Escape and self._drag_start is not None:
            self._drag_start = None
            self._drag_current = None
            self.update()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected_region is not None:
                self.selection_clear_requested.emit()
                event.accept()
                return
        super().keyPressEvent(event)

    def _active_selection_rect(self) -> QRectF | None:
        if self._drag_start is not None and self._drag_current is not None:
            page_rect = self.page_display_rect()
            drag_rect = QRectF(self._drag_start, self._drag_current).normalized()
            drag_rect.translate(page_rect.topLeft())
            return drag_rect
        return self.selection_display_rect()

    def _clamped_page_position(self, widget_position: QPointF) -> QPointF:
        page_rect = self.page_display_rect()
        return QPointF(
            min(max(widget_position.x() - page_rect.left(), 0.0), page_rect.width()),
            min(max(widget_position.y() - page_rect.top(), 0.0), page_rect.height()),
        )

    def _page_pixels_to_region(self, page_rect: QRectF) -> FieldRegion:
        if self._pixmap is None:
            raise ValueError("Nenhuma página está disponível para seleção.")
        return FieldRegion(
            page_index=self._page_index,
            x=page_rect.x() * self._pdf_width / self._pixmap.width(),
            y=page_rect.y() * self._pdf_height / self._pixmap.height(),
            width=page_rect.width() * self._pdf_width / self._pixmap.width(),
            height=page_rect.height() * self._pdf_height / self._pixmap.height(),
        )
