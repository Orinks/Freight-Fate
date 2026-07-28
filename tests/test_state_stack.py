"""The App state stack: what enters, what exits, and what ends the game.

Rebuilding the stack (quit to the title, arriving at a facility) empties it on
the way to a new screen. Only the player backing out of the last state should
end the run.
"""

from freight_fate.app import App
from freight_fate.states.base import State


class RecordingState(State):
    """A screen that notes when it is entered and left."""

    def __init__(self, ctx, name, log):
        super().__init__(ctx)
        self.name = name
        self.log = log

    def enter(self) -> None:
        self.log.append(("enter", self.name))

    def exit(self) -> None:
        self.log.append(("exit", self.name))


def _app_with_stack(*names):
    app = App()
    app.running = True
    log = []
    for name in names:
        app.push_state(RecordingState(app.ctx, name, log))
    log.clear()
    return app, log


def test_reset_to_keeps_the_game_running():
    """Quitting a drive to the main menu must not close the game."""
    app, log = _app_with_stack("menu", "city", "driving", "pause")

    app.reset_to(RecordingState(app.ctx, "title", log))

    assert app.running
    assert [s.name for s in app.states] == ["title"]
    assert log == [
        ("exit", "pause"),
        ("exit", "driving"),
        ("exit", "city"),
        ("exit", "menu"),
        ("enter", "title"),
    ]
    app.shutdown()


def test_replace_state_on_the_last_state_keeps_the_game_running():
    app, log = _app_with_stack("menu")

    app.replace_state(RecordingState(app.ctx, "notice", log))

    assert app.running
    assert [s.name for s in app.states] == ["notice"]
    assert log == [("exit", "menu"), ("enter", "notice")]
    app.shutdown()


def test_popping_the_last_state_ends_the_game():
    """Backing out of the final screen is still how the player leaves."""
    app, log = _app_with_stack("menu")

    app.pop_state()

    assert not app.running
    assert app.states == []
    assert log == [("exit", "menu")]
    app.shutdown()


def test_pop_reveals_the_state_underneath():
    app, log = _app_with_stack("menu", "settings")

    app.pop_state()

    assert app.running
    assert log == [("exit", "settings"), ("enter", "menu")]
    app.shutdown()


def test_rebuilt_stack_can_skip_enter_and_exit():
    """The new-career screens drop their pickers without re-speaking them."""
    app, log = _app_with_stack("menu", "name", "region")

    app.pop_state(True, False)
    app.reset_to(RecordingState(app.ctx, "city", log), should_exit=False, reentry=False)

    assert app.running
    assert [s.name for s in app.states] == ["city"]
    assert log == [("exit", "region")]
    app.shutdown()
