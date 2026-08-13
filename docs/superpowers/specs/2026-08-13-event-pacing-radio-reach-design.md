# Road events breathe; radio contours last

Owner-approved design, 2026-08-13. Two independent fixes for one root
cause: time compression spends road 10-40x faster than a real cab, so
legitimately-spaced road events arrive back to back in every driving mode,
and a radio station's contour passes in a couple of real minutes, most of
it fringe. The owner chose to keep the clock (10x/20x/40x untouched --
career pacing is balanced around it) and fix each symptom at its source.

## Part 1: Road-event breathing room

A real-clock throttle at the SOURCE of the three routine talkers. The
speech pacer keeps its current job (staleness, repeats, priority); this
sits upstream, deciding whether a routine line is generated at all.

- **Categories and minimum real-seconds gaps** (constants, named like the
  existing `*_REAL_S` family):
  - posted-limit change announcements: 12 s
  - traffic situation calls (brake lights / merging / slow lead): 10 s
  - zone-entry chatter (construction, school, congestion colour): 15 s
- **Supersede, never catch up.** A line held by the gap is replaced by any
  newer line of its category; when the window opens, only the newest
  state speaks ("Speed limit now 55" reflects the CURRENT posting). If
  the newest line's condition has expired (already announced by an
  assist, zone already exited), nothing speaks.
- **Mechanics unchanged.** Limits still bind, enforcement still reads the
  real posting, cruise/keeper still follow the road. Only narration is
  throttled. Assist action lines ("speed keeper easing to 45") are the
  assist's own and are not throttled -- but an assist line that already
  named the number satisfies the limit category's pending line (the
  existing `note_limit_preannounced` contract extends to the throttle).
- **Exempt, never delayed:** hazard and AEB lines, curve advisories and
  pacenotes, weigh-station and planned-stop calls, navigation maneuvers,
  enforcement lines, and anything the driver asked for (Space, L, status
  keys always answer immediately).
- **Real seconds, not game seconds.** The gaps use wall-clock dt, the
  same law as `KEEPER_EASE_REAL_S` and the zone warnings, so all three
  driving modes calm down equally.

## Part 2: Radio contours that last

- **Fade curve.** Today clean program holds only while signal >= 0.6,
  which with the `1.4` falloff exponent is the inner ~52% of the contour;
  the outer half is fringe and static smear. Rethreshold so clean program
  holds through ~85% of the contour (`SIGNAL_FULL_VOLUME` ~0.20,
  `STATIC_SIGNAL_THRESHOLD` ~0.12), keeping the owner's 2026-07-24
  smear-into-static ruling at the true edge: static rises TO program
  level, never on top of a loud one. The deep-floor trace survives.
- **Reach multiplier.** One documented constant (~2.0x) applied to
  `range_miles` for ranged stations, compensating for compression: a
  median 40-mile FM contour becomes ~80 game-miles -- about seven real
  minutes of clean listening at Relaxed -- while staying regional. The
  terrain/elevation lift and every other propagation rule stack on top
  unchanged.
- **No data sweep.** The ~4,900 imported stations without `range_miles`
  already play at full volume ("built-in" reception) and are untouched.
  Reception-physics tests use fixtures, not catalog stations, per the
  radio test contract.

## Tests

- Throttle: two limit changes 3 real seconds apart speak once, with the
  second posting's number; a hazard line inside the gap speaks instantly;
  category gaps are independent (a traffic call does not consume the
  limit category's window); gaps measured in real seconds at 20x and 40x
  compression (same real gap, different road distance).
- Radio: signal_volume_factor holds 1.0 at 80% of contour distance and
  fades past 85%; static engages only in the outer edge; reach multiplier
  applied to ranged stations only (always_available and range-less
  stations unchanged); elevation lift still adds on top.

## Out of scope

Lowering the compression scales themselves (rejected: lengthens every
delivery and the career arc), and any radio range data sweep.
