"""Missed-exit recovery and the armed-exit countdown.

Owner playtest (Sedona to Camp Verde, AZ-260, 2026-07-18): the signal-on
announcement at 4.7 miles was the last word about the exit before the
miss, and after the second miss the reroute found no interchange on the
rural highway and stranded the trip at 0 miles remaining with nothing
left to signal for.
"""

import pytest
from driving_feature_helpers import quiet_trip, start_drive

from freight_fate.states.driving_core import (
    DESTINATION_EXIT_BEFORE_END_MI,
    RoadStop,
)


def _capture_events(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(
        app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text)
    )
    return spoken


def test_rural_miss_loops_back_to_the_synthetic_exit(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken = _capture_events(app, monkeypatch)
        # A rural approach: no baked interchange anywhere on the route.
        monkeypatch.setattr(
            driving, "_destination_exit_details", lambda **kwargs: None
        )
        total = driving.trip.total_miles
        driving.trip.position_mi = total - 0.05
        driving._handle_missed_destination_exit()
        synthetic = max(0.0, total - DESTINATION_EXIT_BEFORE_END_MI)
        expected = max(0.0, synthetic - driving._exit_window_mi())
        assert driving.trip.position_mi == pytest.approx(expected)
        assert driving._destination_exit_announced_key is None
        # The reroute text must promise the exit again, not dead-end with
        # the old "take the destination exit when it comes up" fallback.
        miss = next(t for t in spoken if "missed the destination exit" in t)
        assert "ahead again" in miss
    finally:
        app.shutdown()


def test_second_miss_still_loops_back(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        _capture_events(app, monkeypatch)
        monkeypatch.setattr(
            driving, "_destination_exit_details", lambda **kwargs: None
        )
        total = driving.trip.total_miles
        for _ in range(2):
            driving.trip.position_mi = total - 0.05
            driving._handle_missed_destination_exit()
            assert driving.trip.position_mi < total - 1.0
    finally:
        app.shutdown()


def _armed_exit(driving, ahead):
    stop = RoadStop(
        "Camp Verde Dry Warehouse",
        driving.trip.position_mi + ahead,
        "delivery_destination",
        ("deliver",),
    )
    stop.exit_phrase = ""
    driving._exit_stop = stop
    driving._exit_signal_on = True
    driving._exit_signal_canceled = False
    driving._exit_countdown_said = set()
    return stop


class _NoKeys:
    def __getitem__(self, key):
        return False


def test_countdown_anchors_the_exit_with_lane_advice(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        app.ctx.settings.steering_assist = "off"
        spoken = _capture_events(app, monkeypatch)
        stop = _armed_exit(driving, 1.9)
        # Not in the right lane: the countdown must say how to fix it.
        driving.lane.lane = 1
        driving._lane_change_target = None
        driving._update_exit_preparation(_NoKeys(), 1 / 60)
        assert any("in 2 miles" in t and "right lane" in t for t in spoken)
        # Closing to inside a mile speaks the next anchor once.
        driving.trip.position_mi = stop.at_mi - 0.9
        driving._update_exit_preparation(_NoKeys(), 1 / 60)
        driving._update_exit_preparation(_NoKeys(), 1 / 60)
        assert sum("in 1 mile" in t for t in spoken) == 1
    finally:
        app.shutdown()


def test_countdown_crossing_all_milestones_speaks_only_nearest(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        app.ctx.settings.steering_assist = "off"
        spoken = _capture_events(app, monkeypatch)
        stop = _armed_exit(driving, 5.0)
        # Time compression: one frame jumps from far out to almost there.
        driving.trip.position_mi = stop.at_mi - 0.4
        driving._update_exit_preparation(_NoKeys(), 1 / 60)
        countdowns = [t for t in spoken if "Destination exit in" in t]
        assert len(countdowns) == 1
        assert "half a mile" in countdowns[0]
    finally:
        app.shutdown()
