# User Flows

Who uses Icarus, what they are trying to answer, and the path they take through
the app. Screens are named in `docs/ScreenFlow.md`; runtime behaviour is in
`docs/ApplicationFlow.md`.

---

## 1. Personas

| ID | Persona | Wants to answer | Time budget |
|----|---------|-----------------|-------------|
| P1 | Emergency responder / planner | "Is this period normal or elevated, and when does the season peak?" | seconds |
| P2 | Air-quality / environmental analyst | "How has this region trended, and is today unusual for the season?" | minutes |
| P3 | Reviewer / judge | "Is NASA data used correctly and is the result reproducible?" | seconds–minutes |
| P4 | Field user | "Does it still work with no network?" | seconds |

---

## 2. Journey 1 — Region overview (default path)

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

Steps:

1. App cold-starts on Overview (no query needed; default region).
2. Series request resolves and the hero chart paints.
3. User flips the **Raw | Harmonized** mode; both series redraw from the same
   payload — no refetch.
4. Calendar heatmap is derived client-side from the same series.
5. Source badge and parameter hash are visible in the footer.

**Failure paths:** no data → empty state with the reason; offline with no cache →
offline notice and a link to the Offline screen.

---

## 3. Journey 2 — Anomaly check

**Persona:** P2. **Goal:** "Is this unusual?"

```
Anomalies screen
  -> pick date + area (or accept the current selection)
  -> POST /api/v1/anomalies
  -> read z-score, percentile, flag (Normal | Elevated | Extreme | Not scored)
  -> open Provenance drawer (P) to see the JSON and the baseline window
```

- **Not scored** is a first-class outcome with a reason (`low_coverage`,
  insufficient reference years) — never a silent zero.
- The result states the baseline window and the years used.

---

## 4. Journey 3 — Season window (critical period)

**Persona:** P1 / P2. **Goal:** when to expect readiness.

```
Critical period screen
  -> POST /api/v1/critical-period
  -> read onset bin, peak bin, end bin, window mass
  -> cross-check the Calendar highlight for the same window
```

If annual activity is below the density floor, the screen reports
"insufficient activity" and shows no window.

---

## 5. Journey 4 — Custom area of interest

**Persona:** P2. **Goal:** study a non-preset area.

```
Map screen
  -> draw a polygon
  -> client validates (closed ring, >= 4 points, within extent, <= 100,000 cells)
  -> submit -> series / anomalies / critical-period re-run for the polygon
  -> invalid input returns a structured error naming the field
```

---

## 6. Journey 5 — Verify the method

**Persona:** P3. **Goal:** trust the result.

```
Methods screen (from the Rail's Reference group)
  -> read cell size, confidence filter, collapse rule
  -> Validation screen -> raw vs harmonized correlations on the overlap
  -> any chart -> Provenance drawer -> dataset names, versions, retrieval dates,
     parameter hash, the exact JSON behind the view
```

Every number on screen must lead here. Mock/fixture data is labelled at the
point of display and in the drawer.

---

## 7. Journey 6 — Prepare for and use offline

**Persona:** P4. **Goal:** work with no network.

```
Offline screen
  -> choose area + layers
  -> see size estimate -> start download -> progress -> per-layer "last updated"
  -> Success: cold start with the network off serves the app shell and data
```

Exit criteria for this journey: after a full device reload with the network
disabled, the Overview renders and the mode toggle still responds.

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

## 9. Success signals

- P1 reaches a normal/elevated judgement in under 30 seconds.
- P2 completes an anomaly check and can name the baseline window used.
- P3 can trace any number to a dataset, a version, and a parameter hash.
- P4 completes a cold start with the network off.
- The mode toggle measurably removes the sensor step, every time.

---

## 10. Non-goals

- Real-time alerting or push notifications.
- Fire-spread or emissions modelling.
- Multi-user accounts, sharing, or collaboration.
