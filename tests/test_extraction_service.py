"""Tests for native text extraction from mapped PDF regions."""

from __future__ import annotations

from pathlib import Path

import fitz

from pdf_extractor.core.extraction_service import ExtractionService
from pdf_extractor.core.pdf_service import PdfService
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import ExtractionStatus
from pdf_extractor.models.field_region import FieldRegion


def create_text_pdf(path: Path) -> None:
    """Create a synthetic PDF with known text positions."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "Cliente Exemplo", fontsize=12)
    page.insert_text((72, 140), "Linha 1", fontsize=12)
    page.insert_text((72, 156), "Linha 2", fontsize=12)
    document.save(path)
    document.close()


def test_extracts_success_empty_and_continues_after_error(tmp_path: Path) -> None:
    """Each field should produce an independent normalized result."""
    pdf_path = tmp_path / "extracao.pdf"
    create_text_pdf(pdf_path)
    pdf_service = PdfService()
    pdf_service.open_document(pdf_path)
    service = ExtractionService(pdf_service)
    fields = (
        ExtractionField("cliente", "Cliente", FieldRegion(0, 65, 82, 180, 25)),
        ExtractionField("linhas", "Linhas", FieldRegion(0, 65, 122, 180, 42)),
        ExtractionField("vazio", "Vazio", FieldRegion(0, 65, 200, 180, 30)),
        ExtractionField("erro", "Erro", FieldRegion(4, 65, 82, 180, 25)),
    )

    results = service.extract(fields)

    assert [result.status for result in results] == [
        ExtractionStatus.SUCCESS,
        ExtractionStatus.SUCCESS,
        ExtractionStatus.EMPTY,
        ExtractionStatus.ERROR,
    ]
    assert results[0].value == "Cliente Exemplo"
    assert results[1].value == "Linha 1 Linha 2"
    assert results[2].value == ""
    assert results[3].error_message is not None
    pdf_service.close()
