"""Tests for safe PDF filenames built from extracted field values."""

from __future__ import annotations

from pathlib import Path

from pdf_extractor.core.pdf_rename_service import (
    PdfRenameService,
    RenamePattern,
    RenamePlanStatus,
)
from pdf_extractor.models.batch_result import (
    BatchDocumentResult,
    BatchDocumentStatus,
)
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import ExtractionResult, ExtractionStatus
from pdf_extractor.models.field_region import FieldRegion


FIELDS = (
    ExtractionField("cliente", "Cliente", FieldRegion(0, 1, 1, 10, 10)),
    ExtractionField("data", "Data", FieldRegion(0, 20, 1, 10, 10)),
)


def document_result(
    path: Path,
    cliente: str = "Empresa Exemplo",
    data: str = "2026-07-12",
) -> BatchDocumentResult:
    """Return a successful generic document with two extracted values."""
    return BatchDocumentResult(
        path,
        (
            ExtractionResult(
                "cliente",
                "Cliente",
                0,
                cliente,
                ExtractionStatus.SUCCESS,
            ),
            ExtractionResult(
                "data",
                "Data",
                0,
                data,
                ExtractionStatus.SUCCESS,
            ),
        ),
        BatchDocumentStatus.SUCCESS,
    )


def test_builds_and_applies_prefix_and_ordered_field_values(tmp_path: Path) -> None:
    """The planned name should use sanitized values in the selected order."""
    source = tmp_path / "original.pdf"
    source.write_bytes(b"conteudo do pdf")
    document = document_result(source, "Empresa: Exemplo", "2026/07/12")
    service = PdfRenameService()
    pattern = RenamePattern(
        prefix="DOC",
        field_ids=("cliente", "data"),
    )

    plan = service.build_plan((document,), FIELDS, pattern)

    assert plan[0].status == RenamePlanStatus.READY
    assert plan[0].destination_name == "DOC-Empresa_Exemplo-2026_07_12.pdf"

    result = service.apply(plan)

    destination = tmp_path / "DOC-Empresa_Exemplo-2026_07_12.pdf"
    assert result[0].status == RenamePlanStatus.RENAMED
    assert destination.read_bytes() == b"conteudo do pdf"
    assert not source.exists()


def test_prefix_is_optional_and_field_order_is_configurable(tmp_path: Path) -> None:
    """A pattern may omit the prefix and place fields in any selected order."""
    source = tmp_path / "entrada.pdf"
    source.write_bytes(b"pdf")
    document = document_result(source, "Cliente A", "2026")

    plan = PdfRenameService().build_plan(
        (document,),
        FIELDS,
        RenamePattern(field_ids=("data", "cliente")),
    )

    assert plan[0].destination_name == "2026-Cliente A.pdf"


def test_empty_selected_field_prevents_rename(tmp_path: Path) -> None:
    """A PDF should remain untouched when a selected value is empty."""
    source = tmp_path / "vazio.pdf"
    source.write_bytes(b"pdf")
    document = document_result(source, data="")
    service = PdfRenameService()

    plan = service.build_plan(
        (document,),
        FIELDS,
        RenamePattern(field_ids=("cliente", "data")),
    )
    result = service.apply(plan)

    assert plan[0].status == RenamePlanStatus.INVALID
    assert 'campo "Data" está vazio' in plan[0].message
    assert result == plan
    assert source.is_file()


def test_duplicate_generated_names_are_reported_as_conflicts(
    tmp_path: Path,
) -> None:
    """Two PDFs in one folder must never be renamed to the same destination."""
    first = tmp_path / "primeiro.pdf"
    second = tmp_path / "segundo.pdf"
    first.write_bytes(b"primeiro")
    second.write_bytes(b"segundo")
    documents = (document_result(first), document_result(second))

    plan = PdfRenameService().build_plan(
        documents,
        FIELDS,
        RenamePattern(field_ids=("cliente",)),
    )

    assert [item.status for item in plan] == [
        RenamePlanStatus.CONFLICT,
        RenamePlanStatus.CONFLICT,
    ]
    assert first.read_bytes() == b"primeiro"
    assert second.read_bytes() == b"segundo"


def test_existing_destination_is_never_overwritten(tmp_path: Path) -> None:
    """An unrelated existing PDF should cause a conflict and preserve both files."""
    source = tmp_path / "entrada.pdf"
    destination = tmp_path / "Empresa Exemplo.pdf"
    source.write_bytes(b"origem")
    destination.write_bytes(b"existente")
    document = document_result(source)
    service = PdfRenameService()

    plan = service.build_plan(
        (document,),
        FIELDS,
        RenamePattern(field_ids=("cliente",)),
    )
    result = service.apply(plan)

    assert result[0].status == RenamePlanStatus.CONFLICT
    assert source.read_bytes() == b"origem"
    assert destination.read_bytes() == b"existente"
