# Flows

Screens, navigation, and user journeys. The visual system and the keyboard map
are in `docs/DESIGN.md`; structure and runtime in `docs/ARCHITECTURE.md`;
requirements in `docs/PRD.md`.

---

## 1. Personas

| ID | Persona | Wants to answer | Time budget |
|----|---------|-----------------|-------------|
| P1 | Emergency responder / planner | "Is this period normal or elevated, and when does the season peak?" | seconds |
| P2 | Air-quality / environmental analyst | "How has this region trended, and is today unusual for the season?" | minutes |
| P3 | Reviewer / judge | "Is NASA data used correctly and is the result reproducible?" | seconds–minutes |
| P4 | Field user | "Does it still work with no network?" | seconds |

---

## 2. Screen inventory

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
**keyboard hint** (the shortcut list is in `docs/DESIGN.md` §7).

---

## 3. Navigation map

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

Deep links:

- `#calendar?year=2019&mode=harmonized` — shareable view state.
- `#anomalies?aoi=BGD&date=2019-03-01`
- Unknown hashes fall back to `#overview` with a non-blocking notice.

---

## 4. Screen detail

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

## 5. States on every screen

| State | What shows |
|-------|------------|
| Loading | Skeleton rows; no spinner-only layout shift |
| Empty | Named reason + next action (often "go to Offline") |
| Error | Field-level message for 422; retry for transient failures |
| Offline | Cached data with the offline badge; queued actions noted |
| Mock/fixture | Persistent banner: this is not evidence |

---

## 6. Overlay flows

| Overlay | Trigger | Close |
|---------|---------|-------|
| Provenance drawer | `P`, or clicking any source badge | `Esc`, backdrop click |
| Search | `Ctrl/Cmd + K` | `Esc` |
| Shortcut help | `?` | `Esc` |
| Theme switch | `T` | n/a (instant toggle) |

---

## 7. Journeys

### Journey 1 — Region overview (default path)

**Persona:** P1. **Goal:** judge whether the current season is normal.

```
Open app
  -> Overview screen loads (Rail + hero series chart)
  -> select preset region (Rail > region)
  -> hero series renders raw vs harmonized
  -> user presses H (or toggles mode) -> the false step collapses
  -> scroll to Calendar -> scan the current year row
  -> Success: the user can say "this season is normal / elevated"
```

The mode flip redraws both series from the same payload — no refetch — and the
calendar heatmap is derived client-side from it. **Failure paths:** no data →
empty state naming the reason; offline with no cache → offline notice and a link
to the Offline screen.

### Journey 2 — Anomaly check

**Persona:** P2. **Goal:** "Is this unusual?"

```
Anomalies screen
  -> pick date + area (or accept the current selection)
  -> POST /api/v1/anomalies
  -> read z-score, percentile, flag (Normal | Elevated | Extreme | Not scored)
  -> open Provenance drawer (P) to see the JSON and the baseline window
```

"Not scored" is a first-class outcome with a reason (low coverage, insufficient
reference years) — never a silent zero — and it states the baseline window and
the years used.

### Journey 3 — Season window (critical period)

**Persona:** P1 / P2. **Goal:** when to expect readiness.

```
Critical period screen
  -> POST /api/v1/critical-period
  -> read onset bin, peak bin, end bin, window mass
  -> cross-check the Calendar highlight for the same window
```

Below the density floor the screen reports "insufficient activity" and shows no
window.

### Journey 4 — Custom area of interest

**Persona:** P2. **Goal:** study a non-preset area.

```
Map screen
  -> draw a polygon
  -> client validates (closed ring, >= 4 points, within extent, <= 100,000 cells)
  -> submit -> series / anomalies / critical-period re-run for the polygon
  -> invalid input returns a structured error naming the field
```

### Journey 5 — Verify the method

**Persona:** P3. **Goal:** trust the result.

```
Methods screen (from the Rail's Reference group)
  -> read cell size, confidence filter, collapse rule
  -> Validation screen -> raw vs harmonized correlations on the overlap
  -> any chart -> Provenance drawer -> dataset names, versions, retrieval dates,
     parameter hash, the exact JSON behind the view
```

Every number on screen must lead here. Mock/fixture data is labelled at the point
of display and in the drawer.

### Journey 6 — Prepare for and use offline

**Persona:** P4. **Goal:** work with no network.

```
Offline screen
  -> choose area + layers
  -> see size estimate -> start download -> progress -> per-layer "last updated"
  -> Success: cold start with the network off serves the app shell and data
```

Exit criterion: after a full device reload with the network disabled, the
Overview renders and the mode toggle still responds.

---

## 8. Cross-cutting interactions

| Interaction | Applies to | Rule |
|-------------|------------|------|
| Mode toggle (`R` / `H`) | every data view | Global; never triggers a refetch. |
| Source badge | every figure | Shows `mock` / `fixture` / `cache` / `live`. |
| Provenance drawer (`P`) | every figure | Opens the JSON behind the current view. |
| Parameter hash | footer + drawer | Ties the view to a configuration. |
| Keyboard | all screens | Every shortcut has a visible alternative. |

---

## 9. Responsive behaviour

| Width | Shell |
|-------|-------|
| ≥ 1024px | Full rail + single main column |
| 640–1024px | Rail collapses to icon-only; labels on hover/focus |
| < 640px | Rail becomes a bottom bar; one card per view |

The mode control stays reachable at every width.

---

## 10. Success signals

- P1 reaches a normal/elevated judgement in under 30 seconds.
- P2 completes an anomaly check and can name the baseline window used.
- P3 can trace any number to a dataset, a version, and a parameter hash.
- P4 completes a cold start with the network off.
- The mode toggle measurably removes the sensor step, every time.

---

## 11. Non-goals

- Real-time alerting or push notifications.
- Fire-spread or emissions modelling.
- Multi-user accounts, sharing, or collaboration.
