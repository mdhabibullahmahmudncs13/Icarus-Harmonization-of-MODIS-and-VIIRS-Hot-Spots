# DESIGN.md: Icarus Web Experience

**Project:** Icarus: Harmonization of MODIS and VIIRS Hot Spots (NASA Space Apps 2026, Challenge 9, Bangladesh)
**Scope:** `web/` frontend: visual identity, layout, 3D globe, interactions, motion, accessibility, offline UX, demo choreography
**Direction (v2):** light theme in shades of green and black, bento-grid layout over a full-viewport Three.js globe, minimal glassmorphism
**Direction (v3, shipped):** **dark** theme — near-black green ground, one neon green accent, pale mint for raw — with a procedural dot-matrix Earth as the hero (section 0.1). v2's light palette is superseded and kept below only as history.
**Companions:** PRD, TRD (requirements and architecture), `CLAUDE.md` (non-negotiables)

---

## 0. What this document is based on

**Repo.** I reviewed the repo's root page, `README.md`, `CLAUDE.md`, `AGENTS.md`, and `pyproject.toml`. GitHub blocked automated access to the folder pages, so **`web/`, `src/`, `docs/`, and `demo_fixtures/` were not opened**. If `web/` already has a scaffold, keep its stack and map the tokens in section 4 onto it.

What the repo establishes (this design obeys it):

- Status: context files and harness only. Harmonization, API, frontend and agent code are stubs.
- Deliverables: raw/harmonized toggle, burning-activity calendar (day-of-year by year), seasonal baseline plus anomaly question, methods panel (cell size, confidence filter, collapse rule, validation correlations, sensor retirement note).
- Rules: offline-first (`OFFLINE=1`), frontend never calls NASA, every dataset cited with id and URL, FIRMS product names used verbatim, every AI tool recorded in `docs/AI_USE.md`, Apache-2.0, **no under-18 likeness anywhere**.
- Defaults: 5.5 km grid (configurable), confidence >= 50, raw = all detections per day, harmonized = distinct cell-days per day.

**Reference site (https://2050.earth/).** Only the page markup could be read, not its visuals, so nothing here copies its look. The interaction patterns taken from it are: a **Map | Feed** switch, a minimal top navigation, a row of **filter chips**, and a "what's hot" strip of clickable cards that jump the map. Everything visual (glass, green and black, bento) comes from the direction set in this project.

Gaps worth fixing before the UI depends on them:

1. **Sensor list.** README and `CLAUDE.md` list MODIS plus VIIRS NOAA-20 and NOAA-21 only, and describe the problem as "post-2012". NOAA-20 and NOAA-21 launched well after 2012 (from my knowledge, verify), so the 2003 to 2026 demo and a 2012 transition likely also need Suomi-NPP, which NASA stops serving on 1 Nov 2026. The UI's era bands (section 7.2) are driven by `/api/meta` data windows, so they follow whatever the data actually contains.
2. **Package paths.** `pyproject.toml` uses `where = ["src"]`, while the Makefile runs `uvicorn src.api.main:app`. Pick one import style before the API is written.
3. **Dependencies.** No test client for FastAPI (`httpx`) and no numeric/stat library is declared. Add them with the compute code.

---

- **v2 (light) is superseded.** The shipped tokens are the dark set in `web/src/styles/tokens.css`; the v2 block quoted in section 4.2 is history. Dark was P2 in v2 and is now the default because the globe hero is the product surface and a dot-matrix Earth only reads on a dark ground.

## 0.1 Direction v3 — what shipped (4 Oct 2026)

**World.** Near-black green ground (`#010c09`), one neon green accent (`#2ee87d`), pale mint for raw (`#eafff3`). Black can no longer mean "raw" on a black page, so the metaphor inverts: **raw is pale and dense, harmonized is green and corrected.** Everything else from v2 stands — one idea per tile, green-and-black only, no new hues, self-hosted type, glass that serves legibility.

**Hero (section 1).** A code-authored Three.js Earth (`web/src/globe/`, spec in `globeSpec.ts`): a near-black sphere body, a 1° dot-matrix land shell from the Natural Earth 110 m mask (`npm run land:gen`), a faint graticule, one tilted orbit ring, a dim starfield, and the study region's own cells as glowing dots with light streaks on the busiest ones. No downloaded meshes and no image textures — the whole model is procedural, so it stays offline and inspectable. The camera is owned by the page (`GlobeView`): centred on the region by default, held still; drag to spin; "Whole Earth" releases the spin; clicking a cell in the panel flies to it.

**Honesty rules for the hero.**
1. Every dot is a grid cell at its own coordinates with its own count; nothing is placed decoratively.
2. At full density 10 047 cells merge into one white patch with no readable structure, so the globe draws the **500 busiest** (ranked once by the higher of the two counts, so the set does not change when the mode is toggled). The legend says so, and the panel plus the cells JSON carry every cell.
3. WebGL failure degrades to a labelled note; the rest of the page is unaffected.

**Panel (section 1, right).** The reference's "what's hot" column, made data-driven: the seven busiest cells in the active mode, each selectable, with the region total and the mock window stated.

**Timeline (section 2).** The v2 chart, restyled: raw is the pale line, harmonized the green one, era bands and the sensor-transition marker unchanged.

---

## 1. Design concept

**Name story.** Icarus flew too close to the sun. Wildfire analysis has the same trap: a finer sensor gets closer, sees more, and the record inflates. The interface tells that story and then shows the correction.

**Tagline:** *Same fires. One honest record.*

**Experience in one sentence:** a calm, light, glass-and-green workspace over a living 3D globe, where one toggle turns noisy black detections into clean green grid cells and the false step in the data dissolves.

**Color metaphor.** **Black = raw** (dense, noisy, unprocessed). **Green = harmonized** (clean, corrected). The toggle itself tells the story before any chart is read.

**Hero moment:** the raw/harmonized morph. On the globe, scattered black points fly into square green cells. In the same 700 ms the timeline step flattens, the calendar lightens, and the map cells reorganize.

### Design principles

1. **The toggle is the product.** It is global, always visible, and everything responds to it.
2. **Honest by construction.** Same color scale in raw and harmonized so the difference is truthful. No smoothing that hides gaps. Copy reports what was measured, not what it means.
3. **Show the proof next to the claim.** Validation correlations and the provenance drawer are first-class UI, not footnotes.
4. **Minimal.** One idea per tile, generous whitespace, thin type. If an element does not help read the data, remove it.
5. **Glass serves legibility.** Frosted panels float over the globe, but text always sits on a sufficiently opaque fill.
6. **Resilient on camera.** Works with wifi off. Source badges (`live`, `cache`, `fixture`) read as rigor.
7. **Measured claims only.** Never hard-code a metric such as a step ratio or correlation. Every figure comes from the API; loading shows skeletons or an em dash.

---

## 2. Audience and tasks

| Persona | Primary task | Where the UI serves it |
|---|---|---|
| Judge (global, 30 s to 4 min) | Understand the problem and see it solved | Story mode, globe morph, validation tiles |
| Responder / analyst | "Is this unusual for this place and time of year?" | Ask tile, calendar, globe |
| Researcher | Verify method, reproduce | Methods drawer, provenance drawer, README link |

---

## 3. Information architecture

Single-page app. Two ways of using it: **Story** (guided, for demos) and **Explore** (free). Two ways of viewing: **Globe** and **Feed**.

```
Floating top bar:  [Icarus mark] [Overview Calendar Validate Ask Methods]
                   [Globe | Feed] [ RAW | HARMONIZED ] [Story] [theme] [source badge]
Chip row:          Region · Sensor (MODIS/VIIRS) · Date range · Season     (filters everything)
Globe view:        full-viewport Three.js globe + floating glass bento tiles
Feed view:         pale blurred backdrop + single column of the same tiles as cards
Drawers:           Methods (right) · Provenance (right, stacked) · Data table (bottom, accessibility)
Footer:            Datasets, licenses, AI use, repo link, "NASA FIRMS" citation
```

Navigation: top-bar links scroll or focus the matching tile in Globe view; on mobile a bottom tab bar replaces them. All views share one state (section 8).

---

## 4. Visual identity

### 4.1 Mood

Light and airy, like frosted glass over a pale mint landscape, with black used as ink. Precise and quiet. Nothing decorative that is not data. No stock photos, no people.

### 4.2 Color tokens (light theme, v2 — superseded by section 0.1)

Only shades of green and black plus neutral greys. No orange, red, blue or purple anywhere. Separate values by **lightness**, not hue.

```css
:root {
  /* Canvas and mesh gradient (visible through the glass) */
  --bg-0:        #F4F8F4;
  --mesh-mint:   #D9F0E0;
  --mesh-sage:   #BFE0C9;
  --mesh-lime:   #E6F4D7;

  /* Glass */
  --glass-fill:        rgba(255, 255, 255, .60);
  --glass-fill-strong: rgba(255, 255, 255, .82);   /* behind numbers and small text */
  --glass-border:      rgba(255, 255, 255, .70);
  --glass-shadow:      0 10px 40px rgba(15, 60, 35, .10);
  --glass-blur:        24px;

  /* Text and lines */
  --text-1: #0A0F0C;    /* primary, near-black */
  --text-2: #4E5B53;    /* secondary */
  --text-3: #7B887F;    /* non-essential labels only */
  --line:   rgba(10, 15, 12, .10);
  --ghost:  #9BA8A0;    /* inactive or comparison line */

  /* Mode accents (toggle, lines, chrome) */
  --raw:             #0B0F0D;   /* black */
  --harmonized:      #138A4B;   /* green, for fills, lines, chips */
  --harmonized-text: #0F6B3A;   /* darker green, for any green TEXT */

  /* Data ramp (map, globe cells, calendar), light to dark */
  --ramp-0: #F0F8F1;
  --ramp-1: #CFE9D5;
  --ramp-2: #98D3A9;
  --ramp-3: #52B26F;
  --ramp-4: #1F8A50;
  --ramp-5: #0F5A33;
  --ramp-6: #040A07;

  /* Source badges (no new hues) */
  --src-live:    #138A4B;   /* filled green */
  --src-cache:   #4E5B53;   /* grey */
  --src-fixture: #0B0F0D;   /* black outline */

  /* Eras (timeline bands) */
  --era-modis:   rgba(10, 15, 12, .04);
  --era-overlap: rgba(19, 138, 75, .10);
  --era-viirs:   rgba(10, 15, 12, .07);
}
```

Re-verify contrast with a checker once values are final. Use `--harmonized-text` for any green text; `--harmonized` is for fills, lines and chips with white text.

### 4.3 Dark theme — shipped as the default (see section 0.1)

The v3 remap is exactly this, and it is now the only theme: `--bg-0 #010c09`, glass fill `rgba(6, 30, 22, .55)`, `--text-1 #e7f8ee`, **raw is pale mint `#eafff3`** (black would vanish), harmonized is neon green `#2ee87d`. There is no light/dark switch; `prefers-reduced-transparency` swaps glass for an opaque fill instead.

### 4.4 Data color scale

Seven-step sequential ramp from pale green to near-black (section 4.2). Rules:

- The **same domain** is used in raw and harmonized views (domain fixed from the raw 99th percentile). Raw therefore looks darker and denser, and that gap is the point.
- Zero or no-detection cells are transparent, never the lowest ramp color.
- Because the palette is single-hue, **encode with lightness and always show values**: legend with tick labels, hover values, and a selected-cell outline. Do not rely on color alone.
- Mode accents (`--raw`, `--harmonized`) are for lines, toggle and chrome. Map, globe cells and calendar use the ramp.
- Check that the two darkest ramp steps stay distinguishable on glass. If not, lighten `--ramp-5`.

### 4.5 Typography (all self-hosted, no CDN)

| Role | Font | Notes |
|---|---|---|
| Display | **Fraunces** (variable, subset) | Main headline only |
| UI | **Inter** (variable) | Labels, body, controls |
| Numerals | **JetBrains Mono** | Metrics, tooltips, correlations, tabular figures |

Install via fontsource packages and bundle. Provide system fallback stacks. Scale: 12 / 14 / 16 / 20 / 28 / 44 / 72 px. Thin weights (300 to 400) for headings and large numbers, 500 for labels.

### 4.6 Glass, shape, depth

- **Glass recipe:** `background: var(--glass-fill); backdrop-filter: blur(var(--glass-blur)) saturate(1.1); border: 1px solid var(--glass-border); box-shadow: var(--glass-shadow); border-radius: 20px;`
- Small numbers and chart labels sit on `--glass-fill-strong`.
- Radii: 20 px tiles, 12 px inner cards, 999 px pills.
- **Glass budget:** blurred elements over the WebGL canvas are expensive. Keep at most about six blurred layers visible. Provide a quality tier (section 9.4) that lowers blur to 12 px or switches to an opaque fill (`rgba(255,255,255,.92)`) when frame rate drops, when `prefers-reduced-transparency` is set, or when the browser lacks `backdrop-filter`.
- Background: the page behind the globe uses a soft mesh gradient of the three mesh colors. Keep it low contrast so it never competes with the data.

### 4.7 Logo and iconography

- Mark: a circle (sun) with a single line that rises in a step, then smooths into a curve through it. Black on light, with a green dot at the step.
- Icons: line icons, 1.5 px stroke, self-hosted SVG sprite. No icon CDN.

### 4.8 Voice and copy

Short, factual, active.
- Good: "Harmonized: distinct cell-days per day." "Above the 95th percentile of the baseline for this date window."
- Avoid: "alarming," "dangerous," "the climate is drying." Report the measurement and the method.
- Sensor retirement note, always plain: "Suomi-NPP data ends 1 Nov 2026. MODIS is being retired. NOAA-20 and NOAA-21 continue."

---

## 5. Layout: bento grid over a globe

12-column grid, 16 px gaps, equal outer margins (24 px desktop), max content width 1440 px. Tiles have varied sizes; the **center is deliberately left open** so the globe stays visible.

### 5.1 Desktop tile map (1280 px and up)

| Tile | Columns | Rows | Notes |
|---|---|---|---|
| Hero text | 1 to 4 | 1 to 3 | Headline, subtext, "Explore" and "Watch story" |
| Ask | 1 to 4 | 4 to 5 | Question box and answer |
| (Globe window) | 5 to 8 | 1 to 5 | No tile. The globe shows through |
| What's notable | 9 to 12 | 1 to 2 | Three small clickable cards |
| Calendar | 9 to 12 | 3 to 5 | Compact heatmap |
| Timeline | 1 to 8 | 6 to 8 | Wide chart with era bands and brush |
| Validate (raw) | 9 to 10 | 6 to 7 | Large mono r value |
| Validate (harmonized) | 11 to 12 | 6 to 7 | Large mono r value |
| Status | 9 to 12 | 8 | Source badge, datasets, methods link |

### 5.2 Tile behavior

- **Focus-expand:** clicking a tile title (or an expand icon) animates it (FLIP, 320 ms) to a large centered panel; the globe blurs behind it. `Esc` returns. Calendar, Timeline, Validate and Ask each have a focus layout.
- **Collapse on globe interaction:** while the user drags the globe, tiles fade to 40% opacity and ignore pointer events so the view is unobstructed. They return 300 ms after interaction stops.
- **Feed view:** the same tiles become a single column of cards over a blurred pale backdrop (no globe), ordered Timeline, Calendar, Validate, Ask, Methods.

### 5.3 Responsive

| Breakpoint | Layout |
|---|---|
| >= 1280 | Bento over globe as above |
| 768 to 1279 | Globe in the top 45% of the viewport, tiles in a two-column grid below |
| < 768 | Globe as a rounded glass card at the top, single-column tiles, bottom tab bar, calendar in weekly buckets with sticky year column, controls in a bottom sheet |

The RAW | HARMONIZED toggle never collapses. On mobile it becomes a full-width segmented control under the title.

---

## 6. Global interaction model

### 6.1 The mode toggle (RAW | HARMONIZED)

- Segmented control with a sliding thumb. **RAW side fills black with white text; HARMONIZED side fills green with white text**, with a soft glow in the active color.
- Keyboard: `R` / `H` set the mode, `Space` flips it, `[` and `]` step the timeline range.
- On change, the globe, timeline, calendar and map animate together, driven by one `mode` state and a shared transition clock (700 ms, cubic in-out).
- Persist the last mode in `localStorage`; default to RAW on first load so the reveal still lands.

### 6.2 Cross-filtering

One shared `range` (date start/end), `focusDate`, `focusCell`/`focusBBox`, and the chip filters (`region`, `sensor`, `season`):
- Brushing the timeline updates the calendar highlight, the globe's accumulation window, and the validation window.
- Clicking a calendar cell sets `focusDate`. Clicking a globe cell sets `focusCell`. Shift-drag draws a bounding box.
- The chip row shows active filters; each chip clears with one click.

### 6.3 Filter chips

Small glass pills under the top bar: **Region**, **Sensor** (MODIS / VIIRS / both), **Date range**, **Season**. Opening a chip shows a small popover. Active chips are filled black with white text.

### 6.4 What's notable strip

Three small glass cards generated from API results (never typed in): "Largest sensor step", "Peak burning week", "Strongest anomaly". Clicking one sets `range`, `focusDate`, `focusCell` and flies the globe camera to the place (1.2 s ease). Values show placeholders until loaded.

### 6.5 Source badge and provenance

Every tile and chart footer has a small badge (`live`, `cache`, `fixture`) from the API's `source` field and an "i" button that opens the **Provenance drawer** with the raw JSON behind that figure (dataset ids, source URLs, parameters, build hash).

### 6.6 Story mode

A guided walkthrough for the 240 s and 30 s videos. Press **Story** (or `S`) to start; arrows step, `Esc` exits. Each step sets state (mode, range, focus, camera) and shows a one-line caption pinned bottom-left. A hidden timer overlay lets the presenter rehearse to time. Details in section 10.

---

## 7. Views and tiles

### 7.1 Hero tile

- Headline (Fraunces, light weight, up to 72 px): **Same fires. One honest record.**
- Sub: "Reconciling 1 km MODIS and 375 m VIIRS detections so sensor changes do not look like fire trends."
- Buttons: "Explore" (filled black), "Watch story" (outline).
- On first load the globe plays a slow 3 second approach from space to Bangladesh behind the hero. Skippable, and skipped under reduced motion.

### 7.2 Timeline tile

**Content:** daily counts (weekly smoothing toggle, off by default so gaps stay visible), raw and harmonized.
- Raw line in black, harmonized line in green. In RAW mode the harmonized line is a faint ghost (`--ghost`), and vice versa. **Lines are also labeled directly** at their right ends ("Raw", "Harmonized"), so they are not told apart by color alone.
- **Era bands** behind the chart from `/api/meta` windows: MODIS only, overlap, VIIRS era, each labeled. The overlap band is the validation set.
- **Transition marker:** vertical rule with a pulsing green dot and an annotation: "Sensor transition. Measured step: raw ×{r}, harmonized ×{h}" (values from the API).
- **Interactions:** hover crosshair with a tooltip (date, raw, harmonized, ratio, mono font); drag-brush to set `range`; double-click to reset; scroll-wheel zoom with a mini overview strip.
- **Gap days** are drawn as a break with a hatch pattern, never interpolated.
- "View as table" opens the data table drawer.

### 7.3 Calendar tile

- Year-by-day heatmap: rows are years (2003 to latest), columns are day-of-year (366), canvas-rendered. Row labels left, month ticks on top.
- Cells use the green-to-black ramp. Mode changes recolor with a column-wise stagger (about 6 ms per column).
- **Interactions:** hover highlights the cell plus a faint row/column cross and shows a tooltip; click sets `focusDate` (selected cell gets a white-and-black double outline); click-drag on a row selects a season window; click a row label to jump the timeline to that year.
- **Baseline overlay (P1):** a "Show baseline band" switch draws a p5 to p95 ribbon for the focused row.
- **Mobile:** weekly buckets, horizontal scroll with a sticky year column.

### 7.4 Globe (Three.js): the spatial view

See section 9 for technical detail. Behavior:

- Centered on Bangladesh, pale green-white land, soft lighting, slow auto-rotation when idle. Drag to rotate, scroll or pinch to zoom, double-click a place to fly to it.
- **RAW:** small and large near-black points, densely clustered, sized by sensor (larger for 1 km MODIS pixels, smaller for 375 m VIIRS).
- **HARMONIZED:** points merge into square extruded 5.5 km cells (height and color by cell-day count, using the ramp). Cell size comes from `/api/meta`.
- **Time play:** scrubber and play button animate the accumulation window day-by-day or week-by-week with a short fading trail.
- **Swipe compare:** a draggable vertical divider. Left of it raw points, right of it harmonized cells, same camera and ramp. Dragging reveals where raw inflates counts.
- **Hover card (glass):** cell id, raw detections, cell-days, `sensors_agreeing`, peak FRP, date range (mono). Click sets `focusCell`; shift-drag sets a bounding box.
- **Layers button:** land tint, cell outlines, optional GIBS-derived texture (self-hosted), optional POWER wind arrows (P2).
- **Fallback:** if WebGL is unavailable or the quality tier is "low", show a flat 2D map (MapLibre with PMTiles, or a canvas) with the same interactions.

### 7.5 Validate tiles

Purpose: prove it worked, in two numbers.
- Two scatter plots over the **overlap window**, in two tiles (or side by side when expanded):
  - Raw MODIS vs raw VIIRS daily counts (black points).
  - Harmonized MODIS vs harmonized VIIRS (green points).
  - 1:1 dashed reference line in `--ghost`.
- Large mono Pearson r under each (Spearman secondary). Count-up over 800 ms on first view.
- A delta chip between them shows the change (computed by the API, not the UI).
- The overlap window dates and n are always visible. If the improvement is small or negative, the UI shows it the same way, with no celebratory styling that depends on the sign.
- "Sensitivity" link opens a small table of alternate VIIRS-confidence mappings and their effect.

### 7.6 Ask tile: "Is this unusual for this place and time of year?"

- Controls: date (pre-filled from `focusDate`), area (from `focusCell`/`focusBBox` or a region picker), window (default +/- 7 days).
- Quick prompts as chips: "Today in this cell", "Peak week last year", "Whole region, this date".
- **Answer (templated, not model-written):**
  - Horizontal distribution strip with the baseline p5 to p95 band, median tick, and a marker for the selected value (animates in from the left).
  - Sentence: "{value} cell-days on {date} is at the {percentile}th percentile for {area} over {years} years (window {w} days)."
  - Qualifier chip from fixed thresholds documented in Methods: below p25, typical, above p75, above p95.
- Footer: baseline window, n samples, source badge, provenance "i".
- Optional agent layer (P2): a free-text box that routes to the same tools. If no agent or LLM is available, hide it.

### 7.7 Methods drawer

Right-side frosted-glass drawer (480 px), opened from the top bar or any "i". Contents, all read from `/api/meta` and `/api/methods`:
- Cell size, grid reference latitude, day basis (local vs UTC).
- Confidence filter and the VIIRS class mapping table.
- Collapse rule diagram: three tiny panels showing 1 km and 375 m detections inside one 5.5 km cell collapsing to one cell-day.
- Validation window and correlations.
- Known limitation: more overpasses per day as platforms change are not fully removed by the collapse.
- Sensor retirement note and data windows per platform.
- Dataset list with ids, verbatim FIRMS product names, URLs, and licenses.

### 7.8 "How the collapse works" explainer (delight feature)

A glass card (in Methods and linked from the hero):
- A square cell with a few large hollow circles (1 km MODIS pixels) and many small filled dots (375 m VIIRS pixels), labeled "Illustration".
- A **cell-size slider** (3 to 11 km, snapped to precomputed sizes if available). The grid redraws and the counters ("raw detections" vs "cell-days") update live.
- Press "Collapse": dots fly into the cell center and merge. The raw counter drops to the cell-day count. It makes the method graspable in five seconds, and mirrors what the globe does at scale.

---

## 8. State model (frontend)

```ts
type Mode = 'raw' | 'harmonized';
interface AppState {
  mode: Mode;
  view: 'globe' | 'feed';
  range: [string, string];                 // ISO dates
  focusDate: string | null;
  focusCell: { x: number; y: number } | null;
  focusBBox: [number, number, number, number] | null;
  filters: { region: string; sensor: 'both' | 'modis' | 'viirs'; season: string | null };
  expandedTile: string | null;             // focus-expand
  storyStep: number | null;
  theme: 'light' | 'dark';
  quality: 'high' | 'medium' | 'low';
  source: 'live' | 'cache' | 'fixture' | 'mixed';
  reducedMotion: boolean;
}
```

Data layer: fetch both modes for the series, calendar, and cells at load (they are small and precomputed), so the toggle is a client-side tween with no spinner. Lazy-load the globe chunk, the explainer, and fallback map code.

---

## 9. Three.js globe: technical design

### 9.1 Scene

- `three` from npm, tree-shaken, in a lazy chunk. Orbit-style camera controls with clamped zoom and polar angle; slow auto-rotate after 4 s idle; pause on interaction and when the tab is hidden.
- **Land:** a low-poly globe mesh with a self-hosted, compressed texture (WebP or KTX2), tinted pale green-white. No external texture or tile requests. Region detail near Bangladesh comes from a pre-baked heightless overlay (borders and rivers as thin lines from local GeoJSON).
- **Lighting:** one soft directional light plus hemisphere light; subtle fog and a vignette (CSS) instead of post-processing depth of field.
- **Coordinates:** convert lat/lon to the sphere with one shared helper in `src/viz/geo.ts`. Cells are lat/lon rectangles draped on the sphere (tiny at this scale, so a flat quad per cell is acceptable).

### 9.2 Data layers

| Layer | Implementation | Notes |
|---|---|---|
| Raw detections | `THREE.Points` or `InstancedMesh` with a custom shader | Per-point attributes: position, size (sensor), alpha. Cap on-screen points with display-time decimation. **Never decimate for any statistic** |
| Harmonized cells | `InstancedMesh` of boxes | Per-instance attributes: cell center, height, ramp value |
| Morph | One uniform `uMix` (0 raw to 1 harmonized) | Points lerp toward their cell center and fade as cells scale up from 0 to full height |
| Swipe compare | Shader uniform `uSplit` (screen-space x) | Left shows raw layer, right shows harmonized layer; no second render pass needed |
| Selection | Outline on the selected cell | |

### 9.3 Picking and interaction

- Do not raycast thousands of instances. Intersect the ray with the globe sphere, convert the hit to lat/lon, and look up the cell id from the grid index (O(1)).
- Hover and click use that lookup. Bounding-box draw uses two such corner lookups.
- Camera "fly to" for the What's notable cards uses an eased interpolation of lat/lon/zoom (1.2 s).

### 9.4 Performance and quality tiers

- Target 60 fps on a mid-range laptop; 30 fps acceptable on phones.
- **On-demand rendering:** render only when something changes (controls, tween, play), not every frame while idle.
- Pixel ratio capped at 2 (1.5 on `medium`, 1 on `low`).
- Auto quality: measure frame time over the first 2 seconds and during interaction. `high`: full glass blur, all layers. `medium`: blur 12 px, no trail. `low`: opaque tile fills, flat 2D fallback.
- Dispose geometries, materials, textures on unmount. Keep the point buffer in typed arrays, and update attributes in place.

### 9.4.1 Accessibility for the globe

The globe is decorative-plus-interactive and not the only way to reach information. Every value shown on it is available in the tiles, the data table, and the Feed view. Provide "Reset view", a "Jump to a place" list, keyboard rotation with arrow keys when the globe has focus, and an `aria-label` summarizing the current view.

### 9.5 Offline

All globe assets (textures, GeoJSON, shaders, fonts) are bundled or served from `public/` and precached by the service worker. No texture or tile CDN. The cold-start offline test must include the globe.

---

## 10. Motion

| Interaction | Duration / easing | Notes |
|---|---|---|
| Mode toggle morph | 700 ms, cubic in-out | Globe `uMix` tween; timeline paths tween; calendar recolor with column stagger; map cells tween |
| Tile focus-expand | 320 ms, ease-out (FLIP) | Globe blurs behind |
| Tiles on globe drag | 150 ms fade to 40% | Restore 300 ms after release |
| Number count-up | 800 ms, ease-out | Validation values, first view only |
| Drawer | 240 ms, ease-out | Slide plus fade |
| Hover tooltip | 80 ms | 120 ms grace on hide |
| Globe fly-to | 1200 ms, ease-in-out | Used by What's notable and Story |
| Story step | 500 ms between state changes | Captions fade 200 ms |
| Map play | 1 day per 120 ms (adjustable) | Trail fades over 5 frames |

**Reduced motion:** transitions drop to under 100 ms crossfades; auto-rotate, the intro approach, count-ups and trails are off; Story advances only on user input.

---

## 11. Demo choreography (240 s local judging)

All steps are Story presets, so the demo is repeatable and the offline recording is identical to the live run.

| Time | Scene | UI state | Say (concept) |
|---|---|---|---|
| 0:00 to 0:20 | The step | RAW, globe approach, timeline with transition marker pulsing | The finer sensor sees more. The count jumps. The world did not. |
| 0:20 to 0:50 | The fix | Collapse explainer, cell-size slider | One cell-day counts once, no matter how many pixels fire. |
| 0:50 to 1:30 | **The reveal** | Toggle to HARMONIZED, 700 ms morph on globe and charts | Black points become green cells. The step disappears. The seasonal signal remains. |
| 1:30 to 2:10 | The proof | Validate tiles expanded | Measured correlation on the overlap period, before and after. |
| 2:10 to 2:50 | Where and when | Globe swipe compare, calendar | Same fires, honest record, across space and time. |
| 2:50 to 3:20 | The question | Ask tile, click a calendar cell | Percentile against the seasonal baseline, with the window shown. |
| 3:20 to 3:45 | Trust | Provenance drawer, Methods, **wifi off, cache/fixture badge** | Every number traces to a dataset and URL. It runs offline, globe included. |
| 3:45 to 4:00 | Close | Status tile, datasets | Name FIRMS products on camera. Why now: Suomi-NPP ends 1 Nov 2026, MODIS retiring. |

**30 s global cut:** 0 to 5 s problem (raw step), 5 to 15 s toggle reveal on the globe, 15 to 22 s validation numbers, 22 to 27 s FIRMS named on screen plus impact line, 27 to 30 s team. English subtitles baked in.

Rules: name each NASA dataset out loud when it first appears; show the offline badge at least once; no minors' names, voices or likenesses in any capture.

---

## 12. Offline and resilience UX

- Service worker (Workbox): precache the app shell and globe assets, cache-first for tiles, stale-while-revalidate for data, versioned caches.
- Self-host everything: fonts, icons, textures, libraries. A single CDN link breaks the first offline load.
- **Source badge** per tile: `live`, `cache`, `fixture`, plus "data last updated". A calm "Offline: showing cached data" pill appears in the top bar, never an error banner.
- `navigator.storage.persist()` requested after first load.
- Optional "Download for offline" screen (P2): region and layers, size estimate, progress, last-updated per layer.
- Failure states: a failed request shows the cached value with its timestamp, never an estimate. If the agent layer is unavailable, hide its UI.

---

## 13. Accessibility

- WCAG 2.2 AA target: text contrast measured against the **worst-case backdrop** (a glass tile over dark clustered points), 44 px touch targets on mobile, visible 2 px focus ring in dark green, skip link.
- Every chart has a text summary (aria-label), a "View as table" alternative, and keyboard navigation (arrow keys move the crosshair or selected cell).
- Do not rely on color alone: direct line labels, values on hover/focus, hatch patterns for gaps, outlines for selection, legend tick values on the single-hue ramp.
- The toggle is a proper radio group labeled "Raw counts" and "Harmonized counts".
- Respect `prefers-reduced-motion`, `prefers-reduced-transparency`, and `prefers-color-scheme` (light default).
- English labels throughout. If Bangla summaries are added, generate them from the same templates and keep numerals consistent.

---

## 14. Frontend architecture (maps onto the repo)

Because `web/` could not be inspected, this is a recommendation. Keep any existing scaffold if present.

```
web/
  index.html
  vite.config.ts
  src/
    main.tsx
    app/            App shell, Story/Explore modes, providers
    state/          store.ts (Zustand), URL sync, persisted prefs
    api/            client.ts (talks only to /api, never NASA), types.ts
    components/
      TopBar/ ModeToggle/ ViewSwitch/ FilterChips/ SourceBadge/ GlassTile/ BentoGrid/
      Drawer/ Tooltip/ MetricCard/ ThemeSwitch/ NotableStrip/
    views/
      Hero/ Timeline/ Calendar/ Globe/ Validate/ Ask/ Methods/ Provenance/ Explainer/ Feed/
    globe/          scene.ts, layers.ts, shaders/, picking.ts, quality.ts, fallback2d.ts
    viz/            scales.ts (shared ramp and domain), geo.ts, canvas helpers, d3 utils
    story/          steps.ts (state presets and captions), Overlay.tsx
    styles/         tokens.css, glass.css, base.css
    sw/             service worker (Workbox)
  public/
    fonts/ sprites.svg textures/ geo/ demo_series.json pmtiles/
```

- **Stack:** Vite + TypeScript. React with a small store (Zustand). D3 for scales and axes. Canvas for the calendar. **Three.js** for the globe (lazy chunk). MapLibre + PMTiles only for the 2D fallback. CSS variables for tokens.
- **API contract:** the endpoints from the TRD (`/api/meta`, `/series`, `/calendar`, `/cells`, `/validation`, `/anomaly`, `/methods`, `/provenance/{id}`). Every response carries `source`, `dataset_ids`, `source_urls`.
- **Build output:** static files served by FastAPI and also usable from a plain file server for the offline bundle.
- **Budgets:** initial JS under about 300 KB gzipped before the lazy globe chunk; toggle response under 200 ms; first usable view under 2 s from local cache.

---

## 15. Component inventory

| Component | Key props / behavior |
|---|---|
| `BentoGrid` / `GlassTile` | grid areas, focus-expand, fade-on-globe-drag, glass quality tier |
| `ModeToggle` | `mode`, black/green fills, keyboard shortcuts, announces change |
| `ViewSwitch` | Globe / Feed |
| `FilterChips` | region, sensor, date range, season; popovers; clear actions |
| `NotableStrip` | API-driven cards; click sets state and flies camera |
| `GlobeScene` | layers, `uMix` morph, `uSplit` compare, picking, quality tier, 2D fallback |
| `TimelineChart` | series, eras, transition marker, brush, crosshair, table fallback |
| `CalendarHeatmap` | matrix, ramp, selection, hover cross, baseline ribbon |
| `ScatterPair` | overlap series, 1:1 line, r values, sensitivity link |
| `AnomalyCard` | percentile object, distribution strip, templated sentence |
| `CollapseExplainer` | cell-size slider, collapse animation, "Illustration" label |
| `SourceBadge` | `source`, `updatedAt`, opens provenance |
| `MetricCard` | label, value (mono), unit, delta, source, "i" |
| `Drawer` | `side`, `title`, focus trap, Esc to close |
| `StoryOverlay` | steps, caption, timer, keyboard control |
| `ThemeSwitch` | light default, optional dark |

---

## 16. Content and asset checklist

- [ ] Logo mark and favicon (SVG)
- [ ] Self-hosted fonts (Fraunces, Inter, JetBrains Mono), subsetted
- [ ] Icon sprite
- [ ] Globe texture (compressed), borders/rivers GeoJSON, cell geometry
- [ ] 2D fallback basemap (PMTiles) for the region
- [ ] Precomputed JSON: series (both modes), calendar (both modes), validation, baseline, meta
- [ ] Demo fixtures for the full offline run
- [ ] Footer credits: NASA FIRMS with product names verbatim, every library and asset (including Three.js), Apache-2.0 notice
- [ ] `docs/AI_USE.md` entry for any AI-assisted design or code (including Google Stitch mockups)
- [ ] Alt text and table fallbacks for every chart
- [ ] No images, names, or voices of anyone under 18

---

## 17. Acceptance criteria (design)

1. Toggling raw/harmonized animates the globe, timeline, calendar and map together in about 700 ms with no network request.
2. The same color domain is used in both modes, and a legend with tick values states it.
3. The palette uses only shades of green and black plus neutral greys. No other hues appear in data or chrome.
4. Every displayed figure has a source badge and a working provenance drawer.
5. The full demo, including the globe, runs with `OFFLINE=1` and wifi off from a cold start, with no console errors and no external requests.
6. No metric appears that was not returned by the API.
7. Keyboard-only users can toggle the mode, move through all tiles, open and close drawers, and reach every globe value through a tile or the data table.
8. Reduced-motion and reduced-transparency users get a complete, non-animated, opaque-tile experience.
9. If WebGL is unavailable, the 2D fallback offers the same interactions.
10. The Story mode reproduces the 240 s and 30 s scripts without manual setup.
11. Layout works at 360 px width (stacked tiles, bottom tab bar, calendar weekly mode).
12. Text on glass meets AA contrast against the worst-case backdrop.
13. Lighthouse PWA and accessibility audits pass at agreed thresholds.

---

## 18. Build order (UI)

Aligned to the 48-hour plan and the PRD's cut order.

1. Tokens, glass tiles, bento shell, top bar, `ModeToggle`, API client with fixtures.
2. `TimelineChart` with both series and era bands, then the morph. **Core, finish first.**
3. `CalendarHeatmap` and a simple 2D map, wired to the toggle by the 15:00 round.
4. `Validate` tiles and the Methods drawer.
5. **Three.js globe** with raw points, harmonized cells, and the `uMix` morph (fall back to the 2D map if behind).
6. `Ask` tile and the baseline overlay.
7. Story mode, collapse explainer, swipe compare, What's notable, polish.
8. Offline hardening and a full dry run with wifi off.

**If behind, cut in this order:** globe extras (trail, swipe compare, layers), then the explainer animation, then the globe itself (keep the 2D map), then the anomaly UI. Keep the toggle, timeline, validation numbers and the offline badge to the end.

---

## 19. Open design questions

1. Final stack for `web/`: confirm Vite + React + TypeScript, or keep what is already scaffolded.
2. Ship the dark theme, or defer it?
3. Is the globe worth its cost versus a flat map, given the 48-hour limit? (Recommendation: build the flat map first, add the globe once the toggle and charts are done.)
4. Bangla support in the UI: labels only, or full copy?
5. Region default: Bangladesh only, or a South Asia view with a selector?
6. Which grid sizes are precomputed? A single size means the explainer slider is illustrative only.
7. Does the green-and-black palette leave enough contrast between the two darkest ramp steps on glass? Check on real data before locking the ramp.