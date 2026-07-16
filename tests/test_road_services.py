"""Brand-keyed wear service at road stops: who fixes what, and at what price."""

from types import SimpleNamespace

import pytest

from freight_fate.models.business import COMPANY_DRIVER, LEASED_OWNER_OPERATOR
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.states.driving import (
    ROAD_BRAKE_COST_PER_PCT,
    ROAD_TIRE_COST_PER_PCT,
    ROAD_TIRE_SPECIALIST_COST_PER_PCT,
    RestStopState,
)


def _job() -> Job:
    return Job(CARGO_CATALOG["general"], 12.0, "Denver", "yard", "Salt Lake City", 200.0, 900.0, 12.0)


def _driving(app, business_status=LEASED_OWNER_OPERATOR):
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Road Wear", current_city="Denver")
    app.ctx.profile.business_status = business_status
    if business_status != COMPANY_DRIVER:
        app.ctx.profile.owned_trucks = ["rig"]
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, _job(), route, trip_seed=99, start_hour=10.0)
    app.push_state(driving)
    return driving


def _stop(driving, name):
    return SimpleNamespace(
        name=name,
        at_mi=driving.trip.position_mi,
        type="travel_center",
        actions=("fuel", "break"),
        services=(),
        parking="limited",
        exit_label="",
        spoken_name=name,
        parking_text="limited truck parking",
    )


def _labels(state) -> list[str]:
    return [
        item.text if isinstance(item.text, str) else item.text() for item in state.build_items()
    ]


def _quiet(app, monkeypatch, spoken=None):
    monkeypatch.setattr(
        app.ctx, "say", lambda text, interrupt=True: spoken.append(text) if spoken is not None else None
    )
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)


# -- who offers what --------------------------------------------------------------


def test_tire_brand_offers_tires_but_not_brakes(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        _quiet(app, monkeypatch)
        driving = _driving(app)
        driving.truck.tire_wear_pct = 20.0
        driving.truck.brake_wear_pct = 20.0
        state = RestStopState(app.ctx, driving, _stop(driving, "Love's Travel Stop"))
        labels = _labels(state)
        assert any(label.startswith("Replace tires") for label in labels)
        assert not any(label.startswith("Brake job") for label in labels)
    finally:
        app.shutdown()


def test_full_service_brand_offers_brakes_and_marked_up_tires(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        _quiet(app, monkeypatch)
        driving = _driving(app)
        driving.truck.tire_wear_pct = 20.0
        driving.truck.brake_wear_pct = 30.0
        state = RestStopState(app.ctx, driving, _stop(driving, "TA Petro Travel Center"))
        labels = _labels(state)
        tire_cost = 20.0 * ROAD_TIRE_COST_PER_PCT
        brake_cost = 30.0 * ROAD_BRAKE_COST_PER_PCT
        assert f"Replace tires: 20 percent wear for {tire_cost:,.0f} dollars" in labels
        assert f"Brake job: 30 percent wear for {brake_cost:,.0f} dollars" in labels
    finally:
        app.shutdown()


def test_tire_specialist_beats_general_travel_center_price(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        _quiet(app, monkeypatch)
        driving = _driving(app)
        driving.truck.tire_wear_pct = 20.0
        specialist = RestStopState(app.ctx, driving, _stop(driving, "Speedco Truck Service"))
        general = RestStopState(app.ctx, driving, _stop(driving, "Pilot Travel Center"))
        cheap = 20.0 * ROAD_TIRE_SPECIALIST_COST_PER_PCT
        marked_up = 20.0 * ROAD_TIRE_COST_PER_PCT
        assert f"Replace tires: 20 percent wear for {cheap:,.0f} dollars" in _labels(specialist)
        assert f"Replace tires: 20 percent wear for {marked_up:,.0f} dollars" in _labels(general)
    finally:
        app.shutdown()


def test_generic_stop_and_big_bucks_offer_no_wear_service(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        _quiet(app, monkeypatch)
        driving = _driving(app)
        driving.truck.tire_wear_pct = 40.0
        driving.truck.brake_wear_pct = 40.0
        for name in ("Cactus Flats Truck Stop", "Big Buck's Travel Center"):
            state = RestStopState(app.ctx, driving, _stop(driving, name))
            labels = _labels(state)
            assert not any(label.startswith("Replace tires") for label in labels)
            assert not any(label.startswith("Brake job") for label in labels)
    finally:
        app.shutdown()


# -- paying for the work -----------------------------------------------------------


def test_road_tire_service_charges_and_clears_wear(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        spoken = []
        _quiet(app, monkeypatch, spoken)
        driving = _driving(app)
        p = app.ctx.profile
        p.money = 5_000.0
        driving.truck.tire_wear_pct = 20.0
        state = RestStopState(app.ctx, driving, _stop(driving, "Love's Travel Stop"))
        app.push_state(state)
        minutes_before = driving.trip.game_minutes

        state._service_tires()

        assert driving.truck.tire_wear_pct == 0.0
        assert p.tire_wear_pct == 0.0  # synced through store_truck_condition
        assert p.money == pytest.approx(5_000.0 - 20.0 * ROAD_TIRE_SPECIALIST_COST_PER_PCT)
        assert driving.trip.game_minutes > minutes_before
        assert "Tires replaced" in spoken[-1]
    finally:
        app.shutdown()


def test_road_brake_job_is_all_or_nothing_when_broke(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        spoken = []
        _quiet(app, monkeypatch, spoken)
        driving = _driving(app)
        p = app.ctx.profile
        p.money = 100.0
        driving.truck.brake_wear_pct = 30.0
        state = RestStopState(app.ctx, driving, _stop(driving, "Petro Stopping Center"))
        app.push_state(state)

        state._service_brakes()

        assert driving.truck.brake_wear_pct == 30.0
        assert p.money == 100.0
        assert "cannot afford" in spoken[-1]
    finally:
        app.shutdown()


def test_company_driver_road_wear_service_is_carrier_billed(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        spoken = []
        _quiet(app, monkeypatch, spoken)
        driving = _driving(app, business_status=COMPANY_DRIVER)
        p = app.ctx.profile
        money_before = p.money
        driving.truck.brake_wear_pct = 30.0
        state = RestStopState(app.ctx, driving, _stop(driving, "TA Travel Center"))
        app.push_state(state)

        state._service_brakes()

        assert driving.truck.brake_wear_pct == 0.0
        assert p.money == money_before
        assert "carrier account" in spoken[-1]
    finally:
        app.shutdown()
