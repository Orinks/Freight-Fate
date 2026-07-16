"""The event-voice pacer drops stale backlogs instead of performing them.

Owner playtest 2026-07-15: arriving at the yard played the whole approach
script late -- "slow down to dock, at dock, delivering" heard after the
trailer was already empty -- because the event voice queues faster than it
speaks. The pacer projects when the channel falls silent; a queued line
that would start speaking more than STALE_WAIT_S after the moment it
described flushes the backlog and speaks fresh.
"""

from __future__ import annotations

from freight_fate.speech import EventSpeechPacer


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make_pacer() -> tuple[EventSpeechPacer, FakeClock]:
    clock = FakeClock()
    return EventSpeechPacer(clock=clock), clock


LONG_LINE = "x" * 130  # ~10 seconds at the default 13 chars per second


def test_quiet_channel_queues_normally() -> None:
    pacer, _ = make_pacer()
    assert pacer.should_flush("Slow down for the dock.") is False


def test_backlog_past_the_threshold_flushes() -> None:
    pacer, _ = make_pacer()
    # First long line starts immediately; the second waits ~10s behind it --
    # far past the 3-second staleness budget.
    assert pacer.should_flush(LONG_LINE) is False
    assert pacer.should_flush("At the dock.") is True


def test_flush_restarts_the_projection() -> None:
    pacer, _ = make_pacer()
    pacer.should_flush(LONG_LINE)
    assert pacer.should_flush("At the dock.") is True
    # The flush purged the channel: the very next line queues normally.
    assert pacer.should_flush("Delivering.") is False


def test_interrupt_resets_to_truth() -> None:
    pacer, _ = make_pacer()
    pacer.should_flush(LONG_LINE)
    pacer.note_interrupt("Collision!")
    # The interrupting line purged the backlog; a short queued follow-up
    # starts right behind it, inside the staleness budget.
    assert pacer.should_flush("Total damage 12 percent.") is False


def test_projection_expires_with_real_time() -> None:
    pacer, clock = make_pacer()
    pacer.should_flush(LONG_LINE)
    clock.now += 30.0  # the voice long since finished speaking
    assert pacer.should_flush("Exit ahead.") is False


def test_reset_clears_the_projection() -> None:
    pacer, _ = make_pacer()
    pacer.should_flush(LONG_LINE)
    pacer.reset()
    assert pacer.should_flush("At the dock.") is False


def test_say_event_flushes_a_stale_backlog_end_to_end() -> None:
    """ctx.say_event: a burst of queued events turns into an interrupting
    (channel-purging) delivery once the backlog goes stale."""
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = lambda text, interrupt=True: calls.append((text, interrupt))

        approach = [
            "Slow down for the dock, twenty five miles per hour through the yard.",
            "Passing the fuel island, dock doors ahead on the left.",
            "At the dock. Line up square and ease it back.",
            "Delivering. The forklift crew is unloading the trailer.",
        ]
        for line in approach:
            app.ctx.say_event(line, interrupt=False)

        assert all(not interrupt for _, interrupt in calls[:1])
        assert any(interrupt for _, interrupt in calls), (
            "a stale backlog was performed in full -- the pacer never flushed"
        )
        # Every line still reached the voice in order; staleness changes
        # delivery, never drops the newest information.
        assert [text for text, _ in calls] == approach
    finally:
        app.shutdown()


def test_many_short_lines_stay_within_budget_then_flush() -> None:
    pacer, _ = make_pacer()
    line = "Passing the fuel island."  # ~2.3s estimated
    verdicts = [pacer.should_flush(line) for _ in range(4)]
    # The first few fit inside the budget; the backlog eventually crosses it.
    assert verdicts[0] is False
    assert True in verdicts[1:]
