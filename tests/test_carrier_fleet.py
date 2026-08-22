"""Dispatch-assigned company tractors across the 30-level career."""

from freight_fate.models.business import LEASED_OWNER_OPERATOR
from freight_fate.models.career import LEVEL_XP
from freight_fate.models.carrier_fleet import (
    DEDICATED_TRUCK_LEVEL,
    FLEET_TIERS,
    SLIP_SEAT_POOL_SIZE,
    assigned_truck_key,
    assignment_reason_text,
    fleet_assignment_text,
    fleet_tier_for_level,
    slip_seat_pool,
    slip_seats,
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


# -- slip-seating: the tractor is picked for the load ------------------------------


def _job(distance_mi: float, weight_tons: float):
    from types import SimpleNamespace

    return SimpleNamespace(distance_mi=distance_mi, weight_tons=weight_tons)


def test_every_fleet_tier_offers_a_real_choice_of_equipment():
    """Dispatch can only match a load if the yard holds different trucks.

    The regional tier is where slip-seating actually bites, so it has to carry
    both cab types and all three driveline specs; the long-haul tiers up are
    sleepers by definition but still need light through heavy.
    """
    from freight_fate.models.trucks import CAB_DAY, CAB_SLEEPER, TRUCK_CATALOG

    regional = next(tier for tier in FLEET_TIERS if tier.key == "regional")
    cabs = {TRUCK_CATALOG[key].cab for key in regional.pool}
    assert cabs == {CAB_DAY, CAB_SLEEPER}
    for tier in FLEET_TIERS[1:]:
        specs = {TRUCK_CATALOG[key].spec for key in tier.pool}
        assert len(specs) >= 3, (tier.key, specs)
    # Long-haul and up is life-on-the-road work: no day cabs up there.
    for tier in FLEET_TIERS[2:]:
        assert all(TRUCK_CATALOG[key].cab == CAB_SLEEPER for key in tier.pool), tier.key


def test_a_junior_driver_draws_a_small_stable_set_of_spares():
    """The yard leaves the same few trucks free, so their wear is knowable.

    Each tractor keeps its own fuel, wear, and damage, and a driver who drew a
    brand new truck every load would never watch one age.
    """
    profile = _profile_at_level(6)
    pool = slip_seat_pool(profile)
    assert len(pool) == SLIP_SEAT_POOL_SIZE
    assert len(set(pool)) == len(pool)
    assert slip_seat_pool(_profile_at_level(6)) == pool  # stable across calls
    tier = fleet_tier_for_level(6)
    assert set(pool) <= set(tier.pool)
    # Two drivers at the same level do not get the same three trucks.
    others = {slip_seat_pool(_profile_at_level(6, name=f"Driver {n}")) for n in range(12)}
    assert len(others) > 1


def test_a_run_that_needs_a_bunk_never_goes_out_on_a_day_cab():
    """Hours of service decide this, not preference.

    Eleven hours of driving does not cover a nine hundred mile run, so the
    truck has to have a bed in it.
    """
    from freight_fate.models.trucks import CAB_SLEEPER, TRUCK_CATALOG

    long_run = _job(900.0, 12.0)
    for n in range(24):
        profile = _profile_at_level(6, name=f"Driver {n}")
        key = assigned_truck_key(profile, long_run)
        assert TRUCK_CATALOG[key].cab == CAB_SLEEPER, (n, key)


def test_a_heavy_load_gets_a_heavy_spec_tractor():
    from freight_fate.models.trucks import SPEC_HEAVY, TRUCK_CATALOG

    heavy = _job(140.0, 24.0)
    picks = set()
    for n in range(24):
        profile = _profile_at_level(6, name=f"Driver {n}")
        key = assigned_truck_key(profile, heavy)
        picks.add(TRUCK_CATALOG[key].spec)
    assert picks == {SPEC_HEAVY}


def test_a_light_local_turn_gets_a_day_cab():
    """A day's work is day-cab work; the yard keeps its sleepers for the lanes."""
    from freight_fate.models.trucks import CAB_DAY, TRUCK_CATALOG

    turn = _job(120.0, 8.0)
    day_cabs = 0
    for n in range(24):
        profile = _profile_at_level(6, name=f"Driver {n}")
        if TRUCK_CATALOG[assigned_truck_key(profile, turn)].cab == CAB_DAY:
            day_cabs += 1
    # Not every driver's three spares include a day cab, but most yards do.
    assert day_cabs >= 12, day_cabs


def test_the_same_load_from_the_same_yard_always_comes_with_the_same_truck():
    job = _job(700.0, 15.0)
    first = assigned_truck_key(_profile_at_level(6), job)
    assert assigned_truck_key(_profile_at_level(6), job) == first


def test_seniority_ends_slip_seating():
    """A senior driver has a seat of their own and comes back to it."""
    profile = _profile_at_level(DEDICATED_TRUCK_LEVEL)
    assert not slip_seats(profile)
    standing = assigned_truck_key(profile)
    for job in (_job(120.0, 8.0), _job(900.0, 24.0), _job(380.0, 14.0)):
        assert assigned_truck_key(profile, job) == standing
    assert slip_seats(_profile_at_level(DEDICATED_TRUCK_LEVEL - 1))


def test_new_hires_are_not_shuffled_around_the_yard():
    """Levels one to three are the trainer truck, every load, every driver."""
    for n in range(8):
        profile = _profile_at_level(2, name=f"Driver {n}")
        assert assigned_truck_key(profile, _job(900.0, 24.0)) == "rig"
        assert profile.take_slip_seat(_job(120.0, 8.0)) == "rig"


def test_taking_a_slip_seat_sticks_for_the_run():
    """The truck dispatch handed over is the truck the drive uses."""
    profile = _profile_at_level(6)
    key = profile.take_slip_seat(_job(900.0, 12.0))
    assert profile.active_truck_key() == key
    assert profile.truck_specs() == TRUCK_CATALOG[key].specs
    # A different load can bring a different truck, and that one sticks too.
    other = profile.take_slip_seat(_job(120.0, 24.0))
    assert profile.active_truck_key() == other


def test_a_stale_assignment_falls_back_instead_of_stranding_the_driver():
    """A promotion moves the pool on; the old key must not survive it.

    Saves written before slip-seating also carry a truck value from the old
    scheme, and it must not pin a driver to a truck their yard does not hold.
    """
    profile = _profile_at_level(6)
    profile.truck = "presidential_sleeper"  # not in any regional yard
    assert profile.active_truck_key() in fleet_tier_for_level(6).pool


def test_owner_operators_are_never_slip_seated():
    from freight_fate.models.business import LEASED_OWNER_OPERATOR

    profile = _profile_at_level(6)
    profile.business_status = LEASED_OWNER_OPERATOR
    profile.truck = "highline_sleeper"
    profile.owned_trucks = ["highline_sleeper"]
    assert profile.take_slip_seat(_job(900.0, 24.0)) == "highline_sleeper"
    assert profile.active_truck_key() == "highline_sleeper"


def test_the_assignment_reason_is_spoken_plainly():
    """The driver is told why they are in this truck, in driver words."""
    profile = _profile_at_level(6)
    long_run = _job(900.0, 12.0)
    text = assignment_reason_text(assigned_truck_key(profile, long_run), long_run)
    assert "bunk" in text
    lowered = text.lower()
    for marker in ("osm", "_", "spec=", "cab=", "key=", "none"):
        assert marker not in lowered
    heavy = _job(140.0, 24.0)
    assert "heavy" in assignment_reason_text(assigned_truck_key(profile, heavy), heavy)


def test_a_dedicated_driver_hears_why_the_yard_held_their_truck_back():
    """The one thing a held-back driver will ask, said where they will ask it.

    From level 9 a driver stops slip-seating and has one truck, so there is no
    draw to announce at dispatch -- and the note went silent entirely. That
    silence covered the case that most needs words: a driver whose standing
    has capped the yard below the tractor their level earns. Brandon, level
    11, drew a regional-tier yard mule every long haul and asked "what
    gives?". The explanation existed the whole time, on the standing screen,
    which you have to already suspect the answer to go and read.
    """
    from freight_fate.models.carrier_fleet import (
        DEDICATED_TRUCK_LEVEL,
        eligible_fleet_tier,
        equipment_held_back,
        equipment_hold_text,
        slip_seats,
    )

    profile = _profile_at_level(11)
    assert not slip_seats(profile), "level 11 is past slip-seating"
    assert DEDICATED_TRUCK_LEVEL < 11

    # Trust on the floor is what caps the yard's iron.
    profile.career.reputation = 0.0
    assert equipment_held_back(profile) is True

    spoken = equipment_hold_text(profile)
    assert spoken, "a held-back driver must be given a reason"
    # It names all three: what the level earned, why it is being withheld,
    # and the thing that gives it back.
    assert eligible_fleet_tier(profile).label in spoken
    assert "dispatch trust" in spoken
    assert "comes back to you" in spoken

    # A driver in good standing at the same level hears nothing -- there is
    # nothing to explain, and the note must not nag.
    fine = _profile_at_level(11)
    assert equipment_held_back(fine) is False
    assert equipment_hold_text(fine) == ""


def test_the_stats_screen_answers_what_is_holding_the_next_truck_back():
    """Brandon, 2026-08-22: "it still does not tell me whats holding me back
    from driving the next level truck".

    The hold was already explained -- at the dispatch hand-over, and at the
    level-up that arrived without a truck. Both are moments. A driver who
    wants to know where they stand goes to the career stats screen and asks,
    and that screen did not mention equipment at all, so the answer only ever
    reached a player who happened to be listening when it went by.
    """
    from freight_fate.models.carrier_fleet import (
        eligible_fleet_tier,
        equipment_status_lines,
        next_fleet_tier,
    )

    # Held back: what he is in, then why, then what gives it back.
    held = _profile_at_level(11)
    held.career.reputation = 0.0
    lines = equipment_status_lines(held)
    assert len(lines) == 2
    assert lines[0].startswith("Truck: ")
    assert eligible_fleet_tier(held).label in lines[1]
    assert "comes back to you" in lines[1]

    # In good standing there is nothing to explain, so the screen says what
    # the next tier costs instead of nagging about a hold that is not there.
    fine = _profile_at_level(11)
    lines = equipment_status_lines(fine)
    assert len(lines) == 1
    upcoming = next_fleet_tier(fine)
    assert f"Level {upcoming.min_level} earns the {upcoming.label}." in lines[0]

    # And at the top of the ladder there is no next tier to name.
    top = _profile_at_level(20)
    assert next_fleet_tier(top) is None
    assert "the carrier's best equipment" in equipment_status_lines(top)[0]
