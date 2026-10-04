# AI Use

A transparent record of how AI tools contributed to this repository.

## Tools

<!-- List every AI tool you used here. Examples: GitHub Copilot, Claude (claude.ai / Claude Code / puku-cli), ChatGPT, Cursor, etc. -->

- [Graphify](https://github.com/Graphify-Labs/graphify) (PyPI package
  [`graphifyy`](https://pypi.org/project/graphifyy/), Apache-2.0). Installed as a
  project-scoped Agent Skill at `.agents/skills/graphify/`. Code is indexed locally
  with tree-sitter (no LLM, no network); only the optional semantic pass over
  docs/media would call a backend, and no backend is configured in this repo.

## What the AI did

<!-- Per session: what the AI wrote, what it suggested, what it reviewed. Cite the commit hash where applicable. -->

- Installed the Graphify skill into the repository. No project source, no
  `src/compute/` logic, and no scientific output were changed.

## What the AI did not do

<!-- Be explicit. The AI should not generate final scientific decisions, dataset licenses, or anything that requires domain expertise you do not have. -->

- _None yet._

## Prompts

<!-- Append key prompts verbatim, with a short note on the outcome. -->

- _None yet._