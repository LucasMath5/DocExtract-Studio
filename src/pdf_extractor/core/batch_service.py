"""Sequential, cancellable processing of PDFs with one extraction template."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from pathlib import Path

from pdf_extractor.core.extraction_service import ExtractionService
from pdf_extractor.core.pdf_service import PdfService, PdfServiceError
from pdf_extractor.models.batch_result import (
    BatchDocumentResult,
    BatchDocumentStatus,
    BatchReport,
)
from pdf_extractor.models.extraction_result import ExtractionStatus
from pdf_extractor.models.extraction_template import ExtractionTemplate
from pdf_extractor.ocr.base import OcrEngine
from pdf_extractor.ocr.tesseract_service import TesseractService


LOGGER = logging.getLogger(__name__)


class BatchError(RuntimeError):
    """Represent a batch that cannot be started."""


class BatchService:
    """Apply one template to files without stopping after individual failures."""

    def __init__(
        self,
        pdf_service_factory: Callable[[], PdfService] = PdfService,
        ocr_engine: OcrEngine | None = None,
    ) -> None:
        self._pdf_service_factory = pdf_service_factory
        self._ocr_engine = ocr_engine or TesseractService()

    def process(
        self,
        file_paths: Iterable[Path],
        template: ExtractionTemplate,
        *,
        progress_callback: Callable[[int, int, BatchDocumentResult], None]
        | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> BatchReport:
        """Process files in order and check cancellation between documents."""
        paths = tuple(Path(path) for path in file_paths)
        if not paths:
            raise BatchError("Selecione ao menos um arquivo PDF.")
        if not template.fields:
            raise BatchError("O template selecionado não possui campos.")

        results: list[BatchDocumentResult] = []
        is_cancelled = cancellation_requested or (lambda: False)
        for file_path in paths:
            if is_cancelled():
                break
            document_result = self._process_document(file_path, template)
            results.append(document_result)
            if progress_callback is not None:
                progress_callback(len(results), len(paths), document_result)

        return BatchReport(
            template_name=template.name,
            total=len(paths),
            documents=tuple(results),
            cancelled=len(results) < len(paths) and is_cancelled(),
        )

    def _process_document(
        self,
        file_path: Path,
        template: ExtractionTemplate,
    ) -> BatchDocumentResult:
        pdf_service = self._pdf_service_factory()
        try:
            pdf_service.open_document(file_path)
            field_results = ExtractionService(
                pdf_service,
                self._ocr_engine,
            ).extract(template.fields)
        except PdfServiceError as error:
            return BatchDocumentResult(
                file_path=file_path,
                results=(),
                status=BatchDocumentStatus.FAILURE,
                error_message=str(error),
            )
        except Exception:
            LOGGER.exception("Falha inesperada ao processar %s", file_path)
            return BatchDocumentResult(
                file_path=file_path,
                results=(),
                status=BatchDocumentStatus.FAILURE,
                error_message="Ocorreu um erro inesperado ao processar o PDF.",
            )
        finally:
            pdf_service.close()

        failed_fields = [
            result
            for result in field_results
            if result.status == ExtractionStatus.ERROR
        ]
        if failed_fields:
            errors = "; ".join(
                f"{result.field_name}: {result.error_message or 'erro de extração'}"
                for result in failed_fields
            )
            status = BatchDocumentStatus.FAILURE
            error_message = errors
        elif any(
            result.status == ExtractionStatus.EMPTY for result in field_results
        ):
            status = BatchDocumentStatus.REVIEW_NEEDED
            error_message = None
        else:
            status = BatchDocumentStatus.SUCCESS
            error_message = None

        return BatchDocumentResult(
            file_path=file_path,
            results=field_results,
            status=status,
            error_message=error_message,
        )
