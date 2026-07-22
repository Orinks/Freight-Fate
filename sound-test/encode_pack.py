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
    ("896/idle_680.wav", "engine/idle"),            # band idle  (~620 rpm)
    ("896/cruise_neutral.wav", "engine/low"),       # band low   (~1000 rpm)
    ("brakes/brake_hiss_bed.wav", "vehicle/brake_hiss_bed"),
    ("brakes/ebrake_full.wav", "vehicle/ebrake"),
    ("air/pressurize_hiss.wav", "vehicle/air_pressurize"),
]
BANKS: list[tuple[str, str]] = [
    ("brakes/brake_clunk_*.wav", "vehicle/brake_clunk"),
    ("shifts/shift_manual_*.wav", "vehicle/shift_manual"),
    ("shifts/shift_auto_*.wav", "vehicle/shift_auto"),
]
# Not yet cut -- steady band loops for the engine crossfade ring:
PENDING = ["engine/mid (~1500 rpm)", "engine/high (~2100 rpm)  (cut from 60624)"]


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
    print("  PENDING (steady band loops still to cut): " + "; ".join(PENDING))


if __name__ == "__main__":
    main()
