"""Regression test for the ffmpeg-backed OGG encode in ``_write_asset``.

soundfile 0.14.0 + libsndfile 1.2.2 on Windows hard-crashes the whole
Python process (no exception, dead worker) writing an OGG/Vorbis file of
roughly 12 seconds or more at 44.1 kHz -- see
.superpowers/sdd/2026-08-13-radio-content-generation/task5-fix-write-asset-brief.md.
``_write_asset`` now writes a temp WAV via soundfile (unaffected) and
shells out to ffmpeg for the Vorbis encode, matching the pattern
``_write_ogg`` already uses for API-returned mp3 bytes. This test writes a
sample in exactly the length band that used to crash: on the old
soundfile-direct code this test doesn't fail cleanly, it kills the pytest
worker.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import generate_radio  # noqa: E402

RATE = 44100
DURATION_S = 12.5


# _write_asset encodes through ffmpeg on purpose -- that shell-out IS the fix
# this test guards -- so there is nothing left to assert without it. Unlike the
# runner tests, which stub the encode out, this one has to do the real write.
@pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg is not installed; _write_asset encodes Vorbis by shelling out to it",
)
def test_write_asset_survives_a_12_5_second_ogg_write(monkeypatch, tmp_path):
    monkeypatch.setattr(generate_radio, "ASSETS", tmp_path)

    n = int(RATE * DURATION_S)
    sample = (0.3 * np.sin(2.0 * np.pi * 440.0 * np.arange(n) / RATE)).astype("float32")

    generate_radio._write_asset(sample, RATE, "radio/long_test_tone.ogg")

    out = tmp_path / "radio" / "long_test_tone.ogg"
    assert out.exists()

    written, written_rate = sf.read(str(out))
    duration = len(written) / written_rate
    assert abs(duration - DURATION_S) <= 0.2
