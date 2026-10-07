# Contributing to Project Icarus

Icarus harmonizes MODIS and VIIRS active-fire hot spots into one burning activity
calendar (NASA Space Apps 2026). This guide covers setup, conventions, and the
rules that keep the science reproducible. Read `AGENTS.md` / `CLAUDE.md` for the
AI-agent contract before using a coding agent on this repo.

---

## 1. Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| Python | 3.11+ | Pipeline, API, tests |
| `uv` | latest | Fast, reproducible virtualenv (`make venv`) |
| Node.js | 20+ | Frontend (`web/`) |
| DuckDB | bundled via `duckdb` (Python) | Analytical engine |
| Docker | 24+ (optional) | Single-image deployment |
| `ruff` | bundled | Lint |

A `FIRMS_MAP_KEY` is only needed for stage S0 (data acquisition). Everything else
runs offline and with no key.

---

## 2. Getting started

```bash
git clone https://github.com/mdhabibullahmahmudncs13/Icarus-Harmonization-of-MODIS-and-VIIRS-Hot-Spots.git
cd "Icarus: Harmonization of MODIS and VIIRS Hot Spots"

cp .env.example .env        # add FIRMS_MAP_KEY only if you will run S0
make venv                   # create .venv and install Python deps
make test                   # run the Python test suite

cd web && npm install       # frontend deps
npm run test                # unit tests
```

`make help` lists every target.

---

## 3. Repository layout

The module-by-module tree is `docs/ARCHITECTURE.md` §3. At the root:

- `README.md` — quick start and the offline demo steps.
- `config/params.yaml` — every tunable value (`docs/PARAMETERS.md`).
- `data/` — git-ignored except `reference/`.

Full background: `docs/PRD.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md`.

---

## 4. Workflow

Trunk-based development with short-lived branches.

1. Branch from `main`: `git switch -c feat/s5-cell-day`.
2. Make the smallest change that satisfies the requirement.
3. Run `make lint` and `make test` (and `npm test` in `web/` if you touched it).
4. Open a pull request with a Conventional Commit style title
   (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
5. Keep the diff scoped: one stage, one component, or one doc per PR.

Commit messages explain **why**, not just what. Reference the requirement or
parameter you are satisfying when relevant (for example `FR-07`, `§5.5`).

---

## 5. Non-negotiable rules

1. **Determinism.** Identical raw inputs + identical `params.yaml` hash MUST
   produce byte-identical derived output (NFR-01). Never introduce unseeded
   randomness, wall-clock time into outputs, or non-deterministic ordering.
2. **Pure core.** `src/core/` performs no I/O and imports no web framework. It
   takes values in and returns values out.
3. **The API is read-only.** It never mutates data and never computes statistics;
   that work belongs to the pipeline.
4. **The frontend never calls NASA.** It reads the API (or cached JSON) only.
5. **Deterministic code does the science.** An LLM may retrieve, orchestrate, or
   explain — never compute a number.
6. **Every number carries its source.** No displayed value without a provenance
   path.
7. **Never commit data or secrets.** `data/`, `cache/`, `.env`, and `*.parquet`
   (except committed fixtures) are git-ignored. Do not disable that.
8. **Name NASA datasets correctly.** Use product names verbatim and cite them
   with a URL (see `docs/DATA_DICTIONARY.md`).

---

## 6. Code conventions

### Python

- `ruff` with `line-length = 100`, target `py311` (see `pyproject.toml`).
- Type hints on public functions; docstrings state units and the spec section.
- One stage per module: `s0_acquire.py` … `s9_harmonize.py`.
- Raise on invalid configuration; fail loud rather than guessing defaults.
- No hidden network calls outside `src/pipeline/` and `src/acquire/`.

### SQL / DuckDB

- Keep reusable queries in `src/sql/` so the API and the (stretch) browser share
  them.
- Prefer `FILTER (WHERE ...)` for conditional counts, as in the reference SQL.
- Preserve deterministic ordering when writing Parquet (sorted keys).

### Frontend (TypeScript)

- Strict mode on.
- All requests go through the data-source interface; components never fetch
  directly.
- New datasets or sources must be added to the provenance panel.

---

## 7. Testing expectations

Every pipeline stage ships with a test. Details in `docs/TESTING.md`.

- New pure function → unit test with boundary cases.
- New stage → golden-file test on synthetic input.
- New endpoint → contract test validating the response against the schema.
- New randomness → a fixed seed and a reproducibility test.

A PR is not ready if it lowers the existing test coverage or skips a test to go
green. If a check cannot run, say so in the PR rather than silently disabling it.

---

## 8. Parameters

All tunables live in `config/params.yaml`. Adding or changing a parameter:

1. Update `config/params.yaml` with a default and a comment.
2. Document it in `docs/PARAMETERS.md` (default, meaning, section, range).
3. Note the sensitivity experiment it affects (E1–E9).

Derived artifacts record the parameter hash, so a parameter change invalidates
downstream outputs by design.

---

## 9. Working with AI agents

This repo is agent-friendly. When using one:

- Record the tool and any notable prompts in the pull-request description, and
  note installed agent skills so they stay visible in review.
- Keep agents inside `src/`, `web/`, and `docs/` — never let them touch `data/`.
- Require them to run `make lint` and `make test` and to report real results.
- The harmonization method, parameters, and statistics are the team's own and
  must not be delegated blindly to a model.

---

## 10. Pull-request checklist

- [ ] `make lint` passes.
- [ ] `make test` passes (and `npm test` for frontend changes).
- [ ] New behaviour has a test; new parameters are documented.
- [ ] Determinism preserved (no unseeded randomness; outputs unchanged for the
      same input + hash).
- [ ] No data or secrets added to the repository.
- [ ] Docs updated (`docs/PARAMETERS.md`, `docs/DATA_DICTIONARY.md`, or the
      relevant doc).
- [ ] Commit message follows Conventional Commits and explains why.

---

## 11. License

By contributing you agree your work is released under **Apache-2.0** (see
`LICENSE`).
