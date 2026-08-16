"""Cargo condition: what the freight arrives in, and what the dock does.

Truck damage is the driver's problem; cargo damage is the customer's, and it
is much larger money. The load degrades from what the sim already models --
hard braking, taking a bend past its posted advisory, collisions -- scaled by
how well the freight survives being thrown about, and the receiver's ladder
at the dock runs clean, exception, claim, refused.
"""

import pytest
from speech_capture import speech_stub

from freight_fate.models.business import COMPANY_DRIVER, LEASED_OWNER_OPERATOR
from freight_fate.models.cargo_condition import (
    CARGO_CLAIM_PCT,
    CARGO_EXCEPTION_PCT,
    CARGO_OUTCOME_CLAIM,
    CARGO_OUTCOME_CLEAN,
    CARGO_OUTCOME_EXCEPTION,
    CARGO_OUTCOME_REJECTED,
    CARGO_REJECT_PCT,
    cargo_condition_text,
    cargo_fragility,
    cargo_outcome,
    settle_cargo,
)
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.sim.vehicle import (
    CARGO_ADVISORY_LAT_G,
    CARGO_CORNER_LAT_G,
    CARGO_HARD_BRAKE_G,
    EMERGENCY_BRAKE_MULT,
    TruckState,
)

MPS_PER_MPH = 1 / 2.23694


# A bend's radius, in feet, for a given lateral pull at a given speed -- the
# inverse of what the model computes, so a test can ask for "0.1 g over the
# threshold" without hand-solving the geometry each time.
def _radius_for(mph: float, lateral_g: float) -> float:
    mps = mph * MPS_PER_MPH
    return mps * mps / (lateral_g * 9.81) / 0.3048


def _job(cargo="general") -> Job:
    return Job(CARGO_CATALOG[cargo], 12.0, "Denver", "yard", "Salt Lake City", 200.0, 900.0, 12.0)


def _driving(app, cargo="general", business_status=LEASED_OWNER_OPERATOR):
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Cargo Tester", current_city="Denver")
    app.ctx.profile.business_status = business_status
    if business_status != COMPANY_DRIVER:
        app.ctx.profile.owned_trucks = ["rig"]
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, _job(cargo), route, trip_seed=99, start_hour=10.0)
    app.push_state(driving)
    driving.truck.set_air_ready(parking_brake=False)
    return driving


@pytest.fixture
def app():
    from freight_fate.app import App

    made = App()
    try:
        yield made
    finally:
        made.shutdown()


def _loaded(mph=60.0) -> TruckState:
    t = TruckState()
    t.trailer_attached = True
    t.cargo_kg = 12_000.0
    t.velocity_mps = mph * MPS_PER_MPH
    return t


# -- the meter --------------------------------------------------------------


def test_gentle_driving_never_touches_the_load():
    t = _loaded()
    for _ in range(600):
        t._update_cargo(1 / 60, decel_g=CARGO_HARD_BRAKE_G - 0.05)
    assert t.cargo_damage_pct == 0.0


def test_hard_braking_shifts_the_load():
    t = _loaded()
    for _ in range(120):
        t._update_cargo(1 / 60, decel_g=CARGO_HARD_BRAKE_G + 0.3)
    assert t.cargo_damage_pct > 0.0


def test_a_full_service_stop_does_not_hurt_a_secured_load():
    """Securement is rated past what the brakes can produce (49 CFR 393.102).

    A stop at everything the service brakes have -- which is what a startled
    driver makes several times a run -- used to put general freight over the
    exception line on its own, and fragile freight into claim territory.
    """
    t = _loaded(mph=65.0)
    peak = t.specs.max_brake_decel_g
    assert peak < CARGO_HARD_BRAKE_G  # the premise: brakes cannot reach it
    for _ in range(600):
        t._update_cargo(1 / 60, decel_g=peak)
    assert t.cargo_damage_pct == 0.0


def test_an_emergency_application_does_reach_the_freight():
    """Full service plus the spring brakes is past what securement holds."""
    t = _loaded(mph=65.0)
    emergency_g = t.specs.max_brake_decel_g * EMERGENCY_BRAKE_MULT
    assert emergency_g > CARGO_HARD_BRAKE_G
    for _ in range(300):
        t._update_cargo(1 / 60, decel_g=emergency_g)
    assert t.cargo_damage_pct > 0.0


def test_a_bend_taken_well_over_its_advisory_costs_the_freight():
    """The break harness found a hairpin at 45 over doing nothing at all."""
    t = _loaded(mph=75.0)
    t.corner_radius_ft = _radius_for(30.0, CARGO_CORNER_LAT_G)  # a 30 mph bend
    for _ in range(120):
        t._update_cargo(1 / 60, decel_g=0.0)
    assert t.cargo_damage_pct > 0.0


def test_a_bend_taken_at_its_advisory_is_free():
    t = _loaded(mph=45.0)
    # A bend signed for 45: the shipped advisories sit below the threshold.
    t.corner_radius_ft = _radius_for(45.0, CARGO_ADVISORY_LAT_G)
    for _ in range(600):
        t._update_cargo(1 / 60, decel_g=0.0)
    assert t.cargo_damage_pct == 0.0


def test_the_tighter_bend_costs_more_at_the_same_margin_over_its_sign():
    """The realism bug the playtest bench caught: the ranking was inverted.

    A hairpin and a sweeper taken the same mph over their advisories are not
    the same manoeuvre -- the hairpin throws the load half again as hard --
    but the old model read raw mph over the sign and charged the hairpin less.
    """
    costs = []
    for advisory in (30.0, 55.0):
        t = _loaded(mph=advisory + 15.0)
        t.corner_radius_ft = _radius_for(advisory, CARGO_ADVISORY_LAT_G)
        for _ in range(120):
            t._update_cargo(1 / 60, decel_g=0.0)
        costs.append(t.cargo_damage_pct)
    hairpin, sweeper = costs
    assert hairpin > sweeper > 0.0


def test_a_bend_without_a_baked_radius_falls_back_on_its_advisory():
    """A gap in the map must not read as a straight road."""
    t = _loaded(mph=60.0)
    t.corner_radius_ft = 0.0
    t.corner_advisory_mph = 30.0
    assert t.corner_lateral_g > CARGO_CORNER_LAT_G
    for _ in range(120):
        t._update_cargo(1 / 60, decel_g=0.0)
    assert t.cargo_damage_pct > 0.0


def test_a_straight_road_pulls_nothing_sideways():
    t = _loaded(mph=70.0)
    assert t.corner_lateral_g == 0.0


def test_fragile_freight_degrades_faster_than_general():
    rates = []
    for cargo_key in ("general", "electronics"):
        t = _loaded(mph=50.0)
        t.cargo_fragility = cargo_fragility(CARGO_CATALOG[cargo_key])
        t.corner_radius_ft = _radius_for(30.0, CARGO_ADVISORY_LAT_G)
        for _ in range(120):
            t._update_cargo(1 / 60, decel_g=0.0)
        rates.append(t.cargo_damage_pct)
    assert rates[1] > rates[0] * 2


def test_an_empty_trailer_has_nothing_to_damage():
    t = TruckState()
    t.cargo_kg = 0.0
    t.velocity_mps = 60.0 * MPS_PER_MPH
    t.corner_radius_ft = _radius_for(25.0, CARGO_ADVISORY_LAT_G)
    for _ in range(120):
        t._update_cargo(1 / 60, decel_g=1.0)
    assert t.cargo_damage_pct == 0.0
    assert t.add_cargo_damage(50.0) == 0.0


def test_a_collision_goes_through_the_freight_too():
    t = _loaded(mph=50.0)
    t.apply_collision(0.7)
    assert t.cargo_damage_pct > 0.0


def test_cargo_fragility_falls_back_on_the_catalogue_fragile_flag():
    plain = cargo_fragility(CARGO_CATALOG["general"])
    assert plain == pytest.approx(1.0)
    assert cargo_fragility(None) == pytest.approx(1.0)
    assert cargo_fragility(CARGO_CATALOG["electronics"]) > plain


# -- the dock ---------------------------------------------------------------


def test_the_receivers_ladder_runs_clean_exception_claim_refused():
    assert cargo_outcome(0.0) == CARGO_OUTCOME_CLEAN
    assert cargo_outcome(CARGO_EXCEPTION_PCT) == CARGO_OUTCOME_EXCEPTION
    assert cargo_outcome(CARGO_CLAIM_PCT) == CARGO_OUTCOME_CLAIM
    assert cargo_outcome(CARGO_REJECT_PCT) == CARGO_OUTCOME_REJECTED


def test_a_clean_load_costs_nothing():
    settled = settle_cargo(CARGO_EXCEPTION_PCT - 1.0, 3000.0)
    assert settled.clean
    assert settled.pay_loss == 0.0
    assert settled.claim_value == 0.0
    assert settled.reputation_hit == 0.0


def test_the_penalties_escalate_up_the_ladder():
    gross = 3000.0
    exception = settle_cargo(CARGO_EXCEPTION_PCT, gross)
    claim = settle_cargo(CARGO_CLAIM_PCT, gross)
    refused = settle_cargo(CARGO_REJECT_PCT, gross)

    assert exception.pay_loss < claim.pay_loss < refused.pay_loss
    assert exception.reputation_hit < claim.reputation_hit < refused.reputation_hit
    assert exception.claim_value == 0.0
    assert claim.claim_value > 0.0
    assert refused.claim_value > claim.claim_value


def test_a_refused_load_pays_nothing_at_all():
    """The harsh top end: the driver delivered nothing."""
    settled = settle_cargo(90.0, 3000.0)
    assert settled.rejected
    assert settled.pay_loss == pytest.approx(3000.0)
    # And the freight itself is owed on top of the unpaid haul.
    assert settled.claim_value > 3000.0


def test_the_condition_words_map_one_to_one_onto_the_outcomes():
    assert cargo_condition_text(0.0) == "secure"
    assert cargo_condition_text(5.0) == "shifted but sound"
    assert cargo_condition_text(CARGO_EXCEPTION_PCT) == "damaged"
    assert cargo_condition_text(CARGO_CLAIM_PCT) == "badly damaged"
    assert cargo_condition_text(CARGO_REJECT_PCT) == "ruined"


# -- spoken during the drive ------------------------------------------------


def test_each_condition_rung_speaks_once_while_driving(app, monkeypatch):
    """A load that quietly rotted until the dock refused it would be the
    worst kind of surprise for a player who cannot see the trailer."""
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    driving.trip.curve_at = lambda mile: None

    driving.truck.cargo_damage_pct = CARGO_EXCEPTION_PCT + 1.0
    driving._update_cargo_condition(1 / 60)
    driving._update_cargo_condition(1 / 60)
    assert len(events) == 1
    assert "damaged" in events[0]

    driving.truck.cargo_damage_pct = CARGO_CLAIM_PCT + 1.0
    driving._update_cargo_condition(1 / 60)
    assert len(events) == 2
    assert "claim" in events[1].lower()

    driving.truck.cargo_damage_pct = CARGO_REJECT_PCT + 1.0
    driving._update_cargo_condition(1 / 60)
    assert len(events) == 3
    assert "refuse" in events[2].lower()


def test_the_coaching_tail_speaks_once_per_episode(app, monkeypatch):
    """R11: "brake and corner gently from here" teaches; once taught, each
    escalation speaks only the new number and the consequence."""
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    driving.trip.curve_at = lambda mile: None

    driving.truck.cargo_damage_pct = CARGO_EXCEPTION_PCT + 1.0
    driving._update_cargo_condition(1 / 60)
    assert "Brake and corner gently from here." in events[0]

    driving.truck.cargo_damage_pct = CARGO_CLAIM_PCT + 1.0
    driving._update_cargo_condition(1 / 60)
    driving.truck.cargo_damage_pct = CARGO_REJECT_PCT + 1.0
    driving._update_cargo_condition(1 / 60)
    # The escalations still carry the new number and consequence, but never
    # the coaching tail again.
    assert "claim" in events[1].lower()
    assert "Brake and corner gently" not in events[1]
    assert "Brake and corner gently" not in events[2]


def test_terse_cargo_cues_keep_the_consequence(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    app.ctx.settings.driving_speech = "quiet"
    driving = _driving(app)
    driving.trip.curve_at = lambda mile: None

    driving.truck.cargo_damage_pct = CARGO_REJECT_PCT + 1.0
    driving._update_cargo_condition(1 / 60)

    assert len(events) == 1
    assert "ruined" in events[0]
    assert "refuse" in events[0].lower()


def test_the_bend_is_fed_to_the_truck_from_the_road(app, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    driving.truck.velocity_mps = 70.0 * MPS_PER_MPH
    driving.trip.curve_at = lambda mile: SimpleNamespace(advisory_mph=25.0, connector=False)

    driving._update_cargo_condition(1 / 60)

    assert driving.truck.corner_overspeed_mph == pytest.approx(45.0, abs=0.5)


def test_a_connector_ramp_is_not_treated_as_a_signed_bend(app, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    driving.truck.velocity_mps = 70.0 * MPS_PER_MPH
    driving.trip.curve_at = lambda mile: SimpleNamespace(advisory_mph=25.0, connector=True)

    driving._update_cargo_condition(1 / 60)

    assert driving.truck.corner_overspeed_mph == 0.0


# -- status and persistence -------------------------------------------------


def test_the_load_line_names_the_freights_condition(app, monkeypatch):
    from freight_fate.states.driving import DrivingStatusScreenState

    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving = _driving(app)
    screen = DrivingStatusScreenState(app.ctx, driving, "driver")

    clean = next(text for text in screen._driver_lines() if text.startswith("Load:"))
    assert "freight secure" in clean

    driving.truck.cargo_damage_pct = CARGO_CLAIM_PCT + 2.0
    hurt = next(text for text in screen._driver_lines() if text.startswith("Load:"))
    assert "badly damaged" in hurt
    assert "37 percent" in hurt


def test_the_job_sets_the_fragility_the_truck_carries(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    plain = _driving(app, cargo="general")
    assert plain.truck.cargo_fragility == pytest.approx(1.0)
    delicate = _driving(app, cargo="electronics")
    assert delicate.truck.cargo_fragility > 2.0


def test_cargo_condition_round_trips_through_a_snapshot(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    driving.trip.curve_at = lambda mile: None
    driving.truck.cargo_damage_pct = CARGO_CLAIM_PCT + 1.0
    driving._update_cargo_condition(1 / 60)

    data = driving.snapshot()
    restored = type(driving).from_snapshot(app.ctx, data)

    assert restored is not None
    assert restored.truck.cargo_damage_pct == pytest.approx(CARGO_CLAIM_PCT + 1.0)
    # The rung already spoken travels too, so a reload does not re-warn.
    assert restored._cargo_cue_at == pytest.approx(CARGO_CLAIM_PCT)


def test_a_snapshot_without_cargo_keys_resumes_clean(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    data = driving.snapshot()
    data.pop("cargo_damage_pct", None)
    data.pop("cargo_cue_at", None)

    restored = type(driving).from_snapshot(app.ctx, data)

    assert restored is not None
    assert restored.truck.cargo_damage_pct == 0.0
    assert restored._cargo_cue_at == 0.0


# -- the settlement line ----------------------------------------------------


def test_the_settlement_line_names_the_finding_the_cost_and_the_claim(app, monkeypatch):
    from freight_fate.states.driving_menu_states import ArrivalState

    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving = _driving(app)
    arrival = ArrivalState.__new__(ArrivalState)
    arrival.ctx = app.ctx
    arrival.driving = driving

    refused = arrival._cargo_settlement_line(settle_cargo(70.0, 3000.0))
    assert "refused" in refused
    assert "3,000 dollars" in refused
    assert "claim" in refused
    assert "your own authority" in refused  # an owner-op eats it

    noted = arrival._cargo_settlement_line(settle_cargo(CARGO_EXCEPTION_PCT + 1.0, 3000.0))
    assert "exception on the bill of lading" in noted
    assert "dollars" in noted


def test_a_company_drivers_claim_sits_with_the_carrier(app, monkeypatch):
    from freight_fate.states.driving_menu_states import ArrivalState

    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving = _driving(app, business_status=COMPANY_DRIVER)
    arrival = ArrivalState.__new__(ArrivalState)
    arrival.ctx = app.ctx
    arrival.driving = driving

    line = arrival._cargo_settlement_line(settle_cargo(70.0, 3000.0))

    assert "carrier carries the claim" in line
    assert "on your record" in line


def test_terse_settlement_line_keeps_every_number(app, monkeypatch):
    from freight_fate.states.driving_menu_states import ArrivalState

    monkeypatch.setattr(app.ctx, "say", speech_stub())
    app.ctx.settings.driving_speech = "quiet"
    driving = _driving(app)
    arrival = ArrivalState.__new__(ArrivalState)
    arrival.ctx = app.ctx
    arrival.driving = driving

    line = arrival._cargo_settlement_line(settle_cargo(70.0, 3000.0))

    assert "Load refused." in line
    assert "3,000 dollars" in line
    assert "Claim" in line


def test_a_load_ruined_in_one_hit_warns_once_at_the_state_it_is_in(app, monkeypatch):
    """A collision can cross all three rungs at once. Three interrupting
    warnings inside a tenth of a second would be worse than none."""
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    driving.trip.curve_at = lambda mile: None

    driving.truck.cargo_damage_pct = CARGO_REJECT_PCT + 10.0
    driving._update_cargo_condition(1 / 60)
    driving._update_cargo_condition(1 / 60)

    assert len(events) == 1
    assert "ruined" in events[0]
