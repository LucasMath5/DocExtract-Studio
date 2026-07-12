"""Qt tests for configuring and applying PDF rename patterns."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from pdf_extractor.app import batch_result_dialog as batch_dialog_module
from pdf_extractor.app.batch_result_dialog import BatchResultDialog
from pdf_extractor.app.pdf_rename_dialog import PdfRenameDialog
from pdf_extractor.core.pdf_rename_service import RenamePlanItem, RenamePlanStatus
from pdf_extractor.core.template_service import TemplateService
from pdf_extractor.models.batch_result import (
    BatchDocumentResult,
    BatchDocumentStatus,
    BatchReport,
)
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import ExtractionResult, ExtractionStatus
from pdf_extractor.models.field_region import FieldRegion


@pytest.fixture(scope="module")
def application() -> Iterator[QApplication]:
    """Provide one offscreen Qt application for rename dialogs."""
    instance = QApplication.instance() or QApplication(sys.argv)
    yield instance


def sample_data(
    source: Path,
) -> tuple[tuple[ExtractionField, ...], BatchDocumentResult]:
    """Return two fields and one generic processed document."""
    fields = (
        ExtractionField("cliente", "Cliente", FieldRegion(0, 1, 1, 10, 10)),
        ExtractionField("data", "Data", FieldRegion(0, 20, 1, 10, 10)),
    )
    document = BatchDocumentResult(
        source,
        (
            ExtractionResult(
                "cliente",
                "Cliente",
                0,
                "Empresa Exemplo",
                ExtractionStatus.SUCCESS,
            ),
            ExtractionResult(
                "data",
                "Data",
                0,
                "2026-07-12",
                ExtractionStatus.SUCCESS,
            ),
        ),
        BatchDocumentStatus.SUCCESS,
    )
    return fields, document


def test_dialog_updates_preview_from_prefix_selection_and_order(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """The live preview should reflect prefix, checked fields, and visual order."""
    source = tmp_path / "original.pdf"
    source.write_bytes(b"pdf")
    fields, document = sample_data(source)
    dialog = PdfRenameDialog((document,), fields)

    dialog.prefix_input.setText("DOC")
    application.processEvents()

    assert dialog.selected_field_ids() == ("cliente", "data")
    assert dialog.preview_table.item(0, 1).text() == (
        "DOC-Empresa Exemplo-2026-07-12.pdf"
    )
    assert "DOC-{Cliente}-{Data}.pdf" in dialog.example_label.text()

    dialog.field_list.setCurrentRow(0)
    dialog.move_down_button.click()

    assert dialog.selected_field_ids() == ("data", "cliente")
    assert dialog.preview_table.item(0, 1).text() == (
        "DOC-2026-07-12-Empresa Exemplo.pdf"
    )

    dialog.field_list.item(1).setCheckState(Qt.CheckState.Unchecked)
    assert dialog.selected_field_ids() == ("data",)
    assert dialog.preview_table.item(0, 1).text() == "DOC-2026-07-12.pdf"
    dialog.close()


def test_dialog_confirms_and_renames_files(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The action button should execute the visible plan after confirmation."""
    source = tmp_path / "entrada.pdf"
    source.write_bytes(b"pdf")
    fields, document = sample_data(source)
    dialog = PdfRenameDialog((document,), fields)
    dialog.prefix_input.setText("DOC")
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    dialog.rename_button.click()
    application.processEvents()

    destination = tmp_path / "DOC-Empresa Exemplo-2026-07-12.pdf"
    assert destination.is_file()
    assert not source.exists()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.result_items[0].status == RenamePlanStatus.RENAMED


def test_batch_result_refreshes_export_names_after_rename(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The consolidated preview should use new paths after successful renames."""
    source = tmp_path / "antes.pdf"
    destination = tmp_path / "depois.pdf"
    source.write_bytes(b"pdf")
    fields, document = sample_data(source)
    template = TemplateService().create("Teste", fields)
    report = BatchReport("Teste", 1, (document,))
    result_dialog = BatchResultDialog(report, template)
    source.rename(destination)
    item = RenamePlanItem(
        0,
        source,
        destination,
        RenamePlanStatus.RENAMED,
    )

    class FakeRenameDialog:
        result_items = (item,)

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        batch_dialog_module,
        "PdfRenameDialog",
        lambda *args, **kwargs: FakeRenameDialog(),
    )

    result_dialog._rename_pdfs()

    assert result_dialog.report.documents[0].file_path == destination
    assert result_dialog.dataset.rows[0][0] == "depois.pdf"
    assert result_dialog.table.item(0, 0).text() == "depois.pdf"
    result_dialog.close()
