import random

from freight_fate.models.career import XP_PREMIUM_MULT, XP_SPECIALTY_MULT, Career
from freight_fate.models.profile import Profile
from freight_fate.profile_integrity_invariants import invariant_data, rendered_invariants


def test_integrity_invariants_include_public_projection_labels():
    data = invariant_data()
    assert data["sourceSaveVersion"] >= 1
    assert data["cityLabels"]["new_york_ny_us"] == "New York, New York"
    assert data["truckLabels"]["rig"] == "standard rig"
    assert data["levelXp"][0] == 0
    assert rendered_invariants().endswith("\n")


def test_exported_xp_ceiling_bounds_every_honest_career():
    """The exported ceiling must sit at or above what record_delivery awards.

    The server rejects a cloud backup whose XP exceeds
    `deliveries * xpFlatPerDelivery + total_miles * xpPerMileMax`. If a
    balance pass raises the game's rates past the exported figures, that
    check starts convicting the drivers who played best -- which is exactly
    how a hardcoded 1.2 per mile came to sit below the on-time rate. Drive
    a spread of careers through the real award path and hold the line.
    """
    data = invariant_data()
    per_mile = data["xpPerMileMax"]
    flat = data["xpFlatPerDelivery"]
    rng = random.Random(7)

    for _ in range(2_000):
        career = Career()
        for _ in range(rng.randint(1, 40)):
            career.record_delivery(
                rng.uniform(1.0, 900.0),
                pay=0.0,
                on_time=rng.random() < 0.9,
                damage_pct=rng.choice([0.0, 0.5, 30.0]),
                cargo_class_mult=rng.choice([1.0, XP_PREMIUM_MULT, XP_SPECIALTY_MULT]),
            )
        ceiling = career.deliveries * flat + career.total_miles * per_mile
        assert career.xp <= ceiling, (
            f"{career.xp} XP over {career.total_miles} miles in "
            f"{career.deliveries} deliveries breaches the exported ceiling {ceiling}"
        )


def test_exported_starting_money_matches_a_fresh_career():
    """The money rule's floor is this figure; a new profile must equal it."""
    assert invariant_data()["startingMoney"] == Profile().money


def test_exported_condition_fields_match_a_real_record():
    """The export must describe the record the game actually writes.

    The server checks every truck_conditions record against this list and
    rejects a save carrying a key it does not know. The list used to come off
    the TruckCondition dataclass, which this line stopped using -- records are
    plain dicts, and they grew brake wear, engine wear and traction gear while
    the dataclass kept four fields. That gap would have failed every 1.9 save
    on the exact-field check the first time a 1.9 build reached the server.
    """
    profile = Profile()
    profile.provision_truck_condition("rig")
    written = sorted(profile.truck_conditions["rig"])

    assert invariant_data()["truckConditionFields"] == written


def test_exported_profile_fields_include_the_created_on_marker():
    """The 1.9 cutover regen must teach the server allow-list ``created_line``.

    Every 1.9 upload carries the marker, so a validator built from an export
    without it would reject every honest backup on the schema check.
    """
    assert "created_line" in invariant_data()["profileFields"]


def test_exported_public_profile_fields_ride_the_allow_lists():
    """orinks.net's public career projection reads these from the payload.

    The employment status rides the top-level allow-list and self-paid
    endorsement courses ride the career allow-list; drop either and every
    honest 1.9 backup fails the exact-field check, taking the public
    profile's career statistics with it.
    """
    data = invariant_data()
    assert "business_status" in data["profileFields"]
    assert "purchased_endorsements" in data["careerFields"]


def test_exported_endorsements_match_what_the_career_actually_unlocks():
    """The site derives each driver's endorsements from this table.

    Hold it to the real unlock path: a career levelled to each exported
    threshold must hold exactly the endorsements the export promises at that
    level, or the public profile starts crediting training the carrier never
    sponsored (or hiding training it did).
    """
    from freight_fate.models.career import LEVEL_XP

    data = invariant_data()
    endorsements = data["endorsements"]
    for level in range(1, len(LEVEL_XP) + 1):
        career = Career(xp=float(LEVEL_XP[level - 1]))
        assert career.level == level
        expected = {key for key, entry in endorsements.items() if level >= entry["level"]}
        assert career.endorsements == expected

    # A self-paid course unlocks ahead of the sponsored level, which is why
    # purchased_endorsements has to reach the server at all.
    early = Career(xp=0.0, purchased_endorsements=["heavy_haul"])
    assert "heavy_haul" in early.endorsements


def test_exported_fleet_tiers_match_the_carrier_fleet_bands():
    """The site names a company driver's fleet tier from these bands."""
    from freight_fate.models.carrier_fleet import fleet_tier_for_level

    tiers = invariant_data()["fleetTiers"]
    assert tiers[0]["minLevel"] == 1  # every level maps to a band
    assert [t["minLevel"] for t in tiers] == sorted(t["minLevel"] for t in tiers)
    for level in range(1, 31):
        expected = fleet_tier_for_level(level).label
        banded = [t["label"] for t in tiers if level >= t["minLevel"]][-1]
        assert banded == expected
