"""Business rules for creating and managing named extraction fields."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.field_region import FieldRegion


class FieldValidationError(ValueError):
    """Represent a user-correctable field validation error."""


class FieldManager:
    """Maintain ordered fields and enforce unique, non-empty names."""

    def __init__(self, id_factory: Callable[[], str] | None = None) -> None:
        self._fields: list[ExtractionField] = []
        self._id_factory = id_factory or (lambda: str(uuid4()))

    @property
    def fields(self) -> tuple[ExtractionField, ...]:
        """Return the fields in creation order."""
        return tuple(self._fields)

    def create(self, name: str, region: FieldRegion) -> ExtractionField:
        """Create a text field after validating its normalized name."""
        normalized_name = self._validated_name(name)
        field = ExtractionField(
            id=self._id_factory(),
            name=normalized_name,
            region=region,
        )
        self._fields.append(field)
        return field

    def rename(self, field_id: str, name: str) -> ExtractionField:
        """Rename one field without changing its identifier or region."""
        index = self._index_of(field_id)
        normalized_name = self._validated_name(name, ignored_id=field_id)
        renamed_field = self._fields[index].renamed(normalized_name)
        self._fields[index] = renamed_field
        return renamed_field

    def delete(self, field_id: str) -> None:
        """Delete one field by identifier."""
        del self._fields[self._index_of(field_id)]

    def get(self, field_id: str) -> ExtractionField | None:
        """Find a field by identifier."""
        return next((field for field in self._fields if field.id == field_id), None)

    def clear(self) -> None:
        """Remove all fields."""
        self._fields.clear()

    def replace_all(self, fields: tuple[ExtractionField, ...]) -> None:
        """Replace all fields after validating identifiers and unique names."""
        field_ids = [field.id for field in fields]
        field_names = [field.name.casefold() for field in fields]
        if len(field_ids) != len(set(field_ids)):
            raise FieldValidationError(
                "Os identificadores dos campos devem ser únicos."
            )
        if len(field_names) != len(set(field_names)):
            raise FieldValidationError("Os nomes dos campos devem ser únicos.")
        self._fields = list(fields)

    def _validated_name(self, name: str, ignored_id: str | None = None) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise FieldValidationError("O nome do campo não pode ser vazio.")
        comparable_name = normalized_name.casefold()
        if any(
            field.id != ignored_id and field.name.casefold() == comparable_name
            for field in self._fields
        ):
            raise FieldValidationError("Já existe um campo com esse nome.")
        return normalized_name

    def _index_of(self, field_id: str) -> int:
        for index, field in enumerate(self._fields):
            if field.id == field_id:
                return index
        raise KeyError(f"Campo não encontrado: {field_id}")
