"""Qt workflow for creating, importing, editing, and saving templates."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMainWindow, QMessageBox

from pdf_extractor.core.template_service import TemplateError, TemplateService
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_template import ExtractionTemplate


class TemplateController(QObject):
    """Own template actions and persistence state outside the main window."""

    fields_replaced = Signal(object)
    state_changed = Signal()

    def __init__(
        self,
        parent: QMainWindow,
        fields_provider: Callable[[], tuple[ExtractionField, ...]],
        service: TemplateService | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = parent
        self._fields_provider = fields_provider
        self._service = service or TemplateService()
        self._template: ExtractionTemplate | None = None
        self._path: Path | None = None
        self._dirty = False
        self._create_actions()

    @property
    def active_template(self) -> ExtractionTemplate | None:
        """Return the template currently associated with the mapping."""
        return self._template

    @property
    def path(self) -> Path | None:
        """Return the current JSON destination when one exists."""
        return self._path

    @property
    def dirty(self) -> bool:
        """Report whether the active template has unsaved field changes."""
        return self._dirty

    def mark_changed(self) -> None:
        """Mark field edits made to an active template as pending persistence."""
        if self._template is not None:
            self._dirty = True
            self.state_changed.emit()

    def status_fragment(self) -> str:
        """Return the active template fragment used by the status bar."""
        if self._template is None:
            return ""
        pending_marker = " *" if self._dirty else ""
        return f" - Template: {self._template.name}{pending_marker}"

    def _create_actions(self) -> None:
        self.new_action = QAction("Novo template", self)
        self.new_action.setShortcut("Ctrl+N")
        self.new_action.setStatusTip("Criar um template vazio")
        self.new_action.triggered.connect(self._new_template)

        self.save_action = QAction("Salvar template", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.setStatusTip("Salvar o template atual")
        self.save_action.triggered.connect(self._save_template)

        self.import_action = QAction("Importar template...", self)
        self.import_action.setShortcut("Ctrl+I")
        self.import_action.setStatusTip("Carregar campos de um template JSON")
        self.import_action.triggered.connect(self._import_template)

        self.export_action = QAction("Exportar template...", self)
        self.export_action.setShortcut("Ctrl+Shift+S")
        self.export_action.setStatusTip("Salvar uma cópia do template em JSON")
        self.export_action.triggered.connect(self._export_template)

    def _new_template(self) -> None:
        if not self._confirm_replace_fields(
            "Criar um novo template removerá os campos atuais. Continuar?"
        ):
            return
        name, accepted = QInputDialog.getText(
            self._window,
            "Novo template",
            "Nome do template:",
        )
        if not accepted:
            return
        try:
            template = self._service.create(name, ())
        except ValueError as error:
            QMessageBox.warning(self._window, "Nome inválido", str(error))
            return

        self._template = template
        self._path = None
        self._dirty = True
        self.fields_replaced.emit(())
        self.state_changed.emit()

    def _save_template(self) -> None:
        self._save_template_to(self._path)

    def _export_template(self) -> None:
        self._save_template_to(None, always_choose_path=True)

    def _save_template_to(
        self,
        file_path: Path | None,
        *,
        always_choose_path: bool = False,
    ) -> None:
        template = self._template_for_current_fields()
        if template is None:
            return

        if file_path is None or always_choose_path:
            selected_path, _ = QFileDialog.getSaveFileName(
                self._window,
                "Salvar template",
                self._template_file_name(template.name),
                "Templates JSON (*.json)",
            )
            if not selected_path:
                return
            file_path = Path(selected_path)
        if file_path.suffix.lower() != ".json":
            file_path = file_path.with_suffix(".json")

        try:
            self._service.save(template, file_path)
        except TemplateError as error:
            QMessageBox.critical(
                self._window,
                "Erro ao salvar template",
                str(error),
            )
            return

        self._template = template
        self._path = file_path
        self._dirty = False
        self.state_changed.emit()
        QMessageBox.information(
            self._window,
            "Template salvo",
            f"Template salvo em:\n{file_path}",
        )

    def _template_for_current_fields(self) -> ExtractionTemplate | None:
        fields = self._fields_provider()
        if self._template is not None:
            return self._service.update(self._template, fields)

        name, accepted = QInputDialog.getText(
            self._window,
            "Salvar template",
            "Nome do template:",
        )
        if not accepted:
            return None
        try:
            return self._service.create(name, fields)
        except ValueError as error:
            QMessageBox.warning(self._window, "Nome inválido", str(error))
            return None

    def _import_template(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self._window,
            "Importar template",
            "",
            "Templates JSON (*.json)",
        )
        if not selected_path:
            return

        file_path = Path(selected_path)
        try:
            template = self._service.load(file_path)
        except TemplateError as error:
            QMessageBox.critical(self._window, "Template inválido", str(error))
            return
        if not self._confirm_replace_fields(
            "Importar o template removerá os campos atuais. Continuar?"
        ):
            return

        self._template = template
        self._path = file_path
        self._dirty = False
        self.fields_replaced.emit(template.fields)
        self.state_changed.emit()
        QMessageBox.information(
            self._window,
            "Template importado",
            f'Template "{template.name}" carregado com '
            f"{len(template.fields)} campo(s).",
        )

    def _confirm_replace_fields(self, message: str) -> bool:
        if not self._fields_provider():
            return True
        answer = QMessageBox.question(
            self._window,
            "Substituir campos?",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    @staticmethod
    def _template_file_name(name: str) -> str:
        safe_name = "".join(
            character if character.isalnum() or character in "-_ " else "_"
            for character in name
        ).strip()
        return f"{safe_name or 'template'}.json"
