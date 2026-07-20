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

- For every leg: OSM `place=village|town` on or near the
  corridor via the self-hosted Overpass
  (`OVERPASS_URL=http://localhost:12347/api/interpreter` -- the public
  endpoint is the slow trap). Snap to route mileage.
  **No hamlets** (owner, 2026-07-20): a hamlet is a handful of houses,
  and naming one as though the driver arrived somewhere is the same
  false promise the truck-access sweep removed.
- **Bake WIDE, display TIGHT** (owner, 2026-07-20). Collect out to a
  10-15 mi catchment and store each place's offset distance and whether
  it is on-route; let the tight radius be a display rule, not a
  collection rule. The ride-along callout below uses on-route ~0.5 mi
  where "entering" is literally true, but the planned "where am I" key
  answers with whatever is genuinely nearest at any distance -- on I-40
  the honest answer may be "Winslow, eleven miles ahead", and a 0.5 mi
  collection rule would make that key useless exactly where it is most
  needed. One bake, one distance field, two consumers.
- Interstates bypass towns rather than run through them: use the wider
  radius and phrase them as passing, not entering.
- Bake as roadside callouts (same machinery/fields as landmarks,
  category `village`), spoken line "Entering {Name}" composed at bake
  time -- NEVER raw OSM text player-side. Source notes per record.
- Pair with limits: where a baked speed zone (<=45) starts within ~1.5
  mi after the village point, place the callout just BEFORE the zone
  start so the name explains the drop.
- Skip places already route cities; dedupe against existing landmarks.

## Game half (small)

Settings toggle "Village callouts", **ON by default** (owner overrode
the original OFF, 2026-07-20), gating only these callouts (follow the
existing chatter-switch pattern). Spoken result tested; manual +
settings help text updated.

Rationale for the flip, which also sets the shape: the name **rides the
limit announcement the game already makes** -- "Entering Strawberry.
Speed limit drops to 35." -- rather than firing as a second event. It
costs no extra interruption and supplies the context that stops the
drop reading as arbitrary, so defaulting it off would suppress the
explanation for something the game announces regardless. The toggle
stays for anyone who wants the bare limit call.

## Gates and handshake

Sharded world edits via tools/world_source.py only; `index_world.py
--check`; world/overlay suites + full suite; refresh_map_data
--limits-lint zero. When green: push branch, write
`C:/dev/Freight-Fate/logs/oatis-villages-done.json` (branch, commit,
villages added per state, paired-with-zone count, notes). Phil reviews
against this brief and merges. NEVER work in the main checkout.
