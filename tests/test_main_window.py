"""Tests for the initial main window."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import fitz
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from pdf_extractor.app.main_window import MainWindow


@pytest.fixture(scope="module")
def application() -> Iterator[QApplication]:
    """Provide a Qt application instance for the window tests."""
    instance = QApplication.instance() or QApplication(sys.argv)
    yield instance


def test_main_window_has_expected_initial_state(application: QApplication) -> None:
    """The initial window should show its title, empty state, and file actions."""
    window = MainWindow()

    assert window.windowTitle() == "Visual PDF Data Extractor"
    assert "Nenhum documento carregado" in window.pdf_viewer.page_label.text()
    assert window.open_pdf_action.text() == "Abrir PDF"
    assert window.exit_action.text() == "Sair"

    window.close()


def test_open_pdf_action_loads_first_page(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The open action should load and display a synthetic PDF."""
    pdf_path = tmp_path / "exemplo.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Documento sintético")
    document.save(pdf_path)
    document.close()

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(pdf_path), "Documentos PDF (*.pdf)"),
    )
    window = MainWindow()

    window.open_pdf_action.trigger()

    assert window.pdf_viewer.file_name_label.text() == "exemplo.pdf"
    assert window.pdf_viewer.page_label.pixmap() is not None
    assert not window.pdf_viewer.page_label.pixmap().isNull()
    assert "1 página" in window.statusBar().currentMessage()
    window.close()


def test_invalid_pdf_shows_friendly_error(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An invalid PDF should result in a friendly error dialog."""
    invalid_pdf = tmp_path / "corrompido.pdf"
    invalid_pdf.write_text("isto não é um PDF", encoding="utf-8")
    messages: list[tuple[str, str]] = []

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(invalid_pdf), "Documentos PDF (*.pdf)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, message: messages.append((title, message)),
    )
    window = MainWindow()

    window.open_pdf_action.trigger()

    assert messages
    assert messages[0][0] == "Erro ao abrir PDF"
    assert "inválido ou corrompido" in messages[0][1]
    window.close()


def test_exit_action_closes_window(application: QApplication) -> None:
    """The exit action should close the main window."""
    window = MainWindow()
    window.show()
    application.processEvents()

    window.exit_action.trigger()
    application.processEvents()

    assert not window.isVisible()
