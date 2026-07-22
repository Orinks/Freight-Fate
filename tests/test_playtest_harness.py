"""Reusable headless playtest harness coverage."""

from __future__ import annotations

import pygame
import pytest
from career_1_9_scenarios import CAREER_STAGES, career_stage
from hypothesis import given, settings
from hypothesis import strategies as st
from playtest_harness import PlaytestHarness, key_event


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
    # A sentinel proves App replaces a pre-existing non-dummy choice without
    # risking a visible Windows driver during the subprocess test.
    env["SDL_VIDEODRIVER"] = "visible-driver-must-not-start"
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


@pytest.mark.career_1_9
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


@pytest.mark.career_1_9
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
        pytest.param(
            "Chicago",
            "Indianapolis",
            3,
            "heavy traffic",
            None,
            None,
            70.0,
            ["cruise", "keeper", "cruise"],
            marks=pytest.mark.xfail(
                reason=(
                    "No congestion zone is placed on any route on this line. The "
                    "world data carries no traffic_aadt, so congestion placement "
                    "falls back to the metro heuristic, which rarely jams on its "
                    "own -- swept 12 seeds across 8 metro pairs and found none. "
                    "The placement code is sound; the AADT bake has not been "
                    "re-split into world_data. Re-run it, then drop this marker."
                ),
                strict=True,
            ),
        ),
        (
            "wilmington_de_us",
            "salisbury_md_us",
            17,
            None,
            5.0,
            22.0,
            70.0,
            # This segment runs through a bend advised well under the set
            # point, and a curve that far below cruise hands speed control
            # back to the driver rather than carrying 70 into it.
            ["cruise", "off"],
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
    elif "off" in modes:
        # Every speed-control change is spoken with its reason, so a driver
        # never has to guess why cruise dropped out from under them.
        assert "Adaptive cruise off; you need manual speed control" in result.transcript_text
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
    assert "Adaptive cruise easing to 40 miles per hour for the ramp" in result.transcript_text
    # The exit key is a turn signal now: "Signal on for ..." replaced the older
    # "Signaling for ..." callout when the cancel/confirm model landed.
    assert "Signal on for" in result.transcript_text
    assert "You take" in result.transcript_text
    assert "missed the destination exit" not in result.transcript_text.lower()
    assert "Speeding strike" not in result.transcript_text
    assert "speeding fines" not in result.transcript_text.lower()
    assert result.deliveries == 1
    if restricted_zone_reason is not None:
        assert "Speed keeper holding 45 miles per hour" in result.transcript_text
        assert (
            "Adaptive cruise resuming at 40 miles per hour for the ramp" in result.transcript_text
        )


@pytest.mark.smoke
def test_signaled_downhill_exit_keeps_cruise_below_ramp_limit(monkeypatch):
    import pygame

    from freight_fate.states.driving import RAMP_MAX_MPH
    from freight_fate.states.driving_core import RoadStop

    with PlaytestHarness(monkeypatch) as harness:
        harness.app.ctx.settings.automatic_transmission = True
        harness.app.ctx.settings.time_scale = 10.0
        harness.start_route("Chicago", "Indianapolis", trip_seed=0)
        driving = harness.driving
        assert driving is not None
        driving.tutorial = None
        driving.trip.position_mi = 35.0
        driving.trip.patrols = []
        driving.truck.start_engine()
        driving.truck.set_air_ready(parking_brake=False)
        driving.truck.transmission.automatic = True
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 70.0 / 2.23694
        driving.truck.throttle = 0.35

        stop = RoadStop("Downhill Travel Plaza", 40.0, "truck_stop", ("fuel", "sleep"))
        monkeypatch.setattr(driving, "_upcoming_exit_stop", lambda: stop)
        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda _mile: (70.0, None))
        monkeypatch.setattr(driving.trip, "grade_at", lambda _mile: -0.02)
        driving.truck.grade = -0.02

        driving.handle_event(key_event(pygame.K_k))
        driving.handle_event(key_event(pygame.K_x))

        for _frame in range(20_000):
            driving.truck.air_pressure_psi = driving.truck.specs.air_governor_cut_out_psi
            driving.update(1 / 60)
            if driving._ramp_mi is not None or driving._exit_stop is None:
                break

        entry_speed = driving.truck.speed_mph

    assert driving._ramp_mi is not None, harness.result.transcript_text
    assert entry_speed <= RAMP_MAX_MPH
    assert "Adaptive cruise easing to 40 miles per hour for the ramp" in (
        harness.result.transcript_text
    )
    assert "going too fast for the ramp" not in harness.result.transcript_text


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
        pytest.param(
            ["Indianapolis", "Nashville", "Atlanta"],
            "Tennessee",
            "Nashville",
            1,
            marks=pytest.mark.xfail(
                reason="The driver hears the state line exactly once, but from the city passing "
                "line rather than the mapped boundary. A mapped crossing is spoken as an "
                "ambient message, and ambient messages wait in a single slot that the "
                "next critical event discards and any later ambient message overwrites -- "
                "on an interstate the checkpoint cues fire constantly, so it never gets "
                "out. The passing-line fallback is deliberately kept: suppressing it "
                "would leave silence at a state line instead of a repeat. Give ambient "
                "messages a queue that survives both, then drop this and restore the "
                "suppression in trip_road_events._check_cities.",
                strict=True,
            ),
        ),
        pytest.param(
            ["Atlanta", "Nashville", "Indianapolis"],
            "Tennessee",
            "Nashville",
            1,
            marks=pytest.mark.xfail(
                reason="see above: mapped crossing never reaches speech", strict=True
            ),
        ),
        pytest.param(
            ["Shreveport", "Dallas", "Albuquerque"],
            "Texas",
            "Dallas",
            1,
            marks=pytest.mark.xfail(
                reason="see above: mapped crossing never reaches speech", strict=True
            ),
        ),
        # No mapped boundary on this route, so nothing is lost and the
        # fallback is the only announcement either way.
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
    """Both styles share the one safe gesture now: a fresh press at a
    standstill, held through the engage beat. A hold that predates the stop
    never engages, in either style."""
    from freight_fate.sim.transmission import REVERSE

    def hold(driving, *, accelerating=False, braking_key=False, seconds=0.75):
        result = False
        for _ in range(int(seconds * 60) + 2):
            result = driving._update_reverse_controls(
                accelerating=accelerating, braking_key=braking_key, dt=1 / 60
            )
        return result

    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_route("Newark", "New York")
        driving = harness.driving
        driving.truck.velocity_mps = 0.0

        harness.app.ctx.settings.automatic_direction_changes = "simple"
        driving._reverse_brake_held = True
        assert not driving._update_reverse_controls(accelerating=False, braking_key=True)
        assert driving.truck.transmission.gear != REVERSE
        driving._update_reverse_controls(accelerating=False, braking_key=False)
        assert hold(driving, braking_key=True)
        assert "[event] Reverse selected. Backing slowly." in result.transcript

        driving.truck.transmission.gear = 1
        result.transcript.clear()
        harness.app.ctx.settings.automatic_direction_changes = "deliberate"
        driving._reverse_brake_held = True
        assert not driving._update_reverse_controls(accelerating=False, braking_key=True)
        assert driving.truck.transmission.gear != REVERSE
        assert result.transcript == []

        driving._update_reverse_controls(accelerating=False, braking_key=False)
        assert hold(driving, braking_key=True)
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
def test_name_entry_uses_real_space_key_and_preserves_accessible_name(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Harness Driver")
        assert harness.app.ctx.profile.name == "Harness Driver"

    assert "space" in result.transcript


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
        before_enabled = harness.driving.radio.enabled
        harness.press_key(pygame.K_m)
        assert harness.driving.radio.enabled is not before_enabled
        assert result.transcript[-1].lower().startswith("radio ")
        before_station = harness.driving.radio.station_id
        harness.press_key(pygame.K_RIGHTBRACKET, "]")
        assert harness.driving.radio.station_id != before_station
        assert (
            "selected" in result.transcript[-1].lower() or "tuned" in result.transcript[-1].lower()
        )
        harness.press_key(pygame.K_y, "y")
        assert result.transcript[-1].startswith("Radio ")

    assert "radio" in result.transcript_text.lower()
    result.assert_screen_reader_friendly()


@pytest.mark.career_1_9
def test_lane_setup_keys_change_lane_and_speak_result(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        harness.start_delivery(profile_name="Lane Keyboard Driver")
        harness.prepare_for_driving(speed_mph=45.0)
        harness.app.ctx.settings.steering_assist = "off"
        harness.driving.lane.lane = 0
        harness.press_key(pygame.K_LEFT)
        assert harness.driving._lane_change_target == 1
        harness.driving._update_tap_lane_change(3.0)
        assert harness.driving.lane.lane == 1
        assert "left lane" in harness.result.transcript[-1].lower()


@pytest.mark.career_1_9
def test_app_speech_dispatch_flushes_stale_main_speech_for_urgent_events(monkeypatch):
    calls = []

    class SpeechProbe:
        def say(self, text, interrupt=True):
            calls.append(("say_main", text, interrupt))

        def say_event(self, text, interrupt=True):
            calls.append(("say_event", text, interrupt))

        def stop_main(self):
            calls.append(("stop_main",))

        def stop_event(self):
            calls.append(("stop_event",))

    with PlaytestHarness(monkeypatch) as harness:
        ctx = harness.app.ctx
        ctx.speech = SpeechProbe()
        ctx.settings.sapi_events = False
        # Restore the real app-level routing hidden by transcript capture.
        from freight_fate.app import GameContext

        GameContext.say(ctx, "Routine status", interrupt=False)
        GameContext.say_event(ctx, "Brake now!", interrupt=True)
        ctx.stop_speech()

    assert calls == [
        ("say_main", "Routine status", False),
        ("stop_main",),
        ("say_main", "Brake now!", False),
        ("stop_main",),
        ("stop_event",),
    ]


@pytest.mark.career_1_9
def test_app_dedicated_event_voice_does_not_interrupt_main_speech(monkeypatch):
    calls = []

    class SpeechProbe:
        def say_event(self, text, interrupt=True):
            calls.append(("say_event", text, interrupt))

        def stop_main(self):
            calls.append(("stop_main",))

    with PlaytestHarness(monkeypatch) as harness:
        ctx = harness.app.ctx
        ctx.speech = SpeechProbe()
        ctx.settings.sapi_events = True
        from freight_fate.app import GameContext

        GameContext.say_event(ctx, "Construction merge ahead", interrupt=True)

    assert calls == [("say_event", "Construction merge ahead", True)]


@pytest.mark.career_1_9
def test_deterministic_landmark_and_billboard_hooks_honor_granular_toggles(monkeypatch):
    from freight_fate.sim.trip import TripEventKind

    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Chatter Driver")
        harness.emit_trip_event(
            TripEventKind.LANDMARK, "Crossing the Harness River.", {"category": "river"}
        )
        harness.emit_trip_event(
            TripEventKind.BILLBOARD,
            "Billboard: Harness coffee ahead.",
            {"category": "billboard"},
        )
        harness.driving._update_ambient_events(999.0)
        before = len(result.spoken)
        harness.app.ctx.settings.chatter_rivers = False
        harness.app.ctx.settings.chatter_billboards = False
        harness.emit_trip_event(
            TripEventKind.LANDMARK, "Crossing the Muted River.", {"category": "river"}
        )
        harness.emit_trip_event(
            TripEventKind.BILLBOARD,
            "Billboard: Muted roadside joke.",
            {"category": "billboard"},
        )

    assert "Harness River" in result.transcript_text
    assert "Harness coffee" in result.transcript_text
    assert len(result.spoken) == before
    assert "Muted" not in result.transcript_text
