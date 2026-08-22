# Brief: corner speed from real geometry

Owner directive, 2026-08-21, after a Spokane arrival he could not follow:
kill the 15 mph floor, bake the turn geometry the build script already
computes and discards, and fix anything else in this area that is
unrealistic. Use real numbers; where we do not have data, go and get it.

This file is the standing record for that work. Keep it updated as the work
lands -- it is what the next session reads.

## What is wrong today

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

## The open modelling decision

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
