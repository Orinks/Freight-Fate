"""Region taxonomy: derivation, coverage, and stored-equals-derived guard."""

from __future__ import annotations

import pytest

from freight_fate.data.regions import (
    REGION_LABELS,
    REGIONS,
    STATE_REGION,
    classify_region,
)
from freight_fate.data.world import MARKET_TAG_FACILITY_TYPES, REGION_MARKET_TAGS
from freight_fate.models.economy import REGION_FUEL_PRICE
from freight_fate.sim.trip import REGION_HAZARDS
from freight_fate.sim.weather import REGION_WEIGHTS


def test_stored_region_matches_derived(world):
    """Every city's baked region must equal classify_region for its coords.

    This is the guard that keeps a misclassification (such as Reno being tagged
    the Rockies) from ever recurring as the map grows.
    """
    mismatches = []
    for name, city in world.cities.items():
        derived = classify_region(city.state, city.lat, city.lon)
        if city.region != derived:
            mismatches.append(f"{name}: stored {city.region!r} != derived {derived!r}")
    assert not mismatches, "Stored regions out of sync with classifier:\n" + "\n".join(
        mismatches
    )


def test_every_stored_region_is_canonical(world):
    for name, city in world.cities.items():
        assert city.region in REGIONS, f"{name} has non-canonical region {city.region!r}"


def test_reno_is_great_basin_not_rockies(world):
    # The bug this work fixed: Reno is Great Basin / eastern Sierra, not Rockies.
    assert world.cities["Reno"].region == "great_basin"
    assert world.cities["Boise"].region == "great_basin"


@pytest.mark.parametrize("table_name,table", [
    ("REGION_WEIGHTS", REGION_WEIGHTS),
    ("REGION_HAZARDS", REGION_HAZARDS),
    ("REGION_FUEL_PRICE", REGION_FUEL_PRICE),
    ("REGION_MARKET_TAGS", REGION_MARKET_TAGS),
    ("REGION_LABELS", REGION_LABELS),
])
def test_every_region_covered_in_flavor_tables(table_name, table):
    missing = [region for region in REGIONS if region not in table]
    assert not missing, f"{table_name} is missing regions: {missing}"


def test_market_tags_are_valid(world):
    for region, tags in REGION_MARKET_TAGS.items():
        for tag in tags:
            assert tag in MARKET_TAG_FACILITY_TYPES, (
                f"{region} market tag {tag!r} has no facility-type mapping"
            )


def test_classifier_splits_multi_region_states():
    # Texas spans three regions by coordinate.
    assert classify_region("Texas", 29.76, -95.37) == "gulf_coast"      # Houston
    assert classify_region("Texas", 32.78, -96.80) == "southern_plains"  # Dallas
    assert classify_region("Texas", 31.76, -106.48) == "desert_southwest"  # El Paso
    # Nevada: northern Great Basin vs southern Mojave desert.
    assert classify_region("Nevada", 39.53, -119.81) == "great_basin"   # Reno
    assert classify_region("Nevada", 36.17, -115.14) == "desert_southwest"  # Las Vegas
    # Pennsylvania, New York, Tennessee splits.
    assert classify_region("Pennsylvania", 40.44, -80.00) == "appalachia"   # Pittsburgh
    assert classify_region("Pennsylvania", 39.95, -75.17) == "northeast"    # Philadelphia
    assert classify_region("New York", 42.89, -78.88) == "great_lakes"      # Buffalo
    assert classify_region("New York", 40.71, -74.01) == "northeast"        # New York
    assert classify_region("Tennessee", 35.96, -83.92) == "appalachia"      # Knoxville
    assert classify_region("Tennessee", 36.16, -86.78) == "mid_south"       # Nashville


def test_classifier_rejects_unmapped_state():
    with pytest.raises(ValueError):
        classify_region("Atlantis", 0.0, 0.0)


def test_single_region_states_are_canonical():
    for state, region in STATE_REGION.items():
        assert region in REGIONS, f"{state} maps to non-canonical region {region!r}"
