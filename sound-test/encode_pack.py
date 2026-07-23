"""Encode the keeper renders into the compressed pack format the game loads.

Norm 2026-07-21: the assets must ship as compressed .ogg to go in the pack. The
game's existing assets are OGG VORBIS at 44.1 kHz (measured), and the loader
(pygame/BASS) decodes Vorbis natively -- Opus would need a plugin, so Vorbis is
the safe drop-in. This converts the WAV renders to Vorbis .ogg at 44.1 kHz and
stages them under a mirror of the in-game sounds tree, so a finalized set can be
dropped into src/freight_fate/assets/sounds-licensed/ (the gitignored overlay).

Cull first, then run: whatever WAVs are present for the round-robin banks
(clunks, shifts) get encoded, so delete the ones the ear rejected before
staging. Engine mid/high bands still need steady loops cut from the 60624 high-
rpm interior take (1440-2175 rpm) -- listed as PENDING below, not yet encoded.

Outputs to C:\\temp\\ffsound\\pack mirroring the asset keys, with a size report.

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/encode_pack.py
"""

from __future__ import annotations

import wave  # noqa: F401  (kept for parity with sibling scripts)
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

FF = Path(r"C:\temp\ffsound")
OUT = FF / "pack"
TARGET_SR = 44100   # match the existing pack (engine/idle.ogg is 44.1 kHz Vorbis)

# render (under C:\temp\ffsound) -> asset key (path under sounds-licensed/).
# Single files map one-to-one; RR banks map a glob to a numbered key family.
SINGLES: list[tuple[str, str]] = [
    ("896/idle_680.wav", "engine/idle"),            # band idle  (~680 rpm)
    # low = the 896 mid cut pitched to 950 (engine_low_950.py). The 60624
    # neutral hold is RETIRED: it measures ~1125 rpm (not the labeled ~1000,
    # 30 rpm under the mid cut) and is likely a different truck.
    ("896/engine_low_950.wav", "engine/low"),       # band low   (950 rpm)
    # mid/high ship envelope-FLATTENED (engine_band_flatten.py): the raw
    # steady-hold windows carry the real driver's throttle surging (50-64%
    # slow-RMS swing), which loops as an audible stop-start jutter.
    ("896/cruise_mid_1150_flat.wav", "engine/mid"),  # band mid  (~1150 rpm)
    # mid-high = the flattened mid pitched to 1425: splits the too-wide
    # 1150->1800 gap so no band stretches into formant smear.
    ("896/engine_midhigh_1425.wav", "engine/midhigh"),  # band mid-high (1425 rpm)
    ("896/cruise_high_1800_flat.wav", "engine/high"),  # band high  (~1800 rpm)
    ("896/rev_launch.wav", "engine/rev_launch"),    # short pull: launch from a stop
    ("896/rev_load.wav", "engine/rev_load"),        # long pull: digging in under load
    ("brakes/brake_hiss_bed.wav", "vehicle/brake_hiss_bed"),
    ("brakes/ebrake_full.wav", "vehicle/ebrake"),
    ("air/pressurize_hiss.wav", "vehicle/air_pressurize"),
]
BANKS: list[tuple[str, str]] = [
    ("brakes/brake_clunk_*.wav", "vehicle/brake_clunk"),
    ("shifts/shift_manual_*.wav", "vehicle/shift_manual"),
    ("shifts/shift_auto_*.wav", "vehicle/shift_auto"),
]
# Everything for the engine ring is now cut 896-native (one donor, one voice);
# the old plan to pull mid/high from 60624 is retired.
PENDING: list[str] = []


def encode(src: Path, key: str) -> tuple[int, int]:
    """WAV -> Vorbis .ogg at 44.1 kHz. Returns (wav_bytes, ogg_bytes)."""
    x, sr = sf.read(str(src), always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != TARGET_SR:
        x = resample_poly(x, TARGET_SR, sr)
    x = np.clip(x, -1.0, 1.0).astype("float32")
    dst = OUT / f"{key}.ogg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), x, TARGET_SR, format="OGG", subtype="VORBIS")
    return src.stat().st_size, dst.stat().st_size


def main() -> None:
    if OUT.exists():
        for f in OUT.rglob("*.ogg"):
            f.unlink()                                   # rebuild the staging clean
    OUT.mkdir(parents=True, exist_ok=True)
    total_wav = total_ogg = 0
    rows: list[tuple[str, int, int]] = []

    for rel, key in SINGLES:
        src = FF / rel
        if not src.exists():
            print(f"  MISSING {rel}"); continue
        try:
            w, o = encode(src, key)
        except Exception as e:
            print(f"  SKIP {rel}: {e}"); continue
        total_wav += w; total_ogg += o; rows.append((key, w, o))

    for pattern, key_base in BANKS:
        # Skip the *_demo.wav audition aids -- they are not game assets.
        files = sorted(f for f in FF.glob(pattern) if "demo" not in f.stem)
        kept = 0
        for src in files:
            key = f"{key_base}_{kept + 1:02d}"
            try:
                w, o = encode(src, key)
            except Exception as e:                       # one bad file must not kill the run
                print(f"  SKIP {src.name}: {e}"); continue
            kept += 1
            total_wav += w; total_ogg += o; rows.append((key, w, o))
        if kept:
            rows.append((f"  ({kept} in {key_base}_NN)", 0, 0))

    print(f"  {'asset key':32s} {'wav KB':>8s} {'ogg KB':>8s}")
    for key, w, o in rows:
        if w:
            print(f"  {key:32s} {w/1024:8.0f} {o/1024:8.0f}")
        else:
            print(f"  {key}")
    if total_wav:
        print(f"\n  total {total_wav/1024/1024:.1f} MB WAV -> {total_ogg/1024/1024:.1f} MB "
              f"OGG Vorbis  ({total_ogg/total_wav:.0%} of original)")
    print(f"  staged under {OUT}  (mirror of sounds-licensed/)")
    if PENDING:
        print("  PENDING (still to cut): " + "; ".join(PENDING))


def _run_with_deep_stack() -> None:
    """Run main() on a thread with a 64 MB stack.

    soundfile 0.14 + libsndfile 1.2.2 on Windows blows the default 1 MB main-
    thread stack inside the Vorbis encoder on multi-second buffers (silent
    exit 127/253, faulthandler says stack overflow in _cdata_io). A worker
    thread with an explicit big stack sidesteps it.
    """
    import threading

    threading.stack_size(64 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()


if __name__ == "__main__":
    _run_with_deep_stack()
