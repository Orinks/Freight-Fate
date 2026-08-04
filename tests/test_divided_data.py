"""Invariants for the baked per-leg ``divided`` flag (Track D2).

Data layer only -- curve navigation (Track B) reads it; nothing does yet, so
these guard the raw leg data directly. Honest absence: a genuinely mixed or
too-thinly-matched leg carries NO ``divided`` key and the runtime's road-class
inference stays the fallback.
"""

import json
from pathlib import Path

import freight_fate.data as ff_data

LEGS_DIR = Path(ff_data.__file__).parent / "world_data" / "us" / "legs"


def _legs():
    for shard in sorted(LEGS_DIR.glob("*.json")):
        yield from json.loads(shard.read_text(encoding="utf-8"))["legs"]


def test_divided_is_bool_where_present():
    for leg in _legs():
        if "divided" in leg:
            assert isinstance(leg["divided"], bool), f"{leg['from']}:{leg['to']} divided not bool"


def test_a_healthy_share_of_legs_have_the_flag():
    legs = list(_legs())
    flagged = sum(1 for leg in legs if "divided" in leg)
    # A clear majority resolve to true/false; the mixed middle omits.
    assert flagged >= 0.7 * len(legs), f"only {flagged}/{len(legs)} legs carry divided"


def test_interstates_that_resolve_are_mostly_divided():
    """A flagged interstate leg is divided far more often than not (the few
    undivided ones are legs tagged with an interstate but routed on a parallel
    surface road -- real, but the class should still trend hard to divided)."""
    inter = [leg for leg in _legs() if leg.get("highway", "").startswith("I-") and "divided" in leg]
    divided = sum(1 for leg in inter if leg["divided"])
    assert inter, "no flagged interstate legs found"
    assert divided / len(inter) >= 0.9, f"only {divided}/{len(inter)} flagged interstates divided"
