# Brief: corner speed from real geometry

Owner directive, 2026-08-21, after a Spokane arrival he could not follow:
kill the 15 mph floor, bake the turn geometry the build script already
computes and discards, and fix anything else in this area that is
unrealistic. Use real numbers; where we do not have data, go and get it.

This file is the standing record for that work. Keep it updated as the work
lands -- it is what the next session reads.

## STATUS: model and runtime landed 2026-09-18; the map rebake is not

What is done, on `feat/corner-speed-geometry`:

* `crates/ff-core/src/data/corners.rs` is the model, with every source and
  the derivation in its module docs and the calibration gate below kept as an
  executable test.
* `turn_speed_mph` reads it. The 15 mph floor is gone.
* `tools/build_local_geometry.py` keeps the turn angle it used to discard
  (`turn_geometry` replaces `turn_direction`) and reports the read/assumed
  ratio on stdout and in the layer's coverage block.
* `local_turn_deg` is plumbed through `Leg`, the local-geometry JSON, the
  route reversal and the baked container. The container's `FORMAT_VERSION`
  went to 3, so a stale `world.ffdata` is refused with the re-bake command
  rather than half-read.

What is NOT done: **`src/freight_fate/data/local_geometry.json` has not been
rebuilt**, so no shipped route carries a real angle yet and every corner is
priced as a square one (9.4 mph) by the assumed path. The model is correct and
the game is playable; it is uniform rather than varied until the bake runs.
Running it needs the state PBFs in `~/.cache/freight-fate-osm/regions` and a
long wall clock. Until then there is no ratio to read at all: the shipped
`local_geometry.json` and `facility_approaches.json` carry no turn-angle keys
and no `meta` coverage block, so every corner takes the assumed path silently.
The read/assumed ratio first exists in the layer the bake writes.

Note when the bake does run: 84 percent of approach targets are estimated
fallbacks with no coordinates at all, so they can never carry an angle. Only
the 1,077 turn-level city-service routes can. Do not read a low ratio as a
bake failure without checking that denominator first.

### The defect this exposed -- FIXED 2026-09-18

Two tests failed on this branch and they were the same bug:
`states_driving_facility::test_the_approach_assist_stops_the_truck_on_a_facility_street_chain`
and `states_driving_approach_sweep::test_the_approach_assist_stops_the_truck_at_every_kind_of_destination`.
The destination approach assist ran the truck out of air on a facility street
chain, set the spring brakes, and parked it short of the gate, at every
destination.

The first diagnosis blamed `keeper_snub_brakes` cycling across its 1.5/1.0
mph band. **That was wrong**, and the instrumented re-run says so plainly:
over the 1,200 frames of the drain, `keeper_snub` rose ONCE while the pedal
rose 179 times. The snub does not cycle. It latches and stays latched.

The real mechanism is the latch outliving the frames that apply it.
`update_keeper` returns early whenever the driver is on the accelerator or
the automatic has an open driveline mid-shift, and `update_frame`'s input
pass -- which ramps `truck.brake` down every frame nobody commands it --
runs BEFORE it. So on an overridden frame the held application was not
paused, it was dropped; the next frame the keeper reached its controller it
re-made the same application from zero, and `consume_brake_air`, which
charges `air_loss_primary_per_application_psi` on every RISING edge, billed
4.5 psi again. Measured on the Aberdeen chain: nine re-applications a second,
about eight psi a second against the four the compressor makes at idle, 308
rising edges over the chain. FMCSA's CDL manual names the same thing on a
real truck -- fanning the brakes spends reservoir air the compressor cannot
replace, and the spring brakes come on.

The corner price is what put the truck where it shows, not what broke it. At
the old 15 mph corner floor the truck rode above its eased target with no
snub latched; at 9.35 it settles right on the release edge with one latched.

Fixed in two halves, and neither works alone. The pedal write moved into
`apply_keeper_snub` and is re-asserted from `update_frame` beside the other
assists' floors -- the treatment `apply_hazard_brake` and the arrival's
pedals already have -- so one held snub costs one application however many
frames the keeper spends overridden. And a driver on the accelerator now
releases the snub: `keeper_snub_brakes` re-evaluates the latch only on frames
the keeper reaches its controller, so re-asserting a pedal it can no longer
judge deadlocks the truck (measured: Aberdeen at rest at 0.01 mph with the
snub held, ten thousand feet short). The release is also the rule the keeper
already applied to its own throttle, now applied to the driver's.

No threshold was changed: the snub band, the 4.5 psi, and the corner price
are all exactly as they were.

What the truck should FEEL like holding roughly 8 mph through a chain of
square corners is still the owner's call and is still untouched.

## What was wrong (the 2026-08-21 report)

`DrivingTurnMixin._turn_speed_mph` (`src/freight_fate/states/driving_turns.py`)
is not a model. It is the street's posted limit clamped between
`FACILITY_GATE_LIMIT_MPH` (15) and `TURN_CORNER_MAX_MPH` (20), and both ends
are assumed constants with no cited basis. Every corner in the game, from a
sweeping 60-degree bend onto an arterial to a square left into a yard, gets
the same answer.

The 15 floor has a second effect that is worse than the number itself.
`_update_turn_commitment` skips the corner advisory when the truck is already
at or under the corner speed -- correct in itself -- so a truck held at 14-15
by the speed keeper through a facility zone is under EVERY corner and never
hears an advisory at all. Owner drove exactly that and missed a turn.

(The related clock bug -- that same early return also skipped the real-time
decompression, so four corners arrived in fifteen real seconds -- is already
fixed on `feat/career-1.9`. Do not re-fix it; do read it, because the shape
of the mistake is instructive: one early return quietly doing two jobs.)

## The data we already have and throw away

`tools/build_local_geometry.py::turn_direction()` computes the signed heading
change through every junction from read OSM geometry, then keeps only its
SIGN to choose "left"/"right"/"". The magnitude is the corner's real turn
angle. Baking it is a small change to a builder that already runs, and it is
the one piece of per-corner geometry the map can honestly supply.

Whatever else you bake, follow `AGENTS.md` on provenance to the letter: every
value says whether it is **read** (upstream asserts it), **derived** (name the
input and the formula), or **assumed** (a fallback, labelled). A bake that is
mostly assumed says so on stdout and as a ratio in the layer's `meta`.

## Sources gathered (all free, all citable)

* **TxDOT Roadway Design Manual Table 13-7** -- WB-67 minimum simple curve
  radius by turn angle: 60 deg 200 ft, 75 deg 145, 90 deg 125, 105 deg 115,
  120 deg 105. Radius as a function of the one thing the bake can measure.
  <https://www.txdot.gov/manuals/des/rdw/chapter-13--intersections/13-10-additional-intersection-design-consideration/13-10-1-minimum-turning-radii.html>
* **AASHTO Green Book, WB-67 centreline turning radius 41 ft** (p. 2-77) --
  the vehicle's own minimum path, which is NOT the intersection's edge curve.
* **AASHTO side friction by design speed** -- already in the repo at
  `src/freight_fate/data/curves.py::AASHTO_SIDE_FRICTION`, but it stops at
  20 mph (0.27). Cross-checks against TxDOT Table 4-4, whose 20 mph
  normal-crown minimum radius of 99 ft implies e+f = 400/(15*99) = 0.269.
* **Static rollover threshold >= 0.35 g** is the satisfactory criterion for a
  loaded combination; rearward amplification is about 1.0 for a
  tractor-semitrailer, so the trailer does not amplify it.
  NHTSA DOT HS 811 734 <https://www.nhtsa.gov/sites/nhtsa.gov/files/811734.pdf>,
  FHWA <https://www.fhwa.dot.gov/reports/tswstudy/vehiclsaf.htm>
* **Measured turn speeds** -- TTI 0-4365-4, "Turn Speeds and Crashes Within
  Right-Turn Lanes": 85th percentile mid-turn speed 13 to 21 mph over corner
  radii of 27 to 86 ft, free-flow, mostly passenger cars.
  <https://static.tti.tamu.edu/tti.tamu.edu/documents/0-4365-4.pdf>

## The modelling decision, as decided

`V = sqrt(15 R (e + f))`, with `e = 0` at an at-grade intersection. The
question is which R.

* TxDOT's edge curve (125 ft at 90 deg) gives 22-24 mph -- FASTER than
  today's clamp, and plainly wrong for a loaded semi.
* The vehicle's own 41 ft path gives about 10 mph at 0.15 g, which matches
  CDL practice (5-10 mph through a corner) and sits at the bottom of the
  measured TTI band.

The edge curve is what the swept path uses; the vehicle radius is what the
tractor tracks. Decide this on the physics and the sources, write down which
you chose and why, and do NOT pick whichever makes the number look nice --
`AGENTS.md` forbids tuning a threshold until it looks right.

**Calibration gate:** a typical 90-degree city corner must come out in the
5-12 mph band that CDL practice and the bottom of the TTI distribution both
point at, and must never exceed the measured 85th-percentile car speeds for
the same radius. If your model cannot meet that against real baked corners,
say so with numbers rather than adjusting a constant until it does.

**Met, 2026-09-18.** Neither candidate above won: TxDOT gives THREE designs
per angle and the one that matters is the 3-centered compound, whose middle
radius (65 ft at 90 degrees) is the tightest arc the corner actually holds.
The lateral is derived from the equal-rollover-margin principle rather than
chosen -- a car takes a 65 ft corner at a measured 18.8 mph, which is 0.361 g
against its own 1.41 g stability factor, so about a quarter of what would roll
it; the same quarter of the truck's 0.35 g is 0.090 g. That gives 9.4 mph at
90 degrees, 11.6 at 60, 7.8 at 120. Inside the band, well under the car, and
arrived at without CDL practice being an input -- so its agreement is a check
on the model, not a fit to it. `corners.rs` holds the full derivation and
`tests::the_model_meets_its_calibration_gate` keeps this paragraph honest.
