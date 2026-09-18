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
long wall clock. Until then the coverage block will report a 0.0 read ratio,
which is the honest answer and exactly what that field is for.

Note when the bake does run: 84 percent of approach targets are estimated
fallbacks with no coordinates at all, so they can never carry an angle. Only
the 1,077 turn-level city-service routes can. Do not read a low ratio as a
bake failure without checking that denominator first.

### The one open defect this exposed -- READ THIS BEFORE THE NEXT SESSION

Two tests fail on this branch and they are the same bug:
`states_driving_facility::test_the_approach_assist_stops_the_truck_on_a_facility_street_chain`
and `states_driving_approach_sweep::test_the_approach_assist_stops_the_truck_at_every_kind_of_destination`.

The destination approach assist now runs the truck out of air on a facility
street chain, sets the spring brakes, and parks it short of the gate. It does
this at EVERY destination, so it is not a fixture artifact.

Measured, not guessed (instrumented run, Aberdeen Company Yard):

* The truck sheds cleanly for the corner and reaches about 9 mph with 120 psi.
* It then sits at 7.3 mph and the air falls about 3 psi per second with the
  service brake reading ZERO at every sample and a peak of 0.20 between them.
* 125 psi to the 40 psi spring-brake trip in about 20 seconds. The keeper is
  cancelled by the emergency application, the throttle pins at 1.00 against
  set brakes, and the truck never moves again.

The mechanism is `keeper_snub_brakes` cycling. Its band is fixed at
`KEEPER_SNUB_OVER_MPH` 1.5 over and `KEEPER_SNUB_UNDER_MPH` 1.0 under: a
couple of percent of a highway limit, but a quarter of a 9 mph corner. Each
cycle is a fresh application and `air_loss_primary_per_application_psi` is
4.5, so roughly one cycle a second empties the tanks. The function's own
comment already says "Easing and re-pressing is what the air system charges
for" -- the hysteresis was built for exactly this and is simply sized for
highway numbers.

Widening that band by a fraction of the target was tried and does NOT fix it,
because the reason the truck crosses the band at all is that the automatic
cannot hold a steady 9 mph -- it hunts in gear at that speed. So the real
question is what the truck should DO at a street-corner target: creep in a low
gear, hold on the throttle alone and keep the drums out of it (the rule
`update_lane` already applies to ramps -- "lift first and let drag shed the
excess; holding a service floor here spent air all the way down the ramp"), or
have the keeper decline targets below some speed and hand the pedals back.

That is a feel decision and it wants the owner at the wheel, which is why it
was left rather than guessed at. Nothing was tuned to make a test pass.

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
