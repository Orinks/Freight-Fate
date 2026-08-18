"""Ramp terminal controls (owner, 2026-08-17: "no stop signs at the end of
ramps").

Every ramp control in the game is invented: all 18,011 baked exits carry an
empty ``ramp_control``, so the seeded heuristic decides all of them. The one
case that is not a matter of taste is a ramp onto another freeway -- an
interstate meeting an interstate ends in a merge, and nothing stops traffic
there.
"""

import pytest

from freight_fate.states.driving_core import FREEWAY_VIA_RE


@pytest.mark.parametrize(
    "via, is_freeway",
    [
        ("I 20 WEST;I 59 SOUTH", True),
        ("I-70", True),
        ("I 65 NORTH", True),
        ("US 31 SOUTH;US 280", False),
        ("AL 75 NORTH", False),
        ("STATE ROUTE 3", False),
        ("", False),
        # The boundary that a missing \b would swallow: these end in "I"
        # followed by a number and are not interstates.
        ("HAWAII 1", False),
        ("MISSISSIPPI 3", False),
    ],
)
def test_only_a_real_interstate_reads_as_a_freeway(via, is_freeway):
    assert bool(FREEWAY_VIA_RE.search(via)) is is_freeway


def test_the_pattern_carries_a_word_boundary():
    """Pinned because it was briefly a literal backspace character.

    A shell-escaping slip wrote 0x08 into the source instead of backslash-b.
    It still compiled, still matched every interstate, and silently matched
    "HAWAII 1" too -- invisible in an editor and in a diff. The check builds
    the backslash with chr(92) so this assertion cannot fall into the same
    hole it exists to catch.
    """
    backslash = chr(92)
    assert FREEWAY_VIA_RE.pattern.startswith(backslash + "b")
    assert chr(8) not in FREEWAY_VIA_RE.pattern


def test_a_ramp_onto_a_freeway_is_free_flow_not_a_dice_roll(world):
    """The rule has to beat the heuristic, at every seed."""
    from freight_fate.states.driving_events import DrivingEventMixin

    class _Stop:
        at_mi = 10.0

    class _Interchange:
        via = "I 59 SOUTH"

    class _Trip:
        def ramp_control_at(self, mi, tol_mi=2.0):
            return ""

        def interchange_at(self, mi, tol_mi=2.0):
            return _Interchange()

        def _near_city(self, mi):
            return False

    fake = type(
        "D",
        (),
        {
            "trip": _Trip(),
            "trip_seed": 0,
            "_ramp_meets_a_freeway": DrivingEventMixin._ramp_meets_a_freeway,
        },
    )()
    for seed in range(40):
        fake.trip_seed = seed
        got = DrivingEventMixin._ramp_control_for(fake, _Stop())
        assert got == "none", f"seed {seed} put a {got} where two freeways meet"


def test_a_surface_road_ramp_still_takes_its_chances(world):
    """The heuristic is untouched everywhere it was defensible -- a rural
    diamond onto a US route really can be a stop sign."""
    from freight_fate.states.driving_events import DrivingEventMixin

    class _Stop:
        at_mi = 10.0

    class _Interchange:
        via = "US 31 SOUTH"

    class _Trip:
        def ramp_control_at(self, mi, tol_mi=2.0):
            return ""

        def interchange_at(self, mi, tol_mi=2.0):
            return _Interchange()

        def _near_city(self, mi):
            return False

    fake = type(
        "D",
        (),
        {
            "trip": _Trip(),
            "trip_seed": 0,
            "_ramp_meets_a_freeway": DrivingEventMixin._ramp_meets_a_freeway,
        },
    )()
    seen = set()
    for seed in range(60):
        fake.trip_seed = seed
        seen.add(DrivingEventMixin._ramp_control_for(fake, _Stop()))
    assert seen - {"none"}, "a surface ramp should still vary"
