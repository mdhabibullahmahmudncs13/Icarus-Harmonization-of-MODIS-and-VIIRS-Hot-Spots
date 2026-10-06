"""Download NASA FIRMS active-fire detections for a bounding box.

Phase 0 (data safety). This is the acquisition layer: it pulls the FIRMS
Area API CSV for each source product, in day-range chunks, and writes one
parquet per chunk plus a merged parquet per product under ``cache/raw/``.

**Suomi-NPP is downloaded first.** NASA stops serving it on 2026-11-01 and
without its archive the 2012 to 2018 stretch of the record is missing.
The standard-processing (``_SP``) products are used for the historical
record; the near-real-time (``_NRT``) products only cover recent days.

Endpoint (documented at https://firms.modaps.eosdis.nasa.gov/api/area/)::

    /api/area/csv/[MAP_KEY]/[SOURCE]/[AREA_COORDINATES]/[DAY_RANGE]/[DATE]

``DAY_RANGE`` is 1..5 and ``AREA_COORDINATES`` is ``west,south,east,north``.
Larger day ranges count as multiple transactions, and the MAP_KEY limit is
5,000 transactions per 10-minute interval.

Every request goes through :mod:`src.acquire.safe`, so a run never has to
depend on the network: live first, then ``cache/``, then
``demo_fixtures/``. ``OFFLINE=1`` forces the non-live paths.

This is deterministic, network-free logic except for the fetch itself. No
LLM is involved, and the frontend never calls this module.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from src.acquire import safe

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "cache"

# Bangladesh bounding box, west/south/east/north. Matches the doc's
# acquisition snippet and the frontend contract.
BANGLADESH_BBOX: tuple[float, float, float, float] = (88.0, 20.0, 93.0, 27.0)

# Documented Area API ceiling. Larger ranges are chunked into separate calls.
MAX_DAY_RANGE = 5

AREA_API_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
DATA_AVAILABILITY_URL = "https://firms.modaps.eosdis.nasa.gov/api/data_availability/"

MAP_KEY_ENV = "FIRMS_MAP_KEY"

# Documented rate limit: 5,000 transactions per 10 minutes.
MAX_TRANSACTIONS = 5000
RATE_WINDOW_SECONDS = 600.0

# The series window the frontend contract already uses. Product windows are
# intersected with this before any request is made.
DEFAULT_START = date(2003, 1, 1)
DEFAULT_END = date(2026, 9, 30)

# Columns a FIRMS active-fire CSV is expected to carry. Used to reject an
# error page or an empty payload before it reaches the parquet writer.
REQUIRED_COLUMNS = ("latitude", "longitude", "acq_date", "confidence")


@dataclass(frozen=True)
class FirmsProduct:
    """One FIRMS source product (one sensor / processing level)."""

    source: str
    family: str
    satellite: str
    processing: str
    start: date
    end: date


def _d(value: str) -> date:
    return date.fromisoformat(value)


# Product table. Dates are the project's own contract values; confirm each
# against https://firms.modaps.eosdis.nasa.gov/api/data_availability/ before
# the demo rather than trusting this table (see docs/DATA.md).
PRODUCTS: dict[str, FirmsProduct] = {
    p.source: p
    for p in (
        FirmsProduct("VIIRS_SNPP_SP", "VIIRS", "Suomi-NPP", "SP", _d("2012-01-01"), _d("2026-11-01")),
        FirmsProduct("MODIS_SP", "MODIS", "Terra+Aqua", "SP", _d("2003-01-01"), _d("2026-09-30")),
        FirmsProduct("VIIRS_NOAA20_SP", "VIIRS", "NOAA-20", "SP", _d("2018-01-01"), _d("2026-09-30")),
        FirmsProduct("VIIRS_NOAA21_SP", "VIIRS", "NOAA-21", "SP", _d("2023-01-01"), _d("2026-09-30")),
    )
}

# Suomi-NPP first: it has the only hard external deadline.
DOWNLOAD_ORDER: tuple[str, ...] = (
    "VIIRS_SNPP_SP",
    "MODIS_SP",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA21_SP",
)


# --------------------------------------------------------------------------
# Pure helpers (no network, no disk) — these carry the testable logic.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Chunk:
    """One Area API request window: ``days`` days starting at ``start``."""

    start: date
    days: int

    @property
    def end(self) -> date:
        """Inclusive last day of the window."""
        return self.start + timedelta(days=self.days - 1)

    @property
    def key(self) -> str:
        """Stable filename stem for this window."""
        return self.start.strftime("%Y%m%d")


def chunk_windows(
    start: date, end: date, day_range: int = MAX_DAY_RANGE
) -> list[Chunk]:
    """Split ``start..end`` (inclusive) into windows of at most ``day_range`` days.

    Contiguous and gap-free by construction, so no day is requested twice
    and none is skipped. The final window is short when the range does not
    divide evenly.
    """
    if day_range < 1:
        raise ValueError(f"day_range must be >= 1, got {day_range}")
    if end < start:
        return []
    chunks: list[Chunk] = []
    cursor = start
    while cursor <= end:
        remaining = (end - cursor).days + 1
        days = min(day_range, remaining)
        chunks.append(Chunk(cursor, days))
        cursor += timedelta(days=days)
    return chunks


def _fmt_coord(value: float) -> str:
    """Format a coordinate without a redundant trailing ``.0``."""
    if float(value).is_integer():
        return str(int(value))
    return repr(float(value))


def bbox_param(bbox: tuple[float, float, float, float]) -> str:
    """Return the Area API's ``west,south,east,north`` coordinate string."""
    if len(bbox) != 4:
        raise ValueError(f"bbox must have four values, got {bbox!r}")
    west, south, east, north = (float(v) for v in bbox)
    if not (west < east and south < north):
        raise ValueError(f"bbox needs west<east and south<north, got {bbox!r}")
    return ",".join(_fmt_coord(v) for v in (west, south, east, north))


def area_url(
    map_key: str,
    source: str,
    bbox: tuple[float, float, float, float],
    days: int,
    start: date | None = None,
) -> str:
    """Build the documented Area API CSV URL for one chunk."""
    if not map_key:
        raise ValueError("a FIRMS MAP_KEY is required to build a live URL")
    if not 1 <= days <= MAX_DAY_RANGE:
        raise ValueError(f"days must be 1..{MAX_DAY_RANGE}, got {days}")
    if source not in PRODUCTS:
        raise ValueError(f"unknown FIRMS source {source!r}; known: {sorted(PRODUCTS)}")
    url = f"{AREA_API_BASE}/{map_key}/{source}/{bbox_param(bbox)}/{days}"
    if start is not None:
        url = f"{url}/{start.isoformat()}"
    return url


def product_window(
    product: FirmsProduct,
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
) -> tuple[date, date] | None:
    """Intersect the requested window with the product's availability.

    Returns ``None`` when the two do not overlap, so the caller can skip the
    product entirely instead of issuing requests that return nothing.
    """
    lo = max(start, product.start)
    hi = min(end, product.end)
    if hi < lo:
        return None
    return lo, hi


# --------------------------------------------------------------------------
# Key handling and rate limiting
# --------------------------------------------------------------------------


def is_offline() -> bool:
    """:mod:`src.acquire.safe`'s rule for the ``OFFLINE`` flag."""
    return safe._is_offline()


def read_dotenv(path: Path | None = None) -> dict[str, str]:
    """Read ``KEY=VALUE`` pairs from ``.env`` without adding a dependency."""
    env_path = path or (REPO_ROOT / ".env")
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_map_key(environ: Mapping[str, str] | None = None) -> str:
    """Return the FIRMS MAP_KEY from the environment, then from ``.env``."""
    environ = os.environ if environ is None else environ
    key = environ.get(MAP_KEY_ENV) or read_dotenv().get(MAP_KEY_ENV, "")
    return key.strip()


def require_map_key(environ: Mapping[str, str] | None = None) -> str:
    """Return the MAP_KEY or raise with the exact place to get one."""
    key = load_map_key(environ)
    if not key:
        raise RuntimeError(
            "FIRMS_MAP_KEY is not set. Request a free key at "
            "https://firms.modaps.eosdis.nasa.gov/api/map_key/ and put it in .env "
            "(see .env.example). Set OFFLINE=1 to read only from cache/ and "
            "demo_fixtures/ without a key."
        )
    return key


class TransactionLimiter:
    """Throttle requests to FIRMS' documented transactions-per-window limit.

    The clock and sleep functions are injectable so tests never actually
    sleep.
    """

    def __init__(
        self,
        max_transactions: int = MAX_TRANSACTIONS,
        window_seconds: float = RATE_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_transactions = max_transactions
        self.window_seconds = window_seconds
        self._clock = clock
        self._sleep = sleep
        self._stamps: list[float] = []

    def acquire(self) -> None:
        """Record one transaction, sleeping only when the window is full."""
        now = self._clock()
        cutoff = now - self.window_seconds
        self._stamps = [t for t in self._stamps if t > cutoff]
        if len(self._stamps) >= self.max_transactions:
            wait = self._stamps[0] + self.window_seconds - now
            if wait > 0:
                self._sleep(wait)
            now = self._clock()
            cutoff = now - self.window_seconds
            self._stamps = [t for t in self._stamps if t > cutoff]
        self._stamps.append(now)


# --------------------------------------------------------------------------
# Parsing and paths
# --------------------------------------------------------------------------


def _response_text(payload: Any) -> str:
    """safe_fetch returns a Response live and a str from cache/fixture."""
    text = getattr(payload, "text", payload)
    return text if isinstance(text, str) else str(text)


def parse_firms_csv(text: Any, product: FirmsProduct) -> pd.DataFrame:
    """Parse one FIRMS CSV payload into a frame tagged with provenance.

    Returns an empty frame (with the provenance columns) when the payload
    has no detections, so a chunk that legitimately contains no fire is not
    an error.
    """
    raw = _response_text(text)
    if not raw or not raw.strip():
        return _empty_frame(product)
    try:
        frame = pd.read_csv(io.StringIO(raw))
    except pd.errors.EmptyDataError:
        return _empty_frame(product)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(
            f"FIRMS payload for {product.source} is missing columns {missing}; "
            f"got {list(frame.columns)} (a MAP_KEY error page reaches here as CSV)"
        )
    frame = frame.copy()
    frame["source_product"] = product.source
    frame["sensor_family"] = product.family
    frame["satellite_product"] = product.satellite
    return frame


def _empty_frame(product: FirmsProduct) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            *REQUIRED_COLUMNS,
            "source_product",
            "sensor_family",
            "satellite_product",
        ]
    )


def raw_dir(cache_dir: Path | None = None) -> Path:
    """Root of the raw cache: ``cache/raw``."""
    return (cache_dir or CACHE_DIR) / "raw"


def chunk_paths(source: str, chunk: Chunk, cache_dir: Path | None = None) -> tuple[Path, Path]:
    """Return ``(csv_path, parquet_path)`` for one chunk."""
    base = raw_dir(cache_dir)
    return (
        base / "csv" / source / f"{chunk.key}.csv",
        base / source / f"{chunk.key}.parquet",
    )


def merged_path(source: str, cache_dir: Path | None = None) -> Path:
    """Path of the merged per-product parquet."""
    return raw_dir(cache_dir) / f"{source}.parquet"


def _dedupe_key(frame: pd.DataFrame) -> list[str]:
    return [c for c in ("latitude", "longitude", "acq_date", "acq_time") if c in frame.columns]


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------


@dataclass
class ChunkResult:
    """Outcome of one chunk request."""

    chunk: Chunk
    status: str  # "fetched" | "cached" | "skipped" | "empty" | "missing"
    source_of_data: str | None = None  # "live" | "cache" | "fixture"
    rows: int = 0
    parquet: Path | None = None


@dataclass
class ProductReport:
    """Outcome of one product download."""

    product: FirmsProduct
    window: tuple[date, date] | None
    results: list[ChunkResult] = field(default_factory=list)
    merged: Path | None = None

    @property
    def rows(self) -> int:
        return sum(r.rows for r in self.results)

    @property
    def fetched(self) -> int:
        return sum(1 for r in self.results if r.status == "fetched")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")

    @property
    def missing(self) -> int:
        return sum(1 for r in self.results if r.status == "missing")

    def summary(self) -> str:
        if self.window is None:
            return f"{self.product.source}: no overlap with the requested window"
        lo, hi = self.window
        return (
            f"{self.product.source}: {lo}..{hi}  chunks={len(self.results)} "
            f"fetched={self.fetched} skipped={self.skipped} "
            f"missing={self.missing} rows={self.rows}"
        )


def download_chunk(
    product: FirmsProduct,
    chunk: Chunk,
    bbox: tuple[float, float, float, float],
    map_key: str = "",
    *,
    cache_dir: Path | None = None,
    fetcher: Callable[[str], Any] | None = None,
    limiter: TransactionLimiter | None = None,
    offline: bool | None = None,
) -> ChunkResult:
    """Fetch one chunk and write its parquet, reusing anything already on disk.

    Resolution order, which is what makes the download resumable:

    1. parquet already exists -> ``skipped``
    2. raw CSV already cached -> parse it, write parquet -> ``cached``
    3. live fetch via :func:`src.acquire.safe.safe_fetch` -> ``fetched``
    4. nothing available (typically ``OFFLINE=1``) -> ``missing``
    """
    csv_path, parquet_path = chunk_paths(product.source, chunk, cache_dir)
    if parquet_path.exists():
        return ChunkResult(chunk, "skipped", parquet=parquet_path)

    if csv_path.exists():
        try:
            frame = parse_firms_csv(csv_path.read_text(), product)
        except ValueError:
            # A poisoned cache — an error page saved by an earlier run, or a
            # truncated write — is not data. Fall through to the live fetch
            # instead of raising on every run; a successful fetch overwrites
            # it, and an offline run just reports the chunk missing.
            pass
        else:
            return _write_chunk(frame, chunk, csv_path, parquet_path, "cached", "cache")

    if offline is None:
        offline = is_offline()
    if offline:
        return ChunkResult(chunk, "missing")

    if not map_key:
        map_key = require_map_key()
    if limiter is not None:
        limiter.acquire()
    url = area_url(map_key, product.source, bbox, chunk.days, chunk.start)
    try:
        # safe_fetch is used for the live attempt only (the CSV cache above is
        # checked first). Absolute paths are passed because ``Path / absolute``
        # yields the absolute path, so no CACHE_DIR-relative juggling is needed.
        payload, source_of_data = safe.safe_fetch(
            url=url,
            cache_name=str(csv_path),
            fixture_name=str(csv_path),
            fetcher=fetcher,
            parser=_response_text,
        )
    except FileNotFoundError:
        return ChunkResult(chunk, "missing")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    # Parse first: a throttle page ("invalid map_key.") reaches here as CSV,
    # and caching it would poison the chunk — every later run would take the
    # "cached CSV" path above and raise instead of re-fetching.
    frame = parse_firms_csv(payload, product)
    csv_path.write_text(_response_text(payload))
    return _write_chunk(frame, chunk, csv_path, parquet_path, "fetched", source_of_data)


def _write_chunk(
    frame: pd.DataFrame,
    chunk: Chunk,
    csv_path: Path,
    parquet_path: Path,
    status: str,
    source_of_data: str,
) -> ChunkResult:
    if frame.empty:
        return ChunkResult(chunk, "empty", source_of_data, rows=0)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    _sort_frame(frame).to_parquet(parquet_path, index=False)
    return ChunkResult(
        chunk,
        status,
        source_of_data,
        rows=len(frame),
        parquet=parquet_path,
    )


def _sort_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Deterministic ordering, so a rerun produces byte-comparable output."""
    keys = [c for c in ("acq_date", "acq_time", "latitude", "longitude") if c in frame.columns]
    out = frame.sort_values(keys, kind="stable") if keys else frame
    dedupe = _dedupe_key(out)
    return out.drop_duplicates(subset=dedupe) if dedupe else out


def merge_product(source: str, cache_dir: Path | None = None) -> Path | None:
    """Concatenate a product's chunk parquets into ``cache/raw/<source>.parquet``."""
    base = (cache_dir or CACHE_DIR) / "raw" / source
    files = sorted(base.glob("*.parquet")) if base.exists() else []
    if not files:
        return None
    frames = [pd.read_parquet(path) for path in files]
    merged = _sort_frame(pd.concat(frames, ignore_index=True))
    destination = merged_path(source, cache_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(destination, index=False)
    return destination


def write_manifest(report: ProductReport, cache_dir: Path | None = None) -> Path | None:
    """Record what was downloaded, so a run is auditable and resumable."""
    if report.window is None:
        return None
    lo, hi = report.window
    manifest = {
        "source": report.product.source,
        "sensor_family": report.product.family,
        "satellite": report.product.satellite,
        "processing": report.product.processing,
        "url_template": (
            f"{AREA_API_BASE}/{{MAP_KEY}}/{report.product.source}/"
            "{WEST,SOUTH,EAST,NORTH}/{DAY_RANGE}/{DATE}"
        ),
        "data_availability_url": DATA_AVAILABILITY_URL,
        "window": [lo.isoformat(), hi.isoformat()],
        "chunks": [
            {
                "start": r.chunk.start.isoformat(),
                "days": r.chunk.days,
                "status": r.status,
                "source": r.source_of_data,
                "rows": r.rows,
            }
            for r in report.results
        ],
        "rows": report.rows,
    }
    destination = (cache_dir or CACHE_DIR) / "raw" / f"{report.product.source}.manifest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2) + "\n")
    return destination


def download_product(
    source: str,
    bbox: tuple[float, float, float, float] = BANGLADESH_BBOX,
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    *,
    cache_dir: Path | None = None,
    map_key: str = "",
    fetcher: Callable[[str], Any] | None = None,
    limiter: TransactionLimiter | None = None,
    offline: bool | None = None,
    merge: bool = True,
) -> ProductReport:
    """Download one FIRMS source product over a window, chunk by chunk."""
    if source not in PRODUCTS:
        raise ValueError(f"unknown FIRMS source {source!r}; known: {sorted(PRODUCTS)}")
    product = PRODUCTS[source]
    window = product_window(product, start, end)
    report = ProductReport(product=product, window=window)
    if window is None:
        return report
    for chunk in chunk_windows(*window):
        report.results.append(
            download_chunk(
                product,
                chunk,
                bbox,
                map_key,
                cache_dir=cache_dir,
                fetcher=fetcher,
                limiter=limiter,
                offline=offline,
            )
        )
    if merge:
        report.merged = merge_product(source, cache_dir)
    # An all-missing run (typically OFFLINE=1 with an empty cache) is a
    # read-only dry run: record nothing, so `make cache` offline changes no
    # files on disk.
    if any(result.status != "missing" for result in report.results):
        write_manifest(report, cache_dir)
    return report


def download(
    products: Sequence[str] = DOWNLOAD_ORDER,
    bbox: tuple[float, float, float, float] = BANGLADESH_BBOX,
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    *,
    cache_dir: Path | None = None,
    map_key: str = "",
    fetcher: Callable[[str], Any] | None = None,
    limiter: TransactionLimiter | None = None,
    offline: bool | None = None,
    merge: bool = True,
) -> list[ProductReport]:
    """Download every requested product, in order (Suomi-NPP first)."""
    return [
        download_product(
            source,
            bbox,
            start,
            end,
            cache_dir=cache_dir,
            map_key=map_key,
            fetcher=fetcher,
            limiter=limiter,
            offline=offline,
            merge=merge,
        )
        for source in products
    ]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [p for p in value.replace(" ", "").split(",") if p]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"bbox must be west,south,east,north (4 values), got {value!r}"
        )
    try:
        west, south, east, north = (float(p) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"bbox values must be numbers: {value!r}") from exc
    return (west, south, east, north)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.acquire.firms",
        description="Download NASA FIRMS hot spots to parquet (Phase 0).",
    )
    parser.add_argument(
        "--products",
        default=os.environ.get("FIRMS_PRODUCTS", ",".join(DOWNLOAD_ORDER)),
        help="comma-separated FIRMS sources, in order (default: Suomi-NPP first, then MODIS, "
        "NOAA-20, NOAA-21)",
    )
    parser.add_argument(
        "--bbox",
        type=_parse_bbox,
        default=_parse_bbox(os.environ.get("FIRMS_BBOX", "88,20,93,27")),
        help="west,south,east,north (default: Bangladesh 88,20,93,27)",
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=date.fromisoformat(os.environ.get("FIRMS_START", DEFAULT_START.isoformat())),
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=date.fromisoformat(os.environ.get("FIRMS_END", DEFAULT_END.isoformat())),
    )
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--no-merge", action="store_true", help="skip the merged parquet")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    products = [p.strip() for p in args.products.split(",") if p.strip()]
    unknown = [p for p in products if p not in PRODUCTS]
    if unknown:
        print(f"unknown products: {unknown}; known: {sorted(PRODUCTS)}", file=sys.stderr)
        return 2

    offline = is_offline()
    map_key = ""
    if not offline:
        try:
            map_key = require_map_key()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    limiter = None if offline else TransactionLimiter()
    reports = download(
        products,
        args.bbox,
        args.start,
        args.end,
        cache_dir=args.cache_dir,
        map_key=map_key,
        limiter=limiter,
        offline=offline,
        merge=not args.no_merge,
    )
    for report in reports:
        print(report.summary())
        if report.merged:
            print(f"  merged -> {report.merged}")
    total_missing = sum(r.missing for r in reports)
    if offline and total_missing:
        print(
            f"{total_missing} chunk(s) missing from cache/fixtures while OFFLINE=1",
            file=sys.stderr,
        )
    return 0


__all__: Iterable[str] = (
    "AREA_API_BASE",
    "BANGLADESH_BBOX",
    "DOWNLOAD_ORDER",
    "MAX_DAY_RANGE",
    "PRODUCTS",
    "Chunk",
    "ChunkResult",
    "FirmsProduct",
    "ProductReport",
    "TransactionLimiter",
    "area_url",
    "bbox_param",
    "build_parser",
    "chunk_paths",
    "chunk_windows",
    "download",
    "download_chunk",
    "download_product",
    "is_offline",
    "load_map_key",
    "main",
    "merge_product",
    "parse_firms_csv",
    "product_window",
    "read_dotenv",
    "require_map_key",
    "write_manifest",
)


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(main())
