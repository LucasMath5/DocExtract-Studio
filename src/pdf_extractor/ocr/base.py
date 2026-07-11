"""Contracts and expected errors shared by OCR engines."""

from __future__ import annotations

from typing import Protocol


class OcrError(RuntimeError):
    """Represent an expected OCR configuration or recognition failure."""


class OcrUnavailableError(OcrError):
    """Report that no usable OCR engine is installed."""


class OcrEngine(Protocol):
    """Define the minimal interface required by the extraction service."""

    def recognize(self, image_bytes: bytes) -> str:
        """Return text recognized from an encoded image."""
