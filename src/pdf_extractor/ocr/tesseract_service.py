"""Tesseract OCR integration with portable executable discovery."""

from __future__ import annotations

import os
import shutil
from io import BytesIO
from pathlib import Path
from threading import Lock

import pytesseract
from PIL import Image, UnidentifiedImageError

from pdf_extractor.ocr.base import OcrError, OcrUnavailableError


DEFAULT_OCR_LANGUAGE = "por+eng"
DEFAULT_TESSERACT_TIMEOUT = 20


def find_tesseract_executable() -> Path | None:
    """Find Tesseract from configuration, PATH, or Windows program folders."""
    configured = os.getenv("TESSERACT_CMD")
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_file():
            return configured_path

    path_command = shutil.which("tesseract")
    if path_command:
        return Path(path_command)

    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        program_files = os.getenv(variable)
        if not program_files:
            continue
        candidate = Path(program_files) / "Tesseract-OCR" / "tesseract.exe"
        if candidate.is_file():
            return candidate
    return None


class TesseractService:
    """Recognize regional PNG images with a locally installed Tesseract."""

    _process_lock = Lock()

    def __init__(
        self,
        executable: Path | None = None,
        language: str | None = None,
        timeout: int = DEFAULT_TESSERACT_TIMEOUT,
    ) -> None:
        self._executable = executable or find_tesseract_executable()
        self._requested_language = (
            language or os.getenv("PDF_EXTRACTOR_OCR_LANG") or DEFAULT_OCR_LANGUAGE
        )
        self._timeout = timeout
        self._resolved_language: str | None = None

    @property
    def executable(self) -> Path | None:
        """Return the discovered engine path without persisting it anywhere."""
        return self._executable

    @property
    def requested_language(self) -> str:
        """Return the language configuration requested by the application."""
        return self._requested_language

    def recognize(self, image_bytes: bytes) -> str:
        """Return raw OCR text or raise a friendly expected error."""
        executable = self._executable
        if executable is None or not executable.is_file():
            raise OcrUnavailableError(
                "O Tesseract OCR não foi encontrado. Instale-o ou configure "
                "a variável TESSERACT_CMD."
            )
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                with self._process_lock:
                    pytesseract.pytesseract.tesseract_cmd = str(executable)
                    language = self._resolve_language()
                    return pytesseract.image_to_string(
                        image.convert("RGB"),
                        lang=language,
                        config="--oem 3 --psm 6",
                        timeout=self._timeout,
                    )
        except OcrError:
            raise
        except (UnidentifiedImageError, OSError) as error:
            raise OcrError("A imagem da região não pôde ser lida pelo OCR.") from error
        except pytesseract.TesseractNotFoundError as error:
            raise OcrUnavailableError(
                "O executável do Tesseract OCR não está disponível."
            ) from error
        except pytesseract.TesseractError as error:
            raise OcrError(
                f"O Tesseract não conseguiu reconhecer a região: {error}"
            ) from error
        except RuntimeError as error:
            raise OcrError("O Tesseract excedeu o tempo limite da região.") from error

    def _resolve_language(self) -> str:
        if self._resolved_language is not None:
            return self._resolved_language
        try:
            available = set(pytesseract.get_languages(config=""))
        except pytesseract.TesseractError as error:
            raise OcrError(
                "Não foi possível consultar os idiomas do Tesseract."
            ) from error
        requested = self._requested_language.split("+")
        supported = [language for language in requested if language in available]
        if not supported:
            raise OcrError(
                "Nenhum dos idiomas de OCR configurados está instalado: "
                f"{self._requested_language}."
            )
        self._resolved_language = "+".join(supported)
        return self._resolved_language
