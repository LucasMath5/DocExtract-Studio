"""Tests for the selected PDF region domain model."""

from __future__ import annotations

import pytest

from pdf_extractor.models.field_region import FieldRegion


def test_field_region_exposes_edges() -> None:
    """A valid region should expose calculated right and bottom edges."""
    region = FieldRegion(page_index=2, x=10.5, y=20.5, width=30, height=40)

    assert region.right == pytest.approx(40.5)
    assert region.bottom == pytest.approx(60.5)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ((-1, 0, 0, 10, 10), "índice da página"),
        ((0, -1, 0, 10, 10), "X e Y"),
        ((0, 0, -1, 10, 10), "X e Y"),
        ((0, 0, 0, 0, 10), "largura e a altura"),
        ((0, 0, 0, 10, -1), "largura e a altura"),
        ((0, float("nan"), 0, 10, 10), "números finitos"),
    ],
)
def test_field_region_rejects_invalid_values(
    values: tuple[int, float, float, float, float],
    message: str,
) -> None:
    """Invalid pages, coordinates, and dimensions should be rejected."""
    with pytest.raises(ValueError, match=message):
        FieldRegion(*values)
