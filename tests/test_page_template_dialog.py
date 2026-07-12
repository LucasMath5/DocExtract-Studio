"""Qt tests for per-page template analysis and named PDF generation."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import fitz
import pytest
from PySide6.QtCore import QElapsedTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from pdf_extractor.app.page_template_dialog import PageTemplateDialog
from pdf_extractor.core.page_template_service import PageTemplateService
from pdf_extractor.core.template_service import TemplateService
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.field_region import FieldRegion


class EmptyOcrEngine:
    def recognize(self, image_bytes: bytes) -> str:
        return ""


@pytest.fixture(scope="module")
def application() -> Iterator[QApplication]:
    """Provide one offscreen Qt application for the page-template dialog."""
    instance = QApplication.instance() or QApplication(sys.argv)
    yield instance


def create_page_records(path: Path) -> None:
    """Create three pages with values at identical coordinates."""
    document = fitz.open()
    for value in ("Cliente A", "Ignorar", "Cliente C"):
        page = document.new_page()
        page.insert_text((72, 100), value, fontsize=14)
    document.save(path)
    document.close()


def test_dialog_analyzes_exclusions_previews_names_and_generates(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The complete UI flow should skip a page and generate named one-page PDFs."""
    source = tmp_path / "registros.pdf"
    output_directory = tmp_path / "saida"
    output_directory.mkdir()
    create_page_records(source)
    field = ExtractionField(
        "cliente",
        "Cliente",
        FieldRegion(0, 65, 80, 240, 28),
    )
    template = TemplateService().create("Registro", (field,))
    service = PageTemplateService(ocr_engine=EmptyOcrEngine())
    dialog = PageTemplateDialog(source, 3, template, service=service)
    dialog.output_directory_input.setText(str(output_directory))
    dialog.excluded_pages_input.setText("2")
    dialog.prefix_input.setText("DOC")

    dialog.analyze_button.click()
    timer = QElapsedTimer()
    timer.start()
    while (dialog.is_running or not dialog.output_plan) and timer.elapsed() < 5_000:
        application.processEvents()
        QTest.qWait(10)

    assert dialog.output_plan
    assert dialog.preview_table.rowCount() == 2
    assert dialog.preview_table.item(0, 0).text() == "1"
    assert dialog.preview_table.item(1, 0).text() == "3"
    assert dialog.preview_table.item(0, 2).text() == "DOC-Cliente A.pdf"
    assert dialog.preview_table.item(1, 2).text() == "DOC-Cliente C.pdf"
    assert dialog.generate_button.isEnabled()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    dialog.generate_button.click()
    application.processEvents()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert [path.name for path in dialog.result_paths] == [
        "DOC-Cliente A.pdf",
        "DOC-Cliente C.pdf",
    ]
    assert all(path.is_file() for path in dialog.result_paths)


def test_changing_exclusions_invalidates_previous_analysis(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Page exclusions should require a fresh extraction before generation."""
    source = tmp_path / "invalidar.pdf"
    create_page_records(source)
    field = ExtractionField(
        "cliente",
        "Cliente",
        FieldRegion(0, 65, 80, 240, 28),
    )
    template = TemplateService().create("Registro", (field,))
    dialog = PageTemplateDialog(
        source,
        3,
        template,
        service=PageTemplateService(ocr_engine=EmptyOcrEngine()),
    )
    dialog.analyze_button.click()
    timer = QElapsedTimer()
    timer.start()
    while (dialog.is_running or not dialog.output_plan) and timer.elapsed() < 5_000:
        application.processEvents()
        QTest.qWait(10)
    assert dialog.output_plan

    dialog.excluded_pages_input.setText("2")
    application.processEvents()

    assert not dialog.output_plan
    assert not dialog.generate_button.isEnabled()
    assert "Analisar páginas novamente" in dialog.status_label.text()
    dialog.close()
