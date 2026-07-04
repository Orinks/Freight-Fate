"""Spoken menu readout: no doubled periods, optional 'N of M' position."""

from types import SimpleNamespace

from freight_fate.states.base import MenuItem, MenuState, end_sentence


def _menu(announce_position: bool = True) -> MenuState:
    class _Menu(MenuState):
        def build_items(self):
            return [
                MenuItem("Delivered 16 tons to Boston.", lambda: None),
                MenuItem("Sleep 10 hours", lambda: None),
            ]

    ctx = SimpleNamespace(settings=SimpleNamespace(announce_menu_position=announce_position))
    m = _Menu(ctx)
    m.refresh()  # populate items without a real ctx
    return m


def test_end_sentence_adds_one_period_never_two():
    assert end_sentence("Sleep 10 hours") == "Sleep 10 hours."
    assert end_sentence("Delivered to Boston.") == "Delivered to Boston."
    assert end_sentence("Ready?") == "Ready?"
    assert end_sentence("Note:") == "Note:"
    assert end_sentence("trailing space.  ") == "trailing space."


def test_menu_readout_never_doubles_the_period():
    m = _menu()
    # A sentence item keeps its single period before the counter.
    assert m.current_text() == "Delivered 16 tons to Boston. 1 of 2."
    # A plain label still gets its period added.
    m.index = 1
    assert m.current_text() == "Sleep 10 hours. 2 of 2."


def test_menu_position_can_be_suppressed():
    m = _menu(announce_position=False)
    assert m.current_text() == "Delivered 16 tons to Boston."  # no "1 of 2"
    m.index = 1
    assert m.current_text() == "Sleep 10 hours."
