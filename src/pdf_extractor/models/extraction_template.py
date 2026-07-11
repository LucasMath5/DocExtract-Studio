"""Domain model for reusable extraction templates."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from pdf_extractor.models.extraction_field import ExtractionField


CURRENT_TEMPLATE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ExtractionTemplate:
    """Describe an ordered field mapping independently from any PDF path."""

    name: str
    schema_version: int
    created_at: datetime
    modified_at: datetime
    fields: tuple[ExtractionField, ...]

    def __post_init__(self) -> None:
        normalized_name = self.name.strip()
        if not normalized_name:
            raise ValueError("O nome do template não pode ser vazio.")
        if self.schema_version != CURRENT_TEMPLATE_SCHEMA_VERSION:
            raise ValueError(
                "Versão de schema não suportada: "
                f"{self.schema_version}. Esperada: {CURRENT_TEMPLATE_SCHEMA_VERSION}."
            )
        if self.created_at.tzinfo is None or self.modified_at.tzinfo is None:
            raise ValueError("As datas do template devem incluir o fuso horário.")
        if self.modified_at < self.created_at:
            raise ValueError(
                "A data de modificação não pode ser anterior à data de criação."
            )

        fields = tuple(self.fields)
        field_ids = [field.id for field in fields]
        field_names = [field.name.casefold() for field in fields]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("O template contém identificadores de campo duplicados.")
        if len(field_names) != len(set(field_names)):
            raise ValueError("O template contém nomes de campo duplicados.")

        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "fields", fields)

    def with_fields(
        self,
        fields: tuple[ExtractionField, ...],
        modified_at: datetime,
    ) -> ExtractionTemplate:
        """Return an updated template while preserving its creation metadata."""
        return replace(self, fields=fields, modified_at=modified_at)
