"""Reusable headless playtest harness coverage."""

from __future__ import annotations

import pygame
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from playtest_harness import PlaytestHarness


def test_playtest_harness_forces_headless_environment_before_pygame():
    import os
    import subprocess

    env = os.environ.copy()
    env.pop("SDL_VIDEODRIVER", None)
    env.pop("SDL_AUDIODRIVER", None)
    env.pop("FREIGHT_FATE_NO_SPEECH", None)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, ["tests", env.get("PYTHONPATH", "")]))
    script = (
        "import os, playtest_harness; "
        "print(os.environ.get('SDL_VIDEODRIVER')); "
        "print(os.environ.get('SDL_AUDIODRIVER')); "
        "print(os.environ.get('FREIGHT_FATE_NO_SPEECH'))"
    )
    result = subprocess.run(
        [os.sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    assert result.stdout.splitlines() == ["dummy", "dummy", "1"]


def test_app_forces_dummy_video_when_speech_is_disabled():
    import os
    import subprocess

    env = os.environ.copy()
    env["FREIGHT_FATE_NO_SPEECH"] = "1"
    env["SDL_VIDEODRIVER"] = "windib"
    env["PYTHONPATH"] = os.pathsep.join(filter(None, ["src", env.get("PYTHONPATH", "")]))
    script = (
        "import pygame; "
        "from freight_fate.app import App; "
        "app = App(); "
        "print(pygame.display.get_driver()); "
        "app.shutdown()"
    )
    result = subprocess.run(
        [os.sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    assert result.stdout.splitlines()[-1] == "dummy"


@pytest.mark.smoke
def test_playtest_harness_records_headless_delivery_transcript(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Harness Smoke")
        harness.drive_delivery_to_completion()

    transcript = result.transcript_text
    assert "Freight Fate" in transcript
    assert "Navigation set for" in transcript
    assert "arrived" in transcript.lower()
    assert result.deliveries == 1
    result.assert_no_known_destination_exit_regressions()


def test_company_driver_first_delivery_transcript_builds_dispatch_trust(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(
            profile_name="Harness Training Arc",
            job_rank=0,
            route_rank=0,
        )

    text = result.transcript_text.lower()
    assert "dispatch" in text
    assert "trainer" in text or "first-week" in text
    assert "probation" not in text


def test_mid_career_transcript_speaks_level_band_guidance(monkeypatch):
    from freight_fate.models.career import LEVEL_XP

    def configure_profile(profile) -> None:
        profile.achievements.append("first_dispatch")
        profile.career.xp = LEVEL_XP[9]
        profile.career.deliveries = 20
        profile.career.reputation = 86

    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(
            profile_name="Harness Senior Career",
            job_rank=0,
            route_rank=0,
            configure_profile=configure_profile,
        )

    text = result.transcript_text
    assert "Run like a senior company driver" in text
    assert "senior company lane" in text
    assert "probation" not in text.lower()


def test_playtest_harness_neutralizes_random_traffic_by_default(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        harness.start_delivery(profile_name="Harness Quiet Road")

        assert harness.driving.trip.npc_vehicles == []
        assert harness.driving.trip.traffic_pressures == []


def test_playtest_harness_can_exercise_npc_traffic(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Harness NPC Traffic")
        harness.prepare_for_driving(speed_mph=55.0)
        harness.add_npc_traffic_ahead(
            behavior="merging_vehicle",
            gap_mi=0.8,
            speed_mph=42.0,
            relative_lane=1,
        )

        harness.drive_frames(8)

    assert "[event] Merging vehicle" in result.transcript_text
    assert "leave a gap" in result.transcript_text


def test_playtest_harness_can_exercise_traffic_pressure_guidance(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Harness Traffic Pressure")
        harness.add_traffic_pressure_ahead(
            gap_mi=2.0,
            kind="exit",
            direction="right",
            reason="exit traffic for harness ramp",
        )

        harness.press_key(pygame.K_u)

    assert "Coming up:" in result.transcript_text
    assert "exit traffic for harness ramp in 2 miles" in result.transcript_text
    assert "move right" in result.transcript_text


@pytest.mark.property
@settings(max_examples=6, deadline=None)
@given(
    job_rank=st.integers(min_value=0, max_value=3),
    route_rank=st.integers(min_value=0, max_value=2),
)
def test_playtest_harness_delivery_properties(monkeypatch, job_rank, route_rank):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(
            profile_name=f"Hypothesis {job_rank}-{route_rank}",
            job_rank=job_rank,
            route_rank=route_rank,
        )
        harness.drive_delivery_to_completion()

    assert result.deliveries == 1
    assert result.destination == result.current_city
    assert result.remaining_miles == 0.0
    result.assert_no_known_destination_exit_regressions()
