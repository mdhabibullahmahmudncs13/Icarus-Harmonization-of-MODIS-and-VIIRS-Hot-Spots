"""Custom areas of interest: the polygon geometry.

The polygon has to do two honest jobs: decide which detections count, and say
how many grid cells the area holds, so a density means what it says.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.compute import geometry, harmonize

#: A square around Dhaka, in order.
SQUARE = [(88.0, 23.0), (89.0, 23.0), (89.0, 24.0), (88.0, 24.0)]


def _frame(points: list[tuple[float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "latitude": [p[1] for p in points],
            "longitude": [p[0] for p in points],
        }
    )


def test_a_point_inside_the_ring_is_inside():
    assert geometry.point_in_ring(88.5, 23.5, geometry.close_ring(SQUARE))


def test_a_point_outside_the_ring_is_outside():
    assert not geometry.point_in_ring(87.0, 23.5, geometry.close_ring(SQUARE))
    assert not geometry.point_in_ring(88.5, 25.0, geometry.close_ring(SQUARE))


def test_the_ring_is_closed_so_a_drawn_shape_needs_no_closing_click():
    assert geometry.close_ring(SQUARE)[0] == geometry.close_ring(SQUARE)[-1]
    assert len(geometry.close_ring(SQUARE)) == 5


def test_a_ring_that_is_already_closed_is_not_closed_twice():
    closed = geometry.close_ring(SQUARE)
    assert geometry.close_ring(closed) == closed


def test_the_filter_keeps_the_points_inside_and_drops_the_rest():
    frame = _frame([(88.5, 23.5), (87.0, 23.5), (88.6, 23.7), (95.0, 23.5)])
    inside = geometry.within_ring(frame, geometry.close_ring(SQUARE))
    assert len(inside) == 2
    assert sorted(inside["longitude"].tolist()) == [88.5, 88.6]


def test_the_filter_of_an_empty_frame_is_empty():
    empty = _frame([])
    assert geometry.within_ring(empty, geometry.close_ring(SQUARE)).empty


def test_a_degenerate_ring_keeps_nothing():
    """Two points are not an area; nothing can be inside one."""
    frame = _frame([(88.5, 23.5)])
    assert geometry.within_ring(frame, [(88.0, 23.0), (89.0, 23.0)]).empty


def test_the_cell_count_is_the_number_of_cells_the_area_holds():
    """The square is about 1° across, so it holds far fewer cells than its box.

    The box would give 46×43 cells; the square holds a fraction of that. If the
    count were the box's, the density would be far too low.
    """
    ring = geometry.close_ring(SQUARE)
    box = geometry.ring_bbox(ring)
    inside = geometry.ring_cell_count(ring)
    box_cells = harmonize.grid_cell_count(box)
    assert 0 < inside < box_cells


def test_the_cell_count_of_an_empty_ring_is_zero():
    assert geometry.ring_cell_count([]) == 0


def test_a_larger_ring_covers_more_cells():
    small = geometry.close_ring([(88.0, 23.0), (88.5, 23.0), (88.5, 23.5), (88.0, 23.5)])
    large = geometry.close_ring([(88.0, 23.0), (89.0, 23.0), (89.0, 24.0), (88.0, 24.0)])
    assert geometry.ring_cell_count(large) > geometry.ring_cell_count(small)


def test_a_ring_that_crosses_itself_is_refused():
    bowtie = [(88.0, 23.0), (89.0, 24.0), (89.0, 23.0), (88.0, 24.0)]
    with pytest.raises(ValueError, match="crosses itself"):
        geometry.validate_ring(bowtie)


def test_a_ring_with_too_few_points_is_refused():
    with pytest.raises(ValueError, match="at least three points"):
        geometry.validate_ring([(88.0, 23.0), (89.0, 24.0)])


def test_a_ring_outside_the_extent_is_refused():
    with pytest.raises(ValueError, match="leaves the processing extent"):
        geometry.validate_ring(
            [(88.0, 23.0), (89.0, 23.0), (89.0, 24.0), (88.0, 24.0)],
            extent=(88.0, 20.0, 93.0, 22.0),
        )


def test_a_good_ring_passes_validation():
    ring = geometry.validate_ring(SQUARE, extent=(88.0, 20.0, 93.0, 27.0))
    assert len(ring) == 5
