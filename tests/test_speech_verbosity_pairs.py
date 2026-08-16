"""The delivery layer resolves normal/terse message pairs (R5).

Terse coverage used to depend on 79 hand-built call-site branches against
711 speech call sites, which is how the terse hazard call drifted onto a
synonym. A message now carries both renderings in one definition, and
``GameContext.say`` / ``say_event`` pick the one the player's speech mode
asks for -- so a call site cannot forget terse, and the two forms cannot
drift apart.
"""

from __future__ import annotations

from speech_capture import speech_stub

from freight_fate.speech_text import SpokenMessage, terse_silent


def test_a_pair_behaves_as_its_normal_string() -> None:
    pair = SpokenMessage("Watch your speed. The limit is 65 miles per hour.", "Limit 65.")
    assert pair == "Watch your speed. The limit is 65 miles per hour."
    assert "limit" in pair
    assert f"{pair}" == pair.normal
    assert isinstance(pair, str)


def test_render_picks_the_mode() -> None:
    pair = SpokenMessage("Watch your speed. The limit is 65 miles per hour.", "Limit 65.")
    assert pair.render(terse=False) == "Watch your speed. The limit is 65 miles per hour."
    assert pair.render(terse=True) == "Limit 65."


def test_no_terse_rendering_means_both_modes_speak_the_same() -> None:
    line = SpokenMessage("Collision! The truck took damage.")
    assert line.render(terse=True) == line.render(terse=False) == str(line)


def test_empty_terse_rendering_drops_the_line_whole() -> None:
    line = terse_silent("You slow nearly to a stop and ease around it. Well done.")
    assert line.render(terse=False) == "You slow nearly to a stop and ease around it. Well done."
    assert line.render(terse=True) == ""


def test_plus_extends_both_renderings() -> None:
    pair = SpokenMessage(
        "Brake or change lanes! Slow car ahead.", "Brake or change lanes! Slow car ahead."
    )
    grown = pair.plus("Automatic speed control canceled.")
    assert grown.render(terse=False).endswith("Automatic speed control canceled.")
    assert grown.render(terse=True).endswith("Automatic speed control canceled.")
    assert grown.render(terse=True).startswith("Brake or change lanes!")


def test_plus_on_a_dropped_line_keeps_the_suffix_in_terse() -> None:
    grown = terse_silent("Through the bend, held your line.").plus("Cruise resuming.")
    assert grown.render(terse=True) == "Cruise resuming."


class _FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _speaking_app():
    from freight_fate.app import App
    from freight_fate.speech import EventSpeechPacer

    app = App()
    app.ctx.settings.sapi_events = True
    clock = _FakeClock()
    app.ctx._event_pacer = EventSpeechPacer(clock=clock)
    return app, clock


def test_say_event_speaks_the_rendering_the_mode_asks_for() -> None:
    app, clock = _speaking_app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        pair = SpokenMessage("Watch your speed. The limit is 65 miles per hour.", "Limit 65.")

        # The first line finishes (the clock steps past it) before the next
        # speaks, so neither the repeat window, the backlog projection, nor
        # the cut-line requeue gets a say in a test about rendering choice.
        app.ctx.settings.driving_speech = "standard"
        app.ctx.say_event(pair, interrupt=True)
        clock.now += 30.0
        app.ctx.settings.driving_speech = "quiet"
        app.ctx.say_event(pair, interrupt=True)

        assert spoken == [
            "Watch your speed. The limit is 65 miles per hour.",
            "Limit 65.",
        ]
    finally:
        app.shutdown()


def test_a_terse_dropped_line_never_reaches_the_voice_or_the_log() -> None:
    app, _clock = _speaking_app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "quiet"
        before = len(app.ctx.message_log.messages)

        app.ctx.say_event(terse_silent("You swerve around it. Well done."), interrupt=False)

        assert spoken == []
        assert len(app.ctx.message_log.messages) == before
    finally:
        app.shutdown()


def test_the_main_channel_resolves_pairs_too() -> None:
    app, _clock = _speaking_app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say = speech_stub(spoken)
        app.ctx.settings.driving_speech = "quiet"

        app.ctx.say(SpokenMessage("New achievement! Night Owl. Flavor text.", "Night Owl."))
        app.ctx.say(terse_silent("Nice shift."))

        assert spoken == ["Night Owl."]
    finally:
        app.shutdown()


def test_the_capture_stub_resolves_pairs_the_same_way() -> None:
    normal: list[str] = []
    terse: list[str] = []
    pair = SpokenMessage("Toll charged: 15 dollars.", "Toll, 15 dollars, carrier.")
    speech_stub(normal)(pair)
    speech_stub(terse, terse=True)(pair)
    speech_stub(terse, terse=True)(terse_silent("Chatter."))
    assert normal == ["Toll charged: 15 dollars."]
    assert terse == ["Toll, 15 dollars, carrier."]
