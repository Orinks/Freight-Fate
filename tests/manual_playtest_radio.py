"""Temporary manual playtest driver for the 2026-08-12 radio changes.

Not part of the suite (filename avoids the test_* collection pattern); run
explicitly:

    uv run pytest tests/manual_playtest_radio.py -q -n 0 -s

Prints the session as the player heard it: every spoken line, plus [audio]
notes for what the music channel actually did and [debug] notes for the
signal numbers behind the dial order.
"""

import pygame
from playtest_harness import PlaytestHarness


def test_manual_radio_session(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Manual Radio Session")
        d = harness.driving
        audio_log = []
        monkeypatch.setattr(
            d.ctx.audio,
            "play_music",
            lambda track, fade_ms=1500: audio_log.append(f"play_music {track}"),
        )
        monkeypatch.setattr(
            d.ctx.audio,
            "stop_music",
            lambda fade_ms=0: audio_log.append(f"stop_music fade {fade_ms}"),
        )
        monkeypatch.setattr(
            d.ctx.audio,
            "play_radio_stream",
            lambda url, fade_ms=1500: audio_log.append("play_radio_stream (stubbed, no network)"),
        )

        cursor = len(result.transcript)

        def step(label, action=None):
            nonlocal cursor
            print(f"\n=== {label}")
            if action is not None:
                action()
            for line in result.transcript[cursor:]:
                print(f"  spoken | {line}")
            cursor = len(result.transcript)
            for note in audio_log:
                print(f"  audio  | {note}")
            audio_log.clear()

        def terrestrial_debug():
            from freight_fate.radio import TERRESTRIAL_GROUP, _dial_group

            d._sync_radio_settings()
            for r in d.radio.receivable_stations():
                if _dial_group(r.station) == TERRESTRIAL_GROUP:
                    print(
                        f"  debug  | terrestrial {r.station.display_name}: "
                        f"signal {r.signal:.2f} ({r.signal_label})"
                    )

        print(f"\n### Load: {result.destination or 'assigned delivery'}, engine off in the yard")

        step("Press M (radio) with the engine off", lambda: harness.press_key(pygame.K_m))
        step(
            "Press Page Down (tune) with the engine off",
            lambda: harness.press_key(pygame.K_PAGEDOWN),
        )
        step("Press Y (radio status) with the engine off", lambda: harness.press_key(pygame.K_y))

        def tick(seconds=1 / 60):
            # What the real game loop does each frame for sound: advance the
            # audio fades (ignition crank included) and run the audio sync.
            d.ctx.audio.update(seconds)
            d._update_audio(1 / 60)

        def start_engine():
            harness.press_key(pygame.K_e)
            tick(5.0)  # let the ignition crank finish, then the frame sync runs

        step("Press E to start the engine, let the crank finish", start_engine)

        step(
            "Press M twice: radio off, then back on",
            lambda: (harness.press_key(pygame.K_m), harness.press_key(pygame.K_m)),
        )

        print("\n=== The terrestrial band from here, strongest first")
        terrestrial_debug()

        def jump_to_terrestrial():
            event = pygame.event.Event(
                pygame.KEYDOWN, key=pygame.K_PAGEDOWN, unicode="", mod=pygame.KMOD_CTRL
            )
            for _ in range(2):  # route playlist -> Freight Fate stations -> terrestrial
                d.handle_event(event)

        step("Ctrl+Page Down twice to jump to Terrestrial", jump_to_terrestrial)
        step(
            "Tune down the band: Page Down three times",
            lambda: [harness.press_key(pygame.K_PAGEDOWN) for _ in range(3)],
        )
        step("Press Y for the signal readout", lambda: harness.press_key(pygame.K_y))

        def park_on_fringe():
            from freight_fate.radio import TERRESTRIAL_GROUP, _dial_group

            ranged = [
                r
                for r in d.radio.receivable_stations()
                if _dial_group(r.station) == TERRESTRIAL_GROUP and not r.station.always_available
            ]
            weakest = min(ranged, key=lambda r: r.signal)
            print(
                f"  debug  | leaving the radio on {weakest.station.display_name} "
                f"(signal {weakest.signal:.2f})"
            )
            d.radio.station_id = weakest.station.id

        step("Leave the dial on the weakest terrestrial signal", park_on_fringe)
        step(
            "Press M twice: off, then on again -- power-on should land clean",
            lambda: (harness.press_key(pygame.K_m), harness.press_key(pygame.K_m)),
        )

        def shut_down():
            harness.press_key(pygame.K_e)
            tick()

        step("Press E to shut the engine off, next frame", shut_down)
        step("Press M in the dead cab", lambda: harness.press_key(pygame.K_m))
        step("Press Y in the dead cab", lambda: harness.press_key(pygame.K_y))

        print("\n=== The Tab radio screen right now (engine off)")
        from freight_fate.states.driving_menu_states import DrivingStatusScreenState

        screen = DrivingStatusScreenState.__new__(DrivingStatusScreenState)
        screen.ctx = d.ctx
        screen.driving = d
        for line in screen._radio_lines():
            print(f"  screen | {line}")
