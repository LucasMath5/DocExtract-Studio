"""CSV exporter for one extracted PDF document."""

from __future__ import annotations

import csv
from pathlib import Path

from pdf_extractor.exporters.base import ExportDataset, ExportError


class CsvExporter:
    """Write an export dataset as UTF-8 CSV with an Excel-friendly BOM."""

    def export(self, file_path: Path, dataset: ExportDataset) -> None:
        """Write headers and all document rows to a CSV file."""
        try:
            with file_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(dataset.headers)
                writer.writerows(dataset.rows)
        except (OSError, csv.Error) as error:
            raise ExportError("Não foi possível salvar o arquivo CSV.") from error
