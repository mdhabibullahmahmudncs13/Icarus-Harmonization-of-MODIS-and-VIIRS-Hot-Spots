---
version: 1
slug: "web-src-app-tsx"
primary_target: "web/src/App.tsx"
related_targets: []
---

# Surface brief: web/src/App.tsx (app shell + hero timeline)

Mode: Operate (a data instrument for judges, analysts, researchers).
Scope: redesign the existing F1/F2 surface into the visual world committed in
docs/DESIGN.md (v2). No new data features: no globe, calendar, or validation
tiles in this pass (DESIGN.md build order 1–2: shell + timeline first).
Execution: code-led (no image generation available this session).

## Direction contract

THESIS: One toggle turns a sensor artifact into an honest record. The surface
owns the moment the false 2012 step dissolves; it refuses the category-default
arrangement of KPI card grids, chrome-colored charts, and a neutral dashboard
shell.

OWN-WORLD: DESIGN.md light world — pale mint/sage/lime mesh ground; frosted
glass tiles (white 60% fill, 24px blur, 20px radius, hairline white border);
near-black ink #0A0F0C on glass; raw = black #0B0F0D, harmonized = green
#138A4B (green text #0F6B3A); 7-step pale-green→near-black data ramp; neutral
greys only — no red, blue, orange, or purple anywhere. Fraunces for display,
Inter for UI, JetBrains Mono for numerals and tabular figures.

STORY: the judge reads raw counts with a false step at the sensor transition,
flips the black→green toggle, and watches the step collapse while the seasonal
signal stays; every figure opens its source JSON; the persistent mock banner
keeps the demo honest.

FIRST VIEWPORT: at 1440px — a floating glass top bar (sun-step mark +
"Icarus" wordmark left; Timeline / Status anchors center; RAW|HARMONIZED
segmented control with sliding thumb right, black/green active fills; source
badge far right). Below on the mesh ground, a full-width black Mock-data strip
(source=mock). Main column: one large glass hero tile — Fraunces headline
"Same fires. One honest record.", Inter sub-line, then the timeline chart with
era bands (MODIS only / overlap / VIIRS era from meta.sensors), a dashed
sensor-transition marker, a ghost line for the inactive mode with direct
"Raw"/"Harmonized" end labels, mono tooltip and readout. A compact glass
status tile sits below-right with the data-freshness stamp, its own
provenance button ("View meta JSON"), and grid parameters; the source
badge lives in the top bar.
Primary action: the toggle in the top bar. ≤900px: single column, toggle
full-width under the title.

FORM: redesign of the incumbent surface; brief-pinned direction (the user
named docs/DESIGN.md + docs/frontend.md), position 1 of 1 — no concept-seed
roll was run because the direction is pinned; seed key: none (pinned-by-brief;
mode rules taken from mode-operate.md).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Addendum (4 Oct 2026): the globe pass

The direction above is superseded. A later session added the globe hero the
brief excluded, working from a supplied reference image rather than a pinned
type brief, and inverted the world to dark (docs/DESIGN.md section 0.1). Scope
of that pass: section 1 = procedural Three.js Earth + data-driven busiest-cells
panel, section 2 = the same timeline chart. The globe's own reconstruction
contract is `web/src/globe/globeSpec.ts`; the surface is `web/src/components/GlobeHero.tsx`.
