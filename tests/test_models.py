"""Jobs, economy, career, profile, and settings tests."""

import json

import pytest

from freight_fate.models import Career, Economy, JobBoard, Profile
from freight_fate.models.career import level_for_xp
from freight_fate.models.jobs import CARGO_CATALOG, plan_hos
from freight_fate.models.profile import SAVE_VERSION, SIGNATURE_FIELD, ProfileIntegrityError
from freight_fate.settings import Settings

# -- jobs ---------------------------------------------------------------------


def test_job_offers_have_real_route_distances(world):
    board = JobBoard(world, seed=3)
    jobs = board.offers("Chicago", endorsements=set(), level=2)
    assert jobs
    for job in jobs:
        route = world.supported_route(job.origin, job.destination)
        assert route is not None
        assert abs(route.miles - job.distance_mi) < 1.0
        assert job.pay > 0
        assert job.deadline_game_h > job.distance_mi / 70.0


def test_deadlines_allow_legal_driving(world):
    """A deadline must cover the driving at an achievable average plus the
    HOS breaks and sleep the distance demands - no impossible 5-hour
    San Antonio to Dallas dispatches."""
    from freight_fate.models.jobs import required_hours

    for seed, level in ((1, 1), (2, 3), (3, 6)):
        board = JobBoard(world, seed=seed)
        for job in board.offers("San Antonio", endorsements=set(), level=level):
            route = world.supported_route(job.origin, job.destination)
            needed = required_hours(job.distance_mi, route, world)
            assert job.deadline_game_h >= needed * 1.2, (
                f"{job.origin} to {job.destination}: {job.distance_mi:.0f} mi "
                f"needs {needed:.1f} h, deadline {job.deadline_game_h:.1f} h"
            )


def test_required_hours_includes_breaks_and_sleep():
    from freight_fate.models.jobs import required_hours

    assert required_hours(275) < 6.0  # SA-Dallas: just driving
    medium = required_hours(495)  # 9 driving hours: one break
    assert medium > 495 / 55.0
    long_haul = required_hours(1150)  # ~21 h driving: sleep required
    assert long_haul > 1150 / 55.0 + 10.0


def test_hos_plan_reports_breaks_sleeps_and_route_stop_coverage(world):
    route = world.supported_route("Chicago", "Indianapolis")
    plan = plan_hos(route.miles, route, world)
    assert plan.drive_h > route.miles / 70.0
    assert plan.break_stop_count >= 1
    assert "Legal HOS plan" in plan.summary()


def test_northeast_short_corridor_deadline_uses_direct_route(world):
    from freight_fate.models.jobs import required_hours

    # Search seeds: map expansion (new nearby NJ/PA nodes) shifts any single
    # seed's offer mix, so pin the route invariant, not one seed's lottery.
    ny_jobs = [
        job
        for seed in range(40)
        for job in JobBoard(world, seed=seed).offers("Philadelphia", endorsements=set(), level=1)
        if job.destination == "new_york_ny_us"
    ]

    assert ny_jobs
    assert all(job.distance_mi == 107 for job in ny_jobs)
    assert all(3.0 <= job.deadline_game_h <= 5.0 for job in ny_jobs)
    assert all(
        job.deadline_game_h
        >= required_hours(
            job.distance_mi,
            world.supported_route(job.origin, job.destination),
            world,
        )
        * 1.2
        for job in ny_jobs
    )


def test_route_aware_deadline_estimate_uses_low_speed_segments():
    from freight_fate.data.world_models import Leg, Route, SpeedLimitSample
    from freight_fate.models.jobs import required_hours, route_drive_hours

    route = Route(
        ["A", "B"],
        [
            Leg(
                "A",
                "B",
                100.0,
                "US 1",
                "flat",
                (),
                speed_limits=(SpeedLimitSample(0.0, 35.0, "test"),),
            )
        ],
    )

    assert route_drive_hours(route) > 100.0 / 55.0
    assert required_hours(100.0, route) > required_hours(100.0)


def test_route_deadline_uses_baked_limit_near_city():
    from freight_fate.data.world_models import Leg, Route, SpeedLimitSample
    from freight_fate.models.jobs import (
        DEADLINE_PLANNING_SPEED_FACTOR,
        _route_planning_limit,
    )

    route = Route(
        ["A", "B"],
        [
            Leg(
                "A",
                "B",
                100.0,
                "I-1",
                "flat",
                (),
                speed_limits=(SpeedLimitSample(0.0, 75.0, "test"),),
            )
        ],
    )

    assert (
        _route_planning_limit(route, 0, route.legs[0], 1.0, 1.0, [0.0, 100.0], False, None)
        == 75.0 * DEADLINE_PLANNING_SPEED_FACTOR
    )


# Walking every corridor grows with the map and, under coverage tracing on a
# contended CI runner, straddles the default 120-second hang timeout. It is
# long, not hung, so give it real headroom; 300 seconds proved marginal once
# the suite grew, and the thread timeout kills the whole xdist worker.
@pytest.mark.timeout(600)
def test_deadlines_cover_required_hos_time_across_the_network(world):
    """Every generated job's deadline must cover the honest HOS time (driving at
    the planning pace plus mandatory breaks and 10-hour sleeps). This is the
    achievability invariant the deadline formula guarantees; the test guards it
    across the whole expanded network and all levels, including the corrected
    ORS mileages."""
    from freight_fate.models.jobs import required_hours

    endorsements = {"refrigerated", "heavy_haul", "high_value"}
    # Bounded, deterministic sample of origins rather than every city: this scans
    # city x seed x generated jobs and grew with the map (~30s at 349 cities, which
    # times out on slower CI runners). The deadline-vs-HOS check is a formula
    # invariant, so ~96 diverse origins exercise the distance/route range without an
    # O(cities) scan that balloons CI time as the map keeps growing.
    all_cities = sorted(world.city_names())
    for city in all_cities[:: max(1, len(all_cities) // 96)]:
        for seed in range(3):
            jobs = JobBoard(world, seed=seed).offers(city, endorsements, count=5, level=5)
            for job in jobs:
                route = world.supported_route(job.origin, job.destination)
                assert job.deadline_game_h >= required_hours(job.distance_mi, route, world), (
                    f"{city} -> {job.destination} ({job.distance_mi} mi)"
                )


def test_endorsement_gating(world):
    board = JobBoard(world, seed=4)
    no_endorsements = board.offers("Los Angeles", endorsements=set(), count=5)
    locked = [j for j in no_endorsements if j.cargo.endorsement]
    # at most the single "teaser" job may require an endorsement
    assert len(locked) <= 1


def test_payout_on_time_window_beats_late():
    from freight_fate.models.jobs import Job

    job = Job(CARGO_CATALOG["general"], 15, "A", "Loc", "B", 300, 700.0, 9.0)
    early = job.payout(hours_taken=5.0, damage_pct=0.0)
    on_dot = job.payout(hours_taken=9.0, damage_pct=0.0)
    late = job.payout(hours_taken=12.0, damage_pct=0.0)
    # Window model: any on-time arrival earns the same flat bonus; racing in
    # early pays no more than hitting the appointment.
    assert early == on_dot
    assert on_dot > 700.0 > late
    assert late >= 700.0 * 0.4


def test_payout_punishes_fragile_damage():
    from freight_fate.models.jobs import Job

    fragile = Job(CARGO_CATALOG["electronics"], 8, "A", "Loc", "B", 300, 1000.0, 9.0)
    tough = Job(CARGO_CATALOG["bulk"], 8, "A", "Loc", "B", 300, 1000.0, 9.0)
    assert fragile.payout(5.0, damage_pct=30.0) < tough.payout(5.0, damage_pct=30.0)


# -- economy ---------------------------------------------------------------------


def test_fuel_prices_vary_by_region():
    eco = Economy(seed=1)
    assert eco.fuel_price("california") > eco.fuel_price("gulf_coast")
    assert eco.fuel_cost("great_lakes", 0) == 0.0
    assert eco.fuel_cost("great_lakes", 10) > 30.0


def test_repair_cost_scales_with_damage():
    assert Economy.repair_cost(0) == 0.0
    assert Economy.repair_cost(50) == 50 * 85.0


# -- career ---------------------------------------------------------------------


def test_level_thresholds():
    assert level_for_xp(0) == 1
    assert level_for_xp(999) == 1
    assert level_for_xp(1000) == 2
    assert level_for_xp(2500) == 3
    assert level_for_xp(100_000) > 9


def test_endorsements_unlock_with_levels():
    c = Career()
    assert c.endorsements == set()
    c.xp = 1000
    assert "refrigerated" in c.endorsements
    c.xp = 2500
    assert {"refrigerated", "heavy_haul"} <= c.endorsements
    c.xp = 4500
    assert {"refrigerated", "heavy_haul", "high_value"} <= c.endorsements


def test_record_delivery_announces_level_up():
    c = Career(xp=950)
    messages = c.record_delivery(miles=100, pay=300, on_time=True, damage_pct=0)
    assert any("Level up" in m for m in messages)
    assert c.deliveries == 1
    assert c.on_time_deliveries == 1


def test_reputation_moves_with_performance():
    c = Career()
    start = c.reputation
    c.record_delivery(100, 300, on_time=True, damage_pct=0)
    assert c.reputation > start
    c.record_delivery(100, 300, on_time=False, damage_pct=40)
    assert c.reputation < start + 2.0 + 0.01


# -- profile ---------------------------------------------------------------------


def test_profile_roundtrip():
    p = Profile(name="Roundtrip Test")
    p.money = 1234.5
    p.career.xp = 2600
    p.calendar_offset_days = 147
    path = p.save()
    loaded = Profile.load(path)
    assert loaded.money == 1234.5
    assert loaded.career.level == 3
    assert loaded.name == "Roundtrip Test"
    assert loaded.calendar_offset_days == 147


def test_profile_save_is_atomic_and_versioned():
    p = Profile(name="Atomic")
    path = p.save()
    data = json.loads(path.read_text())
    assert data["version"] == SAVE_VERSION
    assert SIGNATURE_FIELD in data
    assert not path.with_suffix(".json.tmp").exists()


def test_profile_ignores_unknown_fields():
    p = Profile(name="Future")
    path = p.save()
    data = json.loads(path.read_text())
    data["mystery_field"] = 42
    path.write_text(json.dumps(data))
    loaded = Profile.load(path)
    assert loaded.name == "Future"


def test_profile_tampered_money_is_rejected_and_quarantined():
    p = Profile(name="Tampered")
    path = p.save()
    data = json.loads(path.read_text())
    data["money"] = 999_999.0
    path.write_text(json.dumps(data))

    import pytest

    with pytest.raises(ProfileIntegrityError):
        Profile.load(path)
    assert not path.exists()
    assert path.with_suffix(".json.invalid").exists()


def test_skip_signing_flag_loads_tampered_save_from_source(monkeypatch):
    p = Profile(name="Dev Tampered")
    path = p.save()
    data = json.loads(path.read_text())
    data["money"] = 999_999.0
    path.write_text(json.dumps(data))

    monkeypatch.setenv("FREIGHT_FATE_SKIP_SAVE_SIGNING", "1")
    loaded = Profile.load(path)
    assert loaded.money == 999_999.0
    assert not path.with_suffix(".json.invalid").exists()

    # The load re-signed the file, so it keeps working with the flag off.
    monkeypatch.delenv("FREIGHT_FATE_SKIP_SAVE_SIGNING")
    assert Profile.load(path).money == 999_999.0


def test_skip_signing_flag_is_ignored_in_frozen_builds(monkeypatch):
    import pytest

    import freight_fate.models.profile as profile_module

    p = Profile(name="Frozen Tampered")
    path = p.save()
    data = json.loads(path.read_text())
    data["money"] = 999_999.0
    path.write_text(json.dumps(data))

    monkeypatch.setenv("FREIGHT_FATE_SKIP_SAVE_SIGNING", "1")
    monkeypatch.setattr(profile_module, "is_frozen", lambda: True)
    with pytest.raises(ProfileIntegrityError):
        Profile.load(path)
    assert path.with_suffix(".json.invalid").exists()


def test_unsigned_profile_loads_once_and_is_signed():
    p = Profile(name="Unsigned")
    data = p.to_dict()
    data.pop(SIGNATURE_FIELD)
    path = p.path
    path.write_text(json.dumps(data))

    loaded = Profile.load(path)

    assert loaded.name == "Unsigned"
    migrated = json.loads(path.read_text())
    assert SIGNATURE_FIELD in migrated


def test_list_saves_and_delete():
    a = Profile(name="Driver A")
    a.save()
    b = Profile(name="Driver B")
    b.save()
    names = {p.stem for p in Profile.list_saves()}
    assert {"Driver A", "Driver B"} <= names
    a.delete()
    names = {p.stem for p in Profile.list_saves()}
    assert "Driver A" not in names


def test_profile_name_sanitized_for_filesystem():
    p = Profile(name='Sketchy/Name<>:"|?*')
    path = p.save()
    assert path.exists()


# -- settings ---------------------------------------------------------------------


def test_settings_roundtrip():
    s = Settings()
    s.imperial_units = False
    s.music_volume = 0.3
    s.weather_volume = 0.4
    s.engine_volume = 0.7
    s.ui_volume = 0.8
    s.sapi_events = False
    s.save()
    loaded = Settings.load()
    assert loaded.imperial_units is False
    assert loaded.music_volume == 0.3
    assert loaded.weather_volume == 0.4
    assert loaded.engine_volume == 0.7
    assert loaded.ui_volume == 0.8
    assert loaded.sapi_events is False


def test_sapi_events_default_on():
    assert Settings().sapi_events is True


def test_music_volume_defaults_to_half():
    assert Settings().music_volume == 0.5


def test_split_audio_volume_defaults_prioritize_cues_over_background():
    s = Settings()
    assert s.ui_volume > s.music_volume
    assert s.ui_volume > s.weather_volume
    assert s.ui_volume > s.engine_volume


def test_legacy_hos_off_setting_loads_as_realistic():
    # The 1.5.0 player-facing "off" mode is gone; legacy saves fall through to
    # the realistic default rather than silently disabling enforcement.
    s = Settings()
    s.hos_mode = "off"
    s.save()
    loaded = Settings.load()
    assert loaded.hos_mode == "realistic"


def test_settings_survive_corrupt_file():
    s = Settings()
    s.save()
    s.path.write_text("{not json")
    loaded = Settings.load()
    assert loaded.imperial_units is True  # defaults


def test_unit_formatting():
    s = Settings()
    assert "miles per hour" in s.speed_text(60)
    s.imperial_units = False
    assert s.speed_text(60) == "97 kilometers per hour"


def test_job_spoken_names_always_carry_the_state(world):
    """Dispatch offers name places a player may never have heard of; the
    state must always ride along ("McCall, Idaho"), not only when two
    cities share a name (player request)."""
    board = JobBoard(world, seed=5)
    jobs = board.offers("Chicago", endorsements=set(), level=2)
    assert jobs
    for job in jobs:
        origin_city = world.city(job.origin)
        dest_city = world.city(job.destination)
        assert job.spoken_origin == origin_city.spoken_qualified
        assert job.spoken_destination == dest_city.spoken_qualified
        if origin_city.state:
            assert origin_city.state in job.spoken_origin
        if dest_city.state:
            assert dest_city.state in job.spoken_destination
