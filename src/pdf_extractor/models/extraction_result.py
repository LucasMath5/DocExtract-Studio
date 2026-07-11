"""Models returned by native PDF text extraction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExtractionStatus(StrEnum):
    """Describe whether one field produced text, was empty, or failed."""

    SUCCESS = "sucesso"
    EMPTY = "vazio"
    ERROR = "erro"


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Store the extracted value and status for one mapped field."""

    field_id: str
    field_name: str
    page_index: int
    value: str
    status: ExtractionStatus
    error_message: str | None = None
