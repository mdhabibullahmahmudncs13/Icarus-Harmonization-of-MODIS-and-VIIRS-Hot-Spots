# Screen Flow

Every screen, how you reach it, and what it shows in each state. Visual tokens
and components are in `docs/DESIGN.md`; journeys in `docs/UserFlow.md`; runtime
behaviour in `docs/ApplicationFlow.md`.

---

## 1. Screen inventory

| # | Screen | Hash | Purpose |
|---|--------|------|---------|
| 0 | Overview | `#overview` | Region summary: hero series + calendar preview |
| 1 | Calendar | `#calendar` | Burning-activity calendar (years × 46 bins) |
| 2 | Map | `#map` | Cell map + AOI selection |
| 3 | Anomalies | `#anomalies` | "Is this unusual?" — z-score, percentile, flag |
| 4 | Critical period | `#critical` | Onset, peak, end, window mass |
| 5 | Validation | `#validation` | Raw vs harmonized correlation on the overlap |
| 6 | Methods | `#methods` | Cell size, confidence filter, collapse rule, datasets |
| 7 | Offline | `#offline` | Download-for-offline manager |

Global chrome on every screen: the **rail** (brand, search, Raw | Harmonized
mode, nav, theme switch, status footer), the **source badge**, and the
**keyboard hint**.

---

## 2. Navigation map

```
                      ┌───────────────────────────────┐
                      │ Rail (persistent, 244px)      │
                      │  Brand · Search · [Raw|Harm]  │
                      │  Views: 0 1 2 3 4 5           │
                      │  Reference: 6 Methods, Data   │
                      │  Footer: theme, source, hash  │
                      └──────────────┬────────────────┘
                                     │ selects view (hash update)
        ┌────────────┬───────────────┼───────────────┬────────────┐
        v            v               v               v            v
   0 Overview   1 Calendar      2 Map          3 Anomalies   4 Critical
                                       │                          │
                                       │ draw polygon             │
                                       v                          v
                              (series/anomalies/critical     5 Validation
                               re-run for polygon)                 │
                                                                   v
                                                             6 Methods
                                                                   │
                                       7 Offline  <───────────────┘
                                                     (from footer or empty state)

  Any figure ──▶ Provenance drawer (overlay) ──▶ Esc to close
```

Navigation is linear via the rail; the URL hash is the source of truth, so any
screen is deep-linkable and the back button works.

---

## 3. Screen detail

### Screen 0 — Overview

- **Entry:** app start; `#overview`.
- **Shows:** hero daily series (raw vs harmonized), sensor epochs, a compact
  calendar preview, source badge.
- **Primary action:** flip the mode to collapse the step.

### Screen 1 — Calendar

- **Entry:** rail, or the calendar preview.
- **Shows:** rows = years, columns = 46 eight-day bins, ramped by density.
  Low-coverage bins hatched; modelled bins outlined.
- **Primary action:** select a bin → tooltip with value, units, coverage, source.

### Screen 2 — Map

- **Entry:** rail, or a "view cells" link from Calendar/Critical period.
- **Shows:** cell polygons shaded by the active mode; legend with units.
- **Primary action:** draw a polygon AOI, or pick a preset.
- **States:** no basemap by default offline; PMTiles when bundled.

### Screen 3 — Anomalies

- **Entry:** rail; accepts a date + area.
- **Shows:** z-score, percentile, flag (Normal / Elevated / Extreme / Not
  scored), baseline window, years used.
- **Primary action:** change date → re-ask.

### Screen 4 — Critical period

- **Entry:** rail.
- **Shows:** onset, peak, end bins, window mass, year-to-year timing deviation.
- **Edge:** "insufficient activity" when below the density floor.

### Screen 5 — Validation

- **Entry:** rail (Reference group), or a Methods link.
- **Shows:** raw and harmonized correlations over the overlap, cell-size sweep.
- **Reads:** static JSON bundled with the app.

### Screen 6 — Methods

- **Entry:** rail (Reference group).
- **Shows:** cell size, confidence filter, collapse rule, dataset ids + URLs,
  notices (e.g. Suomi-NPP ends 1 Nov 2026).

### Screen 7 — Offline

- **Entry:** rail (Reference group), or the offline notice in any empty state.
- **Shows:** area/layer picker, size estimate, progress, per-layer "last
  updated".
- **Exit:** "Done" → returns to the previous screen.

---

## 4. Per-screen states

Every data screen implements the same five states:

| State | What shows |
|-------|------------|
| Loading | Skeleton rows; no spinner-only layout shift |
| Empty | Named reason + next action (often "go to Offline") |
| Error | Field-level message for 422; retry for transient failures |
| Offline | Cached data with the offline badge; queued actions noted |
| Mock/fixture | Persistent banner: this is not evidence |

---

## 5. Overlay flows

| Overlay | Trigger | Close |
|---------|---------|-------|
| Provenance drawer | `P`, or clicking any source badge | `Esc`, backdrop click |
| Search | `Ctrl/Cmd + K` | `Esc` |
| Shortcut help | `?` | `Esc` |
| Theme switch | `T` | n/a (instant toggle) |

---

## 6. Keyboard navigation

| Keys | Action |
|------|--------|
| `1`–`8` | Jump to a screen by rail position |
| `Ctrl/Cmd + B` | Collapse / expand the rail |
| `Ctrl/Cmd + K` | Focus search |
| `R` / `H` | Switch mode to Raw / Harmonized |
| `←` / `→` | Move the selected date/bin (Calendar, Anomalies) |
| `P` | Open Provenance |
| `T` | Toggle theme |
| `?` | Shortcut help |
| `Esc` | Close overlay / dismiss |

Focus order: rail → mode control → main content → overlay. Focus is always
visible (2px accent ring, 2px offset).

---

## 7. Responsive behaviour

| Width | Shell |
|-------|-------|
| ≥ 1024px | Full rail + single main column |
| 640–1024px | Rail collapses to icon-only; labels on hover/focus |
| < 640px | Rail becomes a bottom bar; one card per view |

The mode control stays reachable at every width.

---

## 8. Deep links

- `#calendar?year=2019&mode=harmonized` — shareable view state.
- `#anomalies?aoi=BGD&date=2019-03-01`
- Unknown hashes fall back to `#overview` with a non-blocking notice.
