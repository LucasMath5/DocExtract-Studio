"""Tests for grouping and generating smaller PDF files."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pdf_extractor.core.pdf_split_service import (
    PdfSplitError,
    PdfSplitService,
    format_page_numbers,
    parse_excluded_pages,
)


def create_numbered_pdf(path: Path, page_count: int = 6) -> None:
    """Create a synthetic PDF with a visible number on every page."""
    document = fitz.open()
    for page_number in range(1, page_count + 1):
        page = document.new_page()
        page.insert_text((72, 100), f"Página sintética {page_number}", fontsize=16)
    document.save(path)
    document.close()


def test_parses_individual_pages_ranges_and_duplicates() -> None:
    """Exclusion syntax should support commas, spaces, ranges, and duplicates."""
    excluded = parse_excluded_pages("2, 4-6, 5", 8)

    assert excluded == frozenset({1, 3, 4, 5})
    assert format_page_numbers(tuple(sorted(excluded))) == "2, 4-6"


@pytest.mark.parametrize(
    "expression",
    ["0", "7", "4-2", "dois", "1,,2", "2-9"],
)
def test_rejects_invalid_exclusion_expressions(expression: str) -> None:
    """Invalid or out-of-range pages should produce a clear domain error."""
    with pytest.raises(PdfSplitError):
        parse_excluded_pages(expression, 6)


def test_builds_groups_after_removing_excluded_pages(tmp_path: Path) -> None:
    """Remaining pages should keep source order and fill configured part sizes."""
    source = tmp_path / "documento.pdf"
    create_numbered_pdf(source)
    service = PdfSplitService()

    plan = service.build_plan(
        source,
        6,
        2,
        parse_excluded_pages("2, 5", 6),
        tmp_path,
    )

    assert [part.page_indices for part in plan.parts] == [(0, 2), (3, 5)]
    assert [part.page_label for part in plan.parts] == ["1, 3", "4, 6"]
    assert [part.destination_path.name for part in plan.parts] == [
        "documento_parte_001_paginas_1_3.pdf",
        "documento_parte_002_paginas_4_6.pdf",
    ]


def test_generates_parts_with_exact_original_pages(tmp_path: Path) -> None:
    """Every output should contain only its planned pages with intact content."""
    source = tmp_path / "original.pdf"
    output_directory = tmp_path / "partes"
    output_directory.mkdir()
    create_numbered_pdf(source)
    service = PdfSplitService()
    plan = service.build_plan(
        source,
        service.page_count(source),
        2,
        parse_excluded_pages("2, 5", 6),
        output_directory,
    )

    paths = service.split(plan)

    assert source.is_file()
    assert len(paths) == 2
    first = fitz.open(paths[0])
    second = fitz.open(paths[1])
    assert first.page_count == 2
    assert second.page_count == 2
    assert [page.get_text().strip() for page in first] == [
        "Página sintética 1",
        "Página sintética 3",
    ]
    assert [page.get_text().strip() for page in second] == [
        "Página sintética 4",
        "Página sintética 6",
    ]
    first.close()
    second.close()


def test_all_pages_excluded_and_existing_outputs_are_rejected(
    tmp_path: Path,
) -> None:
    """The service should never create empty parts or overwrite destinations."""
    source = tmp_path / "entrada.pdf"
    create_numbered_pdf(source, page_count=2)
    service = PdfSplitService()

    with pytest.raises(PdfSplitError, match="Todas as páginas"):
        service.build_plan(source, 2, 1, frozenset({0, 1}), tmp_path)

    existing = tmp_path / "entrada_parte_001_paginas_1.pdf"
    existing.write_bytes(b"preservar")
    with pytest.raises(PdfSplitError, match="Já existe"):
        service.build_plan(source, 2, 1, frozenset(), tmp_path)
    assert existing.read_bytes() == b"preservar"


def test_destination_created_after_preview_is_preserved(tmp_path: Path) -> None:
    """A late destination conflict must never be overwritten or removed."""
    source = tmp_path / "corrida.pdf"
    create_numbered_pdf(source, page_count=2)
    service = PdfSplitService()
    plan = service.build_plan(source, 2, 2, frozenset(), tmp_path)
    destination = plan.parts[0].destination_path
    destination.write_bytes(b"arquivo criado depois da previa")

    with pytest.raises(PdfSplitError, match="Já existe"):
        service.split(plan)

    assert destination.read_bytes() == b"arquivo criado depois da previa"
    assert source.is_file()


def test_rejects_corrupted_source_pdf(tmp_path: Path) -> None:
    """A corrupted source should fail before showing split settings."""
    source = tmp_path / "corrompido.pdf"
    source.write_bytes(b"not a pdf")

    with pytest.raises(PdfSplitError, match="inválido ou corrompido"):
        PdfSplitService().page_count(source)
