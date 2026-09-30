"""A sign sheet names a leg the way the driver reads the sign; the bake puts it
in the leg's own frame."""

from __future__ import annotations

from bake_billboards import orient_to_leg

LEG = {"from": "mitchell_sd_us", "to": "rapid_city_sd_us", "miles": 278}


def test_a_sign_read_against_the_stored_leg_is_mirrored_and_faces_back():
    rec = {"category": "billboard_sign", "at_mi": 53.8}
    orient_to_leg(rec, LEG, "rapid_city_sd_us")
    assert rec == {"category": "billboard_sign", "at_mi": 224.2, "directions": ["reverse"]}


def test_a_sign_read_along_the_stored_leg_keeps_its_milepost():
    rec = {"category": "billboard_sign", "at_mi": 222.0}
    orient_to_leg(rec, LEG, "mitchell_sd_us")
    assert rec == {"category": "billboard_sign", "at_mi": 222.0, "directions": ["forward"]}


def test_a_monument_is_mirrored_but_heard_both_ways():
    rec = {"category": "highway_marker", "at_mi": 63.0}
    orient_to_leg(rec, LEG, "rapid_city_sd_us")
    assert rec == {"category": "highway_marker", "at_mi": 215.0}
