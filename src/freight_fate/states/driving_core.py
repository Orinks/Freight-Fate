# ruff: noqa: F401,F821
"""The driving state: live truck control with a fully audio HUD.

Continuous controls (throttle, brake, clutch) are sampled from held keys
each frame. Everything the player needs to know is available on demand from
information keys, and important changes announce themselves.
"""

from __future__ import annotations

import logging
import math
import random
import re

import pygame

from ..achievements import add_unique_stat, increment_stat, reset_stat
from ..data.amenities import classify_brand, spoken_amenities
from ..data.buffs import buffs_for_stop
from ..data.world import Route
from ..models.business import (
    build_business_settlement,
    has_weigh_station_transponder,
    is_owner_operator,
    pay_label,
    player_pays_operating_costs,
    reputation_pay_bonus,
)
from ..models.career import xp_class_multiplier, xp_streak_bonus
from ..models.economy import (
    MOTEL_COST,
    damage_severity_mult,
    pay_advance_grant,
    pay_advance_unavailable_reason,
)
from ..models.enforcement import (
    career_citations,
    citation_fine,
    construction_zone_fine_clause,
)
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
    select_drive_music_sequence,
    select_menu_music_sequence,
    select_station_playlist,
)
from ..radio import (
    PERSONAL_PLAYLIST_SOURCE_TYPE,
    SAFE_ROUTE_PLAYLIST,
    SIGNAL_FULL_VOLUME,
    STATIC_SIGNAL_THRESHOLD,
    RadioPlaybackError,
    RadioState,
    RadioStation,
    signal_volume_factor,
    truck_position,
)
from ..radio_content import content_duration_s, plan_break
from ..sim import hos
from ..sim.driving_modes import tuning_for_time_scale
from ..sim.enforcement_observe import OBSERVE_LEEWAY_MPH
from ..sim.hos import HosClock, clock_text, is_night, time_of_day
from ..sim.lane import CURVE_RATE, LaneKeeping, lane_label, lane_phrase
from ..sim.lane_guidance import LaneGuidance
from ..sim.timezones import city_zone
from ..sim.transmission import REVERSE
from ..sim.trip import RoadStop, Trip, TripEventKind
from ..sim.trip_models import (
    APPROACH_DECEL_MPS2,
    APPROACH_REACTION_S,
    DESTINATION_LOCAL_APPROACH_MI,
    METERS_PER_MILE,
    RAMP_MIN_DESIGN_MPH,
    acceleration_lane_mi,
)
from ..sim.trip_models import RAMP_MAX_MPH as TRIP_RAMP_MAX_MPH
from ..sim.vehicle import (
    CHAIN_SAFE_MPH,
    DAMAGE_BAND_LAST_CALL,
    DAMAGE_BAND_LIMP,
    DAMAGE_BAND_NONE,
    DAMAGE_BAND_OUT_OF_SERVICE,
    DAMAGE_BAND_REDUCED,
    DAMAGE_CREEP_CAP_MPH,
    DAMAGE_DERATE_PCT,
    DAMAGE_LAST_CALL_PCT,
    DAMAGE_LIMP_CAP_MPH,
    DAMAGE_LIMP_PCT,
    DAMAGE_MAX_PCT,
    DAMAGE_OUT_OF_SERVICE_PCT,
    HIGH_IDLE_DEFAULT_RPM,
    HIGH_IDLE_MAX_RPM,
    HIGH_IDLE_MIN_RPM,
    HIGH_IDLE_STEP_RPM,
    JAKE_STAGES,
    KG_PER_TON,
    REFERENCE_CARGO_KG,
    REVERSE_ENGAGE_MAX_MPH,
    TIRE_WINTER,
    G,
    TruckState,
)
from ..sim.weather import WeatherKind, WeatherSystem
from ..sound_catalog import BAR_SOLID_VOLUME
from ..speech_pacing import EventPriority
from .base import MenuItem, MenuState, State

log = logging.getLogger(__name__)

HAZARD_SAFE_MPH = 25.0
# A fixed object in your lane -- debris, a stopped vehicle -- cannot be
# rolled over at 25: clearing it by brake alone means coming nearly to a
# stop and easing around. A lane change remains the no-time-lost answer.
HAZARD_CREEP_MPH = 8.0
MPH_PER_MPS = 2.23694

# Roadside mechanic: a field patch, not a garage restoration.
FIELD_REPAIR_DAMAGE_PCT = 25.0  # damage level the patch repairs down to
MECHANIC_CALLOUT_FEE = 500.0
MECHANIC_RATE_PER_PCT = 110.0  # premium over the garage's 85 per percent
MECHANIC_WAIT_MIN = 90.0  # game minutes waiting for the truck to be fixed
# A full breakdown is the emergency version of that call-out: the truck is
# dead where it stopped, so the fee is the premium and the repair only gets
# the truck moving again -- it does not put it right. The rate per percent is
# the same road rate; the difference is the call-out and the hours.
BREAKDOWN_CALLOUT_FEE = 1200.0
BREAKDOWN_REPAIR_DAMAGE_PCT = 60.0  # still deep in reduced power afterwards
BREAKDOWN_REPAIR_MIN = 180.0  # game minutes at the side of the road
BREAKDOWN_REPUTATION_HIT = 5.0  # a company driver's record instead of their wallet
# A carrier does not send a driver back out in equipment it just had to
# recover: it grounds the tractor and covers the bill, and what the driver
# loses is the day and their standing. Waiting on the yard to bring iron out
# to a stranded truck is slower than a mechanic patching one, which is the
# whole trade -- the company driver keeps their money and pays in hours.
GROUNDED_SWAP_MIN = 300.0  # game minutes waiting on a replacement tractor
GROUNDED_SPARE_DAMAGE_PCT = 15.0  # a yard spare is used equipment, not a new one
# How long a driver may crawl an out-of-service truck before road service
# reaches them anyway. Real seconds: it is a window to clear a live lane,
# not a way to finish the run at ten miles an hour.
OUT_OF_SERVICE_RECOVERY_GRACE_S = 60.0
# What the carrier charges a company driver at settlement for damage its own
# safety committee ruled preventable. The carrier still pays the repair --
# this is the deductible and the voided safety bonus, which is how a real
# company driver feels damage in the wallet without being handed the whole
# invoice. Scaled by the deepest band the run reached, because a driver who
# spent it in limp mode did something to get there.
PREVENTABLE_DAMAGE_DEDUCTIBLE = 250.0  # per band reached, at full preventable share
PREVENTABLE_REPUTATION_PER_BAND = 1.5  # standing lost per band reached
# How fast limp mode winds the road-speed cap down: the same "about 2 mph per
# second of comfortable braking" the dropped-speed-limit grace is built on, so
# the cap never snaps a speed out from under the driver.
LIMP_CAP_RAMP_MPH_PER_S = 2.0
# Chaining up is done kneeling on the shoulder in the weather that made it
# necessary. Real crews quote twenty to thirty minutes for a drive-axle set;
# doing it in the dark by headlamp costs more time and much more out of the
# driver. Removal is quick by comparison.
CHAIN_INSTALL_MIN = 25.0
CHAIN_INSTALL_NIGHT_MULT = 1.6
CHAIN_REMOVE_MIN = 10.0
CHAIN_INSTALL_FATIGUE = 6.0
CHAIN_INSTALL_NIGHT_FATIGUE = 10.0
CHAIN_REMOVE_FATIGUE = 2.0
# Rolling into an active chain law out of compliance: the checkpoint at the
# bottom of the grade is staffed often enough that gambling is a bad trade.
# What the citation costs is priced in models/enforcement with every other fine.
CHAIN_LAW_CHECKPOINT_CHANCE = 0.6
# Road wear service at branded travel centers -- the brand IS the capability
# (amenities.classify_brand): Love's and Speedco run dedicated tire bays at
# close to the terminal-garage rate and turn the truck around fast; TA and
# Petro full-service shops also reline brakes; every other major travel
# center can mount tires at a road markup. Engine overhauls stay in the
# terminal garage, and a landmark like Big Buck's fixes nothing.
ROAD_TIRE_SPECIALIST_COST_PER_PCT = 50.0  # tire brands, near the garage's 45
ROAD_TIRE_SPECIALIST_MIN = 45.0
ROAD_TIRE_COST_PER_PCT = 60.0  # everyone else marks tire work up
ROAD_TIRE_MIN = 75.0
ROAD_BRAKE_COST_PER_PCT = 55.0  # road-shop premium over the garage's 40
ROAD_BRAKE_MIN = 120.0
FUEL_STOP_MIN = 20.0  # fueling is on-duty-not-driving work
INSPECTION_MIN = 15.0  # routine scale/inspection check-in time
OUT_OF_SERVICE_MIN = hos.SLEEP_MIN
# Dynamiting the parking brake: pulling the valve at speed slams the spring
# brakes on and grinds flat spots into the tires. Above this speed the set
# is treated as the violent emergency move it really is; the tread cost
# scales with speed (55 mph costs about a percent and a half of tread).
DYNAMITE_MIN_MPH = 5.0
FLAT_SPOT_WEAR_PCT_PER_MPH = 0.028
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
# Keep the exact announced destination exit available for the same real-time
# budget even if coasting or automatic braking shrinks the dynamic window.
DESTINATION_EXIT_RESPONSE_GRACE_S = EXIT_WARNING_REAL_S
# Spoken distance anchors for an armed exit; a signal-on announcement miles
# out gets buried under canyon pacenotes without them.
EXIT_COUNTDOWN_MILESTONES_MI = (2.0, 1.0, 0.5)
# The pacenote cue tone leans hard toward the curve's side of the field.
PACENOTE_CUE_PAN = 0.85
EXIT_COMMIT_WINDOW_MI = 0.4  # generous gore-window grace after the marker
EXIT_LANE_READY = 0.85  # accumulated right-lane commitment
EXIT_LANE_OFFSET_READY = 0.45  # right-side lane position also counts
EXIT_CANCEL_GUARD_MI = 1.0  # inside this, X keeps the signal; a second press cancels
EXIT_TAP_HOLD_S = 0.35  # a Right press this short is a tap, not held steering
AEB_BUDGET_MARGIN = 1.2  # emergency braking leads the physics budget by this factor
AEB_LEAD_S = 0.5  # plus this flat lead, covering brake heat added during the stop
# The assist brakes on the SERVICE brakes, and the escalation to the emergency
# application is judged on what the truck is actually doing rather than on what
# a full application ought to deliver. The measured deceleration is smoothed
# over this long, is not judged at all until the pedal has been down for one
# smoothing constant, and the shortfall has to hold for the confirm window --
# one noisy frame is not a losing stop.
AEB_DECEL_SMOOTHING_S = 0.4
AEB_ESCALATE_CONFIRM_S = 0.5
# Floor on the driver's own time between hearing a hazard warning and the
# assist taking the truck. Long enough to hear the sentence out and get on
# the pedal: the warning is spoken, so a window shorter than the words is no
# window at all. A dodgeable hazard adds LANE_TAP_CHANGE_S on top, because
# "or change lanes" names a maneuver that takes that long to finish.
HAZARD_MIN_REACTION_S = 3.0
RAMP_CREEP_MI = 0.04  # within ~200 ft of the bar, "creep"; farther is a drive
# Any faster and you blow past the exit. Defined in the portable layer,
# because the arrival speed zones are built from the same number: the
# destination approach must never cap below the speed the ramp needs.
RAMP_MAX_MPH = TRIP_RAMP_MAX_MPH
# How far under a ramp's own design speed automatic control aims. Was the
# gap between a flat 40 and a flat 45; now it is the gap itself, applied to
# whatever number the ramp earns.
RAMP_CRUISE_HEADROOM_MPH = 5.0
RAMP_CRUISE_TARGET_MPH = RAMP_MAX_MPH - RAMP_CRUISE_HEADROOM_MPH
# Ceiling on the light throttle exit speed assistance uses to HOLD that target
# once it has slowed the truck to it. Deliberately small: the assist is keeping
# a truck rolling to its own gore, not driving it.
EXIT_HOLD_MAX_THROTTLE = 0.45
RAMP_LENGTH_MI = 0.5  # deceleration lane plus ramp to the stop
# Ramp terminals: where the off-ramp meets the surface road there is usually
# a light or a stop sign (diamond interchanges), occasionally free flow
# (cloverleafs). The control comes from baked OSM traffic_signals/stop nodes
# on the ramp links when available, else a seeded urban/rural heuristic.
RAMP_ACCESS_MI = 0.12  # terminal-to-driveway stretch at the ramp's end
# Rolling stop-bar countdown milestones (spoken as each is crossed while
# moving): the bar needs a position the way an exit does, or a driver
# stops a quarter mile short and creeps blind (owner playtest, 2026-07-19).
RAMP_GAP_MILESTONES_FT = (1000, 500, 300, 150)
RAMP_GAP_MILESTONES_M = (300, 150, 100, 50)
# Parking-sensor tick for the stop bar (owner ask, 2026-07-19): inside
# this range a center tick speeds up as the bar closes -- rate carries
# the distance, silence means stopped. Placeholder ui/tick until the
# audio-design pass gives the bar its own voice (steering-sound RFC).
RAMP_BAR_TICK_RANGE_MI = 300.0 / 5280.0
# The bar's final leeway: inside this, still rolling, the ticks fuse into a
# continuous tone -- be nearly stopped or eat the intersection (owner spec,
# written straight into the manual, 2026-07-27). About sixty feet.
RAMP_BAR_SOLID_MI = 0.012
RAMP_BAR_TICK_SLOW_S = 1.1  # period at the edge of the range
RAMP_BAR_TICK_FAST_S = 0.15  # period at the bar
# Ground covered while the driver hears the cue and gets to the pedal. The bar
# is the one place in the game where the cue IS the instrument, so its range
# has to pay for the listening as well as the stopping.
RAMP_BAR_REACTION_S = 1.5
# Safety-call re-arm: Ctrl always silences (a screen-reader reflex must
# never be fought), but a curve call cut inside this window re-speaks
# once, refreshed, after the delay -- IF the bend is still ahead and the
# truck is still hot. A stale warning re-spoken is worse than none.
CRITICAL_CALL_WINDOW_S = 8.0
CRITICAL_RESPEAK_DELAY_S = 2.0
RAMP_CONTROL_ANNOUNCE_MI = 0.38  # where the terminal callout fires on the ramp
RAMP_LIGHT_RED_S = 12.0  # red phase of the terminal light, real seconds
RAMP_LIGHT_GREEN_S = 15.0  # green phase: a real minor-leg minimum, crossable from a stop
RAMP_LIGHT_YELLOW_S = 4.0  # yellow phase; entering on yellow is legal, like the real law
RED_STOP_MPH = 3.0  # at or under this you have honored a red or a stop sign
# The stop bar's continuous tone level (BAR_SOLID_VOLUME) is imported from
# ..sound_catalog at the top of this module, so the road and the Learn game
# sounds screen can never drift apart.
# A direction change engages only after the control is held this long at a
# standstill: a confirm-tap on the brake must never grab reverse.
DIRECTION_CHANGE_HOLD_S = 0.6
RAMP_TERMINAL_GRACE_MI = 0.02  # rolling this far past the bar commits the violation
# Route-transition assistance at the terminal: the assist starts braking when
# stopping at the bar needs this much deceleration, maps needed deceleration
# to brake application against the nominal full-service figure, and holds the
# stop once the truck is within the hold window short of the bar.
RAMP_ASSIST_DECEL_START_MPS2 = 0.6
# The destination approach: how hard the assist is willing to shed to ARRIVE
# stopped, and the brake it uses. Gentler than the ramp figure -- an approach
# is a street chain with a gate at the end, and the point is that the stop is
# comfortable rather than a grab.
APPROACH_ASSIST_DECEL_MPS2 = 0.9
# Seconds of road the arrival shed starts EARLY, so the brake has time to
# build before the stop profile binds. Not a change to where the truck
# stops -- the profile still aims at the arrival point -- only to when it
# begins. The exit approach prices its own road the same way
# (APPROACH_REACTION_S); this is the shorter arrival-speed version of the
# same budget, because a truck already down to street speed needs the
# pressure built, not a driver reaction.
APPROACH_ASSIST_REACTION_S = 3.0
APPROACH_ASSIST_BRAKE = 0.4
RAMP_ASSIST_FULL_DECEL_MPS2 = 3.0
RAMP_ASSIST_HOLD_MI = 60.0 / 5280.0
# How far the demand has to fall below the pedal the assist is already holding
# before it eases off. Easing costs nothing; coming back on is charged a whole
# brake application by the air system, so a servo that chases every dip in the
# demand empties the tanks on one approach.
RAMP_ASSIST_RELEASE_BAND = 0.05
GREEN_ROLL_MPH = 25.0  # green lets you roll the terminal up to this
STOP_ROLL_CLIP_MPH = 15.0  # blowing a stop sign this fast clips cross traffic
# A yield taken in a real gap is legal at or under this -- the whole point of
# the sign is that a clear road never demands the stop.
YIELD_ROLL_MPH = 15.0
RED_RUN_DAMAGE = 0.3  # collision severity for running the red
STOP_ROLL_DAMAGE = 0.2  # lighter clip for blowing the stop sign
# Heuristic control mix when OSM has none baked: (signal, stop) cumulative
# weights; the remainder is free flow. Urban terminals are mostly signalized.
# A ramp onto ANOTHER FREEWAY is a system interchange: it ends in a merge,
# never a stop sign and never a light. Nothing stops traffic where an
# interstate meets an interstate. 4,999 of the world's 18,011 exits -- 27.8
# percent -- lead to one, and every single one of them was rolling the dice
# below, so half the rural ones were being given stop signs that cannot
# exist (owner, 2026-08-17: "no stop signs at the end of ramps"). Matched on
# the interchange's own `via`, which is baked from OSM.
FREEWAY_VIA_RE = re.compile(r"\bI[-\s]?\d")

# Cumulative (signal, stop) thresholds for a ramp terminal OSM never tagged:
# roll < signal_w is a light, < stop_w is a stop sign, above is free flow.
#
# The signal-to-stop SPLIT is calibrated, not invented. Of the 8,205 baked
# interchanges where OSM does tag a control, the split is 88.7 / 11.3 within
# URBAN_RADIUS_MI of a route city and 64.3 / 35.7 outside it -- both readings,
# since a signal and a stop sign are equally tagged when either exists. The
# old rural pair asserted 30 / 50, handing out roughly twice the stop signs
# reality has and half the lights, which is what made every country exit feel
# like a farm road.
#
# The free-flow SHARE is the assumed part and is left where it was (5 percent
# urban, 20 percent rural), because it cannot be read: OSM records controls
# that exist and says nothing at all where a ramp merges freely, so absence of
# a tag is not evidence of absence of a control. The far-end bake (2026-08-20)
# shrank the pool these weights govern: exits whose ramp chains provably merge
# onto another motorway carry ramp_control=none outright, and a proven surface
# terminal suppresses the via guess above, so the dice now decide only the
# exits topology could not judge plus the surface terminals OSM left untagged.
# The shares are NOT recalibrated for that smaller pool -- free flow at a
# surface terminal (a channelized merge onto a frontage road) still exists and
# still cannot be read, so the assumption stands, declared here.
_URBAN_FREE_FLOW = 0.05
_RURAL_FREE_FLOW = 0.20
RAMP_CONTROL_URBAN_WEIGHTS = (0.843, 1.0 - _URBAN_FREE_FLOW)
RAMP_CONTROL_RURAL_WEIGHTS = (0.514, 1.0 - _RURAL_FREE_FLOW)
# Grace past the end of the ramp before a taken-but-never-stopped exit counts
# as blown. Distance alone is not enough under trip pacing: at 40 mph the same
# half mile can pass in barely a second, before the driver can hear the arrival
# cue and set the brake. Require both this distance and a real-time reaction
# window. A driver who keeps rolling still misses the stop promptly.
RAMP_OVERSHOOT_MI = 0.5
# Blowing the destination terminal at the end of the ramp costs a scripted
# loop-back through the next safe turnaround, charged the same game minutes as
# the missed destination exit and the missed facility gate -- the same maneuver
# a road up or down. The lost time is the whole consequence; there is no fine.
RAMP_TERMINAL_MISS_LOOP_MIN = 20.0
# The missed destination exit's own loop-back, same maneuver and same clock.
EXIT_MISS_LOOP_MIN = 20.0
RAMP_SPEECH_WPM_MIN = 30.0
RAMP_SPEECH_WPM_MAX = 60.0
RAMP_ARRIVAL_REACTION_S = 3.0
RAMP_ARRIVAL_GRACE_MIN_S = 8.0
# Where the synthetic destination exit sits, and equally the local approach
# road the arrival zones assume behind it when the facility has no usable
# record of its own -- one road, described once (``sim.trip_models``).
DESTINATION_EXIT_BEFORE_END_MI = DESTINATION_LOCAL_APPROACH_MI
# A real interchange counts as the destination exit only inside this final
# approach window. Routes that finish on rural highways carry no baked
# interchanges, and without the floor the scan crowned the last labeled exit
# anywhere on the route -- one playtest got its "destination exit" on I-39 in
# Wisconsin, 1,158 miles from the Montana receiver, and taking it settled the
# load from there (transcripts, 2026-07-16). Past the window the synthetic
# end-of-route exit takes over.
DESTINATION_EXIT_SCAN_WINDOW_MI = 25.0
UNLOADING_MIN = 45.0  # receiver dock work before settlement
UNLOADING_WAIT_S = 1.5

# Discrete lanes on top of the LaneKeeping drift model. With steering assist
# on, holding the wheel across the lane line is the lane change; with assist
# off, a Left/Right arrow tap runs a timed change with signal clicks.
LANE_MIN_MPH = 10.0  # below this there is nothing to steer
LANE_TAP_CHANGE_S = 2.5  # assist-off timed drift across the line
LANE_SIGNAL_CLICK_S = 0.45  # turn-signal cadence during a tap change
MERGE_WINDOW_S = 8.0  # time to vacate a coned-off lane after the warning
# How far under the traffic's speed a truck has to be at the end of an
# acceleration lane before the game says so. Below this it is up to speed for
# practical purposes; at or above it, the gap is what matters and the line
# says to take a big one. Not tuned: it is the shortfall the Green Book's own
# design target implies -- 75 percent of a 65 mph highway is 49, about 16 mph
# short -- rounded down so the line fires a little before that rather than
# only at the design worst case.
MERGE_UNDER_SPEED_MPH = 12.0
MERGE_BARRELS_DAMAGE = 0.25  # collision severity for riding into the barrels
SIDESWIPE_DAMAGE = 0.35  # changing lanes into occupied space costs more
DODGE_CLEARANCE_AHEAD_MI = 0.35  # target lane must be clear this far ahead...
DODGE_CLEARANCE_BEHIND_MI = 0.15  # ...and this far behind your drive tires
# The steering lane cue: the panned position tock, played on its own while a
# lane move is underway rather than waiting for the I key, and clicked off
# like a turn signal when the move is done. Owner request 2026-08-15: taking
# an exit with the lane work yours means HOLDING a position at the right of
# the lane, and that position was the one thing on the road a blind driver
# could not hear.
STEER_CUE_MIN_MPH = 2.0  # same floor as the lane locator: stopped tires steer nothing
STEER_CUE_ARM_S = 0.5  # a steering hold this long is a move, not a drift correction
STEER_CUE_TOCK_S = 0.9  # the locator's own beat, so the two are one sound
STEER_CUE_TOCK_FAST_S = 0.35  # the beat it closes to as the exit lane position fills
STEER_CUE_HOLD = "lane_steer"  # dead-man's-switch latch name, held on the audio clock
STEER_CUE_CANCEL_VOL = 0.45  # the self-cancel click, quieter than the signal going on
KEEP_RIGHT_NAG_S = 45.0  # left-lane camping before the CB calls you out
KEEP_RIGHT_REPEAT_S = 75.0  # spacing for repeat nags while still camping
KEEP_RIGHT_MIN_MPH = 45.0  # lane discipline only matters at highway speed
PASSING_LOOKAHEAD_MI = 0.6  # slower right-lane traffic inside this justifies the left lane

KEEPER_MIN_MPH = 2.0  # the speed keeper just needs the truck rolling
KEEPER_MAX_THROTTLE = 0.5  # zone speeds never need more than half throttle
KEEPER_GAP_SECONDS = 3.0  # follow queued traffic at this gap, down to a stop
CRUISE_MIN_MPH = 20.0  # cruise control needs road speed to hold
CRUISE_STEP_MPH = 5.0  # set-point change per Accel/Coast (+/-) tap
CRUISE_MAX_MPH = 85.0  # highest cruise set point (top US posted limits)


def cruise_step_target(target_mph: float, direction: int, fine: bool) -> float:
    """The next cruise set point from a +/- tap.

    Plain taps walk the fives grid the way a real cruise stalk does: an
    off-grid target (K captures the exact road speed, so 32 happens all
    the time) snaps outward to the next multiple, healing itself in one
    press instead of stepping 37, 42 forever (testers Jerry and Sarah,
    2026-08-13). Ctrl taps move by exactly one for the players who need
    a precise number and cannot feather K onto it. The epsilon keeps a
    float a hair off the grid from turning a tap into a no-op snap.
    """
    if fine:
        stepped = target_mph + direction
    elif direction > 0:
        notches = math.floor(target_mph / CRUISE_STEP_MPH + 1e-9)
        stepped = (notches + 1) * CRUISE_STEP_MPH
    else:
        notches = math.ceil(target_mph / CRUISE_STEP_MPH - 1e-9)
        stepped = (notches - 1) * CRUISE_STEP_MPH
    return max(CRUISE_MIN_MPH, min(CRUISE_MAX_MPH, stepped))


# Speed-hold gains. The feed-forward term (``Truck.hold_throttle``) carries
# the grade; P and I only trim from there. The old loop was integral-only at
# 0.08 per mph-second, which needed over ten seconds just to reach full
# throttle -- a 4 percent climb had already taken twenty mph off the truck by
# then (bench trace, 2026-07-25: 62 set, 31.9 mph low, and the sag never came
# back). Trim is bounded so a grade the engine genuinely cannot pull does not
# wind the integrator into a spike when the road levels out.
CRUISE_P_GAIN = 0.055  # throttle per mph of error
CRUISE_I_GAIN = 0.05  # throttle per mph-second of error
CRUISE_TRIM_LIMIT = 0.4  # how far trim may pull away from the feed-forward
# How fast the working setpoint eases toward the set speed. The loop is pure
# proportional above, so a set speed far over the current one (resume to 85
# from a crawl) used to land the whole error on the pedal at once and command
# wide-open throttle -- governor-loud on the flat, and on a downgrade an
# over-rev past redline during the automatic box's between-shift hold, which
# charged engine wear (tester Shane, ~3 percent on a 12 percent grade). Cruise
# now chases a working setpoint that ramps from the engage speed at this bounded
# rate, so the per-frame error stays small and the throttle stays moderate
# while the box upshifts normally. A loaded rig accelerates in the low single
# digits of mph per second; 2.5 is brisk enough to feel like a resume yet inside
# what the truck can comfortably do, so speed keeps up and the error never grows
# into a governor slam.
CRUISE_ACCEL_MPH_PER_S = 2.5
# Belt and suspenders for the downgrade: even where gravity does the
# accelerating, cruise must not add throttle as the engine nears the governor.
# Demand tapers to nothing across this fraction of max RPM below the redline, so
# the descent-control and retarder staging own the grade and cruise is simply
# off the pedal -- never fighting the retarder, never feeding an over-rev.
CRUISE_RPM_CEILING_BAND = 0.08
CRUISE_COAST_MPH = 2.0  # feed-forward eases to nothing across this much overspeed
# The droop band: how far under its number cruise tolerates before the truck
# counts as beaten by the hill rather than working through a dip. Fleet cruise
# parameters use the same idea (a configurable underspeed), and it is what
# keeps the spoken hand-back off a pull cruise recovers from on its own.
CRUISE_DROOP_MPH = 6.0
CRUISE_FLOORED_THROTTLE = 0.98  # pedal genuinely on the floor, not merely deep
CLIMB_CUE_COOLDOWN_S = 120.0  # a mountain is many pulls; say it once a hill
# ...and only once the grade has genuinely won (dev fix f23a97ec, ported):
# a road the G key calls level never counts as a climb, a shift's open
# driveline is not evidence (drive_ratio is 0 mid-shift), and the condition
# has to hold rather than catch one frame -- a limit rise raising the target
# had cruise flooring the pedal on a slight grade and announcing defeat at
# 71 mph while accelerating to 77 (playtest transcript, 2026-07-27).
CRUISE_GRADE_BEATEN_PCT = 1.5
CRUISE_GRADE_BEATEN_S = 3.0
# Holding the target from above. Cutting fuel was cruise's only answer, so any
# downgrade gentler than the descent assist's 2.5 percent trigger carried the
# truck past the set speed and kept it there (bench trace: 2 percent down, 62
# set, 67.2 held) -- a speeding strike cruise handed the driver. The retarder
# answers first because its heat goes out the exhaust; the drums only join in
# when the jake cannot hold, so a long grade does not fade them away.
CRUISE_JAKE_OVER_MPH = 0.75  # over the target by this much and the jake steps in
CRUISE_JAKE_STEP_MPH = 1.0  # further overspeed per additional jake stage
CRUISE_JAKE_RELEASE_MPH = 0.25  # back inside this and the retarder hands off
CRUISE_JAKE_STEP_S = 4.0  # quiet time between stage changes; the jake is loud
# Descent control announcing itself is a per-grade event, not a per-dip one:
# rolling country crosses the 2.5 percent trigger every dip, and at 1.5
# seconds of retarder spacing the bench heard a stage change every ten
# seconds and the holding cue four times in six minutes (2026-07-25).
DESCENT_CUE_COOLDOWN_S = 120.0
# The drums are the last resort, and they only come out in snubs: apply,
# recover the target, release. Dragging a light application down a long grade
# is how a real truck fades its brakes and empties its air tanks -- and the
# sim models both, so cruise did exactly that to itself (bench trace,
# 2026-07-25: 6 percent down, a tenth of brake held steady, 125 psi to 74 in
# twenty-two seconds, spring brakes on, an emergency stop on a downhill).
CRUISE_BRAKE_OVER_MPH = 2.5  # retarder maxed and still this far over: snub
CRUISE_SNUB_UNDER_MPH = 0.5  # snub runs until this far back under the target
CRUISE_SNUB_BRAKE = 0.3  # a real application, not a drag
# Interactive descent control's ceiling while a grade lasts. A cap on the
# working target only -- it must never be written into the set speed.
DESCENT_SAFE_MAX_MPH = 55.0
# Predictive cruise: the road profile ahead, read the way a real system reads
# a stored 3D map (Volvo I-See, Detroit Intelligent Powertrain Management).
# The preview distance is what those systems use, and the baked grade segments
# resolve to a median half a mile, so a mile and a half is a real look ahead
# rather than a smoothed guess.
PCC_PREVIEW_MI = 1.5
PCC_PREVIEW_STEP_MI = 0.1
PCC_GRADE_MIN = 0.015  # shallower than this is not a hill worth planning for
PCC_GRADE_WINDOW_MI = 0.3  # a hill is a sustained window, not one spike
PCC_PREBUILD_MPH = 3.0  # momentum banked before a climb, at a 4 percent pull
PCC_CREST_SAG_MPH = 4.0  # speed given up rather than fought for at a summit
PCC_DESCENT_SHAVE_MPH = 2.0  # taken off before a downgrade, at 5 percent
# The crest gets its own, much shorter horizon: the summit is "close" when the
# road inside this distance has already gone flat. Judged on the full preview
# instead, a three-mile pull read as cresting from a mile and a half out.
PCC_CREST_WINDOW_MI = 0.4
PCC_CUE_COOLDOWN_S = 45.0  # rolling country must not chant preview cues
# Grade advisories, spoken whether or not cruise is on. A downgrade this steep
# is the one a driver has to plan for -- gear and retarder before the hill, not
# halfway down it.
GRADE_WARN_PCT = 3.0  # steep enough to call out, either direction
GRADE_WARN_CLEAR_PCT = 2.0  # hysteresis: under this the grade is behind you
# A grade that keeps its sign but gets materially worse is a new thing to plan
# for: two percent down that becomes six is the hill gear goes in for, and the
# road never flattens in between to announce it.
GRADE_WARN_STEEPEN_PCT = 1.0
GRADE_WARN_LOOKAHEAD_MI = 0.75  # how far ahead the advisory reaches
GRADE_WARN_SCAN_MI = 15.0  # how far a grade's run is measured before giving up
GRADE_WARN_STEP_MI = 0.25  # sampling stride; matches the baked segment length
GRADE_WARN_MIN_MPH = 25.0  # no advisories while crawling; nothing to plan for
# A grade has to last to be worth planning for. The baked segments are around
# half a mile each and the mountain corridors are full of short punchy dips: a
# 4 percent blip lasting a third of a mile costs a couple of mph and warning
# about it buried the hills that matter. Unfiltered, Knoxville to Asheville
# spoke 76 advisories in 116 miles; at three quarters of a mile it speaks 4.
GRADE_WARN_MIN_RUN_MI = 0.75
GRADE_WARN_RESCAN_MI = 0.1  # how far the truck rolls between advisory scans
ACC_BASE_GAP_SECONDS = 3.0  # clear-weather adaptive cruise gap, normal setting
# The driver's choice of cushion, in seconds of clear-weather gap. Real
# adaptive cruise offers three, and so does this. Weather still ADDS to
# whichever one is chosen (see _acc_gap_seconds), so picking "close" never
# stops the truck opening up on ice.
#
# Every one of them sits far clear of enforcement_observe.TAILGATE_GAP_S
# (1.2 seconds), and that is a floor rather than a coincidence: the closest
# setting the game offers must never be a setting that gets the driver
# ticketed for choosing it. A test pins the margin.
ACC_GAP_CHOICES = {
    "close": 2.5,
    "normal": ACC_BASE_GAP_SECONDS,
    "far": 3.5,
}
ACC_GAP_DEFAULT = "normal"
ACC_LIMIT_OFFSET_MPH = 5.0  # predictive ACC holds this far over the posted
# limit -- a with-traffic pace, sized to sit right at OVERSPEED_WARN_MPH
# without arming it, and comfortably under the 9 mph speeding-strike
# threshold. Cruise used to overshoot it on every downgrade and chime at the
# driver for a speed cruise itself had picked; the grade band is bounded now
# (see CRUISE_JAKE_OVER_MPH and the snub constants) rather than the pace
# being cut.
# Zones the driver is warned about in advance and that cruise pre-brakes for,
# holding their limit exactly rather than the usual with-traffic offset. The
# construction merge taper is deliberately absent: it posts a higher limit
# ahead of the work zone, and aiming at it reached the barrels too fast.
RESTRICTED_ZONE_REASONS = frozenset({"construction", "heavy traffic"})
ACC_LIMIT_LOOKAHEAD_MIN_MI = 0.25
ACC_LIMIT_LOOKAHEAD_MAX_MI = 1.5
ACC_LIMIT_LOOKAHEAD_STEP_MI = 0.1
ACC_LIMIT_COMFORT_DECEL_MPS2 = 1.0
ACC_FOLLOW_DECEL_MPS2 = 0.35  # gentle planned deceleration while closing on a lead
ACC_FOLLOW_CUE_COOLDOWN_S = 30.0  # minimum quiet time between "Traffic ahead" cues
ACC_STOPPED_CANCEL_S = 20.0  # hand control back this many seconds before stopped traffic
ENGINE_SHUTDOWN_SAFE_MPH = 5.0  # prevent accidental kill-switch use at speed
DELIVERY_PARK_MPH = 3.0  # within this, the gate prompts you to stop
DOCKING_MAX_MPH = 0.5  # dock/settle/rest actions need a complete stop
PARKING_BRAKE_SETTLE_MAX_MPH = 3.0  # spring brakes finish a walking-pace stop immediately
# How often a facility gate re-speaks its stop instruction while the truck is
# still rolling past it. The one-shot warnings latch, so without a cadence a
# player who overshot the gate at speed heard them once, minutes ago, and got
# silence for the rest of the drive (playtest 2026-07-22: six minutes and the
# on-time bonus lost three miles past a delivery entrance).
GATE_REMINDER_INTERVAL_S = 10.0
# Minimum quiet time between curve-assist spoken cues. The assist state can
# legitimately cycle when cruise fights the curve brake; the cues must not
# (playtest 2026-07-22: 23 slowing/released flips in four seconds).
CURVE_ASSIST_CUE_COOLDOWN_S = 15.0


def ramp_arrival_grace_seconds(message: str, speech_rate: float = 0.5) -> float:
    """Conservatively cover the spoken cue plus a real response window.

    Screen-reader speech completion is not observable through every Prism
    backend, so model a deliberately slow 30-to-60 WPM voice, scaled by the
    player's event-voice rate, instead of starting a fixed timer when the
    utterance is merely queued. Once the player sets the parking brake, the stop
    remains accepted while the truck finishes decelerating.
    """
    rate = max(0.0, min(1.0, float(speech_rate)))
    modeled_wpm = RAMP_SPEECH_WPM_MIN + (RAMP_SPEECH_WPM_MAX - RAMP_SPEECH_WPM_MIN) * rate
    spoken_seconds = len(message.split()) * 60.0 / modeled_wpm
    return max(RAMP_ARRIVAL_GRACE_MIN_S, spoken_seconds + RAMP_ARRIVAL_REACTION_S)


def timezone_crossing_message(event, terse: bool) -> str:
    """The spoken zone crossing: terse mode says only the zone itself."""
    zone = event.data.get("to_zone")
    if terse and zone is not None:
        return f"{zone.name}."
    return event.message


DRIVE_PHASE_PICKUP = "pickup"
DRIVE_PHASE_DELIVERY = "delivery"
DRIVE_PHASE_SCHOOL = "school"  # sandbox practice drive, never persisted

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


# Turn earcons come from the side of the maneuver, the same convention as
# the lane-guidance beeps: hear it on the side you are about to steer toward.
TURN_CUE_PAN = 0.6


def _route_event_sound_pan(event) -> float:
    """Stereo pan for a route event's sound cue; only local turns pan."""
    if event.kind != TripEventKind.GPS_CUE:
        return 0.0
    cue = event.data.get("cue")
    if getattr(cue, "kind", None) != "local_turn":
        return 0.0
    direction = str(getattr(cue, "direction", "") or "").strip().lower()
    if direction == "left":
        return -TURN_CUE_PAN
    if direction == "right":
        return TURN_CUE_PAN
    return 0.0


def _poi_ambient_key(stop, hour: float) -> str:
    if stop.type == "weigh_station":
        return "poi/weigh_station_lane"
    if is_night(hour):
        return "poi/rest_stop_night"
    return "ambient/truck_stop"


def road_repair_cost(damage_pct: float, down_to: float, callout_fee: float) -> float:
    """What a road shop charges to bring ``damage_pct`` down to ``down_to``.

    Same severity curve as the terminal garage (``damage_severity_mult``) so
    the two never disagree about what deep damage is worth, plus whatever
    call-out fee getting a mechanic to the truck carries.
    """
    repaired = max(0.0, float(damage_pct) - float(down_to))
    return callout_fee + repaired * MECHANIC_RATE_PER_PCT * damage_severity_mult(damage_pct)


def _record_inspection(ctx, *, event: bool = False) -> None:
    """Every inspection feeds both the one-off badge and the career tally."""
    ctx.award_achievement("inspection", event=event)
    if ctx.profile is not None and increment_stat(ctx.profile, "inspections_passed") >= 5:
        ctx.award_achievement("scale_regular", event=event)


class _DrivingRadioBackend:
    """Adapts radio station choices onto the existing safe music backend."""

    def __init__(self, driving: DrivingState) -> None:
        self.driving = driving

    def play_station(self, station: RadioStation, volume: float) -> None:
        radio = getattr(self.driving, "radio", None)
        if radio is not None:
            self.driving._radio_signal_factor = signal_volume_factor(radio.current_reception())
        if station.source_type == PERSONAL_PLAYLIST_SOURCE_TYPE:
            self.driving._apply_radio_volume()
            self.driving._start_playlist_station(station, fade_ms=900)
            return
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


# Tolerance over the posted limit before a speed is a speed at all -- roughly
# real-world ticketing tolerance, judged against the leg's real OSM maxspeed
# rather than a flat number. Canonical in the sim layer, because the officer
# who reads the speed lives there; this name is kept because half the driving
# layer already asks for it.
SPEEDING_LEEWAY_MPH = OBSERVE_LEEWAY_MPH
# The dash overspeed alert speaks up before enforcement does: it arms over the
# limit (under the strike leeway), then chimes on an interval until the truck
# settles back under. Real carrier trucks nag exactly like this, which is why
# nobody in one is surprised by their own speed.
#
# 7 is the only value that sits in the gap, and the gap is narrow:
#   - ACC_LIMIT_OFFSET_MPH (5.0) is the pace predictive cruise itself holds.
#     Arming AT 5 gave the warning zero headroom over the speed the game's own
#     automation picks, so ordinary control-loop wobble -- a downgrade, a
#     traffic adjustment, the grade band -- chimed at a driver for a speed
#     they did not choose. That was patched once by bounding the grade band
#     rather than by moving this number; this is the real fix.
#   - OBSERVE_LEEWAY_MPH (9.0) is where a trooper can act. Arming below it is
#     the whole point: the dash warns while compliance is still free, never
#     after the driver is already ticketable.
# Anything at or above 9 would let a driver become ticketable in silence,
# which inverts what the alert is for.
OVERSPEED_WARN_MPH = 7.0  # over the limit where the warning arms
# Hysteresis measured from the arm point, NOT from the limit. Measured from the
# limit it was six mph deep: one honest trigger at nine over went on chiming
# through six, five, four and three over while the driver was slowing down, so
# a driver who blipped over once heard the alert at speeds it must never speak
# at (playtest, 2026-08-15, and the tester report behind it). Back under the
# threshold by this much and the episode is over.
OVERSPEED_RESET_MPH = 1.0
# The cadence carries the magnitude: slightly over dings politely, a real
# runaway dings twice a second. Interval slides between these ends as the
# overage grows.
OVERSPEED_CHIME_REPEAT_S = 5.0  # cadence just past the warn threshold
OVERSPEED_CHIME_FAST_S = 0.5  # cadence at OVERSPEED_URGENT_MPH over and beyond
OVERSPEED_URGENT_MPH = 20.0
# Speeding tickets are priced by how far over the limit you were, how many
# citations the career already carries, and whether it happened in a
# construction zone -- see models/enforcement.speeding_citation_fine, which is
# anchored to the real state fine schedules. Paid on the spot when a trooper
# pulls you over, and that is the ONLY way speeding costs anything.
#
# There used to be a second, invisible charge: hold nine over for six seconds
# with no patrol anywhere and the drive banked a "speeding strike", billed at
# the dock hours later as a driver-responsibility charge. It was a placeholder
# for enforcement that did not exist -- a fine from an officer who was never
# there -- and it is gone (owner ruling, 2026-08-09). Speeding nobody saw now
# costs nothing, which is both honest and what happens on a real road. The
# presence model is what stands between a speeder and impunity.
# Travel this far still moving after the lights come on and it counts as
# ignoring the stop -- a heavier fine and a bigger reputation hit.
PULL_OVER_IGNORE_MI = 2.0
FAILURE_TO_STOP_WARNING_MI = 0.8
FAILURE_TO_STOP_FINAL_WARNING_MI = 1.5
# The staged warnings run on real seconds, not trip miles: compression could
# burn two miles before the first warning had a chance to speak.
PULL_OVER_FIRST_WARNING_S = 8.0
PULL_OVER_FINAL_WARNING_S = 16.0
# After the final warning, this long before troopers force the stop.
PULL_OVER_FORCED_STOP_S = 10.0
# Running is a felony, so it takes a deliberate held input and never happens
# by hesitating. Doubled when the next one would be a lifetime disqualification.
PURSUIT_HOLD_S = 3.0
FAILURE_TO_STOP_DAMAGE_PCT = 12.0
FAILURE_TO_STOP_PROCESSING_MIN = 180.0
WEIGH_STATION_NOTICE_MI = 2.0
WEIGH_STATION_BYPASS_MPH = 15.0
# A bypass is caught, not certain. The scale house has plate readers and
# weigh-in-motion sensors watching the bypass lane, and dispatches a unit up
# the corridor after a truck that ran it -- but a unit still has to catch up,
# so real bypass enforcement is steep, not perfect. Same shape as
# CHAIN_LAW_CHECKPOINT_CHANCE: a flat, named, seeded roll, not a difficulty
# knob -- the enforcement-presence setting governs ambience only and never
# reaches this number (owner ruling, 2026-08-14: "pretty steep"). What a
# caught bypass costs is priced in models/enforcement, with every other fine.
WEIGH_STATION_BYPASS_CATCH_CHANCE = 0.85
# A transponder-equipped truck gets a weigh-in-motion verdict instead of the
# blanket "all trucks must pull in" demand (see EnforcementWatchMixin's scale
# handling in driving_updates.py / driving_enforcement.py, and
# models.business.has_weigh_station_transponder for who has one). PrePass
# publicly reports the large majority of transponder-equipped, in-compliance
# trucks bypassing an open scale -- this is a design constant informed by
# that public figure, not a measurement of anything in this game, and it
# only ever applies to a truck that is not overweight (see
# WEIGH_STATION_TRANSPONDER_BYPASS_SHARE's use in
# _resolve_transponder_verdict). The remainder are red-lighted anyway,
# matching how real weigh-in-motion programs still spot-check compliant
# carriers rather than waving every one through every time.
WEIGH_STATION_TRANSPONDER_BYPASS_SHARE = 0.9
UNSAFE_DAMAGE_STOP_PCT = 65.0
AMBIENT_EVENT_SPACING_S = 2.5  # keep low-priority chatter from stacking
# Once the lights come on, a compliance tracker (0..1) judges whether you are
# actually pulling over -- signaling and slowing -- rather than how far you
# rolled. It seeds at PULL_OVER_START_COMPLIANCE, rises with braking, falls with
# accelerating/coasting/ignoring, and a felony stop fires the instant it hits 0.
# Disobedient rates outpace the compliant one so it always zeroes faster than it
# fills, and their deductions stack when several apply at once.
PULL_OVER_START_COMPLIANCE = 0.5
PULL_OVER_ACCEL_RATE = 0.34  # per s of rising speed; full 1.0 -> 0.0 in ~3 s
PULL_OVER_ACCEL_EPS_MPH_S = 0.4  # speed must genuinely rise (past jitter) to count
PULL_OVER_COAST_RATE = 0.12  # per s of coasting; lighter than accelerating
PULL_OVER_BRAKE_RATE = 0.15  # per s of braking; the only thing that raises it
PULL_OVER_SIGNAL_GRACE_S = 5.0  # plenty of time to react before the no-signal drain
PULL_OVER_COAST_GRACE_S = 3.0  # coasting is only flagged after this many s
PULL_OVER_SIGNAL_BOOST = 0.20  # one-time bump the first time you signal
PULL_OVER_NOSIGNAL_HIT = 0.25  # one-time 1/4 hit once past the signal grace unsignaled
PULL_OVER_NOSIGNAL_RATE = 0.03  # per s small drain while still unsignaled past grace
PULL_OVER_FULL_COMPLIANCE = 0.95  # at/above this a stop counts as prompt and clean
PULL_OVER_CLEAN_STOP_WARN_CHANCE = 0.25  # chance a clean stop downgrades a ticket to a warning


class Tutorial:
    """First-drive guidance, spoken step by step as the player succeeds.

    Deliberately verbosity-blind (research doc, R15): terse speech is a
    filter on running commentary, and first-run teaching is not commentary.
    A brand-new player who picks terse before their first drive -- exactly
    the player who hates chatty games -- must still be told the status,
    help, and hazard keys exist, or they can never pull information they
    were never told about. The gate is ``tutorial_done`` itself: this class
    is only constructed while the walkthrough is unfinished, and finishing
    it then flipping terse on resurrects nothing.
    """

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self.stage = 0
        self._timer = 0.0
        self._hinted = False

    def begin(self) -> None:
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
            self.ctx.say(
                "Parking brake released. Now hold "
                f"{self.ctx.control_hint('accelerate')} to accelerate.",
                interrupt=False,
            )
        elif self.stage == 1:
            self._timer = 0.0
            self._hinted = False
            self.ctx.say(
                "Parking brake released. Now shift into first gear.",
                interrupt=False,
            )

    def on_gear_engaged(self) -> None:
        if self.stage == 1:
            self.stage = 2
            self._timer = 0.0
            self._hinted = False
            self.ctx.say(
                f"In gear. Now hold {self.ctx.control_hint('accelerate')} to accelerate.",
                interrupt=False,
            )

    def update(self, dt: float, truck) -> None:
        self._timer += dt
        if self.stage == 2 and truck.speed_mph > 20:
            self.stage = 3
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
    driving.truck.advance_parked_time(minutes)
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


def _secure_truck_for_stopped_menu(
    driving: DrivingState, *, max_mph: float = DOCKING_MAX_MPH
) -> bool:
    """Atomically secure a slow truck before a menu freezes driving physics."""
    truck = driving.truck
    if truck.speed_mph > max_mph:
        return False
    truck.velocity_mps = 0.0
    truck.throttle = 0.0
    truck.brake = 1.0
    truck.set_parking_brake()
    driving._cancel_cruise()
    return True


def set_engine_running(ctx, truck, *, running: bool) -> bool:
    """Start or stop the engine from a menu, keeping the audio loop in step.

    The driving frame loop only notices engine transitions that happen inside
    ``truck.update()``, so a change made while a menu holds the screen has to
    move the audio itself; otherwise the loop idles on forever with the engine
    off, or the truck runs in silence. Returns False only when the starter
    refuses (no fuel), which leaves both the truck and the audio untouched.
    """
    if running:
        if not truck.start_engine():
            return False
        ctx.audio.engine_start()
        return True
    if truck.engine_on:
        truck.stop_engine()
        ctx.audio.engine_stop()
    return True


FACILITY_ENGINE_SHUT_DOWN_ITEM = "Shut down the engine"
FACILITY_ENGINE_START_ITEM = "Start the engine"


class FacilityEngineMixin:
    """The engine kill switch, offered where a facility menu has taken over.

    Arriving at a shipper or a receiver parks the truck under half a mile an
    hour and hands straight to a menu, so the road's engine control is out of
    reach at exactly the moment a driver reaches for it: sitting at the gate,
    or waiting on a dock crew (new player feedback, 2026-08-17). A state mixes
    this in and supplies ``facility_truck``; both facilities then offer the
    same one row, worded the same way.
    """

    @property
    def facility_truck(self):
        raise NotImplementedError

    def facility_engine_item(self) -> MenuItem:
        """One row that changes face, never two rows to arrow past."""
        if self.facility_truck.engine_on:
            return MenuItem(
                FACILITY_ENGINE_SHUT_DOWN_ITEM,
                self._toggle_facility_engine,
                help="Shut it down while you sit here. No fuel burned and no "
                "idle noise; you start it again before you pull out.",
            )
        return MenuItem(
            FACILITY_ENGINE_START_ITEM,
            self._toggle_facility_engine,
            help="Bring the engine back up. Air pressure has to reach 100 psi "
            "before the parking brake will release.",
        )

    def on_facility_engine_changed(self) -> None:
        """Hook for a facility state that keeps a resume snapshot of its own."""

    def _toggle_facility_engine(self) -> None:
        truck = self.facility_truck
        if truck.speed_mph > DOCKING_MAX_MPH:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Stop before touching the engine.")
            return
        if truck.engine_on:
            set_engine_running(self.ctx, truck, running=False)
            self.on_facility_engine_changed()
            self.refresh(keep_index=True)
            self.ctx.say("Engine off.")
            return
        if not set_engine_running(self.ctx, truck, running=True):
            self.ctx.audio.play("ui/error")
            self.ctx.say("The engine will not start.")
            return
        self.on_facility_engine_changed()
        self.refresh(keep_index=True)
        self.ctx.say(f"Engine running. Air pressure {truck.air_pressure_psi:.0f} psi.")


def _shut_down_engine(driving: DrivingState) -> str:
    """Stop the engine before a night's sleep; no truck idles through ten
    hours. Returns the spoken prefix, empty when it was already off."""
    if not driving.truck.engine_on:
        return ""
    set_engine_running(driving.ctx, driving.truck, running=False)
    return "You shut down the engine. "


def _wake_air_instruction(driving: DrivingState, *, from_rest_menu: bool = True) -> str:
    """Describe the required keyboard/controller recovery after parked air loss."""
    truck = driving.truck
    if truck.air_ready:
        return ""
    road_step = "Choose Back to the road, then press" if from_rest_menu else "Press"
    return (
        f" Air pressure {truck.air_pressure_psi:.0f} psi. {road_step} "
        f"{driving.ctx.control_hint('engine')} to start the engine. Wait "
        f"for air pressure ready, then press "
        f"{driving.ctx.control_hint('parking_brake')} to release the parking brake."
    )


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
        f"{_wake_air_instruction(driving, from_rest_menu=False)}"
    ]
    if hos.shoulder_fine_due(driving.trip_seed, anchor_mi):
        zone = driving.trip.in_construction_zone
        fine = citation_fine(hos.SHOULDER_FINE, career_citations(p), construction_zone=zone)
        p.money -= fine
        driving.ctx.audio.play("ui/error")
        parts.append(
            f"A trooper ticketed you for illegal parking: "
            f"{fine:,.0f} dollars."
            f"{construction_zone_fine_clause(zone)} "
            f"You have {p.money:,.0f} dollars."
        )
    if hos.shoulder_damage_due(driving.trip_seed, anchor_mi):
        driving.truck.add_damage(hos.SHOULDER_DAMAGE_PCT)
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
