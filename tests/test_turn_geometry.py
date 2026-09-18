"""The turn angle `build_local_geometry` bakes at every street junction.

The magnitude used to be computed and thrown away -- `turn_direction` kept
only the sign -- which is why every corner in the game was priced at the same
assumed clamp. These cases pin that it survives now, and that the sign it
always returned did not change meaning on the way.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_builder():
    """Import tools/build_local_geometry.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "build_local_geometry", ROOT / "tools" / "build_local_geometry.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    return _load_builder()


def _corner(builder, bearing_out_deg: float):
    """A junction: a run due north, then a run off on ``bearing_out_deg``.

    Each leg is long enough to clear TURN_LOOKOUT_MI so the bearings are read
    from the roads themselves rather than from the curb radius.
    """
    import math

    lat0, lon0 = 40.0, -100.0
    # About a tenth of a mile each way, comfortably past the lookout distance.
    step_deg = 0.1 / 69.0
    inbound_start = (lat0 - step_deg, lon0)
    junction = (lat0, lon0)
    theta = math.radians(bearing_out_deg)
    # Longitude degrees shrink with latitude; the bearing has to account for it.
    out_lat = lat0 + step_deg * math.cos(theta)
    out_lon = lon0 + step_deg * math.sin(theta) / math.cos(math.radians(lat0))
    coords = [inbound_start, junction, (out_lat, out_lon)]
    return builder.turn_geometry(coords, boundary=1, prev_start=0, next_end=2)


def test_a_square_right_reports_ninety_degrees(builder):
    direction, degrees = _corner(builder, 90.0)
    assert direction == "right"
    assert degrees == pytest.approx(90.0, abs=1.0)


def test_a_square_left_reports_ninety_degrees(builder):
    direction, degrees = _corner(builder, 270.0)
    assert direction == "left"
    # The magnitude is unsigned: a left and a right of the same shape are the
    # same corner, and the runtime flips only the hand on a reversed route.
    assert degrees == pytest.approx(90.0, abs=1.0)


def test_a_sweeping_turn_reports_its_own_smaller_angle(builder):
    _, gentle = _corner(builder, 45.0)
    _, square = _corner(builder, 90.0)
    _, sharp = _corner(builder, 135.0)
    assert gentle < square < sharp
    assert gentle == pytest.approx(45.0, abs=1.0)
    assert sharp == pytest.approx(135.0, abs=1.0)


def test_a_near_straight_junction_is_not_a_corner(builder):
    # Under TURN_MIN_DEG this reads as "Continue onto", and a corner that does
    # not exist must report 0.0 rather than a small angle the runtime would
    # then price as a real turn.
    direction, degrees = _corner(builder, builder.TURN_MIN_DEG - 5.0)
    assert direction == ""
    assert degrees == 0.0


def test_the_threshold_itself_still_counts_as_a_turn(builder):
    direction, degrees = _corner(builder, builder.TURN_MIN_DEG + 1.0)
    assert direction == "right"
    assert degrees > 0.0


def test_a_junction_with_no_room_to_read_a_bearing_reports_nothing(builder):
    # Both neighbours sitting on the junction: no heading to difference, so
    # there is no corner rather than an invented one.
    point = (40.0, -100.0)
    assert builder.turn_geometry([point, point, point], boundary=1, prev_start=0, next_end=2) == (
        "",
        0.0,
    )
