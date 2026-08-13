"""The closing half of a pass: when the lane you came out of is open again.

Tester Darren Duff, 1.9.0.dev0: "Not sure how you are supposed to know once
you are past vehicles and it's safe to switch lanes again." Moving over was
spoken, arriving was spoken, and coming back was a guess -- one the sideswipe
message answered with advice about mirrors nobody at this keyboard can use.
"""

import pytest
from speech_capture import speech_stub

from freight_fate.sim.traffic_manager import TrafficVehicle
from freight_fate.sim.trip_models import Zone
from freight_fate.states.driving_core import (
    DODGE_CLEARANCE_AHEAD_MI,
    DODGE_CLEARANCE_BEHIND_MI,
)
from freight_fate.states.driving_lane_gap import LANE_GAP_MARGIN_MI


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Gaps", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles,
        1000.0,
        12.0,
        destination_location="Rochester freight market",
    )
    driving = DrivingState(app.ctx, job, route, phase="delivery")
    # A clean road: every vehicle and every closure in these tests is placed
    # by the test, so a randomly seeded work zone cannot decide the answer.
    driving.trip.traffic_manager.vehicles = []
    driving.trip.zones.clear()
    return driving


def _rolling(driving, mph: float = 60.0) -> None:
    driving.truck.start_engine()
    driving.truck.velocity_mps = mph / 2.2369362920544


def _npc(
    position_mi: float,
    lane: int,
    speed_mph: float = 45.0,
    vehicle_class: str = "box truck",
    key: str = "",
) -> TrafficVehicle:
    return TrafficVehicle(
        key=key or f"npc:{lane}:{position_mi}",
        position_mi=position_mi,
        speed_mph=speed_mph,
        target_speed_mph=speed_mph,
        relative_lane=-lane,
        intent="cruising",
        vehicle_class=vehicle_class,
        lane=lane,
    )


def _pass_a_box_truck(d, events):
    """Move out around a box truck in the right lane and pull level with it."""
    d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + 0.1, lane=0)]
    d.lane.lane = 1  # the change has landed
    for _ in range(3):
        d._update_lane_gap(0.1)
    assert events == []  # still alongside it


def _clear_the_box_truck(d):
    """The truck is past it: the box truck is behind the drive tires."""
    d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi - 0.9, lane=0)]


def _openings(spoken):
    return [text for text in spoken if "lane open" in text]


# -- the spoken cue -------------------------------------------------------------


def test_the_lane_you_came_out_of_is_called_open_once_you_are_past(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d)
        _pass_a_box_truck(d, spoken)

        _clear_the_box_truck(d)
        d._update_lane_gap(0.1)

        assert spoken == ["Clear of the box truck. Right lane open."]
    finally:
        app.shutdown()


def test_the_cue_is_said_once_and_never_chants(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d)
        _pass_a_box_truck(d, spoken)
        _clear_the_box_truck(d)

        for _ in range(200):  # twenty seconds of open road behind the pass
            d._update_lane_gap(0.1)

        assert len(_openings(spoken)) == 1
    finally:
        app.shutdown()


def test_nothing_is_said_while_the_vehicle_is_still_alongside(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d)
        d.lane.lane = 1
        d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + 0.05, lane=0)]

        for _ in range(100):
            d._update_lane_gap(0.1)

        assert _openings(spoken) == []
    finally:
        app.shutdown()


def test_the_gap_closing_again_holds_the_cue(monkeypatch):
    """Somebody else fills the lane behind the pass: it is not open any more,
    and the truck must not say it is."""
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d)
        _pass_a_box_truck(d, spoken)
        _clear_the_box_truck(d)
        d._update_lane_gap(0.1)
        assert len(_openings(spoken)) == 1

        # A semi comes up the right lane and sits beside the cab.
        d.trip.traffic_manager.vehicles = [
            _npc(d.trip.position_mi + 0.05, lane=0, vehicle_class="semi", key="npc:semi")
        ]
        for _ in range(100):
            d._update_lane_gap(0.1)

        assert len(_openings(spoken)) == 1
    finally:
        app.shutdown()


def test_moving_back_over_first_leaves_the_cue_unsaid(monkeypatch):
    """The driver who did not wait has already answered the question."""
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d)
        _pass_a_box_truck(d, spoken)

        d.lane.lane = 0  # back in the right lane, still beside the box truck
        d._update_lane_gap(0.1)
        _clear_the_box_truck(d)
        for _ in range(50):
            d._update_lane_gap(0.1)

        assert _openings(spoken) == []
    finally:
        app.shutdown()


def test_an_empty_lane_change_says_nothing(monkeypatch):
    """Nobody was ever passed, so there is nothing to be clear of."""
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d)
        d.lane.lane = 1
        for _ in range(100):
            d._update_lane_gap(0.1)

        assert _openings(spoken) == []
    finally:
        app.shutdown()


def test_passing_on_the_right_calls_the_left_lane_open(monkeypatch):
    """The same manoeuvre the other way round: out of the left lane, and back."""
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d)
        d.lane.lane = 1
        d._update_lane_gap(0.1)  # settled in the left lane
        d.trip.traffic_manager.vehicles = [
            _npc(d.trip.position_mi + 0.1, lane=1, vehicle_class="car")
        ]
        d.lane.lane = 0  # moved right around it
        for _ in range(3):
            d._update_lane_gap(0.1)
        assert _openings(spoken) == []

        d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi - 0.9, lane=1)]
        d._update_lane_gap(0.1)

        assert spoken[-1] == "Clear of the car. Left lane open."
    finally:
        app.shutdown()


def test_a_coned_off_lane_is_never_called_open(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d, 55.0)
        d.trip.position_mi = 6.0
        _pass_a_box_truck(d, spoken)
        # The right lane the pass came out of is closed for roadwork.
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_lane=0))
        _clear_the_box_truck(d)

        for _ in range(50):
            d._update_lane_gap(0.1)

        assert _openings(spoken) == []
    finally:
        app.shutdown()


def test_terse_speech_keeps_the_lane_and_drops_the_vehicle(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        app.ctx.settings.speech_verbosity = 0
        _rolling(d)
        _pass_a_box_truck(d, spoken)
        _clear_the_box_truck(d)
        d._update_lane_gap(0.1)

        assert spoken == ["Right lane open."]
    finally:
        app.shutdown()


# -- the judgment agrees with the collision logic ---------------------------------


def test_a_lane_the_cue_calls_open_never_sideswipes(monkeypatch):
    """The cue and the sideswipe read the same traffic through the same call,
    and the cue's window is the wider of the two -- so "open" can never be the
    more optimistic answer."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        called_open = collided_from_blocked = 0
        for step in range(-24, 25):
            gap = step * 0.05
            _rolling(d)
            d.truck.damage_pct = 0.0
            d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + gap, lane=0)]
            d.lane.lane = 1
            open_now = d._lane_gap_open(0)

            d.lane.lane = 0  # take the lane and let the collision check judge
            d._finish_lane_change()
            hit = d.truck.damage_pct > 0.0

            if open_now:
                called_open += 1
                assert not hit, f"called the right lane open at a gap of {gap:.2f} miles"
            elif hit:
                collided_from_blocked += 1
        assert called_open  # the sweep really did reach open road
        assert collided_from_blocked  # and really did reach occupied space
    finally:
        app.shutdown()


def test_the_cue_is_the_more_cautious_of_the_two_readings():
    """A gap the collision check would let through, but the cue holds back on:
    the margin exists so the answer stays true while the driver acts on it."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        margin_gap = DODGE_CLEARANCE_AHEAD_MI + LANE_GAP_MARGIN_MI / 2.0
        d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + margin_gap, lane=0)]

        assert not d._lane_gap_open(0)
        # The sideswipe test at its own narrower window sees nothing there.
        assert (
            d.trip.traffic_manager.vehicle_in_lane(
                d.trip.position_mi,
                0,
                ahead_mi=DODGE_CLEARANCE_AHEAD_MI,
                behind_mi=DODGE_CLEARANCE_BEHIND_MI,
            )
            is None
        )
    finally:
        app.shutdown()


# -- "open" holds while the driver acts on it -----------------------------------
#
# Tester Jerry Jicha, 1.9.0.dev0: "it said the right lane was open, I even
# double check the right lane... I move over to the left lane, and I hit a
# vehicle." Traffic moves on compressed game time, so the real seconds
# between hearing "open" and arriving in the lane are minutes of road to the
# car being closed on -- the answer must look that far ahead.


def test_a_car_being_closed_on_fast_is_not_called_open():
    """Jerry's collision, in numbers: cruise at 65 closing on slowed traffic
    at 38, time compression at the full 20x. The car sits beyond the static
    window, and the truck eats that gap before the drift across finishes."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d, 65.0)
        d.trip.time_scale = 20.0
        d.lane.lane = 1
        d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + 0.55, lane=0, speed_mph=38.0)]

        assert not d._lane_gap_open(0)
        assert "Right lane open." not in d._lane_status_text()
    finally:
        app.shutdown()


def test_a_faster_vehicle_coming_up_behind_holds_the_lane():
    """The overtaker in the mirror: behind the window now, beside the cab
    before the change lands."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d, 60.0)
        d.trip.time_scale = 20.0
        d.lane.lane = 1
        d.trip.traffic_manager.vehicles = [
            _npc(d.trip.position_mi - 0.6, lane=0, speed_mph=85.0, vehicle_class="car")
        ]

        assert not d._lane_gap_open(0)
    finally:
        app.shutdown()


def test_traffic_holding_your_own_speed_still_opens():
    """A car well ahead and pacing the truck is not being closed on: the
    look-ahead must not turn every occupied road into a blocked one."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d, 60.0)
        d.trip.time_scale = 20.0
        d.lane.lane = 1
        d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + 0.6, lane=0, speed_mph=60.0)]

        assert d._lane_gap_open(0)
    finally:
        app.shutdown()


def test_a_lane_called_open_survives_the_move_under_time_compression(monkeypatch):
    """The end-to-end guarantee: read the lane, spend the real seconds a
    driver spends hearing the line and drifting across -- with traffic
    moving on compressed game time the whole while -- then let the
    collision check judge the arrival. "Open" must never end in contact."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        d.trip.time_scale = 20.0
        called_open = collided_from_blocked = 0
        for step in range(-30, 31):
            gap = step * 0.05
            _rolling(d, 65.0)
            d.truck.damage_pct = 0.0
            # The contact cooldown belongs to the state's update loop, which
            # this sweep never runs: left set, the first contact swallows
            # every collision after it and the sweep goes blind.
            d._sideswipe_cooldown_s = 0.0
            d.trip.position_mi = 5.0
            car = _npc(d.trip.position_mi + gap, lane=0, speed_mph=38.0)
            d.trip.traffic_manager.vehicles = [car]
            d.lane.lane = 1
            open_now = d._lane_gap_open(0)

            # Hearing the line, reaching for the wheel, and the timed drift:
            # about four and a half real seconds, every one of them compressed.
            game_hr = 4.5 * d.trip.effective_time_scale / 3600.0
            car.position_mi += car.speed_mph * game_hr
            d.trip.position_mi += d.truck.speed_mph * game_hr

            d.lane.lane = 0
            d._finish_lane_change()
            hit = d.truck.damage_pct > 0.0

            if open_now:
                called_open += 1
                assert not hit, f"called open at a gap of {gap:.2f} miles, then sideswiped"
            elif hit:
                collided_from_blocked += 1
        assert called_open  # the sweep really did reach open road
        assert collided_from_blocked  # and really did reach space being closed on
    finally:
        app.shutdown()


# -- the on-demand readout ---------------------------------------------------------


def test_the_lane_readout_says_whether_the_next_lane_over_is_open():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        d.lane.lane = 1

        assert d._lane_status_text() == "In the left lane, centered. Right lane open."

        d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + 0.05, lane=0)]
        assert d._lane_status_text() == (
            "In the left lane, centered. Right lane blocked by a box truck."
        )
    finally:
        app.shutdown()


def test_the_lane_readout_reports_a_coned_off_lane_as_closed():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d, 55.0)
        d.trip.position_mi = 6.0
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_lane=1))

        assert "Left lane closed for construction." in d._lane_status_text()
    finally:
        app.shutdown()


def test_the_l_key_speaks_the_lane_readout(monkeypatch):
    import pygame

    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        _rolling(d)
        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l, mod=0, unicode="l"))

        assert spoken == [d._lane_status_text()]
        assert "lane open" in spoken[0]
    finally:
        app.shutdown()


def test_a_one_lane_road_has_no_neighbour_to_report():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        d.lane.set_lane_count(1)

        assert d._lane_status_text() == d.lane.describe()
        assert "lane open" not in d._lane_status_text()
    finally:
        app.shutdown()


def test_the_readout_and_the_cue_read_the_same_traffic():
    """One authority, asked two ways: the key must never disagree with the
    line the truck speaks on its own."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        d.lane.lane = 1
        for step in range(-12, 13):
            d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + step * 0.08, lane=0)]
            open_now = d._lane_gap_open(0)
            assert ("Right lane open." in d._lane_status_text()) is open_now
    finally:
        app.shutdown()


def test_the_cue_waits_for_the_truck_to_be_rolling(monkeypatch):
    """Stopped in traffic nobody is passing anybody, and a queue shuffling
    forward must not read as a completed pass."""
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d)
        _pass_a_box_truck(d, spoken)
        d.truck.velocity_mps = 0.0
        _clear_the_box_truck(d)

        for _ in range(50):
            d._update_lane_gap(0.1)
        assert _openings(spoken) == []

        _rolling(d)  # rolling again, and the answer is owed
        d._update_lane_gap(0.1)
        assert len(_openings(spoken)) == 1
    finally:
        app.shutdown()


def test_a_change_still_underway_holds_the_cue(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d)
        _pass_a_box_truck(d, spoken)
        _clear_the_box_truck(d)
        d._lane_change_target = 0  # already moving back over

        for _ in range(50):
            d._update_lane_gap(0.1)
        assert _openings(spoken) == []

        d._lane_change_target = None
        d._update_lane_gap(0.1)
        assert len(_openings(spoken)) == 1
    finally:
        app.shutdown()


def test_the_watch_survives_the_vehicle_leaving_the_bubble(monkeypatch):
    """A passed vehicle that takes its exit is still a lane that opened."""
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d)
        _pass_a_box_truck(d, spoken)
        d.trip.traffic_manager.vehicles = []  # gone from the road entirely
        d._update_lane_gap(0.1)

        assert spoken == ["Clear of the box truck. Right lane open."]
    finally:
        app.shutdown()


def test_the_cue_spacing_is_real_seconds():
    from freight_fate.states.driving_lane_gap import LANE_GAP_CUE_MIN_GAP_S

    assert pytest.approx(4.0) == LANE_GAP_CUE_MIN_GAP_S
    assert LANE_GAP_MARGIN_MI > 0.0
