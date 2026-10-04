# AI Use

A transparent record of how AI tools contributed to this repository.

## Tools

<!-- List every AI tool you used here. Examples: GitHub Copilot, Claude (claude.ai / Claude Code / puku-cli), ChatGPT, Cursor, etc. -->

- [Graphify](https://github.com/Graphify-Labs/graphify) (PyPI package
  [`graphifyy`](https://pypi.org/project/graphifyy/), Apache-2.0). Installed as a
  project-scoped Agent Skill at `.agents/skills/graphify/`. Code is indexed locally
  with tree-sitter (no LLM, no network); only the optional semantic pass over
  docs/media would call a backend, and no backend is configured in this repo.
- [Reticle](https://github.com/reticlehq/reticle) skill pack — 19 skills installed
  from `npx skills add reticlehq/reticle --agent universal --skill '*'` into
  `.agents/skills/`, with `skills-lock.json` recording source and hashes. All
  Markdown, no code. Reticle's own [LICENSE](https://github.com/reticlehq/reticle/blob/main/LICENSE)
  is a per-package model (Apache-2.0 for SDK packages, FSL-1.1 for the server)
  and does not name the `skills/` directory; redistribution is assumed to be
  permitted because their README advertises this exact `npx skills add` install
  and their CONTRIBUTING calls `SKILL.md` a public product surface.
- [Taste-Skill](https://github.com/leonxlnx/taste-skill) (MIT) — 13 design/UI
  skills installed from `npx skills add leonxlnx/taste-skill --agent universal
  --skill '*'` into `.agents/skills/`, tracked in `skills-lock.json`. Markdown
  only; no build step, no runtime dependency.
- [img2threejs](https://github.com/img2threejs/img2threejs) (Apache-2.0) — 1
  skill, but ships an executable pipeline: 226 Python files under `forge/` plus
  `.sh`/`.mjs` helpers (5.5M). Scanned before use: no credentials, no
  `eval`/`exec`/`rm -rf`. Outbound network is MediaPipe weights from
  `storage.googleapis.com` (vision integration only) and `127.0.0.1`. Also
  ships `scripts/issue_triage.py`, which calls `api.github.com` — their repo
  tooling, unused by the skill.
- [scroll-world](https://github.com/oso95/scroll-world) (MIT) — 1 skill,
  `SKILL.md` plus a bundled `references/scrub-engine.js`. Markdown/JS only; no
  build step.
- [Impeccable](https://github.com/pbakaus/impeccable) (Apache-2.0) — 1 skill
  (2.3M). **Contains a downloader:** `scripts/impeccable` (mode 775) fetches a
  platform binary from
  `https://github.com/pbakaus/impeccable/releases/download/engine-v<ver>/…`
  and `exec`s it on first use, verifying SHA-256. Not run during install. Also
  bundles `scripts/live-browser.js` (drives a local browser over
  `localhost`).
- Freebuff (Buffy coding agent). Session of 4 Oct 2026: implemented Phase 1
  (contract + mock data) and frontend milestones F1/F2 from
  `docs/Implementationplan.md` in TypeScript under `web/`.

## What the AI did

<!-- Per session: what the AI wrote, what it suggested, what it reviewed. Cite the commit hash where applicable. -->

- Installed the Graphify skill and 35 third-party skills into `.agents/skills/`
  (36 total) and reviewed each source for executable code and outbound network
  before use. No project source, no `src/compute/` logic, and no scientific
  output were changed.
- 4 Oct 2026 (Freebuff): wrote `docs/API_CONTRACT.md`, the zod contract in
  `web/src/contract/` and its JSON Schema export to
  `docs/contract.schema.json`; wrote the deterministic mock generator
  `web/scripts/gen-mock.ts` (seeded, validated against the contract, output
  labelled `meta.source: "mock"`); scaffolded the static offline frontend in
  `web/` (F1: Vite + React + TS, tokens, self-hosted fonts, DataSource layer,
  URL-synced state, mock banner, source badge, provenance drawer; F2: hero
  SVG series chart with an accessible Raw | Harmonized toggle and a 600 ms
  reduced-motion-aware transition); added Vitest and Playwright suites. The
  AI generated the mock numbers themselves — they are synthetic by design and
  are never evidence.
- 4 Oct 2026 (Freebuff, redesign session): used the Impeccable design skill
  (project-scoped at `.agents/skills/impeccable/`) to redesign the F1/F2
  surface into the world committed in `docs/DESIGN.md` v2 — green-and-black
  tokens, frosted-glass shell over a mesh ground, Fraunces/Inter/JetBrains
  Mono self-hosted via fontsource, sliding-thumb Raw|Harmonized toggle,
  era-banded timeline with a ghost comparison line and direct labels.
  Created `PRODUCT.md` and `.impeccable/surfaces/web-src-app-tsx.md`
  (direction contract). All copy, palette, and type come from DESIGN.md;
  the AI made no product decisions beyond what the docs and user answers
  specify. Captures in `.impeccable/review/` are gitignored dev artifacts.

- 4 Oct 2026 (Freebuff, globe hero session): used the **img2threejs** skill
  (project-scoped at `.agents/skills/img2threejs/`) to rebuild the direction
  reference (`~/Downloads/reference.png`, a dark neon-green Earth) as a
  **code-only procedural Three.js globe**: `web/src/globe/geo.ts` (pure
  sphere/geography maths), `globeSpec.ts` (the reconstruction parameter sheet),
  `createEarthGlobe.ts` (the scene factory) and `GlobeHero.tsx` (canvas, render
  loop, pointer drag, resize observer, WebGL fallback). The land shell is
  generated offline from Natural Earth 1:110m land by
  `web/scripts/gen-landmask.ts` (`npm run land:gen`) — the input TopoJSON is
  committed at `web/scripts/data/land-110m.json`, so the step needs no network
  and the globe ships no downloaded mesh or image texture. Also restyled the
  whole page to the reference's dark world (tokens + app.css), added the
  data-driven `HottestCells` panel, moved the timeline into section 2, and added
  `web/tests/unit/globe.test.ts` plus three Playwright cases (globe mounts and
  lists real payload values, selecting a cell moves the camera — asserted by a
  canvas pixel diff — and the toggle reaches the hero copy). Session prompts
  below. The AI chose the palette values, the camera framing, and which cells
  the globe draws; every number shown still comes from the payload verbatim.

- 4 Oct 2026 (Freebuff, Phase 0 acquisition session): wrote `src/acquire/firms.py`
  (download NASA FIRMS Area API CSVs for the Bangladesh box into parquet,
  Suomi-NPP first, ≤5-day chunks, rate-limited to the documented 5,000
  transactions / 10 minutes, resumable, offline-safe through
  `src/acquire/safe.py`), `tests/test_firms.py` (26 offline tests), the
  `make cache` / `make venv` targets in the `Makefile`, and the cited product
  list in `docs/DATA.md` and `README.md`. No network call was made: the tests
  use a fake fetcher and the endpoint shapes come from the FIRMS API docs at
  <https://firms.modaps.eosdis.nasa.gov/api/area/>. Session prompt below. The
  AI chose the module structure, the chunking math and the parquet layout; the
  sensor product names, the ≤5-day API limit and the MAP_KEY limit are the
  vendor's documented facts, not the AI's invention.

- 4 Oct 2026 (Freebuff, frontend functionality + design-taste-frontend session):
  added the four surfaces the Implementation plan still had missing —
  `CalendarHeatmap.tsx` (F3, year x day-of-year burning calendar driven by the
  same `series` payload, so the toggle recolors it with no refetch),
  `ValidationCard.tsx` (the overlap correlations and cell-size sweep),
  `AnomalyBox.tsx` (percentile, baseline window, and a day-of-year lookup into
  `baseline`) and `MethodsPanel.tsx` (cell size, confidence mapping, collapse
  rule, notices, and every dataset cited with id, FIRMS product name and URL).
  Added `src/charts/calendar.ts` (pure calendar model), wired all seven
  contract endpoints into `App.tsx`, added nav anchors, and fixed the top-nav
  so it wraps at phone widths. Loaded the **design-taste-frontend** skill and
  applied its applicable rules (this is product/dash UI, so its landing-page
  rules were explicitly out of scope): one-accent lock, shape lock, full
  interactive states, reduced motion, and the em/en-dash ban on visible copy.
  Added `tests/unit/calendar.test.ts` (12) and
  `tests/unit/design-tokens.test.ts` (22, WCAG contrast computed from the
  real `tokens.css`), plus `e2e/preflight.spec.ts` (4) and 3 app e2e tests.
  Session prompts below. No science was computed in the UI: every new number
  is read from a payload, and bucketing is presentation only.

- 4 Oct 2026 (Freebuff, toggle performance check): measured the mode toggle
  against the under-100 ms response budget in `docs/Implementationplan.md`
  section 5.4. On the production build the first DOM feedback lands in 16–34 ms
  and the full chart-plus-calendar commit in 75–95 ms, so the budget is met
  (measured with a temporary Playwright probe and the in-browser Performance
  API; the probe was deleted after the run). Two edits that came out of the
  check: `useDeferredValue(mode)` was tried and measured *worse* (dev ~300 ms
  against ~200 ms), because React still rebuilds all ~8.7k calendar cell vnodes
  in the urgent pass before re-doing them in the deferred pass, so it was
  reverted — `CalendarHeatmap.tsx` reads `mode` directly; and the per-cell
  mouse handlers were replaced by one delegated handler on the SVG. The 700 ms
  chart morph is intentional (`docs/DESIGN.md` section 10) and is disabled
  under `prefers-reduced-motion: reduce`, which is the mode the budget was
  measured in. No science changed; this was presentation-layer timing only.

- 4 Oct 2026 (Freebuff, Phase 4 API session): wrote `src/api/dataset.py` (the
  offline-first dataset resolver: `cache/raw/*.parquet` then the committed
  `demo_fixtures/detections.parquet`, with `OFFLINE=1` forcing the fixture),
  `src/api/main.py` (FastAPI app exposing the seven contract endpoints plus
  `/health`, every payload built by the already-tested
  `src/compute/export.py` builders), `tests/test_api.py` (27 contract tests
  that call each route through the ASGI test client and validate against
  `docs/contract.schema.json`), and `src/demo.py` — the deterministic
  synthetic-detection generator, moved out of `tests/synthetic.py` (which now
  re-exports it) because the API's offline fixture is generated from the same
  code by `python -m src.demo` / `make fixture`. The committed fixture
  (`demo_fixtures/detections.parquet`, 2019-2020, synthetic) is what makes the
  demo run with no API key; its numbers are never evidence and every response
  reports `meta.source: "fixture"`. The AI chose the cache/fixture precedence,
  the zero-fill of quiet days for the anomaly, and the CORS allow-list; it did
  not invent any science. No real FIRMS data exists, so the API has never
  served a real detection.

- 4 Oct 2026 (Freebuff, Phase 5 frontend wiring): implemented
  `web/src/data/ApiDataSource.ts` (the real HTTP source: `/api/*` on the
  app's own origin, every response validated against the same zod contract
  the mock files use), added the `/api` dev/preview proxy in
  `web/vite.config.ts` so the browser makes no cross-origin request, split
  the anomaly fetch in `App.tsx` so the box asks the API for the day the
  reader selects (and reports an uncovered day inside the box rather than
  blanking the page), and added `e2e/api-mode.spec.ts` plus an `api-mode`
  Playwright project that runs the same app with `VITE_DATA=api` against
  `make demo`. The AI chose the proxy-over-CORS approach, the query
  parameter shapes and the failure wording; the payloads and every number
  are still the API's. The banner behaviour is unchanged: `MockBanner`
  still fires only on `source: "mock"`, which means the synthetic
  *fixture* tier shows a source badge but no banner (see "did not do").

## What the AI did not do

<!-- Be explicit. The AI should not generate final scientific decisions, dataset licenses, or anything that requires domain expertise you do not have. -->

- No NASA API or any network data source was called. `src/compute` and
  `src/api` exist and are tested, but both have only ever run on the synthetic
  detections in `src/demo.py`, and the frontend's `VITE_DATA=api` path has
  only ever reached that same synthetic fixture. Two honesty gaps are left
  open rather than papered over: (1) the committed fixture is synthetic yet
  `MockBanner` fires only on `source: "mock"`, so an `api`-mode page shows a
  `fixture` badge and no "not evidence" warning; (2) Phase 6 fixtures are
  meant to be real precomputed bytes, which would make a blanket fixture
  warning wrong. Deciding that wording needs a product call, so the banner
  was left alone. Sensor
  epoch dates are placeholders marked `// TODO verify against FIRMS docs` in the
  mock and, in `src/acquire/firms.py`, flagged in `docs/DATA.md` as unverified
  until checked against the FIRMS data-availability API; they are not facts.
  No harmonization statistics were computed for real data, and no real FIRMS
  data has been downloaded (`cache/` is empty). The frontend was never reviewed
  visually in this environment: every frontend claim above is the result of
  programmatic checks (type-check, lint, unit tests, `vite build`, and headless
  Playwright), not a human or model look at a rendered screenshot.

## Prompts

<!-- Append key prompts verbatim, with a short note on the outcome. -->

- Session brief (4 Oct 2026): "Implement Phase 1 (contract + mock data) and
  frontend milestones F1 and F2 from docs/ImplementationPlan.md, then STOP and
  report. Do not start F3 or later. Do not touch src/compute, src/acquire or
  src/api. Do not call any NASA API." — followed; scope held to Phase 1 + F1/F2.
- Globe hero brief (4 Oct 2026): "use the skill img2threejs,
  '/home/xenon/Downloads/reference.png', my website should look like this and the
  hero section will have the earth sphere, which will have glowing rots which will
  represent live fire spots. the graph will be in 2nd section". Interview answers:
  fire spots = the real mock cells from `public/mock/cells.json` (not an invented
  global field); theme = whole app dark; right column = yes, a data-driven list of
  the busiest cells. Outcome: the globe draws only the 500 busiest of the 10 047
  mock cells, labelled in the hero legend, because at full density the dot field
  saturates into a single white patch; the panel and the cells JSON carry all of
  them. `docs/DESIGN.md` section 0.1 records the direction.
- Phase 0 acquisition brief (4 Oct 2026): "Implement Phase 0: make cache real
  — a src/acquire/firms.py that downloads FIRMS parquet for the Bangladesh box,
  Suomi-NPP first". Outcome: the module, its 26 offline tests, `make cache`, and
  the cited dataset list in docs/DATA.md. Real downloads still need a
  FIRMS_MAP_KEY (not supplied), so no live data was fetched.
- Frontend functionality brief (4 Oct 2026): "make the frontend more fubnctional
  and use this skill design-taste-frontend" (sic, quoted verbatim), followed by
  "continue to work". Outcome: the calendar, validation card, anomaly box and
  methods panel above, with 78 unit and 17 end-to-end tests green. The design
  read, the three dial values and the two documented overrides (Fraunces is
  named by this project's own DESIGN.md; the neon-green accent is the direction
  set from the reference image) are stated in the session's design read.
- Phase 4 API brief (4 Oct 2026): "Build the Phase 4 API: src/api serving the
  seven contract endpoints, offline-first with contract tests". Outcome: the
  FastAPI app above, its resolver, the 27 contract tests and the committed
  fixture, all green with `make lint` and `make test` (115 passed). `httpx2`
  was added to the dependencies because Starlette's test client requires it.
- Frontend-to-API wiring (4 Oct 2026), chosen from a "what next" prompt: "Wire
  the frontend to the API". Outcome: `ApiDataSource`, the `/api` proxy, the
  interactive anomaly fetch, 9 unit tests and 4 api-mode e2e tests, all green
  with `tsc`, eslint, prettier, vitest (87), `vite build` and Playwright (21).
- Redesign brief (4 Oct 2026): "use impeccable skill, redesign the frontend",
  pointing at `docs/DESIGN.md` and `docs/frontend.md`. Interview answers:
  scope = redesign the existing surface only (no globe/calendar yet); type =
  DESIGN.md's Fraunces/Inter/JetBrains Mono; product record approved as
  written in PRODUCT.md.