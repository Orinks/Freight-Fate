"""Jobs, economy, career, profile, and settings tests."""

import json

from freight_fate.models import Career, Economy, JobBoard, Profile
from freight_fate.models.business import (
    COMPANY_DRIVER,
    INDEPENDENT_AUTHORITY,
    LEASED_OWNER_OPERATOR,
    business_status_summary,
)
from freight_fate.models.career import LEVEL_XP, level_for_xp
from freight_fate.models.career_ladder import (
    MAX_CAREER_LEVEL,
    STARTER_CARRIER_NAME,
    rank_for_level,
)
from freight_fate.models.jobs import CARGO_CATALOG, plan_hos
from freight_fate.models.profile import SIGNATURE_FIELD, ProfileIntegrityError
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
            needed = required_hours(job.distance_mi)
            assert job.deadline_game_h >= needed * 1.2, (
                f"{job.origin} to {job.destination}: {job.distance_mi:.0f} mi "
                f"needs {needed:.1f} h, deadline {job.deadline_game_h:.1f} h")


def test_required_hours_includes_breaks_and_sleep():
    from freight_fate.models.jobs import required_hours

    assert required_hours(275) < 6.0            # SA-Dallas: just driving
    medium = required_hours(495)                # 9 driving hours: one break
    assert medium > 495 / 55.0
    long_haul = required_hours(1150)            # ~21 h driving: sleep required
    assert long_haul > 1150 / 55.0 + 10.0


def test_hos_plan_reports_breaks_sleeps_and_route_stop_coverage(world):
    route = world.supported_route("Chicago", "Indianapolis")
    plan = plan_hos(route.miles, route)
    assert plan.drive_h == route.miles / 55.0
    assert plan.break_stop_count >= 1
    assert "Legal HOS plan" in plan.summary()


def test_northeast_short_corridor_deadline_uses_direct_route(world):
    from freight_fate.models.jobs import required_hours

    # Search seeds: map expansion (new nearby NJ/PA nodes) shifts any single
    # seed's offer mix, so pin the route invariant, not one seed's lottery.
    ny_jobs = [
        job
        for seed in range(40)
        for job in JobBoard(world, seed=seed).offers(
            "Philadelphia", endorsements=set(), level=1)
        if job.destination == "New York"
    ]

    assert ny_jobs
    assert all(job.distance_mi == 94 for job in ny_jobs)
    assert all(3.0 <= job.deadline_game_h <= 4.0 for job in ny_jobs)
    assert all(job.deadline_game_h >= required_hours(job.distance_mi) * 1.2
               for job in ny_jobs)


def test_deadlines_cover_required_hos_time_across_the_network(world):
    """Every generated job's deadline must cover the honest HOS time (driving at
    the planning pace plus mandatory breaks and 10-hour sleeps). This is the
    achievability invariant the deadline formula guarantees; the test guards it
    across the whole expanded network and all levels, including the corrected
    ORS mileages."""
    from freight_fate.models.jobs import required_hours

    endorsements = {"refrigerated", "heavy_haul", "high_value"}
    for city in world.city_names():
        for seed in range(3):
            jobs = JobBoard(world, seed=seed).offers(
                city, endorsements, count=5, level=5)
            for job in jobs:
                assert job.deadline_game_h >= required_hours(job.distance_mi), (
                    f"{city} -> {job.destination} ({job.distance_mi} mi)")


def test_endorsement_gating(world):
    board = JobBoard(world, seed=4)
    no_endorsements = board.offers("Los Angeles", endorsements=set(), count=5)
    locked = [j for j in no_endorsements if j.cargo.endorsement]
    # at most the single "teaser" job may require an endorsement
    assert len(locked) <= 1


def test_payout_on_time_beats_late():
    from freight_fate.models.jobs import Job

    job = Job(CARGO_CATALOG["general"], 15, "A", "Loc", "B", 300, 700.0, 9.0)
    early = job.payout(hours_taken=5.0, damage_pct=0.0)
    on_dot = job.payout(hours_taken=9.0, damage_pct=0.0)
    late = job.payout(hours_taken=12.0, damage_pct=0.0)
    assert early > on_dot >= late
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
    assert level_for_xp(202_000) == 20
    assert rank_for_level(20).title == "Established Owner-Operator"
    assert level_for_xp(LEVEL_XP[-1]) == MAX_CAREER_LEVEL
    assert level_for_xp(999_999) == MAX_CAREER_LEVEL
    assert rank_for_level(MAX_CAREER_LEVEL).title == "Freight Fate Independent"


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
    assert any("New Hire Company Driver" in m for m in messages)
    assert c.deliveries == 1
    assert c.on_time_deliveries == 1


def test_career_summary_includes_rank_and_next_step():
    c = Career()

    text = c.summary()

    assert "Yard Trainee" in text
    assert "Career stage: Company driver" in text
    assert "Next: level 2, New Hire Company Driver" in text


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
    p.business_status = LEASED_OWNER_OPERATOR
    p.carrier_name = "Test Carrier"
    path = p.save()
    loaded = Profile.load(path)
    assert loaded.money == 1234.5
    assert loaded.career.level == 3
    assert loaded.business_status == LEASED_OWNER_OPERATOR
    assert loaded.carrier_name == "Test Carrier"
    assert loaded.name == "Roundtrip Test"


def test_profile_save_is_atomic_and_versioned():
    p = Profile(name="Atomic")
    path = p.save()
    data = json.loads(path.read_text())
    assert data["version"] == 10
    assert SIGNATURE_FIELD in data
    assert not path.with_suffix(".json.tmp").exists()


def test_old_save_without_business_status_loads_as_company_driver():
    p = Profile(name="Old Business")
    data = p.to_dict()
    data.pop("business_status")
    data.pop(SIGNATURE_FIELD)
    path = p.path
    path.write_text(json.dumps(data))

    loaded = Profile.load(path)

    assert loaded.business_status == COMPANY_DRIVER
    assert STARTER_CARRIER_NAME in business_status_summary(loaded)


def test_independent_authority_status_round_trips():
    p = Profile(name="Authority Save")
    p.business_status = INDEPENDENT_AUTHORITY
    p.owned_trucks = ["rig"]
    p.owned_trailers = ["dry_van", "reefer"]
    path = p.save()

    loaded = Profile.load(path)

    assert loaded.business_status == INDEPENDENT_AUTHORITY
    assert loaded.owns_equipment()
    assert loaded.visible_owned_trailers() == ("dry_van", "reefer")


def test_old_save_without_carrier_loads_with_starter_company():
    p = Profile(name="Old Carrier")
    data = p.to_dict()
    data.pop("carrier_name")
    data.pop(SIGNATURE_FIELD)
    path = p.path
    path.write_text(json.dumps(data))

    loaded = Profile.load(path)

    assert loaded.carrier_name == STARTER_CARRIER_NAME


def test_old_owner_operator_save_without_trailer_programs_gets_basic_program():
    p = Profile(name="Old Trailer Program")
    p.business_status = LEASED_OWNER_OPERATOR
    p.owned_trucks = ["rig"]
    data = p.to_dict()
    data.pop("trailer_programs")
    data.pop(SIGNATURE_FIELD)
    path = p.path
    path.write_text(json.dumps(data))

    loaded = Profile.load(path)

    assert loaded.business_status == LEASED_OWNER_OPERATOR
    assert loaded.active_trailer_programs() == ("dry_van",)


def test_old_save_without_start_choice_fields_uses_northstar_company_start():
    from freight_fate.models.start_options import DEFAULT_START_KEY, START_MODE_COMPANY

    p = Profile(name="Old Start")
    data = p.to_dict()
    data.pop("carrier_key")
    data.pop("start_mode")
    data.pop(SIGNATURE_FIELD)
    path = p.path
    path.write_text(json.dumps(data))

    loaded = Profile.load(path)

    assert loaded.carrier_key == DEFAULT_START_KEY
    assert loaded.start_mode == START_MODE_COMPANY
    assert loaded.business_status == COMPANY_DRIVER


def test_old_save_without_authority_readiness_loads_with_default():
    p = Profile(name="Old Authority")
    data = p.to_dict()
    data.pop("authority_readiness")
    data.pop(SIGNATURE_FIELD)
    path = p.path
    path.write_text(json.dumps(data))

    loaded = Profile.load(path)

    assert loaded.authority_readiness is False


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
    s.radio_volume = 0.2
    s.radio_enabled = False
    s.radio_station_id = "ff-night-line"
    s.radio_streamer_safe = False
    s.radio_real_streams = True
    s.weather_volume = 0.4
    s.engine_volume = 0.7
    s.ui_volume = 0.8
    s.sapi_events = False
    s.save()
    loaded = Settings.load()
    assert loaded.imperial_units is False
    assert loaded.music_volume == 0.3
    assert loaded.radio_volume == 0.2
    assert loaded.radio_enabled is False
    assert loaded.radio_station_id == "ff-night-line"
    assert loaded.radio_streamer_safe is False
    assert loaded.radio_real_streams is True
    assert loaded.weather_volume == 0.4
    assert loaded.engine_volume == 0.7
    assert loaded.ui_volume == 0.8
    assert loaded.sapi_events is False


def test_sapi_events_default_on():
    assert Settings().sapi_events is True


def test_music_volume_defaults_to_half():
    assert Settings().music_volume == 0.5


def test_radio_defaults_are_streamer_safe_and_quiet():
    s = Settings()
    assert s.radio_enabled is True
    assert s.radio_volume == 0.25
    assert s.radio_streamer_safe is True
    assert s.radio_real_streams is False


def test_split_audio_volume_defaults_prioritize_cues_over_background():
    s = Settings()
    assert s.ui_volume > s.music_volume
    assert s.ui_volume > s.radio_volume
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
