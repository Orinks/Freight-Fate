# ruff: noqa: F403,F405
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..message_log import MessageCategory
from ..sim.cross_traffic import CROSS_SOUND_LEAD_S, CrossTraffic
from ..speech_pacing import EventPriority, SpeechCategory
from ..speech_text import (
    SpokenMessage,
    cruise_curve_dropped,
    cruise_curve_easing,
    roadside_chatter,
    stop_callout,
)
from ..units import spoken_feet_or_meters
from .base import TimedMessageState
from .driving_core import *
from .driving_menu_states import ArrivalState, FacilityArrivalState
from .driving_rest_states import ParkingFullState, RestStopState, ShoulderSleepConfirmationState
from .driving_speed_control import (
    KEEPER_EASE_UNDERSHOOT_MPH,
    KEEPER_OVERRUN_MPH,
    KEEPER_OVERRUN_S,
    KEEPER_SNUB_DECEL_MPS2,
    KEEPER_SNUB_MAX_BRAKE,
    KEEPER_SNUB_MIN_BRAKE,
    KEEPER_SNUB_OVER_MPH,
    KEEPER_SNUB_UNDER_MPH,
)
from .driving_stops import (
    assist_full_decel_mps2,
    assist_servo_brake,
    bar_solid_zone_mi,
    bar_tick_range_mi,
)

# Flavor kinds the driving speech ladder deliberately does not govern. They
# answer to the chatter switches and the place-callouts ladder instead. Kept
# as an explicit set rather than an absence, so the "is every kind
# classified" test can tell "decided to leave alone" from "forgot".
_FLAVOR_EVENT_KINDS = frozenset(
    {
        TripEventKind.LANDMARK,
        TripEventKind.BILLBOARD,
        TripEventKind.CITY_REACHED,
        TripEventKind.STATE_CROSSING,
        TripEventKind.TIMEZONE_CROSSING,
    }
)

_EVENT_CATEGORIES = {
    TripEventKind.HAZARD: SpeechCategory.SAFETY,
    TripEventKind.INSPECTION: SpeechCategory.SAFETY,
    # Entering and leaving a zone is the road's state, and its content is
    # a limit the driver can ask S for at any moment -- the resolver's own
    # rule puts that in STATUS (owner, 2026-08-17: these have to go at
    # quiet). The act-now half of a work zone is its lane closure, which
    # is a HAZARD and stays SAFETY.
    TripEventKind.ZONE_ENTER: SpeechCategory.STATUS,
    TripEventKind.ZONE_EXIT: SpeechCategory.STATUS,
    # A stop you have not reached yet: "Road Ranger, exit 292, one mile."
    # Worth a tone at urgent only rather than words -- a player who has
    # turned the road down that far knows how to pull in, and the arrival
    # itself (STOP_REACHED) still speaks.
    TripEventKind.STOP_AHEAD: SpeechCategory.NAVIGATION_ADVISORY,
    TripEventKind.STOP_REACHED: SpeechCategory.NAVIGATION,
    TripEventKind.CHECKPOINT: SpeechCategory.NAVIGATION,
    TripEventKind.GPS_CUE: SpeechCategory.NAVIGATION,
    TripEventKind.ARRIVED: SpeechCategory.NAVIGATION,
    TripEventKind.CURVE: SpeechCategory.NAVIGATION_ADVISORY,
    TripEventKind.TOLL_CHARGED: SpeechCategory.MONEY,
    TripEventKind.WEATHER_CHANGE: SpeechCategory.STATUS,
    TripEventKind.LANE: SpeechCategory.STATUS,
}


# How many ambient lines may wait for the road to go quiet, and how long a
# waiting one stays worth saying. Both exist because the queue below replaced
# a single slot: without a bound a long hazard would bank a recital and
# perform it once the road cleared, which is the failure the one slot was
# crudely preventing. Sized in REAL seconds, not game miles -- a line waits
# in the player's ear, not on the road -- and generously, because the lines
# that were being lost (a state line, a lane count) describe where the truck
# IS rather than something coming up, and stay true while they wait.
AMBIENT_QUEUE_MAX = 4
AMBIENT_QUEUE_MAX_AGE_S = 12.0


@dataclass
class PendingAmbient:
    """One ambient line waiting its turn, and how long it has waited.

    ``key`` names a standing thing the line is ABOUT -- a patrol post the
    truck is closing on, a traffic pressure, a toll -- rather than a moment
    that happened. A standing thing restates itself as the distance falls,
    and the queue supersedes rather than stacks for those. A moment (a state
    line, a lane count, a billboard) has no key and keeps its place.
    """

    message: str
    sound: str | None
    category: SpeechCategory | None
    waited_s: float = 0.0
    key: str | None = None
    # A line that counts down toward something can re-render at delivery, so
    # a wait never makes it lie: the 12-second age cap is REAL seconds, and
    # under time compression that is miles -- a travel plaza queued at "in 5
    # miles" was performed with two left and the building in sight (Brandon,
    # 2026-08-20). Returning None means the moment passed; drop, not speak.
    render: Callable[[], str | None] | None = None


class DrivingEventMixin:
    def _log_ambient_event(self, message: str) -> None:
        """Log an ambient line the moment it queues, not when it is spoken.

        The one-deep slot below can still let a hazard wipe this line
        outright, or a later ambient line overwrite it, before it is ever
        spoken. Either way the review buffer already has it -- a chimed
        line must never come up empty there (tester Sarah, US-12 East,
        2026-08-14: a lane closure dinged and vanished, spoken nowhere and
        reviewable nowhere; she runs terse speech, which makes this the
        ONLY record of what the earcon was for). A line this speech mode
        drops whole -- an empty terse rendering, an earcon or silence
        carrying it instead -- keeps SpokenMessage's own contract and stays
        out of review too, same as it always has. Anything that does get
        logged is the full, normal wording regardless of speech mode: a
        driver who opens review after hearing the terse form is asking for
        the detail terse left out, not a repeat of the short version.
        """
        if not message:
            return
        if isinstance(message, SpokenMessage) and not message.render(self._terse_speech()):
            return
        self.ctx.message_log.add(message, MessageCategory.EVENT)

    def _speak_ambient_event(
        self,
        message: str,
        sound: str | None = None,
        *,
        log: bool = True,
        category: SpeechCategory | None = None,
        key: str | None = None,
        render: Callable[[], str | None] | None = None,
    ) -> None:
        if log:
            # The drain call below passes log=False so a line that does
            # make it to speech is not entered into review twice.
            self._log_ambient_event(message)
        if self._hazard_deadline is not None or self._ambient_event_cooldown_s > 0.0:
            # Queued, not stored in place. This used to be a single slot, and
            # two things fell through it: a later ambient line overwrote
            # whatever was waiting, and a hazard threw the slot away outright.
            # On an interstate that meant a mapped state line was lost every
            # single time -- the crossing the driver most wants and the one
            # the map is most sure of. The trip compensated by prefixing
            # "Crossing into Ohio." to the next city line, a duplicate kept
            # deliberately because silence at a state line is worse
            # (trip_road_events._check_cities).
            #
            # A queue makes the line survive both. What keeps it from becoming
            # a recital is age, not capacity: a line that waited out a long
            # hazard is dropped in _update_ambient_events rather than
            # performed late. Full queue drops the OLDEST for the same reason.
            #
            # A line ABOUT something still ahead restates itself as the truck
            # closes on it -- "CB chatter in 5 miles", then "in 4". Queueing
            # both would say five when the driver is at four, which is worse
            # than the overwrite ever was: wrong, not merely late. So a keyed
            # line replaces the one already waiting under that key, in place,
            # keeping the wait it had already served. Only what it SAYS
            # changed; it has been waiting the whole time.
            if key is not None:
                for waiting in self._pending_ambient_events:
                    if waiting.key == key:
                        waiting.message = message
                        waiting.sound = sound
                        waiting.category = category
                        waiting.render = render
                        return
            self._pending_ambient_events.append(
                PendingAmbient(message, sound, category, key=key, render=render)
            )
            while len(self._pending_ambient_events) > AMBIENT_QUEUE_MAX:
                self._pending_ambient_events.popleft()
            return
        if sound is not None:
            self.ctx.audio.play(sound)
        self.ctx.say_event(message, interrupt=False, review=False, category=category)
        self._ambient_event_cooldown_s = tuning_for_time_scale(
            self.trip.time_scale
        ).ambient_spacing_s

    def _update_ambient_events(self, dt: float) -> None:
        if self._ambient_event_cooldown_s > 0.0:
            self._ambient_event_cooldown_s = max(0.0, self._ambient_event_cooldown_s - dt)
        # Age everything waiting, including through a hazard: a hazard no
        # longer discards the queue, so this is what stops a line describing
        # a mile the truck left long ago from being spoken as if it were now.
        # Already logged when it queued, so an aged-out line is still in
        # review -- dropped from the ear, not from the record.
        for pending in self._pending_ambient_events:
            pending.waited_s += dt
        while (
            self._pending_ambient_events
            and self._pending_ambient_events[0].waited_s >= AMBIENT_QUEUE_MAX_AGE_S
        ):
            self._pending_ambient_events.popleft()
        if self._hazard_deadline is not None:
            return
        if self._ambient_event_cooldown_s > 0.0 or not self._pending_ambient_events:
            return
        pending = self._pending_ambient_events.popleft()
        message = pending.message
        if pending.render is not None:
            # Say the distance as of NOW, not as of when it queued.
            message = pending.render()
            if message is None:
                return  # the moment passed while it waited; drop, not lie
        # Already logged the moment it queued; speaking it now must not log
        # it a second time.
        self._speak_ambient_event(
            message,
            pending.sound,
            log=False,
            category=pending.category,
            key=pending.key,
        )

    def _ambient_key(self, event) -> str | None:
        """What standing thing this ambient line is about, if any.

        Only the lines that count DOWN toward something get one. A landmark,
        a lane count, a billboard, a state line: each is its own moment, and
        two of them are two things to say, so they queue. A patrol post, a
        traffic pressure or a toll is one thing said again at a nearer
        distance, and the nearer wording replaces the further one.
        """
        post = event.data.get("cb_patrol")
        if post is not None:
            return f"cb:{getattr(post, 'leg_index', 0)}:{getattr(post, 'at_mi', 0.0)}"
        pressure = event.data.get("traffic_pressure")
        if pressure is not None:
            return f"pressure:{getattr(pressure, 'kind', '')}:{getattr(pressure, 'start_mi', 0.0)}"
        cue = event.data.get("cue")
        if getattr(cue, "kind", "") == "toll":
            return f"toll:{getattr(cue, 'key', '')}"
        if event.kind == TripEventKind.WEATHER_CHANGE:
            # The weather is one standing condition; a newer reading of it
            # replaces an older one rather than being read out in sequence.
            return "weather"
        return None

    def _should_space_ambient_event(self, event) -> bool:
        if event.kind == TripEventKind.WEATHER_CHANGE:
            return True
        if event.kind == TripEventKind.STOP_AHEAD:
            # Travel-plaza and rest-stop notices are informational: they queue
            # behind whatever route speech just played instead of stacking on
            # it -- at departure that keeps the merge instruction in front.
            #
            # The stop the player PLANNED is not a notice, it is the drive.
            # Held in the one-deep ambient slot it was overwritten by the next
            # piece of chatter, or thrown away outright by the next hazard,
            # and the player drove past a stop they had chosen (tester Darren,
            # 2026-08-11). It never goes through the ambient channel.
            return not event.data.get("planned")
        if event.kind == TripEventKind.GPS_CUE:
            cue = event.data.get("cue")
            return (
                event.data.get("cb_patrol") is not None
                or event.data.get("traffic_pressure") is not None
                or getattr(cue, "kind", "") == "toll"
            )
        return False

    def _handle_trip_event(self, event) -> None:
        if self._should_ignore_destination_exit_gps_cue(event):
            return
        if self._should_ignore_untaken_destination_facility_event(event):
            return
        if self._should_ignore_unreachable_zone_cue(event):
            return
        if self._should_ignore_unsignalled_exit_pressure(event):
            return
        kind = event.kind
        sound = _route_event_sound(event)
        if kind == TripEventKind.LANE and self._terse_speech():
            return  # lane-count callouts are a normal-verbosity nicety, muted whole
        if kind in (TripEventKind.LANDMARK, TripEventKind.BILLBOARD):
            # Ambient roadside color, filtered by the player's chatter
            # switches at speak time so a mid-trip settings change applies
            # immediately. A muted callout is dropped whole -- it never
            # becomes the A-key replay either.
            #
            # The switch decides WHAT is heard and verbosity decides how much
            # is said about it; the two are separate axes. Terse used to mute
            # roadside chatter wholesale, which left a terse player five
            # switches that were on, looked live, and did nothing at all
            # (owner, 2026-08-15). An enabled category now speaks in either
            # mode, in terse as its short form.
            category = str(event.data.get("category", ""))
            if not self.ctx.settings.chatter_enabled(category):
                return
            # Town and village names answer to the place-callouts ladder, not
            # the chatter switches: sparse keeps only the names that explain
            # a speed limit change, all adds the towns the route passes. That
            # ladder is untouched here, terse muting included -- these are
            # places, not chatter, and they are already at their short form.
            if category == "village":
                if self._terse_speech():
                    return
                mode = self.ctx.settings.place_callouts
                if mode == "off":
                    return
                if mode == "sparse" and not event.data.get("explains_limit"):
                    return
            else:
                event.message = roadside_chatter(event.message, category)
        if kind == TripEventKind.CHECKPOINT and self.ctx.settings.place_callouts != "all":
            # Curated route-town markers ("Passing X on I-40") are places,
            # not safety -- only the loudest place tier speaks them.
            return
        if kind == TripEventKind.GPS_CUE:
            cue = event.data.get("cue")
            if getattr(cue, "kind", "") == "checkpoint":
                # The two-mile advance for a place earns nothing at any tier:
                # a town is not actionable the way an exit or toll is.
                return
        if event.message and kind != TripEventKind.HAZARD:
            self._last_event_message = event.message  # replayable with A
        if kind == TripEventKind.HAZARD:
            if self._ramp_mi is not None:
                return  # off the highway: the hazard passes you by
            # The queue is NOT discarded here any more. A hazard blocks the
            # drain while it is live and the waiting lines age out on their
            # own if it runs long; a short one no longer costs the driver the
            # state line they were crossing when it fired.
            self.ctx.audio.play(sound or "ui/warning")
            self.ctx.controller.rumble.hazard()  # 750 ms right->left sweep
            # The deadline is the moment the assist has to act plus the time
            # that is the driver's own. The rolled window covers hearing the
            # warning and getting on the pedal, and fatigue eats into that
            # part only -- a drowsy driver reacts late, but the truck stops
            # no slower, and no driver reacts below the human floor.
            # A dodgeable hazard sits in the lane you are in *now*; ending up
            # in any other lane before the deadline clears it, if that lane
            # is actually open (see _finish_lane_change). By brake alone it
            # takes nearly a stop, so its deadline budgets the longer stop.
            name = event.data.get("name") or "it"
            dodgeable = bool(event.data.get("dodgeable", False))
            slack = event.data.get("deadline_s", 4.0)
            reaction = tuning_for_time_scale(self.trip.time_scale).reaction_window
            # Computed on THIS hazard's own dodgeable-ness, before it is
            # folded with whatever else may be pending -- its budget (the
            # lane-tap allowance included) is a property of itself, not of
            # the combined wording the fold branch below settles on.
            new_deadline = self._hazard_deadline_for(
                slack * reaction * hos.reaction_window_mult(self.ctx.profile.fatigue),
                dodgeable=dodgeable,
            )
            if self._hazard_deadline is None:
                # A fresh hazard starts the assist from an open pedal, with
                # nothing measured yet from the last one.
                self._hazard_names = [name]
                self._horn_scare_tried = False
                self._hazard_dodgeable = dodgeable
                self._hazard_deadline = new_deadline
                self._hazard_lane = self.lane.lane
                self._release_hazard_brake()
            elif self.truck.speed_mph <= self._hazard_target_mph():
                # A hazard is already pending, but the driver has already
                # outrun it -- it earns its own clean resolution line before
                # this one starts, instead of being silently dropped by the
                # overwrite this used to be (Shane's deer, 2026-08-14).
                self._clear_hazard()
                self._hazard_names = [name]
                self._horn_scare_tried = False
                self._hazard_dodgeable = dodgeable
                self._hazard_deadline = new_deadline
                self._hazard_lane = self.lane.lane
                self._release_hazard_brake()
            else:
                # Still live: fold the new one in rather than clobber it.
                # Any non-dodgeable hazard in the mix means "ease around" is
                # the wrong promise for the group, so it always wins the
                # wording; the shorter deadline is the one still governing
                # how much time is actually left.
                self._hazard_names.append(name)
                self._hazard_dodgeable = self._hazard_dodgeable and dodgeable
                self._hazard_deadline = min(self._hazard_deadline, new_deadline)
            # _hazard_lane is stamped by the two FRESH branches above and by
            # nothing else. Re-stamping it here put the hazard in whatever
            # lane the truck had just reached, so a hazard folding in while
            # the driver was answering the last one moved with them: dodge,
            # get re-armed in the new lane, dodge again. "The repeating
            # happened every time I was changing lanes until the two-three
            # repeats are done" -- Shane, 2026-08-21, and that is the loop.
            # The lane belongs to the hazard, not to the truck.
            self._hazard_slow_hint_said = False
            # A dodgeable hazard leaves the wheel alone: adaptive cruise or
            # the keeper stays armed through the lane change that answers it,
            # and only braking -- the driver's own, or the automatic brake
            # taking over near the deadline (see ``_update_hazard``) --
            # cancels the session. A hazard with no dodge in it (or one
            # folded in with a brake-only hazard, which always wins the
            # group's wording, see above) has no such answer, so hands go
            # back to the pedals right away (Shane, 2026-08-14: a lane change
            # was killing cruise outright, not just easing off the lane being
            # passed -- that narrower bug is 3cbdcffb).
            speed_control_was_active = not self._hazard_dodgeable and (
                self._speed_control_armed
                or self._cruise_mph is not None
                or self._keeper_mph is not None
            )
            if speed_control_was_active:
                self._disarm_speed_control()  # hands back on the wheel to brake
            # The normal/terse pair rides the event from the sim layer; the
            # delivery layer picks the rendering (R5), so no rewriting here.
            message = event.message
            if speed_control_was_active:
                suffix = "Automatic speed control canceled."
                message = (
                    message.plus(suffix)
                    if isinstance(message, SpokenMessage)
                    else f"{message} {suffix}"
                )
            self._last_event_message = message
            self.ctx.say_event(
                message,
                interrupt=True,
                category=self._event_category(event),
                # A hazard call may only come back while the hazard is still
                # live. An interrupting line hands back what it cut so the cut
                # line finishes rather than vanishing, which is what rescued
                # "you swerve around the brake lights" -- but handed back after
                # the truck is clear, "Change lanes or brake!" tells the driver
                # to dodge something that is no longer there. Same rule the
                # scale and destination exit instructions already carry: a
                # rescued line has to still be TRUE (Shane, 2026-08-21, on the
                # retread debris call).
                valid=lambda: self._hazard_deadline is not None,
            )
        elif kind == TripEventKind.INSPECTION:
            self._handle_inspection(event)
        elif kind == TripEventKind.WEATHER_CHANGE:
            self._speak_ambient_event(
                event.message,
                category=self._event_category(event),
                key=self._ambient_key(event),
            )
            self._record_weather_achievement()
        elif kind == TripEventKind.TOLL_CHARGED:
            # Money is a consequence, not chatter: the charged line rides
            # ROUTE's never-dropped contract instead of the one-deep ambient
            # slot, where the next hazard or piece of chatter could silently
            # destroy it. (The toll-ahead heads-up stays ambient.)
            self.ctx.audio.play(sound or "ui/notify")
            self.ctx.say_event(
                event.message,
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=self._event_category(event),
            )
            self.ctx.award_achievement("toll_paid", event=True)
        elif kind == TripEventKind.STATE_CROSSING:
            cue = event.data.get("cue")
            state = getattr(cue, "near_text", event.message)
            add_unique_stat(self.ctx.profile, "states_crossed", str(state))
            message = event.message
            # The welcome sign: authored content that sat unwired since it
            # shipped ("the placement that actually speaks these is
            # gameplay-layer follow-on" -- its own docstring), until Brandon
            # asked why state signs are not read (2026-08-20). The into
            # state rides the cue id's last segment, built from into_state
            # in _build_navigation_cues. Rides the billboard chatter switch
            # -- it is literally roadside signage -- and picks seeded so a
            # replayed crossing reads the same sign.
            if self.ctx.settings.chatter_billboards and cue is not None:
                import zlib

                from ..data.state_welcome import welcome_sign

                into_state = str(getattr(cue, "key", "")).rsplit(":", 1)[-1]
                # crc32, not hash(): str hash is randomized per process and
                # would pick a different sign on every launch.
                sign = welcome_sign(
                    into_state,
                    random.Random(self.trip_seed ^ zlib.crc32(into_state.encode("utf-8"))),
                )
                if sign:
                    message = f"{message} {sign}"
            self._speak_ambient_event(message, sound, category=self._event_category(event))
            self.ctx.award_achievement("state_crossing", event=True)
        elif kind == TripEventKind.TIMEZONE_CROSSING:
            if sound is not None:
                self.ctx.audio.play(sound)
            self.ctx.say_event(
                timezone_crossing_message(event, self._terse_speech()),
                interrupt=False,
                category=self._event_category(event),
            )
        elif kind == TripEventKind.CURVE:
            # Curve approach warnings are critical navigation cues: they
            # preempt ambient chatter and play on the event voice.
            if self._hazard_deadline is not None or self._ramp_mi is not None:
                return
            if not self.ctx.settings.curve_callouts:
                return
            advisory = event.data.get("advisory_mph", 0)
            curve = event.data.get("curve")
            ahead = event.data.get("ahead_mi", 0)
            message = (
                self._pacenote_text(curve, ahead, self.truck.speed_mph)
                if curve is not None
                else event.message
            )
            self._last_event_message = message
            # A curve call sounds like any other announcement until it has
            # a signature: a short cue panned to the curve's side marks
            # "road shape ahead", never a steering command -- the owner
            # steered a lane change off a bare "Sharp left" (playtest,
            # 2026-07-18). One-shot, not the continuous steering tone the
            # community ruled out. Placeholder sound until a dedicated cue
            # is auditioned (docs/sound-hunt-brief.md, need 1).
            if curve is not None:
                pan = -PACENOTE_CUE_PAN if curve.direction == "L" else PACENOTE_CUE_PAN
                self.ctx.audio.play("vehicle/curve_bink", volume=0.9, pan=pan)
            # A curve well above the cruise set point: with curve speed
            # assistance on, the bend is cruise's job -- cap the working
            # target to the advisory the way an armed exit caps for its
            # ramp, and climb back silently past the bend. Cancel to manual
            # only when the advisory sits below what cruise can hold at all
            # (owner direction, 2026-07-22 playtest: all-assists drivers
            # must not be dropped to the pedals for an ordinary bend).
            if self._cruise_mph is not None and self._cruise_mph > advisory + 5:
                assisted = (
                    self.ctx.settings.curve_speed_assist
                    and curve is not None
                    and advisory >= CRUISE_MIN_MPH
                )
                if assisted:
                    self._cruise_curve_mph = float(advisory)
                    self._cruise_curve_end_mi = max(curve.start_mi, curve.end_mi)
                    # Terse speaks the pacenote alone: its advisory number is
                    # the number cruise is easing to, and the deceleration
                    # itself is audible (R4's curve-composite row).
                    self.ctx.say_event(
                        cruise_curve_easing(message, self.ctx.settings.speed_text(advisory)),
                        interrupt=True,
                        category=self._event_category(event),
                    )
                else:
                    self._cancel_cruise()
                    self.ctx.say_event(
                        cruise_curve_dropped(message),
                        interrupt=True,
                        category=self._event_category(event),
                    )
            else:
                # Interrupt, always: a pacenote queued behind landmark chatter
                # arrived with the bend three seconds away instead of a
                # quarter mile (owner's AZ-260 log, 2026-07-19 -- the words
                # were honest when emitted and stale when finally spoken).
                # Ambient lines can wait; the road cannot.
                self.ctx.say_event(message, interrupt=True, category=self._event_category(event))
            # Open the re-arm window: if Ctrl silences this call before it
            # finishes, it gets one refreshed re-speak (owner worry,
            # 2026-07-20 -- his stop-speech reflex vs a safety cue).
            if curve is not None:
                self._critical_curve = curve
                self._critical_call_age_s = 0.0
                self._critical_respeak_at = None
        elif kind in (TripEventKind.LANDMARK, TripEventKind.BILLBOARD):
            self._speak_ambient_event(event.message, category=self._event_category(event))
        elif kind == TripEventKind.LANE:
            # Road-status color: how many lanes the road just became. Ambient,
            # so it yields to safety cues and is muted whole in terse speech.
            self._speak_ambient_event(event.message, category=self._event_category(event))
        elif kind == TripEventKind.ARRIVED:
            pass  # handled by _arrive()
        elif self._event_disables_cruise(event):
            self._cancel_cruise_for_restricted_area(event)
        else:
            # Zone entries, checkpoints, and zone-ahead/traffic warnings used
            # to interrupt here like a collision would. They are act-soon, not
            # act-now: they ride ROUTE's short patience (queued, stale means
            # flush, requeued if cut, never dropped) so each one stops being a
            # chance to erase a warning mid-word (research doc, R1). They
            # bypass the one-deep ambient slot exactly as they did when they
            # interrupted; everything else keeps its spacing.
            priority = self._event_priority(event)
            if not self._demoted_from_interrupt(event) and self._should_space_ambient_event(event):
                render = None
                stop = event.data.get("stop")
                if kind == TripEventKind.STOP_AHEAD and stop is not None:
                    # The queue's age cap is real seconds; the distance in
                    # this line decays in game miles. Re-render at delivery
                    # so a wait never makes it lie -- "Pilot in 5 miles"
                    # was performed with two left (Brandon, 2026-08-20).
                    def render(stop=stop):
                        ahead = stop.at_mi - self.trip.position_mi
                        if ahead <= 0:
                            return None
                        return stop_callout(
                            planned_prefix=self.trip.planned_prefix(stop),
                            typed_name=self.trip.name_facility(stop.name, stop.spoken_name),
                            plain_name=stop.name,
                            exit_label=stop.exit_label,
                            distance=self.trip._ahead_text(ahead),
                            parking_normal=stop.parking_text,
                            parking_certainty=stop.parking,
                            exit_hint=self.trip.exit_hint,
                        )

                self._speak_ambient_event(
                    event.message,
                    sound if kind != TripEventKind.ZONE_ENTER else None,
                    category=self._event_category(event),
                    key=self._ambient_key(event),
                    render=render,
                )
            else:
                if sound is not None and kind != TripEventKind.ZONE_ENTER:
                    self.ctx.audio.play(sound, pan=_route_event_sound_pan(event))
                self.ctx.say_event(
                    event.message,
                    interrupt=False,
                    priority=priority,
                    category=self._event_category(event),
                )
                # Any spoken route line pushes spaced ambient chatter back, so
                # an informational notice never lands on top of a navigation
                # instruction the player needs to act on.
                self._ambient_event_cooldown_s = tuning_for_time_scale(
                    self.trip.time_scale
                ).ambient_spacing_s
        if kind == TripEventKind.ZONE_ENTER:
            self.ctx.audio.play(sound or "ui/notify")
            zone = event.data.get("zone")
            if getattr(zone, "reason", "") == "construction":
                self.construction_seen = True
                self.ctx.award_achievement("construction_zone", event=True)
            elif getattr(zone, "reason", "") == "heavy traffic":
                self.traffic_seen = True
                self.ctx.award_achievement("traffic_slowing", event=True)
        if kind == TripEventKind.GPS_CUE:
            cue = event.data.get("cue")
            if (
                getattr(cue, "kind", "") == "traffic"
                or event.data.get("traffic_pressure") is not None
            ):
                self.traffic_seen = True
                self.ctx.award_achievement("traffic_slowing", event=True)
        if self.construction_seen and self.traffic_seen:
            self.ctx.award_achievement("jam_and_cones", event=True)

    def _should_ignore_destination_exit_gps_cue(self, event) -> bool:
        if self.phase != DRIVE_PHASE_DELIVERY or event.kind != TripEventKind.GPS_CUE:
            return False
        cue = event.data.get("cue")
        if getattr(cue, "kind", "") != "interchange":
            return False
        stop = self._destination_exit_stop()
        if stop is None:
            return False
        return abs(float(getattr(cue, "at_mi", -9999.0)) - stop.at_mi) <= 0.15

    def _should_ignore_unreachable_zone_cue(self, event) -> bool:
        """Drop the heads-up for a zone the delivery will never drive into.

        The facility gate zone covers the last half mile of the route, but a
        delivery leaves the highway at the destination exit at least a mile
        before that, so its 15 mile per hour limit was announced two miles out
        and then never took effect -- the driver slowed for a sign that never
        came (playtest transcript, 2026-07-20). Pickup legs and facility
        approach chains do drive to the gate, and keep their warning.
        """
        if self.phase != DRIVE_PHASE_DELIVERY or event.kind != TripEventKind.GPS_CUE:
            return False
        zone = event.data.get("zone")
        if zone is None:
            return False
        stop = self._destination_exit_stop()
        return stop is not None and zone.start_mi >= stop.at_mi

    def _should_ignore_unsignalled_exit_pressure(self, event) -> bool:
        """Exit traffic is news only to a driver taking that exit.

        Every route stop grows an exit-traffic pressure a couple of miles
        ahead of itself, and each one announced itself in turn -- so a
        corridor thick with truck stops narrated the traffic at exit after
        exit the driver had no intention of using (owner, 2026-08-15). The
        advisory earns its words only for somebody about to move right, so it
        speaks for a signalled exit and for one lane keeping is taking on the
        driver's behalf, and stays silent for the rest of them.

        The trip marks the pressure announced whether or not it is spoken, so
        arming an exit late cannot dump a stale advisory afterwards; signal
        before the window arrives and the whole call comes as usual. Nothing
        else changes -- the traffic is still there, still crowds the exit
        lane, and still explains a missed exit afterwards.

        Merging traffic and construction-taper calls are not gated: they warn
        about the road the truck is already on, not about a turn-off it is
        free to ignore.
        """
        pressure = event.data.get("traffic_pressure")
        if pressure is None or getattr(pressure, "kind", "") != "exit":
            return False
        stop = self._exit_stop
        if stop is None or not self._exit_intent_ready(stop):
            return True
        return not (pressure.start_mi <= stop.at_mi <= pressure.end_mi)

    @staticmethod
    def _is_lane_closure_pressure(event) -> bool:
        """A construction-taper merge call: the lane it warns about really is
        closing, not routine traffic colour. It used to ride the same
        one-deep ambient slot as roadside chatter, where a hazard or the
        next piece of colour could erase it before it ever spoke (tester
        Sarah, US-12 East, 2026-08-14)."""
        pressure = event.data.get("traffic_pressure")
        return pressure is not None and getattr(pressure, "kind", "") == "construction_merge"

    def _demoted_from_interrupt(self, event) -> bool:
        """The act-soon kinds R1 moved out of CRITICAL. As interrupts they
        never went near the one-deep ambient slot, and demotion must not
        start routing them through it -- a slot overwrite or a hazard would
        silently destroy them. ROUTE's queue is their delivery."""
        if event.kind in (TripEventKind.ZONE_ENTER, TripEventKind.CHECKPOINT):
            return True
        if event.kind == TripEventKind.GPS_CUE:
            if event.data.get("zone") is not None:
                return True
            if getattr(event.data.get("cue"), "kind", "") == "traffic":
                return True
            if self._is_lane_closure_pressure(event):
                return True
        return False

    def _is_critical_event(self, event) -> bool:
        """Act NOW or lose something: the hazard call is the only trip event
        left in the class. Zone entries, checkpoints, and zone-ahead/traffic
        warnings are act-soon -- they ride ROUTE's short patience and its
        never-dropped, requeued-if-cut contract instead of purging the
        channel, because every interrupt is a chance to erase a warning the
        player still needed (speech priority research, R1)."""
        return event.kind == TripEventKind.HAZARD

    @staticmethod
    def _event_category(event) -> SpeechCategory | None:
        """What this announcement is ABOUT, for the driving speech ladder.

        Deliberately separate from :meth:`_event_priority`: urgency decides
        how long a line waits, category decides whether the player's rung
        speaks it at all.

        ``None`` means "not the ladder's business" and the gate passes the
        line straight through. Two different things read as None and both
        are correct. Flavor -- billboards, landmarks, the place and border
        callouts -- answers to the chatter switches and the place-callouts
        ladder, and the owner set those separately (2026-08-15); a rung must
        never be able to silence them. And a kind nobody has classified yet
        also reads None, so the failure mode of a new event kind is a line
        too many rather than a warning the ladder ate.

        The navigation/status split is where "act-now cues only" lives: the
        stop, exit, or turn the player must act on is NAVIGATION; the
        weather turning and the road's general state are STATUS and fall
        silent at the quietest rung. Between them sits
        NAVIGATION_ADVISORY -- the lead announcement, the bend coming, the
        stop still miles off. Spoken at quiet, a tone at urgent_only, which
        is what makes those two rungs different settings.
        """
        if event.kind == TripEventKind.GPS_CUE and event.data.get("limit_change"):
            # "Speed limit raised to 55" is the road's state; S answers it on
            # demand. The other GPS cues -- merge onto this highway, take that
            # exit -- are the turn itself and stay NAVIGATION.
            return SpeechCategory.STATUS
        if event.kind == TripEventKind.GPS_CUE and event.data.get("advance"):
            # "In a mile, take exit 42" -- the heads-up. The near call that
            # follows at the exit itself is the one you cannot recover from
            # and stays NAVIGATION, spoken at every rung.
            return SpeechCategory.NAVIGATION_ADVISORY
        if event.kind == TripEventKind.GPS_CUE and event.data.get("npc_vehicle") is not None:
            # A traffic advisory: "Merging car, 2.2 miles". Awareness of the
            # road around you, which the pass-by and engine sounds already
            # carry, and no action attached at that distance (owner,
            # 2026-08-17: "sound is enough"). The act-now half of traffic is a
            # HAZARD event -- "Change lanes or brake! Merging traffic right
            # ahead" -- which is SAFETY and speaks at every rung.
            return SpeechCategory.STATUS
        return _EVENT_CATEGORIES.get(event.kind)

    def _event_priority(self, event):
        """How long this announcement is willing to wait behind other speech.

        ROUTE is act-soon plus every consequence that must be heard: the
        stop the player planned, zone entries and checkpoints, zone-ahead
        and traffic warnings, a construction taper's lane-closure merge
        call, and money (a charged toll could otherwise age out silently,
        making normal mode lossier than terse mode's "what it cost"
        guarantee -- the toll-ahead heads-up stays AMBIENT, since losing the
        preview costs nothing once the charge is guaranteed). Everything
        else waits its turn.
        """
        if self._is_critical_event(event):
            return EventPriority.CRITICAL
        if event.kind in (
            TripEventKind.ZONE_ENTER,
            TripEventKind.CHECKPOINT,
            TripEventKind.TOLL_CHARGED,
        ):
            return EventPriority.ROUTE
        if event.kind == TripEventKind.GPS_CUE:
            if event.data.get("zone") is not None:
                return EventPriority.ROUTE
            cue_kind = getattr(event.data.get("cue"), "kind", "")
            if cue_kind == "traffic":
                return EventPriority.ROUTE
            if self._is_lane_closure_pressure(event):
                return EventPriority.ROUTE
            # The direction itself: which way onto the highway, which way
            # through an interchange, which way down a street. Lose one and
            # the driver goes the wrong way, so none of them may age out.
            # The route-start merge -- "Merge onto I-70 West toward
            # Silverthorne; 67 miles", the first instruction of the whole run
            # -- was dropped as stale chatter on the owner's Denver playtest.
            # The ADVANCE half stays ambient: a heads-up that arrives late is
            # worse than one that never comes, which is the lesson the turn
            # approach cue already carries.
            if not event.data.get("advance") and cue_kind in (
                "onramp",
                "maneuver",
                "local_turn",
            ):
                return EventPriority.ROUTE
        if event.kind == TripEventKind.STOP_AHEAD or event.data.get("planned"):
            return EventPriority.ROUTE
        return EventPriority.AMBIENT

    def _should_ignore_untaken_destination_facility_event(self, event) -> bool:
        if self.phase != DRIVE_PHASE_DELIVERY or self._destination_exit_taken:
            return False
        zone = event.data.get("zone")
        if zone is None:
            return False
        return zone.reason in {
            "destination approach",
            "facility access road",
            "facility gate",
        }

    def _event_disables_cruise(self, event) -> bool:
        if self._cruise_mph is None:
            return False
        if event.kind == TripEventKind.ZONE_ENTER:
            return True
        if event.kind != TripEventKind.GPS_CUE:
            return False
        zone = event.data.get("zone")
        if zone is None:
            return False
        # An armed speed-control session stays on for the advance warning so
        # cruise can slow for the lower limit, then hands off at zone entry.
        if self._speed_control_armed and self.ctx.settings.speed_keeper:
            return False
        return zone.reason in {"construction", "heavy traffic"}

    def _cancel_cruise_for_restricted_area(self, event) -> None:
        message = event.message
        zone = event.data.get("zone")
        if self._speed_control_armed and self.ctx.settings.speed_keeper and zone is not None:
            self._cancel_cruise(preserve_session=True)
            self._engage_keeper(
                zone.limit_mph,
                zone.reason,
                target_mph=zone.limit_mph,
                announce=False,
            )
            self.ctx.audio.play("ui/notify")
            message = (
                f"{message} Speed keeper holding {self.ctx.settings.speed_text(self._keeper_mph)}."
            )
            self.ctx.say_event(
                message,
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=self._event_category(event),
            )
            return
        self._cancel_cruise()
        self.ctx.audio.play("ui/notify")
        # A restricted area (construction, heavy traffic) is act-soon: ROUTE
        # priority gives chatter under a second before going in front of it,
        # without an interrupt that could cut a real warning mid-word.
        if not self._terse_speech():
            message = f"{message} Adaptive cruise disabled; take manual speed control."
        self.ctx.say_event(
            message,
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=self._event_category(event),
        )

    def _hooked_trailer_defect(self) -> str | None:
        """What an inspector would write up on the trailer, if anything."""
        from ..models.trailer_yard import pickup_plan

        if self.ctx.profile is None or self.job is None or self.trailer_refused:
            return None
        plan = pickup_plan(self.job, self.ctx.profile)
        return plan.trailer.defect if plan.trailer is not None else None

    def _handle_inspection(self, event) -> None:
        """Route-backed enforcement with stable evidence and no duplicate fines."""
        event_key = str(
            event.data.get(
                "key",
                f"{event.message}:{round(self.trip.position_mi, 1)}:{self.hos_fine_count}",
            )
        )
        if event_key in self.enforcement_events:
            return
        self.enforcement_events.add(event_key)
        p = self.ctx.profile
        fine = hos.HOS_FINES[min(self.hos_fine_count, len(hos.HOS_FINES) - 1)]
        self.hos_fine_count += 1
        evidence = list(event.data.get("evidence", ()))
        # A trailer hooked out of a drop yard came with whatever the last
        # driver left on it, and an inspector finds what a walk-around would
        # have. This is drop-and-hook's real cost, arriving at the worst moment.
        trailer_defect = self._hooked_trailer_defect()
        if trailer_defect:
            evidence.append(trailer_defect)
        if not evidence:
            evidence = ["HOS/ELD violation"]
        evidence_text = ", ".join(evidence)
        self.ctx.audio.play("ui/error")
        self.ctx.controller.rumble.alert()
        serious_hos = (
            self.ctx.settings.hos_mode not in hos.HOS_NON_ENFORCED_MODES
            and self.hos.in_violation(self.ctx.settings.hos_mode)
        )
        if serious_hos:
            # A serious violation is a REAL roadside stop: lights, signal,
            # brake to the shoulder, and the 10-hour out-of-service order
            # passes while the truck is actually stopped. The old instant
            # ledger hit teleported the clock ten hours mid-drive with the
            # wheels still rolling -- the owner heard "you are stopped"
            # while cruising, then found 3 AM had become 1:57 PM between
            # two spoken lines (log, 2026-07-24). Fine and reputation are
            # applied by the stop itself, not here.
            self._begin_enforcement_pull_over(
                kind="hos_out_of_service",
                title="Log check",
                summary=(
                    f"{event.message} Evidence: {evidence_text}. The officer "
                    "writes the order: out of service, ten hours, right here."
                ),
                fine=fine,
                reputation_hit=hos.HOS_REPUTATION_HIT,
                return_message=("Back on the highway with a reset clock. Keep the logbook clean."),
                lights_message=(
                    "Lights and siren behind you for a log check. Signal "
                    f"with {self.ctx.control_hint('take_exit')} and brake to "
                    "a stop on the shoulder."
                ),
            )
            _record_inspection(self.ctx, event=True)
            return
        p.money -= fine  # can go negative; never a game over
        p.career.reputation = max(0.0, p.career.reputation - hos.HOS_REPUTATION_HIT)
        message = (
            f"{event.message} Evidence: {evidence_text}. "
            f"Fined {fine:,.0f} dollars, and your reputation took a hit."
        )
        # A fine is money, not an act-now warning: ROUTE's never-dropped
        # queue instead of an interrupt that could erase one.
        self.ctx.say_event(
            message,
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=self._event_category(event),
        )
        _record_inspection(self.ctx, event=True)

    def _place_out_of_service(self) -> None:
        _advance_rest_clock(self, OUT_OF_SERVICE_MIN)
        self.hos.sleep()
        self.ctx.profile.fatigue = hos.rest_sleep(self.ctx.profile.fatigue)
        self.out_of_service_count += 1
        self.ctx.profile.active_trip = self.snapshot()
        self.ctx.save_profile()

    def _try_rest_stop(self) -> None:
        rest_hint = self.ctx.control_hint("rest")
        exit_hint = self.ctx.control_hint("take_exit")
        status_hint = self.ctx.control_hint("status_menu")
        if self._pull_over is not None:
            self._set_status("Rest-stop planning unavailable during a police stop.")
            self.ctx.say(
                "Resolve the police stop before planning a rest stop. "
                f"Press {exit_hint} to signal the trooper stop."
            )
            return
        # An open scale ahead is not optional, so the rest key must not plan
        # a sleep stop past it -- the scale comes first, then the plan.
        if self.truck.speed_mph > DOCKING_MAX_MPH and self._scale_outranks_rest_planning():
            return
        # ...and the scale's own RAMP claims the key too, at any speed. The
        # guard above only fires while the scale is still AHEAD, and a truck
        # on the ramp is already past its mile: the rest key fell straight
        # through to sleep planning and answered "the scale is behind you,
        # plan the next sleep-capable stop" to a driver doing exactly what
        # the scale had just told them to do -- press this key at the scale
        # (owner playtest, 2026-08-21). Jerry's 2026-08-12 report was the
        # same confusion one step earlier, before the ramp; that fix guarded
        # the approach and left the ramp itself open.
        # Stopped ON the scale falls through on purpose: the check-in below
        # is what the key means there.
        ramp = self._ramp_stop
        on_scale_ramp = ramp is not None and getattr(ramp, "type", "") == "weigh_station"
        if on_scale_ramp and self.truck.speed_mph > DOCKING_MAX_MPH:
            self.ctx.say(
                f"On the ramp for {ramp.spoken_name}. Come to a full stop at the "
                f"scale, then press {rest_hint} to check in."
            )
            return
        stop = self.trip.nearest_stop_within()
        if self.truck.speed_mph <= DOCKING_MAX_MPH:
            if stop is None:
                if not _secure_truck_for_stopped_menu(self):
                    self.ctx.say("Come to a complete stop first.")
                    return
                reason = self.emergency_shoulder_sleep_reason()
                if reason is None:
                    self.ctx.say(
                        "Emergency shoulder sleep is not available here. "
                        "Use a route stop for normal breaks and sleep."
                    )
                    return
                self.ctx.push_state(
                    ShoulderSleepConfirmationState(self.ctx, self, reason, self.trip.position_mi)
                )
                return
            self._open_poi_stop(stop)
            return

        if self._ramp_stop is not None and self._is_selected_stop(self._ramp_stop):
            active = self._ramp_stop
            assist = (
                "assistance is armed and will stop at the entrance after the ramp control is clear"
                if self._selected_stop_assist_armed and self.ctx.settings.selected_stop_assist
                else "assistance is off; brake to a complete stop at the entrance"
            )
            message = f"On the selected ramp for {active.spoken_name}; {assist}."
            self._set_status(message)
            # The cab confirming a control the player just worked. At the
            # quiet rung this becomes its earcon: you know you pressed K.
            self.ctx.say(message, category=SpeechCategory.CONFIRMATION)
            return

        selected = self._selected_sleep_stop()
        if selected is not None:
            ahead = selected.at_mi - self.trip.position_mi
            if ahead <= 0:
                self.ctx.say(
                    f"{selected.spoken_name} is behind you. Assistance is off. "
                    "Continue safely and plan the next sleep-capable stop with "
                    f"{rest_hint}. If you are already safely stopped at this route "
                    f"point, press {rest_hint} to open its menu."
                )
                return
            self._speak_selected_sleep_stop(selected, repeated=True)
            return

        if stop is not None and stop.at_mi <= self.trip.position_mi:
            self.ctx.say(
                f"{stop.spoken_name} is behind you. Continue safely and plan the next "
                f"sleep-capable stop with {rest_hint}. If you are already safely stopped "
                f"at this route point, press {rest_hint} to open its menu."
            )
            return

        if self._exit_stop is not None and self._exit_signal_on:
            active = self._exit_stop
            self._set_status(f"Exit signal active for {active.spoken_name}.")
            self.ctx.say(
                f"The exit for {active.spoken_name} is already selected. "
                f"Press {exit_hint} to cancel it before planning a different sleep stop."
            )
            return

        candidates = [
            candidate
            for candidate in self.trip.stops
            if 0 < candidate.at_mi - self.trip.position_mi <= self._exit_window_mi()
            and "sleep" in candidate.actions
            and candidate.parking != "none"
        ]
        candidates.sort(key=lambda candidate: candidate.at_mi)
        if not candidates:
            self._set_status("No sleep-capable route stop close enough ahead to plan.")
            self.ctx.say(
                "No sleep-capable route stop is close enough ahead to plan. "
                f"Open the driving status menu with {status_hint} and review upcoming "
                "route points. If you must rest, stop "
                "safely away from a route point and use emergency shoulder sleep."
            )
            return
        candidate = candidates[0]
        current = self.trip.planned_stop
        if current is not None and current.key != candidate.key:
            self._set_status(f"Planned stop remains {current.spoken_name}.")
            self.ctx.say(
                f"Your planned stop remains {current.spoken_name}. "
                f"{candidate.spoken_name} is also ahead. Open the stop details from "
                "the route map to move the plan before selecting it."
            )
            return
        self.trip.planned_stop_key = candidate.key
        self._selected_stop_key = candidate.key
        self._selected_stop_assist_armed = False
        self._selected_stop_assist_said = False
        self._speak_selected_sleep_stop(candidate, repeated=False)

    def _selected_sleep_stop(self):
        key = self._selected_stop_key
        if key is None:
            return None
        return next((stop for stop in self.trip.stops if stop.key == key), None)

    def _is_selected_stop(self, stop) -> bool:
        return self._selected_stop_key is not None and self._selected_stop_key == getattr(
            stop, "key", None
        )

    def _speak_selected_sleep_stop(self, stop, *, repeated: bool) -> None:
        ahead = max(0.0, stop.at_mi - self.trip.position_mi)
        distance = self.ctx.settings.distance_text(ahead, precise=True)
        exit_text = f" at {stop.exit_label}" if stop.exit_label else ""
        assist = (
            "Planned rest-stop stopping assistance is on; after you signal and set "
            "the exit lane, it will stop at the entrance."
            if self.ctx.settings.selected_stop_assist
            else "Planned rest-stop stopping assistance is off; brake to a complete stop at the entrance."
        )
        prefix = "Still selected" if repeated else "Planned sleep stop selected"
        message = (
            f"{prefix}: {stop.spoken_name}, {distance} ahead{exit_text}. "
            f"Press {self.ctx.control_hint('take_exit')} to signal for this exit. {assist}"
        )
        self._set_status(message)
        self.ctx.say(message)

    def _clear_selected_stop_intent(self) -> None:
        if self._selected_stop_assist_brake > 0.0:
            if self.truck.brake <= self._selected_stop_assist_brake + 1e-6:
                self.truck.brake = 0.0
            self._selected_stop_assist_brake = 0.0
        self._selected_stop_key = None
        self._selected_stop_assist_armed = False
        self._selected_stop_assist_said = False

    def _open_poi_stop(
        self, stop, *, settle: bool = False, prefer_sleep: bool | None = None
    ) -> None:
        # Secure the truck before handing off to the stop menu: zero the
        # throttle, apply the service brake, and set the parking brake. A truck
        # that rolled in just under the docking threshold (or idled in gear)
        # would otherwise keep creeping while the driver rests -- napping while
        # the rig drifts down the freeway. Mirrors the pickup/delivery arrivals.
        if not _secure_truck_for_stopped_menu(self):
            self.ctx.say("Come to a complete stop first.")
            return
        selected_sleep_intent = self._is_selected_stop(stop)
        if prefer_sleep is None:
            prefer_sleep = selected_sleep_intent
        if selected_sleep_intent:
            self._clear_selected_stop_intent()
        if self.trip.is_planned(stop):
            # Plan fulfilled; the stop menu announces itself.
            self.trip.planned_stop_key = None

        if settle:
            # A POI stop that pulls in through this wait is a menu-driven
            # stop like a roadside inspection: the frame loop that eases
            # revs down between frames stops the instant the wait state
            # takes over, so without this the engine audio froze at
            # whatever rev the approach left it at for the whole stop.
            self._settle_engine_to_idle()
            _advance_rest_clock(self, STOP_PULL_IN_MIN)
            self.hos.on_duty(STOP_PULL_IN_MIN)
            self.ctx.profile.active_trip = self.snapshot()
            self.ctx.save_profile()

            def complete() -> None:
                self.ctx.pop_state()
                self._open_poi_stop(stop, settle=False, prefer_sleep=prefer_sleep)

            self.ctx.push_state(
                TimedMessageState(
                    self.ctx,
                    title="Pulling into stop",
                    message=(
                        f"Stopped at {stop.spoken_name}. Brakes set; menu opening in a moment."
                    ),
                    status=f"Stopped at {stop.spoken_name}; menu opening. Please wait.",
                    seconds=STOP_PULL_IN_WAIT_S,
                    on_complete=complete,
                    sound_key="ui/notify",
                )
            )
            return

        can_sleep = "sleep" in stop.actions
        if can_sleep and hos.parking_is_full(
            self.trip_seed, stop.at_mi, self.trip.local_hour, stop.parking_spaces
        ):
            self.ctx.push_state(ParkingFullState(self.ctx, self, stop))
            return
        self.ctx.push_state(RestStopState(self.ctx, self, stop, prefer_sleep=prefer_sleep))
        self.ctx.award_achievement("first_rest_stop")

    def _take_exit(self) -> None:
        self._toggle_exit_signal()

    def _toggle_exit_signal(self) -> None:
        if self._ramp_mi is not None:
            self.ctx.say("You are already on the exit ramp. Brake to a stop.")
            return
        selected = self._selected_sleep_stop()
        selected_ahead = (
            selected is not None
            and 0 < selected.at_mi - self.trip.position_mi <= self._exit_window_mi()
        )
        # Explicit T selection outranks inferred destination bookkeeping.
        stop = selected if selected_ahead else self._exit_stop or self._upcoming_exit_stop()
        # ...and a nearer open scale outranks both: the inspection lane is
        # not optional, and arming the farther ramp is exactly what carried
        # a tester past the scale unarmed. The plan itself survives.
        scale_claimed = self._scale_claiming_exit(stop)
        outranked = stop if scale_claimed is not None else None
        if scale_claimed is not None:
            stop = scale_claimed
        if stop is None:
            self.ctx.say(
                "No route exit to signal for yet. Press "
                f"{self.ctx.control_hint('rest')} to plan an upcoming "
                "sleep-capable stop, or wait for an exit announcement."
            )
            return
        responding_to_destination_callout = (
            stop.type == "delivery_destination"
            and self._destination_exit_response_s > 0.0
            and self._destination_exit_key(stop) == self._destination_exit_announced_key
        )
        if responding_to_destination_callout:
            # The shared event voice may now be reading a newer safety warning,
            # so do not stop it just to replace the earlier exit callout.
            self._destination_exit_response_s = 0.0
        self._exit_stop = stop
        ahead = stop.at_mi - self.trip.position_mi
        if self._exit_signal_on:
            # This close to the gore, one stray press must not silently throw
            # the approach away (playtested: an X meant as "confirm" canceled
            # the signal and cost the exit). The first press keeps the signal
            # and says so; only a deliberate second press cancels.
            if ahead <= EXIT_CANCEL_GUARD_MI and not self._exit_cancel_armed:
                self._exit_cancel_armed = True
                self.ctx.say(
                    "Signal stays on. Hold the exit lane and keep slowing. "
                    f"Press {self.ctx.control_hint('take_exit')} again to cancel the exit."
                )
                return
            self._exit_signal_on = False
            self._exit_cancel_armed = False
            self._exit_signal_canceled = True
            # Letting the cap linger would leave automatic control crawling
            # at ramp speed down the open highway after the driver begged off.
            self._cruise_exit_mph = None
            self._destination_exit_response_s = 0.0
            canceled_selected = self._is_selected_stop(stop)
            if canceled_selected:
                self._clear_selected_stop_intent()
            planned = (
                " Planned rest-stop stopping assistance disarmed. Your planned stop "
                "remains on the route map."
                if canceled_selected
                else ""
            )
            message = f"Signal canceled. Keep following the highway.{planned}"
            self._set_status(message)
            self.ctx.say(message)
            return
        self._exit_signal_on = True
        self._exit_cancel_armed = False
        self._exit_signal_canceled = False
        # The player just signalled for an exit; count it toward retiring the
        # "press X to signal" instruction, and update what the stop callout
        # will say from here (research doc R7).
        self._note_instruction_demonstrated("take_exit")
        self._refresh_exit_hint()
        # Re-arming after a cancel starts the distance anchors over; without
        # this the milestones already spoken stay marked and the second
        # approach runs silent.
        self._exit_countdown_said = set()
        self.ctx.audio.play("vehicle/signal_tone", volume=0.7, pan=0.6)
        if scale_claimed is not None:
            head = f"Signal on for the scale exit: {stop.name},"
        elif stop.type == "delivery_destination":
            labeled = getattr(stop, "exit_phrase", "") or stop.exit_label
            head = (
                # A labeled exit already names itself; don't repeat the
                # facility that the fallback phrase would have baked in.
                f"Signal on for {labeled}, destination exit for {stop.name},"
                if labeled
                else f"Signal on for the destination exit for {stop.name},"
            )
        else:
            # Once the stop-ahead callout has named this facility in full this
            # leg, the exit signal speaks its proper name alone (research doc
            # R6).
            facility = self.trip.name_facility(stop.name, stop.spoken_name)
            if stop.exit_label:
                head = f"Signal on for {stop.exit_label}, {facility},"
            else:
                head = f"Signal on for the {facility} exit,"
        lane_hint = "" if self.lane.lane == 0 else " Get into the right lane."
        # Name the ramp's ending now, while there is still a mile of
        # mainline to plan the braking on: a stop sign heard only on the
        # ramp cost real playtesters real cross-traffic damage.
        ending = {
            "signal": " The ramp ends at a traffic light.",
            "stop": " The ramp ends at a stop sign.",
        }.get(self._ramp_control_for(stop), "")
        ahead_text = self.ctx.settings.distance_text(ahead, precise=True)
        ramp_text = self.ctx.settings.speed_text(RAMP_MAX_MPH)
        if self.ctx.settings.lane_is_automated():
            self._exit_lane_alignment = EXIT_LANE_READY
            self._exit_lane_ready_said = True
            self.ctx.audio.play("ui/notify", volume=0.6)
            # The first granted lane of the run says who granted it. A driver
            # who never asked for this needs one chance to notice the truck
            # is doing it, and where to change that.
            if self._lane_keeping_grant_said:
                granted = "Exit lane set."
            else:
                self._lane_keeping_grant_said = True
                granted = "Exit lane set for you by lane keeping."
            message = (
                f"{head} {ahead_text} ahead. {granted}{lane_hint} "
                f"Slow to {ramp_text} or less for the ramp.{ending}" + self._cap_cruise_for_ramp()
            )
        else:
            message = (
                f"{head} {ahead_text} ahead.{lane_hint} "
                "Move right for the exit lane, then slow to "
                f"{ramp_text} or less for the ramp.{ending}" + self._cap_cruise_for_ramp()
            )
        if self._is_selected_stop(stop):
            self._selected_stop_assist_armed = self.ctx.settings.selected_stop_assist
            if self._selected_stop_assist_armed:
                lane_action = "Set the exit lane; " if self.ctx.settings.lane_is_manual() else ""
                message += (
                    " Planned rest-stop stopping assistance armed. "
                    f"{lane_action}After the ramp control is clear, it will stop at the entrance."
                )
            else:
                message += " Brake to a complete stop at the entrance."
        if (
            scale_claimed is not None
            and outranked is not None
            and (self._is_selected_stop(outranked) or self.trip.is_planned(outranked))
        ):
            message += " Your planned sleep stop waits until you are past the scale."
        self._set_status(message)
        if responding_to_destination_callout:
            # Queue behind whichever event is currently speaking. Usually that
            # is the exit callout; if a critical warning preempted it, the
            # warning must finish before the confirmation.
            #
            # And it may only come back while the exit is still THERE. A line
            # cut by an urgent warning is handed back so it finishes rather
            # than vanishing, which is right -- but "move right for the exit
            # lane" handed back after the gore is behind the truck instructs a
            # maneuver that no longer exists. That is the same fault the scale
            # exit line was given a validity check for on 21 August; this one
            # was missed because the report only ever named the scale.
            exit_mi = getattr(stop, "at_mi", None)
            self.ctx.say_event(
                message,
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
                valid=(None if exit_mi is None else (lambda: self.trip.position_mi < exit_mi)),
            )
        else:
            self.ctx.say(message)

    def _cap_cruise_for_ramp(self) -> str:
        """Bring automatic speed control down to ramp speed for an armed exit.

        Arming an exit commits the truck to leaving the highway, so the cruise
        target has to come down with it. Otherwise automatic control holds
        highway speed straight through the gore point and the driver loses the
        exit without ever touching a control. Returns the spoken addition, or
        an empty string when there is nothing to say.
        """
        if self._cruise_mph is None:
            # Paused mid-session -- a zone keeper, or a planned-stop pause.
            # Remember the cap so cruise resumes at ramp speed, but say
            # nothing: the keeper is already holding a low zone speed.
            if self._speed_control_armed and self._speed_control_target_mph is not None:
                self._cruise_exit_mph = min(self._speed_control_target_mph, RAMP_CRUISE_TARGET_MPH)
            return ""
        # The ramp accepts 45 mph or less, but the cruise loop deliberately
        # targets 40. Its normal two-mph brake deadband, downhill acceleration,
        # and frame timing must not leave the truck hovering just above the
        # hard acceptance boundary at the gore point.
        capped = min(self._cruise_mph, RAMP_CRUISE_TARGET_MPH)
        if self._cruise_exit_mph is not None and self._cruise_exit_mph <= capped:
            # The destination-exit announcement already capped cruise and said
            # so; pressing X right after must not repeat the whole sentence.
            return ""
        self._cruise_exit_mph = capped
        # The number is where the truck will BE at the gore, not where it goes
        # now: _ramp_approach_cap_mph holds road speed until the exit is close
        # enough to shed for. Arming five miles out and dropping straight to
        # ramp speed is the "keeper goes to 40 miles away from the exit"
        # report (Shane, 2026-08-15).
        action = "will ease to" if self.truck.speed_mph > self._cruise_exit_mph + 1.0 else "holding"
        return (
            f" Adaptive cruise {action} "
            f"{self.ctx.settings.speed_text(self._cruise_exit_mph)} for the ramp."
        )

    def _ramp_approach_cap_mph(self) -> float | None:
        """The armed exit's cap right now, measured off the road still left.

        The ramp target is where the truck has to BE at the gore. Applied the
        moment the exit is armed it is also where the truck goes immediately,
        and an exit arms as much as five miles out (further under time
        compression, which is what the arming window is sized in) -- so a
        driver heard the callout and then watched automatic control sit at 40
        for miles of open interstate with the exit nowhere near (tester
        report, Shane, 2026-08-15).

        Instead the cap glides: corridor speed stands until the exit is inside
        the road this truck needs to shed for it, then comes down along the
        deceleration itself, reaching the ramp number a little before the gore.
        The road is priced exactly as the keeper's ease prices it -- a reaction
        budget in real seconds at the speed the truck is doing, and a
        comfortable shed rate under that.

        In REAL miles, not compressed ones. Pricing the road through the
        effective time scale looked prudent and was the same report all over
        again: at high pacing the cap fell under a 65 mph cruise nine miles
        out, so signalling early was itself what slowed the truck (Shane,
        2026-08-15, signalling nine miles before a truck stop). The clock is
        where that problem belongs and is now where it is solved --
        ``Trip._armed_exit_decompression`` puts the trip back on real time
        for the whole approach window, which is wider than this glide -- so by
        the time the cap has anything to say, the miles under it really are
        real ones.
        """
        floor = self._cruise_exit_mph
        if floor is None:
            return None
        if self._ramp_mi is not None:
            return floor  # already on the ramp: the number is the number
        stop = self._exit_stop or self._ramp_stop
        if stop is None:
            return floor
        ahead = stop.at_mi - self.trip.position_mi
        if ahead <= 0.0:
            return floor
        # Priced at the set speed, not the live one, so the cap cannot chase
        # its own slowing and hand the road back a mile an hour at a time.
        speed = max(self.truck.speed_mph, self._cruise_mph or 0.0, floor)
        reaction_mi = APPROACH_REACTION_S * speed / 3600.0
        brake_m = max(0.0, ahead - reaction_mi) * METERS_PER_MILE
        floor_mps = floor / MPH_PER_MPS
        allowed = (floor_mps**2 + 2.0 * APPROACH_DECEL_MPS2 * brake_m) ** 0.5 * MPH_PER_MPS
        return max(floor, allowed)

    def _reset_exit_lane_state(self) -> None:
        self._exit_lane_alignment = 0.0
        self._exit_lane_prompt_said = False
        self._exit_lane_ready_said = False
        self._exit_commit_said = False
        self._exit_cancel_armed = False
        self._exit_right_hold_s = 0.0
        self._exit_right_taps = 0
        self._exit_tap_hint_said = False
        self._exit_countdown_said: set[float] = set()

    def _exit_lane_ready(self) -> bool:
        # Ramps peel off the right lane: no amount of in-lane alignment
        # helps from the left lane, and a change in progress toward the
        # right still counts as making the gore.
        if self.lane.lane != 0 and self._lane_change_target != 0:
            return False
        return (
            self._exit_lane_alignment >= EXIT_LANE_READY
            or self.lane.offset >= EXIT_LANE_OFFSET_READY
        )

    def _update_exit_countdown(self, stop) -> None:
        """Distance reminders for an armed exit, every steering mode.

        A canyon approach buries a single signal-on announcement under
        pacenotes and limit changes (owner playtest: signal at 4.7 miles,
        then silence until the miss). The countdown re-anchors the exit as
        it closes, and names the lane fix while there is road to make it.

        Terse speech opts out of the whole countdown: the player asked for
        the signal-on announcement to be the last word."""
        if self._terse_speech():
            return
        ahead = stop.at_mi - self.trip.position_mi
        if ahead <= 0:
            return
        milestones = EXIT_COUNTDOWN_MILESTONES_MI
        if self.ctx.settings.lane_is_manual():
            # Players doing their own lane work get the two-mile exit-lane prep
            # prompt; the countdown adds only the closer anchors.
            milestones = milestones[1:]
        crossed = [m for m in milestones if ahead <= m and m not in self._exit_countdown_said]
        if not crossed:
            return
        # Time compression can cross several milestones in one frame:
        # mark them all, speak only the nearest.
        self._exit_countdown_said.update(crossed)
        nearest = min(crossed)
        if nearest >= 1.0:
            distance = self.ctx.settings.distance_text(nearest)
        else:
            distance = self.ctx.settings.short_distance_text(nearest)
        name = (
            "Destination exit"
            if stop.type == "delivery_destination"
            else f"Exit for {stop.spoken_name}"
        )
        lane_text = ""
        if not self._exit_lane_ready():
            lane_text = (
                " Tap Right to the right lane."
                if self.ctx.settings.lane_is_automated()
                else " Steer right for the exit lane."
            )
        self.ctx.audio.play("ui/notify", volume=0.6)
        self.ctx.say_event(
            f"{name} in {distance}.{lane_text}",
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.NAVIGATION,
        )

    def _update_exit_preparation(self, keys, dt: float) -> None:
        stop = self._exit_stop
        if stop is None or self._ramp_mi is not None:
            self._reset_exit_lane_state()
            return
        # The signal is how a driver COMMITS to an exit -- but with lane
        # keeping automated they never press it, because the game itself says
        # "lane keeping will take this exit". Gating the speed assist on the
        # signal therefore switched it off for exactly the preset that
        # promises the most help: the announcement said "adaptive cruise will
        # ease to 40 for the ramp", nothing eased, and the truck went through
        # the gore at 53 and missed the exit (owner playtest, Denver->
        # Silverthorne, 2026-08-19). Automated lane keeping IS the commitment.
        committed = self._exit_signal_on or self.ctx.settings.lane_is_automated()
        if committed:
            self._update_exit_countdown(stop)
            self._update_exit_speed_assist(stop)
        if self.ctx.settings.lane_is_automated():
            return
        if not self._exit_signal_on:
            return
        ahead = stop.at_mi - self.trip.position_mi
        if ahead < -EXIT_COMMIT_WINDOW_MI:
            return

        right = keys[pygame.K_RIGHT]
        left = keys[pygame.K_LEFT]
        # A quick tap is how full-lane-keeping players change lanes; when the
        # lane work is yours it only nudges the wheel and the exit lane never
        # builds. Two taps
        # on one approach earn the how-to, once, so the silence never reads
        # as broken keys.
        if right:
            self._exit_right_hold_s += dt
        else:
            if 0.0 < self._exit_right_hold_s <= EXIT_TAP_HOLD_S:
                self._exit_right_taps += 1
            self._exit_right_hold_s = 0.0
        if (
            self._exit_right_taps >= 2
            and self._exit_lane_alignment < EXIT_LANE_READY
            and not self._exit_tap_hint_said
        ):
            self._exit_tap_hint_said = True
            self.ctx.say(
                "You are holding the lane yourself, so taps only nudge the wheel. "
                "Hold Right to steer into the exit lane."
            )
        if right:
            self._exit_lane_alignment += dt / 1.2
        elif left:
            self._exit_lane_alignment -= dt / 0.8
        elif (
            self._exit_lane_ready_said
            and self._exit_lane_alignment >= EXIT_LANE_READY
            and self.lane.offset >= -0.25
        ):
            self._exit_lane_alignment = max(self._exit_lane_alignment, EXIT_LANE_READY)
        elif self.lane.offset >= EXIT_LANE_OFFSET_READY:
            self._exit_lane_alignment += dt / 2.0
        elif self.lane.offset < -0.25:
            self._exit_lane_alignment -= dt / 0.8
        else:
            self._exit_lane_alignment -= dt / 4.0
        self._exit_lane_alignment = max(0.0, min(1.0, self._exit_lane_alignment))

        if 0 < ahead <= EXIT_LANE_PREP_MI and not self._exit_lane_prompt_said:
            self._exit_lane_prompt_said = True
            pressure = self._active_exit_pressure(stop)
            pressure_text = (
                " Traffic is tight, so hold the lane and let the gap open."
                if pressure is not None and pressure.intensity >= 0.35
                else ""
            )
            self.ctx.say_event(
                f"Exit lane in {self.ctx.settings.distance_text(ahead, precise=True)}. "
                f"Signal is on; steer right "
                f"for the exit lane and slow to {RAMP_MAX_MPH:.0f}.{pressure_text}",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )
        if (
            0 < ahead <= EXIT_LANE_PREP_MI
            and self._exit_lane_ready()
            and not self._exit_lane_ready_said
        ):
            self._exit_lane_ready_said = True
            self.ctx.audio.play("ui/notify", volume=0.6)
            self.ctx.say("Exit lane set. Hold this lane and keep slowing.")
        if 0 <= ahead <= EXIT_COMMIT_WINDOW_MI and not self._exit_commit_said:
            self._exit_commit_said = True
            self.ctx.say_event(
                f"At the exit gore. Hold the exit lane and stay under {RAMP_MAX_MPH:.0f}.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )

    def _update_exit_speed_assist(self, stop) -> None:
        """Slow an armed exit toward ramp speed, in EVERY steering mode.

        This used to sit below the lane-work early return, so it never ran
        with ``lane_keeping`` on full -- and the All assists preset
        selects full lane keeping, which meant the easiest preset silently
        disabled one of the assists it had just turned on.
        """
        if not self.ctx.settings.exit_speed_assist:
            return
        ahead = stop.at_mi - self.trip.position_mi
        if not 0 < ahead <= 1.5:
            return
        if self._cruise_mph is not None or self._keeper_mph is not None:
            # The assist takes the pedals for the ramp; the session is not its
            # to end. Disarming here was the first of the three places that
            # left both controllers dead for the rest of the run (Shane,
            # 2026-08-15) -- and the keeper has to come off too, or it fights
            # the assist's own brake. A destination exit still holds like any
            # arrival; every other exit is a transit stop.
            self._pause_speed_control(resume_when_rolling=stop.type != "delivery_destination")
        if self.truck.speed_mph <= RAMP_MAX_MPH:
            # Down to ramp speed. HOLD it to the gore rather than handing back
            # an empty pedal: the assist took the throttle to slow the truck,
            # and with automatic speed control paused behind it nothing else
            # is driving. Left alone the truck coasted the rest of the
            # approach down to a dead stop in the through lane, a quarter mile
            # short of its own exit -- worst at real-time pacing, where the
            # coast has the most seconds to finish.
            self._hold_exit_approach_speed()
            return
        self.truck.brake = max(self.truck.brake, 0.35)
        if self._assist_exit_slowing_said:
            return
        self._assist_exit_slowing_said = True
        # Never name a key this driver's settings do not give them: with lane
        # drift off a tap changes lanes, and holding Right does nothing.
        lane_text = (
            "Tap Right to the right lane and keep slowing."
            if self.ctx.settings.lane_is_automated()
            else "Hold Right for the exit lane and keep slowing."
        )
        # Never "confirm": there is no confirm action, and an X pressed to
        # obey it cancels the signal instead.
        self.ctx.say_event(
            f"Exit speed assistance slowing. {lane_text}",
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.CONFIRMATION,
        )

    def _hold_exit_approach_speed(self) -> None:
        """Keep the truck at ramp speed on an approach the assist is running.

        A light, bounded throttle and never a brake. It stands down the moment
        the driver is on a pedal of their own, because slowing further for
        their own gore is their call; the driver can always ask for more than
        this, and the assist's own brake above ramp speed caps the other end.
        Says nothing: the slowing line already named who has the pedal, and
        holding the speed it announced is the same assist finishing its job.
        """
        t = self.truck
        if not t.engine_on or t.stalled or t.air_brakes_holding:
            return
        if t.brake > 0.01 or t.emergency_brake or t.transmission.in_reverse:
            return
        short_by = RAMP_CRUISE_TARGET_MPH - t.speed_mph
        if short_by <= 0.0:
            return  # coasting between the target and the ramp limit is fine
        t.throttle = max(t.throttle, min(EXIT_HOLD_MAX_THROTTLE, short_by / 10.0))

    def _active_exit_pressure(self, stop) -> object | None:
        sample_mi = min(self.trip.position_mi, stop.at_mi)
        pressure = self.trip.traffic_pressure_at(sample_mi)
        if pressure is None or pressure.kind != "exit":
            return None
        if pressure.start_mi <= stop.at_mi <= pressure.end_mi + 0.2:
            return pressure
        return None

    def _exit_window_mi(self) -> float:
        """Arming and announcement window for exits, scaled like zone warnings.

        At speed under time compression a fixed window shrinks to nothing in
        real terms -- at 74 mph on standard pacing, 5 miles is about 14 real
        seconds, and it was half that on the retired Realistic setting: not
        enough to hear the callout, arm the exit, and brake to ramp speed. Scale the window so it covers roughly
        ``EXIT_WARNING_REAL_S`` of real time at the current pace.
        """
        speed = max(self.truck.speed_mph, 30.0)
        miles = EXIT_WARNING_REAL_S * speed * self.trip.effective_time_scale / 3600.0
        return max(EXIT_WINDOW_MI, min(miles, EXIT_WINDOW_MAX_MI))

    def _upcoming_exit_stop(self):
        window = self._exit_window_mi()
        stop = self.trip.upcoming_stop(window)
        destination = self._destination_exit_stop()
        if destination is None:
            return stop
        ahead = destination.at_mi - self.trip.position_mi
        announced_destination_is_actionable = (
            ahead > 0.0
            and self._destination_exit_response_s > 0.0
            and self._destination_exit_key(destination) == self._destination_exit_announced_key
        )
        if announced_destination_is_actionable:
            # X responds to the exit just named, even if an optional stop has
            # since entered the ordinary lookahead window.
            return destination
        if not 0 < ahead <= window:
            return stop
        if stop is None or destination.at_mi <= stop.at_mi:
            return destination
        return stop

    def _destination_exit_stop(self):
        if self.phase != DRIVE_PHASE_DELIVERY or self._destination_exit_taken:
            return None
        if self._departure_chain:
            # Still on the origin's streets: the end of the active trip is
            # the on-ramp merge, not the delivery exit.
            return None
        details = self._destination_exit_details()
        if details is None:
            at_mi = max(0.0, self.trip.total_miles - DESTINATION_EXIT_BEFORE_END_MI)
            exit_label = ""
            exit_phrase = ""
        else:
            at_mi, exit_label, exit_phrase = details
        if at_mi <= self.trip.position_mi + 0.05:
            return None
        stop = RoadStop(
            self._destination_facility_text(),
            at_mi,
            "delivery_destination",
            ("deliver",),
            exit_label=exit_label,
        )
        stop.exit_phrase = exit_phrase
        return stop

    def _destination_exit_label(self) -> str:
        details = self._destination_exit_details()
        return "" if details is None else details[1]

    def _destination_exit_key(self, stop) -> str:
        return f"{stop.at_mi:.3f}:{stop.exit_label}:{stop.name}"

    def _destination_exit_phrase(self, stop) -> str:
        phrase = getattr(stop, "exit_phrase", "")
        if phrase:
            return phrase
        if stop.exit_label:
            return f"{stop.exit_label} for {stop.name}"
        return f"the exit for {stop.name}"

    def _missed_exit_phrase(self, stop) -> str:
        if stop.type == "delivery_destination":
            # The exit phrase already carries its own label; naming both
            # would speak the same exit twice in one sentence.
            return self._destination_exit_phrase(stop)
        if stop.exit_label:
            return f"{stop.exit_label} for {stop.spoken_name}"
        return f"the exit for {stop.spoken_name}"

    def _destination_exit_announcement(self, stop, ahead: float) -> str:
        labeled = getattr(stop, "exit_phrase", "") or stop.exit_label
        # Quarter-mile steps once inside a mile: the whole-mile form rounds a
        # third of a mile to nothing, so the last call before the gore was "In
        # 0 miles, the destination exit" -- which reads as already-missed while
        # there is still road to use it (owner playtest, 2026-08-15). Whole
        # miles still answer from a mile out, because "In 5.0 miles" is worse
        # than "In 5 miles" for the calls that come early.
        distance = (
            self.ctx.settings.short_distance_text(ahead)
            if ahead < 1.0
            else self.ctx.settings.distance_text(ahead)
        )
        core = (
            f"In {distance}, {labeled}, destination exit."
            if labeled
            else f"In {distance}, the destination exit for {stop.name}."
        )
        if not self.ctx.settings.lane_is_automated():
            if self._terse_speech():
                return core
            return f"{core} Move right for the exit lane and slow down."
        # Lane keeping takes this exit with no signal and no lane work, so
        # the one thing the driver must not have to infer is that it is
        # happening at all. Said once per run, and terse keeps it: a
        # consequence is exactly what terse verbosity holds on to.
        if self._lane_keeping_takes_exit_said:
            return core if self._terse_speech() else f"{core} Slow down for the ramp."
        self._lane_keeping_takes_exit_said = True
        if self._terse_speech():
            return f"{core} Lane keeping will take this exit."
        return f"{core} Lane keeping will take this exit. Slow down for the ramp."

    def _check_destination_exit(self) -> None:
        stop = self._destination_exit_stop()
        if stop is None:
            return
        ahead = stop.at_mi - self.trip.position_mi
        if not (0 < ahead <= self._exit_window_mi()):
            return
        key = self._destination_exit_key(stop)
        if key != self._destination_exit_announced_key:
            self._destination_exit_announced_key = key
            # The exact exit stays answerable for a human reaction window even
            # if coasting or automatic braking shrinks the dynamic one.
            self._destination_exit_response_s = DESTINATION_EXIT_RESPONSE_GRACE_S
            # Cruise stays engaged down the ramp approach, capped at the ramp
            # target, rather than handing the pedal back cold.
            message = self._destination_exit_announcement(stop, ahead) + self._cap_cruise_for_ramp()
            self.ctx.audio.play("ui/notify", volume=0.7)
            # ROUTE: this line carries "lane keeping will take this exit",
            # which is the only warning the driver gets that the truck is
            # about to leave the highway without them touching anything. Left
            # at the AMBIENT default it was dropped whenever another line
            # landed in the same moment, and the exit read as taking itself --
            # reported twice now (Sarah A, 2026-08-15; and the report the
            # attribution was written for in the first place).
            self.ctx.say_event(
                message,
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )
        if self._exit_stop is None:
            self._exit_stop = stop
            self._exit_signal_canceled = False
            self._reset_exit_lane_state()
            if self.ctx.settings.lane_is_automated():
                self._exit_lane_alignment = EXIT_LANE_READY
                self._exit_lane_ready_said = True

    def _destination_exit_details(
        self, *, include_past: bool = False
    ) -> tuple[float, str, str] | None:
        if include_past:
            return self._scan_destination_exit_details(include_past=True)
        # This runs every frame from _check_destination_exit, and the scan
        # walks every interchange on the route building spoken phrases -- far
        # too much churn to redo per tick on a coast-to-coast route. The
        # winning exit only changes when the truck passes it, so reuse the
        # last answer until then. A backward position move (missed-exit
        # rewind, rescue) invalidates the cache wholesale, because exits
        # behind the compute position come back into play.
        pos = self.trip.position_mi
        cache = self._destination_exit_cache
        if cache is None or pos < cache[0] or (cache[1] is not None and cache[1][0] <= pos + 0.05):
            cache = (pos, self._scan_destination_exit_details())
            self._destination_exit_cache = cache
        return cache[1]

    def _scan_destination_exit_details(
        self, *, include_past: bool = False
    ) -> tuple[float, str, str] | None:
        if not self.route.legs:
            return None
        # Matched against real interchange sign text, so compare the spoken
        # city name ("Nashville"), never the slug key.
        destination = self.ctx.world.spoken_city(self.route.cities[-1], qualified=False).casefold()
        scan_floor = self.trip.total_miles - DESTINATION_EXIT_SCAN_WINDOW_MI
        candidates = []
        for i in range(len(self.route.legs) - 1, -1, -1):
            leg = self.route.legs[i]
            if self.trip._leg_starts[i] + leg.miles < scan_floor:
                # This leg ends before the final approach; every earlier leg
                # is farther out still.
                break
            forward = self.route.cities[i] == leg.a
            target = leg.miles if forward else 0.0
            for ix in leg.interchanges:
                if not ix.exit_label:
                    continue
                offset = ix.at_mi if forward else leg.miles - ix.at_mi
                route_mile = self.trip._leg_starts[i] + offset
                if route_mile < scan_floor:
                    continue
                if not include_past and route_mile <= self.trip.position_mi + 0.05:
                    continue
                dist_from_destination = abs(ix.at_mi - target)
                matches_destination = any(
                    destination in part.casefold() for part in ix.destinations
                )
                candidates.append(
                    (
                        len(self.route.legs) - 1 - i,
                        dist_from_destination,
                        not matches_destination,
                        route_mile,
                        ix.exit_label,
                        ix.spoken_phrase,
                    )
                )
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][3], candidates[0][4], candidates[0][5]

    def _exit_intent_ready(self, stop) -> bool:
        if self._exit_signal_canceled:
            return False
        if self._exit_signal_on:
            return True
        return stop.type == "delivery_destination" and self.ctx.settings.lane_is_automated()

    def _city_state(self, city: str) -> str:
        """The spoken state name for a city key, or "" when the world is silent.

        A street chain's legs carry no state segments -- they are built from
        local geometry, not from the corridor bake -- so the trip cannot work
        out for itself whose vehicle code governs its streets. The city can.
        """
        try:
            return self.ctx.world.city(city).state
        except (AttributeError, KeyError, ValueError):
            return ""

    def _surface_chain_route(self):
        """The destination facility's tier-1 street chain, or None.

        Only a genuine multi-segment turn-level route makes a chain; a
        single synthetic leg would just be the old teleport with extra
        steps, so those facilities keep the scripted arrival."""
        try:
            route = self.ctx.world.facility_approach_route(
                self.job.destination, self.job.destination_location
            )
        except (KeyError, ValueError):
            return None
        if route is None or len(route.legs) < 2:
            return None
        if not any(leg.local_speed_mph > 0 for leg in route.legs):
            return None
        return route

    def _begin_surface_chain(self, *, announce: bool = True) -> bool:
        """Swap the finished highway trip for the facility's street chain.

        The clock, the day of the week, and the toll ledger carry over, so
        deadlines, rush hour, and settlement are unaffected: only the road
        under the wheels changes."""
        if self._surface_chain:
            return False  # already on the streets
        route = self._surface_chain_route()
        if route is None:
            return False
        old = self.trip
        surface = Trip(
            route,
            self.truck,
            self.weather,
            time_scale=old.time_scale,
            seed=self.trip_seed ^ 0x5AFE,
            start_hour=old.start_hour,
            imperial=old.imperial,
            hazard_scale=0.0,  # no random hazards on the last city miles
            career_hours=old.career_hours,
            bobtail=old.bobtail,
            destination_label=old.destination_label,
            local_state=self._city_state(self.job.destination),
        )
        surface.game_minutes = old.game_minutes  # deadline and clock continuity
        surface.toll_charges = old.toll_charges  # settlement reads the live trip
        surface.hos_violation = old.hos_violation
        self._highway_trip = old
        self.trip = surface
        self._surface_chain = True
        self._reset_exit_lane_state()
        self._exit_signal_on = False
        if announce:
            first = route.legs[0]
            street = first.local_cue.rstrip(".") if first.local_cue else f"Start on {first.highway}"
            self.ctx.audio.play("ui/notify", volume=0.7)
            self.ctx.say_event(
                f"Off the ramp and onto city streets: {street[:1].lower()}{street[1:]}. "
                f"{self.trip._distance_text(route.miles)} to the facility gate.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )
        return True

    def _departure_chain_route(self):
        """The origin facility's street chain driven outbound, or None.

        Same bar as the arrival side: only a genuine multi-segment
        turn-level chain qualifies; other facilities keep the scripted
        departure straight onto the highway."""
        if self.phase != DRIVE_PHASE_DELIVERY:
            return None
        try:
            return self.ctx.world.facility_departure_route(
                self.job.origin, self.job.origin_location
            )
        except (AttributeError, KeyError, ValueError):
            return None

    def _begin_departure_chain(self, *, announce: bool = True) -> bool:
        """Start the loaded run on the origin facility's street chain.

        The full highway trip built at dispatch is parked aside; the truck
        pulls out of the gate onto real streets and the on-ramp merge hands
        the highway trip back with the clock and toll ledger intact."""
        if self._departure_chain or self._surface_chain:
            return False
        route = self._departure_chain_route()
        if route is None:
            return False
        highway = self.trip
        surface = Trip(
            route,
            self.truck,
            self.weather,
            time_scale=highway.time_scale,
            seed=self.trip_seed ^ 0xD00D,
            start_hour=highway.start_hour,
            imperial=highway.imperial,
            hazard_scale=0.0,  # no random hazards on the first city miles
            career_hours=highway.career_hours,
            bobtail=highway.bobtail,
            local_state=self._city_state(self.job.origin),
            # Driven outbound: the gate is the first thing behind you,
            # and this chain ends at the on-ramp.
            outbound=True,
        )
        self._highway_trip = highway
        self.trip = surface
        self._departure_chain = True
        # Pulling out of the gate ENDS the stop that paused automatic speed
        # control. An arrival pause is deliberately never lifted by the resume
        # path -- only a departure clears one -- and nothing was clearing this
        # one, so the pause a driver earned by arriving to load survived being
        # loaded and followed them onto the road: armed, paused, and refusing
        # to engage for the rest of the run (Brandon, 2026-08-21). This is the
        # departure that clears it.
        self._clear_stop_pause()
        if announce:
            first = route.legs[0]
            street = first.local_cue.rstrip(".") if first.local_cue else f"Start on {first.highway}"
            merge_leg = highway.route.legs[0]
            self.ctx.say_event(
                f"Out of the gate and onto city streets: "
                f"{street[:1].lower()}{street[1:]}. "
                f"{surface._distance_text(route.miles)} to the "
                f"{merge_leg.highway} on-ramp.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )
        return True

    def _finish_departure_chain(self) -> None:
        """End of the streets: up the on-ramp and onto the highway trip."""
        surface = self.trip
        highway = self._highway_trip
        highway.game_minutes = surface.game_minutes  # clock continuity
        highway.toll_charges = surface.toll_charges  # settlement reads the live trip
        highway.hos_violation = surface.hos_violation
        self.trip = highway
        self._highway_trip = None
        self._departure_chain = False
        # Coming up the ramp you are in the right lane, merging left.
        self.lane.lane = 0
        self.lane.offset = 0.0
        merge_leg = highway.route.legs[0]
        # The acceleration lane is a real stretch of road with a real length,
        # not a moment. Handing straight to the highway meant arriving at the
        # taper doing whatever the last corner left you at -- about 17 mph in
        # a measured run, which is the "came to a stop" a tester reported
        # (Brandon, 2026-08-21). Now the lane exists, sized from the highway
        # it feeds, and the truck has room to build speed on it.
        highway_mph, _ = highway.speed_limit_at(0.0)
        self._departure_ramp_mi = acceleration_lane_mi(highway_mph, highway.grade_at(0.0))
        lane_text = spoken_feet_or_meters(
            self._departure_ramp_mi, imperial=self.ctx.settings.imperial_units
        )
        # Hand the lane to the KEEPER explicitly, here, rather than leaving it
        # to the resume path to work out. The swap happens late in the frame,
        # so for one tick the new road looks like open highway with no zone on
        # it -- and the keeper duly handed off to cruise, which cannot hold
        # below its own minimum speed. The result was cruise nominally engaged
        # and nothing at all touching the throttle: the truck coasted the
        # entire acceleration lane at zero throttle (measured out of Aberdeen,
        # 2026-08-21). The keeper is the automation for this stretch and it
        # takes it directly.
        if self.ctx.settings.speed_keeper and self._speed_control_armed:
            if self._cruise_mph is not None:
                self._cancel_cruise(preserve_session=True)
            self._engage_keeper(
                highway_mph,
                "acceleration lane",
                target_mph=highway_mph,
                announce=False,
            )
        self.ctx.audio.play("vehicle/signal_tone", volume=0.6, pan=-0.6)
        self.ctx.say_event(
            f"Up the ramp onto {merge_leg.highway}. {lane_text} of acceleration "
            "lane; build your speed and look for a gap.",
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.NAVIGATION,
        )

    def _update_departure_ramp(self, moved_mi: float) -> None:
        """Run down the acceleration lane after pulling out of a facility.

        The lane is the one place a loaded truck is SUPPOSED to be slower than
        the road it is joining. The Green Book sizes these lanes for a
        passenger car -- 75 percent of highway speed is its own design target
        -- so a rig that reaches the taper under the limit has not failed at
        anything, and the game must not pretend otherwise. What a real driver
        does about it is take a bigger gap, which is what the closing line
        says.
        """
        if self._departure_ramp_mi is None:
            return
        self._departure_ramp_mi -= max(0.0, moved_mi)
        if self._departure_ramp_mi > 0.0:
            return
        self._departure_ramp_mi = None
        limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
        speed = self.truck.speed_mph
        short_by = limit - speed
        # Under the limit by enough to matter is the NORMAL outcome for a
        # loaded truck, so it is said as a fact about the gap you need, never
        # as a fault. Only a truck that is genuinely up to speed gets the
        # plain merge line.
        if short_by >= MERGE_UNDER_SPEED_MPH:
            message = (
                f"Lane ending at {self.ctx.settings.speed_text(speed)}. "
                f"You are under the {self.ctx.settings.speed_text(limit)} traffic is "
                "running, so take a big gap and keep building speed once you are in."
            )
        else:
            message = "Lane ending. Merge left when clear."
        self.ctx.audio.play("vehicle/signal_tone", volume=0.6, pan=-0.6)
        self.ctx.say_event(
            message,
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.NAVIGATION,
        )

    def _ramp_control_for(self, stop, rng=None) -> str:
        """The control at this stop's ramp end, decidable any time.

        Baked OSM data (a traffic_signals or stop node on the exit's ramp
        links) wins; otherwise a seeded urban/rural heuristic stands in --
        most urban diamond terminals are signalized, rural ones lean to stop
        signs, and a share flow free like a cloverleaf loop. Pure function
        of the trip seed, the stop, and baked data, so the signal-on
        announcement a mile out and the ramp itself always agree."""
        if getattr(stop, "type", "") == "weigh_station":
            # A scale has its own deceleration ramp flowing straight into
            # the inspection lane -- no public crossroad, no light, no stop
            # sign. The scale bar itself is the terminal, and the arrival
            # stop machinery already owns it ("At the scale. Stop now").
            # The dice used to put a stop sign here, spoken with the
            # MAINLINE's limit on its far side (owner playtest, 2026-08-20,
            # "Stop sign at ramp end. Limit 70").
            return "none"
        control = self.trip.ramp_control_at(stop.at_mi)
        if not control and self._ramp_meets_a_freeway(stop):
            # A system interchange: this ramp ends in a merge onto another
            # freeway, and nothing stops traffic there. Decided before the
            # dice rather than by them -- see FREEWAY_VIA_RE.
            control = "none"
        if not control:
            if rng is None:
                rng = random.Random((self.trip_seed << 16) ^ int(stop.at_mi * 100.0))
            signal_w, stop_w = (
                RAMP_CONTROL_URBAN_WEIGHTS
                if self.trip._near_city(stop.at_mi)
                else RAMP_CONTROL_RURAL_WEIGHTS
            )
            roll = rng.random()
            control = "signal" if roll < signal_w else "stop" if roll < stop_w else "none"
        return control

    def _ramp_meets_a_freeway(self, stop) -> bool:
        """Whether this exit's ramp lands on another freeway.

        The baked ``ramp_far_end`` answers first: it is walked link topology,
        a fact about the road the ramp reaches. ``surface`` in particular
        SUPPRESSES the ``via`` guess below -- via is signage (where the exit
        points), not the road the ramp lands on, and measured against walked
        topology the signage guess called a controlled surface terminal
        "free flow" on about a third of the exits it fired on.

        The via fallback survives for exits the walk could not judge: 4,999
        of the world's 18,011 exits lead to an interstate and every one of
        them used to take its chances with the urban/rural weights below,
        which handed stop signs to roughly half the rural ones -- a stop
        sign where an interstate meets an interstate does not exist (owner,
        2026-08-17).
        """
        interchange = self.trip.interchange_at(stop.at_mi)
        if interchange is None:
            return False
        if interchange.ramp_far_end == "motorway":
            return True
        if interchange.ramp_far_end == "surface":
            return False
        return bool(FREEWAY_VIA_RE.search((interchange.via or "").upper()))

    def _begin_ramp_terminal(self, stop) -> None:
        """Set up the terminal control state for the ramp just taken."""
        rng = random.Random((self.trip_seed << 16) ^ int(stop.at_mi * 100.0))
        self._ramp_control = self._ramp_control_for(stop, rng)
        self._ramp_light_timer = 0.0
        self._ramp_light_offset_s = rng.random() * (
            RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S + RAMP_LIGHT_YELLOW_S
        )
        self._ramp_light_announced = False
        self._ramp_light_last_phase = ""
        self._ramp_terminal_done = self._ramp_control == "none"
        self._ramp_waiting_at_light = False
        self._ramp_creep_prompt_said = False
        self._ramp_gap_milestones_said: set[int] = set()
        self._ramp_bar_tick_timer = 0.0
        self._ramp_assist_said = False
        self._ramp_assist_brake = 0.0
        self._ramp_waiting_at_sign = False
        # The cross bubble: a controlled terminal means a real crossroad, so
        # simulate it. Seeded like the control itself so the same terminal
        # always carries the same traffic day; the near-city split reuses the
        # same urban/rural judgment the control dice already trust.
        self._cross_bubble = (
            CrossTraffic(
                seed=(self.trip_seed << 16) ^ int(stop.at_mi * 100.0) ^ 0x5AFE,
                # A roundabout entry is gap acceptance against circulating
                # traffic: yield rates, spoken as a roundabout.
                control="yield" if self._ramp_control == "roundabout" else self._ramp_control,
                near_city=self.trip._near_city(stop.at_mi),
            )
            if self._ramp_control in ("signal", "stop", "yield", "roundabout")
            else None
        )

    def _ramp_light_phase(self) -> str:
        cycle = RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S + RAMP_LIGHT_YELLOW_S
        into = (self._ramp_light_offset_s + self._ramp_light_timer) % cycle
        if into < RAMP_LIGHT_RED_S:
            return "red"
        if into < RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S:
            return "green"
        return "yellow"

    def _ramp_light_is_red(self) -> bool:
        # Only true red punishes a crossing: entering on yellow is legal,
        # exactly like the real law.
        return self._ramp_light_phase() == "red"

    def _update_ramp_light(self, dt: float) -> None:
        """Advance the terminal light in real time and speak state changes."""
        # The bar's cues run first and unconditionally. They are the only code
        # that stops the solid tone, and every early return below used to skip
        # them: a driver who reached the tone and then crossed the bar --
        # green, red, or stop sign -- carried it through the rest of the run
        # and out into the menus (Shane, 2026-08-03).
        self._update_ramp_bar_ticks(dt)
        self._update_cross_bubble(dt)
        if self._ramp_mi is None or self._ramp_terminal_done:
            return
        if self._ramp_control in ("stop", "yield", "roundabout"):
            # A sign has no phases, but its bar needs a position just
            # as much as a light's: without the countdown, the ticks, and
            # the stopped-short guidance, the sign was one announce line
            # and then silence until the damage message (playtest
            # 2026-07-22, Milwaukee grain elevator, 15 percent).
            self._update_ramp_queue_guidance()
            self._update_ramp_gap_countdown()
            return
        if self._ramp_control != "signal":
            return
        self._ramp_light_timer += dt
        self._update_ramp_queue_guidance()
        self._update_ramp_gap_countdown()
        phase = self._ramp_light_phase()
        if not self._ramp_light_announced or phase == self._ramp_light_last_phase:
            return
        self._ramp_light_last_phase = phase
        if self._ramp_waiting_at_light and phase == "green":
            # The wait at the stop bar ends; the driveway is just ahead.
            self._ramp_waiting_at_light = False
            self._ramp_terminal_done = True
            self.ctx.audio.play("events/ramp_light_green", volume=0.8)
            self.ctx.say_event(
                "Green light. Pull ahead to the entrance.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )
            return
        # Every phase change speaks. The light is an instruction, not
        # ambiance: a silent flip back to red between the spoken green and
        # the stop bar cost real playtesters real trailer damage. The wording
        # is distance-aware: a screen shows where the stop bar is, so speech
        # has to say whether the driver has reached it.
        #
        # ROUTE, for the same reason the comment above gives. Left at the
        # AMBIENT default, this whole family waited the full stale budget
        # behind whatever was speaking, and on a real ramp the pacer dropped
        # the assist's own "braking for the light" sixteen milliseconds after
        # the yellow call, then "through on the yellow" behind it -- so the
        # truck braked for the light and the driver was told none of it
        # (owner playtest, 2026-08-15).
        short = self._ramp_mi > RAMP_ACCESS_MI
        if phase == "red":
            self.ctx.audio.play("events/ramp_light_red", volume=0.7)
            self.ctx.say_event(
                "The light ahead turns red. Be ready to stop.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )
        elif phase == "yellow":
            self.ctx.audio.play("ui/notify", volume=0.7)
            message = (
                "The light ahead turns yellow. You are short of it: stop, "
                "then creep up to the bar on the red."
                if short
                else "The light turns yellow at the bar. Continuing through is legal."
            )
            self.ctx.say_event(
                message,
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )
        else:
            self.ctx.audio.play("events/ramp_light_green", volume=0.7)
            message = (
                "The light ahead turns green. Roll toward it; if it changes "
                "before you are there, stop and creep up on the red."
                if short
                else "The light ahead turns green."
            )
            self.ctx.say_event(
                message,
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )

    def _ramp_bar_milestones(self) -> tuple[int, ...]:
        """Which distances to the stop bar are worth SAYING on this rung.

        The bar already has a non-spoken instrument: inside
        ``RAMP_BAR_TICK_RANGE_MI`` a centre tick speeds up as the bar closes,
        and fuses to a solid tone at the end. Rate carries distance, silence
        means stopped. So a spoken milestone inside that range is speech
        restating what the driver is already listening to -- four calls on
        every ramp terminal, of which the last two were audible twice.

        Standard keeps the calls the tick cannot make, the ones out beyond its
        range. Quiet keeps one: the rung means less automatic speech, the
        terminal callout has already named the light or the sign, and the tick
        does the rest of the work (owner, 2026-08-21).
        """
        imperial = self.ctx.settings.imperial_units
        thresholds = RAMP_GAP_MILESTONES_FT if imperial else RAMP_GAP_MILESTONES_M
        unit_mi = 1.0 / 5280.0 if imperial else 1.0 / 1609.344
        outside_tick = tuple(
            threshold for threshold in thresholds if threshold * unit_mi > RAMP_BAR_TICK_RANGE_MI
        )
        # Never silent: a unit system whose milestones all sit inside the tick
        # range still gets its farthest call, so the bar is never announced by
        # sound alone to a driver who has the tick turned down.
        if not outside_tick:
            outside_tick = thresholds[:1]
        if self._terse_speech():
            return outside_tick[:1]
        # Two is the owner's number (2026-08-21), and it makes both unit
        # systems behave alike: the tick rule alone left metric with a third
        # call at 100 metres that imperial had no equivalent for.
        return outside_tick[:2]

    def _update_cross_bubble(self, dt: float) -> None:
        """Run the crossroad's own traffic while the terminal is live.

        Real seconds, like the light: the terminal already stops the clock
        compressing, and a gap that shrank at 4x would be unreadable. Each
        vehicle fires its crossing cue half a cue-length before it reaches
        the conflict point, panned to the ear it comes from, so the peak of
        the doppler lands on the actual crossing -- the gap IS the audio.
        """
        bubble = getattr(self, "_cross_bubble", None)
        if bubble is None:
            return
        if self._ramp_mi is None or self._ramp_terminal_done:
            # The terminal released the driver; the crossroad is behind them.
            self._cross_bubble = None
            return
        if self._ramp_control == "signal":
            # The cross street runs the orthogonal phase. Yellow counts as
            # ours: real cross traffic is already stopped by then.
            bubble.player_has_green = self._ramp_light_phase() != "red"
        bubble.update(dt)
        # The crossroad fades in down the ramp: nothing until the terminal
        # callout distance, full presence at the bar.
        closeness = 1.0 - min(1.0, max(0.0, self._ramp_mi) / RAMP_CONTROL_ANNOUNCE_MI)
        if closeness <= 0.05:
            return
        for vehicle in bubble.vehicles:
            if vehicle.sound_started or vehicle.position_mi >= 0.0 or vehicle.speed_mph <= 1.0:
                continue
            eta = -vehicle.position_mi * 3600.0 / vehicle.speed_mph
            if eta > CROSS_SOUND_LEAD_S.get(vehicle.vehicle_class, 1.2):
                continue
            vehicle.sound_started = True
            key = "traffic/" + vehicle.vehicle_class.replace(" ", "_") + "_cross"
            self.ctx.audio.play(
                key,
                volume=0.25 + 0.6 * closeness,
                pan=-0.7 if vehicle.from_side == "left" else 0.7,
            )

    def _cross_violation_meets(self):
        """(what a terminal violation met, the vehicle it met).

        "hit" is a vehicle inside the conflict window, "near" is one arriving
        within a horn's length, "empty" is the gamble that happened to pay.
        With no bubble to consult (older saves mid-ramp), the old certainty
        stands: the violation hits.
        """
        bubble = getattr(self, "_cross_bubble", None)
        if bubble is None:
            return "hit", None
        vehicle = bubble.occupant()
        if vehicle is not None:
            return "hit", vehicle
        vehicle = bubble.approaching(2.0)
        if vehicle is not None:
            return "near", vehicle
        return "empty", None

    def _cross_vehicle_sound(self, vehicle) -> str:
        """The crossing cue for the vehicle a violation met."""
        if vehicle is None:
            return "traffic/car_cross"
        return "traffic/" + vehicle.vehicle_class.replace(" ", "_") + "_cross"

    def _update_ramp_queue_guidance(self) -> None:
        """Tell a driver stopped short of the stop bar to close the gap.

        A cautious stop on the first "brake to a stop" callout can land a
        quarter mile short of the bar, where one green is never enough road
        from a standstill. Without this prompt that plays as a light stuck
        in an endless loop (playtest transcript, 2026-07-16)."""
        if not self._ramp_light_announced or self._ramp_waiting_at_light:
            return
        if self._ramp_mi is None or self._ramp_mi <= RAMP_ACCESS_MI:
            return
        if self.truck.speed_mph > RED_STOP_MPH:
            self._ramp_creep_prompt_said = False
            return
        if self._ramp_creep_prompt_said:
            return
        self._ramp_creep_prompt_said = True
        # Name the gap: "creep" for a real 600-foot gap takes minutes and
        # reads as a light stuck in a loop. Far back is a drive, and the red
        # phase is exactly the time to make it.
        gap_mi = self._ramp_mi - RAMP_ACCESS_MI
        if self._ramp_control in ("stop", "yield", "roundabout"):
            noun = {
                "stop": "the stop sign",
                "yield": "the yield line",
                "roundabout": "the roundabout entry",
            }[self._ramp_control]
            # A stop sign demands the stop at the bar; a yield only asks for
            # the gap there.
            tail = (
                "stop again at the bar"
                if self._ramp_control == "stop"
                else "take your gap at the bar"
            )
            if gap_mi > RAMP_CREEP_MI:
                gap = self._short_distance_text(gap_mi)
                message = f"You are stopped about {gap} short of {noun}. Drive up and {tail}."
            else:
                message = f"You are stopped short of {noun}. Creep ahead and {tail}."
            # ROUTE, not the ambient default. This is an instruction about a
            # STANDING condition -- the truck is stopped short of the bar and
            # stays stopped until the driver acts -- so the staleness rule that
            # drops a line "starting after the moment it described" is reading
            # a moment that has not passed. It dropped exactly this line in the
            # owner playtest of 2026-08-17, leaving the truck 1,350 feet short
            # through a whole green-yellow-red cycle with nothing said; the same
            # failure the comment below already records from 2026-07-19. ROUTE
            # waits its turn behind anything urgent, and is never dropped.
            self.ctx.say_event(
                message,
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )
            return
        on_green = self._ramp_light_phase() == "green"
        if gap_mi > RAMP_CREEP_MI:
            gap = self._short_distance_text(gap_mi)
            if on_green:
                message = (
                    f"You are stopped about {gap} short of the light, and it "
                    "is green. Drive up now; stop at the bar if it changes."
                )
            else:
                message = (
                    f"You are stopped about {gap} short of the light. Drive "
                    "up and stop at the bar; the red is the time to close the gap."
                )
        elif on_green:
            message = "You are stopped short of the light and it is green. Roll ahead now."
        else:
            message = (
                "You are stopped short of the light. Creep ahead and hold "
                "at the stop bar for green."
            )
        # ROUTE, not the ambient default. This is an instruction about a
        # STANDING condition -- the truck is stopped short of the bar and
        # stays stopped until the driver acts -- so the staleness rule that
        # drops a line "starting after the moment it described" is reading
        # a moment that has not passed. It dropped exactly this line in the
        # owner playtest of 2026-08-17, leaving the truck 1,350 feet short
        # through a whole green-yellow-red cycle with nothing said; the same
        # failure the comment below already records from 2026-07-19. ROUTE
        # waits its turn behind anything urgent, and is never dropped.
        self.ctx.say_event(
            message,
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.NAVIGATION,
        )

    def _update_ramp_gap_countdown(self) -> None:
        """Count the stop bar down while the truck is rolling toward it.

        The stopped-driver prompt above names the gap only at a standstill,
        so a rolling driver had no idea where the bar was: the owner crept
        1300 feet in stop-and-listen hops across three light cycles
        (playtest log, 2026-07-19). Rolling milestone calls give the bar a
        position the same way the exit countdown gives the exit one."""
        if not self._ramp_light_announced or self._ramp_waiting_at_light:
            return
        if self._ramp_mi is None or self._ramp_mi <= RAMP_ACCESS_MI:
            return
        if self.truck.speed_mph <= RED_STOP_MPH:
            return
        gap_mi = self._ramp_mi - RAMP_ACCESS_MI
        thresholds = self._ramp_bar_milestones()
        unit_mi = 1.0 / 5280.0 if self.ctx.settings.imperial_units else 1.0 / 1609.344
        unit_word = "feet" if self.ctx.settings.imperial_units else "meters"
        for threshold in thresholds:
            if gap_mi <= threshold * unit_mi and threshold not in self._ramp_gap_milestones_said:
                self._ramp_gap_milestones_said.add(threshold)
                if self._terse_speech():
                    # The distance, and nothing else. Quiet gets ONE call for
                    # the whole approach, and by the time it lands the driver
                    # has already been told this is a bar and what the limit
                    # is -- so repeating either of those is the wordiness the
                    # rung exists to remove (owner, 2026-08-21, replacing the
                    # compact-line spec of 2026-07-23 for this line only).
                    self.ctx.say_event(
                        f"{threshold} {unit_word}.",
                        interrupt=False,
                        priority=EventPriority.ROUTE,
                        category=SpeechCategory.NAVIGATION,
                    )
                    return
                self.ctx.say_event(
                    f"{threshold} {unit_word} to the bar.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.NAVIGATION,
                )
                return

    def _set_bar_solid(self, on: bool) -> None:
        """The continuous tone of the bar's final zone.

        Held, not started: the tone is re-asserted on every tick it applies
        to and lapses on its own as soon as it is not, so it cannot survive
        this state losing the frame to a menu or an arrival screen. Turning
        it back off here is still instant."""
        if on:
            # 0.85 read as jarring against everything else on the road
            # (Darren, 2026-08-15): a continuous tone at nearly full scale
            # sits far louder than the intermittent cues around it, and this
            # one plays while the driver is concentrating on stopping. The
            # tone still has to be unmistakable, so it stays the loudest
            # continuous cue -- just no longer the loudest thing in the cab.
            self.ctx.audio.hold_alert("vehicle/bar_solid", volume=BAR_SOLID_VOLUME)
        elif self._bar_solid_on:
            self.ctx.audio.release_alert()
        self._bar_solid_on = on

    def _update_ramp_bar_ticks(self, dt: float) -> None:
        """Parking-sensor tick for the stop bar's last few hundred feet.

        Rate carries the distance -- faster is closer -- and silence means
        stopped, so the cue never nags a driver holding at the bar. Center
        pan, unlike the side-panned curve cues, so the two never read as
        the same instrument (owner ask, 2026-07-19). Inside the last
        stretch of leeway, still moving, the ticks fuse into a continuous
        tone (owner spec, written into the manual 2026-07-27): at the
        solid tone you had better be close to stopped."""
        if not self._ramp_light_announced or self._ramp_waiting_at_light:
            self._set_bar_solid(False)
            return
        if self._ramp_mi is None or self._ramp_terminal_done:
            self._set_bar_solid(False)
            return
        if self.truck.speed_mph <= RED_STOP_MPH:
            self._set_bar_solid(False)
            return
        gap_mi = self._ramp_mi - RAMP_ACCESS_MI
        # Both distances come from what this truck can actually stop in, with
        # the old constants as their floors: a load that stops longer -- hot
        # brakes, ice, a downgrade, liquid running forward in a tank -- hears
        # the bar earlier, because it needs the road earlier.
        tick_range_mi = bar_tick_range_mi(self.truck)
        solid_mi = bar_solid_zone_mi(self.truck)
        if gap_mi > tick_range_mi or gap_mi < 0:
            self._set_bar_solid(False)
            return
        if gap_mi <= solid_mi:
            self._set_bar_solid(True)
            return
        self._set_bar_solid(False)
        closeness = 1.0 - gap_mi / tick_range_mi
        period = RAMP_BAR_TICK_SLOW_S - closeness * (RAMP_BAR_TICK_SLOW_S - RAMP_BAR_TICK_FAST_S)
        self._ramp_bar_tick_timer += dt
        if self._ramp_bar_tick_timer >= period:
            self._ramp_bar_tick_timer = 0.0
            # Full volume: at 0.5 the owner judged it missable by someone
            # not listening for it (2026-07-19). The dedicated beep the old
            # note asked for arrived with the curve bink (2026-07-27).
            self.ctx.audio.play("vehicle/curve_bink", volume=0.9)

    def _ramp_light_query_text(self) -> str | None:
        """Light phase and bar distance on demand, for the info keys.

        "Stop at the bar" is only an instruction if the bar has a position;
        a sighted driver reads it off the windshield, so speech must answer
        the same question whenever the driver asks (owner ask, 2026-07-19)."""
        if (
            self._ramp_mi is None
            or self._ramp_control not in ("signal", "stop")
            or self._ramp_terminal_done
        ):
            return None
        gap_mi = self._ramp_mi - RAMP_ACCESS_MI
        if self._ramp_control == "stop":
            if gap_mi <= 0:
                return "At the stop bar. Stop sign; brake to a full stop."
            limit_text = self._approach_limit_text()
            limit_clause = f", speed limit {limit_text}" if limit_text else ""
            return (
                f"Stop sign, about {self._short_distance_text(gap_mi)} to the "
                f"stop bar{limit_clause}."
            )
        phase = self._ramp_light_phase()
        if gap_mi <= 0:
            return f"At the stop bar. The light is {phase}."
        limit_text = self._approach_limit_text()
        limit_clause = f", speed limit {limit_text}" if limit_text else ""
        return (
            f"Light {phase}, about {self._short_distance_text(gap_mi)} to the "
            f"stop bar{limit_clause}."
        )

    def _short_distance_text(self, miles: float) -> str:
        """A short gap in round spoken units: feet or meters, never decimals."""
        return spoken_feet_or_meters(miles, self.ctx.settings.imperial_units)

    def _approach_limit_text(self) -> str:
        """The enforced limit AT THE STOP BAR, spoken.

        The terminal callouts named the control but never the limit the
        approach is driven at (owner report 2026-07-23). First cut read
        the limit at the truck's position -- which mid-ramp still said 55,
        the highway's number, useless for a light a quarter mile ahead
        (owner's log, same night). The honest number is the zone at the
        bar itself: the street being entered.
        """
        bar_mi = self.trip.position_mi
        if self._ramp_mi is not None:
            bar_mi += max(0.0, self._ramp_mi - RAMP_ACCESS_MI)
        # Probe just PAST the bar, not at it: the entered road's zone (the
        # facility access 25, the street's 35) begins on the far side, so a
        # probe at the bar itself still read the corridor's 55 -- the owner
        # was told "speed limit 55 on the approach" at a stop sign whose far
        # side was a 25 access road (log, 2026-07-23, Merced).
        bar_mi += 0.05
        bar_mi = min(bar_mi, max(0.0, self.trip.total_miles - 0.01))
        limit, _ = self.trip.speed_limit_at(bar_mi)
        # Screened for self-contradiction, not extremity: a street behind a
        # ramp terminal is never posted at the corridor's own highway number,
        # so a probe that comes back with one found no street zone at all --
        # it read the mainline through the gap and told the owner "Stop sign
        # at ramp end. Limit 70" at two exits running (playtest, 2026-08-20).
        # Better no limit clause than a wrong one.
        corridor_limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
        if limit >= corridor_limit and corridor_limit > RAMP_MAX_MPH:
            return ""
        return self.ctx.settings.speed_text(limit)

    def _announce_ramp_terminal(self) -> None:
        """Mid-ramp callout naming the control at the terminal."""
        self._ramp_light_announced = True
        limit_text = self._approach_limit_text()
        if self._ramp_control == "signal":
            phase = self._ramp_light_phase()
            self._ramp_light_last_phase = phase
            self.ctx.audio.play(
                "events/ramp_light_red" if phase == "red" else "events/ramp_light_green",
                volume=0.8,
            )
            if self._terse_speech():
                self.ctx.say_event(
                    f"Light at ramp end, {phase}. Limit {limit_text}.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.NAVIGATION,
                )
                return
            # "Brake to a stop" alone invites stopping right here, a quarter
            # mile short of the bar; the stop belongs at the light.
            if phase == "red":
                message = (
                    "Traffic light at the end of the ramp, currently red. "
                    "Roll down and stop at the light."
                )
            elif phase == "yellow":
                message = (
                    "Traffic light at the end of the ramp, currently yellow -- "
                    "it will be red when you reach it. Roll down and stop at the light."
                )
            else:
                message = "Traffic light at the end of the ramp, currently green."
            approach_clause = f" Speed limit {limit_text} on the approach." if limit_text else ""
            self.ctx.say_event(
                f"{message}{approach_clause}",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )
        elif self._ramp_control == "stop":
            self.ctx.audio.play("ui/notify", volume=0.7)
            if self._terse_speech():
                limit_clause = f" Limit {limit_text}." if limit_text else ""
                self.ctx.say_event(
                    f"Stop sign at ramp end.{limit_clause}",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.NAVIGATION,
                )
                return
            approach_clause = f" Speed limit {limit_text} on the approach." if limit_text else ""
            self.ctx.say_event(
                f"Stop sign at the end of the ramp. Brake to a full stop there.{approach_clause}",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )
        elif self._ramp_control in ("yield", "roundabout"):
            self.ctx.audio.play("ui/notify", volume=0.7)
            terse_noun = "Roundabout" if self._ramp_control == "roundabout" else "Yield"
            if self._terse_speech():
                limit_clause = f" Limit {limit_text}." if limit_text else ""
                self.ctx.say_event(
                    f"{terse_noun} at ramp end.{limit_clause}",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.NAVIGATION,
                )
                return
            # The instruction is the sign's real rule: slow for the gap, and
            # the stop is only owed when the road is not clear. "Brake to a
            # stop" here would teach the stop-sign habit at a sign whose
            # whole point is that a clear road never demands it.
            if self._ramp_control == "roundabout":
                message = (
                    "Roundabout at the end of the ramp. Yield to traffic in "
                    "the circle: slow, listen for your gap, and stop only if "
                    "it is not clear."
                )
            else:
                message = (
                    "Yield sign at the end of the ramp. Slow, listen for "
                    "your gap, and stop only if the road is not clear."
                )
            approach_clause = f" Speed limit {limit_text} on the approach." if limit_text else ""
            self.ctx.say_event(
                f"{message}{approach_clause}",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )

    def _update_ramp_terminal_assist(self) -> None:
        """Route-transition assistance works the pedals for the terminal.

        Stopping a rig blind inside the bar's grace window while the light
        cycles in real time is a positioning task whose failure mode is
        trailer damage -- the 2026-07-22 playtest ended a clean run with
        cross traffic in the trailer. With route-transition assistance on,
        the assist brakes for a red (or a yellow it cannot legally beat),
        holds the stop at the bar, and keeps a green crossing under the
        clean-roll speed. The phases still speak, and pulling ahead when
        the light releases stays the driver's move.
        """
        if not self.ctx.settings.route_transition_assist:
            return
        if self._ramp_mi is None or self._ramp_terminal_done:
            return
        if (
            self._ramp_control not in ("signal", "stop", "yield", "roundabout")
            or not self._ramp_light_announced
        ):
            return
        if self._ramp_waiting_at_light:
            # Holding for green: the assist keeps the brakes on.
            self.truck.throttle = 0.0
            self.truck.brake = 1.0
            return
        gap_mi = self._ramp_mi - RAMP_ACCESS_MI
        speed = self.truck.speed_mph
        if self._ramp_control == "signal":
            phase = self._ramp_light_phase()
            must_stop = phase == "red" or (phase == "yellow" and gap_mi > 0)
            if not must_stop:
                # A green (or a yellow already at the bar) is legal to roll,
                # but not at speed: hold the crossing under the clean-roll
                # threshold with room to spare.
                if gap_mi <= bar_tick_range_mi(self.truck) and speed > GREEN_ROLL_MPH - 5:
                    self.truck.throttle = 0.0
                    self.truck.brake = max(self.truck.brake, 0.4)
                return
        if self._ramp_control in ("yield", "roundabout"):
            bubble = getattr(self, "_cross_bubble", None)
            if bubble is None or bubble.clear_to_cross():
                # A clear yield is rolled, not stopped: the assist holds the
                # crossing at roll speed and the gap verdict lands at the
                # line. Braking to a dead stop on a clear yield is the
                # rear-end setup the roadmap warns the LEAD car will pull.
                if gap_mi <= bar_tick_range_mi(self.truck) and speed > YIELD_ROLL_MPH - 3:
                    self.truck.throttle = 0.0
                    self.truck.brake = max(self.truck.brake, 0.4)
                return
            # Not clear: fall through and brake for the line like a stop.
        if speed <= RED_STOP_MPH and gap_mi <= RAMP_ASSIST_HOLD_MI:
            # At the bar with the truck stopped: the assist owns the hold.
            self.truck.throttle = 0.0
            self.truck.brake = 1.0
            self._ramp_assist_brake = 0.0
            if self._ramp_control in ("stop", "yield", "roundabout"):
                # The assist holds the stop; the release now waits for the
                # bubble's gap, same as an unassisted stop. The hold above
                # keeps the brakes on through the wait.
                noun = {
                    "stop": "sign",
                    "yield": "yield",
                    "roundabout": "roundabout entry",
                }[self._ramp_control]
                bubble = getattr(self, "_cross_bubble", None)
                if bubble is not None and not bubble.clear_to_cross():
                    if not self._ramp_waiting_at_sign:
                        self._ramp_waiting_at_sign = True
                        nearest = bubble.approaching(8.0)
                        what = (
                            f"A {nearest.vehicle_class} crossing from the {nearest.from_side}"
                            if nearest is not None
                            else "Cross traffic"
                        )
                        self.ctx.say_event(
                            f"Stopped at the {noun}. {what}; assistance is holding for your gap.",
                            interrupt=False,
                            priority=EventPriority.ROUTE,
                            category=SpeechCategory.NAVIGATION,
                        )
                    return
                self._ramp_terminal_done = True
                message = (
                    "Gap in traffic. Clear; pull ahead to the entrance."
                    if self._ramp_waiting_at_sign
                    else f"Stopped at the {noun}. Clear; pull ahead to the entrance."
                )
                self._ramp_waiting_at_sign = False
                self.ctx.say_event(
                    message,
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.NAVIGATION,
                )
            elif not self._ramp_waiting_at_light:
                self._ramp_waiting_at_light = True
                # ROUTE, not the ambient default: names an automation (the ramp
                # assist) that just took the brakes, same as the stop-sign
                # sibling above (automation-handoff sweep, 2026-08-20, the
                # deferred 2026-08-15 audit).
                self.ctx.say_event(
                    "Stopped at the red light. Assistance is holding the brakes for green.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.CONFIRMATION,
                )
            return
        if speed <= RED_STOP_MPH:
            # Already stopped, but short of the hold window: a driver braking
            # on their own on top of the assist lands here, and a standing
            # truck has nothing left to brake for. The assist must hand the
            # pedals back -- pinning throttle at zero and the brake at its
            # floor against a truck that is already stopped is a hold with no
            # release, and the driver cannot move again (playtest softlock,
            # 2026-07-24). The queue guidance is what tells them to close the
            # gap to the bar from here. Dropping the held application matters
            # for the same reason: a creep to the bar must start from an open
            # pedal, not from whatever the approach was holding.
            self._ramp_assist_brake = 0.0
            return
        # Brake down the approach: needed deceleration to stop at the bar,
        # recomputed each tick, mapped onto brake application. As the gap
        # closes the demand rises and the pedal follows.
        gap_m = max(0.5, gap_mi * 1609.344)
        v_mps = max(0.0, self.truck.velocity_mps)
        needed = (v_mps * v_mps) / (2.0 * gap_m)
        idle = self._ramp_assist_brake <= 0.0
        if idle and needed < RAMP_ASSIST_DECEL_START_MPS2 and gap_m > 30.0:
            return
        self._ramp_assist_brake = assist_servo_brake(self._ramp_assist_brake, needed, self.truck)
        self.truck.throttle = 0.0
        self.truck.brake = max(self.truck.brake, self._ramp_assist_brake)
        if not self._ramp_assist_said:
            self._ramp_assist_said = True
            # A transit stop: the bar is honored and then driven away from, so
            # the session comes back on its own past it rather than waiting
            # for a departure that never happens on a ramp.
            self._pause_speed_control(resume_when_rolling=True)
            what = {
                "signal": "light",
                "stop": "stop sign",
                "yield": "yield",
                "roundabout": "roundabout",
            }.get(self._ramp_control, "stop sign")
            self.ctx.say_event(
                f"Route-transition assistance braking for the {what}.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.CONFIRMATION,
            )

    def _update_ramp_terminal(self) -> None:
        """Crossing the terminal: honor the light or the sign, or pay for it.

        A driver still braking gets the length of the grace distance past the
        bar to finish the stop; carrying speed beyond it commits the run."""
        speed = self.truck.speed_mph
        past_bar = self._ramp_mi is not None and (
            self._ramp_mi <= RAMP_ACCESS_MI - RAMP_TERMINAL_GRACE_MI
        )
        if self._ramp_control == "signal":
            if self._ramp_light_is_red():
                if speed <= RED_STOP_MPH:
                    if not self._ramp_waiting_at_light:
                        self._ramp_waiting_at_light = True
                        self.ctx.say_event(
                            "Stopped at the red light. Hold the brakes for green.",
                            interrupt=False,
                            priority=EventPriority.ROUTE,
                            category=SpeechCategory.NAVIGATION,
                        )
                    return
                if not past_bar:
                    return  # still braking down to the stop bar
                self._ramp_terminal_done = True
                self._ramp_waiting_at_light = False
                # What the run actually meets is the bubble's answer now,
                # not the old certainty: cross traffic flows on the player's
                # red, so this usually finds a vehicle -- but a gambler who
                # threads a real gap gets away with it, exactly like the road.
                met, vehicle = self._cross_violation_meets()
                pan = -0.4 if vehicle is None or vehicle.from_side == "left" else 0.4
                if speed > STOP_ROLL_CLIP_MPH:
                    if met == "hit":
                        self.ctx.audio.play(self._cross_vehicle_sound(vehicle), volume=1.0, pan=pan)
                        self.ctx.audio.play("vehicle/collision")
                        self.ctx.controller.rumble.impact(RED_RUN_DAMAGE)
                        # A driver already hard on the brakes, carried through
                        # by the load, did not make a preventable mistake. The
                        # violation still stands; the discipline does not.
                        self.truck.apply_collision(
                            RED_RUN_DAMAGE,
                            preventable=not self.truck.pushed_through_by_surge(),
                        )
                        self.ctx.say_event(
                            "You ran the red light at the ramp end and cross traffic "
                            "clipped the trailer! Total damage "
                            f"{self.truck.damage_pct:.0f} percent.",
                            interrupt=True,
                            category=SpeechCategory.SAFETY,
                        )
                    elif met == "near":
                        self.ctx.audio.play(self._cross_vehicle_sound(vehicle), volume=1.0, pan=pan)
                        self.ctx.say_event(
                            "You ran the red light at the ramp end. Cross traffic "
                            "brakes hard and leans on the horn.",
                            interrupt=True,
                            category=SpeechCategory.CONFIRMATION,
                        )
                    else:
                        self.ctx.say_event(
                            "You ran the red light at the ramp end. Nothing was "
                            "crossing; nothing will be next time.",
                            interrupt=True,
                            category=SpeechCategory.CONFIRMATION,
                        )
                elif met == "empty":
                    self.ctx.say_event(
                        "You crept through the red light. Nothing was crossing this time.",
                        interrupt=True,
                        category=SpeechCategory.CONFIRMATION,
                    )
                else:
                    self.ctx.audio.play(self._cross_vehicle_sound(vehicle), volume=1.0, pan=pan)
                    self.ctx.say_event(
                        "You crept through the red light. Cross traffic leans on the horn.",
                        interrupt=True,
                        category=SpeechCategory.CONFIRMATION,
                    )
                return
            self._ramp_terminal_done = True
            self._ramp_waiting_at_light = False
            self.ctx.audio.play("events/ramp_light_green", volume=0.7)
            on_yellow = self._ramp_light_phase() == "yellow"
            if speed > GREEN_ROLL_MPH:
                message = "Through the light, but far too fast. Brake hard for the entrance."
            elif on_yellow:
                message = "Through on the yellow; brake for the entrance."
            else:
                message = "Green light. Through the intersection; brake for the entrance."
            self.ctx.say_event(
                message,
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.CONFIRMATION,
            )
            return
        if self._ramp_control == "stop":
            if speed > RED_STOP_MPH and not past_bar:
                return  # still braking down to the stop bar
            if speed <= RED_STOP_MPH:
                # Stopped at the sign: the clear call now waits for a real
                # gap in the cross bubble instead of arriving with the stop.
                # The crossing cues are the information -- each one is a
                # vehicle in the ear it comes from -- and "clear" is spoken
                # only when the window is genuinely open.
                bubble = getattr(self, "_cross_bubble", None)
                if bubble is not None and not bubble.clear_to_cross():
                    if not self._ramp_waiting_at_sign:
                        self._ramp_waiting_at_sign = True
                        nearest = bubble.approaching(8.0)
                        what = (
                            f"A {nearest.vehicle_class} crossing from the {nearest.from_side}"
                            if nearest is not None
                            else "Cross traffic"
                        )
                        self.ctx.say_event(
                            f"Stopped at the sign. {what}; wait for your gap.",
                            interrupt=False,
                            priority=EventPriority.ROUTE,
                            category=SpeechCategory.NAVIGATION,
                        )
                    return
                self._ramp_terminal_done = True
                message = (
                    "Gap in traffic. Clear; pull ahead to the entrance."
                    if self._ramp_waiting_at_sign
                    else "Stopped at the sign. Clear; pull ahead to the entrance."
                )
                self._ramp_waiting_at_sign = False
                self.ctx.say_event(
                    message,
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.NAVIGATION,
                )
                return
            self._ramp_terminal_done = True
            # Same honesty as the light: the bubble says what the blown sign
            # actually met. A stop-sign crossroad is often empty -- that is
            # what makes rolling one tempting, and what makes the day a
            # semi IS crossing the lesson it should be.
            met, vehicle = self._cross_violation_meets()
            pan = 0.4 if vehicle is None or vehicle.from_side == "right" else -0.4
            if speed > STOP_ROLL_CLIP_MPH:
                if met == "hit":
                    self.ctx.audio.play(self._cross_vehicle_sound(vehicle), volume=1.0, pan=pan)
                    self.ctx.audio.play("vehicle/collision")
                    self.ctx.controller.rumble.impact(STOP_ROLL_DAMAGE)
                    self.truck.apply_collision(
                        STOP_ROLL_DAMAGE,
                        preventable=not self.truck.pushed_through_by_surge(),
                    )
                    self.ctx.say_event(
                        "You blew the stop sign at the ramp end and clipped cross "
                        f"traffic! Total damage {self.truck.damage_pct:.0f} percent.",
                        interrupt=True,
                        category=SpeechCategory.SAFETY,
                    )
                elif met == "near":
                    self.ctx.audio.play(self._cross_vehicle_sound(vehicle), volume=1.0, pan=pan)
                    self.ctx.say_event(
                        "You blew the stop sign at the ramp end. Cross traffic "
                        "brakes hard and leans on the horn.",
                        interrupt=True,
                        category=SpeechCategory.CONFIRMATION,
                    )
                else:
                    self.ctx.say_event(
                        "You blew the stop sign at the ramp end. The crossroad "
                        "was empty; it will not always be.",
                        interrupt=True,
                        category=SpeechCategory.CONFIRMATION,
                    )
            elif met == "empty":
                self.ctx.say_event(
                    "You rolled the stop sign at the ramp end. Nothing was crossing this time.",
                    interrupt=True,
                    category=SpeechCategory.CONFIRMATION,
                )
            else:
                self.ctx.audio.play(self._cross_vehicle_sound(vehicle), volume=1.0, pan=pan)
                self.ctx.say_event(
                    "You rolled the stop sign at the ramp end. Cross traffic leans on the horn.",
                    interrupt=True,
                    category=SpeechCategory.CONFIRMATION,
                )
            return
        if self._ramp_control in ("yield", "roundabout"):
            # The yield rule, straight from the sign: a gap taken at roll
            # speed is the clean crossing, stopping is always legal, and an
            # occupied window is the clip machinery -- at THEIR closing
            # speed, because you rolled under their bumper.
            noun = "roundabout" if self._ramp_control == "roundabout" else "yield"
            if speed <= RED_STOP_MPH:
                # Stopped: exactly the stop sign's wait, spoken for a yield.
                bubble = getattr(self, "_cross_bubble", None)
                if bubble is not None and not bubble.clear_to_cross():
                    if not self._ramp_waiting_at_sign:
                        self._ramp_waiting_at_sign = True
                        nearest = bubble.approaching(8.0)
                        what = (
                            f"A {nearest.vehicle_class} crossing from the {nearest.from_side}"
                            if nearest is not None
                            else "Cross traffic"
                        )
                        self.ctx.say_event(
                            f"Stopped at the {noun}. {what}; wait for your gap.",
                            interrupt=False,
                            priority=EventPriority.ROUTE,
                            category=SpeechCategory.NAVIGATION,
                        )
                    return
                self._ramp_terminal_done = True
                self._ramp_waiting_at_sign = False
                self.ctx.say_event(
                    "Gap in traffic. Clear; pull ahead to the entrance.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.NAVIGATION,
                )
                return
            if not past_bar:
                return  # still rolling down to the line; the gap decides there
            self._ramp_terminal_done = True
            met, vehicle = self._cross_violation_meets()
            pan = 0.4 if vehicle is None or vehicle.from_side == "right" else -0.4
            if met == "hit":
                self.ctx.audio.play(self._cross_vehicle_sound(vehicle), volume=1.0, pan=pan)
                self.ctx.audio.play("vehicle/collision")
                self.ctx.controller.rumble.impact(STOP_ROLL_DAMAGE)
                self.truck.apply_collision(
                    STOP_ROLL_DAMAGE,
                    preventable=not self.truck.pushed_through_by_surge(),
                )
                self.ctx.say_event(
                    f"You rolled the {noun} into cross traffic and it clipped "
                    f"the trailer! Total damage {self.truck.damage_pct:.0f} percent.",
                    interrupt=True,
                    category=SpeechCategory.SAFETY,
                )
            elif met == "near":
                self.ctx.audio.play(self._cross_vehicle_sound(vehicle), volume=1.0, pan=pan)
                self.ctx.say_event(
                    f"You forced the gap at the {noun}. Cross traffic brakes "
                    "hard and leans on the horn.",
                    interrupt=True,
                    category=SpeechCategory.CONFIRMATION,
                )
            elif speed > YIELD_ROLL_MPH:
                self.ctx.say_event(
                    f"Through the {noun}, but far too fast. Brake hard for the entrance.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.CONFIRMATION,
                )
            else:
                self.ctx.say_event(
                    f"Through the {noun} in a gap. Pull ahead to the entrance.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.CONFIRMATION,
                )
            return
        self._ramp_terminal_done = True

    def _update_exit(self, moved_mi: float, dt: float = 0.0) -> None:
        """Advance an armed exit or an active ramp; opens the stop menu."""
        # Real time from the gore to the terminal: while the ramp ends in
        # a live light or sign, the clock must not compress the seconds
        # the driver needs to brake for it.
        self.trip.controlled_ramp = (
            self._ramp_mi is not None
            and self._ramp_control in ("signal", "stop", "yield", "roundabout")
            and not self._ramp_terminal_done
        )
        self.trip.dock_run_in = (
            self._ramp_mi is not None
            and getattr(self._ramp_stop, "type", "") == "delivery_destination"
        )
        # And the road left to an exit the driver has signalled for, which the
        # clock reads to decide whether the approach itself is close enough to
        # be driven in real time. None once the ramp is taken -- from there
        # ``controlled_ramp`` owns the clock -- or once the exit is behind.
        ahead_to_exit = (
            None
            if self._exit_stop is None or self._ramp_mi is not None
            else self._exit_stop.at_mi - self.trip.position_mi
        )
        self.trip.exit_approach_mi = (
            ahead_to_exit if ahead_to_exit is not None and ahead_to_exit > 0.0 else None
        )
        if self._ramp_mi is not None:
            self._ramp_mi -= moved_mi
            if not self._ramp_light_announced and self._ramp_mi <= RAMP_CONTROL_ANNOUNCE_MI:
                self._announce_ramp_terminal()
            self._update_ramp_terminal_assist()
            if self._update_selected_stop_assist():
                return
            if not self._ramp_terminal_done and self._ramp_mi <= RAMP_ACCESS_MI:
                self._update_ramp_terminal()
            if self._ramp_mi > 0:
                return
            if (
                self._ramp_stop.type == "delivery_destination"
                and self._ramp_terminal_done
                and self._begin_surface_chain()
            ):
                # The street chain is a DRIVING continuation: hand off at
                # whatever legal speed the terminal let through. Gating the
                # handoff on docking speed marooned a green-light roll past
                # the end of the ramp -- the streets refused to start until
                # the driver stopped dead in the road (owner playtest,
                # 2026-07-24). The scripted dock-menu arrival below still
                # rightly waits for a crawl.
                self._ramp_mi = None
                self._ramp_stop = None
                self._ramp_control = ""
                return
            if self.truck.speed_mph <= DOCKING_MAX_MPH:
                stop = self._ramp_stop
                self._ramp_mi = None
                self._ramp_stop = None
                self._ramp_control = ""
                if stop.type == "delivery_destination":
                    if self._begin_surface_chain():
                        return
                    self.trip.position_mi = self.trip.total_miles
                    self.trip.finished = True
                    self._open_facility_arrival()
                else:
                    self._open_poi_stop(stop, settle=True)
                return
            stop = self._ramp_stop
            if not self._ramp_end_said:
                if (
                    stop.type == "delivery_destination"
                    and not self._surface_chain
                    and self._surface_chain_route() is not None
                ):
                    # The facility has a street chain, so "you are at X"
                    # here is a lie by two miles: the driver was told they
                    # had arrived and then handed turn-by-turn streets
                    # (owner log, 2026-07-23, Sacramento Dry Warehouse).
                    # The chain's own "off the ramp and onto city streets"
                    # line follows and says it right. The said-latch stays
                    # open so the blown-stop rule below can never fire on a
                    # chain facility: the streets are still the way in.
                    return
                self._ramp_end_said = True
                if stop.type != "delivery_destination":
                    place = stop.spoken_name
                    message = (
                        f"At {place}. Stop now."
                        if self._terse_speech()
                        else f"You are at {place}. Come to a complete stop."
                    )
                else:
                    place = stop.name
                    message = (
                        f"At {place}."
                        if self._terse_speech()
                        else f"You are at {place}. Come to a complete stop."
                    )
                # Both kinds of ramp stop open the same real-time reaction
                # window. The destination opened none at all, so its grace sat
                # at zero forever and nothing downstream could ever read it as
                # spent (owner playtest, Buffalo to Albany, 2026-08-12).
                self._ramp_arrival_grace_s = self._ramp_arrival_grace_for(message)
                self.ctx.say_event(message, interrupt=True, category=SpeechCategory.NAVIGATION)
                return
            self._ramp_arrival_grace_s = max(0.0, self._ramp_arrival_grace_s - dt)
            # Rolled clear past the end of the ramp without ever stopping. Both
            # the distance and the real-time grace must expire, so trip pacing
            # cannot consume the player's spoken-cue reaction window.
            if (
                self._ramp_mi > -RAMP_OVERSHOOT_MI
                or self._ramp_arrival_grace_s > 0.0
                or self.truck.parking_brake
            ):
                return
            if stop.type == "delivery_destination":
                # The destination terminal used to be the one blown stop with
                # no consequence at all: the arrival line was spoken once, the
                # ramp counted down past it forever, and the player circled
                # with the route status frozen and nothing said until they quit
                # to the menu (owner playtest, Buffalo to Albany, 2026-08-12).
                self._loop_back_to_destination_terminal(stop)
                return
            # A route POI is blown, so give the highway back instead of leaving
            # a stuck, unpatrolled ramp lingering for miles.
            self._ramp_mi = None
            self._ramp_stop = None
            self._ramp_end_said = False
            self._ramp_arrival_grace_s = 0.0
            planned = self.trip.is_planned(stop)
            if planned:
                self.trip.planned_stop_key = None
            if self._is_selected_stop(stop):
                self._clear_selected_stop_intent()
            exit_ref = (
                f"{stop.exit_label} for {stop.spoken_name}"
                if stop.exit_label
                else f"the exit for {stop.spoken_name}"
            )
            line = (
                f"Drove past {stop.spoken_name}; you never stopped."
                if self._terse_speech()
                else f"You never stopped and drove past {exit_ref}."
            )
            if planned:
                line += " Plan cancelled."
            line += (
                " Planned rest-stop stopping assistance is off. Continue safely and "
                f"press {self.ctx.control_hint('rest')} to plan the next sleep-capable stop."
            )
            self.ctx.say_event(line, interrupt=True, category=SpeechCategory.CONFIRMATION)
            return
        stop = self._exit_stop
        if stop is None:
            return
        if self.trip.position_mi < stop.at_mi:
            self._update_exit_countdown(stop)
            return
        self._exit_stop = None
        # The exit is settled either way now, so the ramp cap comes off:
        # taking it pauses the session for the ramp, and missing it must not
        # leave automatic control crawling at ramp speed down the open highway.
        self._cruise_exit_mph = None
        if self._exit_signal_canceled:
            self._reset_exit_lane_state()
            self._exit_signal_canceled = False
            self.ctx.say_event(
                "Exit signal was canceled, so you stayed on the highway.",
                category=SpeechCategory.CONFIRMATION,
            )
            return
        self._exit_signal_canceled = False
        if self.trip.position_mi > stop.at_mi + EXIT_COMMIT_WINDOW_MI:
            self._reset_exit_lane_state()
            self._exit_signal_on = False
            if self._is_selected_stop(stop):
                self._clear_selected_stop_intent()
            pressure = self._active_exit_pressure(stop)
            if pressure is not None and pressure.intensity >= 0.35:
                self.ctx.say_event(
                    "You missed the exit window in heavy traffic and stayed on the highway.",
                    category=SpeechCategory.CONFIRMATION,
                )
            else:
                self.ctx.say_event(
                    "You missed the exit window and stayed on the highway.",
                    category=SpeechCategory.CONFIRMATION,
                )
            return
        if not self._exit_intent_ready(stop):
            self._reset_exit_lane_state()
            self._exit_signal_on = False
            if self._is_selected_stop(stop):
                self._clear_selected_stop_intent()
            place = self._missed_exit_phrase(stop)
            self.ctx.say_event(
                f"You missed {place}: the turn signal was not set. "
                "Stay on the highway and recover at the next safe exit.",
                category=SpeechCategory.CONFIRMATION,
            )
            return
        if not self._exit_lane_ready():
            self._reset_exit_lane_state()
            self._exit_signal_on = False
            if self._is_selected_stop(stop):
                self._clear_selected_stop_intent()
            missed = self._missed_exit_phrase(stop)
            pressure = self._active_exit_pressure(stop)
            if pressure is not None:
                self.ctx.say_event(
                    "Traffic boxed you out of the exit lane at the gore, so "
                    f"you missed {missed}. Stay on the highway and "
                    "recover at the next safe exit.",
                    category=SpeechCategory.CONFIRMATION,
                )
            else:
                self.ctx.say_event(
                    f"You missed {missed}: you were not in the "
                    "exit lane. Stay on the highway and recover at the next safe exit.",
                    category=SpeechCategory.CONFIRMATION,
                )
            return
        if self.truck.speed_mph <= RAMP_MAX_MPH:
            self._reset_exit_lane_state()
            self._exit_signal_on = False
            self._ramp_mi = RAMP_LENGTH_MI
            self._ramp_stop = stop
            self._ramp_end_said = False
            self._ramp_arrival_grace_s = 0.0
            self._destination_exit_taken = stop.type == "delivery_destination"
            if self._destination_exit_taken:
                self._post_gate_zone()
            # The ramp is a single lane peeling off the right side.
            self.lane.lane = 0
            self.lane.offset = 0.0
            self._lane_change_target = None
            self._merge_deadline = None
            self._begin_ramp_terminal(stop)
            # The ramp takes the pedals back, but the SESSION rides along: a
            # ramp terminal is a transit stop, so automatic speed control
            # returns on its own once the bar is honored and the ramp is
            # behind the truck. Disarming here is why both controllers stayed
            # dead until the player pressed resume (Shane, 2026-08-15). The
            # resume helper still refuses the whole ramp, so nothing
            # re-engages between here and the bar.
            #
            # A destination exit is the exception: that ramp ends at the gate,
            # and winding the truck back up on it is exactly what drove a
            # playtest past the terminal at 66 mph. It holds like any other
            # arrival, until the player departs with the next load.
            self._pause_speed_control(resume_when_rolling=stop.type != "delivery_destination")
            self.ctx.audio.play("ui/notify", volume=0.7)
            if stop.type == "delivery_destination":
                labeled = getattr(stop, "exit_phrase", "") or stop.exit_label
                take = (
                    f"You take {labeled}, destination exit for {stop.name}."
                    if labeled
                    else f"You take the destination exit for {stop.name}."
                )
            else:
                take = (
                    f"You take {stop.exit_label} for {stop.spoken_name}."
                    if stop.exit_label
                    else f"You take the exit for {stop.spoken_name}."
                )
            scale_ramp = getattr(stop, "type", "") == "weigh_station"
            if self._terse_speech():
                terminal = {
                    "signal": " Traffic light at the end.",
                    "stop": " Stop sign at the end.",
                }.get(self._ramp_control, "")
                if scale_ramp:
                    terminal = " The scale is at the end."
                message = f"{take} Half a mile of ramp.{terminal}"
            else:
                ending = {
                    "signal": "traffic light at the end, then brake to a stop at the entrance",
                    "stop": "stop sign at the end, then brake to a stop at the entrance",
                }.get(self._ramp_control, "brake to a stop at the end")
                if scale_ramp:
                    ending = "roll down to the scale and stop at the bar"
                message = f"{take} Half a mile of ramp; {ending}."
            self.ctx.say_event(message, interrupt=True, category=SpeechCategory.NAVIGATION)
        else:
            missed = self._missed_exit_phrase(stop)
            line = f"You were going too fast for the ramp and missed {missed}."
            if self.trip.is_planned(stop):
                # Fold the plan cancellation into this one line so the driver
                # hears a single cue, and clear it here so _check_stops doesn't
                # also emit a "drove past your planned stop" warning next tick.
                self.trip.planned_stop_key = None
                line += " Plan cancelled."
            if self._is_selected_stop(stop):
                self._clear_selected_stop_intent()
            self.ctx.say_event(line, interrupt=True, category=SpeechCategory.CONFIRMATION)
            self._exit_signal_on = False
            self._reset_exit_lane_state()

    def _ramp_arrival_grace_for(self, message: str) -> float:
        """Real reaction seconds after ``message`` at the player's own rate.

        A screen-reader-owned voice reads at a rate the game cannot see, so
        the slowest assumption stands in for it.
        """
        speech_rate = (
            self.ctx.settings.speech_rate
            if self.ctx.settings.sapi_events
            and getattr(self.ctx.speech, "event_supports_rate", False)
            else 0.0
        )
        return ramp_arrival_grace_seconds(message, speech_rate)

    def _destination_terminal_retry_mi(self) -> float:
        """How much road a loop-back puts back in front of the entrance.

        Sized in real seconds at the current pace, never a fixed stretch: once
        the terminal is behind the truck the ramp runs on the compressed clock
        again, and a fixed retry distance would be gone before the fresh cue
        could be heard -- the lesson the missed-exit and missed-gate loops both
        already carry. Bounded by the road it lives on: never shorter than the
        terminal-to-driveway stretch, never longer than the ramp itself.
        """
        speed = max(self.truck.speed_mph, RAMP_MAX_MPH)
        miles = EXIT_WARNING_REAL_S * speed * self.trip.effective_time_scale / 3600.0
        return max(RAMP_ACCESS_MI, min(miles, RAMP_LENGTH_MI))

    def _loop_back_to_destination_terminal(self, stop) -> None:
        """Blown the destination terminal at speed: the scripted loop-back.

        The fourth instance of a pattern the blown ramp POI, the missed
        destination exit, and the missed facility gate already share, and the
        one place it was missing. Only the no-chain terminal reaches here: a
        facility with a street chain hands off at legal speed and never blows.

        The turnaround comes back to the facility, not back up the ramp, so
        the light or sign the driver already honored is not re-run -- only the
        entrance is ahead again. The clock keeps running through every loop;
        the lost time is the consequence, never a fine.
        """
        self._ramp_terminal_miss_count += 1
        self.trip.game_minutes += RAMP_TERMINAL_MISS_LOOP_MIN
        self._ramp_mi = self._destination_terminal_retry_mi()
        # The say-once latch must never swallow the reposition: when the
        # missed-exit loop let it, a second miss stranded the trip with
        # nothing left to aim at. The arrival line speaks fresh instead.
        self._ramp_end_said = False
        self._ramp_arrival_grace_s = 0.0
        # Automatic speed control is what drove this miss, so the whole
        # session goes -- not just the active controller. Left armed, the
        # resume helper would wind the truck straight back up to speed on the
        # re-approach and blow the same entrance again.
        self._cancel_cruise()
        self._cancel_keeper()
        place = stop.name
        if self._terse_speech():
            message = (
                f"Drove past {place}; you never stopped. Safe turnaround. "
                f"{place} ahead again; stop this time."
            )
        else:
            message = (
                f"You drove past {place} without stopping. You continue to the "
                "next safe turnaround and loop back onto the approach. "
                f"{place} is ahead again; slow to a stop this time. "
                "The clock is still running."
            )
        if self._ramp_terminal_miss_count >= 2:
            # The identical core line keeps the flow predictable by ear; a
            # repeat miss earns help, not scolding.
            message += f" Brake with {self.ctx.control_hint('brake')} well before it."
        self.ctx.audio.play("ui/warning")
        self._set_status(f"Drove past {place}. Use the next safe turnaround.")
        # The mandatory destination terminal, not an optional stop: names the
        # loop-back maneuver that still delivers the load, so it must survive
        # quiet/urgent_only as words.
        self.ctx.say_event(message, interrupt=True, category=SpeechCategory.NAVIGATION)

    def _update_selected_stop_assist(self) -> bool:
        """Brake an explicitly selected optional stop at its entrance."""
        stop = self._ramp_stop
        if (
            stop is None
            or not self._selected_stop_assist_armed
            or not self._is_selected_stop(stop)
            or not self.ctx.settings.selected_stop_assist
            or not self._ramp_terminal_done
        ):
            return False
        if self._ramp_mi is not None and self._ramp_mi <= -RAMP_OVERSHOOT_MI:
            return False
        gap_mi = max(0.0, self._ramp_mi or 0.0)
        speed = self.truck.speed_mph
        if speed <= DOCKING_MAX_MPH and gap_mi <= 0.08:
            self.truck.throttle = 0.0
            self.truck.brake = 1.0
            self.truck.set_parking_brake()
            self._ramp_mi = None
            self._ramp_stop = None
            self._ramp_control = ""
            self._exit_signal_on = False
            self._cruise_exit_mph = None
            self._reset_exit_lane_state()
            self._open_poi_stop(stop, settle=True)
            return True
        if speed <= DOCKING_MAX_MPH:
            # Stopped short of the entrance: never trap the driver in a brake
            # hold. The ramp guidance tells them to pull ahead.
            self.truck.brake = 0.0
            return False
        gap_m = max(0.5, gap_mi * 1609.344)
        v_mps = max(0.0, self.truck.velocity_mps)
        needed = (v_mps * v_mps) / (2.0 * gap_m)
        if (
            self._selected_stop_assist_brake <= 0.0
            and needed < RAMP_ASSIST_DECEL_START_MPS2
            and gap_mi > 0.08
        ):
            return False
        self.truck.throttle = 0.0
        self._selected_stop_assist_brake = assist_servo_brake(
            self._selected_stop_assist_brake, needed, self.truck
        )
        self.truck.brake = max(self.truck.brake, self._selected_stop_assist_brake)
        if not self._selected_stop_assist_said:
            self._selected_stop_assist_said = True
            self._pause_speed_control()
            # ROUTE, not the ambient default: an automation naming that it just
            # took the brakes, same class as the ramp assist's own braking-for
            # line (automation-handoff sweep, 2026-08-20, the deferred
            # 2026-08-15 audit).
            self.ctx.say_event(
                f"Planned rest-stop stopping assistance braking for the entrance to {stop.spoken_name}.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.CONFIRMATION,
            )
        return False

    def _toggle_cruise(self) -> None:
        t = self.truck
        # Parked with the brake set, the cruise button is the fast-idle
        # switch, exactly like a real electronic truck: latch a high idle
        # (warm-up, faster air build), press again to drop it. It also
        # cancels on its own the moment the parking brake releases.
        if t.high_idle_allowed:
            if t.high_idle_rpm is None:
                t.high_idle_rpm = HIGH_IDLE_DEFAULT_RPM
                self.ctx.say(
                    f"High idle, {t.high_idle_rpm:.0f} RPM. "
                    "Plus and minus adjust it; releasing the parking brake cancels."
                )
            else:
                t.high_idle_rpm = None
                self.ctx.say("High idle off.")
            return
        if (
            self._speed_control_armed
            or self._keeper_mph is not None
            or self._cruise_mph is not None
        ):
            self._disarm_speed_control()
            self.ctx.say("Automatic speed control off.")
            return
        limit, zone_reason = self.trip.speed_limit_at(self.trip.position_mi)
        if zone_reason is not None:
            # Adaptive cruise never runs on facility access roads, gates, work
            # zones, or heavy traffic. The speed keeper covers those low-speed
            # stretches instead, so nobody has to hold the accelerator down.
            self._engage_keeper(limit, zone_reason)
            return
        if not t.engine_on or t.speed_mph < CRUISE_MIN_MPH:
            self.ctx.say(
                "Adaptive cruise needs the engine running and at "
                f"least {self.ctx.settings.speed_text(CRUISE_MIN_MPH)}."
            )
            return
        self._engage_cruise(t.speed_mph)

    def _engage_cruise(self, target_mph: float, *, transition: bool = False) -> None:
        """Start adaptive cruise as part of the armed speed-control session."""
        t = self.truck
        self._speed_control_armed = True
        self._speed_control_paused_at_stop = False
        # Round to the whole mph the player actually hears (speed_text already
        # rounds the readout): a plain K-set otherwise captures the truck's
        # exact float speed (e.g. 59.95), and the first +/- tap would spend
        # itself just healing that invisible fraction onto the grid instead
        # of making an audible step.
        self._cruise_mph = max(CRUISE_MIN_MPH, min(CRUISE_MAX_MPH, round(target_mph)))
        self._speed_control_target_mph = self._cruise_mph
        # An armed exit still ahead keeps its cap across a cruise session.
        # Cancelling cruise clears _cruise_exit_mph, and on the Denver run the
        # descent cancelled it a mile before the ramp; the driver re-engaged
        # at 53 and the fresh session had forgotten the exit entirely, so
        # nothing ever eased for it. The cap is a property of the road ahead,
        # not of the cruise session that happened to be running when the exit
        # was announced -- so re-arming it here rather than leaving it to the
        # announcement, which has already been made and will not repeat.
        if self._cruise_exit_mph is None and self._exit_stop is not None:
            ahead = self._exit_stop.at_mi - self.trip.position_mi
            if ahead > 0 and (self._exit_signal_on or self.ctx.settings.lane_is_automated()):
                self._cruise_exit_mph = min(self._cruise_mph, RAMP_CRUISE_TARGET_MPH)
        # Chase a working setpoint that starts at road speed, so a big resume
        # error eases on rather than landing on the pedal at once. Engaging at
        # the current speed (a plain K-set) seeds it at the target, so there is
        # no ramp to feel.
        self._cruise_working_mph = max(CRUISE_MIN_MPH, min(self._cruise_mph, t.speed_mph))
        self._cruise_throttle = t.throttle
        self._cruise_applied = t.throttle
        # Engaging on a grade starts from the feed-forward, so the trim opens
        # at zero rather than carrying a stale wind-up into the new session.
        self._cruise_trim = 0.0
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False
        self._acc_limit_cap_said = None
        self._acc_weather_cap_said = None
        gap = self._acc_gap_seconds()
        effective_mph = (
            min(self._cruise_mph, self._cruise_exit_mph)
            if self._cruise_exit_mph is not None
            else self._cruise_mph
        )
        exit_note = " for the ramp" if self._cruise_exit_mph is not None else ""
        # Name the number the truck will actually hold. The resume line used
        # to speak the SET speed while a zone cap silently pinned the working
        # target far below it: clear of the visible queue in a heavy-traffic
        # zone posting 20, cruise said "resuming at 70" and held 23 -- the
        # zone's 20 plus the ACC offset -- for the rest of the zone, minutes
        # of open-looking road with the announcement contradicting the truck
        # (Brandon, 2026-08-20). The queue ahead is real even when the bubble
        # happens to be showing empty road; the words just have to match.
        posted, limit_reason = self._acc_posted_limit_ahead()
        cap_mph = (
            posted if limit_reason in RESTRICTED_ZONE_REASONS else posted + ACC_LIMIT_OFFSET_MPH
        )
        if cap_mph < effective_mph:
            effective_mph = cap_mph
            exit_note = {
                "construction": " through the construction zone",
                "heavy traffic": " through the heavy traffic",
            }.get(limit_reason, " for the lower limit")
        effects = self.weather.effects
        if (effects.grip < 1.0 or effects.visibility_mi < 8.0) and (
            effects.safe_speed_mph < effective_mph
        ):
            effective_mph = effects.safe_speed_mph
            exit_note = f" in the {self.weather.current.value}"
        self.ctx.audio.play("ui/notify", volume=0.5)
        message = (
            f"Adaptive cruise {'resuming' if transition else 'set'} at "
            f"{self.ctx.settings.speed_text(effective_mph)}{exit_note}. "
            f"Following gap {gap:.0f} seconds. K or braking cancels."
        )
        if transition:
            # ROUTE: automation retaking the pedals after a zone, the same
            # handoff as the keeper's resume line (driving_speed_control 291,
            # already ROUTE). The quiet rung still silences it by category;
            # ROUTE only stops a busy channel eating it at standard.
            self.ctx.say_event(
                f"Open road. {message}",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.CONFIRMATION,
            )
        else:
            self.ctx.say(message)

    def _adjust_cruise(self, direction: int, *, fine: bool = False) -> None:
        """Raise or lower the cruise set point -- the Accel/Coast (+/-) buttons.

        Plain taps walk the fives grid (an off-grid captured speed heals on
        the first press); Ctrl taps move by exactly one mile per hour. While
        the speed keeper is handling a restricted zone, the same buttons
        adjust the open-road target that adaptive cruise will resume. Parked
        with high idle latched, they step the idle setpoint instead."""
        t = self.truck
        if t.high_idle_rpm is not None and t.high_idle_allowed:
            step = HIGH_IDLE_STEP_RPM if direction > 0 else -HIGH_IDLE_STEP_RPM
            t.high_idle_rpm = max(HIGH_IDLE_MIN_RPM, min(HIGH_IDLE_MAX_RPM, t.high_idle_rpm + step))
            self.ctx.say(f"High idle {t.high_idle_rpm:.0f} RPM.")
            return
        if self._cruise_mph is None and self._keeper_mph is None:
            self.ctx.say("Adaptive cruise is off. Press K to set it first.")
            return
        base = self._speed_control_target_mph
        if base is None:
            limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
            base = max(CRUISE_MIN_MPH, limit)
        target = cruise_step_target(base, direction, fine)
        self._speed_control_target_mph = target
        if self._cruise_mph is not None:
            self._cruise_mph = target
            if self._cruise_exit_mph is not None:
                ramp_target = min(target, self._cruise_exit_mph)
                self.ctx.say(
                    SpokenMessage(
                        f"Open-road cruise target {self.ctx.settings.speed_text(target)}. "
                        "Ramp approach target "
                        f"{self.ctx.settings.speed_text(ramp_target)}.",
                        f"{self._speed_number(target)}, ramp {self._speed_number(ramp_target)}.",
                    ),
                    category=SpeechCategory.CONFIRMATION,
                )
            else:
                # Terse is the number alone. Walking the dial is a rapid
                # sequence of presses and the player already knows which
                # control they are holding, so a sentence per press is the
                # unit repeated, not information (owner, 2026-08-17).
                self.ctx.say(
                    SpokenMessage(
                        f"Adaptive cruise {self.ctx.settings.speed_text(target)}.",
                        f"{self._speed_number(target)}.",
                    ),
                    category=SpeechCategory.CONFIRMATION,
                )
        else:
            self.ctx.say(
                SpokenMessage(
                    f"Open-road cruise target {self.ctx.settings.speed_text(target)}.",
                    f"{self._speed_number(target)}.",
                ),
                category=SpeechCategory.CONFIRMATION,
            )

    def _speed_number(self, mph: float) -> str:
        """Just the figure, in the player's units -- no unit word.

        What the dial answers with at quiet. The unit never changes between
        presses, so repeating it on every tap of the Accel/Coast buttons is
        the one part of the line carrying no information.
        """
        return self.ctx.settings.speed_text(mph).split()[0]

    def _engage_keeper(
        self,
        limit_mph: float,
        zone_reason: str,
        *,
        target_mph: float | None = None,
        announce: bool = True,
    ) -> None:
        """Hold the current speed through a low-speed zone (K in a zone).

        An input-accessibility aid: facility access roads, gate queues, work
        zones, and congestion otherwise demand a continuously held accelerator,
        which some players cannot sustain. The keeper caps at the zone's limit,
        follows queued traffic, and hands back on any brake input.
        """
        t = self.truck
        if not self.ctx.settings.speed_keeper:
            # Naming the way out matters more than the refusal: the keeper is
            # exactly the thing that holds speed here, and a driver who has
            # never turned it on hears only that cruise "is not available"
            # and concludes the ramp kills speed control (Shane, 2026-08-15).
            self.ctx.say(
                f"Adaptive cruise is not available in a {zone_reason} zone. "
                "The speed keeper holds your speed here instead; turn it on "
                "in Settings, Controls."
            )
            return
        if not t.engine_on or (target_mph is None and t.speed_mph < KEEPER_MIN_MPH):
            self.ctx.say("The speed keeper needs the engine running and the truck rolling.")
            return
        self._speed_control_armed = True
        self._speed_control_paused_at_stop = False
        # Same rounding as _engage_cruise: a plain K-set captures the truck's
        # exact float speed, which the player never hears -- only its rounded
        # form does.
        captured_mph = round(t.speed_mph) if target_mph is None else target_mph
        self._keeper_mph = min(captured_mph, limit_mph)
        self._keeper_zone = zone_reason
        self._keeper_zone_limit = limit_mph
        self._keeper_throttle = t.throttle
        if announce:
            self.ctx.audio.play("ui/notify", volume=0.5)
            self.ctx.say(
                f"Automatic speed control on. Speed keeper holding "
                f"{self.ctx.settings.speed_text(self._keeper_mph)} through the "
                f"{zone_reason} zone. K or braking cancels."
            )

    def _update_keeper(
        self, dt: float, braking: bool, accelerating: bool, clutch_disengaged: bool
    ) -> None:
        """Hold a gentle low-speed target while the zone lasts."""
        if self._keeper_mph is None:
            return
        t = self.truck
        if braking or t.emergency_brake or t.air_brakes_holding or not t.engine_on or t.stalled:
            self._cancel_keeper()
            # ROUTE, not the ambient default: the automation just released the
            # throttle, and a driver who assumed it still held speed needs to
            # hear that (automation-handoff sweep, 2026-08-20, the deferred
            # 2026-08-15 audit).
            self.ctx.say_event(
                "Speed keeper canceled; automatic speed control off.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.CONFIRMATION,
            )
            return
        if accelerating:
            return  # manual override; the keeper resumes when the key lifts
        if clutch_disengaged:
            t.throttle = 0.0
            return
        limit, zone_reason = self.trip.speed_limit_at(self.trip.position_mi)
        if zone_reason is None and self._departure_ramp_mi is not None:
            # The acceleration lane is a low-speed regime like a zone, and the
            # keeper is the tool for those -- it exists because holding an
            # accelerator down is exactly what some players cannot do. Handing
            # to cruise here handed to nothing: cruise refuses below its own
            # minimum holding speed, so a driver coming off yard streets at
            # twenty had no automation at all until they had got themselves
            # back up to road speed by hand (Brandon, 2026-08-21). The keeper
            # stays on and builds toward the road's own limit instead.
            zone_reason = "acceleration lane"
        if zone_reason is None:
            target_mph = self._speed_control_target_mph or limit
            self._cancel_keeper(preserve_session=True)
            self._engage_cruise(target_mph, transition=True)
            return
        self._keeper_zone = zone_reason
        self._take_new_posted_limit(limit, zone_reason)
        target_mph = min(self._keeper_mph, limit)
        # The road ahead, not just the road under the wheels: a corner or a
        # lower posted limit close enough that the shedding has to start now.
        # A posted drop gets the same one-shot cue adaptive cruise gives it;
        # a corner does not, because its own approach call already names the
        # number and says the keeper is taking it.
        ahead = self._keeper_speed_ahead()
        if ahead is not None and ahead[0] < target_mph:
            target_mph = max(KEEPER_MIN_MPH, ahead[0] - KEEPER_EASE_UNDERSHOOT_MPH)
            if ahead[1] != "turn" and (
                self._keeper_ease_said is None or ahead[0] < self._keeper_ease_said - 0.5
            ):
                self._keeper_ease_said = ahead[0]
                reason = {
                    "construction": "Construction zone ahead",
                    "heavy traffic": "Heavy traffic ahead",
                }.get(ahead[1], "Posted limit lower")
                # ROUTE, not the ambient default: same family as the adaptive
                # cruise easing line below (4054) -- an assist saying it is
                # about to change how fast the truck is going is a
                # consequence, not colour, and this one governs the same class
                # of dropped-stale incident (automation-handoff sweep,
                # 2026-08-20, the deferred 2026-08-15 audit).
                self.ctx.say_event(
                    f"{reason}; speed keeper easing to {self.ctx.settings.speed_text(ahead[0])}.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.CONFIRMATION,
                )
                # This line already named the number for a plain posted-limit
                # drop; the arrival "Speed limit reduced to X" would otherwise
                # repeat it a moment later.
                if ahead[1] not in ("construction", "heavy traffic"):
                    self.trip.note_limit_preannounced(ahead[0])
        elif ahead is None:
            self._keeper_ease_said = None
        context = self.trip.traffic_context()
        if context is not None and (
            context.gap_seconds <= KEEPER_GAP_SECONDS
            or (
                context.lead.speed_mph < target_mph
                # Once there is a reason to shed for it, on the keeper's own
                # ease law. Matching a slower vehicle the moment it is visible
                # meant matching one two and a half miles off (the traffic
                # bubble's whole reach), so a car doing 35 in a 45 work zone
                # put the truck at 35 from the far end of the zone with
                # nothing said. The stopped-queue case still lands here: a
                # standstill lead prices out at zero, and the gap to it is
                # inside anybody's window.
                and context.gap_mi
                <= self._keeper_ease_mi(context.lead.speed_mph, self.trip.effective_time_scale)
            )
        ):
            # Creep along with the queue, all the way down to a stop, and roll
            # again when it moves -- gates and work zones are queue country.
            target_mph = min(target_mph, context.lead.speed_mph)
        error = target_mph - t.speed_mph
        self._keeper_throttle = max(
            0.0, min(KEEPER_MAX_THROTTLE, self._keeper_throttle + error * 0.1 * dt)
        )
        if ahead is not None and t.speed_mph >= ahead[0]:
            # Easing toward a lower number: rebuild throttle under it freely,
            # never through it. The snub cycle deliberately rides a band
            # around the eased target (one application, held, released -- the
            # air model's price list), and on a compressed clock the
            # release-and-rebuild peak poked half a mile per hour over the
            # sign's own number right at the sign -- the keeper burning fuel
            # to defeat its own easing, and the 15.47-against-15 flake
            # (ROADMAP 2026-08-19). Coasting at the boundary caps the peak at
            # the number; the snub thresholds below it are untouched.
            self._keeper_throttle = 0.0
        t.throttle = self._keeper_throttle
        self._keeper_snub_brakes(dt, over=-error, target_mph=target_mph)

    def _take_new_posted_limit(self, limit: float, zone_reason: str) -> None:
        """Hand the keeper back up to street speed when the street changes.

        The keeper's number is the one it was given when it engaged, capped by
        the limit under the wheels -- so it comes DOWN with the road on its
        own, and used to have no way back UP. A facility approach is a chain of
        streets zoned one per leg (25 named, 15 unnamed service ways), so a
        session started on a service way held that crawl over every named
        street after it, for the whole chain, while the zone entry announced
        the higher number (tester report, access roads, 2026-08). The spoken
        promise is "holding X through the <reason> zone"; a new posted number
        is a new zone, and it takes it.

        Only ever upward, and only on a real change to the posted number: a
        driver who set a lower speed by hand keeps it as long as the street
        does, and coming down is already the cap's job.
        """
        if self._keeper_mph is None or limit == self._keeper_zone_limit:
            return
        self._keeper_zone_limit = limit
        if limit <= self._keeper_mph:
            return
        self._keeper_mph = limit
        easing = self._keeper_ease_target
        if easing is not None and easing[1] < limit:
            # Already shedding for something lower up the road, on a street
            # short enough that both land together. The ease line names the
            # number the truck will actually be doing; "holding 25" on top of
            # it is a promise contradicted in the same breath.
            return
        # An assist that speeds the truck up on its own has to say so: the
        # zone entry announced the law, not what the truck is about to do.
        # ROUTE, not the ambient default, for the same reason (automation-
        # handoff sweep, 2026-08-20, the deferred 2026-08-15 audit).
        spoken = (
            f"Speed keeper building to {self.ctx.settings.speed_text(limit)} for the merge."
            if zone_reason == "acceleration lane"
            else f"Speed keeper holding {self.ctx.settings.speed_text(limit)} "
            f"through the {zone_reason} zone."
        )
        self.ctx.say_event(
            spoken,
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.CONFIRMATION,
        )

    def _keeper_snub_brakes(self, dt: float, *, over: float, target_mph: float) -> None:
        """Work the drums in snubs to hold the keeper's target.

        One application, held until the truck is back under the number, then
        released -- never a trim that tracks the error up and down. The air
        model charges a whole application every time the pedal rises, so a
        hunting command is charged for hundreds of them; and a proportional
        term fades exactly as it approaches the target, so on a downgrade it
        settles wherever the fading command happens to balance gravity rather
        than ever arriving. Sizing the snub against the grade is what makes it
        arrive; holding it is what makes it affordable.
        """
        t = self.truck
        # Net of the grade: on the level this is a light application, and on a
        # downgrade it is however much more it takes to still take
        # KEEPER_SNUB_DECEL_MPS2 off the truck. Read every frame and allowed to
        # firm up mid-snub -- a snub sized once, on the grade under the wheels
        # when it started, holds that pedal onto a steepening hill and simply
        # accelerates against it.
        gravity_mps2 = max(0.0, -t.grade) * G
        wanted = min(
            KEEPER_SNUB_MAX_BRAKE,
            max(
                KEEPER_SNUB_MIN_BRAKE,
                (KEEPER_SNUB_DECEL_MPS2 + gravity_mps2) / assist_full_decel_mps2(t),
            ),
        )
        if self._keeper_snub > 0.0:
            if over <= -KEEPER_SNUB_UNDER_MPH:
                self._keeper_snub = 0.0  # under the number: let it go
            else:
                # Only ever firmer while the snub lasts. Easing and re-pressing
                # is what the air system charges for.
                self._keeper_snub = max(self._keeper_snub, wanted)
        elif over > KEEPER_SNUB_OVER_MPH:
            self._keeper_snub = wanted
        if self._keeper_snub > 0.0:
            t.throttle = 0.0  # never brake against our own throttle
            t.brake = max(t.brake, self._keeper_snub)
        # Pressing everything it has and still riding well over the number:
        # say so. An assist that quietly holds the wrong speed is the one
        # thing a driver who cannot see the speedometer cannot catch.
        maxed = self._keeper_snub >= KEEPER_SNUB_MAX_BRAKE - 1e-6
        if maxed and over > KEEPER_OVERRUN_MPH:
            self._keeper_overrun_s += dt
        else:
            self._keeper_overrun_s = 0.0
            if over <= 0.0:
                self._keeper_overrun_said = False
        if self._keeper_overrun_s >= KEEPER_OVERRUN_S and not self._keeper_overrun_said:
            self._keeper_overrun_said = True
            # Name the grade only where there is one: hot drums or ice take the
            # same authority away on level road, and blaming a hill the driver
            # is not on would send them looking for the wrong thing.
            because = " on this grade" if t.grade <= -0.01 else ""
            self.ctx.say_event(
                f"Speed keeper cannot hold {self.ctx.settings.speed_text(target_mph)}"
                f"{because}. Apply service brakes.",
                interrupt=True,
                category=SpeechCategory.SAFETY,
            )

    def _acc_gap_seconds(self) -> float:
        """Seconds of room adaptive cruise leaves to the vehicle ahead.

        The driver's chosen cushion is the floor; weather only ever adds to
        it. Someone who picked "close" on a clear day still gets the full
        wet-road opening when it rains, and someone who picked "far" never
        has it quietly shortened back to the middle.
        """
        chosen = ACC_GAP_CHOICES.get(self.ctx.settings.acc_following_gap, ACC_BASE_GAP_SECONDS)
        effects = self.weather.effects
        gap = chosen
        if effects.grip < 0.9:
            gap += (0.9 - effects.grip) * 4.2
        if effects.visibility_mi < 3.0:
            gap += (3.0 - effects.visibility_mi) * 0.5
        return min(6.0, max(chosen, gap))

    def _acc_weather_gap_text(self) -> str | None:
        effects = self.weather.effects
        if effects.grip < 0.9:
            return "Wet roads, adaptive cruise increasing following gap."
        if effects.visibility_mi < 3.0:
            return "Low visibility, adaptive cruise increasing following gap."
        return None

    def _acc_limit_lookahead_mi(self, speed_mph: float, target_mph: float) -> float:
        """Distance ACC needs to ease down to a specific lower limit."""
        speed_mps = max(0.0, speed_mph * 0.44704)
        target_mps = max(0.0, target_mph * 0.44704)
        if target_mps >= speed_mps:
            return ACC_LIMIT_LOOKAHEAD_MIN_MI
        braking_m = (speed_mps * speed_mps - target_mps * target_mps) / (
            2.0 * ACC_LIMIT_COMFORT_DECEL_MPS2
        )
        braking_mi = max(0.0, braking_m / 1609.344)
        return max(ACC_LIMIT_LOOKAHEAD_MIN_MI, min(ACC_LIMIT_LOOKAHEAD_MAX_MI, braking_mi + 0.25))

    def _acc_posted_limit_ahead(self) -> tuple[float, str | None]:
        """Lowest posted limit close enough that ACC should start slowing now."""
        start = self.trip.position_mi
        end = min(self.trip.total_miles, start + ACC_LIMIT_LOOKAHEAD_MAX_MI)
        lowest_limit, lowest_reason = self.trip.speed_limit_at(start)
        probe = start + ACC_LIMIT_LOOKAHEAD_STEP_MI
        while probe <= end + 1e-6:
            limit, reason = self.trip.speed_limit_at(probe)
            cap_mph = limit + ACC_LIMIT_OFFSET_MPH
            braking_mi = self._acc_limit_lookahead_mi(self.truck.speed_mph, cap_mph)
            if limit < lowest_limit and probe - start <= braking_mi:
                lowest_limit, lowest_reason = limit, reason
            probe += ACC_LIMIT_LOOKAHEAD_STEP_MI
        restricted = self._restricted_zone_limit_ahead()
        if restricted is not None and restricted[0] <= lowest_limit:
            return restricted[0], restricted[1]
        return lowest_limit, lowest_reason

    def _grade_samples(self, distance_mi: float) -> list[float]:
        """Grade every tenth of a mile over the road ahead.

        Real predictive cruise plans against a stored road profile a mile or
        two out (Volvo I-See, Detroit Intelligent Powertrain Management). The
        baked grade segments are the same thing at the same resolution -- a
        median half a mile, ninety-odd segments a leg -- so the preview is a
        straight read of data the trip already carries, no new bake.
        """
        start = self.trip.position_mi
        end = min(self.trip.total_miles, start + distance_mi)
        samples = []
        probe = start + PCC_PREVIEW_STEP_MI
        while probe <= end + 1e-6:
            samples.append(self.trip.grade_at(probe))
            probe += PCC_PREVIEW_STEP_MI
        return samples

    def _grade_preview(self, distance_mi: float = PCC_PREVIEW_MI) -> float:
        """Mean grade over the road ahead, or 0.0 with nothing to read.

        The crest test uses this on a short horizon: near the top, the road
        just ahead has already gone flat. Judged on the full preview instead,
        a three-mile pull read as cresting from a mile and a half out and the
        truck stopped recovering for half the hill (bench, 2026-07-25).
        """
        samples = self._grade_samples(distance_mi)
        return sum(samples) / len(samples) if samples else 0.0

    def _grade_extremes_ahead(self) -> tuple[float, float]:
        """Steepest sustained climb and descent inside the preview.

        Windowed rather than averaged over the whole preview: a half-mile
        four percent hill inside a mile and a half of otherwise flat road
        averages out to nothing, and short hills are exactly where banked
        momentum pays -- long enough to hurt, short enough that speed carried
        in still reaches the top (bench, 2026-07-25: averaging skipped the
        half-mile hills entirely). A window rather than a bare maximum so a
        single tenth-mile spike is not mistaken for a grade.
        """
        samples = self._grade_samples(PCC_PREVIEW_MI)
        window = max(1, int(round(PCC_GRADE_WINDOW_MI / PCC_PREVIEW_STEP_MI)))
        if len(samples) < window:
            return (0.0, 0.0) if not samples else (max(samples), min(samples))
        means = [sum(samples[i : i + window]) / window for i in range(len(samples) - window + 1)]
        return max(means), min(means)

    def _preview_grade_ahead(self) -> tuple[float, float] | None:
        """The first sustained grade inside the preview, and how far off it is.

        The same windowed read the preview plans against, so the G key and the
        preview cue describe one road. Predictive cruise banks momentum from
        one and a half percent up and the steep advisory only speaks at three,
        so the truck could say it was building speed for the grade ahead while
        G answered that nothing steep was coming for fifteen miles -- both
        true, and together they read as broken (tester report, 2026-08-15).
        """
        samples = self._grade_samples(PCC_PREVIEW_MI)
        window = max(1, int(round(PCC_GRADE_WINDOW_MI / PCC_PREVIEW_STEP_MI)))
        if len(samples) < window:
            return None
        means = [sum(samples[i : i + window]) / window for i in range(len(samples) - window + 1)]
        # The steepest window, not the first one over the bar: on the run into
        # Asheville the first was a 1.5 percent lift a mile out and the cue was
        # already building for the 3.7 percent pull behind it, so naming the
        # first put two different numbers on one hill (sweep, 2026-08-15).
        peak = max(range(len(means)), key=lambda i: abs(means[i]))
        if abs(means[peak]) < PCC_GRADE_MIN:
            return None
        sign = 1.0 if means[peak] > 0 else -1.0
        start = peak
        while start > 0 and means[start - 1] * sign >= PCC_GRADE_MIN:
            start -= 1
        return means[peak], (start + 1) * PCC_PREVIEW_STEP_MI

    def _predictive_cruise_bias(self, target_mph: float) -> float:
        """Speed to add or give up for the grade the truck is about to reach.

        Three behaviors, all of them what a real predictive system does:

        Bank momentum before a climb. Entering a pull two or three mph faster
        means carrying more speed the whole way up and holding a taller gear
        for longer -- the truck arrives at the top sooner having done the same
        work, instead of meeting the hill at exactly the set speed and
        immediately falling behind it.

        Give up the last few mph at a crest. Holding full throttle to the top
        of a pull buys seconds and costs a downshift that upshifts again over
        the summit; letting it sag inside a band leaves the truck in the gear
        it is already turning.

        Do not accelerate into a descent cruise is about to brake away. Speed
        added just before a downgrade comes straight back out through the
        retarder and the drums, which in this truck means real heat and real
        air -- so the preview shaves instead of adding.
        """
        if not self.ctx.settings.predictive_cruise:
            return 0.0
        # Following a lead, capped for a ramp or a bend, or already fighting a
        # lower posted limit: something closer than the horizon owns the speed.
        if self._acc_following or self._cruise_exit_mph is not None:
            return 0.0
        climb_ahead, descent_ahead = self._grade_extremes_ahead()
        here = self.truck.grade
        speed = self.truck.speed_mph
        if descent_ahead <= -PCC_GRADE_MIN and climb_ahead < PCC_GRADE_MIN:
            # A downgrade is coming and no pull stands between here and it.
            # Shave in proportion to how steep, so the truck rolls onto the
            # grade at or under the set speed instead of arriving over it and
            # spending the retarder to get back down.
            return -min(PCC_DESCENT_SHAVE_MPH, PCC_DESCENT_SHAVE_MPH * (-descent_ahead / 0.05))
        if here >= PCC_GRADE_MIN and self._grade_preview(PCC_CREST_WINDOW_MI) < PCC_GRADE_MIN:
            # On a pull whose top is inside the crest window. Stop reaching for
            # speed the summit is about to hand back for nothing: hold what
            # the truck has rather than spending the last of the climb at full
            # throttle recovering it, and taking a downshift to do it.
            #
            # It asks the truck to hold, never to slow: the bias can only ever
            # bring the target down to the speed already on the clock. An
            # earlier cut of this gave up a flat four mph and cost a 2 percent
            # pull three miles an hour it had been holding comfortably (bench,
            # 2026-07-25) -- the allowance is a ceiling on the giveaway, not
            # the giveaway itself.
            if speed < target_mph - 0.5:
                return max(-PCC_CREST_SAG_MPH, speed - target_mph)
            return 0.0
        if here < PCC_GRADE_MIN and climb_ahead >= PCC_GRADE_MIN:
            # Level ground now, a pull inside the preview: bank what the grade
            # is about to take. Scaled by the climb, capped so cruise never
            # reads as running away with the truck.
            return min(PCC_PREBUILD_MPH, PCC_PREBUILD_MPH * (climb_ahead / 0.04))
        return 0.0

    def _say_predictive_cruise(self, dt: float, bias: float) -> None:
        """Name what the preview is doing, once per hill and never terse.

        A truck that quietly runs three over and then sags four under reads as
        broken to a driver who cannot see the road ahead. Naming it once turns
        the same behavior into the system working. It is information, not
        safety, so terse speech keeps it.
        """
        self._pcc_cue_s = max(0.0, self._pcc_cue_s - dt)
        if bias > 0.5:
            phase = "building"
        elif bias < -0.5:
            phase = "easing"
        else:
            phase = ""
        if phase == self._pcc_phase:
            return
        self._pcc_phase = phase
        if not phase or self._terse_speech() or self._pcc_cue_s > 0.0:
            return
        self._pcc_cue_s = PCC_CUE_COOLDOWN_S
        if phase == "building":
            # Name the number. "The grade ahead" reads as a steep one, and the
            # G key -- which only calls a grade steep at three percent -- then
            # answered that nothing steep was coming for fifteen miles, which
            # is how a two percent pull looked like a bug (tester, 2026-08-15).
            climb_ahead, _ = self._grade_extremes_ahead()
            message = f"Building speed for a {climb_ahead * 100:.1f} percent upgrade ahead."
        else:
            message = "Easing off for the road ahead."
        self.ctx.say_event(message, interrupt=False, category=SpeechCategory.CONFIRMATION)

    def _descent_hold_mph(self) -> float:
        """The speed descent control is actually working to: set speed under
        the interactive level's safe ceiling."""
        target = self._cruise_mph or CRUISE_MIN_MPH
        if self._cruise_descent_mph is not None:
            target = min(target, self._cruise_descent_mph)
        return target

    def _update_cruise(
        self, dt: float, braking: bool, accelerating: bool, clutch_disengaged: bool
    ) -> None:
        """Hold speed when clear, and follow slower modeled traffic when present."""
        if self._cruise_mph is None:
            return
        t = self.truck
        # A limp-mode cap under the set speed is invisible from the seat: the
        # truck simply never reaches its number. Name it, once per engagement.
        self._announce_limp_cruise_cap()
        self._acc_follow_cue_s = max(0.0, self._acc_follow_cue_s - dt)
        self._descent_cue_s = max(0.0, self._descent_cue_s - dt)
        descent_level = self.ctx.settings.descent_speed_control
        descending = t.grade <= -0.025 and descent_level != "off"
        if descending and self._cruise_mph is not None:
            if braking and descent_level in ("balanced", "interactive"):
                self._descent_control_active = True
                new_target = max(CRUISE_MIN_MPH, t.speed_mph)
                should_announce = (
                    not self._descent_capture_active or abs(new_target - self._cruise_mph) >= 2.0
                )
                self._descent_capture_active = True
                self._cruise_mph = new_target
                # Capture pins the set speed to what the truck is doing now, so
                # the working setpoint follows it down rather than easing back
                # up toward a target the driver just abandoned.
                self._cruise_working_mph = new_target
                if should_announce:
                    self.ctx.say_event(
                        f"Descent target changed to {self.ctx.settings.speed_text(self._cruise_mph)}.",
                        interrupt=False,
                        category=SpeechCategory.CONFIRMATION,
                    )
                return
            self._descent_capture_active = False
            if not self._descent_control_active:
                self._descent_control_active = True
                # Rolling country crosses the descent trigger on every dip, so
                # the announcement needs a clock of its own or it becomes the
                # loudest thing on the road: four times in six minutes of
                # rollers on the bench (2026-07-25). The control still engages
                # every time; only saying so waits.
                if self._descent_cue_s <= 0.0 and not self._terse_speech():
                    self._descent_cue_s = DESCENT_CUE_COOLDOWN_S
                    # ROUTE, not the ambient default: names an automation that
                    # just took the brakes for a grade (automation-handoff
                    # sweep, 2026-08-20, the deferred 2026-08-15 audit).
                    self.ctx.say_event(
                        "Descent control holding "
                        f"{self.ctx.settings.speed_text(self._descent_hold_mph())}.",
                        interrupt=False,
                        priority=EventPriority.ROUTE,
                        category=SpeechCategory.CONFIRMATION,
                    )
            if not t.transmission.automatic and t.rpm < 1100:
                limit_state = "gear"
                limit_message = "Descent control needs a lower gear. Downshift now."
            elif t.grip < 0.55:
                limit_state = "traction"
                limit_message = "Low traction limits descent control. Apply brakes carefully."
            else:
                limit_state = ""
                limit_message = ""
                # The retarder is staged against the overspeed further down,
                # not pinned open here. Selecting all three stages the moment
                # the grade passed 2.5 percent over-retarded every descent
                # gentler than the one that balances full jake: a 4 percent
                # grade settled seven mph under the set speed and stayed
                # there, with cruise at full throttle fighting its own
                # engine brake (bench trace, 2026-07-25: 62 set, 54.9 held).
                if descent_level == "interactive":
                    # A cap that lives as long as the grade does, not a rewrite
                    # of the driver's set speed. It used to assign straight into
                    # _cruise_mph, so one 3 percent dip on a 65 road knocked
                    # cruise down to 55 permanently -- on the flat, uphill, the
                    # rest of the run (bench trace, 2026-07-25: 62 set, 55 held
                    # ever after). The driver's number now survives the hill.
                    self._cruise_descent_mph = DESCENT_SAFE_MAX_MPH
                    safe_target = min(self._cruise_mph, DESCENT_SAFE_MAX_MPH)
                    if t.speed_mph > safe_target + 8.0:
                        t.brake = max(t.brake, min(0.7, (t.speed_mph - safe_target) / 25.0))
                if t.speed_mph > self._descent_hold_mph() + 10.0:
                    limit_state = "grade"
                    limit_message = "Descent control cannot hold this grade. Apply service brakes."
            if limit_state != self._descent_limit_state:
                self._descent_limit_state = limit_state
                if limit_message:
                    self.ctx.say_event(
                        limit_message, interrupt=True, category=SpeechCategory.SAFETY
                    )
        elif self._descent_control_active:
            self._descent_control_active = False
            self._descent_limit_state = ""
            self._descent_capture_active = False
            self._cruise_descent_mph = None  # the grade is behind us; so is its cap
            # Release only the retarder cruise itself raised: the driver's own
            # jake switch survives the road levelling out.
            if self._cruise_jake_stage > 0:
                self._cruise_jake_stage = 0
                t.engine_brake_stage = 0
        if braking or t.emergency_brake or t.air_brakes_holding or not t.engine_on or t.stalled:
            self._cancel_cruise()
            # ROUTE, not the ambient default: the automation just released the
            # throttle (automation-handoff sweep, 2026-08-20, the deferred
            # 2026-08-15 audit).
            self.ctx.say_event(
                "Adaptive cruise canceled; automatic speed control off.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.CONFIRMATION,
            )
            return
        limit, zone_reason = self.trip.speed_limit_at(self.trip.position_mi)
        if zone_reason is not None and self._speed_control_armed and self.ctx.settings.speed_keeper:
            self._cancel_cruise(preserve_session=True)
            self._engage_keeper(limit, zone_reason, target_mph=limit, announce=False)
            # ROUTE, not the ambient default: cruise handing off to the
            # keeper is the automation changing which system holds the
            # throttle (automation-handoff sweep, 2026-08-20, the deferred
            # 2026-08-15 audit).
            self.ctx.say_event(
                f"{zone_reason.title()} zone. Speed keeper holding "
                f"{self.ctx.settings.speed_text(self._keeper_mph)}.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.CONFIRMATION,
            )
            return
        if accelerating:
            return  # manual override; cruise resumes when the key lifts
        if clutch_disengaged:
            # Clutch in / mid-shift: driveline is open, so any applied throttle
            # only free-revs the engine. Cut throttle to idle and hold the
            # integrator; the applied throttle ramps back up from zero once the
            # clutch engages again.
            t.throttle = 0.0
            self._cruise_applied = 0.0
            return
        # Ease the working setpoint toward the set speed at a bounded rate, in
        # both directions, and chase that rather than the set speed itself. A
        # resume to a far target climbs a couple of mph a second instead of
        # putting the whole error on the pedal at once; a drop in the set speed
        # backs off just as gently. Everything below still caps this working
        # target down for a lead, a ramp, a curve, a limit, or a grade.
        if self._cruise_working_mph is None:
            self._cruise_working_mph = max(CRUISE_MIN_MPH, min(self._cruise_mph, t.speed_mph))
        step = CRUISE_ACCEL_MPH_PER_S * dt
        if self._cruise_working_mph < self._cruise_mph:
            self._cruise_working_mph = min(self._cruise_mph, self._cruise_working_mph + step)
        elif self._cruise_working_mph > self._cruise_mph:
            self._cruise_working_mph = max(self._cruise_mph, self._cruise_working_mph - step)
        target_mph = self._cruise_working_mph
        exit_cap = self._ramp_approach_cap_mph()
        exit_capped = exit_cap is not None and exit_cap < target_mph
        if exit_capped:
            target_mph = exit_cap
        # A pacenote capped cruise for a bend: hold the advisory until the
        # curve's footprint is behind the truck, then climb back silently --
        # announcing every release would chant through a curve cluster.
        if (
            self._cruise_curve_end_mi is not None
            and self.trip.position_mi > self._cruise_curve_end_mi
        ):
            self._cruise_curve_mph = None
            self._cruise_curve_end_mi = None
        curve_capped = self._cruise_curve_mph is not None and self._cruise_curve_mph < target_mph
        if curve_capped:
            target_mph = self._cruise_curve_mph
        # Interactive descent control's safe ceiling, which lasts exactly as
        # long as the grade under the wheels.
        if self._cruise_descent_mph is not None and self._cruise_descent_mph < target_mph:
            target_mph = self._cruise_descent_mph
        # Predictive ACC: never carry the driver past the posted limit. With real
        # OSM limits baked per leg, a held set speed would otherwise sail through
        # urban drops and corridor limit changes straight into speeding strikes,
        # tickets, and trooper stops -- all of which now exist. The "Speed limit X"
        # cue still names the number; this cue says cruise is handling it.
        posted, limit_reason = self._acc_posted_limit_ahead()
        cap_mph = (
            posted if limit_reason in RESTRICTED_ZONE_REASONS else posted + ACC_LIMIT_OFFSET_MPH
        )
        # Measured against the working target, not the set speed, so this cap
        # can only ever lower it. Against the set speed it overwrote a stricter
        # ramp cap: cruise announced it was easing to 45 for the exit and then
        # held the 60 the posted limit allowed, missing the exit and costing
        # the driver a twenty-minute loop back.
        limit_capped = cap_mph < target_mph
        if limit_capped:
            # Take the lower of the two caps. A posted limit above ramp speed
            # must not undo an armed exit's cap and send the truck past its
            # ramp at the corridor limit.
            target_mph = min(target_mph, cap_mph)
            # Once per cap, not once per frame it happens to be in force. The
            # advance-warning window scales with speed, so as cruise slows for
            # a work zone the zone slips out of the window and back in, and a
            # plain on/off latch recited the same easing line all the way to
            # the barrels.
            if self._acc_limit_cap_said is None or cap_mph < self._acc_limit_cap_said - 0.5:
                self._acc_limit_cap_said = cap_mph
                reason = {
                    "construction": "Construction zone ahead",
                    "heavy traffic": "Heavy traffic ahead",
                }.get(limit_reason, "Posted limit lower")
                # ROUTE, not the ambient default. An assist saying it is
                # about to change how fast the truck is going is a
                # consequence, not colour -- the same reasoning that moved
                # the toll charge off the ambient channel. As AMBIENT this
                # was droppable as stale chatter, and it WAS dropped:
                # tester Darren's I-75 log, 2026-08-18, "[pacer] stale
                # ambient dropped: Construction zone ahead; adaptive cruise
                # easing to 45 miles per hour" -- seventeen seconds before
                # a trooper stopped him over the gap the easing was
                # closing. The truck slowed itself and never said why.
                self.ctx.say_event(
                    f"{reason}; adaptive cruise easing to {self.ctx.settings.speed_text(cap_mph)}.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.CONFIRMATION,
                )
                # This line already named the number for a plain posted-limit
                # drop; the arrival "Speed limit reduced to X" would otherwise
                # repeat it a moment (or, under compression, an instant)
                # later -- the owner's live-playtest complaint (2026-08-12).
                if limit_reason not in RESTRICTED_ZONE_REASONS:
                    self.trip.note_limit_preannounced(cap_mph)
        elif cap_mph >= self._cruise_mph:
            # Back out on the open road at the set speed: the next drop is
            # news again.
            self._acc_limit_cap_said = None
        self._acc_limit_capped = limit_capped
        # The weather's safe speed, enforced like any other road fact. The
        # number was computed and SPOKEN as guidance since live weather
        # shipped, and consumed by nothing: cruise held a set seventy
        # through a thunderstorm until the driver tapped it down by hand --
        # which is what the owner's own storm playtest was actually showing
        # (2026-08-20, Brandon's suggestion). Same once-per-cap latch as
        # the posted limit above; releases as the weather lifts.
        # Only weather that actually degrades the road caps: grip under 1.0
        # or meaningfully shortened sight lines. CLEAR and CLOUDY carry a 70
        # in safe_speed_mph as a GUIDANCE number for the status keys, and
        # capping at it made every 75-and-up western limit unreachable in
        # perfect weather (caught by the full sweep: a resume test stalled
        # at exactly 70.0).
        effects = self.weather.effects
        adverse = effects.grip < 1.0 or effects.visibility_mi < 8.0
        safe_mph = effects.safe_speed_mph
        if adverse and safe_mph < target_mph:
            target_mph = safe_mph
            if self._acc_weather_cap_said is None or safe_mph < self._acc_weather_cap_said - 0.5:
                self._acc_weather_cap_said = safe_mph
                kind = self.weather.current.value
                self.ctx.say_event(
                    f"{kind.capitalize()}; adaptive cruise easing to "
                    f"{self.ctx.settings.speed_text(safe_mph)}.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.CONFIRMATION,
                )
        elif safe_mph >= self._cruise_mph:
            # Weather no longer binds at this set speed: the next front is
            # news again.
            self._acc_weather_cap_said = None
        # The preview goes on last so it can only ever move the number the
        # caps already agreed on, and it is clamped against the posted cap:
        # banking momentum for a hill must never bank it past the limit.
        bias = self._predictive_cruise_bias(target_mph)
        self._say_predictive_cruise(dt, bias)
        if bias:
            target_mph = max(CRUISE_MIN_MPH, min(target_mph + bias, cap_mph))
        context = self.trip.traffic_context()
        following = False
        if context is not None:
            desired_gap = self._acc_gap_seconds()
            reason = self._acc_weather_gap_text()
            if (
                reason
                and not self._acc_weather_gap_said
                and context.gap_seconds <= desired_gap + 1.5
            ):
                self._acc_weather_gap_said = True
                self.ctx.say_event(
                    reason,
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.CONFIRMATION,
                )
            lead_mph = context.lead.speed_mph
            if (
                lead_mph <= 5.0
                and not self.ctx.settings.stop_and_go_assist
                and context.closing_mph > 0.5
                and context.gap_mi / context.closing_mph * 3600.0 <= ACC_STOPPED_CANCEL_S
            ):
                self._cancel_cruise()
                # Handing the truck back is the least droppable line the
                # assist has: a driver who does not hear it believes the
                # cruise is still holding the gap.
                self.ctx.say_event(
                    "Stopped traffic ahead; adaptive cruise canceled.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.SAFETY,
                )
                return
            # Approach control: a slower lead constrains the target only once the
            # gap actually matters. Distance beyond the desired gap converts to
            # allowed closing speed at a gentle planned deceleration, so the truck
            # closes smoothly and settles onto the lead's speed at the desired
            # gap. A slower vehicle merely existing in the traffic bubble must
            # not drag the target down: matching a distant lead's speed parks the
            # truck at the bubble edge, where the lead drifts in and out of range
            # and the follow cue re-announces itself forever.
            headway_mi = desired_gap * max(lead_mph, 5.0) / 3600.0
            approach_m = max(0.0, context.gap_mi - headway_mi) * 1609.344
            closing_allowed_mph = (2.0 * ACC_FOLLOW_DECEL_MPS2 * approach_m) ** 0.5 * MPH_PER_MPS
            follow_mph = lead_mph + closing_allowed_mph
            if follow_mph < target_mph - 0.5 or context.gap_seconds <= desired_gap + 1.0:
                target_mph = min(target_mph, follow_mph)
                following = True
        if following and not self._acc_following and self._acc_follow_cue_s <= 0.0:
            self._acc_follow_cue_s = ACC_FOLLOW_CUE_COOLDOWN_S
            self.ctx.audio.play("ui/notify", volume=0.55)
            self.ctx.say_event(
                "Traffic ahead, adaptive cruise reducing speed.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.CONFIRMATION,
            )
        self._acc_following = following
        error = target_mph - t.speed_mph
        # Feed-forward first: the truck's own physics knows what throttle
        # balances the grade under the wheels, so cruise answers a hill as it
        # arrives. P and I only trim from there.
        hold = t.hold_throttle()
        trim = max(
            -CRUISE_TRIM_LIMIT,
            min(CRUISE_TRIM_LIMIT, self._cruise_trim + error * CRUISE_I_GAIN * dt),
        )
        if error < 0.0:
            # Over the target, cruise comes off the fuel: feeding the grade-hold
            # value into a truck that also needs to lose speed is a truck
            # fighting itself, and the speeding-strike grace only forgives a
            # cruise genuinely off the throttle. Eased out across a band rather
            # than switched -- a hard cut at the boundary chattered the pedal on
            # and off at steady state, and the engine voice shows every bit of
            # that.
            hold *= max(0.0, 1.0 + error / CRUISE_COAST_MPH)
            if error <= -CRUISE_COAST_MPH:
                trim = min(0.0, trim)
        demand = hold + error * CRUISE_P_GAIN + trim
        # Off the throttle as the engine nears the governor. On a downgrade
        # gravity does the accelerating, and cruise adding fuel into a coupled
        # RPM already climbing toward redline is what over-revved the engine
        # and charged wear during the automatic box's between-shift hold. Taper
        # demand to nothing across the top of the RPM range so descent control
        # and the retarder own the grade and cruise simply lifts -- it never
        # fights the retarder, it just stops feeding the over-rev.
        ceiling_rpm = self.truck.specs.max_rpm
        band = ceiling_rpm * CRUISE_RPM_CEILING_BAND
        ceiling_factor = (
            1.0 if band <= 0.0 else max(0.0, min(1.0, (ceiling_rpm - t.coupled_rpm()) / band))
        )
        demand *= ceiling_factor
        # Anti-windup: a grade the engine cannot pull, or a downgrade gravity
        # owns, pins the pedal at one end for as long as it lasts. Integrating
        # through that buries the trim at its limit, and the truck then sags or
        # overshoots for seconds after the road levels out while it unwinds.
        # Only take the new trim when it can still move the pedal -- and the RPM
        # ceiling holding the pedal down counts as pinned just as much as the
        # floor or the roof does.
        saturated = (
            (demand <= 0.0 and error < 0.0)
            or (demand >= 1.0 and error > 0.0)
            or (ceiling_factor < 1.0 and error > 0.0)
        )
        if not saturated:
            self._cruise_trim = trim
        self._cruise_throttle = max(0.0, min(1.0, demand))
        # Ramp the applied throttle up to the held integrator value rather than
        # snapping, so cruise eases back in after a clutch release; drops (traffic
        # or a lower limit) still apply immediately. On a steady frame the applied
        # throttle already equals _cruise_throttle, so this holds as before.
        if self._cruise_throttle > self._cruise_applied:
            load_fraction = min(1.0, max(0.0, t.cargo_kg / REFERENCE_CARGO_KG))
            recovery_rate = 0.7 + 0.8 * (1.0 - load_fraction)
            recovery_rate += min(0.6, max(0.0, error) / 15.0)
            self._cruise_applied = min(
                self._cruise_throttle,
                self._cruise_applied + dt * recovery_rate,
            )
        else:
            self._cruise_applied = self._cruise_throttle
        t.throttle = self._cruise_applied
        self._say_cruise_out_of_truck(dt, error)
        # Every reason the working target sits below the set speed except one
        # is a target speed to arrive at, and the drums are what arrive: a
        # lead vehicle, an armed exit's ramp cap, a lower posted limit or a
        # construction zone, and now a bend's advisory. The exception is a
        # grade, which is sustained speed control and the retarder's own job
        # -- so a bend on a downgrade still retards, because that is the
        # grade's doing and not the corner's. See _on_downgrade for the rule
        # and _update_lane for the same rule in the curve assist.
        self._hold_cruise_from_above(
            dt,
            error,
            closing=following
            or limit_capped
            or exit_capped
            or (curve_capped and not self._on_downgrade()),
        )

    def _say_cruise_out_of_truck(self, dt: float, error: float) -> None:
        """Say plainly when the hill has beaten cruise.

        The descent side has said "cannot hold this grade" for a while; the
        climb side said nothing at all, so the truck just quietly sank. A
        sighted driver reads that off the tach in a second. A blind driver has
        the engine note and the downshifts, which say the truck is working but
        not that it is losing -- and losing is the part that decides whether to
        take it over by hand.

        Only once the pedal is genuinely on the floor and the truck is still
        falling past the droop band, so a normal pull that cruise recovers
        from on its own stays quiet.
        """
        self._climb_cue_s = max(0.0, self._climb_cue_s - dt)
        t = self.truck
        # error is target minus speed, so a positive error is the truck
        # sitting below the number cruise is working to. The three ported
        # guards (see CRUISE_GRADE_BEATEN_* in driving_core): a real grade,
        # not mid-shift, and the condition holding rather than one frame.
        beaten = (
            self._cruise_applied >= CRUISE_FLOORED_THROTTLE
            and t.grade * 100.0 >= CRUISE_GRADE_BEATEN_PCT
            and error > CRUISE_DROOP_MPH
        )
        if not beaten:
            self._climb_beaten_s = 0.0
            if error < CRUISE_DROOP_MPH * 0.5:
                self._climb_cue_said = False  # back on its number: arm again
            return
        if t.transmission.shifting:
            return  # an open driveline is no evidence either way; hold the count
        self._climb_beaten_s += dt
        if self._climb_beaten_s < CRUISE_GRADE_BEATEN_S:
            return
        if self._climb_cue_said or self._climb_cue_s > 0.0 or self._terse_speech():
            return
        self._climb_cue_said = True
        self._climb_cue_s = CLIMB_CUE_COOLDOWN_S
        self.ctx.say_event(
            "Cruise is flat out and still losing the grade. "
            f"Holding {self.ctx.settings.speed_text(t.speed_mph)}.",
            interrupt=False,
            category=SpeechCategory.STATUS,
        )

    def _hold_cruise_from_above(self, dt: float, error: float, *, closing: bool) -> None:
        """Bring the truck back down to the target: retarder first, drums last.

        Cutting fuel was cruise's whole answer to being over the target, which
        works on the flat and fails on every downgrade. Anything gentler than
        the descent assist's 2.5 percent trigger got no retarder at all, so
        gravity carried the truck past the set speed and simply held it there
        -- and the service brake only ever came out while a cap or a lead was
        already pulling the target down. Cruise now stages the retarder against
        the overspeed rather than leaving it off or pinning it open.

        Closing on a lead, easing down to a lower posted limit, or shedding
        speed for a bend or a ramp keeps the old proportional service-brake
        trim and no retarder at all. That is deliberate: each of those is a
        target speed to arrive at, which wants the precise control only the
        drums give, and the jake is a loud device besides -- reaching for it
        on every piece of traffic would put a stage change in the player's
        ears several times a mile for a job the drums do quietly.
        """
        t = self.truck
        over = -error
        self._cruise_jake_cooldown_s = max(0.0, self._cruise_jake_cooldown_s - dt)
        if closing:
            if over > 2.0:
                weather_brake = 0.45 if self.weather.effects.grip < 0.7 else 0.65
                t.brake = max(t.brake, min(weather_brake, over / 30.0))
            # Hand the speed over cleanly: give back a retarder cruise itself
            # raised on the grade that has just run out, rather than letting
            # it ride on into the bend or the queue. On a real downgrade it
            # stays up -- there the retarder is holding the truck, and
            # dropping it puts the whole grade onto the drums. The driver's
            # own jake switch is never touched.
            if self._cruise_jake_stage > 0 and not self._on_downgrade():
                self._cruise_jake_stage = 0
                t.engine_brake_stage = 0
            self._cruise_snubbing = False
            return
        if self._auto_jake:
            # The driver put the AMT retarder manager in charge with J; it
            # already holds the descent target. Two owners would fight.
            return
        # Cruise reaches for the retarder only where a real one would: the
        # engine-brake stalk has to permit it. Descent control set to off is
        # the driver saying they manage grades themselves, and a real truck's
        # cruise does not flip the stalk on for you. Town no-engine-brake
        # zones close the stalk too (unless a real downgrade exempts them --
        # see driving_engine_brake). The drums below still answer either way,
        # so losing the retarder never costs the ability to hold the speed.
        # Only on a real downgrade -- which is _on_downgrade's own doctrine,
        # written on the predicate and never consulted here: holding a load
        # back on a grade is what the retarder is built for; slowing to a
        # target -- a storm's safe speed, a zone, a lead -- is the drums'
        # job. Without this gate the governor raised the jake wherever
        # overspeed appeared: on flat soaked I-24 for a thunderstorm ease
        # (owner playtest, 2026-08-20), and on UPGRADES, barking away speed
        # that the climb itself was about to eat -- the opposite of what a
        # real driver does with a hill in front of the hood (Brandon,
        # 2026-08-20). The slick-surface question resolves itself: no flat
        # raises means no storm-ease raises, and a retarder already holding
        # a real grade stays up, wet or dry, because dropping it puts the
        # whole hill onto the drums.
        may_retard = (
            self.ctx.settings.descent_speed_control != "off"
            and self._assist_jake_allowed()
            and self._on_downgrade()
        )
        wanted = 0
        if may_retard and over > CRUISE_JAKE_OVER_MPH and t.throttle <= 0.05:
            steps = int((over - CRUISE_JAKE_OVER_MPH) / CRUISE_JAKE_STEP_MPH)
            wanted = min(JAKE_STAGES, 1 + steps)
        elif may_retard and over > CRUISE_JAKE_RELEASE_MPH:
            wanted = self._cruise_jake_stage  # inside the deadband, hold
        wanted = min(wanted, max(0, self._auto_jake_max_stage()))
        # Never reach for a retarder the driver's own jake switch is holding,
        # and never release one either -- only what cruise raised itself.
        driver_owns_jake = self._cruise_jake_stage == 0 and t.engine_brake_stage > 0
        if wanted != self._cruise_jake_stage and not driver_owns_jake:
            # Stage changes wait out a cooldown so a rolling grade does not
            # make the retarder chatter -- it is a loud device. Coming off it
            # because the truck has fallen under the target goes through at
            # once: holding retard the truck no longer needs is what drags it
            # below the speed cruise is supposed to be keeping.
            releasing_under_target = wanted == 0 and over < -CRUISE_JAKE_RELEASE_MPH
            if releasing_under_target or self._cruise_jake_cooldown_s <= 0.0:
                self._cruise_jake_stage = wanted
                t.engine_brake_stage = wanted
                self._cruise_jake_cooldown_s = CRUISE_JAKE_STEP_S
        # Holding a grade. The drums only come out once the retarder is doing
        # everything it can -- or once it is clear there is no retarder coming,
        # which is the whole of it when the stalk is off -- and then as a snub
        # that finishes and lets go.
        jake_ceiling = min(JAKE_STAGES, self._auto_jake_max_stage()) if may_retard else 0
        jake_maxed = self._cruise_jake_stage >= max(1, jake_ceiling) or jake_ceiling <= 0
        if self._cruise_snubbing:
            self._cruise_snubbing = over > -CRUISE_SNUB_UNDER_MPH
        elif jake_maxed and over > CRUISE_BRAKE_OVER_MPH:
            self._cruise_snubbing = True
        if self._cruise_snubbing:
            weather_brake = 0.45 if self.weather.effects.grip < 0.7 else 0.65
            t.brake = max(t.brake, min(weather_brake, CRUISE_SNUB_BRAKE))

    def _handle_out_of_fuel(self) -> None:
        if self._rescue_offered:
            return
        self._rescue_offered = True
        p = self.ctx.profile
        fee = 750.0
        if player_pays_operating_costs(p.business_status):
            p.money -= fee  # can go negative: the rescue is not optional
            billing = f"for {fee:,.0f} dollars"
        else:
            # the carrier pays for company fuel, but a preventable service
            # call goes straight onto the driver's record
            p.career.reputation = max(0.0, p.career.reputation - 2.0)
            billing = "on the carrier account, and dispatch noted the service call"
        self.truck.refuel(30.0)
        self.truck.recover_from_fuel_depletion()
        self._cancel_cruise()
        self._rescue_offered = False
        self.ctx.audio.play("ui/error")
        # A repair bill and an instruction, spoken to a truck already coasted
        # to a stop: nothing act-now left, so it queues on ROUTE's
        # never-dropped contract instead of purging the channel.
        self.ctx.say_event(
            f"You ran out of fuel. Roadside rescue brought thirty "
            f"gallons {billing}. Press "
            f"{self.ctx.control_hint('engine')} to restart "
            "the engine, and plan your fuel stops.",
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.MONEY,
        )

    def _arrive(self) -> None:
        self.ctx.replace_state(ArrivalState(self.ctx, self))

    def _handle_missed_destination_exit(self) -> None:
        exit_details = self._destination_exit_details(include_past=True)
        self.trip.finished = False
        self._exit_stop = None
        self._exit_signal_on = False
        self._exit_signal_canceled = False
        self._cancel_cruise()
        if exit_details is not None:
            exit_at = exit_details[0]
        else:
            # Rural approaches carry no baked interchange, so the details
            # scan finds nothing -- but the exit the player just missed was
            # the synthetic one _destination_exit_stop places a mile before
            # route end, and the loop-back must return to it. Without this
            # the second miss stranded the trip at 0 miles remaining with
            # no exit left to signal for (owner playtest, Sedona to Camp
            # Verde on AZ-260, 2026-07-18).
            exit_at = max(0.0, self.trip.total_miles - DESTINATION_EXIT_BEFORE_END_MI)
        # Every miss loops back. The say-once latch must never swallow
        # this reposition: when it did, the second miss stranded the trip
        # pinned at the end of the route with no exit left to signal for,
        # cruise dying every frame (playtest transcript, 2026-07-16).
        self._missed_destination_exit_said = True
        self.trip.game_minutes += EXIT_MISS_LOOP_MIN
        # The loop-back is a real drive: hours, fatigue, and idle fuel move
        # with the clock, exactly as the facility-gate miss charges them.
        self._charge_scripted_loop(EXIT_MISS_LOOP_MIN)
        # Drop back a full exit window, not a fixed mile: under time
        # compression one mile passes in a few real seconds, making the
        # re-approach unwinnable before it was heard.
        self.trip.position_mi = max(0.0, exit_at - self._exit_window_mi())
        self._destination_exit_announced_key = None
        self._destination_exit_response_s = 0.0
        self._destination_exit_cache = None
        if self._terse_speech():
            # The signal reset with the miss; when the lane work is theirs, terse
            # players still need to hear that arming it is on them again.
            reroute_text = "Safe turnaround. Destination exit ahead again."
            if self.ctx.settings.lane_is_manual():
                reroute_text = (
                    "Safe turnaround. Destination exit ahead again; press "
                    f"{self.ctx.control_hint('take_exit')} to signal."
                )
        else:
            reroute_text = (
                "You continue to the next safe turnaround and loop back onto "
                "the approach. The destination exit is ahead again; press "
                f"{self.ctx.control_hint('take_exit')} "
                "when you are close enough to take it."
            )
        self.ctx.audio.play("ui/warning")
        self._set_status("Destination exit missed. Use the next safe turnaround.")
        # A mandatory-stop miss, not an optional one: the route just changed
        # and this names the maneuver that still gets the load delivered, so
        # it must survive quiet/urgent_only as words, not an earcon blip.
        self.ctx.say_event(
            f"You missed the destination exit for {self._destination_facility_text()}. "
            f"{reroute_text}",
            interrupt=True,
            category=SpeechCategory.NAVIGATION,
        )

    def _handle_arrival_gate(self) -> None:
        if self.ctx.settings.destination_approach_assist:
            self._cancel_cruise()
            self.truck.throttle = 0.0
            self.truck.brake = 1.0
            if self.truck.speed_mph <= 0.5 and not self._arrival_full_stop_said:
                self._arrival_full_stop_said = True
                self.truck.set_parking_brake()
                self.ctx.say_event(
                    "Destination approach stopped and holding. Press Enter, or controller A, to continue into the facility.",
                    interrupt=True,
                    category=SpeechCategory.NAVIGATION,
                )
            return
        if self.truck.speed_mph <= DOCKING_MAX_MPH:
            self._open_facility_arrival()
            return
        if self.truck.speed_mph <= DELIVERY_PARK_MPH:
            self._handle_arrival_creep()
            return
        # Above the gate zone's posted limit with the warning heard and the
        # reaction window spent: the entrance is missed, not still ahead.
        # (See driving_facility_gate.py; the assist branch above brakes the
        # truck itself and must never reach this.)
        if self._gate_miss_pending():
            self._handle_missed_facility_gate()
            return
        if self._arrival_stop_said:
            self._remind_arrival_gate(
                "Destination gate: stop to dock.",
                f"At {self._destination_facility_text()}. Stop to dock."
                if self._terse_speech()
                else (
                    f"Still at {self._destination_facility_text()}. The delivery "
                    "is here, not ahead: slow down and stop to dock."
                ),
            )
            return
        self._arrival_stop_said = True
        self._gate_reminder_s = GATE_REMINDER_INTERVAL_S
        self._cancel_cruise()
        self.ctx.audio.play("ui/warning")
        self._set_status("Destination ahead: slow down and come to a complete stop.")
        message = (
            f"Destination ahead: {self._destination_facility_text()}."
            if self._terse_speech()
            else (
                f"Destination ahead: {self._destination_facility_text()}. "
                "Slow down and come to a complete stop at the gate."
            )
        )
        self._seed_gate_grace_at_gate(message)
        self.ctx.say_event(message, interrupt=True, category=SpeechCategory.NAVIGATION)

    def _remind_arrival_gate(self, status: str, message: str, *, pickup: bool = False) -> None:
        """Repeat a gate's stop instruction while the truck rolls past it.

        The gate warnings latch after speaking once, which is right for a
        driver who is slowing -- but a driver who rolls on hears nothing
        again for the rest of the drive, with any re-armed cruise happily
        holding highway speed at a dead-end. Re-speak on a calm cadence and
        drop the cruise each time; the reminder stops the moment the truck
        slows into the gate's own creep-and-dock flow.
        """
        if self._gate_reminder_s > 0.0:
            return
        self._gate_reminder_s = GATE_REMINDER_INTERVAL_S
        if pickup:
            self._pause_speed_control()
        else:
            self._cancel_cruise()
        self.ctx.audio.play("ui/warning")
        self._set_status(status)
        self.ctx.say_event(message, interrupt=True, category=SpeechCategory.NAVIGATION)

    def _arrival_gate_query_text(self) -> str | None:
        """The gate's instruction when the trip has ended at one, else None.

        Mirrors the update loop's gate dispatch so the info keys agree with
        what the gate handlers are actually waiting for.
        """
        if not self.trip.finished or self._arrival_menu_open or self._departure_chain:
            return None
        if self.phase == DRIVE_PHASE_PICKUP:
            return f"At {self._pickup_facility_text()}. Stop to check in."
        if self._ramp_mi is not None or not self._destination_exit_taken:
            return None
        return f"At {self._destination_facility_text()}. Stop to dock."

    def _handle_arrival_creep(self) -> None:
        if self._arrival_full_stop_said:
            return
        self._arrival_full_stop_said = True
        self._cancel_cruise()
        self.ctx.audio.play("ui/notify", volume=0.7)
        self._set_status("Destination gate: stop to dock.")
        self.ctx.say_event(
            f"At {self._destination_facility_text()}. Stop to dock.",
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.NAVIGATION,
        )

    def _open_facility_arrival(self) -> None:
        if self._arrival_menu_open:
            return
        self._arrival_menu_open = True
        self._cancel_cruise()
        self.truck.brake = 1.0
        self.truck.set_parking_brake()
        # A dock gate is a menu-driven stop like a roadside inspection: the
        # frame loop that eases revs down between frames stops the instant
        # the dock menu takes over, so without this the engine audio froze
        # at whatever rev the approach left it at, all the way through the
        # stop.
        self._settle_engine_to_idle()
        _advance_rest_clock(self, STOP_PULL_IN_MIN)
        self.hos.on_duty(STOP_PULL_IN_MIN)
        self._set_status("Pulling into destination. Dock menu opening.")

        def complete() -> None:
            self._set_status("Parked at destination. Dock and deliver.")
            self.ctx.replace_state(FacilityArrivalState(self.ctx, self))

        self.ctx.replace_state(
            TimedMessageState(
                self.ctx,
                title="Pulling into destination",
                message=(
                    f"Pulling into {self._destination_facility_text()}. "
                    "Brakes set; dock menu opening in a moment."
                ),
                status="Pulling into the destination facility. Please wait.",
                seconds=STOP_PULL_IN_WAIT_S,
                on_complete=complete,
                sound_key="ui/notify",
            )
        )

    def _destination_facility_text(self) -> str:
        return self.job.destination_facility_text()

    def _objective_text(self) -> str:
        if self.phase == DRIVE_PHASE_PICKUP:
            return "pickup at " + self._pickup_facility_text()
        return "deliver to " + self._destination_facility_text()

    def _set_status(self, text: str) -> None:
        self._status_text = text

    def presence(self):
        from ..discord_presence import driving_presence
        from ..models.trucks import TRUCK_CATALOG

        total = self.trip.total_miles or 1.0
        fraction = self.trip.position_mi / total
        moving = self.truck.speed_mph >= 1.0
        truck = TRUCK_CATALOG.get(self.ctx.profile.truck) if self.ctx.profile else None
        return driving_presence(
            phase=self.phase,
            origin=self.job.spoken_origin,
            destination=self.job.spoken_destination,
            cargo=self.job.cargo.label,
            fraction=fraction,
            moving=moving,
            truck_label=truck.label if truck else "",
        )

    def online_presence(self):
        # The drivers board line adds what the cab radio is playing; Discord
        # presence (above) does not, so the clause rides only the board copy.
        # Station display names are curated public catalog data (call sign and
        # name), never a stream URL, and the clause disappears the moment the
        # radio is switched off -- the board only ever hears what a passenger
        # in the cab would.
        base = self.presence()
        if base is None or not self.radio.enabled:
            return base
        from ..discord_presence import PresenceState

        clause = f"listening to {self.radio.current_station().display_name}"
        detail = f"{base.detail}, {clause}" if base.detail else clause
        return PresenceState(base.activity, detail)

    def lines(self) -> list[str]:
        t = self.truck
        limit, reason = self.trip.speed_limit_at(self.trip.position_mi)
        gear = "N" if t.transmission.in_neutral else str(t.transmission.gear)
        title = (
            f"Deadheading to pickup at {self._pickup_facility_text()}"
            if self.phase == DRIVE_PHASE_PICKUP
            else f"Driving loaded to {self.job.spoken_destination}"
        )
        s = self.ctx.settings
        decimals = 1 if self.phase == DRIVE_PHASE_PICKUP else 0
        remaining = (
            f"{s.distance_value(self.trip.remaining_miles, decimals)} of "
            f"{s.distance_value(self.trip.total_miles, decimals)} {s.distance_unit_text()}"
        )
        return [
            title,
            "",
            f"Speed: {s.hud_speed_text(t.speed_mph)} "
            f"(limit {s.distance_value(limit)}{', ' + reason if reason else ''})"
            f"   Lane: {self.lane.lane_name}",
            f"Gear: {gear}   RPM: {t.rpm:.0f}   {'ENGINE ON' if t.engine_on else 'engine off'}"
            + (f"   CRUISE {self._cruise_mph:.0f}" if self._cruise_mph is not None else ""),
            f"Air: {t.air_pressure_psi:.0f} psi   "
            f"{'LOW AIR' if t.air_low_warning else 'air ready' if t.air_ready else 'building'}   "
            f"{'spring brakes' if t.spring_brakes_active else 'parking set' if t.parking_brake else 'parking released'}",
            f"Fuel: {t.fuel_fraction * 100:.0f}%   Damage: {t.damage_pct:.0f}%",
            f"Remaining: {remaining}",
            f"Weather: {self.weather.current.value}",
            f"Date: {self._calendar_phrase() or 'unknown'}",
            f"Clock: {clock_text(self.trip.local_hour)} "
            f"{self.trip.current_timezone.name} "
            f"({time_of_day(self.trip.local_hour)})   "
            f"Fatigue: {self.ctx.profile.fatigue:.0f}%",
            "",
            self._status_text,
        ]
