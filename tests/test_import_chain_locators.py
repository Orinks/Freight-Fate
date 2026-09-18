"""Tests for tools/import_chain_locators.py and tools/chain_store_table.py.

Everything here is synthetic and offline: no OSM cache, no real world tree.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


table = _load("chain_store_table")
tool = _load("import_chain_locators")

# One leg along a parallel, mile 0 at lon -100, about 55 miles per degree.
_LEG_POINTS = [
    {"lat": 40.0, "lon": -100.0, "at_mi": 0.0},
    {"lat": 40.0, "lon": -98.0, "at_mi": 106.0},
]
_OSM_NOTE = "OpenStreetMap/Overpass development-time corridor amenity query, accessed 2026-06-21."


def _store(brand: str, lat: float, lon: float, **fields) -> table.Store:
    defaults = {
        "town": "Rolla",
        "town_kind": "town read from the mapped site's address",
        "serves_trucks": True,
    }
    return table.Store(
        key=f"{brand}@{lat:.4f},{lon:.4f}",
        brand=brand,
        lat=lat,
        lon=lon,
        extract="missouri",
        dated="2026-06-22",
        points=[(lat, lon)],
        **{**defaults, **fields},
    )


def _stop(name: str, at_mi: float, **fields) -> dict:
    stop = {"name": name, "type": "service_plaza", "at_mi": at_mi, "source": _OSM_NOTE}
    stop.update(fields)
    return stop


def _world(*stops: dict) -> dict:
    leg = {
        "from": "here_zz_us",
        "to": "there_zz_us",
        "miles": 106.0,
        "stops": [copy.deepcopy(stop) for stop in stops],
        "corridor": {"route_points": _LEG_POINTS},
    }
    return {"legs": [leg]}


def test_only_the_chains_themselves_are_read_as_chain_stores():
    assert table.osm_brand({"brand": "Love's", "name": "Love's"}) == "loves"
    assert table.osm_brand({"name": "Flying J Travel Center"}) == "flyingj"
    assert table.osm_brand({"brand": "TA", "name": "TA Express"}) == "taexpress"
    assert table.osm_brand({"brand": "Shell", "name": "Pilot"}) == "pilot"
    for name in ("Petro Champ", "Petro-Card 24", "Pilot Thomas Logistics", "PetroStop"):
        assert table.osm_brand({"name": name}) is None, name
    assert table.osm_brand({"brand": "Love's Alternative Energy", "name": "CNG"}) is None


def test_a_town_is_made_fit_to_be_spoken_or_refused():
    assert table.clean_town("Ft. Pierce") == "Fort Pierce"
    assert table.clean_town("MCCAMMON") == "McCammon"
    assert table.clean_town("St. Joseph") == "St. Joseph"
    for junk in ("#367 Le Roy, IL", "Rocker #2", "Toquerville/St. George, UT", "146", ""):
        assert table.clean_town(junk) == "", junk


def test_a_store_page_in_another_state_names_nothing():
    link = "https://locations.pilotflyingj.com/us/nd/beach/i-94-nd-16"
    assert table._town_from_link(link, {}, {"nd"}) == "Beach"
    assert table._town_from_link(link, {}, {"va"}) == ""
    ta = "https://www.ta-petro.com/location/md/ta-elkton"
    assert table._town_from_link(ta, {}, {"md"}) == "Elkton"
    assert (
        table._town_from_link(link.replace("beach", "mccammon"), {"mccammon": "McCammon"}, {"nd"})
        == "McCammon"
    )


def test_bare_names_and_mile_marker_points_are_told_apart():
    for name in (
        "Love's Travel Stop",
        "Flying J Truck Lanes",
        "Pilot Flying J",
        "TA Express",
        "One9",
    ):
        assert tool.is_bare(name), name
    for name in (
        "Love's Travel Stop Rolla",
        "Pilot Dealer Sacramento",
        "Pilot Express",
        "TA Tonopah",
    ):
        assert not tool.is_bare(name), name
    assert tool.record_brand("PetroStop") is None
    assert tool.has_site_coordinates({"lat": 40.0001, "lon": -99.0000001})
    assert not tool.has_site_coordinates({"lat": 42.27193572605037, "lon": -79.72539661148352})
    assert not tool.has_site_coordinates({})


def test_a_bare_record_at_a_store_is_named_typed_and_sourced_once():
    world = _world(_stop("Love's Travel Stop", 53.0, lat=40.0101, lon=-99.0))
    stores = [_store("loves", 40.01, -99.0, number="253")]
    report = tool.apply(world, stores)
    stop = world["legs"][0]["stops"][0]
    assert stop["name"] == "Love's Travel Stop Rolla"
    assert stop["type"] == "travel_center"
    assert stop["source"].startswith(_OSM_NOTE)
    assert "Love's store 253 at Rolla" in stop["source"]
    assert "matched by coordinate" in stop["source"]
    assert "253" not in stop["name"], "no store numbers in a spoken name"
    assert report["per_brand"]["loves"]["bare named"] == 1
    again = copy.deepcopy(world)
    tool.apply(again, [_store("loves", 40.01, -99.0, number="253")])
    assert again == world, "a second run changes nothing"


def test_a_record_with_coordinates_and_no_store_beside_it_is_left_alone():
    world = _world(_stop("Love's Travel Stop", 53.0, lat=40.05, lon=-99.0))
    before = copy.deepcopy(world)
    tool.apply(world, [_store("loves", 40.01, -99.0)])  # 2.8 miles away
    assert world == before


def test_a_store_that_does_not_say_it_serves_trucks_names_nothing():
    world = _world(_stop("Love's", 53.0, lat=40.01, lon=-99.0, type="fuel_station"))
    before = copy.deepcopy(world)
    tool.apply(world, [_store("loves", 40.01, -99.0, serves_trucks=False)])
    assert world == before


def test_the_bare_twin_of_a_named_record_is_deleted():
    named = _stop(
        "Flying J Travel Center Corfu",
        54.5,
        type="travel_center",
        source="Pilot Flying J official locator lists Flying J Travel Center store 693 in Corfu, NY",
    )
    bare = _stop("Flying J Travel Center", 53.0, lat=40.0101, lon=-99.0)
    world = _world(bare, named)
    report = tool.apply(world, [_store("flyingj", 40.01, -99.0, town="Pembroke")])
    stops = world["legs"][0]["stops"]
    assert [stop["name"] for stop in stops] == ["Flying J Travel Center Corfu"]
    assert (stops[0]["lat"], stops[0]["lon"]) == (40.01, -99.0)
    assert "Store coordinates read from OpenStreetMap" in stops[0]["source"]
    assert len(report["deletions"]) == 1


def test_a_store_number_in_the_source_refuses_the_wrong_store():
    named = _stop(
        "Love's Travel Stop Fort Pierce",
        53.0,
        type="travel_center",
        source="Love's official store feed lists store 415 in Fort Pierce, FL on I-95",
    )
    world = _world(named)
    before = copy.deepcopy(world)
    report = tool.apply(world, [_store("loves", 40.02, -99.0, town="Fort Pierce", number="467")])
    assert world == before
    assert any("another store number" in line for line in report["outcome"])


def test_two_stores_in_reach_refuse_a_record_without_coordinates():
    world = _world(_stop("Pilot Travel Center", 53.0))
    before = copy.deepcopy(world)
    tool.apply(world, [_store("pilot", 40.01, -99.0), _store("pilot", 40.0, -98.97)])
    assert world == before


def test_a_named_record_far_from_its_mile_marker_is_found_by_its_name():
    named = _stop("Love's Travel Stop Rolla", 75.0, type="travel_center", source="Curated.")
    bare = _stop("Love's Travel Stop", 53.0, lat=40.0101, lon=-99.0)
    world = _world(bare, named)
    tool.apply(world, [_store("loves", 40.01, -99.0)])
    (stop,) = world["legs"][0]["stops"]
    assert stop["name"] == "Love's Travel Stop Rolla"
    assert stop["at_mi"] == 53.0, "the kept record takes the well-placed twin's mile marker"
    assert "Mile marker moved from 75 to 53: DERIVED" in stop["source"]


def test_a_bare_record_is_not_given_a_name_already_on_its_leg():
    other = _stop("Love's Travel Stop Rolla", 20.0, type="travel_center", source="Curated.")
    bare = _stop("Love's Travel Stop", 53.0, lat=40.0101, lon=-99.0)
    world = _world(other, bare)
    # Two stores called Rolla: the named record finds neither by name.
    stores = [_store("loves", 40.01, -99.0), _store("loves", 40.0, -99.3)]
    tool.apply(world, stores)
    names = [stop["name"] for stop in world["legs"][0]["stops"]]
    assert names == ["Love's Travel Stop Rolla", "Love's Travel Stop"]
    assert world["legs"][0]["stops"][1]["type"] == "travel_center"
