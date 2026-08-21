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
- After the full suite passes, run the adversarial battery too:
  `uv run pytest tests/adversarial -m adversarial`. The playtest HARNESS is
  already in the full run (`tests/test_playtest_harness.py`, 54 tests); the
  battery is not, because `-m "not adversarial"` lives in the addopts. So a
  green suite says nothing about whether deliberately unreasonable play still
  behaves, which is exactly what a change to driving, traffic, speech or the
  world data can break. Fix any XPASS by deleting its `KNOWN_OPEN` entry in
  the same change.
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

A baked number nobody can tell apart from a measurement is the recurring bug
in this data. Upstream rarely asserts anything false; we fill its gaps, or
mis-derive from it, then store the result in a `source`-carrying record that
reads as a survey.

- **Say which KIND of value it is.** `source` must state **read** (upstream
  asserts it), **derived** (name the input and the formula), or **assumed**
  (a fallback, because upstream is silent). Model: `tools/toll_rates.py`.
- **A silent upstream is not a reading.** Filling a gap is fine; shipping the
  fill in the same shape as the real readings is what hides it. Prefer a
  published statutory or design value to a guess, and label it either way.
- **A bake that mostly assumed says so loudly** -- on stdout, and as a ratio
  in the layer's `meta`.
- **Screen derived values against the physical limit for their class**, and
  screen for **self-contradiction, not extremity**: real roads are sometimes
  brutal, so a record is suspect when it disagrees with ITSELF (a steep slope
  on ground classed level, an arc longer than its own span). Worked example:
  `src/freight_fate/data/curves.py`.
- **Never tune a threshold until it looks right.** Derive it from a published
  standard, or calibrate against real data and report how well it separates.
- **Screen at load; never edit the bake.** A screen that deletes what it
  rejects cannot be re-judged when the rule turns out too broad.
- **Prefer official sources**: state DOT design manuals (AASHTO controls,
  free) for grade and curve ceilings; FHWA HPMS for terrain, lanes, AADT and
  curve class; USGS 3DEP for elevation; FHWA NBI for bridges; state vehicle
  codes for truck limits; 23 CFR 658 App. A for truck-legal routes.

Which layers are screened, and what each measured, belongs in `ROADMAP.md`.
This file is how to behave; that one is where things stand.

## Working with the owner

Rules Josh set on 2026-08-21, after each was learned the hard way.

**Fix it; do not flag it.** Finding a real defect means fixing it END TO END
before reporting: the code, the regression test that would have caught it,
CHANGELOG and ROADMAP if either moves, the full suite plus the adversarial
battery, the commit and push, and the living-document reply to whoever
reported it. Then one short report of what changed. Ask first only when the
work spends money, is hard to reverse, or turns on a design rule only the
owner sets -- "it is a separate report" is not a reason to hand it back.

**Stay steerable: background anything that would block.** A foreground tool
call holds the turn and queues whatever the owner types next. Background any
single call over ~30 seconds (full suites, the adversarial battery, OSM
scans, release builds, world re-bakes). Then go do something that needs
neither the CPU nor the result -- never sit in a foreground `until ... sleep`
loop waiting for a background task, which throws away the whole point. At
most four background agents; exactly ONE pytest run in flight anywhere, ever.
And never pipe a test run to `tail`: the shell reports the pipeline's status,
so `pytest | tail` exits 0 while pytest is failing. Redirect to a file and
read the count.

**A manual playtest means the OWNER drives it.** Speech on, at the wheel,
hearing it -- that is the only thing that answers whether something feels
right. `--headless` is a different tool for a different question ("does this
machinery fire at all", "does the transcript contain the line"). It never
substitutes: reporting a bench as the playtest he asked for hands him a
verdict nobody listened to. When he asks for one, land the code, tell him
what to drive and what to listen for, then stop.

**Everything written in the living document is for a player.** No file names,
function names, constants, commit hashes, or internal vocabulary ("zone
builder", "the runtime", "provenance", "regression"), and no counts only a
maintainer wants. Say what the TRUCK did and what it does now. The status
words -- FIXED, PARTLY FIXED, OPEN, RECORDED -- are shared vocabulary and
stay. Re-read the document immediately before writing a reply, and read it
back afterwards; testers keep editing for a minute or two after the save that
fired the watcher.

**Tell a research subagent to write its findings file FIRST and rewrite it as
it goes.** One instructed to write at the end loses everything if the host
dies. Subagents also never background their own commands -- a detached
process outlives the agent that started it.

## Code conventions

- Keep practical code files at or below 1000 lines; split oversized modules.
- Match the surrounding code's naming, comment density, and idiom.
