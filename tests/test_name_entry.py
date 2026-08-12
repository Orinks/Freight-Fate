"""Accessible review of the driver-name text field.

Regression coverage for the bug where left/right arrows did nothing while
typing a driver name for a new career: a screen reader user had no way to
step back through what they had typed to check it before pressing Enter.
These pin the standard accessible-text-field behavior: a review cursor that
speaks each character as it moves, Home/End jump-and-speak, backspace that
edits (and deletes) at the cursor rather than always the end, and character
echo -- including a "cap" marker so a capital letter is distinguishable by
ear from a lowercase one, since text-to-speech reads "J" and "j" the same.
"""

import pygame
from speech_capture import speech_stub


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def open_name_entry(app):
    from freight_fate.states.main_menu import MainMenuState, NameEntryState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, NameEntryState)
    return app.state


def type_text(state, text):
    for ch in text:
        state.handle_event(key_event(ord(ch.lower()) if ch.isalpha() else ord(ch), ch))


def test_typed_characters_are_echoed_including_space_and_capitals(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        state = open_name_entry(app)
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        type_text(state, "Jo Ann")
        assert state.name == "Jo Ann"
        assert spoken == ["cap j", "o", "space", "cap a", "n", "n"]
    finally:
        app.shutdown()


def test_left_arrow_reviews_characters_back_to_front(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        state = open_name_entry(app)
        type_text(state, "Cary")
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

        state.handle_event(key_event(pygame.K_LEFT))
        state.handle_event(key_event(pygame.K_LEFT))
        state.handle_event(key_event(pygame.K_LEFT))
        state.handle_event(key_event(pygame.K_LEFT))

        assert spoken == ["y", "r", "a", "cap c"]
        assert state.cursor == 0
        # Reviewing does not change what was typed.
        assert state.name == "Cary"
    finally:
        app.shutdown()


def test_right_arrow_reviews_characters_front_to_back_after_reviewing_left(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        state = open_name_entry(app)
        type_text(state, "Cary")
        # Walk the cursor back to the start first, as a player checking
        # their spelling would, then arrow forward again.
        for _ in range(4):
            state.handle_event(key_event(pygame.K_LEFT))
        assert state.cursor == 0

        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        state.handle_event(key_event(pygame.K_RIGHT))
        state.handle_event(key_event(pygame.K_RIGHT))
        state.handle_event(key_event(pygame.K_RIGHT))
        state.handle_event(key_event(pygame.K_RIGHT))

        assert spoken == ["cap c", "a", "r", "y"]
        assert state.cursor == 4
    finally:
        app.shutdown()


def test_left_arrow_at_start_of_empty_field_does_not_crash(monkeypatch):
    from freight_fate.app import App

    app = App()
    played = []
    try:
        state = open_name_entry(app)
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **_kwargs: played.append(key))
        state.handle_event(key_event(pygame.K_LEFT))
        assert state.cursor == 0
        assert state.name == ""
        assert "ui/error" in played
    finally:
        app.shutdown()


def test_right_arrow_at_end_of_typed_name_gives_boundary_feedback(monkeypatch):
    from freight_fate.app import App

    app = App()
    played = []
    try:
        state = open_name_entry(app)
        type_text(state, "Cary")
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **_kwargs: played.append(key))
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

        state.handle_event(key_event(pygame.K_RIGHT))

        assert state.cursor == 4
        assert spoken == []  # no character left to move over
        assert "ui/error" in played
    finally:
        app.shutdown()


def test_home_and_end_jump_to_ends_and_speak_the_edge_character(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        state = open_name_entry(app)
        type_text(state, "Cary")
        state.handle_event(key_event(pygame.K_LEFT))
        state.handle_event(key_event(pygame.K_LEFT))
        assert state.cursor == 2

        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        state.handle_event(key_event(pygame.K_HOME))
        assert state.cursor == 0
        assert spoken == ["Start. cap c"]

        spoken.clear()
        state.handle_event(key_event(pygame.K_END))
        assert state.cursor == 4
        assert spoken == ["End. y"]
    finally:
        app.shutdown()


def test_home_and_end_are_no_ops_when_the_cursor_is_already_there(monkeypatch):
    from freight_fate.app import App

    app = App()
    played = []
    try:
        state = open_name_entry(app)
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **_kwargs: played.append(key))
        # Fresh, empty field: cursor is already at 0, which is also the end.
        state.handle_event(key_event(pygame.K_HOME))
        assert "ui/error" in played
        played.clear()
        state.handle_event(key_event(pygame.K_END))
        assert "ui/error" in played
    finally:
        app.shutdown()


def test_backspace_deletes_the_character_before_the_cursor_and_speaks_it(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        state = open_name_entry(app)
        type_text(state, "Cary")
        # Move the cursor to just after the "a" (index 2) and delete it,
        # not the last-typed "y" -- true cursor editing, not append-only.
        state.handle_event(key_event(pygame.K_LEFT))
        state.handle_event(key_event(pygame.K_LEFT))
        assert state.cursor == 2

        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        state.handle_event(key_event(pygame.K_BACKSPACE))

        assert state.name == "Cry"
        assert state.cursor == 1
        assert spoken == ["Deleted a. Cry"]
    finally:
        app.shutdown()


def test_backspace_on_empty_field_gives_boundary_feedback_not_a_crash(monkeypatch):
    from freight_fate.app import App

    app = App()
    played = []
    try:
        state = open_name_entry(app)
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **_kwargs: played.append(key))
        state.handle_event(key_event(pygame.K_BACKSPACE))
        assert state.name == ""
        assert "ui/error" in played
    finally:
        app.shutdown()


def test_typing_inserts_at_the_cursor_not_only_at_the_end(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        state = open_name_entry(app)
        type_text(state, "Crry")
        # Fix the typo (missing "a" after "C") by moving the cursor back
        # between "C" and the first "r", then inserting there.
        state.handle_event(key_event(pygame.K_LEFT))
        state.handle_event(key_event(pygame.K_LEFT))
        state.handle_event(key_event(pygame.K_LEFT))
        assert state.cursor == 1

        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        state.handle_event(key_event(ord("a"), "a"))

        assert state.name == "Carry"
        assert state.cursor == 2
        assert spoken == ["a"]
    finally:
        app.shutdown()


def test_deleting_the_last_character_reports_empty(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        state = open_name_entry(app)
        type_text(state, "A")
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        state.handle_event(key_event(pygame.K_BACKSPACE))
        assert state.name == ""
        assert state.cursor == 0
        assert spoken == ["Deleted cap a. Empty."]
    finally:
        app.shutdown()


def test_lines_show_a_cursor_marker_at_the_review_position():
    from freight_fate.app import App

    app = App()
    try:
        state = open_name_entry(app)
        type_text(state, "Cary")
        state.handle_event(key_event(pygame.K_LEFT))
        state.handle_event(key_event(pygame.K_LEFT))
        assert state.cursor == 2
        lines = state.lines()
        assert any(line == "Driver name: Ca|ry" for line in lines)
    finally:
        app.shutdown()
