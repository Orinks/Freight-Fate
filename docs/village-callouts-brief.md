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

## Follow-ups on the shipped bake (owner review, 2026-07-20)

The sweep landed on `map/village-callouts` (26,894 places, 1,280 legs,
2199 tests green). Two changes came out of reviewing it. Both are small
and neither needs a re-bake.

### 1. Pairing overrides radius

The single 1.5 mi display radius does two jobs badly. Measured on the
shipped bake:

| radius | speakable | share |
| --- | --- | --- |
| 1.0 mi | 6,128 | 22.8% |
| 1.5 mi | 7,899 | 29.4% |

Tightening to 1.0 removes ~1,771 announcements but also silences ~49
villages that sit right before the limit drop they explain -- the
highest-value records in the bake. Trading an explanation away to save
flavour is backwards, so **split the rule instead of moving the number**:

- **Unpaired (flavour) village: 1.0 mi.** "Entering" should mean the
  driver is actually in it; 1.5 was loose.
- **Village paired with a speed-zone drop: out to ~2.0 mi.** It earns
  its place by explaining something. The existing offset phrasing keeps
  it honest -- "Passing Strawberry" where the road only skirts the town,
  "Entering" where it runs through.

Net: roughly 23% less chatter than today with **zero explanations lost**.
One constant plus one condition.

### 2. Fix endpoint snapping before "where am I" reads this data

8.6% of records are pinned to a leg endpoint (`at_mi` exactly 0.0, or
within 0.05 of leg end). This is legitimate clamping for places near the
origin/destination city, and it is **harmless today** -- verified that
zero endpoint-pinned records fall inside the display radius, so none of
them speak.

It stops being harmless the moment [[project-where-am-i-key]] reads the
far field, because those are exactly the distant records the key exists
to report, and their along-route distance is a clamp artifact rather
than a measurement. **Fix the snap before the key ships, not after** --
a key whose whole job is answering "where am I" must not answer with a
distance the bake invented.

Related: the per-leg cap of 30 truncates the far field on 569 legs.
Nothing announceable was lost, but the key will want it raised.
