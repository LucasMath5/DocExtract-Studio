"""Coordinate native text extraction for mapped PDF fields."""

from __future__ import annotations

from pdf_extractor.core.pdf_service import PdfService, PdfServiceError
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import (
    ExtractionMethod,
    ExtractionResult,
    ExtractionStatus,
)
from pdf_extractor.ocr.base import OcrEngine, OcrError
from pdf_extractor.ocr.tesseract_service import TesseractService


class ExtractionService:
    """Extract every field independently and normalize basic whitespace."""

    def __init__(
        self,
        pdf_service: PdfService,
        ocr_engine: OcrEngine | None = None,
    ) -> None:
        self._pdf_service = pdf_service
        self._ocr_engine = ocr_engine or TesseractService()

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
                method = ExtractionMethod.NATIVE_TEXT
                if not value:
                    region_image = self._pdf_service.render_region(field.region)
                    raw_value = self._ocr_engine.recognize(region_image)
                    value = " ".join(raw_value.split())
                    method = ExtractionMethod.OCR
                status = ExtractionStatus.SUCCESS if value else ExtractionStatus.EMPTY
                result = ExtractionResult(
                    field.id,
                    field.name,
                    field.page_index,
                    value,
                    status,
                    method=method,
                )
            except (PdfServiceError, OcrError) as error:
                result = ExtractionResult(
                    field.id,
                    field.name,
                    field.page_index,
                    "",
                    ExtractionStatus.ERROR,
                    str(error),
                    ExtractionMethod.OCR if isinstance(error, OcrError) else None,
                )
            results.append(result)
        return tuple(results)
