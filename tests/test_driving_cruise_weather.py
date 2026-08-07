"""Cruise-control, ACC, hazard timing, and real-weather driving tests."""

import pygame
import pytest
from driving_feature_helpers import (
    key_event,
    open_limits,
    quiet_trip,
    start_drive,
)
from speech_capture import speech_stub

from freight_fate.states.driving import CRUISE_GRADE_BEATEN_S, SPEEDING_HOLD_S

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
        assert base == pytest.approx(60.0, abs=1.0)

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
            app.ctx.audio, "play", lambda key, volume=1.0: played.append((key, volume))
        )
        driving.truck.start_engine()
        driving.truck.transmission.gear = 3
        driving.truck.velocity_mps = 5.0

        driving.update(0.0)

        assert ("vehicle/gear_shift", 0.65) in played
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
def test_adaptive_cruise_follows_modeled_traffic(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TrafficLead

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
        open_limits(driving)  # isolate following from the limit cap
        driving.trip.traffic_leads = [
            TrafficLead(driving.trip.position_mi + 0.08, 45.0, "slow lead traffic", 4.0)
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


@pytest.mark.parametrize(
    ("speed_mph", "timer_before", "dt"),
    [
        (45.0, SPEEDING_HOLD_S - 0.05, 0.1),
        (46.0, SPEEDING_HOLD_S - 0.05, 0.1),
        (55.0, SPEEDING_HOLD_S - 0.25, 0.5),
        (65.0, SPEEDING_HOLD_S - 0.5, 1.0),
        (70.0, SPEEDING_HOLD_S - 1.0, 1.5),
    ],
)
@pytest.mark.smoke
def test_adaptive_cruise_limit_drop_does_not_trigger_speeding_strike(
    monkeypatch, speed_mph, timer_before, dt
):
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
        driving._speeding_timer = timer_before

        driving.update(dt)

        assert driving._acc_limit_capped
        assert driving.truck.brake > 0.0
        assert driving.speeding_strikes == 0
        assert not any("Speeding strike" in e for e in events)
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
    from freight_fate.sim.trip import TrafficLead
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

        driving.trip.traffic_leads = [
            TrafficLead(driving.trip.position_mi + 0.08, 65.0, "slow lead traffic", 4.0)
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
        assert events[-1].startswith("New achievement! Bumper-to-Bumper Blues.")
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
    stop from 65 to 25 mph alone takes ~5 s. The deadline must be the braking
    time from the current speed plus the rolled reaction slack."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import HAZARD_SAFE_MPH, MPH_PER_MPS, G

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        t.velocity_mps = 29.0  # ~65 mph
        t.grip, t.grade = 1.0, 0.0
        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 3.0})
        driving._handle_trip_event(hazard)
        brake_s = (t.speed_mph - HAZARD_SAFE_MPH) / MPH_PER_MPS / (G * t.specs.max_brake_decel_g)
        assert driving._hazard_deadline == pytest.approx(brake_s + 3.0, abs=0.01)
        assert driving._hazard_deadline > 7.5
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
    from freight_fate.sim.weather import WeatherKind

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
        provider.is_refreshing = True
        driving.handle_event(event)
        assert "Live weather is updating for your current location" in spoken[-1]
        provider.is_refreshing = False
        provider.kind = None
        provider.is_unavailable = True
        driving.trip.update(0.0)
        driving.handle_event(event)
        assert spoken[-1].startswith("Simulated fallback weather:")
        assert "Ahead:" in spoken[-1]
    finally:
        app.shutdown()


def test_old_but_freshly_fetched_weather_is_live_across_v_and_status(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.weather import WeatherKind

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

    finally:
        app.shutdown()


def test_limit_drop_earns_braking_grace(monkeypatch):
    """A slowing driver gets compliance time after a posted-limit drop."""
    from freight_fate.app import App

    app = App()
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.zones = []
        driving.trip.patrols = []
        truck = driving.truck
        truck.velocity_mps = 65.0 / 2.23694
        truck.throttle = 0.0

        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda mi: (65.0, None))
        driving._update_speeding(0.1)
        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda mi: (50.0, None))

        before = driving.speeding_strikes
        for _ in range(70):
            driving._update_speeding(0.1)
        assert driving.speeding_strikes == before

        for _ in range(100):
            driving._update_speeding(0.1)
        assert driving.speeding_strikes == before + 1

        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda mi: (35.0, None))
        truck.throttle = 1.0
        strikes = driving.speeding_strikes
        for _ in range(70):
            driving._update_speeding(0.1, accelerator_held=True)
        assert driving.speeding_strikes == strikes + 1
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


# -- holding the set speed on a grade --------------------------------------------


def _grade_hold(app, grade, *, set_mph=62.0, seconds=90.0, settle_s=20.0):
    """Run cruise at a set speed on a fixed grade; return the speed trace.

    Mirrors the driving loop's own order for the pieces a grade exercises:
    pedals decay when nothing is held, cruise runs, the automatic gets its
    turn, then the physics steps.
    """
    driving = start_drive(app)
    quiet_trip(driving)
    open_limits(driving)
    driving.trip.traffic_context = lambda: None
    driving.trip.grade_at = lambda mile: grade
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
        t.grade = 0.0 if step < settle_s * 60 else grade
        ramp = dt * 2.2
        t.throttle = max(0.0, t.throttle - ramp * 2)
        t.brake = max(0.0, t.brake - ramp * 3)
        driving._update_cruise(dt, False, False, False)
        if t.transmission.automatic and t.engine_on:
            t.auto_shift()
        t.update(dt)
        if step >= settle_s * 60:
            speeds.append(t.speed_mph)
    return driving, speeds


@pytest.mark.smoke
def test_cruise_does_not_run_away_down_a_grade():
    """Cutting fuel is not speed control on a downgrade.

    Cruise had no authority over the truck from above unless a lead or a
    lower posted limit was already pulling the target down, so gravity simply
    carried it: the player reported fifteen-plus mph over with no warning
    (playtest, 2026-07-27). The engine brake now answers the overspeed and
    the drums snub when it is not enough.
    """
    from freight_fate.app import App

    for grade in (-0.02, -0.04, -0.06):
        app = App()
        app.ctx.say_event = lambda text, interrupt=False: None
        try:
            _, speeds = _grade_hold(app, grade)
            assert max(speeds) <= 67.0, (grade, max(speeds))
            # And it is holding a speed, not braking the truck to a stop.
            assert min(speeds[-600:]) >= 55.0, (grade, min(speeds[-600:]))
        finally:
            app.shutdown()


def test_cruise_snubs_the_drums_instead_of_dragging_them_down_a_grade():
    """A held application empties the air tanks and fades the shoes.

    The service brake used to be trimmed proportionally, which on a long
    grade settles into a permanent light application: the compressor loses
    ground until the spring brakes set and stop the truck dead on a downhill.
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = lambda text, interrupt=False: None
    try:
        driving, speeds = _grade_hold(app, -0.06, seconds=80.0)
        t = driving.truck
        assert max(speeds) <= 67.0, max(speeds)
        assert min(speeds) > 30.0, min(speeds)
        assert not t.air_brakes_holding
        assert t.air_pressure_psi >= 100.0, t.air_pressure_psi
        assert t.brake_temp_c < t.specs.brake_fade_temp_c, t.brake_temp_c
    finally:
        app.shutdown()


def test_cruise_answers_a_climb_with_the_grade_feed_forward():
    """The old integral-only loop needed ten seconds to reach full throttle.

    A climb takes speed away faster than that, so cruise arrived late every
    time. The feed-forward asks the truck's own physics what holds the grade.
    """
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = lambda text, interrupt=False: None
    try:
        driving, speeds = _grade_hold(app, 0.02, seconds=40.0)
        # A 2 percent pull is well inside what the truck has: hold it.
        assert min(speeds) >= 57.0, min(speeds)
        assert speeds[-1] >= 58.0, speeds[-1]
    finally:
        app.shutdown()


def test_cruise_hands_back_only_the_engine_brake_it_switched_on():
    """The driver's own jake switch survives a cruise session ending."""
    from freight_fate.app import App

    app = App()
    app.ctx.say_event = lambda text, interrupt=False: None
    try:
        driving, _ = _grade_hold(app, -0.06, seconds=30.0)
        assert driving.truck.engine_brake  # cruise reached for it on the grade
        assert driving._cruise_jake_on
        driving._cancel_cruise()
        assert not driving.truck.engine_brake
        assert not driving._cruise_jake_on
    finally:
        app.shutdown()

    app = App()
    app.ctx.say_event = lambda text, interrupt=False: None
    try:
        driving, _ = _grade_hold(app, 0.0, seconds=5.0, settle_s=0.0)
        driving.truck.engine_brake = True  # the driver's own J
        driving._cruise_jake_on = False
        driving._cancel_cruise()
        assert driving.truck.engine_brake
    finally:
        app.shutdown()


def test_cruise_says_when_the_downgrade_has_beaten_it(monkeypatch):
    """Silence was the complaint: fifteen over and no word about it."""
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        open_limits(driving)
        driving.trip.traffic_context = lambda: None
        t = driving.truck
        t.start_engine()
        t.set_air_ready(parking_brake=False)
        t.cargo_kg = 18_000.0
        t.velocity_mps = 60.0 / 2.23694
        t.transmission.gear = t.transmission.num_gears
        driving._engage_cruise(60.0)
        t.grade = -0.08
        t.velocity_mps = 80.0 / 2.23694  # the grade has plainly won
        # The verdict is debounced: the grade has to keep winning, because a
        # single frame is also what a gear change looks like.
        for _ in range(int(CRUISE_GRADE_BEATEN_S * 60) + 60):
            t.velocity_mps = 80.0 / 2.23694
            driving._update_cruise(1 / 60, False, False, False)
        assert any("cannot hold this downgrade" in line for line in spoken), spoken
        said = len(spoken)
        for _ in range(120):
            t.velocity_mps = 80.0 / 2.23694
            driving._update_cruise(1 / 60, False, False, False)
        assert len(spoken) == said  # once per grade, not every frame
    finally:
        app.shutdown()


def test_the_cruise_grade_verdict_follows_the_speech_verbosity(monkeypatch):
    """It goes out on the event voice, so it obeys terse speech like the rest.

    Terse keeps the fact and drops the instruction, the way the hazard cue
    drops its "Brake now!" prefix.
    """
    from freight_fate.app import App

    for verbosity, expect, absent in (
        (2, "Cruise cannot hold this downgrade", None),
        (0, "Cruise losing the downgrade", "Brake"),
    ):
        app = App()
        spoken = []
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        try:
            app.ctx.settings.speech_verbosity = verbosity
            driving = start_drive(app)
            quiet_trip(driving)
            open_limits(driving)
            driving.trip.traffic_context = lambda: None
            t = driving.truck
            t.start_engine()
            t.set_air_ready(parking_brake=False)
            t.velocity_mps = 60.0 / 2.23694
            t.transmission.gear = t.transmission.num_gears
            driving._engage_cruise(60.0)
            t.grade = -0.08
            for _ in range(int(CRUISE_GRADE_BEATEN_S * 60) + 60):
                t.velocity_mps = 80.0 / 2.23694
                driving._update_cruise(1 / 60, False, False, False)
            said = [line for line in spoken if line.startswith("Cruise")]
            assert any(expect in line for line in said), (verbosity, spoken)
            if absent is not None:
                assert not any(absent in line for line in said), (verbosity, said)
        finally:
            app.shutdown()


def test_cruise_does_not_cry_defeat_while_it_is_still_accelerating(monkeypatch):
    """Under the target is not the same as beaten.

    Engaging on a grade below the set speed -- or dialing the target up with
    the plus key -- put the truck several mph under its number with the
    throttle still winding on, and cruise announced that the climb had beaten
    it while it was accelerating to a speed it would have reached (bench
    trace, 2026-07-27, at the moment of engagement).
    """
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        open_limits(driving)
        driving.trip.traffic_context = lambda: None
        t = driving.truck
        t.start_engine()
        t.set_air_ready(parking_brake=False)
        t.cargo_kg = 0.0  # light: this climb is well inside what it can pull
        t.velocity_mps = 55.0 / 2.23694
        t.transmission.gear = t.transmission.num_gears
        driving._engage_cruise(70.0)  # 15 mph under, on a gentle climb
        t.grade = 0.01
        for _ in range(120):
            driving._update_cruise(1 / 60, False, False, False)
            t.update(1 / 60)
        assert not any("climb" in line for line in spoken), spoken
    finally:
        app.shutdown()


def test_the_climb_verdict_does_not_fire_on_a_downgrade(monkeypatch):
    """The verdict follows the road, not the sign of the speed error."""
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        open_limits(driving)
        driving.trip.traffic_context = lambda: None
        t = driving.truck
        t.start_engine()
        t.set_air_ready(parking_brake=False)
        t.velocity_mps = 55.0 / 2.23694
        t.transmission.gear = t.transmission.num_gears
        driving._engage_cruise(70.0)
        # Well under the target, but the road is going down: whatever this is,
        # it is not a climb beating cruise.
        t.grade = -0.008
        for _ in range(300):
            driving._announce_cruise_grade_verdict(1 / 60, 15.0, closing=False)
        assert not any("climb" in line for line in spoken), spoken
    finally:
        app.shutdown()


def test_a_gear_change_is_not_the_hill_winning(monkeypatch):
    """The driveline opens on every shift, and that is not a verdict.

    ``drive_ratio`` is 0 while the transmission is shifting, so ``drive_force``
    is exactly 0 for those frames -- which read as "the hill has beaten us"
    even while the truck was accelerating hard. A 50-to-75 limit rise raised
    the cruise target 25 mph, the box shifted, and cruise announced defeat at
    71 mph on its way to 77 (playtest transcript, 2026-07-27).
    """
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        open_limits(driving)
        driving.trip.traffic_context = lambda: None
        t = driving.truck
        t.start_engine()
        t.set_air_ready(parking_brake=False)
        t.velocity_mps = 56.0 / 2.23694
        t.transmission.gear = t.transmission.num_gears
        driving._engage_cruise(80.0)  # the target jumps well above current speed
        t.grade = 0.02
        t.throttle = 1.0
        t.transmission._shift_timer = 0.5  # mid-shift: no torque path at all
        assert t.drive_force() == 0.0  # the condition the old gate tripped on
        for _ in range(30):
            driving._announce_cruise_grade_verdict(1 / 60, 24.0, closing=False)
        assert not any("climb" in line for line in spoken), spoken
    finally:
        app.shutdown()


def test_cruise_concedes_a_climb_only_after_the_grade_keeps_winning(monkeypatch):
    """Sustained, not instantaneous -- but it still gets said."""
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        open_limits(driving)
        t = driving.truck
        t.start_engine()
        t.set_air_ready(parking_brake=False)
        t.cargo_kg = 20_000.0
        t.velocity_mps = 45.0 / 2.23694
        t.transmission.gear = t.transmission.num_gears
        driving._engage_cruise(65.0)
        t.grade = 0.06  # a real hill this truck cannot pull in top gear
        t.throttle = 1.0
        # Under the debounce: still silent.
        for _ in range(int(CRUISE_GRADE_BEATEN_S * 60) - 30):
            driving._announce_cruise_grade_verdict(1 / 60, 20.0, closing=False)
        assert not any("climb" in line for line in spoken), spoken
        # Past it: said once, and only once.
        for _ in range(180):
            driving._announce_cruise_grade_verdict(1 / 60, 20.0, closing=False)
        assert sum("climb" in line for line in spoken) == 1, spoken
    finally:
        app.shutdown()


def test_a_near_level_road_never_reads_as_a_climb(monkeypatch):
    """G calls half a percent level; cruise must not call it a climb."""
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        open_limits(driving)
        t = driving.truck
        t.start_engine()
        t.set_air_ready(parking_brake=False)
        t.velocity_mps = 56.0 / 2.23694
        driving._engage_cruise(80.0)
        t.grade = 0.008  # 0.8 percent: the G key calls this level road
        t.throttle = 1.0
        for _ in range(600):
            driving._announce_cruise_grade_verdict(1 / 60, 24.0, closing=False)
        assert not spoken, spoken
    finally:
        app.shutdown()
