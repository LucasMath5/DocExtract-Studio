"""Tests for native text extraction from mapped PDF regions."""

from __future__ import annotations

from pathlib import Path

import fitz

from pdf_extractor.core.extraction_service import ExtractionService
from pdf_extractor.core.pdf_service import PdfService
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import (
    ExtractionMethod,
    ExtractionStatus,
)
from pdf_extractor.models.field_region import FieldRegion
from pdf_extractor.ocr.base import OcrUnavailableError


class StubOcrEngine:
    """Return configured text and retain regional images for assertions."""

    def __init__(self, value: str = "") -> None:
        self.value = value
        self.images: list[bytes] = []

    def recognize(self, image_bytes: bytes) -> str:
        self.images.append(image_bytes)
        return self.value


class UnavailableOcrEngine:
    """Simulate a machine where Tesseract is not installed."""

    def recognize(self, image_bytes: bytes) -> str:
        raise OcrUnavailableError("Tesseract indisponível para teste.")


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
    ocr_engine = StubOcrEngine()
    service = ExtractionService(pdf_service, ocr_engine)
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
    assert results[0].method == ExtractionMethod.NATIVE_TEXT
    assert results[1].method == ExtractionMethod.NATIVE_TEXT
    assert results[2].method == ExtractionMethod.OCR
    assert len(ocr_engine.images) == 1
    assert ocr_engine.images[0].startswith(b"\x89PNG")
    pdf_service.close()


def test_empty_native_region_uses_ocr_and_normalizes_text(tmp_path: Path) -> None:
    """OCR should run only after native text is absent in the mapped region."""
    pdf_path = tmp_path / "fallback_ocr.pdf"
    create_text_pdf(pdf_path)
    pdf_service = PdfService()
    pdf_service.open_document(pdf_path)
    ocr_engine = StubOcrEngine("  Texto   reconhecido\npor OCR  ")
    service = ExtractionService(pdf_service, ocr_engine)
    field = ExtractionField(
        "imagem",
        "Imagem",
        FieldRegion(0, 65, 200, 180, 30),
    )

    result = service.extract((field,))[0]

    assert result.value == "Texto reconhecido por OCR"
    assert result.status == ExtractionStatus.SUCCESS
    assert result.method == ExtractionMethod.OCR
    assert len(ocr_engine.images) == 1
    pdf_service.close()


def test_missing_tesseract_becomes_field_error_without_crashing(tmp_path: Path) -> None:
    """An unavailable OCR engine should affect only the empty native field."""
    pdf_path = tmp_path / "sem_tesseract.pdf"
    create_text_pdf(pdf_path)
    pdf_service = PdfService()
    pdf_service.open_document(pdf_path)
    service = ExtractionService(pdf_service, UnavailableOcrEngine())
    fields = (
        ExtractionField("nativo", "Nativo", FieldRegion(0, 65, 82, 180, 25)),
        ExtractionField("ocr", "OCR", FieldRegion(0, 65, 200, 180, 30)),
    )

    results = service.extract(fields)

    assert results[0].status == ExtractionStatus.SUCCESS
    assert results[0].method == ExtractionMethod.NATIVE_TEXT
    assert results[1].status == ExtractionStatus.ERROR
    assert results[1].method == ExtractionMethod.OCR
    assert "Tesseract indisponível" in (results[1].error_message or "")
    pdf_service.close()
