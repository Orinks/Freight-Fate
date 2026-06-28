"""Reusable headless playtest harness coverage."""

from __future__ import annotations

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
