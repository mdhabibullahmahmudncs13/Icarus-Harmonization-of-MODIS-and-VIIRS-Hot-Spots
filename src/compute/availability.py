"""S7 stream availability (docs/TRD.md §5.5, docs/DATA_DICTIONARY.md §4–5).

Availability answers "was this stream expected to observe that day?", which is
an acquisition fact independent of whether a fire happened. It is built from two
inputs:

* **Epochs** — a stream can only report inside its FIRMS product window
  (``src/acquire/firms.py``, the one product table).
* **Outages** — the explicit downlink gaps in ``src/outages.json``.

``a(s, d) = 1`` when the epoch covers ``d`` and ``d`` is not in one of stream
``s``'s outages. Days the epoch does not cover are *outside the record*, not
unavailable, so they are excluded from a bin's denominator rather than counted
as zero — otherwise every pre-2012 bin would be hatched for the absence of
VIIRS. This is the spec's "outside active period" clause made concrete.

Deterministic, network-free, no LLM.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The outage table: per-stream windows treated as unavailable.
OUTAGES_PATH = REPO_ROOT / "src" / "outages.json"

#: Stream -> FIRMS product. Kept in step with ``src.compute.export.PRODUCT_STREAMS``
#: by ``tests/test_availability.py``; it lives here so this module does not
#: import the payload builders (which import coverage, which imports this).
STREAM_PRODUCT: dict[str, str] = {
    "MOD_T": "MODIS_SP",
    "MOD_A": "MODIS_SP",
    "VIIRS_SNPP": "VIIRS_SNPP_SP",
    "VIIRS_N20": "VIIRS_NOAA20_SP",
    "VIIRS_N21": "VIIRS_NOAA21_NRT",
}

#: Stream -> family, for rolling streams up to the coverage the contract reports.
STREAM_FAMILY: dict[str, str] = {
    "MOD_T": "MODIS",
    "MOD_A": "MODIS",
    "VIIRS_SNPP": "VIIRS",
    "VIIRS_N20": "VIIRS",
    "VIIRS_N21": "VIIRS",
}

#: The outage-table keyword that silences every stream.
ALL_STREAMS = "ALL"


@dataclass(frozen=True)
class Outage:
    """One stream's downlink gap, inclusive of both ends."""

    stream: str
    start: date
    end: date
    reason: str

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


def load_outages(path: Path = OUTAGES_PATH) -> list[Outage]:
    """Read the outage table. Returns an empty list when the file is absent."""
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [
        Outage(
            stream=str(entry["stream"]),
            start=_parse_day(str(entry["start"])),
            end=_parse_day(str(entry["end"])),
            reason=str(entry.get("reason", "")),
        )
        for entry in data.get("outages", [])
    ]


def stream_epochs() -> dict[str, tuple[date, date | None]]:
    """Each stream's expected-observation window, from the FIRMS product table."""
    from src.acquire import firms

    epochs: dict[str, tuple[date, date | None]] = {}
    for stream, product in STREAM_PRODUCT.items():
        entry = firms.PRODUCTS[product]
        epochs[stream] = (entry.start, entry.end)
    return epochs


def expected_days(
    stream: str,
    start: date,
    end: date,
    *,
    epochs: Mapping[str, tuple[date, date | None]] | None = None,
    outages: Iterable[Outage] | None = None,
) -> set[date]:
    """Days ``stream`` was expected to observe inside ``start..end`` inclusive.

    Empty when the window falls outside the stream's epoch entirely.
    """
    epochs = stream_epochs() if epochs is None else epochs
    outages = load_outages() if outages is None else outages
    if stream not in epochs:
        raise ValueError(f"unknown stream {stream!r}; known: {sorted(epochs)}")
    epoch_start, epoch_end = epochs[stream]
    lo = max(start, epoch_start)
    hi = min(end, epoch_end) if epoch_end is not None else end
    if hi < lo:
        return set()
    gaps = [o for o in outages if o.stream in (stream, ALL_STREAMS)]
    days: set[date] = set()
    cursor = lo
    while cursor <= hi:
        if not any(gap.covers(cursor) for gap in gaps):
            days.add(cursor)
        cursor += timedelta(days=1)
    return days


def availability_table(
    start: date,
    end: date,
    *,
    epochs: Mapping[str, tuple[date, date | None]] | None = None,
    outages: Iterable[Outage] | None = None,
) -> dict[str, set[date]]:
    """Every stream's expected-observation calendar over ``start..end``."""
    epochs = stream_epochs() if epochs is None else epochs
    outages = load_outages() if outages is None else outages
    return {
        stream: expected_days(stream, start, end, epochs=epochs, outages=outages)
        for stream in epochs
    }


def families_available(availability: Mapping[str, set[date]]) -> dict[date, set[str]]:
    """Roll the stream calendar up to per-day available families."""
    families: dict[date, set[str]] = {}
    for stream, days in availability.items():
        family = STREAM_FAMILY.get(stream, stream)
        for day in days:
            families.setdefault(day, set()).add(family)
    return families


__all__: Iterable[str] = (
    "ALL_STREAMS",
    "OUTAGES_PATH",
    "STREAM_FAMILY",
    "STREAM_PRODUCT",
    "Outage",
    "availability_table",
    "expected_days",
    "families_available",
    "load_outages",
    "stream_epochs",
)
