"""Domain models returned by batch PDF extraction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pdf_extractor.models.extraction_result import ExtractionResult


class BatchDocumentStatus(StrEnum):
    """Describe the technical outcome of processing one PDF."""

    SUCCESS = "sucesso"
    REVIEW_NEEDED = "revisão necessária"
    FAILURE = "falha"


@dataclass(frozen=True, slots=True)
class BatchDocumentResult:
    """Store extraction values and an optional error for one source file."""

    file_path: Path
    results: tuple[ExtractionResult, ...]
    status: BatchDocumentStatus
    error_message: str | None = None

    @property
    def file_name(self) -> str:
        """Return only the source filename for display and export."""
        return self.file_path.name

    @property
    def empty_count(self) -> int:
        """Count fields whose native extraction returned no text."""
        return sum(not result.value for result in self.results)


@dataclass(frozen=True, slots=True)
class BatchReport:
    """Summarize a possibly cancelled batch run."""

    template_name: str
    total: int
    documents: tuple[BatchDocumentResult, ...]
    cancelled: bool = False

    @property
    def processed(self) -> int:
        """Return the number of files that reached a final result."""
        return len(self.documents)

    def count(self, status: BatchDocumentStatus) -> int:
        """Count documents with one batch status."""
        return sum(document.status == status for document in self.documents)

    @property
    def success_count(self) -> int:
        return self.count(BatchDocumentStatus.SUCCESS)

    @property
    def review_count(self) -> int:
        return self.count(BatchDocumentStatus.REVIEW_NEEDED)

    @property
    def failure_count(self) -> int:
        return self.count(BatchDocumentStatus.FAILURE)
