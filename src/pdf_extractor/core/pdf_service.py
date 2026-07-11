"""PDF loading and rendering services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from pdf_extractor.models.field_region import FieldRegion


class PdfServiceError(Exception):
    """Represent an expected error while loading or rendering a PDF."""


@dataclass(frozen=True, slots=True)
class PdfDocumentInfo:
    """Expose non-sensitive information about the loaded document."""

    file_name: str
    page_count: int


@dataclass(frozen=True, slots=True)
class PdfPageSize:
    """Represent the native dimensions of one PDF page in points."""

    width: float
    height: float


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
                "Não foi possível abrir o PDF. "
                "O arquivo pode estar inválido ou corrompido."
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
            raise PdfServiceError(
                "Não foi possível renderizar a página do PDF."
            ) from error

    def page_size(self, page_index: int = 0) -> PdfPageSize:
        """Return a page's native width and height in PDF points."""
        if self._document is None:
            raise PdfServiceError("Nenhum documento PDF está carregado.")
        if not 0 <= page_index < self._document.page_count:
            raise PdfServiceError("A página solicitada não existe neste documento.")

        try:
            page_rect = self._document.load_page(page_index).rect
            return PdfPageSize(float(page_rect.width), float(page_rect.height))
        except (OSError, RuntimeError, ValueError) as error:
            raise PdfServiceError(
                "Não foi possível obter as dimensões da página do PDF."
            ) from error

    def extract_region_text(self, region: FieldRegion) -> str:
        """Extract native text clipped to one region in PDF coordinates."""
        if self._document is None:
            raise PdfServiceError("Nenhum documento PDF está carregado.")
        if not 0 <= region.page_index < self._document.page_count:
            raise PdfServiceError("A página do campo não existe neste documento.")

        try:
            page = self._document.load_page(region.page_index)
            clip = fitz.Rect(region.x, region.y, region.right, region.bottom)
            clipped_region = clip & page.rect
            if clipped_region.is_empty:
                raise PdfServiceError("A região do campo está fora da página.")
            return page.get_text("text", clip=clipped_region)
        except PdfServiceError:
            raise
        except (OSError, RuntimeError, ValueError) as error:
            raise PdfServiceError(
                "Não foi possível extrair o texto da região."
            ) from error

    def close(self) -> None:
        """Release the loaded document and its operating-system resources."""
        if self._document is not None:
            self._document.close()
        self._document = None
        self._file_name = None
