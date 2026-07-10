"""PDF loading and rendering services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz


class PdfServiceError(Exception):
    """Represent an expected error while loading or rendering a PDF."""


@dataclass(frozen=True, slots=True)
class PdfDocumentInfo:
    """Expose non-sensitive information about the loaded document."""

    file_name: str
    page_count: int


class PdfService:
    """Manage one PDF document and render its pages with PyMuPDF."""

    def __init__(self) -> None:
        self._document: fitz.Document | None = None
        self._file_name: str | None = None

    @property
    def document_info(self) -> PdfDocumentInfo | None:
        """Return information about the current document, when available."""
        if self._document is None or self._file_name is None:
            return None
        return PdfDocumentInfo(self._file_name, self._document.page_count)

    def open_document(self, file_path: str | Path) -> PdfDocumentInfo:
        """Open a PDF after validating its extension and basic structure."""
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            raise PdfServiceError("Selecione um arquivo com a extensão .pdf.")

        try:
            new_document = fitz.open(str(path))
        except (OSError, RuntimeError, ValueError) as error:
            raise PdfServiceError(
                "Não foi possível abrir o PDF. O arquivo pode estar inválido ou corrompido."
            ) from error

        if new_document.page_count < 1:
            new_document.close()
            raise PdfServiceError("O PDF selecionado não possui páginas.")

        previous_document = self._document
        self._document = new_document
        self._file_name = path.name
        if previous_document is not None:
            previous_document.close()

        return PdfDocumentInfo(path.name, new_document.page_count)

    def render_page(self, page_index: int = 0, scale: float = 1.0) -> bytes:
        """Render a page as PNG bytes at the requested scale."""
        if self._document is None:
            raise PdfServiceError("Nenhum documento PDF está carregado.")
        if not 0 <= page_index < self._document.page_count:
            raise PdfServiceError("A página solicitada não existe neste documento.")
        if scale <= 0:
            raise PdfServiceError("A escala de renderização deve ser maior que zero.")

        try:
            page = self._document.load_page(page_index)
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale),
                colorspace=fitz.csRGB,
                alpha=False,
            )
            return pixmap.tobytes("png")
        except (OSError, RuntimeError, ValueError) as error:
            raise PdfServiceError("Não foi possível renderizar a página do PDF.") from error

    def close(self) -> None:
        """Release the loaded document and its operating-system resources."""
        if self._document is not None:
            self._document.close()
        self._document = None
        self._file_name = None
