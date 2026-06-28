# Gameplay And Truck Realism Design

## Goal

Make Freight Fate feel like driving a real heavy truck within an audio-first,
2-D design. The player should be a truck driver first: planning speed, managing
momentum, reading the road, and handling the consequences of weight, weather,
grades, exits, traffic, and cargo.

Realism should change driving decisions. Avoid adding detail that only creates
accounting chores or hidden simulation. The sweet spot is: the player drives
differently because this truck, load, route, weather, and deadline matter.

## Pillar 1: Speed Planning And Braking

Realistic mode should make speed planning the heart of truck driving. Freight
Fate already has real speed data, route context, grades, weather, traffic,
exits, and enforcement; this slice should make those systems converge into one
clear question: am I setting up the truck early enough?

The player should need to manage speed before the problem arrives:

- Slow before exits, ramps, construction tapers, traffic queues, weigh stations,
  and facility or local roads.
- Use service brakes carefully, because repeated hard braking builds heat and
  uses air.
- Use engine brake and lower gears to control descents.
- Feel weight through stopping distance and acceleration, especially with heavy
  cargo.
- Hear enough advance warning to make a realistic decision, without the game
  driving for them.

Realistic mode consequences should be meaningful: missed exits, brake fade,
traction loss, cargo damage, speeding enforcement, or late arrivals. Relaxed
mode should keep the same driving model but widen timing, reduce damage, and
give earlier cues.

Speed guidance should come from actual route context where possible. Real posted
speeds, local-road transitions, ramps, grades, traffic pressure, and
truck-relevant restrictions should shape the cues. Avoid generic "slow down
soon" wording when the route can say "destination exit in one mile,"
"construction taper ahead," "downgrade continuing," or "local street approach."

## Pillar 2: Powertrain And Grade Control

The truck should feel alive under load without becoming a full mechanical
simulator.

Realistic mode should reward using the truck correctly:

- Heavy cargo climbs slower, downshifts sooner, and loses more speed on grades.
- Descents require planning: choose a safe speed early, use engine brake, and
  avoid riding service brakes.
- Manual transmission rewards correct gear choice, clutch use, and staying in a
  useful RPM band.
- Automatic remains accessible, but makes sensible heavy-truck decisions: hold
  lower gears under load, avoid frantic shifting, and cooperate with engine
  braking.
- Cruise control is useful on open highway but should not be trusted blindly on
  grades, traffic, construction, exits, or local roads.

Player-facing cues should stay practical: "Grade ahead, use engine brake,"
"Too fast for this descent," "Downshift to hold speed," or "Brake heat rising."
Avoid dense technical chatter unless the player asks for detailed status.

Relaxed mode can simplify the consequences with less brake heat, more forgiving
shift timing, and softer speed-loss penalties, while still preserving the
feeling that a loaded truck needs planning.

## Pillar 3: Routing And Road Context

Routing realism should support driving decisions, not just map accuracy. The
route should feel truck-plausible:

- Prefer truck-legal, major freight corridors where data supports that choice.
- Use real posted speeds and truck-specific speed limits when available.
- Treat local approaches, facility roads, ramps, weigh stations, service plazas,
  construction zones, and city-service drives as different driving contexts.
- Keep highway miles, ramp or local approach miles, and facility approach miles
  clearly distinct in speech.
- Avoid pretending representative or fallback facility coordinates are exact
  gates or docks.
- Use road context to shape speed cues: local road, ramp, merge, work zone,
  downgrade, urban limit, open interstate, toll plaza, or inspection lane.

The player should trust that slowing, exiting, merging, or preparing for a
facility comes from the road they are actually driving, not from a generic event.

Truck restrictions and dimensions are an advanced layer. Height, weight, hazmat,
and trailer-specific restrictions are valuable only when the game has data good
enough to avoid fake precision.

## Pillar 4: Route Commitment And Exits

Exits should stop being a discrete "press X to take exit" action. The player
should take an exit by driving correctly.

New model:

- GPS announces the exit and destination or ramp context.
- The player slows and positions for the exit.
- The truck takes the ramp automatically when it reaches the exit marker if
  route commitment, speed, and lane setup are valid.
- If setup is bad, the truck misses the exit and gets spoken recovery guidance.
- X becomes a turn signal or route-intent key, not the exit action itself.
- In realistic mode, missing speed, lane, or intent requirements has real
  consequences.
- In relaxed mode, the game can infer intent more generously and widen the lane
  and speed windows.

This makes local approaches and facility entrances more natural later. The
player follows a route, prepares for turns, ramps, and entrances, and the game
transitions when the driving setup is believable.

The first implementation slice should avoid ripping out every stop interaction
at once. Start with destination exits: auto-trigger the ramp when setup is valid,
while X becomes signal or cancel signal. Later slices can extend the same model
to rest stops, ramps, weigh stations, local turns, and facility gates.

## Pillar 5: Trailer And Load Awareness

The player should gradually feel that they are pulling a trailer:

- Heavy loads increase acceleration time, braking distance, brake heat, and
  grade difficulty.
- Fragile or high-value freight makes harsh braking, collisions, and rough
  handling more consequential.
- Reefer, flatbed, bulk, and dry van freight can eventually have different
  handling or risk profiles.
- Crosswinds, slick roads, bad lane control, and abrupt maneuvers can create
  trailer sway or cargo-shift risk.
- Local roads, ramps, and facility approaches should feel tighter and slower
  than open highway.
- Trailer ownership and condition can matter later, but driving feel comes
  first.

Feedback should be sensory and actionable: "Trailer tugging in the wind," "Load
shifted after the hard stop," "Heavy trailer pushing on the downgrade," or
"Ease off; cargo took a hit." Avoid hidden math that appears only at settlement.

Relaxed mode should soften cargo and trailer consequences but preserve the cues,
so players still learn good truck handling.

## Realistic Vs Relaxed Mode

The mode split lets the game become more honest without becoming inaccessible.

Realistic mode:

- Honest mass, braking, grade, weather, traffic, lane, and trailer
  consequences.
- Late braking and poor setup can cause missed exits, brake fade, cargo damage,
  inspections, traction loss, or late delivery.
- Cues are fair but not hand-holding.
- Player decisions carry meaningful cost.

Relaxed mode:

- Same truck model and same route context, so it still feels like driving a
  truck.
- Earlier warnings, wider timing windows, softer damage, slower brake-heat
  buildup, and more generous exit or intent inference.
- Lower hazard and enforcement pressure where appropriate.
- Air brakes, weather, mass, and speed planning remain active.

Relaxed mode is not arcade mode. It is more forgiving truck mode.

## Playtesting And Verification

Playtest truck realism with scenario saves instead of long grinds:

- Light empty or bobtail route: should feel nimble but still truck-like.
- Heavy load on flat interstate: slow launch, steady highway momentum, longer
  stop.
- Heavy load with downgrade: engine brake and speed planning matter.
- Exit approach: no "press X to take exit"; speed, lane, and intent determine
  success.
- Construction taper: advance cue, braking plan, merge or slowdown, enforcement
  consequence.
- Wet or snowy route: safe speed and braking decisions change.
- Local facility or city-service route: slower, tighter, and more
  route-context-driven.
- Relaxed-mode replay of the same scenarios: same truck identity, softer
  consequences.

Automated tests should cover transition rules and spoken feedback:

- Valid exit setup auto-takes the ramp.
- Bad speed, lane, or intent misses the exit.
- Relaxed mode widens exit acceptance.
- Heavy load increases braking or grade difficulty.
- Engine brake reduces speed gain on descents.
- Speech names why a maneuver succeeded or failed.
- No route cue depends on visual-only information.

Manual verification should focus on one feel question: did I have to think ahead
like a truck driver?

## Recommended First Slice

Implement route commitment and exit realism first. It removes one of the most
gamey mechanics, connects directly to speed planning and route context, and can
be verified with focused driving tests. The first code slice should target
destination exits only:

- GPS announces the destination exit as it does today, but does not say "press X
  to take the exit."
- X acts as a right-turn signal or route-intent control.
- A valid setup at the exit marker automatically takes the ramp.
- Invalid setup misses the exit with clear spoken recovery.
- Relaxed mode infers intent more generously.

After that slice proves the feel, extend the same model to ordinary route stops,
weigh stations, local street turns, and facility gates.
