"""Consumable buffs: catalog, availability by brand, purchase, and physics."""

from types import SimpleNamespace

import pytest

from freight_fate.data.buffs import BUFF_CATALOG, BUFF_GROUPS, buffs_for_stop
from freight_fate.models.business import COMPANY_DRIVER, LEASED_OWNER_OPERATOR
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.sim.vehicle import TruckState
from freight_fate.states.driving import RestStopState


def _job() -> Job:
    return Job(CARGO_CATALOG["general"], 12.0, "Denver", "yard", "Salt Lake City", 200.0, 900.0, 12.0)


def _driving(app, business_status=LEASED_OWNER_OPERATOR):
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Buff Tester", current_city="Denver")
    app.ctx.profile.business_status = business_status
    if business_status != COMPANY_DRIVER:
        app.ctx.profile.owned_trucks = ["rig"]
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, _job(), route, trip_seed=99, start_hour=10.0)
    app.push_state(driving)
    return driving


def _stop(driving, name, actions=("fuel", "break")):
    return SimpleNamespace(
        name=name,
        at_mi=driving.trip.position_mi,
        type="travel_center",
        actions=tuple(actions),
        services=(),
        parking="limited",
        exit_label="",
        spoken_name=name,
        parking_text="limited truck parking",
    )


def _quiet(app, monkeypatch, spoken=None):
    monkeypatch.setattr(
        app.ctx,
        "say",
        lambda text, interrupt=True: spoken.append(text) if spoken is not None else None,
    )
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)


def _buff_ids(name, actions=()):
    return {buff.id for buff in buffs_for_stop(name, tuple(actions))}


# -- catalog ------------------------------------------------------------------------


def test_catalog_loads_and_is_valid():
    # the loader raises on any invalid entry at import; spot-check the shape
    assert BUFF_CATALOG
    for buff in BUFF_CATALOG.values():
        assert buff.group in BUFF_GROUPS
        assert 0.0 < buff.rate <= 1.0
        assert buff.help and buff.purchased
        if buff.group == "fatigue":
            assert buff.duration_game_h > 0.0
            assert buff.worn_off
        else:
            assert buff.trip_scoped


def test_brand_availability_matches_signatures():
    assert _buff_ids("Love's Travel Stop", ("fuel",)) == {
        "energy_drink",
        "diesel_additive",
        "quick_lube",
        "tire_rotation",
    }
    assert _buff_ids("Pilot Travel Center", ("fuel",)) == {
        "energy_drink",
        "diesel_additive",
        "shower",
    }
    assert _buff_ids("Petro Stopping Center", ("fuel", "food")) == {
        "energy_drink",
        "diesel_additive",
        "diner_meal",
        "iron_skillet_dinner",
    }
    assert _buff_ids("Cactus Flats Truck Stop", ("food",)) == {"diner_meal"}
    assert _buff_ids("Big Buck's Travel Center") == {"big_bucks_brisket"}


# -- purchases ----------------------------------------------------------------------


def test_energy_drink_lifts_fatigue_and_starts_a_timed_buff(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        spoken = []
        _quiet(app, monkeypatch, spoken)
        driving = _driving(app)
        p = app.ctx.profile
        p.money = 1_000.0
        p.fatigue = 50.0
        state = RestStopState(app.ctx, driving, _stop(driving, "Cactus Flats Truck Stop"))
        app.push_state(state)
        minutes_before = driving.trip.game_minutes

        state._buy_buff(BUFF_CATALOG["energy_drink"])

        assert p.money == pytest.approx(994.0)
        assert p.fatigue == pytest.approx(47.0)
        assert len(p.active_buffs) == 1
        entry = p.active_buffs[0]
        assert entry["id"] == "energy_drink"
        assert entry["rate"] == pytest.approx(0.85)
        assert driving.trip.game_minutes == pytest.approx(minutes_before + 5.0)
        assert "sharper" in spoken[-1]
    finally:
        app.shutdown()


def test_new_fatigue_buff_replaces_the_old_one(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        _quiet(app, monkeypatch)
        driving = _driving(app)
        p = app.ctx.profile
        p.money = 1_000.0
        state = RestStopState(app.ctx, driving, _stop(driving, "Cactus Flats", ("fuel", "food")))
        app.push_state(state)

        state._buy_buff(BUFF_CATALOG["energy_drink"])
        state._buy_buff(BUFF_CATALOG["diner_meal"])

        assert [entry["id"] for entry in p.active_buffs] == ["diner_meal"]
    finally:
        app.shutdown()


def test_shower_is_free_after_fueling_at_pilot(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        _quiet(app, monkeypatch)
        driving = _driving(app)
        p = app.ctx.profile
        p.money = 5_000.0
        driving.truck.fuel_gal = 40.0
        state = RestStopState(app.ctx, driving, _stop(driving, "Pilot Travel Center"))
        app.push_state(state)
        shower = BUFF_CATALOG["shower"]

        assert state._buff_price(shower) == pytest.approx(15.0)
        state._refuel()
        assert state._buff_price(shower) == 0.0
        assert "free with your fuel purchase" in state._buff_label(shower)
        money_after_fuel = p.money
        state._buy_buff(shower)
        assert p.money == money_after_fuel
        assert p.active_buffs[0]["id"] == "shower"
    finally:
        app.shutdown()


def test_quick_lube_sets_a_trip_buff_and_carrier_pays_for_company_drivers(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        spoken = []
        _quiet(app, monkeypatch, spoken)
        driving = _driving(app, business_status=COMPANY_DRIVER)
        p = app.ctx.profile
        money_before = p.money
        state = RestStopState(app.ctx, driving, _stop(driving, "Speedco Truck Service"))
        app.push_state(state)

        state._buy_buff(BUFF_CATALOG["quick_lube"])

        assert p.money == money_before
        assert driving.rig_buffs["engine"]["rate"] == pytest.approx(0.75)
        assert "carrier" in spoken[-1].lower()
        assert driving.snapshot()["rig_buffs"]["engine"]["id"] == "quick_lube"
    finally:
        app.shutdown()


def test_food_stays_personal_money_for_company_drivers(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        _quiet(app, monkeypatch)
        driving = _driving(app, business_status=COMPANY_DRIVER)
        p = app.ctx.profile
        p.money = 100.0
        state = RestStopState(app.ctx, driving, _stop(driving, "Cactus Flats", ("food",)))
        app.push_state(state)

        state._buy_buff(BUFF_CATALOG["diner_meal"])

        assert p.money == pytest.approx(100.0 - 18.0)
    finally:
        app.shutdown()


def test_big_bucks_buffs_require_running_bobtail(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        _quiet(app, monkeypatch)
        driving = _driving(app)
        stop = _stop(driving, "Big Buck's Travel Center", ())
        loaded = RestStopState(app.ctx, driving, stop)
        texts = [i.text if isinstance(i.text, str) else i.text() for i in loaded.build_items()]
        assert not any("brisket" in t.lower() for t in texts)

        driving.job.bobtail = True
        bobtail = RestStopState(app.ctx, driving, stop)
        texts = [i.text if isinstance(i.text, str) else i.text() for i in bobtail.build_items()]
        assert any("brisket" in t.lower() for t in texts)
    finally:
        app.shutdown()


# -- effects and expiry ----------------------------------------------------------------


def test_fatigue_buff_rate_active_then_expires():
    p = Profile(name="Rate")
    p.add_timed_buff(
        {"id": "energy_drink", "label": "Energy drink", "group": "fatigue",
         "rate": 0.85, "expires_h": 12.0, "worn_off": "The energy drink has worn off."}
    )
    assert p.fatigue_buff_rate(11.0) == pytest.approx(0.85)
    expired = p.expire_buffs(12.5)
    assert [entry["id"] for entry in expired] == ["energy_drink"]
    assert p.active_buffs == []
    assert p.fatigue_buff_rate(12.5) == 1.0


def test_tire_buff_slows_tread_wear():
    plain = TruckState()
    buffed = TruckState()
    buffed.tire_wear_buff_mult = 0.5
    for t in (plain, buffed):
        t.velocity_mps = 25.0
        t._update_wear(60.0)
    assert plain.tire_wear_pct > 0.0
    assert buffed.tire_wear_pct == pytest.approx(plain.tire_wear_pct * 0.5)


def test_engine_buff_slows_duty_wear_but_not_over_rev_abuse():
    plain = TruckState()
    buffed = TruckState()
    buffed.engine_wear_buff_mult = 0.5
    for t in (plain, buffed):
        t.start_engine()
        t.throttle = 0.6
        t.rpm = 1_500.0
        t._update_wear(600.0)
    assert plain.engine_wear_pct > 0.0
    assert buffed.engine_wear_pct == pytest.approx(plain.engine_wear_pct * 0.5)

    # over-revving charges full price no matter the buff
    plain_abuse = TruckState()
    buffed_abuse = TruckState()
    buffed_abuse.engine_wear_buff_mult = 0.5
    for t in (plain_abuse, buffed_abuse):
        t.start_engine()
        t.throttle = 0.0
        t.rpm = t.specs.max_rpm * 1.1  # a downgrade driving the engine past the governor
        t._update_wear(1.0)
    assert plain_abuse.engine_wear_pct >= 0.8  # the abuse term alone
    assert buffed_abuse.engine_wear_pct == pytest.approx(plain_abuse.engine_wear_pct, abs=1e-3)


def test_active_buffs_round_trip_through_a_saved_profile():
    p = Profile(name="Buff Save")
    p.add_timed_buff(
        {"id": "diner_meal", "label": "Diner meal", "group": "fatigue",
         "rate": 0.75, "expires_h": 40.0, "worn_off": "That meal has worn off."}
    )
    path = p.save()
    loaded = Profile.load(path)
    assert loaded.active_buffs == p.active_buffs
