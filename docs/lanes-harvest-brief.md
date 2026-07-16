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

## Sequencing

Worktree, per the no-parallel-world-data rule. Not alongside any other
bake job. Overpass health first if the extracts prove insufficient.
