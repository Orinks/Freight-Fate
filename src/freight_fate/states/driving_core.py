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

from ..achievements import add_unique_stat, increment_stat
from ..data.amenities import spoken_amenities
from ..data.world import Route
from ..models.business import (
    build_business_settlement,
    is_owner_operator,
    pay_label,
    player_pays_operating_costs,
    reputation_pay_bonus,
)
from ..models.career import xp_class_multiplier, xp_streak_bonus
from ..models.economy import MOTEL_COST, pay_advance_grant, pay_advance_unavailable_reason
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
    RADIO_TRACKS_PER_HOST_BREAK,
    music_track_duration_s,
    select_drive_music_sequence,
    select_host_segments,
    select_menu_music_sequence,
    select_station_playlist,
)
from ..radio import (
    SAFE_ROUTE_PLAYLIST,
    STATIC_SIGNAL_THRESHOLD,
    RadioPlaybackError,
    RadioState,
    RadioStation,
    signal_volume_factor,
    truck_position,
)
from ..sim import hos
from ..sim.hos import HosClock, clock_text, is_night, time_of_day
from ..sim.lane import LaneKeeping, lane_label
from ..sim.timezones import city_zone
from ..sim.transmission import REVERSE
from ..sim.trip import RoadStop, Trip, TripEventKind
from ..sim.trip_models import leg_lane_count
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
STOP_PULL_IN_MIN = 5.0
STOP_PULL_IN_WAIT_S = 1.0

# Highway exits: signal inside the window, slow enough to make the ramp.
# The window is the *minimum*; at speed it grows so the spoken callout stays
# far enough out to hear, arm, and brake despite time compression -- see
# _exit_window_mi(), which mirrors the zone-warning lead scaling.
EXIT_WINDOW_MI = 5.0  # how far out X can arm the upcoming exit, at minimum
EXIT_WARNING_REAL_S = 25.0  # target real seconds from callout to the ramp
EXIT_WINDOW_MAX_MI = 20.0
EXIT_LANE_PREP_MI = 2.0  # where GPS starts asking for the exit lane
EXIT_COMMIT_WINDOW_MI = 0.4  # generous gore-window grace after the marker
EXIT_LANE_READY = 0.85  # accumulated right-lane commitment
EXIT_LANE_OFFSET_READY = 0.45  # right-side lane position also counts
RAMP_MAX_MPH = 45.0  # any faster and you blow past the exit
RAMP_LENGTH_MI = 0.5  # deceleration lane plus ramp to the stop
# Ramp terminals: where the off-ramp meets the surface road there is usually
# a light or a stop sign (diamond interchanges), occasionally free flow
# (cloverleafs). The control comes from baked OSM traffic_signals/stop nodes
# on the ramp links when available, else a seeded urban/rural heuristic.
RAMP_ACCESS_MI = 0.12  # terminal-to-driveway stretch at the ramp's end
RAMP_CONTROL_ANNOUNCE_MI = 0.38  # where the terminal callout fires on the ramp
RAMP_LIGHT_RED_S = 12.0  # red phase of the terminal light, real seconds
RAMP_LIGHT_GREEN_S = 9.0  # green phase, real seconds
RED_STOP_MPH = 3.0  # at or under this you have honored a red or a stop sign
RAMP_TERMINAL_GRACE_MI = 0.02  # rolling this far past the bar commits the violation
GREEN_ROLL_MPH = 25.0  # green lets you roll the terminal up to this
STOP_ROLL_CLIP_MPH = 15.0  # blowing a stop sign this fast clips cross traffic
RED_RUN_DAMAGE = 0.3  # collision severity for running the red
STOP_ROLL_DAMAGE = 0.2  # lighter clip for blowing the stop sign
# Heuristic control mix when OSM has none baked: (signal, stop) cumulative
# weights; the remainder is free flow. Urban terminals are mostly signalized.
RAMP_CONTROL_URBAN_WEIGHTS = (0.70, 0.95)
RAMP_CONTROL_RURAL_WEIGHTS = (0.30, 0.80)
DESTINATION_EXIT_BEFORE_END_MI = 1.0
UNLOADING_MIN = 45.0  # receiver dock work before settlement
UNLOADING_WAIT_S = 1.5

# Discrete lanes on top of the LaneKeeping drift model. With steering assist
# on, holding the wheel across the lane line is the lane change; with assist
# off, a Left/Right arrow tap runs a timed change with signal clicks.
LANE_MIN_MPH = 10.0  # below this there is nothing to steer
LANE_TAP_CHANGE_S = 2.5  # assist-off timed drift across the line
LANE_SIGNAL_CLICK_S = 0.45  # turn-signal cadence during a tap change
MERGE_WINDOW_S = 8.0  # time to vacate a coned-off lane after the warning
MERGE_BARRELS_DAMAGE = 0.25  # collision severity for riding into the barrels
SIDESWIPE_DAMAGE = 0.35  # changing lanes into occupied space costs more
DODGE_CLEARANCE_AHEAD_MI = 0.35  # target lane must be clear this far ahead...
DODGE_CLEARANCE_BEHIND_MI = 0.15  # ...and this far behind your drive tires
KEEP_RIGHT_NAG_S = 45.0  # left-lane camping before the CB calls you out
KEEP_RIGHT_REPEAT_S = 75.0  # spacing for repeat nags while still camping
KEEP_RIGHT_MIN_MPH = 45.0  # lane discipline only matters at highway speed
PASSING_LOOKAHEAD_MI = 0.6  # slower right-lane traffic inside this justifies the left lane

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
    """Trim the hazard call for terse speech.

    "Brake now!" is implied by the hazard tone and can go; "Brake or change
    lanes!" carries real information -- the hazard is dodgeable -- so terse
    mode keeps it as a two-word cue instead of dropping it."""
    text = message.strip()
    for prefix in ("Brake now! ", "Brake now!"):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    for prefix in ("Brake or change lanes! ", "Brake or change lanes!"):
        if text.startswith(prefix):
            text = "Brake or swerve! " + text[len(prefix) :].strip()
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
DRIVE_PHASE_CITY_SERVICE = "city_service"

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
        if event.data.get("cb_patrol") is not None:
            return "events/cb_radio_chatter"
        if event.data.get("traffic_pressure") is not None:
            return "events/traffic_slowing"
        cue = event.data.get("cue")
        cue_kind = getattr(cue, "kind", None)
        if cue_kind == "local_turn":
            return _local_turn_sound(cue)
        if cue_kind == "traffic":
            return _traffic_vehicle_sound(event)
        if cue_kind == "toll":
            return "events/toll_charged"
    return None


def _traffic_vehicle_sound(event) -> str:
    vehicle = event.data.get("npc_vehicle")
    vehicle_class = str(getattr(vehicle, "vehicle_class", "") or "").strip().lower()
    if vehicle_class == "state trooper":
        return "traffic/trooper_pass"
    if vehicle_class == "semi":
        return "traffic/semi_pass"
    if vehicle_class == "box truck":
        return "traffic/box_truck_pass"
    if vehicle_class == "car":
        return "traffic/car_pass"
    return "events/traffic_slowing"


def _local_turn_sound(cue) -> str | None:
    direction = str(getattr(cue, "direction", "") or "").strip().lower()
    sounds = {
        "left": "events/turn_left",
        "right": "events/turn_right",
        "ahead": "events/turn_ahead",
        "straight": "events/turn_ahead",
    }
    return sounds.get(direction)


def _poi_ambient_key(stop, hour: float) -> str:
    if stop.type == "weigh_station":
        return "poi/weigh_station_lane"
    if is_night(hour):
        return "poi/rest_stop_night"
    return "ambient/truck_stop"


def _speeding_settlement_fine(strikes: int) -> float:
    return min(400.0, 80.0 * strikes) if strikes else 0.0


def _record_inspection(ctx, *, event: bool = False) -> None:
    """Every inspection feeds both the one-off badge and the career tally."""
    ctx.award_achievement("inspection", event=event)
    if ctx.profile is not None and increment_stat(
            ctx.profile, "inspections_passed") >= 5:
        ctx.award_achievement("scale_regular", event=event)


class _DrivingRadioBackend:
    """Adapts radio station choices onto the existing safe music backend."""

    def __init__(self, driving: DrivingState) -> None:
        self.driving = driving

    def play_station(self, station: RadioStation, volume: float) -> None:
        radio = getattr(self.driving, "radio", None)
        if radio is not None:
            self.driving._radio_signal_factor = signal_volume_factor(radio.current_reception())
        if station.real_stream:
            if not station.stream_url:
                raise RadioPlaybackError("station has no stream URL")
            self.driving._apply_radio_volume()
            try:
                self.driving.ctx.audio.play_radio_stream(station.stream_url, fade_ms=900)
            except RuntimeError as exc:
                raise RadioPlaybackError("external stream playback failed") from exc
            return
        self.driving._apply_radio_volume()
        if station.fallback:
            self.driving.ctx.audio.stop_music(600)
        else:
            self.driving._start_station_rotation(station, fade_ms=900)

    def stop_radio(self) -> None:
        self.driving.ctx.audio.stop_music(600)


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
FAILURE_TO_STOP_WARNING_MI = 0.8
FAILURE_TO_STOP_FINAL_WARNING_MI = 1.5
FAILURE_TO_STOP_FINE = 2500.0
FAILURE_TO_STOP_DAMAGE_PCT = 12.0
FAILURE_TO_STOP_PROCESSING_MIN = 180.0
WEIGH_STATION_NOTICE_MI = 2.0
WEIGH_STATION_BYPASS_MPH = 15.0
WEIGH_STATION_BYPASS_FINE = 750.0
UNSAFE_DAMAGE_STOP_PCT = 65.0
UNSAFE_DAMAGE_FINE = 900.0
AMBIENT_EVENT_SPACING_S = 2.5  # keep low-priority chatter from stacking


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


def _advance_rest_clock(
    driving: DrivingState, minutes: float, duty_status: str | None = None, note: str = ""
) -> None:
    """Resting advances game time, so deadlines keep counting."""
    start_hour = driving._absolute_game_hour()
    driving.trip.game_minutes += minutes
    driving.weather.update(minutes)
    if duty_status is not None:
        driving.ctx.profile.duty_log.record(
            duty_status,
            start_hour,
            driving._absolute_game_hour(),
            driving._logbook_location(),
            note,
        )


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
    p.store_truck_condition(driving.truck)
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
    brand_text = spoken_amenities(stop.name, getattr(stop, "type", ""))
    if brand_text:
        parts.append(brand_text)
    if getattr(stop, "parking_text", ""):
        parts.append(stop.parking_text)
    return "; ".join(parts) if parts else "services not listed"


__all__ = [name for name in globals() if not name.startswith("__")]
