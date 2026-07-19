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

# A following curve starting within this gap after the called one gets a
# "then left/right" tail instead of its own later call.
PACENOTE_LINK_GAP_MI = 0.3
PACENOTE_MARGIN_MPH = 3.0
# Below this the quarter-mile rounding would LIE upward: a bend 200 feet
# out spoken as "a quarter mile" reads as time the driver does not have
# (owner's AZ-260 log, 2026-07-19). Say "just ahead" instead.
PACENOTE_JUST_AHEAD_MI = 0.15

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

    def _pacenote_text(self, curve, ahead_mi: float, speed_mph: float) -> str:
        s = self.ctx.settings
        distance = (
            "just ahead"
            if ahead_mi < PACENOTE_JUST_AHEAD_MI
            else s.short_distance_text(ahead_mi)
        )
        call = f"{self._pacenote_phrase(curve)}, {distance}."
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
