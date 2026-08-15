"""Resuming (or setting) cruise to a high target must ease up, not floor it.

The tester report (Shane): Shift+K resumes cruise to a high remembered target
(85 mph) from low road speed. The old proportional loop saw the whole error at
once and commanded wide-open throttle. On flat ground the fuel governor caps
that -- loud, but harmless. On a downgrade cruise adding fuel while gravity is
already driving the engine toward redline is what fed the over-rev during the
automatic box's between-shift hold, "the engine is screaming at redline".

The fix has three parts, each covered here:

* a working setpoint that eases from the engage speed up to the target at a
  bounded rate, so a big resume error never lands on the pedal at once;
* an RPM ceiling that tapers cruise's throttle to nothing as the engine nears
  the governor, so cruise never feeds an over-rev -- the descent-control and
  retarder staging own the grade;
* an engage gate, so on the open road cruise waits for road speed before it
  engages, the same bridge the zone-preceded automatic resume already gave the
  tester a behaviour he trusts.

Note on scope: a truck left to coast an unbraked 12 percent grade up from a
near standstill over-revs on gravity alone, threading up through the gears --
that is descent-control territory, not cruise, and it happens whether cruise is
off the throttle or not. These tests pin what cruise itself does: at a
realistic rolling resume it never redlines and charges no over-rev wear, and it
is off the throttle near the governor.
"""

import pygame
import pytest
from driving_feature_helpers import key_event, open_limits, quiet_trip, start_drive


class NoKeys:
    def __getitem__(self, _key):
        return False


def _arm_high_target(
    app,
    monkeypatch,
    *,
    automatic: bool,
    grade: float,
    speed_mph: float,
    gear: int,
    cargo_kg: float | None = None,
):
    """Arm a session, remember an 85 mph target, and Shift+K resume it.

    Returns the DrivingState rolling at ``speed_mph`` on ``grade`` with the
    resume just requested, ready for the caller to step frames.
    """
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())
    driving = start_drive(app)
    quiet_trip(driving)
    open_limits(driving)
    driving.trip.zones = []
    driving.trip.curves = []  # a real bend rightly caps cruise; not under test here
    driving.trip.traffic_context = lambda: None
    driving.trip.grade_at = lambda mile, _g=grade: _g
    driving._destination_exit_taken = True
    app.ctx.settings.automatic_transmission = automatic
    app.ctx.settings.descent_speed_control = "balanced"
    t = driving.truck
    driving.handle_event(key_event(pygame.K_e))  # engine on
    t.transmission.automatic = automatic
    if cargo_kg is not None:
        t.cargo_kg = cargo_kg
    t.grade = grade
    t.transmission.gear = gear
    t.velocity_mps = speed_mph / 2.23694
    # A remembered open-road target the way a braked-away cruise leaves it.
    driving._resume_target_mph = 85.0
    assert driving._cruise_mph is None and driving._keeper_mph is None
    shift_k = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k, mod=pygame.KMOD_LSHIFT)
    driving.handle_event(shift_k)
    assert driving._speed_control_armed
    return driving


def test_resume_eases_up_and_reaches_the_target_on_the_flat(monkeypatch):
    """Flat ground: the working setpoint climbs toward 85 gradually rather than
    the whole error landing on the loop at once, and given time the truck does
    reach and hold the number."""
    from freight_fate.app import App

    app = App()
    try:
        driving = _arm_high_target(
            app, monkeypatch, automatic=True, grade=0.0, speed_mph=21.0, gear=6, cargo_kg=0.0
        )
        t = driving.truck
        # First frame engages cruise; the working setpoint starts near road
        # speed, nowhere near the 85 target.
        driving.update(1 / 30.0)
        assert driving._cruise_mph == pytest.approx(85.0)
        assert driving._cruise_working_mph is not None
        assert driving._cruise_working_mph < 30.0
        early = driving._cruise_working_mph
        # It climbs over the next second rather than snapping to the target.
        for _ in range(30):
            driving.update(1 / 30.0)
        assert early < driving._cruise_working_mph < 85.0
        # And given time, cruise reaches and holds the number, never redlining.
        reached = False
        for _ in range(3000):
            driving.update(1 / 30.0)
            assert not t.over_revving
            if t.speed_mph >= 82.0:
                reached = True
                break
        assert reached, f"cruise never climbed to the target (stalled at {t.speed_mph:.1f})"
    finally:
        app.shutdown()


@pytest.mark.parametrize(
    ("automatic", "grade", "speed_mph", "gear"),
    [
        (True, 0.0, 21.0, 6),  # automatic, flat
        (True, -0.12, 25.0, 6),  # automatic, steep downgrade, rolling
        (False, 0.0, 21.0, 6),  # manual, flat (governor-capped)
        (False, -0.12, 55.0, 10),  # manual, steep downgrade, top gear (85 has headroom)
    ],
)
def test_resume_at_road_speed_never_redlines_or_wears(
    monkeypatch, automatic, grade, speed_mph, gear
):
    """A rolling resume to 85 -- flat and on a -12% grade, automatic and manual
    -- never crosses the over-rev threshold and charges no over-rev wear."""
    from freight_fate.app import App

    app = App()
    try:
        driving = _arm_high_target(
            app, monkeypatch, automatic=automatic, grade=grade, speed_mph=speed_mph, gear=gear
        )
        t = driving.truck
        wear_before = t.engine_wear_pct
        max_crpm = 0.0
        ever_over = False
        for _ in range(600):  # ~20 s of frames
            driving.update(1 / 30.0)
            max_crpm = max(max_crpm, t.coupled_rpm())
            ever_over = ever_over or t.over_revving
        over_thresh = t.specs.max_rpm * 1.05
        assert not ever_over, (
            f"engine over-revved (peak coupled_rpm {max_crpm:.0f} > {over_thresh:.0f})"
        )
        # Duty-cycle wear still ticks; the over-rev term (0.8%/s) does not.
        assert t.engine_wear_pct - wear_before < 0.05, t.engine_wear_pct - wear_before
    finally:
        app.shutdown()


def test_cruise_backs_off_the_throttle_near_redline(monkeypatch):
    """The belt-and-suspenders ceiling in isolation: with the same setpoint
    error, cruise commands full throttle when the engine has RPM headroom and
    next to nothing when the engine is up against the governor -- so on a
    downgrade, where gravity does the accelerating, cruise never feeds the
    over-rev."""
    from freight_fate.app import App

    app = App()
    try:
        # Manual, flat, a mid gear, rolling. The remembered target is far above,
        # so cruise wants throttle throughout -- the only thing that changes
        # between the two probes below is how close coupled RPM sits to redline.
        driving = _arm_high_target(
            app, monkeypatch, automatic=False, grade=0.0, speed_mph=50.0, gear=8
        )
        t = driving.truck
        driving.update(1 / 30.0)
        assert driving._cruise_mph == pytest.approx(85.0)

        # Near the governor: coupled RPM in the top of the range, big error.
        driving._cruise_working_mph = 70.0
        t.transmission.gear = 8
        t.velocity_mps = 52.0 / 2.23694
        driving.update(1 / 60.0)
        assert t.coupled_rpm() >= t.specs.max_rpm * 0.95
        near_redline_throttle = driving._cruise_throttle
        assert near_redline_throttle < 0.3, near_redline_throttle

        # Same gear, same error, but plenty of RPM headroom: full throttle.
        driving._cruise_working_mph = 70.0
        t.transmission.gear = 8
        t.velocity_mps = 30.0 / 2.23694
        driving.update(1 / 60.0)
        assert t.coupled_rpm() < t.specs.max_rpm * 0.7
        assert driving._cruise_throttle > 0.8, driving._cruise_throttle
    finally:
        app.shutdown()


def test_open_road_resume_waits_for_road_speed_before_engaging_cruise(monkeypatch):
    """From a near standstill on the open road, resume arms the session but
    holds off engaging cruise until the truck is at cruise's holding speed --
    the old resume snapped cruise on at KEEPER_MIN (2 mph) and floored the
    throttle to chase the high remembered target."""
    from freight_fate.app import App

    app = App()
    try:
        driving = _arm_high_target(
            app, monkeypatch, automatic=True, grade=0.0, speed_mph=6.0, gear=1
        )
        t = driving.truck
        # Well below cruise's floor: armed, but cruise must not engage yet.
        for _ in range(10):
            driving.update(1 / 30.0)
        assert driving._speed_control_armed
        assert driving._cruise_mph is None
        # Bring the truck up past the cruise floor by hand; now it engages, and
        # eased in from road speed rather than floored.
        t.velocity_mps = 24.0 / 2.23694
        driving.update(1 / 30.0)
        assert driving._cruise_mph == pytest.approx(85.0)
        assert driving._cruise_working_mph is not None
        assert driving._cruise_working_mph < 40.0
    finally:
        app.shutdown()


def _armed_exit_at(app, monkeypatch, *, ahead_mi: float, time_scale: float = 1.0):
    """Cruise holding 65 with a route exit armed ``ahead_mi`` up the road.

    ``time_scale`` is set on the settings, not the trip: the drive re-reads it
    from there every frame, so a trip-only assignment lasts exactly one tick.
    """
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())
    app.ctx.settings.time_scale = time_scale
    driving = start_drive(app)
    quiet_trip(driving)
    open_limits(driving)
    driving.trip.zones = []
    driving.trip.curves = []
    driving.trip.traffic_context = lambda: None
    driving.trip.grade_at = lambda mile: 0.0
    driving.trip.traffic_pressures = []
    driving._destination_exit_taken = True  # a plain route exit, not the delivery
    driving.trip.time_scale = time_scale
    assert app.ctx.settings.time_scale == time_scale
    t = driving.truck
    driving.handle_event(key_event(pygame.K_e))
    t.cargo_kg = 0.0
    t.grade = 0.0
    t.transmission.gear = 10
    t.velocity_mps = 65.0 / 2.23694
    stop = driving.trip.stops[0]
    driving.trip.position_mi = stop.at_mi - ahead_mi
    driving.handle_event(key_event(pygame.K_k))  # cruise at road speed
    driving.handle_event(key_event(pygame.K_x))  # signal for the exit
    assert driving._exit_stop is stop
    return driving, stop


def test_shane_2026_08_15_the_ramp_cap_no_longer_lands_miles_from_the_exit(monkeypatch):
    """The tester report this branch exists for.

    "When taking an exit, the keeper goes to 40 MPH miles away from the exit.
    It should gradually slow, or at least keep 45 so the exit can be taken. It
    should measure how far the truck is away from the exit and gradually slow
    like a driver would."

    Arming an exit set the ramp target as the cap outright, and an exit arms
    five miles out at the least -- so automatic control sat at 40 for miles of
    open interstate. The ramp number is now where the truck has to BE at the
    gore: the cap is measured off the road still left, holds road speed while
    there is plenty, and never sits below the speed the ramp needs until the
    ramp is genuinely close.
    """
    from freight_fate.app import App
    from freight_fate.states.driving import RAMP_CRUISE_TARGET_MPH, RAMP_MAX_MPH

    app = App()
    try:
        driving, stop = _armed_exit_at(app, monkeypatch, ahead_mi=4.5)
        assert driving._cruise_exit_mph == pytest.approx(RAMP_CRUISE_TARGET_MPH)

        # Four and a half miles out, the cap is not the thing holding the
        # truck: road speed stands, and it is never under ramp speed.
        far_cap = driving._ramp_approach_cap_mph()
        assert far_cap >= RAMP_MAX_MPH
        assert far_cap >= driving._cruise_mph

        # And the truck really does hold it rather than shedding to 40: five
        # seconds of driving with the exit armed, and it is still at road
        # speed with the brakes off.
        for _ in range(60 * 5):
            driving.update(1 / 60)
        assert driving.truck.speed_mph > driving._cruise_mph - 3.0
        assert driving.truck.brake == pytest.approx(0.0)
    finally:
        app.shutdown()


def test_the_ramp_cap_glides_down_as_the_exit_closes(monkeypatch):
    """Measured off the distance, the way the report asked: the cap comes down
    smoothly with the road left, and lands on the ramp target at the gore."""
    from freight_fate.app import App
    from freight_fate.states.driving import RAMP_CRUISE_TARGET_MPH

    app = App()
    try:
        driving, stop = _armed_exit_at(app, monkeypatch, ahead_mi=4.5)
        caps = []
        for ahead in (4.5, 2.0, 1.0, 0.6, 0.4, 0.2, 0.05):
            driving.trip.position_mi = stop.at_mi - ahead
            caps.append(driving._ramp_approach_cap_mph())
        assert caps == sorted(caps, reverse=True), caps
        assert caps[-1] == pytest.approx(RAMP_CRUISE_TARGET_MPH)
        assert min(caps) >= RAMP_CRUISE_TARGET_MPH
    finally:
        app.shutdown()


def _cap_at(driving, stop, ahead_mi: float) -> float:
    """The exit cap with the truck ``ahead_mi`` short of the gore."""
    driving.trip.position_mi = stop.at_mi - ahead_mi
    driving._update_exit(0.0, 0.0)  # publishes the approach distance to the clock
    return driving._ramp_approach_cap_mph()


def test_shane_2026_08_15_signalling_nine_miles_out_sheds_nothing(monkeypatch):
    """The second tester report on this branch.

    "If you signal more than 5 miles out you're still slowing down as soon as
    you signal... I noticed this when I purposely signalled for an exit 9 miles
    before a truck stop."

    The glide itself was right; the compression handling was not. The cap
    divided the available road by the effective time scale, so at high pacing
    it fell under a 65 mph cruise nine miles from the gore and signalling early
    was itself what slowed the truck. The road is measured in real miles now,
    and the trip decompresses over the approach so that stays true.
    """
    from freight_fate.app import App

    for time_scale in (1.0, 4.0, 20.0):
        app = App()
        try:
            driving, stop = _armed_exit_at(app, monkeypatch, ahead_mi=4.5, time_scale=time_scale)
            cruise = driving._cruise_mph
            for ahead in (9.0, 5.0, 2.0, 1.0):
                assert _cap_at(driving, stop, ahead) > cruise, (time_scale, ahead)
            # Half a mile out is where a driver would really lift; the shed
            # runs from there, not from the moment the signal went on.
            assert _cap_at(driving, stop, 0.5) <= cruise
        finally:
            app.shutdown()


def test_the_ramp_cap_reads_the_same_road_at_every_pacing(monkeypatch):
    """The cap is a fact about the map, not about the clock: it must answer
    identically at 1x, 4x and 20x. Decompressing the approach is what makes
    those real miles real."""
    from freight_fate.app import App

    rows = {}
    for time_scale in (1.0, 4.0, 20.0):
        app = App()
        try:
            driving, stop = _armed_exit_at(app, monkeypatch, ahead_mi=4.5, time_scale=time_scale)
            rows[time_scale] = [
                _cap_at(driving, stop, ahead) for ahead in (9.0, 5.0, 2.0, 1.0, 0.5)
            ]
        finally:
            app.shutdown()
    assert rows[4.0] == pytest.approx(rows[1.0])
    assert rows[20.0] == pytest.approx(rows[1.0])


def test_the_exit_approach_runs_on_the_real_clock(monkeypatch):
    """The mechanism: inside the road the shed needs, the trip decompresses the
    way a hard bend already does, and pacing eases back afterwards instead of
    snapping."""
    from freight_fate.app import App
    from freight_fate.sim.trip import EXIT_APPROACH_RELEASE_S

    app = App()
    try:
        driving, stop = _armed_exit_at(app, monkeypatch, ahead_mi=4.5, time_scale=20.0)
        trip = driving.trip

        trip.position_mi = stop.at_mi - 4.0
        driving._update_exit(0.0, 0.0)
        assert trip.effective_time_scale > 1.0  # nothing to shed for yet

        trip.position_mi = stop.at_mi - 0.5
        driving._update_exit(0.0, 0.0)
        assert trip.effective_time_scale == pytest.approx(1.0)
        trip.update(1 / 60)
        assert trip._exit_approach_release_s == pytest.approx(EXIT_APPROACH_RELEASE_S)

        # The exit is cancelled: pacing climbs back rather than snapping.
        driving._exit_stop = None
        driving._update_exit(0.0, 0.0)
        trip.update(EXIT_APPROACH_RELEASE_S / 2.0)
        eased = trip.effective_time_scale
        assert 1.0 < eased < 20.0
        trip.update(EXIT_APPROACH_RELEASE_S)
        assert trip._exit_approach_release_s == pytest.approx(0.0)
        assert trip.effective_time_scale > eased
    finally:
        app.shutdown()


def test_the_truck_still_makes_the_ramp_at_every_pacing(monkeypatch):
    """The constraint the glide must never trade away: whatever the pacing, the
    truck arrives at the gore slow enough to take the exit."""
    from freight_fate.app import App
    from freight_fate.states.driving import RAMP_MAX_MPH

    for time_scale in (1.0, 4.0, 20.0, 40.0):
        app = App()
        try:
            driving, stop = _armed_exit_at(app, monkeypatch, ahead_mi=4.5, time_scale=time_scale)
            entry = None
            for _ in range(60 * 60 * 20):
                driving.update(1 / 60)
                if driving._ramp_mi is not None:
                    entry = driving.truck.speed_mph
                    break
                if driving.trip.position_mi > stop.at_mi + 0.5:
                    break
            assert entry is not None, f"never took the exit at {time_scale}x"
            assert entry <= RAMP_MAX_MPH, (time_scale, entry)
        finally:
            app.shutdown()


def test_set_at_current_speed_cruise_is_unchanged(monkeypatch):
    """The K-set-at-current-speed path: engaging at 60 with the target at 60
    seeds the working setpoint at road speed, so there is no ramp artifact and
    the hold is exactly as before."""
    from freight_fate.app import App

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())
    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.zones = []
        driving.trip.traffic_context = lambda: None
        driving.trip.curves = []
        driving._destination_exit_taken = True
        open_limits(driving)
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))
        t.cargo_kg = 0.0
        t.grade = 0.0
        driving.trip.grade_at = lambda mile: 0.0
        t.transmission.gear = 10
        t.velocity_mps = 26.8  # ~60 mph
        t.throttle = 0.35
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph == pytest.approx(60.0, abs=1.0)
        assert driving._cruise_working_mph == pytest.approx(t.speed_mph, abs=0.5)
        for _ in range(60 * 15):
            driving.update(1 / 60)
        assert driving._cruise_mph is not None
        assert abs(t.speed_mph - 60.0) < 5.0
        assert not t.over_revving
    finally:
        app.shutdown()
