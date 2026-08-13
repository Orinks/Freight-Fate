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
