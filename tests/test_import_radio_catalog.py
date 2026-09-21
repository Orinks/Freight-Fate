"""Tests for the imported radio tier: name cleaning, and the hand curation.

The build is only useful if running it twice gives the same catalog. A
rebuild that quietly undid a curator's judgement is how fifteen stations
went back to reading "Birmingham s Beautiful QEZ" out loud.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_importer():
    """Import tools/import_radio_catalog.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "import_radio_catalog", ROOT / "tools" / "import_radio_catalog.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


irc = _load_importer()

OVERRIDES_PATH = ROOT / "data" / "radio_imported_overrides.json"
CATALOG_PATH = ROOT / "data" / "radio_imported.json"


def _catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _overrides() -> dict:
    return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))


def test_a_stranded_s_is_restored_as_the_possessive_it_was():
    # The upstream directory stripped every apostrophe. Both tiers repair it:
    # the local tier read these out for a release before it did.
    assert irc.clean_local_name("Birmingham s Beautiful QEZ") == "Birmingham's Beautiful QEZ"
    assert irc.clean_web_name("Hampton s Jazz") == "Hampton's Jazz"
    assert irc.clean_terrestrial_name("Today s Southern Gospel Music") == (
        "Today's Southern Gospel Music"
    )


def test_a_lone_s_that_is_not_a_possessive_is_left_alone():
    # Nothing follows, so there is no word to own: "Kings of Leon s" stays.
    assert irc.restore_possessives("Kings of Leon s") == "Kings of Leon s"
    # One letter is not a word that can own anything.
    assert irc.restore_possessives("A s B") == "A s B"


def test_an_unclosed_bracket_is_a_note_that_got_away():
    assert irc.clean_local_name("NPR Syracuse University, NY (New") == "NPR Syracuse University, NY"
    assert irc.clean_terrestrial_name("KFLP All Agriculture (new link 2/2025") == (
        "KFLP All Agriculture"
    )
    # A closed bracket is part of the name and stays.
    assert irc.clean_local_name("The Eagle 105.7 (aka, KYTS)") == "The Eagle 105.7 (aka, KYTS)"


def test_hand_curation_wins_over_what_the_build_derived():
    overrides, dropped = irc.hand_curation(OVERRIDES_PATH)
    station = irc.apply_overrides(
        {"id": "rb-web-b4844481-c223-4fa0-9229-e0a19541c163", "name": "x", "format": "y"},
        overrides,
    )
    assert station["name"] == "Country104 (Star104)"
    assert station["format"] == "country"
    # The reason each entry exists is for the reader, not the catalog.
    assert "why" not in station


def test_every_hand_curated_station_says_why():
    doc = _overrides()
    for station_id, row in doc["overrides"].items():
        assert row.get("why"), f"{station_id} changes the catalog without saying why"
        assert len(row) > 1, f"{station_id} says why but changes nothing"
    for row in doc["dropped"]:
        assert row.get("why"), f"{row['id']} is dropped without saying why"


def test_hand_curation_lands_in_the_checked_in_catalog():
    # A stale entry is worse than none: it reads as curation that is in
    # force. The build fails on one; this is the same check on what shipped.
    doc = _overrides()
    stations = {station["id"]: station for station in _catalog()["stations"]}
    for station_id, row in doc["overrides"].items():
        assert station_id in stations, f"{station_id} is curated but not in the catalog"
        for field, value in row.items():
            if field == "why":
                continue
            assert stations[station_id][field] == value
    for row in doc["dropped"]:
        assert row["id"] not in stations, f"{row['id']} is dropped but in the catalog"


def test_no_station_name_reads_a_stranded_s_out_loud():
    # The whole point of the repair, checked against what actually shipped.
    stranded = [
        station["name"]
        for station in _catalog()["stations"]
        if irc.restore_possessives(station["name"]) != station["name"]
    ]
    assert not stranded


def test_the_catalog_counts_match_the_stations_in_it():
    catalog = _catalog()
    assert catalog["counts"]["stations"] == len(catalog["stations"])
