def test_the_summary_says_how_much_experience_the_next_level_needs():
    """Brandon, tester report 2026-08-17: "put in a way to check to see how
    much experience you need to go up to the next level."

    The summary named the level and the next RANK, and gave the raw XP total,
    but never the gap between them -- so the one question a player actually
    asks had no answer anywhere in the game.
    """
    from freight_fate.models.career import (
        LEVEL_XP,
        MAX_CAREER_LEVEL,
        Career,
        level_for_xp,
        xp_to_next_level,
    )

    career = Career(xp=LEVEL_XP[1] + 10)
    owed = xp_to_next_level(career.xp)
    assert owed == LEVEL_XP[2] - career.xp
    # And it is spoken, next to the level it belongs to.
    assert f"more to level {career.level + 1}" in career.summary()

    # Landing exactly on a threshold owes the whole of the next step, not zero.
    on_threshold = float(LEVEL_XP[2])
    assert xp_to_next_level(on_threshold) == LEVEL_XP[3] - on_threshold
    assert level_for_xp(on_threshold) == 3

    # At the ceiling there is no next level to owe anything to, and the
    # summary must not promise one.
    top = Career(xp=float(LEVEL_XP[-1]) + 5000)
    assert top.level == MAX_CAREER_LEVEL
    assert xp_to_next_level(top.xp) is None
    assert "more to level" not in top.summary()
