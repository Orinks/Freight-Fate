"""State welcome signs: clean spoken pools and the crossing lookup."""

import random

from freight_fate.data import state_welcome as sw


def _all_lines():
    for pool in sw.WELCOME_SIGNS.values():
        yield from pool


def test_every_state_has_a_non_empty_pool():
    assert sw.WELCOME_SIGNS
    for state, pool in sw.WELCOME_SIGNS.items():
        assert pool, state
        for line in pool:
            assert line, state


def test_lines_are_clean_spoken_text():
    for line in _all_lines():
        assert line.strip() == line and line
        for marker in ("amenity=", "osm", "node/", "way/", "_"):
            assert marker not in line.lower(), line
        # Numbers spelled out so a screen reader never reads a bare figure.
        assert not any(ch.isdigit() for ch in line), line


def test_every_line_opens_with_a_welcome():
    # The spoken moment is a welcome sign; keep the register consistent.
    for line in _all_lines():
        assert line.startswith("Welcome to "), line


def test_lookup_is_case_insensitive_and_matches_crossing_names():
    expected = sw.WELCOME_SIGNS["New Hampshire"]
    for spelling in ("New Hampshire", "new hampshire", "  New Hampshire  "):
        assert sw.welcome_signs(spelling) == expected, spelling


def test_unknown_state_returns_empty():
    # Alaska and Hawaii are deliberately absent (no drivable crossing).
    assert sw.welcome_signs("Alaska") == ()
    assert sw.welcome_signs("Hawaii") == ()
    assert sw.welcome_signs("Freedonia") == ()


def test_welcome_sign_is_deterministic_and_in_pool():
    pick = sw.welcome_sign("Nevada", random.Random(5))
    assert pick in sw.WELCOME_SIGNS["Nevada"]
    assert sw.welcome_sign("Nevada", random.Random(5)) == pick
    # A missing state yields the empty string, not an error.
    assert sw.welcome_sign("Hawaii", random.Random(5)) == ""
