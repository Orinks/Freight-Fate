# Surface Roads Plan

This is the design plan for surface streets -- the named local roads that
connect highways to freight facilities, terminals, and city services. Today
those trips exist as a single synthetic leg ("Deadhead 2.1 miles on unnamed
public road"); the goal is audio-first local driving on real named streets,
with turns, local speed zones, and a continuous drive from the destination
exit ramp to the facility gate.

It builds on the approach-data contract described in
[`docs/route-stop-data.md`](route-stop-data.md) and the build pipeline in
[`docs/osm-routing-plan.md`](osm-routing-plan.md). Everything here keeps the
offline-first, deterministic posture: builders read cached Geofabrik extracts,
runtime reads checked-in JSON, no network on the game loop.

## Where The System Stands Today

The runtime already has a tiered local-route ladder in
`World.facility_approach_route` (`src/freight_fate/data/world_services.py`):

1. **Turn-level segments** -- multi-leg local route with per-segment road
   names, miles, spoken cues, and speed limits. Only 6 facilities qualify:
   the source batch was bounded to Illinois/Indiana/Ohio and a
   high-confidence facility-type set.
2. **Source-backed endpoint** -- real approach miles plus one road name.
3. **Local approach** -- nearest-road snap: one road name, estimated miles.
4. **Synthetic fallback** -- seeded miles and a type-generic label
   ("facility access road").

Data files (all build-time, checked in):

- `facility_approaches.json` -- 2,088 facilities; road names inherited from
  `local_approaches.json`.
- `local_approaches.json` -- 2,748 targets (facilities + city services),
  nearest-road snapped from state PBF extracts.
- `local_geometry.json` -- turn-level paths for 459 city services.
- `facility_endpoints.json` -- source-backed gate/dock coordinates
  (1,642 of 2,088 source-backed).

The pre-regen weakness was naming: the nearest-road snap let an unnamed
service way beat a named street a few meters farther, so 39% of approaches
said "unnamed public road" even where OSM had a perfectly good street name.
The builder now prefers the nearest *named* road inside the same 1.25-mile
search radius (`tools/build_local_approaches.py`), and the facility builder
inherits the fix on regeneration.

## Goals

1. **Every approach names a real street** where OSM knows one. (Data-only;
   no engine changes. Largely delivered by the named-road snap fix.)
2. **Multi-segment local drives**: the deadhead and the final approach drive
   the turn-level segment list -- "Turn right onto Palm Street", per-segment
   speed zones, distance callouts per segment.
3. **A continuous arrival**: destination exit ramp flows into the surface
   chain and ends at the facility gate, replacing the "Pulling into..."
   teleport. Mirrored on departure: gate, surface chain, on-ramp merge.
4. **Coverage grows honestly**: turn-level data expands beyond the Midwest
   batch, and coverage stats stay pinned in tests so regressions are loud.

## Phases

### Phase 1 -- Real names everywhere (data pass)

Re-run `build_local_approaches` (named-road preference) and
`build_facility_approaches` over all cached state extracts. No runtime
change; the deadhead and approach announcements pick up real street names
through the existing ladder. Update the pinned coverage tests to the new
counts and keep the `named_road` coverage counter as the visibility metric.

### Phase 2 -- Drive the segments (DELIVERED)

Shipped on the lanes/realism branch: `Leg` carries the baked segment cue and
street speed (`local_cue`, `local_speed_mph`), the route builders populate
them for tier-1 segments, boundary cues speak the baked maneuver verbatim
with block-aware distances, per-street speed zones replace the blanket
access-road limit (merged over same-speed runs), same-city boundaries no
longer announce a city passage, and highway merge/exit pressure language is
suppressed on surface routes. `tests/test_surface_streets.py` pins the
behavior. The original gap list, for the record:

`Trip` already models a route as a list of `Leg`s, and tier-1 approaches
already return multi-leg routes. What is missing:

- **Turn cues at leg boundaries.** At each segment boundary, speak the baked
  cue ("Turn right onto Palm Street; half a mile") through `say_event`,
  reusing the local-turn sound cue support that shipped with the checked-in
  local direction data.
- **Per-segment speed zones.** The builders bake `speed_mph` per segment
  (25 named / 15 unnamed). Surface segments should register as a zone
  (like facility access roads today) so adaptive cruise declines and the
  speed-limit announcements match the street.
- **Local pacing.** Short segments under time compression can vanish;
  surface legs should pin the effective time scale near the low end
  (`Trip.effective_time_scale` already ramps by speed, which mostly covers
  this -- verify with the harness, do not special-case first).

Scope guard: steering stays abstract. Turns are spoken cues plus a steering
prompt window (same interaction family as the exit-lane setup), not a lane
geometry change. The discrete two-lane prototype is a separate, unlanded
design and this plan must not depend on it.

### Phase 3 -- Chain highway and surface

Today `DrivingState` runs one route object per phase (deadhead route, or the
highway route) and the arrival is a scripted stop. Chaining:

- On the delivery side, when the destination exit ramp completes, push the
  facility's tier-1 surface route as the active trip tail instead of the
  scripted arrival, ending at the gate zone.
- On the pickup side, start the deadhead on the terminal's surface route and
  end it at the shipper check-in rather than the current single-leg drive.
- Save compatibility: an active trip snapshot gains an optional
  `surface_chain` marker; old saves resume exactly as before (single-leg).

### Phase 4 -- Intersections (optional, later)

Stop signs / signals on surface segments, junction decision prompts, and
traffic pressure at intersections. Only worth designing after Phase 2 ships
and the pacing of local drives is proven in playtests.

## Data Expansion

Raising tier-1 coverage from 6 facilities means re-running the bounded
road-snap batch with a wider net:

- Extend `--states` beyond Illinois/Indiana/Ohio batch by batch (the full
  50-state extract cache is ~23 GB and already local).
- Revisit `HIGH_CONFIDENCE_TYPES`: grain elevators, ports, and cold storage
  are currently excluded but have source-backed endpoints at high rates.
- Watch the size budget: `facility_approaches.json` ships in the release
  executable via the baked-world pipeline; keep the per-facility segment
  lists bounded (the builder already caps route length at 18 miles).

## Verification

- The headless harness (`tools/playtest.py`, `tests/playtest_harness.py`)
  is the review channel: a sweep across one corridor per highway system
  plus a new-career pickup drive should show named streets, turn cues, and
  no "unnamed public road" in covered cities.
- Pinned coverage tests assert the counts (total approaches, named share,
  turn-level count) so a bad regen fails CI instead of shipping silence.
