"""Every career level pays out something concrete on the 30-level ladder."""

from freight_fate.models.career import LEVEL_XP
from freight_fate.models.career_ladder import CAREER_RANKS, MAX_CAREER_LEVEL
from freight_fate.models.jobs import JobBoard, board_offer_count
from freight_fate.models.profile import Profile


def _profile_at_level(level: int) -> Profile:
    profile = Profile(name="Unlock Audit", current_city="Chicago")
    profile.career.xp = LEVEL_XP[level - 1]
    assert profile.career.level == level
    return profile


def test_every_rank_describes_a_real_unlock():
    assert len(CAREER_RANKS) == MAX_CAREER_LEVEL == 30
    for rank in CAREER_RANKS:
        assert rank.unlock.strip()
        assert rank.status.strip()


def test_fleet_tier_boundaries_are_named_in_the_ladder():
    # Dispatch upgrades the assigned tractor at these ranks; the level-up
    # announcement reads the unlock text, so the text must say so.
    for level in (4, 9, 13, 17):
        assert "tractor" in CAREER_RANKS[level - 1].unlock.lower()


def test_dispatch_board_grows_with_seniority():
    assert board_offer_count(1) == 5
    assert board_offer_count(5) == 5
    assert board_offer_count(6) == 6
    assert board_offer_count(9) == 6
    assert board_offer_count(10) == 7
    assert board_offer_count(12) == 8
    assert board_offer_count(30) == 8


def test_seniority_boards_actually_offer_more_jobs():
    world_board = None
    from freight_fate.app import App

    app = App()
    try:
        world_board = JobBoard(app.ctx.world, seed=7)
        rookie = world_board.offers("Chicago", set(), count=board_offer_count(1), level=1)
        senior = world_board.offers(
            "Chicago",
            {"refrigerated", "heavy_haul", "high_value"},
            count=board_offer_count(12),
            level=12,
        )
        assert len(rookie) == 5
        assert len(senior) == 8
    finally:
        app.shutdown()


def test_specialized_freight_weighs_heavier_for_specialized_drivers():
    from freight_fate.app import App

    app = App()
    try:
        board = JobBoard(app.ctx.world, seed=3)
        city = app.ctx.world.city("Chicago")
        junior = board._cargo_weight(city, "refrigerated", level=9)
        senior = board._cargo_weight(city, "refrigerated", level=11)
        assert senior > junior
        # Plain freight keeps the same weight either way.
        assert board._cargo_weight(city, "general", level=9) == board._cargo_weight(
            city, "general", level=11
        )
    finally:
        app.shutdown()


def test_premium_lane_drivers_see_longer_freight_weighted_up():
    from freight_fate.app import App

    app = App()
    try:
        board = JobBoard(app.ctx.world, seed=3)
        far = ("los_angeles_ca_us", 2000.0, 8)
        junior = board._destination_weight("chicago_il_us", far, level=11)
        senior = board._destination_weight("chicago_il_us", far, level=12)
        assert senior > junior
    finally:
        app.shutdown()


def test_business_checklist_opens_at_the_prep_rank():
    from freight_fate.models.business import next_business_unlock

    # Level 13 still points at the next rank; level 14 (Business Prep
    # Driver) starts reading the real owner-operator checklist.
    younger = next_business_unlock(_profile_at_level(13))
    assert younger.startswith("Next: level 14")
    prep = next_business_unlock(_profile_at_level(14))
    assert "Owner-operator gate locked" in prep
    assert "Reach level 18" in prep
