"""Re-enriching a rerouted leg: the geometry every builder locates it by.

Rerouting a leg drops every corridor layer keyed to the old polyline, and the
builders that put them back had all been locating the leg the same way --
``corridor.route_points``, one point roughly every 25 miles, threaded either
through a cached OSRM route or through straight chords. Off a chord that long
a way on the real road is simply too far away to snap, so the layer comes back
thin and the tool exits 0. That failure has now happened twice for real: 0 of
59,924 ramp nodes retained, and 2 speed-limit rows where the leg had 24.

These tests pin the fix -- the checked-in dense geometry archive is what a
corridor builder reads -- plus the two other holes the same reroute opened: a
leg left with no grade profile at all, and bakes that deduped against their
own previous output when re-run.

Pure logic and fixtures; no network, no PBF, no world load.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load(name: str):
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


leg_geometry = _load("leg_geometry")
reclassify_terrain = _load("reclassify_terrain")
reenrich_leg = _load("reenrich_leg")
straw = _load("straw_curve_sample")


# --- fixtures ---------------------------------------------------------------
# A 1-degree north-south line at lon -97: about 69.1 miles. Two vertices is
# what the archive leaves of a dead-straight run, and it is exactly the case
# that used to starve the corridor bakes.
STRAIGHT = [[-97.0, 28.0], [-97.0, 29.0]]


def _archive(monkeypatch, coords, elevations_m=None):
    """Install a one-leg geometry archive, encoded the way the bake writes it."""
    elevations_ft = [
        (elevations_m[i] if elevations_m else 0.0) * 3.280839895 for i in range(len(coords))
    ]
    geom = straw.encode_geometry(coords, elevations_ft, list(range(len(coords))))
    monkeypatch.setattr(
        leg_geometry,
        "_GEOMETRY_CACHE",
        {"a_tx_us:b_tx_us": {"leg": "a_tx_us:b_tx_us", "miles": 69.1, "geom": geom}},
    )


# --- the archive is the road ------------------------------------------------
def test_dense_geometry_fills_in_a_thinned_straight_run(monkeypatch):
    """Two archived vertices 69 miles apart still yield a sampleable road."""
    _archive(monkeypatch, STRAIGHT)
    geom = leg_geometry.dense_geometry("a_tx_us:b_tx_us", 69.1)
    assert len(geom) > 600  # ~0.1 mi apart, not one point per 69 miles
    gaps = [b[2] - a[2] for a, b in zip(geom, geom[1:], strict=False)]
    assert max(gaps) <= leg_geometry.DENSIFY_MI * 1.5
    assert geom[0][2] == 0.0
    assert geom[-1][2] == pytest.approx(69.1, abs=0.01)


def test_dense_geometry_is_keyed_to_the_legs_adopted_mileage(monkeypatch):
    """at_mi drives pay, deadlines and every other layer -- not raw polyline length."""
    _archive(monkeypatch, STRAIGHT)
    geom = leg_geometry.dense_geometry("a_tx_us:b_tx_us", 100.0)
    assert geom[-1][2] == pytest.approx(100.0, abs=0.01)


def test_dense_geometry_is_none_for_a_leg_with_no_archive(monkeypatch):
    monkeypatch.setattr(leg_geometry, "_GEOMETRY_CACHE", {})
    assert leg_geometry.dense_geometry("nowhere:else", 10.0) is None


def test_densify_leaves_an_already_dense_line_alone(monkeypatch):
    close = [[-97.0, 28.0 + i * 0.0005] for i in range(20)]  # ~0.035 mi apart
    assert leg_geometry.densify(close) == [list(c) for c in close]


def test_archived_route_reads_the_elevation_back(monkeypatch):
    """The curve/speed bake wants coordinates AND elevation, as ORS gives it."""
    _archive(monkeypatch, STRAIGHT, elevations_m=[100.0, 400.0])
    route = leg_geometry.archived_route("a_tx_us:b_tx_us")
    assert len(route["coordinates"]) == len(route["elevations_ft"]) == 2
    assert route["elevations_ft"][0] == pytest.approx(328.0, abs=2.0)
    assert route["elevations_ft"][1] == pytest.approx(1312.3, abs=2.0)
    assert route["miles"] == pytest.approx(69.1, abs=0.5)


# --- grade segments: a rerouted leg must not lose its grade simulation ------
def _ramp_profile(rise_ft: float, miles: float, step: float = 0.05):
    """A constant grade climbing ``rise_ft`` over ``miles``."""
    n = int(miles / step)
    return [(i * step, rise_ft * (i * step) / miles) for i in range(n + 1)]


def test_grade_segments_tile_the_whole_leg():
    """Trip.grade_at reads the segment covering the mile, so a hole is a hole."""
    profile = _ramp_profile(1000.0, 10.0)
    segments = reclassify_terrain.build_grade_segments(profile, 10.0, "test")
    assert segments
    assert segments[0]["start_mi"] == 0.0
    assert segments[-1]["end_mi"] == pytest.approx(10.0)
    for a, b in zip(segments, segments[1:], strict=False):
        assert a["end_mi"] == b["start_mi"]
        assert b["end_mi"] > b["start_mi"]  # the parser rejects a zero-width span


def test_grade_segments_read_the_real_slope():
    """1,000 ft over 10 miles is 1.89 percent, and every segment should say so."""
    profile = _ramp_profile(1000.0, 10.0)
    segments = reclassify_terrain.build_grade_segments(profile, 10.0, "test")
    for segment in segments:
        assert segment["avg_grade_pct"] == pytest.approx(1.89, abs=0.05)


def test_grade_segments_merge_only_where_nothing_changes():
    """A constant grade is one segment; the merge is lossless, not a threshold."""
    segments = reclassify_terrain.build_grade_segments(_ramp_profile(1000.0, 10.0), 10.0, "test")
    assert len(segments) == 1


def test_grade_segments_keep_a_roller_a_flat_leg_would_otherwise_lose():
    """The reason segmentation is by grade and not only by terrain label.

    South Texas is flat end to end, so grouping by terrain alone would give
    I-37 ONE 144-mile segment at its net grade -- no rollers, and a truck that
    feels nothing for the whole leg.
    """
    profile = [(i * 0.05, 40.0 * ((i * 0.05) % 2.0)) for i in range(201)]  # 10 mi of sawtooth
    segments = reclassify_terrain.build_grade_segments(profile, 10.0, "test")
    assert len({s["terrain"] for s in segments}) == 1  # all one terrain...
    assert len(segments) > 5  # ...and still not one segment
    assert max(s["avg_grade_pct"] for s in segments) > 0.5
    assert min(s["avg_grade_pct"] for s in segments) < -0.5


def test_grade_segments_stay_inside_the_parsers_realistic_band():
    """A profile artifact must be clamped and SAY it was, never shipped raw.

    Outside +/-15 percent the world source does not merely screen the record,
    it refuses to load at all.
    """
    profile = _ramp_profile(30_000.0, 1.0)  # ~568 percent: impossible
    segments = reclassify_terrain.build_grade_segments(profile, 1.0, "test")
    for segment in segments:
        assert abs(segment["avg_grade_pct"]) <= reclassify_terrain.GRADE_ABS_CEILING_PCT
        assert "clamped at bake" in segment["source"]


def test_grade_segments_refuse_a_profile_too_short_to_read():
    assert reclassify_terrain.build_grade_segments([(0.0, 100.0)], 10.0, "test") == []
    assert reclassify_terrain.build_grade_segments(_ramp_profile(10.0, 1.0), 0.0, "test") == []


# --- posted limits are judged on coverage, not on row count -----------------
def _speed_shard(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "speed_limits.jsonl"
    lines = ['{"meta": {"layer": "speed_limits"}}']
    lines += [json.dumps({"leg": "a:b", **row}) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_speed_coverage_is_total_when_nothing_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        reenrich_leg, "SPEED_SHARD", _speed_shard(tmp_path, [{"at_mi": 0.0, "mph": 75}])
    )
    assert reenrich_leg.speed_coverage("a:b", 100.0) == pytest.approx(1.0)


def test_speed_coverage_counts_a_marked_hole(tmp_path, monkeypatch):
    """A row count cannot tell a complete profile from a starved one; this can."""
    monkeypatch.setattr(
        reenrich_leg,
        "SPEED_SHARD",
        _speed_shard(
            tmp_path,
            [
                {"at_mi": 0.0, "mph": 75},
                {"at_mi": 20.0, "mph": None},
                {"at_mi": 60.0, "mph": 65},
            ],
        ),
    )
    assert reenrich_leg.speed_coverage("a:b", 100.0) == pytest.approx(0.6)


def test_speed_coverage_counts_the_run_before_the_first_reading(tmp_path, monkeypatch):
    monkeypatch.setattr(
        reenrich_leg, "SPEED_SHARD", _speed_shard(tmp_path, [{"at_mi": 40.0, "mph": 75}])
    )
    assert reenrich_leg.speed_coverage("a:b", 100.0) == pytest.approx(0.6)


def test_speed_coverage_is_zero_for_a_leg_with_no_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(reenrich_leg, "SPEED_SHARD", _speed_shard(tmp_path, []))
    assert reenrich_leg.speed_coverage("a:b", 100.0) == 0.0


# --- checkpoint discovery: a rerouted leg has to find its towns again -------
place_checkpoints = _load("place_checkpoints")


def _leg_and_world(checkpoints=()):
    leg = {
        "from": "a_tx_us",
        "to": "b_tx_us",
        "miles": 69.1,
        "highway": "I-37",
        "corridor": {"checkpoints": list(checkpoints), "state_miles": [{"state": "Texas"}]},
    }
    data = {
        "cities": {
            "a_tx_us": {"lat": 28.0, "lon": -97.0, "state": "TX", "spoken_city": "Alpha"},
            "b_tx_us": {"lat": 29.0, "lon": -97.0, "state": "TX", "spoken_city": "Beta"},
        },
        "geo": {"countries": {"us": {"states": {"TX": "Texas"}}}},
    }
    return leg, data


def _places(monkeypatch, places):
    import bake_villages as bv

    monkeypatch.setattr(bv, "load_places", lambda: places)


def _town(name, lat, lon, kind="town", oid=1):
    return {"id": oid, "name": name, "place": kind, "lat": lat, "lon": lon, "state": ""}


# What ``leg_route`` hands the discovery pass: the archive, densified. The
# thinned form is deliberately NOT used here -- see
# ``test_discovery_needs_the_densified_route`` for why.
DENSE = leg_geometry.densify(STRAIGHT)


def test_discovery_needs_the_densified_route():
    """The bug this file exists to stop happening again in another shape.

    ``position_on_route`` measures to the nearest VERTEX. Handed the archive
    as it is stored -- two vertices for a 69-mile straight run -- a town
    beside the road at the halfway point reads 34 miles off-route and is
    thrown out as the wrong town.
    """
    _, thinned_off = place_checkpoints.position_on_route(STRAIGHT, 69.1, 69.1, 28.5, -97.0)
    _, dense_off = place_checkpoints.position_on_route(DENSE, 69.1, 69.1, 28.5, -97.0)
    assert thinned_off > 30.0
    assert dense_off < 0.1


def test_discovery_finds_a_town_on_the_route(monkeypatch):
    _places(monkeypatch, [_town("Mathis", 28.5, -97.0)])
    leg, data = _leg_and_world()
    found = place_checkpoints.discover_candidates(data, leg, DENSE, 69.1, 2.0, 8.9)
    assert [c["name"] for c in found] == ["Mathis"]
    assert found[0]["at_mi"] == pytest.approx(34.5, abs=1.0)


def test_discovery_rejects_a_town_off_the_road(monkeypatch):
    """The checkpoint gate is tighter than the village one on purpose: a
    checkpoint claims the road runs through the place."""
    _places(monkeypatch, [_town("Faraway", 28.5, -97.3)])  # ~18 mi off
    leg, data = _leg_and_world()
    assert place_checkpoints.discover_candidates(data, leg, DENSE, 69.1, 2.0, 8.9) == []


def test_discovery_thins_a_crowd_to_the_networks_own_spacing(monkeypatch):
    """Two towns four miles apart: the bigger one is what orients a driver."""
    _places(
        monkeypatch,
        [
            _town("Smallville", 28.50, -97.0, kind="village", oid=1),
            _town("Bigtown", 28.56, -97.0, kind="town", oid=2),
        ],
    )
    leg, data = _leg_and_world()
    found = place_checkpoints.discover_candidates(data, leg, DENSE, 69.1, 2.0, 8.9)
    assert [c["name"] for c in found] == ["Bigtown"]


def test_discovery_skips_a_town_the_leg_already_names(monkeypatch):
    _places(monkeypatch, [_town("Mathis", 28.5, -97.0)])
    leg, data = _leg_and_world(checkpoints=[{"name": "Mathis", "at_mi": 34.5}])
    assert place_checkpoints.discover_candidates(data, leg, DENSE, 69.1, 2.0, 8.9) == []


def test_discovery_finds_it_again_once_the_old_list_is_cleared(monkeypatch):
    """What ``--replace`` has to do BEFORE discovery, not after.

    Clearing afterwards made a second run dedupe against its own previous
    output and report "0 real places along the route" on a leg with five.
    """
    _places(monkeypatch, [_town("Mathis", 28.5, -97.0)])
    leg, data = _leg_and_world(checkpoints=[{"name": "Mathis", "at_mi": 34.5}])
    leg["corridor"].pop("checkpoints")
    found = place_checkpoints.discover_candidates(data, leg, DENSE, 69.1, 2.0, 8.9)
    assert [c["name"] for c in found] == ["Mathis"]


def test_discovery_skips_the_legs_own_endpoint_cities(monkeypatch):
    _places(monkeypatch, [_town("Alpha", 28.005, -97.0)])
    leg, data = _leg_and_world()
    assert place_checkpoints.discover_candidates(data, leg, DENSE, 69.1, 2.0, 8.9) == []


def test_state_at_mile_reads_the_legs_own_crossings():
    """OSM rarely tags a US place with its state; the leg was measured."""
    leg, data = _leg_and_world()
    leg["corridor"]["state_miles"] = [{"state": "Texas"}, {"state": "Louisiana"}]
    leg["corridor"]["state_crossings"] = [
        {"at_mi": 40.0, "from_state": "Texas", "state": "Louisiana"}
    ]
    assert place_checkpoints.state_at_mile(data, leg, 10.0) == "Texas"
    assert place_checkpoints.state_at_mile(data, leg, 50.0) == "Louisiana"


def test_state_at_mile_falls_back_to_a_single_state_leg():
    leg, data = _leg_and_world()
    assert place_checkpoints.state_at_mile(data, leg, 10.0) == "Texas"


# --- truck stops: the milepost was measured on a road we no longer drive ----
reproject_stops = _load("reproject_stops")


def test_name_score_matches_a_branded_stop_to_its_osm_entry():
    """ "Love's Travel Stop Cayce" against OSM's "Love's Travel Stop"."""
    assert reproject_stops.name_score("Love's Travel Stop Cayce", "Love's Travel Stop") >= 0.5


def test_name_score_refuses_a_different_brand():
    assert reproject_stops.name_score("Love's Travel Stop", "Pilot Travel Center") == 0.0


def test_name_score_ignores_the_words_every_truck_stop_shares():
    """Two unrelated places must not match on "travel center" alone."""
    assert reproject_stops.name_score("Fick & Sons Travel Center Grayling", "Travel Center") == 0.0


def test_stop_with_coordinates_is_re_measured_not_rescaled(monkeypatch):
    _archive(monkeypatch, STRAIGHT)
    leg = {
        "from": "a_tx_us",
        "to": "b_tx_us",
        "miles": 69.1,
        "stops": [{"name": "Love's Travel Stop", "at_mi": 5.0, "lat": 28.5, "lon": -97.0}],
    }
    report = reproject_stops.reproject_leg(leg, reproject_stops.MAX_OFF_ROUTE_MI)
    assert report["dropped"] == []
    assert report["stops"][0]["at_mi"] == pytest.approx(34.5, abs=1.0)  # not the old 5.0
    assert "re-measured" in report["stops"][0]["source"]


def test_stop_now_far_from_the_route_is_dropped_and_named(monkeypatch):
    """It is still a real place; it is simply not on this leg any more."""
    _archive(monkeypatch, STRAIGHT)
    leg = {
        "from": "a_tx_us",
        "to": "b_tx_us",
        "miles": 69.1,
        "stops": [{"name": "Old Road Truck Stop", "at_mi": 20.0, "lat": 28.5, "lon": -97.5}],
    }
    report = reproject_stops.reproject_leg(leg, reproject_stops.MAX_OFF_ROUTE_MI)
    assert report["stops"] == []
    assert report["dropped"][0][0] == "Old Road Truck Stop"


def test_stop_without_coordinates_is_recovered_from_osm(monkeypatch):
    """A stop whose only position was the old milepost gets READ off the map."""
    _archive(monkeypatch, STRAIGHT)
    monkeypatch.setattr(
        reproject_stops,
        "corridor_pois",
        lambda route, cum: [
            {"name": "Pilot Travel Center", "lat": 28.75, "lon": -97.0, "kind": "fuel"},
            {"name": "Love's Travel Stop", "lat": 28.25, "lon": -97.0, "kind": "fuel"},
        ],
    )
    leg = {
        "from": "a_tx_us",
        "to": "b_tx_us",
        "miles": 69.1,
        "stops": [{"name": "Pilot Travel Center Cornersville", "at_mi": 9.9}],
    }
    report = reproject_stops.reproject_leg(leg, reproject_stops.MAX_OFF_ROUTE_MI)
    assert report["recovered"], "the facility is beside the new road; OSM has it"
    kept = report["stops"][0]
    assert kept["at_mi"] == pytest.approx(51.8, abs=1.5)
    assert kept["lat"] == pytest.approx(28.75)  # now carries real coordinates
    assert "read from OpenStreetMap" in kept["source"]


def test_stop_without_coordinates_and_no_match_is_dropped(monkeypatch):
    _archive(monkeypatch, STRAIGHT)
    monkeypatch.setattr(reproject_stops, "corridor_pois", lambda route, cum: [])
    leg = {
        "from": "a_tx_us",
        "to": "b_tx_us",
        "miles": 69.1,
        "stops": [{"name": "Ghost Travel Plaza Nowhere", "at_mi": 9.9}],
    }
    report = reproject_stops.reproject_leg(leg, reproject_stops.MAX_OFF_ROUTE_MI)
    assert report["stops"] == []
    assert report["dropped"][0][0] == "Ghost Travel Plaza Nowhere"


# --- the shield check has to be measured in miles ---------------------------
reroute_leg = _load("reroute_leg")


def _town_then_freeway():
    """A leg whose vertices bunch where the road is NOT the interstate.

    Twenty vertices packed into the first two miles of town streets, then ten
    spread over sixty miles of tangent freeway. By miles it is 97 percent
    interstate; by vertex count it is 33 percent, which is how a straight
    freeway run came to read as a city street.
    """
    town = [[-97.0, 28.0 + i * 0.001] for i in range(20)]  # ~1.3 mi, 20 verts
    freeway = [[-97.0, 28.02 + i * 0.1] for i in range(10)]  # ~62 mi, 10 verts
    return town + freeway, len(town)


def _fake_trace(shape, town_vertices, monkeypatch):
    """Answer trace_attributes as Valhalla would for that shape."""

    def fake_post(path, body):
        if path != "/trace_attributes":
            return None
        points = body["shape"]
        edges = [{"names": ["Main Street"], "use": "road"}, {"names": ["I 5"], "use": "road"}]
        # The chunker may send a slice; match on latitude, which is unique here.
        matched = []
        for point in points:
            index = next(
                (i for i, (lon, lat) in enumerate(shape) if abs(lat - point["lat"]) < 1e-9), 0
            )
            matched.append({"edge_index": 0 if index < town_vertices else 1})
        return {"edges": edges, "matched_points": matched}

    monkeypatch.setattr(reroute_leg, "_post", fake_post)


def test_shield_share_is_measured_in_miles_not_vertices(monkeypatch):
    shape, town_vertices = _town_then_freeway()
    _fake_trace(shape, town_vertices, monkeypatch)
    share, dominant = reroute_leg.rides_its_label(shape, "I-5")
    assert share > 0.9, f"a leg that is 97 percent freeway by miles read {share:.0%}"
    assert dominant == "I 5"


def test_shield_share_counts_each_vertex_once_across_chunk_seams(monkeypatch):
    """Valhalla caps a trace by path distance, so a long leg is sent in pieces.

    The pieces deliberately overlap so no match is lost at a seam, which means
    the overlap would otherwise be weighed twice.
    """
    # 500 miles of freeway: several chunks, every vertex on the shield.
    shape = [[-97.0, 28.0 + i * 0.02] for i in range(360)]
    _fake_trace(shape, 0, monkeypatch)
    share, _ = reroute_leg.rides_its_label(shape, "I-5")
    assert share == pytest.approx(1.0, abs=0.01)


def test_shield_share_ignores_ramps(monkeypatch):
    """Getting on and off the freeway is not evidence about which road it is."""
    shape = [[-97.0, 28.0 + i * 0.01] for i in range(20)]

    def fake_post(path, body):
        edges = [{"names": ["I 5"], "use": "ramp"}]
        return {"edges": edges, "matched_points": [{"edge_index": 0} for _ in body["shape"]]}

    monkeypatch.setattr(reroute_leg, "_post", fake_post)
    share, dominant = reroute_leg.rides_its_label(shape, "I-5")
    assert share == 0.0
    assert dominant == "(nothing matched)"


# --- a shard's content hash must describe the shard -------------------------
def test_rewriting_a_record_restamps_the_shards_content_hash():
    """It had drifted on all fifty checked-in geometry shards.

    A ``data_version`` that does not match its own records is worse than none
    at all: anything using it to detect drift is told the file is unchanged.
    """
    meta = json.dumps({"meta": {"schema": 1, "data_version": "sha256:stale0000000"}})
    records = ['{"leg": "a:b"}', '{"leg": "c:d"}']
    restamped = json.loads(reroute_leg.restamp_data_version(meta, records))
    import hashlib

    expected = "sha256:" + hashlib.sha256("\n".join(records).encode()).hexdigest()[:12]
    assert restamped["meta"]["data_version"] == expected
    assert restamped["meta"]["schema"] == 1


def test_restamping_a_line_that_is_not_meta_leaves_it_alone():
    assert reroute_leg.restamp_data_version('{"leg": "a:b"}', ["x"]) == '{"leg": "a:b"}'
