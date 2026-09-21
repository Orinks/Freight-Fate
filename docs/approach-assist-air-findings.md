# Approach assist runs the truck out of air

Status: FIXED.

Branch: `fix/approach-assist-air`, forked from `b123bb9c` on
`feat/corner-speed-geometry`.

## The defect

- `states_driving_facility::test_the_approach_assist_stops_the_truck_on_a_facility_street_chain`
- `states_driving_approach_sweep::test_the_approach_assist_stops_the_truck_at_every_kind_of_destination`

Reproduced: Aberdeen Company Yard, spring brakes applied from low air, truck
stranded 8726 ft short of the gate.

## What I measured (instrumented trace, Aberdeen chain, 74520 frames)

Trace fields: position, speed, throttle, keeper trim, brake, primary air,
gear, keeper target, ease target, `keeper_snub`, curve servo, `ramp_mi`,
`transition_assist_active`, arrival latch.

Phase totals:

| phase | frames | air |
| --- | --- | --- |
| highway + destination ramp | 3198 | 125.0 -> 125.0 (no loss) |
| facility street chain | to spring-brake trip | 125.0 -> 39.9 |

So the air is spent entirely on the street chain, with `ramp_mi = None` and
`transition_assist_active = false`. Two episodes:

- frames 1500-2000: 23 mph, keeper target 8.4, 46 brake re-applications per
  500 frames. Air 114.6 -> 107.1, recovered by the compressor.
- frames 4000-5000: 7.33 mph, keeper target 8.35, **75 brake re-applications
  per 500 frames (9 per second)**. Air 98.3 -> 71.7 -> 45.1 -> spring brakes
  at 40.

Over the whole chain: **308 rising brake edges**, 61.6 of commanded brake in
total, i.e. 277 psi of primary air demanded against a compressor that makes
4 psi/s at idle.

### The mechanism is NOT the hysteresis band

`keeper_snub` rose **once** in the 1200 frames of episode B while the brake
rose 179 times. The snub does not cycle. It latches at 0.20 and stays there.

The raw frames show a 7-frame pattern, repeating:

```
v=7.33 thr=0.00 brk=0.20   <- update_keeper reached its controller
v=7.32 thr=0.04 brk=0.09   <- input ramp bleeds the brake, driver back on the pedal
v=7.32 thr=0.07 brk=0.00
v=7.33 thr=0.11 brk=0.00
v=7.34 thr=0.15 brk=0.00
v=7.35 thr=0.18 brk=0.00
v=7.36 thr=0.22 brk=0.00
v=7.33 thr=0.00 brk=0.20   <- application RE-MADE from zero: 4.5 psi again
```

`update_keeper` has an early return for a driver on the accelerator
(`if accelerating { return; }`, the manual override). The input pass at the
top of `update_frame` ramps `truck.brake` down every frame nobody commands
it, and it runs BEFORE `update_keeper`. So on every overridden frame the
keeper's held application is not paused, it is **dropped**; on the next frame
the keeper runs, `brake.max(keeper_snub)` re-makes it from zero, and
`consume_brake_air` charges a fresh `air_loss_primary_per_application_psi`
(4.5) for the rising edge. Held, that snub costs 0.25 psi/s of leakage.
Fanned at 9 Hz it costs about 8 psi/s, twice what the compressor makes.

FMCSA's CDL manual, Section 5 (Air Brakes), names this on a real truck: do
not fan the brakes, because each application spends reservoir air the
compressor cannot replace, and the spring brakes come on. That is precisely
the observed outcome.

### Why the snub never releases

At 7.33 mph against a target of 8.3517, `over` is about -1.02, just past
`KEEPER_SNUB_UNDER_MPH` (-1.0) -- but the keeper only ever runs on the one
frame per cycle right after the driver lifts, which is the FASTEST point of
the oscillation (7.36 mph, `over` = -0.99). Sampled only there, the release
test never fires.

### Why the corner-speed commit exposed it

Before `b123bb9c` a corner was floored at `FACILITY_GATE_LIMIT_MPH` (15), so
on a facility chain the keeper's eased target was 14 and the truck rode above
it with no snub latched. A square corner is now priced at 9.35 mph, the eased
target is 8.35, and the truck settles exactly on the release edge with a snub
latched. The latch bug was always there; the corner price put the truck where
it shows.

### The ramp-chatter report (coordinator's second hypothesis)

Checked, and it is **not** this defect. Over the whole destination ramp the
trace shows `transition_assist_active` flipping twice, `brake` at 0.00
throughout, and air 125.0 -> 125.0. Route-transition assistance only lifts
the throttle -- it has not braked since the ramp-cap fix -- so it cannot
spend air at all. The comment about paying air "every time round" is the
record of the 2026-08-11 bench, i.e. of the behaviour that fix removed.

The collapsed hysteresis band on a low-design-speed ramp is a real, separate
defect (it costs speech), and the coordinator is fixing it on
`feat/corner-speed-geometry`. Nothing in `lanes.rs` or `exits.rs` is touched
here.

## What I changed

1. `driving_events/cruise.rs` and `driving_updates/frame.rs`: the snub's
   pedal write moves into `apply_keeper_snub`, re-asserted from
   `update_frame` beside `apply_hazard_brake` -- the same repair, for the
   same reason, that the hazard assist and the arrival assist already carry.
   A held snub now costs one application however many frames the keeper
   spends overridden.

   This is the third time this exact defect has been found in this codebase.
   `apply_hazard_brake`'s own doc comment describes it; so does the Shelby
   downgrade lesson in the facility lane hold ("dropped, it re-applied every
   other frame, 7 psi a half-second, spring brakes a third of a mile short").
   Recorded in `docs/roadmap-details.md` as a rule for the next assist that
   holds a pedal, rather than as a third one-off.

2. `driving_events/cruise.rs`: a driver on the accelerator releases the snub.
   The re-assert alone is NOT safe: `keeper_snub_brakes` decides the latch
   only on frames `update_keeper` reaches its controller, so re-asserting a
   pedal the keeper can no longer re-evaluate deadlocks the truck. Measured:
   Aberdeen came to rest at 0.01 mph with the snub held and the driver's
   throttle zeroed under it, ten thousand feet short. Releasing on override
   is what makes the held application safe to hold -- and it is the rule the
   keeper already applies to its own throttle, now applied to the driver's.
   Every other exit from keeper control (`clear_keeper`, `cancel_keeper`)
   already clears the snub; this path was the odd one out.

   The two halves are one fix and neither works alone: the release stops the
   keeper owning a pedal it is not controlling, and the re-assert stops the
   pedal it IS controlling being dropped and re-bought across a shift.

### A second defect the air failure was hiding

Once Aberdeen survived, Abilene failed differently -- and it turned out
Abilene never passed at base either. Measured with a single-destination
probe:

| | ready | crossed the gate at | short by | spring brakes |
| --- | --- | --- | --- | --- |
| base | no | never got there | 20987 ft | yes |
| with the air fix | yes | 19.8 mph | 0 ft | no |

So the air fix took Abilene from "stranded, delivery impossible" to
"arrives, but over the gate limit". The overspeed is the test's own driver
model, not the game. `driver_target_mph` honoured a corner's advisory only
while the corner's milepost was still ahead of the truck. The game's
definition of a corner still in play is wider and is the one the docstring
names: `turn_cue_in_play` -- unresolved, within the commit tail. In the gap
between those two the driver went back to the posted 30 and floored it: 8.6
mph to 19.8 in the last seven hundred feet, with "turn right now, advise
nine" still being spoken. The corner was then judged on the speed the driver
had just put on, and the loop-back set the truck down on the gate at 19.8.

Fixed by using the game's own predicate. The threshold is not touched;
the guard that disagreed with it is removed.

### Considered and rejected

**Re-asserting the pedal without releasing on override.** Deadlocks the
truck; see above. Rejected on measurement, not on taste.

**Widening `KEEPER_SNUB_OVER_MPH` / `KEEPER_SNUB_UNDER_MPH`** -- the original
diagnosis. The band was never the mechanism: the snub rose ONCE in the 1,200
frames where the pedal rose 179 times. Changing it would have moved a number
that was not wrong.

**Coasting at low targets, creeping in a low gear, or having the keeper
decline targets below some speed** -- the three directions in the brief. All
three answer "what should the truck do at a nine mph corner", which is a feel
question the owner owns. None of them is the defect: the truck was not
failing to hold nine mph, it was buying the same brake application over and
over. No threshold was touched. The snub band, the 4.5 psi per application
and the corner price are exactly as they were.

## What the owner should listen for

- On a facility street chain, the truck no longer sets its own parking brakes
  short of the gate, and the air gauge should stay high the whole way in.
- Pressing the accelerator with the speed keeper on now lets its brake off
  instead of fighting it. That should feel like the truck answering the
  pedal, where before it felt like driving against something.
- The keeper's snub itself is unchanged: one application, held until the
  truck is back under its number. Nothing else should sound different.

## Not resolved

- How the truck FEELS holding roughly 8 mph through a chain of square corners
  is the owner's call and is untouched here. The keeper now reaches the gate
  with air to spare, but it does hold the corner price for the whole chain,
  and on a long chain that is several minutes at a walking pace.
- The keeper now lets its snub off the moment the driver touches the
  accelerator, and re-makes it when they lift. On a stretch where the driver
  is feathering the pedal that is still a series of applications -- far fewer
  than before, and the tanks stay high, but it is the next thing to look at
  if air ever gets tight again.

## The regression test

`states_driving_facility::test_the_approach_assist_still_has_its_air_at_the_gate`.

Arriving was never enough to catch this: a truck can arrive on the last of
its air, or be stopped by its own spring brakes ON the gate and read as
parked there. The case now measures the tanks every frame of the approach
and fails if the pressure ever reaches the truck's own low-air warning --
that warning, not a number this test chose, because an approach the driver
never even hears an air warning on is one that never spent the air, and it
sits far enough above the spring-brake trip that the case fails while the
truck is still drivable.

`Arrival` also records `brake_applications`, the number of rising pedal
edges. It is in the failure message, not in an assertion: what a chain
costs depends on how many corners it turns, so there is no count I could
defend as a bar.

## Test results

- The two named cases pass, and so do the four other approach-assist cases
  that share their rigging.
- `cargo test -p ff-core -p freight-fate`: 5,039 passed, 0 failed. Nothing
  was skipped for `ci_quick` -- the whole-map sweeps ran.
- The regression case was checked BOTH ways: it fails on the unfixed source
  (spring brakes, Aberdeen) and passes with the fix.
- `cargo fmt --all --check` and
  `cargo clippy -p ff-core -p freight-fate --all-targets --locked -- -D warnings`
  are clean.
- The adversarial battery was run through its test binary
  (`cargo test -p freight-fate --test it -- --ignored adversarial`), not
  through `freightfate --break-battery`: a human was driving the real game
  and `SingleInstanceGuard` would have taken their session.
- BASS was copied into this worktree's `crates/bass-sys/vendor` before the
  full run, so the audio cases really ran rather than skipping themselves
  into a green result that proved nothing.
