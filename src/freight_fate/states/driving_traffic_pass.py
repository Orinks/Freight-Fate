# ruff: noqa: F403,F405
"""The whoosh when somebody goes by.

Four pass-by cues have been shipped and credited since the traffic bubble
landed -- car, box truck, semi, trooper -- and only the trooper's could ever
play. Its earcon hangs off the enforcement layer, which fires on crossing a
post's mile marker; civilian traffic had no equivalent, so the other three
were reachable only as decoration on a spoken hazard warning about a vehicle
*ahead*. Ordinary traffic going past the cab made no sound at all.

That is a hole in the game's only spatial channel. A sighted player watches
a truck come up the left lane and go by; a blind player had silence, then a
sentence about something else entirely.

Three rules, all borrowed from cues that already work here:

* **Earcon, never a sentence.** Nothing follows from hearing a car pass, and
  the run's spoken budget belongs to things that cost money -- the same
  reasoning that keeps the marked-unit pass wordless in the enforcement
  layer.
* **Pan is confirmation, not meaning.** Both audio backends apply pan once at
  trigger, so the sweep has to be baked into the clip. The pan says which
  side; it is never the thing carrying the information.
* **Once per vehicle.** A truck alongside in stop-and-go traffic can cross
  the bumper repeatedly, and a cue that re-fired on each would sound broken.

Troopers are skipped here on purpose: enforcement already gives them a
marker-plus-whoosh pass, and playing this one too would double them up.
"""

from __future__ import annotations

from .driving_core import *

# Panned to the side the vehicle went by on. Matches the enforcement pass so
# a civilian and a marked unit place the same way.
TRAFFIC_PASS_PAN = 0.55
TRAFFIC_PASS_BASE_VOLUME = 0.55
# A vehicle barely out-running the truck is a long, quiet event; one going by
# twenty over is a bang. Scaled on closing speed between these two, so the
# dial has somewhere to move without ever reaching the level of a cue the
# driver has to act on.
TRAFFIC_PASS_MIN_CLOSING_MPH = 3.0
TRAFFIC_PASS_FULL_CLOSING_MPH = 22.0
TRAFFIC_PASS_QUIET_VOLUME = 0.34
# Real seconds between whooshes, and it has to be REAL seconds: the clock
# runs at ten times pacing on a highway, so a populated road produces a
# crossing every couple of seconds at the speaker even though the truck is
# meeting traffic at an ordinary rate on the road. Measured before this
# existed: 2.7 passes per mile is one every 2.2 seconds in the player's ear,
# which is a machine gun, not a highway.
#
# Dropping the extras rather than thinning the traffic is the honest way
# round. The road should stay as busy as the road is -- the lead-vehicle and
# hazard systems read that population -- and closely spaced vehicles do not
# arrive as separate whooshes anyway; they blend into the road bed the cab
# already carries.
TRAFFIC_PASS_MIN_GAP_S = 6.0


class TrafficPassMixin:
    def _reset_traffic_passes(self) -> None:
        self._traffic_pass_side = {}
        self._traffic_passed_keys = set()
        self._traffic_pass_cooldown_s = 0.0

    def _traffic_pass_volume(self, closing_mph: float) -> float:
        span = TRAFFIC_PASS_FULL_CLOSING_MPH - TRAFFIC_PASS_MIN_CLOSING_MPH
        share = (abs(closing_mph) - TRAFFIC_PASS_MIN_CLOSING_MPH) / span
        share = max(0.0, min(1.0, share))
        return TRAFFIC_PASS_QUIET_VOLUME + share * (
            TRAFFIC_PASS_BASE_VOLUME - TRAFFIC_PASS_QUIET_VOLUME
        )

    def _update_traffic_passes(self, dt: float) -> None:
        """Fire a whoosh for every bubble vehicle that just changed ends."""
        manager = getattr(self.trip, "traffic_manager", None)
        if manager is None:
            return
        self._traffic_pass_cooldown_s = max(0.0, self._traffic_pass_cooldown_s - dt)
        position = self.trip.position_mi
        truck_mph = self.truck.speed_mph
        live_keys = set()
        for vehicle in manager.vehicles:
            key = vehicle.key
            live_keys.add(key)
            relative = vehicle.position_mi - position
            was = self._traffic_pass_side.get(key)
            self._traffic_pass_side[key] = relative
            if was is None or key in self._traffic_passed_keys:
                continue
            if (was > 0.0) == (relative > 0.0):
                continue  # still on the same end of the truck
            # A marked unit's pass belongs to the enforcement layer, which
            # gives it a marker the civilian clips deliberately lack.
            if str(getattr(vehicle, "vehicle_class", "")).lower() == "state trooper":
                continue
            # Marked passed either way: the vehicle really did go by, and
            # replaying it later when the cooldown lapses would put the
            # whoosh somewhere the vehicle no longer is.
            self._traffic_passed_keys.add(key)
            if self._traffic_pass_cooldown_s > 0.0:
                continue
            self._traffic_pass_cooldown_s = TRAFFIC_PASS_MIN_GAP_S
            closing = truck_mph - vehicle.speed_mph
            volume = self._traffic_pass_volume(closing)
            scale = getattr(self, "_ambience_scale", None)
            if callable(scale):
                volume = min(1.0, volume * min(1.4, scale()))
            # Which side it went by on: anything not sharing the truck's lane
            # passed in another one, and lane indices count leftward.
            side = 0.0 if vehicle.lane == manager.player_lane else TRAFFIC_PASS_PAN
            if vehicle.lane > manager.player_lane:
                side = -TRAFFIC_PASS_PAN
            self.ctx.audio.play(_traffic_vehicle_pass_sound(vehicle), volume=volume, pan=side)
        # A vehicle that has left the bubble is gone for good (the manager
        # never re-spawns a retired cell), so its bookkeeping goes with it
        # rather than growing for the whole run.
        for key in list(self._traffic_pass_side):
            if key not in live_keys:
                del self._traffic_pass_side[key]
                self._traffic_passed_keys.discard(key)


def _traffic_vehicle_pass_sound(vehicle) -> str:
    """The cue for this vehicle class, falling back to the car whoosh."""
    vehicle_class = str(getattr(vehicle, "vehicle_class", "") or "").strip().lower()
    return {
        "semi": "traffic/semi_pass",
        "box truck": "traffic/box_truck_pass",
        "service vehicle": "traffic/box_truck_pass",
        "car": "traffic/car_pass",
    }.get(vehicle_class, "traffic/car_pass")
