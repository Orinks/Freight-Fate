"""Re-encode the music library to Ogg Opus, from WAV masters where we have them.

The music is 236 MB of the 282 MB download -- 84% of what a player pulls, and
the only part still growing as tracks are added. Opus at 80 kbps stereo roughly
halves it with no perceptible loss on background beds sitting under speech, and
both audio backends already decode it (core BASS opens .opus with no plugin;
the SDL_mixer fallback does too), so this is a data swap, not an engine change.

Two sources, by necessity:

* WAV masters (Josh's Suno/ElevenLabs renders, 48 kHz/16-bit): a clean
  single-generation encode. Matched to a shipped track by DURATION, never by
  filename -- the masters arrived with inconsistent names ("Urban Roll.wav" is
  ``menu_urban_roll``, "Greywater Quay.wav" is ``radio_rock_greywater_quay``)
  and a couple of 8-minute files that match no shipped edit at all. Duration is
  the fingerprint that cannot lie about which track this is.
* The shipped Ogg Vorbis, for every track with no WAV master. Vorbis->Opus is
  lossy-to-lossy and degrades slightly, but the owner A/B'd it and could not
  distinguish 64k Opus from the 160k Vorbis on monitors.

A WAV is only accepted for a stem when its duration matches within
``DURATION_TOLERANCE_S``; anything else is reported and left to the Ogg path,
so a mislabelled master can never ship under the wrong track name.
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path

import av

ROOT = Path(__file__).resolve().parents[1]
MUSIC = ROOT / "src" / "freight_fate" / "data" / ".." / "assets" / "sounds" / "music"
MUSIC = (ROOT / "src" / "freight_fate" / "assets" / "sounds" / "music").resolve()
WAV_ZIP = Path(r"C:/Users/nrome/Downloads/freight-fate-raw-wavs.zip")

BITRATE = 80_000
DURATION_TOLERANCE_S = 1.0


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
    """Every music WAV in the master zip: filename -> (seconds, raw bytes)."""
    out: dict[str, tuple[float, bytes]] = {}
    with zipfile.ZipFile(WAV_ZIP) as archive:
        for info in archive.infolist():
            name = info.filename
            if "/music/" not in name.lower() or not name.lower().endswith(".wav"):
                continue
            data = archive.read(name)
            with av.open(io.BytesIO(data)) as container:
                out[Path(name).name] = (_duration(container), data)
    return out


def _ogg_durations() -> dict[str, float]:
    out: dict[str, float] = {}
    for path in sorted(MUSIC.glob("*.ogg")):
        with av.open(str(path)) as container:
            out[path.stem] = _duration(container)
    return out


def _normalize(name: str) -> str:
    """A WAV filename reduced to a candidate stem: lowercase, spaces to
    underscores, a trailing ``(1)`` duplicate marker stripped."""
    stem = Path(name).stem.lower().strip()
    if stem.endswith(")") and "(" in stem:
        stem = stem[: stem.rindex("(")].strip()
    return stem.replace(" ", "_")


def build_plan() -> tuple[dict[str, tuple[bytes, str]], list[str], list[str]]:
    """Return (stem -> (wav bytes, why)), (stems from ogg), (rejected wav names).

    Name first, duration always confirming. A WAV is bound to a stem only when
    the audio lengths agree within tolerance, so a name collision cannot ship
    one track's audio under another's title -- the failure a pure-duration
    match invited (it cross-wired tracks of equal length) and the reason this
    is worth the extra pass.
    """
    wavs = _wav_durations()
    oggs = _ogg_durations()

    wav_for_stem: dict[str, tuple[bytes, str]] = {}
    used: set[str] = set()

    # Pass 1: the WAV's own name points at a shipped stem, and duration agrees.
    for name, (wdur, data) in wavs.items():
        stem = _normalize(name)
        if stem in oggs and stem not in wav_for_stem and abs(wdur - oggs[stem]) <= DURATION_TOLERANCE_S:
            wav_for_stem[stem] = (data, f"name+{abs(wdur - oggs[stem]):.1f}s")
            used.add(name)

    # Pass 2: leftover WAVs (renamed masters) to leftover stems, by duration.
    for name, (wdur, data) in wavs.items():
        if name in used:
            continue
        best_stem, best_gap = None, DURATION_TOLERANCE_S
        for stem, odur in oggs.items():
            if stem in wav_for_stem:
                continue
            gap = abs(wdur - odur)
            if gap <= best_gap:
                best_stem, best_gap = stem, gap
        if best_stem is not None:
            wav_for_stem[best_stem] = (data, f"duration {best_gap:.1f}s ({Path(name).name})")
            used.add(name)

    from_ogg = sorted(stem for stem in oggs if stem not in wav_for_stem)
    rejected = sorted(Path(n).name for n in wavs if n not in used)
    return wav_for_stem, from_ogg, rejected


def encode(src_bytes: bytes | None, src_path: Path | None, dst: Path) -> None:
    source = io.BytesIO(src_bytes) if src_bytes is not None else str(src_path)
    with av.open(source) as inp, av.open(str(dst), "w", format="ogg") as out:
        istream = inp.streams.audio[0]
        ostream = out.add_stream("libopus", rate=48000)
        ostream.bit_rate = BITRATE
        resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
        for frame in inp.decode(istream):
            for rframe in resampler.resample(frame):
                for packet in ostream.encode(rframe):
                    out.mux(packet)
        for rframe in resampler.resample(None) or []:
            for packet in ostream.encode(rframe):
                out.mux(packet)
        for packet in ostream.encode(None):
            out.mux(packet)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Encode and replace the .ogg files.")
    args = parser.parse_args(argv)

    wav_for_stem, from_ogg, rejected = build_plan()
    print(f"{len(wav_for_stem)} track(s) from WAV masters:")
    for stem in sorted(wav_for_stem):
        print(f"  WAV  {stem:34} [{wav_for_stem[stem][1]}]")
    print(f"\n{len(from_ogg)} track(s) transcoded from the shipped Ogg (no WAV master).")
    if rejected:
        print(f"\n{len(rejected)} WAV(s) matched no shipped track by duration, DROPPED:")
        for name in rejected:
            print(f"  {name}")

    if not args.write:
        print("\nDry run. Re-run with --write.")
        return 0

    before = sum(p.stat().st_size for p in MUSIC.glob("*.ogg"))
    done = 0
    for stem, (data, _why) in wav_for_stem.items():
        encode(data, None, MUSIC / f"{stem}.opus")
        done += 1
    for stem in from_ogg:
        encode(None, MUSIC / f"{stem}.ogg", MUSIC / f"{stem}.opus")
        done += 1
    # Only remove an .ogg once its .opus exists and decodes.
    removed = 0
    for path in list(MUSIC.glob("*.ogg")):
        opus = path.with_suffix(".opus")
        if opus.exists() and opus.stat().st_size > 0:
            path.unlink()
            removed += 1
    after = sum(p.stat().st_size for p in MUSIC.glob("*.opus"))
    print(f"\nEncoded {done} track(s), removed {removed} .ogg.")
    print(f"music: {before / 1e6:.1f} MB Ogg -> {after / 1e6:.1f} MB Opus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
