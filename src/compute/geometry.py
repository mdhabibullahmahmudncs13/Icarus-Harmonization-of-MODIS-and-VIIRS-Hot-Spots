"""Custom areas of interest: a polygon, not a rectangle.

A preset region is a bounding box, and the whole pipeline is built on boxes —
the grid, the density divisor, the map extent. A user who draws an area wants
the shape they drew, so the polygon has to be honoured where it matters: the
detections that count, and the number of cells the counts are divided by.

The polygon is a single ring of ``(lon, lat)`` positions. No dependency: the
point-in-polygon test is a ray cast, and the cell count is the cells whose
centre falls inside the ring.
"""

from __future__ import annotations

import math

import pandas as pd

from src.compute import harmonize

#: A ring of ``(longitude, latitude)`` positions.
Ring = list[tuple[float, float]]


def close_ring(positions: list[tuple[float, float]]) -> Ring:
    """The ring with its last position repeated first, if it was not already.

    A GeoJSON ring is closed; a ring drawn by clicking points is not. Closing
    it here means the rest of the code never has to think about the difference.
    """
    if not positions:
        return []
    first, last = positions[0], positions[-1]
    if abs(first[0] - last[0]) < 1e-12 and abs(first[1] - last[1]) < 1e-12:
        return list(positions)
    return [*positions, positions[0]]


def point_in_ring(lon: float, lat: float, ring: Ring) -> bool:
    """Is the point inside the ring? Ray casting, on the horizontal axis.

    A ray is cast east from the point and the ring is crossed an odd number of
    times exactly when the point is inside. A point exactly on a horizontal
    edge is counted as inside, because the edge belongs to the area the user
    drew.
    """
    if len(ring) < 4:
        return False
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            # The edge crosses the ray's latitude. Where it crosses decides
            # which side of the ray the point is on.
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon <= x_cross:
                inside = not inside
        j = i
    return inside


def within_ring(frame: pd.DataFrame, ring: Ring) -> pd.DataFrame:
    """The detections inside the ring.

    A point on the boundary is kept, so a detection exactly on a drawn edge
    is not silently dropped.
    """
    if frame.empty or len(ring) < 4:
        return frame.iloc[0:0]
    ring = close_ring(list(ring))
    lons = frame["longitude"].to_numpy(dtype=float)
    lats = frame["latitude"].to_numpy(dtype=float)
    keep = [point_in_ring(lon, lat, ring) for lon, lat in zip(lons, lats, strict=True)]
    return frame[pd.Series(keep, index=frame.index)]


def ring_cell_count(
    ring: Ring,
    cell_km: float = harmonize.DEFAULT_CELL_KM,
    reference_latitude_deg: float = harmonize.REFERENCE_LATITUDE_DEG,
) -> int:
    """How many grid cells the ring covers.

    The density metric divides a count by this figure, so it has to count the
    cells the area actually holds, not the cells its bounding box touches: a
    thin diagonal shape covers far fewer cells than its box, and dividing by
    the box would report a density far too low.

    A cell counts when its centre is inside the ring. The cell edges are not
    clipped to the ring, which is an approximation, but it is the same
    approximation the grid itself makes everywhere else: a detection and the
    cell it belongs to are not split by the polygon either.
    """
    ring = close_ring(list(ring))
    if len(ring) < 4:
        return 0
    dlat = harmonize.degrees_per_lat(cell_km)
    dlon = harmonize.degrees_per_lon(cell_km, reference_latitude_deg)
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)

    first_row = math.floor(south / dlat)
    last_row = math.floor(north / dlat)
    first_col = math.floor(west / dlon)
    last_col = math.floor(east / dlon)

    count = 0
    for row in range(first_row, last_row + 1):
        centre_lat = (row + 0.5) * dlat
        if centre_lat < south or centre_lat > north:
            continue
        for col in range(first_col, last_col + 1):
            centre_lon = (col + 0.5) * dlon
            if centre_lon < west or centre_lon > east:
                continue
            if point_in_ring(centre_lon, centre_lat, ring):
                count += 1
    return count


def ring_bbox(ring: Ring) -> tuple[float, float, float, float]:
    """The bounding box of the ring, as ``(west, south, east, north)``."""
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (min(lons), min(lats), max(lons), max(lats))


def validate_ring(
    positions: list[tuple[float, float]],
    *,
    extent: tuple[float, float, float, float] | None = None,
) -> Ring:
    """The ring, or a reason it cannot be used.

    The checks are the ones ``docs/TRD.md`` §6.1 promises: the ring is closed,
    it has at least four positions, and it lies within the processing extent.
    A self-intersecting ring is refused too — the ray cast gives a nonsense
    answer for one, and a nonsense area is worse than no area.
    """
    if len(positions) < 3:
        raise ValueError("a polygon needs at least three points")
    ring = close_ring(positions)
    if len(ring) < 4:
        raise ValueError("a polygon needs at least four positions")
    if self_intersects(ring):
        raise ValueError("the polygon crosses itself")
    if extent is not None:
        west, south, east, north = extent
        for lon, lat in ring:
            if not (west <= lon <= east and south <= lat <= north):
                raise ValueError(
                    f"the polygon leaves the processing extent; "
                    f"{lon},{lat} is outside {west},{south},{east},{north}"
                )
    return ring


def self_intersects(ring: Ring) -> bool:
    """Do two edges of the ring cross?

    Edges that share a vertex do not count: a ring touches itself at every
    vertex by definition. The ring is closed, so edge ``n - 1`` runs from the
    last vertex back to the first, and it is a neighbour of edge 0.
    """
    n = len(ring) - 1  # the last position repeats the first
    for i in range(n):
        for j in range(i + 1, n):
            if _share_vertex(i, j, n):
                continue
            if _segments_cross(ring[i], ring[i + 1], ring[j], ring[j + 1]):
                return True
    return False


def _share_vertex(i: int, j: int, n: int) -> bool:
    """Do edges ``i`` and ``j`` of a closed ring meet at a vertex?"""
    if j == i + 1 or i == j + 1:
        return True
    # The last edge closes back onto the first.
    return (i == 0 and j == n - 1) or (j == 0 and i == n - 1)


def _segments_cross(
    a: tuple[float, float], b: tuple[float, float],
    c: tuple[float, float], d: tuple[float, float],
) -> bool:
    """Do the segments ``a-b`` and ``c-d`` cross?"""
    d1 = _cross(a, b, c)
    d2 = _cross(a, b, d)
    d3 = _cross(c, d, a)
    d4 = _cross(c, d, b)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    # A touch counts as a crossing too: a figure-eight is not a valid area.
    return (
        (d1 == 0 and _on_segment(a, b, c))
        or (d2 == 0 and _on_segment(a, b, d))
        or (d3 == 0 and _on_segment(c, d, a))
        or (d4 == 0 and _on_segment(c, d, b))
    )


def _cross(
    o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    """The z component of the cross product of ``oa`` and ``ob``."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _on_segment(
    a: tuple[float, float], b: tuple[float, float], p: tuple[float, float]
) -> bool:
    """Is ``p`` on the segment ``a-b``?"""
    return (
        min(a[0], b[0]) - 1e-12 <= p[0] <= max(a[0], b[0]) + 1e-12
        and min(a[1], b[1]) - 1e-12 <= p[1] <= max(a[1], b[1]) + 1e-12
    )
