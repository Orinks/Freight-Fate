"""Reusable headless playtest harness coverage."""

from __future__ import annotations

import pygame
import pytest
from career_1_9_scenarios import CAREER_STAGES, career_stage
from hypothesis import given, settings
from hypothesis import strategies as st
from playtest_harness import PlaytestHarness


@pytest.mark.career_1_9
@pytest.mark.parametrize(
    ("mode", "time_scale"),
    [("relaxed", 10.0), ("standard", 20.0), ("realistic", 40.0)],
)
def test_each_driving_mode_completes_a_full_spoken_delivery(monkeypatch, mode, time_scale):
    with PlaytestHarness(monkeypatch) as harness:
        harness.app.ctx.settings.time_scale = time_scale
        result = harness.start_delivery(profile_name=f"Harness {mode.title()} Mode")
        harness.drive_delivery_to_completion()

    assert result.deliveries == 1
    assert result.destination == result.current_city
    assert "Dispatch routed you to" in result.transcript_text
    assert "arrived" in result.transcript_text.lower()
    result.assert_no_known_destination_exit_regressions()


@pytest.mark.parametrize(
    ("time_scale", "minimum_slack", "maximum_damage"),
    [(10.0, 5.9, 11.0), (20.0, 3.9, 18.1), (40.0, 3.9, 18.1)],
)
def test_mode_transcripts_prove_hazard_warning_and_recovery_pressure(
    monkeypatch, time_scale, minimum_slack, maximum_damage
):
    from freight_fate.sim.trip import TripEventKind
    from freight_fate.sim.trip_models import TripEvent

    with PlaytestHarness(monkeypatch) as harness:
        harness.app.ctx.settings.time_scale = time_scale
        result = harness.start_delivery(profile_name=f"Harness Pressure {time_scale:g}")
        harness.prepare_for_driving(speed_mph=70.0)
        event = TripEvent(
            TripEventKind.HAZARD,
            "Brake now! Disabled truck ahead.",
            {"deadline_s": 4.0, "dodgeable": False},
        )
        harness.driving._handle_trip_event(event)
        brake_budget = harness.driving._brake_budget_s()
        reaction_slack = harness.driving._hazard_deadline - brake_budget
        harness.driving._update_hazard(harness.driving._hazard_deadline + 0.1)

        assert reaction_slack >= minimum_slack
        assert harness.driving.truck.damage_pct <= maximum_damage

    assert "Brake now! Disabled truck ahead." in result.transcript_text
    assert "Collision! The truck took damage." in result.transcript_text


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
@pytest.mark.career_1_9
def test_playtest_harness_records_headless_delivery_transcript(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Harness Smoke")
        harness.drive_delivery_to_completion()

    transcript = result.transcript_text
    assert "Freight Fate" in transcript
    assert "Dispatch routed you to" in transcript
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


def test_new_hire_transcript_runs_assigned_load_and_route(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Harness New Hire")

    transcript = result.transcript_text
    assert "Dispatch assigns your load and route" in transcript
    assert "Accept assigned dispatch:" in transcript
    assert "Dispatch routed you to" in transcript
    # the route menu never appears for a new company hire
    assert "Route planning to" not in transcript
    assert "route option" not in transcript


def test_owner_operator_transcript_keeps_load_and_route_choice(monkeypatch):
    from freight_fate.models.start_options import (
        OWNER_OPERATOR_START_KEY,
        apply_start_option,
        start_option,
    )

    def configure_profile(profile) -> None:
        apply_start_option(profile, start_option(OWNER_OPERATOR_START_KEY))
        profile.achievements.append("first_dispatch")
        # all trailer programs, so a specialty-heavy random board can never
        # leave the harness with zero unlocked jobs
        profile.trailer_programs = ["dry_van", "reefer", "flatbed", "bulk"]

    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(
            profile_name="Harness Owner Choice",
            configure_profile=configure_profile,
        )

    transcript = result.transcript_text
    assert "dispatches available" in transcript  # browsable board, not assigned
    assert "Accept assigned dispatch:" not in transcript
    assert "Route planning to" in transcript  # route choice preserved
    assert "route option" in transcript
    assert "Dispatch routed you to" not in transcript


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


@pytest.mark.smoke
def test_playtest_harness_drives_a_specific_route(monkeypatch):
    # The Newark -> New York corridor crosses to NY at the GWB on I-95 (the
    # Holland Tunnel fix); driving it directly should complete and never mention
    # the tunnel.
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_route("Newark", "New York")
        assert harness.driving.trip.route.highways == ["I-95"]
        harness.drive_delivery_to_completion()

    transcript = result.transcript_text
    assert result.deliveries == 1
    assert result.destination == "New York"
    assert result.remaining_miles == 0.0
    assert "Holland Tunnel" not in transcript
    assert "New Jersey into New York" in transcript


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


@pytest.mark.career_1_9
@pytest.mark.parametrize("stage", CAREER_STAGES)
def test_reusable_career_stage_presets_reach_real_dispatch(monkeypatch, stage):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(
            profile_name=f"Harness {stage}", configure_profile=career_stage(stage)
        )

        profile = harness.app.ctx.profile
        preset = CAREER_STAGES[stage]
        assert profile.business_status == preset.business_status
        assert profile.career.level == preset.level

    result.assert_screen_reader_friendly()


@pytest.mark.career_1_9
def test_structured_transcript_preserves_channel_interrupt_and_order(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Harness Structured Speech")
        harness.app.ctx.say_event("Harness event channel check", interrupt=False)

    assert {entry.channel for entry in result.spoken} == {"main", "event"}
    assert any(entry.interrupt for entry in result.spoken)
    assert result.spoken[-1].interrupt is False
    result.assert_ordered("Freight Fate", "New career", "Dispatch assigns", "Dispatch routed")
    result.assert_screen_reader_friendly()


@pytest.mark.career_1_9
def test_keyboard_navigation_failure_is_bounded_and_descriptive(monkeypatch):
    from freight_fate.states.main_menu import MainMenuState

    with PlaytestHarness(monkeypatch) as harness:
        harness.app.push_state(MainMenuState(harness.app.ctx))
        with pytest.raises(AssertionError, match="not reachable with Down"):
            harness._select_current_menu_text("Missing harness action")


@pytest.mark.career_1_9
def test_deterministic_hook_restores_inspection_event(monkeypatch):
    from freight_fate.sim.trip import TripEventKind

    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Harness Inspection")
        harness.emit_trip_event(
            TripEventKind.INSPECTION,
            "Inspection station ahead.",
            {"facility": "Harness safety scale"},
        )

    assert "Inspection station ahead" in result.transcript_text
    assert any(entry.channel == "event" for entry in result.spoken)
    result.assert_screen_reader_friendly()


@pytest.mark.career_1_9
def test_radio_controls_are_keyboard_reachable(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Harness Radio")
        harness.press_key(pygame.K_m)
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        harness.press_key(pygame.K_BACKSLASH, "\\")

    assert "radio" in result.transcript_text.lower()
    result.assert_screen_reader_friendly()
