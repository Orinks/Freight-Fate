# Pedal latch yields to speed authorities

Owner-approved design, 2026-08-13. Tester context: Brandon latches the
throttle for the whole trip and expects the speed assists to manage speed
over it; today every assist reads the latched throttle as a manual override
and stands down (speed keeper and cruise return early on `accelerating`;
curve assist's 0.35 service brake fights a pedal ramping to full and its
jake needs `throttle < 0.05`). The owner keeps the current latch design --
this change only redefines who wins while an assist is engaged.

## Meaning

- A **latched** throttle is the lowest-priority speed input. It drives the
  pedal only when no speed authority is engaged. It never counts as the
  driver insisting on speed.
- A **hand-held** throttle key keeps today's meaning everywhere: live
  manual override, assists stand down until the key lifts.
- **Speed authorities** that outrank the latch, whenever engaged: cruise /
  adaptive cruise (whole session), the speed keeper (while active in a
  zone), curve speed assist (while assisting). While any is engaged the
  latch contributes no throttle; when the last one releases, the latch
  ramps back in. The latch state itself does not change -- no re-gesture.
- The existing **hard releases stay releases** (opposite pedal/brake,
  emergency brake, live hazard including AEB, overspeed alarm): those mean
  "driver takes over", not "the truck is managing speed".
- **Releasing the latch never cancels an assist.** A fresh press of the
  throttle key returns the pedal to the hand (and while held, overrides,
  as any hand throttle does); cruise or the keeper keeps holding its
  speed exactly as if the driver had feathered the pedal. The brake
  remains the way to cancel, unchanged.
- Realistic play is the `pedal_latch` setting turned off; the latch is an
  input-accessibility accommodation and is documented as such.

## Revision 2026-08-13 (owner, mid-implementation): three-way setting

The `pedal_latch` setting becomes a three-way mode instead of a toggle,
following the `overspeed_warning` bool-to-string precedent:

- **"assists first"** (default; legacy `True` migrates here): everything in
  this spec -- the latch yields to engaged speed authorities.
- **"latch first"**: the behavior before this change, kept for players who
  want the latch to mean "hold this whatever the assists think" -- a
  latched throttle counts as a manual override and the assists stand down.
  The hard safety releases apply in both modes, unchanged.
- **"off"** (legacy `False` migrates here): no latching at all, the plain
  pedals -- the realistic mode.

The catch line naming the authority speaks only in "assists first" mode;
in "latch first" the plain "Throttle latched." is the truth.

## Mechanism

`_update_pedal_latches` returns hand and latch state separately instead of
pre-blending them. The frame keeps two signals:

- `accelerating` (hand OR latch) -- unchanged consumers that mean "is the
  pedal down": reverse gesture, air-lockout cue, brake-latch release.
- hand-only throttle -- what the assists' `if accelerating: return` gates
  and cruise's manual-override checks read.

While any speed authority is engaged, the latch's contribution to the
throttle ramp in `update()` is skipped, so the authority owns the pedal.
No per-assist wiring inside the assists themselves beyond swapping which
signal they read.

## Speech

No new per-event lines; the assists' own cues (curve assist slowing /
released, keeper ease lines, cruise resume) already narrate the speed. One
addition: performing the catch while cruise or the keeper is holding the
speed appends the authority to the confirmation -- "Throttle latched.
Cruise holds the speed." / "... Speed keeper holds the speed." -- so the
latch never seems dead. Wording uses the canonical nouns from
`docs/ontology.md`.

## Tests

In `tests/` beside the existing latch coverage:

- Keeper holds a zone target with the throttle latched (was: stood down).
- Curve assist under latch: throttle drops below its jake threshold and
  the service trim is not fought.
- Cruise runs under a latch; canceling cruise with K hands the pedal back
  to the latch, which ramps again.
- A hand-held key still stands the keeper down (override unchanged).
- Brake tap still hard-releases the latch and cancels cruise (unchanged).
- Releasing the latch mid-cruise leaves cruise engaged and holding.
- The catch confirmation names the active authority; plain catch wording
  unchanged when nothing is engaged.
