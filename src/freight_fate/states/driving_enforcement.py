# ruff: noqa: F403,F405
"""The enforcement watch: hearing the police, and being seen by them.

This is the game-layer half of the presence model. ``sim/enforcement_posts``
decides where the posts are and who is sitting in them;
``sim/enforcement_observe`` decides what one of them notices and how sure it
is. This module assembles what the truck is doing into a sample, plays the
cues, makes the named seeded draw, and hands a confirmed observation to the
pull-over machinery that already exists.

Three rules shape everything here.

**Audible before it can bite.** A staffed post cannot observe a driver who was
never told it was there. That is not balance, it is the whole accessibility
contract: a blind player cannot see a cruiser on a crossover, so if the game
never made a sound about it, the ticket it writes is arbitrary. Every staffed
post emits its marker earcon before it enters observing range, at every
enforcement-presence level, and ``observe`` refuses to look at a driver who
has not heard it.

**Speech is rationed; earcons are not.** Two spoken enforcement lines for a
whole run, spent on the things that cost money -- an open scale, and anything
that has already taken something from you. The marked-unit pass is never
spoken: it is a fact about the world with no action attached, and narrating it
twelve times a run is pure noise. A closed scale is never spoken either; the
ambience swells, nothing is said, and the absence of speech is what says
"closed".

**One demand at a time.** Nothing here fires while a hazard deadline is
running, during a microsleep, on a ramp, inside an arrival gate sequence, or
during a stop already in progress. Deferred, never dropped: the post keeps
watching, and the moment the cab is quiet again it gets its look.
"""

from __future__ import annotations

import random

from ..audio import CH_SCALE
from ..models.enforcement import (
    CHAIN_LAW_FINE,
    FOLLOWING_TOO_CLOSE_FINE,
    LANE_MISUSE_FINE,
    LIGHTS_FINE,
    UNSAFE_DAMAGE_FINE,
)
from ..models.safety_record import (
    inspection_selection_chance,
    refresh_selection_score,
    safety_record_text,
)
from ..settings import ENFORCEMENT_AMBIENCE_SCALE
from ..sim.enforcement_observe import (
    CERTAIN_OVER_MPH,
    COVER_RADIUS_MI,
    COVER_SPEED_TOLERANCE_MPH,
    OBSERVE_HOLD_MI,
    OBSERVE_LEEWAY_MPH,
    WHAT_CHAINS,
    WHAT_DAMAGE,
    WHAT_FOLLOWING,
    WHAT_LIGHTS,
    WHAT_SPEEDING,
    Observation,
    RoadSample,
    observe,
)
from ..sim.enforcement_posts import (
    KIND_FIXED_SCALE,
    KIND_SCALE_APRON,
    TABLEAU_SIREN_LEAD_MI,
    post_seed,
)
from ..sim.trip_models import ENFORCEMENT_WARNING_MAX_MI, SCALE_WARNING_REAL_S
from .driving_core import *
from .driving_siren import (
    PASS_MARKER_LEAD_S,
    SIGNATURE_KEY,
    SIREN_RISE_S,
    SirenLoop,
    register_enforcement_sounds,
)

# -- cue tuning --------------------------------------------------------------

# The marker earcon fires this far before a post starts watching, so the cue
# and the observation can never land in the same instant.
POST_MARKER_LEAD_MI = 0.25

# How far a held look can travel before the officer has simply lost you. A
# trooper who clocks a truck pulls out and catches it; one who never did is
# not entitled to the stop half a state later. Generous on purpose: the thing
# doing the deferring is usually a hazard, and a hazard window now runs long
# enough to be answerable, which at full compression is several miles of road.
# Five was not enough -- it stranded two looks out of three in a bench drive.
DEFERRED_STOP_MAX_MI = 10.0

# A marked unit going the other way is the most common police sound on a real
# road, and it now is here too. Pan is confirmation only -- the gesture in the
# asset is what says "oncoming pass" -- and the level falls off with distance
# from the post so a distant unit reads as distant.
PASS_PAN = 0.55
PASS_BASE_VOLUME = 0.7

# The weigh-station bed. It starts early and quiet and swells as the scale
# closes, which is a distance cue that works at any pacing: a loop rising over
# real seconds conveys closing speed correctly however compressed the clock is.
SCALE_BED_START_MI = 2.2
SCALE_BED_MIN_VOLUME = 0.10
SCALE_BED_OPEN_MAX_VOLUME = 0.62
SCALE_BED_CLOSED_MAX_VOLUME = 0.26
SCALE_BED_FADE_MS = 700

# The radio duck for a cue. A sibling of the picket duck, never the picket
# duck itself -- that one self-heals on _stop_radio_fringe and would drag the
# enforcement duck away with it.
RADIO_CUE_DUCK = 0.22
RADIO_CUE_DUCK_S = 1.1

# How far past a post the truck has to be before its pass earcon has fired.
PASS_TRIGGER_MI = 0.05

# The tableau: a staffed patrol post that already has somebody stopped. Both
# cues are pure flavor -- the mechanical truth is the catch suppression in
# ``EnforcementPost.tableau_busy_at`` -- so neither is gated on the
# enforcement-presence ambience scale, the same way a staffed post's ordinary
# marked-unit pass never is.
TABLEAU_SHOULDER_PAN = 0.85  # hard right: US traffic keeps the shoulder there
TABLEAU_SIREN_VOLUME = 0.7
TABLEAU_PASS_VOLUME = 0.7

# One short reminder this close to an announced open scale, if the truck is
# still over the bypass speed with no scale exit armed. The full notice can
# land miles out; nothing else spoke between it and the bypass point, and a
# tester who mis-followed it heard silence all the way to the lights.
WEIGH_STATION_REMINDER_MI = 0.5

# The sentence the open-scale lead distance is sized from. It must pace the
# real announcement's longest realistic rendering -- a long stop name and the
# controller phrases, which run longer than the keyboard letters -- or the
# spoken lead undershoots and the notice lands with no road left to act on.
SCALE_NOTICE_SAMPLE = (
    "Open weigh station ahead in two miles: Northbound Platte River Port "
    "of Entry. All trucks must pull in. Slow below fifteen and signal for "
    "the scale exit with right bumper plus D-pad down. Once you are "
    "stopped at the scale, press right bumper plus D-pad down to check in."
)

# The fines for the things an officer sees rather than clocks -- chain law,
# following too close, lights, lane misuse -- are priced in
# models/enforcement, with every other citation amount and the multipliers
# that scale them, and reach this module through the driving_core star
# import. They used to be declared here as well as there, two constants
# claiming to be the same Colorado citation with nothing keeping them equal.


class EnforcementWatchMixin:
    """Cues, sampling, and the seeded observation draw, on the driving state."""

    # -- lifecycle -----------------------------------------------------------

    def _enforcement_init(self) -> None:
        """Set up the watch. Called once from the driving state's constructor."""
        register_enforcement_sounds()
        self.siren = SirenLoop()
        # Continuous distance over the limit. This -- not a real-time hold --
        # is what a post reads as a speed. See _update_enforcement_watch.
        self._over_limit_mi = 0.0
        self._enforcement_prev_mi = 0.0
        self._passed_post_ids: set[str] = set()
        self._marked_post_ids: set[str] = set()
        # A tableau's two cues, each fired once: the siren some seconds
        # before the spot, and the stopped pair as you go by it.
        self._tableau_siren_ids: set[str] = set()
        self._tableau_pass_ids: set[str] = set()
        self._scale_bed_key = ""
        self._scale_bed_volume = 0.0
        self._radio_cue_duck = 1.0
        self._radio_cue_duck_s = 0.0
        self._radio_cut_for_stop = False
        self._pending_sounds: list[tuple[float, str, float, float]] = []
        # Posts whose look was deferred because the cab was busy. They keep
        # their turn; nothing is silently dropped.
        self._deferred_post_ids: set[str] = set()
        # The look itself, and the mile it was taken at: what makes the
        # deferral a postponement rather than a discard.
        self._held_observation: tuple[Observation, float] | None = None
        self._pacing_since_s: dict[str, float] = {}

    # -- presence ------------------------------------------------------------

    def _ambience_scale(self) -> float:
        """The enforcement-presence multiplier. Ambience only, never odds."""
        level = getattr(self.ctx.settings, "enforcement_presence", "standard")
        return ENFORCEMENT_AMBIENCE_SCALE.get(level, 1.0)

    def _enforcement_busy(self) -> bool:
        """Whether the cab already has a demand on the driver.

        The weigh-station and unsafe-damage checks used to guard on the stop
        and the ramp but not on the hazard deadline, so a trooper could light
        you up in the middle of a braking window you had two seconds to make.
        """
        return (
            self._pull_over is not None
            or self._ramp_mi is not None
            or self._hazard_deadline is not None
            or self._microsleep_deadline is not None
            or getattr(self, "_arrival_menu_open", False)
        )

    # -- scheduled audio -----------------------------------------------------

    def _schedule_sound(self, delay_s: float, key: str, volume: float, pan: float) -> None:
        self._pending_sounds.append((delay_s, key, volume, pan))

    def _service_pending_sounds(self, dt: float) -> None:
        if not self._pending_sounds:
            return
        still: list[tuple[float, str, float, float]] = []
        for delay, key, volume, pan in self._pending_sounds:
            remaining = delay - dt
            if remaining <= 0.0:
                self.ctx.audio.play(key, volume=volume, pan=pan)
            else:
                still.append((remaining, key, volume, pan))
        self._pending_sounds = still

    # -- radio ---------------------------------------------------------------

    def _duck_radio_for_cue(self) -> None:
        """Make a hole in the programme for an enforcement earcon.

        The catalog ships dozens of always-available police and fire scanner
        streams, so an enforcement earcon played on top of the radio is
        competing with material that sounds exactly like it. Ducking is what
        makes the synthesized signature legible.
        """
        self._radio_cue_duck = RADIO_CUE_DUCK
        self._radio_cue_duck_s = RADIO_CUE_DUCK_S
        self._apply_radio_volume()

    def _service_radio_cue_duck(self, dt: float) -> None:
        if self._radio_cue_duck_s <= 0.0:
            return
        self._radio_cue_duck_s -= dt
        if self._radio_cue_duck_s <= 0.0 and self._radio_cue_duck != 1.0:
            self._radio_cue_duck = 1.0
            self._apply_radio_volume()

    def _cut_radio_for_stop(self) -> None:
        """Kill the radio outright for the duration of a stop.

        Cut, not ducked. The sudden silence is itself an unambiguous cue that
        something has taken the cab over, and it removes any chance of a
        scanner stream being mistaken for the cruiser behind you.
        """
        if self._radio_cut_for_stop:
            return
        self._radio_cut_for_stop = True
        self.ctx.audio.stop_music(200)

    def _restore_radio_after_stop(self) -> None:
        if not self._radio_cut_for_stop:
            return
        self._radio_cut_for_stop = False
        self._radio_cue_duck = 1.0
        self._radio_cue_duck_s = 0.0
        self._play_radio_current()

    # -- cues ----------------------------------------------------------------

    def _play_enforcement_marker(self, *, volume: float = 0.8, pan: float = 0.0) -> None:
        self._duck_radio_for_cue()
        self.ctx.audio.play(SIGNATURE_KEY, volume=volume, pan=pan)

    def _mark_post_audible(self, post) -> None:
        """The guarantee: a staffed post makes a sound before it can see you.

        Fires at every presence level, because this cue is not ambience -- it
        is the only reason the post is allowed to cost the player anything.
        """
        if post.id in self._marked_post_ids:
            return
        self._marked_post_ids.add(post.id)
        # The flag and the sound are set together, on purpose. ``announced``
        # is what ``observe`` checks before it will look at the driver at all,
        # so it must mean "this post has made a noise", not "the trip meant to
        # make one". A post that could set the flag without playing anything
        # would be a post that tickets a player it never spoke to.
        post.announced = True
        self._play_enforcement_marker(volume=0.75)

    def _play_marked_unit_pass(self, post) -> None:
        """The oncoming pass: marker first, vehicle 200 ms behind it.

        Both backends apply pan once at trigger, so a real Doppler sweep is
        not buildable from code -- the sweep has to be baked into the asset,
        and the pan here is a static confirmation of side, never the carrier
        of the meaning. The two-element shape is what makes it survive: the
        civilian and trooper pass clips differ only by a chirp buried inside
        the whoosh, which is gone under engine, road, weather and radio, but a
        marker arriving first at its own level is not.
        """
        side = PASS_PAN if post.kind in (KIND_FIXED_SCALE, KIND_SCALE_APRON) else -PASS_PAN
        volume = PASS_BASE_VOLUME * min(1.4, self._ambience_scale())
        self._play_enforcement_marker(volume=min(1.0, volume), pan=side)
        self._schedule_sound(PASS_MARKER_LEAD_S, "traffic/trooper_pass", min(1.0, volume), side)

    def _update_marked_unit_passes(self, previous_mi: float) -> None:
        """Fire a pass earcon for every post the truck has just gone by."""
        position = self.trip.position_mi
        for post in self.trip.posts:
            if post.id in self._passed_post_ids:
                continue
            trigger = post.at_mi + PASS_TRIGGER_MI
            if not (previous_mi < trigger <= position):
                continue
            self._passed_post_ids.add(post.id)
            if post.tableau:
                # The tableau already gets its own richer pass -- the siren
                # lead and the stopped pair hard on the shoulder -- so the
                # anonymous marked-unit pass would only double it up.
                continue
            if not post.staffed:
                # An empty crossover is silent unless the presence setting is
                # buying atmosphere: this is the one cue the slider governs,
                # and it can never cost the player anything, because there is
                # nobody there to observe them.
                if self._ambience_scale() >= 1.2:
                    self._play_marked_unit_pass(post)
                continue
            if post.is_scale:
                continue  # the scale bed already covers the approach
            self._play_marked_unit_pass(post)

    # -- the tableau -----------------------------------------------------

    def _play_tableau_siren_pass(self, post) -> None:
        """The siren of a trooper working somebody else, heard before you reach them.

        Same two-element shape as the marked-unit pass -- the marker leads,
        then the vehicle -- with the siren asset standing in for the whoosh.
        This is the one enforcement sound that means "not about you": a
        trooper who already has a customer is off the hunt.
        """
        self._play_enforcement_marker(volume=TABLEAU_SIREN_VOLUME, pan=TABLEAU_SHOULDER_PAN)
        self._schedule_sound(
            PASS_MARKER_LEAD_S, "events/police_siren", TABLEAU_SIREN_VOLUME, TABLEAU_SHOULDER_PAN
        )

    def _play_tableau_pass(self, post) -> None:
        """The stopped pair, panned hard to the shoulder as you go by.

        Reuses the pass-by vocabulary already used for a marked unit and for
        ordinary traffic: a cruiser and the car it stopped, both parked hard
        right, gone in a moment because that is exactly how long you are
        alongside a parked pair at highway speed. No marker, no radio duck --
        it is news, not a warning.
        """
        volume = min(1.0, TABLEAU_PASS_VOLUME * min(1.4, self._ambience_scale()))
        self.ctx.audio.play("traffic/trooper_pass", volume=volume, pan=TABLEAU_SHOULDER_PAN)
        self.ctx.audio.play("traffic/car_pass", volume=volume * 0.85, pan=TABLEAU_SHOULDER_PAN)

    def _update_tableaus(self, previous_mi: float) -> None:
        """Fire the siren lead and the shoulder pass for every tableau post."""
        position = self.trip.position_mi
        for post in self.trip.posts:
            if not post.tableau:
                continue
            siren_trigger = post.at_mi - TABLEAU_SIREN_LEAD_MI
            if post.id not in self._tableau_siren_ids and previous_mi < siren_trigger <= position:
                self._tableau_siren_ids.add(post.id)
                self._play_tableau_siren_pass(post)
            pass_trigger = post.at_mi + PASS_TRIGGER_MI
            if post.id not in self._tableau_pass_ids and previous_mi < pass_trigger <= position:
                self._tableau_pass_ids.add(post.id)
                self._play_tableau_pass(post)

    def _update_scale_bed(self) -> None:
        """The weigh-station approach bed, swelling on the real clock.

        Open and closed are NOT two different ambiences. Two lot beds
        differing by activity level is exactly the discrimination that fails
        against a road bed, and it would be competing with the truck-stop and
        facility-gate ambiences besides. The swell says "scale". Open adds a
        spoken line, because an open scale costs money and time and has earned
        speech. Closed says nothing at all, and the silence is the answer.

        Whether a trooper is sitting on a closed apron stays unknowable. A
        sighted driver cannot reliably see that either, so it is fair tension
        rather than hidden information.
        """
        position = self.trip.position_mi
        nearest = None
        for post in self.trip.posts:
            if not post.is_scale:
                continue
            ahead = post.at_mi - position
            if -0.3 <= ahead <= SCALE_BED_START_MI and (nearest is None or ahead < nearest[0]):
                nearest = (ahead, post)
        if nearest is None:
            if self._scale_bed_key:
                self._scale_bed_key = ""
                self._scale_bed_volume = 0.0
                self.ctx.audio.stop_loop(CH_SCALE, fade_ms=SCALE_BED_FADE_MS)
            return
        ahead, post = nearest
        closeness = 1.0 - max(0.0, min(1.0, max(0.0, ahead) / SCALE_BED_START_MI))
        ceiling = (
            SCALE_BED_OPEN_MAX_VOLUME
            if post.kind == KIND_FIXED_SCALE
            else SCALE_BED_CLOSED_MAX_VOLUME
        )
        ceiling *= self._ambience_scale()
        volume = SCALE_BED_MIN_VOLUME + (max(0.0, ceiling - SCALE_BED_MIN_VOLUME)) * closeness
        self._scale_bed_key = post.id
        self._scale_bed_volume = volume
        # start_loop dedupes on a running key, so this doubles as the level
        # update and self-heals if anything stopped the channel.
        self.ctx.audio.start_loop(
            CH_SCALE, "poi/weigh_station_lane", volume=volume, fade_ms=SCALE_BED_FADE_MS
        )

    # -- scales --------------------------------------------------------------

    def _scale_is_open(self, stop) -> bool:
        """Whether this weigh station is open today.

        Settled once when the trip was built, from a named seeded draw over
        the stop's own key, so a reload cannot reopen a dark scale.
        """
        for post in self.trip.posts:
            if post.anchor == stop.key:
                return post.kind == KIND_FIXED_SCALE
        return False

    def _scale_notice_lookahead_mi(self) -> float:
        """Lead distance for the open-scale call, sized in real seconds.

        An open scale costs money and time, so it gets a longer lead than a
        heads-up does -- and the lead is derived from the actual sentence,
        not a constant, because enforcement lines differ a lot in length.
        """
        speed = max(self.truck.speed_mph, 1.0)
        seconds = max(
            SCALE_WARNING_REAL_S,
            self._pull_over_grace_seconds(SCALE_NOTICE_SAMPLE),
        )
        miles = seconds * speed * self.trip.effective_time_scale / 3600.0
        return max(WEIGH_STATION_NOTICE_MI, min(miles, ENFORCEMENT_WARNING_MAX_MI))

    def _open_scale_ahead(self, within_mi: float):
        """The nearest open weigh station strictly ahead, or None.

        Returns ``(stop, ahead_mi)``. A closed scale never matches -- its
        guards must stay inert so the silence-means-closed rule holds.
        """
        best = None
        for stop in self.trip.stops:
            if stop.type != "weigh_station":
                continue
            ahead = stop.at_mi - self.trip.position_mi
            if (
                0 < ahead <= within_mi
                and self._scale_is_open(stop)
                and (best is None or ahead < best[1])
            ):
                best = (stop, ahead)
        return best

    def _check_scale_reminder(self, stop, ahead: float, key: str) -> None:
        """One short line before the bypass point, if nothing has changed.

        The full notice latches miles out; between it and the gore the old
        build said nothing at all, so a driver who mis-read the instruction
        crossed at speed in silence. Fires once per scale, only while the
        truck is still over the bypass speed with no scale exit armed.
        """
        if not 0 < ahead <= WEIGH_STATION_REMINDER_MI:
            return
        if key != self._weigh_station_notice_key or key == self._weigh_station_reminder_key:
            return
        if self.truck.speed_mph <= WEIGH_STATION_BYPASS_MPH:
            return
        if self._exit_is_armed_for(stop):
            return
        self._weigh_station_reminder_key = key
        self.ctx.say_event(
            "Weigh station in half a mile. Slow below fifteen for the scale.",
            interrupt=False,
            priority=EventPriority.ROUTE,
        )

    def _scale_outranks_rest_planning(self) -> bool:
        """An open scale ahead owns the next exit; rest planning waits.

        The old announcement told the driver to press the rest key, and the
        rest key at speed planned a sleep stop PAST the scale -- two
        instructions marching the player into a bypass charge. Says what
        comes first and changes nothing; repeats dedupe in the pacer.
        """
        if self._enforcement_bypassed() or self._ramp_mi is not None:
            return False
        window = max(self._scale_notice_lookahead_mi(), self._exit_window_mi())
        found = self._open_scale_ahead(window)
        if found is None:
            return False
        stop, ahead = found
        distance = self.ctx.settings.distance_text(ahead, precise=True)
        self.ctx.say_event(
            f"Weigh station first: {stop.name}, {distance} ahead. All trucks "
            "must stop. Slow below fifteen and signal for the scale exit "
            f"with {self.ctx.control_hint('take_exit')}. Rest planning can "
            "wait until you are past the scale.",
            interrupt=False,
        )
        return True

    def _scale_claiming_exit(self, stop):
        """The open scale that outranks ``stop`` for the exit key, or None.

        An exit press with an open scale nearer than the chosen stop belongs
        to the scale: arming the farther ramp is exactly the move that
        carried a tester past the inspection lane unarmed.
        """
        if self._enforcement_bypassed():
            return None
        found = self._open_scale_ahead(self._exit_window_mi())
        if found is None:
            return None
        scale, _ = found
        if stop is None or stop.key == scale.key:
            return None  # nothing outranked; the normal arming handles it
        if stop.at_mi <= scale.at_mi:
            return None  # the chosen stop comes first anyway
        return scale

    def _stand_down_exit_for_stop(self) -> bool:
        """One demand at a time: a beginning pull-over owns the road.

        An exit armed for a ramp kept announcing and steering for it while
        the trooper stop was running, which turned one mistake into a
        failure-to-stop cascade. Returns True when something actually stood
        down; the plan itself stays on the route map.
        """
        had_exit = self._exit_signal_on or self._exit_stop is not None
        if not had_exit:
            return False
        stop = self._exit_stop
        self._exit_stop = None
        self._exit_signal_on = False
        self._exit_signal_canceled = False
        self._cruise_exit_mph = None
        self._destination_exit_response_s = 0.0
        self._reset_exit_lane_state()
        if stop is not None and self._is_selected_stop(stop):
            self._clear_selected_stop_intent()
        return True

    # -- the siren -----------------------------------------------------------

    def _hold_stop_siren(self) -> None:
        """Keep the cruiser audible for as long as it is behind you.

        The old build played one mono, centred, fixed-level wail and never
        repeated it, and the whole pull-over update contained no audio at all.
        Miss that one shot and there was no ongoing evidence of a police car
        anywhere in the encounter.
        """
        # Pan is confirmation of side and nothing more -- "behind you" is in
        # the spoken instruction, because stereo cannot carry front from back
        # and plenty of players run a single earbud. It closes toward centre
        # as the cruiser comes up, so the pan agrees with the level rise
        # rather than fighting it.
        closing = min(1.0, self.siren.elapsed_s / max(1e-6, SIREN_RISE_S))
        self.siren.hold(self.ctx.audio, pan=-0.5 * (1.0 - closing))

    def _end_stop_audio(self) -> None:
        """Every path out of a stop comes through here."""
        self.siren.stop(self.ctx.audio)
        self._restore_radio_after_stop()

    # -- the sample ----------------------------------------------------------

    def _road_sample(self, post) -> RoadSample:
        """Everything a post could notice about the truck, read defensively."""
        trip, truck = self.trip, self.truck
        position = trip.position_mi
        limit, _ = trip.speed_limit_at(position)
        effects = getattr(trip.weather, "effects", None)
        visibility = float(getattr(effects, "visibility_mi", 10.0) or 10.0)
        context = trip.traffic_context()
        gap_s = getattr(context, "gap_seconds", None) if context is not None else None
        chain_level = trip.chain_law_level() if hasattr(trip, "chain_law_level") else 0
        return RoadSample(
            position_mi=position,
            speed_mph=truck.speed_mph,
            limit_mph=limit,
            # A parallel change is reworking damage into bands; read it
            # defensively so neither side can break the other.
            damage_pct=float(getattr(truck, "damage_pct", 0.0) or 0.0),
            visibility_mi=visibility,
            night=is_night(trip.local_hour),
            lights_on=bool(getattr(truck, "lights_on", True)),
            chains_required=chain_level > 0,
            chains_on=bool(getattr(truck, "chains_on", False)) or chain_level == 0,
            following_gap_s=gap_s,
            left_lane_restricted=bool(getattr(self, "_left_lane_restricted", False)),
            in_left_lane=int(getattr(self.lane, "lane", 0) or 0) > 0,
            pack_neighbours=trip.traffic_manager.pack_neighbours(
                position,
                truck.speed_mph,
                radius_mi=COVER_RADIUS_MI,
                tolerance_mph=COVER_SPEED_TOLERANCE_MPH,
            ),
            crest_between=self._crest_between(position, post.at_mi),
            paced_real_s=self._pacing_since_s.get(post.id, 0.0),
            over_limit_mi=self._over_limit_mi,
        )

    def _crest_between(self, position_mi: float, post_mi: float) -> bool:
        """Whether the road hides the post from an optical method.

        A crest is a grade sign change across the intervening stretch -- the
        road goes up and then comes down between you and the officer, so
        neither of you can see the other. A hard bend does the same thing, and
        the curve bake already knows where those are.
        """
        low, high = sorted((position_mi, post_mi))
        if high - low < 0.05:
            return False
        grades = [self.trip.grade_at(low + (high - low) * f) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
        if max(grades) > 0.015 and min(grades) < -0.015:
            return True
        for curve in getattr(self.trip, "curves", ()):
            if low <= curve.start_mi <= high and abs(getattr(curve, "radius_m", 1e9)) < 400.0:
                return True
        return False

    # -- the watch -----------------------------------------------------------

    def _update_enforcement_watch(self, dt: float) -> None:
        """One frame of the enforcement layer: cues, sampling, and the draw.

        **The pacing mismatch, and how it is solved.** Speeding used to be
        judged on a six REAL second hold, but the old patrol window could last
        7.6 real seconds at standard pacing and 3.8 at the fastest -- so at
        the fastest pacing a speeder could be structurally unable to be caught
        inside a patrol at all. Decompressing the clock inside every post's
        reach was the other option and was rejected: with a post every
        thirty-odd miles it would have put a dozen miles of a five-hundred
        mile run onto the real clock, which is a different game.

        Instead, observation is DISTANCE-quantised. A post reads a speed the
        way a radar does -- over a stretch of road (``OBSERVE_HOLD_MI``, about
        four hundred feet) -- and a stretch of road is the same stretch at
        every pacing, at every frame rate, and after a reload. The real-time
        hold is gone entirely along with the silent at-delivery charge it
        served; there is nothing left for it to disagree with.
        """
        self._service_pending_sounds(dt)
        self._service_radio_cue_duck(dt)
        self.siren.service(self.ctx.audio, dt)
        previous_mi = self._enforcement_prev_mi
        position = self.trip.position_mi
        self._enforcement_prev_mi = position
        moved = max(0.0, position - previous_mi)
        limit, _ = self.trip.speed_limit_at(position)
        if self.truck.speed_mph <= limit + OBSERVE_LEEWAY_MPH:
            self._over_limit_mi = 0.0
        elif self._limit_drop_grace_s > 0.0:
            # A limit that just dropped under a loaded truck: the driver is
            # braking and has not disregarded anything yet. Nothing accrues,
            # so no post can read a speed out of the transition itself.
            self._over_limit_mi = 0.0
        elif (
            self._speed_control_engaged() and self.truck.brake > 0.0 and self.truck.throttle <= 0.05
        ):
            # An automatic speed control is already braking the truck down.
            # Nothing about that is disregard either -- and the rule has to
            # cover every assist that brakes, not just the adaptive-cruise
            # limit cap: the destination-exit ease used to accrue over-limit
            # distance while the assist was doing exactly what it was asked
            # to, which would have ticketed the most cautious drivers in the
            # game for using the feature.
            self._over_limit_mi = 0.0
        else:
            self._over_limit_mi += moved
        self._track_pacing(dt)
        self._update_scale_bed()
        if self._ramp_mi is None:
            self._update_marked_unit_passes(previous_mi)
            self._update_tableaus(previous_mi)
        for post in self.trip.posts:
            if post.staffed and position >= post.watch_start_mi - POST_MARKER_LEAD_MI:
                self._mark_post_audible(post)
        if self._enforcement_bypassed():
            return
        if self._enforcement_busy():
            # Defer, never drop. The look is TAKEN here and held: the officer
            # saw what they saw, and only the lights wait for the cab to be
            # quiet. Recording post ids instead threw the look away, because
            # by the time a hazard window closes the truck is miles past a
            # one-mile radar reach and nothing is watching it any more.
            self._hold_observation()
            return
        held = self._take_held_observation()
        if held is not None:
            self._begin_observed_stop(held)
            return
        self._run_observations()

    def _speed_control_engaged(self) -> bool:
        """Whether cruise or the speed keeper currently owns the throttle."""
        return self._cruise_mph is not None or bool(getattr(self, "_speed_control_armed", False))

    def _track_pacing(self, dt: float) -> None:
        """How long each roving unit has been sitting behind the truck."""
        position = self.trip.position_mi
        for post in self.trip.posts:
            if post.method != "pacing" or not post.staffed:
                continue
            behind = position - post.at_mi
            if 0.0 < behind <= 1.0:
                self._pacing_since_s[post.id] = self._pacing_since_s.get(post.id, 0.0) + dt
            elif behind > 1.0:
                self._pacing_since_s.pop(post.id, None)

    def _run_observations(self) -> None:
        """Take this mile's look and act on it."""
        found = self._observed_now()
        if found is not None:
            self._begin_observed_stop(found)

    def _hold_observation(self) -> None:
        """Take the look the busy cab cannot act on yet, and keep it."""
        if self._held_observation is not None:
            return  # one held look at a time; the first officer has the claim
        found = self._observed_now()
        if found is None:
            return
        self._held_observation = (found, self.trip.position_mi)
        self._deferred_post_ids.add(found.post.id)

    def _take_held_observation(self):
        """The held look, if the officer could still plausibly be behind you."""
        if self._held_observation is None:
            return None
        found, seen_mi = self._held_observation
        self._held_observation = None
        self._deferred_post_ids.discard(found.post.id)
        if self.trip.position_mi - seen_mi > DEFERRED_STOP_MAX_MI:
            return None
        return found

    def _observed_now(self):
        """Ask every post watching this mile what it sees, best first.

        Returns the observation that survived its seeded roll, or ``None``.
        """
        position = self.trip.position_mi
        watching = self.trip.posts_watching(position)
        if not watching:
            return None
        best = None
        for post in watching:
            found = observe(post, self._road_sample(post))
            if found is not None and (best is None or found.confidence > best.confidence):
                best = found
        if best is None:
            return None
        post = best.post
        # The named, seeded, POSITION-quantised draw. Never time-quantised:
        # identical driving through identical road has to produce an identical
        # outcome whatever the frame rate, and a reload must not re-roll
        # whether a trooper was looking at you.
        violation_key = f"{best.what}:{round(position, 1)}"
        roll = random.Random(
            post_seed(self.trip_seed, post.id, f"observe:{violation_key}")
        ).random()
        if roll >= best.confidence:
            # Noticed and let go. A post does not re-decide: this is what
            # makes "five over near a post is ignored" a state rather than a
            # rare piece of bad luck the player can never learn from.
            post.declined = True
            return None
        return best

    def _begin_observed_stop(self, observation) -> None:
        """Turn a confirmed observation into the pull-over that already exists."""
        post = observation.post
        self._cut_radio_for_stop()
        self._over_limit_mi = 0.0
        post.declined = True
        if observation.what == WHAT_SPEEDING:
            limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
            self._begin_pull_over(limit)
            return
        summary, fine, return_message = self._observed_stop_terms(observation)
        self._begin_enforcement_pull_over(
            kind="observed",
            title="Roadside pull-over",
            summary=summary,
            fine=fine,
            reputation_hit=hos.HOS_REPUTATION_HIT,
            return_message=return_message,
            lights_message=(
                f"Lights and siren behind you. A trooper on this {post.reason} "
                f"saw {observation.what}. Signal with "
                f"{self.ctx.control_hint('take_exit')} and brake to a stop on "
                "the shoulder."
            ),
        )

    def _observed_stop_terms(self, observation) -> tuple[str, float, str]:
        post = observation.post
        what = observation.what
        if what == WHAT_DAMAGE:
            return (
                f"A trooper on this {post.reason} saw visible truck damage at "
                f"{self.truck.damage_pct:.0f} percent and ordered a roadside "
                "safety inspection.",
                UNSAFE_DAMAGE_FINE,
                "Back on the highway. Repair the truck at the next safe stop.",
            )
        if what == WHAT_CHAINS:
            return (
                f"A trooper on this {post.reason} saw you running the chain "
                "control without chains on the drives.",
                CHAIN_LAW_FINE,
                "Back on the highway. Chain up before the next control.",
            )
        if what == WHAT_FOLLOWING:
            return (
                f"A trooper on this {post.reason} watched you close right up on the vehicle ahead.",
                FOLLOWING_TOO_CLOSE_FINE,
                "Back on the highway. Leave yourself a gap.",
            )
        if what == WHAT_LIGHTS:
            return (
                f"A trooper on this {post.reason} saw you running dark.",
                LIGHTS_FINE,
                "Back on the highway. Keep your lights on after dark.",
            )
        return (
            f"A trooper on this {post.reason} pulled you over for {what}.",
            LANE_MISUSE_FINE,
            "Back on the highway. Keep right except to pass.",
        )

    # -- scale screening -----------------------------------------------------

    def _scale_selects_driver(self, stop) -> bool:
        """Whether an open scale sends this truck to the inspection lane.

        The safety record is the dial. A clean career is waved through nearly
        every time; a career carrying citations, out-of-service history and a
        damaged truck is pulled in at every open scale, which is what makes a
        dirty record feel relentless without the game inventing bad luck.
        """
        profile = self.ctx.profile
        if profile is None:
            return False
        score = refresh_selection_score(
            profile, damage_pct=float(getattr(self.truck, "damage_pct", 0.0) or 0.0)
        )
        key = post_seed(self.trip_seed, f"scale:{stop.key}", "select")
        return random.Random(key).random() < inspection_selection_chance(score)

    def safety_record_line(self) -> str:
        """The spoken safety-record line, for the driver's own status readout."""
        profile = self.ctx.profile
        if profile is None:
            return "Safety record: clean. Inspectors have no reason to pull you in."
        score = refresh_selection_score(
            profile, damage_pct=float(getattr(self.truck, "damage_pct", 0.0) or 0.0)
        )
        return safety_record_text(score)


__all__ = [
    "CERTAIN_OVER_MPH",
    "DEFERRED_STOP_MAX_MI",
    "OBSERVE_HOLD_MI",
    "PASS_PAN",
    "POST_MARKER_LEAD_MI",
    "RADIO_CUE_DUCK",
    "SCALE_BED_START_MI",
    "SCALE_NOTICE_SAMPLE",
    "TABLEAU_PASS_VOLUME",
    "TABLEAU_SHOULDER_PAN",
    "TABLEAU_SIREN_VOLUME",
    "WEIGH_STATION_REMINDER_MI",
    "EnforcementWatchMixin",
]
