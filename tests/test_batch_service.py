"""Tests for cancellable multi-PDF extraction."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Event

import fitz
import pytest

from pdf_extractor.core.batch_service import BatchError, BatchService
from pdf_extractor.core.template_service import TemplateService
from pdf_extractor.models.batch_result import BatchDocumentStatus
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_template import ExtractionTemplate
from pdf_extractor.models.field_region import FieldRegion


def create_pdf(path: Path, text: str | None = None) -> None:
    """Create a generic one-page PDF, optionally with native text."""
    document = fitz.open()
    page = document.new_page()
    if text is not None:
        page.insert_text((72, 100), text, fontsize=12)
    document.save(path)
    document.close()


def sample_template() -> ExtractionTemplate:
    """Create a deterministic template covering the synthetic text position."""
    service = TemplateService(
        now_factory=lambda: datetime(2026, 7, 11, tzinfo=timezone.utc)
    )
    return service.create(
        "Cadastro genérico",
        (
            ExtractionField(
                "cliente",
                "Cliente",
                FieldRegion(0, 65, 82, 180, 25),
            ),
        ),
    )


def test_batch_processes_success_empty_and_invalid_pdf_independently(
    tmp_path: Path,
) -> None:
    """One broken file should not stop later PDFs from reaching a result."""
    success_pdf = tmp_path / "01_sucesso.pdf"
    empty_pdf = tmp_path / "02_vazio.pdf"
    invalid_pdf = tmp_path / "03_invalido.pdf"
    last_pdf = tmp_path / "04_sucesso.pdf"
    create_pdf(success_pdf, "Empresa Exemplo")
    create_pdf(empty_pdf)
    invalid_pdf.write_text("não é PDF", encoding="utf-8")
    create_pdf(last_pdf, "Outro Exemplo")
    progress: list[tuple[int, str]] = []

    report = BatchService().process(
        (success_pdf, empty_pdf, invalid_pdf, last_pdf),
        sample_template(),
        progress_callback=lambda current, total, result: progress.append(
            (current, result.file_name)
        ),
    )

    assert report.total == 4
    assert report.processed == 4
    assert report.success_count == 2
    assert report.review_count == 1
    assert report.failure_count == 1
    assert not report.cancelled
    assert report.documents[0].results[0].value == "Empresa Exemplo"
    assert report.documents[1].status == BatchDocumentStatus.REVIEW_NEEDED
    assert report.documents[2].error_message
    assert progress[-1] == (4, last_pdf.name)


def test_batch_cancellation_stops_before_next_document(tmp_path: Path) -> None:
    """Cancellation should preserve completed results and skip remaining files."""
    paths = tuple(tmp_path / f"documento_{index}.pdf" for index in range(3))
    for index, path in enumerate(paths):
        create_pdf(path, f"Documento {index}")
    cancellation = Event()

    report = BatchService().process(
        paths,
        sample_template(),
        progress_callback=lambda *args: cancellation.set(),
        cancellation_requested=cancellation.is_set,
    )

    assert report.total == 3
    assert report.processed == 1
    assert report.cancelled


def test_batch_rejects_template_without_fields(tmp_path: Path) -> None:
    """An empty template should fail before opening any PDF."""
    pdf_path = tmp_path / "documento.pdf"
    create_pdf(pdf_path, "Teste")
    service = TemplateService()

    with pytest.raises(BatchError, match="não possui campos"):
        BatchService().process((pdf_path,), service.create("Vazio", ()))
