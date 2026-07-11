"""Tests for portable Tesseract discovery and OCR error handling."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from pdf_extractor.ocr import tesseract_service as tesseract_module
from pdf_extractor.ocr.base import OcrError, OcrUnavailableError
from pdf_extractor.ocr.tesseract_service import (
    TesseractService,
    find_tesseract_executable,
)


def png_image() -> bytes:
    """Return a small valid PNG for OCR adapter tests."""
    stream = BytesIO()
    Image.new("RGB", (80, 30), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_discovers_tesseract_in_windows_program_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows discovery should avoid a machine-specific hardcoded path."""
    executable = tmp_path / "Tesseract-OCR" / "tesseract.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"executable")
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr(tesseract_module.shutil, "which", lambda command: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)

    assert find_tesseract_executable() == executable


def test_recognize_uses_available_requested_languages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The adapter should pass language, page mode, and timeout to pytesseract."""
    executable = tmp_path / "tesseract.exe"
    executable.write_bytes(b"executable")
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        tesseract_module.pytesseract,
        "get_languages",
        lambda config="": ["eng", "por"],
    )

    def fake_image_to_string(image: Image.Image, **kwargs: object) -> str:
        captured.update(kwargs)
        captured["mode"] = image.mode
        return "Texto OCR"

    monkeypatch.setattr(
        tesseract_module.pytesseract,
        "image_to_string",
        fake_image_to_string,
    )
    service = TesseractService(
        executable=executable,
        language="por+fra+eng",
        timeout=7,
    )

    value = service.recognize(png_image())

    assert value == "Texto OCR"
    assert captured == {
        "lang": "por+eng",
        "config": "--oem 3 --psm 6",
        "timeout": 7,
        "mode": "RGB",
    }


def test_missing_executable_has_friendly_error(tmp_path: Path) -> None:
    """A missing local engine should be an expected, actionable error."""
    service = TesseractService(executable=tmp_path / "ausente.exe")

    with pytest.raises(OcrUnavailableError, match="não foi encontrado"):
        service.recognize(png_image())


def test_missing_configured_language_has_friendly_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An unavailable language should not invoke OCR with a bad configuration."""
    executable = tmp_path / "tesseract.exe"
    executable.write_bytes(b"executable")
    monkeypatch.setattr(
        tesseract_module.pytesseract,
        "get_languages",
        lambda config="": ["eng"],
    )
    service = TesseractService(executable=executable, language="por")

    with pytest.raises(OcrError, match="Nenhum dos idiomas"):
        service.recognize(png_image())
