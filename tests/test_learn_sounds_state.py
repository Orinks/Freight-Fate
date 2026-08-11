"""Learn game sounds: the demo sequencer and the screen that drives it."""

from freight_fate.sound_catalog import Cue, SoundEntry


class FakeAudio:
    """Records what a demo asked for, in order."""

    def __init__(self) -> None:
        self.played: list[tuple[str, float, float]] = []
        self.holds: list[tuple[str, float]] = []
        self.pans: list[tuple[int, float]] = []
        self.released = 0

    def play(self, key, volume=1.0, pan=0.0):
        self.played.append((key, volume, pan))

    def hold_alert(self, key, volume=1.0, fade_ms=60):
        self.holds.append((key, volume))

    def set_loop_pan(self, channel, pan):
        self.pans.append((channel, pan))

    def release_alert(self, fade_ms=120):
        self.released += 1

    def has_asset(self, key):
        return not key.startswith("missing/")


def test_a_one_shot_entry_plays_once_with_its_volume_and_pan():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("a/one", volume=0.5, pan=-0.6),), "why"))
    assert audio.played == [("a/one", 0.5, -0.6)]
    demo.update(0.1)
    assert audio.played == [("a/one", 0.5, -0.6)], "a one-shot must not repeat"


def test_a_delayed_cue_waits_for_its_moment():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(
        SoundEntry(
            "X",
            (Cue("a/left", pan=-0.8), Cue("a/right", pan=0.8, delay_s=1.0)),
            "why",
        )
    )
    assert [k for k, _v, _p in audio.played] == ["a/left"]
    demo.update(0.5)
    assert [k for k, _v, _p in audio.played] == ["a/left"]
    demo.update(0.6)
    assert [k for k, _v, _p in audio.played] == ["a/left", "a/right"]


def test_a_held_cue_is_reasserted_every_frame_then_released():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("a/loop", volume=0.7, pan=0.3, hold_s=1.0),), "why"))
    assert audio.holds == [("a/loop", 0.7)]
    assert audio.pans and audio.pans[-1][1] == 0.3
    demo.update(0.5)
    assert len(audio.holds) > 1, "a held cue must be re-asserted while it runs"
    assert audio.released == 0
    demo.update(0.6)
    assert audio.released == 1
    assert not demo.running


def test_starting_a_new_demo_cancels_the_running_one():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("a/loop", hold_s=5.0),), "why"))
    demo.start(SoundEntry("Y", (Cue("b/one"),), "why"))
    assert audio.released == 1
    demo.update(0.1)
    assert audio.released == 1, "the second demo has nothing to release"


def test_stop_releases_a_held_cue_and_ends_the_demo():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("a/loop", hold_s=5.0),), "why"))
    demo.stop()
    assert audio.released == 1
    assert not demo.running


def test_a_cue_falls_back_when_its_key_is_missing():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("missing/thing", fallback="a/real"),), "why"))
    assert [k for k, _v, _p in audio.played] == ["a/real"]


def test_a_delayed_held_cue_holds_for_its_full_duration_even_across_a_big_step():
    """The road lean is exactly this shape: Cue(..., delay_s=2.4, hold_s=2.0).

    A hold that starts mid-frame must not lose that frame from its duration --
    a coarse ``dt`` (a hitching frame, a screen resuming, a stepped test) must
    never truncate or skip the hold.
    """
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("a/loop", hold_s=2.0, delay_s=1.0),), "why"))
    assert audio.holds == []
    demo.update(3.0)  # spans the 1.0s delay and lands inside the 2.0s hold
    assert audio.holds, "the delayed hold must have fired"
    assert audio.released == 0, "must not be released in the same update that started it"
    assert demo.running
    demo.update(3.0)  # now past elapsed 5.0 (1.0 delay + 2.0 hold)
    assert audio.released == 1
    assert not demo.running


def test_a_cue_with_no_playable_key_plays_and_holds_nothing():
    """Missing key, missing fallback: play nothing, hold nothing, do not raise."""
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("missing/thing", fallback="missing/other"),), "why"))
    assert audio.played == []
    assert audio.holds == []
    assert audio.released == 0
    demo.update(0.1)
    assert audio.played == []
    assert audio.holds == []
    assert audio.released == 0
    assert not demo.running


def test_a_one_shot_is_not_layered_over_a_copy_of_itself():
    """Enter twice on the yawn used to play two yawns a moment apart.

    A one-shot handed to the mixer comes back with no handle, so the demo
    cannot cut the first copy short; the only way not to double it is not to
    start it. ``driver/yawn`` is the longest one-shot in the catalog at 3.8
    seconds, which is long enough that a player mashing Enter really did hear
    a sound the road never makes.
    """
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    yawn = SoundEntry("Yawn", (Cue("driver/yawn", volume=0.9),), "why")

    demo.start(yawn)
    demo.update(0.2)
    demo.start(yawn)  # Enter again, well inside the clip
    assert [k for k, _v, _p in audio.played] == ["driver/yawn"], "the yawn must not double"

    demo.update(4.0)  # past the end of the clip
    demo.start(yawn)
    assert len(audio.played) == 2, "once it has finished, Enter plays it again"


def test_a_different_entry_still_interrupts_a_sounding_one():
    """The guard is per entry: arrowing on and playing the next cue must work."""
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("Yawn", (Cue("driver/yawn"),), "why"))
    demo.update(0.2)
    demo.start(SoundEntry("Other", (Cue("events/spike_strip"),), "why"))
    assert [k for k, _v, _p in audio.played] == ["driver/yawn", "events/spike_strip"]


def test_a_cue_with_nothing_to_play_reports_itself_unplayable():
    from freight_fate.sound_demo import SoundDemo

    demo = SoundDemo(FakeAudio())
    assert demo.can_play(SoundEntry("X", (Cue("a/real"),), "why"))
    assert demo.can_play(SoundEntry("X", (Cue("missing/thing", fallback="a/real"),), "why"))
    assert not demo.can_play(SoundEntry("X", (Cue("missing/thing"),), "why"))


def _app():
    from freight_fate.app import App

    return App()


def test_the_category_screen_lists_every_catalog_category():
    from freight_fate.sound_catalog import CATALOG
    from freight_fate.states.learn_sounds import LearnSoundsState

    app = _app()
    try:
        state = LearnSoundsState(app.ctx)
        labels = [item.text for item in state.build_items()]
        assert labels == [c.name for c in CATALOG]
    finally:
        app.shutdown()


def test_arrowing_speaks_the_name_and_plays_no_cue(monkeypatch):
    from speech_capture import speech_stub

    from freight_fate.sound_catalog import CATALOG
    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        spoken: list[str] = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        played: list[str] = []
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **_kw: played.append(key))

        state = LearnSoundCategoryState(app.ctx, CATALOG[0])
        state.enter()
        played.clear()
        spoken.clear()
        state.move(1)

        assert any(state.items[state.index].text in line for line in spoken)
        # Only the menu's own movement click, never a catalogued cue.
        assert played == ["ui/menu_move"]
    finally:
        app.shutdown()


def test_enter_plays_the_entrys_cue_with_its_volume_and_pan(monkeypatch):
    from speech_capture import speech_stub

    from freight_fate.sound_catalog import CATALOG
    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        calls: list[tuple[str, float, float]] = []
        monkeypatch.setattr(
            app.ctx.audio,
            "play",
            lambda key, volume=1.0, pan=0.0: calls.append((key, volume, pan)),
        )
        monkeypatch.setattr(app.ctx.audio, "hold_alert", lambda key, **_kw: None)
        monkeypatch.setattr(app.ctx.audio, "set_loop_pan", lambda *_a, **_k: None)

        category = CATALOG[0]
        state = LearnSoundCategoryState(app.ctx, category)
        state.enter()
        # Land on an entry whose first cue is a one-shot so the assert is direct.
        index = next(i for i, e in enumerate(category.entries) if e.plays[0].hold_s == 0.0)
        state.index = index
        calls.clear()
        state.activate()

        cue = category.entries[index].plays[0]
        assert (cue.key, cue.volume, cue.pan) in calls
    finally:
        app.shutdown()


def test_f1_speaks_the_meaning_and_the_when_note():
    from freight_fate.sound_catalog import CATALOG
    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        category = next(c for c in CATALOG if any(e.when for e in c.entries))
        entry_index = next(i for i, e in enumerate(category.entries) if e.when)
        state = LearnSoundCategoryState(app.ctx, category)
        state.items = state.build_items()
        state.index = entry_index

        help_text = state.current_help()
        entry = category.entries[entry_index]
        assert entry.meaning in help_text
        assert entry.when in help_text
    finally:
        app.shutdown()


def test_leaving_the_screen_releases_a_held_cue(monkeypatch):
    from speech_capture import speech_stub

    from freight_fate.sound_catalog import Cue, SoundCategory, SoundEntry
    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx.audio, "play", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "hold_alert", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "set_loop_pan", lambda *_a, **_k: None)
        releases: list[int] = []
        monkeypatch.setattr(app.ctx.audio, "release_alert", lambda **_kw: releases.append(1))

        held = SoundCategory(
            "Held", (SoundEntry("Held cue", (Cue("vehicle/bar_solid", hold_s=5.0),), "why"),)
        )
        state = LearnSoundCategoryState(app.ctx, held)
        state.enter()
        state.activate()
        state.exit()

        assert releases, "a held cue must not survive the screen closing"
    finally:
        app.shutdown()


def _held_and_other_category():
    from freight_fate.sound_catalog import Cue, SoundCategory, SoundEntry

    return SoundCategory(
        "Two",
        (
            SoundEntry("Held cue", (Cue("vehicle/bar_solid", hold_s=5.0),), "why"),
            SoundEntry("Other cue", (Cue("vehicle/lane_centered"),), "why"),
        ),
    )


def test_jump_stops_a_running_held_demo(monkeypatch):
    """Home and End go through ``jump``, a route separate from ``move``.

    Both funnel through ``speak_current``, which is where the demo actually
    gets stopped; this pins that Home/End does not bypass it.
    """
    from speech_capture import speech_stub

    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx.audio, "play", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "hold_alert", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "set_loop_pan", lambda *_a, **_k: None)
        releases: list[int] = []
        monkeypatch.setattr(app.ctx.audio, "release_alert", lambda **_kw: releases.append(1))

        state = LearnSoundCategoryState(app.ctx, _held_and_other_category())
        state.enter()
        state.activate()  # starts the held demo on "Held cue"
        assert state.demo.running

        state.jump(1)  # the Home/End route (bound to K_HOME / K_END in base.py)

        assert releases, "Home/End must stop a running held demo"
        assert not state.demo.running
    finally:
        app.shutdown()


def test_first_letter_jump_stops_a_running_held_demo(monkeypatch):
    """Typing a letter jumps by name, a third route independent of ``move``.

    Same rule, same reason: it must not leave a held cue ringing under the
    entry it just landed on.
    """
    from speech_capture import speech_stub

    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx.audio, "play", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "hold_alert", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "set_loop_pan", lambda *_a, **_k: None)
        releases: list[int] = []
        monkeypatch.setattr(app.ctx.audio, "release_alert", lambda **_kw: releases.append(1))

        state = LearnSoundCategoryState(app.ctx, _held_and_other_category())
        state.enter()
        state.activate()  # starts the held demo on "Held cue"
        assert state.demo.running

        state._first_letter_jump("o")  # jumps to "Other cue"

        assert releases, "a first-letter jump must stop a running held demo"
        assert not state.demo.running
    finally:
        app.shutdown()


def test_arrow_move_stops_a_running_held_demo(monkeypatch):
    """The ordinary arrow route, checked the same way as the other two.

    Asserting on ``release_alert`` rather than only ``demo.running`` means
    this fails if the tone is left sounding, not just if the bookkeeping
    thinks it stopped.
    """
    from speech_capture import speech_stub

    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx.audio, "play", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "hold_alert", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "set_loop_pan", lambda *_a, **_k: None)
        releases: list[int] = []
        monkeypatch.setattr(app.ctx.audio, "release_alert", lambda **_kw: releases.append(1))

        state = LearnSoundCategoryState(app.ctx, _held_and_other_category())
        state.enter()
        state.activate()  # starts the held demo on "Held cue"
        assert state.demo.running

        state.move(1)

        assert releases, "an ordinary arrow move must stop a running held demo"
        assert not state.demo.running
    finally:
        app.shutdown()


def test_reentering_the_screen_stops_a_running_held_demo(monkeypatch):
    """Coming back from a screen pushed over this one is its own route.

    ``pop_state`` calls ``enter`` again on whatever it uncovered, which
    re-announces the title -- while a demo whose clock froze under the
    covering state would pick its hold straight back up underneath it.
    """
    from speech_capture import speech_stub

    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx.audio, "play", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "hold_alert", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "set_loop_pan", lambda *_a, **_k: None)
        releases: list[int] = []
        monkeypatch.setattr(app.ctx.audio, "release_alert", lambda **_kw: releases.append(1))

        state = LearnSoundCategoryState(app.ctx, _held_and_other_category())
        state.enter()
        state.activate()
        assert state.demo.running

        state.enter()  # what pop_state(reentry=True) does to the state beneath

        assert releases, "re-entry must stop a running held demo"
        assert not state.demo.running
    finally:
        app.shutdown()


def test_the_enforcement_marker_plays_on_a_cold_open(monkeypatch):
    """Opening the screen with no drive in progress must still play the marker.

    The enforcement signature is synthesized, and the only other thing that
    publishes it is a drive starting. Opened from the main menu it resolved to
    nothing, so the entry that teaches the one cue the enforcement contract
    rests on would have demonstrated silence.
    """
    from speech_capture import speech_stub

    from freight_fate import audio as audio_module
    from freight_fate.sound_catalog import CATALOG
    from freight_fate.states import driving_siren
    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        # Put the process back where a fresh launch is: nothing has driven yet,
        # so the synthesized cue has not been published. monkeypatch restores
        # both on the way out.
        monkeypatch.delitem(audio_module._GENERATED, driving_siren.SIGNATURE_KEY, raising=False)
        monkeypatch.setattr(driving_siren, "_registered", False)
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        played: list[str] = []
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **_kw: played.append(key))

        enforcement = next(c for c in CATALOG if c.name == "Enforcement")
        state = LearnSoundCategoryState(app.ctx, enforcement)
        state.enter()
        state.index = next(
            i for i, e in enumerate(enforcement.entries) if e.name == "Enforcement marker"
        )
        played.clear()
        state.activate()

        assert played == [driving_siren.SIGNATURE_KEY]
    finally:
        app.shutdown()


def test_an_unplayable_cue_is_spoken_about_rather_than_silent(monkeypatch):
    """Silence would teach the player that a real cue makes no sound."""
    from speech_capture import speech_stub

    from freight_fate.sound_catalog import Cue, SoundCategory, SoundEntry
    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        spoken: list[str] = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        played: list[str] = []
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **_kw: played.append(key))

        gone = SoundCategory(
            "Gone",
            (SoundEntry("Missing cue", (Cue("nothing/at_all"),), "why"),),
        )
        state = LearnSoundCategoryState(app.ctx, gone)
        state.enter()
        played.clear()
        spoken.clear()
        state.activate()

        assert played == [], "nothing resolved, so nothing should have been played"
        assert any("Missing cue" in line and "not available" in line for line in spoken)
        assert not state.demo.running
    finally:
        app.shutdown()


def test_the_category_help_does_not_promise_a_stop_it_cannot_make():
    """Escape releases a held cue; a one-shot already playing finishes."""
    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    help_text = LearnSoundCategoryState.intro_help
    assert "finishes on its own" in help_text
    assert "stops the sound and goes back" not in help_text


def test_the_main_menu_offers_learn_game_sounds():
    from freight_fate.states.main_menu import MainMenuState

    app = _app()
    try:
        labels = [item.text for item in MainMenuState(app.ctx).build_items()]
        assert "Learn game sounds" in labels
        # It sits with the other learning material, after How to play.
        assert labels.index("Learn game sounds") == labels.index("How to play") + 1
    finally:
        app.shutdown()


def test_the_pause_menu_offers_learn_game_sounds():
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState, PauseMenuState

    app = _app()
    try:
        app.ctx.profile = Profile(name="Sounds", current_city="Buffalo")
        route = app.ctx.world.supported_route("Buffalo", "Rochester")
        job = Job(
            CARGO_CATALOG["general"],
            12.0,
            "Buffalo",
            "company yard",
            "Rochester",
            route.miles,
            1000.0,
            12.0,
            destination_location="Rochester freight market",
        )
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        labels = [item.text for item in PauseMenuState(app.ctx, driving).build_items()]
        assert "Learn game sounds" in labels
        assert labels.index("Learn game sounds") == labels.index("Controls and help") + 1
    finally:
        app.shutdown()


def test_both_entry_points_push_the_same_screen(monkeypatch):
    from freight_fate.states.learn_sounds import LearnSoundsState
    from freight_fate.states.main_menu import MainMenuState

    app = _app()
    try:
        pushed: list[object] = []
        monkeypatch.setattr(app.ctx, "push_state", lambda state, **_kw: pushed.append(state))
        menu = MainMenuState(app.ctx)
        item = next(i for i in menu.build_items() if i.text == "Learn game sounds")
        item.action()
        assert isinstance(pushed[0], LearnSoundsState)
    finally:
        app.shutdown()
