"""Lane-position assist tests."""

from freight_fate.settings import Settings
from freight_fate.sim.lane import MAX_OFFSET, OFF_ROAD, LaneKeeping


def run_lane(lane: LaneKeeping, seconds: float, dt: float = 0.1, **kwargs) -> int:
    events = 0
    for _ in range(int(seconds / dt)):
        if lane.update(dt, 29.0, **kwargs):
            events += 1
    return events


def test_assist_off_preserves_centered_lane() -> None:
    lane = LaneKeeping(seed=1)
    lane.offset = 0.9
    assert run_lane(lane, 30.0, curve=1.0, wind=1.0, assist="off") == 0
    assert lane.offset == 0.0


def test_drift_and_steering_correction() -> None:
    lane = LaneKeeping(seed=7)
    run_lane(lane, 12.0, curve=1.0, assist="realistic")
    assert abs(lane.offset) > 0.4
    for _ in range(100):
        lane.steering = max(-1.0, min(1.0, -lane.offset * 2.0))
        lane.update(0.1, 29.0, assist="realistic")
    assert abs(lane.offset) < 0.25


def test_off_road_event_repeats_after_grace() -> None:
    lane = LaneKeeping(seed=1)
    fired = run_lane(lane, 40.0, curve=1.0, assist="realistic")
    assert abs(lane.offset) >= OFF_ROAD
    assert abs(lane.offset) <= MAX_OFFSET
    assert fired >= 2


def test_steering_assist_setting_is_validated(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("freight_fate.models.profile.data_dir", lambda: tmp_path)
    settings = Settings()
    settings.steering_assist = "realistic"
    settings.save()
    assert Settings.load().steering_assist == "realistic"
    settings.steering_assist = "bogus"
    settings.save()
    assert Settings.load().steering_assist == "off"
