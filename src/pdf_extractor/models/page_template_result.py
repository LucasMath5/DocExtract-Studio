"""Models for applying one extraction template independently to PDF pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pdf_extractor.models.batch_result import BatchDocumentStatus
from pdf_extractor.models.extraction_result import ExtractionResult


@dataclass(frozen=True, slots=True)
class PageTemplateResult:
    """Store extraction values and status for one original PDF page."""

    page_index: int
    results: tuple[ExtractionResult, ...]
    status: BatchDocumentStatus
    error_message: str | None = None

    @property
    def page_number(self) -> int:
        """Return the user-facing one-based page number."""
        return self.page_index + 1


@dataclass(frozen=True, slots=True)
class PageTemplateReport:
    """Summarize template extraction across selected pages of one PDF."""

    source_path: Path
    source_page_count: int
    excluded_pages: frozenset[int]
    pages: tuple[PageTemplateResult, ...]
    cancelled: bool = False

    @property
    def processed(self) -> int:
        return len(self.pages)
