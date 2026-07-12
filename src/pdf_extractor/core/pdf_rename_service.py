"""Build and safely execute PDF rename plans from extracted field values."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from pdf_extractor.models.batch_result import BatchDocumentResult
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import ExtractionResult


INVALID_FILENAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
REPEATED_UNDERSCORES = re.compile(r"_{2,}")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class RenamePlanStatus(StrEnum):
    """Describe whether one PDF can or could be renamed."""

    READY = "pronto"
    NO_CHANGE = "sem alteração"
    INVALID = "dados incompletos"
    CONFLICT = "conflito"
    RENAMED = "renomeado"
    ERROR = "erro"


class PdfFilenameError(ValueError):
    """Represent extracted values that cannot produce a valid PDF name."""


@dataclass(frozen=True, slots=True)
class RenamePattern:
    """Define an optional prefix and ordered fields used in PDF names."""

    field_ids: tuple[str, ...]
    prefix: str = ""
    separator: str = "-"

    def __post_init__(self) -> None:
        if not self.field_ids:
            raise ValueError("Selecione ao menos um campo para montar o nome.")
        if not self.separator:
            raise ValueError("O separador do nome não pode ser vazio.")


@dataclass(frozen=True, slots=True)
class RenamePlanItem:
    """Represent the proposed or completed rename of one processed PDF."""

    document_index: int
    source_path: Path
    destination_path: Path | None
    status: RenamePlanStatus
    message: str = ""

    @property
    def destination_name(self) -> str:
        """Return a displayable destination filename."""
        return self.destination_path.name if self.destination_path else "-"


class PdfRenameService:
    """Compose valid filenames, detect conflicts, and rename without overwrite."""

    MAX_STEM_LENGTH = 180

    def build_plan(
        self,
        documents: tuple[BatchDocumentResult, ...],
        fields: tuple[ExtractionField, ...],
        pattern: RenamePattern,
    ) -> tuple[RenamePlanItem, ...]:
        """Return one validated rename proposal per processed document."""
        field_names = {field.id: field.name for field in fields}
        unknown_fields = [
            field_id for field_id in pattern.field_ids if field_id not in field_names
        ]
        if unknown_fields:
            raise ValueError("O padrão contém campos que não existem no template.")

        prefix = self.sanitize_component(pattern.prefix) if pattern.prefix else ""
        if pattern.prefix.strip() and not prefix:
            return tuple(
                self._invalid_item(
                    index,
                    document,
                    "O prefixo não contém caracteres válidos.",
                )
                for index, document in enumerate(documents)
            )

        items = [
            self._build_document_item(
                index,
                document,
                fields,
                pattern,
            )
            for index, document in enumerate(documents)
        ]
        return self._mark_destination_conflicts(items)

    def compose_filename(
        self,
        results: tuple[ExtractionResult, ...],
        fields: tuple[ExtractionField, ...],
        pattern: RenamePattern,
    ) -> str:
        """Compose one safe PDF filename using the shared rename rules."""
        field_names = {field.id: field.name for field in fields}
        unknown_fields = [
            field_id for field_id in pattern.field_ids if field_id not in field_names
        ]
        if unknown_fields:
            raise PdfFilenameError(
                "O padrão contém campos que não existem no template."
            )
        prefix = self.sanitize_component(pattern.prefix) if pattern.prefix else ""
        if pattern.prefix.strip() and not prefix:
            raise PdfFilenameError(
                "O prefixo não contém caracteres válidos."
            )

        values_by_field = {result.field_id: result.value for result in results}
        components = [prefix] if prefix else []
        for field_id in pattern.field_ids:
            value = self.sanitize_component(values_by_field.get(field_id, ""))
            if not value:
                raise PdfFilenameError(
                    f'O campo "{field_names[field_id]}" está vazio.'
                )
            components.append(value)

        stem = pattern.separator.join(components)[: self.MAX_STEM_LENGTH]
        stem = stem.rstrip(" .")
        if stem.upper() in WINDOWS_RESERVED_NAMES:
            stem = f"_{stem}"
        return f"{stem}.pdf"

    def apply(
        self,
        plan: tuple[RenamePlanItem, ...],
    ) -> tuple[RenamePlanItem, ...]:
        """Execute ready items and preserve every non-ready result unchanged."""
        completed: list[RenamePlanItem] = []
        for item in plan:
            if (
                item.status != RenamePlanStatus.READY
                or item.destination_path is None
            ):
                completed.append(item)
                continue
            if not item.source_path.is_file():
                completed.append(
                    replace(
                        item,
                        status=RenamePlanStatus.ERROR,
                        message="O arquivo de origem não existe mais.",
                    )
                )
                continue
            if item.destination_path.exists():
                completed.append(
                    replace(
                        item,
                        status=RenamePlanStatus.CONFLICT,
                        message="Já existe um arquivo com o nome de destino.",
                    )
                )
                continue
            try:
                item.source_path.rename(item.destination_path)
            except OSError as error:
                completed.append(
                    replace(
                        item,
                        status=RenamePlanStatus.ERROR,
                        message=f"Não foi possível renomear: {error}",
                    )
                )
                continue
            completed.append(
                replace(
                    item,
                    status=RenamePlanStatus.RENAMED,
                    message="Arquivo renomeado com sucesso.",
                )
            )
        return tuple(completed)

    @staticmethod
    def sanitize_component(value: str) -> str:
        """Normalize whitespace and replace characters forbidden in filenames."""
        normalized = " ".join(value.split())
        sanitized = INVALID_FILENAME_CHARACTERS.sub("_", normalized)
        sanitized = re.sub(r"\s*_\s*", "_", sanitized)
        sanitized = REPEATED_UNDERSCORES.sub("_", sanitized)
        return sanitized.strip(" .-_")

    def _build_document_item(
        self,
        index: int,
        document: BatchDocumentResult,
        fields: tuple[ExtractionField, ...],
        pattern: RenamePattern,
    ) -> RenamePlanItem:
        if not document.file_path.is_file():
            return self._invalid_item(
                index,
                document,
                "O arquivo de origem não existe.",
            )
        try:
            file_name = self.compose_filename(
                document.results,
                fields,
                pattern,
            )
        except PdfFilenameError as error:
            return self._invalid_item(index, document, str(error))
        destination = document.file_path.with_name(file_name)
        if destination.name.casefold() == document.file_path.name.casefold():
            return RenamePlanItem(
                index,
                document.file_path,
                destination,
                RenamePlanStatus.NO_CHANGE,
                "O arquivo já possui o nome proposto.",
            )
        if destination.exists():
            return RenamePlanItem(
                index,
                document.file_path,
                destination,
                RenamePlanStatus.CONFLICT,
                "Já existe um arquivo com o nome de destino.",
            )
        return RenamePlanItem(
            index,
            document.file_path,
            destination,
            RenamePlanStatus.READY,
        )

    @staticmethod
    def _invalid_item(
        index: int,
        document: BatchDocumentResult,
        message: str,
    ) -> RenamePlanItem:
        return RenamePlanItem(
            index,
            document.file_path,
            None,
            RenamePlanStatus.INVALID,
            message,
        )

    @staticmethod
    def _mark_destination_conflicts(
        items: list[RenamePlanItem],
    ) -> tuple[RenamePlanItem, ...]:
        destination_counts: dict[str, int] = {}
        for item in items:
            if item.status != RenamePlanStatus.READY or item.destination_path is None:
                continue
            key = str(item.destination_path.absolute()).casefold()
            destination_counts[key] = destination_counts.get(key, 0) + 1

        result: list[RenamePlanItem] = []
        for item in items:
            if item.status == RenamePlanStatus.READY and item.destination_path:
                key = str(item.destination_path.absolute()).casefold()
                if destination_counts[key] > 1:
                    item = replace(
                        item,
                        status=RenamePlanStatus.CONFLICT,
                        message=(
                            "Mais de um PDF produziria o mesmo nome de destino."
                        ),
                    )
            result.append(item)
        return tuple(result)
