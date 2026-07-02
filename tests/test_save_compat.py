"""Saves from older nightly/stable builds keep loading on this snapshot."""

from freight_fate.models.business import COMPANY_DRIVER
from freight_fate.models.dispatch_policy import dispatch_policy
from freight_fate.models.profile import SAVE_VERSION, Profile


def _v4_nightly_payload() -> dict:
    """The exact top-level shape a v1.7-era build (SAVE_VERSION 4) wrote.

    No hos/duty_log blocks, no business-status fields, no tire wear, and
    ``owned_trucks`` defaulted to the starter rig.
    """
    return {
        "version": 4,
        "name": "Legacy Driver",
        "money": 12_345.0,
        "current_city": "Chicago",
        "truck_damage_pct": 12.0,
        "truck_fuel_gal": 90.0,
        "game_hours": 55.0,
        "tutorial_done": True,
        "truck": "rig",
        "owned_trucks": ["rig"],
        "upgrades": {"engine_tune": 1},
        "active_trip": None,
        "dispatch_board_cache": None,
        "fatigue": 20.0,
        "pay_advance": 0.0,
        "pay_advance_used_for_load": False,
        "career": {
            "xp": 12_000.0,
            "reputation": 74.0,
            "deliveries": 18,
            "on_time_deliveries": 16,
            "total_miles": 9_000.0,
            "total_earnings": 30_000.0,
        },
        "market": {"seed": 1234, "day": 2},
        "achievements": ["first_dispatch"],
        "achievement_stats": {},
    }


def test_v4_nightly_save_loads_with_current_defaults():
    profile = Profile.from_dict(_v4_nightly_payload())

    assert profile.name == "Legacy Driver"
    assert profile.money == 12_345.0
    assert profile.career.level == 6
    assert profile.career.dispatch_declines_used == 0
    # fields added since v4 default cleanly
    assert profile.business_status == COMPANY_DRIVER
    assert profile.tire_wear_pct == 0.0
    assert profile.road_grime_pct == 0.0
    assert profile.trailer_programs == []
    assert profile.hos.driving_min == 0.0  # fresh clock, not a violation
    assert profile.duty_log.segments == []


def test_v4_save_joins_the_dispatch_autonomy_bands_at_its_level():
    profile = Profile.from_dict(_v4_nightly_payload())

    policy = dispatch_policy(profile)  # level 6 company driver: new-hire band
    assert policy.assigns_load
    assert policy.assigns_route

    profile.career.xp = 25_000.0  # level 8+
    assert not dispatch_policy(profile).assigns_load


def test_v4_save_round_trips_to_current_version():
    profile = Profile.from_dict(_v4_nightly_payload())
    data = profile.to_dict()

    assert data["version"] == SAVE_VERSION
    reloaded = Profile.from_dict(data)
    assert reloaded.career.deliveries == 18
    assert reloaded.market.day == 2


def test_newer_save_with_unknown_fields_still_loads():
    data = _v4_nightly_payload()
    data["career"]["future_counter"] = 7
    data["market"]["future_flag"] = True
    data["some_future_top_level_field"] = {"nested": 1}

    profile = Profile.from_dict(data)

    assert profile.career.deliveries == 18
    assert profile.market.seed == 1234


def test_corrupt_nested_payload_types_fall_back_to_defaults():
    data = _v4_nightly_payload()
    data["career"] = "not-a-dict"
    data["market"] = 42

    profile = Profile.from_dict(data)

    assert profile.career.deliveries == 0
    assert profile.market.multipliers
