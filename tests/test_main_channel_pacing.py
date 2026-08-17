"""The main channel comes under discipline while the player is driving.

The event voice has a pacer; the main channel had 535 call sites defaulting
to interrupt=True and none (research doc, part 1.1). R2's central fix: while
the top state is the driving state, ``ctx.say`` queues instead of cutting,
so an achievement or assist notice cannot stamp on the line mid-air. Menus
-- including menus pushed OVER a drive -- keep today's immediate behavior,
mirroring how screen readers cancel speech on navigation.
"""

from __future__ import annotations

from speech_capture import speech_stub

from freight_fate.states.base import State


class _Wheel(State):
    paces_main_speech = True


class _Menu(State):
    pass


def test_the_driving_state_declares_main_channel_pacing() -> None:
    from freight_fate.states.driving import DrivingState

    assert DrivingState.paces_main_speech is True
    assert State.paces_main_speech is False


def test_main_speech_queues_while_at_the_wheel() -> None:
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.speech.say = speech_stub(calls, with_interrupt=True)
        app.push_state(_Wheel(app.ctx))

        app.ctx.say("New achievement! Bumper-to-Bumper Blues.")

        assert calls == [("New achievement! Bumper-to-Bumper Blues.", False)]
    finally:
        app.shutdown()


def test_a_menu_over_the_drive_keeps_immediate_speech() -> None:
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.speech.say = speech_stub(calls, with_interrupt=True)
        app.push_state(_Wheel(app.ctx))
        app.push_state(_Menu(app.ctx))

        app.ctx.say("Settings. Audio. 1 of 9.")

        assert calls == [("Settings. Audio. 1 of 9.", True)]
    finally:
        app.shutdown()


def test_menu_speech_with_no_drive_anywhere_still_interrupts() -> None:
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.speech.say = speech_stub(calls, with_interrupt=True)
        app.push_state(_Menu(app.ctx))

        app.ctx.say("Main menu. New career. 1 of 6.")

        assert calls == [("Main menu. New career. 1 of 6.", True)]
    finally:
        app.shutdown()


def test_queued_reply_no_longer_purges_the_shared_event_channel() -> None:
    """The point of the demotion on a shared voice: a main-channel line
    during the drive cannot cut a pending ROUTE line any more, so nothing
    needs rescuing -- the road line simply keeps its place in the queue."""
    from freight_fate.app import App
    from freight_fate.speech import EventPriority

    app = App()
    try:
        main: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = False  # events ride the main voice
        app.ctx.speech.say = speech_stub(main, with_interrupt=True)
        app.push_state(_Wheel(app.ctx))

        scale = "Open weigh station ahead in two miles. All trucks must pull in."
        app.ctx.say_event(scale, interrupt=False, priority=EventPriority.ROUTE)
        app.ctx.say("Fifty five miles per hour.")  # info reply, default interrupt

        # Reply queued behind the scale line; the scale line was never cut,
        # so it appears exactly once -- no rescue, no repetition.
        assert main == [(scale, False), ("Fifty five miles per hour.", False)]
    finally:
        app.shutdown()


def test_a_readout_the_player_asked_for_still_cuts() -> None:
    """R2 was aimed at lines nobody asked for, and caught info keys too.

    On the 1.8 release every readout cut the line in progress, so pressing a
    key was how you got out from under an announcement. R2's central demotion
    removed that on 1.9 for the keys as well as for the notices, which is what
    a tester reported as the controller "not interrupting" (Sarah R. via the
    owner, 2026-08-16) -- it was never controller-specific.
    """
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.speech.say = speech_stub(calls, with_interrupt=True)
        app.push_state(_Wheel(app.ctx))

        with app.ctx.player_asked():
            app.ctx.say("Speed limit 65 miles per hour.")

        assert calls == [("Speed limit 65 miles per hour.", True)]
    finally:
        app.shutdown()


def test_the_asked_for_exemption_does_not_leak_past_the_press() -> None:
    """An assist notice arriving after the key must still queue."""
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.speech.say = speech_stub(calls, with_interrupt=True)
        app.push_state(_Wheel(app.ctx))

        with app.ctx.player_asked():
            app.ctx.say("Speed limit 65 miles per hour.")
        app.ctx.say("New achievement! Bumper-to-Bumper Blues.")

        assert calls[-1] == ("New achievement! Bumper-to-Bumper Blues.", False)
    finally:
        app.shutdown()


def test_nested_presses_restore_rather_than_latch() -> None:
    """A handler that opens a screen which speaks must not stick the flag on."""
    from freight_fate.app import App

    app = App()
    try:
        app.push_state(_Wheel(app.ctx))
        assert app.ctx._speech_requested is False
        with app.ctx.player_asked():
            with app.ctx.player_asked():
                assert app.ctx._speech_requested is True
            assert app.ctx._speech_requested is True
        assert app.ctx._speech_requested is False
    finally:
        app.shutdown()


def test_pressing_an_info_key_at_the_wheel_cuts_the_line_in_progress() -> None:
    """End to end through the real driving state, keyboard and pad alike."""
    import pygame
    from driving_feature_helpers import quiet_trip, start_drive

    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        calls: list[tuple[str, bool]] = []
        app.ctx.speech.say = speech_stub(calls, with_interrupt=True)

        driving.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, unicode=" ", mod=0)
        )
        assert calls and calls[-1][1] is True, "a pressed key must cut"

        driving.handle_controller(
            pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_B),
            app.ctx.controller,
        )
        assert calls[-1][1] is True, "a pad button is a request too"

        # And the drive's own chatter still queues behind whatever is playing.
        app.ctx.say("New achievement! Bumper-to-Bumper Blues.")
        assert calls[-1] == ("New achievement! Bumper-to-Bumper Blues.", False)
    finally:
        app.shutdown()
