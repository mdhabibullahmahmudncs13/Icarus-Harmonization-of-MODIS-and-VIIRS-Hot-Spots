# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Vite + React + TypeScript (strict), d3 (scale/shape/array) for charts, zod as
the API contract, Vitest + Playwright for tests. Static build; no server
required. Chosen during the F1 scaffold session.

## Users

- NASA Space Apps judges (primary): 30–240 s demo; must grasp the problem and
  the fix almost immediately.
- Responders / analysts: "Is this burning activity unusual for this place and
  time of year?"
- Researchers: verify method, parameters, and validation correlations.

## Product Purpose

Reconcile 1 km MODIS and 375 m VIIRS (NOAA-20, NOAA-21) hotspot detections
from NASA FIRMS so the post-2012 count series is not inflated by the finer
sensor. Success: on one toggle the false 2012 step visibly collapses, the demo
runs offline from a cold start, and every displayed number traces back to its
source.

## Positioning

One global Raw | Harmonized toggle over the same record: raw = detections per
day, harmonized = distinct 5.5 km cell-days per day. The mechanism is shown,
not asserted — and mock data is never presented as evidence.

## Operating Context

- Demo and judging environments, frequently offline (OFFLINE=1, wifi off,
  airplane mode).
- The backend (later phases) serves from local cache/fixtures; the frontend
  never calls NASA directly.
- AI-use disclosure (docs/AI_USE.md) and an Apache-2.0 public repo are
  submission requirements.

## Capabilities and Constraints

- Shipped today: mock data source, contract-validated payloads, daily series
  2003–2026, raw/harmonized toggle, provenance drawer, source badge, persistent
  mock banner. Calendar, map, validation card, methods panel and story mode
  (F3+) are not built yet.
- Offline-first; zero third-party requests; self-hosted fonts and assets;
  deterministic science only in src/compute; the frontend displays numbers and
  never computes statistics.
- Defaults: 5.5 km grid (configurable), confidence ≥ 50, VIIRS l/n/h mapped
  to 25/60/90.
- Open decision: dark theme deferred (P2 in docs/DESIGN.md).

## Brand Commitments

- Name: "Icarus". Tagline: "Same fires. One honest record." (docs/DESIGN.md).
- Voice: short, factual, active; report the measurement and the method, never
  alarm.
- FIRMS sensor product names used verbatim; every dataset cited with an id and
  a URL.

## Evidence on Hand

- Committed mock fixtures: web/public/mock/*.json (synthetic, labelled
  meta.source="mock").
- Docs: PRD, TRD, Implementation plan, DESIGN.md, DATA.md, METHODS.md.
- Absence: no real NASA FIRMS data has been downloaded yet. Future work must
  not fabricate real-data claims.

## Product Principles

1. The killer demo comes first: the toggle is global and everything responds
   to it.
2. Mock data is never evidence.
3. Deterministic statistics live in tested code, never in the UI or an LLM.
4. Offline from day one: one CDN link breaks the cold start.
5. Every number carries its source.

## Accessibility & Inclusion

- WCAG 2.2 AA target: visible focus, keyboard-operable toggle, reduced-motion
  support, contrast verified against worst-case backdrops; every chart needs a
  text readout path.
