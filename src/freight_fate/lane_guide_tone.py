"""The optional tone the lane guide can lean instead of the road bed.

The guide normally pans the road bed the driver is already hearing -- the
community ruling from the audiogames.net thread (JaceK, 2026-07-17): a
continuous tone overwhelms the soundscape and hurts players with sensory or
hearing conditions, and Forza's blind driving assists reached the same
answer, panning the car's own engine and tires rather than adding anything.
That ruling stands and the bed is still the default.

It fails one real case. ``vehicle/road`` sits at -33.3 dBFS RMS against the
engine loops' -18.7, and ``set_road_noise`` already runs the road channel at
full gain by highway speed, so there is no headroom left to give it. A bed
15 dB under the engine carries no pan information, because you cannot hear
which side a sound went to if you cannot hear the sound. Darren reported
exactly that and was right.

So this is offered as a choice rather than a replacement (owner, 2026-08-17):
off unless the driver turns it on, which is the shape the ruling actually
objects to -- a tone nobody asked for -- and which the steering-sound RFC
already asks of every cue ("individually toggleable, pitch- and
volume-adjustable, and previewable"). Regenerating the bed louder is still
the fix that helps everyone and is still on the roadmap for September.

The pitch and level are Darren's, from the candidate he sent to the tester
Dropbox on 2026-08-17: a 291.6 Hz sine at -16 dBFS RMS, which puts it 2.6 dB
ABOVE the engine rather than 15 under. His file is a 1.45 s one-shot that
cannot loop -- no trailing silence, and mp3 noise at the seam that trimming
cannot remove -- and the harmonics sit 40 dB down, so there is nothing in it
but the tone. Synthesized here instead, the same way the ladder earcons and
the enforcement signature are: pure arithmetic, identical bytes from the
same build, nothing to add to LFS. The loop LENGTH is chosen as a whole
number of cycles rather than trimmed to one, so the wrap is seamless by
construction and not by tuning.
"""

from __future__ import annotations

import array
import io
import math
import wave

from .audio import register_generated_sound

# Keyed under "guide/" rather than "vehicle/" for the same reason the
# ladder earcons sit under "ladder/": the asset-scan test walks the
# shipped folders looking for a file on disk, and a synthesized cue has
# none.
LANE_GUIDE_TONE_KEY = "guide/lane_guide_tone"

_RATE = 44100
# Darren's tone, measured off his file.
TONE_HZ = 291.620
TONE_RMS_DBFS = -16.0
# Cycles in one loop. 64 gives about 220 ms -- long enough that the loop is
# not itself a rhythm, short enough to start and stop with the drift.
TONE_CYCLES = 64

_registered = False


def lane_guide_tone_wav() -> bytes:
    """One seamless loop of the guide tone.

    The sample count comes first and the frequency follows from it, so the
    loop holds a whole number of cycles exactly and the last sample runs
    into the first with no step. Trimming a recording to length cannot do
    this: it leaves a fraction of a cycle and a click on every wrap.
    """
    frames = int(round(TONE_CYCLES * _RATE / TONE_HZ))
    peak = (10 ** (TONE_RMS_DBFS / 20)) * 32767 * math.sqrt(2)
    samples = array.array("h")
    for i in range(frames):
        value = int(peak * math.sin(2.0 * math.pi * TONE_CYCLES * i / frames))
        value = max(-32768, min(32767, value))
        samples.append(value)
        samples.append(value)  # centred: the guide's pan carries the side
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(_RATE)
        out.writeframes(samples.tobytes())
    return buffer.getvalue()


def register_lane_guide_tone() -> None:
    """Publish the tone under its ordinary sound key.

    Idempotent, mirroring ``ladder_earcons.register_ladder_earcons``: safe to
    call from the Learn screen every time it opens.
    """
    global _registered
    if _registered:
        return
    register_generated_sound(LANE_GUIDE_TONE_KEY, lane_guide_tone_wav(), "wav")
    _registered = True
