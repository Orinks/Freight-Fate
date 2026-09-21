"""The endpoint matcher reads an object's own identity, and the re-sweep merge
keeps what is good, replaces what is not, and labels what it cannot replace."""

import importlib.util
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _load(name: str):
    pytest.importorskip("osmium")
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool():
    return _load("build_facility_endpoints")


# Every one of these was a sourced endpoint before 2026-09-17.
@pytest.mark.parametrize(
    ("name", "tags"),
    [
        ("Elm Street Substation", {"power": "substation", "substation": "distribution"}),
        ("UP Coast Subdivision", {"railway": "rail", "usage": "freight"}),
        ("Tower 12", {"power": "tower", "material": "steel"}),
        ("Aberdeen Regional Airport Terminal", {"aeroway": "terminal", "building": "yes"}),
        ("Steele Street", {"highway": "residential"}),
        ("First Assembly of God", {"amenity": "place_of_worship", "building": "yes"}),
        ("Greyhound Terminal", {"highway": "bus_stop", "public_transport": "platform"}),
        ("Costco Food Court", {"amenity": "fast_food"}),
        ("The UPS Store", {"shop": "copyshop", "brand": "The UPS Store"}),
        ("Miller Works Apartments", {"building": "apartments", "landuse": "residential"}),
    ],
)
def test_matcher_refuses_what_the_substring_matcher_took(tool, name, tags):
    assert tool.classify({"name": name, **tags}, name) == (set(), 0, "")


def test_matcher_reads_whole_words_not_substrings(tool):
    site = {"landuse": "industrial"}
    steel, _, _ = tool.classify({"name": "Gerdau Steel", **site}, "Gerdau Steel")
    steele, _, _ = tool.classify({"name": "Steele Inc", **site}, "Steele Inc")
    assert "steel_industrial" in steel
    assert "steel_industrial" not in steele

    port, _, _ = tool.classify({"name": "Port of Tampa", **site}, "Port of Tampa")
    transport, _, _ = tool.classify(
        {"name": "Acme Transport Sports Co", **site}, "Acme Transport Sports Co"
    )
    assert {"port", "port_terminal"} <= port
    assert not {"port", "port_terminal"} & transport


def test_matcher_ranks_tag_and_name_above_either_above_assumed(tool):
    both = tool.candidate_from_tags(
        {"name": "Lakefront Distribution Warehouse", "building": "warehouse"}, 0, 0, "way/1"
    )
    tag_only = tool.candidate_from_tags({"name": "Pactiv", "building": "warehouse"}, 0, 0, "way/2")
    assumed = tool.candidate_from_tags(
        {"name": "Hub City Inc", "landuse": "industrial"}, 0, 0, "way/3"
    )
    assert both.match_for("cross_dock").tier == 3
    assert tag_only.match_for("cross_dock").tier == 2
    assert assumed.match_for("cross_dock").tier == 1
    assert assumed.match_for("cross_dock").kind == "assumed"
    assert both.match_for("cross_dock").kind == "read"
    # The assumed tier never reaches a type that names a trade.
    assert assumed.match_for("cold_storage") is None
    assert assumed.match_for("steel_industrial") is None


def test_matcher_keeps_the_rail_and_port_exceptions(tool):
    yard = tool.candidate_from_tags({"name": "Corwith Yard", "railway": "yard"}, 0, 0, "node/1")
    strip = tool.candidate_from_tags({"name": "BNSF Railway", "landuse": "railway"}, 0, 0, "way/2")
    amtrak = tool.candidate_from_tags(
        {"name": "Amtrak Coach Yard", "railway": "yard"}, 0, 0, "node/3"
    )
    marina = tool.candidate_from_tags(
        {"name": "Embarcadero Marina", "landuse": "harbour"}, 0, 0, "way/4"
    )
    port = tool.candidate_from_tags(
        {"name": "Tenth Avenue Terminal", "landuse": "industrial", "industrial": "port"},
        0,
        0,
        "way/5",
    )
    assert "intermodal_ramp" in yard.roles
    assert "cross_dock" not in yard.roles
    assert strip is None
    assert amtrak is None
    assert marina is None
    assert "port_terminal" in port.roles


def test_matcher_reads_the_four_families_that_had_no_rule(tool):
    # Grain elevators, quarries, construction materials and lumber/paper had
    # no rule at all until 2026-09-20: all 419 of their rows were fallbacks.
    for name, tags, role in [
        ("Farmers Cooperative Elevator", {"man_made": "silo"}, "farm_elevator"),
        ("Cargill Grain Terminal", {"landuse": "industrial"}, "farm_elevator"),
        ("Vulcan Materials Quarry", {"landuse": "quarry"}, "mine_quarry"),
        (
            "Ready Mix Concrete Co",
            {"industrial": "concrete_plant"},
            "construction_materials_yard",
        ),
        ("Martin Marietta Sand and Gravel", {"landuse": "quarry"}, "construction_materials_yard"),
        ("Pine Ridge Sawmill", {"craft": "sawmill"}, "lumber_paper"),
        ("Georgia-Pacific Paper Mill", {"man_made": "works"}, "lumber_paper"),
    ]:
        roles, _, _ = tool.classify({"name": name, **tags}, name)
        assert role in roles, (name, roles)
    for name, tags, role in [
        # A silo is a structure every farmyard has, so the tag alone is not a
        # grain elevator; "elevator" alone is a lift company; "pit" a barbecue
        # and "paper" a stationer.
        ("Hillside Farm", {"man_made": "silo"}, "farm_elevator"),
        ("Otis Elevator Company", {"building": "warehouse"}, "farm_elevator"),
        ("The Pit BBQ", {"landuse": "industrial"}, "mine_quarry"),
        ("The Paper Store", {"building": "warehouse"}, "lumber_paper"),
    ]:
        roles, _, _ = tool.classify({"name": name, **tags}, name)
        assert role not in roles, (name, roles)
    # Each family's site tag serves that family alone.
    silo, _, _ = tool.classify(
        {"name": "Farmers Cooperative Elevator", "man_made": "silo"},
        "Farmers Cooperative Elevator",
    )
    quarry, _, _ = tool.classify(
        {"name": "Vulcan Materials Quarry", "landuse": "quarry"}, "Vulcan Materials Quarry"
    )
    assert not silo & {"cross_dock", "dry_warehouse", "company_yard"}
    assert not quarry & {"dry_warehouse", "manufacturing_plant"}


def test_matcher_vetoes_utilities_and_converted_buildings(tool):
    for name, tags in [
        ("City Water Treatment Plant", {"man_made": "works", "landuse": "industrial"}),
        ("Central Heating Plant", {"man_made": "works"}),
        ("The Warehouse Lofts", {"building": "warehouse"}),
        ("Former Michigan Seat Co.", {"landuse": "industrial"}),
        ("Lincoln Truck & Auto Parts", {"landuse": "industrial", "industrial": "scrap_yard"}),
    ]:
        roles, _, _ = tool.classify({"name": name, **tags}, name)
        assert not roles & {"manufacturing_plant", "dry_warehouse", "automotive_plant"}, name
    # A civic name needs the tag AND the name to agree.
    kept, _, _ = tool.classify(
        {"name": "County Food Bank Warehouse", "building": "warehouse"},
        "County Food Bank Warehouse",
    )
    dropped, _, _ = tool.classify(
        {"name": "County Fleet Garage", "building": "warehouse"}, "County Fleet Garage"
    )
    assert "warehouse" in kept
    assert not dropped


def test_border_screen_judges_from_the_city(tool):
    # A border running east-west at latitude 31.334, city north of it.
    border = [(31.334, -109.7, 31.334, -109.4)]
    city = (31.3445, -109.5453)
    assert tool.crosses_border(city, (31.3324, -109.5824), border)
    assert not tool.crosses_border(city, (31.3600, -109.5600), border)


OSM_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="fixture">
  <node id="1" lat="41.000" lon="-87.000" />
  <node id="2" lat="41.000" lon="-86.999" />
  <node id="3" lat="41.001" lon="-86.999" />
  <node id="4" lat="41.010" lon="-87.000" />
  <node id="5" lat="41.010" lon="-86.999" />
  <node id="6" lat="41.011" lon="-86.999" />
  <node id="7" lat="41.020" lon="-87.000" />
  <node id="8" lat="41.020" lon="-86.999" />
  <node id="9" lat="41.021" lon="-86.999" />
  <node id="20" lat="41.030" lon="-87.000">
    <tag k="name" v="Fixture Substation" />
    <tag k="power" v="substation" />
    <tag k="substation" v="distribution" />
  </node>
  <node id="21" lat="41.031" lon="-87.000">
    <tag k="name" v="Fixture Subdivision" />
    <tag k="railway" v="rail" />
  </node>
  <way id="10">
    <nd ref="1" /><nd ref="2" /><nd ref="3" />
    <tag k="name" v="Good Freight Lines" />
    <tag k="building" v="warehouse" />
  </way>
  <way id="11">
    <nd ref="4" /><nd ref="5" /><nd ref="6" />
    <tag k="name" v="Fixture Cold Storage Warehouse" />
    <tag k="building" v="warehouse" />
  </way>
  <way id="12">
    <nd ref="7" /><nd ref="8" /><nd ref="9" />
    <tag k="name" v="Lakefront Distribution Warehouse" />
    <tag k="building" v="warehouse" />
  </way>
</osm>
"""


def _sourced(tool, target, name, ref, lat, lon):
    candidate = tool.Candidate(("x",), name, lat, lon, 1, ref, "old substring match")
    record = tool.sourced_record(target, candidate, "2026-06-27")
    for key in ("match_kind", "endpoint_screen"):
        record.pop(key)
    return record


def test_resweep_keeps_passing_replaces_failing_and_labels_the_rest(tool, tmp_path, monkeypatch):
    osm_path = tmp_path / "fixture.osm"
    osm_path.write_text(OSM_FIXTURE, encoding="utf-8")

    def target(kind: str) -> object:
        return tool.FacilityTarget(
            facility_id=f"fixture:{kind}",
            city="Fixture City",
            state="Illinois",
            name=f"Fixture {kind}",
            facility_type=kind,
            lat=41.0,
            lon=-87.0,
            source_note="fixture",
            city_lat=41.0,
            city_lon=-87.0,
        )

    kinds = ["company_yard", "cross_dock", "cold_storage", "intermodal_ramp", "parcel_hub", "port"]
    targets = [target(kind) for kind in kinds]
    by_kind = dict(zip(kinds, targets, strict=True))
    estimated = tool.fallback_record(by_kind["port"], reason="estimated near city")
    estimated["estimated"] = True
    existing = {
        "version": 1,
        "generated": {"regeocode_far_pins": {"matched": 357}},
        "sources": [],
        "endpoints": {
            # Passes the screen: kept, and its object stays reserved.
            "fixture:company_yard": _sourced(
                tool, by_kind["company_yard"], "Good Freight Lines", "way/10", 41.0003, -86.9993
            ),
            # A substation: replaced by the one warehouse left.
            "fixture:cross_dock": _sourced(
                tool, by_kind["cross_dock"], "Fixture Substation", "node/20", 41.03, -87.0
            ),
            # A fallback the fixed matcher can fill, and must fill FIRST: the
            # cold store is the only candidate cold storage has.
            "fixture:cold_storage": tool.fallback_record(by_kind["cold_storage"], reason="none"),
            # Railway track with no yard in the extract: kept and labelled.
            "fixture:intermodal_ramp": _sourced(
                tool, by_kind["intermodal_ramp"], "Fixture Subdivision", "node/21", 41.031, -87.0
            ),
            "fixture:parcel_hub": tool.fallback_record(by_kind["parcel_hub"], reason="none"),
            "fixture:port": estimated,
        },
    }
    before = {key: dict(row) for key, row in existing["endpoints"].items()}

    class FakeWorld:
        def facility_by_id(self, facility_id):
            return type("Location", (), {"id": facility_id})()

    monkeypatch.setattr(tool, "collect_targets", lambda: targets)
    monkeypatch.setattr(tool, "get_world", lambda: FakeWorld())
    monkeypatch.setattr(tool, "state_extract_path", lambda _cache, _state: osm_path)

    payload = tool.build_facility_endpoints(
        tmp_path, states=("Illinois",), existing=existing, accessed="2026-09-17"
    )
    rows = payload["endpoints"]

    kept = rows["fixture:company_yard"]
    assert kept["endpoint_screen"] == "passed"
    assert {k: v for k, v in kept.items() if k != "endpoint_screen"} == before[
        "fixture:company_yard"
    ]

    replaced = rows["fixture:cross_dock"]
    assert replaced["endpoint_name"] == "Lakefront Distribution Warehouse"
    assert replaced["source_ref"] == "way/12"
    assert replaced["endpoint_screen"] == "passed"
    assert replaced["match_kind"] == "read"
    assert replaced["replaced"]["endpoint_name"] == "Fixture Substation"
    assert "power-grid" in replaced["replaced"]["reason"]
    assert replaced["source_note"] != before["fixture:cross_dock"]["source_note"]

    filled = rows["fixture:cold_storage"]
    assert filled["source_backed"]
    assert filled["endpoint_name"] == "Fixture Cold Storage Warehouse"
    assert "replaced" not in filled

    labelled = rows["fixture:intermodal_ramp"]
    assert labelled["endpoint_screen"] == "refused"
    assert "railway track" in labelled["endpoint_screen_reason"]
    assert {
        k: v for k, v in labelled.items() if k not in ("endpoint_screen", "endpoint_screen_reason")
    } == before["fixture:intermodal_ramp"]

    assert rows["fixture:parcel_hub"] == before["fixture:parcel_hub"]
    assert rows["fixture:port"] == before["fixture:port"]

    assert payload["generated"]["regeocode_far_pins"] == {"matched": 357}
    assert payload["generated"]["resweep"]["states"] == ["Illinois"]
    assert payload["coverage"]["screen"] == {
        "passed": 3,
        "refused": 1,
        "not_screened": 0,
        "trade_assumed": 0,
    }
    # No spoken field carries a raw reference.
    for row in rows.values():
        spoken = f"{row['facility_name']} {row['endpoint_name']} {row['approach_road']}".lower()
        assert "way/" not in spoken and "node/" not in spoken
