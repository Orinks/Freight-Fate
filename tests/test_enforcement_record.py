"""The driving record: fines that scale, a serious-violation ladder, major
offenses that actually disqualify a CDL, and dispatch trust that slides.

The bug behind all of it: the game recorded pursuit felonies on the trip
snapshot, then threw the snapshot away. Nothing downstream ever read them, so
a driver could run from troopers twice and keep every load on the board.
"""

from speech_capture import speech_stub

DAY = 24.0


def _record(**kwargs):
    from freight_fate.models.enforcement import DrivingRecord

    return DrivingRecord(**kwargs)


# --- money ------------------------------------------------------------------


def test_speeding_fine_climbs_with_how_far_over_the_limit():
    from freight_fate.models.enforcement import speeding_citation_fine

    mild = speeding_citation_fine(8.0)
    serious = speeding_citation_fine(15.0)
    reckless = speeding_citation_fine(31.0)
    assert mild < serious < reckless
    # The 15-mph step is where a citation also becomes a serious violation.
    assert serious >= 1_000.0


def test_repeat_offenders_pay_more_up_to_the_cap():
    # Priors compound the way real repeat offenders are charged "double, even
    # triple" a standard fine -- but the step stops at
    # CITATION_REPEAT_MAX_MULTIPLIER. Uncapped it reached 39,600 for a scale
    # bypass in roadwork, which reads as a broken game rather than a severe
    # one. See the constant for why solvency, not statute, sets the ceiling.
    from freight_fate.models.enforcement import (
        CITATION_REPEAT_MAX_MULTIPLIER,
        citation_fine,
        speeding_citation_fine,
    )

    first = speeding_citation_fine(16.0, prior_citations=0)
    third = speeding_citation_fine(16.0, prior_citations=2)
    assert third > first
    # Beyond the cap the money stops climbing; the record keeps escalating.
    many = speeding_citation_fine(35.0, prior_citations=20)
    plenty = speeding_citation_fine(35.0, prior_citations=40)
    assert plenty == many
    assert citation_fine(900.0, 99) == 900.0 * CITATION_REPEAT_MAX_MULTIPLIER


def test_priors_climb_monotonically_and_then_hold():
    from freight_fate.models.enforcement import citation_fine, speeding_citation_fine

    escalating = [speeding_citation_fine(16.0, prior_citations=n) for n in range(12)]
    assert escalating == sorted(escalating)  # never cheaper for more priors
    assert len(set(escalating)) > 1  # and it really does climb before holding
    # The same rule governs non-speeding citations.
    assert citation_fine(900.0, 30) == citation_fine(900.0, 5)
    assert citation_fine(900.0, 2) > citation_fine(900.0, 0)


def test_no_single_citation_can_repossess_a_truck_on_its_own():
    """The binding balance constraint, not a statutory one.

    An owner-operator who owes past REPOSSESSION_FLOOR loses the tractor. If
    one stop could reach that, a traffic stop would end a career outright --
    which no player reads as a rule, only as the game breaking. This pins the
    worst case the game can actually produce: the top speeding step, a
    habitual offender, inside a construction zone.
    """
    from freight_fate.models import enforcement
    from freight_fate.models.solvency import REPOSSESSION_FLOOR

    worst = enforcement.speeding_citation_fine(99.0, prior_citations=999, construction_zone=True)
    assert worst < REPOSSESSION_FLOOR
    flat = max(
        enforcement.citation_fine(base, 999, construction_zone=True)
        for base in (
            enforcement.UNSAFE_DAMAGE_FINE,
            enforcement.WEIGH_STATION_BYPASS_FINE,
            enforcement.FAILURE_TO_STOP_CITATION_FINE,
            enforcement.WORK_ZONE_BARRELS_FINE,
        )
    )
    assert flat < REPOSSESSION_FLOOR


def test_the_construction_zone_doubling_survives_the_repeat_cap():
    """Capping the step, not the total -- so the spoken line stays true.

    The player is told a fine was doubled because they were in a construction
    zone. If the cap applied to the combined figure it would silently swallow
    that for any repeat offender and make the sentence a lie.
    """
    from freight_fate.models.enforcement import citation_fine

    for priors in (0, 1, 2, 5, 40):
        plain = citation_fine(1_800.0, priors)
        zoned = citation_fine(1_800.0, priors, construction_zone=True)
        assert zoned == round(plain * 2.0, 2)


def test_every_fine_is_anchored_to_the_real_penalty_it_names():
    """The amounts themselves, so a rebalance is a deliberate edit here too."""
    from freight_fate.models import enforcement as e

    assert e.UNSAFE_DAMAGE_FINE == 2300.0  # FMCSA unsafe conditions: 2,304
    assert e.WEIGH_STATION_BYPASS_FINE == 1800.0  # CA/NY pass 1,000 on a first offense
    assert e.CHAIN_LAW_FINE == 580.0  # Colorado: 500 plus a 79-dollar surcharge
    assert e.FOLLOWING_TOO_CLOSE_FINE == 600.0  # a 383.51 Table 2 serious violation
    assert e.LANE_MISUSE_FINE == 500.0  # Virginia's highway safety corridor figure
    assert e.LIGHTS_FINE == 350.0
    assert e.FAILURE_TO_STOP_CITATION_FINE == 1500.0
    assert e.FAILURE_TO_STOP_FINE == 5000.0  # already a felony-sized number
    assert e.WORK_ZONE_BARRELS_FINE == 1000.0  # Missouri RSMo 304.585, top of range
    assert e.SPEEDING_FINE_STEPS[0][1] == 250.0
    assert e.SPEEDING_FINE_STEPS[-1][1] == 2500.0


def test_the_shoulder_parking_ticket_moved_with_the_rest():
    from freight_fate.sim import hos

    assert hos.SHOULDER_FINE == 400.0


def test_a_fine_earned_in_a_construction_zone_is_doubled():
    from freight_fate.models.enforcement import (
        CONSTRUCTION_ZONE_FINE_MULTIPLIER,
        WEIGH_STATION_BYPASS_FINE,
        citation_fine,
        speeding_citation_fine,
    )

    assert CONSTRUCTION_ZONE_FINE_MULTIPLIER == 2.0
    plain = citation_fine(WEIGH_STATION_BYPASS_FINE)
    in_zone = citation_fine(WEIGH_STATION_BYPASS_FINE, construction_zone=True)
    assert plain == 1_800.0
    assert in_zone == 3_600.0
    # Speeding doubles the same way; it is not exempt for going through its
    # own schedule first.
    assert speeding_citation_fine(16.0, construction_zone=True) == (
        speeding_citation_fine(16.0) * 2.0
    )


def test_priors_and_the_construction_zone_compound_rather_than_add():
    """The owner's explicit call: 1,800 x 1.5 x 2 on a second offense."""
    from freight_fate.models.enforcement import WEIGH_STATION_BYPASS_FINE, citation_fine

    second_offense_in_zone = citation_fine(WEIGH_STATION_BYPASS_FINE, 1, construction_zone=True)
    assert second_offense_in_zone == 5_400.0
    # Adding the two multipliers instead of compounding them would give 2.5x.
    assert second_offense_in_zone != WEIGH_STATION_BYPASS_FINE * 2.5


def test_a_missing_driving_record_reads_as_a_first_offender():
    from types import SimpleNamespace

    from freight_fate.models.enforcement import career_citations

    assert career_citations(SimpleNamespace()) == 0
    assert career_citations(SimpleNamespace(driving_record=None)) == 0
    assert career_citations(SimpleNamespace(driving_record=_record(citations=3))) == 3


def test_the_doubled_fine_says_why_in_plain_player_language():
    from freight_fate.models.enforcement import construction_zone_fine_clause

    assert construction_zone_fine_clause(False) == ""
    clause = construction_zone_fine_clause(True)
    assert "doubled" in clause
    # The canonical spoken noun from docs/ontology.md, never "work zone".
    assert "construction zone" in clause
    assert "work zone" not in clause


# --- the serious-violation ladder ------------------------------------------


def test_first_serious_violation_does_not_suspend():
    r = _record()
    assert r.record_serious_violation(100.0) == 1
    assert not r.suspended(100.0)


def test_second_serious_violation_suspends_the_cdl_for_sixty_days():
    from freight_fate.models.enforcement import SERIOUS_SECOND_SUSPENSION_DAYS

    r = _record()
    r.record_serious_violation(100.0)
    assert r.record_serious_violation(200.0) == 2
    assert r.suspended(200.0)
    assert round(r.days_left(200.0)) == SERIOUS_SECOND_SUSPENSION_DAYS


def test_third_serious_violation_suspends_for_a_hundred_and_twenty_days():
    from freight_fate.models.enforcement import SERIOUS_THIRD_SUSPENSION_DAYS

    r = _record()
    for at in (100.0, 200.0):
        r.record_serious_violation(at)
    # Serve the 60 days out, then earn a third.
    later = r.suspended_until_h + 1.0
    assert r.record_serious_violation(later) == 3
    assert round(r.days_left(later)) == SERIOUS_THIRD_SUSPENSION_DAYS


def test_violations_older_than_three_years_stop_counting():
    from freight_fate.models.enforcement import SERIOUS_WINDOW_DAYS

    r = _record()
    r.record_serious_violation(0.0)
    much_later = (SERIOUS_WINDOW_DAYS + 10) * DAY
    assert r.serious_in_window(much_later) == 0
    # So the next one is a first offense again, not a suspension.
    assert r.record_serious_violation(much_later) == 1
    assert not r.suspended(much_later)


# --- major offenses: Jerry's case ------------------------------------------


def test_first_major_offense_disqualifies_the_cdl_for_a_year():
    from freight_fate.models.enforcement import (
        MAJOR_FIRST_DISQUALIFICATION_DAYS,
        SUSPENSION_MAJOR,
    )

    r = _record()
    assert r.record_major_offense(50.0) == SUSPENSION_MAJOR
    assert r.suspended(50.0)
    assert round(r.days_left(50.0)) == MAJOR_FIRST_DISQUALIFICATION_DAYS
    assert not r.lifetime_disqualified


def test_second_major_offense_is_a_lifetime_disqualification():
    from freight_fate.models.enforcement import SUSPENSION_LIFETIME

    r = _record()
    r.record_major_offense(50.0)
    assert r.record_major_offense(60.0) == SUSPENSION_LIFETIME
    assert r.lifetime_disqualified
    # There is no date this clears, at any point on the career clock.
    assert r.suspended(999_999.0)


def test_a_served_suspension_gives_the_licence_back():
    r = _record()
    r.record_major_offense(50.0)
    cleared = r.suspended_until_h + 1.0
    assert not r.suspended(cleared)
    r.serve_until(cleared)
    assert r.suspended_until_h == 0.0
    assert r.suspension_reason == ""


# --- fatigue (49 CFR 392.3) -------------------------------------------------


def test_first_run_off_road_asleep_costs_standing_not_the_licence():
    r = _record()
    count, serious = r.record_fatigue_event(100.0)
    assert (count, serious) == (1, 0)
    assert not r.suspended(100.0)


def test_second_run_off_road_asleep_is_a_serious_violation():
    r = _record()
    r.record_fatigue_event(100.0)
    count, serious = r.record_fatigue_event(200.0)
    assert count == 2
    assert serious == 1
    assert r.serious_in_window(200.0) == 1


# --- dispatch trust ---------------------------------------------------------


def test_a_clean_driver_sees_the_board_they_have_always_seen():
    from freight_fate.models.enforcement import (
        TRUST_FULL,
        board_offers_for_reputation,
        trust_band,
    )

    assert board_offers_for_reputation(6, 50.0) == 6
    assert board_offers_for_reputation(6, 100.0) == 6
    assert trust_band(50.0) == TRUST_FULL  # where every new career starts


def test_dispatch_trust_slides_the_whole_way_down():
    from freight_fate.models.enforcement import board_offers_for_reputation

    steps = [board_offers_for_reputation(6, rep) for rep in (50.0, 40.0, 25.0, 5.0)]
    assert steps == sorted(steps, reverse=True)
    assert steps[0] > steps[-1]
    assert steps[-1] == 1


def test_losing_trust_takes_back_the_right_to_pick_your_own_loads():
    from freight_fate.models.dispatch_policy import SENIOR_LOAD_CHOICE_LEVEL, dispatch_policy
    from freight_fate.models.profile import Profile

    p = Profile(name="Senior")
    p.career.xp = 200_000.0  # comfortably past the load-choice level
    assert p.career.level >= SENIOR_LOAD_CHOICE_LEVEL
    assert not dispatch_policy(p).assigns_load
    p.career.reputation = 18.0
    assert dispatch_policy(p).assigns_load  # back to taking what dispatch gives
    p.career.reputation = 10.0
    assert dispatch_policy(p).decline_budget == 0  # and no refusals left at all


# --- persistence and retroactivity -----------------------------------------


def test_the_record_survives_save_and_load():
    from freight_fate.models.profile import Profile

    p = Profile(name="Jerry")
    p.game_hours = 500.0
    p.driving_record.record_major_offense(p.game_hours)
    p.driving_record.record_citation(1_000.0)
    restored = Profile.from_dict(p.to_dict())
    assert restored.driving_record.major_count == 1
    assert restored.driving_record.citations == 1
    assert restored.driving_record.suspended(p.game_hours)


def test_a_legacy_save_counts_the_felonies_it_still_holds():
    from freight_fate.models.profile import Profile

    p = Profile(name="Jerry")
    data = p.to_dict()
    data.pop("driving_record")
    # Exactly what the old build wrote: the felony count lived on the trip.
    data["active_trip"] = {"failure_to_stop_count": 2, "speeding_tickets": 1}
    data["game_hours"] = 400.0
    restored = Profile.from_dict(data)
    record = restored.driving_record
    assert record.major_count == 2
    assert record.lifetime_disqualified  # no amnesty
    assert record.notice_pending


def test_a_clean_legacy_save_gets_a_clean_record_and_no_notice():
    from freight_fate.models.profile import Profile

    p = Profile(name="Clean")
    data = p.to_dict()
    data.pop("driving_record")
    restored = Profile.from_dict(data)
    assert restored.driving_record.clean(restored.game_hours)
    assert not restored.driving_record.notice_pending


# --- spoken surfaces --------------------------------------------------------


def test_standing_is_said_plainly_and_names_the_next_consequence():
    from freight_fate.models.enforcement import standing_text
    from freight_fate.models.profile import Profile

    p = Profile(name="Driver")
    p.game_hours = 100.0
    assert standing_text(p) == "Record: clean."
    p.driving_record.record_serious_violation(p.game_hours)
    text = standing_text(p)
    assert "one serious violation" in text
    assert "60 days" in text
    assert "strike" not in text.lower()  # that noun belongs to the per-trip counter


def test_a_suspended_record_says_when_it_clears():
    from freight_fate.models.enforcement import career_menu_status, standing_text
    from freight_fate.models.profile import Profile

    p = Profile(name="Driver")
    p.game_hours = 100.0
    # The ladder suspends; a major offense disqualifies. Two nouns, two things.
    p.driving_record.record_serious_violation(p.game_hours)
    p.driving_record.record_serious_violation(p.game_hours)
    assert "suspended" in career_menu_status(p)
    assert "60 days" in standing_text(p)

    q = Profile(name="Jerry")
    q.game_hours = 100.0
    q.driving_record.record_major_offense(q.game_hours)
    assert "disqualified" in career_menu_status(q)
    text = standing_text(q)
    assert "365 days" in text
    assert "clears" in text
    assert "hours" not in text  # served in game days, never raw hours


def test_the_lifetime_line_states_the_facts_and_the_way_forward():
    from freight_fate.models.enforcement import SUSPENSION_LIFETIME
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving_rest_states import _major_offense_text

    p = Profile(name="Jerry")
    p.driving_record.record_major_offense(10.0)
    p.driving_record.record_major_offense(20.0)
    text = _major_offense_text(p, SUSPENSION_LIFETIME, 20.0)
    assert "for life" in text
    assert "start a new career" in text
    assert "keeps every dollar" in text
    # No blame language, and no promise of options that do not exist.
    for scold in ("you should have", "your fault", "stupid", "punish"):
        assert scold not in text.lower()


# --- the road: what the stops now write ------------------------------------


def _driving(app, name="Jerry"):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name=name, current_city="Buffalo")
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


def _quiet(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    return spoken


def test_running_from_the_stop_writes_a_major_offense_on_the_career():
    from freight_fate.app import App
    from freight_fate.states.driving import FelonyStopState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        FelonyStopState(app.ctx, d)
        assert p.driving_record.major_count == 1
        assert p.driving_record.suspended(p.game_hours)
    finally:
        app.shutdown()


def test_a_second_pursuit_ends_this_career_driving_for_good(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import FelonyStopState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        p.driving_record.record_major_offense(0.0)  # Jerry's first one
        state = FelonyStopState(app.ctx, d)
        state.announce_entry()
        assert p.driving_record.lifetime_disqualified
        assert any("for life" in line for line in spoken)
        assert any("start a new career" in line for line in spoken)
    finally:
        app.shutdown()


def test_a_stop_that_suspends_the_cdl_does_not_send_you_back_out_driving(monkeypatch):
    # The stop menu used to offer "Pull back onto the highway" no matter what
    # had just happened -- so a driver whose licence had been pulled seconds
    # earlier was invited to drive on, with no way to end the run from the
    # shoulder. A suspended driver is done for now; the run ends here.
    from freight_fate.app import App
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        p.driving_record.record_serious_violation(p.game_hours)  # one already on file
        d.speeding_tickets = 1
        stop = TrafficStopState(app.ctx, d, signaled=False, over=22.0, limit=65.0)
        assert p.driving_record.suspended(p.game_hours)
        labels = [item.text for item in stop.build_items()]
        assert not any("highway" in label for label in labels)
        assert any("terminal" in label.lower() for label in labels)
    finally:
        app.shutdown()


def test_an_ordinary_ticket_still_pulls_back_onto_the_highway(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        d = _driving(app)
        _quiet(app, monkeypatch)
        d.speeding_tickets = 1
        stop = TrafficStopState(app.ctx, d, signaled=True, over=11.0, limit=65.0)
        assert not app.ctx.profile.driving_record.suspended(app.ctx.profile.game_hours)
        assert any("highway" in item.text for item in stop.build_items())
    finally:
        app.shutdown()


def test_the_suspended_stop_says_the_run_is_over_and_why(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        p.driving_record.record_serious_violation(p.game_hours)
        d.speeding_tickets = 1
        stop = TrafficStopState(app.ctx, d, signaled=False, over=22.0, limit=65.0)
        stop.announce_entry()
        said = " ".join(spoken)
        assert "cannot drive" in said or "may not drive" in said
        assert "load" in said  # what happens to the freight is stated
    finally:
        app.shutdown()


def test_an_enforcement_stop_that_suspends_also_ends_the_run(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import EnforcementStopState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        p.driving_record.record_serious_violation(p.game_hours)
        stop = EnforcementStopState(
            app.ctx,
            d,
            title="Enforcement stop",
            summary="Unsafe equipment.",
            fine=900.0,
            reputation_hit=5.0,
            signaled=True,
            return_message="Back on the highway.",
            warned=True,  # a serious violation: this is the second
        )
        assert p.driving_record.suspended(p.game_hours)
        assert not any("highway" in item.text for item in stop.build_items())
    finally:
        app.shutdown()


def test_a_serious_speeding_ticket_moves_the_ladder_and_says_so(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        d.speeding_tickets = 1  # past the first-stop warning
        TrafficStopState(app.ctx, d, signaled=False, over=22.0, limit=65.0)
        assert p.driving_record.serious_in_window(p.game_hours) == 1
        assert "serious violation" in d.record_events[-1]
    finally:
        app.shutdown()


def test_a_mild_speeding_ticket_is_money_only(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        d.speeding_tickets = 1
        TrafficStopState(app.ctx, d, signaled=True, over=11.0, limit=65.0)
        assert p.driving_record.serious_in_window(p.game_hours) == 0
        assert p.driving_record.citations == 1
        assert not d.record_events
    finally:
        app.shutdown()


def test_speeding_nobody_saw_never_touches_the_licence(monkeypatch):
    """The old silent settlement strike deliberately never moved the ladder.

    The strike is gone, and the guarantee it needed is now structural rather
    than deliberate: with nobody watching, speeding produces no citation to
    put on the record in the first place. Nothing may reach the licence file
    without a trooper having been there.
    """
    from freight_fate.app import App
    from freight_fate.states.driving import SPEEDING_LEEWAY_MPH

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        d.trip.posts = []  # empty road
        d.trip.position_mi = d.trip.total_miles / 2.0
        d._enforcement_prev_mi = d.trip.position_mi
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        d.truck.velocity_mps = (limit + SPEEDING_LEEWAY_MPH + 30) / 2.23694
        for _ in range(40):
            d.trip.position_mi += 0.05
            d._update_enforcement_watch(0.2)
            d._update_speeding(0.2)
        assert d.speeding_tickets == 0
        assert p.driving_record.citations == 0
        assert p.driving_record.serious_in_window(p.game_hours) == 0
        assert not p.driving_record.suspended(p.game_hours)
    finally:
        app.shutdown()


def test_debug_hours_mode_freezes_the_ladder(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import FelonyStopState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        app.ctx.settings.hos_mode = "debug_off"
        FelonyStopState(app.ctx, d)
        assert p.driving_record.major_count == 0
        assert not p.driving_record.suspended(p.game_hours)
    finally:
        app.shutdown()


def test_running_off_the_road_asleep_costs_reputation_and_is_spoken(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.enforcement import FATIGUE_EVENT_REPUTATION_HIT

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        before = p.career.reputation
        d._microsleep_misses = 0
        d._microsleep_drift_off_road()
        assert p.driving_record.fatigue_events == 1
        assert p.career.reputation == before - FATIGUE_EVENT_REPUTATION_HIT
        assert any("reputation" in line for line in spoken)
    finally:
        app.shutdown()


def test_terse_speech_still_hears_every_consequence(monkeypatch):
    """Terse drops description, never anything with money or standing on it."""
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.speech_verbosity = 0
        d = _driving(app)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        p.driving_record.record_fatigue_event(0.0)  # so the next one is serious
        d._microsleep_misses = 0
        d._microsleep_drift_off_road()
        said = " ".join(spoken)
        assert "serious violation" in said
        assert "suspended" in said  # the second one lands the 60-day suspension
    finally:
        app.shutdown()


def test_repeat_fatigue_events_speak_the_real_count(monkeypatch):
    """Every occurrence past the first is a serious violation, and the line
    must say how many times it has actually happened -- not freeze at
    'twice now' once the driver runs off the road asleep a third or fourth
    time."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _quiet(app, monkeypatch)
        for _ in range(4):
            d._microsleep_misses = 0
            d._microsleep_drift_off_road()
        said = " ".join(spoken)
        assert "That is twice now that you have run off the road asleep." in said
        assert "That is three times now that you have run off the road asleep." in said
        assert "That is four times now that you have run off the road asleep." in said
    finally:
        app.shutdown()


def test_a_clean_driver_hears_and_pays_nothing_new(monkeypatch):
    """The economy guardrail: nothing here reaches a driver who runs clean."""
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        _driving(app)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        menu = CityMenuState(app.ctx)
        menu.announce_entry()
        said = " ".join(spoken)
        assert "CDL" not in said
        assert "Dispatch trust" not in said
        assert not any(item.text.startswith("Wait out") for item in menu.build_items())
        assert p.driving_record.citations == 0
    finally:
        app.shutdown()


# --- running is a choice, never an accident ---------------------------------


def _hold_run_key(app, monkeypatch, *, held=True):
    import pygame

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: {pygame.K_x: held})
    monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_LSHIFT if held else 0)


def test_holding_the_run_key_states_the_cost_before_it_counts(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import PURSUIT_HOLD_S

    app = App()
    try:
        d = _driving(app)
        spoken = _quiet(app, monkeypatch)
        d.trip.position_mi = d.trip.total_miles / 2.0
        d._begin_pull_over(65.0)
        spoken.clear()
        _hold_run_key(app, monkeypatch)
        d._update_pursuit_optin(0.1)
        assert any("felony" in line for line in spoken)
        assert any("disqualifies your CDL" in line for line in spoken)
        assert d._pull_over is not None  # nothing has happened yet
        # Letting go before the hold completes stops nothing from happening.
        _hold_run_key(app, monkeypatch, held=False)
        d._update_pursuit_optin(PURSUIT_HOLD_S)
        assert d._pull_over is not None
        assert app.ctx.profile.driving_record.major_count == 0
    finally:
        app.shutdown()


def test_holding_the_run_key_through_the_warning_lands_the_full_offense(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import PURSUIT_HOLD_S, FelonyStopState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        d.trip.position_mi = d.trip.total_miles / 2.0
        d._begin_pull_over(65.0)
        _hold_run_key(app, monkeypatch)
        d._update_pursuit_optin(PURSUIT_HOLD_S + 0.1)
        assert isinstance(app.state, FelonyStopState)
        assert p.driving_record.major_count == 1
        assert p.driving_record.suspended(p.game_hours)
    finally:
        app.shutdown()


def test_the_second_pursuit_takes_twice_as_long_to_choose(monkeypatch):
    """A lifetime disqualification gets its own, longer confirmation."""
    from freight_fate.app import App
    from freight_fate.states.driving import PURSUIT_HOLD_S

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        p.driving_record.record_major_offense(0.0)
        d.trip.position_mi = d.trip.total_miles / 2.0
        d._begin_pull_over(65.0)
        spoken.clear()
        _hold_run_key(app, monkeypatch)
        d._update_pursuit_optin(PURSUIT_HOLD_S + 0.1)
        assert any("for life" in line for line in spoken)
        assert not p.driving_record.lifetime_disqualified  # one hold is not enough
        d._update_pursuit_optin(PURSUIT_HOLD_S)
        assert p.driving_record.lifetime_disqualified
    finally:
        app.shutdown()


# --- exploits the adversarial harness found ---------------------------------


def test_reloading_mid_stop_does_not_cancel_the_stop(monkeypatch):
    """Save-scumming out of a pull-over would make every suspension optional."""
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        d = _driving(app)
        _quiet(app, monkeypatch)
        d.trip.position_mi = d.trip.total_miles / 2.0
        d._begin_pull_over(65.0)
        d._pull_over_warning_level = 1
        d._pull_over_compliance = 0.3
        assert d._pull_over is not None
        restored = DrivingState.from_snapshot(app.ctx, d.snapshot())
        assert restored._pull_over == d._pull_over
        assert restored._pull_over_warning_level == 1
        assert restored._pull_over_compliance == 0.3
        assert restored._pull_over_limit == d._pull_over_limit
    finally:
        app.shutdown()


def test_a_paid_stop_is_not_charged_again_on_the_next_resume(monkeypatch):
    """The other half of "a stop survives a reload": it has to end, too.

    The lights are written into the save before a word of the stop is spoken,
    so a crash cannot erase it. Nothing wrote the save back once the fine was
    paid, so every resume found a cruiser still sitting behind a parked truck
    and charged for the same stop again -- at the repeat rate, so it cost more
    each time. A tester lost his career's money to four of them in a minute
    (log, 2026-08-10).
    """
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.driving_rest_states import EnforcementStopState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        monkeypatch.setattr(app.ctx, "save_profile", lambda *a, **k: None)
        d.trip.position_mi = d.trip.total_miles / 2.0
        d._begin_enforcement_pull_over(
            kind="weigh_station_bypass",
            title="Weigh station bypass stop",
            summary="Scale officers saw you blow past the scale.",
            fine=750.0,
            reputation_hit=3.0,
            return_message="Back on the highway.",
            lights_message="Lights and siren behind you.",
        )
        assert p.active_trip is not None
        money_before = p.money
        # Brake to a stop: the roadside stop opens and the fine is paid.
        d.truck.velocity_mps = 0.0
        d._pull_over_grace_s = 0.0
        d._update_pull_over(0.1)
        assert isinstance(app.state, EnforcementStopState)
        paid = money_before - p.money
        assert paid > 0.0
        app.pop_state()

        # Quit to the title and resume. The truck is parked and the stop is
        # settled, so nothing about it may happen a second time.
        resumed = DrivingState.from_snapshot(app.ctx, dict(p.active_trip))
        assert resumed is not None
        assert resumed._pull_over is None
        resumed._update_pull_over(0.1)
        assert not isinstance(app.state, EnforcementStopState)
        assert p.money == money_before - paid
    finally:
        app.shutdown()


def test_toggling_the_jake_cannot_farm_warnings_forever(monkeypatch):
    """One grace window per town, not a renewable exemption."""
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_FINES

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        _quiet(app, monkeypatch)
        # First engagement: warned, then complies before the timer runs out.
        d._jake_zone_grace_used.add("buffalo_ny_us")
        d._jake_violation_deadline_s = None
        d._jake_citation_latched = False
        money_before = p.money
        d._fine_engine_braking("buffalo_ny_us")
        assert p.money == money_before - JAKE_ZONE_FINES[0]
        # The citation is on the record even though it is not a serious one.
        assert p.driving_record.citations == 1
        assert p.driving_record.serious_in_window(p.game_hours) == 0
    finally:
        app.shutdown()


def test_the_fatigue_out_of_service_actually_holds_the_truck(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import MICROSLEEP_FORCE_STOP_MISSES

    app = App()
    try:
        d = _driving(app)
        spoken = _quiet(app, monkeypatch)
        d.truck.velocity_mps = 27.0
        d.truck.throttle = 1.0
        d._microsleep_misses = MICROSLEEP_FORCE_STOP_MISSES - 1
        d._microsleep_drift_off_road()
        assert d.truck.velocity_mps == 0.0
        assert d.truck.parking_brake  # not a one-frame brake tap
        assert any("out of service" in line for line in spoken)
    finally:
        app.shutdown()


def test_a_fine_a_load_cannot_cover_stays_owed_and_is_said_so():
    from freight_fate.models.business import build_business_settlement
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    job = Job(CARGO_CATALOG["general"], 5.0, "Buffalo", "yard", "Rochester", 40.0, 120.0, 8.0)
    settled = build_business_settlement(
        "company_driver", job, 120.0, on_time=True, driver_charges=2_000.0
    )
    assert settled.net_before_advance == 0.0
    # The shortfall is owed, not quietly forgiven.
    assert settled.uncollected_charges > 0
    assert settled.uncollected_charges < 2_000.0


# --- the dispatch board while suspended ------------------------------------


def test_the_board_says_the_suspension_before_it_lists_anything(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        p.driving_record.record_serious_violation(p.game_hours)
        p.driving_record.record_serious_violation(p.game_hours)
        state = JobBoardState(app.ctx, [d.job])
        state.announce_entry()
        assert spoken[0].startswith("Dispatch board. Your CDL is suspended")
        assert "driving jobs return" in spoken[0].lower()
    finally:
        app.shutdown()


def test_taking_a_job_while_suspended_is_refused_with_the_clear_date(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        d = _driving(app)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        p.driving_record.record_major_offense(p.game_hours)
        state = JobBoardState(app.ctx, [d.job])
        state._accept(d.job)
        assert p.active_trip is None
        assert "disqualified" in spoken[-1]
        assert "clears" in spoken[-1]
    finally:
        app.shutdown()


def test_waiting_out_the_suspension_gives_the_licence_back(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        _driving(app)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        p.driving_record.record_serious_violation(p.game_hours)
        p.driving_record.record_serious_violation(p.game_hours)
        assert p.driving_record.suspended(p.game_hours)
        menu = CityMenuState(app.ctx)
        assert any(item.text == "Wait out the CDL suspension" for item in menu.build_items())
        menu._wait_out_suspension()
        assert not p.driving_record.suspended(p.game_hours)
        assert any("clear again" in line for line in spoken)
    finally:
        app.shutdown()


def test_a_floor_reputation_company_driver_loses_the_carrier(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.enforcement import LAST_CHANCE_CARRIER_KEY
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        _driving(app)
        p = app.ctx.profile
        spoken = _quiet(app, monkeypatch)
        former = p.carrier_name
        p.career.reputation = 4.0
        CityMenuState(app.ctx)._check_carrier_termination()
        assert p.carrier_key == LAST_CHANCE_CARRIER_KEY
        assert p.driving_record.carrier_terminations == 1
        # "Ended your employment", never "let you go": the ontology settled on
        # the plain factual verb over the softening one.
        assert any(former in line and "ended your employment" in line for line in spoken)
        # Nothing is taken away but the seat.
        assert p.money > 0 or p.career.level >= 1
    finally:
        app.shutdown()
