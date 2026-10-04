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

## What the AI did

<!-- Per session: what the AI wrote, what it suggested, what it reviewed. Cite the commit hash where applicable. -->

- Installed the Graphify skill and 35 third-party skills into `.agents/skills/`
  (36 total) and reviewed each source for executable code and outbound network
  before use. No project source, no `src/compute/` logic, and no scientific
  output were changed.

## What the AI did not do

<!-- Be explicit. The AI should not generate final scientific decisions, dataset licenses, or anything that requires domain expertise you do not have. -->

- _None yet._

## Prompts

<!-- Append key prompts verbatim, with a short note on the outcome. -->

- _None yet._