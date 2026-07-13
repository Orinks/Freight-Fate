"""Persistent multi-delivery career playtests."""

import pytest
from playtest_harness import PlaytestHarness


@pytest.mark.career_1_9
@pytest.mark.smoke
def test_two_delivery_career_persists_settlement_and_progression(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Persistent Driver")
        profile = harness.app.ctx.profile
        starting_money = profile.money
        starting_xp = profile.career.xp
        starting_reputation = profile.career.reputation

        harness.drive_delivery_to_completion()
        first_money = profile.money
        first_xp = profile.career.xp
        first_destination = profile.current_city
        assert profile.career.deliveries == 1
        assert first_money > starting_money
        assert first_xp > starting_xp
        assert profile.career.reputation >= starting_reputation

        harness.continue_to_next_delivery(job_rank=0)
        assert harness.driving.job.origin == first_destination
        harness.drive_delivery_to_completion()

        assert profile.name == "Persistent Driver"
        assert profile.career.deliveries == 2
        assert profile.money > first_money
        assert profile.career.xp > first_xp
        assert profile.current_city == harness.driving.job.destination
        assert profile.active_trip is None
        result.assert_ordered("Delivery complete", "Dispatch board", "Delivery complete")
        result.assert_screen_reader_friendly()
