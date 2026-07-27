from freight_fate.message_log import MessageCategory, MessageLog


def test_messages_can_be_reviewed() -> None:
    log = MessageLog()

    log.add("General one", MessageCategory.GENERAL)
    log.add("Event one", MessageCategory.EVENT)
    log.add("General two", MessageCategory.GENERAL)

    assert log.current_message().text == "General two"
    assert log.previous_message().text == "Event one"
    assert log.previous_message().text == "General one"


def test_category_change_moves_to_latest_matching_message() -> None:
    log = MessageLog()

    log.add("General one", MessageCategory.GENERAL)
    log.add("Event one", MessageCategory.EVENT)
    log.add("General two", MessageCategory.GENERAL)

    assert log.next_category() == "General"
    assert log.current_message().text == "General two"

    assert log.next_category() == "Event"
    assert log.current_message().text == "Event one"


def test_empty_log_returns_none() -> None:
    log = MessageLog()

    assert log.current_message() is None
    assert log.previous_message() is None
    assert log.next_message() is None
    assert log.first_message() is None
    assert log.last_message() is None
