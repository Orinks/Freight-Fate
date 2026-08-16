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
    Disposition,
    SpeechCategory,
    disposition_for,
)
from freight_fate.states.driving_events import _EVENT_CATEGORIES, _FLAVOR_EVENT_KINDS


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
    # status-query keys still answer for it.
    app = _app()
    try:
        app.ctx.speech.say_event = speech_stub()
        app.ctx.settings.driving_speech = "urgent_only"
        before = len(app.ctx.message_log.messages)

        app.ctx.say_event(
            "Load damage 43 percent.", interrupt=False, category=SpeechCategory.STATUS
        )

        assert len(app.ctx.message_log.messages) == before + 1
    finally:
        app.shutdown()


def test_safety_speaks_at_the_quietest_rung() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event(
            "Brake or change lanes! Slow car ahead.",
            interrupt=True,
            category=SpeechCategory.SAFETY,
        )

        assert spoken == ["Brake or change lanes! Slow car ahead."]
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

    app.ctx.profile = Profile(name="Ladder Fix Round", current_city="Denver")
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
