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
- Tests: `uv run pytest` (config already applies `-q -n auto` and a per-test
  timeout). **Focused tests while you iterate, the full suite once before you
  push or merge.** The full run is about four minutes, so spending it on every
  one-line change is waste -- run the files covering your area instead, as
  many times as it takes. Run it in full exactly once, at the end, because
  that is where the surprises live: a canonical-phrase change on 2026-08-17
  passed every focused suite and still had a stale assertion waiting in
  `test_lane_discrete.py`, three files away from anything obviously related.
  A slow sweep test needs its own `@pytest.mark.timeout` -- under
  xdist the thread timeout kills the worker and reads as "node down". What
  `-n auto` resolves to is capped in `tests/conftest.py`: workers load pygame
  and the audio stack, so past about eight the run stops getting faster, and
  uncapped on a 28-core machine it died in the reporter rather than merely
  running slowly.
- Adversarial battery: `uv run pytest tests/adversarial -m adversarial`. Slow,
  so it is deselected by default and not even collected without the marker.
  Deliberately unreasonable play (floor it through town, coast a mountain in
  neutral, save-scum a traffic stop) against the real driving state. Known
  open findings are strict xfails in `KNOWN_OPEN`; fix one and delete its
  entry in the same change, which is what the XPASS failure will tell you to
  do. Same scenarios still run as a tool for reading spoken output:
  `uv run python tools/playtest_break.py --scenario NAME --transcript`.
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
- Use the canonical spoken noun for each concept from `docs/ontology.md`.
  Synonyms for one thing cost screen reader users a re-read. Adding a concept
  means adding a row there in the same change.
- Never use Computer Use, desktop UI automation, or OS-level game window or
  process interaction to validate or control Freight Fate. These tools do not
  reliably control Pygame and can disrupt a player's active drive. Use the
  deterministic headless transcript/playtest harness, automated tests, and
  user-provided manual validation instead.

## World and route data

- The build tools edit `src/freight_fate/data/world_source/`; the game loads
  the indexed `src/freight_fate/data/world_data/` tree. After editing the
  source, regenerate with `uv run python tools/index_world.py` and verify with
  `--check` -- CI and tests expect the two in sync.
- Never read or write the source files directly. Go through
  `tools/world_source.py`: `load_world()` returns the whole world as one dict,
  `save_world(data)` writes it back as per-state shards. Both trees are
  sharded by the state a leg starts in (`legs/TX.json`) so a one-leg edit is a
  small reviewable diff instead of a 60 MB blob.
- Data must be deterministic and load offline. Add source notes for
  real-world facilities, stops, and limits. No raw OpenStreetMap tags in
  player-facing names.
- Enriching a leg (real checkpoints, truck-stop POIs, fine grades) or
  finishing a new corridor: follow `docs/map-enrichment-recipe.md` exactly --
  it encodes the judgment rules and the spoken-text invariants.
- After data changes run the world and route tests, e.g.
  `uv run pytest tests/test_world.py tests/test_world_overlay.py`.

### Provenance: read, derived, or assumed -- never blurred

Three bugs in one week were the same bug: a baked number nobody could tell
apart from a measurement. 455 grade segments steeper than 8 percent (worst
+14.4 on I-5) came from elevation-profile noise over bridges. 1,079 curve
records bend tighter than any highway of their class can. And `ramp_control`
is empty on **all 18,011** interchanges, so a seeded runtime fallback decides
every ramp terminal in the game. Not one of those upstream sources asserted
anything false -- we filled their gaps, or mis-derived from them, and then
stored the result in a `source`-carrying record that reads as a survey.

- **Say which KIND of value it is, not just where it came from.** Every baked
  record carries `source`; that string must also make plain whether the value
  was **read** (the upstream data asserts it), **derived** (computed from a
  reading -- name the input and the formula), or **assumed** (a fallback used
  because upstream is silent). `tools/toll_rates.py` is the model to copy: a
  `verified` flag beside `src` on every figure, and a refusal to mark one
  verified just to look tidy.
- **A silent upstream is not a reading.** OSM covers `maxspeed` on 14,563 of
  15,234 speed-limit segments and tagged ramp control on none of 18,011
  interchanges. Filling that silence is fine and often necessary. Filling it
  with an invented default, and shipping it in the same shape as the 14,563,
  is what makes the gap invisible. Prefer a published statutory or design
  value to a guess, and label it `assumed` either way.
- **A bake that mostly assumed must say so, loudly.** When a builder writes
  `assumed` for more than half a layer's records it prints that on stdout and
  records the ratio in the layer's `meta`. A quiet builder that produced a
  complete-looking file out of nothing is how the ramp fallback survived to
  18,011.
- **Screen a derived value against the physical limit for its class before
  writing it.** A slope no interstate can hold, a radius no through highway
  can bend to, an arc that will not fit its own recorded span. See the three
  screens in `src/freight_fate/data/curves.py`; grade still has none.
- **Self-contradiction is the tell, not extremity.** Real roads are sometimes
  brutal, so steepness alone proves nothing. What proved the artifacts fake
  was each record disagreeing with itself: an 8.3 percent slope on a segment
  labelled `flat` terrain, a hairpin on flat local ground, a curve whose arc
  is longer than the span containing it. Screen the contradiction and leave
  the merely steep or merely sharp alone.
- **Screen at load; never edit the bake to hide the evidence.** Both existing
  screens run over an untouched bake and name the flagged rows in a separate
  file (`curve_artifacts.jsonl`). Keep that shape: a screen that deletes what
  it rejects cannot be re-judged when the rule turns out too broad.
- **Official sources exist for most of this -- prefer them to a default.**
  Grade and curve ceilings by class and terrain: state DOT road design
  manuals (Caltrans HDM, TxDOT Roadway Design Manual), which republish the
  AASHTO Green Book controls for free. Per-section terrain, through lanes,
  and grade/curve class: FHWA HPMS public release. Elevation: USGS 3DEP at
  1/3 arc-second, finer than the SRTM under ORS. Bridge locations and
  vertical clearances, which is what to mask elevation noise against: FHWA
  NBI. Truck speed limits by state: the state vehicle codes. Truck-legal
  routes: the National Network, 23 CFR 658 Appendix A. All free, all
  downloadable once and read offline, which the data rule above requires.

## Code conventions

- Keep practical code files at or below 1000 lines; split oversized modules.
- Match the surrounding code's naming, comment density, and idiom.
