"""Big Buck's landmark content: spoken pools and the escalation helpers."""

import random

from freight_fate.data import big_bucks as bb

ALL_POOLS = [
    bb.NO_BIG_RIGS_SIGNAGE,
    (bb.FIRST_OFFENSE_HINT,),
    bb.MENACE_LINES,
    (bb.BAN_NOTICE,),
    (bb.STILL_BANNED,),
    bb.CROWD_REFUSALS,
    bb.ARRIVAL_GREETING,
    bb.MENU,
]


def _all_lines():
    for pool in ALL_POOLS:
        yield from pool


def test_pools_are_non_empty():
    for pool in ALL_POOLS:
        assert pool, pool


def test_lines_are_clean_spoken_text():
    for line in _all_lines():
        assert line.strip() == line and line
        # No raw map tags, codes, or stray markers reach speech.
        for marker in ("amenity=", "osm", "node/", "way/", "_"):
            assert marker not in line.lower(), line
        # Numbers are spelled out, so a screen reader never reads a bare figure.
        assert not any(ch.isdigit() for ch in line), line


def test_menace_ladder_escalates_and_clamps():
    assert bb.menace_line(1) == bb.MENACE_LINES[0]
    assert bb.menace_line(2) == bb.MENACE_LINES[1]
    # Past the end of the ladder, the final warning repeats.
    assert bb.menace_line(99) == bb.MENACE_LINES[-1]
    # Defensive: a zero/negative count still returns the first line.
    assert bb.menace_line(0) == bb.MENACE_LINES[0]


def test_ban_is_earned_at_threshold():
    assert not bb.is_ban_earned(bb.BAN_THRESHOLD - 1)
    assert bb.is_ban_earned(bb.BAN_THRESHOLD)
    assert bb.is_ban_earned(bb.BAN_THRESHOLD + 5)


def test_pickers_are_deterministic_and_in_pool():
    for picker, pool in (
        (bb.crowd_refusal, bb.CROWD_REFUSALS),
        (bb.signage, bb.NO_BIG_RIGS_SIGNAGE),
        (bb.arrival_greeting, bb.ARRIVAL_GREETING),
    ):
        first = picker(random.Random(7))
        assert first in pool
        # Same seed reproduces the choice -- offline-deterministic.
        assert picker(random.Random(7)) == first


def test_crowd_refusal_has_no_reputation_language():
    # Situational refusals are not the player's fault, so they must not threaten
    # a penalty the way the structural ban notice does.
    for line in bb.CROWD_REFUSALS:
        assert "banned" not in line.lower()
        assert "reputation" not in line.lower()
