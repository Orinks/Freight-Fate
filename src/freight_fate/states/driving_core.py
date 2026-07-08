# ruff: noqa: F401,F821
"""The driving state: live truck control with a fully audio HUD.

Continuous controls (throttle, brake, clutch) are sampled from held keys
each frame. Everything the player needs to know is available on demand from
information keys, and important changes announce themselves.
"""

from __future__ import annotations

import logging
import random

import pygame

from ..achievements import add_unique_stat
from ..data.world import Route
from ..models.economy import pay_advance_grant, pay_advance_unavailable_reason
from ..models.jobs import (
    Job,
    fair_active_deadline,
    job_from_payload,
    job_payload,
    normalize_job_cities,
)
from ..models.settlement import (
    carrier_accessorial_charges,
    charge_summary,
    charge_total,
)
from ..music import (
    music_track_duration_s,
    select_drive_music_sequence,
    select_menu_music_sequence,
)
from ..sim import hos
from ..sim.hos import HosClock, clock_text, is_night, time_of_day
from ..sim.lane import LaneKeeping
from ..sim.timezones import city_zone
from ..sim.transmission import REVERSE
from ..sim.trip import RoadStop, Trip, TripEventKind
from ..sim.vehicle import KG_PER_TON, G, TruckState
from ..sim.weather import WeatherKind, WeatherSystem
from .base import MenuItem, MenuState, State

log = logging.getLogger(__name__)

HAZARD_SAFE_MPH = 25.0
MPH_PER_MPS = 2.23694

# Roadside mechanic: a field patch, not a garage restoration.
FIELD_REPAIR_DAMAGE_PCT = 25.0  # damage level the patch repairs down to
MECHANIC_CALLOUT_FEE = 500.0
MECHANIC_RATE_PER_PCT = 110.0  # premium over the garage's 85 per percent
MECHANIC_WAIT_MIN = 90.0  # game minutes waiting for the truck to be fixed
FUEL_STOP_MIN = 20.0  # fueling is on-duty-not-driving work
INSPECTION_MIN = 15.0  # routine scale/inspection check-in time
OUT_OF_SERVICE_MIN = hos.SLEEP_MIN

# Highway exits: signal inside the window, slow enough to make the ramp.
# The window is the *minimum*; at speed it grows so the spoken callout stays
# far enough out to hear, arm, and brake despite time compression -- see
# _exit_window_mi(), which mirrors the zone-warning lead scaling.
EXIT_WINDOW_MI = 5.0  # how far out X can arm the upcoming exit, at minimum
EXIT_WARNING_REAL_S = 25.0  # target real seconds from callout to the ramp
EXIT_WINDOW_MAX_MI = 20.0
RAMP_MAX_MPH = 45.0  # any faster and you blow past the exit
RAMP_LENGTH_MI = 0.5  # deceleration lane plus ramp to the stop
DESTINATION_EXIT_BEFORE_END_MI = 1.0

CRUISE_MIN_MPH = 20.0  # cruise control needs road speed to hold
CRUISE_STEP_MPH = 5.0  # set-point change per Accel/Coast (+/-) tap
CRUISE_MAX_MPH = 85.0  # highest cruise set point (top US posted limits)
ACC_BASE_GAP_SECONDS = 3.0  # clear-weather adaptive cruise gap
ACC_LIMIT_OFFSET_MPH = 5.0  # predictive ACC holds this far over the posted
# limit -- a with-traffic pace, comfortably under
# the 9 mph speeding-strike threshold
ACC_LIMIT_LOOKAHEAD_MIN_MI = 0.25
ACC_LIMIT_LOOKAHEAD_MAX_MI = 1.5
ACC_LIMIT_LOOKAHEAD_STEP_MI = 0.1
ACC_LIMIT_COMFORT_DECEL_MPS2 = 1.0
ENGINE_SHUTDOWN_SAFE_MPH = 5.0  # prevent accidental kill-switch use at speed
DELIVERY_PARK_MPH = 3.0  # within this, the gate prompts you to stop
DOCKING_MAX_MPH = 0.5  # dock/settle/rest actions need a complete stop


def terse_hazard_message(message: str) -> str:
    text = message.strip()
    for prefix in ("Brake now! ", "Brake now!"):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    return text or message


def timezone_crossing_message(event, terse: bool) -> str:
    """The spoken zone crossing: terse mode says only the zone itself."""
    zone = event.data.get("to_zone")
    if terse and zone is not None:
        return f"{zone.name}."
    return event.message


DRIVE_PHASE_PICKUP = "pickup"
DRIVE_PHASE_DELIVERY = "delivery"

# Microsleeps: once fatigue is severe, the driver involuntarily nods off and
# must respond (steer or brake) within a short window or drift off the road.
# They come faster the more exhausted you are, and escalate to a forced stop.
MICROSLEEP_REACTION_S = 2.2  # real seconds to respond before drifting off
MICROSLEEP_BASE_GM = 9.0  # game-minutes between nods at the severe threshold
MICROSLEEP_MIN_GM = 3.0  # ...shrinking to this nearer total exhaustion
MICROSLEEP_COOLDOWN_GM = 4.0  # quiet period after one resolves
MICROSLEEP_SHOULDER_DAMAGE_PCT = 6.0
MICROSLEEP_FORCE_STOP_MISSES = 3  # consecutive misses that force a stop


def _route_event_sound(event) -> str | None:
    kind = event.kind
    if kind == TripEventKind.HAZARD:
        return "events/hazard_warning"
    if kind == TripEventKind.INSPECTION:
        return "events/inspection_warning"
    if kind == TripEventKind.TOLL_CHARGED:
        return "events/toll_charged"
    if kind in {TripEventKind.STATE_CROSSING, TripEventKind.CHECKPOINT}:
        return "events/state_crossing"
    if kind == TripEventKind.TIMEZONE_CROSSING:
        # A boundary marker like a state line; reuse its earcon until the
        # sound pack gains a dedicated one.
        return "events/state_crossing"
    if kind == TripEventKind.ZONE_ENTER:
        zone = event.data.get("zone")
        if zone is not None and zone.reason == "construction":
            return "events/construction_zone"
        return "events/traffic_slowing"
    if kind == TripEventKind.GPS_CUE:
        cue = event.data.get("cue")
        cue_kind = getattr(cue, "kind", None)
        if cue_kind == "traffic":
            return "events/traffic_slowing"
        if cue_kind == "toll":
            return "events/toll_charged"
    return None


def _poi_ambient_key(stop) -> str:
    if stop.type == "weigh_station":
        return "poi/weigh_station_lane"
    return "poi/rest_stop_night"


def _speeding_settlement_fine(strikes: int) -> float:
    return min(400.0, 80.0 * strikes) if strikes else 0.0


# A strike is recorded only above the posted limit plus this leeway, held for the
# sustained window below -- roughly real-world ticketing tolerance, now judged
# against the leg's real OSM maxspeed rather than a flat number.
SPEEDING_LEEWAY_MPH = 9.0
SPEEDING_HOLD_S = 6.0
# On-the-spot speeding tickets, escalating per ticket within a trip. Paid
# immediately when a trooper pulls you over (unlike the silent at-delivery
# strikes, which stand in for the cost of speeding nobody caught).
SPEEDING_TICKET_FINES = (150.0, 300.0, 600.0, 1200.0)
# Travel this far still moving after the lights come on and it counts as
# ignoring the stop -- a heavier fine and a bigger reputation hit.
PULL_OVER_IGNORE_MI = 2.0


class Tutorial:
    """First-drive guidance, spoken step by step as the player succeeds."""

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self.stage = 0
        self._timer = 0.0
        self._hinted = False

    def begin(self) -> None:
        if self.ctx.settings.speech_verbosity == 0:
            return
        self.ctx.say(
            "This is your first run, so let's walk through it. First: press "
            f"{self.ctx.control_hint('engine')} to start the engine.",
            interrupt=False,
        )

    def on_engine_started(self) -> None:
        if self.stage == 0:
            self.stage = 1
            self._timer = 0.0
            self._hinted = False
            if self.ctx.settings.speech_verbosity == 0:
                return
            if self.ctx.settings.automatic_transmission:
                self.ctx.say(
                    "Now let air pressure build. When you hear air ready, "
                    f"press {self.ctx.control_hint('parking_brake')} to release "
                    f"the parking brake, then hold {self.ctx.control_hint('accelerate')} "
                    "to accelerate. The transmission shifts for you.",
                    interrupt=False,
                )
            else:
                self.ctx.say(
                    "Now let air pressure build. When you hear air ready, "
                    f"press {self.ctx.control_hint('parking_brake')} to release "
                    f"the parking brake, then hold {self.ctx.control_hint('clutch')}, "
                    f"select {self.ctx.control_hint('gear_first')} for first gear, "
                    "and release the clutch.",
                    interrupt=False,
                )

    def on_parking_brake_released(self) -> None:
        if self.stage == 1 and self.ctx.settings.automatic_transmission:
            self.stage = 2
            self._timer = 0.0
            self._hinted = False
            message = (
                "Parking brake released."
                if self.ctx.settings.speech_verbosity == 0
                else "Parking brake released. Now hold "
                f"{self.ctx.control_hint('accelerate')} to accelerate."
            )
            self.ctx.say(message, interrupt=False)
        elif self.stage == 1:
            self._timer = 0.0
            self._hinted = False
            message = (
                "Parking brake released."
                if self.ctx.settings.speech_verbosity == 0
                else "Parking brake released. Now shift into first gear."
            )
            self.ctx.say(message, interrupt=False)

    def on_gear_engaged(self) -> None:
        if self.stage == 1:
            self.stage = 2
            self._timer = 0.0
            self._hinted = False
            message = (
                "In gear."
                if self.ctx.settings.speech_verbosity == 0
                else f"In gear. Now hold {self.ctx.control_hint('accelerate')} to accelerate."
            )
            self.ctx.say(message, interrupt=False)

    def update(self, dt: float, truck) -> None:
        self._timer += dt
        if self.stage == 2 and truck.speed_mph > 20:
            self.stage = 3
            if self.ctx.settings.speech_verbosity == 0:
                self.ctx.say("Rolling.", interrupt=False)
            else:
                self.ctx.say(
                    "You are rolling. Press "
                    f"{self.ctx.control_hint('speed')} anytime for your speed, "
                    f"{self.ctx.control_hint('status_menu')} for a full report, and "
                    f"{self.ctx.control_hint('help')} to hear all the controls. "
                    "Watch for hazard warnings, and brake hard when you hear them. "
                    f"Press {self.ctx.control_hint('emergency_brake')} when you need "
                    "to stop fast. Safe travels.",
                    interrupt=False,
                )
            self.ctx.profile.tutorial_done = True
            self.ctx.save_profile()
        elif self.stage in (0, 1) and self._timer > 25 and not self._hinted:
            self._hinted = True
            if self.ctx.settings.speech_verbosity == 0:
                return
            if self.stage == 0:
                self.ctx.say(
                    f"Reminder: press {self.ctx.control_hint('engine')} to start the engine.",
                    interrupt=False,
                )
            elif truck.parking_brake:
                self.ctx.say(
                    "Reminder: wait for air pressure to reach 100 psi, then press "
                    f"{self.ctx.control_hint('parking_brake')} to release the parking brake.",
                    interrupt=False,
                )
            else:
                self.ctx.say(
                    f"Reminder: hold {self.ctx.control_hint('clutch')}, "
                    f"select {self.ctx.control_hint('gear_first')}, "
                    "then release the clutch.",
                    interrupt=False,
                )


def _advance_rest_clock(driving: DrivingState, minutes: float) -> None:
    """Resting advances game time, so deadlines keep counting."""
    driving.trip.game_minutes += minutes
    driving.weather.update(minutes)


def _shut_down_engine(driving: DrivingState) -> str:
    """Stop the engine before a night's sleep; no truck idles through ten
    hours. Returns the spoken prefix, empty when it was already off."""
    if not driving.truck.engine_on:
        return ""
    driving.truck.stop_engine()
    return "You shut down the engine. "


def _deadline_appointment(driving: DrivingState) -> str:
    """The delivery appointment in the receiving city's local time.

    Anchored on the job's destination, not the current trip's endpoint: a
    pickup drive ends at the origin facility, possibly in another zone.
    """
    zone = city_zone(driving.ctx.world.city(driving.job.destination))
    return driving.trip.deadline_clock_text(driving.job.deadline_game_h, zone)


def _deadline_text(driving: DrivingState) -> str:
    remaining = driving.job.deadline_game_h - driving.trip.game_minutes / 60.0
    if remaining > 0:
        # The appointment reads in the receiver's local time, the way a real
        # dispatcher quotes it -- the zone name keeps it unambiguous mid-route.
        return f"{remaining:.1f} hours left to deliver; that is {_deadline_appointment(driving)}."
    return f"You are now {-remaining:.1f} hours past the deadline."


def _perform_shoulder_sleep(driving: DrivingState, anchor_mi: float) -> str:
    """Apply the emergency shoulder-sleep outcome and return spoken text."""
    p = driving.ctx.profile
    engine_off = _shut_down_engine(driving)
    _advance_rest_clock(driving, hos.SLEEP_MIN)
    driving.hos.sleep()
    p.fatigue = hos.rest_shoulder(p.fatigue)
    parts = [
        f"{engine_off}You sleep poorly on the shoulder, woken again and again by "
        f"passing trucks. It is {clock_text(driving.trip.local_hour)}. "
        f"Hours of service reset, but you are still tired."
    ]
    if hos.shoulder_fine_due(driving.trip_seed, anchor_mi):
        p.money -= hos.SHOULDER_FINE
        driving.ctx.audio.play("ui/error")
        parts.append(
            f"A trooper ticketed you for illegal parking: "
            f"{hos.SHOULDER_FINE:,.0f} dollars. "
            f"You have {p.money:,.0f} dollars."
        )
    if hos.shoulder_damage_due(driving.trip_seed, anchor_mi):
        driving.truck.damage_pct = min(100.0, driving.truck.damage_pct + hos.SHOULDER_DAMAGE_PCT)
        parts.append(
            f"Roadside debris and wake turbulence added "
            f"{hos.SHOULDER_DAMAGE_PCT:.0f} percent truck damage."
        )
    p.truck_fuel_gal = driving.truck.fuel_gal
    p.truck_damage_pct = driving.truck.damage_pct
    p.active_trip = driving.snapshot()
    driving.ctx.save_profile()
    parts.append(_deadline_text(driving))
    return " ".join(parts)


POI_ACTION_LABELS = {
    "park": "parking",
    "save": "save point",
    "fuel": "fuel",
    "food": "food and coffee",
    "break": "30-minute rest break",
    "sleep": "sleep or long rest",
    "repair": "repairs",
    "roadside_assistance": "roadside assistance",
    "towing": "towing",
    "inspect": "inspection check-in",
}

POI_SERVICE_LABELS = {
    "diesel": "diesel",
    "food": "food",
    "parking": "truck parking",
    "truck_parking": "truck parking",
    "restrooms": "restrooms",
    "scale": "scale",
    "repair": "repair",
    "roadside_assistance": "roadside assistance",
    "towing": "towing",
}


def _join_phrase(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def _poi_offers_text(stop) -> str:
    offers = [POI_ACTION_LABELS[action] for action in stop.actions if action in POI_ACTION_LABELS]
    services = [
        POI_SERVICE_LABELS.get(service, service.replace("_", " ")) for service in stop.services
    ]
    parts = []
    if offers:
        parts.append(f"offers {_join_phrase(offers)}")
    if services:
        parts.append(f"listed services: {_join_phrase(services)}")
    if getattr(stop, "parking_text", ""):
        parts.append(stop.parking_text)
    return "; ".join(parts) if parts else "services not listed"


__all__ = [name for name in globals() if not name.startswith("__")]
