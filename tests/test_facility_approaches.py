import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAW_MARKERS = ("osm_id", "amenity=", "highway=", "operator=", "node/", "way/", "source_ref")


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
    data = json.loads(
        Path("src/freight_fate/data/facility_approaches.json").read_text(encoding="utf-8")
    )
    coverage = data["coverage"]

    assert coverage["facilities"] == 5037
    # Synced with facility_endpoints after far-pin regeocode (419 estimated).
    assert coverage["source_backed_endpoints"] == 2779
    assert coverage["road_snapped"] == 1579
    assert coverage["turn_level"] == 1415
    assert coverage["nearest_road_fallback"] == 1200
    assert coverage["representative_fallback"] == 2258
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
    data = json.loads(
        Path("src/freight_fate/data/facility_approaches.json").read_text(encoding="utf-8")
    )

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


def test_facility_route_prefers_turn_level_source_approach(world):
    from freight_fate.sim.trip import Trip, TripEvent, TripEventKind
    from freight_fate.sim.vehicle import TruckState
    from freight_fate.sim.weather import WeatherSystem
    from freight_fate.states.driving import _route_event_sound

    data = json.loads(
        Path("src/freight_fate/data/facility_approaches.json").read_text(encoding="utf-8")
    )
    facility_id, record = next(item for item in data["approaches"].items() if item[1]["turn_level"])
    facility = world.facility_by_id(facility_id)
    route = world.facility_approach_route(record["city"], facility.name)
    approach = world.facility_source_approach(record["city"], facility.name)

    assert approach is not None
    assert approach.turn_level
    assert route.miles == pytest.approx(approach.total_miles)
    assert route.highways == [segment.road for segment in approach.segments]
    trip = Trip(route, TruckState(), WeatherSystem())
    start_cue = next(cue for cue in trip.navigation_cues if cue.key == "local:start")
    assert start_cue.direction == "ahead"
    assert (
        _route_event_sound(
            TripEvent(TripEventKind.GPS_CUE, start_cue.near_text, {"cue": start_cue})
        )
        == "events/turn_ahead"
    )


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


def test_facility_approach_status_names_the_dock_not_the_town():
    # Owner playtest 2026-07-19: 14 miles of "toward Camp Verde" while
    # pulling out of Camp Verde for its own warehouse read as a wrong turn.
    from freight_fate.data.world import Leg
    from freight_fate.data.world_models import Route, StateMileage
    from freight_fate.sim import Trip, TruckState, WeatherSystem

    leg = Leg(
        "camp_verde_az_us",
        "camp_verde_az_us",
        14.0,
        "South Quarterhorse Lane",
        "flat",
        (),
        state_miles=(StateMileage("Arizona", 14.0),),
    )
    route = Route(["camp_verde_az_us", "camp_verde_az_us"], [leg])
    trip = Trip(
        route,
        TruckState(),
        WeatherSystem("desert_southwest", seed=1),
        seed=2,
        destination_label="dry warehouse Camp Verde Dry Warehouse",
    )
    status = trip.progress_summary()
    assert "toward dry warehouse Camp Verde Dry Warehouse" in status
    assert "toward Camp Verde," not in status
    assert "Destination dry warehouse Camp Verde Dry Warehouse ahead." in status


def test_long_synthetic_approach_steps_down_45_25_15(world):
    """Owner design 2026-07-24: a long local approach is an arterial before
    it is an access road -- 45 wide out, 25 for the last two miles, 15 at
    the gate. A blanket 25 for six-plus miles was a crawl no city posts."""
    from freight_fate.sim.trip import Trip
    from freight_fate.sim.vehicle import TruckState
    from freight_fate.sim.weather import WeatherSystem

    # Madison Cold Storage became estimated-near-city @2.1 mi after far-pin
    # regeocode; Kenosha Dry Warehouse still has a long synthetic approach.
    route = world.facility_approach_route("kenosha_wi_us", "Kenosha Dry Warehouse")
    assert route.miles > 3.0  # long synthetic approach (clamped to Josh's band)
    truck = TruckState()
    truck.transmission.automatic = True
    truck.start_engine()
    trip = Trip(route, truck, WeatherSystem("great_lakes", seed=1), seed=2)

    reasons = [(z.reason, z.limit_mph) for z in trip.zones]
    assert ("facility approach", 45.0) in reasons
    assert ("facility access road", 25.0) in reasons
    assert ("facility gate", 15.0) in reasons
    arterial = next(z for z in trip.zones if z.reason == "facility approach")
    access = next(z for z in trip.zones if z.reason == "facility access road")
    assert arterial.end_mi == access.start_mi  # steps down, never overlaps up
