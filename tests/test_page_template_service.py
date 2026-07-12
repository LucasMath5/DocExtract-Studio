"""Tests for applying one template independently to source PDF pages."""

from __future__ import annotations

from pathlib import Path
from threading import Event

import fitz

from pdf_extractor.core.page_template_service import (
    PageOutputStatus,
    PageTemplateService,
)
from pdf_extractor.core.pdf_rename_service import RenamePattern
from pdf_extractor.core.template_service import TemplateService
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_template import ExtractionTemplate
from pdf_extractor.models.field_region import FieldRegion


class EmptyOcrEngine:
    """Keep blank page results deterministic without a local Tesseract."""

    def recognize(self, image_bytes: bytes) -> str:
        return ""


def create_page_records(path: Path, values: tuple[str | None, ...]) -> None:
    """Create one visible record at the same coordinates on every page."""
    document = fitz.open()
    for value in values:
        page = document.new_page()
        if value is not None:
            page.insert_text((72, 100), value, fontsize=14)
    document.save(path)
    document.close()


def sample_template() -> ExtractionTemplate:
    """Return a field whose stored page is intentionally not page zero."""
    field = ExtractionField(
        "cliente",
        "Cliente",
        FieldRegion(4, 65, 80, 240, 28),
    )
    return TemplateService().create("Registro por página", (field,))


def test_processes_selected_pages_with_same_template_coordinates(
    tmp_path: Path,
) -> None:
    """Excluded pages should be skipped and each remaining page extracted alone."""
    source = tmp_path / "registros.pdf"
    create_page_records(source, ("Cliente A", "Ignorar", "Cliente C"))
    progress: list[int] = []
    service = PageTemplateService(ocr_engine=EmptyOcrEngine())

    report = service.process(
        source,
        sample_template(),
        frozenset({1}),
        progress_callback=lambda current, total, result: progress.append(
            result.page_number
        ),
    )

    assert report.source_page_count == 3
    assert [page.page_number for page in report.pages] == [1, 3]
    assert [page.results[0].value for page in report.pages] == [
        "Cliente A",
        "Cliente C",
    ]
    assert progress == [1, 3]


def test_builds_names_and_generates_individual_one_page_pdfs(
    tmp_path: Path,
) -> None:
    """Generated files should use extracted values and preserve source pages."""
    source = tmp_path / "multipaginas.pdf"
    output_directory = tmp_path / "saida"
    output_directory.mkdir()
    create_page_records(source, ("Cliente A", "Cliente B", "Cliente C"))
    template = sample_template()
    service = PageTemplateService(ocr_engine=EmptyOcrEngine())
    report = service.process(source, template, frozenset({1}))

    plan = service.build_output_plan(
        report,
        template.fields,
        RenamePattern(("cliente",), prefix="DOC"),
        output_directory,
    )
    result = service.generate(report, plan)

    assert [item.destination_name for item in result] == [
        "DOC-Cliente A.pdf",
        "DOC-Cliente C.pdf",
    ]
    assert all(item.status == PageOutputStatus.GENERATED for item in result)
    for path, expected in zip(
        (item.destination_path for item in result),
        ("Cliente A", "Cliente C"),
        strict=True,
    ):
        assert path is not None
        document = fitz.open(path)
        assert document.page_count == 1
        assert document[0].get_text().strip() == expected
        document.close()
    original = fitz.open(source)
    assert original.page_count == 3
    original.close()


def test_empty_and_duplicate_values_are_not_generated(tmp_path: Path) -> None:
    """Incomplete fields and duplicate filenames should remain visible as issues."""
    source = tmp_path / "conflitos.pdf"
    output_directory = tmp_path / "saida"
    output_directory.mkdir()
    create_page_records(source, (None, "Repetido", "Repetido"))
    template = sample_template()
    service = PageTemplateService(ocr_engine=EmptyOcrEngine())
    report = service.process(source, template, frozenset())

    plan = service.build_output_plan(
        report,
        template.fields,
        RenamePattern(("cliente",)),
        output_directory,
    )
    result = service.generate(report, plan)

    assert [item.status for item in result] == [
        PageOutputStatus.INCOMPLETE,
        PageOutputStatus.CONFLICT,
        PageOutputStatus.CONFLICT,
    ]
    assert not tuple(output_directory.iterdir())


def test_page_processing_can_be_cancelled_between_pages(tmp_path: Path) -> None:
    """Cancellation should retain the completed page and skip later pages."""
    source = tmp_path / "cancelar.pdf"
    create_page_records(source, ("A", "B", "C"))
    cancellation = Event()
    service = PageTemplateService(ocr_engine=EmptyOcrEngine())

    report = service.process(
        source,
        sample_template(),
        frozenset(),
        progress_callback=lambda *args: cancellation.set(),
        cancellation_requested=cancellation.is_set,
    )

    assert report.processed == 1
    assert report.cancelled
