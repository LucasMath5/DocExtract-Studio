"""Tests for the initial main window."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import fitz
import pytest
from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from pdf_extractor.app.main_window import MainWindow
from pdf_extractor.core.template_service import TemplateService
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.field_region import FieldRegion
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
    assert "Nenhum documento carregado" in window.pdf_viewer.page_canvas.text()
    assert window.open_pdf_action.text() == "Abrir PDF"
    assert window.exit_action.text() == "Sair"
    assert window.new_template_action.text() == "Novo template"
    assert window.save_template_action.text() == "Salvar template"
    assert window.import_template_action.text() == "Importar template..."
    assert window.export_template_action.text() == "Exportar template..."
    assert window.batch_files_action.text() == "Processar PDFs..."
    assert window.batch_folder_action.text() == "Processar pasta..."
    assert window.pdf_viewer.page_indicator.text() == "Página 0 de 0"
    assert not window.pdf_viewer.previous_button.isEnabled()
    assert not window.pdf_viewer.next_button.isEnabled()
    assert not window.pdf_viewer.zoom_in_button.isEnabled()
    assert window.field_panel.title_label.text() == "Campos mapeados (0)"

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
    assert window.pdf_viewer.page_canvas.pixmap() is not None
    assert not window.pdf_viewer.page_canvas.pixmap().isNull()
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
    original_width = window.pdf_viewer.page_canvas.pixmap().width()

    window.pdf_viewer.zoom_in_button.click()
    assert window.pdf_viewer.zoom_indicator.text() == "125%"
    assert window.pdf_viewer.page_canvas.pixmap().width() > original_width
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
    field = window.field_manager.create(
        "Campo temporário",
        FieldRegion(1, 20, 30, 100, 40),
    )
    window._selected_field_id = field.id
    window._refresh_fields()

    window._load_pdf(second_pdf)

    assert window.pdf_viewer.page_indicator.text() == "Página 1 de 1"
    assert window.pdf_viewer.zoom_indicator.text() == "100%"
    assert not window.pdf_viewer.previous_button.isEnabled()
    assert not window.pdf_viewer.next_button.isEnabled()
    assert not window.field_manager.fields
    assert window._selected_field_id is None
    assert window.field_panel.title_label.text() == "Campos mapeados (0)"
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


def test_ctrl_mouse_wheel_controls_zoom_by_direction(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Ctrl+wheel should zoom while an unmodified wheel keeps normal behavior."""
    pdf_path = tmp_path / "zoom_roda.pdf"
    create_synthetic_pdf(pdf_path)
    window = MainWindow()
    window._load_pdf(pdf_path)
    window.show()
    application.processEvents()
    viewport = window.pdf_viewer.scroll_area.viewport()

    def send_wheel(delta: int, modifiers: Qt.KeyboardModifier) -> None:
        event = QWheelEvent(
            QPointF(30, 30),
            QPointF(30, 30),
            QPoint(),
            QPoint(0, delta),
            Qt.MouseButton.NoButton,
            modifiers,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(viewport, event)
        application.processEvents()

    send_wheel(120, Qt.KeyboardModifier.ControlModifier)
    assert window.pdf_viewer.zoom_indicator.text() == "125%"

    send_wheel(-120, Qt.KeyboardModifier.ControlModifier)
    assert window.pdf_viewer.zoom_indicator.text() == "100%"

    send_wheel(-120, Qt.KeyboardModifier.NoModifier)
    assert window.pdf_viewer.zoom_indicator.text() == "100%"
    window.close()


def test_mouse_selection_creates_pdf_region_and_delete_clears_it(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Dragging should create named fields and Delete should remove one."""
    pdf_path = tmp_path / "selecao.pdf"
    create_synthetic_pdf(pdf_path)
    window = MainWindow()
    window._load_pdf(pdf_path)
    window.show()
    application.processEvents()
    names = iter([("Primeiro", True), ("Segundo", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: next(names))
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    canvas = window.pdf_viewer.page_canvas
    page_rect = canvas.page_display_rect()
    start = QPoint(int(page_rect.left() + 50), int(page_rect.top() + 80))
    end = QPoint(int(page_rect.left() + 210), int(page_rect.top() + 160))

    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, end)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)

    region = window.field_manager.fields[0].region
    assert region.page_index == 0
    assert region.x == pytest.approx(50, abs=1)
    assert region.y == pytest.approx(80, abs=1)
    assert region.width == pytest.approx(160, abs=1)
    assert region.height == pytest.approx(80, abs=1)
    assert canvas.selection_display_rect() is not None
    assert window.field_panel.title_label.text() == "Campos mapeados (1)"

    reverse_start = QPoint(int(page_rect.left() + 300), int(page_rect.top() + 220))
    reverse_end = QPoint(int(page_rect.left() + 100), int(page_rect.top() + 120))
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=reverse_start)
    QTest.mouseMove(canvas, reverse_end)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=reverse_end)

    assert len(window.field_manager.fields) == 2
    replacement = window.field_manager.fields[1].region
    assert replacement.x == pytest.approx(100, abs=1)
    assert replacement.y == pytest.approx(120, abs=1)
    assert replacement.width == pytest.approx(200, abs=1)
    assert replacement.height == pytest.approx(100, abs=1)

    QTest.keyClick(canvas, Qt.Key.Key_Delete)
    assert len(window.field_manager.fields) == 1
    assert window.field_manager.fields[0].name == "Primeiro"
    window.close()


def test_escape_cancels_selection_in_progress(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Escape should cancel a drag without creating a saved region."""
    pdf_path = tmp_path / "cancelar.pdf"
    create_synthetic_pdf(pdf_path)
    window = MainWindow()
    window._load_pdf(pdf_path)
    window.show()
    application.processEvents()

    canvas = window.pdf_viewer.page_canvas
    page_rect = canvas.page_display_rect()
    start = QPoint(int(page_rect.left() + 40), int(page_rect.top() + 40))
    end = QPoint(int(page_rect.left() + 180), int(page_rect.top() + 120))
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, end)
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)

    assert not window.field_manager.fields
    assert canvas.selection_display_rect() is None
    window.close()


def test_mouse_selection_uses_pdf_coordinates_at_zoom(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A drag on a zoomed page should still store native PDF coordinates."""
    pdf_path = tmp_path / "coordenadas_zoom.pdf"
    create_synthetic_pdf(pdf_path)
    window = MainWindow()
    window._load_pdf(pdf_path)
    window._set_zoom(200)
    window.show()
    application.processEvents()
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Campo com zoom", True),
    )

    canvas = window.pdf_viewer.page_canvas
    page_rect = canvas.page_display_rect()
    start = QPoint(int(page_rect.left() + 100), int(page_rect.top() + 120))
    end = QPoint(int(page_rect.left() + 300), int(page_rect.top() + 280))
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas, end)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)

    region = window.field_manager.fields[0].region
    assert region.x == pytest.approx(50, abs=1)
    assert region.y == pytest.approx(60, abs=1)
    assert region.width == pytest.approx(100, abs=1)
    assert region.height == pytest.approx(80, abs=1)
    window.close()


def test_selection_follows_zoom_and_appears_only_on_its_page(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """A PDF region should scale visually and remain tied to its page."""
    pdf_path = tmp_path / "regiao_zoom.pdf"
    create_synthetic_pdf(pdf_path, page_count=2)
    window = MainWindow()
    window._load_pdf(pdf_path)
    field = window.field_manager.create(
        "Campo",
        FieldRegion(0, 50, 60, 120, 80),
    )
    window._selected_field_id = field.id
    window._refresh_fields()

    initial_rect = window.pdf_viewer.page_canvas.selection_display_rect()
    assert initial_rect is not None

    window._set_zoom(200)
    zoomed_rect = window.pdf_viewer.page_canvas.selection_display_rect()
    assert zoomed_rect is not None
    assert zoomed_rect.width() == pytest.approx(initial_rect.width() * 2, abs=1)
    assert zoomed_rect.height() == pytest.approx(initial_rect.height() * 2, abs=1)

    window.pdf_viewer.next_button.click()
    assert window.pdf_viewer.page_canvas.selection_display_rect() is None

    window.pdf_viewer.previous_button.click()
    assert window.pdf_viewer.page_canvas.selection_display_rect() is not None
    window.close()


def test_field_dialog_retries_invalid_name(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The naming dialog should retry after an empty field name."""
    pdf_path = tmp_path / "nomes.pdf"
    create_synthetic_pdf(pdf_path)
    window = MainWindow()
    window._load_pdf(pdf_path)
    answers = iter([("   ", True), ("Cliente", True)])
    warnings: list[str] = []
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append(message),
    )

    window._handle_region_selected(FieldRegion(0, 10, 20, 30, 40))

    assert [field.name for field in window.field_manager.fields] == ["Cliente"]
    assert warnings == ["O nome do campo não pode ser vazio."]
    window.close()


def test_panel_selection_navigates_to_field_page(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Selecting a panel item should navigate and highlight its field."""
    pdf_path = tmp_path / "painel_paginas.pdf"
    create_synthetic_pdf(pdf_path, page_count=2)
    window = MainWindow()
    window._load_pdf(pdf_path)
    first = window.field_manager.create(
        "Primeira página",
        FieldRegion(0, 10, 20, 80, 30),
    )
    second = window.field_manager.create(
        "Segunda página",
        FieldRegion(1, 15, 25, 90, 35),
    )
    window._selected_field_id = first.id
    window._refresh_fields()

    window.field_panel.field_list.setCurrentRow(1)

    assert window._current_page_index == 1
    assert window._selected_field_id == second.id
    assert window.pdf_viewer.page_indicator.text() == "Página 2 de 2"
    assert window.pdf_viewer.page_canvas.selection_display_rect() is not None
    window.close()


def test_rename_rejects_duplicate_then_updates_field(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Renaming should preserve data and retry after a duplicate name."""
    pdf_path = tmp_path / "renomear.pdf"
    create_synthetic_pdf(pdf_path)
    window = MainWindow()
    window._load_pdf(pdf_path)
    first = window.field_manager.create("Cliente", FieldRegion(0, 10, 20, 80, 30))
    second = window.field_manager.create("Data", FieldRegion(0, 10, 60, 80, 30))
    window._selected_field_id = second.id
    window._refresh_fields()
    answers = iter([("CLIENTE", True), ("Data do documento", True)])
    warnings: list[str] = []
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append(message),
    )

    window._rename_field(second.id)

    renamed = window.field_manager.get(second.id)
    assert renamed is not None
    assert renamed.name == "Data do documento"
    assert renamed.region == second.region
    assert window.field_manager.get(first.id) == first
    assert warnings == ["Já existe um campo com esse nome."]
    window.close()


def test_delete_field_requires_confirmation(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A field should remain after No and be removed after Yes."""
    pdf_path = tmp_path / "excluir.pdf"
    create_synthetic_pdf(pdf_path)
    window = MainWindow()
    window._load_pdf(pdf_path)
    field = window.field_manager.create("Cliente", FieldRegion(0, 10, 20, 80, 30))
    window._selected_field_id = field.id
    window._refresh_fields()
    answers = iter(
        [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes]
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: next(answers),
    )

    window._request_delete_field(field.id)
    assert window.field_manager.get(field.id) is not None

    window._request_delete_field(field.id)
    assert window.field_manager.get(field.id) is None
    assert window.field_panel.title_label.text() == "Campos mapeados (0)"
    window.close()


def test_extract_button_populates_result_table(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """The field panel should run extraction and populate read-only rows."""
    pdf_path = tmp_path / "resultado_interface.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "Empresa Exemplo", fontsize=12)
    document.save(pdf_path)
    document.close()
    window = MainWindow()
    window._load_pdf(pdf_path)
    field = window.field_manager.create(
        "Cliente",
        FieldRegion(0, 65, 82, 180, 25),
    )
    window._selected_field_id = field.id
    window._refresh_fields()

    assert window.field_panel.extract_button.isEnabled()
    window.field_panel.extract_button.click()

    assert window.result_table.table.rowCount() == 1
    assert window.result_table.table.item(0, 0).text() == "Cliente"
    assert window.result_table.table.item(0, 1).text() == "1"
    assert window.result_table.table.item(0, 2).text() == "Empresa Exemplo"
    assert window.result_table.table.item(0, 3).text() == "texto nativo"
    assert window.result_table.table.item(0, 4).text() == "sucesso"
    assert "1 sucesso" in window.statusBar().currentMessage()
    assert window.result_table.export_csv_button.isEnabled()
    assert window.result_table.export_excel_button.isEnabled()
    window.close()


def test_export_buttons_save_csv_and_excel(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Export buttons should use destinations, add suffixes, and report success."""
    pdf_path = tmp_path / "origem.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "Empresa Exemplo", fontsize=12)
    document.save(pdf_path)
    document.close()
    window = MainWindow()
    window._load_pdf(pdf_path)
    field = window.field_manager.create(
        "Cliente",
        FieldRegion(0, 65, 82, 180, 25),
    )
    window._selected_field_id = field.id
    window._refresh_fields()
    window._extract_data()
    destinations = iter(
        [
            (str(tmp_path / "resultado_csv"), "Arquivos CSV (*.csv)"),
            (str(tmp_path / "resultado_excel.xlsx"), "Planilhas Excel (*.xlsx)"),
        ]
    )
    messages: list[str] = []
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: next(destinations),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, message: messages.append(message),
    )

    window.result_table.export_csv_button.click()
    window.result_table.export_excel_button.click()

    assert (tmp_path / "resultado_csv.csv").is_file()
    assert (tmp_path / "resultado_excel.xlsx").is_file()
    assert len(messages) == 2
    window.close()


def test_save_template_exports_current_fields_as_json(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Saving should name the mapping and create a portable JSON template."""
    pdf_path = tmp_path / "origem_template.pdf"
    create_synthetic_pdf(pdf_path)
    destination = tmp_path / "template_cliente"
    window = MainWindow()
    window._load_pdf(pdf_path)
    field = window.field_manager.create(
        "Cliente",
        FieldRegion(0, 20, 30, 160, 25),
    )
    window._selected_field_id = field.id
    window._refresh_fields()
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Cadastro genérico", True),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(destination), "Templates JSON (*.json)"),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    window.save_template_action.trigger()

    template_path = destination.with_suffix(".json")
    template = TemplateService().load(template_path)
    assert template.name == "Cadastro genérico"
    assert template.fields == (field,)
    assert window.template_controller.path == template_path
    assert not window.template_controller.dirty
    assert str(pdf_path) not in template_path.read_text(encoding="utf-8")
    window.close()


def test_import_edit_and_reuse_template_in_another_pdf(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Imported fields should be editable, saved, and kept for another PDF."""
    template_path = tmp_path / "reutilizavel.json"
    service = TemplateService()
    original_field = ExtractionField(
        "field-1",
        "Cliente",
        FieldRegion(0, 30, 40, 150, 25),
    )
    service.save(service.create("Cadastro", (original_field,)), template_path)
    first_pdf = tmp_path / "primeiro_template.pdf"
    second_pdf = tmp_path / "segundo_template.pdf"
    create_synthetic_pdf(first_pdf)
    create_synthetic_pdf(second_pdf)
    window = MainWindow()
    window._load_pdf(first_pdf)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(template_path), "Templates JSON (*.json)"),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    window.import_template_action.trigger()

    assert window.field_manager.fields == (original_field,)
    assert window.pdf_viewer.page_canvas.selection_display_rect() is not None
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Nome do cliente", True),
    )
    window._rename_field(original_field.id)
    assert window.template_controller.dirty
    window.save_template_action.trigger()
    assert TemplateService().load(template_path).fields[0].name == "Nome do cliente"

    window._load_pdf(second_pdf)

    assert window.pdf_service.document_info is not None
    assert window.pdf_service.document_info.file_name == second_pdf.name
    assert [field.name for field in window.field_manager.fields] == [
        "Nome do cliente"
    ]
    assert window.pdf_viewer.page_canvas.selection_display_rect() is not None
    window.close()


def test_import_invalid_template_shows_friendly_error(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Invalid template files should not replace the current fields."""
    template_path = tmp_path / "invalido.json"
    template_path.write_text("{ inválido", encoding="utf-8")
    window = MainWindow()
    existing = window.field_manager.create(
        "Existente",
        FieldRegion(0, 10, 20, 80, 20),
    )
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(template_path), "Templates JSON (*.json)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, message: messages.append((title, message)),
    )

    window.import_template_action.trigger()

    assert window.field_manager.fields == (existing,)
    assert messages
    assert messages[0][0] == "Template inválido"
    assert "JSON inválido" in messages[0][1]
    window.close()


def test_batch_action_processes_multiple_pdfs_in_worker_thread(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The batch UI should load a template and report every selected PDF."""
    first_pdf = tmp_path / "lote_01.pdf"
    second_pdf = tmp_path / "lote_02.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "Empresa Exemplo", fontsize=12)
    document.save(first_pdf)
    document.close()
    second_document = fitz.open()
    second_page = second_document.new_page()
    second_page.insert_text((72, 100), "Outra Empresa", fontsize=12)
    second_document.save(second_pdf)
    second_document.close()
    template_path = tmp_path / "lote_template.json"
    template_service = TemplateService()
    template = template_service.create(
        "Lote genérico",
        (
            ExtractionField(
                "cliente",
                "Cliente",
                FieldRegion(0, 65, 82, 180, 25),
            ),
        ),
    )
    template_service.save(template, template_path)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        lambda *args, **kwargs: (
            [str(first_pdf), str(second_pdf)],
            "Documentos PDF (*.pdf)",
        ),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(template_path), "Templates JSON (*.json)"),
    )
    window = MainWindow()
    reports: list[object] = []
    window.batch_controller.report_ready.connect(reports.append)

    window.batch_files_action.trigger()
    timer = QElapsedTimer()
    timer.start()
    while not reports and timer.elapsed() < 5_000:
        application.processEvents()
        QTest.qWait(10)

    assert reports
    report = reports[0]
    assert report.processed == 2
    assert report.success_count == 2
    assert report.review_count == 0
    assert window.batch_controller.result_dialog is not None
    preview = window.batch_controller.result_dialog.table
    assert preview.rowCount() == 2
    assert preview.columnCount() == 5
    assert [
        preview.horizontalHeaderItem(column).text()
        for column in range(preview.columnCount())
    ] == ["arquivo", "status", "método", "erro", "Cliente"]
    assert preview.item(0, 0).text() == first_pdf.name
    assert preview.item(0, 2).text() == "texto nativo"
    assert preview.item(0, 4).text() == "Empresa Exemplo"
    assert preview.item(1, 1).text() == "sucesso"
    assert preview.item(1, 2).text() == "texto nativo"
    assert preview.item(1, 4).text() == "Outra Empresa"
    while window.batch_controller.is_running and timer.elapsed() < 5_000:
        application.processEvents()
        QTest.qWait(10)
    window.batch_controller.result_dialog.close()
    window.close()


def test_batch_folder_discovery_is_sorted_and_ignores_non_pdfs(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Folder processing should include only top-level PDFs in stable order."""
    (tmp_path / "b.PDF").write_bytes(b"pdf")
    (tmp_path / "A.pdf").write_bytes(b"pdf")
    (tmp_path / "notas.txt").write_text("ignorar", encoding="utf-8")
    nested = tmp_path / "subpasta"
    nested.mkdir()
    (nested / "interno.pdf").write_bytes(b"pdf")
    window = MainWindow()

    paths = window.batch_controller.pdfs_in_folder(tmp_path)

    assert [path.name for path in paths] == ["A.pdf", "b.PDF"]
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
