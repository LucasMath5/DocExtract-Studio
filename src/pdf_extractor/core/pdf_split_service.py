"""Plan and generate smaller PDFs while optionally excluding source pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import fitz


PAGE_TOKEN = re.compile(r"^(\d+)(?:\s*-\s*(\d+))?$")


class PdfSplitError(RuntimeError):
    """Represent an invalid split configuration or generation failure."""


@dataclass(frozen=True, slots=True)
class PdfSplitPart:
    """Describe one output PDF and its zero-based source pages."""

    part_number: int
    page_indices: tuple[int, ...]
    destination_path: Path

    @property
    def page_label(self) -> str:
        """Return compact one-based page numbers for display."""
        return format_page_numbers(self.page_indices)


@dataclass(frozen=True, slots=True)
class PdfSplitPlan:
    """Store a fully validated PDF split operation."""

    source_path: Path
    source_page_count: int
    pages_per_file: int
    excluded_pages: frozenset[int]
    output_directory: Path
    parts: tuple[PdfSplitPart, ...]


def parse_excluded_pages(expression: str, page_count: int) -> frozenset[int]:
    """Parse one-based pages and ranges such as ``2, 5-7``."""
    text = expression.strip()
    if not text:
        return frozenset()
    if page_count < 1:
        raise PdfSplitError("O PDF não possui páginas disponíveis.")

    excluded: set[int] = set()
    tokens = text.split(",")
    if any(not token.strip() for token in tokens):
        raise PdfSplitError("A lista de páginas contém um item vazio.")
    for token in tokens:
        match = PAGE_TOKEN.fullmatch(token.strip())
        if match is None:
            raise PdfSplitError(
                f'Página ou intervalo inválido: "{token.strip()}".'
            )
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < 1 or start > page_count or end > page_count:
            raise PdfSplitError(
                f"As páginas devem estar entre 1 e {page_count}."
            )
        if end < start:
            raise PdfSplitError(
                f'O intervalo "{token.strip()}" deve estar em ordem crescente.'
            )
        excluded.update(range(start - 1, end))
    return frozenset(excluded)


def format_page_numbers(page_indices: tuple[int, ...]) -> str:
    """Compact ordered zero-based pages into labels like ``1, 3-5``."""
    if not page_indices:
        return ""
    one_based = [page_index + 1 for page_index in page_indices]
    ranges: list[str] = []
    start = previous = one_based[0]
    for page_number in one_based[1:]:
        if page_number == previous + 1:
            previous = page_number
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = page_number
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(ranges)


class PdfSplitService:
    """Inspect PDFs, build page groups, and generate outputs without overwrite."""

    def page_count(self, source_path: Path) -> int:
        """Return the page count after validating the selected PDF."""
        document = self._open_source(source_path)
        try:
            return document.page_count
        finally:
            document.close()

    def build_plan(
        self,
        source_path: Path,
        source_page_count: int,
        pages_per_file: int,
        excluded_pages: frozenset[int],
        output_directory: Path,
    ) -> PdfSplitPlan:
        """Build deterministic output groups and filenames."""
        if source_page_count < 1:
            raise PdfSplitError("O PDF não possui páginas disponíveis.")
        if pages_per_file < 1:
            raise PdfSplitError("Cada arquivo deve conter ao menos uma página.")
        if not output_directory.is_dir():
            raise PdfSplitError("Selecione uma pasta de destino válida.")
        if any(
            page_index < 0 or page_index >= source_page_count
            for page_index in excluded_pages
        ):
            raise PdfSplitError("A exclusão contém uma página inexistente.")

        remaining_pages = tuple(
            page_index
            for page_index in range(source_page_count)
            if page_index not in excluded_pages
        )
        if not remaining_pages:
            raise PdfSplitError("Todas as páginas foram excluídas da geração.")

        page_groups = tuple(
            remaining_pages[index : index + pages_per_file]
            for index in range(0, len(remaining_pages), pages_per_file)
        )
        parts: list[PdfSplitPart] = []
        for part_number, page_indices in enumerate(page_groups, start=1):
            page_suffix = format_page_numbers(page_indices).replace(", ", "_")
            file_name = (
                f"{source_path.stem}_parte_{part_number:03d}_"
                f"paginas_{page_suffix}.pdf"
            )
            destination = output_directory / file_name
            if destination.exists():
                raise PdfSplitError(
                    f'Já existe um arquivo de destino chamado "{file_name}".'
                )
            parts.append(PdfSplitPart(part_number, page_indices, destination))

        return PdfSplitPlan(
            source_path=source_path,
            source_page_count=source_page_count,
            pages_per_file=pages_per_file,
            excluded_pages=excluded_pages,
            output_directory=output_directory,
            parts=tuple(parts),
        )

    def split(self, plan: PdfSplitPlan) -> tuple[Path, ...]:
        """Generate every planned PDF and roll back outputs after any failure."""
        source = self._open_source(plan.source_path)
        created_paths: list[Path] = []
        try:
            if source.page_count != plan.source_page_count:
                raise PdfSplitError(
                    "O número de páginas do PDF mudou desde a criação da prévia."
                )
            for part in plan.parts:
                destination = part.destination_path
                if destination.exists():
                    raise PdfSplitError(
                        f'Já existe o arquivo "{destination.name}".'
                    )
                temporary_path = destination.with_name(
                    f".{destination.stem}.{uuid4().hex}.tmp.pdf"
                )
                destination_claimed = False
                try:
                    output = fitz.open()
                    try:
                        for page_index in part.page_indices:
                            output.insert_pdf(
                                source,
                                from_page=page_index,
                                to_page=page_index,
                            )
                        metadata = {
                            key: value
                            for key, value in source.metadata.items()
                            if value
                        }
                        if metadata:
                            output.set_metadata(metadata)
                        output.save(temporary_path)
                    finally:
                        output.close()
                    with destination.open("xb"):
                        destination_claimed = True
                    temporary_path.replace(destination)
                    destination_claimed = False
                except FileExistsError as error:
                    raise PdfSplitError(
                        f'Já existe o arquivo "{destination.name}".'
                    ) from error
                finally:
                    temporary_path.unlink(missing_ok=True)
                    if destination_claimed:
                        destination.unlink(missing_ok=True)
                created_paths.append(destination)
        except PdfSplitError:
            self._remove_partial_outputs(created_paths)
            raise
        except (OSError, RuntimeError, ValueError) as error:
            self._remove_partial_outputs(created_paths)
            raise PdfSplitError(
                "Não foi possível gerar todos os PDFs divididos."
            ) from error
        finally:
            source.close()
        return tuple(created_paths)

    @staticmethod
    def _open_source(source_path: Path) -> fitz.Document:
        if source_path.suffix.casefold() != ".pdf":
            raise PdfSplitError("Selecione um arquivo com a extensão .pdf.")
        try:
            document = fitz.open(source_path)
        except (OSError, RuntimeError, ValueError) as error:
            raise PdfSplitError(
                "Não foi possível abrir o PDF para divisão. "
                "O arquivo pode estar inválido ou corrompido."
            ) from error
        if document.needs_pass:
            document.close()
            raise PdfSplitError("PDFs protegidos por senha não podem ser divididos.")
        if document.page_count < 1:
            document.close()
            raise PdfSplitError("O PDF selecionado não possui páginas.")
        return document

    @staticmethod
    def _remove_partial_outputs(
        created_paths: list[Path],
    ) -> None:
        for path in created_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
