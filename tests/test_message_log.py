from freight_fate.message_log import REVIEW_WINDOW_S, MessageCategory, MessageLog


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_messages_can_be_reviewed() -> None:
    log = MessageLog()

    log.add("General one", MessageCategory.GENERAL)
    log.add("Event one", MessageCategory.EVENT)
    log.add("General two", MessageCategory.GENERAL)

    assert log.current_message().text == "General two"
    # The first step back repeats what was just said, then walks.
    assert log.previous_message().text == "General two"
    assert log.previous_message().text == "Event one"
    assert log.previous_message().text == "General one"


def test_new_speech_re_arms_the_repeat_for_a_reviewer_at_the_latest() -> None:
    log = MessageLog()

    log.add("General one", MessageCategory.GENERAL)
    assert log.previous_message().text == "General one"

    log.add("General two", MessageCategory.GENERAL)
    assert log.previous_message().text == "General two"


def test_new_speech_does_not_move_a_reviewer_who_walked_back() -> None:
    log = MessageLog()

    log.add("One", MessageCategory.GENERAL)
    log.add("Two", MessageCategory.GENERAL)
    log.previous_message()  # repeats "Two"
    log.previous_message()  # steps to "One"

    log.add("Three", MessageCategory.GENERAL)

    # Still parked where they were; getting back to now is Ctrl+period.
    assert log.current_message().text == "One"
    assert log.last_message().text == "Three"


def test_stepping_forward_does_not_repeat() -> None:
    log = MessageLog()

    log.add("One", MessageCategory.GENERAL)
    log.add("Two", MessageCategory.GENERAL)

    assert log.first_message().text == "One"
    assert log.next_message().text == "Two"
    # Explicit positioning cancels the repeat, so back really goes back.
    assert log.previous_message().text == "One"


def test_category_change_moves_to_latest_matching_message() -> None:
    log = MessageLog()

    log.add("General one", MessageCategory.GENERAL)
    log.add("Event one", MessageCategory.EVENT)
    log.add("General two", MessageCategory.GENERAL)

    assert log.next_category() == "General"
    assert log.current_message().text == "General two"

    assert log.next_category() == "Event"
    assert log.current_message().text == "Event one"


def test_log_is_bounded_and_drops_the_oldest() -> None:
    log = MessageLog(limit=3)

    for index in range(5):
        log.add(f"Message {index}", MessageCategory.GENERAL)

    assert [message.text for message in log.messages] == [
        "Message 2",
        "Message 3",
        "Message 4",
    ]
    assert log.first_message().text == "Message 2"


def test_reviewer_keeps_their_place_when_the_log_trims() -> None:
    log = MessageLog(limit=3)

    for index in range(3):
        log.add(f"Message {index}", MessageCategory.GENERAL)

    log.previous_message()  # repeat "Message 2"
    log.previous_message()  # step to "Message 1"
    assert log.current_message().text == "Message 1"

    log.add("Message 3", MessageCategory.GENERAL)  # drops "Message 0"

    # Still on the same message, not shifted by the drop.
    assert log.current_message().text == "Message 1"


def test_reviewer_on_a_trimmed_away_message_lands_on_the_oldest_kept() -> None:
    log = MessageLog(limit=2)

    log.add("One", MessageCategory.GENERAL)
    log.add("Two", MessageCategory.GENERAL)
    log.previous_message()  # repeat "Two"
    log.previous_message()  # step to "One"

    log.add("Three", MessageCategory.GENERAL)  # "One" ages out

    assert log.current_message().text == "Two"


def test_the_same_line_twice_running_is_logged_once() -> None:
    log = MessageLog()

    log.add("Speed limit 55.", MessageCategory.GENERAL)
    log.add("Speed limit 55.", MessageCategory.GENERAL)
    log.add("Fuel is low.", MessageCategory.GENERAL)
    log.add("Speed limit 55.", MessageCategory.GENERAL)

    assert [message.text for message in log.messages] == [
        "Speed limit 55.",
        "Fuel is low.",
        "Speed limit 55.",
    ]


def test_a_lapsed_review_session_starts_again_at_the_newest() -> None:
    """The playtest case: glance at the history mid-run, drive on, press again."""
    clock = FakeClock()
    log = MessageLog(clock=clock)

    for text in ("One.", "Two.", "Three."):
        log.add(text, MessageCategory.GENERAL)

    log.previous_message()  # repeats "Three."
    log.previous_message()  # steps to "Two."
    assert log.current_message().text == "Two."

    # Back to driving. More happens while the cursor sits in the past.
    clock.advance(REVIEW_WINDOW_S + 1)
    for text in ("Four.", "Five."):
        log.add(text, MessageCategory.GENERAL)

    assert log.previous_message().text == "Five."


def test_an_active_review_session_is_not_dragged_forward() -> None:
    clock = FakeClock()
    log = MessageLog(clock=clock)

    for text in ("One.", "Two.", "Three."):
        log.add(text, MessageCategory.GENERAL)

    log.previous_message()
    log.previous_message()
    assert log.current_message().text == "Two."

    # Still browsing: a message arriving must not move the cursor.
    clock.advance(REVIEW_WINDOW_S / 2)
    log.add("Four.", MessageCategory.GENERAL)

    assert log.previous_message().text == "One."


def test_a_lapsed_session_keeps_the_filter_but_never_hides_in_silence() -> None:
    """Two tester reports pull opposite ways, and both are right.

    A filter left on Event once hid a whole delivery settlement in review, so
    the lapse used to clear it. But clearing it meant Tim S, who sets the
    filter to Event precisely because it makes the cab navigable, lost his
    choice every time he spent eleven seconds driving instead of browsing --
    which reads as the filter dropping at random (2026-08-21).

    The harm in the first report was SILENCE, not filtering: the settlement
    was unreachable without any sign it existed. So the preference stands,
    and the log can say what the filter is keeping out.
    """
    clock = FakeClock()
    log = MessageLog(clock=clock)

    log.add("Hazard ahead.", MessageCategory.EVENT)
    assert log.next_category() == "General"
    assert log.next_category() == "Event"

    clock.advance(REVIEW_WINDOW_S + 1)
    log.add("Delivery complete.", MessageCategory.GENERAL)

    # The driver's choice survives the lapse.
    assert log.category_name() == "Event"
    assert log.previous_message().text == "Hazard ahead."
    # And the settlement is not silently gone: the log knows it is out there.
    assert log.hidden_newer_count() == 1

    # Winding the filter back the way the player does reaches it, as ever.
    assert log.previous_category() == "General"
    assert log.previous_category() == "All"
    assert log.previous_message().text == "Delivery complete."
    assert log.hidden_newer_count() == 0


def test_copying_after_a_lapse_copies_the_newest() -> None:
    clock = FakeClock()
    log = MessageLog(clock=clock)

    log.add("One.", MessageCategory.GENERAL)
    log.add("Two.", MessageCategory.GENERAL)
    log.previous_message()
    log.previous_message()
    assert log.current_message().text == "One."

    clock.advance(REVIEW_WINDOW_S + 1)
    assert log.message_in_review().text == "Two."


def test_empty_log_returns_none() -> None:
    log = MessageLog()

    assert log.current_message() is None
    assert log.previous_message() is None
    assert log.next_message() is None
    assert log.first_message() is None
    assert log.last_message() is None
