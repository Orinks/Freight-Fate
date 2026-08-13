# Cruise steps snap to fives, Shift steps by one

Owner-approved design, 2026-08-13. Tester context: K captures the exact
current speed as the cruise target, and +/- stepped a flat 5 from there --
so a captured 32 stepped to 37, 42, never landing on the fives. Jerry
(limited hand dexterity) worked around it by latching the throttle to ~35
and tapping K at just the right moment; he asked for a fine step, Sarah
asked for real-stalk snapping, and the owner wants both.

## Behavior

- **Plain +/-** snaps the target outward to the next multiple of 5 mph:
  from 32, plus gives 35 then 40; minus gives 30. Already on a multiple,
  it moves a full 5. This heals an off-grid captured speed in one tap.
- **Ctrl with +/-** moves the target by exactly 1 mph, no snapping --
  the precise-target path for players who cannot feather K onto an exact
  speed. Ctrl rather than Shift (the owner offered either): on a US
  keyboard the main-row plus IS Shift+equals, so a Shift modifier cannot
  be told apart from the plus key itself.
- Both clamp to the existing `CRUISE_MIN_MPH`/`CRUISE_MAX_MPH` bounds.
- Both apply wherever +/- applies today: the open-road cruise target, and
  the resume target while the speed keeper is holding a restricted zone.
- The high-idle stepping that owns these keys while parked with high idle
  latched is untouched (its branch runs first and returns, as today).
- The controller keeps plain snapped fives -- a pad has no Shift; fine
  steps are keyboard-only until someone asks otherwise.
- The grid is miles per hour, matching `CRUISE_STEP_MPH` today; metric
  display converts for speech as it already does.

## Mechanism

A small pure helper beside `_adjust_cruise` (driving_events.py) computes
the next target from (current target, direction, fine flag): fine gives
target±1; coarse gives the next multiple of 5 strictly above/below, i.e.
`floor(target/5)*5 + 5` upward and the mirror downward, which degenerates
to ±5 on-grid. The key handler (driving_controls.py:83-89) reads
`event.mod & pygame.KMOD_SHIFT` the same way the adjacent K binding does.
The existing spoken confirmation line is unchanged apart from the numbers
it speaks.

## Copy

The F1 driving help's "cruise target by five" sentence gains one clause:
Shift with the same keys moves it by one mile per hour. Canonical nouns
per `docs/ontology.md`; no other new speech.

## Tests

- Off-grid snap up (32 -> 35) and the following on-grid step (35 -> 40).
- Off-grid snap down (32 -> 30); on-grid down (30 -> 25).
- Clamp at both bounds, stepping and snapping.
- Shift fine steps up and down by 1, including from on-grid targets.
- Keeper active in a zone: +/- moves the open-road resume target with the
  same snapping.
- Parked with high idle latched: the keys still step idle RPM, cruise
  target untouched.
