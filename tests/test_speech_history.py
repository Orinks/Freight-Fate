"""Speech history walk-back: quick repeat presses step back through the ring.

Owner design 2026-07-15: the comma key must reach more than the newest line.
First press repeats what just spoke; pressing again within a few seconds
walks one line older per press; a fresh announcement snaps back to newest.
"""

from freight_fate.speech import SpeechHistory


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _walked(history):
    step = history.step_back()
    assert step is not None
    return step


def test_first_press_speaks_the_newest_line():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("Fuel 62 gallons.")
    h.record("Safe speed 45.")

    assert _walked(h) == (0, "Safe speed 45.")


def test_quick_presses_walk_one_line_older_each():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    for line in ("first", "second", "third"):
        h.record(line)

    assert _walked(h) == (0, "third")
    clock.now += 2.0
    assert _walked(h) == (1, "second")
    clock.now += 2.0
    assert _walked(h) == (2, "first")


def test_walk_clamps_at_the_oldest_line():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("only line")

    assert _walked(h) == (0, "only line")
    clock.now += 1.0
    assert _walked(h) == (0, "only line")


def test_a_pause_longer_than_the_window_snaps_back_to_newest():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    for line in ("first", "second", "third"):
        h.record(line)
    assert _walked(h) == (0, "third")
    clock.now += 2.0
    assert _walked(h) == (1, "second")

    clock.now += SpeechHistory.STEP_WINDOW_S + 0.1
    assert _walked(h) == (0, "third")


def test_a_fresh_announcement_resets_the_walk():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("first")
    h.record("second")
    assert _walked(h) == (0, "second")
    clock.now += 1.0
    assert _walked(h) == (1, "first")

    h.record("breaking news")
    clock.now += 1.0
    assert _walked(h) == (0, "breaking news")


def test_consecutive_duplicates_collapse():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("older line")
    for _ in range(5):
        h.record("Cruise set, 55.")

    assert _walked(h) == (0, "Cruise set, 55.")
    clock.now += 1.0
    assert _walked(h) == (1, "older line")


def test_ring_keeps_only_the_newest_lines():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    for i in range(SpeechHistory.KEPT + 5):
        h.record(f"line {i}")

    seen = []
    step = h.step_back()
    while step is not None:
        back, line = step
        if seen and back == seen[-1][0]:
            break  # clamped at the oldest
        seen.append((back, line))
        clock.now += 1.0
        step = h.step_back()
    assert len(seen) == SpeechHistory.KEPT
    assert seen[0][1] == f"line {SpeechHistory.KEPT + 4}"
    assert seen[-1][1] == "line 5"


def test_empty_history_returns_none():
    h = SpeechHistory(clock=_Clock())
    assert h.step_back() is None


def test_comma_walks_back_through_game_and_event_speech():
    """End to end: both channels land in one ring, and older lines speak
    with a spoken "N back:" position so the player knows where they are."""
    from freight_fate.app import App

    app = App()
    try:
        spoken = []
        app.ctx.speech.say = lambda text, interrupt=True: spoken.append(text)
        app.ctx.settings.sapi_events = False

        app.ctx.say("Fuel 62 gallons.")
        app.ctx.say_event("Crossing the Agua Fria River.")
        del spoken[:]

        app.ctx.repeat_last_spoken()
        assert spoken[-1] == "Crossing the Agua Fria River."
        app.ctx.repeat_last_spoken()
        assert spoken[-1] == "1 back: Fuel 62 gallons."
        app.ctx.repeat_last_spoken()
        assert spoken[-1] == "1 back: Fuel 62 gallons."

        # A fresh line ends the walk: the next press repeats it plainly.
        app.ctx.say("Chains are on.")
        app.ctx.repeat_last_spoken()
        assert spoken[-1] == "Chains are on."
    finally:
        app.shutdown()
