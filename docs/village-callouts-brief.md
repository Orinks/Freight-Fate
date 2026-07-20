# Village callouts brief: name the towns a leg passes through

For Oatis, own worktree off feat/career-1.9 (tip 8111651+), branch
`map/village-callouts`. Owner approved 2026-07-20. `[skip changelog]`
on data commits; ONE player bullet on the game-side commit.

## Why

Camp Verde-Payson drives straight through Strawberry and Pine: their
35 mph zones are baked (mi ~37-57) and now end honestly, but nothing
speaks their names -- the leg's landmarks are the forests and the East
Verde River. A limit drop with no town attached reads as arbitrary.

## The sweep (map half)

- For every leg: OSM `place=village|town|hamlet` on or near the
  corridor via the self-hosted Overpass
  (`OVERPASS_URL=http://localhost:12347/api/interpreter` -- the public
  endpoint is the slow trap). Snap to route mileage.
- Bake as roadside callouts (same machinery/fields as landmarks,
  category `village`), spoken line "Entering {Name}" composed at bake
  time -- NEVER raw OSM text player-side. Source notes per record.
- Pair with limits: where a baked speed zone (<=45) starts within ~1.5
  mi after the village point, place the callout just BEFORE the zone
  start so the name explains the drop.
- Skip places already route cities; dedupe against existing landmarks.

## Game half (small)

Settings toggle "Village callouts", OFF by default, gating only these
callouts (follow the existing chatter-switch pattern). Spoken result
tested; manual + settings help text updated.

## Gates and handshake

Sharded world edits via tools/world_source.py only; `index_world.py
--check`; world/overlay suites + full suite; refresh_map_data
--limits-lint zero. When green: push branch, write
`C:/dev/Freight-Fate/logs/oatis-villages-done.json` (branch, commit,
villages added per state, paired-with-zone count, notes). Phil reviews
against this brief and merges. NEVER work in the main checkout.
