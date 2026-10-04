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

## What the AI did not do

<!-- Be explicit. The AI should not generate final scientific decisions, dataset licenses, or anything that requires domain expertise you do not have. -->

- No NASA API or any network data source was called; `src/compute`,
  `src/acquire` and `src/api` were not touched. Sensor epoch dates in the
  mock are placeholders marked `// TODO verify against FIRMS docs` and are
  labelled as placeholders in the UI; they are not facts. No harmonization
  statistics were computed for real data.

## Prompts

<!-- Append key prompts verbatim, with a short note on the outcome. -->

- Session brief (4 Oct 2026): "Implement Phase 1 (contract + mock data) and
  frontend milestones F1 and F2 from docs/ImplementationPlan.md, then STOP and
  report. Do not start F3 or later. Do not touch src/compute, src/acquire or
  src/api. Do not call any NASA API." — followed; scope held to Phase 1 + F1/F2.
- Redesign brief (4 Oct 2026): "use impeccable skill, redesign the frontend",
  pointing at `docs/DESIGN.md` and `docs/frontend.md`. Interview answers:
  scope = redesign the existing surface only (no globe/calendar yet); type =
  DESIGN.md's Fraunces/Inter/JetBrains Mono; product record approved as
  written in PRODUCT.md.