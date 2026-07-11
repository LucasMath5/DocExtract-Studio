"""Domain model for a named PDF extraction field."""

from __future__ import annotations

from dataclasses import dataclass, replace

from pdf_extractor.models.field_region import FieldRegion


@dataclass(frozen=True, slots=True)
class ExtractionField:
    """Associate a unique name and identifier with a PDF region."""

    id: str
    name: str
    region: FieldRegion
    field_type: str = "text"
    required: bool = False

    def __post_init__(self) -> None:
        normalized_id = self.id.strip()
        normalized_name = self.name.strip()
        if not normalized_id:
            raise ValueError("O identificador do campo não pode ser vazio.")
        if not normalized_name:
            raise ValueError("O nome do campo não pode ser vazio.")
        if self.field_type != "text":
            raise ValueError("O tipo inicial do campo deve ser text.")
        object.__setattr__(self, "id", normalized_id)
        object.__setattr__(self, "name", normalized_name)

    @property
    def page_index(self) -> int:
        """Return the page index stored by the field region."""
        return self.region.page_index

    def renamed(self, name: str) -> ExtractionField:
        """Return a copy with a different validated name."""
        return replace(self, name=name)
