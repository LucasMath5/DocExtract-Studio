"""Tests for reusable JSON extraction templates."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pdf_extractor.core.template_service import TemplateError, TemplateService
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.field_region import FieldRegion


def sample_fields() -> tuple[ExtractionField, ...]:
    """Return ordered generic fields for template tests."""
    return (
        ExtractionField(
            id="field-1",
            name="Razão social",
            region=FieldRegion(0, 10.5, 20.25, 180, 24),
        ),
        ExtractionField(
            id="field-2",
            name="Data",
            region=FieldRegion(1, 15, 50, 90, 18),
        ),
    )


def test_template_json_round_trip_preserves_metadata_and_fields() -> None:
    """Serialization should preserve Unicode, order, coordinates, and metadata."""
    now = datetime(2026, 7, 11, 14, 30, tzinfo=timezone.utc)
    service = TemplateService(now_factory=lambda: now)
    template = service.create("Documento genérico", sample_fields())

    content = service.dumps(template)
    restored = service.loads(content)
    payload = json.loads(content)

    assert restored == template
    assert [field.name for field in restored.fields] == ["Razão social", "Data"]
    assert payload["schema_version"] == 1
    assert "pdf" not in content.casefold()
    assert "path" not in content.casefold()


def test_template_save_load_and_update_dates(tmp_path: Path) -> None:
    """Saving and editing should preserve creation time and advance modification."""
    created_at = datetime(2026, 7, 11, 10, tzinfo=timezone.utc)
    modified_at = created_at + timedelta(hours=2)
    times = iter([created_at, modified_at])
    service = TemplateService(now_factory=lambda: next(times))
    template = service.create("Notas", sample_fields())
    updated = service.update(template, sample_fields()[:1])
    destination = tmp_path / "notas.json"

    service.save(updated, destination)
    restored = service.load(destination)

    assert restored.created_at == created_at
    assert restored.modified_at == modified_at
    assert restored.fields == sample_fields()[:1]


@pytest.mark.parametrize(
    ("content", "expected_message"),
    [
        ("{", "JSON inválido"),
        (
            '{"schema_version": 99, "name": "Teste", "fields": []}',
            "versão de schema não suportada",
        ),
        (
            """{
              "schema_version": 1,
              "name": "Teste",
              "created_at": "2026-07-11T10:00:00Z",
              "modified_at": "2026-07-11T10:00:00Z",
              "fields": {}
            }""",
            "'fields' deve ser uma lista",
        ),
    ],
)
def test_invalid_templates_have_clear_messages(
    content: str,
    expected_message: str,
) -> None:
    """Malformed or unsupported templates should fail with actionable messages."""
    with pytest.raises(TemplateError, match=expected_message):
        TemplateService().loads(content)


def test_duplicate_field_names_are_rejected() -> None:
    """Templates should enforce field-name uniqueness case-insensitively."""
    payload = json.loads(
        TemplateService(
            now_factory=lambda: datetime(2026, 7, 11, tzinfo=timezone.utc)
        ).dumps(
            TemplateService(
                now_factory=lambda: datetime(2026, 7, 11, tzinfo=timezone.utc)
            ).create("Teste", sample_fields())
        )
    )
    payload["fields"][1]["name"] = "RAZÃO SOCIAL"

    with pytest.raises(TemplateError, match="nomes de campo duplicados"):
        TemplateService().loads(json.dumps(payload))
