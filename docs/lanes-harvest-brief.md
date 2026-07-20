# Lane-data harvest brief (Job 3) — specced 2026-07-16

Owner-approved 2026-07-16 (bedtime design session): real lane counts and
lane-level facts from OSM, baked with the same offline pipeline, shard
pattern, and determinism rules as the dense maxspeed sweep (Job 2). This
is the data half of the steering/lane realism work; no gameplay consumer
ships in this job. Follow the rules exactly and record what shipped in
ROADMAP.md per AGENTS.md.

## Context

The game models discrete lanes but invents their count. OSM carries the
truth: `lanes`, `lanes:forward/backward`, `turn:lanes`,
`destination:lanes`, `change:lanes`, `overtaking`, `oneway`, and the
`highway=` class. Harvesting them buys, in later wiring jobs: real lane
counts spoken and enforced (four lanes through Albuquerque, two-plus-two
rural), REAL lane drops as genuine merge events at real mileposts,
exit-only lane warnings ("the right lane becomes exit only"), keep-right
pressure that knows how many lanes exist, no-passing zones on two-lane
surface roads, and the lane grammar the steering design (offered to
Josh) will need. Bake now, wire later.

## Sources and pipeline

- Offline Geofabrik PBF extracts first (`D:\ors\files\`, pyosmium — the
  escape-ramp harvest pattern); self-hosted Overpass (`ff-overpass`,
  port 12347) for anything the extracts lack. Health-check before
  relying on it; recovery runbook in project memory.
- **The self-hosted Overpass extract is tag-filtered and is NOT a
  general OSM mirror** (learned the hard way, 2026-07-20: the village
  sweep found `node["place"]` returns zero nationwide because the
  extract kept only roads, landmarks, and truck POIs). A healthy status
  endpoint tells you the server is up, not that it holds the tags you
  need — probe for an actual known feature before trusting a nil result.
- **Rebuild the extract for this job, and widen it while you are in
  there** (owner, 2026-07-20). If it is being rebuilt for lanes,
  interchanges, and `destination:*`, include `place=village|town` in the
  same pass: that retires the bespoke `tools/extract_osm_places.py`
  written during the village sweep and leaves one query path instead of
  two. Note this is gated on the Crucial RAM RMA — see
  [[project-overpass-selfhost]].
- Sample along each leg's real routed geometry like Job 2, but lane
  facts change at way boundaries, not continuously: record a step
  function of transitions, not dense samples.

## What to harvest, per leg direction of travel

1. **Lane count step function.** Prefer `lanes:forward`/`backward` for
   the travel direction; on `oneway=yes` ways take `lanes` whole; on
   undivided two-way ways without direction tags, `lanes` split evenly
   rounding down (a bare `lanes=3` two-way is 1 for us plus a center
   context — record 1 and flag `estimated`). Clamp 1..6; an absurd tag
   (0, negative, non-numeric) is logged and skipped, never baked.
2. **Lane drops.** Wherever the count decreases along travel, derive a
   merge record: at_mi, from-count, to-count, side if `turn:lanes` or
   way geometry proves it (merge-left vs merge-right), else side
   unknown. Only real transitions — never synthesized.
3. **Exit-only lanes.** Near baked interchanges, a `turn:lanes` entry
   whose rightmost lane carries only right-ish arrows into a
   motorway_link marks that lane exit-only: record interchange key,
   at_mi where the marking starts, and lanes_total there.
4. **No-passing / no-change zones** (surface legs): `overtaking=no`
   and restrictive `change:lanes` become [start_mi, end_mi] zones.
5. **Carriageway class per segment:** divided (separate oneway ways)
   vs undivided two-way, from the way topology and `oneway` — the
   future oncoming-traffic tier needs to know which roads have it.
6. **destination:lanes** raw strings, stored verbatim per transition
   where present (future gantry speech; no processing this job, and
   never player-facing raw — OSM tag text must not leak into speech).
7. **`destination` and `destination:ref` on the `motorway_link` ways
   themselves** (added 2026-07-20, owner design session). These are the
   guide-sign legend — `destination=Nashville`,
   `destination:ref=I-40 West` — and they are what turns an interchange
   callout into "stay left for I-40 toward Nashville" rather than a bare
   exit number. Item 6 alone does not buy this: `destination:lanes` says
   which lane, `destination` says the city, and the sentence the owner
   asked for needs both. US interstate coverage of these tags is good.
   Harvest per interchange, per direction of travel, under the same
   verbatim-storage and never-raw-in-speech rule as item 6.

## Storage

`world_data/us/gameplay/lanes.jsonl`, one meta header line (schema
version, data_version hash, params) then per-leg records, delta-encoded
step functions with `[at_mi, next)` semantics exactly like
`speed_limits.jsonl`. Deterministic: stable key ordering, sorted
records, byte-identical re-runs on unchanged inputs. Source notes per
the data rules. Absence policy is explicit: a stretch with no lane tag
bakes NOTHING (runtime heuristics stay in charge there) — never bake a
guessed count without an `estimated` flag.

## Acceptance

- Coverage report printed by the bake: percent of interstate miles with
  a real (non-estimated) lane count; expect motorway coverage to be
  high, surface coverage patchy — report, do not pad.
- Spot checks: I-40 through Albuquerque shows 3+ lanes somewhere in the
  metro; rural I-40 Arizona shows 2; at least one derived lane drop
  verified against aerial/OSM by hand and named in the PR body.
- A lanes linter (same spirit as the anchor linter, added as a test on
  the fresh bake): no count outside 1..6, no zero-length zones, no
  drop record without a real transition behind it, monotone at_mi.
- `tools/index_world.py --check`; `uv run pytest tests/test_world.py
  tests/test_world_overlay.py`; then full gates.
- `[skip changelog]` is correct for this job — data with no consumer is
  not player-facing yet; the wiring jobs carry the changelog entries.
  ROADMAP: check off the lane-counts bullet with what actually shipped.

## For the wiring jobs: advisory may guess, punitive may not

Recorded here because it constrains what this bake must flag, not just
what it must collect (owner design session, 2026-07-20).

The planned lane mechanic makes a wrong lane cost the player a wrong
exit, with the GPS routing them back. That is the right call on realism
and it is the first mechanic where **a gap in our data becomes a penalty
against the player.** If `turn:lanes` is absent and we guess, a driver
who did everything right gets pulled off the interstate — and a blind
player has no way to tell our missing tag from their own mistake. The
truck-access sweep drew this line already: a cue with no real referent
is refused.

So:

- **Enforce wrong-lane consequences only where lane data is real
  (non-`estimated`).** Everywhere else the guidance degrades to the side
  it can prove — "stay left" — and costs nothing if ignored.
- **Never speak a lane ordinal we did not harvest.** "Take the second
  lane" requires a real `turn:lanes`/`destination:lanes`; with only a
  count and a side, say the side.
- This makes the `estimated` flag from item 1 load-bearing at runtime
  rather than merely informational, so it must be baked accurately and
  never defaulted to "real" for a tidier record.

Advisory guidance may run on partial data. Punitive guidance may not.

### The owner's closed loop resolves this (2026-07-20)

Owner pushed back: a sighted driver who misses an exit also has to get
back on, so why is a consequence unfair? He is right, and the objection
above was aimed slightly wrong. The issue is not that a penalty exists —
it is **information parity**. A sighted driver had signs, lane arrows,
and the traffic around them; they were told and did not act. Our player
has only what we speak. A penalty is fair exactly when we told them.

His design supplies the telling, and it is better than what ships today.
Current exits announce the required lane once, several miles out, and
never say whether the driver is actually **in** it — the one fact a
blind driver cannot check. Modern lane-level GPS closes that loop, and
so should we:

- Announce the exit and required lane once, at distance.
- Then compare **required lane against the lane the truck is actually
  in** — the sim already models this, so it needs no harvested data.
- Speak again only when the driver is **wrong**, escalating as the exit
  closes ("still need the right lane" → "right lane now").
- Confirm once at the commit point when they are right, then go quiet.

Establish the contract explicitly in the manual: **the game will tell you
if you are in the wrong lane, so silence means you are fine.** Silence is
only usable as information when the player knows it would have been
broken. That is the same contract the rest of the warning layer already
keeps, and it is what a real co-driver does — nothing when you are set,
insistent when you are not ([[feedback-amplify-real-cues-never-invent]]).

With that loop running, missing the exit **is** the driver's doing, and
the reroute is honest consequence rather than a penalty for our silence.
The restriction above then narrows usefully: it governs the lane
*ordinal* ("second lane"), which needs harvested `turn:lanes`, not the
side, which we can already prove.

## Sequencing

Worktree, per the no-parallel-world-data rule. Not alongside any other
bake job. Overpass health first if the extracts prove insufficient.
