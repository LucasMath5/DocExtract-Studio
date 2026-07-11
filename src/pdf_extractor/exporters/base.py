"""Common export contracts and dataset construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import ExtractionResult


class ExportError(Exception):
    """Represent an expected failure while writing an export file."""


@dataclass(frozen=True, slots=True)
class ExportDataset:
    """Represent one document row with ordered export columns."""

    headers: tuple[str, ...]
    values: tuple[str, ...]


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
        values=(
            document_name,
            *(values_by_field.get(field.id, "") for field in fields),
        ),
    )
