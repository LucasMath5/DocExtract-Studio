"""JSON persistence and validation for reusable extraction templates."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_template import (
    CURRENT_TEMPLATE_SCHEMA_VERSION,
    ExtractionTemplate,
)
from pdf_extractor.models.field_region import FieldRegion


class TemplateError(RuntimeError):
    """Represent a template file that cannot be read, validated, or saved."""


class TemplateService:
    """Create and persist versioned extraction templates as portable JSON."""

    def __init__(
        self,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def create(
        self,
        name: str,
        fields: tuple[ExtractionField, ...],
    ) -> ExtractionTemplate:
        """Create a new template with current UTC timestamps."""
        now = self._now()
        return ExtractionTemplate(
            name=name,
            schema_version=CURRENT_TEMPLATE_SCHEMA_VERSION,
            created_at=now,
            modified_at=now,
            fields=fields,
        )

    def update(
        self,
        template: ExtractionTemplate,
        fields: tuple[ExtractionField, ...],
    ) -> ExtractionTemplate:
        """Return a template containing the latest ordered fields."""
        return template.with_fields(fields, self._now())

    def save(self, template: ExtractionTemplate, file_path: Path) -> None:
        """Serialize a template to a UTF-8 JSON file."""
        try:
            file_path.write_text(self.dumps(template), encoding="utf-8")
        except OSError as error:
            raise TemplateError(
                f"Não foi possível salvar o template em '{file_path}'."
            ) from error

    def load(self, file_path: Path) -> ExtractionTemplate:
        """Read and validate a template from a JSON file."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise TemplateError(
                f"Não foi possível ler o template '{file_path}'."
            ) from error
        return self.loads(content)

    def dumps(self, template: ExtractionTemplate) -> str:
        """Return the stable, human-readable JSON representation."""
        payload = {
            "schema_version": template.schema_version,
            "name": template.name,
            "created_at": self._format_datetime(template.created_at),
            "modified_at": self._format_datetime(template.modified_at),
            "fields": [self._serialize_field(field) for field in template.fields],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    def loads(self, content: str) -> ExtractionTemplate:
        """Deserialize JSON content and report validation errors clearly."""
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise TemplateError(
                f"JSON inválido na linha {error.lineno}, coluna {error.colno}."
            ) from error

        try:
            data = self._mapping(payload, "a raiz do template")
            schema_version = self._integer(data.get("schema_version"), "schema_version")
            if schema_version != CURRENT_TEMPLATE_SCHEMA_VERSION:
                raise ValueError(
                    "versão de schema não suportada: "
                    f"{schema_version}; esperada: {CURRENT_TEMPLATE_SCHEMA_VERSION}"
                )
            raw_fields = data.get("fields")
            if not isinstance(raw_fields, list):
                raise ValueError("'fields' deve ser uma lista")
            fields = tuple(
                self._deserialize_field(raw_field, index)
                for index, raw_field in enumerate(raw_fields)
            )
            return ExtractionTemplate(
                name=self._string(data.get("name"), "name"),
                schema_version=schema_version,
                created_at=self._datetime(data.get("created_at"), "created_at"),
                modified_at=self._datetime(
                    data.get("modified_at"),
                    "modified_at",
                ),
                fields=fields,
            )
        except (TypeError, ValueError) as error:
            raise TemplateError(f"Template inválido: {error}.") from error

    def _now(self) -> datetime:
        value = self._now_factory()
        if value.tzinfo is None:
            raise ValueError("O relógio do serviço deve fornecer uma data com fuso.")
        return value

    @staticmethod
    def _serialize_field(field: ExtractionField) -> dict[str, Any]:
        region = field.region
        return {
            "id": field.id,
            "name": field.name,
            "type": field.field_type,
            "required": field.required,
            "region": {
                "page_index": region.page_index,
                "x": region.x,
                "y": region.y,
                "width": region.width,
                "height": region.height,
            },
        }

    def _deserialize_field(
        self,
        value: object,
        index: int,
    ) -> ExtractionField:
        label = f"fields[{index}]"
        data = self._mapping(value, label)
        region_data = self._mapping(data.get("region"), f"{label}.region")
        required = data.get("required")
        if not isinstance(required, bool):
            raise ValueError(f"'{label}.required' deve ser booleano")
        return ExtractionField(
            id=self._string(data.get("id"), f"{label}.id"),
            name=self._string(data.get("name"), f"{label}.name"),
            field_type=self._string(data.get("type"), f"{label}.type"),
            required=required,
            region=FieldRegion(
                page_index=self._integer(
                    region_data.get("page_index"),
                    f"{label}.region.page_index",
                ),
                x=self._number(region_data.get("x"), f"{label}.region.x"),
                y=self._number(region_data.get("y"), f"{label}.region.y"),
                width=self._number(
                    region_data.get("width"),
                    f"{label}.region.width",
                ),
                height=self._number(
                    region_data.get("height"),
                    f"{label}.region.height",
                ),
            ),
        )

    @staticmethod
    def _mapping(value: object, label: str) -> Mapping[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"'{label}' deve ser um objeto")
        return value

    @staticmethod
    def _string(value: object, label: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"'{label}' deve ser texto")
        return value

    @staticmethod
    def _integer(value: object, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"'{label}' deve ser um número inteiro")
        return value

    @staticmethod
    def _number(value: object, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"'{label}' deve ser um número")
        return float(value)

    @staticmethod
    def _datetime(value: object, label: str) -> datetime:
        text = TemplateService._string(value, label)
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"'{label}' deve usar o formato ISO 8601") from error
        if parsed.tzinfo is None:
            raise ValueError(f"'{label}' deve incluir o fuso horário")
        return parsed

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        utc_value = value.astimezone(timezone.utc)
        return utc_value.isoformat().replace("+00:00", "Z")
