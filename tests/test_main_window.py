"""Tests for the initial main window."""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

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
    assert "Nenhum documento carregado" in window.centralWidget().text()
    assert window.open_pdf_action.text() == "Abrir PDF"
    assert window.exit_action.text() == "Sair"

    window.close()


def test_open_pdf_action_shows_stage_message(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The open action should respond without implementing stage-two behavior."""
    messages: list[tuple[str, str]] = []

    def record_message(
        parent: MainWindow,
        title: str,
        message: str,
    ) -> QMessageBox.StandardButton:
        messages.append((title, message))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "information", record_message)
    window = MainWindow()

    window.open_pdf_action.trigger()

    assert messages == [
        ("Abrir PDF", "A abertura de documentos PDF será adicionada na Etapa 2."),
    ]
    window.close()


def test_exit_action_closes_window(application: QApplication) -> None:
    """The exit action should close the main window."""
    window = MainWindow()
    window.show()
    application.processEvents()

    window.exit_action.trigger()
    application.processEvents()

    assert not window.isVisible()
