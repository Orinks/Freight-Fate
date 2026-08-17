"""The opt-in lane guide tone (owner call, 2026-08-17).

The community ruled against steering tones on the audiogames.net thread
(JaceK, 2026-07-17): a continuous tone overwhelms the soundscape and hurts
players with sensory or hearing conditions. That ruling stands -- what is
added here is a CHOICE, off unless a driver turns it on, because the bed it
replaces genuinely fails some of them.
"""

import math
import wave
from io import BytesIO

import pytest

from freight_fate.lane_guide_tone import (
    LANE_GUIDE_TONE_KEY,
    TONE_CYCLES,
    TONE_RMS_DBFS,
    lane_guide_tone_wav,
)
from freight_fate.settings import Settings


def _samples():
    with wave.open(BytesIO(lane_guide_tone_wav()), "rb") as w:
        assert w.getnchannels() == 2
        raw = w.readframes(w.getnframes())
        rate = w.getframerate()
    import array

    a = array.array("h")
    a.frombytes(raw)
    return [float(x) for x in a[0::2]], rate


def test_the_loop_wraps_with_no_step():
    """Seamless by construction, not by trimming.

    Darren's recording could not be cut into a loop -- no trailing silence
    and mp3 noise at the seam that no amount of crossfading removed (three
    attempts, best was -35 dBFS, plainly audible on a cue that wraps four
    times a second). Choosing the sample count so a whole number of cycles
    fits exactly makes the wrap error zero instead of small.
    """
    mono, rate = _samples()
    n = len(mono)
    assert abs(n / rate * 1000 - 219.5) < 1.0, "loop length drifted"

    # The sample that would follow the last one is the first one.
    period = n / TONE_CYCLES
    nxt = math.sin(2.0 * math.pi * TONE_CYCLES * n / n)
    assert abs(nxt - math.sin(0.0)) < 1e-9
    assert abs(n / period - TONE_CYCLES) < 1e-9, "not a whole number of cycles"

    # And the real samples agree: end and start sit within a quantisation step
    # of each other, which is what a listener would hear as no click.
    step = abs(mono[0] - mono[-1])
    peak = max(abs(x) for x in mono)
    assert step < peak * 0.05, f"seam step {step} against peak {peak}"


def test_the_level_is_darrens_number():
    """-16 dBFS RMS, which is 2.6 dB ABOVE the engine loops' -18.7.

    That figure is the whole reason this exists: vehicle/road sits at -33.3
    and already runs at full gain by highway speed, so the bed is 15 dB
    under the engine and carries no pan at all.
    """
    mono, _ = _samples()
    rms = math.sqrt(sum(x * x for x in mono) / len(mono))
    assert abs(20 * math.log10(rms / 32768) - TONE_RMS_DBFS) < 0.2


def test_the_tone_is_centred_so_the_guide_carries_the_side():
    with wave.open(BytesIO(lane_guide_tone_wav()), "rb") as w:
        import array

        a = array.array("h")
        a.frombytes(w.readframes(w.getnframes()))
    assert list(a[0::2]) == list(a[1::2]), "a pre-panned asset would fight the guide"


def test_the_default_is_the_road_bed_not_the_tone():
    """The ruling's line: a tone is chosen, never given."""
    assert Settings().lane_guide_tone is False


@pytest.mark.parametrize("junk", ["yes", 1, None, "true"])
def test_an_unreadable_setting_falls_to_the_bed(junk):
    """A broken settings file must not be able to choose a tone for someone
    the tone would hurt."""
    s = Settings.from_dict({"lane_guide_tone": junk})
    assert s.lane_guide_tone is False


def test_the_tone_is_learnable_like_every_other_cue():
    """R14: a sound a player cannot look up is information removed."""
    from freight_fate.sound_catalog import CATALOG

    entries = [e for group in CATALOG for e in group.entries]
    match = [e for e in entries if any(c.key == LANE_GUIDE_TONE_KEY for c in e.plays)]
    assert match, "the guide tone is not in Learn game sounds"
    # And it says it is the non-default, so a player auditioning sounds is
    # not left wondering why they have never heard it.
    assert "default" in match[0].meaning.lower()
