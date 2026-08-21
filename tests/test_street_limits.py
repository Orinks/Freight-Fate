"""The statutory street-limit layer: law, cited, and never a guess in disguise.

The map cannot tell us what a facility's access street is posted at -- OSM
carries `maxspeed` on about 1 percent of service ways. The state vehicle code
can: it sets the limit that governs when no sign is present, which is exactly
the situation. These tests hold that layer to the provenance rule -- a number
the game speaks as law must name the section it came from, and a number
nobody could confirm must not reach the road at all.
"""

import json
from pathlib import Path

import pytest

from freight_fate.data.street_limits import (
    FALLBACK_MPH,
    MAX_PLAUSIBLE_MPH,
    MIN_PLAUSIBLE_MPH,
    StatutoryLimit,
    load_street_limits,
    parse_street_limits,
)

FACILITY_APPROACHES = Path("src/freight_fate/data/facility_approaches.json")


def _row(**overrides) -> StatutoryLimit:
    base = dict(
        state="Testland",
        business_mph=25.0,
        residence_mph=25.0,
        urban_mph=None,
        citation="Test Code Sec. 1",
        title="Speed limits in districts",
        url="https://example.gov/1",
        rule_type="absolute",
        signs_required=False,
        truck_note="",
        verified=True,
        notes="",
    )
    base.update(overrides)
    return StatutoryLimit(**base)


def test_the_facility_street_number_prefers_the_business_district():
    """A warehouse stands in a business district, so that figure governs --
    then a single urban-district figure, then residence as the last resort."""
    assert _row(business_mph=30.0, residence_mph=25.0).facility_street_mph == 30.0
    assert _row(business_mph=None, urban_mph=20.0, residence_mph=25.0).facility_street_mph == 20.0
    assert _row(business_mph=None, urban_mph=None, residence_mph=25.0).facility_street_mph == 25.0
    assert _row(business_mph=None, urban_mph=None, residence_mph=None).facility_street_mph is None


def test_an_uncovered_state_falls_back_and_says_so():
    table = load_street_limits()
    assert table.facility_street_mph("Nowhere") == FALLBACK_MPH
    assert table.is_assumed("Nowhere") is True
    assert table.facility_street_mph("") == FALLBACK_MPH


def test_a_verified_row_without_a_citation_is_refused():
    """The point of the layer is the citation. A row claiming to be law with
    nothing to check it against is worse than an honest blank."""
    raw = {"limits": {"Testland": {"business_mph": 25, "verified": True, "citation": ""}}}
    with pytest.raises(ValueError, match="verified with no citation"):
        parse_street_limits(raw)


def test_an_unverified_row_must_say_why():
    raw = {"limits": {"Testland": {"business_mph": 25, "verified": False, "notes": ""}}}
    with pytest.raises(ValueError, match="unverified without saying why"):
        parse_street_limits(raw)


def test_a_number_outside_the_street_band_is_refused():
    """No state's code puts an ordinary street at 70. A row that says so is a
    transcription error, and it must fail loudly rather than be driven."""
    raw = {
        "limits": {
            "Testland": {
                "business_mph": 70,
                "verified": True,
                "citation": "Test Code Sec. 1",
            }
        }
    }
    with pytest.raises(ValueError, match="outside the plausible street band"):
        parse_street_limits(raw)


def test_every_shipped_row_is_plausible_and_carries_its_source():
    table = load_street_limits()
    if len(table) == 0:
        pytest.skip("the statutory table has not been baked yet")
    for state in _shipped_states():
        row = table.get(state)
        assert row is not None
        for value in (row.business_mph, row.residence_mph, row.urban_mph):
            if value is not None:
                assert MIN_PLAUSIBLE_MPH <= value <= MAX_PLAUSIBLE_MPH, state
        if row.verified:
            assert row.citation, state
            assert row.url, state
            assert row.rule_type in ("absolute", "prima facie"), state
        else:
            assert row.notes, state


def _shipped_states() -> list[str]:
    raw = json.loads(Path("src/freight_fate/data/street_limits.json").read_text(encoding="utf-8"))
    return sorted(raw["limits"])


def test_the_table_covers_every_state_the_map_delivers_to():
    """A state on the map with no row is a facility approach still driving on
    the old blanket 25. The gap is allowed -- it just has to be visible."""
    table = load_street_limits()
    if len(table) == 0:
        pytest.skip("the statutory table has not been baked yet")
    approaches = json.loads(FACILITY_APPROACHES.read_text(encoding="utf-8"))["approaches"]
    on_the_map = {str(entry.get("state", "")).strip() for entry in approaches.values()}
    on_the_map.discard("")
    missing = sorted(state for state in on_the_map if state not in table)
    assert not missing, f"facility states with no statutory row: {missing}"


def test_the_meta_says_how_much_of_the_layer_is_actually_law():
    """A bake that mostly assumed has to say so loudly (CLAUDE.md). Here the
    ratio that matters is how many rows are verified law."""
    table = load_street_limits()
    if len(table) == 0:
        pytest.skip("the statutory table has not been baked yet")
    assert "verified" in table.meta
    assert "unverified" in table.meta
    assert table.meta["verified"] + table.meta["unverified"] == table.meta["states"]


def test_a_state_with_no_district_default_is_a_finding_not_a_gap():
    """Connecticut writes no district default at all: a limit exists there
    only where a traffic authority has established and signed a zone, which
    makes 55 the legally correct figure for an unposted street -- not a speed
    to drive a yard approach at. The row has to be able to say "checked,
    there is none" so it reads differently from a row nobody filled in."""
    raw = {
        "limits": {
            "Testland": {
                "business_mph": None,
                "residence_mph": None,
                "urban_mph": None,
                "no_district_default": True,
                "citation": "Test Code Sec. 1",
                "rule_type": "absolute",
                "verified": True,
            }
        }
    }
    table = parse_street_limits(raw)
    assert table.get("Testland").no_district_default is True
    # And it drives on the fallback rather than on the statutory ceiling.
    assert table.facility_street_mph("Testland") == FALLBACK_MPH
    assert table.is_assumed("Testland") is True


def test_an_empty_row_that_does_not_declare_itself_is_refused():
    raw = {"limits": {"Testland": {"verified": True, "citation": "Test Code Sec. 1"}}}
    with pytest.raises(ValueError, match="no_district_default"):
        parse_street_limits(raw)


def test_a_limit_that_only_applies_when_posted_is_not_used_for_an_unposted_street():
    """Pennsylvania writes a 35 mph urban district figure and then makes it
    ineffective without signs at both ends of the zone and every half mile.
    On the streets this table is for -- the ones with no sign at all -- that
    35 is not the law, so it must not be posted. The statute is real; its
    application to an unsigned street is not."""
    row = _row(business_mph=None, urban_mph=35.0, residence_mph=25.0, signs_required=True)
    assert row.facility_street_mph is None
    raw = {
        "limits": {
            "Testland": {
                "urban_mph": 35,
                "residence_mph": 25,
                "signs_required": True,
                "citation": "Test Code Sec. 1",
                "rule_type": "absolute",
                "verified": True,
            }
        }
    }
    table = parse_street_limits(raw)
    assert table.facility_street_mph("Testland") == FALLBACK_MPH
    assert table.is_assumed("Testland") is True


def test_an_unverified_row_is_not_driven_on():
    """A state nobody could confirm falls back, and every view of the table
    agrees that it did. These three answers drifted apart once already: the
    number accessor handed back an unconfirmed figure while is_assumed called
    the same state assumed."""
    raw = {
        "limits": {
            "Testland": {
                "business_mph": 30,
                "verified": False,
                "rule_type": "absolute",
                "notes": "official code not fetchable; read from a secondary source",
            }
        }
    }
    table = parse_street_limits(raw)
    assert table.statutory_mph("Testland") is None
    assert table.facility_street_mph("Testland") == FALLBACK_MPH
    assert table.is_assumed("Testland") is True
