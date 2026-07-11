"""Coordinate native text extraction for mapped PDF fields."""

from __future__ import annotations

from pdf_extractor.core.pdf_service import PdfService, PdfServiceError
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import ExtractionResult, ExtractionStatus


class ExtractionService:
    """Extract every field independently and normalize basic whitespace."""

    def __init__(self, pdf_service: PdfService) -> None:
        self._pdf_service = pdf_service

    def extract(
        self,
        fields: tuple[ExtractionField, ...],
    ) -> tuple[ExtractionResult, ...]:
        """Return one result per field without stopping after individual errors."""
        results: list[ExtractionResult] = []
        for field in fields:
            try:
                raw_value = self._pdf_service.extract_region_text(field.region)
                value = " ".join(raw_value.split())
                status = (
                    ExtractionStatus.SUCCESS if value else ExtractionStatus.EMPTY
                )
                result = ExtractionResult(
                    field.id,
                    field.name,
                    field.page_index,
                    value,
                    status,
                )
            except PdfServiceError as error:
                result = ExtractionResult(
                    field.id,
                    field.name,
                    field.page_index,
                    "",
                    ExtractionStatus.ERROR,
                    str(error),
                )
            results.append(result)
        return tuple(results)
