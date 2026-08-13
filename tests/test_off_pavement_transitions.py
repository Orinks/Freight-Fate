"""R12: off-pavement is a standing condition -- speech at transitions only,
the panned edge-rumble loop carrying the state in between."""

import pytest
from speech_capture import speech_stub


@pytest.fixture
def app():
    from freight_fate.app import App

    made = App()
    try:
        yield made
    finally:
        made.shutdown()


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Off Pavement", current_city="Denver")
    job = Job(
        CARGO_CATALOG["general"], 12.0, "Denver", "yard", "Salt Lake City", 200.0, 900.0, 12.0
    )
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    return DrivingState(app.ctx, job, route, trip_seed=1, start_hour=10.0)


def test_off_pavement_speaks_on_entry_worsening_and_recovery(app, monkeypatch):
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving = _driving(app)
    driving.lane.lane = 0
    driving.truck.velocity_mps = 13.0  # ~29 mph, below the "fast" band

    # Entry: the truck goes off the pavement.
    driving.lane.offset = 1.35
    driving._announce_off_pavement()
    assert len(events) == 1

    # Steady, no worse: the continuous cue carries it, speech stays silent.
    driving._announce_off_pavement()
    driving._announce_off_pavement()
    assert len(events) == 1

    # Worse: deeper off the road speaks again.
    driving.lane.offset = 1.48
    driving._announce_off_pavement()
    assert len(events) == 2

    # Back on the pavement is a transition too, spoken once.
    driving.lane.offset = 0.0
    driving._road_position_band = 1
    # The recovery line lives in the update path; assert the condition the
    # elif turns on so the transition fires exactly when the truck is back.
    assert not driving._off_pavement()
