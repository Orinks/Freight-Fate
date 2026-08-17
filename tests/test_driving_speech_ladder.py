"""The S4 driving verbosity ladder: rungs cut categories, not word counts.

The rung table is pinned as data so that changing what a rung silences is a
visible diff in this file rather than a behaviour surprise on the road.
"""

from __future__ import annotations

import pytest
from speech_capture import speech_stub

from freight_fate.settings import Settings
from freight_fate.sim.trip_models import TripEvent, TripEventKind
from freight_fate.speech_pacing import (
    DRIVING_SPEECH_DISPOSITIONS,
    DRIVING_SPEECH_MODES,
    LADDER_EARCONS,
    Disposition,
    EventSpeechPacer,
    SpeechCategory,
    disposition_for,
)
from freight_fate.states.driving_events import _EVENT_CATEGORIES, _FLAVOR_EVENT_KINDS


class _FakeClock:
    """A controllable clock for the pacer, so a key= test can advance real
    seconds between two calls without a real sleep -- matching how a
    standing condition actually changes seconds apart, not in the same
    instant, and avoiding the anti-backlog projection (an unrelated pacer
    concern) mistaking a same-instant follow-up for a stale AMBIENT line."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_ladder_has_four_named_rungs() -> None:
    assert DRIVING_SPEECH_MODES == ("coaching", "standard", "quiet", "urgent_only")


def test_every_rung_rules_on_every_category() -> None:
    for mode in DRIVING_SPEECH_MODES:
        for category in SpeechCategory:
            assert disposition_for(mode, category) in set(Disposition)


@pytest.mark.parametrize("mode", DRIVING_SPEECH_MODES)
@pytest.mark.parametrize("category", [SpeechCategory.SAFETY, SpeechCategory.MONEY])
def test_safety_and_money_speak_at_every_rung(mode: str, category: SpeechCategory) -> None:
    # R1's never-dropped contract outranks the ladder. A rung may shorten
    # these; it may never silence them.
    assert disposition_for(mode, category) in (Disposition.FULL, Disposition.TERSE)


@pytest.mark.parametrize("mode", DRIVING_SPEECH_MODES)
def test_an_untagged_line_speaks_at_every_rung(mode: str) -> None:
    # A call site nobody has classified yet must be too loud, never silent.
    assert disposition_for(mode, None) in (Disposition.FULL, Disposition.TERSE)


def test_the_table_reads_exactly_as_the_spec_says() -> None:
    assert DRIVING_SPEECH_DISPOSITIONS["coaching"] == {
        SpeechCategory.SAFETY: Disposition.FULL,
        SpeechCategory.MONEY: Disposition.FULL,
        SpeechCategory.NAVIGATION: Disposition.FULL,
        SpeechCategory.COACHING: Disposition.FULL,
        SpeechCategory.CONFIRMATION: Disposition.FULL,
        SpeechCategory.STATUS: Disposition.FULL,
    }
    assert DRIVING_SPEECH_DISPOSITIONS["standard"] == {
        SpeechCategory.SAFETY: Disposition.FULL,
        SpeechCategory.MONEY: Disposition.FULL,
        SpeechCategory.NAVIGATION: Disposition.FULL,
        SpeechCategory.COACHING: Disposition.FIRST_OCCURRENCE,
        SpeechCategory.CONFIRMATION: Disposition.FULL,
        SpeechCategory.STATUS: Disposition.TRANSITIONS,
    }
    assert DRIVING_SPEECH_DISPOSITIONS["quiet"] == {
        SpeechCategory.SAFETY: Disposition.TERSE,
        SpeechCategory.MONEY: Disposition.TERSE,
        SpeechCategory.NAVIGATION: Disposition.TERSE,
        SpeechCategory.COACHING: Disposition.EARCON,
        SpeechCategory.CONFIRMATION: Disposition.EARCON,
        SpeechCategory.STATUS: Disposition.EARCON,
    }
    assert DRIVING_SPEECH_DISPOSITIONS["urgent_only"] == {
        SpeechCategory.SAFETY: Disposition.TERSE,
        SpeechCategory.MONEY: Disposition.TERSE,
        SpeechCategory.NAVIGATION: Disposition.TERSE,
        SpeechCategory.COACHING: Disposition.SILENT,
        SpeechCategory.CONFIRMATION: Disposition.EARCON,
        SpeechCategory.STATUS: Disposition.SILENT,
    }


def test_an_unknown_rung_falls_back_to_standard() -> None:
    assert disposition_for("nonsense", SpeechCategory.STATUS) == Disposition.TRANSITIONS


def test_the_default_rung_is_standard() -> None:
    assert Settings().driving_speech == "standard"


def test_a_saved_terse_player_lands_on_quiet() -> None:
    s = Settings.from_dict({"speech_verbosity": 0})
    assert s.driving_speech == "quiet"


def test_a_saved_normal_player_lands_on_standard() -> None:
    s = Settings.from_dict({"speech_verbosity": 1})
    assert s.driving_speech == "standard"


def test_a_nonsense_saved_verbosity_lands_on_standard() -> None:
    s = Settings.from_dict({"speech_verbosity": 7})
    assert s.driving_speech == "standard"


def test_a_settings_file_that_already_has_a_rung_is_left_alone() -> None:
    # The migration must not re-run against a file that has moved on, or a
    # player who chose urgent_only would be dragged back to quiet on the
    # next launch of a build that still saw a stale speech_verbosity.
    s = Settings.from_dict({"speech_verbosity": 0, "driving_speech": "urgent_only"})
    assert s.driving_speech == "urgent_only"


def test_an_unreadable_rung_falls_back_to_standard() -> None:
    s = Settings.from_dict({"driving_speech": "loud please"})
    assert s.driving_speech == "standard"


def test_the_settings_object_answers_for_a_category() -> None:
    s = Settings()
    s.driving_speech = "urgent_only"
    assert s.speaks(SpeechCategory.SAFETY) is True
    assert s.speaks(SpeechCategory.STATUS) is False
    assert s.speaks(None) is True
    assert s.renders_terse() is True

    s.driving_speech = "coaching"
    assert s.speaks(SpeechCategory.STATUS) is True
    assert s.renders_terse() is False


def test_verbosity_is_gone() -> None:
    # 11 references across 7 src files, all replaced -- a leftover reader
    # would silently see normal for every player.
    assert not hasattr(Settings(), "speech_verbosity")


def _app():
    from freight_fate.app import App

    app = App()
    app.ctx.settings.sapi_events = True
    return app


def test_a_silenced_category_never_reaches_the_voice() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event(
            "Load damage 43 percent.", interrupt=False, category=SpeechCategory.STATUS
        )

        assert spoken == []
    finally:
        app.shutdown()


def test_a_silenced_category_still_reaches_the_message_log() -> None:
    # Nothing the ladder cuts becomes unreachable -- the log and the
    # status-query keys still answer for it. Asserts the logged TEXT, not
    # just a count delta: a regression that logged an empty fallback or a
    # stale string would still pass a bare length check.
    app = _app()
    try:
        app.ctx.speech.say_event = speech_stub()
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event(
            "Load damage 43 percent.", interrupt=False, category=SpeechCategory.STATUS
        )

        assert app.ctx.message_log.messages[-1].text == "Load damage 43 percent."
    finally:
        app.shutdown()


def test_a_silenced_category_never_reaches_the_voice_via_say() -> None:
    # ``say``'s gate is separate hand-written code from ``say_event``'s
    # (app.py, both branches now call the shared ``_ladder_applies`` helper
    # but the surrounding silencing logic is duplicated per method), and
    # nothing exercised it before this test -- only inspection did.
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say("Load damage 43 percent.", category=SpeechCategory.STATUS)

        assert spoken == []
    finally:
        app.shutdown()


def test_a_silenced_category_still_reaches_the_log_through_say() -> None:
    app = _app()
    try:
        app.ctx.speech.say = speech_stub()
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say("Load damage 43 percent.", category=SpeechCategory.STATUS)

        assert app.ctx.message_log.messages[-1].text == "Load damage 43 percent."
    finally:
        app.shutdown()


def test_safety_speaks_at_the_quietest_rung() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event(
            "Change lanes or brake! Slow car ahead.",
            interrupt=True,
            category=SpeechCategory.SAFETY,
        )

        assert spoken == ["Change lanes or brake! Slow car ahead."]
    finally:
        app.shutdown()


def test_the_rung_picks_the_rendering() -> None:
    from freight_fate.speech_text import SpokenMessage

    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        pair = SpokenMessage("Watch your speed. The limit is 65 miles per hour.", "Limit 65.")

        app.ctx.settings.driving_speech = "quiet"
        app.ctx.say_event(pair, interrupt=True, category=SpeechCategory.NAVIGATION)

        assert spoken == ["Limit 65."]
    finally:
        app.shutdown()


def test_an_untagged_line_still_speaks_at_the_quietest_rung() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event("Something nobody classified.", interrupt=False)

        assert spoken == ["Something nobody classified."]
    finally:
        app.shutdown()


def _event(kind):
    return type("E", (), {"kind": kind, "data": {}})()


def test_the_hazard_call_is_safety() -> None:
    from freight_fate.states.driving_events import DrivingEventMixin

    assert DrivingEventMixin._event_category(_event(TripEventKind.HAZARD)) is (
        SpeechCategory.SAFETY
    )


def test_a_planned_stop_is_navigation() -> None:
    from freight_fate.states.driving_events import DrivingEventMixin

    assert DrivingEventMixin._event_category(_event(TripEventKind.STOP_AHEAD)) is (
        SpeechCategory.NAVIGATION
    )


def test_weather_colour_is_status_not_navigation() -> None:
    # This is what makes "act-now cues only" real at urgent_only: the stop
    # you must act on is NAVIGATION and speaks; the weather turning is
    # STATUS and does not.
    from freight_fate.states.driving_events import DrivingEventMixin

    assert DrivingEventMixin._event_category(_event(TripEventKind.WEATHER_CHANGE)) is (
        SpeechCategory.STATUS
    )


def test_billboards_and_landmarks_bypass_the_ladder_entirely() -> None:
    # The owner's directive, at the classification layer: flavor is not a
    # ladder category. Mapping BILLBOARD to STATUS would silence billboards
    # at urgent_only, which is precisely what must not happen. A flavor kind
    # classifies as None, so the gate passes it through and its own chatter
    # switch decides.
    from freight_fate.states.driving_events import DrivingEventMixin

    for kind in (TripEventKind.BILLBOARD, TripEventKind.LANDMARK):
        assert DrivingEventMixin._event_category(_event(kind)) is None
        assert kind in _FLAVOR_EVENT_KINDS
        assert kind not in _EVENT_CATEGORIES


def test_the_load_damage_coaching_tail_is_silent_at_urgent_only() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event(
            "Brake and corner gently from here.",
            interrupt=False,
            category=SpeechCategory.COACHING,
        )

        assert spoken == []
    finally:
        app.shutdown()


def test_the_same_tail_speaks_on_the_coaching_rung() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "coaching"

        app.ctx.say_event(
            "Brake and corner gently from here.",
            interrupt=False,
            category=SpeechCategory.COACHING,
        )

        assert spoken == ["Brake and corner gently from here."]
    finally:
        app.shutdown()


def test_no_driving_say_event_call_site_is_left_untagged() -> None:
    # The gate defaults untagged lines to speaking, which is the right
    # failure mode but the wrong finished state: an untagged line is one
    # the ladder cannot quiet. This pins the sweep as done.
    #
    # Walk the AST rather than regex-matching source text -- a regex
    # anchored on a newline before the closing paren misses single-line
    # calls like say_event("x", interrupt=False) and would go green
    # without ever having looked at them.
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "states"
    untagged: list[str] = []
    for path in root.glob("driving*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name != "say_event":
                continue
            keywords = {kw.arg for kw in node.keywords}
            if "category" in keywords:
                continue
            if any(
                kw.arg == "force" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                for kw in node.keywords
            ):
                continue
            untagged.append(f"{path.name}:{node.lineno}")
    assert untagged == [], f"untagged say_event call sites: {untagged}"


def test_weather_change_is_silent_at_urgent_only_through_the_real_path() -> None:
    # Classification alone cannot catch a call site that never threads the
    # category through: WEATHER_CHANGE and LANE only ever reach the voice by
    # way of _speak_ambient_event, which used to drop the category on the
    # floor no matter what _event_category said. This drives a real
    # WEATHER_CHANGE TripEvent through _handle_trip_event -- the actual
    # speaking path -- instead of calling _event_category directly.
    from driving_feature_helpers import quiet_trip, start_drive

    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        # A fresh New career profile has tutorial_done False, which now
        # exempts it from the rung (task 6). This test is about
        # WEATHER_CHANGE's category threading, not the tutorial, so mark
        # the walkthrough done to get the rung's ordinary behaviour.
        app.ctx.profile.tutorial_done = True
        quiet_trip(driving)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        driving._handle_trip_event(
            TripEvent(TripEventKind.WEATHER_CHANGE, "Weather turning: heavy rain.", {})
        )

        assert spoken == []
    finally:
        app.shutdown()


# -- fix round: real announce-path coverage for the review's six findings ---
#
# The gate-only tests above (and the brief's two coaching-tail tests) pass a
# literal string straight to say_event, so they only prove the gate honors
# whatever category it is handed -- never that a real call site hands it the
# right one. These drive the actual announce methods (message assembly and
# all) so a category regression on a real line fails a test, not just a
# reviewer's re-read.


def _real_driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    # tutorial_done=True: these tests are about the rung, not first-run
    # teaching (task 6's exemption reads this flag, and a bare Profile()
    # defaults it False, which would otherwise exempt every one of them).
    app.ctx.profile = Profile(name="Ladder Fix Round", current_city="Denver", tutorial_done=True)
    job = Job(
        CARGO_CATALOG["general"], 12.0, "Denver", "yard", "Salt Lake City", 200.0, 900.0, 12.0
    )
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, job, route, trip_seed=1, start_hour=10.0)
    driving.trip.traffic_manager.vehicles = []
    return driving


def _urgent_only_app():
    app = _app()
    app.ctx.settings.driving_speech = "urgent_only"
    return app


def test_the_out_of_service_wall_speaks_at_urgent_only() -> None:
    # Critical 1: the wall governs the truck to a 15 mph creep and orders a
    # stop on the shoulder right now -- SAFETY, not the STATUS every other
    # damage band correctly uses.
    from freight_fate.sim.vehicle import DAMAGE_OUT_OF_SERVICE_PCT

    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        driving.truck.engine_on = True
        driving.truck.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT + 1.0

        driving._update_damage_bands(1 / 60)

        assert spoken
        assert "out of service" in spoken[-1].lower()
    finally:
        app.shutdown()


def test_a_reduced_power_band_still_stays_quiet_at_urgent_only() -> None:
    # Specificity check for Critical 1: the fix must be a local override on
    # the wall's own branch, not a blanket SAFETY over every damage band.
    from freight_fate.sim.vehicle import DAMAGE_DERATE_PCT

    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        driving.truck.engine_on = True
        driving.truck.damage_pct = DAMAGE_DERATE_PCT + 1.0

        driving._update_damage_bands(1 / 60)

        assert spoken == []
    finally:
        app.shutdown()


def test_drifting_off_the_pavement_speaks_at_urgent_only() -> None:
    # Critical 2: _announce_off_pavement only ever fires on entry or
    # worsening (its own docstring), so every line it emits is the warning,
    # never the standing position -- SAFETY throughout.
    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        driving.lane.lane = 0
        driving.truck.velocity_mps = 13.0

        driving.lane.offset = 1.35
        driving._announce_off_pavement()

        assert spoken
    finally:
        app.shutdown()


def test_back_on_the_pavement_still_stays_quiet_at_urgent_only() -> None:
    # Specificity check for Critical 2: the standing-condition recovery line
    # is correctly STATUS and must stay silenced at the quietest rung; only
    # the warning transition was miscategorized. Drives _update_lane directly
    # (not the whole update() frame) so a fresh drive's other first-frame
    # NAVIGATION chatter -- always audible -- cannot mask the assertion.
    from driving_feature_helpers import HeldKeys

    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        driving.lane.lane = 0
        driving.lane.offset = 0.0
        driving._road_position_band = 1  # was off, band tracked from before

        driving._update_lane(HeldKeys(), 1 / 60)

        assert spoken == []
    finally:
        app.shutdown()


def test_spring_brakes_setting_speaks_at_urgent_only() -> None:
    # Critical 3: this is the low-air *emergency* the taxonomy splits from
    # the low-air *band* -- already interrupt=True with the buzzer, which is
    # the code's own verdict on its urgency. SAFETY, not STATUS.
    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        t = driving.truck
        t.air_pressure_psi = 35.0  # below the spring-brake-set threshold (40)

        driving._update_air_brake_announcements(was_spring=False)

        assert spoken
        assert "spring brakes" in spoken[-1].lower()
    finally:
        app.shutdown()


def test_the_rolling_low_air_warning_speaks_at_urgent_only() -> None:
    # Critical 4, rolling branch: the last warning before the spring brakes
    # set on their own. Same urgency-decides-the-category shape as the HOS
    # check -- SAFETY while rolling.
    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        t = driving.truck
        t.engine_on = True
        t.velocity_mps = 10.0  # rolling
        t.air_pressure_psi = 55.0  # low-air band, above the spring threshold
        # A fresh cold-started truck constructs with _low_air_said already
        # true (it starts low), so a fresh degradation must re-arm it --
        # exactly the hysteresis the real update loop re-arms on recovery.
        driving._low_air_said = False

        driving._update_air_brake_announcements()

        assert spoken
        assert "low air" in spoken[-1].lower()
    finally:
        app.shutdown()


def test_the_parked_low_air_warning_stays_quiet_at_urgent_only() -> None:
    # Critical 4, parked branch: legitimately STATUS -- "leave the parking
    # brake alone" is a band readout, not an act-now cue.
    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        t = driving.truck
        t.engine_on = True
        t.velocity_mps = 0.0  # parked
        t.air_pressure_psi = 55.0
        driving._low_air_said = False

        driving._update_air_brake_announcements()

        assert spoken == []
    finally:
        app.shutdown()


# -- Task 8 audit: the air-brake lockout re-read the same standing reason ---
#
# tools/playtest_break.py --scenario microsleep_throttle_through --transcript
# showed "Parking brake set. Press P to release it." spoken twice back to
# back with nothing about the truck changed in between: the player kept
# holding the accelerator against a parked, air-ready truck, and
# _maybe_say_air_brake_lockout's 4-second retrigger timer re-announced the
# same fact every time it fired. These drive the real method (not a literal
# string handed to say_event) so a key removed from the actual call site
# fails the test, not just a generic pacer check.
#
# Both tests advance a fake clock past EventSpeechPacer.REPEAT_WINDOW_S
# (2.5s) between calls. Without that, an identical-text repeat would already
# be caught by the pacer's plain "said this recently" window regardless of
# key=, and the test would pass whether or not the key survived a revert --
# exactly the vacuous-test trap the plan's history warns about. Past that
# window, only key= keeps an unchanged reason from re-announcing.


def test_the_air_brake_lockout_speaks_once_while_the_reason_is_unchanged() -> None:
    app = _app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        clock = _FakeClock()
        app.ctx._event_pacer = EventSpeechPacer(clock=clock)
        driving.truck.engine_on = True
        driving.truck.set_air_ready(parking_brake=True)  # air ready, brake still set

        for _ in range(4):  # the player holding the accelerator against the lockout
            driving._brake_lockout_cue_timer = 0.0
            clock.now += 10.0  # well past the plain repeat window
            driving._maybe_say_air_brake_lockout()

        assert len(spoken) == 1
    finally:
        app.shutdown()


def test_the_air_brake_lockout_speaks_again_when_the_reason_changes() -> None:
    app = _app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        clock = _FakeClock()
        app.ctx._event_pacer = EventSpeechPacer(clock=clock)
        driving.truck.engine_on = False  # fresh trip: cold air start, engine off

        driving._maybe_say_air_brake_lockout()
        driving._brake_lockout_cue_timer = 0.0
        clock.now += 10.0  # well past the plain repeat window
        driving.truck.engine_on = True  # engine started, air still not built

        driving._maybe_say_air_brake_lockout()

        assert len(spoken) == 2
        assert spoken[0] != spoken[1]
    finally:
        app.shutdown()


def test_the_air_brake_lockout_recurs_once_it_clears_and_comes_back() -> None:
    # Review fix: the key was set but never released, so EventSpeechPacer's
    # single app-session _conditions dict (never cleared by pause/resume/
    # reset, app.py:112) kept the first "Parking brake set..." on file
    # forever. A later, unrelated recurrence of the identical text -- the
    # lockout clears, then hours later the player parks at a different stop
    # and hits the accelerator before releasing the brake -- would go
    # silent under the stale key: exactly the "swallows a genuine
    # re-warning" failure the task's constraints forbid. Mirrors
    # test_a_cleared_condition_announces_itself_afresh
    # (test_event_speech_pacer.py) and _update_overrev's
    # reset_event_condition("engine_redline") pattern, but through the real
    # per-frame update() -- where the new reset actually lives -- not the
    # pacer directly.
    from driving_feature_helpers import quiet_trip

    app = _app()
    try:
        driving = _real_driving(app)
        quiet_trip(driving)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        clock = _FakeClock()
        app.ctx._event_pacer = EventSpeechPacer(clock=clock)
        driving.truck.engine_on = True
        driving.truck.set_air_ready(parking_brake=True)  # locked out, air ready

        driving._maybe_say_air_brake_lockout()  # first instance: speaks

        driving.truck.parking_brake = False  # the lockout genuinely clears
        clock.now += 10.0
        driving.update(1 / 60)  # a real per-frame pass sees the clear

        driving.truck.set_air_ready(parking_brake=True)  # locked out again, later
        driving._brake_lockout_cue_timer = 0.0
        clock.now += 10.0
        driving._maybe_say_air_brake_lockout()  # a fresh instance: must speak too

        parking_lines = [s for s in spoken if "Parking brake set" in s]
        assert len(parking_lines) == 2
        assert parking_lines[0] == parking_lines[1]  # identical text, both spoken
    finally:
        app.shutdown()


def test_cargo_condition_speaks_at_urgent_only_as_money() -> None:
    # Important 5: the coaching tail only rides the first report; every
    # message this sends -- including that first one -- carries the pay
    # consequence (an exception, a claim, a refused load). MONEY, not
    # COACHING, governs the whole line.
    from freight_fate.models.cargo_condition import CARGO_EXCEPTION_PCT

    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        driving.truck.cargo_damage_pct = CARGO_EXCEPTION_PCT + 1.0

        driving._announce_cargo_condition()

        assert spoken
    finally:
        app.shutdown()


def test_the_carrier_grounding_speaks_at_urgent_only_as_money() -> None:
    # Critical 2 (final review): this line is the company driver's twin of
    # the owner-operator's roadside-repair report (already MONEY) -- same
    # moment, but this one was tagged CONFIRMATION, an EARCON category at
    # quiet and urgent_only. A company driver at either rung would have
    # heard one chime and learned neither that dispatch took the tractor,
    # the reputation hit, nor the damage on the truck they are now in.
    # ``_real_driving``'s ``Profile`` defaults to ``COMPANY_DRIVER``
    # (business_status's own default), so no extra setup is needed to land
    # in ``_carrier_grounds_the_tractor`` rather than its owner-operator
    # sibling. Reverting the category back to CONFIRMATION makes
    # ``spoken`` empty here.
    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)

        driving._carrier_grounds_the_tractor()

        assert spoken
        assert "grounded" in spoken[-1].lower()
        assert "carrier" in spoken[-1].lower()
    finally:
        app.shutdown()


def test_an_engine_stall_speaks_at_urgent_only_as_safety() -> None:
    # Critical 3 (final review): a stall is an unrequested failure that
    # stops the truck and names the key to get it moving again -- the same
    # "will not move, here is what to press" shape as the out-of-service
    # wall and the spring-brake emergency, both already SAFETY. It was
    # tagged CONFIRMATION, so a quiet or urgent_only driver got a chime and
    # no recovery instruction with a dead engine. ``TruckState.update`` is
    # monkeypatched to force the stall directly (real stall physics need a
    # manual gearbox held in the wrong gear at low speed, which is
    # incidental to what this test is pinning: the category on the line
    # that fires once ``was_on and not t.engine_on and t.stalled``).
    # Reverting the category back to CONFIRMATION makes ``spoken`` empty.
    from driving_feature_helpers import quiet_trip

    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        quiet_trip(driving)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        driving.truck.engine_on = True

        def _force_stall(dt: float) -> None:
            driving.truck.engine_on = False
            driving.truck.stalled = True

        driving.truck.update = _force_stall

        driving.update(1 / 60)

        assert spoken
        assert "engine stalled" in spoken[-1].lower()
    finally:
        app.shutdown()


def test_a_tire_chain_release_speaks_at_urgent_only_as_money() -> None:
    # Critical 3 (final review), the chain-release half: "the set is scrap"
    # is a purchase, and running unchained under an active chain law is
    # citation exposure -- MONEY, matching its own text, not CONFIRMATION.
    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        driving.truck.chains_just_snapped = True

        driving._update_traction_cues()

        assert spoken
        assert "scrap" in spoken[-1].lower()
    finally:
        app.shutdown()


def test_missed_destination_exit_speaks_at_urgent_only() -> None:
    # Important 6: the route just changed and this names the maneuver that
    # still gets the load delivered -- NAVIGATION, not CONFIRMATION, so it
    # survives urgent_only as words, not an earcon blip.
    from driving_feature_helpers import quiet_trip, start_drive

    from freight_fate.app import App

    app = App()
    app.ctx.settings.driving_speech = "urgent_only"
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        driving.trip.position_mi = driving.trip.total_miles
        driving.trip.finished = True
        driving.truck.velocity_mps = 20.0

        driving.update(1 / 60)

        assert spoken
        assert "missed the destination exit" in spoken[-1].lower()
    finally:
        app.shutdown()


def test_missed_facility_gate_speaks_at_urgent_only() -> None:
    # Important 6: same mandatory-stop-miss family as the destination exit.
    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)

        driving._handle_missed_facility_gate()

        assert spoken
        assert "gate" in spoken[-1].lower()
    finally:
        app.shutdown()


def test_drove_past_the_destination_terminal_speaks_at_urgent_only() -> None:
    # Important 6: the ramp-terminal loop-back names the same maneuver as
    # the facility-gate and destination-exit misses.
    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        stop = type("Stop", (), {"name": "Salt Lake City Warehouse"})()

        driving._loop_back_to_destination_terminal(stop)

        assert spoken
        assert "drove past" in spoken[-1].lower()
    finally:
        app.shutdown()


def test_missed_turn_speaks_at_urgent_only() -> None:
    # Important 6: a blown street turn is the same mandatory-stop-miss
    # family as the highway misses above.
    from freight_fate.data.world_models import Leg, Route
    from freight_fate.sim import Trip

    app = _urgent_only_app()
    try:
        driving = _real_driving(app)
        city = driving.trip.route.cities[0]
        legs = [
            Leg(
                city,
                city,
                0.6,
                "East Navarre Street",
                "flat",
                (),
                local_cue="Start on East Navarre Street.",
                local_speed_mph=25.0,
            ),
            Leg(
                city,
                city,
                0.5,
                "North Michigan Street",
                "flat",
                (),
                local_cue="Turn left onto North Michigan Street.",
                local_speed_mph=25.0,
            ),
        ]
        trip = Trip(Route([city] * 3, legs), driving.truck, driving.trip.weather, seed=3)
        trip.traffic_manager.vehicles = []
        driving.trip = trip
        driving._reset_turn_state_for_trip()
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)

        # Roll up to the turn far too fast and let the reaction window lapse.
        driving.trip.position_mi = 0.4
        driving.truck.engine_on = True
        driving.truck.velocity_mps = 45.0 / 2.23694
        driving._update_turn_commitment(0.016)
        driving.trip.position_mi = 0.6
        driving._update_turn_commitment(driving._turn_grace_s + 1.0)

        assert spoken
        assert "missed the turn" in spoken[-1].lower()
    finally:
        app.shutdown()


# -- the tutorial exemption, and learnable earcons (task 6) -----------------


def test_the_ladder_does_not_apply_before_the_walkthrough_is_done() -> None:
    # R15, defended against a new mechanism. Terse used to silence the
    # tutorial outright, which orphaned exactly the new player most likely
    # to pick the quietest setting on day one. A rung must not do it either.
    # Uses a real Profile (not a bare literal on a None ctx.profile): the
    # gate reads ctx.profile.tutorial_done, and GameContext.profile is None
    # until something assigns it, exactly like every other real-profile test
    # in this file (see _real_driving above).
    from freight_fate.models.profile import Profile

    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"
        app.ctx.profile = Profile(name="New Driver", current_city="Denver")
        app.ctx.profile.tutorial_done = False

        app.ctx.say_event(
            "Press E to start the engine.",
            interrupt=False,
            category=SpeechCategory.COACHING,
        )

        assert spoken == ["Press E to start the engine."]
    finally:
        app.shutdown()


def test_the_ladder_applies_once_the_walkthrough_is_done() -> None:
    from freight_fate.models.profile import Profile

    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"
        app.ctx.profile = Profile(name="New Driver", current_city="Denver")
        app.ctx.profile.tutorial_done = True

        app.ctx.say_event(
            "Press E to start the engine.",
            interrupt=False,
            category=SpeechCategory.COACHING,
        )

        assert spoken == []
    finally:
        app.shutdown()


def test_the_ladder_applies_with_no_profile_at_all() -> None:
    # ctx.profile is Profile | None; the exemption must default to "the rung
    # applies" when there is no profile (a menu, a screen with no career
    # loaded), never to "nobody can ever be silenced". Getting the default
    # backwards would make the whole ladder inert outside a drive.
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"
        assert app.ctx.profile is None

        app.ctx.say_event(
            "Press E to start the engine.",
            interrupt=False,
            category=SpeechCategory.COACHING,
        )

        assert spoken == []
    finally:
        app.shutdown()


def test_every_earcon_category_is_learnable() -> None:
    # R14's standing rule, binding S4's substitutions: no earcon may carry
    # meaning that the Learn game sounds screen cannot teach. This is what
    # makes "the rung replaces words with sounds" legitimate rather than
    # exclusionary. ``SoundEntry`` has no ``key`` field -- its spoken
    # identity is ``name`` -- so ``LADDER_EARCONS`` and this check both key
    # off that.
    from freight_fate.sound_catalog import CATALOG

    learnable = {entry.name for category in CATALOG for entry in category.entries}
    for rung in DRIVING_SPEECH_MODES:
        for category in SpeechCategory:
            if disposition_for(rung, category) is Disposition.EARCON:
                assert LADDER_EARCONS[category] in learnable, (
                    f"{category} becomes an earcon at {rung} with nothing to learn it by"
                )


def test_an_earcon_category_actually_asks_the_audio_layer_to_play(monkeypatch) -> None:
    # Task 10: spec invariant 3 was unmet -- LADDER_EARCONS existed and was
    # pinned learnable, but nothing during a drive ever asked the audio
    # layer to sound it, so a "quiet" driver got silence where the spec
    # promises a cue. This asserts the actual call into ``ctx.audio.play``,
    # not that a dictionary contains a key: reverting app.py's gate to its
    # old log-and-return (no ``_play_ladder_earcon`` call) leaves ``played``
    # empty and fails this, where a test that only inspected LADDER_EARCONS
    # or DRIVING_SPEECH_DISPOSITIONS would stay green either way.
    from freight_fate.sound_catalog import entry_by_name

    app = _app()
    try:
        app.ctx.speech.say_event = speech_stub()
        played: list[tuple[str, float, float]] = []
        monkeypatch.setattr(
            app.ctx.audio,
            "play",
            lambda key, volume=1.0, pan=0.0: played.append((key, volume, pan)),
        )
        app.ctx.settings.driving_speech = "quiet"

        app.ctx.say_event(
            "Load damage 43 percent.", interrupt=False, category=SpeechCategory.STATUS
        )

        cue = entry_by_name(LADDER_EARCONS[SpeechCategory.STATUS]).plays[0]
        assert played == [(cue.key, cue.volume, cue.pan)]
    finally:
        app.shutdown()


def test_a_silent_category_asks_the_audio_layer_for_nothing(monkeypatch) -> None:
    # The other half of the pair above: SILENT and EARCON both cut the
    # words, and only EARCON is supposed to sound anything. This is the
    # entire remaining difference at the voice between "quiet" and
    # "urgent_only" -- without the disposition check in app.py's gate
    # (playing on every silenced line rather than only EARCON ones), this
    # would see the same call the quiet-rung test above asserts and fail.
    app = _app()
    try:
        app.ctx.speech.say_event = speech_stub()
        played: list[tuple[str, float, float]] = []
        monkeypatch.setattr(
            app.ctx.audio,
            "play",
            lambda key, volume=1.0, pan=0.0: played.append((key, volume, pan)),
        )
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event(
            "Load damage 43 percent.", interrupt=False, category=SpeechCategory.STATUS
        )

        assert played == []
    finally:
        app.shutdown()


def test_an_earcon_category_plays_through_say_too(monkeypatch) -> None:
    # ``say``'s gate is separate hand-written code from ``say_event``'s
    # (see test_a_silenced_category_never_reaches_the_voice_via_say above),
    # so the earcon wiring has to be checked there too rather than assumed
    # to follow from the ``say_event`` coverage.
    from freight_fate.sound_catalog import entry_by_name

    app = _app()
    try:
        app.ctx.speech.say = speech_stub()
        played: list[tuple[str, float, float]] = []
        monkeypatch.setattr(
            app.ctx.audio,
            "play",
            lambda key, volume=1.0, pan=0.0: played.append((key, volume, pan)),
        )
        app.ctx.settings.driving_speech = "quiet"

        app.ctx.say("Nice smooth shift.", category=SpeechCategory.COACHING)

        cue = entry_by_name(LADDER_EARCONS[SpeechCategory.COACHING]).plays[0]
        assert played == [(cue.key, cue.volume, cue.pan)]
    finally:
        app.shutdown()


def test_a_silenced_keyed_status_line_plays_the_earcon_once(monkeypatch) -> None:
    # Critical 1 (final review): both silenced branches in app.py used to
    # ``return`` before ever consulting the pacer, so a keyed standing
    # condition -- air_brake_lockout re-firing every 4s while the
    # accelerator is held (driving_updates.py's _maybe_say_air_brake_lockout),
    # engine_redline re-firing every OVERREV_REPEAT_S -- played its earcon on
    # every re-announce at quiet, where the same condition speaks one
    # sentence and falls silent at coaching/standard. Fires the identical
    # keyed STATUS line five times, exactly as a held accelerator against a
    # locked-out brake does, and requires exactly one earcon. Reverting the
    # ``is_silenced_repeat``/``note_silenced`` pair this fix added to
    # say_event's silenced branch restores the old log-and-play-every-time
    # behaviour, which collects five entries here and fails the length
    # assertion.
    from freight_fate.sound_catalog import entry_by_name

    app = _app()
    try:
        app.ctx.speech.say_event = speech_stub()
        played: list[tuple[str, float, float]] = []
        monkeypatch.setattr(
            app.ctx.audio,
            "play",
            lambda key, volume=1.0, pan=0.0: played.append((key, volume, pan)),
        )
        app.ctx.settings.driving_speech = "quiet"

        for _ in range(5):
            app.ctx.say_event(
                "Parking brake set. Press P to release it.",
                interrupt=False,
                key="air_brake_lockout",
                category=SpeechCategory.STATUS,
            )

        cue = entry_by_name(LADDER_EARCONS[SpeechCategory.STATUS]).plays[0]
        assert played == [(cue.key, cue.volume, cue.pan)]
    finally:
        app.shutdown()


def test_a_silenced_plain_repeat_via_say_plays_the_earcon_once(monkeypatch) -> None:
    # Critical 1's other half: ``say`` has no ``key=``/``force=``, so its
    # silenced branch relies on the pacer's plain repeat window instead. The
    # same identical line fired twice in a row (well inside
    # EventSpeechPacer.REPEAT_WINDOW_S) must not double the earcon. Reverting
    # the ``is_silenced_repeat``/``note_silenced`` pair added to ``say``'s
    # silenced branch collects two entries here.
    from freight_fate.sound_catalog import entry_by_name

    app = _app()
    try:
        app.ctx.speech.say = speech_stub()
        played: list[tuple[str, float, float]] = []
        monkeypatch.setattr(
            app.ctx.audio,
            "play",
            lambda key, volume=1.0, pan=0.0: played.append((key, volume, pan)),
        )
        app.ctx.settings.driving_speech = "quiet"

        app.ctx.say("Nice smooth shift.", category=SpeechCategory.COACHING)
        app.ctx.say("Nice smooth shift.", category=SpeechCategory.COACHING)

        cue = entry_by_name(LADDER_EARCONS[SpeechCategory.COACHING]).plays[0]
        assert played == [(cue.key, cue.volume, cue.pan)]
    finally:
        app.shutdown()


def test_raising_the_rung_still_speaks_an_active_silenced_condition() -> None:
    # Re-review regression: the silenced branches' earcon dedup must not
    # write into the state the SPEAKING path's ``is_repeat`` reads. Silence
    # a keyed STATUS condition at quiet (it plays an earcon and gets marked
    # under ``EventSpeechPacer._silenced_conditions``), then raise the rung
    # to coaching with the condition still active and its text byte-for-byte
    # unchanged -- STATUS is FULL at coaching, so this occurrence must
    # actually speak, because the player raised the rung specifically to
    # hear it. Before this fix, the silenced branch called
    # ``note_spoken(text, key=key)``, which wrote ``_conditions[key] =
    # text`` -- the exact map ``is_repeat`` reads on the speaking path below.
    # The speaking call would then find its own silenced text already on
    # file, read the now-audible occurrence as an unchanged repeat, and
    # silently return: the line would never speak and never log, for the
    # rest of that occurrence, at the very rung that promises full
    # sentences. Reverting ``is_silenced_repeat``/``note_silenced`` back to
    # ``is_repeat``/``note_spoken`` makes ``spoken`` empty here.
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "quiet"

        app.ctx.say_event(
            "Parking brake set. Press P to release it.",
            interrupt=False,
            key="air_brake_lockout",
            category=SpeechCategory.STATUS,
        )
        assert spoken == []  # silenced (earcon only) at quiet

        app.ctx.settings.driving_speech = "coaching"
        app.ctx.say_event(
            "Parking brake set. Press P to release it.",
            interrupt=False,
            key="air_brake_lockout",
            category=SpeechCategory.STATUS,
        )

        assert spoken == ["Parking brake set. Press P to release it."]
    finally:
        app.shutdown()


def test_an_unchanged_status_line_speaks_once() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "coaching"

        for _ in range(4):
            app.ctx.say_event(
                "Gap to the truck ahead: 3 seconds.",
                interrupt=False,
                key="lead_gap",
                category=SpeechCategory.STATUS,
            )

        assert spoken == ["Gap to the truck ahead: 3 seconds."]
    finally:
        app.shutdown()


def test_a_changed_status_line_speaks_again() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "coaching"
        # A real gap-closing update arrives seconds apart, not in the same
        # instant -- advance the pacer's clock between the two calls so the
        # anti-backlog projection (unrelated to the key= mechanism under
        # test) doesn't read the second line as starting stale behind the
        # first one's still-projected utterance.
        clock = _FakeClock()
        app.ctx._event_pacer = EventSpeechPacer(clock=clock)

        app.ctx.say_event(
            "Gap to the truck ahead: 3 seconds.",
            interrupt=False,
            key="lead_gap",
            category=SpeechCategory.STATUS,
        )
        clock.now += 5.0
        app.ctx.say_event(
            "Gap to the truck ahead: 1 second.",
            interrupt=False,
            key="lead_gap",
            category=SpeechCategory.STATUS,
        )

        assert spoken == [
            "Gap to the truck ahead: 3 seconds.",
            "Gap to the truck ahead: 1 second.",
        ]
    finally:
        app.shutdown()


# -- Task 9: the whole-drive proof -------------------------------------------
#
# Every test above drives the gate directly, with a literal string handed to
# say_event. That proves the gate honours whatever category and rung it is
# given -- it does not prove a real drive actually says fewer things as the
# rung tightens, which is the owner's actual complaint (a COUNT complaint,
# not a length complaint). These drive a real scenario from the adversarial
# battery (``tools/playtest_break.py``) through real DrivingState frames and
# count what reaches the voice.
#
# The transcript capture seam these tests rely on -- stubbing
# ``ctx.speech.say``/``ctx.speech.say_event`` rather than ``ctx.say``/
# ``ctx.say_event`` themselves -- is the harness fix this task also makes to
# ``tools/playtest_break.py`` and ``tools/playtest_road.py``: the ladder's
# gate and the event pacer both live *inside* ``GameContext.say``/
# ``say_event``, so replacing those methods (the previous state of both
# tools) would have skipped both and shown every scenario what the game
# would say with no rung applied at all.


def _load_break_harness():
    """Import tools/playtest_break.py under its own name, in-process.

    Mirrors ``tests/adversarial/test_break_scenarios.py``'s loader exactly:
    ``tools/`` is not a package, so the battery is loaded by path, and it
    must land in ``sys.modules`` under the literal name ``"playtest_break"``
    because its scenario modules register themselves back into it with
    ``from playtest_break import ...``.
    """
    import importlib.util
    import sys
    from pathlib import Path

    if "playtest_break" in sys.modules:
        return sys.modules["playtest_break"]
    tools = Path(__file__).resolve().parents[1] / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    spec = importlib.util.spec_from_file_location("playtest_break", tools / "playtest_break.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["playtest_break"] = module
    spec.loader.exec_module(module)
    return module


def _spoken_transcript_for_scenario(name: str, rung: str) -> list[str]:
    """Run one playtest_break scenario with the driving-speech rung forced,
    returning the transcript exactly as a player at that rung would hear it.

    Forcing the rung takes two overrides on top of ``Rig``'s own setup, both
    found by actually walking the battery rather than assuming:

    * ``settings.driving_speech`` -- the rig itself never sets this, so
      every scenario runs at the stock default ("standard") unless told
      otherwise.
    * ``profile.tutorial_done`` -- ``Rig`` builds a fresh ``Profile``, whose
      default is ``tutorial_done=False``. R15's exemption (task 6) makes the
      *entire* ladder gate a no-op whenever that flag is False, so every one
      of the battery's 34 scenarios speaks identically at all four rungs
      out of the box -- confirmed by monkeypatching ``Settings.speaks`` to
      always return ``True`` (simulating the ladder never having shipped)
      and finding every scenario's transcript came back byte-for-byte
      unchanged. Setting it True here is what ``test_driving_speech_ladder``
      does everywhere else it drives a real ``DrivingState`` (see
      ``_real_driving`` above): the rung, not first-run teaching, is what
      is under test.
    """
    break_harness = _load_break_harness()
    Rig = break_harness.Rig
    original_init = Rig.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.ctx.settings.driving_speech = rung
        self.ctx.profile.tutorial_done = True

    Rig.__init__ = patched_init
    try:
        outcome = break_harness.run_scenario(name)
    finally:
        Rig.__init__ = original_init
    assert outcome.verdict != "ERROR", f"{name} crashed at rung {rung!r}: {outcome.note}"
    return outcome.transcript


def _spoken_line_count_for_scenario(name: str, rung: str) -> int:
    return len(_spoken_transcript_for_scenario(name, rung))


# ``reverse_down_the_route`` (backing down the interstate) was picked by
# actually measuring every registered scenario, not by assumption -- most of
# the battery's 34 scenarios never reach a CONFIRMATION or STATUS call site
# that survives the pre-existing per-condition repeat suppression, so their
# rung-to-rung counts are flat and would make this a vacuous test. This one
# reliably says "Reverse selected. Backing slowly." (CONFIRMATION) once and
# then a fresh "engine is screaming at redline" STATUS readout on each
# further mile of engine wear -- both EARCON-silenced at quiet and
# urgent_only, both full words at coaching and standard.
_SCENARIO = "reverse_down_the_route"


@pytest.mark.timeout(300)
def test_a_drive_gets_quieter_as_the_rung_tightens() -> None:
    # The owner's report is a COUNT complaint, not a length complaint, so
    # the pin is a count. Under xdist a sweep like this needs its own
    # timeout or the worker reads as "node down".
    transcripts = {
        rung: _spoken_transcript_for_scenario(_SCENARIO, rung) for rung in DRIVING_SPEECH_MODES
    }
    counts = {rung: len(lines) for rung, lines in transcripts.items()}

    # Non-vacuous: the coaching rung must actually carry a CONFIRMATION line
    # and a STATUS line -- the two categories quiet and urgent_only cut to
    # EARCON -- or a tie further down the ladder would pass for the wrong
    # reason (nothing to cut) rather than because the gate did its job.
    coaching_text = "\n".join(transcripts["coaching"])
    assert "Reverse selected. Backing slowly." in coaching_text  # CONFIRMATION
    assert "screaming at redline" in coaching_text  # STATUS

    # coaching and standard tie on this drive (and on every other candidate
    # scenario measured while building this test). That is not a scenario
    # problem: Disposition.FIRST_OCCURRENCE and Disposition.TRANSITIONS --
    # the two rows "standard" uses to blunt the same COACHING/STATUS
    # categories "coaching" leaves FULL -- are pinned in
    # DRIVING_SPEECH_DISPOSITIONS but not actually wired anywhere:
    # Settings.speaks() only branches on EARCON/SILENT (settings.py), so
    # every disposition that is not one of those two currently speaks
    # exactly like FULL. That gap is real, confirmed by grepping every
    # consumer of Disposition in src/, and is tracked as roadmap follow-up
    # rather than silently implemented as a side effect of this proof.
    assert counts["coaching"] >= counts["standard"]

    # The real cut: CONFIRMATION and STATUS both go silent at quiet, and
    # nothing else in this drive is rung-sensitive. Verified to be the
    # ladder's doing and not some other terse-mode mechanism (several call
    # sites carry their own pre-existing ``_terse_speech()`` early return)
    # by monkeypatching Settings.speaks() to always return True and
    # confirming this scenario's counts go flat at 19 across every rung.
    assert counts["standard"] > counts["quiet"]

    # quiet and urgent_only are identical on every input Settings.speaks()
    # and Settings.renders_terse() consult -- see DRIVING_SPEECH_DISPOSITIONS:
    # both rungs render every category TERSE or EARCON, and EARCON/SILENT
    # both silence the voice (Disposition's own docstring: "EARCON and
    # SILENT both stop the words; they differ in whether the sound layer
    # still marks the moment"). This harness only observes the speech
    # transcript -- ``_spoken_transcript_for_scenario`` stubs
    # ``ctx.speech.say_event`` -- so it cannot see the two rungs' real
    # difference at the voice: quiet plays an earcon where COACHING,
    # CONFIRMATION, and STATUS go EARCON, and urgent_only plays nothing
    # where COACHING and STATUS go SILENT instead. That split is wired (Task
    # 10) and covered directly by
    # ``test_an_earcon_category_actually_asks_the_audio_layer_to_play`` and
    # ``test_a_silent_category_asks_the_audio_layer_for_nothing``, which
    # stub ``ctx.audio.play`` rather than the speech channel. Pinned here as
    # full transcript equality, not just a count tie, so a future asymmetry
    # between them AT THE VOICE is caught immediately rather than only once
    # it changes a length.
    assert counts["quiet"] >= counts["urgent_only"]
    assert transcripts["quiet"] == transcripts["urgent_only"]


def test_every_trip_event_kind_is_classified() -> None:
    # Every kind is either governed by the ladder or explicitly left to the
    # flavor switches. Neither list may quietly gain a member by omission:
    # a new event kind must make someone decide which it is.
    from freight_fate.sim.trip_models import TripEventKind
    from freight_fate.states.driving_events import _EVENT_CATEGORIES, _FLAVOR_EVENT_KINDS

    undecided = [
        k.name for k in TripEventKind if k not in _EVENT_CATEGORIES and k not in _FLAVOR_EVENT_KINDS
    ]
    assert undecided == [], f"trip event kinds nobody classified: {undecided}"

    both = [k.name for k in TripEventKind if k in _EVENT_CATEGORIES and k in _FLAVOR_EVENT_KINDS]
    assert both == [], f"trip event kinds claimed by both lists: {both}"


def test_flavor_is_independent_of_the_rung() -> None:
    # The owner's directive of 2026-08-15, as an executable assertion: the
    # ladder governs information, the chatter switches govern colour, and
    # neither may grow a dependency on the other.
    from freight_fate.settings import Settings

    s = Settings()
    s.driving_speech = "urgent_only"
    s.set_all_chatter(True)
    assert s.chatter_enabled("billboard") is True

    s.driving_speech = "coaching"
    s.set_all_chatter(False)
    assert s.chatter_enabled("billboard") is False


def test_the_cab_is_categorised_so_quiet_is_actually_quiet():
    """Owner playtest, 2026-08-17: "quiet still feels busy".

    The ladder had categorised the ROAD thoroughly and left the CAB alone, so
    control feedback -- the thing that fires on every key you press -- went
    out uncategorised and always spoke in full. In that session, 130 of the
    178 lines spoken after the rung was set to quiet had never been near it,
    including ten consecutive "Adaptive cruise N miles per hour" from ten
    taps of the plus key.
    """
    from freight_fate.settings import Settings
    from freight_fate.speech_pacing import Disposition, SpeechCategory

    quiet = Settings()
    quiet.driving_speech = "quiet"
    assert quiet.speech_disposition(SpeechCategory.CONFIRMATION) is Disposition.EARCON

    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "freight_fate"
    src = (root / "states").glob("driving_*.py")
    joined = "\n".join(p.read_text(encoding="utf-8") for p in src)
    # The exact lines from that transcript must now carry a category.
    for marker in (
        'f"Adaptive cruise {self.ctx.settings.speed_text(target)}."',
        '"Engine off."',
        'f"Parking brake set. Air pressure {t.air_pressure_psi:.0f} psi.{slowing}"',
    ):
        i = joined.index(marker)
        window = joined[i : i + 260]
        assert "SpeechCategory.CONFIRMATION" in window, marker


def test_wrapping_a_curve_call_never_flattens_its_short_form():
    """A plus sign is all it took to lose the quiet rung's whole benefit.

    ``SpokenMessage`` subclasses ``str``, so ``message + " ..."`` hands back
    a plain ``str`` and the terse rendering is gone without a word. The curve
    call was built as a pair, and one branch concatenated a cruise handback
    onto it, so at quiet the driver still heard the full sentence (owner
    playtest, 2026-08-17).
    """
    from freight_fate.speech_text import (
        SpokenMessage,
        cruise_curve_dropped,
        cruise_curve_easing,
    )

    pacenote = SpokenMessage(
        "Sharp right, half a mile. Advise 35 miles per hour.",
        terse="Sharp right, 35 miles per hour.",
    )
    for wrapped in (
        cruise_curve_dropped(pacenote),
        cruise_curve_easing(pacenote, "35 miles per hour"),
    ):
        assert isinstance(wrapped, SpokenMessage), "the pair must survive the wrapper"
        assert wrapped.terse is not None
        assert "half a mile" not in wrapped.terse, "the short form must stay short"
        assert wrapped.terse != str(wrapped)
