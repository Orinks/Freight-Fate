#!/usr/bin/env python3
"""Listen to every stream on the dial: is it there, is it the station, is it silent.

``check_radio_streams.py`` asks whether a host answers with audio. That
misses the failures a driver actually hears: a mount that answers and plays
dead air, a stream that connects and drops after two seconds, and an address
that plays perfectly well but is a different station from the one the dial
names. This tool records what each stream says about itself and decodes a
sample of it, so those can be judged.

Per station it records:

* the HTTP answer from curl (status, final address after redirects,
  content type) and the ICY headers the server names itself with
  (``icy-name``, ``icy-description``, ``icy-genre``, ``icy-url``), plus the
  first ``StreamTitle`` in the in-band metadata when the server sends one;
* a ffmpeg decode of ``--seconds`` of audio: the codec, how many seconds
  actually decoded, peak and mean level, and how much of it was silence.

Verdicts: ``ok``; ``dead`` (nothing decodable came back); ``dropped`` (it
connected but stopped well short of the sample); ``silent`` (it decoded, but
at a level or with a share of silence that is dead air). Whether a stream is
the station it claims to be is a judgement, not a verdict: the report carries
the evidence for a human to read.

It needs ``curl`` and ``ffmpeg`` on PATH and an unrestricted network; the
radio-sweep workflow runs it on a GitHub runner. Like the reachability check
it only reports, and never edits a catalog::

    uv run python tools/audit_radio_streams.py --only curated --output audit.json
    uv run python tools/audit_radio_streams.py --shard 2/4 --output part2.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURATED_PATH = ROOT / "data" / "radio_catalog.json"
IMPORTED_PATH = ROOT / "data" / "radio_imported.json"
HEALTH_PATH = ROOT / "data" / "radio_stream_health.json"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FreightFate/1.9 stream check"
HEADER_SECONDS = 8
DEFAULT_SAMPLE_S = 25.0
# Dead air: a peak this low is a carrier with nothing on it, or a sign-off
# loop of room tone. Real programme peaks within a few dB of full scale.
SILENT_PEAK_DB = -45.0
SILENCE_FLOOR_DB = -50
SILENCE_SHARE = 0.9
# A stream that connects and hands over less than this much of the sample
# has dropped, which on the dial is a tune followed by a fallback hand-off.
DROPPED_SHARE = 0.4

_HLS_MARKERS = ("#EXT-X-", "#EXTINF")


def rows_to_audit(only: str, recheck_dropped: bool) -> list[dict]:
    rows: list[dict] = []
    if only in {"all", "curated"}:
        for row in json.loads(CURATED_PATH.read_text(encoding="utf-8"))["stations"]:
            rows.append({**row, "_tier": "curated"})
    if only in {"all", "imported"}:
        for row in json.loads(IMPORTED_PATH.read_text(encoding="utf-8"))["stations"]:
            rows.append({**row, "_tier": "imported"})
        if recheck_dropped and HEALTH_PATH.exists():
            present = {row["id"] for row in rows}
            for row in json.loads(HEALTH_PATH.read_text(encoding="utf-8"))["dead"]:
                if row["tier"] == "imported" and row["id"] not in present:
                    rows.append({**row, "_tier": "imported_dropped"})
    return [r for r in rows if (r.get("stream_url") or "").startswith(("http://", "https://"))]


def _parse_headers(raw: str) -> tuple[int, dict]:
    """The status and headers of the LAST response in a curl ``-D`` dump."""
    blocks = [b for b in re.split(r"\r?\n\r?\n", raw) if b.strip()]
    if not blocks:
        return 0, {}
    lines = blocks[-1].splitlines()
    status = 0
    match = re.match(r"^(?:HTTP/\S+|ICY)\s+(\d{3})", lines[0].strip())
    if match:
        status = int(match.group(1))
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return status, headers


def _stream_title(body: bytes, metaint: int) -> str:
    """The first non-empty ``StreamTitle`` in the in-band ICY metadata."""
    offset = metaint
    while offset < len(body):
        length = body[offset] * 16
        block = body[offset + 1 : offset + 1 + length]
        if length and len(block) == length:
            text = block.rstrip(b"\0").decode("utf-8", errors="replace")
            match = re.search(r"StreamTitle='(.*?)';", text, re.S)
            if match and match.group(1).strip():
                return match.group(1).strip()
        offset += 1 + length + metaint
    return ""


def _playlist_target(body: bytes) -> str:
    text = body[:65536].decode("utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("file") and "=" in line:
            line = line.split("=", 1)[1].strip()
        if line.startswith(("http://", "https://")):
            return line
    return ""


def curl_probe(url: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        head_path = Path(tmp) / "head"
        body_path = Path(tmp) / "body"
        proc = subprocess.run(
            [
                "curl",
                "-sS",
                "-L",
                "-k",
                "--max-redirs",
                "8",
                "-m",
                str(HEADER_SECONDS),
                "-A",
                USER_AGENT,
                "-H",
                "Icy-MetaData: 1",
                "-D",
                str(head_path),
                "-o",
                str(body_path),
                "-w",
                "%{http_code}\t%{content_type}\t%{url_effective}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=HEADER_SECONDS + 10,
        )
        raw = head_path.read_text(errors="replace") if head_path.exists() else ""
        body = body_path.read_bytes() if body_path.exists() else b""
    status, headers = _parse_headers(raw)
    written = proc.stdout.split("\t")
    final_url = written[2] if len(written) > 2 else url
    content_type = (headers.get("content-type") or (written[1] if len(written) > 1 else "")).lower()
    result = {
        "http": status,
        "final_url": final_url,
        "content_type": content_type,
        "bytes": len(body),
        "curl_error": proc.stderr.strip()[:160] if proc.returncode not in (0, 28) else "",
    }
    for key in ("icy-name", "icy-description", "icy-genre", "icy-url", "icy-br"):
        if headers.get(key):
            result[key.replace("-", "_")] = headers[key]
    metaint = headers.get("icy-metaint", "")
    if metaint.isdigit() and int(metaint) > 0:
        result["stream_title"] = _stream_title(body, int(metaint))
    head = body[:4096].lstrip()
    if (
        head.startswith(b"#EXTM3U")
        or head.lower().startswith(b"[playlist]")
        or "mpegurl" in content_type
        or "scpls" in content_type
    ):
        text = body[:65536].decode("utf-8", errors="replace")
        if any(marker in text for marker in _HLS_MARKERS):
            result["hls"] = True
        else:
            result["playlist_target"] = _playlist_target(body)
    return result


_FFMPEG_META = re.compile(r"^\s{4,}([A-Za-z_\-]+)\s*:\s(.*)$")


def ffmpeg_sample(url: str, seconds: float) -> dict:
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "info",
        "-user_agent",
        USER_AGENT,
        "-rw_timeout",
        "15000000",
        "-t",
        str(seconds),
        "-i",
        url,
        "-vn",
        "-af",
        f"silencedetect=noise={SILENCE_FLOOR_DB}dB:d=2,volumedetect",
        "-f",
        "null",
        "-",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=seconds + 45
        )
        log = proc.stderr
    except subprocess.TimeoutExpired as error:
        log = (
            (error.stderr or b"").decode("utf-8", "replace")
            if isinstance(error.stderr, bytes)
            else (error.stderr or "")
        )
    result: dict = {}
    audio = re.search(r"Stream #\S+.*?Audio: (.*)", log)
    if audio:
        result["codec"] = audio.group(1).strip()[:80]
    meta: dict[str, str] = {}
    for line in log.splitlines():
        match = _FFMPEG_META.match(line)
        if match and match.group(1).lower() in {
            "icy-name",
            "icy-description",
            "icy-genre",
            "icy-url",
            "streamtitle",
            "title",
            "station",
        }:
            meta.setdefault(match.group(1).lower(), match.group(2).strip())
    if meta:
        result["ffmpeg_meta"] = meta
    times = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", log)
    decoded = 0.0
    if times:
        h, m, s = times[-1]
        decoded = int(h) * 3600 + int(m) * 60 + float(s)
    result["decoded_s"] = round(decoded, 1)
    for key in ("mean_volume", "max_volume"):
        match = re.search(rf"{key}: (-?[\d.]+|-inf) dB", log)
        if match:
            result[key] = -200.0 if match.group(1) == "-inf" else float(match.group(1))
    silence = 0.0
    for match in re.finditer(r"silence_duration: ([\d.]+)", log):
        silence += float(match.group(1))
    trailing = re.findall(r"silence_start: (-?[\d.]+)", log)
    ends = re.findall(r"silence_end:", log)
    if len(trailing) > len(ends) and decoded:
        silence += max(0.0, decoded - float(trailing[-1]))
    result["silence_s"] = round(silence, 1)
    if decoded == 0.0:
        errors = [
            line.strip()
            for line in log.splitlines()
            if "rror" in line or "HTTP" in line or "failed" in line.lower()
        ]
        result["ffmpeg_error"] = (
            (errors[-1] if errors else log.strip().splitlines()[-1:] or [""])[0][:160]
            if log.strip()
            else "no output"
        )
    return result


def audit(row: dict, seconds: float) -> dict:
    url = row["stream_url"]
    out = {
        "id": row["id"],
        "tier": row["_tier"],
        "name": row.get("name", ""),
        "call_sign": row.get("call_sign", ""),
        "station_type": row.get("station_type", ""),
        "source_type": row.get("source_type", ""),
        "supported": row.get("supported", True),
        "stream_url": url,
    }
    try:
        out.update(curl_probe(url))
    except Exception as error:  # noqa: BLE001 -- a report row, never a crash
        out["curl_error"] = f"{type(error).__name__}: {error}"[:160]
    target = out.get("playlist_target") or url
    try:
        out.update(ffmpeg_sample(target, seconds))
    except Exception as error:  # noqa: BLE001
        out["ffmpeg_error"] = f"{type(error).__name__}: {error}"[:160]
    decoded = out.get("decoded_s", 0.0)
    if decoded <= 0.5:
        out["verdict"] = "dead"
    elif decoded < seconds * DROPPED_SHARE:
        out["verdict"] = "dropped"
    elif (
        out.get("max_volume", 0.0) <= SILENT_PEAK_DB
        or out.get("silence_s", 0.0) >= decoded * SILENCE_SHARE
    ):
        out["verdict"] = "silent"
    else:
        out["verdict"] = "ok"
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--only", choices=("all", "curated", "imported"), default="all")
    parser.add_argument(
        "--recheck-dropped",
        action="store_true",
        help="also audit imported rows the health file dropped",
    )
    parser.add_argument("--ids", default="", help="comma-separated ids to audit (overrides --only)")
    parser.add_argument("--shard", default="1/1", help="audit part K of N, e.g. 2/4")
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--seconds", type=float, default=DEFAULT_SAMPLE_S)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    rows = rows_to_audit("all" if args.ids else args.only, args.recheck_dropped or bool(args.ids))
    if args.ids:
        wanted = set(args.ids.split(","))
        rows = [r for r in rows if r["id"] in wanted]
    part, total = (int(x) for x in args.shard.split("/"))
    rows = rows[part - 1 :: total]
    print(f"Auditing {len(rows)} streams with {args.workers} workers...", flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(audit, row, args.seconds) for row in rows]
        for done, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if done % 100 == 0:
                print(f"  {done}/{len(rows)}", flush=True)
    results.sort(key=lambda r: (r["tier"], r["id"]))
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(counts)
    args.output.write_text(
        json.dumps({"counts": counts, "results": results}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
