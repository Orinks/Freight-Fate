"""Badges for the months-long 1.9 career arc: levels, fleet, business, map."""

import pytest

from freight_fate.models.career import LEVEL_XP
from freight_fate.models.profile import Profile


def _first_unlocked_job(app, profile):
    from freight_fate.models.jobs import JobBoard

    return next(
        job
        for job in JobBoard(app.ctx.world).offers(
            profile.current_city,
            profile.career.endorsements,
            level=profile.career.level,
            market=profile.market,
        )
        if not job.locked_reason(profile.career.endorsements, profile.career.level)
    )


def _deliver(app, monkeypatch, profile):
    from freight_fate.states.driving import ArrivalState, DrivingState

    job = _first_unlocked_job(app, profile)
    route = app.ctx.world.supported_route_options(job.origin, job.destination)[0]
    driving = DrivingState(app.ctx, job, route)
    driving.trip.game_minutes = job.deadline_game_h * 30.0
    driving.speeding_strikes = 0
    monkeypatch.setattr(app.ctx, "say", lambda *_a, **_k: None)
    return ArrivalState(app.ctx, driving)


def test_new_arc_badges_exist_with_song_inspirations():
    from freight_fate.achievements import ACHIEVEMENT_BY_ID, ACHIEVEMENTS

    for badge_id in (
        "level_five",
        "level_ten",
        "level_fifteen",
        "level_twenty_five",
        "level_thirty",
        "fleet_upgrade",
        "fleet_flagship",
        "owner_operator_buyin",
        "authority_active",
        "three_trucks",
        "twenty_five_cities",
        "seventy_five_cities",
        "hundred_fifty_cities",
        "fifteen_states",
        "thirty_states",
        "dakota_delivery",
        "montana_delivery",
        "new_england_delivery",
        "self_paid_course",
    ):
        assert badge_id in ACHIEVEMENT_BY_ID, badge_id
    assert len(ACHIEVEMENTS) >= 130


def test_song_city_badges_map_to_real_cities_and_real_badges():
    from freight_fate.achievements import ACHIEVEMENT_BY_ID
    from freight_fate.app import App
    from freight_fate.states.driving_menu_states import SIMPLE_ARRIVAL_BADGES

    # The new song-city arrivals ride the same mapping as the shipped ones.
    for badge_id in (
        "muskogee_arrival",
        "kansas_city_arrival",
        "memphis_arrival",
        "saginaw_arrival",
        "fort_worth_arrival",
        "san_antonio_arrival",
        "new_orleans_arrival",
        "houston_arrival",
        "winslow_arrival",
        "chattanooga_arrival",
        "jackson_arrival",
        "abilene_arrival",
    ):
        assert badge_id in SIMPLE_ARRIVAL_BADGES.values(), badge_id
    # Either disputed Jackson earns the badge; Michigan's Jackson does not.
    assert SIMPLE_ARRIVAL_BADGES["jackson_tn_us"] == "jackson_arrival"
    assert SIMPLE_ARRIVAL_BADGES["jackson_ms_us"] == "jackson_arrival"
    assert "jackson_mi_us" not in SIMPLE_ARRIVAL_BADGES

    app = App()
    try:
        for city, badge_id in SIMPLE_ARRIVAL_BADGES.items():
            assert badge_id in ACHIEVEMENT_BY_ID, badge_id
            assert city in app.ctx.world.cities, city
    finally:
        app.shutdown()


def test_muskogee_delivery_awards_its_badge(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.states.driving import ArrivalState, DrivingState

    app = App()
    try:
        world = app.ctx.world
        destination = "muskogee_ok_us"
        origin = next(
            city
            for city in world.city_names()
            if city != destination and world.supported_route(city, destination) is not None
        )
        app.ctx.profile = Profile(name="Muskogee Run", current_city=origin)
        route = world.supported_route(origin, destination)
        miles = round(route.miles)
        job = Job(
            CARGO_CATALOG["general"],
            15,
            origin,
            f"{origin} yard",
            destination,
            miles,
            max(500, miles * 10),
            max(4.0, miles / 20.0),
            destination_location=f"{destination} dock",
        )
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        driving.trip.game_minutes = job.deadline_game_h * 30.0
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_k: None)

        ArrivalState(app.ctx, driving)

        assert "muskogee_arrival" in app.ctx.profile.achievements
    finally:
        app.shutdown()


def test_level_milestones_award_at_their_levels(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.profile = Profile(name="Milestone Driver", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[29]
        _deliver(app, monkeypatch, p)

        earned = set(p.achievements)
        assert {
            "level_three",
            "level_five",
            "level_ten",
            "level_fifteen",
            "max_level",
            "level_twenty_five",
            "level_thirty",
        } <= earned
        # City and state map progress starts counting from the first arrival.
        assert p.achievement_stats["cities_delivered"]
        assert p.achievement_stats["states_delivered"]
    finally:
        app.shutdown()


def test_veteran_badge_now_means_level_twenty(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.profile = Profile(name="Ten Not Twenty", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[9]  # level 10: senior, but not the veteran badge
        _deliver(app, monkeypatch, p)

        assert "level_ten" in p.achievements
        assert "max_level" not in p.achievements
    finally:
        app.shutdown()


def test_promotion_across_a_fleet_tier_hands_over_a_fresh_tractor(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.carrier_fleet import assigned_truck_key
    from freight_fate.models.trucks import TRUCK_CATALOG

    app = App()
    try:
        app.ctx.profile = Profile(name="Tier Jump", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[3] - 10.0  # a hair below level 4
        p.truck_damage_pct = 12.0
        p.tire_wear_pct = 9.0
        arrival = _deliver(app, monkeypatch, p)

        assert p.career.level >= 4
        assert "fleet_upgrade" in p.achievements
        summary = " ".join(arrival.summary_parts)
        assert "Dispatch upgraded your assigned tractor" in summary
        model = TRUCK_CATALOG[assigned_truck_key(p)]
        assert p.truck_fuel_gal == pytest.approx(model.specs.fuel_tank_gal)
        assert p.truck_damage_pct == 0.0
        assert p.tire_wear_pct == 0.0
    finally:
        app.shutdown()


def test_promotion_within_a_tier_keeps_the_same_tractor(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.profile = Profile(name="Same Tier", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[1] - 10.0  # a hair below level 2
        arrival = _deliver(app, monkeypatch, p)

        assert p.career.level >= 2
        assert "fleet_upgrade" not in p.achievements
        assert "Dispatch upgraded your assigned tractor" not in " ".join(arrival.summary_parts)
    finally:
        app.shutdown()


def test_owner_operator_buy_in_awards_the_title_badge(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city_business import BusinessStatusState

    app = App()
    try:
        app.ctx.profile = Profile(name="Buy In", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[17]
        p.career.deliveries = 40
        p.career.reputation = 85.0
        p.money = 60_000.0
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_k: None)
        state = BusinessStatusState(app.ctx)
        state._become_owner_operator()

        assert p.business_status != "company_driver"
        assert "owner_operator_buyin" in p.achievements
    finally:
        app.shutdown()


def test_authority_activation_awards_its_badge(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.business import LEASED_OWNER_OPERATOR
    from freight_fate.states.city_business import BusinessStatusState

    app = App()
    try:
        app.ctx.profile = Profile(name="Authority Up", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[24]
        p.career.deliveries = 90
        p.career.reputation = 95.0
        p.money = 80_000.0
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        p.truck = "rig"
        p.authority_readiness = True
        p.trailer_programs = ["dry_van", "reefer"]
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_k: None)
        state = BusinessStatusState(app.ctx)
        state._activate_authority()

        assert "authority_active" in p.achievements
    finally:
        app.shutdown()


def test_third_tractor_purchase_awards_the_yard_badge(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.business import LEASED_OWNER_OPERATOR
    from freight_fate.models.trucks import TRUCK_CATALOG
    from freight_fate.states.city_business import TruckShopState

    app = App()
    try:
        app.ctx.profile = Profile(name="Fleet Owner", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig", "heavy_hauler"]
        p.truck = "rig"
        p.money = 500_000.0
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_k: None)
        state = TruckShopState(app.ctx)
        state._pick(TRUCK_CATALOG["highline_sleeper"])

        assert len(p.owned_trucks) == 3
        assert "three_trucks" in p.achievements
    finally:
        app.shutdown()
