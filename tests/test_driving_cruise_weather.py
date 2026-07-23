"""Cruise-control, ACC, hazard timing, and real-weather driving tests."""

import pygame
import pytest
from driving_feature_helpers import (
    key_event,
    open_limits,
    quiet_trip,
    start_drive,
)

from freight_fate.states.driving import SPEEDING_HOLD_S

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
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: said.append(text))
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
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: said.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: said.append(text))
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
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: said.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
        open_limits(driving)
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
    from freight_fate.sim.trip import NPCVehicle
    from freight_fate.sim.weather import WeatherKind

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: said.append(text))
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
    time the truck actually needs -- fade, wear, and load included -- from
    the current speed, plus the rolled reaction slack."""
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
        assert driving._hazard_deadline == pytest.approx(brake_s + 3.0, abs=0.01)
        assert driving._hazard_deadline > 7.5
    finally:
        app.shutdown()


def test_automatic_emergency_braking_engages_once_and_cancels_cruise(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say_event = lambda text, interrupt=False: spoken.append((text, interrupt))
    try:
        driving = start_drive(app)
        driving.truck.velocity_mps = 25.0
        driving._cruise_mph = 55.0
        driving._hazard_deadline = driving._brake_budget_s()
        driving._update_hazard(0.01)
        driving._update_hazard(0.01)
        assert driving.truck.brake == 1.0
        assert driving._cruise_mph is None
        assert [text for text, _ in spoken].count("Emergency braking engaged.") == 1
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
    app.ctx.say_event = lambda text, interrupt=False: spoken.append(text)
    try:
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
    from freight_fate.states.driving import HAZARD_CREEP_MPH

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
            driving._brake_budget_s(HAZARD_CREEP_MPH) + 3.0, abs=0.01
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
    app.ctx.say_event = lambda text, interrupt=False: spoken.append(text)
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
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(app.ctx, "real_weather_provider", lambda: provider)
    app.ctx.settings.real_weather = True
    app.ctx.settings.live_weather_controls_calendar = False
    try:
        driving = start_drive(app)
        driving._speak_weather()
        assert "Live weather is still loading" in spoken[-1]
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

        before = driving.speeding_strikes
        for _ in range(70):  # 7 s: inside the (65-50)/2 = 7.5 s grace
            driving._update_speeding(0.1)
        assert driving.speeding_strikes == before

        # Grace spent, still 15 over with no brake: the normal hold applies.
        for _ in range(100):  # 0.5 s of leftover grace + the 6 s hold, once
            driving._update_speeding(0.1)
        assert driving.speeding_strikes == before + 1

        # Second drop, but the driver stays on the throttle: no grace.
        monkeypatch.setattr(driving.trip, "speed_limit_at", lambda mi: (35.0, None))
        t.throttle = 1.0
        strikes = driving.speeding_strikes
        for _ in range(70):  # > SPEEDING_HOLD_S at 0.1 s steps
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


def test_overspeed_warning_speaks_then_chimes_until_compliant(monkeypatch):
    """The dash overspeed alert: spoken once when armed, chiming on an
    interval while over, disarmed by settling back under the limit -- and
    a fresh episode speaks again. Off means silent."""
    from freight_fate.app import App

    app = App()
    events, played = [], []
    monkeypatch.setattr(app.ctx.audio, "play", lambda key, **k: played.append(key))
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
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
