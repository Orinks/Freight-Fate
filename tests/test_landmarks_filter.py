"""OSM narratable-landmark SELECT filter: classification, cleaning, queries."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_landmarks():
    """Import tools/enrich_routes_landmarks.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "enrich_routes_landmarks", ROOT / "tools" / "enrich_routes_landmarks.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lm = _load_landmarks()


def test_zone_categories_are_name_led():
    forest = lm.classify_narratable_feature(
        {"boundary": "protected_area", "protect_class": "6"}, "Coconino National Forest"
    )
    assert forest == {
        "category": "national_forest",
        "kind": "zone",
        "rank": 70,
        "name": "Coconino National Forest",
    }
    # The forest/park trap: a park whose name contains "Forest" stays a park.
    park = lm.classify_narratable_feature(
        {"boundary": "national_park"}, "Petrified Forest National Park"
    )
    assert park["category"] == "national_park" and park["kind"] == "zone"
    wild = lm.classify_narratable_feature(
        {"boundary": "protected_area", "protect_class": "1b"}, "Gila Wilderness"
    )
    assert wild["category"] == "wilderness"


def test_point_categories():
    museum = lm.classify_narratable_feature({"tourism": "museum"}, "Route 66 Museum")
    assert museum["category"] == "museum" and museum["kind"] == "point"
    pass_ = lm.classify_narratable_feature({"mountain_pass": "yes"}, "Loveland Pass")
    assert pass_["category"] == "mountain_pass"
    river = lm.classify_narratable_feature({"waterway": "river"}, "Colorado River")
    assert river["category"] == "river"


def test_unnarratable_and_unnamed_are_dropped():
    assert lm.classify_narratable_feature({"shop": "supermarket"}, "Kroger") is None
    assert lm.classify_narratable_feature({"highway": "motorway"}, "Interstate 40") is None
    assert lm.classify_narratable_feature({"tourism": "museum"}, "") is None  # unnamed
    assert lm.classify_narratable_feature({"tourism": "museum"}, "way/12345") is None  # raw


def test_clean_landmark_name_expands_abbreviations():
    assert lm.clean_landmark_name("Mt. Hood") == "Mount Hood"
    assert lm.clean_landmark_name("Ft. Union") == "Fort Union"
    assert lm.clean_landmark_name("  Coconino   National Forest ") == "Coconino National Forest"
    assert lm.clean_landmark_name("node/99") == ""
    assert lm.clean_landmark_name("") == ""


def test_spoken_text_per_kind():
    forest = lm.classify_narratable_feature({}, "Coconino National Forest")
    assert lm.spoken_landmark_text(forest) == "Entering Coconino National Forest"
    named_museum = lm.classify_narratable_feature({"tourism": "museum"}, "Route 66 Museum")
    assert lm.spoken_landmark_text(named_museum) == "Route 66 Museum ahead"
    bare_museum = lm.classify_narratable_feature({"tourism": "museum"}, "The Smithsonian")
    assert lm.spoken_landmark_text(bare_museum) == "Museum ahead: The Smithsonian"
    # A river name without the word "River" gets it appended.
    pecos = lm.classify_narratable_feature({"waterway": "river"}, "Pecos")
    assert lm.spoken_landmark_text(pecos) == "Crossing the Pecos River"
    colorado = lm.classify_narratable_feature({"waterway": "river"}, "Colorado River")
    assert lm.spoken_landmark_text(colorado) == "Crossing the Colorado River"
    pass_ = lm.classify_narratable_feature({"mountain_pass": "yes"}, "Loveland Pass")
    assert lm.spoken_landmark_text(pass_) == "Approaching Loveland Pass"


def test_rank_orders_headline_features_first():
    order = ["national_park", "national_forest", "mountain_pass", "river", "museum"]
    ranks = [lm._RANK[c] for c in order]
    assert ranks == sorted(ranks, reverse=True)


def test_query_and_import_filter_share_the_tag_set():
    query = lm.overpass_query("south,west,north,east")
    for _osm_type, key, value in lm.NARRATABLE_OSM_TAGS:
        assert f'"{key}"="{value}"' in query
    assert "out tags center" in query
    osmium = lm.osmium_tags_filter()
    assert "w/waterway=river" in osmium
    assert "n/mountain_pass=yes" in osmium
    assert "nwr/tourism=museum" in osmium
