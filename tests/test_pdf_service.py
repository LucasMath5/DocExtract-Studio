"""Tests for PDF loading and first-page rendering."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_extractor.core.pdf_service import PdfService, PdfServiceError


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
