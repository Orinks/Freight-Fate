"""Reusable headless playtest harness coverage."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from playtest_harness import PlaytestHarness, key_event


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


def test_speed_control_follows_job_from_deadhead_to_loaded_trip(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(
            profile_name="Speed Control Handoff",
            arm_speed_control_on_deadhead=True,
        )
        driving = harness.driving
        assert driving is not None
        assert driving._speed_control_armed
        assert driving._keeper_mph is None
        assert driving._cruise_mph is None

        driving.truck.set_air_ready(parking_brake=False)
        driving.truck.velocity_mps = 2.0
        driving.update(1 / 60)

        assert driving._keeper_mph is not None or driving._cruise_mph is not None

    transcript = result.transcript_text
    assert "Automatic speed control on" in transcript
    assert transcript.count("Automatic speed control paused for pickup") == 1
    assert "resuming" in transcript


@pytest.mark.smoke
@pytest.mark.parametrize(
    (
        "origin",
        "destination",
        "trip_seed",
        "zone_reason",
        "start_mi",
        "end_mi",
        "set_mph",
        "modes",
    ),
    [
        (
            "Chicago",
            "Indianapolis",
            0,
            "construction",
            None,
            None,
            70.0,
            ["cruise", "keeper", "cruise"],
        ),
        (
            "Chicago",
            "Indianapolis",
            3,
            "heavy traffic",
            None,
            None,
            70.0,
            ["cruise", "keeper", "cruise"],
        ),
        (
            "wilmington_de_us",
            "salisbury_md_us",
            17,
            None,
            5.0,
            22.0,
            70.0,
            ["cruise"],
        ),
    ],
)
def test_realistic_speed_control_transitions_do_not_issue_speeding_fines(
    monkeypatch,
    origin,
    destination,
    trip_seed,
    zone_reason,
    start_mi,
    end_mi,
    set_mph,
    modes,
):
    from freight_fate.states.driving import SPEEDING_HOLD_S

    with PlaytestHarness(monkeypatch) as harness:
        harness.app.ctx.settings.hos_mode = "realistic"
        harness.app.ctx.settings.speed_keeper = True
        harness.app.ctx.settings.automatic_transmission = True
        harness.app.ctx.settings.time_scale = 10.0
        harness.start_route(origin, destination, trip_seed=trip_seed)
        if zone_reason is not None:
            zone = next(zone for zone in harness.driving.trip.zones if zone.reason == zone_reason)
            start_mi = max(0.0, zone.start_mi - 5.0)
            end_mi = min(harness.driving.trip.total_miles, zone.end_mi + 3.0)
        result = harness.drive_speed_control_segment(
            start_mi=start_mi,
            end_mi=end_mi,
            set_mph=set_mph,
        )
        harness.settle_delivery_after_segment()

    assert result.speed_control_transitions == modes
    assert result.speeding_strikes == 0, result.transcript_text
    assert result.speeding_tickets == 0, result.transcript_text
    assert result.max_speeding_timer_s < SPEEDING_HOLD_S
    assert "Speeding strike" not in result.transcript_text
    assert "speeding fines" not in result.transcript_text.lower()
    assert result.deliveries == 1
    if "keeper" in modes:
        assert "Speed keeper holding" in result.transcript_text
        assert "Adaptive cruise resuming" in result.transcript_text
    else:
        assert "Posted limit lower; adaptive cruise easing" in result.transcript_text


@pytest.mark.smoke
@pytest.mark.parametrize("restricted_zone_reason", [None, "construction"])
def test_realistic_cruise_eases_for_destination_exit_without_speeding_fine(
    monkeypatch,
    restricted_zone_reason,
):
    from freight_fate.states.driving import RAMP_MAX_MPH, SPEEDING_HOLD_S

    with PlaytestHarness(monkeypatch) as harness:
        harness.app.ctx.settings.hos_mode = "realistic"
        harness.app.ctx.settings.speed_keeper = True
        harness.app.ctx.settings.automatic_transmission = True
        harness.app.ctx.settings.time_scale = 10.0
        harness.start_route("Chicago", "Indianapolis", trip_seed=0)
        result = harness.drive_destination_exit_with_speed_control(
            set_mph=70.0,
            restricted_zone_reason=restricted_zone_reason,
        )

    assert result.destination_exit_speed_mph is not None
    assert result.destination_exit_speed_mph <= RAMP_MAX_MPH
    assert result.speeding_strikes == 0, result.transcript_text
    assert result.speeding_tickets == 0, result.transcript_text
    assert result.max_speeding_timer_s < SPEEDING_HOLD_S
    assert "destination exit" in result.transcript_text
    assert "Adaptive cruise easing to 45 miles per hour for the ramp" in result.transcript_text
    assert "Signaling for" in result.transcript_text
    assert "You take" in result.transcript_text
    assert "missed the destination exit" not in result.transcript_text.lower()
    assert "Speeding strike" not in result.transcript_text
    assert "speeding fines" not in result.transcript_text.lower()
    assert result.deliveries == 1
    if restricted_zone_reason is not None:
        assert "Speed keeper holding 45 miles per hour" in result.transcript_text
        assert (
            "Adaptive cruise resuming at 45 miles per hour for the ramp" in result.transcript_text
        )


@pytest.mark.smoke
def test_delivery_publication_is_queued_without_spoken_interruption(monkeypatch):
    from freight_fate.online_presence import OnlineIdentity

    posted = []

    def transport(url, payload, headers):
        posted.append((url, payload, headers))
        return {"ok": True}

    with PlaytestHarness(monkeypatch) as harness:
        harness.app.journal.identity = OnlineIdentity("driver-1234", "ffd_" + "a" * 64)
        harness.app.journal.enabled = True
        harness.app.journal.transport = transport
        result = harness.start_delivery(profile_name="Silent Publisher")
        harness.drive_delivery_to_completion()
        harness.app.journal.flush()

    assert result.deliveries == 1
    assert any(url.endswith("/api/freight-fate/events/delivery") for url, _, _ in posted)
    transcript = result.transcript_text.lower()
    assert "journal" not in transcript
    assert "publishing" not in transcript
    assert "upload" not in transcript


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
    # State lines announce only when crossed; this short delivery finishes at
    # the terminal before its mapped crossing cue.
    assert "New Jersey into New York" not in transcript


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("route_cities", "state", "passing_city", "expected_crossings"),
    [
        (["Indianapolis", "Nashville", "Atlanta"], "Tennessee", "Nashville", 1),
        (["Atlanta", "Nashville", "Indianapolis"], "Tennessee", "Nashville", 1),
        (["Shreveport", "Dallas", "Albuquerque"], "Texas", "Dallas", 1),
        (["Dallas", "San Antonio", "Houston"], "Texas", "San Antonio", 0),
    ],
)
def test_mapped_state_lines_are_authoritative_in_delivery_transcripts(
    monkeypatch, route_cities, state, passing_city, expected_crossings
):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_route(
            route_cities[0],
            route_cities[-1],
            profile_name=f"{state} narration",
            route_cities=route_cities,
        )
        harness.drive_delivery_to_completion()

    crossing_lines = [line for line in result.transcript if f"Crossing into {state}" in line]
    assert len(crossing_lines) == expected_crossings, result.transcript_text
    passing_phrase = f"Passing {passing_city}, {state}."
    assert passing_phrase in result.transcript_text
    assert f"Crossing into {state}. Passing {passing_city}" not in result.transcript_text
    if expected_crossings:
        boundary_index = next(
            i for i, line in enumerate(result.transcript) if f"Crossing into {state} near " in line
        )
        passing_index = next(
            i for i, line in enumerate(result.transcript) if passing_phrase in line
        )
        assert boundary_index < passing_index, result.transcript_text


def test_playtest_route_report_includes_current_location_on_real_keyboard_path(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_route("Buffalo", "Rochester")
        harness.driving.trip.position_mi = 40.0
        harness.driving.handle_event(key_event(ord("r")))

    assert result.transcript[-1].startswith("Route status: on I-90 East in New York")
    assert "Near Batavia, New York" in result.transcript[-1]


def test_playtest_transcript_covers_both_automatic_direction_styles(monkeypatch):
    from freight_fate.sim.transmission import REVERSE

    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_route("Newark", "New York")
        driving = harness.driving
        driving.truck.velocity_mps = 0.0

        harness.app.ctx.settings.automatic_direction_changes = "simple"
        driving._reverse_brake_held = True
        assert driving._update_reverse_controls(accelerating=False, braking_key=True)
        assert "[event] Reverse selected. Backing slowly." in result.transcript

        driving.truck.transmission.gear = 1
        result.transcript.clear()
        harness.app.ctx.settings.automatic_direction_changes = "deliberate"
        driving._reverse_brake_held = True
        assert not driving._update_reverse_controls(accelerating=False, braking_key=True)
        assert driving.truck.transmission.gear != REVERSE
        assert result.transcript == []

        driving._update_reverse_controls(accelerating=False, braking_key=False)
        assert driving._update_reverse_controls(accelerating=False, braking_key=True)
        assert "[event] Reverse selected. Backing slowly." in result.transcript


# Six full simulated deliveries in one test, under coverage tracing on a
# contended CI runner, straddle the default 120-second hang timeout. It is
# long, not hung, so give it real headroom; 300 seconds proved marginal for
# the sibling sweep tests once the suite grew, and the thread timeout kills
# the whole xdist worker.
@pytest.mark.timeout(600)
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
