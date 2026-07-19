"""Highway exits and cruise control, end to end through the driving state."""

import pygame
import pytest
from driving_feature_helpers import (
    key_event,
    mark_destination_exit_taken,
    open_status_screen,
    quiet_trip,
    start_drive,
    take_destination_exit,
)


def test_trip_event_sounds_use_contextual_cues():
    from freight_fate.sim.trip import TripEvent, TripEventKind, Zone
    from freight_fate.states.driving import _route_event_sound

    assert _route_event_sound(TripEvent(TripEventKind.HAZARD, "Brake now!")) == (
        "events/hazard_warning"
    )
    assert _route_event_sound(TripEvent(TripEventKind.TOLL_CHARGED, "Toll")) == (
        "events/toll_charged"
    )
    assert _route_event_sound(TripEvent(TripEventKind.STATE_CROSSING, "Crossing")) == (
        "events/state_crossing"
    )
    event = TripEvent(
        TripEventKind.ZONE_ENTER,
        "construction ahead",
        {"zone": Zone(1.0, 2.0, 45.0, "construction")},
    )
    assert _route_event_sound(event) == "events/construction_zone"


def test_active_drive_applies_manual_setting_and_announces_it(monkeypatch):
    from freight_fate.app import App

    app = App()
    events = []

    class HeldShift:
        def __getitem__(self, key):
            return key == pygame.K_LSHIFT

    keys = HeldShift()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: keys)
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        assert driving.truck.transmission.automatic
        app.ctx.settings.automatic_transmission = False

        driving.update(1 / 60)

        assert not driving.truck.transmission.automatic
        assert driving.truck.transmission.clutch == 1.0
        assert ("Transmission changed to manual.", True) in events
    finally:
        app.shutdown()


def test_passing_hazard_plays_clear_sound(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_core import HAZARD_SAFE_MPH

    app = App()
    played = []
    events = []
    monkeypatch.setattr(app.ctx.audio, "play", lambda key, volume=1.0: played.append((key, volume)))
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        played.clear()
        driving._hazard_deadline = 3.0
        driving.truck.velocity_mps = (HAZARD_SAFE_MPH - 1.0) / 2.2369362920544

        driving._update_hazard(1 / 60)

        assert driving._hazard_deadline is None
        assert ("events/hazard_clear", 0.75) in played
        assert events == [("Hazard avoided. Well done.", False)]
    finally:
        app.shutdown()


def test_control_stops_event_voice_without_flushing_main_speech():
    from freight_fate.app import App

    class RecordingSpeech:
        def __init__(self):
            self.event_stops = 0
            self.main_stops = 0

        def stop_event(self):
            self.event_stops += 1

        def stop_main(self):
            self.main_stops += 1

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        speech = RecordingSpeech()
        app.ctx.speech = speech

        driving.handle_event(key_event(pygame.K_LCTRL))

        assert speech.event_stops == 1
        assert speech.main_stops == 0
        assert "Event voice stopped" in driving.lines()[-1]
    finally:
        app.shutdown()


def test_shift_key_does_not_press_clutch_in_automatic(monkeypatch):
    from freight_fate.app import App

    class Keys:
        def __getitem__(self, key):
            return key == pygame.K_LSHIFT

    app = App()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: Keys())
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        assert driving.truck.transmission.automatic

        driving.update(1 / 60)

        assert driving.truck.transmission.clutch == 0.0
    finally:
        app.shutdown()


def test_automatic_reverse_selection_is_spoken(monkeypatch):
    from freight_fate.app import App

    app = App()
    events = []
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)

        assert driving._update_reverse_controls(accelerating=False, braking_key=True)

        assert events[-1] == ("Reverse selected. Backing slowly.", False)
    finally:
        app.shutdown()


def test_sustained_redline_speaks_a_damage_warning(monkeypatch):
    import math

    from freight_fate.app import App

    app = App()
    events = []
    played = []
    monkeypatch.setattr(app.ctx.audio, "play", lambda key, volume=1.0: played.append(key))
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        t.engine_on = True
        t.transmission.gear = 1
        ratio = abs(t.transmission.ratio_for(1))
        wheel_rps = (t.specs.max_rpm * 1.1) / (60.0 * ratio)
        t.velocity_mps = wheel_rps * 2 * math.pi * t.specs.wheel_radius_m
        t.rpm = t.specs.max_rpm
        t.damage_pct = 12.0

        driving._update_overrev(1.0)  # inside the grace period: a shift flare
        assert events == []

        driving._update_overrev(1.0)  # sustained past the grace: warn
        assert "redline" in events[-1][0].lower()
        assert "12 percent" in events[-1][0]
        assert events[-1][1] is True
        assert "ui/warning" in played

        events.clear()
        driving._update_overrev(5.0)  # repeat interval not reached yet
        assert events == []
        driving._update_overrev(6.0)  # past it: nag again while damage accrues
        assert len(events) == 1

        events.clear()
        t.rpm = t.specs.idle_rpm  # easing off resets the whole cycle
        driving._update_overrev(1.0)
        t.rpm = t.specs.max_rpm
        driving._update_overrev(1.0)  # back at redline, but within fresh grace
        assert events == []
    finally:
        app.shutdown()


def test_simple_automatic_holds_through_stop_to_change_direction(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.transmission import REVERSE

    app = App()
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        assert app.ctx.settings.automatic_direction_changes == "simple"

        driving.truck.velocity_mps = 0.0
        driving._reverse_brake_held = True
        assert driving._update_reverse_controls(accelerating=False, braking_key=True)
        assert driving.truck.transmission.in_reverse

        driving.truck.velocity_mps = 0.0
        driving._reverse_accel_held = True
        driving._update_reverse_controls(accelerating=True, braking_key=False)
        assert driving.truck.transmission.gear != REVERSE
    finally:
        app.shutdown()


def test_controller_trigger_edges_follow_automatic_direction_style(monkeypatch):
    """The deliberate controller path reads the unsmoothed trigger target so
    a full release is observable even while the smoothed brake value lingers."""
    from freight_fate.app import App

    app = App()
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.velocity_mps = 0.0

        app.ctx.settings.automatic_direction_changes = "simple"
        driving._reverse_brake_held = True
        assert driving._update_reverse_controls(
            accelerating=False,
            braking_key=True,
            accel_held=False,
            brake_held=True,
        )

        driving.truck.transmission.gear = 1
        app.ctx.settings.automatic_direction_changes = "deliberate"
        driving._reverse_brake_held = True
        assert not driving._update_reverse_controls(
            accelerating=False,
            braking_key=True,
            accel_held=False,
            brake_held=True,
        )
        assert not driving.truck.transmission.in_reverse

        # The instantaneous target reaches neutral before the smoothed brake.
        assert not driving._update_reverse_controls(
            accelerating=False,
            braking_key=True,
            accel_held=False,
            brake_held=False,
        )
        assert driving._update_reverse_controls(
            accelerating=False,
            braking_key=True,
            accel_held=False,
            brake_held=True,
        )
        assert driving.truck.transmission.in_reverse
    finally:
        app.shutdown()


def test_automatic_held_brake_does_not_engage_reverse(monkeypatch):
    """Braking to a stop and holding must not slip into reverse; only a fresh
    press (release, then press again) engages it."""
    from freight_fate.app import App

    app = App()
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    try:
        app.ctx.settings.automatic_direction_changes = "deliberate"
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.velocity_mps = 0.0
        # Brake was already held coming into this frame, as after braking to
        # a stop -- no rising edge, so reverse must not engage.
        driving._reverse_brake_held = True
        assert not driving._update_reverse_controls(accelerating=False, braking_key=True)
        assert not driving.truck.transmission.in_reverse
        # Release the brake, then a fresh press engages reverse.
        assert not driving._update_reverse_controls(accelerating=False, braking_key=False)
        assert driving._update_reverse_controls(accelerating=False, braking_key=True)
        assert driving.truck.transmission.in_reverse
    finally:
        app.shutdown()


def test_automatic_held_accelerator_does_not_flip_out_of_reverse(monkeypatch):
    """Holding the accelerator to brake a reverse roll to a stop must not flip
    to forward; a fresh press is required."""
    from freight_fate.app import App
    from freight_fate.sim.transmission import REVERSE

    app = App()
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    try:
        app.ctx.settings.automatic_direction_changes = "deliberate"
        driving = start_drive(app)
        quiet_trip(driving)
        tr = driving.truck.transmission
        tr.gear = REVERSE
        driving.truck.velocity_mps = 0.0
        # Accelerator was held while it braked the reverse roll to a stop.
        driving._reverse_accel_held = True
        assert not driving._update_reverse_controls(accelerating=True, braking_key=False)
        assert tr.in_reverse
        # Release, then a fresh press flips to forward.
        driving._update_reverse_controls(accelerating=False, braking_key=False)
        driving._update_reverse_controls(accelerating=True, braking_key=False)
        assert not tr.in_reverse
    finally:
        app.shutdown()


def test_accelerator_does_not_thrust_while_braking_in_reverse(monkeypatch):
    """Pressing the accelerator to brake a backward roll must never command
    reverse thrust -- throttle stays down while the service brake engages."""
    from freight_fate.app import App
    from freight_fate.sim.transmission import REVERSE

    class Keys:
        def __getitem__(self, key):
            return key == pygame.K_UP

    app = App()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: Keys())
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    try:
        app.ctx.settings.automatic_direction_changes = "deliberate"
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        t.transmission.gear = REVERSE
        t.velocity_mps = -3.0
        t.throttle = 0.5
        # Accelerator already held, so this is not a fresh press: no gear flip.
        driving._reverse_accel_held = True

        driving.update(1 / 60)

        assert t.transmission.in_reverse
        assert t.throttle < 0.5  # decays toward 0 rather than ramping up
        assert t.brake > 0.0  # the service brake is what arrests the roll
    finally:
        app.shutdown()


def test_driving_help_explains_selected_automatic_direction_style(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)

        app.ctx.settings.automatic_direction_changes = "simple"
        driving._speak_keyboard_help()
        assert "simple direction changes" in spoken[-1]
        assert "keep holding the Down arrow" in spoken[-1]

        app.ctx.settings.automatic_direction_changes = "deliberate"
        driving._speak_keyboard_help()
        assert "deliberate direction changes" in spoken[-1]
        assert "release the Down arrow and press it again" in spoken[-1]

        app.ctx.settings.automatic_direction_changes = "simple"
        driving._speak_controller_help()
        assert "simple direction changes" in spoken[-1]
        assert "keep holding the left trigger" in spoken[-1]

        app.ctx.settings.automatic_direction_changes = "deliberate"
        driving._speak_controller_help()
        assert "deliberate direction changes" in spoken[-1]
        assert "let the left trigger return to neutral" in spoken[-1]
    finally:
        app.shutdown()


def test_driving_f1_describes_safe_shutdown_and_destination_parking(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(
        app.ctx,
        "say",
        lambda text, interrupt=True: spoken.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)

        driving.handle_event(key_event(pygame.K_F1))

        help_text = spoken[-1][0]
        assert "stops it only below 5 miles per hour" in help_text
        assert "stop, then dock and deliver" in help_text
        assert "Left or Right Control stops the driving event voice" in help_text
    finally:
        app.shutdown()


def test_closing_status_panel_does_not_restart_drive_music(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingStatusState

    app = App()
    played = []
    monkeypatch.setattr(
        app.ctx.audio,
        "play_music",
        lambda track, fade_ms=1500: played.append((track, fade_ms)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        played.clear()

        driving.handle_event(key_event(pygame.K_TAB))
        assert isinstance(app.state, DrivingStatusState)
        app.state.handle_event(key_event(pygame.K_ESCAPE))

        assert app.state is driving
        assert played == []
    finally:
        app.shutdown()


def test_drive_music_advances_to_next_track_while_paused(monkeypatch):
    from freight_fate.app import App
    from freight_fate.music import music_track_duration_s
    from freight_fate.states.driving import PauseMenuState

    app = App()
    played = []
    monkeypatch.setattr(
        app.ctx.audio,
        "play_music",
        lambda track, fade_ms=1500: played.append(track),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)

        driving.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, PauseMenuState)
        first = driving._current_music_track()
        played.clear()

        # Sit on the pause menu until the current bed's one-shot playback ends.
        app.state.update(music_track_duration_s(first) + 1.0)

        following = driving._current_music_track()
        assert following != first
        assert played == [following]
    finally:
        app.shutdown()


def test_how_to_play_documents_new_gameplay_systems():
    from freight_fate.states.main_menu import HELP_PAGES

    help_text = " ".join(line for _title, lines in HELP_PAGES for line in lines).lower()

    assert "air brakes need pressure" in help_text
    assert "wait for air pressure to reach 100 psi" in help_text
    assert "press p to release or set the parking brake" in help_text
    assert "low air" in help_text
    assert "tab opens a driving status menu" in help_text
    assert "slow below 5 miles per hour" in help_text
    assert "destination facility" in help_text
    assert "local deadhead moves to the origin facility" in help_text
    assert "company terminal or yard" in help_text
    assert "pickup gate" in help_text
    assert "loading requires the truck to be stopped" in help_text
    assert "loaded and sealed" in help_text
    assert "dispatch gives you the destination route" in help_text
    assert "route choice happens after pickup" in help_text
    assert "real highway corridors" in help_text
    assert "gps announces state lines" in help_text
    assert "grades and terrain come from the route" in help_text
    assert "weather, traffic, and construction still vary" in help_text
    assert "slow lead vehicles" in help_text
    assert "settings are grouped into categories" in help_text
    assert "open a category to see its settings" in help_text
    assert "trip pacing changes how quickly distance and game time pass" in help_text
    assert "relaxed pacing gives you more real time to react, and is the default" in help_text
    assert "relaxed keeps the clock but gives a more forgiving schedule" in help_text
    assert "longer limits and fewer penalties" in help_text
    assert "adaptive cruise" in help_text
    assert "three second clear-weather gap" in help_text
    assert "increase the following gap" in help_text
    assert "keypad keys" in help_text
    assert "active speed-control mode" in help_text
    assert "open-road target" in help_text
    assert "sharp posted-limit drops" in help_text
    assert "highway stops use clear place names" in help_text
    assert "list the actions available there" in help_text
    assert "call for help" in help_text
    assert "tolls and approved company charges" in help_text
    assert "costs you caused, like speeding fines" in help_text
    assert "gross pay, carrier-paid or reimbursed charges" in help_text
    assert "net driver pay" in help_text
    assert "touch the brakes to cancel" in help_text
    assert "save" in help_text
    assert "dock and deliver" in help_text
    assert "wider freight area with many possible shippers" in help_text
    assert "rail and intermodal ramps" in help_text
    assert "parcel hubs" in help_text
    assert "farms and grain elevators" in help_text
    assert "chemical terminals" in help_text
    assert "not every market supports every cargo equally" in help_text
    assert "major freight areas instead of every town" in help_text
    assert "routes with enough stops" in help_text
    assert "refrigerated, heavy-haul, and high-value freight" in help_text
    assert "full tank or full repair" in help_text
    assert "engine tune gives more pulling power" in help_text
    assert "aerodynamic kit burns less fuel" in help_text
    assert "same tank, fewer gallons per mile" in help_text
    assert "long-range tank carries fifty more gallons" in help_text
    assert "more fuel onboard, not better efficiency" in help_text
    assert "emergency stops" in help_text
    assert "emergency shoulder sleep" in help_text
    assert "parking ticket or minor damage" in help_text
    # Always-available sleep, and the 1.8.0 systems, are documented in-game.
    assert "sleep 10 hours in the lot" in help_text
    assert "fully-rested ten-hour sleep" in help_text
    assert "risks losing traction" in help_text
    assert "low visibility shortens" in help_text
    assert "career runs on a calendar that starts in spring" in help_text
    assert "state troopers patrol" in help_text
    assert "speed keeper handles low-speed local roads" in help_text


def test_dispatch_board_keeps_route_planning_out_of_load_offer():
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState, route_planning_summary

    app = App()
    try:
        app.ctx.profile = Profile(name="Dispatch Test", current_city="New York")
        jobs = JobBoard(app.ctx.world, seed=2).offers(
            "New York", {"refrigerated", "heavy_haul", "high_value"}, level=5
        )
        assert jobs
        state = JobBoardState(app.ctx, jobs)
        items = state.build_items()
        rows = [item.text if isinstance(item.text, str) else item.text() for item in items]

        assert any("Equipment:" in row for row in rows)
        assert all("Legal HOS plan" not in row for row in rows)
        assert all("Route has" not in row for row in rows)
        assert all("Fuel-capable stops" not in row for row in rows)
        assert "Route inspection after pickup covers rest, fuel, toll" in items[0].help

        toll_route = app.ctx.world.route_from_cities(["New York", "Philadelphia"])
        summary = route_planning_summary(toll_route)
        assert "Legal HOS plan" in summary
        assert "Fuel-capable stops:" in summary
        assert "Estimated carrier-paid toll exposure" in summary
        assert "not a guaranteed open space" in summary
    finally:
        app.shutdown()


def test_terse_air_brake_startup_omits_control_instructions(monkeypatch):
    from freight_fate.app import App

    class FakeKeys:
        def __getitem__(self, key):
            return key == pygame.K_UP

    app = App()
    events = []
    spoken = []
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys())
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    monkeypatch.setattr(
        app.ctx,
        "say",
        lambda text, interrupt=True: spoken.append((text, interrupt)),
    )
    try:
        app.ctx.settings.speech_verbosity = 0
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.set_cold_air_start()
        events.clear()
        spoken.clear()

        driving.handle_event(key_event(pygame.K_e))
        for _ in range(60):
            driving.update(1 / 60)

        assert spoken[-1][0].endswith("Air pressure 55 psi.")
        event_texts = [text for text, _interrupt in events]
        assert "Air pressure 55 psi." in event_texts
        assert all("Wait for" not in text for text in event_texts)
        assert all("press P" not in text for text in event_texts)

        driving.handle_event(key_event(pygame.K_p))
        assert spoken[-1][0] == "Parking brake set. Air pressure 58 psi."
        assert "wait for" not in spoken[-1][0].lower()

        for _ in range(60 * 15):
            driving.update(1 / 60)
            if driving.truck.air_ready:
                break

        assert events[-1][0].startswith("Air ready:")
        assert "Press P" not in events[-1][0]
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_air_brake_startup_blocks_movement_until_ready_and_released(monkeypatch):
    from freight_fate.app import App

    class FakeKeys:
        def __init__(self, held):
            self.held = held

        def __getitem__(self, key):
            return key in self.held

    app = App()
    events = []
    spoken = []
    played = []
    held = {pygame.K_UP}
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    monkeypatch.setattr(
        app.ctx,
        "say",
        lambda text, interrupt=True: spoken.append((text, interrupt)),
    )
    monkeypatch.setattr(app.ctx.audio, "play", lambda key, volume=1.0: played.append((key, volume)))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.set_cold_air_start()

        driving.handle_event(key_event(pygame.K_e))
        for _ in range(60):
            driving.update(1 / 60)

        assert driving.truck.speed_mph == 0.0
        assert driving.truck.parking_brake
        assert any("Wait for 100 psi" in text for text, _interrupt in events)

        driving.handle_event(key_event(pygame.K_p))
        assert driving.truck.parking_brake
        assert "Parking brake stays set" in spoken[-1][0]

        for _ in range(60 * 15):
            driving.update(1 / 60)
            if driving.truck.air_ready:
                break

        assert driving.truck.air_ready
        assert any("Air pressure ready" in text for text, _interrupt in events)
        # The compressor-ready cue is now a real air-dryer purge, not a UI beep.
        assert any(key == "vehicle/air_dryer_purge" for key, _volume in played)

        driving.handle_event(key_event(pygame.K_p))
        assert not driving.truck.parking_brake
        assert ("vehicle/brake_release", 0.65) in played

        for _ in range(60 * 5):
            driving.update(1 / 60)
            if driving.truck.speed_mph > 1.0:
                break

        assert driving.truck.speed_mph > 1.0

        driving.handle_event(key_event(pygame.K_p))
        assert driving.truck.parking_brake
        assert ("vehicle/brake_set", 0.65) in played
    finally:
        app.shutdown()


def test_terse_hazard_drops_brake_now_instruction(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    events = []
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    try:
        app.ctx.settings.speech_verbosity = 0
        driving = start_drive(app)
        quiet_trip(driving)

        driving._handle_trip_event(
            TripEvent(
                TripEventKind.HAZARD,
                "Brake now! Debris on the shoulder.",
                {"deadline_s": 4.0},
            )
        )

        assert events[-1] == ("Debris on the shoulder.", True)
    finally:
        app.shutdown()


def test_low_air_warning_flushes_event_voice(monkeypatch):
    from freight_fate.app import App

    app = App()
    events = []
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.set_cold_air_start()
        driving.truck.engine_on = True
        driving.truck.air_pressure_psi = 50.0
        driving.truck.primary_air_psi = 50.0
        driving.truck.secondary_air_psi = 50.0
        driving.truck.trailer_air_psi = 50.0
        driving._update_air_brake_announcements(
            was_ready=False,
            was_low=False,
            was_spring=False,
        )

        assert events[-1][0].startswith("Low air warning")
        assert events[-1][1] is True
    finally:
        app.shutdown()


def test_terse_lane_departure_omits_recovery_instruction(monkeypatch):
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    app = App()
    events = []
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    monkeypatch.setattr(app.ctx.audio, "play", lambda *args, **kwargs: None)
    try:
        app.ctx.settings.speech_verbosity = 0
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.velocity_mps = 20.0
        monkeypatch.setattr(driving.lane, "update", lambda *args, **kwargs: True)
        monkeypatch.setattr(driving.lane, "describe", lambda: "Right rumble strip.")

        driving._update_lane(NoKeys(), 1 / 60)

        assert events[-1] == ("Right rumble strip.", True)
    finally:
        app.shutdown()


def test_lane_departure_warning_flushes_event_voice(monkeypatch):
    from freight_fate.app import App

    class NoKeys:
        def __getitem__(self, _key):
            return False

    app = App()
    events = []
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    monkeypatch.setattr(app.ctx.audio, "play", lambda *args, **kwargs: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.velocity_mps = 20.0
        monkeypatch.setattr(driving.lane, "update", lambda *args, **kwargs: True)
        monkeypatch.setattr(driving.lane, "describe", lambda: "Right rumble strip.")

        driving._update_lane(NoKeys(), 1 / 60)

        assert events[-1] == (
            "Right rumble strip. Steer back toward the lane center.",
            True,
        )
    finally:
        app.shutdown()


def test_speeding_strike_flushes_event_voice(monkeypatch):
    from freight_fate.app import App

    app = App()
    events = []
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.velocity_mps = 40.0
        monkeypatch.setattr(
            driving.trip,
            "speed_limit_at",
            lambda _position: (25.0, None),
        )
        monkeypatch.setattr(driving, "_trooper_catches_speeder", lambda _limit: False)

        driving._update_speeding(11.0)

        assert events[-1][0].startswith("Speeding strike.")
        assert events[-1][1] is True
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_air_brake_help_and_status_are_spoken(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState, DrivingStatusState

    app = App()
    spoken = []
    monkeypatch.setattr(
        app.ctx,
        "say",
        lambda text, interrupt=True: spoken.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.set_cold_air_start()

        driving.handle_event(key_event(pygame.K_F1))
        assert "Air pressure must build" in spoken[-1][0]
        assert "Press P to release or set the parking brake" in spoken[-1][0]

        driving.handle_event(key_event(pygame.K_TAB))
        assert isinstance(app.state, DrivingStatusState)
        open_status_screen(app, "Route")
        status_lines = [item.text for item in app.state.items]
        air_status = next(line for line in status_lines if line.startswith("Air brakes:"))
        assert "primary 55 psi" in air_status
        assert "secondary 55 psi" in air_status
        assert "trailer 55 psi" in air_status
        assert "parking brake set" in air_status
        assert "compressor idle" in air_status
        assert "brakes cool" in air_status
        assert any(line.startswith("Weather:") for line in status_lines)

        app.state.handle_event(key_event(pygame.K_ESCAPE))  # back to the screen picker
        open_status_screen(app, "Driver")
        driver_lines = [item.text for item in app.state.items]
        assert any(line.startswith("Driver:") for line in driver_lines)
        assert any(line.startswith("Hours:") for line in driver_lines)

        app.state.handle_event(key_event(pygame.K_ESCAPE))
        open_status_screen(app, "Map")
        map_lines = [item.text for item in app.state.items]
        assert any(line.startswith("Route:") for line in map_lines)
        assert any("offers" in line for line in map_lines)

        app.state.handle_event(key_event(pygame.K_ESCAPE))  # screen -> picker
        app.state.handle_event(key_event(pygame.K_ESCAPE))  # picker -> driving
        assert isinstance(app.state, DrivingState)
        assert spoken[-1] == ("Back to driving.", False)

        driving.handle_event(key_event(pygame.K_SPACE))
        assert "air 55 psi" in spoken[-1][0]
        assert any(line.startswith("Air: 55 psi") for line in driving.lines())
    finally:
        app.shutdown()


# -- highway exits -------------------------------------------------------------


@pytest.mark.smoke
def test_engine_shutdown_is_blocked_at_highway_speed(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.handle_event(key_event(pygame.K_e))
        assert driving.truck.engine_on
        app.ctx.audio.update(5.0)  # let the ignition finish before toggling again
        driving.truck.velocity_mps = 31.3

        driving.handle_event(key_event(pygame.K_e))

        assert driving.truck.engine_on
        assert "Unsafe to shut the engine off" in spoken[-1]
        assert "70 miles per hour" in spoken[-1]
        assert "shutdown blocked" in driving.lines()[-1]
    finally:
        app.shutdown()


def test_metric_status_lines_do_not_mix_mph_and_miles(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import NavigationCue

    app = App()
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
    try:
        app.ctx.settings.imperial_units = False
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.velocity_mps = 26.8
        driving._cruise_mph = 60.0
        # Force a known traffic cue ahead so the route line always renders the
        # traffic speed. The speed used to be baked into the cue text as mph at
        # build time, so it leaked imperial units in metric mode -- but only when
        # a traffic lead randomly landed in range, which made this test flaky.
        driving.trip.navigation_cues = [
            NavigationCue(
                "traffic:test",
                "traffic",
                driving.trip.position_mi + 5.0,
                "traffic queue ahead",
                speed_mph=50.0,
            ),
        ]

        lines = driving.status_lines()

        assert any("kilometers per hour" in line for line in lines)
        # 50 mph rendered in metric, not "miles per hour".
        assert any("traffic queue ahead at 80 kilometers per hour" in line for line in lines)
        assert not any(" mph" in line for line in lines)
        assert not any(" miles" in line for line in lines)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_engine_shutdown_is_allowed_once_stopped():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.handle_event(key_event(pygame.K_e))
        assert driving.truck.engine_on
        app.ctx.audio.update(5.0)  # let the ignition finish before toggling again
        driving.truck.velocity_mps = 0.0
        driving.handle_event(key_event(pygame.K_e))
        assert not driving.truck.engine_on
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_delivery_requires_parking_at_destination(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import ArrivalState, DrivingState, FacilityArrivalState

    app = App()
    events = []
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        mark_destination_exit_taken(driving)
        driving.truck.velocity_mps = 26.8

        driving.update(1 / 60)

        assert isinstance(app.state, DrivingState)
        assert "Destination ahead" in events[-1]
        assert "come to a complete stop" in events[-1].lower()
        assert "complete stop" in driving.lines()[-1].lower()

        driving.truck.velocity_mps = 0.0
        driving.update(1 / 60)

        assert isinstance(app.state, FacilityArrivalState)
        assert app.state.items[app.state.index].text == "Dock and deliver"
        assert "Docking required before delivery settlement." in app.state.lines()
        assert app.ctx.profile.career.deliveries == 0

        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, ArrivalState)
        assert any("Trailer secured and paperwork signed" in text for text in spoken)
    finally:
        app.shutdown()


def test_cargo_mass_is_loaded_on_delivery_and_empty_on_pickup():
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.sim.vehicle import KG_PER_TON
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Load Mass", current_city="Buffalo")
        route = app.ctx.world.supported_route("Buffalo", "Rochester")
        job = Job(
            CARGO_CATALOG["general"],
            18.0,
            "Buffalo",
            "company yard",
            "Rochester",
            route.miles,
            1000.0,
            12.0,
            destination_location="Rochester freight market",
        )
        loaded = DrivingState(app.ctx, job, route, phase="delivery")
        assert loaded.truck.cargo_kg == pytest.approx(18 * KG_PER_TON)
        assert loaded.truck.gross_mass_kg > loaded.truck.tare_kg

        # The pickup deadhead runs empty: no payload aboard yet.
        empty = DrivingState(app.ctx, job, route, phase="pickup")
        assert empty.truck.cargo_kg == 0.0
        assert empty.truck.gross_mass_kg == pytest.approx(empty.truck.tare_kg)
    finally:
        app.shutdown()


def test_delivery_exit_uses_real_destination_interchange():
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Rochester Exit", current_city="Buffalo")
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
        destination = driving._destination_exit_stop()

        assert destination is not None
        assert destination.exit_label
        assert destination.at_mi == pytest.approx(72.8, abs=0.2)
    finally:
        app.shutdown()


def test_delivery_exit_prefers_nearest_interchange_over_early_city_sign():
    import dataclasses

    from freight_fate.app import App
    from freight_fate.data.world_models import Interchange
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Nearest Exit", current_city="Buffalo")
        route = app.ctx.world.supported_route("Buffalo", "Rochester")
        leg = route.legs[-1]
        early = Interchange(
            at_mi=10.0,
            exit_ref="10",
            destinations=("Rochester",),
            name="",
            highway=leg.highway,
            source="test",
        )
        near = Interchange(
            at_mi=leg.miles - 1.0,
            exit_ref="near",
            destinations=("Freight district",),
            name="",
            highway=leg.highway,
            source="test",
        )
        route.legs[-1] = dataclasses.replace(leg, interchanges=(early, near))
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

        details = driving._destination_exit_details()

        assert details is not None
        assert details[1] == "exit near"
    finally:
        app.shutdown()


def test_destination_exit_scan_is_cached_until_the_exit_passes():
    # The scan walks every interchange on the route building spoken phrases,
    # and _check_destination_exit runs every frame -- the cache must absorb
    # that (issue 70's crash landed in this per-frame churn) while still
    # rescanning when the winning exit is passed or the truck moves backward.
    import dataclasses

    from freight_fate.app import App
    from freight_fate.data.world_models import Interchange
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Cached Exit", current_city="Buffalo")
        route = app.ctx.world.supported_route("Buffalo", "Rochester")
        leg = route.legs[-1]
        early = Interchange(
            at_mi=10.0,
            exit_ref="10",
            destinations=("Rochester",),
            name="",
            highway=leg.highway,
            source="test",
        )
        near = Interchange(
            at_mi=leg.miles - 1.0,
            exit_ref="near",
            destinations=("Freight district",),
            name="",
            highway=leg.highway,
            source="test",
        )
        route.legs[-1] = dataclasses.replace(leg, interchanges=(early, near))
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

        calls = 0
        scan = driving._scan_destination_exit_details

        def counting_scan(**kwargs):
            nonlocal calls
            calls += 1
            return scan(**kwargs)

        driving._scan_destination_exit_details = counting_scan

        first = driving._destination_exit_details()
        assert first is not None
        assert first[1] == "exit near"
        assert driving._destination_exit_details() == first
        assert calls == 1

        # Passing the winning exit forces one rescan; nothing is left ahead,
        # and that empty answer is itself cached.
        driving.trip.position_mi = first[0] + 0.1
        assert driving._destination_exit_details() is None
        assert driving._destination_exit_details() is None
        assert calls == 2

        # A backward move (the missed-exit rewind) brings the exit back.
        driving.trip.position_mi = first[0] - 1.0
        assert driving._destination_exit_details() == first
        assert calls == 3

        # include_past bypasses the cache entirely for the one-shot callers.
        assert driving._destination_exit_details(include_past=True) == first
        assert calls == 4
    finally:
        app.shutdown()


def test_terse_destination_exit_omits_press_x_instruction(monkeypatch):
    from freight_fate.app import App

    app = App()
    events = []
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    try:
        app.ctx.settings.speech_verbosity = 0
        driving = start_drive(app)
        quiet_trip(driving)
        destination = driving._destination_exit_stop()
        driving.trip.position_mi = destination.at_mi - 4.0

        driving._check_destination_exit()

        message, interrupt = events[-1]
        assert interrupt is True
        assert "destination exit" in message
        assert "Press X" not in message
        assert "take it" not in message
    finally:
        app.shutdown()


def test_destination_exit_announces_and_disables_cruise(monkeypatch):
    from freight_fate.app import App

    app = App()
    events = []
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=True: events.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        # Pin the exit signage: the random job assignment picks the route,
        # and not every destination exit carries a "toward" phrase in its
        # sign data, so scanning the real interchanges here is a coin flip.
        monkeypatch.setattr(
            driving,
            "_destination_exit_details",
            lambda *, include_past=False: (
                24.0,
                "exit 20",
                "exit 20 for US-64 East toward Memphis",
            ),
        )
        destination = driving._destination_exit_stop()
        driving.trip.position_mi = destination.at_mi - 4.0
        driving._cruise_mph = 60.0

        driving._check_destination_exit()

        assert driving._cruise_mph is None
        message, interrupt = events[-1]
        assert interrupt is True
        assert "exit " in message
        assert "toward" in message
        assert "destination exit" in message
        assert "Press X to take it" in message
        assert "Adaptive cruise disabled" in message
    finally:
        app.shutdown()


def test_destination_exit_suppresses_matching_interchange_gps_cue(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.sim.trip_models import NavigationCue

    app = App()
    events = []
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        destination = driving._destination_exit_stop()
        driving.trip.position_mi = destination.at_mi - 1.0

        driving._check_destination_exit()
        driving._handle_trip_event(
            TripEvent(
                TripEventKind.GPS_CUE,
                "Exit ahead from generic navigation cue.",
                {
                    "cue": NavigationCue(
                        "interchange:test",
                        "interchange",
                        destination.at_mi,
                        "generic exit cue",
                    )
                },
            )
        )

        assert len(events) == 1
        assert "destination exit" in events[0]
        assert "generic navigation cue" not in events[0]
    finally:
        app.shutdown()


def test_delivery_does_not_complete_without_taking_destination_exit(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    events = []
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.position_mi = driving.trip.total_miles
        driving.trip.finished = True
        driving.truck.velocity_mps = 0.0

        driving.update(1 / 60)

        assert isinstance(app.state, DrivingState)
        assert not driving.trip.finished
        assert driving.trip.position_mi < driving.trip.total_miles
        assert driving._destination_exit_stop() is not None
        assert "missed the destination exit" in events[-1].lower()
        assert "safe turnaround" in events[-1].lower()
        assert "back up" not in events[-1].lower()
    finally:
        app.shutdown()


def test_missed_destination_recovery_does_not_keep_issuing_gate_speed_strikes(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import SPEEDING_HOLD_S, DrivingState

    app = App()
    events = []
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.position_mi = driving.trip.total_miles
        driving.trip.finished = True
        driving.truck.velocity_mps = 85.0 / 2.23694

        driving.update(1 / 60)
        assert isinstance(app.state, DrivingState)
        assert "missed the destination exit" in events[-1].lower()
        assert "back up" not in events[-1].lower()

        driving.update(SPEEDING_HOLD_S + 1.0)

        assert driving.speeding_strikes == 0
        assert not any("End of facility gate zone" in event for event in events)
    finally:
        app.shutdown()


def test_destination_exit_opens_delivery_gate():
    from freight_fate.app import App
    from freight_fate.states.driving import FacilityArrivalState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        take_destination_exit(driving)

        assert isinstance(app.state, FacilityArrivalState)
        assert app.state.items[app.state.index].text == "Dock and deliver"
    finally:
        app.shutdown()


def test_destination_exit_completion_clears_remaining_route_miles():
    from freight_fate.app import App
    from freight_fate.states.driving import FacilityArrivalState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        take_destination_exit(driving)

        assert isinstance(app.state, FacilityArrivalState)
        assert driving.trip.finished
        assert driving.trip.position_mi == pytest.approx(driving.trip.total_miles)
        assert driving.trip.remaining_miles == pytest.approx(0.0)
        assert any("0 miles remaining" in line for line in driving.status_lines())
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_facility_menu_waits_for_full_stop(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState, FacilityArrivalState

    app = App()
    events = []
    played = []
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(app.ctx.audio, "play", lambda key, volume=1.0: played.append((key, volume)))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken.clear()
        played.clear()
        mark_destination_exit_taken(driving)
        driving.truck.velocity_mps = 1.1  # about 2.5 mph: parked, not docked

        driving.update(1 / 60)
        assert isinstance(app.state, DrivingState)
        assert app.ctx.profile.career.deliveries == 0
        assert "Stop to dock" in events[-1]
        assert "stop to dock" in driving.lines()[-1]
        assert played[-1][0] == "ui/notify"

        driving.truck.velocity_mps = 0.0
        driving.update(1 / 60)

        assert isinstance(app.state, FacilityArrivalState)
        assert played[-1][0] == "facility/dock_gate"
        assert all(key != "ui/menu_open" for key, _volume in played)
        assert [item.text for item in app.state.items] == [
            "Dock and deliver",
            "Check paperwork",
            "Check arrival status",
        ]

        app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, FacilityArrivalState)
        assert app.ctx.profile.career.deliveries == 0
        assert "Paperwork for" in spoken[-1]
        assert "current gross payout" in spoken[-1]
        assert "Carrier-paid or reimbursed charges recorded so far" in spoken[-1]
        assert "Those charges do not reduce driver pay" in spoken[-1]
        assert "estimated net driver pay" in spoken[-1]
        assert "hours remain before the deadline" in spoken[-1]
        assert "Cargo condition" in spoken[-1]
        assert "Dock and deliver to settle" in spoken[-1]

        app.state.handle_event(key_event(pygame.K_UP))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert not isinstance(app.state, FacilityArrivalState)
        assert app.ctx.profile.career.deliveries == 1
        played_keys = [key for key, _volume in played]
        assert "poi/dock_and_deliver" in played_keys
        assert "ui/job_complete" in played_keys
        assert "ui/cash" in played_keys
        assert "ui/menu_open" not in played_keys
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_flow_reaches_the_rest_stop_menu():
    from freight_fate.app import App
    from freight_fate.states.driving import ParkingFullState, RestStopState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 2.0
        driving.truck.velocity_mps = 15.0  # ~34 mph: slow enough for the ramp
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop

        driving.trip.position_mi = stop.at_mi  # reach the exit point
        driving.update(1 / 60)
        assert driving._ramp_mi is not None  # on the ramp
        assert driving._exit_stop is None

        driving._ramp_mi = 0.0  # end of the ramp...
        driving.truck.velocity_mps = 0.0  # ...braked to a stop
        driving.update(1 / 60)
        assert isinstance(app.state, (RestStopState, ParkingFullState))
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_rest_stop_menu_can_save_active_drive():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ParkingFullState, RestStopState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi
        driving.truck.velocity_mps = 0.0
        driving.handle_event(key_event(pygame.K_t))
        assert isinstance(app.state, (RestStopState, ParkingFullState))
        if isinstance(app.state, ParkingFullState):
            return

        while app.state.items[app.state.index].text != "Save at this stop":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        saved = app.ctx.profile.active_trip
        assert saved is not None
        assert saved["kind"] == "delivery"
        assert saved["route_kind"] == "corridor_itinerary"
        assert saved["position_mi"] == stop.at_mi
        loaded = Profile.load(app.ctx.profile.path)
        assert loaded.active_trip == saved
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_engine_brake_cannot_be_enabled_while_accelerating(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.engine_brake = False
        driving.truck.throttle = 0.4

        driving.handle_event(key_event(pygame.K_j))

        assert not driving.truck.engine_brake
        assert any("Release the accelerator" in text for text in spoken)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_accelerating_turns_engine_brake_off(monkeypatch):
    from freight_fate.app import App

    class FakeKeys:
        def __getitem__(self, key):
            return key == pygame.K_UP

    app = App()
    events = []
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys())
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.engine_brake = True
        driving.truck.set_air_ready(parking_brake=False)

        driving.update(1 / 60)

        assert not driving.truck.engine_brake
        assert driving.truck.throttle > 0.0
        assert "Engine brake off." in events
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_opening_a_route_stop_secures_the_truck():
    """A truck that rolled in just under the docking threshold must be parked
    when the stop menu opens, so it cannot creep while the driver rests."""
    from freight_fate.app import App
    from freight_fate.states.driving import ParkingFullState, RestStopState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi
        driving.truck.velocity_mps = 0.0
        driving.truck.parking_brake = False  # rolled in still un-parked
        driving.truck.throttle = 0.4  # idling in gear, creeping
        driving.handle_event(key_event(pygame.K_t))
        assert isinstance(app.state, (RestStopState, ParkingFullState))
        assert driving.truck.parking_brake  # menu open => truck secured
        assert driving.truck.throttle == 0.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_poi_menu_uses_curated_roadside_assistance_label():
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = RoadStop(
            "Example Turnpike Service Plaza",
            driving.trip.position_mi,
            "service_plaza",
            ("park", "save", "roadside_assistance"),
            ("parking", "roadside_assistance"),
        )
        state = RestStopState(app.ctx, driving, stop)
        texts = [
            item.text if isinstance(item.text, str) else item.text() for item in state.build_items()
        ]
        assert "Call roadside assistance" in texts
        assert all("osm" not in text.lower() for text in texts)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_status_map_screen_describes_source_backed_poi_services():
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState, DrivingStatusScreenState

    app = App()
    try:
        app.ctx.profile = Profile(name="Map Test", current_city="New York")
        job = Job(
            CARGO_CATALOG["electronics"],
            18,
            "New York",
            "JFK Air Cargo",
            "Philadelphia",
            78,
            2500,
            12,
            origin_type="air_cargo",
            destination_location="Philadelphia Distribution Center",
            destination_type="retail_distribution",
        )
        route = app.ctx.world.route_from_cities(["New York", "Philadelphia"])
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        quiet_trip(driving)
        state = DrivingStatusScreenState(app.ctx, driving, "map")
        state.items = state.build_items()

        text = " ".join(item.text for item in state.items)
        assert "offers" in text
        assert "fuel" in text
        assert "food" in text
        assert "sleep or long rest" in text or "30-minute rest break" in text
        assert "listed services" in text
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_toll_route_delivery_settlement_records_expense(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ArrivalState, DrivingState
    from freight_fate.states.driving_menu_states import _settlement_hours

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        app.ctx.profile = Profile(name="Toll Test", current_city="New York")
        job = Job(
            CARGO_CATALOG["electronics"],
            18,
            "New York",
            "JFK Air Cargo",
            "Philadelphia",
            78,
            2500,
            12,
            origin_type="air_cargo",
            destination_location="Philadelphia Distribution Center",
            destination_type="retail_distribution",
        )
        route = app.ctx.world.route_from_cities(["New York", "Philadelphia"])
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        # Both I-95 tolls now sit at mi 8.9 (NJ Turnpike) and 86.1 (Delaware
        # River) after the node moved to Hunts Point; drive past both.
        driving.trip.position_mi = 90.0
        driving.trip.update(0.0)
        assert driving.trip.toll_expense == 30.0

        app.ctx.profile.money = 1000.0
        gross = job.payout(_settlement_hours(driving), 0.0)
        app.ctx.push_state(ArrivalState(app.ctx, driving))

        assert app.ctx.profile.money == pytest.approx(1000.0 + gross)
        assert app.ctx.profile.career.total_earnings == pytest.approx(gross)
        text = " ".join(app.state.summary_parts)
        assert f"Gross pay {gross:,.0f} dollars" in text
        assert "Carrier-paid or reimbursed charges 215 dollars" in text
        assert "tolls 30" in text
        assert "accessorials carrier-authorized unloading service 185 dollars" in text
        assert "not deducted from driver pay" in text
        assert "Driver-responsibility charges 0 dollars" in text
        assert f"Net driver pay {gross:,.0f} dollars" in text

        assert not hasattr(app.state, "screen_index")
        assert app.state.lines()[0] == "Delivery complete"
        summary_lines = [item.text for item in app.state.items]
        assert any(line.startswith("Delivered 18 tons of electronics") for line in summary_lines)
        assert any(line.startswith(f"Gross pay: {gross:,.0f} dollars") for line in summary_lines)
        assert any("Carrier-paid or reimbursed charges" in line for line in summary_lines)
        assert any(line.startswith("Route: New York to Philadelphia") for line in summary_lines)

        old_index = app.state.index
        app.state.handle_event(key_event(pygame.K_RIGHT))
        assert app.state.index == old_index
        assert [item.text for item in app.state.items] == summary_lines
    finally:
        app.shutdown()


def test_engine_audio_load_eases_without_dropping_out_during_automatic_shift(monkeypatch):
    from freight_fate.app import App

    app = App()
    samples = []
    monkeypatch.setattr(
        app.ctx.audio, "set_engine_rpm", lambda rpm, throttle=0.0: samples.append((rpm, throttle))
    )
    monkeypatch.setattr(app.ctx.audio, "set_road_noise", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_weather", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_wind", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_ambient", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.throttle = 1.0
        driving.truck.rpm = 1700.0
        driving.truck.transmission.automatic = True
        driving.truck.transmission.gear = 4
        driving.truck.transmission._shift_timer = 0.5

        driving._update_audio(0.0)

        assert samples[-1] == (1700.0, 0.45)
        from freight_fate.audio import engine_load_gain

        assert engine_load_gain(samples[-1][1]) >= 0.75
    finally:
        app.shutdown()


def test_engine_audio_load_tracks_manual_throttle_smoothly(monkeypatch):
    from freight_fate.app import App

    app = App()
    samples = []
    monkeypatch.setattr(
        app.ctx.audio, "set_engine_rpm", lambda rpm, throttle=0.0: samples.append((rpm, throttle))
    )
    monkeypatch.setattr(app.ctx.audio, "set_road_noise", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_weather", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_wind", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_ambient", lambda *a, **k: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.transmission._shift_timer = 0.0
        driving._engine_audio_throttle = 0.5
        driving.truck.throttle = 0.75
        driving._update_audio(0.1)
        rising = samples[-1][1]
        driving.truck.throttle = 0.25
        driving._update_audio(0.1)
        falling = samples[-1][1]

        # Raw throttle still controls audible load, but the 450-millisecond
        # filter prevents an immediate gain step for a cruise correction.
        assert rising == pytest.approx(0.5 + (0.75 - 0.5) * (0.1 / 0.45))
        assert falling == pytest.approx(rising + (0.25 - rising) * (0.1 / 0.45))
        assert 0.25 < falling < rising < 0.75
    finally:
        app.shutdown()


def test_reverse_audio_cue_loops_while_reverse_is_engaged(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.transmission import REVERSE

    app = App()
    starts = []
    stops = []
    monkeypatch.setattr(app.ctx.audio, "set_engine_rpm", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_road_noise", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_weather", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_wind", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_ambient", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "reverse_start", lambda: starts.append("start"))
    monkeypatch.setattr(app.ctx.audio, "reverse_stop", lambda: stops.append("stop"))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        starts.clear()
        stops.clear()
        driving.truck.start_engine()
        driving.truck.transmission.gear = REVERSE

        driving._update_audio(0.0)
        driving._update_audio(0.0)
        assert starts == ["start"]
        assert stops == []

        driving.truck.transmission.gear = 1
        driving._update_audio(0.0)
        assert stops == ["stop"]

        driving.truck.transmission.gear = REVERSE
        driving._update_audio(0.0)
        assert starts == ["start", "start"]
    finally:
        app.shutdown()


def test_reverse_audio_loop_restarts_after_pause_resume(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.transmission import REVERSE
    from freight_fate.states.driving import PauseMenuState

    app = App()
    starts = []
    stops = []
    monkeypatch.setattr(app.ctx.audio, "set_engine_rpm", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_road_noise", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_weather", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_wind", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "set_ambient", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "play_music", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "reverse_start", lambda: starts.append("start"))
    monkeypatch.setattr(app.ctx.audio, "reverse_stop", lambda: stops.append("stop"))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        starts.clear()
        stops.clear()
        driving.truck.start_engine()
        driving.truck.transmission.gear = REVERSE
        driving._update_audio(0.0)
        assert starts == ["start"]

        app.ctx.push_state(PauseMenuState(app.ctx, driving))
        assert stops == ["stop"]
        app.state._resume()

        starts.clear()
        driving._update_audio(0.0)

        assert starts == ["start"]
    finally:
        app.shutdown()


def test_pause_menu_reports_off_duty_to_the_drivers_board():
    from freight_fate.app import App
    from freight_fate.states.driving import PauseMenuState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        assert driving.online_presence() is not None

        app.ctx.push_state(PauseMenuState(app.ctx, driving))
        pause = app.state
        assert isinstance(pause, PauseMenuState)
        # Paused players leave the public board like an off-duty sign-off...
        assert pause.online_presence() is None
        # ...while Discord presence still tells friends the game is paused.
        assert pause.presence().activity == "Paused"
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_can_back_up_to_a_missed_rest_stop_with_t_menu():
    from freight_fate.app import App
    from freight_fate.states.driving import ParkingFullState, RestStopState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi + 0.7
        driving.truck.velocity_mps = -1.0

        driving.trip.update(60)
        driving.truck.velocity_mps = 0.0
        assert abs(driving.trip.position_mi - stop.at_mi) <= 1.5

        driving.handle_event(key_event(pygame.K_t))

        assert isinstance(app.state, (RestStopState, ParkingFullState))
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_missed_when_too_fast():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 29.0  # ~65 mph: way too fast for the ramp
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)
        assert driving._ramp_mi is None  # blew past it
        assert driving._exit_stop is None
    finally:
        app.shutdown()


def test_exit_window_scales_with_speed_and_pacing():
    from freight_fate.app import App
    from freight_fate.states.driving_core import EXIT_WINDOW_MAX_MI, EXIT_WINDOW_MI

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.time_scale = 20.0

        driving.truck.velocity_mps = 0.0  # crawling -> the minimum window
        assert driving._exit_window_mi() == pytest.approx(EXIT_WINDOW_MI)

        driving.truck.velocity_mps = 70 / 2.23694  # highway speed -> more lead
        fast = driving._exit_window_mi()
        assert fast > EXIT_WINDOW_MI
        assert fast <= EXIT_WINDOW_MAX_MI

        driving.trip.time_scale = 40.0  # fast pacing compresses time -> even more
        faster = driving._exit_window_mi()
        assert faster >= fast
        assert faster <= EXIT_WINDOW_MAX_MI
    finally:
        app.shutdown()


def test_destination_exit_announced_within_scaled_window(monkeypatch):
    """At highway speed on fast pacing the callout fires beyond the base
    5-mile window, buying real seconds to hear it, arm, and brake."""
    from freight_fate.app import App
    from freight_fate.states.driving_core import EXIT_WINDOW_MI

    app = App()
    events = []
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.trip.time_scale = 40.0
        driving.truck.velocity_mps = 74 / 2.23694
        destination = driving._destination_exit_stop()
        driving.trip.position_mi = destination.at_mi - (EXIT_WINDOW_MI + 3.0)

        driving._check_destination_exit()

        assert events, "no callout inside the scaled window"
        assert "destination exit" in events[-1]
    finally:
        app.shutdown()


def test_exit_announcements_speak_each_name_once(monkeypatch):
    """Fallback phrasing must not repeat the facility or exit label -- the
    sentence is heard, not read."""
    from freight_fate.app import App
    from freight_fate.states.driving_core import RoadStop

    app = App()
    said = []
    monkeypatch.setattr(app.ctx, "say", lambda text, **k: said.append(text))
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: said.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        facility = "grocery warehouse Trenton Distribution in Trenton"
        stop = RoadStop(facility, 10.0, "delivery_destination", ("deliver",), exit_label="")
        stop.exit_phrase = ""

        monkeypatch.setattr(driving, "_upcoming_exit_stop", lambda: stop)
        driving.trip.position_mi = 9.0
        driving._take_exit()
        assert said[-1].count(facility) == 1
        assert "destination exit for" in said[-1]

        announcement = driving._destination_exit_announcement(stop, 1.2)
        assert announcement.count(facility) == 1
        assert "In 1 mile," in announcement  # singular, not "1 miles"

        driving.trip.position_mi = stop.at_mi
        driving.truck.velocity_mps = 29.0  # too fast: blow past it
        driving._update_exit(0.0)
        assert "missed" in said[-1]
        assert said[-1].count(facility) == 1
    finally:
        app.shutdown()


def test_labeled_missed_exit_names_the_exit_once(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_core import RoadStop

    app = App()
    said = []
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: said.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = RoadStop(
            "grocery warehouse in Trenton",
            10.0,
            "delivery_destination",
            ("deliver",),
            exit_label="exit 5B",
        )
        stop.exit_phrase = "exit 5B for US-1 South toward Trenton"
        driving._exit_stop = stop
        driving.trip.position_mi = stop.at_mi
        driving.truck.velocity_mps = 29.0

        driving._update_exit(0.0)

        assert "missed exit 5B for US-1 South toward Trenton" in said[-1]
        assert said[-1].count("exit 5B") == 1
    finally:
        app.shutdown()


def test_spoken_distances_pluralize():
    from freight_fate.sim.trip import _spoken_distance

    assert _spoken_distance(1.4, "mile") == "1 mile"
    assert _spoken_distance(0.6, "mile") == "1 mile"
    assert _spoken_distance(2.6, "kilometer") == "3 kilometers"
    assert _spoken_distance(0.2, "mile") == "0 miles"


@pytest.mark.smoke
def test_exit_key_is_a_toggle_and_needs_an_exit_nearby():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        # far from any stop: X does not arm
        driving.trip.position_mi = 0.0
        if driving.trip.stops[0].at_mi > 6.0:
            driving.handle_event(key_event(pygame.K_x))
            assert driving._exit_stop is None
        # in range it arms; pressing X again cancels
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 2.0
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is None
    finally:
        app.shutdown()


# -- engine audio follows out-of-band engine stops (nightly regression) ------------


def test_rest_menu_shutdown_also_stops_engine_audio():
    """Sleeping shuts the truck's engine down from a rest menu, outside the
    driving frame loop. Regression: the audio loop was left running -- masked
    while band volumes tracked RPM, plainly audible once the BASS engine
    model kept constant volume."""
    from freight_fate.app import App
    from freight_fate.states import driving_core

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        assert driving.truck.start_engine()
        driving._update_audio(0.0)
        assert app.ctx.audio.engine_running

        prefix = driving_core._shut_down_engine(driving)

        assert prefix == "You shut down the engine. "
        assert not driving.truck.engine_on
        assert not app.ctx.audio.engine_running

        # Already off: no double narration, audio stays off.
        assert driving_core._shut_down_engine(driving) == ""
        assert not app.ctx.audio.engine_running
    finally:
        app.shutdown()


def test_engine_audio_mirror_sync_catches_any_out_of_band_stop():
    """The frame-loop audio sync must work in both directions: any path that
    turns the truck's engine off without telling the audio engine is corrected
    on the next frame, silently."""
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        assert driving.truck.start_engine()
        driving._update_audio(0.0)
        assert app.ctx.audio.engine_running

        driving.truck.stop_engine()  # off-path stop: audio not told directly
        driving._update_audio(0.0)

        assert not app.ctx.audio.engine_running
    finally:
        app.shutdown()


def test_route_planning_labels_name_through_cities_with_states():
    """Route options must say which cities they pass through, state-qualified,
    in the spoken label itself -- not only in the F1 help (player request:
    'I have no idea where McCall is, but knowing the state gives me a
    general idea of, oh, that's the way we're going')."""
    from freight_fate.app import App
    from freight_fate.models import JobBoard
    from freight_fate.states.city_dispatch import RouteSelectState

    app = App()
    try:
        world = app.ctx.world
        job = next(
            j
            for j in JobBoard(world, seed=3).offers("Chicago", endorsements=set(), level=2)
            if len(world.supported_route_options(j.origin, j.destination)[0].cities) > 2
        )
        routes = world.supported_route_options(job.origin, job.destination)
        state = RouteSelectState(app.ctx, job, routes)
        state.items = state.build_items()

        label = state.items[0].text
        assert "through " in label or "passing no major cities" in label
        route = routes[0]
        first_via = world.city(route.cities[1])
        assert first_via.spoken_qualified in label
        # The destination line carries the state too.
        assert world.city(job.destination).spoken_qualified == job.spoken_destination
    finally:
        app.shutdown()


def test_destination_exit_scan_stays_on_the_final_approach():
    """Routes that finish on rural highways carry no baked interchanges, and
    the scan used to crown the last labeled exit anywhere on the route as the
    destination exit: player transcripts (2026-07-16) show a Lampasas run
    settled from Wichita Falls, 224 miles out, and a Havre, Montana run
    settled from I-39 in Wisconsin, 1,158 miles out. The scan must find an
    exit on the final approach or report none, so the synthetic end-of-route
    exit takes over."""
    from types import SimpleNamespace

    from freight_fate.data.world import get_world
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.driving_core import DESTINATION_EXIT_SCAN_WINDOW_MI

    world = get_world()
    for start, end in [
        ("springfield_il_us", "lampasas_tx_us"),
        ("jamestown_ny_us", "havre_mt_us"),
    ]:
        route = world.shortest_route(start, end, require_metadata=True)
        assert route is not None
        leg_starts: list[float] = []
        total = 0.0
        for leg in route.legs:
            leg_starts.append(total)
            total += leg.miles
        driving = SimpleNamespace(
            route=route,
            trip=SimpleNamespace(_leg_starts=leg_starts, position_mi=0.0, total_miles=total),
            ctx=SimpleNamespace(world=world),
        )
        details = DrivingState._scan_destination_exit_details(driving)
        if details is not None:
            assert details[0] >= total - DESTINATION_EXIT_SCAN_WINDOW_MI
