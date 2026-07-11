"""Tests for PDF loading and first-page rendering."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_extractor.core.pdf_service import PdfService, PdfServiceError
from pdf_extractor.models.field_region import FieldRegion


def create_synthetic_pdf(path: Path, page_count: int = 1) -> None:
    """Create a generic PDF fixture without external documents."""
    document = fitz.open()
    for page_number in range(1, page_count + 1):
        page = document.new_page()
        page.insert_text((72, 72), f"Página sintética {page_number}")
    document.save(path)
    document.close()


def test_open_and_render_first_page(tmp_path: Path) -> None:
    """A valid PDF should expose metadata and render a PNG image."""
    pdf_path = tmp_path / "documento.pdf"
    create_synthetic_pdf(pdf_path, page_count=2)
    service = PdfService()

    info = service.open_document(pdf_path)
    image = service.render_page()

    assert info.file_name == "documento.pdf"
    assert info.page_count == 2
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    service.close()
    assert service.document_info is None


def test_render_different_pages_and_scales(tmp_path: Path) -> None:
    """The service should render any valid page at the requested scale."""
    pdf_path = tmp_path / "paginas.pdf"
    create_synthetic_pdf(pdf_path, page_count=2)
    service = PdfService()
    service.open_document(pdf_path)

    first_page = fitz.Pixmap(service.render_page(0, scale=1.0))
    second_page = fitz.Pixmap(service.render_page(1, scale=2.0))

    assert second_page.width == first_page.width * 2
    assert second_page.height == first_page.height * 2
    service.close()


def test_returns_native_page_size(tmp_path: Path) -> None:
    """The service should expose native dimensions for coordinate mapping."""
    pdf_path = tmp_path / "dimensoes.pdf"
    create_synthetic_pdf(pdf_path)
    service = PdfService()
    service.open_document(pdf_path)

    page_size = service.page_size(0)

    assert page_size.width == pytest.approx(595, abs=1)
    assert page_size.height == pytest.approx(842, abs=1)
    service.close()


def test_extracts_text_from_native_region(tmp_path: Path) -> None:
    """The PDF service should clip native text to the requested region."""
    pdf_path = tmp_path / "texto_regiao.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "Dentro", fontsize=12)
    page.insert_text((300, 100), "Fora", fontsize=12)
    document.save(pdf_path)
    document.close()
    service = PdfService()
    service.open_document(pdf_path)

    value = service.extract_region_text(FieldRegion(0, 65, 82, 120, 25))

    assert value.strip() == "Dentro"
    service.close()


def test_renders_only_selected_region_for_ocr(tmp_path: Path) -> None:
    """Regional rendering should preserve the PDF rectangle at OCR scale."""
    pdf_path = tmp_path / "regiao_ocr.pdf"
    create_synthetic_pdf(pdf_path)
    service = PdfService()
    service.open_document(pdf_path)
    region = FieldRegion(0, 50, 60, 120, 40)

    image = fitz.Pixmap(service.render_region(region, scale=4.0))

    assert image.width == pytest.approx(480, abs=1)
    assert image.height == pytest.approx(160, abs=1)
    service.close()


def test_rejects_page_outside_document(tmp_path: Path) -> None:
    """Rendering should reject indexes outside the loaded document."""
    pdf_path = tmp_path / "documento.pdf"
    create_synthetic_pdf(pdf_path)
    service = PdfService()
    service.open_document(pdf_path)

    with pytest.raises(PdfServiceError, match="página solicitada não existe"):
        service.render_page(1)

    service.close()


def test_rejects_non_pdf_extension(tmp_path: Path) -> None:
    """A file without the PDF extension should be rejected."""
    service = PdfService()

    with pytest.raises(PdfServiceError, match="extensão .pdf"):
        service.open_document(tmp_path / "documento.txt")


def test_rejects_corrupted_pdf(tmp_path: Path) -> None:
    """A corrupted PDF should raise a domain-specific friendly error."""
    pdf_path = tmp_path / "corrompido.pdf"
    pdf_path.write_bytes(b"not a pdf")
    service = PdfService()

    with pytest.raises(PdfServiceError, match="inválido ou corrompido"):
        service.open_document(pdf_path)
