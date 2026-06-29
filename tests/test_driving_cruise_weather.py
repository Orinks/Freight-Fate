"""Cruise-control, ACC, hazard timing, and real-weather driving tests."""

import pygame
import pytest
from driving_feature_helpers import (
    key_event,
    open_limits,
    quiet_trip,
    start_drive,
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
        driving._destination_exit_taken = True          # isolate cruise from exit setup
        open_limits(driving)                           # isolate hold from the limit cap
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))   # engine on
        t.cargo_kg = 0.0
        t.grade = 0.0
        t.transmission.gear = 10
        t.velocity_mps = 26.8                          # ~60 mph
        t.throttle = 0.35
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph == pytest.approx(60.0, abs=1.0)
        for _ in range(60 * 15):                       # 15 seconds, no keys held
            driving.update(1 / 60)
        assert driving._cruise_mph is not None
        assert abs(t.speed_mph - 60.0) < 5.0
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
        open_limits(driving)                           # isolate from the limit cap
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8              # ~60 mph
        driving.handle_event(key_event(pygame.K_k))
        base = driving._cruise_mph
        assert base == pytest.approx(60.0, abs=1.0)

        driving.handle_event(key_event(pygame.K_EQUALS))   # + raises by a step
        assert driving._cruise_mph == pytest.approx(base + CRUISE_STEP_MPH)
        driving.handle_event(key_event(pygame.K_MINUS))    # - lowers it back
        assert driving._cruise_mph == pytest.approx(base)
        driving.handle_event(key_event(pygame.K_PLUS, "+"))
        assert driving._cruise_mph == pytest.approx(base + CRUISE_STEP_MPH)
        driving.handle_event(key_event(pygame.K_KP_MINUS, "-"))
        assert driving._cruise_mph == pytest.approx(base)

        for _ in range(20):                                # clamps at the max
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
        monkeypatch.setattr(app.ctx, "say",
                            lambda text, interrupt=True: said.append(text))
        # On a low-speed facility access road, cruise must not engage.
        driving.trip.speed_limit_at = lambda mile: (25.0, "facility access road")
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 4
        driving.truck.velocity_mps = 10.0              # ~22 mph, above the floor
        driving.handle_event(key_event(pygame.K_k))

        assert driving._cruise_mph is None
        assert any("not available" in s and "facility access road" in s
                   for s in said)
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
        monkeypatch.setattr(app.ctx, "say",
                            lambda text, interrupt=True: said.append(text))
        driving.handle_event(key_event(pygame.K_e))
        assert driving._cruise_mph is None
        driving.handle_event(key_event(pygame.K_EQUALS))
        assert driving._cruise_mph is None              # nothing to adjust
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
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
        t = driving.truck
        t.parking_brake = True                                  # cue only fires while set
        t.air_pressure_psi = t.specs.air_governor_cut_out_psi   # charged
        driving._air_ready_said = True                          # already announced

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
        monkeypatch.setattr(app.ctx.audio, "play",
                            lambda key, volume=1.0: played.append((key, volume)))
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


@pytest.mark.smoke
def test_adaptive_cruise_follows_npc_traffic(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import NPCVehicle

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
        open_limits(driving)
        driving.trip.npc_vehicles = [
            NPCVehicle("npc:acc", driving.trip.position_mi + 0.08,
                       44.0, 44.0, 0, "braking_traffic")
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
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
        # A posted limit well below the held set speed: predictive ACC must ease
        # off rather than carry the driver over the limit into a speeding strike.
        driving.trip.speed_limit_at = lambda mile: (45.0, None)
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0              # ~65 mph
        driving.truck.throttle = 0.8
        driving.handle_event(key_event(pygame.K_k))    # set cruise at ~65
        assert driving._cruise_mph > 60

        driving.update(1 / 60)

        assert driving._acc_limit_capped
        assert driving.truck.throttle < 0.8            # backed off the throttle
        assert driving.truck.brake > 0.0               # braking down toward the limit
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
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
        drop_at = driving.trip.position_mi + 0.4
        driving.trip.speed_limit_at = (
            lambda mile: (40.0, None) if mile >= drop_at else (65.0, None)
        )
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 30.4              # ~68 mph
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


@pytest.mark.smoke
def test_adaptive_cruise_ignores_far_small_limit_drop(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        drop_at = driving.trip.position_mi + 1.4
        driving.trip.speed_limit_at = (
            lambda mile: (60.0, None) if mile >= drop_at else (65.0, None)
        )
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 30.4              # ~68 mph
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
        driving.truck.velocity_mps = 28.2             # ~63 mph, 3 over a 60 limit
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
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 29.0
        driving.truck.throttle = 0.5
        driving.handle_event(key_event(pygame.K_k))

        driving.trip.npc_vehicles = [
            NPCVehicle("npc:weather-gap", driving.trip.position_mi + 0.08,
                       65.0, 65.0, 0, "steady_truck")
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
def test_adaptive_cruise_disables_before_restricted_zone(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind, Zone

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
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

        assert driving._cruise_mph is None
        assert events[-1] == (
            "In 2 miles, construction ahead. Speed limit 45. "
            "Adaptive cruise disabled; take manual speed control."
        )
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_adaptive_cruise_disables_for_heavy_traffic_zone_entry(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind, Zone

    app = App()
    events = []
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: events.append(text))
        monkeypatch.setattr(app.ctx, "say",
                            lambda text, interrupt=True: events.append(text))
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None

        zone = Zone(10.0, 15.0, 50.0, "heavy traffic")
        event = TripEvent(
            TripEventKind.ZONE_ENTER,
            "heavy traffic ahead. Speed limit 50.",
            {"zone": zone},
        )
        driving._handle_trip_event(event)

        assert driving._cruise_mph is None
        assert events[-2] == (
            "heavy traffic ahead. Speed limit 50. "
            "Adaptive cruise disabled; take manual speed control."
        )
        assert events[-1].startswith("New achievement! Bumper-to-Bumper Blues.")
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
        t.velocity_mps = 29.0          # ~65 mph
        t.grip, t.grade = 1.0, 0.0
        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 3.0})
        driving._handle_trip_event(hazard)
        brake_s = ((t.speed_mph - HAZARD_SAFE_MPH) / MPH_PER_MPS
                   / (G * t.specs.max_brake_decel_g))
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
        t.velocity_mps = 29.0          # ~65 mph
        damage_before = t.damage_pct

        held = set()

        class FakeKeys:
            def __getitem__(self, key):
                return key in held

        monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys())

        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 3.0})
        driving._handle_trip_event(hazard)
        for _ in range(int(60 * 1.5)):      # hearing the warning: no input yet
            driving.update(1 / 60)
        held.add(pygame.K_DOWN)             # then service brakes only
        for _ in range(60 * 20):
            driving.update(1 / 60)
            if driving._hazard_deadline is None:
                break
        assert driving._hazard_deadline is None
        assert t.damage_pct == damage_before    # avoided, not collided
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
