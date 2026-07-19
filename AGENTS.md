# Agent Contributor Guide

Freight Fate is an audio-first, accessibility-first trucking simulation for
blind and low-vision players. Python 3.12, managed with `uv`. Full contributor
policy lives in `CONTRIBUTING.md`; this file is the short version a coding
agent needs at authoring time.

## Branches and PRs

- Open all feature, fix, data, and documentation PRs against `dev`.
  `main` is only for stable release, hotfix, or release-sync work.
- When creating a PR with `gh pr create`, build the body from the sections in
  `.github/PULL_REQUEST_TEMPLATE.md` (the template is not applied
  automatically outside the web UI): what changed and why, what players will
  notice, tests run, accessibility impact, and the changelog checklist.
- When reviewing and merging a contributor's PR, always credit the PR author
  in the release notes for the first build that includes it. Use the
  contributor's name and GitHub handle, and link to the PR.

## Changelog gate (CI-enforced)

Release notes are built only from curated entries in `CHANGELOG.md`, never
from commit subjects. CI fails any PR that changes user-facing paths
(`src/`, `docs/`, `CHANGELOG.md`, `README.md`, release tooling) without one.

- Player-facing change: add a bullet under `## Unreleased` in the fitting
  section (`Added`, `Changed`, `Fixed`, ...). Bold lead sentence, then plain
  player language about what they will hear or notice. Entries are read
  aloud by screen readers -- no jargon, tables, or decorative symbols.
- Nothing player-facing (refactors, CI, tests, tooling): put
  `[skip changelog]` or `changelog: none` in every commit message.

## Roadmap upkeep

`ROADMAP.md` tracks feature status per release line and must move with the
code, in the same change:

- Landing a roadmap feature (or a meaningful slice of one): check it off or
  reword its bullet to describe what actually shipped.
- Building something new that is not on the roadmap: add it to the current
  release-line section as you land it.
- Discovering follow-up work worth doing (deferred wiring, a needed data
  re-sweep, a known gap): record it as an unchecked bullet rather than
  leaving it only in commit messages or session memory.

## Commands

- Setup: `uv sync --group dev`
- Tests: `uv run pytest` (config already applies `-q`; per-test timeout is
  set). Run focused tests for your area first, the full suite for shared
  behavior.
- Lint: `uv run ruff check src tests tools`
- Byte-compile check: `uv run python -m compileall src tests tools`
- Headless runs: set `FREIGHT_FATE_NO_SPEECH=1` (CI also uses
  `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy`).

## Accessibility expectations

- Every gameplay path must stay usable by keyboard and screen reader.
- Spoken text is player-facing: no maintainer or CI jargon, and never replace
  spoken information with visual-only cues.
- If you touch menu items, prompts, warnings, settings, or status text, test
  the spoken result and say how in the PR.

## World and route data

- The build tools edit `src/freight_fate/data/world.json`; the game loads the
  split `src/freight_fate/data/world_data/` tree. After editing `world.json`,
  regenerate with `uv run python tools/index_world.py` and verify with
  `--check` -- CI and tests expect the two in sync.
- Data must be deterministic and load offline. Add source notes for
  real-world facilities, stops, and limits. No raw OpenStreetMap tags in
  player-facing names.
- Enriching a leg (real checkpoints, truck-stop POIs, fine grades) or
  finishing a new corridor: follow `docs/map-enrichment-recipe.md` exactly --
  it encodes the judgment rules and the spoken-text invariants.
- After data changes run the world and route tests, e.g.
  `uv run pytest tests/test_world.py tests/test_world_overlay.py`.

## Code conventions

- Keep practical code files at or below 1000 lines; split oversized modules.
- Match the surrounding code's naming, comment density, and idiom.
