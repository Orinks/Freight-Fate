"""A sign sheet names a leg the way the driver reads the sign; the bake puts it
in the leg's own frame."""

from __future__ import annotations

import pytest
from bake_billboards import orient_to_leg, remove_from_leg, sign_record

LEG = {"from": "mitchell_sd_us", "to": "rapid_city_sd_us", "miles": 278}


def test_a_sign_read_against_the_stored_leg_is_mirrored_and_faces_back():
    rec = {"category": "billboard_sign", "at_mi": 53.8}
    orient_to_leg(rec, LEG, "rapid_city_sd_us")
    assert rec == {"category": "billboard_sign", "at_mi": 224.2, "directions": ["reverse"]}


def test_a_sign_read_along_the_stored_leg_keeps_its_milepost():
    rec = {"category": "billboard_sign", "at_mi": 222.0}
    orient_to_leg(rec, LEG, "mitchell_sd_us")
    assert rec == {"category": "billboard_sign", "at_mi": 222.0, "directions": ["forward"]}


def test_remove_deletes_only_the_named_billboard_and_refuses_a_miss():
    leg = dict(
        LEG,
        corridor={
            "landmarks": [
                {"name": "Keep", "category": "billboard_sign"},
                {"name": "Gone", "category": "billboard_sign"},
                {"name": "Gone", "category": "river"},
            ]
        },
    )
    pairs = {("mitchell_sd_us", "rapid_city_sd_us"): leg}
    remove_from_leg(pairs, {"name": "Gone", "leg": "rapid_city_sd_us -> mitchell_sd_us"})
    assert [(lm["name"], lm["category"]) for lm in leg["corridor"]["landmarks"]] == [
        ("Keep", "billboard_sign"),
        ("Gone", "river"),
    ]
    with pytest.raises(SystemExit):
        remove_from_leg(pairs, {"name": "Gone", "leg": "mitchell_sd_us -> rapid_city_sd_us"})


def test_a_landmark_faces_the_way_its_sheet_reads_unless_marked_both():
    rec = {"category": "highway_marker", "at_mi": 63.0}
    orient_to_leg(rec, LEG, "rapid_city_sd_us")
    assert rec == {"category": "highway_marker", "at_mi": 215.0, "directions": ["reverse"]}
    rec = {"category": "highway_marker", "at_mi": 63.0}
    orient_to_leg(rec, LEG, "rapid_city_sd_us", both=True)
    assert rec == {"category": "highway_marker", "at_mi": 215.0, "directions": ["both"]}


def test_billboard_source_from_sheet_is_preserved():
    sign = {
        "name": "Madison",
        "treatment": "billboard",
        "leg": "atlanta_ga_us -> augusta_ga_us",
        "at_mi": "50.0",
        "spoken": "Billboard: Madison is ahead.",
        "source": "derived from the approved review.",
    }

    _from, _to, record = sign_record(sign)

    assert record["source"] == "derived from the approved review."
