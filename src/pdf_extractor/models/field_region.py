"""Domain model for a rectangular region on a PDF page."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class FieldRegion:
    """Represent one rectangular selection in native PDF coordinates."""

    page_index: int
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.page_index < 0:
            raise ValueError("O índice da página não pode ser negativo.")

        coordinates = (self.x, self.y, self.width, self.height)
        if not all(isfinite(value) for value in coordinates):
            raise ValueError("As coordenadas da região devem ser números finitos.")
        if self.x < 0 or self.y < 0:
            raise ValueError("As coordenadas X e Y não podem ser negativas.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("A largura e a altura da região devem ser positivas.")

    @property
    def right(self) -> float:
        """Return the right edge in PDF coordinates."""
        return self.x + self.width

    @property
    def bottom(self) -> float:
        """Return the bottom edge in PDF coordinates."""
        return self.y + self.height
