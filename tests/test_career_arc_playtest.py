"""Transcript-backed playtests for the months-long 1.9 career arc.

These drive the real game states end to end: a promotion across a fleet
tier must speak the level-up, then the tractor hand-over, all reachable
line by line from the settlement menu with the keyboard.
"""

import pytest
from career_1_9_scenarios import CAREER_STAGES, career_stage
from playtest_harness import PlaytestHarness

from freight_fate.models.career import LEVEL_XP


@pytest.mark.career_1_9
def test_tier_promotion_speaks_level_up_then_new_tractor(monkeypatch):
    def just_below_level_four(profile):
        profile.career.xp = LEVEL_XP[3] - 10.0

    with PlaytestHarness(monkeypatch) as harness:
        harness.start_delivery(
            profile_name="Fleet Promotion",
            configure_profile=just_below_level_four,
        )
        harness.settle_current_delivery()
        result = harness.read_settlement_lines()

        profile = harness.app.ctx.profile
        assert profile.career.level == 4
        assert "fleet_upgrade" in profile.achievements
        from freight_fate.models.carrier_fleet import assigned_truck_key
        from freight_fate.models.trucks import TRUCK_CATALOG

        model = TRUCK_CATALOG[assigned_truck_key(profile)]
        assert profile.truck_fuel_gal == pytest.approx(model.specs.fuel_tank_gal)

    result.assert_ordered(
        "Level up! You are now level 4",
        "Dispatch upgraded your assigned tractor",
        "New achievement! Newer Iron from the Yard",
    )
    result.assert_screen_reader_friendly()


@pytest.mark.career_1_9
def test_promotion_within_a_tier_stays_quiet_about_equipment(monkeypatch):
    def just_below_level_two(profile):
        profile.career.xp = LEVEL_XP[1] - 10.0

    with PlaytestHarness(monkeypatch) as harness:
        harness.start_delivery(
            profile_name="Same Rig",
            configure_profile=just_below_level_two,
        )
        harness.settle_current_delivery()
        result = harness.read_settlement_lines()

        assert harness.app.ctx.profile.career.level == 2

    result.assert_ordered("Level up! You are now level 2")
    assert "Dispatch upgraded your assigned tractor" not in result.transcript_text


@pytest.mark.career_1_9
def test_premium_lane_board_offers_eight_jobs(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import open_freight_market

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_k: None)
        app.ctx.profile = Profile(name="Premium Board", current_city="Chicago")
        career_stage("premium_fleet_driver")(app.ctx.profile)

        jobs = open_freight_market(app.ctx)

        # Seniority deepens the board: eight offers at the premium rank.
        assert len(jobs) == 8
        assert app.ctx.profile.dispatch_board_cache["key"]["count"] == 8
    finally:
        app.shutdown()


def test_fleet_band_presets_land_in_their_tiers():
    from freight_fate.models.carrier_fleet import fleet_tier_for_level

    assert fleet_tier_for_level(CAREER_STAGES["regional_fleet_driver"].level).key == "regional"
    assert fleet_tier_for_level(CAREER_STAGES["premium_fleet_driver"].level).key == "premium"
    assert fleet_tier_for_level(CAREER_STAGES["first_pick_driver"].level).key == "first_pick"
