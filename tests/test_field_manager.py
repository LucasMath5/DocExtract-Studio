"""Tests for named field domain rules and ordered management."""

from __future__ import annotations

import pytest

from pdf_extractor.core.field_manager import FieldManager, FieldValidationError
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.field_region import FieldRegion


def region(page_index: int = 0) -> FieldRegion:
    """Return a valid generic region for field tests."""
    return FieldRegion(page_index, 10, 20, 30, 40)


def test_extraction_field_defaults_and_page() -> None:
    """A new field should default to text, optional, and expose its page."""
    field = ExtractionField("id-1", " Cliente ", region(page_index=2))

    assert field.id == "id-1"
    assert field.name == "Cliente"
    assert field.page_index == 2
    assert field.field_type == "text"
    assert field.required is False


def test_manager_creates_ordered_unique_ids_and_names() -> None:
    """Created fields should retain order and receive unique identifiers."""
    ids = iter(["field-1", "field-2"])
    manager = FieldManager(id_factory=lambda: next(ids))

    first = manager.create("Cliente", region())
    second = manager.create("Data", region(page_index=1))

    assert first.id == "field-1"
    assert second.id == "field-2"
    assert manager.fields == (first, second)


@pytest.mark.parametrize("name", ["", "   "])
def test_manager_rejects_empty_names(name: str) -> None:
    """Blank names should be rejected before a field is created."""
    manager = FieldManager()

    with pytest.raises(FieldValidationError, match="não pode ser vazio"):
        manager.create(name, region())


def test_manager_rejects_case_insensitive_duplicate_names() -> None:
    """Names should be unique after trimming and case folding."""
    manager = FieldManager()
    manager.create("Valor Total", region())

    with pytest.raises(FieldValidationError, match="Já existe"):
        manager.create("  VALOR TOTAL  ", region(page_index=1))


def test_rename_preserves_identity_and_region() -> None:
    """Renaming should change only the field name."""
    manager = FieldManager(id_factory=lambda: "field-1")
    original = manager.create("Cliente", region())

    renamed = manager.rename(original.id, "Nome do cliente")

    assert renamed.id == original.id
    assert renamed.region == original.region
    assert renamed.name == "Nome do cliente"


def test_delete_and_clear_fields() -> None:
    """Delete should remove one field and clear should remove all remaining."""
    ids = iter(["field-1", "field-2"])
    manager = FieldManager(id_factory=lambda: next(ids))
    first = manager.create("Primeiro", region())
    manager.create("Segundo", region())

    manager.delete(first.id)
    assert [field.name for field in manager.fields] == ["Segundo"]

    manager.clear()
    assert manager.fields == ()


def test_replace_all_restores_ordered_template_fields() -> None:
    """A manager should restore fields from a validated template in order."""
    manager = FieldManager()
    fields = (
        ExtractionField("field-2", "Data", region(1)),
        ExtractionField("field-1", "Cliente", region()),
    )

    manager.replace_all(fields)

    assert manager.fields == fields
