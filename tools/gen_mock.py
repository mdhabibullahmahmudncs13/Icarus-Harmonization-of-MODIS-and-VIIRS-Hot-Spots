#!/usr/bin/env python3
"""Phase 0 mock generator for Project Icarus.

Generates deterministic, clearly-labelled mock payloads for the contract defined
in docs/contract.schema.json. Records are generated as cell-days first and then
aggregated, so the series, cells, baseline and calendar always agree.

The mock is NEVER evidence: every payload carries meta.source = "mock".

Usage:
    python3 tools/gen_mock.py --out web/public/mock
    python3 tools/gen_mock.py --check          # regenerate and validate only

Determinism: fixed seed, fixed generated_at, fixed iteration order -> identical
bytes on every run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# --- fixed configuration (mirrors config/params.yaml defaults) -------------
SEED = 20260101
CELL_KM = 5.5
K = 20  # cells per degree -> 0.05 deg step
STEP = 1.0 / K
BBOX = (60.0, 5.0, 93.0, 36.0)  # pilot extent: 60-93E, 5-36N
WINDOW = (date(2010, 1, 1), date(2016, 12, 31))
VIIRS_START = date(2012, 1, 20)
MIN_CONFIDENCE = 50
CONF_MAP = {"low": 25, "nominal": 60, "high": 90}
GENERATED_AT = "2026-10-05T00:00:00Z"  # fixed for byte-stable output
COLLAPSE_RULE = "harmonized = distinct 5.5 km cell-days per day; a cell is one row"

# sensor sensitivities (mock only). MODIS and VIIRS mostly see the same cell-days;
# VIIRS emits several detections per cell-day, which is what inflates raw counts.
T_MOD = 0.50
T_VIIRS = 0.45
P_MOD_EXTRA = 0.04
P_VIIRS_EXTRA = 0.03
VIIRS_DET_LAMBDA = 1.6

BLOB_CENTERS = [
    (90.0, 23.5),
    (91.5, 24.5),
    (88.5, 22.5),
    (79.0, 21.5),
    (85.0, 24.0),
]
BLOB_RADIUS_DEG = 0.30

# AOI presets, inside the pilot extent. Read from the shared JSON that the
# API's /api/v1/aoi payload also uses, so the mock and the API cannot drift
# (docs/IMPLEMENTATION_PLAN.md §5).
PRESETS_PATH = Path(__file__).resolve().parents[1] / "src" / "aoi_presets.json"
PRESETS = [
    (str(entry["id"]), str(entry["name"]), [float(v) for v in entry["bbox"]])
    for entry in json.loads(PRESETS_PATH.read_text())["presets"]
]

DATASETS = [
    {
        "id": "FIRMS_MODIS",
        "product": "MODIS_SP",
        "sensor": "MODIS C6.1 (Terra + Aqua), 1 km",
        "used_for": "Raw + harmonized MODIS series",
        "url": "https://firms.modaps.eosdis.nasa.gov/api/area/",
    },
    {
        "id": "FIRMS_VIIRS_NOAA20",
        "product": "VIIRS_NOAA20_SP",
        "sensor": "VIIRS 375 m, NOAA-20",
        "used_for": "Raw + harmonized VIIRS series",
        "url": "https://firms.modaps.eosdis.nasa.gov/api/area/",
    },
    {
        "id": "FIRMS_VIIRS_SNPP",
        "product": "VIIRS_SNPP_SP",
        "sensor": "VIIRS 375 m, Suomi-NPP",
        "used_for": "Overlap validation only",
        "url": "https://firms.modaps.eosdis.nasa.gov/api/area/",
    },
]

NOTICES = [
    "Mock data: not evidence, not an observation, not used in the demo video.",
    "Cell size 5.5 km; harmonized series is distinct cell-days per day.",
    "Confidence filter >= 50 after mapping VIIRS low/nominal/high.",
]


def params_hash() -> str:
    payload = json.dumps(
        {
            "seed": SEED,
            "cell_km": CELL_KM,
            "K": K,
            "bbox": BBOX,
            "window": [WINDOW[0].isoformat(), WINDOW[1].isoformat()],
            "min_confidence": MIN_CONFIDENCE,
            "confidence_mapping": CONF_MAP,
            "viirs_start": VIIRS_START.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:12]


def seasonal(doy: int) -> float:
    """Broad single peak around late March (dry-season burning). Mock only."""
    return 0.08 + 0.92 * (0.5 * (1.0 + math.cos(2 * math.pi * (doy - 90) / 365.0))) ** 1.5


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth's algorithm; small lambda only."""
    limit = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limit:
            return k - 1


def cell_index(lon: float, lat: float, factor: int = 1) -> tuple[int, int]:
    step = STEP * factor
    return math.floor(lon / step), math.floor(lat / step)


def build_cells() -> list[tuple[float, float, float]]:
    """Return sorted list of (lon_centre, lat_centre, intensity)."""
    seen: dict[tuple[int, int], tuple[float, float]] = {}
    for cx, cy in BLOB_CENTERS:
        ix0, ix1 = cell_index(cx - BLOB_RADIUS_DEG, cy - BLOB_RADIUS_DEG)
        ix2, ix3 = cell_index(cx + BLOB_RADIUS_DEG, cy + BLOB_RADIUS_DEG)
        for ix in range(ix0, ix2 + 1):
            for iy in range(ix1, ix3 + 1):
                lon, lat = (ix + 0.5) * STEP, (iy + 0.5) * STEP
                if BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]:
                    seen[(ix, iy)] = (lon, lat)
    rng = random.Random(SEED ^ 0xB10B)
    cells = []
    for (ix, iy) in sorted(seen):
        lon, lat = seen[(ix, iy)]
        cells.append((lon, lat, rng.uniform(0.05, 0.35)))
    return cells


def simulate() -> dict:
    rng = random.Random(SEED)
    cells = build_cells()
    days = [WINDOW[0] + timedelta(days=i) for i in range((WINDOW[1] - WINDOW[0]).days + 1)]

    daily = []  # per day: raw_modis, raw_viirs, harm sets
    cell_raw: dict[tuple[int, int], int] = {}
    cell_harm: dict[tuple[int, int], int] = {}
    cell_frp: dict[tuple[int, int], float] = {}
    day_sets: list[tuple[set, set]] = []

    for d in days:
        s = seasonal(d.timetuple().tm_yday)
        modis_set: set[tuple[int, int]] = set()
        viirs_set: set[tuple[int, int]] = set()
        raw_modis = 0
        raw_viirs = 0
        for idx, (lon, lat, intensity) in enumerate(cells):
            if rng.random() >= intensity * s:
                continue  # no fire this cell-day
            size = rng.random()
            key = cell_index(lon, lat)
            is_modis = size >= T_MOD or rng.random() < P_MOD_EXTRA
            is_viirs = d >= VIIRS_START and (size >= T_VIIRS or rng.random() < P_VIIRS_EXTRA)
            if is_modis:
                raw_modis += 1
                modis_set.add(key)
                frp = math.exp(rng.gauss(1.2, 0.7))
                cell_raw[key] = cell_raw.get(key, 0) + 1
                cell_frp[key] = max(cell_frp.get(key, 0.0), frp)
            if is_viirs:
                k = 1 + poisson(rng, VIIRS_DET_LAMBDA)
                raw_viirs += k
                viirs_set.add(key)
                frp = math.exp(rng.gauss(1.5, 0.7))
                cell_raw[key] = cell_raw.get(key, 0) + k
                cell_frp[key] = max(cell_frp.get(key, 0.0), frp)
        union = modis_set | viirs_set
        for key in union:
            cell_harm[key] = cell_harm.get(key, 0) + 1
        daily.append(
            {
                "date": d.isoformat(),
                "raw_modis": raw_modis,
                "raw_viirs": raw_viirs,
                "raw_total": raw_modis + raw_viirs,
                "harm_modis": len(modis_set),
                "harm_viirs": len(viirs_set),
                "harm_total": len(union),
            }
        )
        day_sets.append((modis_set, viirs_set))

    return {
        "cells": cells,
        "days": days,
        "daily": daily,
        "day_sets": day_sets,
        "cell_raw": cell_raw,
        "cell_harm": cell_harm,
        "cell_frp": cell_frp,
    }


# --- statistics ------------------------------------------------------------
def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def ranks(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    return pearson(ranks(xs), ranks(ys))


def percentile(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def meta() -> dict:
    return {
        "source": "mock",
        "generated_at": GENERATED_AT,
        "region": {"bbox": list(BBOX)},
        "cell_km": CELL_KM,
        "min_confidence": MIN_CONFIDENCE,
        "date_range": [WINDOW[0].isoformat(), WINDOW[1].isoformat()],
        "params_hash": params_hash(),
    }


def build_payloads(sim: dict) -> dict[str, dict]:
    days = sim["days"]
    daily = sim["daily"]

    meta_response = {
        "meta": meta(),
        "sensors": [
            {"product": "MODIS_SP", "family": "MODIS", "start": WINDOW[0].isoformat(), "end": WINDOW[1].isoformat()},
            {"product": "VIIRS_NOAA20_SP", "family": "VIIRS", "start": VIIRS_START.isoformat(), "end": WINDOW[1].isoformat()},
            {"product": "VIIRS_SNPP_SP", "family": "VIIRS", "start": VIIRS_START.isoformat(), "end": "2018-12-31"},
        ],
        "years": {"start": WINDOW[0].year, "end": WINDOW[1].year},
        "streams": ["MOD_T", "MOD_A", "VIIRS_SNPP", "VIIRS_N20", "VIIRS_N21"],
    }

    series = {"meta": meta(), "metric": "cell_days", "bin_days": 1, "series": daily}

    cells_payload = {
        "meta": meta(),
        "window": {"start": WINDOW[0].isoformat(), "end": WINDOW[1].isoformat()},
        "cells": [],
    }
    for (lon, lat, _intensity) in sim["cells"]:
        key = cell_index(lon, lat)
        cells_payload["cells"].append(
            {
                "cell_id": f"{key[0]}_{key[1]}",
                "bounds": [
                    round(key[0] * STEP, 4),
                    round(key[1] * STEP, 4),
                    round((key[0] + 1) * STEP, 4),
                    round((key[1] + 1) * STEP, 4),
                ],
                "raw": sim["cell_raw"].get(key, 0),
                "harmonized": sim["cell_harm"].get(key, 0),
                "peak_frp": round(sim["cell_frp"][key], 3) if key in sim["cell_frp"] else None,
            }
        )

    baseline_rows = []
    years_used = sorted({d.year for d in days})
    for doy in range(1, 367):
        vals = [daily[i]["harm_total"] for i, d in enumerate(days) if d.timetuple().tm_yday == doy]
        baseline_rows.append(
            {
                "doy": doy,
                "p05": round(percentile(vals, 0.05), 2),
                "p25": round(percentile(vals, 0.25), 2),
                "p50": round(percentile(vals, 0.50), 2),
                "p75": round(percentile(vals, 0.75), 2),
                "p95": round(percentile(vals, 0.95), 2),
            }
        )
    baseline = {"meta": meta(), "window_days": 15, "years_used": years_used, "baseline": baseline_rows}

    # anomaly: the peak-harmonized day of the last full year
    last_year = max(d.year for d in days)
    last_idx = [i for i, d in enumerate(days) if d.year == last_year]
    peak_i = max(last_idx, key=lambda i: daily[i]["harm_total"])
    peak_doy = days[peak_i].timetuple().tm_yday
    window = 15
    lo, hi = peak_doy - window, peak_doy + window
    ref = [
        daily[i]["harm_total"]
        for i, d in enumerate(days)
        if i != peak_i and lo <= d.timetuple().tm_yday <= hi
    ]
    value = daily[peak_i]["harm_total"]
    pct = (sum(1 for v in ref if v <= value) / len(ref)) if ref else None
    if pct is None or len(ref) < 8:
        flag, reason = "not_scored", "insufficient_reference_years"
    elif pct >= 0.99:
        flag, reason = "extreme", None
    elif pct >= 0.90:
        flag, reason = "elevated", None
    else:
        flag, reason = "normal", None
    anomalies = {
        "meta": meta(),
        "query": {"date": days[peak_i].isoformat(), "aoi": "BGD"},
        "value": value,
        "percentile": round(pct, 4) if pct is not None else None,
        "flag": flag,
        "baseline_window": window,
        "doy_range": [lo, hi],
        "years_used": years_used,
        "reason": reason,
    }

    # critical period from 8-day bins of harmonized activity
    bins = [0] * 46
    for i, d in enumerate(days):
        b = min((d.timetuple().tm_yday - 1) // 8 + 1, 46)
        bins[b - 1] += daily[i]["harm_total"]
    total = sum(bins)
    if total == 0:
        critical = {
            "meta": meta(), "aoi": "BGD", "insufficient_activity": True,
            "onset_bin": None, "peak_bin": None, "end_bin": None, "window": None,
            "year_timing_deviation": [],
        }
    else:
        cum, onset, end = 0.0, None, None
        for i, v in enumerate(bins):
            cum += v
            if onset is None and cum / total >= 0.10:
                onset = i + 1
            if end is None and cum / total >= 0.90:
                end = i + 1
        peak = max(range(46), key=lambda i: bins[i]) + 1
        mass = sum(bins[max(onset - 2, 0):end + 1]) / total
        critical = {
            "meta": meta(), "aoi": "BGD", "insufficient_activity": False,
            "onset_bin": onset, "peak_bin": peak, "end_bin": end,
            "window": {"start_bin": max(onset - 1, 1), "end_bin": min(end + 1, 46), "mass": round(mass, 4)},
            "year_timing_deviation": [
                {"year": y, "days": round(seasonal(90 + y % 7 - 3) * 30 - 20)} for y in years_used
            ],
        }

    # validation over the overlap years (both sensors present)
    overlap_idx = [i for i, d in enumerate(days) if d >= VIIRS_START]
    rm = [daily[i]["raw_modis"] for i in overlap_idx]
    rv = [daily[i]["raw_viirs"] for i in overlap_idx]
    hm = [daily[i]["harm_modis"] for i in overlap_idx]
    hv = [daily[i]["harm_viirs"] for i in overlap_idx]

    def ratio(a: list[int], b: list[int]) -> float | None:
        sa, sb = sum(a), sum(b)
        return round(sa / sb, 4) if sb else None

    raw_corr = pearson([float(v) for v in rm], [float(v) for v in rv]) or 0.0

    def sweep() -> list[dict]:
        """Agreement between MODIS and VIIRS as cell size coarsens.

        Raw correlation stays flat (detections are point data and do not
        aggregate); harmonized correlation is recomputed at each resolution
        from the underlying cell-day sets.
        """
        out = []
        overlap = [(ms, vs) for (ms, vs), d in zip(sim["day_sets"], days) if d >= VIIRS_START]
        for factor in (1, 2, 4):
            a_counts, b_counts = [], []
            for (ms, vs) in overlap:
                if factor == 1:
                    a_counts.append(len(ms))
                    b_counts.append(len(vs))
                else:
                    a_counts.append(len({cell_index((ix + 0.5) * STEP, (iy + 0.5) * STEP, factor) for (ix, iy) in ms}))
                    b_counts.append(len({cell_index((ix + 0.5) * STEP, (iy + 0.5) * STEP, factor) for (ix, iy) in vs}))
            corr = pearson([float(v) for v in a_counts], [float(v) for v in b_counts]) or 0.0
            out.append({
                "cell_km": round(CELL_KM * factor, 2),
                "raw_correlation": round(raw_corr, 4),
                "harmonized_correlation": round(corr, 4),
            })
        return out

    validation = {
        "meta": meta(),
        "overlap": {"years": sorted({days[i].year for i in overlap_idx}), "n_days": len(overlap_idx)},
        "raw": {
            "pearson": round(pearson([float(v) for v in rm], [float(v) for v in rv]) or 0.0, 4),
            "spearman": round(spearman([float(v) for v in rm], [float(v) for v in rv]) or 0.0, 4),
            "ratio": ratio(rm, rv),
        },
        "harmonized": {
            "pearson": round(pearson([float(v) for v in hm], [float(v) for v in hv]) or 0.0, 4),
            "spearman": round(spearman([float(v) for v in hm], [float(v) for v in hv]) or 0.0, 4),
            "ratio": ratio(hm, hv),
        },
        "cell_sweep": sweep(),
    }

    methods = {
        "meta": meta(),
        "cell_km": CELL_KM,
        "min_confidence": MIN_CONFIDENCE,
        "confidence_mapping": CONF_MAP,
        "collapse_rule": COLLAPSE_RULE,
        "notices": NOTICES,
        "datasets": DATASETS,
    }

    aoi = {
        "meta": meta(),
        "presets": [{"id": pid, "name": name, "bbox": bbox} for pid, name, bbox in PRESETS],
    }

    return {
        "meta": meta_response,
        "series": series,
        "cells": cells_payload,
        "baseline": baseline,
        "anomaly": anomalies,
        "critical-period": critical,
        "validation": validation,
        "methods": methods,
        "aoi": aoi,
    }


# --- validation ------------------------------------------------------------
DEF_FOR = {
    "meta": "metaResponse",
    "series": "series",
    "cells": "cells",
    "baseline": "baseline",
    "anomaly": "anomalies",
    "critical-period": "criticalPeriod",
    "validation": "validation",
    "methods": "methods",
    "aoi": "aoi",
}


def validate(payloads: dict[str, dict], schema_path: Path) -> list[str]:
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads(schema_path.read_text())
    defs = schema["$defs"]
    errors = []
    for name, payload in payloads.items():
        target = DEF_FOR.get(name, name)
        if target not in defs:
            errors.append(f"{name}: no $defs entry named {target!r}")
            continue
        validator = Draft202012Validator({"$ref": f"#/$defs/{target}", "$defs": defs}, format_checker=FormatChecker())
        for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
            errors.append(f"{name}: {'/'.join(map(str, err.path))}: {err.message}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="web/public/mock", help="output directory")
    ap.add_argument("--schema", default="docs/contract.schema.json")
    ap.add_argument("--check", action="store_true", help="validate without writing")
    args = ap.parse_args()

    sim = simulate()
    payloads = build_payloads(sim)

    errors = validate(payloads, Path(args.schema))
    if errors:
        print("SCHEMA ERRORS:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 1

    if not args.check:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for name, payload in payloads.items():
            (out / f"{name}.json").write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")

    # summary
    daily = payloads["series"]["series"]
    pre = [d for d in daily if d["date"] < VIIRS_START.isoformat()]
    post = [d for d in daily if d["date"] >= VIIRS_START.isoformat()]

    def mean(vals):
        return sum(vals) / len(vals) if vals else 0.0

    print("Phase 0 mock generated")
    print(f"  source         : {payloads['meta']['meta']['source']}")
    print(f"  params_hash    : {payloads['meta']['meta']['params_hash']}")
    print(f"  days           : {len(daily)}  ({WINDOW[0]} .. {WINDOW[1]})")
    print(f"  active cells   : {len(payloads['cells']['cells'])}")
    print(f"  raw step ratio : {mean([d['raw_total'] for d in post]) / max(mean([d['raw_total'] for d in pre]), 1e-9):.2f}x")
    print(f"  harm step ratio: {mean([d['harm_total'] for d in post]) / max(mean([d['harm_total'] for d in pre]), 1e-9):.2f}x")
    print(f"  schema         : OK ({len(payloads)} payloads)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
