"""Enforcement presence: posts on the road, and being seen by one.

The old catch model produced a country with no police in it. Five patrol
windows covered under five percent of a six-hundred-mile route, a run under a
hundred and twenty miles carried none at all, and a driver who never sped
never heard a trooper once in a career. These tests pin the replacement: posts
are places, observation is graded, presence costs a clean driver nothing, and
nothing can bite a player it never made a sound for.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from enforcement_helpers import always_observing_post
from speech_capture import speech_stub

from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.enforcement_observe import (
    CERTAIN_OVER_MPH,
    OBSERVE_HOLD_MI,
    RoadSample,
    observe,
)
from freight_fate.sim.enforcement_posts import (
    KIND_CHAIN,
    KIND_CMV,
    KIND_FIXED_SCALE,
    KIND_MEDIAN,
    KIND_ROVING,
    KIND_SCALE_APRON,
    KIND_WORK_ZONE,
    hour_multiplier,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "freight_fate"


def _trip(
    a="Chicago", b="Denver", *, seed=7, hazard_scale=1.0, start_hour=12.0, career_hours=100.0
):
    world = __import__("freight_fate.data", fromlist=["get_world"]).get_world()
    route = world.supported_route(a, b)
    return Trip(
        route,
        TruckState(),
        WeatherSystem(seed=1),
        seed=seed,
        hazard_scale=hazard_scale,
        start_hour=start_hour,
        career_hours=career_hours,
    )


# --- placement --------------------------------------------------------------


def test_placement_is_deterministic_from_the_seed():
    a = [(p.id, p.staffed) for p in _trip().posts]
    b = [(p.id, p.staffed) for p in _trip().posts]
    assert a == b
    assert a


def test_a_short_run_still_carries_enforcement():
    """Any run under 120 miles used to carry exactly zero patrols."""
    trip = _trip("Buffalo", "Rochester")
    assert trip.route.miles < 120.0
    assert trip.posts


def test_interstates_carry_more_posts_per_mile_than_two_lane_roads():
    from freight_fate.sim.enforcement_posts import CLASS_SPACING_MULT

    assert CLASS_SPACING_MULT["interstate"] < CLASS_SPACING_MULT["us_highway"]
    assert CLASS_SPACING_MULT["us_highway"] < CLASS_SPACING_MULT["state_route"]


def test_hot_regions_run_denser_than_cold_ones():
    from freight_fate.sim.enforcement_posts import region_multiplier

    assert region_multiplier("northeast") > region_multiplier("heartland")
    assert region_multiplier("heartland") < region_multiplier("appalachia") <= 1.0


def test_the_small_hours_are_thin_and_the_commuter_peaks_are_thick():
    assert hour_multiplier(3.0) < 1.0
    assert hour_multiplier(7.0) > 1.0
    assert hour_multiplier(16.0) > 1.0
    assert hour_multiplier(12.0) == 1.0


def test_scales_are_mostly_dark_at_the_weekend():
    from freight_fate.sim.enforcement_posts import scale_open_chance
    from freight_fate.sim.season import day_of_week

    weekday = next(h for h in range(0, 24 * 14, 24) if day_of_week(float(h)) < 5)
    weekend = next(h for h in range(0, 24 * 14, 24) if day_of_week(float(h)) >= 5)
    assert scale_open_chance(float(weekend)) < scale_open_chance(float(weekday))


def test_every_post_kind_anchors_to_world_data():
    """No post kind may invent a feature the world does not already carry."""
    trip = _trip()
    for post in trip.posts:
        if post.kind in (KIND_FIXED_SCALE, KIND_SCALE_APRON):
            assert any(s.key == post.anchor for s in trip.stops if s.type == "weigh_station")
        elif post.kind == KIND_WORK_ZONE:
            assert any(z.reason == "construction" for z in trip.zones)


def test_relaxed_hazards_do_not_thin_the_police():
    """Presence is a fact about the country, not a difficulty knob."""
    assert len(_trip(hazard_scale=0.2).posts) == len(_trip(hazard_scale=1.0).posts)


def test_a_reload_does_not_re_roll_the_road():
    trip = _trip()
    before = [(p.id, p.staffed) for p in trip.posts]
    trip.restore(trip.total_miles / 3.0, 0.0)
    assert [(p.id, p.staffed) for p in trip.posts] == before


# --- the tableau: a post already working somebody else ----------------------


def test_a_tableau_schedules_on_a_patrol_stretch_and_never_on_a_post_free_stretch():
    from freight_fate.sim.enforcement_posts import TABLEAU_KINDS, assign_tableau

    assert {KIND_MEDIAN, KIND_ROVING, "urban_unit"} == TABLEAU_KINDS

    # A staffed patrol-kind post: some seed schedules a tableau on it.
    staffed = always_observing_post(at_mi=10.0, kind=KIND_MEDIAN)
    assert any(assign_tableau(staffed, seed) for seed in range(50))

    # An empty post (nobody sitting there) never runs a tableau, whatever the
    # seed -- there is no trooper to be busy.
    empty = always_observing_post(at_mi=10.0, kind=KIND_MEDIAN)
    empty.staffed = False
    assert not any(assign_tableau(empty, seed) for seed in range(50))

    # A fixed-spot kind never runs a tableau either, even staffed: a scale,
    # a work zone, a CMV unit and a chain control have no roving "somebody
    # else" to be caught with.
    fixed = always_observing_post(at_mi=10.0, kind=KIND_FIXED_SCALE)
    assert not any(assign_tableau(fixed, seed) for seed in range(50))

    # A route that carries no enforcement posts at all schedules nothing --
    # there is nothing to schedule a tableau ON.
    trip = _trip()
    trip.posts = []
    assert not any(p.tableau for p in trip.posts)


def test_a_tableau_is_deterministic_from_the_seed():
    from freight_fate.sim.enforcement_posts import assign_tableau

    post = always_observing_post(at_mi=10.0, kind=KIND_MEDIAN)
    assert assign_tableau(post, 42) == assign_tableau(post, 42)


def test_the_tableau_busy_window_suppresses_only_that_posts_catches():
    trip = _trip()
    busy = always_observing_post(at_mi=10.0, kind=KIND_MEDIAN, reach_mi=5.0)
    busy.tableau = True
    other = always_observing_post(at_mi=10.0, kind=KIND_ROVING, reach_mi=5.0)
    trip.posts = [busy, other]

    mile_in_window = 9.5
    assert busy.tableau_busy_at(mile_in_window)
    watching = trip.posts_watching(mile_in_window)
    assert busy not in watching
    assert other in watching  # only the busy post's catches are suppressed

    mile_outside = 6.0  # still covered by reach_mi, but well clear of the window
    assert not busy.tableau_busy_at(mile_outside)
    watching_outside = trip.posts_watching(mile_outside)
    assert busy in watching_outside
    assert other in watching_outside


def test_the_tableau_cues_play_once_each(monkeypatch):
    """The siren leads the spot; the stopped pair plays as you pass it."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        played = _capture_audio(app, monkeypatch)
        post = always_observing_post(at_mi=6.0, kind=KIND_MEDIAN)
        post.tableau = True
        d.trip.posts = [post]

        from freight_fate.sim.enforcement_posts import TABLEAU_SIREN_LEAD_MI

        d._enforcement_prev_mi = 6.0 - TABLEAU_SIREN_LEAD_MI - 0.1
        d.trip.position_mi = 6.0 - TABLEAU_SIREN_LEAD_MI + 0.1
        d._update_enforcement_watch(0.1)
        d._service_pending_sounds(1.0)
        assert "events/police_siren" in played
        assert "traffic/trooper_pass" not in played

        d._enforcement_prev_mi = 5.9
        d.trip.position_mi = 6.1
        d._update_enforcement_watch(0.1)
        assert "traffic/trooper_pass" in played
        assert "traffic/car_pass" in played
    finally:
        app.shutdown()


def test_tableau_audio_defers_while_the_players_own_stop_is_active(monkeypatch):
    """Never layered on the player's own siren: the tableau waits its turn.

    A tableau siren and the player's own pull-over siren share the same
    ``events/police_siren`` asset, so playing the tableau's while the player
    is mid-stop would sound like a second trooper on top of their own. The
    missed cue is dropped for good rather than replayed once the stop
    clears -- the shoulder pass still fires normally afterward, proving the
    whole tableau was not disabled, only the one cue that fell inside the
    busy window.
    """
    from freight_fate.app import App
    from freight_fate.sim.enforcement_posts import TABLEAU_SIREN_LEAD_MI

    app = App()
    try:
        d = _driving(app)
        played = _capture_audio(app, monkeypatch)
        post = always_observing_post(at_mi=6.0, kind=KIND_MEDIAN)
        post.tableau = True
        d.trip.posts = [post]

        d.trip.position_mi = 6.0 - TABLEAU_SIREN_LEAD_MI - 0.1
        d._enforcement_prev_mi = d.trip.position_mi
        d._pull_over = "lights"  # the player's own stop is running
        d.trip.position_mi = 6.0 - TABLEAU_SIREN_LEAD_MI + 0.1
        d._update_enforcement_watch(0.1)
        d._service_pending_sounds(1.0)
        assert "events/police_siren" not in played

        d._pull_over = None
        d.trip.position_mi = 6.1
        d._update_enforcement_watch(0.1)
        d._service_pending_sounds(1.0)
        assert "events/police_siren" not in played  # dropped, not replayed late
        assert "traffic/trooper_pass" in played
        assert "traffic/car_pass" in played
    finally:
        app.shutdown()


def test_a_post_that_already_caught_the_player_never_also_runs_its_tableau(monkeypatch):
    """The trooper who just wrote the player up is not also busy with somebody else.

    A tableau post can still independently observe and stop the player
    before its own busy window is reached (or after it ends); ``declined``
    is set either way, whether the post let the player go or pulled them
    over. Once that has happened this post's own tableau story -- "a bear
    has somebody stopped" -- no longer makes sense, so neither cue fires.
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        played = _capture_audio(app, monkeypatch)
        post = always_observing_post(at_mi=6.0, kind=KIND_MEDIAN)
        post.tableau = True
        post.declined = True  # this post already had its own look at the player
        d.trip.posts = [post]

        d.trip.position_mi = 4.0
        d._enforcement_prev_mi = 4.0
        d.trip.position_mi = 6.1  # cross both trigger miles in one frame
        d._update_enforcement_watch(0.1)
        d._service_pending_sounds(1.0)
        assert "events/police_siren" not in played
        assert "traffic/trooper_pass" not in played
        assert "traffic/car_pass" not in played
    finally:
        app.shutdown()


def test_the_tableau_intro_line_speaks_once_and_says_it_is_not_the_player(monkeypatch):
    """The siren cue alone reads like a driver's own stop starting, so it now
    reliably introduces itself -- every tableau, not a chance draw like the
    CB flavor line -- and only once, on the siren-lead trigger."""
    from freight_fate.app import App
    from freight_fate.sim.enforcement_posts import TABLEAU_SIREN_LEAD_MI

    app = App()
    try:
        d = _driving(app)
        d.trip_seed = 1
        events: list[str] = []
        monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        post = always_observing_post(at_mi=6.0, kind=KIND_MEDIAN)
        post.tableau = True
        d.trip.posts = [post]

        d._enforcement_prev_mi = 6.0 - TABLEAU_SIREN_LEAD_MI - 0.1
        d.trip.position_mi = 6.0 - TABLEAU_SIREN_LEAD_MI + 0.1
        d._update_enforcement_watch(0.1)

        assert len(events) == 1
        assert "not you" in events[0]
        assert "trooper" in events[0].lower()

        # The shoulder pass a little later must not repeat the introduction.
        d.trip.position_mi = 6.1
        d._update_enforcement_watch(0.1)
        assert len(events) == 1
    finally:
        app.shutdown()


def test_the_tableau_intro_line_stays_silent_while_deferred(monkeypatch):
    """Same deferral as the tableau audio: never layered on the player's own
    stop, and not replayed late once the stop clears."""
    from freight_fate.app import App
    from freight_fate.sim.enforcement_posts import TABLEAU_SIREN_LEAD_MI

    app = App()
    try:
        d = _driving(app)
        d.trip_seed = 1
        events: list[str] = []
        monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        post = always_observing_post(at_mi=6.0, kind=KIND_MEDIAN)
        post.tableau = True
        d.trip.posts = [post]

        d.trip.position_mi = 6.0 - TABLEAU_SIREN_LEAD_MI - 0.1
        d._enforcement_prev_mi = d.trip.position_mi
        d._pull_over = "lights"  # the player's own stop is running
        d.trip.position_mi = 6.0 - TABLEAU_SIREN_LEAD_MI + 0.1
        d._update_enforcement_watch(0.1)
        assert events == []

        d._pull_over = None
        d.trip.position_mi = 6.1
        d._update_enforcement_watch(0.1)
        assert events == []  # dropped with the cue it rides, not replayed late
    finally:
        app.shutdown()


def test_the_tableau_intro_terse_form_keeps_the_bare_fact():
    """A seeded pinch of why lands on some tableaus and not others, but the
    terse rendering never carries it -- only the bare "not you" fact."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip_seed = 7
        bare_seen = flavored_seen = False
        for i in range(30):
            post = always_observing_post(at_mi=float(i), kind=KIND_MEDIAN)
            message = d._tableau_intro_message(post)
            assert (
                message.render(True) == "A trooper has somebody stopped on the shoulder -- not you."
            )
            if message.normal == message.render(True):
                bare_seen = True
            else:
                flavored_seen = True
                assert message.normal.startswith("A trooper has somebody stopped on the shoulder ")
                assert message.normal.endswith("-- not you.")
        assert bare_seen and flavored_seen
    finally:
        app.shutdown()


def test_the_tableau_cb_line_waits_for_the_players_own_stop_and_a_declined_post():
    """The CB speech-side twin of the audio deferral above."""
    trip = _trip()
    post = always_observing_post(at_mi=trip.position_mi + 2.0, kind=KIND_MEDIAN)
    post.tableau = True
    trip.posts = [post]

    trip.pull_over_active = True
    trip._check_enforcement_heads_up()
    assert not any("somebody stopped" in e.message for e in trip._events)

    trip.pull_over_active = False
    trip._heads_up_seen.discard(post.id)
    post.declined = True
    trip._check_enforcement_heads_up()
    assert not any("somebody stopped" in e.message for e in trip._events)


# --- presence targets -------------------------------------------------------


@pytest.mark.timeout(300)
def test_a_five_hundred_mile_run_lands_in_the_presence_target():
    """Six to twelve audible police contacts per five hundred miles.

    "Present" means heard constantly and, for a clean driver, costing nothing.
    The old model gave a clean driver exactly zero contacts and zero cost,
    which reads as absent.
    """
    for a, b in (("Chicago", "Denver"), ("Los Angeles", "Phoenix")):
        rates = []
        for seed in range(6):
            trip = _trip(a, b, seed=seed)
            contacts = len(trip.audible_enforcement_contacts())
            rates.append(contacts / trip.route.miles * 500.0)
        average = sum(rates) / len(rates)
        assert 6.0 <= average <= 12.0, f"{a}->{b} averaged {average:.1f} per 500 miles"


# --- observation ------------------------------------------------------------


def _sample(**kwargs):
    base = dict(
        position_mi=9.8,
        speed_mph=75.0,
        limit_mph=65.0,
        over_limit_mi=OBSERVE_HOLD_MI * 2,
    )
    base.update(kwargs)
    return RoadSample(**base)


def test_five_over_near_a_post_is_noticed_and_ignored():
    post = always_observing_post(at_mi=10.0)
    assert observe(post, _sample(speed_mph=70.0)) is None


def test_twenty_over_is_a_certainty_at_any_post_that_can_see_you():
    post = always_observing_post(at_mi=10.0)
    found = observe(post, _sample(speed_mph=65.0 + CERTAIN_OVER_MPH))
    assert found is not None
    assert found.confidence == 1.0


def test_a_post_that_was_never_announced_cannot_observe_you():
    """The accessibility gate: no cue, no consequence."""
    post = always_observing_post(at_mi=10.0)
    post.announced = False
    assert observe(post, _sample(speed_mph=95.0)) is None


def test_a_post_that_already_let_you_go_does_not_re_decide():
    post = always_observing_post(at_mi=10.0)
    post.declined = True
    assert observe(post, _sample(speed_mph=95.0)) is None


def test_an_empty_post_sees_nothing():
    post = always_observing_post(at_mi=10.0)
    post.staffed = False
    assert observe(post, _sample(speed_mph=95.0)) is None


def test_a_crest_blocks_lidar_and_barely_troubles_radar():
    lidar = always_observing_post(at_mi=10.0, kind="urban_unit")
    radar = always_observing_post(at_mi=10.0, kind=KIND_MEDIAN)
    speed = dict(speed_mph=80.0, position_mi=9.8)
    lidar_clear = observe(lidar, _sample(**speed)).confidence
    lidar_blind = observe(lidar, _sample(**speed, crest_between=True)).confidence
    radar_clear = observe(radar, _sample(**speed)).confidence
    radar_blind = observe(radar, _sample(**speed, crest_between=True)).confidence
    assert lidar_blind < lidar_clear * 0.3
    assert radar_blind > radar_clear * 0.7


def test_fog_blinds_the_eye_and_not_the_radar():
    visual = always_observing_post(at_mi=10.0, kind=KIND_WORK_ZONE, reach_mi=1.0)
    radar = always_observing_post(at_mi=10.0, kind=KIND_MEDIAN)
    speed = dict(speed_mph=80.0, position_mi=9.8)
    assert (
        observe(visual, _sample(**speed, visibility_mi=0.25)).confidence
        < observe(visual, _sample(**speed, visibility_mi=10.0)).confidence * 0.5
    )
    assert (
        observe(radar, _sample(**speed, visibility_mi=0.25)).confidence
        > observe(radar, _sample(**speed, visibility_mi=10.0)).confidence * 0.85
    )


def test_running_in_a_pack_lowers_the_odds_you_are_the_one_picked():
    post = always_observing_post(at_mi=10.0)
    alone = observe(post, _sample(speed_mph=80.0)).confidence
    packed = observe(post, _sample(speed_mph=80.0, pack_neighbours=3)).confidence
    assert packed < alone
    assert packed < alone * 0.6


def test_a_pack_is_no_cover_for_a_damaged_truck():
    """Speed hides in traffic. A wrecked trailer is visible whoever is around."""
    post = always_observing_post(at_mi=10.0, kind=KIND_WORK_ZONE, reach_mi=1.0)
    alone = observe(post, _sample(speed_mph=65.0, damage_pct=90.0))
    packed = observe(post, _sample(speed_mph=65.0, damage_pct=90.0, pack_neighbours=4))
    assert alone.what == packed.what == "unsafe equipment"
    assert alone.confidence == packed.confidence


def test_a_visual_post_sees_more_than_speed():
    post = always_observing_post(at_mi=10.0, kind=KIND_WORK_ZONE, reach_mi=1.0)
    found = observe(
        post,
        _sample(speed_mph=60.0, chains_required=True, chains_on=False),
    )
    assert found is not None and found.what == "no chains"


def test_a_radar_post_never_writes_you_up_for_something_it_cannot_see():
    post = always_observing_post(at_mi=10.0, kind=KIND_MEDIAN)
    assert observe(post, _sample(speed_mph=60.0, damage_pct=95.0)) is None


def test_the_hold_is_distance_not_time():
    """Observation must behave identically at every pacing and frame rate."""
    post = always_observing_post(at_mi=10.0)
    blip = _sample(speed_mph=80.0, over_limit_mi=OBSERVE_HOLD_MI / 4.0)
    held = _sample(speed_mph=80.0, over_limit_mi=OBSERVE_HOLD_MI * 1.5)
    assert observe(post, blip) is None
    assert observe(post, held) is not None


# --- determinism ------------------------------------------------------------


def test_the_observation_seed_is_position_quantised_never_time_quantised():
    from freight_fate.sim.enforcement_posts import post_seed

    post = always_observing_post(at_mi=10.0)
    a = post_seed(42, post.id, f"observe:speeding:{round(9.84, 1)}")
    b = post_seed(42, post.id, f"observe:speeding:{round(9.83, 1)}")
    assert a == b  # the same tenth of a mile is the same decision
    assert post_seed(42, post.id, "observe:speeding:9.9") != a


def test_road_joint_audio_does_not_consume_the_enforcement_stream():
    """Ambience once decided whether a trooper caught you.

    The road-joint spacer drew from the shared patrol stream about a hundred
    times a mile, so being ticketed came down to how many joints had played --
    frame timing, effectively, and a reload re-rolled it. There is no shared
    enforcement stream left to consume.
    """
    source = (SRC / "states" / "driving.py").read_text(encoding="utf-8")
    assert "_patrol_rng" not in source
    assert "_road_texture_rng" in source


# --- presence is not difficulty --------------------------------------------


def test_there_is_no_enforcement_presence_setting_any_more():
    """Removed 2026-08-16 on the owner's ruling, and it must not come back.

    It governed ambient volume only and never touched odds, but at its
    loudest it gave an EMPTY crossover the same pass-by cue a staffed one
    gets -- and by ear that is a trooper who watched you speed and did
    nothing, which is what taught players the police do not enforce.
    """
    from dataclasses import fields

    from freight_fate.settings import Settings

    assert not hasattr(Settings(), "enforcement_presence")
    assert "enforcement_presence" not in {f.name for f in fields(Settings)}
    menu = (SRC / "states" / "main_menu.py").read_text(encoding="utf-8")
    assert "enforcement_presence" not in menu
    assert "Enforcement presence" not in menu


def test_placement_and_staffing_read_no_difficulty_dial():
    posts = (SRC / "sim" / "enforcement_posts.py").read_text(encoding="utf-8")
    observing = (SRC / "sim" / "enforcement_observe.py").read_text(encoding="utf-8")
    for source in (posts, observing):
        assert "enforcement_presence" not in source
        assert "hazard_scale" not in source.replace("``hazard_scale``", "")


def test_a_quiet_road_still_reports_enforcement_in_full_when_asked():
    """You lose ambience, never information you can ask a key for."""
    trip = _trip()
    trip.posts = [always_observing_post(at_mi=trip.position_mi + 4.0)]
    line = trip.cb_patrol_status(trip.posts[0], 4.0)
    assert "enforcement post" in line
    assert "median" in line


# --- CB chatter -------------------------------------------------------------


def test_cb_confidence_is_carried_in_the_words():
    """A blind player cannot falsify a CB call by looking out of the window.

    So the channel's unreliability has to be audible in the attribution, not
    silent: a silently wrong report is indistinguishable from a bug, and the
    rational response to that is to distrust the whole channel.
    """
    trip = _trip()
    staffed = always_observing_post(at_mi=20.0)
    empty = always_observing_post(at_mi=20.0)
    empty.staffed = False
    lines = {trip.cb_patrol_message(p, 3.0) for p in (staffed, empty)}
    assert any("two drivers call" in line or "a driver reports" in line for line in lines)


def test_the_cb_never_says_the_road_is_clear():
    """Wrong in one direction only. Silence is the only honest "nothing heard"."""
    trip = _trip()
    for post in trip.posts[:40]:
        line = trip.cb_patrol_message(post, 3.0)
        lowered = line.lower()
        assert "clear" not in lowered
        assert "nothing" not in lowered
        assert "no bear" not in lowered


def test_cb_chatter_varies_by_what_the_post_actually_is():
    """The rewrite that shipped the presence model collapsed every post kind
    to "a bear {side}" x3 confidence levels. A patrol/speed post still calls
    a bear; a work zone is drivers talking about enforcement working the
    zone, not a trooper sighting; a scale or a commercial-vehicle unit is
    chatter about logs (and, for the CMV unit, equipment) being checked; a
    chain control is chatter about chains being checked at the grade --
    and every kind keeps the same confidence framing and the distance/side
    slots."""
    trip = _trip()
    patrol = always_observing_post(at_mi=20.0, kind=KIND_MEDIAN)
    work_zone = always_observing_post(at_mi=20.0, kind=KIND_WORK_ZONE)
    scale_apron = always_observing_post(at_mi=20.0, kind=KIND_SCALE_APRON)
    fixed_scale = always_observing_post(at_mi=20.0, kind=KIND_FIXED_SCALE)
    cmv = always_observing_post(at_mi=20.0, kind=KIND_CMV)
    chain = always_observing_post(at_mi=20.0, kind=KIND_CHAIN)

    patrol_line = trip.cb_patrol_message(patrol, 3.0)
    work_zone_line = trip.cb_patrol_message(work_zone, 3.0)
    apron_line = trip.cb_patrol_message(scale_apron, 3.0)
    scale_line = trip.cb_patrol_message(fixed_scale, 3.0)
    cmv_line = trip.cb_patrol_message(cmv, 3.0)
    chain_line = trip.cb_patrol_message(chain, 3.0)

    # Every line still carries the distance and its own side slot.
    for line, post in (
        (patrol_line, patrol),
        (work_zone_line, work_zone),
        (apron_line, scale_apron),
        (scale_line, fixed_scale),
        (cmv_line, cmv),
        (chain_line, chain),
    ):
        assert "3.0" in line or "miles" in line or line.startswith("CB chatter:")
        assert trip._cb_side(post) in line

    # Only the patrol/speed line is a bear report.
    assert "bear" in patrol_line.lower()
    assert "bear" not in work_zone_line.lower()
    assert "bear" not in apron_line.lower()
    assert "bear" not in scale_line.lower()
    assert "bear" not in cmv_line.lower()
    assert "bear" not in chain_line.lower()

    # The work zone talks about enforcement, not a trooper sighting.
    assert "troopers" in work_zone_line.lower()

    # The scale chatter is about logs, and uses only canonical nouns -- never
    # the forbidden "chicken coop" synonym.
    assert "logs" in apron_line.lower()
    assert "logs" in scale_line.lower()
    assert "coop" not in apron_line.lower()
    assert "coop" not in scale_line.lower()

    # The commercial-vehicle unit gets the inspection family too -- logs
    # AND equipment, since a roadside CMV stop is a full equipment check,
    # not just a paperwork check.
    assert "logs" in cmv_line.lower()
    assert "equipment" in cmv_line.lower()
    assert "coop" not in cmv_line.lower()

    # The chain control gets its own line, naming the checkpoint by its
    # ontology-canonical noun rather than calling it a bear.
    assert "chain control" in chain_line.lower()

    # The confidence framing (two drivers / a driver / somebody a while
    # back) is shared across every kind.
    for line in (patrol_line, work_zone_line, apron_line, scale_line, cmv_line, chain_line):
        assert any(marker in line for marker in ("two drivers", "a driver", "somebody"))


def test_cb_tableau_line_reports_a_bear_with_a_customer():
    """The new line kind: a bear who already has somebody stopped.

    Same confidence framing and distance/side slots as ``cb_patrol_message``;
    only the fact differs, and it stays CB-attributed slang.
    """
    trip = _trip()
    post = always_observing_post(at_mi=20.0, kind=KIND_MEDIAN)
    line = trip.cb_tableau_message(post, 3.0)
    assert "bear" in line.lower()
    assert "CB chatter" in line
    assert "somebody stopped" in line.lower()
    assert trip._cb_side(post) in line
    assert "3.0" in line or "miles" in line


def test_spoken_cb_lines_are_capped_for_a_whole_run():
    from freight_fate.sim.trip_models import CB_CALLS_PER_RUN

    assert CB_CALLS_PER_RUN == 2


def test_the_cb_lead_is_sized_in_real_seconds_not_a_flat_distance():
    """A flat five miles is 3.5 real seconds at realistic pacing.

    The CB line takes about seven seconds to speak, so the player used to pass
    the post mid-sentence.
    """
    slow = _trip()
    slow.time_scale = 4.0
    slow.truck.velocity_mps = 65.0 / 2.23694
    fast = _trip()
    fast.time_scale = 40.0
    fast.truck.velocity_mps = 65.0 / 2.23694
    assert fast._enforcement_warning_lookahead_mi() > slow._enforcement_warning_lookahead_mi()


# --- vocabulary -------------------------------------------------------------


_PLAYER_STRING = re.compile(r"""(['"])((?:\\.|(?!\1)[^\\])*)\1""")
# Lowercase only. "Black Bear Road" is a song title in the radio catalog, not
# a driver calling a trooper on the CB.
_CB_SLANG = re.compile(r"(?<![A-Za-z])bears?(?![A-Za-z])")


def test_bear_is_cb_voice_only_in_every_player_facing_string():
    """ "Bear" may appear only inside a clause attributed to the CB.

    It is trade slang. In a warning, a menu, or a status readout the word is
    "trooper" -- and this is the only thing that stops it leaking into new
    strings as the feature grows.
    """
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "bear" not in line.lower():
                continue
            if line.lstrip().startswith("#"):
                continue
            for _quote, body in _PLAYER_STRING.findall(line):
                if not _CB_SLANG.search(body):
                    continue
                if "CB" not in body:
                    offenders.append(f"{path.name}: {body}")
    assert not offenders, offenders


def test_the_safety_record_is_never_spoken_as_a_trade_acronym():
    from freight_fate.models import safety_record

    for score in (0.0, 50.0, 90.0):
        line = safety_record.safety_record_text(score)
        assert line.startswith("Safety record:")
        for jargon in ("ISS", "CSA", "SMS", "score"):
            assert jargon not in line


# --- the safety record ------------------------------------------------------


def test_a_clean_record_is_waved_through_and_a_dirty_one_is_not():
    from freight_fate.models.safety_record import (
        inspection_selection_chance,
        safety_band,
        selection_score,
    )

    clean = selection_score(reputation=80.0, clean_inspections=6)
    dirty = selection_score(
        reputation=20.0,
        citations=4,
        serious_violations=2,
        out_of_service_events=2,
        damage_pct=70.0,
    )
    assert safety_band(clean) == "clean"
    assert safety_band(dirty) == "targeted"
    assert inspection_selection_chance(clean) < 0.15
    assert inspection_selection_chance(dirty) == 1.0


def test_the_safety_record_rides_on_the_profile_and_survives_a_save():
    from freight_fate.models.profile import Profile
    from freight_fate.models.safety_record import refresh_selection_score

    profile = Profile(name="Record")
    profile.driving_record.citations = 3
    refresh_selection_score(profile, damage_pct=60.0)
    assert profile.selection_score > 40.0
    restored = Profile.from_dict(profile.to_dict())
    assert restored.selection_score == profile.selection_score


# --- the cue ladder, on a live drive ---------------------------------------


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Presence", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles,
        1000.0,
        12.0,
        destination_location="Rochester freight market",
    )
    return DrivingState(app.ctx, job, route, phase="delivery")


def _capture_audio(app, monkeypatch):
    played = []
    monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "play", lambda key, **k: played.append(key))
    return played


def test_the_marked_unit_pass_actually_plays(monkeypatch):
    """The shipped, credited, unit-tested pass-by never once played.

    Troopers spawned with intent "cruising" and next_situation returned None
    for cruising, so the asset was unreachable from inside the game.
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        played = _capture_audio(app, monkeypatch)
        d.trip.posts = [always_observing_post(at_mi=5.0)]
        d._enforcement_prev_mi = 4.0
        d.trip.position_mi = 6.0
        d._update_enforcement_watch(0.1)
        # The marker leads; the vehicle whoosh is scheduled behind it.
        assert "enforcement/signature" in played
        d._service_pending_sounds(1.0)
        assert "traffic/trooper_pass" in played
    finally:
        app.shutdown()


def test_the_marker_leads_the_whoosh_rather_than_being_buried_in_it():
    """A garnished whoosh is gone under engine, road, weather and radio.

    traffic/trooper_pass and traffic/car_pass are both tyre-whoosh clips
    differing only by a subtle chirp inside the whoosh. A two-element
    signature -- marker first, at its own level, then the vehicle -- survives
    where a garnished one does not.
    """
    from freight_fate.states.driving_siren import PASS_MARKER_LEAD_S

    assert PASS_MARKER_LEAD_S >= 0.15


def test_every_staffed_post_is_audible_before_it_can_observe_you(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        played = _capture_audio(app, monkeypatch)
        post = always_observing_post(at_mi=6.0, reach_mi=1.0)
        post.announced = False
        d.trip.posts = [post]
        # Still outside the post's reach: it watches from 5.0 up to 6.0.
        d._enforcement_prev_mi = 3.0
        d.trip.position_mi = 4.9
        d._update_enforcement_watch(0.1)
        assert "enforcement/signature" in played
        assert post.announced is True
        assert d.trip.position_mi < post.watch_start_mi
    finally:
        app.shutdown()


def test_the_siren_is_a_held_loop_that_rises():
    """The rise is the "he is coming up behind you" information.

    The old siren was one mono, centred, fixed-level shot that never
    repeated, and the whole pull-over update contained no audio at all.
    """
    from freight_fate.states.driving_siren import (
        SIREN_FULL_LEVEL,
        SIREN_RISE_S,
        SIREN_START_LEVEL,
        SirenLoop,
    )

    class _Audio:
        def __init__(self):
            self.started = 0
            self.levels = []
            self.released = 0

        def start_sustain_loop(self, *a, **k):
            self.started += 1

        def set_loop_volume(self, _ch, volume):
            self.levels.append(volume)

        def set_loop_pan(self, _ch, _pan):
            pass

        def release_sustain_loop(self, _ch, fade_ms=0):
            self.released += 1

    audio = _Audio()
    siren = SirenLoop()
    for _ in range(int(SIREN_RISE_S / 0.2) + 1):
        siren.hold(audio, pan=0.0)
        siren.service(audio, 0.2)
    assert audio.started == 1  # held, not re-triggered every frame
    assert audio.levels[0] == pytest.approx(SIREN_START_LEVEL)
    assert audio.levels[-1] == pytest.approx(SIREN_FULL_LEVEL)
    # Dead man's switch: stop asserting it and it releases itself.
    siren.service(audio, 1.0)
    assert audio.released == 1
    assert siren.active is False


def test_the_enforcement_signature_is_deterministic_and_not_a_radio_timbre():
    from freight_fate.states.driving_siren import (
        SIGNATURE_HIGH_HZ,
        SIGNATURE_LOW_HZ,
        enforcement_signature_wav,
    )

    assert enforcement_signature_wav() == enforcement_signature_wav()
    assert enforcement_signature_wav()[:4] == b"RIFF"
    # Two dry gated tones a fixed interval apart. The catalog ships dozens of
    # always-available police scanner streams, so the enforcement earcon must
    # not borrow police-radio timbre for its identity.
    assert SIGNATURE_HIGH_HZ > SIGNATURE_LOW_HZ


def test_the_siren_is_off_the_shared_sfx_bus():
    """So it can be raised without dragging every clunk and chime up with it."""
    from freight_fate.audio import CH_SCALE, CH_SIREN, RESERVED, _loop_category

    assert _loop_category(CH_SIREN) == "siren"
    # Every named channel has to sit inside the reserved block, or pygame's
    # allocator is free to steal it under one-shot pressure.
    assert max(CH_SIREN, CH_SCALE) < RESERVED


def test_a_stop_cuts_the_radio_rather_than_ducking_it(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        stopped = []
        monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx.audio, "stop_music", lambda fade: stopped.append(fade))
        d._cut_radio_for_stop()
        assert stopped  # cut, not merely lowered
        assert d._radio_cut_for_stop is True
    finally:
        app.shutdown()


def test_a_cue_ducks_the_radio_on_its_own_field(monkeypatch):
    """Never the picket duck: that one self-heals and would drag this away."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        d._duck_radio_for_cue()
        assert d._radio_cue_duck < 1.0
        assert d._radio_picket_duck == 1.0
        d._service_radio_cue_duck(10.0)
        assert d._radio_cue_duck == 1.0
    finally:
        app.shutdown()


def test_enforcement_defers_while_the_cab_already_has_a_demand(monkeypatch):
    """One demand on the driver at a time. Deferred, never dropped."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture_audio(app, monkeypatch)
        post = always_observing_post(at_mi=6.0, reach_mi=2.0)
        d.trip.posts = [post]
        d.trip.position_mi = 5.5
        d._enforcement_prev_mi = 5.4
        d.truck.velocity_mps = 120.0 / 2.23694  # flagrant
        d._over_limit_mi = OBSERVE_HOLD_MI * 3
        d._hazard_deadline = 2.0
        d._update_enforcement_watch(0.1)
        assert d._pull_over is None
        assert post.id in d._deferred_post_ids
        assert post.declined is False  # it still has its look owing
        d._hazard_deadline = None
        d._enforcement_prev_mi = 5.5
        d._over_limit_mi = OBSERVE_HOLD_MI * 3
        d._update_enforcement_watch(0.1)
        assert d._pull_over == "lights"
    finally:
        app.shutdown()


def test_a_deferred_look_survives_the_truck_leaving_the_post_behind(monkeypatch):
    """The officer saw you; the hazard only postponed the lights.

    ``_deferred_post_ids`` was written and never read anywhere, so "defer,
    never drop" only held while the post still covered the truck's mile. A
    hazard window outlasts a one-mile radar reach several times over at any
    pacing, so in practice every look that landed during one was thrown away
    (Jerry, 2026-08-11: whole routes over the limit with nothing happening).
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture_audio(app, monkeypatch)
        post = always_observing_post(at_mi=6.0, reach_mi=1.0)
        d.trip.posts = [post]
        d.trip.position_mi = 5.5
        d._enforcement_prev_mi = 5.4
        d.truck.velocity_mps = 120.0 / 2.23694  # flagrant
        d._over_limit_mi = OBSERVE_HOLD_MI * 3
        d._hazard_deadline = 6.0
        d._update_enforcement_watch(0.1)
        assert d._pull_over is None  # one demand on the driver at a time

        # The hazard runs long enough that the truck is well past the post by
        # the time the cab is quiet. The stop still happens.
        d.trip.position_mi = 9.0
        d._enforcement_prev_mi = 9.0
        d._hazard_deadline = None
        assert not d.trip.posts_watching(d.trip.position_mi)
        d._update_enforcement_watch(0.1)
        assert d._pull_over == "lights"
    finally:
        app.shutdown()


def test_a_trooper_who_never_caught_up_loses_you(monkeypatch):
    """A held look is not a debt collected fifty miles later."""
    from freight_fate.app import App
    from freight_fate.states.driving_enforcement import DEFERRED_STOP_MAX_MI

    app = App()
    try:
        d = _driving(app)
        _capture_audio(app, monkeypatch)
        post = always_observing_post(at_mi=6.0, reach_mi=1.0)
        d.trip.posts = [post]
        d.trip.position_mi = 5.5
        d._enforcement_prev_mi = 5.4
        d.truck.velocity_mps = 120.0 / 2.23694
        d._over_limit_mi = OBSERVE_HOLD_MI * 3
        d._hazard_deadline = 6.0
        d._update_enforcement_watch(0.1)
        assert d._pull_over is None

        d.trip.position_mi = 5.5 + DEFERRED_STOP_MAX_MI + 1.0
        d._enforcement_prev_mi = d.trip.position_mi
        d._hazard_deadline = None
        d._update_enforcement_watch(0.1)
        assert d._pull_over is None
    finally:
        app.shutdown()


def test_a_closed_scale_says_nothing_and_an_open_one_speaks(monkeypatch):
    """The swell says "scale"; the absence of speech says "closed"."""
    from enforcement_helpers import open_scale_post

    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop

    app = App()
    try:
        d = _driving(app)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx, "say_event", lambda text, *a, **k: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        stop = RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))
        d.trip.stops = [stop]
        d.trip.position_mi = 9.0
        d.truck.velocity_mps = 45.0 / 2.23694

        closed = always_observing_post(at_mi=10.0, kind=KIND_SCALE_APRON)
        closed.anchor = stop.key
        d.trip.posts = [closed]
        d._check_weigh_station_enforcement(8.9)
        assert not [s for s in spoken if "weigh station" in s.lower()]

        d.trip.posts = [open_scale_post(stop)]
        d._weigh_station_notice_key = ""
        d._check_weigh_station_enforcement(8.9)
        assert [s for s in spoken if "Open weigh station ahead" in s]
    finally:
        app.shutdown()


def _scale_crossing(app, monkeypatch, *, mph, armed):
    """Set a truck onto the gore of an open scale's own exit and run one frame.

    The frame is the real one: the bypass check, then the exit watch, then the
    verdict, in exactly the order ``DrivingState.update`` calls them.
    """
    from enforcement_helpers import open_scale_post

    from freight_fate.sim.trip import RoadStop

    d = _driving(app)
    # A bypass is caught, not certain (85 percent) -- seed 1 lands under that
    # chance for this exact scale key, so a bypass here is deterministic.
    d.trip_seed = 1
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, *a, **k: spoken.append(text))
    monkeypatch.setattr(app.ctx, "say_event", lambda text, *a, **k: spoken.append(text))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "save_profile", lambda *a, **k: None)
    stop = RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))
    d.trip.stops = [stop]
    d.trip.posts = [open_scale_post(stop)]
    d.trip.position_mi = 9.95
    d.truck.velocity_mps = mph / 2.23694
    if armed:
        d._exit_stop = stop
        d._exit_signal_on = True
        d._exit_lane_alignment = 1.0
        d.lane.lane = 0
    previous_mi = d.trip.position_mi
    d.trip.position_mi = 10.02
    d._check_weigh_station_enforcement(previous_mi)
    d._update_exit(0.07, 0.1)
    d._resolve_weigh_station_bypass()
    return d, stop, spoken


def test_taking_the_scales_own_ramp_is_never_a_bypass(monkeypatch):
    """Signalling, slowing, and turning in is the compliant thing to do.

    A tester signalled for the scale, dropped to eighteen, and was fined for
    blowing past it while he was on its ramp (log, 2026-08-10). The gore is
    crossed at ramp speed by definition, so speed alone can never tell a
    check-in from a bypass.
    """
    from freight_fate.app import App

    app = App()
    try:
        d, stop, spoken = _scale_crossing(app, monkeypatch, mph=18.0, armed=True)
        assert d._pull_over is None
        assert d._ramp_stop is not None and d._ramp_stop.key == stop.key
        assert not [s for s in spoken if "Scale bypass enforcement" in s]
        assert [s for s in spoken if "You take the exit for" in s]
    finally:
        app.shutdown()


def test_arming_the_scales_exit_and_not_taking_it_is_still_a_bypass(monkeypatch):
    """The signal is not the compliance; pulling in is.

    Too fast for the ramp is a miss, and a miss past an open scale is the
    same bypass it would be with no signal at all -- otherwise flicking the
    signal on would buy a free pass at any speed.
    """
    from freight_fate.app import App

    app = App()
    try:
        d, _stop, spoken = _scale_crossing(app, monkeypatch, mph=62.0, armed=True)
        assert d._ramp_stop is None
        assert d._pull_over == "lights"
        assert [s for s in spoken if "Scale bypass enforcement" in s]
    finally:
        app.shutdown()


def test_rolling_past_an_open_scale_is_still_a_bypass(monkeypatch):
    """The plain case, unchanged: no signal, highway speed, a fine."""
    from freight_fate.app import App

    app = App()
    try:
        d, _stop, spoken = _scale_crossing(app, monkeypatch, mph=62.0, armed=False)
        assert d._pull_over == "lights"
        assert [s for s in spoken if "Scale bypass enforcement" in s]
    finally:
        app.shutdown()


# --- calibration: what presence costs a clean driver, and a reckless one ----


def _walk(trip, *, over, damage, pack=0, duty=1.0, recover_mi=0.0, seed=0):
    """Drive the route in position steps and count the pull-overs.

    Position steps, not physics frames, on purpose: the whole claim of the
    distance-quantised model is that the outcome depends on where you were and
    how fast, never on how many frames it took to get there.
    """
    import random as _random

    from freight_fate.sim.enforcement_posts import post_seed

    for post in trip.posts:
        post.announced = True
    step = 0.05
    stops = 0
    mile = 0.0
    quiet_until = -1.0
    hot = True
    duty_rng = _random.Random(f"duty:{seed}")
    while mile < trip.route.miles:
        mile += step
        if int(mile / 5.0) != int((mile - step) / 5.0):
            hot = duty_rng.random() < duty
        # After a pull-over the truck is stopped on the shoulder and has to
        # get back up to speed; nobody is twenty over for the next few miles.
        legal = mile < quiet_until or not hot
        limit, _ = trip.speed_limit_at(mile)
        sample = RoadSample(
            position_mi=mile,
            speed_mph=limit + (5.0 if legal else over),
            limit_mph=limit,
            damage_pct=damage,
            pack_neighbours=pack,
            over_limit_mi=0.0 if legal else OBSERVE_HOLD_MI * 2,
        )
        for post in trip.posts_watching(mile):
            if post.declined:
                continue
            found = observe(post, sample)
            if found is None:
                continue
            post.declined = True
            key = post_seed(trip._seed, post.id, f"observe:{found.what}:{round(mile, 1)}")
            if _random.Random(key).random() < found.confidence:
                stops += 1
                quiet_until = mile + recover_mi
    return stops


@pytest.mark.timeout(300)
def test_a_clean_driver_hears_the_police_constantly_and_pays_nothing():
    """The whole point. Present means heard, not charged.

    The old model gave a clean driver zero contacts and zero cost, which reads
    as a country with no police in it.
    """
    for a, b in (("Chicago", "Denver"), ("Los Angeles", "Phoenix")):
        for seed in range(4):
            trip = _trip(a, b, seed=seed)
            assert trip.audible_enforcement_contacts()
            assert _walk(trip, over=5.0, damage=0.0, seed=seed) == 0


@pytest.mark.timeout(300)
def test_a_reckless_driver_meets_the_same_road_and_a_very_different_bill():
    """Presence is identical; consequence is not."""
    for a, b in (("Chicago", "Denver"), ("Los Angeles", "Phoenix")):
        clean_contacts = []
        reckless_contacts = []
        rates = []
        for seed in range(4):
            clean = _trip(a, b, seed=seed)
            clean_contacts.append(len(clean.audible_enforcement_contacts()))
            trip = _trip(a, b, seed=seed)
            reckless_contacts.append(len(trip.audible_enforcement_contacts()))
            stops = _walk(trip, over=22.0, damage=60.0, duty=0.5, recover_mi=25.0, seed=seed)
            rates.append(stops / trip.route.miles * 500.0)
        # The world does not change shape for a bad driver.
        assert clean_contacts == reckless_contacts
        average = sum(rates) / len(rates)
        assert 2.0 <= average <= 5.0, f"{a}->{b} averaged {average:.1f} stops per 500 miles"


@pytest.mark.timeout(300)
def test_speeding_scales_from_free_to_expensive_with_no_flat_spot():
    """Being seen is now the ONLY thing speeding costs.

    With the silent at-delivery charge deleted, this model is the whole of
    what stands between a speeder and impunity, so the curve between the two
    has to be a curve. A driver inside the leeway pays nothing at all; one
    drifting over occasionally carries real risk without certainty; one
    holding twenty over habitually is stopped several times a run.
    """
    route_pairs = (("Chicago", "Denver"), ("Los Angeles", "Phoenix"))
    for a, b in route_pairs:

        def rate(**kw):
            totals = []
            for seed in range(6):
                trip = _trip(a, b, seed=seed)  # noqa: B023
                totals.append(_walk(trip, seed=seed, **kw) / trip.route.miles * 500.0)
            return sum(totals) / len(totals)

        legal = rate(over=5.0, damage=0.0)
        occasional = rate(over=13.0, damage=0.0, duty=0.2, recover_mi=25.0)
        habitual = rate(over=22.0, damage=0.0, duty=0.5, recover_mi=25.0)
        assert legal == 0.0, f"{a}->{b}: driving legally cost {legal:.2f} stops"
        assert 0.15 <= occasional <= 1.5, (
            f"{a}->{b}: an occasional speeder saw {occasional:.2f} stops per 500 miles "
            "-- that is either immunity or certainty, and it should be neither"
        )
        assert habitual >= 2.0, f"{a}->{b}: a habitual speeder saw only {habitual:.2f}"
        assert habitual > occasional * 3.0


@pytest.mark.timeout(300)
def test_riding_in_a_pack_is_a_real_tactic_over_a_whole_run():
    """The unit test proves the factor; this proves it survives a run."""
    alone = []
    packed = []
    for seed in range(4):
        alone.append(
            _walk(_trip(seed=seed), over=16.0, damage=20.0, duty=0.5, recover_mi=25.0, seed=seed)
        )
        packed.append(
            _walk(
                _trip(seed=seed),
                over=16.0,
                damage=20.0,
                duty=0.5,
                recover_mi=25.0,
                pack=4,
                seed=seed,
            )
        )
    assert sum(packed) < sum(alone)


@pytest.mark.timeout(300)
def test_the_same_driving_through_the_same_road_produces_the_same_outcome():
    a = _walk(_trip(seed=3), over=18.0, damage=30.0, duty=0.5, recover_mi=25.0, seed=3)
    b = _walk(_trip(seed=3), over=18.0, damage=30.0, duty=0.5, recover_mi=25.0, seed=3)
    assert a == b


# --- the setting, and what it promises --------------------------------------


def test_how_loud_the_road_sounds_comes_from_the_road():
    """The slider's replacement: the same number that places the posts.

    A hot-region interstate at the afternoon peak should sound more policed
    than a cold-region two-lane at four in the morning, and it should do it
    without the player choosing anything.
    """
    trip = _trip()
    at = trip._post_density_at(trip.total_miles / 2.0)
    assert at > 0.0
    # It is the placement number itself, not a parallel formula that could
    # drift away from it.
    from freight_fate.states.driving_enforcement import EnforcementWatchMixin

    source = EnforcementWatchMixin._ambience_scale.__doc__ or ""
    assert "placement" in source.lower()


def test_an_empty_crossover_is_never_audible():
    """The cue that read as a trooper ignoring a speeder, because it was.

    An unstaffed post cannot observe anyone, so a pass-by earcon for one is a
    police presence the player can hear and can never be caught by. Whatever
    the road's own presence works out to, an empty post stays silent.
    """
    watch = (SRC / "states" / "driving_enforcement.py").read_text(encoding="utf-8")
    marker = watch.index("if not post.staffed:")
    block = watch[marker : marker + 700]
    assert "continue" in block
    assert "_play_marked_unit_pass" not in block.split("continue")[0]


def test_an_open_scale_reads_the_safety_record_aloud(monkeypatch):
    """The screening lane's decision, and the reason for it, in plain words.

    The decision is a real seeded draw -- a clean driver is waved through
    nearly always, not always -- so this pins the wording and the odds over a
    spread of trips rather than one lucky roll.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop
    from freight_fate.states.driving_rest_states import RestStopState

    def _check_in(app, seed, *, citations, reputation):
        d = _driving(app)
        d.trip_seed = seed
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, *a, **k: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        app.ctx.profile.driving_record.citations = citations
        app.ctx.profile.driving_record.serious_violations = [0.0] * citations
        app.ctx.profile.career.reputation = reputation
        stop = RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))
        RestStopState(app.ctx, d, stop)._inspect()
        return next(s for s in spoken if "Inspection check-in complete" in s)

    app = App()
    try:
        clean_lines = [_check_in(app, s, citations=0, reputation=85.0) for s in range(20)]
        waved = [line for line in clean_lines if "wave you straight back" in line]
        assert len(waved) >= 16  # a clean record is waved through nearly every time
        assert all("Safety record: clean" in line for line in clean_lines)
        for line in clean_lines:
            for jargon in ("ISS", "CSA"):
                assert jargon not in line

        dirty = [_check_in(app, s, citations=5, reputation=10.0) for s in range(6)]
        assert all("pull you into the inspection lane" in line for line in dirty)
        assert all("Safety record: targeted" in line for line in dirty)
    finally:
        app.shutdown()
