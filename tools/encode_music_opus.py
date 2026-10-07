"""Re-encode the music library to Ogg Opus at one loudness, from WAV masters where we have them.

The music is 236 MB of the 282 MB download -- 84% of what a player pulls, and
the only part still growing as tracks are added. Opus at 80 kbps stereo roughly
halves it with no perceptible loss on background beds sitting under speech, and
both audio backends already decode it (core BASS opens .opus with no plugin;
the SDL_mixer fallback does too), so this is a data swap, not an engine change.

Loudness. The game applies no per-track gain: the music and radio sliders are
the only thing between a file and the player's ears, so a track mastered 8 dB
hotter than its neighbour is 8 dB louder at the same slider. Every track is
measured (EBU R128 integrated loudness and true peak, ``tools/loudness.py``)
and given one static gain to ``--target-lufs``. Static gain only, never
compression: a quiet track whose peaks would cross ``--max-tp`` stops at that
ceiling and stays under the target, and the report says so. A shipped Opus
already within ``SKIP_WITHIN_DB`` of the target is left untouched rather than
put through another lossy generation for nothing.

Two sources, by necessity:

* WAV masters (Josh's Suno/ElevenLabs renders, 48 kHz/16-bit): a clean
  single-generation encode. Matched to a shipped track by DURATION, never by
  filename -- the masters arrived with inconsistent names ("Urban Roll.wav" is
  ``menu_urban_roll``, "Greywater Quay.wav" is ``radio_rock_greywater_quay``)
  and a couple of 8-minute files that match no shipped edit at all. Duration is
  the fingerprint that cannot lie about which track this is.
* The shipped audio (Ogg Vorbis or Opus), for every track with no WAV master.
  Lossy-to-lossy degrades slightly, but the owner A/B'd it and could not
  distinguish 64k Opus from the 160k Vorbis on monitors.

A WAV is only accepted for a stem when its duration matches within
``DURATION_TOLERANCE_S``; anything else is reported and left to the shipped
path, so a mislabelled master can never ship under the wrong track name.

The WAV masters zip defaults to the owner's machine and most contributors
won't have it -- that's fine, the tool falls back to encoding every track
from the shipped audio. Point ``FREIGHT_FATE_WAV_MASTERS`` at your own copy of
the zip to get the WAV path instead.

The loose ``assets/sounds/music`` tree is often stale next to the verified
``assets/music.pak``; unpack the pack somewhere and pass ``--music-dir``, then
repack with ``tools/pack_sounds.py``'s ``pack_music_only``.

Usage: ``uv run --group tooling python tools/encode_music_opus.py`` (``av``
lives in the ``tooling`` dependency group). Add ``--write`` to actually
encode; without it this only prints the plan. ``--report before.tsv`` writes
each track's measured loudness, the gain applied and the result.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import av
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loudness  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MUSIC = (ROOT / "assets" / "sounds" / "music").resolve()
WAV_ZIP = Path(
    os.environ.get(
        "FREIGHT_FATE_WAV_MASTERS", r"C:/Users/nrome/Downloads/freight-fate-raw-wavs.zip"
    )
)

BITRATE = 80_000
DURATION_TOLERANCE_S = 1.0
SHIPPED_SUFFIXES = (".opus", ".ogg")
# Music and the radio's songs, hosts, ads and station IDs all ride the one
# music channel, so they share one target. -18 LUFS leaves room under the
# -1 dBTP ceiling for nearly every track without touching its dynamics.
TARGET_LUFS = -18.0
MAX_TRUE_PEAK = -1.0
SKIP_WITHIN_DB = 0.5


def _duration(container: av.container.InputContainer) -> float:
    stream = container.streams.audio[0]
    if stream.duration:
        return float(stream.duration * stream.time_base)
    # Fall back to decoding if the header carries no duration.
    total = 0
    for frame in container.decode(stream):
        total += frame.samples
    return total / (stream.rate or 48000)


def _wav_durations() -> dict[str, tuple[float, bytes]]:
    """Every music WAV in the master zip: filename -> (seconds, raw bytes).

    Most contributors don't have the zip -- that's expected, not an error.
    Return empty and let every track fall back to the shipped audio.
    """
    out: dict[str, tuple[float, bytes]] = {}
    if not WAV_ZIP.exists():
        print(f"No WAV masters zip at {WAV_ZIP} -- encoding everything from the shipped audio.")
        return out
    with zipfile.ZipFile(WAV_ZIP) as archive:
        for info in archive.infolist():
            name = info.filename
            if "/music/" not in name.lower() or not name.lower().endswith(".wav"):
                continue
            data = archive.read(name)
            with av.open(io.BytesIO(data)) as container:
                out[Path(name).name] = (_duration(container), data)
    return out


def _shipped(music: Path) -> dict[str, Path]:
    """Each shipped track's stem -> its file, Opus winning over a stale Ogg."""
    out: dict[str, Path] = {}
    for suffix in reversed(SHIPPED_SUFFIXES):
        for path in sorted(music.glob(f"*{suffix}")):
            out[path.stem] = path
    return out


def _shipped_durations(music: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for stem, path in _shipped(music).items():
        with av.open(str(path)) as container:
            out[stem] = _duration(container)
    return out


def _normalize(name: str) -> str:
    """A WAV filename reduced to a candidate stem: lowercase, spaces to
    underscores, a trailing ``(1)`` duplicate marker stripped."""
    stem = Path(name).stem.lower().strip()
    if stem.endswith(")") and "(" in stem:
        stem = stem[: stem.rindex("(")].strip()
    return stem.replace(" ", "_")


def build_plan(music: Path = MUSIC) -> tuple[dict[str, tuple[bytes, str]], list[str], list[str]]:
    """Return (stem -> (wav bytes, why)), (stems from shipped audio), (rejected wav names).

    Name first, duration always confirming. A WAV is bound to a stem only when
    the audio lengths agree within tolerance, so a name collision cannot ship
    one track's audio under another's title -- the failure a pure-duration
    match invited (it cross-wired tracks of equal length) and the reason this
    is worth the extra pass.
    """
    wavs = _wav_durations()
    shipped = _shipped_durations(music)

    wav_for_stem: dict[str, tuple[bytes, str]] = {}
    used: set[str] = set()

    # Pass 1: the WAV's own name points at a shipped stem, and duration agrees.
    for name, (wdur, data) in wavs.items():
        stem = _normalize(name)
        if (
            stem in shipped
            and stem not in wav_for_stem
            and abs(wdur - shipped[stem]) <= DURATION_TOLERANCE_S
        ):
            wav_for_stem[stem] = (data, f"name+{abs(wdur - shipped[stem]):.1f}s")
            used.add(name)

    # Pass 2: leftover WAVs (renamed masters) to leftover stems, by duration.
    for name, (wdur, data) in wavs.items():
        if name in used:
            continue
        best_stem, best_gap = None, DURATION_TOLERANCE_S
        for stem, sdur in shipped.items():
            if stem in wav_for_stem:
                continue
            gap = abs(wdur - sdur)
            if gap <= best_gap:
                best_stem, best_gap = stem, gap
        if best_stem is not None:
            wav_for_stem[best_stem] = (data, f"duration {best_gap:.1f}s ({Path(name).name})")
            used.add(name)

    from_shipped = sorted(stem for stem in shipped if stem not in wav_for_stem)
    rejected = sorted(Path(n).name for n in wavs if n not in used)
    return wav_for_stem, from_shipped, rejected


def decode(source: bytes | Path) -> np.ndarray:
    """The whole track as float32 ``(2, n)`` at 48 kHz; mono goes to both sides."""
    chunks = []
    with av.open(io.BytesIO(source) if isinstance(source, bytes) else str(source)) as inp:
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=loudness.RATE)
        for frame in inp.decode(inp.streams.audio[0]):
            chunks.extend(f.to_ndarray() for f in resampler.resample(frame))
        chunks.extend(f.to_ndarray() for f in resampler.resample(None) or [])
    return np.concatenate(chunks, axis=1)


def measure(samples: np.ndarray) -> tuple[float, float, float]:
    """(integrated LUFS, loudness range LU, true peak dBTP)."""
    return (
        loudness.integrated(samples),
        loudness.loudness_range(samples),
        loudness.true_peak(samples),
    )


def write_opus(samples: np.ndarray, dst: Path) -> None:
    """Encode ``(2, n)`` float samples to Ogg Opus at ``BITRATE``."""
    interleaved = np.clip(samples, -1.0, 1.0).T.astype(np.float32)
    with av.open(str(dst), "w", format="ogg") as out:
        ostream = out.add_stream("libopus", rate=loudness.RATE)
        ostream.bit_rate = BITRATE
        step = loudness.RATE
        for start in range(0, len(interleaved), step):
            block = np.ascontiguousarray(interleaved[start : start + step]).reshape(1, -1)
            frame = av.AudioFrame.from_ndarray(block, format="flt", layout="stereo")
            frame.rate = loudness.RATE
            frame.pts = start
            for packet in ostream.encode(frame):
                out.mux(packet)
        for packet in ostream.encode(None):
            out.mux(packet)


def encode_track(job: tuple) -> dict:
    """Measure one track, apply its gain, encode, re-measure. One report row."""
    stem, source, music, target, max_tp, write = job
    samples = decode(source)
    lufs, lra, tp = measure(samples)
    gain, limited = loudness.normalizing_gain(lufs, tp, target, max_tp)
    row = {
        "track": stem,
        "source": "wav" if isinstance(source, bytes) else Path(source).suffix[1:],
        "seconds": samples.shape[1] / loudness.RATE,
        "lufs": lufs,
        "lra": lra,
        "true_peak": tp,
        "gain_db": gain,
        "peak_limited": limited,
    }
    skip = not isinstance(source, bytes) and source.suffix == ".opus" and abs(gain) < SKIP_WITHIN_DB
    if not write or skip:
        row["gain_db"] = 0.0 if skip else gain
        row.update(after_lufs=lufs if skip else None, after_true_peak=tp if skip else None)
        return row
    dst = music / f"{stem}.opus"
    tmp = dst.with_suffix(".opus.tmp")
    write_opus(samples * 10.0 ** (gain / 20.0), tmp)
    tmp.replace(dst)
    after = decode(dst)
    row.update(after_lufs=loudness.integrated(after), after_true_peak=loudness.true_peak(after))
    return row


def write_report(rows: list[dict], path: Path) -> None:
    def fmt(value) -> str:
        if value is None:
            return ""
        return f"{value:.2f}" if isinstance(value, float) else str(value)

    columns = list(rows[0])
    lines = ["\t".join(columns)]
    lines += ["\t".join(fmt(row.get(c)) for c in columns) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Encode and replace the tracks.")
    parser.add_argument("--music-dir", type=Path, default=MUSIC, help="Folder of shipped tracks.")
    parser.add_argument("--target-lufs", type=float, default=TARGET_LUFS)
    parser.add_argument("--max-tp", type=float, default=MAX_TRUE_PEAK, help="True-peak ceiling.")
    parser.add_argument("--report", type=Path, help="Write a per-track loudness TSV here.")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    args = parser.parse_args(argv)
    music = args.music_dir.resolve()

    wav_for_stem, from_shipped, rejected = build_plan(music)
    print(f"{len(wav_for_stem)} track(s) from WAV masters:")
    for stem in sorted(wav_for_stem):
        print(f"  WAV  {stem:34} [{wav_for_stem[stem][1]}]")
    print(f"\n{len(from_shipped)} track(s) from the shipped audio (no WAV master).")
    if rejected:
        print(f"\n{len(rejected)} WAV(s) matched no shipped track by duration, DROPPED:")
        for name in rejected:
            print(f"  {name}")

    if not args.write and not args.report:
        print("\nDry run. Re-run with --write, or --report to measure.")
        return 0

    shipped = _shipped(music)
    before = sum(p.stat().st_size for p in shipped.values())
    jobs = [
        (stem, data, music, args.target_lufs, args.max_tp, args.write)
        for stem, (data, _why) in wav_for_stem.items()
    ]
    jobs += [
        (stem, shipped[stem], music, args.target_lufs, args.max_tp, args.write)
        for stem in from_shipped
    ]
    with ProcessPoolExecutor(args.jobs) as pool:
        rows = sorted(pool.map(encode_track, jobs), key=lambda row: row["track"])

    limited = [row["track"] for row in rows if row["peak_limited"]]
    print(
        f"\n{len(rows)} track(s) measured; target {args.target_lufs} LUFS, ceiling {args.max_tp} dBTP."
    )
    if limited:
        print(
            f"{len(limited)} stopped short of the target at the peak ceiling: {', '.join(limited)}"
        )
    if args.report:
        write_report(rows, args.report)
        print(f"Report: {args.report}")
    if not args.write:
        return 0

    # Only remove an .ogg once its .opus exists.
    removed = 0
    for path in list(music.glob("*.ogg")):
        opus = path.with_suffix(".opus")
        if opus.exists() and opus.stat().st_size > 0:
            path.unlink()
            removed += 1
    after = sum(p.stat().st_size for p in music.glob("*.opus"))
    print(f"\nEncoded {len(rows)} track(s), removed {removed} .ogg.")
    print(f"music: {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
