"""Roadside billboard content: clean spoken pools and corridor lookup."""

import random

from freight_fate.data import billboards as bb

POOLS = [
    bb.GENERIC_BILLBOARDS,
    bb.ATTORNEY_BILLBOARDS,
    bb.FAITH_BILLBOARDS,
    bb.ROADSIDE_ODDITIES,
    bb.TRUCKER_SERVICES_BILLBOARDS,
    bb.META_BILLBOARDS,
    bb.SONG_TRIBUTE_BILLBOARDS,
    bb.BIG_BUCKS_BILLBOARDS,
]

# 2026-08-12 owner batch: final tester-round copy the owner asked to ship
# verbatim, numerals included -- see the matching note in billboards.py's
# module docstring. This is the only sanctioned way a line may contain a
# digit; anything not on this exact list must stay spelled out in words.
DIGIT_EXEMPT_LINES = {
    "The Last Chance Cafe: 37 miles back was The First Chance Cafe.",
    "World's 3rd-best pie: we used to be #2. Then Jerry complained.",
    "Truckers welcome! Trucks less welcome. Our parking lot only has 6 spaces.",
    "Need diesel? Of course you do. $4.89/gallon. Please cry inside.",
    "Bubba's Fireworks: open 362 days a year! Closed on the other three because we're usually in the hospital.",
}


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
        # Numbers spelled out so a screen reader never reads a bare figure,
        # except the small, explicit owner-approved allow-list above.
        if line not in DIGIT_EXEMPT_LINES:
            assert not any(ch.isdigit() for ch in line), line


def test_digit_exempt_lines_are_still_present_and_exact():
    # Guards the allow-list itself: every exempt line must be real content,
    # not a typo that silently stopped matching (which would let a bare
    # digit slip back under the general rule's radar).
    found = set(_all_lines())
    for line in DIGIT_EXEMPT_LINES:
        assert line in found, line


def test_corridor_lookup_normalizes_shield_format():
    expected = bb.CORRIDOR_BILLBOARDS["I-90"]
    for shield in ("I-90", "I 90", "Interstate 90", "i-90"):
        assert bb.corridor_billboards(shield) == expected, shield


def test_unknown_corridor_returns_empty():
    assert bb.corridor_billboards("I-976") == ()
    assert bb.corridor_billboards("some county road") == ()


def test_big_bucks_billboards_accessor_returns_pool():
    assert bb.big_bucks_billboards() == bb.BIG_BUCKS_BILLBOARDS
    assert bb.BIG_BUCKS_BILLBOARDS


def test_random_billboard_is_deterministic_and_in_pool():
    pick = bb.random_billboard(random.Random(3))
    assert pick in (
        bb.GENERIC_BILLBOARDS
        + bb.ATTORNEY_BILLBOARDS
        + bb.FAITH_BILLBOARDS
        + bb.ROADSIDE_ODDITIES
        + bb.TRUCKER_SERVICES_BILLBOARDS
        + bb.META_BILLBOARDS
        + bb.SONG_TRIBUTE_BILLBOARDS
    )
    assert bb.random_billboard(random.Random(3)) == pick


def test_song_tribute_corridors_resolve_by_shield():
    # The tribute batch added corridor keys beyond the original attractions
    # set; the number-normalized lookup must serve them like any other.
    fctc = bb.corridor_billboards("I-44")
    assert any("Franklin County Trucking Company" in line for line in fctc)
    assert bb.corridor_billboards("Interstate 44") == fctc
    for shield in (
        "I-35",
        "I-5",
        "I-55",
        "I-65",
        "I-59",
        "I-75",
        "I-85",
        "I-24",
        "I-94",
        "I-96",
        "I-71",
        "I-77",
        "I-81",
        "I-64",
        "I-30",
        "I-8",
        "I-78",
        "I-20",
    ):
        assert bb.corridor_billboards(shield), shield


def test_song_tributes_stay_rare_in_the_random_draw():
    # The tribute pool is a low-weight fold-in: roughly TRIBUTE_DRAW_CHANCE
    # of corridor-agnostic picks, so the roadside never becomes a museum.
    rng = random.Random(7)
    draws = 4000
    tributes = set(bb.SONG_TRIBUTE_BILLBOARDS)
    hits = sum(1 for _ in range(draws) if bb.random_billboard(rng) in tributes)
    fraction = hits / draws
    assert 0.05 < fraction < 0.2, fraction
