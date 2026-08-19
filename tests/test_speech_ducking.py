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
    # Opt in: the duck ships off by default (the engine is the instrument
    # panel), and these tests exercise what it does once a player enables it.
    app.ctx.settings.duck_audio_for_speech = True
    app.ctx.speech.say_event = speech_stub()
    app.ctx.audio.set_speech_duck = ducks.append
    clock = FakeClock()
    app.ctx._event_pacer = EventSpeechPacer(clock=clock)
    return ducks, clock


def test_ducking_defaults_off() -> None:
    """In an audio-first sim the engine is the instrument panel -- a blind
    driver reads speed off it -- so ducking is opt-in for players who need
    it, not a default that changes what everyone hears (owner, 2026-08-12)."""
    from freight_fate.settings import Settings

    assert Settings().duck_audio_for_speech is False


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


def test_an_earcon_gets_the_room_the_words_it_replaces_would_have_had():
    """Tester Shane, 2026-08-17: "some of the sounds when you put speech in
    quiet mode have been significantly lowered."

    Measured absolutely they were not -- the confirmation note is about 4 dB
    LOUDER than the chime it replaced, and a trooper pass never drops below
    its old level. Both checks missed it, because a listener hears a level
    RELATIVE to what is under it.

    A spoken line ducks engine, weather and radio while it talks. A silenced
    line returned from say_event before reaching that duck, so its earcon
    played against the full road bed -- and quiet is exactly the rung where
    confirmation, status and coaching all become earcons, so the sound
    carrying the information was the one competing hardest to be heard.
    """
    from freight_fate.app import App
    from freight_fate.audio import SPEECH_DUCK_LEVEL
    from freight_fate.speech_pacing import SpeechCategory

    app = App()
    try:
        ducks: list[float] = []
        app.ctx.audio.set_speech_duck = lambda d: ducks.append(d)
        app.ctx.audio.play = lambda *a, **k: None
        app.ctx.settings.duck_audio_for_speech = True
        app.ctx.settings.driving_speech = "quiet"  # confirmation -> earcon

        app.ctx.say_event(
            "Automatic braking.", interrupt=False, category=SpeechCategory.CONFIRMATION
        )

        assert ducks, "the earcon played against an unducked mix"
        assert ducks[-1] == SPEECH_DUCK_LEVEL
        assert app.ctx._speech_ducked
    finally:
        app.shutdown()


def test_the_earcon_duck_lets_go_on_its_own():
    """It cannot lean on the pacer's projection, because a silenced line has
    no voice to project -- so it holds for its own short window and releases.
    A duck that never released would leave the road permanently halved."""
    import time

    from freight_fate.app import App
    from freight_fate.audio import EARCON_DUCK_S
    from freight_fate.speech_pacing import SpeechCategory

    assert EARCON_DUCK_S <= 0.5, "longer than any ladder earcon needs"

    app = App()
    try:
        ducks: list[float] = []
        app.ctx.audio.set_speech_duck = lambda d: ducks.append(d)
        app.ctx.audio.play = lambda *a, **k: None
        app.ctx.settings.duck_audio_for_speech = True
        app.ctx.settings.driving_speech = "quiet"

        app.ctx.say_event(
            "Automatic braking.", interrupt=False, category=SpeechCategory.CONFIRMATION
        )
        assert app.ctx._speech_ducked

        # Still inside the window: the mix stays back.
        app.ctx.update_speech_duck()
        assert app.ctx._speech_ducked

        app.ctx._earcon_duck_until = time.monotonic() - 0.01
        app.ctx.update_speech_duck()
        assert not app.ctx._speech_ducked
        assert ducks[-1] == 1.0
    finally:
        app.shutdown()


def test_nothing_anywhere_ducks_when_the_player_turned_ducking_off():
    """Owner, 2026-08-19: "if the duck setting is off, absolutely nothing,
    earcons, radio or anything should be ducked at all."

    Pinned as a PROPERTY over every duck in the game rather than one test per
    mechanism, because the failure mode is a NEW duck being added that forgets
    to ask -- which is exactly how the picket duck and, before it, the earcon
    duck got in. "Do not step my audio back" is one behavior with one name;
    a player who turned it off did not mean "except for this one".
    """
    import inspect

    from freight_fate.app import GameContext
    from freight_fate.states import driving_enforcement, driving_updates

    # Every place that engages a duck must consult the setting. Checked in the
    # source so a new engage point cannot pass by never being exercised.
    engage_points = [
        ("earcon", inspect.getsource(GameContext._engage_earcon_duck)),
        ("speech", inspect.getsource(GameContext._engage_speech_duck)),
        (
            "radio cue",
            inspect.getsource(driving_enforcement.EnforcementWatchMixin._duck_radio_for_cue),
        ),
    ]
    for name, src in engage_points:
        assert "duck_audio_for_speech" in src, f"the {name} duck never asks the setting"

    picket = inspect.getsource(driving_updates.DrivingUpdateMixin._update_radio_fringe)
    assert "duck_audio_for_speech" in picket, "the picket duck never asks the setting"


def test_with_ducking_off_an_earcon_leaves_the_mix_alone():
    """The behavioral half of the rule, end to end."""
    from freight_fate.app import App
    from freight_fate.speech_pacing import SpeechCategory

    app = App()
    try:
        ducks: list[float] = []
        app.ctx.audio.set_speech_duck = lambda d: ducks.append(d)
        app.ctx.audio.play = lambda *a, **k: None
        app.ctx.settings.duck_audio_for_speech = False
        app.ctx.settings.driving_speech = "quiet"

        app.ctx.say_event(
            "Automatic braking.", interrupt=False, category=SpeechCategory.CONFIRMATION
        )

        assert ducks == [], f"the mix was stepped back anyway: {ducks}"
        assert not app.ctx._speech_ducked
    finally:
        app.shutdown()
