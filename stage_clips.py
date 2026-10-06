"""stage_clips.py -- encode Channel 3000's programming into clips/ and write clips.json.

Run from the Freight Fate repo (it borrows the music pack's encoder and
loudness code), pointing at the Dark Nursery Rhymes folder that holds the
rendered masters:

    uv run --group tooling python <this file> --source "C:/Users/joshu/Documents/Dark Nursery Rhymes" --ff-repo C:/Users/joshu/ff-c3k --out .

Every clip is a WAV master, measured and given one static gain to -18 LUFS
(-1 dBTP ceiling), like music.pak, then encoded to Ogg Opus at 48 kbps
stereo (ffmpeg's libopus, constrained VBR): voices only, so 48 kbps carries it, and the parts are panned, so it
stays stereo. clips.json lists each clip's kind, dayparts, opener flag,
title and measured duration; the station brief (STATION.md, "What plays
when") is where the daypart choices come from.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

BITRATE = 48_000
DAYPARTS = ["day", "prime", "late", "overnight"]

AFTER_HOURS = {  # segment number -> dayparts (STATION.md, "What plays when"); 03 is not used
    "00": ["prime"], "01": ["prime"], "02": ["prime"], "08": ["prime"], "09": ["prime"],
    "07": ["late"], "10": ["late"], "12": ["late"],
    "11": ["overnight"], "13": ["overnight"],
    "04": ["day"], "05": ["day"], "06": ["day"],
}
GRIMATONICS_OVERNIGHT = {"brahms-lullaby", "wee-willie-winkie", "row-row-row-your-boat"}
GRIMATONICS_DROPPED = {"kagome-kagome"}
SHORTS = {"04": "The Lone Courier", "06": "Planet Office", "07": "The Bold and the Rebooted"}


def header(song: Path) -> list[str]:
    lines = []
    for line in song.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        lines.append(line[1:].strip())
    return lines


def tag(lines: list[str], name: str) -> str | None:
    for line in lines:
        m = re.match(rf"{name}:\s*(.+)", line, re.I)
        if m:
            return m.group(1).strip()
    return None


def dayparts_of(value: str | None) -> list[str]:
    if not value or value.strip().lower() == "any":
        return list(DAYPARTS)
    parts = [p.strip().lower() for p in value.split(",")]
    bad = [p for p in parts if p not in DAYPARTS]
    if bad:
        raise SystemExit(f"unknown daypart {bad} in {value!r}")
    return parts


def show_table(show_md: Path) -> dict[str, str]:
    """'| 07 | The Last Payphone | ...' rows -> {'07': 'The Last Payphone'}."""
    out = {}
    for line in show_md.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(\d{1,2})\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            out[m.group(1).zfill(2)] = m.group(2)
    return out


def plan(src: Path) -> list[dict]:
    radio = src / "channel-3000-radio"
    jobs = []
    for wav in sorted(radio.glob("*.wav")):
        stem = wav.stem
        song = wav.with_suffix(".song")
        if not song.exists() or not re.match(r"(day|night|host|id|ad)_", stem):
            continue
        if stem.startswith(("day_", "night_")) and not wav.with_suffix(".mp3").exists():
            continue  # an episode is finished when its MP3 is made, last
        h = header(song)
        first = h[0].split("--", 1)[-1].strip() if h else stem
        if stem.startswith(("day_", "night_")):
            kind, title = "programme", re.split(r",\s*episode|:", first)[0].strip()
        elif stem.startswith("host_"):
            kind, title = "continuity", "Channel 3000"
        elif stem.startswith("id_"):
            kind, title = "ident", "Channel 3000"
        else:
            kind, title = "ad", "a commercial break"
        dayparts = dayparts_of(tag(h, "dayparts"))
        if stem.startswith("day_") and tag(h, "dayparts") is None:
            dayparts = ["day"]
        opener = (tag(h, "opener") or "").lower().startswith("yes")
        jobs.append(dict(key=stem, kind=kind, dayparts=dayparts, opener=opener, title=title, sources=[str(wav)]))

    ah_titles = show_table(src / "sketch-show-2" / "SHOW.md")
    for wav in sorted((src / "sketch-show-2").glob("[0-9][0-9]-*.wav")):
        num = wav.stem[:2]
        if num not in AFTER_HOURS:
            continue
        key = "afterhours_" + wav.stem.replace("-", "_")
        jobs.append(dict(key=key, kind="programme", dayparts=AFTER_HOURS[num], opener=False,
                         title=ah_titles.get(num, wav.stem[3:].replace("-", " ").title()), sources=[str(wav)]))

    fc = sorted((src / "sketch-show").glob("0[1-8]-*.wav"))
    jobs.append(dict(key="flying_circus_full_show", kind="programme", dayparts=["prime"], opener=False,
                     title="Phoneme's Flying Circus", sources=[str(p) for p in fc]))
    for wav in fc:
        if wav.stem[:2] in SHORTS:
            jobs.append(dict(key="flying_circus_" + wav.stem.replace("-", "_"), kind="short", dayparts=list(DAYPARTS),
                             opener=False, title=SHORTS[wav.stem[:2]], sources=[str(wav)]))

    for wav in sorted((src / "songs").glob("*.wav")):
        if wav.stem in GRIMATONICS_DROPPED:
            continue
        song = wav.with_suffix(".song")
        title = header(song)[0].split(". ")[0].strip() if song.exists() else wav.stem
        jobs.append(dict(key="grimatonics_" + wav.stem.replace("-", "_"), kind="programme",
                         dayparts=["overnight"] if wav.stem in GRIMATONICS_OVERNIGHT else ["late"],
                         opener=False, title=title, sources=[str(wav)]))
    return jobs


def encode(job_and_paths: tuple) -> dict:
    job, ff_tools, out = job_and_paths
    sys.path.insert(0, ff_tools)
    import encode_music_opus as emo
    import loudness

    emo.BITRATE = BITRATE
    parts = []
    gap = np.zeros((2, 2 * loudness.RATE), dtype=np.float32)
    for i, path in enumerate(job["sources"]):
        if i:
            parts.append(gap)  # two seconds between the Flying Circus sketches, as in the full-show MP3
        parts.append(emo.decode(Path(path)))
    samples = np.concatenate(parts, axis=1)
    lufs, _lra, tp = emo.measure(samples)
    gain, limited = loudness.normalizing_gain(lufs, tp, emo.TARGET_LUFS, emo.MAX_TRUE_PEAK)
    dst = Path(out) / "clips" / f"{job['key']}.opus"
    # ffmpeg's libopus with CONSTRAINED VBR: unconstrained VBR (what PyAV gives
    # write_opus) ran these voice-and-reverb mixes at 66-78 kbps against a
    # 48 kbps target; constrained holds the average at the target.
    pcm = np.clip(samples * 10.0 ** (gain / 20.0), -1.0, 1.0).T.astype("<f4").tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(loudness.RATE), "-ac", "2",
                    "-i", "pipe:0", "-c:a", "libopus", "-b:a", str(BITRATE), "-vbr", "constrained",
                    str(dst)], input=pcm, check=True)
    after = emo.decode(dst)
    row = {k: job[k] for k in ("key", "kind", "dayparts", "opener", "title")}
    row.update(duration_s=round(after.shape[1] / loudness.RATE, 3),
               source_lufs=round(lufs, 2), gain_db=round(gain, 2), peak_limited=limited,
               lufs=round(loudness.integrated(after), 2), true_peak=round(float(loudness.true_peak(after)), 2))
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--ff-repo", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("."))
    ap.add_argument("--jobs", type=int, default=6)
    args = ap.parse_args()
    jobs = plan(args.source)
    (args.out / "clips").mkdir(parents=True, exist_ok=True)
    tools = str((args.ff_repo / "tools").resolve())
    with ProcessPoolExecutor(args.jobs) as pool:
        rows = list(pool.map(encode, [(j, tools, str(args.out)) for j in jobs]))
    rows.sort(key=lambda r: r["key"])
    manifest = {
        "schema": 1,
        "notes": "Channel 3000's clips for channel3000.pak: Ogg Opus, 48 kbps stereo, 48 kHz, "
                 "one static gain each to -18 LUFS with a -1 dBTP ceiling. Made by stage_clips.py "
                 "from the Dark Nursery Rhymes masters. Dayparts by the truck's local hour: "
                 "day 5-19, prime 19-22, late 22-2, overnight 2-5.",
        "frequency_mhz": 87.7,
        "dayparts": {"day": [5, 19], "prime": [19, 22], "late": [22, 2], "overnight": [2, 5]},
        "clips": rows,
    }
    (args.out / "clips.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    total = sum(r["duration_s"] for r in rows)
    size = sum(p.stat().st_size for p in (args.out / "clips").glob("*.opus"))
    print(f"{len(rows)} clips, {total / 60:.1f} min, {size / 1e6:.1f} MB")
    for dp in DAYPARTS:
        progs = [r for r in rows if r["kind"] == "programme" and dp in r["dayparts"]]
        print(f"  {dp}: {len(progs)} programmes, {sum(r['duration_s'] for r in progs) / 60:.1f} min,"
              f" opener: {[r['key'] for r in rows if r['opener'] and dp in r['dayparts']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
