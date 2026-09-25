import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAW_MARKERS = ("osm_id", "amenity=", "highway=", "operator=", "node/", "way/", "source_ref")


def in_town(_kind: str, _lat: float, _lon: float) -> bool:
    """The fixture town judge: every fixture street is in town. The real
    bake judges by the Census boundaries, a local download CI does not have."""
    return True


def _load_tool():
    pytest.importorskip("osmium")
    path = Path(__file__).resolve().parents[1] / "tools" / "build_facility_approaches.py"
    spec = importlib.util.spec_from_file_location("build_facility_approaches", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_facility_approach_data_covers_full_facility_set(world):
    data = json.loads(Path("data/facility_approaches.json").read_text(encoding="utf-8"))
    coverage = data["coverage"]

    assert coverage["facilities"] == 4271
    # Synced with facility_endpoints after far-pin regeocode (419 estimated)
    # and the 2026-09-17 endpoint re-sweep, which replaced 1,224 endpoints and
    # had every chain to one of them rebuilt toward the new endpoint.
    # The 2026-09-17 yard-road rule then gave 89 facilities the public roads
    # do not reach a chain over the facility's own private road (52 new chains,
    # 37 stale ones rebuilt).
    # 2026-09-20: the four families that had no matcher rule -- grain
    # elevators, quarries, construction materials yards, lumber and paper --
    # gained one, and the six sibling types the builder still skipped are in.
    # Chains 2,314 to 2,456. The public search also honours gates and ways
    # signed against trucks now; not one of the 2,314 existing chains needed a
    # truck-signed way, so nothing was demoted.
    assert coverage["source_backed_endpoints"] == 2874
    assert coverage["road_snapped"] == 2490
    assert coverage["turn_level"] == 2456
    assert coverage["nearest_road_fallback"] == 384
    # Sourced endpoints with no chain whose own OSM object is not a freight site
    # (a railway line, a substation, a shop): the 2026-09-17 endpoint screen.
    assert coverage["endpoint_screen_refused"] == 344
    # Chains that still lead to a replaced endpoint because no public-road
    # path reaches the new one, not even over its own private road; kept until
    # a chain replaces them, and labelled. 2026-09-24's national re-route
    # (street detail) found a path to Knoxville's new endpoint: 42 to 41.
    assert coverage["stale_chain_kept"] == 41
    assert coverage["representative_fallback"] == 1397
    assert coverage["gate_yard_dock_hints"] == 0

    # The 2026-07-14 regen keys records by current slug facility ids and
    # covers every facility the endpoint/local-approach sweeps know about;
    # facilities added by map growth since those sweeps are simply absent
    # until the next data expansion pass (see ROADMAP).
    facilities = {
        location.id for city in world.city_names() for location in world.cities[city].locations
    }
    resolved, missing = set(), []
    for facility_id in data["approaches"]:
        try:
            resolved.add(world.facility_by_id(facility_id).id)
        except KeyError:
            missing.append(facility_id)
    assert resolved <= facilities
    assert not missing, missing[:10]
    assert len(resolved) == coverage["facilities"]


def test_facility_approach_records_are_clean_and_honest(world):
    data = json.loads(Path("data/facility_approaches.json").read_text(encoding="utf-8"))

    for facility_id, record in data["approaches"].items():
        try:
            world.facility_by_id(facility_id)
        except KeyError:
            continue  # facility retired by map growth; record is inert
        approach = world.facility_source_approach(record["city"], facility_id)
        assert approach is not None
        spoken = " ".join(
            [record["facility_name"], record["endpoint_name"], record["approach_road"]]
            + [segment["road"] for segment in record["segments"]]
            + [segment["cue"] for segment in record["segments"]]
        ).lower()
        assert not any(marker in spoken for marker in RAW_MARKERS)
        assert not record["gate_hint"]
        assert not record["yard_hint"]
        assert not record["dock_hint"]
        if record["turn_level"]:
            assert record["road_snapped"]
            assert record["nearest_road_context"]
            assert record["source_type"] == "osm_local_road_graph"
            assert not record["fallback"]
            assert record["total_miles"] > 0
            assert len(record["segments"]) >= 1
        else:
            assert record["fallback"]
            assert record["fallback_reason"]
            assert record["source_type"] == "facility_approach_fallback"


def test_facility_route_keeps_existing_fallback_when_no_source_geometry(world):
    facility = world.facility_by_id("abilene:grocery_retail_dc:abilene-grocery-distribution-center")
    source_approach = world.facility_source_approach("Abilene", facility.name)
    fallback_approach = world.facility_approach("Abilene", facility.name)
    route = world.facility_approach_route("Abilene", facility.name)

    assert source_approach is not None
    assert source_approach.fallback
    assert fallback_approach is not None
    assert route.miles == pytest.approx(fallback_approach.approach_miles)
    assert route.highways == [fallback_approach.road]


def test_build_tool_routes_tiny_facility_fixture(tmp_path, monkeypatch):
    tool = _load_tool()
    osm_path = tmp_path / "facility.osm"
    osm_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="fixture">
  <node id="1" lat="41.0000" lon="-87.0000" />
  <node id="2" lat="41.0000" lon="-86.9950" />
  <node id="3" lat="41.0000" lon="-86.9900" />
  <way id="10">
    <nd ref="1" />
    <nd ref="2" />
    <tag k="highway" v="tertiary" />
    <tag k="name" v="Terminal Road" />
  </way>
  <way id="20">
    <nd ref="2" />
    <nd ref="3" />
    <tag k="highway" v="service" />
    <tag k="name" v="Warehouse Drive" />
  </way>
  <way id="40">
    <nd ref="3" />
    <nd ref="2" />
    <tag k="building" v="warehouse" />
    <tag k="name" v="Real Warehouse" />
  </way>
</osm>
""",
        encoding="utf-8",
    )
    target = tool.FacilityTarget(
        facility_id="fixture:warehouse",
        city="Fixture City",
        state="Illinois",
        facility_name="Fixture Warehouse",
        facility_type="warehouse",
        endpoint_name="Real Warehouse",
        lat=41.0000,
        lon=-86.9900,
        start_lat=41.0000,
        start_lon=-87.0000,
        endpoint_source_backed=True,
        endpoint_fallback=False,
        endpoint_source_note="fixture",
        local_approach_miles=0.8,
        local_approach_road="Terminal Road",
        endpoint_source_ref="way/40",
    )
    monkeypatch.setattr(tool, "collect_targets", lambda: [target])
    monkeypatch.setattr(tool, "MIN_PLAYABLE_ROUTE_MI", 0.1)
    local_geometry = tool._load_local_geometry_tool()
    monkeypatch.setattr(local_geometry, "state_extract_path", lambda _cache, _state: osm_path)
    monkeypatch.setattr(tool, "_load_local_geometry_tool", lambda: local_geometry)

    payload = tool.build_facility_approaches(
        tmp_path,
        states=("Illinois",),
        max_route_mi=2.0,
        town_judge=in_town,
    )
    record = payload["approaches"]["fixture:warehouse"]

    assert payload["coverage"]["road_snapped"] == 1
    assert record["turn_level"]
    assert record["approach_road"] == "Terminal Road"
    assert [segment["road"] for segment in record["segments"]] == [
        "Terminal Road",
        "Warehouse Drive",
    ]


def test_build_tool_says_what_an_unnamed_road_is(tmp_path, monkeypatch):
    """Agent drive 2026-09-01: "Turn left onto unnamed public road" into a
    cross-dock. The builders retired that wording on 2026-08-25 (a nameless
    way is spoken by its class), but the shipped facility file was baked
    before that. This pins the builder's side of the promise, so a re-run
    of the facility bake cannot bring the old wording back."""
    tool = _load_tool()
    osm_path = tmp_path / "facility.osm"
    osm_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="fixture">
  <node id="1" lat="41.0000" lon="-87.0000" />
  <node id="2" lat="41.0000" lon="-86.9950" />
  <node id="3" lat="41.0000" lon="-86.9900" />
  <node id="4" lat="41.0000" lon="-86.9850" />
  <way id="10">
    <nd ref="1" />
    <nd ref="2" />
    <tag k="highway" v="tertiary" />
    <tag k="name" v="Terminal Road" />
  </way>
  <way id="20">
    <nd ref="2" />
    <nd ref="3" />
    <tag k="highway" v="residential" />
  </way>
  <way id="30">
    <nd ref="3" />
    <nd ref="4" />
    <tag k="highway" v="service" />
  </way>
  <way id="40">
    <nd ref="3" />
    <nd ref="2" />
    <tag k="building" v="warehouse" />
    <tag k="name" v="Real Warehouse" />
  </way>
</osm>
""",
        encoding="utf-8",
    )
    target = tool.FacilityTarget(
        facility_id="fixture:cross_dock",
        city="Fixture City",
        state="Illinois",
        facility_name="Fixture Cross-Dock",
        facility_type="cross_dock",
        endpoint_name="Real Cross-Dock",
        lat=41.0000,
        lon=-86.9850,
        start_lat=41.0000,
        start_lon=-87.0000,
        endpoint_source_backed=True,
        endpoint_fallback=False,
        endpoint_source_note="fixture",
        local_approach_miles=0.8,
        local_approach_road="Terminal Road",
        endpoint_source_ref="way/40",
    )
    monkeypatch.setattr(tool, "collect_targets", lambda: [target])
    monkeypatch.setattr(tool, "MIN_PLAYABLE_ROUTE_MI", 0.1)
    local_geometry = tool._load_local_geometry_tool()
    monkeypatch.setattr(local_geometry, "state_extract_path", lambda _cache, _state: osm_path)
    monkeypatch.setattr(tool, "_load_local_geometry_tool", lambda: local_geometry)

    payload = tool.build_facility_approaches(
        tmp_path,
        states=("Illinois",),
        max_route_mi=2.0,
        town_judge=in_town,
    )
    record = payload["approaches"]["fixture:cross_dock"]

    assert record["turn_level"]
    assert [segment["road"] for segment in record["segments"]] == [
        "Terminal Road",
        "a side street",
        "a service road",
    ]
    spoken = " ".join(
        [record["approach_road"]]
        + [segment["road"] for segment in record["segments"]]
        + [segment["cue"] for segment in record["segments"]]
    )
    assert "unnamed public road" not in spoken
    assert "onto a service road" in spoken
    # The generic labels keep the 15 mph zone a nameless way gets; the named
    # street keeps its 25.
    assert [segment["speed_mph"] for segment in record["segments"]] == [25.0, 15.0, 15.0]


def test_endpoint_screen_reads_the_object_not_a_substring_of_its_tags():
    """2026-09-17: 2,212 of 2,779 "source-backed" endpoints turned out to be
    railway main lines, substations, shops, roads and churches, because the
    endpoint sweep substring-matches the whole tag dump. The approach builder
    only routes a street chain to an object that reads as a freight site."""
    _load_tool()
    from facility_endpoint_screen import screen_endpoint

    def accepted(facility_type, name, tags):
        return screen_endpoint(facility_type, name, tags)[0]

    # `substation=distribution` is how a substation became a cross-dock.
    assert not accepted(
        "cross_dock", "Veterans Substation", {"power": "substation", "substation": "distribution"}
    )
    assert not accepted(
        "intermodal_ramp", "UP Coast Subdivision", {"railway": "rail", "usage": "main"}
    )
    assert not accepted("dry_warehouse", "Redwood Highway", {"highway": "trunk"})
    assert not accepted("dry_warehouse", "Costco", {"building": "warehouse", "shop": "wholesale"})
    assert not accepted("cross_dock", "Gone", None)
    assert accepted("cold_storage", "Americold", {"building": "warehouse"})
    assert accepted("intermodal_ramp", "Oak Point Yard", {"railway": "yard"})
    # The three name-matched types must also state their trade.
    assert not accepted(
        "automotive_plant", "First Assembly of God", {"amenity": "place_of_worship"}
    )
    assert not accepted("steel_industrial", "General Mills", {"landuse": "industrial"})
    assert not accepted("steel_industrial", "Steele Street Storage", {"building": "industrial"})
    assert accepted(
        "steel_industrial",
        "Nucor Steel Birmingham",
        {"landuse": "industrial", "industrial": "steel_mill"},
    )
    assert accepted(
        "automotive_plant",
        "Flint Truck Assembly",
        {"landuse": "industrial", "product": "automobiles"},
    )
    assert accepted(
        "chemical_petroleum_terminal",
        "Houma Terminal",
        {"landuse": "industrial", "industrial": "petroleum_terminal"},
    )


def test_build_tool_refuses_a_chain_to_an_endpoint_that_is_not_a_freight_site(
    tmp_path, monkeypatch
):
    tool = _load_tool()
    osm_path = tmp_path / "facility.osm"
    osm_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="fixture">
  <node id="1" lat="41.0000" lon="-87.0000" />
  <node id="2" lat="41.0000" lon="-86.9950" />
  <node id="3" lat="41.0000" lon="-86.9900" />
  <way id="10">
    <nd ref="1" />
    <nd ref="2" />
    <tag k="highway" v="tertiary" />
    <tag k="name" v="Terminal Road" />
  </way>
  <way id="20">
    <nd ref="2" />
    <nd ref="3" />
    <tag k="highway" v="service" />
    <tag k="name" v="Warehouse Drive" />
  </way>
  <way id="40">
    <nd ref="3" />
    <nd ref="2" />
    <tag k="power" v="substation" />
    <tag k="substation" v="distribution" />
    <tag k="name" v="Fixture Substation" />
  </way>
</osm>
""",
        encoding="utf-8",
    )
    target = tool.FacilityTarget(
        facility_id="fixture:cross_dock",
        city="Fixture City",
        state="Illinois",
        facility_name="Fixture Cross-Dock",
        facility_type="cross_dock",
        endpoint_name="Fixture Substation",
        lat=41.0000,
        lon=-86.9900,
        start_lat=41.0000,
        start_lon=-87.0000,
        endpoint_source_backed=True,
        endpoint_fallback=False,
        endpoint_source_note="fixture",
        local_approach_miles=0.8,
        local_approach_road="Terminal Road",
        endpoint_source_ref="way/40",
    )
    monkeypatch.setattr(tool, "collect_targets", lambda: [target])
    monkeypatch.setattr(tool, "MIN_PLAYABLE_ROUTE_MI", 0.1)
    local_geometry = tool._load_local_geometry_tool()
    monkeypatch.setattr(local_geometry, "state_extract_path", lambda _cache, _state: osm_path)
    monkeypatch.setattr(tool, "_load_local_geometry_tool", lambda: local_geometry)

    screened = tool.build_facility_approaches(
        tmp_path, states=("Illinois",), max_route_mi=2.0, town_judge=in_town
    )
    record = screened["approaches"]["fixture:cross_dock"]
    assert not record["turn_level"]
    assert record["fallback_reason"].startswith(tool.SCREEN_REFUSAL_PREFIX)
    assert "power-grid" in record["fallback_reason"]
    assert screened["coverage"]["endpoint_screen_refused"] == 1

    # The screen is a switch, not an edit: off, the same endpoint routes.
    unscreened = tool.build_facility_approaches(
        tmp_path, states=("Illinois",), max_route_mi=2.0, endpoint_screen=False, town_judge=in_town
    )
    assert unscreened["approaches"]["fixture:cross_dock"]["turn_level"]

    # The endpoint row's own verdict counts too: the tag screen cannot see an
    # endpoint across the border, or one the matcher has stopped accepting.
    warehouse = osm_path.read_text(encoding="utf-8").replace(
        '<tag k="power" v="substation" />', '<tag k="building" v="warehouse" />'
    )
    osm_path.write_text(warehouse, encoding="utf-8")
    assert tool.build_facility_approaches(
        tmp_path, states=("Illinois",), max_route_mi=2.0, town_judge=in_town
    )["approaches"]["fixture:cross_dock"]["turn_level"]
    across = "The sourced endpoint lies across the national border from its city."
    monkeypatch.setattr(tool, "endpoint_row_refusals", lambda: {"fixture:cross_dock": across})
    labelled = tool.build_facility_approaches(
        tmp_path, states=("Illinois",), max_route_mi=2.0, town_judge=in_town
    )
    record = labelled["approaches"]["fixture:cross_dock"]
    assert not record["turn_level"]
    assert across in record["fallback_reason"]


def test_search_budget_follows_the_endpoint_being_routed_to():
    """The path search was sized from the facility's representative pin, a
    2.1-mile floor near the city centre, while routing to a sourced endpoint
    miles further out: 52 of 88 "no connected path" failures in California,
    New York and Texas had a path and ran out of budget."""
    import dataclasses

    tool = _load_tool()
    target = tool.FacilityTarget(
        facility_id="fixture:far",
        city="Fixture City",
        state="Illinois",
        facility_name="Fixture Warehouse",
        facility_type="warehouse",
        endpoint_name="Real Warehouse",
        lat=41.0000,
        lon=-86.9000,  # about 5.2 miles east of the city context
        start_lat=41.0000,
        start_lon=-87.0000,
        endpoint_source_backed=True,
        endpoint_fallback=False,
        endpoint_source_note="fixture",
        local_approach_miles=2.1,
        local_approach_road="Terminal Road",
    )
    assert 6.4 <= tool.routed_approach_miles(target) <= 6.6
    # Never below the representative figure a facility was searched at before.
    near = dataclasses.replace(target, lon=-86.9950, local_approach_miles=3.0)
    assert tool.routed_approach_miles(near) == 3.0


def test_long_chain_keeps_the_streets_at_the_facility_and_folds_junction_links():
    tool = _load_tool()
    local_geometry = tool._load_local_geometry_tool()
    # Twelve streets, city context first; the last one is the facility's own.
    edges = [(f"Street {i}", 0.2, None) for i in range(12)]
    kept = local_geometry.collapse_segments(edges)
    assert [segment["road"] for segment in kept] == [f"Street {i}" for i in range(4, 12)]
    assert kept[0]["cue"] == "Start on Street 4."

    # An unnamed slip lane is part of the turn, never a street of its own.
    link = local_geometry.road_label({"highway": "primary_link"})
    assert link == local_geometry.JUNCTION_LINK
    folded = local_geometry.collapse_segments(
        [("Main Street", 0.5, None), (link, 0.1, None), ("Redwood Highway (US 101)", 1.0, None)]
    )
    assert [(segment["road"], segment["miles"]) for segment in folded] == [
        ("Main Street", 0.6),
        ("Redwood Highway (US 101)", 1.0),
    ]
    # One street under several route refs is heard once, as its longest run.
    one_street = local_geometry.collapse_segments(
        [
            ("Pine Street", 0.3, None),
            ("Saint John Avenue (US 51 Bus)", 0.2, None),
            ("Saint John Avenue", 0.1, None),
            ("Saint John Avenue (TN 211)", 0.6, None),
            ("West Main Street", 0.4, None),
        ]
    )
    assert [(segment["road"], segment["miles"]) for segment in one_street] == [
        ("Pine Street", 0.3),
        ("Saint John Avenue (TN 211)", 0.9),
        ("West Main Street", 0.4),
    ]
    # A nameless stretch inside one street is a gap in its name tag when the
    # road runs straight through it, and a real detour when it turns.
    east = [(41.0, -87.0 + 0.005 * i) for i in range(4)]
    gap = [("Main Street", 0.26, None), ("a side street", 0.26, None), ("Main Street", 0.26, None)]
    assert [segment["road"] for segment in local_geometry.collapse_segments(gap, east)] == [
        "Main Street"
    ]
    dogleg = [east[0], east[1], (41.005, east[1][1]), (41.005, east[2][1])]
    assert [segment["road"] for segment in local_geometry.collapse_segments(gap, dogleg)] == [
        "Main Street",
        "a side street",
        "Main Street",
    ]
    # A town's main street classed `trunk` is a street; a motorway is not.
    assert local_geometry.road_label({"highway": "trunk", "name": "Main Street"}) == "Main Street"
    assert (
        local_geometry.road_label({"highway": "trunk", "motorroad": "yes", "ref": "US 101"}) == ""
    )
    assert local_geometry.road_label({"highway": "motorway", "ref": "I 5"}) == ""

    # A drive-through, a parking aisle, an emergency access and a busway are
    # `highway=service` and none of them is a road a combination can use. The
    # tester report this comes from: the Oshkosh approach turned off West
    # Murdock Avenue and said "Continue onto Starbucks Drive-Through" (OSM way
    # 849313280, `service=drive-through`, one lane wide).
    for service in ("drive-through", "drive_through", "parking_aisle", "bus"):
        assert (
            local_geometry.road_label(
                {"highway": "service", "service": service, "name": "Starbucks Drive-Through"}
            )
            == ""
        ), service
    # The service ways that ARE how a yard, a dock and a loading bay are
    # reached stay routable.
    assert local_geometry.road_label({"highway": "service"}) == local_geometry.UNNAMED_SERVICE
    for service in ("driveway", "alley", "yard"):
        assert (
            local_geometry.road_label({"highway": "service", "service": service})
            == local_geometry.UNNAMED_SERVICE
        ), service

    # And who upstream says may use it. A permit is a refusal: the Burlington
    # grocery chain ran two miles of a way named "Route 127 Bike Path" tagged
    # `access=permit`.
    for access in ("permit", "residents", "employees", "emergency", "private"):
        assert (
            local_geometry.road_label(
                {"highway": "service", "access": access, "name": "Route 127 Bike Path"}
            )
            == ""
        ), access
    # A truck bound for the site is the traffic these name.
    for access in ("customers", "delivery", "destination", "permissive"):
        assert (
            local_geometry.road_label({"highway": "service", "access": access, "name": "Dock Road"})
            == "Dock Road"
        ), access


def _approach_stub(facility_id, *, turn_level, reason="", source_backed=True, estimated=False):
    return {
        "facility_id": facility_id,
        "turn_level": turn_level,
        "road_snapped": turn_level,
        "fallback": not turn_level,
        "fallback_reason": reason,
        "estimated": estimated,
        "endpoint_source_backed": source_backed,
        "representative_fallback": not source_backed,
        "gate_hint": False,
        "yard_hint": False,
        "dock_hint": False,
    }


def test_merge_existing_keeps_chains_and_deferred_residuals_across_a_partial_batch():
    """A state batch used to rebuild the whole file, so every chain outside
    the batch became a fallback row. The merge keeps prior turn-level chains,
    leaves facilities the batch never attempted byte for byte (the 419
    estimated-near-city residuals from the far-pin regeocode included), and
    only refreshes fallback rows the batch really tried to route."""
    tool = _load_tool()
    residual_reason = (
        "Re-geocode within city bounds found no high-confidence OSM name+type match "
        "inside 6.4 mi; estimated near city pending better source evidence."
    )
    outside = "Source-backed endpoint is outside this bounded Midwest road-snap batch."
    no_path = (
        "No connected public-road path was found between the city context and sourced endpoint."
    )
    existing = {
        "version": 1,
        "generated": {
            "accessed": "2026-06-27",
            "states": ["Ohio", "Texas"],
            "regeocode_far_pins": {"estimated_near_city": 419, "matched": 357},
        },
        "sources": [{"state": "Ohio", "file": "old-ohio"}, {"state": "Texas", "file": "texas"}],
        "coverage": {},
        "approaches": {
            "tx:chain": _approach_stub("tx:chain", turn_level=True),
            "tx:residual": _approach_stub(
                "tx:residual",
                turn_level=False,
                reason=residual_reason,
                source_backed=False,
                estimated=True,
            ),
            "oh:chain": _approach_stub("oh:chain", turn_level=True),
            "oh:untried": _approach_stub("oh:untried", turn_level=False, reason=outside),
            "oh:new": _approach_stub("oh:new", turn_level=False, reason=outside),
            "oh:retired": _approach_stub("oh:retired", turn_level=False, reason=outside),
        },
    }
    fresh = {
        "version": 1,
        "generated": {
            "accessed": "2026-09-16",
            "family": "f",
            "source_policy": "s",
            "road_policy": "r",
            "gate_policy": "g",
            "max_route_mi": 18.0,
            "states": ["Ohio"],
        },
        "sources": [{"state": "Ohio", "file": "new-ohio"}],
        "coverage": {},
        "approaches": {
            # Texas is outside this batch: the whole-file path would demote
            # its chain and overwrite the residual's honest reason.
            "tx:chain": _approach_stub("tx:chain", turn_level=False, reason=outside),
            "tx:residual": _approach_stub(
                "tx:residual",
                turn_level=False,
                reason="Facility endpoint is representative fallback, so source-backed "
                "routing is not claimed.",
                source_backed=False,
            ),
            # Ohio was attempted: a chain that failed to re-route stays a
            # chain, a fallback that was tried takes the run's real outcome.
            "oh:chain": _approach_stub("oh:chain", turn_level=False, reason=no_path),
            "oh:untried": _approach_stub("oh:untried", turn_level=False, reason=outside),
            "oh:new": _approach_stub("oh:new", turn_level=True),
            "oh:added": _approach_stub("oh:added", turn_level=True),
        },
    }

    merged = tool.merge_existing(
        existing, fresh, {"oh:chain", "oh:new", "oh:added"}, accessed="2026-09-16"
    )
    rows = merged["approaches"]

    assert rows["tx:chain"] is existing["approaches"]["tx:chain"]
    assert rows["tx:residual"] is existing["approaches"]["tx:residual"]
    assert rows["tx:residual"]["fallback_reason"] == residual_reason
    assert rows["oh:chain"] is existing["approaches"]["oh:chain"]
    assert rows["oh:untried"] is existing["approaches"]["oh:untried"]
    assert rows["oh:new"]["turn_level"]
    assert rows["oh:added"]["turn_level"]
    assert "oh:retired" not in rows
    assert merged["coverage"]["turn_level"] == 4
    assert merged["coverage"]["facilities"] == 6

    generated = merged["generated"]
    assert generated["regeocode_far_pins"] == {"estimated_near_city": 419, "matched": 357}
    assert generated["accessed"] == "2026-06-27"
    assert generated["states"] == ["Ohio", "Texas"]
    assert generated["merge"] == {
        "accessed": "2026-09-16",
        "batch_states": ["Ohio"],
        "new_geometry": 1,
        "kept_turn_level": 2,
        "refreshed": 0,
        "kept": 2,
        "added": 1,
    }
    assert [source["file"] for source in merged["sources"]] == ["new-ohio", "texas"]


def test_write_guard_ignores_retired_facilities_but_catches_a_lost_chain():
    """The refuse-to-write guard compares chains over facilities both files
    know: a facility the world retired drops from the merge without reading
    as a regression, while a chain that turned into a fallback does."""
    tool = _load_tool()
    existing = {
        "approaches": {
            "a": _approach_stub("a", turn_level=True),
            "retired": _approach_stub("retired", turn_level=True),
            "b": _approach_stub("b", turn_level=False, reason="x"),
        }
    }
    healthy = {
        "approaches": {
            "a": _approach_stub("a", turn_level=True),
            "b": _approach_stub("b", turn_level=True),
        }
    }
    assert tool.shared_turn_level(existing, healthy) == (1, 2)

    demoted = {
        "approaches": {
            "a": _approach_stub("a", turn_level=False, reason="x"),
            "b": _approach_stub("b", turn_level=False, reason="x"),
        }
    }
    assert tool.shared_turn_level(existing, demoted) == (1, 0)


def test_merge_existing_refreshes_only_what_the_batch_attempted():
    tool = _load_tool()
    outside = "Source-backed endpoint is outside this bounded Midwest road-snap batch."
    no_path = (
        "No connected public-road path was found between the city context and sourced endpoint."
    )
    existing = {
        "generated": {"states": ["Ohio"]},
        "sources": [],
        "approaches": {
            "oh:tried": _approach_stub("oh:tried", turn_level=False, reason=outside),
            "oh:missing_extract": _approach_stub(
                "oh:missing_extract", turn_level=False, reason=outside
            ),
        },
    }
    fresh = {
        "version": 1,
        "generated": {
            "family": "f",
            "source_policy": "s",
            "road_policy": "r",
            "gate_policy": "g",
            "max_route_mi": 18.0,
            "states": ["Ohio", "Indiana"],
        },
        "sources": [],
        "approaches": {
            "oh:tried": _approach_stub("oh:tried", turn_level=False, reason=no_path),
            "oh:missing_extract": _approach_stub(
                "oh:missing_extract", turn_level=False, reason=no_path
            ),
        },
    }

    merged = tool.merge_existing(existing, fresh, {"oh:tried"})

    assert merged["approaches"]["oh:tried"]["fallback_reason"] == no_path
    assert merged["approaches"]["oh:missing_extract"]["fallback_reason"] == outside
    assert merged["generated"]["states"] == ["Indiana", "Ohio"]
    assert merged["generated"]["merge"]["refreshed"] == 1
    assert merged["generated"]["merge"]["kept"] == 1


def test_merge_rebuilds_a_chain_whose_endpoint_the_resweep_replaced():
    """A chain belongs to the endpoint it was routed to. The endpoint re-sweep
    swaps a railway line for a real warehouse; the chain must then follow.
    When the new endpoint cannot be reached the old streets stay (owner
    ruling: a chain is kept until one replaces it) and the row says so. A
    chain whose endpoint merely failed the screen, with no replacement, is
    left exactly as it was."""
    tool = _load_tool()

    def row(facility_id, *, turn_level, endpoint, note, reason=""):
        stub = _approach_stub(facility_id, turn_level=turn_level, reason=reason)
        return {**stub, "endpoint_name": endpoint, "source_note": note, "state": "Ohio"}

    existing = {
        "generated": {"states": ["Ohio"]},
        "sources": [],
        "approaches": {
            "oh:rebuilt": row("oh:rebuilt", turn_level=True, endpoint="UP Subdivision", note="old"),
            "oh:no_path": row("oh:no_path", turn_level=True, endpoint="Elm Substation", note="old"),
            "oh:refused": row("oh:refused", turn_level=True, endpoint="Bus Terminal", note="old"),
            "oh:good": row("oh:good", turn_level=True, endpoint="Acme Freight", note="same"),
            "oh:rail": row(
                "oh:rail", turn_level=False, endpoint="NS Main Line", note="old", reason="type"
            ),
        },
    }
    disconnected = tool.ROUTE_FAILURE_REASONS["disconnected"]
    refused = tool.SCREEN_REFUSAL_PREFIX + "railway track. A street chain to it is not claimed."
    fresh = {
        "version": 1,
        "generated": {
            "family": "f",
            "source_policy": "s",
            "road_policy": "r",
            "gate_policy": "g",
            "max_route_mi": 18.0,
            "states": ["Ohio"],
        },
        "sources": [],
        "approaches": {
            "oh:rebuilt": row(
                "oh:rebuilt", turn_level=True, endpoint="Lakefront Warehouse", note="resweep"
            ),
            "oh:no_path": row(
                "oh:no_path",
                turn_level=False,
                endpoint="Island Cold Storage",
                note="resweep",
                reason=disconnected,
            ),
            # Same endpoint as before, refused by the screen: nothing replaced it.
            "oh:refused": row(
                "oh:refused", turn_level=False, endpoint="Bus Terminal", note="old", reason=refused
            ),
            "oh:good": row(
                "oh:good", turn_level=False, endpoint="Acme Freight", note="same", reason="x"
            ),
            # A type the tool does not route, whose endpoint was replaced.
            "oh:rail": row(
                "oh:rail", turn_level=False, endpoint="Corwith Yard", note="resweep", reason="type"
            ),
        },
    }

    merged = tool.merge_existing(
        existing,
        fresh,
        {"oh:rebuilt", "oh:no_path", "oh:refused", "oh:good"},
        accessed="2026-09-17",
    )
    rows = merged["approaches"]

    assert rows["oh:rebuilt"] is fresh["approaches"]["oh:rebuilt"]
    kept = rows["oh:no_path"]
    assert kept["turn_level"]
    assert kept["endpoint_name"] == "Elm Substation"
    assert kept["stale_endpoint"] == {
        "leads_to": "Elm Substation",
        "endpoint_now": "Island Cold Storage",
        "rebuild_failed": disconnected,
        "accessed": "2026-09-17",
    }
    assert rows["oh:refused"] is existing["approaches"]["oh:refused"]
    assert rows["oh:good"] is existing["approaches"]["oh:good"]
    assert rows["oh:rail"]["endpoint_name"] == "Corwith Yard"
    assert merged["coverage"]["turn_level"] == 4
    assert merged["coverage"]["stale_chain_kept"] == 1
    assert merged["generated"]["merge"]["rebuilt_to_new_endpoint"] == 1
    assert merged["generated"]["merge"]["stale_chain_kept"] == 1
    assert tool.shared_turn_level(existing, merged) == (4, 4)
