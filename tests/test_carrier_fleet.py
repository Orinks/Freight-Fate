"""Dispatch-assigned company tractors across the 30-level career."""

from freight_fate.models.business import LEASED_OWNER_OPERATOR
from freight_fate.models.career import LEVEL_XP
from freight_fate.models.carrier_fleet import (
    FLEET_TIERS,
    assigned_truck_key,
    fleet_assignment_text,
    fleet_tier_for_level,
)
from freight_fate.models.profile import Profile
from freight_fate.models.trucks import TRUCK_CATALOG


def _profile_at_level(level: int, name: str = "Fleet Driver") -> Profile:
    profile = Profile(name=name)
    profile.career.xp = LEVEL_XP[level - 1]
    assert profile.career.level == level
    return profile


def test_new_hires_run_the_standard_starter_rig():
    profile = _profile_at_level(1)
    assert assigned_truck_key(profile) == "rig"
    assert profile.active_truck_key() == "rig"


def test_fleet_tiers_cover_the_whole_company_ladder_in_order():
    assert FLEET_TIERS[0].min_level == 1
    levels = [tier.min_level for tier in FLEET_TIERS]
    assert levels == sorted(levels)
    assert len(levels) == len(set(levels))
    # Every pool references real catalog trucks the simulation can build.
    for tier in FLEET_TIERS:
        assert tier.pool
        for key in tier.pool:
            assert key in TRUCK_CATALOG


def test_tier_upgrades_land_at_the_documented_levels():
    assert fleet_tier_for_level(1).key == fleet_tier_for_level(3).key
    boundaries = [tier.min_level for tier in FLEET_TIERS[1:]]
    assert boundaries == [4, 9, 13, 17]
    for boundary in boundaries:
        below = fleet_tier_for_level(boundary - 1)
        at = fleet_tier_for_level(boundary)
        assert below.key != at.key


def test_assignment_is_deterministic_and_varies_by_driver():
    a1 = assigned_truck_key(_profile_at_level(9, name="Driver A"))
    a2 = assigned_truck_key(_profile_at_level(9, name="Driver A"))
    assert a1 == a2
    tier = fleet_tier_for_level(9)
    assert a1 in tier.pool
    # Across many driver names dispatch hands out more than one model.
    picks = {assigned_truck_key(_profile_at_level(9, name=f"Driver {n}")) for n in range(12)}
    assert len(picks) > 1


def test_fleet_tanks_never_shrink_on_promotion():
    keys = ["rig"]
    for tier in FLEET_TIERS:
        keys.extend(tier.pool)
    previous_min = 0.0
    for tier in FLEET_TIERS:
        tanks = [TRUCK_CATALOG[key].specs.fuel_tank_gal for key in tier.pool]
        assert min(tanks) >= previous_min
        previous_min = min(tanks)


def test_owner_operators_keep_their_own_tractor():
    profile = _profile_at_level(18)
    profile.business_status = LEASED_OWNER_OPERATOR
    profile.truck = "highline_sleeper"
    profile.owned_trucks = ["highline_sleeper"]
    assert profile.active_truck_key() == "highline_sleeper"


def test_company_driver_specs_follow_the_assigned_tractor():
    profile = _profile_at_level(13)
    key = assigned_truck_key(profile)
    assert profile.active_truck_key() == key
    assert profile.truck_specs() == TRUCK_CATALOG[key].specs


def test_assignment_text_is_spoken_plainly():
    profile = _profile_at_level(9)
    text = fleet_assignment_text(profile)
    assert TRUCK_CATALOG[assigned_truck_key(profile)].label in text
    lowered = text.lower()
    for marker in ("osm", "_", "tier_", "key="):
        assert marker not in lowered
