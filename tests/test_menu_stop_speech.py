"""Left or Right Control silences speech in menus and the help reader.

The driving screen already stops its event voice with Control; menus and the
how-to-play reader speak on the main channel, so they need the same key to quiet
a long readout (job details, cargo loading, a whole help page).
"""

from types import SimpleNamespace

import pygame

from freight_fate.states.base import MenuItem, MenuState


class _Menu(MenuState):
    def build_items(self):
        return [MenuItem("One", lambda: None), MenuItem("Two", lambda: None)]


def _keydown(key):
    return SimpleNamespace(type=pygame.KEYDOWN, key=key, unicode="")


def _menu_with_stop(calls):
    ctx = SimpleNamespace(
        settings=SimpleNamespace(announce_menu_position=True),
        stop_speech=lambda: calls.append("stop"),
    )
    m = _Menu(ctx)
    m.refresh()  # populate items without a real ctx
    return m


def test_left_and_right_control_stop_speech_in_menus():
    calls = []
    m = _menu_with_stop(calls)
    m.handle_event(_keydown(pygame.K_LCTRL))
    m.handle_event(_keydown(pygame.K_RCTRL))
    assert calls == ["stop", "stop"]


def test_control_stops_speech_in_the_help_reader():
    from freight_fate.states.main_menu_help import HelpState

    calls = []
    ctx = SimpleNamespace(stop_speech=lambda: calls.append("stop"))
    state = HelpState(ctx, start_page=0)
    state.handle_event(_keydown(pygame.K_LCTRL))
    assert calls == ["stop"]


def test_stop_speech_silences_both_channels():
    from freight_fate.app import GameContext

    stopped = []
    speech = SimpleNamespace(
        stop_main=lambda: stopped.append("main"),
        stop_event=lambda: stopped.append("event"),
    )
    ctx = object.__new__(GameContext)
    ctx.speech = speech
    from freight_fate.speech import EventSpeechPacer

    ctx._event_pacer = EventSpeechPacer()  # stop_speech resets the event pacer
    ctx.stop_speech()
    assert stopped == ["main", "event"]


def test_menu_intro_help_documents_the_stop_key():
    assert "Control stops the current speech" in MenuState.intro_help
