"""Game audio steps back while the event voice speaks (R13, XAG 105).

A warning must survive a loud cab -- engine, weather, and the radio -- without
the voice itself getting louder. The duck engages the moment a line reaches
the event channel and restores on the pacer's own projection of when the
voice falls silent: no polling of the speech backend, which cannot be asked.
"""

from __future__ import annotations

import pytest
from speech_capture import speech_stub

from freight_fate.audio import SPEECH_DUCK_LEVEL
from freight_fate.speech import EventSpeechPacer


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _rig(app):
    ducks: list[float] = []
    app.ctx.settings.sapi_events = True
    app.ctx.speech.say_event = speech_stub()
    app.ctx.audio.set_speech_duck = ducks.append
    clock = FakeClock()
    app.ctx._event_pacer = EventSpeechPacer(clock=clock)
    return ducks, clock


def test_ducking_defaults_on() -> None:
    from freight_fate.settings import Settings

    assert Settings().duck_audio_for_speech is True


def test_event_speech_ducks_the_mix_and_the_frame_after_silence_restores_it() -> None:
    from freight_fate.app import App

    app = App()
    try:
        ducks, clock = _rig(app)

        app.ctx.say_event("Open weigh station ahead in two miles.", interrupt=False)
        assert ducks == [SPEECH_DUCK_LEVEL]

        # Voice still speaking: the per-frame check leaves the duck alone.
        app.ctx.update_speech_duck()
        assert ducks == [SPEECH_DUCK_LEVEL]

        # The projection says the line has finished: the mix comes back.
        clock.now += 30.0
        app.ctx.update_speech_duck()
        assert ducks == [SPEECH_DUCK_LEVEL, 1.0]

        # And it is restored exactly once, not every frame.
        app.ctx.update_speech_duck()
        assert ducks == [SPEECH_DUCK_LEVEL, 1.0]
    finally:
        app.shutdown()


def test_the_setting_turns_the_duck_off() -> None:
    from freight_fate.app import App

    app = App()
    try:
        ducks, _ = _rig(app)
        app.ctx.settings.duck_audio_for_speech = False

        app.ctx.say_event("Open weigh station ahead in two miles.", interrupt=False)

        assert ducks == []
    finally:
        app.shutdown()


def test_a_suppressed_repeat_does_not_duck() -> None:
    """A line the pacer never lets reach the voice must not touch the mix."""
    from freight_fate.app import App

    app = App()
    try:
        ducks, _ = _rig(app)
        line = "You sideswiped a box truck in the right lane!"
        app.ctx.say_event(line, interrupt=True)
        ducks.clear()

        app.ctx.say_event(line, interrupt=True)  # inside the repeat window

        assert ducks == []
    finally:
        app.shutdown()


def test_the_backends_scale_engine_weather_and_music_only() -> None:
    """The duck reaches the channels the doc names -- engine, weather, and
    the music slot the radio rides -- and leaves UI, siren, and gameplay
    cues at full volume."""
    from freight_fate.app import App

    app = App()
    try:
        impl = app.ctx.audio._impl
        engine = impl._category_volume("engine")
        weather = impl._category_volume("weather")
        ui = impl._category_volume("ui")
        siren = impl._category_volume("siren")
        sfx = impl._category_volume("sfx")

        app.ctx.audio.set_speech_duck(SPEECH_DUCK_LEVEL)
        assert impl.speech_duck == SPEECH_DUCK_LEVEL
        assert impl._category_volume("engine") == pytest.approx(engine * SPEECH_DUCK_LEVEL)
        assert impl._category_volume("weather") == pytest.approx(weather * SPEECH_DUCK_LEVEL)
        assert impl._category_volume("ui") == pytest.approx(ui)
        assert impl._category_volume("siren") == pytest.approx(siren)
        assert impl._category_volume("sfx") == pytest.approx(sfx)

        app.ctx.audio.set_speech_duck(1.0)
        assert impl._category_volume("engine") == pytest.approx(engine)
    finally:
        app.shutdown()
