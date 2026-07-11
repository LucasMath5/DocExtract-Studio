"""Tests for CSV and Excel export files."""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import load_workbook

from pdf_extractor.exporters.base import ExportDataset, build_export_dataset
from pdf_extractor.exporters.csv_exporter import CsvExporter
from pdf_extractor.exporters.excel_exporter import ExcelExporter
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import ExtractionResult, ExtractionStatus
from pdf_extractor.models.field_region import FieldRegion


def sample_dataset() -> ExportDataset:
    """Build an ordered dataset containing accents and an empty field."""
    fields = (
        ExtractionField("cliente", "Cliente", FieldRegion(0, 1, 1, 10, 10)),
        ExtractionField("observacao", "Observação", FieldRegion(0, 1, 20, 10, 10)),
    )
    results = (
        ExtractionResult(
            "cliente",
            "Cliente",
            0,
            "Empresa São João",
            ExtractionStatus.SUCCESS,
        ),
        ExtractionResult(
            "observacao",
            "Observação",
            0,
            "",
            ExtractionStatus.EMPTY,
        ),
    )
    return build_export_dataset("documento.pdf", fields, results)


def test_csv_export_preserves_order_accents_and_empty_values(tmp_path: Path) -> None:
    """CSV should contain one ordered document row in UTF-8."""
    output = tmp_path / "dados.csv"

    CsvExporter().export(output, sample_dataset())

    with output.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    assert rows == [
        ["arquivo", "Cliente", "Observação"],
        ["documento.pdf", "Empresa São João", ""],
    ]


def test_excel_export_creates_readable_formatted_workbook(tmp_path: Path) -> None:
    """XLSX should contain one sheet, ordered values, and styled headers."""
    output = tmp_path / "dados.xlsx"

    ExcelExporter().export(output, sample_dataset())

    workbook = load_workbook(output)
    worksheet = workbook["Dados extraídos"]
    assert list(worksheet.values) == [
        ("arquivo", "Cliente", "Observação"),
        ("documento.pdf", "Empresa São João", None),
    ]
    assert worksheet.freeze_panes == "A2"
    assert worksheet["A1"].font.bold is True
    assert worksheet.auto_filter.ref == "A1:C2"
    workbook.close()
