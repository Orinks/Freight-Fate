# Agent Contributor Guide

Freight Fate is an audio-first, accessibility-first trucking simulation for
blind and low-vision players. Full contributor policy lives in
`CONTRIBUTING.md`; this file is the short version a coding agent needs at
authoring time.

**Career 1.9 is a native Rust game.** The Cargo workspace under `crates/`
(`ff-core`, `freight-fate`, `prism`, `prism-sys`, `bass-sys`) is the shipping
runtime. Python is no longer part of gameplay: `src/freight_fate/` remains as
the port's reference implementation and as the home of the world data tree,
and `tools/` stays Python for baking, packaging, and data generation. Write
gameplay changes in Rust. The `dev` line is still Python-only, so a fix that
must reach both lines has to be written twice -- ask before assuming it
should be.

## How the code fits together

Read this before opening files; the rest is discoverable from `lib.rs` docs.

- **`ff-core` is everything headless**: no window, audio device, screen
  reader or network, and the crate has no such dependencies, so the boundary
  is enforced by Cargo rather than convention. `data/` is the world (cities,
  legs, a Dijkstra graph; alternatives come from re-running the search with
  used legs penalised). `models/` is the career (profile, jobs, economy,
  trucks, credentials). `sim/` is the drive: one `Trip` struct owns the
  `TruckState`, `WeatherSystem` and `TrafficManager`, with the former Python
  mixins as extra `impl Trip` blocks in sibling files. The spoken-text rules
  (`speech_text`, `spoken_advice`, `speech_pacing`) live here too, so a
  transcript can be asserted without a game.
- **Every `ff-core` module keeps the name of the Python module it replaced**,
  and the port is line for line. When a Rust module's intent is unclear, the
  `src/freight_fate/` file of the same name is the reference. `pyrandom` and
  `pyfmt` exist because the tests pin spoken strings byte for byte to what
  Python produced; do not "fix" their rounding or RNG.
- **World data has two shapes.** The JSON tree under `src/freight_fate/data/`
  (`FREIGHT_FATE_DATA_ROOT` overrides it) and the baked, memory-mapped
  `world.ffdata` container (`data/baked/`) that the shipped game reads. A loose
  JSON path that is missing on disk falls through to the container's copy, so
  a release with no tree still answers. Heavy per-leg data is decoded on first
  touch either way.
- **`freight-fate` is the game**: `app/` holds `GameContext`, the shared
  services every state receives, plus the state stack it owns
  (`Vec<Rc<RefCell<dyn State>>>`; a lifecycle call runs immediately unless it
  targets the state currently in its own handler, which is deferred until that
  handler returns). `states/` is one `State` per screen; menus embed a
  `MenuCore`, implement `Menu`, and get their `State` impl from
  `impl_state_for_menu!`. `DrivingState` is one struct with one `impl` block
  per `driving_*.rs` file, the way the Python mixins were split.
- **Two speech channels, never interchangeable.** `ctx.say` is the menu and
  screen-reader channel. `ctx.say_event` is the driving channel: it goes
  through the priority ladder, the anti-backlog pacer and the audio duck, and
  can be silenced or cut, so a driving cue on `say` bypasses every one of
  those protections. Both land in the `freight_fate.transcript` log target,
  which is what a session log with `FREIGHT_FATE_LOG_FILE` set reads as.
- **Speech and audio are pluggable and optional.** `speech/` has the live
  Prism backend on its own worker thread, a capture sink the tests read
  transcripts from, and fakes. `audio/` is BASS behind a backend trait with a
  null fallback. `prism`/`prism-sys` wrap the Prism screen-reader and TTS
  library; `bass-sys` declares the BASS C ABI by hand and loads the DLL at
  run time, so a machine without either still starts the game.
- **Environment variables are two different roots.** `FREIGHT_FATE_DATA_ROOT`
  is where world data comes from; `FREIGHT_FATE_DATA_DIR` is where settings,
  saves and the keyring-backed token go. The playtest harness redirects the
  second, never the first.
- **Off-loop work** (cloud saves, presence, the updater, Discord, the agent
  server) lives in its own module under `freight-fate` and talks to the loop
  through channels; see the Rust engineering practices below for the rules.

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

The gameplay runtime is Rust; the tooling around it is Python. Which one you
need depends on what you touched.

### Rust -- gameplay, and what CI gates

#### Rust engineering practices

- Make ownership and lifetime boundaries explicit. Prefer borrowing over
  cloning, model optional ownership with `Option`, and use RAII for ordinary
  cleanup. Keep `unsafe` blocks small, explain the invariant they rely on, and
  expose a safe wrapper rather than spreading raw handles or pointers.
- Do not put network access, IPC, thread joins, window-manager calls, or other
  potentially unbounded work in `Drop`. Give long-lived workers an explicit,
  idempotent shutdown method: signal cancellation first, stop accepting work,
  then wait only within a measured bound. Log each shutdown boundary so a
  tester's timestamps identify the component that stalled.
- Never block the game loop on speech, audio-device discovery, HTTP, cloud
  saves, Discord, or operating-system UI. Move the work off-loop and return
  results through bounded channels; define what is dropped, cancelled, or
  retained when a queue fills or shutdown begins.
- Treat `unwrap`, `expect`, indexing, and panics as assertions of an invariant,
  not routine error handling. Player data, devices, network responses, and OS
  services are fallible: return or log contextual errors and keep the game in a
  usable state.
- Follow the pinned toolchain and keep `cargo fmt`, Clippy with warnings denied,
  focused tests, the full crate tests, and the adversarial battery as separate
  gates. Do not enable Clippy's restriction group wholesale; justify individual
  stricter lints where they fit this codebase.

References: [The Rust Programming Language: graceful shutdown and
cleanup](https://doc.rust-lang.org/book/ch21-03-graceful-shutdown-and-cleanup.html),
[Rust API Guidelines](https://rust-lang.github.io/api-guidelines/), and
[Clippy documentation](https://doc.rust-lang.org/stable/clippy/).

- Setup: install `rustup` (the pinned toolchain and its `rustfmt`/Clippy
  components come from `rust-toolchain.toml` via `rustup show`), then
  `uv sync` and `uv run python tools/fetch_bass.py` for the licensed BASS
  runtime. Without BASS the workspace still builds and the audio tests skip
  themselves, which reads as a green run that proved nothing -- so fetch it.
- Run the game: `cargo run --release -p freight-fate`
- Format: `cargo fmt --all --check`
- Lint: `cargo clippy --all-targets --locked -- -D warnings`. Warnings are
  errors, and `--all-targets` means test and bench code is linted too.
- Tests: `cargo test -p ff-core` and `cargo test -p freight-fate` (CI runs
  both in ONE invocation, `cargo test -p ff-core -p freight-fate`, so the
  build is shared). Integration tests live in `crates/<crate>/tests/it/*.rs`,
  wired in through that directory's `main.rs` -- one test binary named `it`
  per crate, deliberately, so add a `mod` line there rather than a new
  top-level file. The two exceptions, `crates/ff-core/tests/data_baked.rs`
  and `data_map_correction.rs`, each point the process at a different data
  root and so keep their own binary.
- One test: `cargo test -p freight-fate --test it <name_filter> -- --nocapture`
  (`--test it` skips the unit-test and doc-test binaries; the filter is a
  substring of the test path).
- **Focused tests while you iterate, the full run once before you push.**
  `cargo test -p ff-core <name_filter>` while the change is in motion. The
  full pair at the end, exactly once, because that is where the surprises
  live: a change to spoken text can strand an assertion in a file three
  directories from anything obviously related.
- Adversarial battery: `cargo run -p freight-fate --bin freightfate --
  --break-battery`. Every registered scenario, deliberately unreasonable play
  against the real driving state. `--list-break-scenarios` names them,
  `--break-scenario NAME --transcript` runs one and prints what was said.
  **The battery is NOT part of `cargo test`**, so a green test run says
  nothing about whether floor-it-through-town still behaves -- which is
  exactly what a change to driving, traffic, speech or world data breaks.
  Run it after the tests pass. Rust has no `xfail`, so a scenario that starts
  passing is a verdict change you fix or record, not something to leave.
- The playtest harness is a library module, `crates/freight-fate/src/playtest/`
  (`harness`, `menu`, `sandbox`, `road`, `breaker`), reachable from both the
  tests and the binary. Everything in it runs headless and isolated -- dummy
  SDL drivers, no speech, a throwaway `FREIGHT_FATE_DATA_DIR` -- so it never
  touches the operator's real settings, saves or keyring.
- Rust CI (`.github/workflows/rust.yml`) is **Windows only**, deliberately:
  SDL2 is vendored for `windows-x86_64` alone. Linux is not covered at all.
  macOS builds from source (BASS is fetched for both Mac architectures, Prism
  is vendored, and SDL2 is compiled in statically via the crate's `bundled` +
  `static-link` features -- NEVER Homebrew's sdl2, which is sdl2-compat and
  loads SDL3 at runtime, dying on player Macs), but has no runner. Add a
  platform's libraries before adding its runner.

### Python -- tools, data, packaging

- Setup: `uv sync --group dev`
- Tests: `uv run pytest` -- about six seconds now, so just run all of it.
  `pyproject.toml` already sets `-n auto` and a 120 s per-test timeout, so
  a bare `pytest` is a full-CPU xdist run; that is why only one may be in
  flight. A single file is `uv run pytest tests/test_build_release.py`.
  **The suite covers the Python that still ships and nothing else**: the
  build, bake, indexing and release tooling under `tools/`, plus the workflow
  and sound-pack guards. The ~220 files that mirrored gameplay in
  `src/freight_fate/` were retired on 2026-08-29: Career 1.9 is the Rust game
  and `cargo test` is what proves it, so do NOT add a gameplay test here --
  write it in Rust. A slow sweep test still needs its own
  `@pytest.mark.timeout`; under xdist the thread timeout kills the worker and
  reads as "node down".
- Lint: `uv run ruff check src tests tools`
- Byte-compile check: `uv run python -m compileall src tests tools`

### Both

- Headless runs: set `FREIGHT_FATE_NO_SPEECH=1` (CI also uses
  `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy`).
- **Exactly one test run in flight anywhere, ever.** Parallel agents each
  starting `pytest -n auto`, or each building the Cargo workspace at full
  job count, is the recurring way this machine falls over. Cap concurrent
  agents' builds with `CARGO_BUILD_JOBS`.
- Never pipe a test run to `tail`: the shell reports the pipeline's status,
  so `pytest | tail` exits 0 while pytest is failing. Redirect to a file and
  read the count.

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
  user-provided manual validation instead. For agent-driven play against the
  REAL game (real runtime, real audio, real menus), the sanctioned path is
  `freightfate --agent-server`: an MCP server inside the game that gives an
  agent a player's capabilities only -- keys in through the normal input
  seam, ears out (both speech channels plus every earcon and cue) -- always
  in the audited playtest sandbox, never against the owner's account.

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
- The shipped game reads a single baked container, not the JSON tree. After
  a data change re-bake it with `cargo run -p ff-core --bin ff-bake --
  --data-dir src/freight_fate/data --out dist/freight_fate/data/world.ffdata`,
  and prove a committed container matches its tree with the same command plus
  `--check`, which re-bakes to a temp file and compares bytes.
- After data changes run the world and route tests: the `data_*` and `sim_*`
  cases in `crates/ff-core/tests/it/` -- e.g. `cargo test -p ff-core
  data_world`. The Python world tests were retired with the rest of the
  gameplay mirror; what remains on that side is the tooling that BUILDS the
  data (`tests/test_index_world.py`, `tests/test_baked_data.py`).

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

**Report short.** One or two sentences: what changed, and what is different
now. Not a status board. No inventory of every file touched, no "found and
fixed" lists, no narration of things tried and reverted, no restating numbers
already given. A bug you hit and fixed is not news -- say it is fixed, or say
nothing. Reported 2026-08-24, on a closing summary with five headed sections
that left the owner unsure whether the bugs in it were fixed or still open.

Longer only when he asks for analysis, a decision needs context, or something
is genuinely still broken.

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
verdict nobody listened to.

**Launch the scenario for him, with the watcher on it.** Handing over a
command to paste is half the job. Start it -- `tools/playtest_road.py --find
<feature>` for a road feature, `tools/playtest_sandbox.py --launch` for
anything needing dispatch, a dock or the menus -- in the background, and put
`tools/playtest_watch.py` on that session's log under the Monitor tool so its
stdout becomes live notifications. It reports errors and any network call
immediately (a sandboxed session must never reach the site), checks in every
few minutes on where the drive got to, and summarises when the game exits.
Then say what to drive and what to listen for, and let him drive. One game at
a time: `SingleInstanceGuard` refuses a second window. Log paths are
`logs/playtest.log` for playtest_road and `logs/playtest-manual.log` for the
sandbox launcher.

**Triage by what it costs the driver, not by whether it sounds like a
bug.** Rule set 2026-08-23, after a "does the horn line read in quiet?"
question took a three-mode bench and a catalog check to answer "yes, by
design" while a real adaptive-cruise fault sat unread.

Order of work:
  1. It costs the drive -- the truck ignores an instruction, progress or
     cargo is lost, or a spoken line is untrue in a way that causes the
     mistake. Drop everything.
  2. It makes the drive harder -- information missing, wrong, cut off, or
     buried. Fix in turn.
  3. Preference, polish, or working as intended. Answer, do not
     investigate at length, and batch them.

TIER 3 IS ANSWERED FROM WHAT IS ALREADY WRITTEN DOWN. If the design is
recorded -- a docstring, the sound catalog, ontology.md -- quote it and
move on. Needing a bench to find out whether behaviour is intended means
the intent is not written anywhere, and THAT is the finding: record it,
then answer. What must never happen is asserting "by design" without
either evidence or a source, which is how a real bug gets closed.

WHAT THIS RULE MUST NOT DO is filter on how a report sounds. "Not sure if
those curves are supposed to be there" was a chain of bends that damaged
a load; "the U key didn't keep up" was a readout frozen three minutes at
a time. Both read as tier 3 and were tier 1 and 2. Judge the cost after
looking, not the wording before.

ASK FOR THE LOG EARLY on anything about speed, traffic or the assists.
Two wrong diagnoses of Brandon's cruise report came from reading code;
his log settled it in minutes. A report of that kind with no log is
worth one cheap check and then a request, not an investigation.

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
