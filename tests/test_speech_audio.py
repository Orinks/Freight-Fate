"""Speech fallback and audio engine tests (headless-safe)."""

from dataclasses import dataclass, field

from asset_helpers import asset_exists

from freight_fate import speech as speech_module
from freight_fate.audio import ASSETS, AudioEngine
from freight_fate.speech import REFRESH_INTERVAL_S, Speech, pick_backend, pick_event_backend


@dataclass
class FakeFeatures:
    is_supported_at_runtime: bool = True
    supports_output: bool = True
    supports_speak: bool = True


@dataclass
class FakeBackend:
    name: str
    priority: int
    features: FakeFeatures = field(default_factory=FakeFeatures)


class FakeContext:
    """Mimics prism.Context: a static, priority-ordered backend registry."""

    def __init__(self, backends: list[FakeBackend], best: str) -> None:
        self._backends = {b.name: b for b in backends}
        self._order = sorted(backends, key=lambda b: b.priority, reverse=True)
        self._best = best

    @property
    def backends_count(self) -> int:
        return len(self._order)

    def id_of(self, index_or_name):
        if isinstance(index_or_name, int):
            return self._order[index_or_name].name
        if index_or_name in self._backends:
            return index_or_name
        raise ValueError(index_or_name)

    def priority_of(self, backend_id) -> int:
        return self._backends[backend_id].priority

    def acquire(self, backend_id):
        return self._backends[backend_id]

    def acquire_best(self):
        return self._backends[self._best]


def registry(nvda_running: bool) -> FakeContext:
    """The shape of Prism's real registry: NVDA outranks everything even
    when it is not running."""
    return FakeContext(
        [
            FakeBackend("NVDA", 103, FakeFeatures(is_supported_at_runtime=nvda_running)),
            FakeBackend("JAWS", 100, FakeFeatures(is_supported_at_runtime=False)),
            FakeBackend("ONE_CORE", 98),
            FakeBackend("SAPI", 97),
        ],
        best="NVDA",
    )


def test_running_screen_reader_wins():
    assert pick_backend(registry(nvda_running=True)).name == "NVDA"


def test_falls_past_not_running_screen_readers():
    # NVDA is the registry's "best" but is not running: the highest-priority
    # backend that actually works at runtime must win instead.
    assert pick_backend(registry(nvda_running=False)).name == "ONE_CORE"


def test_env_override_is_honored():
    assert pick_backend(registry(nvda_running=False), "SAPI").name == "SAPI"


def test_unusable_override_falls_back_to_automatic_choice():
    assert pick_backend(registry(nvda_running=False), "JAWS").name == "ONE_CORE"
    assert pick_backend(registry(nvda_running=False), "NoSuch").name == "ONE_CORE"


def test_no_usable_backend_returns_none():
    ctx = FakeContext(
        [FakeBackend("NVDA", 103, FakeFeatures(is_supported_at_runtime=False))],
        best="NVDA",
    )
    assert pick_backend(ctx) is None


def test_backend_without_speak_or_output_is_skipped():
    ctx = FakeContext(
        [
            FakeBackend(
                "BRAILLE_ONLY", 103, FakeFeatures(supports_output=False, supports_speak=False)
            ),
            FakeBackend("SAPI", 97),
        ],
        best="BRAILLE_ONLY",
    )
    assert pick_backend(ctx).name == "SAPI"


def test_cached_fallback_does_not_mask_a_screen_reader_that_started():
    # The acquire_best trap: it returns the highest-priority backend with a
    # live cached instance -- whatever voice the game is already holding --
    # not what is running. Here NVDA started mid-session while acquire_best
    # still offers the usable OneCore fallback; selection must ignore it and
    # find NVDA through live runtime checks.
    ctx = FakeContext(
        [FakeBackend("NVDA", 103), FakeBackend("ONE_CORE", 98)],
        best="ONE_CORE",  # what acquire_best returns: the held, cached voice
    )
    assert pick_backend(ctx).name == "NVDA"


def _narrator_registry(nvda_running: bool) -> FakeContext:
    """A Windows registry shape including the UIA backend, which claims
    runtime support whether or not Narrator is listening."""
    return FakeContext(
        [
            FakeBackend("NVDA", 103, FakeFeatures(is_supported_at_runtime=nvda_running)),
            FakeBackend("OneCore", 98),
            FakeBackend("SAPI", 97),
            FakeBackend("UIA", 97),
        ],
        best="NVDA",
    )


def test_uia_is_skipped_when_narrator_is_not_running(monkeypatch):
    # Without the gate the game would talk into UIA notifications nobody
    # reads aloud -- silence. The plain software voice must win instead.
    monkeypatch.setattr(speech_module, "_narrator_running", lambda: False)
    assert pick_backend(_narrator_registry(nvda_running=False)).name == "OneCore"


def test_narrator_route_stays_last_resort_even_when_narrator_runs(monkeypatch):
    # Prism's UIA backend cannot interrupt or stop (Narrator queues every
    # notification), so menu browsing through it is unusable. While any
    # software voice works, it must win over the Narrator route.
    monkeypatch.setattr(speech_module, "_narrator_running", lambda: True)
    assert pick_backend(_narrator_registry(nvda_running=False)).name == "OneCore"


def test_narrator_route_used_when_nothing_else_can_speak(monkeypatch):
    # Queued speech through Narrator still beats total silence.
    monkeypatch.setattr(speech_module, "_narrator_running", lambda: True)
    ctx = FakeContext(
        [
            FakeBackend("NVDA", 103, FakeFeatures(is_supported_at_runtime=False)),
            FakeBackend("OneCore", 98, FakeFeatures(is_supported_at_runtime=False)),
            FakeBackend("UIA", 97),
        ],
        best="NVDA",
    )
    assert pick_backend(ctx).name == "UIA"


def test_running_screen_reader_beats_narrator(monkeypatch):
    # NVDA and Narrator both up: the richer screen reader API wins.
    monkeypatch.setattr(speech_module, "_narrator_running", lambda: True)
    assert pick_backend(_narrator_registry(nvda_running=True)).name == "NVDA"


def test_event_channel_uses_sapi_alongside_the_screen_reader():
    ctx = registry(nvda_running=True)
    main = pick_backend(ctx)
    assert main.name == "NVDA"
    assert pick_event_backend(ctx, main).name == "SAPI"


def test_event_channel_skipped_when_main_voice_is_already_sapi():
    ctx = FakeContext(
        [
            FakeBackend("NVDA", 103, FakeFeatures(is_supported_at_runtime=False)),
            FakeBackend("SAPI", 97),
        ],
        best="NVDA",
    )
    main = pick_backend(ctx)
    assert main.name == "SAPI"
    assert pick_event_backend(ctx, main) is None


def test_event_channel_absent_when_sapi_is_unusable():
    ctx = FakeContext(
        [
            FakeBackend("NVDA", 103),
            FakeBackend("SAPI", 97, FakeFeatures(is_supported_at_runtime=False)),
        ],
        best="NVDA",
    )
    main = pick_backend(ctx)
    assert pick_event_backend(ctx, main) is None
    assert pick_event_backend(ctx, None) is None


@dataclass
class FakeParamFeatures:
    is_supported_at_runtime: bool = True
    supports_output: bool = True
    supports_speak: bool = True
    supports_stop: bool = False
    supports_set_rate: bool = False
    supports_set_pitch: bool = False
    supports_set_volume: bool = False
    supports_set_voice: bool = False
    supports_count_voices: bool = False
    supports_get_voice_name: bool = False


class RecordingBackend:
    """A backend that records the parameters Speech.configure pushes to it."""

    def __init__(self, name, voices, features, priority=0):
        self.name = name
        self.priority = priority
        self._voices = list(voices)
        self.features = features
        self.rate = None
        self.pitch = None
        self.volume = None
        self.voice = None
        self.spoken = []
        self.stop_calls = 0
        self.fail_output = False

    @property
    def voices_count(self):
        return len(self._voices)

    def get_voice_name(self, idx):
        return self._voices[idx]

    def output(self, text, interrupt=True):
        if self.fail_output:
            raise RuntimeError("speech backend failed")
        self.spoken.append((text, interrupt))

    def speak(self, text, interrupt=True):
        self.output(text, interrupt)

    def stop(self):
        self.stop_calls += 1


def _configurable_speech():
    """A Speech with an unsupported main voice and a fully adjustable event
    voice -- the common real layout (running NVDA plus a SAPI event voice)."""
    s = Speech()  # FREIGHT_FATE_NO_SPEECH (conftest) leaves it empty
    main = RecordingBackend("NVDA", [], FakeParamFeatures())
    event = RecordingBackend(
        "SAPI",
        ["David", "Zira"],
        FakeParamFeatures(
            supports_set_rate=True,
            supports_set_pitch=True,
            supports_set_volume=True,
            supports_set_voice=True,
            supports_count_voices=True,
            supports_get_voice_name=True,
        ),
    )
    s._backend = main
    s._event_backend = event
    return s, main, event


def test_configure_pushes_params_to_supporting_backends_only():
    s, main, event = _configurable_speech()
    s.configure(rate=0.8, pitch=0.3, volume=0.5, voice="Zira")
    assert (event.rate, event.pitch, event.volume, event.voice) == (0.8, 0.3, 0.5, 1)
    # the unsupported main voice is left untouched
    assert (main.rate, main.pitch, main.volume, main.voice) == (None, None, None, None)


def test_adjustment_preview_uses_configurable_voice():
    s, main, event = _configurable_speech()

    assert s.say_adjustment_preview("speech_rate", "Speech rate: 60 percent.")

    assert main.spoken == []
    assert event.spoken == [("Speech rate: 60 percent.", True)]


def test_adjustment_preview_falls_back_when_setting_is_not_configurable():
    s, _main, _event = _configurable_speech()

    assert not s.say_adjustment_preview("speech_verbosity", "Speech verbosity: normal.")


def test_configure_preserves_onecore_default_pitch_at_midpoint():
    s = Speech()
    event = RecordingBackend(
        "OneCore",
        [],
        FakeParamFeatures(supports_set_rate=True, supports_set_pitch=True),
    )
    s._event_backend = event
    s.configure(rate=0.5, pitch=0.5)
    assert event.rate == 0.5
    assert event.pitch is None
    s.configure(pitch=0.7)
    assert event.pitch == 0.7


def test_supports_and_voice_names_reflect_backend_features():
    s, _main, _event = _configurable_speech()
    assert s.supports_rate and s.supports_pitch and s.supports_volume
    assert s.voice_names() == ["David", "Zira"]


def test_configure_skips_unknown_voice_name():
    s, _main, event = _configurable_speech()
    s.configure(voice="Nonexistent")
    assert event.voice is None


def test_no_configurable_backend_reports_no_support():
    s = Speech()
    s._backend = RecordingBackend("NVDA", [], FakeParamFeatures())
    s._event_backend = None
    assert not s.supports_rate
    assert not s.supports_pitch
    assert not s.supports_volume
    assert s.voice_names() == []


def test_interrupting_main_speech_uses_backend_interrupt_without_extra_stop():
    s = Speech()
    backend = RecordingBackend("SAPI", [], FakeParamFeatures(supports_stop=True))
    s._backend = backend

    s.say("Fresh menu item.", interrupt=True)

    assert backend.stop_calls == 0
    assert backend.spoken == [("Fresh menu item.", True)]


def test_main_speech_flush_does_not_stop_event_voice():
    s = Speech()
    main = RecordingBackend("NVDA", [], FakeParamFeatures(supports_stop=True))
    event = RecordingBackend("SAPI", [], FakeParamFeatures(supports_stop=True))
    s._backend = main
    s._event_backend = event

    s.say("Fresh menu item.", interrupt=True)

    assert main.stop_calls == 0
    assert event.stop_calls == 0
    assert main.spoken == [("Fresh menu item.", True)]


def test_urgent_event_speech_uses_backend_interrupt_without_extra_stop():
    s = Speech()
    main = RecordingBackend("NVDA", [], FakeParamFeatures(supports_stop=True))
    event = RecordingBackend("SAPI", [], FakeParamFeatures(supports_stop=True))
    s._backend = main
    s._event_backend = event

    s.say_event("Brake now.", interrupt=True)

    assert main.stop_calls == 0
    assert event.stop_calls == 0
    assert event.spoken == [("Brake now.", True)]


def test_urgent_event_without_event_voice_flushes_main_before_fallback():
    s = Speech()
    main = RecordingBackend("NVDA", [], FakeParamFeatures(supports_stop=True))
    s._backend = main
    s._event_backend = None

    s.say_event("Brake now.", interrupt=True)

    assert main.stop_calls == 1
    assert main.spoken == [("Brake now.", False)]


def test_failed_urgent_event_voice_falls_back_without_main_interrupt():
    s = Speech()
    main = RecordingBackend("NVDA", [], FakeParamFeatures(supports_stop=True))
    event = RecordingBackend("SAPI", [], FakeParamFeatures(supports_stop=True))
    event.fail_output = True
    s._backend = main
    s._event_backend = event

    s.say_event("Brake now.", interrupt=True)

    assert event.stop_calls == 0
    assert main.stop_calls == 1
    assert main.spoken == [("Brake now.", False)]


def test_nonurgent_event_speech_can_queue_on_event_voice():
    s = Speech()
    event = RecordingBackend("SAPI", [], FakeParamFeatures(supports_stop=True))
    s._event_backend = event

    s.say_event("Weather changing.", interrupt=False)

    assert event.stop_calls == 0
    assert event.spoken == [("Weather changing.", False)]
    s.configure(rate=0.9, voice="David")  # must not raise


def _multi_voice_ctx():
    """A registry shaped like a real Windows box with NVDA running: the screen
    reader plus two controllable software voices."""
    params = dict(
        supports_set_rate=True,
        supports_set_pitch=True,
        supports_set_volume=True,
        supports_set_voice=True,
        supports_count_voices=True,
        supports_get_voice_name=True,
    )
    return FakeContext(
        [
            FakeBackend("NVDA", 103, FakeParamFeatures()),
            FakeBackend("OneCore", 98, FakeParamFeatures(**params)),
            FakeBackend("SAPI", 97, FakeParamFeatures(**params)),
        ],
        best="NVDA",
    )


def test_event_backend_options_lists_software_voices_by_priority():
    s = Speech()
    s._ctx = _multi_voice_ctx()
    s._backend = s._ctx.acquire("NVDA")  # the main voice is excluded
    assert s.event_backend_options() == ["OneCore", "SAPI"]


def test_select_event_backend_switches_and_clears():
    s = Speech()
    s._ctx = _multi_voice_ctx()
    s._backend = s._ctx.acquire("NVDA")
    s.select_event_backend("OneCore")
    assert s.event_backend_name == "OneCore"
    s.select_event_backend(None)  # back to the main voice
    assert s.event_backend_name == "none"
    # Asking for the main voice by name is not a real separate option, so the
    # preference falls back to the best available one (None is how you pick the
    # main voice for events).
    s.select_event_backend("NVDA")
    assert s.event_backend_name == "OneCore"


def test_event_backend_falls_back_to_platform_voice():
    # A macOS-shaped registry: VoiceOver running, AVSpeech as the software voice,
    # no SAPI. A Windows save's "SAPI" preference must still land on a real voice.
    params = dict(
        supports_set_rate=True,
        supports_set_pitch=True,
        supports_set_volume=True,
        supports_set_voice=True,
        supports_count_voices=True,
        supports_get_voice_name=True,
    )
    ctx = FakeContext(
        [
            FakeBackend("VoiceOver", 103, FakeParamFeatures()),
            FakeBackend("AVSpeech", 98, FakeParamFeatures(**params)),
        ],
        best="VoiceOver",
    )
    s = Speech()
    s._ctx = ctx
    s._backend = ctx.acquire("VoiceOver")
    s.select_event_backend("SAPI")  # not on this machine
    assert s.event_backend_name == "AVSpeech"  # best available wins


def test_event_backend_none_when_no_separate_voice_exists():
    # Only a screen reader is usable: there is nothing to separate onto.
    ctx = FakeContext([FakeBackend("VoiceOver", 103, FakeParamFeatures())], best="VoiceOver")
    s = Speech()
    s._ctx = ctx
    s._backend = ctx.acquire("VoiceOver")
    s.select_event_backend("SAPI")
    assert s.event_backend_name == "none"


# -- runtime screen reader switching (NVDA -> Narrator -> NVDA) ---------------


def _live_registry(nvda_running: bool):
    """A speakable registry for runtime-switch tests: NVDA (a screen reader
    that may or may not be running) plus SAPI (always-on software voice)."""
    nvda = RecordingBackend(
        "NVDA",
        [],
        FakeParamFeatures(is_supported_at_runtime=nvda_running, supports_stop=True),
        priority=103,
    )
    sapi = RecordingBackend(
        "SAPI",
        ["David", "Zira"],
        FakeParamFeatures(
            supports_stop=True,
            supports_set_rate=True,
            supports_set_pitch=True,
            supports_set_volume=True,
            supports_set_voice=True,
            supports_count_voices=True,
            supports_get_voice_name=True,
        ),
        priority=97,
    )
    ctx = FakeContext([nvda, sapi], best="NVDA")
    s = Speech()  # FREIGHT_FATE_NO_SPEECH (conftest) leaves it empty
    s._ctx = ctx
    return s, nvda, sapi


def test_say_failure_switches_to_a_live_voice_and_retries():
    # NVDA quits mid-game: the utterance that fails must come out of the
    # fallback voice instead of muting the game forever.
    s, nvda, sapi = _live_registry(nvda_running=False)
    s._backend = nvda
    nvda.fail_output = True
    s.say("Turn left ahead.")
    assert s.backend_name == "SAPI"
    assert sapi.spoken == [("Turn left ahead.", True)]


def test_say_failure_with_no_live_voice_recovers_when_one_returns():
    s, nvda, sapi = _live_registry(nvda_running=False)
    sapi.features.is_supported_at_runtime = False  # nothing else to speak with
    s._backend = nvda
    nvda.fail_output = True
    s.say("hello")
    assert not s.available
    nvda.fail_output = False
    nvda.features.is_supported_at_runtime = True  # the screen reader is back
    s.poll(REFRESH_INTERVAL_S)
    assert s.backend_name == "NVDA"
    assert nvda.spoken == [("Speech is now using NVDA.", False)]


def test_poll_returns_to_the_screen_reader_when_it_comes_back():
    # The game fell back to SAPI while NVDA was closed; when NVDA reappears
    # the periodic check must switch back and say so through the new voice.
    s, nvda, sapi = _live_registry(nvda_running=False)
    s._backend = sapi
    s.poll(REFRESH_INTERVAL_S)
    assert s.backend_name == "SAPI"  # nothing better yet: stays put
    nvda.features.is_supported_at_runtime = True
    s.poll(REFRESH_INTERVAL_S)
    assert s.backend_name == "NVDA"
    assert nvda.spoken == [("Speech is now using NVDA.", False)]


def test_switch_reselects_event_voice_and_reapplies_settings():
    # While NVDA was closed the main voice fell back to SAPI, so there was no
    # separate event voice. Switching back to NVDA must revive the SAPI event
    # voice and push the player's saved speech settings onto it.
    s, nvda, sapi = _live_registry(nvda_running=False)
    s._backend = sapi
    s.select_event_backend("SAPI")  # SAPI is the main voice: nothing separate
    assert s.event_backend_name == "none"
    s.configure(rate=0.8, voice="Zira")
    nvda.features.is_supported_at_runtime = True
    s.poll(REFRESH_INTERVAL_S)
    assert s.backend_name == "NVDA"
    assert s.event_backend_name == "SAPI"
    assert sapi.rate == 0.8
    assert sapi.voice == 1


def test_event_voice_revives_after_a_failure():
    s, nvda, sapi = _live_registry(nvda_running=True)
    s._backend = nvda
    s.select_event_backend("SAPI")
    assert s.event_backend_name == "SAPI"
    sapi.fail_output = True
    s.say_event("Brake now.")  # falls back to the main voice...
    assert s.event_backend_name == "none"
    assert nvda.spoken == [("Brake now.", False)]
    sapi.fail_output = False
    s.poll(REFRESH_INTERVAL_S)  # ...and the health check brings it back
    assert s.event_backend_name == "SAPI"


def test_request_refresh_makes_the_next_poll_immediate():
    s, nvda, sapi = _live_registry(nvda_running=False)
    s._backend = sapi
    nvda.features.is_supported_at_runtime = True
    s.poll(0.016)  # a normal frame: far too soon for the periodic check
    assert s.backend_name == "SAPI"
    s.request_refresh()  # the game window regained focus
    s.poll(0.016)
    assert s.backend_name == "NVDA"


def test_speech_appears_for_a_screen_reader_started_after_the_game():
    s, nvda, sapi = _live_registry(nvda_running=False)
    sapi.features.is_supported_at_runtime = False
    s.poll(REFRESH_INTERVAL_S)
    assert not s.available  # still nothing on the machine can speak
    nvda.features.is_supported_at_runtime = True
    s.poll(REFRESH_INTERVAL_S)
    assert s.backend_name == "NVDA"


def test_healthy_backend_is_kept_without_announcements():
    s, nvda, _sapi = _live_registry(nvda_running=True)
    s._backend = nvda
    for _ in range(3):
        s.poll(REFRESH_INTERVAL_S)
    assert s.backend_name == "NVDA"
    assert nvda.spoken == []  # no spurious "speech is now using" chatter


def test_poll_is_safe_without_prism():
    s = Speech()  # headless: no context at all
    s.poll(REFRESH_INTERVAL_S)  # must not raise
    s.request_refresh()
    assert not s.refresh()


class _RecordingSpeech:
    """Captures which channel a GameContext routes event speech to."""

    def __init__(self) -> None:
        self.say_calls: list[tuple[str, bool]] = []
        self.event_calls: list[tuple[str, bool]] = []
        self.stop_calls = 0

    def say(self, text: str, interrupt: bool = True) -> None:
        self.say_calls.append((text, interrupt))

    def say_event(self, text: str, interrupt: bool = True) -> None:
        self.event_calls.append((text, interrupt))

    def stop(self) -> None:
        self.stop_calls += 1

    def stop_main(self) -> None:
        self.stop()

    def stop_event(self) -> None:
        self.stop()


def test_events_via_screen_reader_never_interrupt_even_when_critical():
    from freight_fate.app import App

    app = App()
    try:
        rec = _RecordingSpeech()
        app.ctx.speech = rec
        app.ctx.settings.sapi_events = False  # event voice = screen reader
        app.ctx.say_event("Brake now!", interrupt=True)  # a critical event
        # Not on a separate voice, so the stale queue is flushed first and the
        # event is then spoken as a fresh screen-reader utterance.
        assert rec.stop_calls == 1
        assert rec.event_calls == []
        assert rec.say_calls == [("Brake now!", False)]
    finally:
        app.shutdown()


def test_events_on_separate_sapi_voice_keep_requested_interrupt():
    from freight_fate.app import App

    app = App()
    try:
        rec = _RecordingSpeech()
        app.ctx.speech = rec
        app.ctx.settings.sapi_events = True  # dedicated SAPI event voice
        app.ctx.say_event("Brake now!", interrupt=True)
        app.ctx.say_event("Weather changing.", interrupt=False)
        assert rec.say_calls == []
        assert rec.event_calls == [("Brake now!", True), ("Weather changing.", False)]
    finally:
        app.shutdown()


def test_state_transitions_do_not_flush_menu_speech_before_enter():
    from freight_fate.app import App
    from freight_fate.states.base import State

    class SayingState(State):
        def enter(self):
            self.ctx.say("New screen.")

    app = App()
    try:
        rec = _RecordingSpeech()
        app.ctx.speech = rec
        app.push_state(SayingState(app.ctx))
        assert rec.stop_calls == 0
        assert rec.say_calls == [("New screen.", True)]
    finally:
        app.shutdown()


def test_speech_disabled_by_env_is_silent_and_safe():
    s = Speech()
    assert not s.available
    assert s.backend_name == "none"
    assert s.event_backend_name == "none"
    s.say("hello")  # must not raise
    s.say("")  # empty text is fine
    s.say_event("hazard")  # falls back to the (absent) main voice safely
    s.stop()
    s.shutdown()
    s.shutdown()  # idempotent


def test_audio_engine_headless_noops():
    audio = AudioEngine()
    # with the dummy SDL driver the mixer may or may not init; either way
    # every call must be safe
    audio.play("ui/menu_select")
    audio.play("nonexistent/sound")
    audio.engine_start()
    audio.set_engine_rpm(1500, 0.5)
    audio.set_road_noise(20.0)
    audio.set_weather("weather/rain_light", 0.8)
    audio.set_wind(0.5)
    audio.play_music("menu_theme")
    audio.play_music("not_a_track")
    audio.set_volumes(master=0.5, sfx=0.5, music=0.5)
    audio.stop_world()
    audio.stop_music()
    audio.shutdown()


def test_all_referenced_assets_exist():
    """Every sound key used in the codebase must exist on disk.

    Keys named inside ``play_bank(...)`` (the bank base) or ``has_asset(...)``
    are exempt: they live only in the gitignored licensed overlay, and every
    such call site degrades on a clean clone -- ``play_bank`` to its fallback
    key (which this test still requires to exist) and ``has_asset`` guards to
    the committed cue or the old silence.
    """
    import re
    from pathlib import Path

    src = Path(__file__).parents[1] / "src" / "freight_fate"
    pattern = re.compile(
        r"""["']((?:ui|engine|vehicle|weather|ambient|driver|events|facility|poi)/[a-z_]+)["']"""
    )
    optional_pattern = re.compile(
        r"""(?:play_bank|has_asset)\(\s*["']((?:ui|engine|vehicle|weather|ambient|driver|events|facility|poi)/[a-z_]+)["']"""
    )
    keys: set[str] = set()
    optional: set[str] = set()
    for py in src.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        keys |= set(pattern.findall(text))
        optional |= set(optional_pattern.findall(text))
    assert keys, "expected to find sound keys in source"
    missing = [k for k in keys - optional if not asset_exists(ASSETS, k)]
    assert not missing, f"missing sound files: {missing}"


def test_music_tracks_exist():
    from freight_fate.music import ALL_MUSIC_TRACKS

    for track in (track.key for track in ALL_MUSIC_TRACKS):
        assert asset_exists(ASSETS / "music", track), track
