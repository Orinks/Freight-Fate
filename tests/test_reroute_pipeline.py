"""The per-leg reroute pipeline: pure logic, no PBF, no network.

Each test here pins a bug that shipped, or nearly did, while the enrichment
half of the reroute was being built. The comments say which.
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
    """Import a tools/*.py module by path (tools is not a package)."""
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lg = _load("leg_geometry")
oc = _load("overpass_corridor")
scs = _load("straw_curve_sample")
# build_interchanges_base, NOT the build_interchanges aggregate: that module
# merges its sub-modules' namespaces at import, and importing it twice in one
# process (which is what happens when two test files each load it by path)
# leaves the second copy holding the FIRST copy's functions. A monkeypatch on
# the module then lands on an object nothing calls. select_only is defined
# here anyway; the aggregate only re-exports it.
bi = _load("build_interchanges_base")
bv = _load("bake_villages")


# --- the geometry archive is the road -----------------------------------


def _straight_leg(vertices: int = 21) -> list[list[float]]:
    """A 20-mile due-north line as ``[[lon, lat], ...]``."""
    return [[-86.0, 40.0 + 0.0145 * i] for i in range(vertices)]


def test_elevation_decodes_back_out_of_the_archive():
    # decode_geometry drops elevation, which is fine for a curve read and
    # useless for a grade; the archive carries it and nothing read it back.
    coords = _straight_leg(5)
    feet = [100.0, 200.0, 350.0, 350.0, 120.0]
    geom = scs.encode_geometry(coords, feet, list(range(len(coords))))
    back = lg.decode_elevations_ft(geom)
    assert len(back) == len(feet)
    for wanted, got in zip(feet, back, strict=True):
        assert abs(wanted - got) < 4.0  # stored to the nearest metre


def test_state_code_comes_from_the_leg_itself():
    leg = {"from": "corpus_christi_tx_us", "to": "san_antonio_tx_us"}
    assert lg.state_code_of(leg) == "tx"
    assert lg.leg_id_of(leg) == "corpus_christi_tx_us:san_antonio_tx_us"


@pytest.mark.parametrize("slug", ["A", "chicago", "", "no_state"])
def test_a_slug_with_no_state_in_it_is_not_a_crash(slug):
    # build_interchanges.discover_leg reaches this with hand-built leg dicts,
    # so a slug that is not city_state_country has to answer "no archive"
    # rather than raise -- it crashed the interchange tool's own tests.
    leg = {"from": slug, "to": "b"}
    assert lg.state_code_of(leg) == ""
    assert lg.archived_record("whatever", "") is None
    assert lg.corridor_geometry(leg) is None


def test_archived_geometry_is_rescaled_to_the_legs_own_mileage(tmp_path, monkeypatch):
    # Curated `miles` drives pay and deadlines and may differ from the raw
    # polyline length, so positions are rescaled -- exactly as the route-point
    # interpolation this replaced did.
    coords = _straight_leg()
    geom = scs.encode_geometry(coords, [0.0] * len(coords), list(range(len(coords))))
    shard = tmp_path / "xx.jsonl"
    shard.write_text(json.dumps({"leg": "a_xx_us:b_xx_us", "geom": geom}) + "\n", encoding="utf-8")
    monkeypatch.setattr(lg, "GEOM_DIR", tmp_path)
    lg._CACHE.clear()
    out = lg.archived_geometry("a_xx_us:b_xx_us", "xx", 50.0)
    assert out is not None
    assert out[0][2] == pytest.approx(0.0)
    assert out[-1][2] == pytest.approx(50.0)


# --- checkpoints survive a reroute --------------------------------------


def test_a_town_on_the_new_road_is_moved_not_dropped():
    # The curated checkpoints are real named towns with real coordinates.
    # Dropping them and re-deriving would have thrown away 111 hand-placed
    # names across the rerouted legs to answer a question their coordinates
    # already answer.
    coords = _straight_leg()
    town = {"name": "Halfway", "lat": 40.145, "lon": -86.0, "at_mi": 99.0}
    kept, dropped = lg.reposition_on_route([town], coords, 20.0, max_off_mi=3.0)
    assert not dropped
    assert kept[0]["name"] == "Halfway"
    assert kept[0]["at_mi"] == pytest.approx(10.0, abs=0.3)


def test_a_town_the_new_road_left_behind_is_dropped():
    coords = _straight_leg()
    far = {"name": "Elsewhere", "lat": 40.145, "lon": -86.2, "at_mi": 10.0}
    kept, dropped = lg.reposition_on_route([far], coords, 20.0, max_off_mi=3.0)
    assert not kept
    assert dropped[0][0]["name"] == "Elsewhere"
    assert dropped[0][1] > 3.0


def test_a_checkpoint_with_no_coordinates_cannot_be_placed():
    # The synthetic "corridor between A and B" placeholder, which spoke as a
    # place and should never have existed.
    coords = _straight_leg()
    kept, dropped = lg.reposition_on_route(
        [{"name": "I-37 corridor between Corpus Christi and San Antonio", "at_mi": 73.0}],
        coords,
        20.0,
        max_off_mi=3.0,
    )
    assert not kept
    assert dropped[0][1] == float("inf")


# --- Overpass is asked about a corridor, not about a state ---------------


def test_corridor_boxes_cover_every_point_the_matcher_could_use():
    # A way only governs a sample within MATCH_CORRIDOR_M (90 m) of the route.
    # If a box missed one, the bake would read a tagged road as untagged and
    # write a coverage gap that is not in OpenStreetMap.
    coords = [[-86.0 + 0.02 * i, 40.0 + 0.03 * i] for i in range(200)]
    boxes = [tuple(float(value) for value in box.split(",")) for box in oc.corridor_boxes(coords)]
    assert len(boxes) > 1  # a long route is split at all
    margin_deg = scs.MATCH_CORRIDOR_M / 111_320.0
    for lon, lat in coords:
        assert any(
            south - margin_deg <= lat <= north + margin_deg
            and west - margin_deg <= lon <= east + margin_deg
            for south, west, north, east in boxes
        )


def test_a_route_is_split_at_the_span_that_the_service_will_answer():
    # MEASURED: the public service answered every quarter-degree box on a
    # 150-mile leg in 4 to 25 seconds, and answered "too busy" more often
    # than not at half a degree. So the split is not cosmetic, and a route
    # longer than the span must come back as more than one box.
    assert len(oc.corridor_boxes(_straight_leg(3))) == 1  # ~2 miles
    assert len(oc.corridor_boxes(_straight_leg(200))) > 1  # ~200 miles
    for box in oc.corridor_boxes(_straight_leg(200)):
        south, west, north, east = (float(value) for value in box.split(","))
        assert north - south <= oc.MAX_SPAN_DEG + 2 * oc.PAD_DEG
        assert east - west <= oc.MAX_SPAN_DEG + 2 * oc.PAD_DEG


# --- which road is this, really ------------------------------------------


@pytest.mark.parametrize(
    ("name", "highway"),
    [
        ("I 37 North", "I-37"),
        ("I 95 South", "I-95"),
        ("US 60", "US-60"),
        ("US Highway 181 North", "US-181"),
        ("South US Highway 181", "US-181"),  # the N of a direction word, not a shield
        ("US 31 BUS", "US-31"),  # a business route is the same mile of the same road
        ("NC 16", "NC-16"),
        ("NC-16", "NC-16"),  # the N here is NOT a compass point
        ("TX 35", "TX-35"),
        ("Illinois Route 3", "IL-3"),
        ("State Highway 6", "TX-6"),
        ("County Road 12", "CR-12"),
    ],
)
def test_a_road_is_recognised_as_the_road_the_leg_is_named_for(name, highway):
    assert scs.matches_shield(name, highway)


@pytest.mark.parametrize(
    ("name", "highway"),
    [
        # The bug this replaced scored a leg by the NUMBER alone, which credits
        # a parallel US route to the interstate it runs beside.
        ("US 95", "I-95"),
        ("US 181", "I-37"),
        ("CA 99", "I-5"),
        ("US 169", "I-90"),
        ("I 40 West", "I-85"),
        # ...and streets and named toll roads are not shields at all.
        ("Hillsborough Street", "I-40"),
        ("South Michigan Street", "I-80"),
        ("Palm Bay Road Northeast", "I-95"),
        ("Florida's Turnpike", "I-95"),
        ("ACE", "I-676"),
    ],
)
def test_a_different_road_is_not_the_road_the_leg_is_named_for(name, highway):
    assert not scs.matches_shield(name, highway)


def test_a_us_route_can_score_at_all():
    """The bug that hid 166 legs.

    ``rides_its_label`` counted a matched road only when its name began with
    "I", so a leg named US-60 scored zero however faithfully it drove US 60 --
    and ``reroute_leg`` would have refused to reroute any non-interstate leg
    with "this route does not ride US-60". The label probe filtered those legs
    out before anyone found out.
    """
    assert scs.shield_key("US-60") == ("US", "60")
    assert scs.matches_shield("US 60", "US-60")
    assert scs.shield_key("Hillsborough Street") is None


# --- a busy server is not an empty map -----------------------------------


def test_a_busy_dispatcher_is_a_refusal_not_an_answer():
    # Overpass answers a dispatcher timeout with 200 and an HTML page. The
    # client decoded that as JSON and died, so one busy minute killed a bake
    # that had hours of work behind it.
    html = (
        "<?xml version='1.0'?><html><body><p><strong>Error</strong>: runtime "
        "error: ... Dispatcher_Client::request_read_and_idx::timeout. The "
        "server is probably too busy to handle your request. </p></body></html>"
    )
    with pytest.raises(oc.TooBusy):
        oc._parse(html)


def test_a_remark_with_no_elements_is_a_refusal_not_an_empty_road():
    # The other shape of the same thing, and the more dangerous one: valid
    # JSON, no elements, a remark. Read as data it says this stretch of road
    # has no speed limits and no lanes on it.
    with pytest.raises(oc.TooBusy):
        oc._parse('{"elements": [], "remark": "runtime error: query timed out"}')


def test_a_road_with_genuinely_nothing_on_it_is_still_an_answer():
    # And the case that must NOT be mistaken for a refusal: plenty of real
    # corridor boxes hold no tagged way at all.
    assert oc._parse('{"elements": []}') == {"elements": []}


# --- one PBF read, not thirty -------------------------------------------


def test_only_takes_a_list_of_legs():
    # Every interchange sub-mode builds one index over a 12 GB extract and
    # keys its cache to the selected legs' bounds. One leg at a time meant one
    # full read of that extract per leg per sub-mode.
    legs = [
        {"from": "a_tx_us", "to": "b_tx_us"},
        {"from": "c_tx_us", "to": "d_tx_us"},
        {"from": "e_tx_us", "to": "f_tx_us"},
    ]
    picked = bi.select_only(legs, "e_tx_us->f_tx_us;a_tx_us->b_tx_us")
    assert [leg["from"] for leg in picked] == ["e_tx_us", "a_tx_us"]


def test_only_says_which_leg_it_could_not_find():
    legs = [{"from": "a_tx_us", "to": "b_tx_us"}]
    with pytest.raises(SystemExit) as raised:
        bi.select_only(legs, "Corpus Christi->San Antonio")
    assert "Corpus Christi" in str(raised.value)


def test_only_refuses_a_pair_with_no_arrow():
    with pytest.raises(SystemExit):
        bi.select_only([], "a_tx_us:b_tx_us")


# --- a re-bake must not eat its own output -------------------------------


def test_a_village_rebake_does_not_treat_its_own_names_as_taken():
    # This shipped: `taken` counted every landmark already on the leg,
    # including the villages this bake had written last time. A second run
    # therefore skipped all of them and replaced twenty-nine names with three,
    # printing "villages: 3 across 1 legs" and exiting zero.
    leg = {
        "from": "a_tx_us",
        "to": "b_tx_us",
        "miles": 20.0,
        "corridor": {
            "landmarks": [
                {"name": "Sinton", "category": "village"},
                {"name": "Nueces River", "category": "river"},
            ],
            "checkpoints": [{"name": "Beeville"}],
        },
    }
    corridor = leg["corridor"]
    taken = {
        bv._norm(landmark.get("name"))
        for landmark in corridor["landmarks"]
        if landmark.get("category") != "village"
    }
    taken |= {bv._norm(point.get("name")) for point in corridor["checkpoints"]}
    assert bv._norm("Sinton") not in taken  # its own output, up for regeneration
    assert bv._norm("Nueces River") in taken  # another layer speaks it
    assert bv._norm("Beeville") in taken


# --- the pipeline reports a builder that did nothing ---------------------


def test_a_grade_profile_with_a_hole_in_it_fails_the_run():
    re_ = _load("reroute_enrich")
    leg = {
        "from": "a_tx_us",
        "to": "b_tx_us",
        "miles": 20.0,
        "corridor": {
            "grade_segments": [
                {"start_mi": 0.0, "end_mi": 5.0},
                {"start_mi": 12.0, "end_mi": 20.0},
            ]
        },
    }
    gaps = re_.grade_coverage_gaps(leg)
    assert gaps and "nothing between mile 5.0 and 12.0" in gaps[0]


def test_a_grade_profile_covering_the_leg_passes():
    re_ = _load("reroute_enrich")
    leg = {
        "from": "a_tx_us",
        "to": "b_tx_us",
        "miles": 20.0,
        "corridor": {
            "grade_segments": [
                {"start_mi": 0.0, "end_mi": 12.0},
                {"start_mi": 12.0, "end_mi": 20.0},
            ]
        },
    }
    assert re_.grade_coverage_gaps(leg) == []


def test_no_grade_profile_at_all_is_the_loudest_failure():
    re_ = _load("reroute_enrich")
    leg = {"from": "a_tx_us", "to": "b_tx_us", "miles": 20.0, "corridor": {}}
    assert re_.grade_coverage_gaps(leg) == ["no grade profile at all"]
