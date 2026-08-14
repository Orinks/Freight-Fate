"""Cruise-control, ACC, hazard timing, and real-weather driving tests."""

import pygame
import pytest
from driving_feature_helpers import (
    facility_street_chain,
    key_event,
    open_limits,
    quiet_trip,
    release_air_brakes,
    roll_to,
    short_block_street_chain,
    start_drive,
)
from speech_capture import speech_stub

from freight_fate.states.driving import (
    ACC_LIMIT_OFFSET_MPH,
    PCC_CREST_SAG_MPH,
)

# -- cruise control -------------------------------------------------------------


@pytest.mark.smoke
def test_cruise_control_holds_the_set_speed(monkeypatch):
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.zones = []
        driving.trip.traffic_pressures = []
        driving.trip.curves = []  # a real bend rightly cancels cruise; not this test
        driving._destination_exit_taken = True  # isolate cruise from exit setup
        open_limits(driving)  # isolate hold from the limit cap
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))  # engine on
        t.cargo_kg = 0.0
        t.grade = 0.0
        t.transmission.gear = 10
        t.velocity_mps = 26.8  # ~60 mph
        t.throttle = 0.35
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph == pytest.approx(60.0, abs=1.0)
        for _ in range(60 * 15):  # 15 seconds, no keys held
            driving.update(1 / 60)
        assert driving._cruise_mph is not None
        assert abs(t.speed_mph - 60.0) < 5.0
    finally:
        app.shutdown()


def test_shift_k_resumes_the_braked_away_cruise_speed(monkeypatch):
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    spoken = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.zones = []
        driving.trip.traffic_pressures = []
        driving.trip.curves = []
        driving._destination_exit_taken = True
        open_limits(driving)
        monkeypatch.setattr(app.ctx, "say", lambda text, **k: spoken.append(text))
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))
        t.transmission.gear = 10
        t.velocity_mps = 26.8  # ~60 mph
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph == pytest.approx(60.0, abs=1.0)
        set_speed = driving._speed_control_target_mph

        # The player brakes: the session cancels but the speed is remembered.
        driving._cancel_cruise()
        assert driving._cruise_mph is None
        assert driving._resume_target_mph == pytest.approx(set_speed, abs=1.0)

        # Shift+K re-arms at the remembered target; the per-frame helper
        # engages as soon as the truck is rolling and off the brakes.
        shift_k = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k, mod=pygame.KMOD_LSHIFT)
        t.velocity_mps = 22.0  # slowed, still rolling
        driving.handle_event(shift_k)
        assert driving._speed_control_armed
        assert driving._speed_control_target_mph == pytest.approx(set_speed, abs=1.0)
        assert any("Resuming automatic speed control" in s for s in spoken)
        driving.update(1 / 60)
        assert driving._cruise_mph == pytest.approx(set_speed, abs=1.0)
    finally:
        app.shutdown()


def test_parked_cruise_button_latches_high_idle(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.vehicle import HIGH_IDLE_DEFAULT_RPM, HIGH_IDLE_STEP_RPM

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    spoken = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say", lambda text, **k: spoken.append(text))
        t = driving.truck
        t.set_air_ready(parking_brake=True)
        t.start_engine()
        t.velocity_mps = 0.0

        driving.handle_event(key_event(pygame.K_k))  # parked: fast-idle switch
        assert t.high_idle_rpm == HIGH_IDLE_DEFAULT_RPM
        assert driving._cruise_mph is None  # not a cruise session
        assert any("High idle" in text for text in spoken)

        driving.handle_event(key_event(pygame.K_KP_PLUS))
        assert t.high_idle_rpm == HIGH_IDLE_DEFAULT_RPM + HIGH_IDLE_STEP_RPM
        driving.handle_event(key_event(pygame.K_KP_MINUS))
        assert t.high_idle_rpm == HIGH_IDLE_DEFAULT_RPM

        driving.handle_event(key_event(pygame.K_k))  # press again: off
        assert t.high_idle_rpm is None
        assert any("High idle off" in text for text in spoken)

        # Latch it, then release the parking brake: the sim cancels it.
        driving.handle_event(key_event(pygame.K_k))
        assert t.high_idle_rpm is not None
        t.release_parking_brake()
        driving.update(1 / 60)
        assert t.high_idle_rpm is None
    finally:
        app.shutdown()


def test_players_brake_press_cancels_cruise(monkeypatch):
    from freight_fate.app import App

    class Keys:
        pressed = set()

        def __getitem__(self, key):
            return key in self.pressed

    keys = Keys()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: keys)

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.zones = []
        open_limits(driving)
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))  # engine on
        t.cargo_kg = 0.0
        t.grade = 0.0
        t.transmission.gear = 10
        t.velocity_mps = 26.8  # ~60 mph
        t.throttle = 0.35
        driving.handle_event(key_event(pygame.K_k))  # engage cruise
        assert driving._cruise_mph is not None

        # The first tap of the service brake drops cruise, like a real truck.
        keys.pressed = {pygame.K_DOWN}
        driving.update(1 / 60)
        assert driving._cruise_mph is None

        # Releasing the brake must not bring it back.
        keys.pressed = set()
        for _ in range(30):
            driving.update(1 / 60)
        assert driving._cruise_mph is None
    finally:
        app.shutdown()


def test_cruise_does_not_rev_engine_when_clutch_is_depressed(monkeypatch):
    from freight_fate.app import App

    class Keys:
        pressed = set()

        def __getitem__(self, key):
            return key in self.pressed

    keys = Keys()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: keys)

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.zones = []
        open_limits(driving)
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))  # engine on
        t.cargo_kg = 0.0
        # A flat road for the whole run, not just the first frame: the trip
        # re-reads the grade every update, and this test needs cruise to be
        # genuinely holding throttle. On a downgrade it correctly holds none.
        driving.trip.grade_at = lambda mile: 0.0
        t.grade = 0.0
        app.ctx.settings.automatic_transmission = False
        t.transmission.automatic = False  # the bug is manual-only
        t.transmission.gear = 10
        t.velocity_mps = 26.8  # ~60 mph
        t.throttle = 0.35
        driving.handle_event(key_event(pygame.K_k))  # engage cruise
        # Let cruise settle to its holding throttle with the clutch out.
        for _ in range(30):
            driving.update(1 / 60)
        held_throttle = driving._cruise_throttle
        assert held_throttle > 0.05
        assert t.rpm < t.specs.max_rpm * 0.9

        # Depress the clutch to shift: throttle must cut to idle, not free-rev.
        keys.pressed = {pygame.K_LSHIFT}
        for _ in range(30):  # ~0.5 s clutch in
            driving.update(1 / 60)
            assert t.throttle == 0.0
        assert driving._cruise_mph is not None  # cruise stays engaged
        assert t.rpm < t.specs.max_rpm * 0.6  # engine settled toward idle

        # Release the clutch: cruise ramps the throttle back up toward the hold.
        keys.pressed = set()
        driving.update(1 / 60)
        assert t.throttle > 0.0
        for _ in range(30):
            driving.update(1 / 60)
        assert t.throttle > held_throttle * 0.5
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_cruise_set_point_adjusts_with_plus_and_minus():
    from freight_fate.app import App
    from freight_fate.states.driving import CRUISE_MAX_MPH, CRUISE_STEP_MPH

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        open_limits(driving)  # isolate from the limit cap
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8  # ~60 mph
        driving.handle_event(key_event(pygame.K_k))
        base = driving._cruise_mph
        # _engage_cruise rounds the captured road speed (~59.95) to the whole
        # mph the player actually hears, so base lands exactly on the fives
        # grid here -- a plain tap steps a full CRUISE_STEP_MPH.
        assert base == pytest.approx(60.0)

        driving.handle_event(key_event(pygame.K_EQUALS))  # + raises by a step
        assert driving._cruise_mph == pytest.approx(base + CRUISE_STEP_MPH)
        driving.handle_event(key_event(pygame.K_MINUS))  # - lowers it back
        assert driving._cruise_mph == pytest.approx(base)
        driving.handle_event(key_event(pygame.K_PLUS, "+"))
        assert driving._cruise_mph == pytest.approx(base + CRUISE_STEP_MPH)
        driving.handle_event(key_event(pygame.K_KP_MINUS, "-"))
        assert driving._cruise_mph == pytest.approx(base)

        for _ in range(20):  # clamps at the max
            driving.handle_event(key_event(pygame.K_EQUALS))
        assert driving._cruise_mph == pytest.approx(CRUISE_MAX_MPH)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_cruise_refuses_to_engage_in_a_facility_zone(monkeypatch):
    from freight_fate.app import App

    app = App()
    said = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say", speech_stub(said))
        # With the speed keeper turned off, the original explanation applies:
        # cruise must not engage on a low-speed facility access road.
        app.ctx.settings.speed_keeper = False
        driving.trip.speed_limit_at = lambda mile: (25.0, "facility access road")
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 4
        driving.truck.velocity_mps = 10.0  # ~22 mph, above the floor
        driving.handle_event(key_event(pygame.K_k))

        assert driving._cruise_mph is None
        assert driving._keeper_mph is None
        assert any("not available" in s and "facility access road" in s for s in said)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_speed_keeper_holds_through_a_facility_zone(monkeypatch):
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    said = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say", speech_stub(said))
        driving.trip.speed_limit_at = lambda mile: (15.0, "facility access road")
        driving.trip.traffic_context = lambda: None
        driving.handle_event(key_event(pygame.K_e))
        t = driving.truck
        t.cargo_kg = 0.0
        t.grade = 0.0
        t.transmission.gear = 3
        t.velocity_mps = 4.5  # ~10 mph, no need to hold the accelerator
        driving.handle_event(key_event(pygame.K_k))

        assert driving._cruise_mph is None
        assert driving._keeper_mph == pytest.approx(10.0, abs=0.5)
        assert any("Speed keeper holding" in s for s in said)
        for _ in range(60 * 10):  # ten seconds, no keys held
            driving.update(1 / 60)
        assert driving._keeper_mph is not None
        assert abs(t.speed_mph - 10.0) < 4.0
    finally:
        app.shutdown()


def test_speed_keeper_cancels_on_braking(monkeypatch):
    from freight_fate.app import App

    class Keys:
        pressed = set()

        def __getitem__(self, key):
            return key in self.pressed

    keys = Keys()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: keys)

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        driving.trip.speed_limit_at = lambda mile: (15.0, "facility access road")
        driving.trip.traffic_context = lambda: None
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 3
        driving.truck.velocity_mps = 4.5
        driving.handle_event(key_event(pygame.K_k))
        assert driving._keeper_mph is not None

        keys.pressed = {pygame.K_DOWN}  # brake
        driving.update(1 / 60)
        assert driving._keeper_mph is None
        assert not driving._speed_control_armed
        assert any("Speed keeper canceled" in s for s in events)

        driving.trip.speed_limit_at = lambda mile: (55.0, None)
        keys.pressed = set()
        driving.update(1 / 60)
        assert driving._cruise_mph is None  # braking disarmed it; no surprise restart
    finally:
        app.shutdown()


def test_speed_keeper_switches_to_cruise_on_the_open_road(monkeypatch):
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        zone = {"limit": 15.0, "reason": "facility access road"}
        driving.trip.speed_limit_at = lambda mile: (zone["limit"], zone["reason"])
        driving.trip.traffic_context = lambda: None
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 3
        driving.truck.velocity_mps = 4.5
        driving.handle_event(key_event(pygame.K_k))
        assert driving._keeper_mph is not None

        zone.update(limit=55.0, reason=None)  # the access stretch ends
        driving.update(1 / 60)
        assert driving._keeper_mph is None
        assert driving._cruise_mph == pytest.approx(55.0)
        assert driving._speed_control_armed
        assert any("Open road. Adaptive cruise resuming" in s for s in events)
    finally:
        app.shutdown()


def _keeper_on_a_street_chain(app, monkeypatch, *, start_before_mi: float):
    """A keeper session holding the street limit, rolling up to the corner."""
    driving = start_drive(app)
    quiet_trip(driving)
    trip = facility_street_chain(driving)
    cue = next(c for c in trip.navigation_cues if c.key.startswith("local:turn:"))
    t = driving.truck
    driving.handle_event(key_event(pygame.K_e))
    t.cargo_kg = 0.0
    t.grade = 0.0
    t.transmission.gear = 5
    t.velocity_mps = 25.0 / 2.23694
    trip.position_mi = cue.at_mi - start_before_mi
    release_air_brakes(driving)
    driving.handle_event(key_event(pygame.K_k))
    assert driving._keeper_mph == pytest.approx(25.0, abs=0.5)
    return driving, cue


def test_speed_keeper_is_under_the_turn_speed_before_the_corner(monkeypatch):
    # The tester report: the keeper held the street's 25 into a corner that
    # advises 20, so the corner was taken over its speed and the safe
    # turnaround was charged. It now sheds the speed on the approach.
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    try:
        driving, cue = _keeper_on_a_street_chain(app, monkeypatch, start_before_mi=0.25)
        advise = driving._turn_speed_mph(cue)
        assert advise == 20.0  # a 25 mph street, capped at what a trailer turns

        trace = roll_to(driving, cue.at_mi)
        # Under the number BEFORE the corner, not arriving at it on the spot:
        # the settling tail is what the tester was missing.
        under = [mile for mile, mph in trace if mph <= advise]
        assert under, "the keeper never reached the corner speed"
        assert cue.at_mi - min(under) >= 0.01
        assert driving.truck.speed_mph <= advise
        # And the corner is made without the loop-back, with the session intact.
        driving.update(1 / 60)
        assert driving._turn_miss_count == 0
        assert driving._keeper_mph is not None
    finally:
        app.shutdown()


def test_speed_keeper_holds_the_street_limit_until_the_corner_is_close(monkeypatch):
    # The other half of the fix: easing early enough must not mean crawling a
    # whole block. Well outside the ease window there is nothing to slow for.
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    try:
        driving, cue = _keeper_on_a_street_chain(app, monkeypatch, start_before_mi=0.4)
        assert driving._keeper_speed_ahead() is None
        for _ in range(60 * 5):
            driving.update(1 / 60)
            assert driving.truck.brake < 0.02  # below where the brake even sounds
        assert driving.truck.speed_mph == pytest.approx(25.0, abs=1.0)
    finally:
        app.shutdown()


def test_speed_keeper_makes_the_second_corner_of_a_short_block(monkeypatch):
    # The rest of the tester report: turns coming up really quickly. The
    # keeper held the corner it was already easing for through that corner's
    # whole tail, and a city block is shorter than the tail -- so the 15 mph
    # service way one block on was invisible until the truck was on top of it,
    # and the keeper drove into the second corner at the first corner's speed.
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        trip, first, second = short_block_street_chain(driving)
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))
        t.cargo_kg = 0.0
        t.grade = 0.0
        t.transmission.gear = 5
        t.velocity_mps = 25.0 / 2.23694
        trip.position_mi = first.at_mi - 0.25
        release_air_brakes(driving)
        driving.handle_event(key_event(pygame.K_k))
        assert driving._keeper_mph == pytest.approx(25.0, abs=0.5)
        assert driving._turn_speed_mph(first) == 20.0
        assert driving._turn_speed_mph(second) == 15.0
        assert second.at_mi - first.at_mi < 0.15  # inside the first corner's tail

        roll_to(driving, first.at_mi)
        assert t.speed_mph <= 20.0  # the first corner, as before
        # The second corner is the one the old planner could not see: while
        # there is still road to shed on, the keeper has to be aiming at ITS
        # number rather than still holding the first corner's.
        roll_to(driving, second.at_mi - 0.03)
        # The label depends on which source latched first -- the corner's own
        # advise or the service way's posted 15 -- and both are the truth.
        # The number is the behavior under test.
        ahead = driving._keeper_speed_ahead()
        assert ahead is not None and ahead[0] == 15.0
        trace = roll_to(driving, second.at_mi)
        under = [mile for mile, mph in trace if mph <= 15.0]
        assert under, "the keeper never reached the service road's corner speed"
        assert t.speed_mph <= 15.0

        driving.update(1 / 60)
        assert driving._turn_miss_count == 0
        assert driving._keeper_mph is not None
    finally:
        app.shutdown()


def test_speed_keeper_eases_for_a_lower_posted_limit_and_says_so(monkeypatch):
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        driving.trip.traffic_context = lambda: None
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))
        t.cargo_kg = 0.0
        t.grade = 0.0
        t.transmission.gear = 5
        t.velocity_mps = 25.0 / 2.23694
        # Just inside the window the keeper says it needs for this drop, which
        # is what the window is a promise about.
        drop_mi = driving.trip.position_mi + 0.9 * driving._keeper_ease_mi(
            15.0, driving.trip.effective_time_scale
        )
        driving.trip.speed_limit_at = lambda mile: (
            (15.0, "facility access road") if mile >= drop_mi else (25.0, "facility access road")
        )
        driving.handle_event(key_event(pygame.K_k))
        assert driving._keeper_mph == pytest.approx(25.0, abs=0.5)

        for _ in range(60 * 30):
            driving.update(1 / 60)
            if driving.trip.position_mi >= drop_mi:
                break
        # Down to the new number by the time the sign is under the wheels, said
        # once for that number rather than once a frame.
        assert any(
            e == "Posted limit lower; speed keeper easing to 15 miles per hour." for e in events
        )
        assert t.speed_mph <= 15.0
        assert sum("speed keeper easing to 15" in e for e in events) == 1
        # The keeper's own line already named the number; it must feed the
        # trip's pre-announce set so the plain arrival "Speed limit reduced
        # to 15" does not repeat it a moment later (owner's live playtest,
        # 2026-08-12, on the plain posted-drop case this hook covers).
        assert 15.0 in driving.trip._limit_drop_preannounced
    finally:
        app.shutdown()


def test_speed_keeper_takes_the_next_street_up_to_its_posted_number(monkeypatch):
    # The tester report: the keeper "sometimes doesn't hold speeds on access
    # roads". A facility approach zones every street at its own baked number,
    # and the keeper's number was frozen at whatever it engaged with, capped by
    # the limit under the wheels -- so a session started on a 15 mph service
    # way carried that crawl over every 25 mph street after it, for the rest of
    # the chain, while the zone entry announced 25 and nothing on the wheel
    # could raise it.
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        street = {"limit": 15.0}
        driving.trip.speed_limit_at = lambda mile: (street["limit"], "facility access road")
        driving.trip.traffic_context = lambda: None
        driving.trip.grade_at = lambda mile: 0.0
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))
        t.cargo_kg = 0.0
        t.grade = 0.0
        t.transmission.gear = 4
        t.velocity_mps = 15.0 / 2.23694
        release_air_brakes(driving)
        driving.handle_event(key_event(pygame.K_k))
        assert driving._keeper_mph == pytest.approx(15.0, abs=0.5)

        street["limit"] = 25.0  # the service way ends and a named street begins
        driving.update(1 / 60)
        assert driving._keeper_mph == pytest.approx(25.0)
        # An assist that speeds the truck up on its own says the new number:
        # the zone entry announced the law, not what the truck will do.
        assert any(
            e == "Speed keeper holding 25 miles per hour through the facility access road zone."
            for e in events
        )
        for _ in range(60 * 40):
            driving.update(1 / 60)
        assert t.speed_mph > 21.0, t.speed_mph
        # Said once for the street, not once a frame.
        assert sum("Speed keeper holding 25" in e for e in events) == 1

        # A lower street is still simply obeyed, without re-arming the number
        # or announcing anything: coming down was never the broken direction.
        before = len(events)
        street["limit"] = 15.0
        driving.update(1 / 60)
        assert driving._keeper_mph == pytest.approx(25.0)  # the number it was handed
        assert not [e for e in events[before:] if "Speed keeper holding" in e]
    finally:
        app.shutdown()


def test_speed_keeper_ease_window_buys_only_the_road_the_shed_costs():
    # The other half of the same report. The window is a budget of real
    # seconds, but it was priced at the speed the truck STARTS from for every
    # one of them -- and the truck is slowing through most of them. On a
    # 25-to-15 drop that bought about 40 percent more road than the shed
    # costs, and since 7ff22b6e the eased number is a held floor, so the
    # surplus is crawled at the low number rather than re-planned.
    from freight_fate.app import App
    from freight_fate.states.driving_core import MPH_PER_MPS
    from freight_fate.states.driving_speed_control import (
        KEEPER_EASE_DECEL_MPS2,
        KEEPER_EASE_REAL_S,
        KEEPER_SETTLE_REAL_S,
    )

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.velocity_mps = 25.0 / 2.23694
        speed = driving.truck.speed_mph

        reaction_mi = (KEEPER_EASE_REAL_S + KEEPER_SETTLE_REAL_S) * speed / 3600.0
        window = driving._keeper_ease_mi(15.0, 1.0)
        shed_s = (speed - 15.0) / MPH_PER_MPS / KEEPER_EASE_DECEL_MPS2
        # Exactly what the shed costs: its seconds at the mean of the two
        # speeds, plus the settling tail down at the new number.
        shed_mi = (shed_s * (speed + 15.0) / 2.0 + KEEPER_SETTLE_REAL_S * 15.0) / 3600.0
        assert shed_mi > reaction_mi  # a drop big enough to be shed-bound
        assert window == pytest.approx(shed_mi)
        # And strictly less than charging every budgeted second at the speed
        # the truck came in at, which is what it used to claim.
        entry_sized_mi = (shed_s + KEEPER_SETTLE_REAL_S) * speed / 3600.0
        assert window < entry_sized_mi * 0.9

        # The reaction budget underneath is untouched. Those seconds are spent
        # before any slowing starts, so they still cost road at today's speed
        # -- a corner-sized drop, and no drop at all, are both as they were.
        assert driving._keeper_ease_mi(20.0, 1.0) == pytest.approx(reaction_mi)
        assert driving._keeper_ease_mi(speed + 5.0, 1.0) == pytest.approx(reaction_mi)
    finally:
        app.shutdown()


def test_speed_keeper_ignores_a_slower_vehicle_miles_up_the_road(monkeypatch):
    # The keeper matched any slower vehicle the traffic bubble could see --
    # two and a half miles of it -- with no test on the gap at all, so a car
    # doing 35 in a 45 work zone put the truck at 35 from the far end of the
    # zone, silently. It now waits until there is a reason to shed for it, and
    # still creeps behind a queue that is genuinely there.
    from freight_fate.app import App
    from freight_fate.sim.trip_models import NPCVehicle, TrafficContext

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.speed_limit_at = lambda mile: (45.0, "construction")
        driving.trip.grade_at = lambda mile: 0.0
        lead = {"gap_mi": 2.2, "speed_mph": 35.0}

        def _gap() -> float:
            # A stopped lead is a fixed point in space: the gap must close as
            # the truck rolls toward it, or the "creep to the queue and stop"
            # contract is untestable (a frozen 105-foot gap earns a permanent
            # 2 mph creep, correctly).
            if "stop_at_mi" in lead:
                return max(0.0, lead["stop_at_mi"] - driving.trip.position_mi)
            return lead["gap_mi"]

        driving.trip.traffic_context = lambda: TrafficContext(
            lead=NPCVehicle(
                key="lead",
                position_mi=driving.trip.position_mi + _gap(),
                speed_mph=lead["speed_mph"],
                target_speed_mph=lead["speed_mph"],
                relative_lane=0,
                behavior="slow_car",
            ),
            gap_mi=_gap(),
            closing_mph=10.0,
        )
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))
        t.cargo_kg = 0.0
        t.grade = 0.0
        t.transmission.gear = 8
        t.velocity_mps = 45.0 / 2.23694
        release_air_brakes(driving)
        driving.handle_event(key_event(pygame.K_k))
        assert driving._keeper_mph == pytest.approx(45.0, abs=0.5)
        # Well outside anything the keeper has a reason to shed for.
        assert lead["gap_mi"] > driving._keeper_ease_mi(
            lead["speed_mph"], driving.trip.effective_time_scale
        )

        for _ in range(60 * 20):
            driving.update(1 / 60)
            # Matching the lead outright would have parked the truck at 35
            # within a few seconds and held it there for the whole zone.
            assert t.speed_mph > 37.0, t.speed_mph

        # Right behind it, the queue rule still applies all the way to a stop.
        lead.update(speed_mph=0.0)
        lead["stop_at_mi"] = driving.trip.position_mi + 0.02
        for _ in range(60 * 60):
            driving.update(1 / 60)
            if t.speed_mph < 1.0:
                break
        assert t.speed_mph < 1.0, t.speed_mph
    finally:
        app.shutdown()


def test_speed_keeper_needs_the_truck_rolling(monkeypatch):
    from freight_fate.app import App

    app = App()
    said = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say", speech_stub(said))
        driving.trip.speed_limit_at = lambda mile: (15.0, "facility access road")
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.velocity_mps = 0.0
        driving.handle_event(key_event(pygame.K_k))

        assert driving._keeper_mph is None
        assert any("needs the engine running and the truck rolling" in s for s in said)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_cruise_adjust_is_inert_when_cruise_is_off(monkeypatch):
    from freight_fate.app import App

    app = App()
    said = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say", speech_stub(said))
        driving.handle_event(key_event(pygame.K_e))
        assert driving._cruise_mph is None
        driving.handle_event(key_event(pygame.K_EQUALS))
        assert driving._cruise_mph is None  # nothing to adjust
        assert any("off" in s.lower() for s in said)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_air_ready_cue_does_not_repeat_on_compressor_cycling(monkeypatch):
    from freight_fate.app import App

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        t = driving.truck
        t.parking_brake = True  # cue only fires while set
        t.air_pressure_psi = t.specs.air_governor_cut_out_psi  # charged
        driving._air_ready_said = True  # already announced

        def ready_count():
            return sum("Air pressure ready" in e for e in events)

        # Routine compressor cycling dips below the release threshold (which sits
        # at the cut-in pressure) but stays well above low air. Must not re-announce.
        for _ in range(3):
            t.air_pressure_psi = t.specs.air_governor_cut_in_psi - 5
            driving._update_air_brake_announcements(True, False, False)
            t.air_pressure_psi = t.specs.air_governor_cut_out_psi
            driving._update_air_brake_announcements(False, False, False)
        assert ready_count() == 0

        # A genuine depletion to low air, then recovery, re-announces exactly once.
        t.air_pressure_psi = t.specs.air_low_warning_psi - 5
        driving._update_air_brake_announcements(False, False, False)
        t.air_pressure_psi = t.specs.air_governor_cut_out_psi
        driving._update_air_brake_announcements(False, True, False)
        assert ready_count() == 1
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_automatic_shift_uses_shift_cue_not_brake_air(monkeypatch):
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    app = App()
    played = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())
        monkeypatch.setattr(
            app.ctx.audio, "play", lambda key, volume=1.0, pan=0.0: played.append((key, volume))
        )
        driving.truck.start_engine()
        driving.truck.transmission.gear = 3
        driving.truck.velocity_mps = 5.0

        driving.update(0.0)

        # The shift cue is the auto-shift bank when the licensed cuts are
        # installed (volume carries a small per-trigger jitter around 0.65),
        # the classic gear_shift on a clean clone.
        shifts = [
            (key, vol)
            for key, vol in played
            if key == "vehicle/gear_shift" or key.startswith("vehicle/shift_auto")
        ]
        assert shifts and all(0.5 <= vol <= 0.8 for _key, vol in shifts)
        assert all(key != "vehicle/brake_air" for key, _volume in played)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_cruise_control_requires_road_speed_and_cancels_on_hazard():
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        # parked: refuses to engage
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is None
        # engaged at speed, a hazard hands control back to the driver
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None
        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 4.0})
        driving._handle_trip_event(hazard)
        assert driving._cruise_mph is None
    finally:
        app.shutdown()


def test_hazard_announces_speed_control_cancellation_once(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))

        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 4.0})
        driving._handle_trip_event(hazard)

        assert not driving._speed_control_armed
        assert events[-1].startswith("Brake now!")
        assert events[-1].count("Automatic speed control canceled.") == 1
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_dodgeable_hazard_leaves_cruise_armed_through_the_lane_change_dodge():
    """Shane's report, 2026-08-14: with adaptive cruise on, dodging a
    dodgeable hazard by changing lanes killed the whole session outright --
    not just easing off for the lane being left, which is the narrower bug
    3cbdcffb fixed. Only braking, the driver's own or the automatic brake
    taking over, may cancel cruise; a lane change that answers the hazard
    must not."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import LANE_TAP_CHANGE_S

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.curves = []
        open_limits(driving)
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8  # ~60 mph
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None
        assert driving.lane.lane == 0

        hazard = TripEvent(
            TripEventKind.HAZARD, "A deer is in the road.", {"name": "deer", "dodgeable": True}
        )
        driving._handle_trip_event(hazard)
        # A dodgeable hazard alone never hands the pedal back -- that is what
        # the lane change below is for.
        assert driving._cruise_mph is not None
        assert driving._hazard_deadline is not None

        driving._tap_lane_change(1)  # dodge into the open lane
        for _ in range(int(LANE_TAP_CHANGE_S * 60) + 5):
            driving.update(1 / 60)
            assert driving._cruise_mph is not None  # never drops mid-maneuver

        assert driving.lane.lane == 1
        assert driving._lane_change_target is None
        assert driving._cruise_mph is not None
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_dodgeable_hazard_leaves_the_keeper_armed_through_the_lane_change_dodge():
    """The speed keeper shares ``_disarm_speed_control`` with cruise, so the
    same dodge that must not kill adaptive cruise must not kill the keeper
    either."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import LANE_TAP_CHANGE_S

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.curves = []
        # A real construction zone the whole way, so the keeper holds itself
        # rather than handing straight back to cruise the moment the road
        # under the wheels reads as open (that switch is _update_keeper's own
        # job, not this test's).
        driving.trip.speed_limit_at = lambda mile: (25.0, "construction")
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 6
        driving.truck.velocity_mps = 11.2  # ~25 mph
        driving._engage_keeper(30.0, "construction", target_mph=25.0, announce=False)
        assert driving._keeper_mph is not None
        assert driving.lane.lane == 0

        hazard = TripEvent(
            TripEventKind.HAZARD, "A deer is in the road.", {"name": "deer", "dodgeable": True}
        )
        driving._handle_trip_event(hazard)
        assert driving._keeper_mph is not None  # announcement alone spares it
        assert driving._hazard_deadline is not None

        driving._tap_lane_change(1)  # dodge into the open lane
        for _ in range(int(LANE_TAP_CHANGE_S * 60) + 5):
            driving.update(1 / 60)
            assert driving._keeper_mph is not None  # never drops mid-maneuver

        assert driving.lane.lane == 1
        assert driving._lane_change_target is None
        assert driving._keeper_mph is not None
    finally:
        app.shutdown()


def test_driver_braking_still_cancels_cruise_during_a_dodge(monkeypatch):
    """The other half of Shane's contract: a lane change never cancels
    cruise, but the driver's own brake still does, mid-dodge or not."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    class DownKeys:
        def __getitem__(self, key):
            return key == pygame.K_DOWN

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.curves = []
        open_limits(driving)
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None

        hazard = TripEvent(
            TripEventKind.HAZARD, "A deer is in the road.", {"name": "deer", "dodgeable": True}
        )
        driving._handle_trip_event(hazard)
        driving._tap_lane_change(1)
        assert driving._cruise_mph is not None  # still armed, mid-dodge

        monkeypatch.setattr(pygame.key, "get_pressed", lambda: DownKeys())
        driving.update(1 / 60)
        assert driving._cruise_mph is None
    finally:
        app.shutdown()


def test_an_ignored_dodgeable_hazard_still_ends_cruise_at_the_deadline(monkeypatch):
    """Reviewer-caught regression on the announce-time fix above: with the
    automatic brake turned OFF, a dodgeable hazard the driver never answers
    -- no dodge, no brake -- used to ride cruise straight into the collision
    with the session still showing armed. Only braking may cancel cruise,
    but the deadline lapsing un-dodged IS the collision, which is the third
    way the promise ends -- whatever the AEB setting."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.curves = []
        open_limits(driving)
        driving.ctx.settings.automatic_emergency_braking = False
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None

        hazard = TripEvent(
            TripEventKind.HAZARD, "A deer is in the road.", {"name": "deer", "dodgeable": True}
        )
        driving._handle_trip_event(hazard)
        assert driving._cruise_mph is not None  # the hazard alone still spares it
        assert driving._hazard_deadline is not None
        damage_before = driving.truck.damage_pct

        for _ in range(2000):
            driving.update(1 / 60)
            if driving._hazard_deadline is None:
                break
        else:
            raise AssertionError("the hazard deadline never lapsed")

        assert driving.truck.damage_pct > damage_before  # the collision applied
        assert driving._cruise_mph is None
        assert not driving._speed_control_armed
    finally:
        app.shutdown()


def test_metric_cruise_minimum_refusal_uses_metric_units(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        driving = start_drive(app)
        quiet_trip(driving)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is None
        assert "kilometers per hour" in spoken[-1]
        assert "miles per hour" not in spoken[-1]
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_follows_npc_traffic(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import NPCVehicle

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        open_limits(driving)  # isolate following from the limit cap
        driving.trip.traffic_manager.vehicles = [
            NPCVehicle("npc:acc", driving.trip.position_mi + 0.08, 44.0, 44.0, 0, "braking_traffic")
        ]
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0
        driving.truck.throttle = 0.9
        driving.handle_event(key_event(pygame.K_k))
        driving.update(1 / 60)

        assert driving._cruise_mph is not None
        assert driving._acc_following
        assert driving.truck.throttle < 0.9
        assert driving.truck.brake > 0.0
        assert "Traffic ahead, adaptive cruise reducing speed." in events
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_ignores_the_lane_being_left_mid_change(monkeypatch):
    """Tester report: with an automated lane change underway, cruise kept
    following the slow lead in the lane being LEFT for the whole maneuver --
    "I'm changing lanes, fucking drive." Mid-change, lead selection follows
    the destination lane, so a lead still sitting in the origin lane no
    longer caps the target."""
    from freight_fate.app import App
    from freight_fate.sim.trip import NPCVehicle

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        open_limits(driving)
        driving.trip.traffic_manager.vehicles = [
            NPCVehicle(
                "npc:origin", driving.trip.position_mi + 0.08, 44.0, 44.0, 0, "braking_traffic"
            )
        ]
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0  # ~65 mph
        driving.handle_event(key_event(pygame.K_k))
        assert driving.lane.lane == 0
        driving._tap_lane_change(1)  # start the pass into the left lane
        assert driving._lane_change_target == 1

        for _ in range(10):
            driving.update(1 / 60)

        assert driving._lane_change_target == 1  # the change is still underway
        assert not driving._acc_following
        assert driving.truck.brake == 0.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_follows_the_lane_being_entered_mid_change(monkeypatch):
    """The other half of the fix: a slow lead already sitting in the
    DESTINATION lane must still cap the target mid-change. Lead selection
    follows the lane being entered -- it does not simply stop following."""
    from freight_fate.app import App
    from freight_fate.sim.trip import NPCVehicle

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        open_limits(driving)
        driving.trip.traffic_manager.vehicles = [
            NPCVehicle(
                "npc:dest",
                driving.trip.position_mi + 0.08,
                44.0,
                44.0,
                -1,
                "braking_traffic",
                lane=1,
            )
        ]
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0
        driving.handle_event(key_event(pygame.K_k))
        assert driving.lane.lane == 0
        driving._tap_lane_change(1)
        assert driving._lane_change_target == 1

        for _ in range(10):
            driving.update(1 / 60)

        assert driving._lane_change_target == 1  # the change is still underway
        assert driving._acc_following
        assert "Traffic ahead, adaptive cruise reducing speed." in events
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_reverts_to_origin_lane_when_a_change_is_aborted(monkeypatch):
    """No latching: drifting back out of a change must hand lead selection
    back to the origin lane the instant the lane layer stops reporting a
    change, restoring the origin-lane lead's cap."""
    from freight_fate.app import App
    from freight_fate.sim.trip import NPCVehicle

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        open_limits(driving)
        driving.trip.traffic_manager.vehicles = [
            NPCVehicle(
                "npc:origin", driving.trip.position_mi + 0.08, 44.0, 44.0, 0, "braking_traffic"
            )
        ]
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0
        driving.handle_event(key_event(pygame.K_k))
        driving._tap_lane_change(1)

        for _ in range(10):
            driving.update(1 / 60)
        assert not driving._acc_following  # destination lane is clear mid-change

        driving._lane_change_target = None  # the driver drifted back -- aborted
        for _ in range(10):
            driving.update(1 / 60)

        assert driving.lane.lane == 0  # still in the origin lane
        assert driving._acc_following  # following the origin-lane lead again
        assert "Traffic ahead, adaptive cruise reducing speed." in events
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_ignores_distant_slower_traffic(monkeypatch):
    """A slower vehicle far out in the traffic bubble must not drag cruise down:
    matching a distant lead's speed parked the truck at the bubble edge, where
    the lead popped in and out of range and re-announced itself every lap."""
    from freight_fate.app import App
    from freight_fate.sim.trip import NPCVehicle

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        open_limits(driving)
        driving.trip.traffic_manager.vehicles = [
            NPCVehicle("npc:far", driving.trip.position_mi + 2.3, 30.0, 30.0, 0, "slow_car")
        ]
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8  # ~60 mph
        driving.handle_event(key_event(pygame.K_k))
        driving.update(1 / 60)

        assert not driving._acc_following
        assert driving.truck.brake == 0.0
        assert "Traffic ahead, adaptive cruise reducing speed." not in events
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_follow_cue_does_not_repeat_within_the_cooldown(monkeypatch):
    """If following flaps (the lead leaves the bubble and comes back), the
    spoken cue must not fire again inside the quiet window."""
    from freight_fate.app import App
    from freight_fate.sim.trip import NPCVehicle

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        open_limits(driving)
        # Flat ground: this test pins the follow-cue cooldown, not descent
        # physics. The helper route opens on a real 8.6 percent downhill,
        # where descent control engages the jake, the automatic starts a
        # downshift, and cruise rightly skips traffic decisions mid-shift --
        # on exactly the frame this test asserts.
        driving.trip.grade_at = lambda mile: 0.0

        # The lead must also sit clearly INSIDE the follow gap: at the bubble
        # edge the approach-control formula is deliberately indifferent (a
        # distant lead must not drag the target down), and "following" there
        # flips on hundredths of a mile per hour of truck state.
        def slow_lead():
            return [
                NPCVehicle("npc:acc", driving.trip.position_mi + 0.04, 44.0, 44.0, 0, "slow_car")
            ]

        driving.trip.traffic_manager.vehicles = slow_lead()
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0  # ~65 mph
        driving.handle_event(key_event(pygame.K_k))

        def cue_count():
            return events.count("Traffic ahead, adaptive cruise reducing speed.")

        driving.update(1 / 60)
        assert driving._acc_following
        assert cue_count() == 1

        driving.trip.traffic_manager.vehicles = []  # lead drifts out of the bubble
        driving.update(1 / 60)
        assert not driving._acc_following

        driving.trip.traffic_manager.vehicles = slow_lead()  # and back in
        driving.update(1 / 60)
        assert driving._acc_following  # follows again, but quietly
        assert cue_count() == 1
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_caps_at_posted_limit(monkeypatch):
    from freight_fate.app import App

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        # A posted limit well below the held set speed: predictive ACC must ease
        # off rather than carry the driver over the limit into a speeding strike.
        driving.trip.speed_limit_at = lambda mile: (45.0, None)
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0  # ~65 mph
        driving.truck.throttle = 0.8
        driving.handle_event(key_event(pygame.K_k))  # set cruise at ~65
        assert driving._cruise_mph > 60

        driving.update(1 / 60)

        assert driving._acc_limit_capped
        assert driving.truck.throttle < 0.8  # backed off the throttle
        assert driving.truck.brake > 0.0  # braking down toward the limit
        assert any("adaptive cruise easing to" in e for e in events)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_slows_before_large_limit_drop(monkeypatch):
    from freight_fate.app import App

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        drop_at = driving.trip.position_mi + 0.4
        driving.trip.speed_limit_at = lambda mile: (40.0, None) if mile >= drop_at else (65.0, None)
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 30.4  # ~68 mph
        driving.truck.throttle = 0.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving.trip.position_mi < drop_at

        driving.update(1 / 60)

        assert driving._acc_limit_capped
        assert driving.truck.throttle < 0.8
        assert driving.truck.brake > 0.0
        assert any("adaptive cruise easing to" in e for e in events)
    finally:
        app.shutdown()


def test_adaptive_cruise_easing_preannounces_the_capped_target(monkeypatch):
    """Cruise's own 'easing to X' line for a plain posted-limit drop already
    named a number; wiring it into the trip's pre-announce set is the other
    half of the fix that lets a plain arrival confirmation for that same
    number stay quiet (owner's live playtest, 2026-08-12). What cruise
    actually said is the ACC-offset target (posted + ACC_LIMIT_OFFSET_MPH
    here, since this is a plain drop, not a restricted zone), not the raw
    posted number -- pre-announcing that raw number instead would silence an
    arrival confirmation cruise never actually spoke."""
    from freight_fate.app import App

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        drop_at = driving.trip.position_mi + 0.4
        driving.trip.speed_limit_at = lambda mile: (40.0, None) if mile >= drop_at else (65.0, None)
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 30.4  # ~68 mph
        driving.truck.throttle = 0.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving.trip.position_mi < drop_at

        driving.update(1 / 60)

        assert any("adaptive cruise easing to" in e for e in events)
        assert 45.0 in driving.trip._limit_drop_preannounced  # 40 + ACC_LIMIT_OFFSET_MPH
    finally:
        app.shutdown()


@pytest.mark.parametrize(
    ("speed_mph", "over_before_mi", "dt"),
    [
        (45.0, 0.07, 0.1),
        (46.0, 0.07, 0.1),
        (55.0, 0.06, 0.5),
        (65.0, 0.05, 1.0),
        (70.0, 0.04, 1.5),
    ],
)
@pytest.mark.smoke
def test_adaptive_cruise_limit_drop_is_never_read_as_speeding(
    monkeypatch, speed_mph, over_before_mi, dt
):
    """Cruise braking the truck down to a new limit is not disregard.

    It used to be measured against a real-time strike clock; it is measured
    against the over-limit distance an officer reads now, and the answer has
    to be the same: the accrual resets, and nothing is charged.
    """
    from freight_fate.app import App

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        driving.trip.speed_limit_at = lambda mile: (35.0, None)
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = speed_mph / 2.23694
        driving.truck.throttle = 0.0
        driving._cruise_mph = 65.0
        driving._over_limit_mi = over_before_mi

        driving.update(dt)

        assert driving._acc_limit_capped
        assert driving.truck.brake > 0.0
        assert driving._over_limit_mi == 0.0
        assert driving._pull_over is None
        assert not any("Lights and siren" in e for e in events)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_ignores_far_small_limit_drop(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        drop_at = driving.trip.position_mi + 1.4
        driving.trip.speed_limit_at = lambda mile: (60.0, None) if mile >= drop_at else (65.0, None)
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 30.4  # ~68 mph
        driving.handle_event(key_event(pygame.K_k))

        driving.update(1 / 60)

        assert not driving._acc_limit_capped
        assert driving.truck.brake == 0.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_allows_a_small_offset_over_the_limit(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        # A few mph over the posted limit is a natural with-traffic pace and well
        # under the speeding-strike threshold, so cruise should not pull it back.
        driving.trip.speed_limit_at = lambda mile: (60.0, None)
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 28.2  # ~63 mph, 3 over a 60 limit
        driving.handle_event(key_event(pygame.K_k))

        driving.update(1 / 60)

        assert not driving._acc_limit_capped
        assert driving.truck.brake == 0.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_increases_gap_for_bad_weather(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import NPCVehicle
    from freight_fate.sim.weather import WeatherKind

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0
        driving.truck.throttle = 0.5
        driving.handle_event(key_event(pygame.K_k))

        driving.trip.traffic_manager.vehicles = [
            NPCVehicle(
                "npc:weather-gap", driving.trip.position_mi + 0.08, 65.0, 65.0, 0, "steady_truck"
            )
        ]
        driving.weather.current = WeatherKind.CLEAR
        clear_gap = driving._acc_gap_seconds()
        driving.update(1 / 60)
        assert not driving._acc_following

        driving.weather.current = WeatherKind.HEAVY_RAIN
        wet_gap = driving._acc_gap_seconds()
        driving.update(1 / 60)

        assert wet_gap > clear_gap
        assert driving._acc_following
        assert "Wet roads, adaptive cruise increasing following gap." in events
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_stays_armed_before_restricted_zone(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind, Zone

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None

        zone = Zone(10.0, 15.0, 45.0, "construction")
        event = TripEvent(
            TripEventKind.GPS_CUE,
            "In 2 miles, construction ahead. Speed limit 45.",
            {"zone": zone},
        )
        driving._handle_trip_event(event)

        assert driving._cruise_mph is not None
        assert events[-1] == "In 2 miles, construction ahead. Speed limit 45."
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_switches_to_keeper_for_heavy_traffic(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind, Zone

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        monkeypatch.setattr(app.ctx, "say", speech_stub(events))
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None

        zone = Zone(10.0, 15.0, 50.0, "heavy traffic")
        event = TripEvent(
            TripEventKind.ZONE_ENTER,
            "Entering heavy traffic zone. Speed limit 50 now.",
            {"zone": zone},
        )
        driving._handle_trip_event(event)

        assert driving._cruise_mph is None
        assert driving._keeper_mph == pytest.approx(50.0)
        assert driving._speed_control_target_mph == pytest.approx(60.0, abs=1.0)
        assert driving._speed_control_armed
        assert events[-2] == (
            "Entering heavy traffic zone. Speed limit 50 now. "
            "Speed keeper holding 50 miles per hour."
        )
        # Live achievement announces are name-only now (R9: the flavor moved to
        # the log). The announce reads exactly "New achievement! <name>." with
        # no trailing flavor, unlike the full-record log line.
        assert events[-1] == "New achievement! Bumper-to-Bumper Blues."
    finally:
        app.shutdown()


def test_cruise_pre_brakes_for_heavy_traffic_like_a_work_zone(monkeypatch):
    """Heavy traffic is a restricted zone, so cruise aims at its posted limit
    exactly instead of carrying the with-traffic offset into the jam, and it
    keeps aiming there once the warning window has retracted behind it.

    The end-to-end playtest case for this cannot run on this line: without
    baked traffic volume no congestion zone lands on any route, so it is
    marked xfail in the harness tests and the gap is a 2.0 item. This covers
    the lookahead itself with a zone put on the route directly.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip import Zone, _zone_key

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.speed_limit_at = lambda mile: (70.0, None)
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 31.3  # ~70 mph
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None

        start = driving.trip.position_mi + 0.5
        zone = Zone(start, start + 3.0, 50.0, "heavy traffic")
        driving.trip.zones.append(zone)
        driving.trip._announced_zone_warnings.add(_zone_key(zone))

        assert driving._restricted_zone_limit_ahead() == (50.0, "heavy traffic")
        # Exactly the zone's limit, with no with-traffic offset added.
        assert driving._acc_posted_limit_ahead() == (50.0, "heavy traffic")
        # The latch carries the reason too, so a zone that slips back out of
        # the speed-scaled warning window is still braked for by name.
        assert driving._construction_slowdown == (zone.end_mi, 50.0, "heavy traffic")
        driving.trip._zone_warning_lookahead_mi = lambda: 0.0
        assert driving._restricted_zone_limit_ahead() == (50.0, "heavy traffic")
    finally:
        app.shutdown()


def test_speed_control_restores_cruise_target_after_zone(monkeypatch):
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())
    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        state = {"limit": 65.0, "reason": None}
        driving.trip.speed_limit_at = lambda mile: (state["limit"], state["reason"])
        driving.trip.traffic_context = lambda: None
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8  # ~60 mph
        driving.handle_event(key_event(pygame.K_k))
        original_target = driving._cruise_mph

        state.update(limit=25.0, reason="construction")
        driving.update(1 / 60)
        assert driving._cruise_mph is None
        assert driving._keeper_mph == pytest.approx(25.0)

        state.update(limit=65.0, reason=None)
        driving.update(1 / 60)
        assert driving._keeper_mph is None
        assert driving._cruise_mph == pytest.approx(original_target)
        assert sum("Speed keeper holding" in event for event in events) == 1
        assert sum("Adaptive cruise resuming" in event for event in events) == 1
    finally:
        app.shutdown()


def test_cruise_target_can_be_adjusted_while_keeper_is_active(monkeypatch):
    from freight_fate.app import App

    app = App()
    said = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say", speech_stub(said))
        driving.trip.speed_limit_at = lambda mile: (15.0, "facility access road")
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 3
        driving.truck.velocity_mps = 4.5
        driving.handle_event(key_event(pygame.K_k))

        driving.handle_event(key_event(pygame.K_EQUALS))

        assert driving._keeper_mph == pytest.approx(10.0, abs=0.5)
        assert driving._speed_control_target_mph == pytest.approx(25.0)
        assert said[-1] == "Open-road cruise target 25 miles per hour."
    finally:
        app.shutdown()


# -- hazard reaction windows ---------------------------------------------------


def clear_weather(driving):
    """Pin the trip's weather to clear so grip stays 1.0 for the whole test."""
    from freight_fate.sim.weather import WeatherKind

    weather = driving.trip.weather
    weather.provider = None
    weather.live = False
    weather.current = WeatherKind.CLEAR
    weather.minutes_until_change = 1e9


@pytest.mark.smoke
def test_hazard_deadline_covers_braking_time_from_current_speed():
    """A fixed 3-4.5 s window was unbeatable at highway speed: a full-service
    stop from 65 to 25 mph alone takes ~5 s. The deadline must cover the
    braking the truck actually needs -- fade, wear, and load included -- from
    the current speed, and leave the rolled reaction slack on top of it."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import HAZARD_SAFE_MPH, MPH_PER_MPS

    app = App()
    try:
        app.ctx.settings.time_scale = 20.0
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        t.velocity_mps = 29.0  # ~65 mph
        t.grip, t.grade = 1.0, 0.0
        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 3.0})
        driving._handle_trip_event(hazard)
        brake_s = (t.speed_mph - HAZARD_SAFE_MPH) / MPH_PER_MPS / t.full_service_decel_mps2()
        assert driving._brake_budget_s() == pytest.approx(brake_s, abs=0.01)
        assert driving._hazard_deadline == pytest.approx(
            driving._aeb_engage_s(HAZARD_SAFE_MPH) + 3.0, abs=0.01
        )
        assert driving._hazard_deadline > brake_s + 3.0
    finally:
        app.shutdown()


def test_automatic_emergency_braking_engages_once_and_cancels_cruise(monkeypatch):
    """The assist takes the truck on the SERVICE brakes and says so once.

    "Emergency braking engaged" is reserved for the escalation, which this
    truck has not earned: the announcement must not claim the hardest stop
    the rig has while the assist is on the normal brakes.
    """
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken, with_interrupt=True))
    try:
        driving = start_drive(app)
        driving.truck.velocity_mps = 25.0
        driving._cruise_mph = 55.0
        driving._hazard_deadline = driving._brake_budget_s()
        driving._update_hazard(0.01)
        driving._update_hazard(0.01)
        assert driving.truck.brake == 1.0
        assert not driving.truck.emergency_brake
        assert driving._cruise_mph is None
        said = [text for text, _ in spoken]
        assert said.count("Automatic braking.") == 1
        assert "Emergency braking engaged." not in said
    finally:
        app.shutdown()


def test_fixed_object_hazard_needs_nearly_a_stop_or_a_swerve(monkeypatch):
    """You cannot roll over a ladder at 25: a dodgeable hazard resolved by
    brake alone takes nearly a stop, with a one-time hint past the old safe
    speed so the quiet never reads as an already-cleared hazard."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import HAZARD_CREEP_MPH, HAZARD_SAFE_MPH, MPH_PER_MPS

    app = App()
    spoken = []
    app.ctx.say_event = speech_stub(spoken)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        # This test is about the swerve option, so pin a lane beside the
        # truck to actually swerve into -- which real route the new career
        # was dispatched onto is not this test's business.
        monkeypatch.setattr(driving.trip, "has_open_adjacent_lane_at", lambda mile=None: True)
        t = driving.truck
        t.velocity_mps = 29.0  # ~65 mph
        t.grip, t.grade = 1.0, 0.0
        hazard = TripEvent(
            TripEventKind.HAZARD,
            "Brake or change lanes! Debris on the road.",
            {"deadline_s": 3.0, "dodgeable": True},
        )
        driving._handle_trip_event(hazard)
        assert driving._hazard_dodgeable

        # The old moving-hazard speed no longer clears it; the hint speaks once.
        t.velocity_mps = (HAZARD_SAFE_MPH - 1.0) / MPH_PER_MPS
        driving._update_hazard(1 / 60)
        driving._update_hazard(1 / 60)
        assert driving._hazard_deadline is not None
        assert spoken.count("It is still in your lane. Nearly stop, or change lanes.") == 1

        # Nearly stopping resolves it, with the ease-around fiction spoken.
        t.velocity_mps = (HAZARD_CREEP_MPH - 1.0) / MPH_PER_MPS
        driving._update_hazard(1 / 60)
        assert driving._hazard_deadline is None
        assert any("ease around it" in text for text in spoken)
    finally:
        app.shutdown()


def test_fixed_object_hazard_deadline_budgets_the_longer_stop():
    """The dodgeable deadline must cover braking to the creep speed, not the
    moving-hazard speed -- otherwise the honest demand becomes unwinnable."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import HAZARD_CREEP_MPH, LANE_TAP_CHANGE_S

    app = App()
    try:
        app.ctx.settings.time_scale = 20.0  # reaction window multiplier 1.0
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        t.velocity_mps = 29.0  # ~65 mph
        t.grip, t.grade = 1.0, 0.0
        hazard = TripEvent(
            TripEventKind.HAZARD,
            "Brake or change lanes! Debris on the road.",
            {"deadline_s": 3.0, "dodgeable": True},
        )
        driving._handle_trip_event(hazard)
        assert driving._hazard_deadline == pytest.approx(
            driving._aeb_engage_s(HAZARD_CREEP_MPH) + 3.0 + LANE_TAP_CHANGE_S, abs=0.01
        )
        assert driving._hazard_deadline > driving._brake_budget_s() + 3.0
    finally:
        app.shutdown()


def test_brake_budget_honors_fade_wear_and_load():
    """The AEB budget must use the braking the truck can actually deliver:
    the spec number engaged the assist two seconds before a collision on
    hot brakes (playtest transcript, 2026-07-16)."""
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        t = driving.truck
        t.velocity_mps = 29.0  # ~65 mph
        t.grip, t.grade = 1.0, 0.0
        fresh = driving._brake_budget_s()

        t.brake_temp_c = t.specs.brake_fade_temp_c + 150.0  # cooked drums
        hot = driving._brake_budget_s()
        assert hot > fresh * 1.5

        t.brake_temp_c = 20.0
        t.brake_wear_pct = 60.0
        worn = driving._brake_budget_s()
        assert worn > fresh
    finally:
        app.shutdown()


@pytest.mark.parametrize(
    ("label", "mph", "grade", "brake_temp_c", "wear_pct", "grip", "fatigue"),
    [
        ("fresh at highway speed", 65.0, 0.0, 20.0, 0.0, 1.0, 0.0),
        ("drowsy", 65.0, 0.0, 20.0, 0.0, 1.0, 80.0),
        ("down a five percent grade", 65.0, -0.05, 20.0, 0.0, 1.0, 0.0),
        ("on cooked brakes", 65.0, 0.0, 500.0, 0.0, 1.0, 0.0),
        ("on worn brakes in the wet", 65.0, 0.0, 20.0, 60.0, 0.6, 0.0),
    ],
)
def test_the_driver_always_gets_a_real_window_before_the_assist_takes_over(
    label, mph, grade, brake_temp_c, wear_pct, grip, fatigue
):
    """The reaction window must be a promise, not a leftover.

    Reported by Munchkinbear, 2026-08-11: "less than half a second between
    being told to brake or change lanes and the truck slamming on the
    emergency brakes". The window was whatever survived after the assist's
    engage margin -- which scales with the stopping budget -- was subtracted
    from the fixed slack, so every reason the truck stops badly (speed,
    grade, heat, wear, grip) ate the driver's time instead of the truck's.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import HAZARD_MIN_REACTION_S, MPH_PER_MPS

    app = App()
    try:
        app.ctx.settings.time_scale = 20.0
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        t.velocity_mps = mph / MPH_PER_MPS
        t.grade, t.grip = grade, grip
        t.brake_temp_c, t.brake_wear_pct = brake_temp_c, wear_pct
        app.ctx.profile.fatigue = fatigue
        # The tightest slack the road emits: the traffic-pressure warning.
        driving._handle_trip_event(
            TripEvent(
                TripEventKind.HAZARD,
                "Brake or change lanes! Slow truck right ahead.",
                {"deadline_s": 2.5, "dodgeable": True},
            )
        )
        window = driving._hazard_deadline - driving._aeb_engage_s(driving._hazard_target_mph())
        assert window >= HAZARD_MIN_REACTION_S, f"{label}: only {window:.2f} s to react"
    finally:
        app.shutdown()


def test_a_dodgeable_hazard_leaves_time_to_finish_the_lane_change_it_asks_for():
    """ "Brake or change lanes" names a maneuver that takes 2.5 s of drift.
    Demanding it inside a window shorter than the maneuver is not a demand,
    it is a trap -- so a dodgeable hazard budgets the move on top of the
    time to hear the warning and decide."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import (
        HAZARD_MIN_REACTION_S,
        LANE_TAP_CHANGE_S,
        MPH_PER_MPS,
    )

    app = App()
    try:
        app.ctx.settings.time_scale = 20.0
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        t.velocity_mps = 65.0 / MPH_PER_MPS
        t.grade, t.grip = 0.0, 1.0
        driving._handle_trip_event(
            TripEvent(
                TripEventKind.HAZARD,
                "Brake or change lanes! Debris on the road.",
                {"deadline_s": 2.5, "dodgeable": True},
            )
        )
        window = driving._hazard_deadline - driving._aeb_engage_s(driving._hazard_target_mph())
        assert window >= HAZARD_MIN_REACTION_S + LANE_TAP_CHANGE_S
    finally:
        app.shutdown()


def test_the_assist_does_not_slam_on_mid_lane_change(monkeypatch):
    """A driver already sliding into the next lane has answered the warning.
    Taking the truck away from them halfway through the move is what the
    report described as "as you change lanes, slam go the emergency brakes"."""
    from freight_fate.app import App
    from freight_fate.states.driving import LANE_TAP_CHANGE_S

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.velocity_mps = 25.0
        driving._hazard_dodgeable = True
        driving._hazard_lane = driving.lane.lane
        # Past the engage point, but the dodge still lands before the hazard.
        driving._hazard_deadline = driving._aeb_engage_s(driving._hazard_target_mph())
        driving._lane_change_target = driving.lane.lane + 1
        driving._lane_change_timer = LANE_TAP_CHANGE_S * 0.4
        driving._update_hazard(0.01)
        assert driving.truck.brake == 0.0

        # A dodge that can no longer beat the hazard does not hold the assist off.
        driving._lane_change_timer = driving._hazard_deadline + 1.0
        driving._update_hazard(0.01)
        assert driving.truck.brake == 1.0
    finally:
        app.shutdown()


def test_the_assist_stands_on_everything_when_service_braking_is_losing():
    """An assist that takes the truck has to actually stop it.

    Owner question, 2026-08-11: to help a player it should stop in time. It
    did not always. The assist applied full SERVICE braking and the budget
    that sized its engage point assumed the same, but a stop on hot, worn
    brakes in the wet on a downgrade gets slower while it happens -- the
    drums heat further under the very application meant to save it. Two of
    nine benched conditions collided after "Emergency braking engaged."

    Full service stays the first answer. When the time left no longer covers
    even that, the assist uses the hardest stop the rig has, which is what
    the driver would do and exactly what the B key already gives them.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import MPH_PER_MPS

    app = App()
    try:
        app.ctx.settings.time_scale = 20.0
        app.ctx.settings.automatic_emergency_braking = True
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        t.velocity_mps = 65.0 / MPH_PER_MPS
        t.grade, t.grip = -0.06, 0.7
        t.brake_temp_c, t.brake_wear_pct = 450.0, 40.0
        t.cargo_kg = 19_000.0
        damage_before = t.damage_pct
        driving._handle_trip_event(
            TripEvent(
                TripEventKind.HAZARD,
                "Brake or change lanes! Slow truck right ahead.",
                {"deadline_s": 2.5, "dodgeable": True},
            )
        )
        stood_on_it = False
        elapsed = 0.0
        while driving._hazard_deadline is not None and elapsed < 120.0:
            t.throttle = 0.0
            driving._update_hazard(1 / 60)
            stood_on_it = stood_on_it or t.emergency_brake
            if driving._hazard_deadline is None:
                break
            t.grade = -0.06
            t.update(1 / 60)
            elapsed += 1 / 60
        assert t.damage_pct == damage_before, "the assist engaged and still hit the hazard"
        assert stood_on_it, "service braking alone was losing and nothing escalated"
    finally:
        app.shutdown()


def test_a_stop_service_braking_can_make_stays_on_the_service_brakes():
    """The escalation is a last resort, not the new normal: an ordinary
    hazard on good brakes must not become a spring-brake panic stop."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import MPH_PER_MPS

    app = App()
    try:
        app.ctx.settings.time_scale = 20.0
        app.ctx.settings.automatic_emergency_braking = True
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        t.velocity_mps = 65.0 / MPH_PER_MPS
        t.grade, t.grip = 0.0, 1.0
        t.brake_temp_c, t.brake_wear_pct = 20.0, 0.0
        driving._handle_trip_event(
            TripEvent(
                TripEventKind.HAZARD,
                "Brake or change lanes! Slow truck right ahead.",
                {"deadline_s": 2.5, "dodgeable": True},
            )
        )
        elapsed = 0.0
        while driving._hazard_deadline is not None and elapsed < 120.0:
            t.throttle = 0.0
            driving._update_hazard(1 / 60)
            assert not t.emergency_brake, "good brakes on the flat needed no panic stop"
            if driving._hazard_deadline is None:
                break
            t.update(1 / 60)
            elapsed += 1 / 60
    finally:
        app.shutdown()


def test_a_routine_assisted_stop_costs_one_brake_application(monkeypatch):
    """Owner ruling from a live drive, 2026-08-12: "This emergency braking has
    to stop for brake assist. Air pressure keeps running out. Just use the
    dang service brakes."

    Two things spent that air. The assist decided its application afresh every
    frame against a threshold its own braking pushed away, so it let go, the
    threshold came back and it pressed again -- and the air system charges a
    whole brake application every time the pedal RISES. And the input pass
    ramps the brake down and writes the emergency flag from the B key, both
    before the physics runs and both after the assist's last word on the
    frame, so what the drums actually got was a frame's ramp short of full
    service and the difference was re-charged every frame.

    One held stop, one application: the pedal the drums see is the full one
    the budget assumed, the gauge barely moves, and nothing escalates.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import MPH_PER_MPS

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())

    app = App()
    try:
        app.ctx.settings.automatic_emergency_braking = True
        driving = start_drive(app)
        quiet_trip(driving)
        clear_weather(driving)
        open_limits(driving)
        driving.trip.traffic_pressures = []
        driving.trip.curves = []
        driving.trip.grade_at = lambda mile: 0.0  # level ground for the whole stop
        driving._destination_exit_taken = True
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))  # engine on
        t.transmission.gear = 10
        t.velocity_mps = 65.0 / MPH_PER_MPS
        t.grade, t.grip = 0.0, 1.0
        t.brake_temp_c, t.brake_wear_pct = 20.0, 0.0
        t.air_pressure_psi = 125.0  # governor cut-out, so nothing rebuilds mid-test
        damage_before = t.damage_pct
        psi_before = t.primary_air_psi
        driving._handle_trip_event(
            TripEvent(
                TripEventKind.HAZARD,
                "Brake now! Stopped traffic ahead.",
                {"deadline_s": 3.0},
            )
        )
        # Units of pedal RISE the air system charged for, the measure the
        # fanning assists were caught with (bench trace, 2026-08-11).
        charged = 0.0
        previous = t._last_service_air_application
        held_decel = 0.0
        pedal_seen = 0.0
        for _ in range(60 * 30):
            driving.update(1 / 60)
            assert not t.emergency_brake, "a sound truck on the flat needed no panic stop"
            application = t._last_service_air_application
            charged += max(0.0, application - previous)
            previous = application
            if driving._aeb_brake > 0.0:
                held_decel = max(held_decel, driving._aeb_decel_mps2)
                pedal_seen = max(pedal_seen, application)
            if driving._hazard_deadline is None:
                break
        assert driving._hazard_deadline is None, "the assist never resolved the hazard"
        assert t.damage_pct == damage_before, "the assist engaged and still hit the hazard"
        # The pedal the physics and the air system saw is the full service
        # application the budget assumed, not what survived the input ramp.
        assert pedal_seen == pytest.approx(1.0)
        assert held_decel >= t.full_service_decel_mps2() * 0.95
        assert charged <= 1.2, f"one held stop was charged {charged:.1f} brake applications"
        spent = psi_before - t.primary_air_psi
        assert 3.0 <= spent <= 9.0, f"a single held stop spent {spent:.1f} psi"
    finally:
        app.shutdown()


def test_the_escalation_reads_what_the_truck_is_doing_not_what_it_should():
    """Same speed, same time left, same brakes -- and only one of them panics.

    The old predicate asked whether the time left still covered what a full
    application OUGHT to deliver. That is a prediction, and the assist was not
    delivering it, so an ordinary assisted stop could trip it. The escalation
    now reads the deceleration the truck is actually making: a stop that is
    getting there keeps the service brakes however tight the arithmetic looks,
    and only a stop that has stopped getting there stands on everything.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import MPH_PER_MPS

    def run(*, slowing: bool) -> bool:
        app = App()
        try:
            app.ctx.settings.time_scale = 20.0
            app.ctx.settings.automatic_emergency_braking = True
            driving = start_drive(app)
            quiet_trip(driving)
            t = driving.truck
            held = 65.0 / MPH_PER_MPS
            t.velocity_mps = held
            t.grade, t.grip = 0.0, 1.0
            t.brake_temp_c, t.brake_wear_pct = 20.0, 0.0
            driving._handle_trip_event(
                TripEvent(
                    TripEventKind.HAZARD,
                    "Brake now! Stopped traffic ahead.",
                    {"deadline_s": 3.0},
                )
            )
            stood_on_it = False
            for _ in range(60 * 60):
                t.throttle = 0.0
                driving._update_hazard(1 / 60)
                stood_on_it = stood_on_it or t.emergency_brake
                if driving._hazard_deadline is None:
                    break
                if slowing:
                    t.update(1 / 60)
                    t.grade = 0.0
                else:
                    # Grip that is not there: everything is applied and the
                    # truck is not losing a single mile an hour.
                    t.velocity_mps = held
            return stood_on_it
        finally:
            app.shutdown()

    assert not run(slowing=True), "a stop that was getting there did not need the hard version"
    assert run(slowing=False), "a truck that was not slowing at all rode it into the hazard"


def test_automatic_emergency_braking_leads_the_budget(monkeypatch):
    """The assist engages with margin over the physics budget: braking heats
    the brakes, so a zero-margin engage under-delivers exactly as it fires."""
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        driving.truck.velocity_mps = 25.0
        # More time left than the raw budget, but within the safety lead.
        driving._hazard_deadline = driving._brake_budget_s() * 1.1 + 0.2
        driving._update_hazard(0.01)
        assert driving.truck.brake == 1.0
    finally:
        app.shutdown()


@pytest.mark.parametrize(
    ("level", "braking", "expected_active"),
    [
        ("off", False, False),
        ("realistic", False, True),
        ("balanced", True, True),
        ("interactive", True, True),
    ],
)
def test_descent_control_levels_and_brake_capture(monkeypatch, level, braking, expected_active):
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say_event = speech_stub(spoken)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        open_limits(driving)
        driving.trip.traffic_context = lambda: None
        driving.ctx.settings.descent_speed_control = level
        driving.truck.grade = -0.06
        driving.truck.engine_on = True
        driving.truck.velocity_mps = 22.0
        driving.truck.transmission.automatic = True
        driving._cruise_mph = 60.0
        driving._update_cruise(0.1, braking, False, False)
        assert driving._descent_control_active is expected_active
        if braking and level in ("balanced", "interactive"):
            assert driving._cruise_mph == pytest.approx(driving.truck.speed_mph)
            assert sum("Descent target changed" in text for text in spoken) == 1
            driving._update_cruise(0.1, True, False, False)
            assert sum("Descent target changed" in text for text in spoken) == 1
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_service_brakes_beat_a_highway_hazard_after_human_reaction(monkeypatch):
    """The taught response -- hear the warning, hold Down -- must succeed from
    highway speed even with a slow human reaction, without the emergency brake."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        clear_weather(driving)
        t = driving.truck
        t.transmission.gear = 10
        t.velocity_mps = 29.0  # ~65 mph
        damage_before = t.damage_pct

        held = set()

        class FakeKeys:
            def __getitem__(self, key):
                return key in held

        monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys())

        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 3.0})
        driving._handle_trip_event(hazard)
        for _ in range(int(60 * 1.5)):  # hearing the warning: no input yet
            driving.update(1 / 60)
        held.add(pygame.K_DOWN)  # then service brakes only
        for _ in range(60 * 20):
            driving.update(1 / 60)
            if driving._hazard_deadline is None:
                break
        assert driving._hazard_deadline is None
        assert t.damage_pct == damage_before  # avoided, not collided
    finally:
        app.shutdown()


class _FakeWeatherProvider:
    """Returns ``kind`` for any city; ``None`` models data not yet fetched."""

    def __init__(self, kind=None):
        self.kind = kind

    def request(self, city, lat, lon):
        pass

    def get(self, city):
        return self.kind


def test_real_weather_starts_clear_with_no_simulated_warmup(monkeypatch):
    """Regression: with real weather enabled, a drive starts neutral (clear) and
    holds until live data arrives, instead of showing a provisional simulated
    condition. So no momentary simulated rain can unlock an achievement."""
    from freight_fate.app import App
    from freight_fate.sim.weather import WeatherKind

    provider = _FakeWeatherProvider(kind=None)  # data not fetched yet
    app = App()
    monkeypatch.setattr(app.ctx, "real_weather_provider", lambda: provider)
    app.ctx.settings.real_weather = True
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        assert driving.weather.provider is provider
        assert driving.weather.current is WeatherKind.CLEAR
        assert driving.weather.live is False

        # While the fetch is still pending, weather holds clear -- no simulated
        # transitions, so no weather achievement fires.
        for _ in range(10):
            driving.update(1 / 60)
        assert driving.weather.current is WeatherKind.CLEAR
        assert "rain_driver" not in driving.ctx.profile.achievements
    finally:
        app.shutdown()


def test_live_weather_calendar_off_does_not_announce_simulated_forecast_while_loading(
    monkeypatch,
):
    """V must not invent a forecast while the selected live source is loading.

    The calendar toggle changes seasonal plausibility, not the weather source.
    """
    from freight_fate.app import App

    provider = _FakeWeatherProvider(kind=None)
    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "real_weather_provider", lambda: provider)
    app.ctx.settings.real_weather = True
    app.ctx.settings.live_weather_controls_calendar = False
    try:
        driving = start_drive(app)
        driving._speak_weather()
        assert "Live weather is loading for your current route position" in spoken[-1]
        assert "Ahead:" not in spoken[-1]
    finally:
        app.shutdown()


def test_real_weather_applies_and_awards_live_condition(monkeypatch):
    """Once live conditions arrive, they take over from clear and award their
    achievement -- e.g. genuine live rain unlocks the rain achievement."""
    from freight_fate.app import App
    from freight_fate.sim.weather import WeatherKind

    provider = _FakeWeatherProvider(kind=WeatherKind.RAIN)
    app = App()
    monkeypatch.setattr(app.ctx, "real_weather_provider", lambda: provider)
    app.ctx.settings.real_weather = True
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        for _ in range(5):
            driving.update(1 / 60)
        assert driving.weather.live is True
        assert driving.weather.current is WeatherKind.RAIN
        assert "rain_driver" in driving.ctx.profile.achievements
    finally:
        app.shutdown()


def test_v_reports_live_weather_from_multiple_current_route_positions(monkeypatch):
    """Real V-key reports follow stable route cells instead of the destination."""
    from freight_fate.app import App
    from freight_fate.sim.weather import WeatherKind

    class SpatialProvider:
        def __init__(self):
            self.requests = []
            self.conditions = {}

        def request(self, key, lat, lon):
            if key not in self.conditions:
                kinds = (WeatherKind.CLEAR, WeatherKind.RAIN, WeatherKind.HEAVY_RAIN)
                self.conditions[key] = kinds[min(len(self.conditions), 2)]
                self.requests.append((key, lat, lon))

        def get(self, key):
            return self.conditions.get(key)

        def stale(self, key):
            return False

        def unavailable(self, key):
            return False

    provider = SpatialProvider()
    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "real_weather_provider", lambda: provider)
    app.ctx.settings.real_weather = True
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        from freight_fate.sim.trip import Trip

        route = app.ctx.world.route_options("chicago_il_us", "indianapolis_in_us")[0]
        driving.route = route
        driving.trip = Trip(
            route,
            driving.truck,
            driving.weather,
            time_scale=driving.ctx.settings.time_scale,
            seed=driving.trip_seed,
        )
        provider.requests.clear()
        provider.conditions.clear()
        driving.weather.live = False
        driving.weather._live_raw = None
        driving.weather._live_city = None
        driving.weather._live_kind = None
        positions = (0.0, 40.0, 80.0)
        expected = ("clear", "rain", "heavy rain")
        for position, condition in zip(positions, expected, strict=True):
            driving.trip.position_mi = position
            driving.trip.update(0.0)
            driving.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v, unicode="v", mod=0)
            )
            assert spoken[-1].startswith(f"Live weather: {condition}")
        assert len({key for key, _lat, _lon in provider.requests}) == 3
        destination = app.ctx.world.city(driving.route.cities[-1])
        assert provider.requests[0][1:] != (destination.lat, destination.lon)
        assert app.state is driving
    finally:
        app.shutdown()


def test_v_distinguishes_loading_last_known_and_fallback(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEventKind
    from freight_fate.sim.weather import WeatherKind
    from freight_fate.states.driving_menu_states import DriverAppScreenState

    class StatefulProvider:
        kind = None
        is_stale = False
        is_unavailable = False
        is_refreshing = False
        is_failed = False

        def request(self, *args):
            pass

        def get(self, key):
            return self.kind

        def stale(self, key):
            return self.is_stale

        def unavailable(self, key):
            return self.is_unavailable

        def refreshing(self, key):
            return self.is_refreshing

        def observation_age_s(self, key):
            return 12 * 60 if self.kind is not None else None

        def refresh_failed(self, key):
            return self.is_failed

    provider = StatefulProvider()
    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "real_weather_provider", lambda: provider)
    app.ctx.settings.real_weather = True
    try:
        driving = start_drive(app)
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v, unicode="v", mod=0)
        driving.trip.update(0.0)
        driving.handle_event(event)
        assert spoken[-1].startswith("Live weather is loading for your current route position")
        assert "Ahead:" not in spoken[-1]

        provider.kind = WeatherKind.HEAVY_RAIN
        driving.trip.update(0.0)
        provider.is_stale = True
        driving.handle_event(event)
        assert spoken[-1].startswith("Last-known live weather: heavy rain")
        assert "The observation is 12 minutes old" in spoken[-1]
        assert "updating" not in spoken[-1].lower()
        assert "Ahead:" not in spoken[-1]
        status_weather = next(
            line for line in driving.status_lines() if line.startswith("Weather:")
        )
        assert "Last-known live weather" in status_weather
        tablet = DriverAppScreenState(app.ctx, driving, "weather")
        assert [line.split(":", 1)[0] for line in tablet._weather_lines()] == [
            "Weather source",
            "Observation age",
            "Conditions",
            "Safe speed guidance",
            "Forecast ahead",
        ]
        assert tablet._weather_lines()[0].startswith(
            "Weather source: Last-known live weather for your current route position"
        )
        assert tablet._weather_lines()[1] == "Observation age: 12 minutes old."
        tablet.enter()
        selected = tablet.index
        assert tablet.items[0].text.startswith("Weather source: Last-known live weather")

        provider.is_refreshing = True
        driving.handle_event(event)
        assert "Live weather is updating for your current location" in spoken[-1]
        provider.is_refreshing = False

        provider.is_failed = True
        tablet.update(0.0)
        assert "The latest live weather check failed" in spoken[-1]
        assert driving.trip._weather_refresh_issue_announced
        duplicate_events = driving.trip.update(0.0)
        assert not any(
            event.kind is TripEventKind.WEATHER_CHANGE
            and "latest live weather check failed" in event.message
            for event in duplicate_events
        )
        provider.is_failed = False

        provider.kind = None
        provider.is_unavailable = True
        driving.trip.update(0.0)
        driving.handle_event(event)
        # The session has heard live weather, so an unavailable provider holds
        # last-known conditions -- simulated fallback never takes over mid-run
        # (owner ruling, 2026-08-08).
        assert spoken[-1].startswith("Last-known live weather")
        assert tablet.items[0].text.startswith("Weather source: Last-known live weather")
        tablet.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="", mod=0)
        )
        assert spoken[-1].startswith("Weather source: Last-known live weather")
        assert tablet.index == selected
    finally:
        app.shutdown()


def test_old_but_freshly_fetched_weather_is_live_across_v_status_and_tablet(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.weather import WeatherKind
    from freight_fate.states.driving_menu_states import DriverAppScreenState

    class FreshOldProvider:
        def request(self, *args):
            pass

        def get(self, key):
            return WeatherKind.RAIN

        def stale(self, key):
            return False

        def unavailable(self, key):
            return False

        def refreshing(self, key):
            return False

        def refresh_failed(self, key):
            return False

        def observation_age_s(self, key):
            return 12 * 60

    app = App()
    spoken = []
    provider = FreshOldProvider()
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "real_weather_provider", lambda: provider)
    app.ctx.settings.real_weather = True
    try:
        driving = start_drive(app)
        driving.trip.update(0.0)
        driving.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v, unicode="v", mod=0))
        assert spoken[-1].startswith("Live weather: rain")
        assert "The observation is 12 minutes old" in spoken[-1]
        assert "updating" not in spoken[-1].lower()

        weather_status = next(
            line for line in driving.status_lines() if line.startswith("Weather:")
        )
        assert "Live weather: rain" in weather_status
        assert "The observation is 12 minutes old" in weather_status
        assert "updating" not in weather_status.lower()

        tablet = DriverAppScreenState(app.ctx, driving, "weather")
        assert tablet._weather_lines()[0].startswith(
            "Weather source: Live weather for your current route position"
        )
        assert tablet._weather_lines()[1] == "Observation age: 12 minutes old."
        assert "updating" not in " ".join(tablet._weather_lines()).lower()
    finally:
        app.shutdown()


def test_limit_drop_earns_braking_grace(monkeypatch):
    """A posted-limit drop gives braking time before strikes accrue -- real
    enforcement tickets sustained disregard, not the transition (owner struck
    0.6 s after the 65-to-50 step in the Queen Creek canyon). Staying on the
    throttle forfeits the grace."""
    from freight_fate.app import App

    app = App()
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.zones = []
        driving.trip.patrols = []
        t = driving.truck
        t.velocity_mps = 65.0 / 2.23694
        t.throttle = 0.0

        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda mi: (65.0, None))
        driving._update_speeding(0.1)  # seed the previous limit
        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda mi: (50.0, None))

        def _roll(steps, *, accelerator_held=False):
            for _ in range(steps):
                driving.trip.position_mi += 0.01
                driving._update_speeding(0.1, accelerator_held=accelerator_held)
                driving._update_enforcement_watch(0.1)

        _roll(70)  # 7 s: inside the (65-50)/2 = 7.5 s grace
        assert driving._over_limit_mi == 0.0  # the transition itself is not a speed

        # Grace spent, still 15 over with no brake: the distance accrues.
        _roll(30)
        assert driving._over_limit_mi > 0.0

        # Second drop with the driver still on the throttle. For the first
        # ROUTE-budget seconds the zone-entry line may not have spoken yet,
        # so the held throttle is not yet disregard and the grace holds
        # (the R1 demotion's coupled invariant)...
        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda mi: (35.0, None))
        t.throttle = 1.0
        driving._over_limit_mi = 0.0
        _roll(5, accelerator_held=True)  # 0.5 s: inside the speech-latency window
        assert driving._over_limit_mi == 0.0

        # ...but once the line has had time to speak, staying on the
        # throttle forfeits the grace and the distance accrues.
        _roll(10, accelerator_held=True)
        assert driving._over_limit_mi > 0.0
    finally:
        app.shutdown()


def test_limit_drop_grace_uses_released_key_not_smoothed_throttle(monkeypatch):
    """Releasing Up keeps grace even while applied throttle ramps down."""
    from freight_fate.app import App

    class Keys:
        pressed = {pygame.K_UP}

        def __getitem__(self, key):
            return key in self.pressed

    keys = Keys()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: keys)
    app = App()
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.zones = []
        driving.trip.patrols = []
        driving.truck.velocity_mps = 65.0 / 2.23694
        driving.truck.throttle = 1.0
        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda mi: (65.0, None))

        driving.update(1 / 60)
        assert driving.truck.throttle > 0.0

        keys.pressed.clear()
        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda mi: (50.0, None))
        driving.update(1 / 60)

        assert driving.truck.throttle > 0.0
        assert driving._limit_drop_grace_s > 0.0
    finally:
        app.shutdown()


def test_overspeed_warning_speaks_then_chimes_until_compliant(monkeypatch):
    """The dash overspeed alert: spoken once when armed, chiming on an
    interval while over, disarmed by settling back under the limit -- and
    a fresh episode speaks again. Off means silent."""
    from freight_fate.app import App

    app = App()
    events, played = [], []
    monkeypatch.setattr(app.ctx.audio, "play", lambda key, **k: played.append(key))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.zones = []
        driving.trip.patrols = []
        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda mi: (50.0, None))
        t = driving.truck
        t.throttle = 0.3
        # 56 in a 50: over the warn threshold, inside the strike leeway.
        t.velocity_mps = 56.0 / 2.23694

        driving._update_speeding(0.1)
        assert any("Watch your speed" in e for e in events)
        assert played.count("vehicle/overspeed_chime") == 1

        for _ in range(52):  # past one 5 s repeat interval
            driving._update_speeding(0.1)
        assert played.count("vehicle/overspeed_chime") == 2
        assert sum("Watch your speed" in e for e in events) == 1  # spoken once

        # Settling under the limit disarms; the next episode speaks again.
        t.velocity_mps = 50.0 / 2.23694
        driving._update_speeding(0.1)
        t.velocity_mps = 56.0 / 2.23694
        driving._update_speeding(0.1)
        assert sum("Watch your speed" in e for e in events) == 2

        # Way over, the cadence escalates: at 25 over the ding runs about
        # every 1.5 seconds instead of every 5.
        t.velocity_mps = 75.0 / 2.23694
        played.clear()
        for _ in range(40):  # 4 seconds
            driving._update_speeding(0.1)
        assert played.count("vehicle/overspeed_chime") >= 2

        # Urgent-only mode: deliberate fast cruising stays unjudged, but a
        # runaway past the urgent line still rings, at the fast cadence.
        app.ctx.settings.overspeed_warning = "urgent only"
        t.velocity_mps = 50.0 / 2.23694
        driving._update_speeding(0.1)  # disarm
        played.clear()
        events.clear()
        t.velocity_mps = 60.0 / 2.23694  # 10 over: quiet in urgent-only
        for _ in range(60):
            driving._update_speeding(0.1)
        assert played.count("vehicle/overspeed_chime") == 0
        t.velocity_mps = 75.0 / 2.23694  # 25 over: the runaway alarm rings
        for _ in range(30):  # 3 seconds at the 0.5 s cadence
            driving._update_speeding(0.1)
        assert any("Watch your speed" in e for e in events)
        assert played.count("vehicle/overspeed_chime") >= 4

        # The setting turns the whole alert off.
        app.ctx.settings.overspeed_warning = "off"
        t.velocity_mps = 50.0 / 2.23694
        driving._update_speeding(0.1)
        t.velocity_mps = 56.0 / 2.23694
        chimes = played.count("vehicle/overspeed_chime")
        spoken = sum("Watch your speed" in e for e in events)
        for _ in range(60):
            driving._update_speeding(0.1)
        assert played.count("vehicle/overspeed_chime") == chimes
        assert sum("Watch your speed" in e for e in events) == spoken
    finally:
        app.shutdown()


# -- holding the set speed on a grade --------------------------------------------


def _grade_hold(
    app,
    grade,
    *,
    set_mph=62.0,
    seconds=90.0,
    descent="realistic",
    advisory=None,
    stages=None,
):
    """Run cruise at a set speed on a fixed grade; return the speed trace.

    Mirrors the driving loop's own order for the pieces a grade exercises:
    pedals decay when nothing is held, cruise runs, the retarder manager and
    the automatic get their turn, then the physics steps.

    ``advisory`` caps the working target for a mapped bend the way a pacenote
    does, and ``stages`` (a list) collects the retarder stage each frame --
    what the corner-versus-grade tests below are actually reading.
    """
    driving = start_drive(app)
    quiet_trip(driving)
    open_limits(driving)
    driving.trip.traffic_context = lambda: None
    driving.trip.grade_at = lambda mile: grade
    driving.trip.engine_brake_ban_at = lambda mile: None
    app.ctx.settings.descent_speed_control = descent
    app.ctx.settings.automatic_transmission = True
    t = driving.truck
    t.transmission.automatic = True
    t.cargo_kg = 18_000.0
    t.start_engine()
    t.set_air_ready(parking_brake=False)
    t.velocity_mps = set_mph / 2.23694
    t.transmission.gear = t.transmission.num_gears
    driving._engage_cruise(set_mph)

    dt = 1 / 60
    speeds = []
    for step in range(int(seconds * 60)):
        # Settle on the flat first so the grade arrives at a steady truck.
        t.grade = 0.0 if step < 20 * 60 else grade
        if advisory is not None and step == 20 * 60:
            # The bend's footprint outlasts the run, so the cap stays on.
            driving._cruise_curve_mph = float(advisory)
            driving._cruise_curve_end_mi = driving.trip.position_mi + 5.0
        ramp = dt * 2.2
        t.throttle = max(0.0, t.throttle - ramp * 2)
        t.brake = max(0.0, t.brake - ramp * 3)
        driving._update_cruise(dt, False, False, False)
        driving._update_auto_jake(dt)
        if t.transmission.automatic and t.engine_on:
            t.auto_shift()
        t.update(dt)
        if step >= 20 * 60:
            speeds.append(t.speed_mph)
            if stages is not None:
                stages.append(t.engine_brake_stage)
    return driving, speeds


@pytest.mark.smoke
def test_cruise_does_not_run_away_down_a_grade():
    """Cutting fuel is not speed control on a downgrade.

    Cruise had no authority over the truck from above unless a lead or a
    lower posted limit was already pulling the target down, so gravity simply
    carried it: a 2 percent descent settled nine mph past the set speed and a
    6 percent descent accelerated without limit (bench trace, 2026-07-25: 62
    set, 100 mph and still climbing). The retarder now stages against the
    overspeed, and the drums snub when it is not enough.
    """
    from freight_fate.app import App

    for grade, ceiling in ((-0.02, 63.5), (-0.04, 66.0), (-0.06, 66.0)):
        app = App()
        app.ctx.say_event = speech_stub()
        try:
            _, speeds = _grade_hold(app, grade)
            assert max(speeds) <= ceiling, (grade, max(speeds))
            # And it is holding a speed, not braking the truck to a stop: the
            # jake used to be pinned wide open the moment the grade passed
            # 2.5 percent, which dragged the truck well under its own target.
            assert min(speeds[-600:]) >= 58.0, (grade, min(speeds[-600:]))
        finally:
            app.shutdown()


@pytest.mark.smoke
def test_cruise_answers_a_climb_before_it_costs_twenty_mph():
    """Feed-forward plus the pull downshift, instead of a slow integrator.

    Cruise used to walk the throttle up at 0.08 per mph-second with no idea
    what the grade was asking for, and the automatic held top gear because
    the revs were not lugging yet. A 2 percent climb bled six mph and never
    got them back; a 4 percent climb lost thirty (bench trace, 2026-07-25).
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        driving, speeds = _grade_hold(app, 0.02)
        # A 2 percent pull is well inside what the truck has: hold it.
        assert min(speeds) >= 59.0, min(speeds)
        assert speeds[-1] >= 60.0, speeds[-1]
        assert driving.truck.transmission.gear < driving.truck.transmission.num_gears or (
            driving.truck.throttle < 1.0
        )
    finally:
        app.shutdown()

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        driving, speeds = _grade_hold(app, 0.04)
        # A 4 percent pull genuinely costs a loaded truck speed -- but it
        # must cost it in a lower gear making real torque, not at full
        # throttle in overdrive watching the hill win.
        assert speeds[-1] >= 40.0, speeds[-1]
        assert driving.truck.transmission.gear < driving.truck.transmission.num_gears
    finally:
        app.shutdown()


def test_interactive_descent_control_caps_the_target_without_rewriting_it():
    """The safe descent ceiling lasts as long as the grade, not the career.

    It used to assign straight into the cruise set speed, so one downgrade on
    a 65 road knocked cruise to 55 permanently -- on the flat, uphill, the
    rest of the run.
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        driving, _ = _grade_hold(app, -0.06, seconds=25.0, descent="interactive")
        assert driving._cruise_mph == pytest.approx(62.0)
        assert driving._cruise_descent_mph == pytest.approx(55.0)

        # Back on the level: the ceiling lifts and the driver's number returns.
        driving.trip.grade_at = lambda mile: 0.0
        driving.truck.grade = 0.0
        for _ in range(120):
            driving._update_cruise(1 / 60, False, False, False)
            driving.truck.update(1 / 60)
        assert driving._cruise_descent_mph is None
        assert driving._cruise_mph == pytest.approx(62.0)
    finally:
        app.shutdown()


def test_cruise_snubs_the_drums_instead_of_dragging_them_down_a_grade():
    """A held application empties the air tanks and fades the shoes.

    Cruise trimmed the service brake proportionally, which on a long grade
    settled into a permanent light application: the compressor lost ground
    until the spring brakes set and stopped the truck dead on a downhill
    (bench trace, 2026-07-25: 125 psi to 74 in twenty-two seconds).
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        driving, speeds = _grade_hold(app, -0.06, seconds=80.0)
        t = driving.truck
        # The grade is held, and held without the drums paying for it: full
        # tanks, cool shoes, no spring brakes.
        assert max(speeds) <= 66.0, max(speeds)
        assert min(speeds) > 30.0, min(speeds)
        assert not t.air_brakes_holding
        assert t.air_pressure_psi >= 100.0, t.air_pressure_psi
        assert t.brake_temp_c < t.brake_fade_onset_c, t.brake_temp_c
    finally:
        app.shutdown()


def test_cruise_leaves_the_drivers_own_jake_alone():
    """Cruise releases only the retarder stages it raised itself."""
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        open_limits(driving)
        driving.trip.traffic_context = lambda: None
        t = driving.truck
        t.start_engine()
        t.set_air_ready(parking_brake=False)
        t.transmission.gear = t.transmission.num_gears
        t.velocity_mps = 62.0 / 2.23694
        t.grade = 0.0
        driving._engage_cruise(62.0)
        t.engine_brake_stage = 2  # the driver's own selection

        for _ in range(60):
            driving._update_cruise(1 / 60, False, False, False)

        assert t.engine_brake_stage == 2
        assert driving._cruise_jake_stage == 0
    finally:
        app.shutdown()


# -- predictive cruise ------------------------------------------------------------


def _hill_road(driving, *, flat_mi, grade, climb_mi):
    """Flat, then a sustained climb, then flat, anchored where the truck is."""
    start = driving.trip.position_mi

    def grade_at(mile):
        offset = mile - start
        if offset < flat_mi:
            return 0.0
        return grade if offset < flat_mi + climb_mi else 0.0

    driving.trip.grade_at = grade_at
    return start


def _cruising(app, set_mph=62.0):
    driving = start_drive(app)
    quiet_trip(driving)
    open_limits(driving)
    driving.trip.traffic_context = lambda: None
    app.ctx.settings.automatic_transmission = True
    t = driving.truck
    t.transmission.automatic = True
    t.cargo_kg = 18_000.0
    t.start_engine()
    t.set_air_ready(parking_brake=False)
    t.velocity_mps = set_mph / 2.23694
    t.transmission.gear = t.transmission.num_gears
    driving._engage_cruise(set_mph)
    return driving


def test_predictive_cruise_banks_speed_before_a_climb():
    """The preview reads the grade profile and enters the pull carrying more.

    Momentum banked on the flat is speed the truck keeps most of the way up,
    which is the whole point of a predictive system reading a stored road
    profile.
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        driving = _cruising(app)
        _hill_road(driving, flat_mi=0.5, grade=0.04, climb_mi=1.0)
        driving.truck.grade = 0.0
        app.ctx.settings.predictive_cruise = True
        assert driving._predictive_cruise_bias(62.0) > 1.0

        # Turned off, cruise plans nothing and holds the number it was given.
        app.ctx.settings.predictive_cruise = False
        assert driving._predictive_cruise_bias(62.0) == 0.0
    finally:
        app.shutdown()


def test_predictive_cruise_finds_a_short_hill():
    """A half-mile hill must not average away inside the preview.

    Averaging the whole preview, a half-mile four percent pull came out at
    1.3 percent -- under the threshold -- so the hills that gain the most from
    banked momentum were exactly the ones the preview skipped (bench,
    2026-07-25). The windowed reading finds them.
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        driving = _cruising(app)
        _hill_road(driving, flat_mi=0.3, grade=0.04, climb_mi=0.5)
        driving.truck.grade = 0.0
        climb_ahead, _ = driving._grade_extremes_ahead()
        assert climb_ahead >= 0.03, climb_ahead
        assert driving._predictive_cruise_bias(62.0) > 1.0
    finally:
        app.shutdown()


def test_predictive_cruise_holds_at_a_crest_but_never_slows_the_truck():
    """Near the top it stops reaching for speed; it does not give speed away.

    An earlier cut returned a flat four mph giveaway and cost a 2 percent pull
    three mph it had been holding comfortably (bench, 2026-07-25).
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        driving = _cruising(app)
        start = _hill_road(driving, flat_mi=0.0, grade=0.04, climb_mi=0.2)
        driving.trip.position_mi = start
        driving.truck.grade = 0.04
        driving.truck.velocity_mps = 55.0 / 2.23694
        bias = driving._predictive_cruise_bias(62.0)
        assert bias < 0.0
        # It brings the target down to the speed on the clock, no further.
        assert 62.0 + bias >= driving.truck.speed_mph - 0.01
        assert bias >= -PCC_CREST_SAG_MPH

        # A truck still holding its number at a crest is left alone.
        driving.truck.velocity_mps = 62.0 / 2.23694
        assert driving._predictive_cruise_bias(62.0) == 0.0
    finally:
        app.shutdown()


def test_predictive_cruise_shaves_before_a_descent():
    """Speed added just before a downgrade comes back out through the brakes."""
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        driving = _cruising(app)
        _hill_road(driving, flat_mi=0.4, grade=-0.05, climb_mi=1.0)
        driving.truck.grade = 0.0
        assert driving._predictive_cruise_bias(62.0) < 0.0
    finally:
        app.shutdown()


def test_predictive_cruise_never_banks_past_the_posted_limit():
    """Momentum for a hill is not a licence to speed."""
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        driving = _cruising(app, set_mph=55.0)
        driving.trip.speed_limit_at = lambda mile: (55.0, None)
        _hill_road(driving, flat_mi=0.5, grade=0.06, climb_mi=1.0)
        driving.truck.grade = 0.0
        for _ in range(240):
            driving._update_cruise(1 / 60, False, False, False)
            driving.truck.update(1 / 60)
        assert driving.truck.speed_mph <= 55.0 + ACC_LIMIT_OFFSET_MPH + 0.5
    finally:
        app.shutdown()


def test_cruise_says_when_a_climb_has_beaten_it():
    """The climb side owes the driver the same honesty the descent side gives.

    Terse speech keeps it: the engine note and the downshifts already say the
    truck is working, and a terse player asked for less.
    """
    from freight_fate.app import App

    for verbosity, expected in ((1, True), (0, False)):
        app = App()
        events: list[str] = []
        app.ctx.say_event = lambda text, interrupt=False, sink=events, **_: sink.append(text)
        try:
            app.ctx.settings.speech_verbosity = verbosity
            driving = _cruising(app)
            driving.trip.grade_at = lambda mile: 0.07
            for _ in range(90 * 60):
                driving.truck.grade = 0.07
                driving._update_cruise(1 / 60, False, False, False)
                if driving.truck.transmission.automatic:
                    driving.truck.auto_shift()
                driving.truck.update(1 / 60)
            said = sum("still losing the grade" in e for e in events)
            assert bool(said) is expected, (verbosity, events[-3:])
            if expected:
                assert said == 1  # once a hill, not once a second
        finally:
            app.shutdown()


def test_climb_cue_stays_quiet_when_cruise_is_winning():
    """The ported dev guards (f23a97ec): a limit rise that jumps the target
    well above current speed floors the throttle on near-level road -- that
    is acceleration toward the number, not defeat, and it must stay silent
    (71-and-climbing-to-77 was announced as losing the grade; playtest
    transcript 2026-07-27)."""
    from freight_fate.app import App

    app = App()
    events: list[str] = []
    app.ctx.say_event = lambda text, interrupt=False, sink=events, **_: sink.append(text)
    try:
        app.ctx.settings.speech_verbosity = 1
        driving = _cruising(app)
        # The target sits well above the truck -- the limit-rise shape --
        # so cruise floors the pedal while genuinely accelerating.
        driving.truck.velocity_mps = 50.0 / 2.23694
        # Road the G key calls level: below the beaten-grade floor.
        driving.trip.grade_at = lambda mile: 0.005
        for _ in range(30 * 60):
            driving.truck.grade = 0.005
            driving._update_cruise(1 / 60, False, False, False)
            if driving.truck.transmission.automatic:
                driving.truck.auto_shift()
            driving.truck.update(1 / 60)
        assert not any("still losing the grade" in e for e in events), events[-3:]
    finally:
        app.shutdown()


def test_cruise_leaves_the_retarder_alone_when_descent_control_is_off():
    """The stalk decides. The drums still hold the speed either way.

    Turning descent control off is the driver saying they manage grades
    themselves, and a real truck's cruise does not flip the engine brake on
    for you. It must cost the quiet retarder, never the ability to hold the
    set speed -- that was the runaway this whole area started with.
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        app.ctx.settings.descent_speed_control = "off"
        driving = _cruising(app)
        driving.trip.grade_at = lambda mile: -0.06
        speeds = []
        for _ in range(60 * 60):
            driving.truck.grade = -0.06
            ramp = (1 / 60) * 2.2
            driving.truck.throttle = max(0.0, driving.truck.throttle - ramp * 2)
            driving.truck.brake = max(0.0, driving.truck.brake - ramp * 3)
            driving._update_cruise(1 / 60, False, False, False)
            if driving.truck.transmission.automatic:
                driving.truck.auto_shift()
            driving.truck.update(1 / 60)
            speeds.append(driving.truck.speed_mph)
        assert driving._cruise_jake_stage == 0
        assert driving.truck.engine_brake_stage == 0
        assert max(speeds) <= 68.0, max(speeds)
        assert not driving.truck.air_brakes_holding
    finally:
        app.shutdown()


# -- the retarder answers grades, not corners -----------------------------------


def test_cruise_slows_for_a_level_bend_on_the_drums_not_the_retarder():
    """A corner is a target speed, and target speeds belong to the drums.

    Adaptive cruise capped its working target to the bend's advisory and then
    reached for the retarder against the resulting overspeed, at three
    quarters of a mile per hour over, on flat road -- a tester heard the
    engine brake in corners three times running. The CDL rule is to reach a
    safe speed BEFORE a bend and pull through, because braking mid-corner is
    what locks a wheel and jackknifes a trailer, and a retarder drives the
    tractor's rear wheels alone. Jacobs say the same: sustained speed
    control, "not a substitute for a service braking system".

    Bench, level road, 62 set against a 45 advisory: the retarder was up for
    350 of 1200 frames at stage three, once per bend over a route of five
    (2026-08-11). It must be silent, and cruise must still arrive.
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        stages = []
        _, speeds = _grade_hold(app, 0.0, seconds=60.0, advisory=45.0, stages=stages)
        assert max(stages) == 0, max(stages)
        # And it genuinely slows for the bend -- silence must not mean cruise
        # simply carried the set speed through the corner.
        assert speeds[-1] <= 48.0, speeds[-1]
        assert speeds[-1] >= 38.0, speeds[-1]
    finally:
        app.shutdown()


def test_cruise_still_retards_for_a_bend_on_a_downgrade():
    """A bend on a grade retards -- that is the grade's doing, not the bend's.

    Removing the retarder here would put a six percent descent on the drums
    alone: past fade onset in four and a half minutes (bench, 2026-08-11).
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        stages = []
        _, speeds = _grade_hold(app, -0.06, seconds=60.0, advisory=45.0, stages=stages)
        assert max(stages) >= 1, max(stages)
        # Holding the advisory, not running away down the hill.
        assert max(speeds[-600:]) <= 55.0, max(speeds[-600:])
    finally:
        app.shutdown()


def test_cruise_holds_a_sustained_grade_on_the_retarder():
    """The descent case, pinned: a plain downgrade is the retarder's own job."""
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        stages = []
        driving, speeds = _grade_hold(app, -0.06, seconds=60.0, stages=stages)
        assert max(stages) >= 1, max(stages)
        assert driving.truck.brake_temp_c < driving.truck.brake_fade_onset_c
        assert max(speeds) <= 66.0, max(speeds)
    finally:
        app.shutdown()


def test_cruise_gives_the_retarder_back_when_the_grade_runs_out_in_a_bend():
    """The grade ends under the corner: the retarder goes with it.

    Handing the number to the drums used to leave whatever stage cruise had
    raised on the hill still barking, all the way through the level bend --
    182 of 600 frames at stage three (bench, 2026-08-11). Only the stage
    cruise raised itself is released; the driver's own switch is untouched.
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        app.ctx.settings.descent_speed_control = "realistic"
        driving = _cruising(app)
        driving.trip.engine_brake_ban_at = lambda mile: None
        driving.trip.grade_at = lambda mile: -0.06
        t = driving.truck
        dt = 1 / 60
        for _ in range(int(12 * 60)):
            t.grade = -0.06
            ramp = dt * 2.2
            t.throttle = max(0.0, t.throttle - ramp * 2)
            t.brake = max(0.0, t.brake - ramp * 3)
            driving._update_cruise(dt, False, False, False)
            t.auto_shift()
            t.update(dt)
        assert driving._cruise_jake_stage >= 1, driving._cruise_jake_stage

        # The bend arrives and the road levels out underneath it.
        driving._cruise_curve_mph = 45.0
        driving._cruise_curve_end_mi = driving.trip.position_mi + 5.0
        driving.trip.grade_at = lambda mile: 0.0
        stages = []
        for _ in range(int(10 * 60)):
            t.grade = 0.0
            ramp = dt * 2.2
            t.throttle = max(0.0, t.throttle - ramp * 2)
            t.brake = max(0.0, t.brake - ramp * 3)
            driving._update_cruise(dt, False, False, False)
            t.auto_shift()
            t.update(dt)
            stages.append(t.engine_brake_stage)
        assert max(stages) == 0, max(stages)
        assert driving._cruise_jake_stage == 0
    finally:
        app.shutdown()


def test_auto_jake_does_not_chase_a_bend_advisory():
    """The AMT retarder manager holds the driver's number, not the corner's.

    The third retarder path: the driver armed the stalk with J, so auto mode
    owns the stage. It targets the speed it was armed at (or descent
    control's ceiling on a grade) and never reads a curve advisory, so a bend
    cannot step it up. Pinned because it is the one path that would otherwise
    reintroduce the corner bark by another route.
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = speech_stub()
    try:
        app.ctx.settings.descent_speed_control = "realistic"
        driving = _cruising(app)
        driving.trip.engine_brake_ban_at = lambda mile: None
        driving.trip.grade_at = lambda mile: 0.0
        driving._cancel_cruise()
        t = driving.truck
        t.grade = 0.0
        t.throttle = 0.0
        driving._auto_jake = True
        driving._auto_jake_hold_mph = max(5.0, t.speed_mph)
        t.engine_brake_stage = 1  # the controller climbs from here
        driving._cruise_curve_mph = 45.0
        driving._cruise_curve_end_mi = driving.trip.position_mi + 5.0

        stages = []
        for _ in range(int(20 * 60)):
            t.grade = 0.0
            t.throttle = 0.0
            driving._update_auto_jake(1 / 60)
            t.auto_shift()
            t.update(1 / 60)
            stages.append(t.engine_brake_stage)
        assert max(stages) == 1, max(stages)
    finally:
        app.shutdown()


def test_descent_control_cue_does_not_chant_through_rolling_country():
    """Every dip crosses the trigger; the announcement needs its own clock."""
    import math

    from freight_fate.app import App

    app = App()
    events = []
    app.ctx.say_event = speech_stub(events)
    try:
        driving = _cruising(app)
        driving.trip.grade_at = lambda mile: 0.05 * math.sin(2 * math.pi * mile / 2.0)
        for _ in range(6 * 60 * 60):
            driving.truck.grade = driving.trip.grade_at(driving.trip.position_mi)
            ramp = (1 / 60) * 2.2
            driving.truck.throttle = max(0.0, driving.truck.throttle - ramp * 2)
            driving.truck.brake = max(0.0, driving.truck.brake - ramp * 3)
            driving._update_cruise(1 / 60, False, False, False)
            if driving.truck.transmission.automatic:
                driving.truck.auto_shift()
            driving.truck.update(1 / 60)
            driving.trip.position_mi += driving.truck.speed_mph / 60.0 / 3600.0
        holding = sum("Descent control holding" in e for e in events)
        assert holding <= 3, holding
    finally:
        app.shutdown()


# -- the speed keeper's air budget ----------------------------------------------


def _count_brake_applications(monkeypatch):
    """Count the rising-edge brake applications the air system charges for."""
    from freight_fate.sim.vehicle import TruckState

    tally = {"applications": 0, "rise": 0.0}
    original = TruckState._consume_brake_air

    def counting(self, dt):
        rising = max(0.0, min(1.0, self.brake) - self._last_service_air_application)
        if rising > 1e-9:
            tally["applications"] += 1
            tally["rise"] += rising
        original(self, dt)

    monkeypatch.setattr(TruckState, "_consume_brake_air", counting)
    return tally


def _keeper_on_a_grade(app, monkeypatch, *, grade_pct: float, limit_mph: float = 15.0):
    """Speed keeper holding a zone limit down a steady grade."""

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())
    driving = start_drive(app)
    quiet_trip(driving)
    driving.trip.traffic_context = lambda: None
    driving.trip.grade_at = lambda mile: grade_pct / 100.0
    driving.trip.speed_limit_at = lambda mile: (limit_mph, "facility access road")
    driving.handle_event(key_event(pygame.K_e))
    driving.truck.cargo_kg = 15000.0
    driving.truck.velocity_mps = 25.0 / 2.23694
    driving.handle_event(key_event(pygame.K_k))
    assert driving._keeper_mph is not None
    return driving


def test_speed_keeper_holds_a_zone_speed_without_emptying_the_tanks(monkeypatch):
    """The report this exists for: the assist ran the truck out of air.

    A mild downgrade put the old proportional trim right on its own braking
    deadband, so it made and released a brake application several times a
    second. The air system charges a whole application on every rise, so the
    tanks went 125 psi to 41 in eighteen seconds, the spring brakes set, and
    the truck stopped dead in a 15 mph zone.
    """
    from freight_fate.app import App

    app = App()
    try:
        driving = _keeper_on_a_grade(app, monkeypatch, grade_pct=-2.0)
        t = driving.truck
        tally = _count_brake_applications(monkeypatch)
        for _ in range(60 * 60):
            driving.update(1 / 60)
        assert not t.spring_brakes_active
        assert not t.air_low_warning, t.air_pressure_psi
        assert t.air_pressure_psi > 100.0, t.air_pressure_psi
        # Still driving the zone a minute later, not parked in it.
        assert driving._keeper_mph is not None
        assert t.speed_mph > 5.0
        # A snub is one application held to the number, so a minute of holding
        # costs a handful of them rather than one per frame.
        assert tally["applications"] <= 20, tally
    finally:
        app.shutdown()


def test_speed_keeper_says_when_it_cannot_hold_the_speed(monkeypatch):
    """Hot brakes on a real grade: the keeper is out of pedal and says so.

    An assist that quietly holds the wrong speed is the one failure a driver
    who cannot see the speedometer has no way to catch.
    """
    from freight_fate.app import App

    app = App()
    events = []
    try:
        driving = _keeper_on_a_grade(app, monkeypatch, grade_pct=-6.0)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        t = driving.truck
        for _ in range(60 * 30):
            t.brake_temp_c = max(t.brake_temp_c, 750.0)  # faded past any authority
            driving.update(1 / 60)
        said = [
            e
            for e in events
            if e == "Speed keeper cannot hold 15 miles per hour on this grade. "
            "Apply service brakes."
        ]
        assert len(said) == 1, events
    finally:
        app.shutdown()
