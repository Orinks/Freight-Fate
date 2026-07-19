"""Spoken curve calls -- the co-driver reads the road ahead.

The first audible slice of the steering-by-ear design (see
docs/steering-sound-rfc.md): plain-language pacenotes from the baked
curve geometry, called early enough to brake before the bend, and only
when the bend actually demands slowing at the truck's current speed. A
gentle sweep taken at a legal speed stays silent -- the road only speaks
when it has something to say.

Grammar: "Sharp left, half a mile. Advise 35." Severity comes from the
baked advisory speed (the number a posted yellow diamond would show);
the advisory sentence is included only when the truck is above it.
Curves that follow within a breath get a linked tail: "then right."
"""

from __future__ import annotations

# The call must land early enough to hear it, decide, and shed the speed
# before the entry -- reaction covers the sentence plus the driver, the
# braking term uses a comfortable service application, not a panic stop.
PACENOTE_REACTION_S = 5.0
PACENOTE_BRAKE_MPH_PER_S = 3.0
# Below this margin over the advisory the bend needs no call at all.
# Gentle sweeps get a wider berth: a five-over correction on a gentle
# bend is chatter, not help -- they call only when the truck is truly
# hot into them, and stay listed under U either way.
PACENOTE_MARGIN_MPH = 3.0
PACENOTE_GENTLE_MARGIN_MPH = 8.0
# Floor and ceiling on the call distance: the call is front-loaded --
# brake before the bend, never in it -- so the floor is a third of a
# mile, twenty seconds of highway.
PACENOTE_MIN_LEAD_MI = 0.33
PACENOTE_MAX_LEAD_MI = 1.5
# A following curve starting within this gap after the called one gets a
# "then left/right" tail instead of its own later call.
PACENOTE_LINK_GAP_MI = 0.3
# No calls while crawling: parking lots and gate queues are not rally stages.
PACENOTE_MIN_SPEED_MPH = 20.0
# The cue tone leans hard toward the curve's side of the stereo field.
PACENOTE_CUE_PAN = 0.85

_SEVERITY_PHRASE = {
    "hairpin": "Hairpin",
    "sharp": "Sharp",
    "moderate": "Curve",
    "gentle": "Gentle bend",
}
_DIRECTION_WORD = {"L": "left", "R": "right"}


class DrivingPacenoteMixin:
    """Per-frame curve callouts. Wired from the driving update loop."""

    def _pacenote_phrase(self, curve) -> str:
        return f"{_SEVERITY_PHRASE[curve.severity]} {_DIRECTION_WORD[curve.direction]}"

    def _pacenote_lead_mi(self, speed_mph: float, advisory_mph: float) -> float:
        over = max(0.0, speed_mph - advisory_mph)
        react_mi = speed_mph * PACENOTE_REACTION_S / 3600.0
        brake_s = over / PACENOTE_BRAKE_MPH_PER_S
        brake_mi = (speed_mph + advisory_mph) / 2.0 * brake_s / 3600.0
        return min(PACENOTE_MAX_LEAD_MI, max(PACENOTE_MIN_LEAD_MI, react_mi + brake_mi))

    def _pacenote_margin(self, curve) -> float:
        if curve.severity == "gentle":
            return PACENOTE_GENTLE_MARGIN_MPH
        return PACENOTE_MARGIN_MPH

    def _pacenote_text(self, curve, ahead_mi: float, speed_mph: float) -> str:
        s = self.ctx.settings
        call = f"{self._pacenote_phrase(curve)}, {s.short_distance_text(ahead_mi)}."
        if speed_mph > curve.advisory_mph + PACENOTE_MARGIN_MPH:
            call += f" Advise {s.speed_text(curve.advisory_mph)}."
        linked = self._pacenote_linked(curve)
        if linked is not None:
            call += f" Then {_DIRECTION_WORD[linked.direction]}."
        return call

    def _pacenote_linked(self, curve):
        """The next curve when it follows within a breath of this one."""
        for other in self.trip.curves_within(
            curve.end_mi - self.trip.position_mi + PACENOTE_LINK_GAP_MI
        ):
            if other.start_mi > curve.end_mi:
                return other
        return None

    def _update_pacenotes(self, dt: float) -> None:
        if not self.ctx.settings.curve_callouts:
            return
        # Ramps carry their own speech; the curve-nav layer owns their arcs.
        if getattr(self, "_ramp_mi", None) is not None:
            return
        speed = self.truck.speed_mph
        if speed < PACENOTE_MIN_SPEED_MPH:
            return
        pos = self.trip.position_mi
        spoken: set[int] = self._pacenote_spoken
        for curve in self.trip.curves_within(PACENOTE_MAX_LEAD_MI):
            key = int(curve.start_mi * 1000)
            if key in spoken:
                continue
            # Advisory relevance is checked at call time, so speeding up
            # late can still earn the warning it just created.
            if speed <= curve.advisory_mph + self._pacenote_margin(curve):
                continue
            ahead = curve.start_mi - pos
            if ahead > self._pacenote_lead_mi(speed, curve.advisory_mph):
                continue
            spoken.add(key)
            # A curve call sounds like any other announcement until it has
            # a signature: a short cue panned to the curve's side marks
            # "road shape ahead", never a steering command -- the owner
            # steered a lane change off a bare "Sharp left" (playtest,
            # 2026-07-18). One-shot, not the continuous steering tone the
            # community ruled out. Placeholder sound until a dedicated cue
            # is sourced.
            pan = -PACENOTE_CUE_PAN if curve.direction == "L" else PACENOTE_CUE_PAN
            self.ctx.audio.play("ui/tick", volume=0.9, pan=pan)
            self.ctx.say_event(self._pacenote_text(curve, ahead, speed))
            break
        if len(spoken) > 64:
            # Keep only keys still ahead of the truck; the rest are history.
            floor = int(pos * 1000)
            spoken.intersection_update({k for k in spoken if k >= floor})
