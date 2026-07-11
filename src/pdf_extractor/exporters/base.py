"""Common export contracts and dataset construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import ExtractionResult
from pdf_extractor.models.batch_result import BatchDocumentResult


class ExportError(Exception):
    """Represent an expected failure while writing an export file."""


@dataclass(frozen=True, slots=True)
class ExportDataset:
    """Represent ordered headers and one or more document rows."""

    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    @property
    def values(self) -> tuple[str, ...]:
        """Return the first row for compatibility with single-PDF workflows."""
        return self.rows[0] if self.rows else ()


class TabularExporter(Protocol):
    """Define the interface shared by tabular file exporters."""

    def export(self, file_path: Path, dataset: ExportDataset) -> None:
        """Write one export dataset to the requested destination."""


def build_export_dataset(
    document_name: str,
    fields: tuple[ExtractionField, ...],
    results: tuple[ExtractionResult, ...],
) -> ExportDataset:
    """Build one row using field order and empty values for missing results."""
    values_by_field = {result.field_id: result.value for result in results}
    return ExportDataset(
        headers=("arquivo", *(field.name for field in fields)),
        rows=(
            (
                document_name,
                *(values_by_field.get(field.id, "") for field in fields),
            ),
        ),
    )


def build_batch_export_dataset(
    fields: tuple[ExtractionField, ...],
    documents: tuple[BatchDocumentResult, ...],
) -> ExportDataset:
    """Build one consolidated row per processed PDF, including error details."""
    rows: list[tuple[str, ...]] = []
    for document in documents:
        values_by_field = {
            result.field_id: result.value for result in document.results
        }
        rows.append(
            (
                document.file_name,
                document.status.value,
                document.error_message or "",
                *(values_by_field.get(field.id, "") for field in fields),
            )
        )
    return ExportDataset(
        headers=(
            "arquivo",
            "status",
            "erro",
            *(field.name for field in fields),
        ),
        rows=tuple(rows),
    )
