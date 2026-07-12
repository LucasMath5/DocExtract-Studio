"""Qt tests for PDF split settings, preview, and generation."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import fitz
import pytest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from pdf_extractor.app.pdf_split_dialog import PdfSplitDialog


@pytest.fixture(scope="module")
def application() -> Iterator[QApplication]:
    """Provide one offscreen Qt application for split dialogs."""
    instance = QApplication.instance() or QApplication(sys.argv)
    yield instance


def create_numbered_pdf(path: Path, page_count: int = 6) -> None:
    """Create a synthetic PDF used by the split interface tests."""
    document = fitz.open()
    for page_number in range(1, page_count + 1):
        page = document.new_page()
        page.insert_text((72, 100), f"Página {page_number}", fontsize=16)
    document.save(path)
    document.close()


def test_dialog_updates_groups_and_excluded_page_preview(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Changing size and exclusions should immediately rebuild the preview."""
    source = tmp_path / "preview.pdf"
    create_numbered_pdf(source)
    dialog = PdfSplitDialog(source, 6)

    dialog.pages_per_file_spin.setValue(2)
    dialog.excluded_pages_input.setText("2, 5")
    application.processEvents()

    assert dialog.generate_button.isEnabled()
    assert dialog.preview_table.rowCount() == 2
    assert dialog.preview_table.item(0, 1).text() == "1, 3"
    assert dialog.preview_table.item(1, 1).text() == "4, 6"
    assert "Páginas excluídas: 2, 5" in dialog.validation_label.text()

    dialog.excluded_pages_input.setText("0")
    application.processEvents()

    assert not dialog.generate_button.isEnabled()
    assert dialog.preview_table.rowCount() == 0
    assert "entre 1 e 6" in dialog.validation_label.text()
    dialog.close()


def test_dialog_generates_confirmed_pdf_parts(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The generate button should write exactly the files shown in the preview."""
    source = tmp_path / "gerar.pdf"
    output_directory = tmp_path / "saida"
    output_directory.mkdir()
    create_numbered_pdf(source, page_count=5)
    dialog = PdfSplitDialog(source, 5)
    dialog.output_directory_input.setText(str(output_directory))
    dialog.pages_per_file_spin.setValue(2)
    dialog.excluded_pages_input.setText("2")
    dialog._refresh_plan()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    dialog.generate_button.click()
    application.processEvents()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert len(dialog.result_paths) == 2
    assert all(path.is_file() for path in dialog.result_paths)
    first = fitz.open(dialog.result_paths[0])
    second = fitz.open(dialog.result_paths[1])
    assert [page.get_text().strip() for page in first] == ["Página 1", "Página 3"]
    assert [page.get_text().strip() for page in second] == ["Página 4", "Página 5"]
    first.close()
    second.close()
