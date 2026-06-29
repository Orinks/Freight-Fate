# Traffic Bubble Manager Design

## Goal

Build an experimental NPC traffic layer that feels richer than one-off traffic
cues while staying practical for Freight Fate's audio-first driving model. The
first implementation should replace the current simple NPC list with a
dedicated traffic bubble around the player's truck, and it should leave a clear
path toward a fuller lane and behavior system later.

This work starts from `codex/player-experience-integration`, where `NPCVehicle`,
traffic-pressure cues, adaptive-cruise following, and deterministic harness
traffic tests already exist.

## Non-Goals

- Do not build a visual traffic simulator.
- Do not add intersection right-of-way, city-grid pathfinding, or route-wide
  vehicle persistence in this first slice.
- Do not make traffic constantly talk. Real-time traffic speech should stay
  sparse, actionable, and tied to driving decisions.
- Do not merge the experimental branch into `dev` until it has been manually
  reviewed and playtested.

## Recommended Approach

Use a traffic bubble manager. A `TrafficManager` owns a small moving area around
the truck, such as one or two miles behind and five to ten miles ahead. It
spawns, updates, removes, and queries nearby traffic vehicles. The rest of the
game asks the manager simple questions instead of reaching directly into a raw
vehicle list.

This is the best fit for the current game because the player experiences the
road through audio cues, status menus, adaptive cruise, and hazards. The bubble
can create meaningful nearby situations without simulating every vehicle across
the full route.

## Architecture

### TrafficManager

`TrafficManager` is owned by `Trip`. It receives the route, truck, weather,
time-of-day, hazard scale, and deterministic seed context it needs to create and
update traffic.

Responsibilities:

- spawn vehicles ahead of the truck based on highway context;
- update nearby vehicle speed, lane, and intent each trip tick;
- remove vehicles that fall far behind or leave the forward bubble;
- expose the nearest lead vehicle for adaptive cruise;
- expose status lines for the driver tablet and driving status;
- produce traffic situations that the trip can convert into events;
- preserve deterministic behavior for tests and playtests.

### TrafficVehicle

`TrafficVehicle` is the richer successor to `NPCVehicle`.

Initial fields:

- stable key;
- route position in miles;
- lane relative to the player route;
- current speed;
- target speed;
- vehicle class, such as car, box truck, semi, or service vehicle;
- intent, such as cruising, following, passing, merging, yielding, or braking;
- behavior flags used for deduping spoken cues.

The first implementation can keep compatibility properties such as `at_mi`,
`end_mi`, `lane_text`, and `reason` so existing call sites can migrate
incrementally.

### TrafficLane

The first lane model should stay lightweight: relative lanes are enough for the
current audio game.

Examples:

- `0`: player's lane;
- `-1`: left lane;
- `1`: right lane or merge lane.

The design should avoid hardcoding "one lead vehicle ahead" as the whole
worldview. Even the first version should allow multiple nearby vehicles, because
that is the bridge toward a fuller lane/behavior rewrite later.

### TrafficSituation

`TrafficSituation` represents what the gameplay layer needs to know now. It is
not a speech string by itself; it is a structured situation that can become
speech, status text, adaptive-cruise behavior, or a hazard.

Initial situations:

- lead vehicle ahead;
- merging vehicle ahead;
- passing traffic nearby;
- brake lights ahead;
- traffic bunching near exits, merges, or construction.

## Gameplay Behavior

The first experimental slice should make traffic matter without making it noisy.

Real-time cues should only fire when traffic affects a driving decision:

- a vehicle merges into the player's lane;
- a lead vehicle is close enough for adaptive cruise to react;
- brake lights create a closing-speed risk;
- traffic bunching makes an exit, merge, or construction taper harder.

Status/menu views can be more descriptive. They may report nearby traffic,
lanes, speed, and intent because the player explicitly asked for reviewable
information.

Adaptive cruise should continue to use the nearest relevant lead vehicle, but it
should receive that answer from the manager instead of scanning raw vehicle
lists. Future work can add multi-vehicle following, passing, or lane-availability
logic without changing the cruise API again.

## Audio Rules

Traffic speech should be short and actionable.

Examples:

- "Brake lights half a mile ahead."
- "Merging car ahead, leave room."
- "Truck passing on your left."
- "Traffic bunching near the exit. Signal early."

Rules:

- do not repeat the same vehicle cue every few seconds;
- critical traffic warnings can interrupt;
- ambient traffic cues should queue;
- status/menu wording can be longer than live driving cues;
- cue text should avoid visual-only assumptions and identify position, lane, or
  action in plain language.

## Testing Strategy

### Pure Manager Tests

Add low-cost tests around `TrafficManager` before broad playtests:

- deterministic spawning from the same seed and route;
- vehicles are removed after leaving the bubble;
- merging intent moves a vehicle into the player's lane at the right range;
- braking intent lowers target speed and creates a lead-vehicle context;
- multiple vehicles can coexist without losing nearest-lead selection;
- weather, rush hour, and metro context affect density or speeds.

### Trip Integration Tests

Update existing trip tests so `Trip` exposes traffic context through the manager
without changing player-facing behavior unexpectedly:

- adaptive cruise follows manager-provided lead vehicles;
- status lines describe nearby traffic;
- traffic cues dedupe correctly;
- traffic pressure remains available for exits, merges, and construction.

### Harness Tests

Keep deterministic harness helpers for known traffic situations. Add at least
one transcript-backed playtest for a manager-created merging or braking
situation.

The harness must remain headless. Any test that constructs `App` should keep
`FREIGHT_FATE_NO_SPEECH=1` and SDL dummy drivers active.

## Migration Plan

1. Introduce traffic dataclasses and manager without removing the existing
   public trip methods.
2. Change `Trip` to create and update `TrafficManager`.
3. Re-route `traffic_context`, `traffic_target_speed`, `npc_traffic_status`, and
   traffic cue checks through the manager.
4. Update harness helpers to inject manager traffic scenarios.
5. Remove direct mutation of `trip.npc_vehicles` from tests once manager helpers
   exist.
6. Only after tests pass, decide whether to delete or keep compatibility aliases
   for `npc_vehicles`.

## Open Questions For Later

- Should traffic state be saved mid-trip, or is it acceptable to regenerate the
  bubble on resume?
- Should lane drift settings affect how much lane-relative traffic is spoken?
- Should traffic density be player-configurable separately from relaxed mode?
- Should traffic manager events contribute to achievements differently from
  traffic-pressure events?

These do not block the first experimental implementation.
