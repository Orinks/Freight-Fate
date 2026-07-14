"""Roadside billboard content: clean spoken pools and corridor lookup."""

import random

from freight_fate.data import billboards as bb

POOLS = [
    bb.GENERIC_BILLBOARDS,
    bb.ATTORNEY_BILLBOARDS,
    bb.FAITH_BILLBOARDS,
    bb.ROADSIDE_ODDITIES,
]


def _all_lines():
    for pool in POOLS:
        yield from pool
    for pool in bb.CORRIDOR_BILLBOARDS.values():
        yield from pool


def test_pools_are_non_empty():
    for pool in POOLS:
        assert pool
    assert bb.CORRIDOR_BILLBOARDS


def test_lines_are_clean_spoken_text():
    for line in _all_lines():
        assert line.strip() == line and line
        for marker in ("amenity=", "osm", "node/", "way/", "_"):
            assert marker not in line.lower(), line
        # Numbers spelled out so a screen reader never reads a bare figure.
        assert not any(ch.isdigit() for ch in line), line


def test_corridor_lookup_normalizes_shield_format():
    expected = bb.CORRIDOR_BILLBOARDS["I-90"]
    for shield in ("I-90", "I 90", "Interstate 90", "i-90"):
        assert bb.corridor_billboards(shield) == expected, shield


def test_unknown_corridor_returns_empty():
    assert bb.corridor_billboards("I-976") == ()
    assert bb.corridor_billboards("some county road") == ()


def test_random_billboard_is_deterministic_and_in_pool():
    pick = bb.random_billboard(random.Random(3))
    assert pick in (
        bb.GENERIC_BILLBOARDS + bb.ATTORNEY_BILLBOARDS + bb.FAITH_BILLBOARDS + bb.ROADSIDE_ODDITIES
    )
    assert bb.random_billboard(random.Random(3)) == pick
