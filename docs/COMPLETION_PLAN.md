# Completion plan

What is left to finish Project Icarus, in the order that matters. The
scientific core is done and verified against real NASA data; everything here is
about the demo gate and the spec/code agreement.

**Status: §1, §2 and §3 are done.** The offline-demo gate passes, FR-19 is
reclassified, and the two stale plan items are retired. §4 lists what is still
unmeasured.

---

## 1. The offline-demo gate (task #25) — the blocker — **DONE**

`docs/IMPLEMENTATION_PLAN.md` §7 gates the demo on two Playwright specs:
`no-third-party.spec.ts` and `offline-cold-start.spec.ts`. Both assert that
`.mock-banner` is visible, which only renders on the **mock** tier
(`web/src/lib/source.ts` — `cache` and `live` are evidence and get no banner).

Three defects stop them passing:

| # | Defect | Evidence |
|---|--------|----------|
| a | The repo-root `.env` sets `VITE_DATA=api`, so `vite build` bakes the api tier | `web/dist/assets/main-CxKCNdrD.js` contains `127.0.0.1:8011/api/v1` and no `/mock/` reference |
| b | `VITE_API_BASE` points at port **8011**, which nothing serves | `curl 127.0.0.1:8011` → connection refused; 8010 is the live port |
| c | `web/playwright.config.ts` has `reuseExistingServer: true` and no build step, so the suite silently tests whatever `dist/` happens to be on disk | the config comment says to build first, but nothing enforces it |

**The specs are right; the build configuration is wrong.** An offline cold
start cannot depend on a live API — if the API is unreachable the test cannot
tell "served from the cache" from "failed to load". So the fix is the build,
not the assertions.

### The fix

1. **The e2e suite builds its own mock-tier bundle.** Give
   `web/playwright.config.ts` a `webServer` that runs
   `VITE_DATA=mock vite build && vite preview --port 4173 --strictPort`. The
   build happens inside the suite, so it cannot test a stale `dist/`, and the
   tier is explicit rather than inherited from whatever `.env` says.

2. **The stale port.** `.env` and `.env.example` both name 8011. The port the
   API actually uses is the uvicorn default, **8000**
   (`make demo` → `uvicorn src.api.main:app`, no `--port`). Correct both files
   to 8000 so `VITE_DATA=api` works out of the box. `ALLOWED_ORIGINS` already
   allows the dev origin, so nothing else changes.

3. **The tier split stays explicit.** `.env` is a developer-local file and is
   git-ignored; the suite must not read it. Building with an explicit
   `VITE_DATA=mock` in the webServer command does that.

### Also

- `web/package.json` gets a `test:e2e` script that builds first, so the
  documented command matches what actually runs.
- The Playwright browser-version mismatch on this machine
  (`chromium_headless_shell-1243` expected, `-1248` installed) is an
  environment problem, not a repo problem — CI installs its own browsers.

---

## 2. FR-19 versus the placeholder (task #26) — **DONE**

The PRD marked FR-19 "Download for offline" as **M (Must)** while the
implementation was a placeholder card that said "arrives in Phase 5". A
Must-have that is a placeholder is a broken promise. Two honest options:

- **Implement it** — but the size estimate, progress and per-layer timestamps
  it describes are properties of a download manager the app does not have, and
  the offline story already works through the service worker. This is new
  scope, not a completion task.
- **Reclassify it** — mark it **C (Could)** with a note that the offline
  story is the service worker, and that the download manager is later work.

**Chosen: reclassify.** FR-19 is now `C` in `docs/PRD.md` §6, with a note
explaining why. The placeholder card is gone: `OfflinePanel` now reads the
Cache API and reports the real cache state (cache name, entry count, size)
plus the data source, with a "Reload to refresh the cache" action. The
arithmetic is pure and tested in `web/tests/cacheState.test.ts`;
`web/src/lib/cacheState.ts` holds the reader.

`docs/FLOWS.md` Screen 7 and Journey 6, `docs/ROADMAP.md` WP5,
`docs/ARCHITECTURE.md` §8 and `docs/TRD.md` §7 now describe the screen that
exists.

---

## 3. The remaining plan items (task #24) — **DONE**

Three unchecked boxes in `docs/IMPLEMENTATION_PLAN.md` §7:

- **PMTiles basemap** — superseded: the map is client-side SVG polygons and
  requests no tiles at all. The no-third-party test keeps that honest. Now
  checked, with the reason.
- **Docker image** — superseded by the source-checkout model that
  `docs/DEPLOYMENT.md` §1 now documents. Now checked, with the reason.
- **Real-device cold start and the fallback video** — genuinely needs
  hardware. Still open, annotated as blocked on a device rather than on work.

The §7 bullet list also mentioned Workbox and PMTiles; a note now says those
bullets describe an architecture the project no longer has.

---

## 4. Unmeasured things worth knowing

Not blockers, but the demo should not overclaim:

- **Lighthouse PWA score** — unmeasured.
- **E8 burned-area validation covers 2019 only** (36 granules). The plan
  itself says to widen the window before treating it as final.
- **E2 is partial** — the residual offset falls 1.61 → 0.39, above the
  pre-registered 0.25 ceiling. Reported honestly already; keep it that way.
- **`LICENSE` and the root `README.md`** were retired in `c8781da`. Apache-2.0
  is the stated intent and should be restored before release.

---

## Order

1. Task #25 — the offline-demo gate. Nothing else matters until this passes. **Done.**
2. Task #26 — FR-19. A one-line PRD change once the decision is made. **Done.**
3. Task #24 — retire the two stale plan items, annotate the device one. **Done.**

Each task ends with the suite re-run: `make lint`, `make test`, `npm test`,
`npm run test:e2e`.

---

## 5. What is still open

Two things that are not code:

1. **A real device and a fallback video** — the automated cold start passes,
   but AC-3 wants the demo recorded on hardware.
2. **`LICENSE` and the root `README.md`** — restore before release; the
   Apache-2.0 intent is stated but the files are not there.

And three gaps against the challenge statement, which are code:

3. **Polygon drawing for a custom AOI** (FR-16). The API half-supports it —
   `_resolve` accepts a bbox and refuses polygon objects — but the frontend
   can only pick a preset, and `AppState` has no bbox field.
4. **Monthly and annual aggregation.** The pipeline bins cell-days into
   46 eight-day bins and never aggregates them up, though the statement asks
   for seasonal and annual comparisons.
5. **Global extent.** The statement says "global", but only the Bangladesh
   bbox is cached, so the `IND-C` and `NPL` presets have no data at the API
   tier.

The CSV export (FR-22) was the fourth gap and is now built: `GET
/api/v1/export` serves the filtered hotspot records as CSV, and the frontend
offers the download with its record count on the button.

