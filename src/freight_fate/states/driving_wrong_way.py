# ruff: noqa: F403,F405
"""Backing down a live road: the one manoeuvre nothing used to object to.

Reverse exists for the yard and the dock, and the sim already prices its
abuse -- the box refuses reverse above a walking pace, and holding a loaded
rig against its governor in reverse wears the engine out. What none of that
covers is *where*. The adversarial harness backed a tractor-trailer a full
mile down an interstate to route mile zero, and the only thing the game said
in all that time was a merge instruction for the exit it was reversing away
from. A sighted player would at least see the world sliding the wrong way; a
blind player had nothing at all, which makes this an accessibility gap before
it is a realism one.

Backing on a travelled lane is prohibited outright on a controlled-access
highway and is how real drivers get hit, so the ladder here is short and it
escalates on distance rather than time:

* **the reminder** -- past a truck length or two, say which way the truck is
  going and what it is undoing. This is the line the harness was looking for.
* **the warning** -- past a tenth of a mile, name it as illegal, because by
  then it is not a misjudged dock approach, and give the distance back so the
  player knows how far they have to make up.
* **traffic** -- past a quarter mile, the road stops being empty. Reversing
  into a live lane is a collision waiting to happen, and the collision is
  what a real driver would meet.

Legitimate backing is exempt: the yard, the dock approach, a facility gate
zone, and anywhere within reach of a stop the player pulled into. A driver
lining up on a dock must never be scolded for doing their job.
"""

from __future__ import annotations

from ..sim.trip_models import FACILITY_GATE_ZONE_MI
from .driving_core import *

# The rungs, in miles backed along the route since reverse was engaged.
WRONG_WAY_REMIND_MI = 0.02  # about a hundred feet: past any dock manoeuvre
WRONG_WAY_WARN_MI = 0.10
WRONG_WAY_TRAFFIC_MI = 0.25
# How far the warning repeats after that, so a player who keeps going keeps
# hearing it with a fresh distance rather than once and then silence.
WRONG_WAY_REPEAT_MI = 0.25
# Backing into a live lane. Modest per hit -- the point is the event and the
# noise it makes, not a one-shot kill -- but it repeats for as long as the
# truck keeps going the wrong way.
WRONG_WAY_COLLISION_SEVERITY = 0.3
# Anywhere a driver has real business in reverse.
WRONG_WAY_STOP_RADIUS_MI = 0.3


class WrongWayMixin:
    def _reverse_is_legitimate(self) -> bool:
        """True where backing is the job: the yard, a dock, a stop's lot."""
        trip = self.trip
        if trip.position_mi <= WRONG_WAY_STOP_RADIUS_MI:
            return True  # still in the origin yard
        if trip.position_mi >= trip.total_miles - FACILITY_GATE_ZONE_MI:
            return True  # lining up on the receiver
        return trip.nearest_stop_within(WRONG_WAY_STOP_RADIUS_MI) is not None

    def _reset_wrong_way(self) -> None:
        self._wrong_way_mi = 0.0
        self._wrong_way_said_at = 0.0

    def _update_wrong_way(self, dt: float) -> None:
        """Watch how far the truck has travelled backwards along the route."""
        t = self.truck
        trip = self.trip
        backing = t.transmission.in_reverse and t.speed_mph > 0.5
        if not backing or self._reverse_is_legitimate():
            self._reset_wrong_way()
            return
        # Distance along the route, not wheel rotations: what matters is how
        # much of the trip is being undone.
        self._wrong_way_mi += abs(trip.last_moved_mi)
        backed = self._wrong_way_mi
        said_at = self._wrong_way_said_at

        # Fires AT the rung, then repeats on the interval. Gating the first
        # one behind the repeat distance too would have let the truck reach a
        # third of a mile back down the road before traffic noticed it.
        reached_traffic = said_at < WRONG_WAY_TRAFFIC_MI or backed - said_at >= WRONG_WAY_REPEAT_MI
        if backed >= WRONG_WAY_TRAFFIC_MI and reached_traffic:
            self._wrong_way_said_at = backed
            self.ctx.audio.play("ui/warning")
            self.ctx.say_event(
                "You are backing into traffic. Stop, select a forward gear, and "
                "get the truck pointed the right way.",
                interrupt=True,
            )
            severity = WRONG_WAY_COLLISION_SEVERITY
            self.ctx.audio.play("vehicle/collision")
            self.ctx.controller.rumble.impact(severity)
            t.apply_collision(severity)
            self.ctx.say_event(
                f"Something hit the trailer. Total damage {t.damage_pct:.0f} percent.",
                interrupt=True,
            )
            return
        if backed >= WRONG_WAY_WARN_MI and said_at < WRONG_WAY_WARN_MI:
            self._wrong_way_said_at = backed
            self.ctx.audio.play("ui/warning")
            # Precise: at this rung the distance is a tenth of a mile, and the
            # whole-number form would say "0 miles" to a driver who has just
            # been told they are giving the route back.
            distance = self.ctx.settings.distance_text(backed, precise=True)
            self.ctx.say_event(
                f"You are driving the wrong way. Backing on a travelled lane is "
                f"illegal, and you have given up {distance} of the route. Stop and "
                "select a forward gear.",
                interrupt=True,
            )
            return
        if backed >= WRONG_WAY_REMIND_MI and said_at < WRONG_WAY_REMIND_MI:
            self._wrong_way_said_at = backed
            self.ctx.say_event(
                "You are still in reverse, backing away from your destination.",
                interrupt=False,
            )
