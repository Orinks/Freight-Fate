"""Damage bands: reduced power, limp mode, and the out-of-service wall.

A wrecked truck must not drive like a healthy one, and past a point it must
not drive at all. Damage crosses named bands that bite in the vehicle model
itself -- a torque derate, a thirstier engine, a road-speed governor, and
finally a wall -- and every crossing is announced before the physics is felt,
in both verbosity settings.

The wall is where the two business statuses part company: a company driver's
tractor is grounded by the carrier at the carrier's expense and the driver
pays in hours and standing; an owner-operator pays the whole bill themselves.
Neither may keep driving.
"""

import pytest
from speech_capture import speech_stub

from freight_fate.models.business import COMPANY_DRIVER, LEASED_OWNER_OPERATOR
from freight_fate.models.career import LEVEL_XP
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.sim.transmission import REVERSE
from freight_fate.sim.vehicle import (
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
    REVERSE_CRASH_DAMAGE_PCT,
    REVERSE_ENGAGE_MAX_MPH,
    RUNAWAY_SPEED_MPH,
    TruckState,
)
from freight_fate.states.driving_core import (
    BREAKDOWN_CALLOUT_FEE,
    BREAKDOWN_REPAIR_DAMAGE_PCT,
    BREAKDOWN_REPAIR_MIN,
    BREAKDOWN_REPUTATION_HIT,
    GROUNDED_SWAP_MIN,
    LIMP_CAP_RAMP_MPH_PER_S,
    MECHANIC_RATE_PER_PCT,
)

MPS_PER_MPH = 1 / 2.23694


def _job() -> Job:
    return Job(
        CARGO_CATALOG["general"], 12.0, "Denver", "yard", "Salt Lake City", 200.0, 900.0, 12.0
    )


def _driving(app, business_status=LEASED_OWNER_OPERATOR, level=1):
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Damage Tester", current_city="Denver")
    app.ctx.profile.business_status = business_status
    app.ctx.profile.career.xp = LEVEL_XP[level - 1]
    if business_status != COMPANY_DRIVER:
        app.ctx.profile.owned_trucks = ["rig"]
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, _job(), route, trip_seed=99, start_hour=10.0)
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


def _rolling(driving, mph):
    t = driving.truck
    t.engine_on = True
    t.velocity_mps = mph * MPS_PER_MPH
    return t


# -- the vehicle model ------------------------------------------------------


def test_damage_below_the_first_band_changes_nothing():
    """A careful driver must see exactly the behaviour they saw before."""
    clean = TruckState()
    worn = TruckState()
    worn.damage_pct = DAMAGE_DERATE_PCT - 1.0
    assert worn.damage_band == DAMAGE_BAND_NONE
    assert worn.damage_derate_factor == 1.0
    assert worn.damage_fuel_penalty == 0.0
    assert worn.speed_cap_mph is None
    assert not worn.out_of_service
    assert clean.damage_derate_factor == 1.0


def test_reduced_power_band_derates_torque_and_costs_fuel():
    t = TruckState()
    t.damage_pct = DAMAGE_DERATE_PCT
    assert t.damage_band == DAMAGE_BAND_REDUCED
    assert t.damage_derate_factor == pytest.approx(1.0)
    t.damage_pct = (DAMAGE_DERATE_PCT + DAMAGE_LIMP_PCT) / 2.0
    mid = t.damage_derate_factor
    assert 0.0 < mid < 1.0
    assert t.damage_fuel_penalty > 0.0
    # Progressive, not a cliff: deeper damage always derates further.
    t.damage_pct = DAMAGE_LIMP_PCT
    assert t.damage_derate_factor < mid
    assert t.damage_band == DAMAGE_BAND_LIMP


def test_damage_bands_ladder_up_to_the_wall():
    t = TruckState()
    for damage, band in (
        (0.0, DAMAGE_BAND_NONE),
        (DAMAGE_DERATE_PCT, DAMAGE_BAND_REDUCED),
        (DAMAGE_LIMP_PCT, DAMAGE_BAND_LIMP),
        (DAMAGE_LAST_CALL_PCT, DAMAGE_BAND_LAST_CALL),
        (DAMAGE_OUT_OF_SERVICE_PCT, DAMAGE_BAND_OUT_OF_SERVICE),
        (DAMAGE_MAX_PCT, DAMAGE_BAND_OUT_OF_SERVICE),
    ):
        t.damage_pct = damage
        assert t.damage_band == band, damage


def test_the_wall_sits_below_a_full_meter():
    """The owner's rule: a wrecked truck stops while it still has paint on it."""
    assert DAMAGE_OUT_OF_SERVICE_PCT < DAMAGE_MAX_PCT
    assert DAMAGE_LAST_CALL_PCT < DAMAGE_OUT_OF_SERVICE_PCT


def test_derate_reaches_the_engine_torque_the_truck_actually_makes():
    healthy = TruckState()
    hurt = TruckState()
    hurt.damage_pct = DAMAGE_LIMP_PCT
    for t in (healthy, hurt):
        t.engine_on = True
        t.throttle = 1.0
        t.velocity_mps = 20.0
        t.transmission.automatic = True
        t.transmission.gear = 8
    assert hurt.drive_force() < healthy.drive_force()


def test_derated_engine_burns_more_fuel_for_the_same_work():
    healthy = TruckState()
    hurt = TruckState()
    hurt.damage_pct = DAMAGE_LAST_CALL_PCT
    burned = []
    for t in (healthy, hurt):
        t.engine_on = True
        t.throttle = 0.5
        t.velocity_mps = 25.0
        before = t.fuel_gal
        for _ in range(120):
            t._update_fuel(1 / 60)
        burned.append(before - t.fuel_gal)
    assert burned[1] > burned[0]


def test_speed_cap_cuts_fuel_like_a_road_speed_governor():
    t = TruckState()
    t.engine_on = True
    t.throttle = 1.0
    t.transmission.automatic = True
    t.transmission.gear = 8
    t.velocity_mps = DAMAGE_LIMP_CAP_MPH * MPS_PER_MPH
    assert t.drive_force() > 0.0
    t.speed_cap_mph = DAMAGE_LIMP_CAP_MPH
    assert t.drive_force() == 0.0
    assert t.hold_throttle() == 0.0
    # Under the cap the engine still pulls: this is a governor, not a brake.
    t.velocity_mps = (DAMAGE_LIMP_CAP_MPH - 10.0) * MPS_PER_MPH
    assert t.drive_force() > 0.0


def test_out_of_service_leaves_the_engine_alone():
    """The wall is not a dead engine: a stricken truck must be able to crawl
    out of a live lane rather than sit in one."""
    t = TruckState()
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT
    assert t.out_of_service
    t.engine_on = True
    t.velocity_mps = 20.0
    t.update(1 / 60)
    assert t.engine_on
    t.stop_engine()
    assert t.start_engine()


def test_roadside_repair_leaves_the_truck_stopped_and_restartable():
    t = TruckState()
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT
    t.velocity_mps = 20.0
    t.recover_from_breakdown(BREAKDOWN_REPAIR_DAMAGE_PCT)
    assert t.damage_pct == BREAKDOWN_REPAIR_DAMAGE_PCT
    assert t.velocity_mps == 0.0
    assert t.speed_cap_mph is None
    assert not t.out_of_service
    t.parking_brake = False
    assert t.start_engine()


def test_a_runaway_destroys_the_truck_instead_of_just_chiming():
    """Coasting out of gear down a grade used to reach 128 mph with nothing
    but an overspeed chime. It now wrecks the truck, and the bands own it."""
    t = TruckState()
    t.transmission.gear = 0  # neutral, no driveline to hold anything back
    t.velocity_mps = 128.0 * MPS_PER_MPH
    for _ in range(60 * 30):
        t._update_wear(1 / 60)
        if t.out_of_service:
            break
    assert t.out_of_service


def test_below_the_runaway_threshold_nothing_accrues():
    t = TruckState()
    t.velocity_mps = (RUNAWAY_SPEED_MPH - 5.0) * MPS_PER_MPH
    for _ in range(600):
        t._update_wear(1 / 60)
    assert t.damage_pct == 0.0


def test_reverse_at_speed_is_refused_and_costs_the_driveline():
    t = TruckState()
    t.transmission.automatic = False
    t.transmission.clutch = 1.0
    t.velocity_mps = 60.0 * MPS_PER_MPH

    result = t.request_gear(REVERSE)

    assert not result.ok
    assert result.grind
    assert not t.transmission.in_reverse
    assert t.damage_pct == pytest.approx(REVERSE_CRASH_DAMAGE_PCT)


def test_reverse_still_engages_at_a_standstill():
    t = TruckState()
    t.transmission.automatic = False
    t.transmission.clutch = 1.0
    t.velocity_mps = (REVERSE_ENGAGE_MAX_MPH - 1.0) * MPS_PER_MPH

    assert t.request_gear(REVERSE).ok
    assert t.transmission.in_reverse
    assert t.damage_pct == 0.0


# -- spoken band edges ------------------------------------------------------


def test_each_band_announces_once_when_it_begins(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    t = _rolling(driving, 60.0)

    t.damage_pct = DAMAGE_DERATE_PCT + 1.0
    driving._update_damage_bands(1 / 60)
    driving._update_damage_bands(1 / 60)
    reduced = [line for line in events if "Reduced power" in line]
    assert len(reduced) == 1
    assert f"{DAMAGE_DERATE_PCT:.0f} percent" in reduced[0]

    t.damage_pct = DAMAGE_LIMP_PCT + 1.0
    driving._update_damage_bands(1 / 60)
    driving._update_damage_bands(1 / 60)
    assert len([line for line in events if "Limp mode" in line]) == 1


def test_the_last_call_names_the_number_that_stops_the_truck(app, monkeypatch):
    """Nobody may be surprised by the wall."""
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    t = _rolling(driving, 60.0)

    t.damage_pct = DAMAGE_LAST_CALL_PCT + 1.0
    driving._update_damage_bands(1 / 60)

    line = events[-1]
    assert f"{DAMAGE_OUT_OF_SERVICE_PCT:.0f}" in line
    assert "out of service" in line.lower()


def test_terse_last_call_still_names_the_wall(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    app.ctx.settings.speech_verbosity = 0
    driving = _driving(app)
    t = _rolling(driving, 60.0)

    t.damage_pct = DAMAGE_LAST_CALL_PCT + 1.0
    driving._update_damage_bands(1 / 60)

    assert events[-1] == (f"Damage 86 percent. Out of service at {DAMAGE_OUT_OF_SERVICE_PCT:.0f}.")


def test_a_second_excursion_into_a_band_warns_again(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    t = _rolling(driving, 60.0)

    t.damage_pct = DAMAGE_DERATE_PCT + 1.0
    driving._update_damage_bands(1 / 60)
    t.damage_pct = 0.0
    driving._update_damage_bands(1 / 60)
    t.damage_pct = DAMAGE_DERATE_PCT + 1.0
    driving._update_damage_bands(1 / 60)

    assert len([line for line in events if "Reduced power" in line]) == 2


def test_terse_speech_keeps_a_short_form_of_every_band(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    app.ctx.settings.speech_verbosity = 0
    driving = _driving(app)
    t = _rolling(driving, 60.0)

    for damage in (DAMAGE_DERATE_PCT + 1.0, DAMAGE_LIMP_PCT + 1.0, DAMAGE_LAST_CALL_PCT + 1.0):
        t.damage_pct = damage
        driving._update_damage_bands(1 / 60)

    assert len(events) == 3
    assert events[0] == "Reduced power. Damage 51 percent."
    assert events[1].startswith("Limp mode. Capped at ")
    assert "Out of service at" in events[2]


def test_repair_announces_the_band_on_the_way_back_down(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    t = _rolling(driving, 60.0)

    t.damage_pct = DAMAGE_LIMP_PCT + 5.0
    driving._update_damage_bands(1 / 60)
    events.clear()

    t.damage_pct = 30.0
    driving._update_damage_bands(1 / 60)

    assert len(events) == 1
    assert "30 percent" in events[0]
    assert "full power" in events[0].lower()


def test_terse_repair_keeps_the_fact_without_the_flourish(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    app.ctx.settings.speech_verbosity = 0
    driving = _driving(app)
    t = _rolling(driving, 60.0)
    t.damage_pct = DAMAGE_LIMP_PCT + 5.0
    driving._update_damage_bands(1 / 60)
    events.clear()

    t.damage_pct = 30.0
    driving._update_damage_bands(1 / 60)

    assert events == ["Damage 30 percent. Full power."]


# -- the speed cap ----------------------------------------------------------


def test_limp_cap_speaks_before_the_physics_bites(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    t = _rolling(driving, 68.0)

    t.damage_pct = DAMAGE_LIMP_PCT + 1.0
    driving._update_damage_bands(1 / 60)

    assert any("Limp mode" in line for line in events)
    # The cap opens at the speed the truck already has: nothing snapped away.
    assert t.speed_cap_mph == pytest.approx(68.0, abs=0.5)


def test_limp_cap_ramps_down_at_comfortable_braking(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    t = _rolling(driving, 65.0)
    t.damage_pct = DAMAGE_LIMP_PCT + 1.0
    driving._update_damage_bands(1 / 60)

    for _ in range(60):  # one second of ramp
        driving._update_damage_bands(1 / 60)
    assert t.speed_cap_mph == pytest.approx(65.0 - LIMP_CAP_RAMP_MPH_PER_S, abs=0.2)

    for _ in range(60 * 60):  # and all the way down
        driving._update_damage_bands(1 / 60)
    assert t.speed_cap_mph == pytest.approx(DAMAGE_LIMP_CAP_MPH)


def test_the_wall_cap_also_ramps_instead_of_snapping(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    t = _rolling(driving, 62.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT

    driving._update_damage_bands(1 / 60)

    assert t.speed_cap_mph == pytest.approx(62.0, abs=0.5)
    for _ in range(60):
        driving._update_damage_bands(1 / 60)
    assert t.speed_cap_mph == pytest.approx(62.0 - LIMP_CAP_RAMP_MPH_PER_S, abs=0.2)


def test_limp_cap_never_engages_during_a_pull_over(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    t = _rolling(driving, 60.0)
    t.damage_pct = DAMAGE_LIMP_PCT + 5.0
    driving._pull_over = "stopping"

    driving._update_damage_bands(1 / 60)

    assert t.speed_cap_mph is None


def test_limp_cap_never_engages_inside_the_gate_zone(app, monkeypatch):
    from freight_fate.sim.trip_models import FACILITY_GATE_ZONE_MI

    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    t = _rolling(driving, 60.0)
    t.damage_pct = DAMAGE_LIMP_PCT + 5.0
    driving._destination_exit_taken = True
    driving.trip.position_mi = driving.trip.total_miles - FACILITY_GATE_ZONE_MI / 2.0

    driving._update_damage_bands(1 / 60)

    assert t.speed_cap_mph is None


def test_cruise_says_once_that_limp_mode_owns_the_target(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    t = _rolling(driving, DAMAGE_LIMP_CAP_MPH)
    t.damage_pct = DAMAGE_LIMP_PCT + 5.0
    t.speed_cap_mph = DAMAGE_LIMP_CAP_MPH
    driving._cruise_mph = 65.0
    events.clear()

    for _ in range(10):
        driving._announce_limp_cruise_cap()

    said = [line for line in events if "Cruise cannot hold" in line or "Limp mode" in line]
    assert len(said) == 1
    assert "65" in said[0]


# -- the out-of-service wall ------------------------------------------------


def test_a_wrecked_truck_cannot_hold_highway_speed(app, monkeypatch):
    """The owner's complaint, as a test: at the top of the meter the truck
    used to cruise indefinitely. It now winds down to a crawl."""
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    t = _rolling(driving, 65.0)
    t.damage_pct = DAMAGE_MAX_PCT

    for _ in range(60 * 40):
        driving._update_damage_bands(1 / 60)
        if driving.truck.speed_cap_mph is None:
            break  # recovery ran; the wall is behind us
        driving.truck.velocity_mps = min(
            driving.truck.velocity_mps, driving.truck.speed_cap_mph * MPS_PER_MPH
        )

    assert driving.truck.speed_mph <= DAMAGE_CREEP_CAP_MPH + 0.5


def test_below_the_wall_the_truck_still_drives(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    t = _rolling(driving, 60.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT - 1.0

    for _ in range(60 * 60):
        driving._update_damage_bands(1 / 60)

    assert t.speed_cap_mph == pytest.approx(DAMAGE_LIMP_CAP_MPH)
    assert not t.out_of_service


def test_the_wall_states_the_fact_the_cost_and_the_way_out(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    t = _rolling(driving, 60.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT

    driving._update_damage_bands(1 / 60)

    line = events[0]
    assert "Out of service" in line
    assert "dollars" in line  # an owner-operator is told the bill up front
    assert "shoulder" in line or "clear of the lane" in line


def test_terse_wall_message_keeps_all_three(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    app.ctx.settings.speech_verbosity = 0
    driving = _driving(app)
    t = _rolling(driving, 60.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT

    driving._update_damage_bands(1 / 60)

    line = events[0]
    assert line.startswith("Out of service.")
    assert "90 percent" in line
    assert "dollars" in line


# -- recovery: owner-operator -----------------------------------------------


def test_owner_operator_pays_the_whole_bill_and_the_hours(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    p = app.ctx.profile
    p.money = 100.0
    t = _rolling(driving, 0.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT
    minutes_before = driving.trip.game_minutes

    driving._update_damage_bands(1 / 60)

    from freight_fate.states.driving_core import road_repair_cost

    cost = road_repair_cost(
        DAMAGE_OUT_OF_SERVICE_PCT, BREAKDOWN_REPAIR_DAMAGE_PCT, BREAKDOWN_CALLOUT_FEE
    )
    # Deep damage prices on the severity curve, so recovering a wrecked truck
    # is a five-figure day rather than a flat per-percent invoice.
    assert cost > BREAKDOWN_CALLOUT_FEE + 30.0 * MECHANIC_RATE_PER_PCT
    assert p.money == pytest.approx(100.0 - cost)  # may go negative: not optional
    assert p.money < 0
    assert t.damage_pct == BREAKDOWN_REPAIR_DAMAGE_PCT
    assert not t.out_of_service
    assert driving.trip.game_minutes == pytest.approx(minutes_before + BREAKDOWN_REPAIR_MIN)
    spoken = " ".join(events)
    assert f"{cost:,.0f} dollars" in spoken


def test_owner_operator_keeps_their_own_tractor(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    before = driving.ctx.profile.active_truck_key()
    t = _rolling(driving, 0.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT

    driving._update_damage_bands(1 / 60)

    assert driving.ctx.profile.active_truck_key() == before
    assert driving.ctx.profile.career.reputation == 50.0  # nobody grades them


# -- recovery: company driver -----------------------------------------------


def test_company_driver_pays_no_money_but_hours_and_standing(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app, business_status=COMPANY_DRIVER)
    p = app.ctx.profile
    p.money = 1000.0
    p.career.reputation = 50.0
    t = _rolling(driving, 0.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT
    minutes_before = driving.trip.game_minutes

    driving._update_damage_bands(1 / 60)

    assert p.money == 1000.0
    assert p.career.reputation == pytest.approx(50.0 - BREAKDOWN_REPUTATION_HIT)
    assert driving.trip.game_minutes == pytest.approx(minutes_before + GROUNDED_SWAP_MIN)
    assert not driving.truck.out_of_service
    spoken = " ".join(events)
    assert "carrier" in spoken
    assert "out of service" in spoken.lower()


def test_company_grounding_costs_more_hours_than_paying_for_it(app, monkeypatch):
    """The asymmetry in one line: the company driver trades money for time."""
    assert GROUNDED_SWAP_MIN > BREAKDOWN_REPAIR_MIN


def test_company_driver_grounding_is_recorded_for_the_career_layer(app, monkeypatch):
    from freight_fate.achievements import int_stat

    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app, business_status=COMPANY_DRIVER)
    t = _rolling(driving, 0.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT

    driving._update_damage_bands(1 / 60)

    assert int_stat(app.ctx.profile, "preventable_equipment_damage") >= 1


def test_slip_seating_driver_is_moved_into_a_different_yard_spare(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app, business_status=COMPANY_DRIVER, level=5)
    p = app.ctx.profile
    grounded = p.active_truck_key()
    t = _rolling(driving, 0.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT

    driving._update_damage_bands(1 / 60)

    assert p.active_truck_key() != grounded
    # The grounded tractor keeps its damage: it is in the shop, not fixed.
    assert p.truck_conditions[grounded]["damage_pct"] >= DAMAGE_OUT_OF_SERVICE_PCT
    # And the driver is in something they can actually drive.
    assert not driving.truck.out_of_service
    assert driving.truck.cargo_kg == t.cargo_kg


def test_a_driver_with_no_spare_gets_the_road_crew_instead(app, monkeypatch):
    """A level-one yard has one tractor. Grounding must still leave a way on."""
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app, business_status=COMPANY_DRIVER, level=1)
    p = app.ctx.profile
    before = p.active_truck_key()
    t = _rolling(driving, 0.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT

    driving._update_damage_bands(1 / 60)

    assert p.active_truck_key() == before
    assert not driving.truck.out_of_service
    assert driving.truck.damage_pct == BREAKDOWN_REPAIR_DAMAGE_PCT


def test_recovery_runs_once_however_many_frames_pass(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    p = app.ctx.profile
    p.money = 50_000.0
    t = _rolling(driving, 0.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT

    driving._update_damage_bands(1 / 60)
    charged = 50_000.0 - p.money
    for _ in range(30):
        driving._update_damage_bands(1 / 60)

    assert 50_000.0 - p.money == pytest.approx(charged)
    assert len([line for line in events if "Out of service" in line]) == 1


def test_creeping_past_the_grace_window_summons_service_anyway(app, monkeypatch):
    """A driver who never stops must not be left crawling forever."""
    from freight_fate.states.driving_core import OUT_OF_SERVICE_RECOVERY_GRACE_S

    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    t = _rolling(driving, 60.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT

    for _ in range(int(OUT_OF_SERVICE_RECOVERY_GRACE_S * 60) + 120):
        driving._update_damage_bands(1 / 60)
        driving.truck.velocity_mps = max(driving.truck.velocity_mps, 5.0)

    assert not driving.truck.out_of_service


# -- readouts ---------------------------------------------------------------


def test_truck_status_line_carries_the_band_with_the_number(app, monkeypatch):
    from freight_fate.states.driving import DrivingStatusScreenState

    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving = _driving(app)
    driving.truck.damage_pct = DAMAGE_LIMP_PCT + 3.0
    screen = DrivingStatusScreenState(app.ctx, driving, "driver")
    line = next(text for text in screen._driver_lines() if text.startswith("Truck:"))
    assert "damage 78 percent" in line
    assert "limp mode" in line
    assert "capped at" in line

    driving.truck.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT
    walled = next(text for text in screen._driver_lines() if text.startswith("Truck:"))
    assert "out of service" in walled

    driving.truck.damage_pct = 10.0
    clean = next(text for text in screen._driver_lines() if text.startswith("Truck:"))
    assert "limp mode" not in clean
    assert "reduced power" not in clean


def test_redline_speaks_the_meter_that_is_actually_moving(app, monkeypatch):
    """The warning read damage_pct while over-revving charged engine wear, so
    it told the player nothing was being harmed. Speak the moving meter."""
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    app.ctx.settings.speech_verbosity = 0
    driving = _driving(app)
    t = _rolling(driving, 60.0)
    t.damage_pct = 0.0
    t.engine_wear_pct = 12.0
    monkeypatch.setattr(type(t), "over_revving", property(lambda self: True))
    driving._overrev_s = 99.0
    driving._overrev_warn_due = 0.0

    driving._update_overrev(1 / 60)

    line = next(entry for entry in events if entry.startswith("Redline."))
    assert "12 percent" in line
    assert "engine wear" in line.lower()
    assert "0 percent" not in line


def test_redline_still_names_an_active_damage_band(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    app.ctx.settings.speech_verbosity = 0
    driving = _driving(app)
    t = _rolling(driving, 60.0)
    t.damage_pct = DAMAGE_LIMP_PCT + 3.0
    t.engine_wear_pct = 20.0
    monkeypatch.setattr(type(t), "over_revving", property(lambda self: True))
    driving._overrev_s = 99.0
    driving._overrev_warn_due = 0.0

    driving._update_overrev(1 / 60)

    line = next(entry for entry in events if entry.startswith("Redline."))
    assert "limp mode" in line


def test_delivery_summary_names_the_band_with_the_damage(app):
    from freight_fate.states.driving_damage import damage_summary_line

    settings = app.ctx.settings
    truck = TruckState()
    truck.damage_pct = 4.0
    assert damage_summary_line(settings, truck, 0.5) is None

    truck.damage_pct = 12.0
    healthy = damage_summary_line(settings, truck, 12.0)
    assert healthy is not None
    assert "12 percent truck damage" in healthy
    assert "limp mode" not in healthy

    truck.damage_pct = DAMAGE_LIMP_PCT + 3.0
    hurt = damage_summary_line(settings, truck, 40.0)
    assert hurt is not None
    assert "78 percent" in hurt
    assert "limp mode" in hurt


# -- persistence ------------------------------------------------------------


def test_band_state_round_trips_through_a_snapshot(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    t = _rolling(driving, 62.0)
    t.damage_pct = DAMAGE_LIMP_PCT + 4.0
    driving._update_damage_bands(1 / 60)
    for _ in range(120):
        driving._update_damage_bands(1 / 60)
    saved_cap = t.speed_cap_mph
    assert saved_cap is not None and saved_cap < 62.0

    data = driving.snapshot()
    app.ctx.profile.truck_damage_pct = t.damage_pct
    restored = type(driving).from_snapshot(app.ctx, data)
    assert restored is not None
    assert restored._damage_band == DAMAGE_BAND_LIMP
    assert restored._limp_cap_mph == pytest.approx(saved_cap)

    events.clear()
    restored._update_damage_bands(1 / 60)
    assert not [line for line in events if "Limp mode" in line]


def test_snapshot_without_band_keys_resumes_from_the_damage(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    driving.truck.damage_pct = DAMAGE_LAST_CALL_PCT + 2.0
    data = driving.snapshot()
    data.pop("damage_band", None)
    data.pop("limp_cap_mph", None)
    data.pop("out_of_service_creep_s", None)
    app.ctx.profile.truck_damage_pct = driving.truck.damage_pct

    restored = type(driving).from_snapshot(app.ctx, data)

    assert restored is not None
    assert restored._damage_band == DAMAGE_BAND_LAST_CALL
    assert restored._limp_cap_mph is None
    assert restored._out_of_service_creep_s == 0.0


def test_the_creep_window_round_trips_so_a_reload_is_not_a_reset(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app)
    t = _rolling(driving, 60.0)
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT
    for _ in range(120):
        driving._update_damage_bands(1 / 60)
    used = driving._out_of_service_creep_s
    assert used > 1.0

    data = driving.snapshot()
    app.ctx.profile.truck_damage_pct = t.damage_pct
    restored = type(driving).from_snapshot(app.ctx, data)

    assert restored is not None
    assert restored._out_of_service_creep_s == pytest.approx(used)


# -- escalating penalties ---------------------------------------------------


def test_repair_cost_curves_up_instead_of_scaling_by_the_percent():
    """A truck at ninety is far more than three times the bill of one at thirty."""
    from freight_fate.models.economy import REPAIR_COST_PER_PCT, Economy

    assert Economy.repair_cost(0) == 0.0
    shallow = Economy.repair_cost(30)
    deep = Economy.repair_cost(90)
    assert deep / shallow > 5.0
    # The shallow end stays close to the old flat rate: a careful driver's
    # occasional scrape must not suddenly cost more than it used to.
    assert Economy.repair_cost(10) < 10 * REPAIR_COST_PER_PCT * 1.05


def test_road_shops_share_the_garage_severity_curve():
    from freight_fate.models.economy import damage_severity_mult
    from freight_fate.states.driving_core import (
        FIELD_REPAIR_DAMAGE_PCT,
        MECHANIC_CALLOUT_FEE,
        road_repair_cost,
    )

    cost = road_repair_cost(80.0, FIELD_REPAIR_DAMAGE_PCT, MECHANIC_CALLOUT_FEE)
    flat = MECHANIC_CALLOUT_FEE + (80.0 - FIELD_REPAIR_DAMAGE_PCT) * MECHANIC_RATE_PER_PCT
    assert cost > flat
    assert damage_severity_mult(80.0) > damage_severity_mult(20.0) > 1.0


def test_preventable_damage_is_counted_apart_from_the_rest():
    t = TruckState()
    t.add_damage(10.0)  # preventable by default: nearly everything is
    t.add_damage(6.0, preventable=False)  # reacting correctly to a hazard
    assert t.damage_pct == pytest.approx(16.0)
    assert t.preventable_damage_pct == pytest.approx(10.0)


def test_collisions_and_runaways_count_as_preventable():
    t = TruckState()
    t.velocity_mps = 20.0
    t.apply_collision(0.5)
    assert t.preventable_damage_pct > 0.0

    runaway = TruckState()
    runaway.velocity_mps = 120.0 * MPS_PER_MPH
    for _ in range(120):
        runaway._update_wear(1 / 60)
    assert runaway.preventable_damage_pct == pytest.approx(runaway.damage_pct)


def test_the_settlement_charge_scales_with_the_band_the_run_reached(app, monkeypatch):
    from freight_fate.states.driving_core import PREVENTABLE_DAMAGE_DEDUCTIBLE
    from freight_fate.states.driving_damage import preventable_damage_charge

    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app, business_status=COMPANY_DRIVER)
    driving.truck.preventable_damage_pct = DAMAGE_OUT_OF_SERVICE_PCT

    driving._worst_damage_band = DAMAGE_BAND_REDUCED
    light, light_rep, reason = preventable_damage_charge(driving)
    driving._worst_damage_band = DAMAGE_BAND_OUT_OF_SERVICE
    heavy, heavy_rep, _ = preventable_damage_charge(driving)

    assert light == pytest.approx(PREVENTABLE_DAMAGE_DEDUCTIBLE)
    assert heavy > light * 3
    assert heavy_rep > light_rep > 0.0
    assert reason


def test_a_clean_run_is_charged_nothing(app, monkeypatch):
    from freight_fate.states.driving_damage import preventable_damage_charge

    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app, business_status=COMPANY_DRIVER)

    assert preventable_damage_charge(driving) == (0.0, 0.0, "")


def test_hazard_damage_alone_is_not_ruled_preventable(app, monkeypatch):
    from freight_fate.states.driving_damage import preventable_damage_charge

    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app, business_status=COMPANY_DRIVER)
    driving.truck.add_damage(DAMAGE_LIMP_PCT + 2.0, preventable=False)
    driving._update_damage_bands(1 / 60)

    deductible, reputation, _ = preventable_damage_charge(driving)
    assert deductible == 0.0
    assert reputation == 0.0


def test_the_worst_band_reached_survives_a_shoulder_repair(app, monkeypatch):
    """Patching the truck on the shoulder must not launder the run."""
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app, business_status=COMPANY_DRIVER)
    t = _rolling(driving, 60.0)
    t.add_damage(DAMAGE_LIMP_PCT + 2.0)
    driving._update_damage_bands(1 / 60)
    t.damage_pct = 5.0
    driving._update_damage_bands(1 / 60)

    assert driving.truck.damage_band == DAMAGE_BAND_NONE
    assert driving._worst_damage_band == DAMAGE_BAND_LIMP


def test_the_settlement_grade_round_trips_through_a_snapshot(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving = _driving(app, business_status=COMPANY_DRIVER)
    t = _rolling(driving, 60.0)
    t.add_damage(DAMAGE_LIMP_PCT + 2.0)
    driving._update_damage_bands(1 / 60)

    data = driving.snapshot()
    app.ctx.profile.truck_damage_pct = t.damage_pct
    restored = type(driving).from_snapshot(app.ctx, data)

    assert restored is not None
    assert restored._worst_damage_band == DAMAGE_BAND_LIMP
    assert restored.truck.preventable_damage_pct == pytest.approx(t.preventable_damage_pct)
