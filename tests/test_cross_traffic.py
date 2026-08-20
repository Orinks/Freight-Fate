"""The cross bubble: real NPC traffic on the crossroad at a ramp terminal.

Pure-simulation tests first (the bubble is a self-contained model), then the
terminal integration: the stop-sign clear call must wait for a real gap, and
a violation's consequence must be what the bubble actually held.
"""

from freight_fate.sim.cross_traffic import (
    ARRIVAL_MEAN_S,
    CROSS_CLASSES,
    CROSS_EXTENT_MI,
    CROSS_SOUND_LEAD_S,
    CrossTraffic,
)


def _run(bubble, seconds, dt=0.25):
    crossed = []
    for _ in range(int(seconds / dt)):
        crossed.extend(bubble.update(dt))
    return crossed


# -- the simulation itself -------------------------------------------------


def test_same_seed_same_road():
    a = CrossTraffic(seed=42, control="signal", near_city=True)
    b = CrossTraffic(seed=42, control="signal", near_city=True)
    _run(a, 30.0)
    _run(b, 30.0)
    assert [(v.vehicle_class, round(v.position_mi, 6), v.from_side) for v in a.vehicles] == [
        (v.vehicle_class, round(v.position_mi, 6), v.from_side) for v in b.vehicles
    ]


def test_the_preroll_populates_the_road():
    """An intersection does not begin existing when the player arrives."""
    bubble = CrossTraffic(seed=7, control="signal", near_city=True)
    assert bubble.vehicles, "an urban signalized crossroad should be mid-life at first listen"


def test_an_urban_signal_is_busier_than_a_rural_stop():
    urban = sum(
        len(_run(CrossTraffic(seed=s, control="signal", near_city=True), 120.0)) for s in range(5)
    )
    rural = sum(
        len(_run(CrossTraffic(seed=s, control="stop", near_city=False), 120.0)) for s in range(5)
    )
    assert urban > 2 * rural, (urban, rural)


def test_every_class_has_a_crossing_cue_lead():
    """The class list and the audio lead table must not drift apart: a class
    without a lead falls back to a default and its cue lands off-peak."""
    assert {name for name, _, _ in CROSS_CLASSES} == set(CROSS_SOUND_LEAD_S)


def test_every_context_has_an_arrival_rate():
    for near_city in (True, False):
        for control in ("signal", "stop", "yield"):
            assert (near_city, control) in ARRIVAL_MEAN_S


def test_vehicles_despawn_past_the_extent():
    bubble = CrossTraffic(seed=3, control="signal", near_city=True)
    _run(bubble, 300.0)
    assert all(v.position_mi <= CROSS_EXTENT_MI for v in bubble.vehicles)


def test_followers_do_not_drive_through_their_leader():
    """Platooning is the point: a slow leader collects a queue, it does not
    get overlapped. Rear bumper of the leader stays ahead of the follower's
    front bumper (a small numeric tolerance for one integration step)."""
    bubble = CrossTraffic(seed=11, control="signal", near_city=False)
    for _ in range(1200):
        bubble.update(0.25)
        for side in ("left", "right"):
            lane = sorted(
                (v for v in bubble.vehicles if v.from_side == side),
                key=lambda v: -v.position_mi,
            )
            for leader, follower in zip(lane, lane[1:], strict=False):
                assert follower.front_mi <= leader.position_mi + 1e-4


def test_cross_traffic_queues_on_the_players_green():
    """The cross street runs the orthogonal phase: hold the player's green
    long enough and the cross stream dies at its own bar."""
    bubble = CrossTraffic(seed=5, control="signal", near_city=True)
    bubble.player_has_green = True
    _run(bubble, 20.0)  # whatever was already inside the bar clears
    late = _run(bubble, 60.0)
    assert not late, "no vehicle should cross against its own red"
    assert any(v.speed_mph < 1.0 for v in bubble.vehicles), "a queue should form at the bar"


def test_the_queue_dissolves_when_the_light_flips():
    bubble = CrossTraffic(seed=5, control="signal", near_city=True)
    bubble.player_has_green = True
    _run(bubble, 80.0)
    bubble.player_has_green = False
    released = _run(bubble, 45.0)
    assert released, "the held queue should cross once the cross street gets its green"


def test_each_crossing_reports_exactly_once():
    bubble = CrossTraffic(seed=9, control="stop", near_city=True)
    crossed = _run(bubble, 240.0)
    assert len(crossed) == len({id(v) for v in crossed})
    assert all(v.crossed for v in crossed)


def test_clear_to_cross_means_nothing_there_and_nothing_imminent():
    bubble = CrossTraffic(seed=13, control="stop", near_city=True)
    saw_clear = saw_blocked = False
    for _ in range(2400):
        bubble.update(0.25)
        if bubble.clear_to_cross():
            saw_clear = True
            assert not bubble.occupied()
            assert bubble.approaching() is None
        elif bubble.occupied() or bubble.approaching() is not None:
            saw_blocked = True
    assert saw_clear, "a stop-sign crossroad must offer real gaps"
    assert saw_blocked, "and real traffic to wait for"


def test_a_rural_stop_offers_gaps_within_patience():
    """The wait must end: at rural stop-sign arrival rates a clear window
    has to open within a minute of watching, or the sign is a softlock."""
    for seed in range(8):
        bubble = CrossTraffic(seed=seed, control="stop", near_city=False)
        for _ in range(240):
            bubble.update(0.25)
            if bubble.clear_to_cross():
                break
        else:
            raise AssertionError(f"seed {seed}: no gap in 60 seconds at a rural stop")


# -- the terminal asks the bubble ------------------------------------------


class _Recorder:
    def __init__(self):
        self.spoken = []
        self.played = []

    def say_event(self, message, **kwargs):
        self.spoken.append(message)

    def play(self, key, **kwargs):
        self.played.append(key)


def _stopped_driver(bubble, control="stop"):
    """A driver stopped at a controlled terminal, wired to the real method."""
    from freight_fate.states.driving_events import DrivingEventMixin

    recorder = _Recorder()

    class _Ctx:
        say_event = staticmethod(recorder.say_event)

        class audio:
            play = staticmethod(recorder.play)

    class _Truck:
        speed_mph = 0.0

    driver = type(
        "D",
        (),
        {
            "ctx": _Ctx(),
            "truck": _Truck(),
            "trip": None,
            "_ramp_mi": 0.10,
            "_ramp_control": control,
            "_ramp_terminal_done": False,
            "_ramp_waiting_at_sign": False,
            "_ramp_waiting_at_light": False,
            "_cross_bubble": bubble,
            "_update_ramp_terminal": DrivingEventMixin._update_ramp_terminal,
            "_cross_violation_meets": DrivingEventMixin._cross_violation_meets,
            "_cross_vehicle_sound": DrivingEventMixin._cross_vehicle_sound,
        },
    )()
    return driver, recorder


def _blocked_bubble():
    """A bubble caught with traffic bearing down on the conflict point."""
    for seed in range(100):
        bubble = CrossTraffic(seed=seed, control="stop", near_city=True)
        for _ in range(400):
            bubble.update(0.25)
            if not bubble.clear_to_cross():
                return bubble
    raise AssertionError("no blocked moment found in an urban stop bubble")


def _clear_bubble():
    for seed in range(100):
        bubble = CrossTraffic(seed=seed, control="stop", near_city=False)
        for _ in range(400):
            bubble.update(0.25)
            if bubble.clear_to_cross():
                return bubble
    raise AssertionError("no clear moment found in a rural stop bubble")


def test_the_stop_sign_clear_waits_for_the_gap():
    bubble = _blocked_bubble()
    driver, recorder = _stopped_driver(bubble)
    driver._update_ramp_terminal()
    assert not driver._ramp_terminal_done
    assert driver._ramp_waiting_at_sign
    assert "wait for your gap" in recorder.spoken[0]
    # Drive the road until the window opens; the clear call follows.
    for _ in range(2400):
        bubble.update(0.25)
        driver._update_ramp_terminal()
        if driver._ramp_terminal_done:
            break
    assert driver._ramp_terminal_done, "the gap never came: softlock"
    assert "Clear; pull ahead" in recorder.spoken[-1]
    assert recorder.spoken[-1].startswith("Gap in traffic")


def test_the_stop_sign_clear_is_immediate_on_an_empty_road():
    driver, recorder = _stopped_driver(_clear_bubble())
    driver._update_ramp_terminal()
    assert driver._ramp_terminal_done
    assert recorder.spoken == ["Stopped at the sign. Clear; pull ahead to the entrance."]


def test_blowing_an_empty_stop_sign_hits_nothing():
    driver, recorder = _stopped_driver(_clear_bubble())
    driver.truck.speed_mph = 25.0
    driver._ramp_mi = 0.05  # past the bar
    driver._update_ramp_terminal()
    assert driver._ramp_terminal_done
    assert "was empty" in recorder.spoken[0]
    assert "vehicle/collision" not in recorder.played


def test_the_yield_waits_when_stopped_in_traffic():
    """Stopping at a yield is always legal, and earns the stop sign's wait."""
    bubble = _blocked_bubble()
    driver, recorder = _stopped_driver(bubble, control="yield")
    driver._update_ramp_terminal()
    assert not driver._ramp_terminal_done
    assert "wait for your gap" in recorder.spoken[0]
    assert "Stopped at the yield" in recorder.spoken[0]
    for _ in range(2400):
        bubble.update(0.25)
        driver._update_ramp_terminal()
        if driver._ramp_terminal_done:
            break
    assert driver._ramp_terminal_done
    assert recorder.spoken[-1].startswith("Gap in traffic")


def test_a_clear_yield_is_rolled_not_stopped():
    """The point of the sign: a real gap at roll speed crosses clean."""
    driver, recorder = _stopped_driver(_clear_bubble(), control="yield")
    driver.truck.speed_mph = 12.0
    driver._ramp_mi = 0.05  # at the line
    driver._update_ramp_terminal()
    assert driver._ramp_terminal_done
    assert recorder.spoken == ["Through the yield in a gap. Pull ahead to the entrance."]


def test_a_roundabout_speaks_as_a_roundabout():
    driver, recorder = _stopped_driver(_clear_bubble(), control="roundabout")
    driver.truck.speed_mph = 12.0
    driver._ramp_mi = 0.05
    driver._update_ramp_terminal()
    assert driver._ramp_terminal_done
    assert "roundabout" in recorder.spoken[0]


def test_rolling_a_yield_into_an_occupied_window_clips():
    bubble = _blocked_bubble()
    for _ in range(2400):
        if bubble.occupied():
            break
        bubble.update(0.25)
    assert bubble.occupied()
    driver, recorder = _stopped_driver(bubble, control="yield")

    class _Truck:
        speed_mph = 12.0
        damage_pct = 8.0

        def apply_collision(self, amount, preventable=True):
            self.collided = True

        def pushed_through_by_surge(self):
            return False

    class _Rumble:
        def impact(self, amount):
            pass

    driver.truck = _Truck()
    driver.ctx.controller = type("C", (), {"rumble": _Rumble()})()
    driver._ramp_mi = 0.05
    driver._update_ramp_terminal()
    assert driver._ramp_terminal_done
    assert getattr(driver.truck, "collided", False)
    assert "vehicle/collision" in recorder.played
    assert "rolled the yield into cross traffic" in recorder.spoken[0]


def test_a_baked_yield_control_passes_through_the_chooser():
    """trip.ramp_control_at saying yield must reach the terminal unchanged --
    no dice roll, no remap."""
    from freight_fate.states.driving_events import DrivingEventMixin

    class _Stop:
        at_mi = 10.0
        type = "poi"

    class _Trip:
        def ramp_control_at(self, mi, tol_mi=2.0):
            return "yield"

        def _near_city(self, mi):
            return False

    fake = type("D", (), {"trip": _Trip(), "trip_seed": 0})()
    assert DrivingEventMixin._ramp_control_for(fake, _Stop()) == "yield"


def test_blowing_an_occupied_stop_sign_still_clips():
    bubble = _blocked_bubble()
    # Force the caught moment into the conflict window if it is not already.
    for _ in range(2400):
        if bubble.occupied():
            break
        bubble.update(0.25)
    assert bubble.occupied()
    driver, recorder = _stopped_driver(bubble)

    class _Truck:
        speed_mph = 25.0
        damage_pct = 12.0

        def apply_collision(self, amount, preventable=True):
            self.collided = True

        def pushed_through_by_surge(self):
            return False

    class _Rumble:
        def impact(self, amount):
            pass

    driver.truck = _Truck()
    driver.ctx.controller = type("C", (), {"rumble": _Rumble()})()
    driver._ramp_mi = 0.05
    driver._update_ramp_terminal()
    assert driver._ramp_terminal_done
    assert getattr(driver.truck, "collided", False)
    assert "vehicle/collision" in recorder.played
