"""Extract, name, and generate one-page PDFs from a multi-page document."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

import fitz

from pdf_extractor.core.extraction_service import ExtractionService
from pdf_extractor.core.pdf_rename_service import (
    PdfFilenameError,
    PdfRenameService,
    RenamePattern,
)
from pdf_extractor.core.pdf_service import PdfService, PdfServiceError
from pdf_extractor.models.batch_result import BatchDocumentStatus
from pdf_extractor.models.extraction_field import ExtractionField
from pdf_extractor.models.extraction_result import ExtractionResult, ExtractionStatus
from pdf_extractor.models.extraction_template import ExtractionTemplate
from pdf_extractor.models.page_template_result import (
    PageTemplateReport,
    PageTemplateResult,
)
from pdf_extractor.ocr.base import OcrEngine
from pdf_extractor.ocr.tesseract_service import TesseractService


class PageTemplateError(RuntimeError):
    """Represent a page-template workflow that cannot be started."""


class PageOutputStatus(StrEnum):
    """Describe whether one extracted page can or could be generated."""

    READY = "pronto"
    INCOMPLETE = "dados incompletos"
    CONFLICT = "conflito"
    GENERATED = "gerado"
    ERROR = "erro"


@dataclass(frozen=True, slots=True)
class PageOutputItem:
    """Represent one proposed or completed one-page output PDF."""

    result_index: int
    page_index: int
    destination_path: Path | None
    status: PageOutputStatus
    message: str = ""

    @property
    def destination_name(self) -> str:
        return self.destination_path.name if self.destination_path else "-"


class PageTemplateService:
    """Apply template coordinates to each selected page and generate outputs."""

    def __init__(self, ocr_engine: OcrEngine | None = None) -> None:
        self._ocr_engine = ocr_engine or TesseractService()
        self._rename_service = PdfRenameService()

    def process(
        self,
        source_path: Path,
        template: ExtractionTemplate,
        excluded_pages: frozenset[int],
        *,
        progress_callback: Callable[[int, int, PageTemplateResult], None]
        | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> PageTemplateReport:
        """Extract every non-excluded page and check cancellation between pages."""
        if not template.fields:
            raise PageTemplateError("O template selecionado não possui campos.")
        pdf_service = PdfService()
        try:
            info = pdf_service.open_document(source_path)
        except PdfServiceError as error:
            raise PageTemplateError(str(error)) from error
        if any(
            page_index < 0 or page_index >= info.page_count
            for page_index in excluded_pages
        ):
            pdf_service.close()
            raise PageTemplateError("A exclusão contém uma página inexistente.")
        selected_pages = tuple(
            page_index
            for page_index in range(info.page_count)
            if page_index not in excluded_pages
        )
        if not selected_pages:
            pdf_service.close()
            raise PageTemplateError("Todas as páginas foram excluídas.")

        extraction_service = ExtractionService(pdf_service, self._ocr_engine)
        is_cancelled = cancellation_requested or (lambda: False)
        page_results: list[PageTemplateResult] = []
        try:
            for page_index in selected_pages:
                if is_cancelled():
                    break
                fields = self._fields_for_page(template.fields, page_index)
                results = extraction_service.extract(fields)
                page_result = self._page_result(page_index, results)
                page_results.append(page_result)
                if progress_callback is not None:
                    progress_callback(
                        len(page_results),
                        len(selected_pages),
                        page_result,
                    )
        finally:
            pdf_service.close()
        return PageTemplateReport(
            source_path=source_path,
            source_page_count=info.page_count,
            excluded_pages=excluded_pages,
            pages=tuple(page_results),
            cancelled=len(page_results) < len(selected_pages) and is_cancelled(),
        )

    def build_output_plan(
        self,
        report: PageTemplateReport,
        fields: tuple[ExtractionField, ...],
        pattern: RenamePattern,
        output_directory: Path,
    ) -> tuple[PageOutputItem, ...]:
        """Compose safe filenames and mark duplicates or existing destinations."""
        if not output_directory.is_dir():
            raise PageTemplateError("Selecione uma pasta de destino válida.")
        items: list[PageOutputItem] = []
        for result_index, page in enumerate(report.pages):
            try:
                file_name = self._rename_service.compose_filename(
                    page.results,
                    fields,
                    pattern,
                )
            except PdfFilenameError as error:
                items.append(
                    PageOutputItem(
                        result_index,
                        page.page_index,
                        None,
                        PageOutputStatus.INCOMPLETE,
                        str(error),
                    )
                )
                continue
            destination = output_directory / file_name
            if destination.exists():
                items.append(
                    PageOutputItem(
                        result_index,
                        page.page_index,
                        destination,
                        PageOutputStatus.CONFLICT,
                        "Já existe um arquivo com o nome de destino.",
                    )
                )
                continue
            items.append(
                PageOutputItem(
                    result_index,
                    page.page_index,
                    destination,
                    PageOutputStatus.READY,
                )
            )
        return self._mark_duplicate_destinations(items)

    def generate(
        self,
        report: PageTemplateReport,
        plan: tuple[PageOutputItem, ...],
    ) -> tuple[PageOutputItem, ...]:
        """Generate ready one-page PDFs atomically and continue after failures."""
        try:
            source = fitz.open(report.source_path)
        except (OSError, RuntimeError, ValueError) as error:
            raise PageTemplateError(
                "Não foi possível reabrir o PDF original."
            ) from error
        completed: list[PageOutputItem] = []
        try:
            if source.page_count != report.source_page_count:
                raise PageTemplateError(
                    "O número de páginas do PDF mudou após a extração."
                )
            for item in plan:
                if (
                    item.status != PageOutputStatus.READY
                    or item.destination_path is None
                ):
                    completed.append(item)
                    continue
                completed.append(self._generate_item(source, item))
        finally:
            source.close()
        return tuple(completed)

    @staticmethod
    def _fields_for_page(
        fields: tuple[ExtractionField, ...],
        page_index: int,
    ) -> tuple[ExtractionField, ...]:
        return tuple(
            replace(
                field,
                region=replace(field.region, page_index=page_index),
            )
            for field in fields
        )

    @staticmethod
    def _page_result(
        page_index: int,
        results: tuple[ExtractionResult, ...],
    ) -> PageTemplateResult:
        failed = [
            result
            for result in results
            if result.status == ExtractionStatus.ERROR
        ]
        if failed:
            status = BatchDocumentStatus.FAILURE
            message = "; ".join(
                f"{result.field_name}: {result.error_message or 'erro de extração'}"
                for result in failed
            )
        elif any(result.status == ExtractionStatus.EMPTY for result in results):
            status = BatchDocumentStatus.REVIEW_NEEDED
            message = None
        else:
            status = BatchDocumentStatus.SUCCESS
            message = None
        return PageTemplateResult(page_index, results, status, message)

    @staticmethod
    def _mark_duplicate_destinations(
        items: list[PageOutputItem],
    ) -> tuple[PageOutputItem, ...]:
        counts: dict[str, int] = {}
        for item in items:
            if item.status == PageOutputStatus.READY and item.destination_path:
                key = str(item.destination_path.absolute()).casefold()
                counts[key] = counts.get(key, 0) + 1
        result: list[PageOutputItem] = []
        for item in items:
            if item.status == PageOutputStatus.READY and item.destination_path:
                key = str(item.destination_path.absolute()).casefold()
                if counts[key] > 1:
                    item = replace(
                        item,
                        status=PageOutputStatus.CONFLICT,
                        message="Mais de uma página produziria o mesmo nome.",
                    )
            result.append(item)
        return tuple(result)

    @staticmethod
    def _generate_item(
        source: fitz.Document,
        item: PageOutputItem,
    ) -> PageOutputItem:
        destination = item.destination_path
        if destination is None:
            return item
        if destination.exists():
            return replace(
                item,
                status=PageOutputStatus.CONFLICT,
                message="Já existe um arquivo com o nome de destino.",
            )
        temporary = destination.with_name(
            f".{destination.stem}.{uuid4().hex}.tmp.pdf"
        )
        destination_claimed = False
        try:
            output = fitz.open()
            try:
                output.insert_pdf(
                    source,
                    from_page=item.page_index,
                    to_page=item.page_index,
                )
                metadata = {
                    key: value for key, value in source.metadata.items() if value
                }
                if metadata:
                    output.set_metadata(metadata)
                output.save(temporary)
            finally:
                output.close()
            with destination.open("xb"):
                destination_claimed = True
            temporary.replace(destination)
            destination_claimed = False
        except FileExistsError:
            return replace(
                item,
                status=PageOutputStatus.CONFLICT,
                message="Já existe um arquivo com o nome de destino.",
            )
        except (OSError, RuntimeError, ValueError) as error:
            return replace(
                item,
                status=PageOutputStatus.ERROR,
                message=f"Não foi possível gerar a página: {error}",
            )
        finally:
            temporary.unlink(missing_ok=True)
            if destination_claimed:
                destination.unlink(missing_ok=True)
        return replace(
            item,
            status=PageOutputStatus.GENERATED,
            message="PDF gerado com sucesso.",
        )
