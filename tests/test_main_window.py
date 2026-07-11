"""Tests for the initial main window."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import fitz
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from pdf_extractor.app.main_window import MainWindow
from pdf_extractor.utils.app_icon import application_icon_path, load_application_icon


@pytest.fixture(scope="module")
def application() -> Iterator[QApplication]:
    """Provide a Qt application instance for the window tests."""
    instance = QApplication.instance() or QApplication(sys.argv)
    yield instance


def create_synthetic_pdf(path: Path, page_count: int = 1) -> None:
    """Create a generic multi-page PDF for interface tests."""
    document = fitz.open()
    for page_number in range(1, page_count + 1):
        page = document.new_page()
        page.insert_text((72, 72), f"Página sintética {page_number}")
    document.save(path)
    document.close()


def test_main_window_has_expected_initial_state(application: QApplication) -> None:
    """The initial window should show its title, empty state, and file actions."""
    window = MainWindow()

    assert window.windowTitle() == "Visual PDF Data Extractor"
    assert not window.windowIcon().isNull()
    assert "Nenhum documento carregado" in window.pdf_viewer.page_label.text()
    assert window.open_pdf_action.text() == "Abrir PDF"
    assert window.exit_action.text() == "Sair"
    assert window.pdf_viewer.page_indicator.text() == "Página 0 de 0"
    assert not window.pdf_viewer.previous_button.isEnabled()
    assert not window.pdf_viewer.next_button.isEnabled()
    assert not window.pdf_viewer.zoom_in_button.isEnabled()

    window.close()


def test_application_icon_contains_windows_sizes(application: QApplication) -> None:
    """The packaged icon should exist and expose small and large resolutions."""
    icon_path = application_icon_path()
    icon = load_application_icon()
    available_sizes = {(size.width(), size.height()) for size in icon.availableSizes()}

    assert icon_path.is_file()
    assert not icon.isNull()
    if icon_path.suffix == ".ico":
        assert (16, 16) in available_sizes
        assert (256, 256) in available_sizes


def test_open_pdf_action_loads_first_page(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The open action should load and display a synthetic PDF."""
    pdf_path = tmp_path / "exemplo.pdf"
    create_synthetic_pdf(pdf_path)

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
    assert window.pdf_viewer.page_indicator.text() == "Página 1 de 1"
    assert window.pdf_viewer.zoom_indicator.text() == "100%"
    assert "Página 1 de 1" in window.statusBar().currentMessage()
    window.close()


def test_page_navigation_updates_controls(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Navigation should reach every page and disable buttons at the limits."""
    pdf_path = tmp_path / "tres_paginas.pdf"
    create_synthetic_pdf(pdf_path, page_count=3)
    window = MainWindow()
    window._load_pdf(pdf_path)

    assert not window.pdf_viewer.previous_button.isEnabled()
    assert window.pdf_viewer.next_button.isEnabled()

    window.pdf_viewer.next_button.click()
    assert window.pdf_viewer.page_indicator.text() == "Página 2 de 3"
    assert window.pdf_viewer.previous_button.isEnabled()

    window.pdf_viewer.next_button.click()
    assert window.pdf_viewer.page_indicator.text() == "Página 3 de 3"
    assert not window.pdf_viewer.next_button.isEnabled()

    window.pdf_viewer.previous_button.click()
    assert window.pdf_viewer.page_indicator.text() == "Página 2 de 3"
    window.close()


def test_zoom_controls_respect_limits_and_reset(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Zoom should render, clamp to its limits, and reset to 100 percent."""
    pdf_path = tmp_path / "zoom.pdf"
    create_synthetic_pdf(pdf_path)
    window = MainWindow()
    window._load_pdf(pdf_path)
    original_width = window.pdf_viewer.page_label.pixmap().width()

    window.pdf_viewer.zoom_in_button.click()
    assert window.pdf_viewer.zoom_indicator.text() == "125%"
    assert window.pdf_viewer.page_label.pixmap().width() > original_width
    assert window.pdf_viewer.reset_zoom_button.isEnabled()

    window.pdf_viewer.reset_zoom_button.click()
    assert window.pdf_viewer.zoom_indicator.text() == "100%"
    assert not window.pdf_viewer.reset_zoom_button.isEnabled()

    window._set_zoom(1)
    assert window.pdf_viewer.zoom_indicator.text() == "50%"
    assert not window.pdf_viewer.zoom_out_button.isEnabled()

    window._set_zoom(999)
    assert window.pdf_viewer.zoom_indicator.text() == "300%"
    assert not window.pdf_viewer.zoom_in_button.isEnabled()
    window.close()


def test_opening_another_pdf_resets_page_and_zoom(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """A new document should always start on page one at default zoom."""
    first_pdf = tmp_path / "primeiro.pdf"
    second_pdf = tmp_path / "segundo.pdf"
    create_synthetic_pdf(first_pdf, page_count=2)
    create_synthetic_pdf(second_pdf)
    window = MainWindow()
    window._load_pdf(first_pdf)
    window.pdf_viewer.next_button.click()
    window.pdf_viewer.zoom_in_button.click()

    window._load_pdf(second_pdf)

    assert window.pdf_viewer.page_indicator.text() == "Página 1 de 1"
    assert window.pdf_viewer.zoom_indicator.text() == "100%"
    assert not window.pdf_viewer.previous_button.isEnabled()
    assert not window.pdf_viewer.next_button.isEnabled()
    window.close()


def test_keyboard_shortcuts_navigate_and_control_zoom(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Arrow and Ctrl shortcuts should control pages and zoom."""
    pdf_path = tmp_path / "atalhos.pdf"
    create_synthetic_pdf(pdf_path, page_count=2)
    window = MainWindow()
    window._load_pdf(pdf_path)
    window.show()
    window.activateWindow()
    window.setFocus()
    application.processEvents()

    QTest.keyClick(window, Qt.Key.Key_Right)
    assert window.pdf_viewer.page_indicator.text() == "Página 2 de 2"

    QTest.keyClick(window, Qt.Key.Key_Left)
    assert window.pdf_viewer.page_indicator.text() == "Página 1 de 2"

    QTest.keyClick(
        window,
        Qt.Key.Key_Plus,
        Qt.KeyboardModifier.ControlModifier,
    )
    assert window.pdf_viewer.zoom_indicator.text() == "125%"

    QTest.keyClick(
        window,
        Qt.Key.Key_Minus,
        Qt.KeyboardModifier.ControlModifier,
    )
    assert window.pdf_viewer.zoom_indicator.text() == "100%"
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
