# DESIGN.md — Icarus Design System

**Version:** 1.0 · **Date:** 05 October 2026 · **Status:** Baseline
**Direction:** Morrow Admin (calm, airy, one loud accent), adapted to a scientific
data app.
**Tagline:** *Same fires. One honest record.*

---

## 0. Identity and Design Principles

Icarus shows one measurement honestly: MODIS and VIIRS fire detections, raw and
harmonized, side by side. The interface must make the artifact visible and the
correction obvious, without alarm.

1. **Calm and airy.** Soft gray canvas, white floating surfaces, generous
   whitespace. Data is the loudest thing on screen.
2. **One loud accent.** A single electric lime (`--accent`) marks the brand,
   the active mode, and positive state. It is never used for large fills behind
   data, and never as a substitute for a semantic colour.
3. **Quiet typography.** Near-black text, muted gray metadata, tight bold
   headings, tabular numerals for every count.
4. **Keyboard-first.** Every primary action has a shortcut and a visible
   alternative.
5. **Two themes, one truth.** Light and dark ship together; dark is the default
   because the globe reads on dark ground. Tokens, not hardcoded colours.
6. **Honest encodings.** Coverage, modelled values, and missing data are always
   visually distinct from zero. Colour is never the only channel.

---

## 1. Color Tokens

### 1.1 Base (light)

| Token | Value | Use |
|-------|-------|-----|
| `--bg` | `#E7E8EE` | Page canvas |
| `--surface` | `#FFFFFF` | Cards, rail |
| `--surface-hover` | `#F3F4F7` | Nav hover/active, inputs |
| `--border` | `#ECEDF1` | Dividers, hairlines, gridlines |
| `--text` | `#111114` | Headings, names, amounts |
| `--text-muted` | `#8B8E98` | Subtitles, labels, hints |
| `--text-info` | `#6F727C` | Muted text that carries real information (AA) |
| `--accent` | `#C4F43A` | Brand tile, active bar, positive state |
| `--accent-ink` | `#111114` | Text/icons on accent |
| `--status-neutral` | `#9A9DA6` | Neutral state dots |
| `--status-positive` | `#A6E02B` | Positive / full coverage |

### 1.2 Base (dark)

| Token | Value |
|-------|-------|
| `--bg` | `#0E0F12` |
| `--surface` | `#17181C` |
| `--surface-hover` | `#202126` |
| `--border` | `#26272D` |
| `--text` | `#F4F4F6` |
| `--text-muted` | `#8B8E98` |
| `--accent` | `#C4F43A` (unchanged) |
| `--accent-ink` | `#111114` |

### 1.3 Data encodings

These are semantic and never borrowed by the UI chrome.

| Token | Light | Dark | Use |
|-------|-------|------|-----|
| `--series-raw` | `#C2402B` | `#FF7A66` | Raw detection series |
| `--series-harmonized` | `#3F7A1F` | `#A6E02B` | Harmonized series |
| `--cov-full` | `#A6E02B` | `#A6E02B` | Full coverage |
| `--cov-partial` | `#E0A62B` | `#F0C36B` | Partial coverage |
| `--cov-low` | `#E0684B` | `#FF9A7A` | Low coverage |
| `--cov-missing` | hatch on `--border` | hatch on `--border` | No observation |

**Activity ramp** (density, sequential, 5 stops): light
`#F3F4F7 → #F0C36B → #E0684B → #B3452F → #111114`; dark
`#202126 → #7A5A2B → #E0684B → #FFB199 → #F4F4F6`.

**Anomaly palette** (categorical, deliberately unlike activity):
`--anom-elevated` `#7C5CFF` / `#A78BFA`; `--anom-extreme` `#4B2ECC` / `#C4B5FD`;
`--anom-normal` uses `--text-muted`. Activity and anomaly palettes are never
shown in the same view using the same hues.

---

## 2. Typography

- **Family:** geometric grotesk — `Inter`, `Geist`, or `Satoshi`, with
  `system-ui, sans-serif` fallback. Self-hosted; no CDN.
- **Numerals:** tabular for all counts, amounts, and axis labels.

| Role | Size / weight | Notes |
|------|---------------|-------|
| Page title | 36px / 700 | letter-spacing −0.02em |
| Page subtitle | 13px / 400 | `--text-muted` |
| Section label | 11px / 500 | `--text-muted`, sentence case |
| Card title | 13px / 600 | |
| Row primary | 14px / 600 | e.g. a period label |
| Row secondary | 12px / 400 | `--text-muted` |
| Amount / count | 14px / 700 | right-aligned, tabular |
| Chart axis | 11px / 500 | `--text-muted` |
| Nav label | 14px / 500 | |
| Hint text | 12px / 400 | `--text-muted` |

Line length under 80 characters for prose. Sentence case; no all-caps labels.

---

## 3. Spacing, Radius, Elevation

- **Base unit:** 4px. Steps: 8, 12, 16, 20, 24, 36.
- **Content padding:** 36px from the rail, 32px top.
- **Radius:** card 20px (`--radius-card`), control 12px
  (`--radius-control`), badges full pill.
- **Elevation:** almost flat. White on gray with at most
  `0 1px 2px rgba(17,17,20,.04)`. No heavy shadows.

---

## 4. Layout and App Shell

```
┌──────────┬────────────────────────────────┐
│ Rail     │  Page title + subtitle          │
│ 244px    │  [ Raw | Harmonized ]  mode     │
│ fixed    │  ┌──────────────────────────┐  │
│          │  │ Card: hero series chart  │  │
│          │  └──────────────────────────┘  │
│          │  Calendar · Map · Anomaly       │
│          │  Keyboard hint line             │
└──────────┴────────────────────────────────┘
```

- Floating rail, ~244px, inset ~4px from the viewport, radius 20px.
- Main content is a single column, card max-width ~720px, left-aligned.
- On narrow viewports the rail collapses to icon-only (see §7).

**Screens:** Overview; Calendar; Map; Anomalies; Critical period; Validation;
Methods; Offline.

---

## 5. Components

### 5.1 Rail

1. **Brand block:** 28px rounded-square lime tile with an "i" glyph, "Icarus"
   (15px/700), subtitle "MODIS + VIIRS" (11px muted), collapse button right.
2. **Search:** full-width field, `--surface-hover`, radius 12px, ~40px tall,
   `Ctrl K` kbd chip.
3. **Primary control — mode:** segmented `[ Raw | Harmonized ]`, full width,
   accent underline on the active segment.
4. **Nav group "Views":** Overview, Calendar, Map, Anomalies (badge count),
   Critical period, Validation.
5. **Nav group "Reference":** Methods, Datasets, Offline.
6. **Footer:** theme toggle row, then a status card (source badge, parameter
   hash, last-updated).

### 5.2 Nav item

Height ~40px, padding 0 12px, gap 14px, icon 18px, radius 12px. Default
transparent; hover/active uses `--surface-hover` with a short lime vertical bar
on the left edge. Counts are pills: lime fill + dark text for attention, neutral
gray text for a plain count.

### 5.3 Card

`--surface`, 20px radius, no visible border. Header row padding 16px 20px with a
hairline divider below.

### 5.4 Row

Height ~60px, padding 0 20px, bottom hairline (none on the last). Left: label
over description. Right: status chip, then a right-aligned tabular value.

### 5.5 Source badge

Pill, 12px/600. Distinct treatment per source so provenance is scannable:

| Source | Treatment |
|--------|-----------|
| `MODIS` | neutral fill, `--text` ink |
| `BRIDGE` | outline only |
| `VIIRS_CAL` | accent-tinted fill, `--accent-ink` |
| `NONE` | hatched fill |
| `mock` / `fixture` | hatched, with the word spelled out — never evidence |

### 5.6 Coverage chip

6px dot + 12px label in `--text-info`: **Full**, **Partial**, **Low**,
**Missing**. Missing is hatched, not greyed to look like zero.

### 5.7 Status chip (anomaly)

Dot + label: **Normal**, **Elevated**, **Extreme**, **Not scored**. Uses the
anomaly palette, never the activity ramp.

### 5.8 Toggle switch

~36×20px pill. Off: `--border` track, white knob. On: accent track.

### 5.9 Calendar heatmap

Rows = years, columns = 46 eight-day bins. Cell fill from the activity ramp.
Low-coverage bins are diagonal-hatched over the fill. Modelled bins carry a thin
outline. Tooltip states value, units, coverage, and source.

### 5.10 Cell map

Cells as polygons shaded by the active mode. No basemap by default (a tile
source would be a third-party request offline); PMTiles when bundled. Legend
shows units and the ramp.

### 5.11 Panels

- **Anomaly box:** enters a date/area, returns percentile and baseline window.
- **Critical-period panel:** onset, peak, end bins, window mass.
- **Validation card:** raw and harmonized correlations from the overlap period.
- **Provenance drawer:** the JSON behind the current view, dataset names,
  versions, retrieval dates, parameter hash.

### 5.12 Keyboard hint

One line under the card, 12px muted:
"Press **R/H** to switch modes, **T** for theme, **?** for all shortcuts."

### 5.13 Mock banner

Persistent strip while mock or fixture data is shown; states the source and that
no number from it is evidence.

---

## 6. Data-Visualization Encoding Rules

1. Activity and anomaly never share a palette in the same view.
2. Low-coverage bins are hatched and labelled — never coloured as zero.
3. Modelled bins carry a thin outline; tooltip reads "modelled (VIIRS
   calibrated)" or "modelled (bridge)".
4. Every chart shows units and bin length (8 days).
5. The accent does not fill data marks; it marks state (active, positive).
6. Colour is never the only channel: pair with a label, shape, or hatch.

---

## 7. Interaction and Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + B` | Collapse / expand the rail |
| `Ctrl/Cmd + K` | Focus search |
| `R` / `H` | Switch mode to Raw / Harmonized |
| `1`–`8` | Jump to view by position |
| `←` / `→` | Move the selected date/bin |
| `T` | Toggle light/dark theme |
| `P` | Open the provenance drawer |
| `Esc` | Close the drawer |
| `?` | Show the shortcut list |

This is the single keyboard map (`docs/FLOWS.md` refers here).

- Hover transitions 120–150ms ease-out; respect `prefers-reduced-motion`.
- Changing a view updates the hash (`#calendar`) and swaps the main column.
- Focus order: rail → mode control → main content → overlay.
- Focus ring: 2px `--accent` outline with 2px offset; focus is always visible.
- Every shortcut has a visible button or menu equivalent.

---

## 8. Iconography

Outline icons, 1.5px stroke, rounded caps and joins, 18px. Lucide or Phosphor
"regular" matches well. Icons never carry meaning alone — always paired with a
label or an accessible name.

---

## 9. CSS Starter

```css
:root {
  --bg: #E7E8EE;
  --surface: #FFFFFF;
  --surface-hover: #F3F4F7;
  --border: #ECEDF1;
  --text: #111114;
  --text-muted: #8B8E98;
  --text-info: #6F727C;
  --accent: #C4F43A;
  --accent-ink: #111114;
  --status-neutral: #9A9DA6;
  --status-positive: #A6E02B;
  --series-raw: #C2402B;
  --series-harmonized: #3F7A1F;
  --radius-card: 20px;
  --radius-control: 12px;
  --font: "Inter", "Geist", system-ui, sans-serif;
}
:root[data-theme="dark"] {
  --bg: #0E0F12;
  --surface: #17181C;
  --surface-hover: #202126;
  --border: #26272D;
  --text: #F4F4F6;
  --series-raw: #FF7A66;
  --series-harmonized: #A6E02B;
}
body { background: var(--bg); color: var(--text); font-family: var(--font); }
.card { background: var(--surface); border-radius: var(--radius-card);
        box-shadow: 0 1px 2px rgba(17,17,20,.04); }
.row { display: flex; align-items: center; height: 60px; padding: 0 20px;
       border-bottom: 1px solid var(--border); }
.badge { font: 600 12px var(--font); padding: 2px 8px; border-radius: 999px; }
.badge--accent { background: var(--accent); color: var(--accent-ink); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
```

---

## 10. Accessibility Notes

- Target **WCAG 2.2 AA**. `--text-muted` on white is ~3.5:1 — secondary text
  only; use `--text-info` (`#6F727C`) when the text carries information.
- Verify every data-encoding colour for contrast in both themes; the activity
  ramp's extremes must remain distinguishable under deuteranopia.
- Status never relies on dot colour alone; the label stays visible.
- Charts need a text readout path (table or accessible summary).
- Every shortcut has a visible alternative; focus is always visible.
- Respect `prefers-reduced-motion`; swap state instantly instead of animating.
- The mock/fixture banner is announced to assistive tech, not just shown.

---

## 11. Voice and Content

- Short, factual, active. Report the measurement and the method; never alarm.
- Plain labels the public understands: "Raw detections", "Harmonized
  cell-days" — not internal names.
- Cite every dataset with its product name and URL; no unattributed number.
- Say what is modelled and what is measured, every time.
