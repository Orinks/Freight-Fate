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
