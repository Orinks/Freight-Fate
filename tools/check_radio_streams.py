#!/usr/bin/env python3
"""Probe every real stream on the dial and report which ones still play.

The curated catalog and the imported directory tier both carry stream URLs
that were reachable when they were written down and may not be now: a
station folds, an account lapses, a host moves. A dead stream on the dial
costs a screen reader user a tune, a wait, and a fallback hand-off, so the
data should know which ones are gone.

This tool only *reports*. It writes a health file that
``tools/import_radio_catalog.py`` reads to drop dead imported rows at build
time, and prints the curated casualties for a human to mark
``"supported": false`` with a note. Nothing here edits a catalog.

Run from the repository root::

    uv run python tools/check_radio_streams.py
    uv run python tools/check_radio_streams.py --only curated --workers 8
    uv run python tools/check_radio_streams.py --recheck-dead

A probe asks for the first couple of kilobytes and hangs up. Verdicts:

``ok``        audio came back (or a Shoutcast v1 ``ICY 200 OK`` greeting).
``playlist``  a .pls/.m3u came back -- playable, but a redirect the game
              resolves at play time rather than a stream in its own right.
``dead``      the host said no: 4xx/5xx, refused, unknown name, or silence
              until the timeout. Retried once, and re-asked at the
              Shoutcast ``/;`` mount, before it counts.

Stations with no stream URL -- the built-in and playlist ones -- are never
probed and never appear in the report.

The report accumulates. A row dropped from the built catalog is no longer
there to probe, so a report written from scratch each time would forget it
and the next build would put it straight back on the dial; casualties are
carried forward until ``--recheck-dead`` sees one answer again.
"""

from __future__ import annotations

import argparse
import http.client
import json
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

CURATED_PATH = ROOT / "src" / "freight_fate" / "data" / "radio_catalog.json"
IMPORTED_PATH = ROOT / "src" / "freight_fate" / "data" / "radio_imported.json"
# Build input, not game data: the player's build never reads it, so it
# lives with the other catalog inputs instead of inside the package.
DEFAULT_OUTPUT = ROOT / "data" / "radio_stream_health.json"

# A player's user agent, not a crawler's: several Icecast hosts answer a
# bare urllib with 403 and the same request with a browser UA with audio.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FreightFate/1.9 stream check"
PROBE_BYTES = 2048
DEFAULT_TIMEOUT_S = 12.0
DEFAULT_WORKERS = 12

_AUDIO_TYPES = (
    "audio/",
    "application/ogg",
    "application/octet-stream",
    "video/",  # some Icecast hosts mislabel AAC as video/mp4
)
_PLAYLIST_TYPES = (
    "audio/x-mpegurl",
    "audio/mpegurl",
    "audio/x-scpls",
    "application/pls+xml",
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
)


def _opener() -> urllib.request.OpenerDirector:
    """A client permissive enough to reach a station that really is up.

    Directory streams are a long tail of self-signed and expired certs on
    hosts that stream fine, so certificates are not verified: a cert error
    is not the question being asked here, and BASS does not verify them
    either.

    The cipher setting matters more than it looks. Python 3.12's default
    security level refuses the older suites that a great many Icecast hosts
    still offer, and the handshake dies with SSLV3_ALERT_HANDSHAKE_FAILURE
    -- which reads exactly like a dead station. The first sweep called
    KBOO, WBAI, KPFK, KZYX, Utah Public Radio and two dozen more dead on
    that alone, while curl played every one of them. Probe with what a
    media player would accept, or the report measures Python's TLS policy
    instead of the dial.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.MINIMUM_SUPPORTED
    context.set_ciphers("DEFAULT@SECLEVEL=1")
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))


def probe(url: str, timeout: float) -> dict:
    """One station's verdict: ``{"verdict": ..., "detail": ...}``."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Icy-MetaData": "1",
            "Range": f"bytes=0-{PROBE_BYTES - 1}",
            "Accept": "*/*",
        },
    )
    try:
        with _opener().open(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            body = response.read(PROBE_BYTES)
            if any(content_type.startswith(kind) for kind in _PLAYLIST_TYPES):
                return {"verdict": "playlist", "detail": content_type}
            if any(content_type.startswith(kind) for kind in _AUDIO_TYPES):
                return {"verdict": "ok", "detail": content_type}
            # An Icecast mount that names no type but hands over bytes is
            # still playing; an HTML error page dressed as 200 is not.
            if body and not content_type.startswith(("text/", "application/json")):
                return {"verdict": "ok", "detail": content_type or "untyped bytes"}
            return {"verdict": "dead", "detail": f"not audio: {content_type or 'empty'}"}
    except urllib.error.HTTPError as error:
        return {"verdict": "dead", "detail": f"HTTP {error.code}"}
    except http.client.BadStatusLine as error:
        # Shoutcast v1 greets with "ICY 200 OK", which is not HTTP and which
        # urllib refuses to parse. The server is up and serving audio.
        if "ICY 200" in str(error.line or ""):
            return {"verdict": "ok", "detail": "shoutcast ICY 200"}
        return {"verdict": "dead", "detail": f"bad status line: {error.line!r}"}
    except (urllib.error.URLError, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        if isinstance(reason, http.client.BadStatusLine) and "ICY 200" in str(reason.line or ""):
            return {"verdict": "ok", "detail": "shoutcast ICY 200"}
        return {"verdict": "dead", "detail": str(reason)[:120]}
    except (http.client.HTTPException, ConnectionError, OSError, ValueError) as error:
        return {"verdict": "dead", "detail": f"{type(error).__name__}: {error}"[:120]}


def _shoutcast_mount(url: str) -> str:
    """The ``/;`` form of a URL, which is where Shoutcast keeps the audio.

    A Shoutcast server answers its bare root with an HTML status page and
    serves the stream from ``/;``. Asking the root and believing the HTML
    calls a live station dead -- it is how WMFO, WRBH, KFMG and WHYR all
    came back "not audio: text/html" while playing perfectly.
    """
    return url.rstrip("/") + "/;"


def probe_twice(url: str, timeout: float) -> dict:
    """A verdict, with a retry and a Shoutcast fallback.

    One timeout is not a dead station, and an HTML page at the root is not
    a dead station either -- so a body that came back as HTML is re-asked
    at the Shoutcast mount before the station is written off.
    """
    result = probe(url, timeout)
    if result["verdict"] != "dead":
        return result
    if "not audio: text/html" in result["detail"]:
        mounted = probe(_shoutcast_mount(url), timeout)
        if mounted["verdict"] != "dead":
            mounted["detail"] = f"{mounted['detail']} (at {_shoutcast_mount(url)})"
            mounted["repaired_url"] = _shoutcast_mount(url)
            return mounted
    return probe(url, timeout)


def _previous_dead(path: Path) -> list[dict]:
    """The dead list from the last sweep, or nothing on a first run."""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("dead", [])


def rows_to_check(only: str) -> list[dict]:
    rows: list[dict] = []
    if only in {"all", "curated"}:
        for row in json.loads(CURATED_PATH.read_text(encoding="utf-8"))["stations"]:
            row = dict(row)
            row["_tier"] = "curated"
            rows.append(row)
    if only in {"all", "imported"} and IMPORTED_PATH.exists():
        for row in json.loads(IMPORTED_PATH.read_text(encoding="utf-8"))["stations"]:
            row = dict(row)
            row["_tier"] = "imported"
            rows.append(row)
    return [
        row for row in rows if (row.get("stream_url") or "").startswith(("http://", "https://"))
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=("all", "curated", "imported"), default="all")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--limit", type=int, default=0, help="probe only the first N (smoke test)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--recheck-dead",
        action="store_true",
        help="probe only the stations the existing health file calls dead",
    )
    args = parser.parse_args(argv)

    rows = rows_to_check(args.only)
    if args.recheck_dead:
        if not args.output.exists():
            parser.error(f"no health file to recheck: {args.output}")
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        dead_ids = {entry["id"] for entry in previous["dead"]}
        rows = [row for row in rows if row["id"] in dead_ids]
    if args.limit:
        rows = rows[: args.limit]

    print(f"Probing {len(rows)} streams with {args.workers} workers...", flush=True)
    results: list[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe_twice, row["stream_url"], args.timeout): row for row in rows}
        for future, row in futures.items():
            outcome = future.result()
            done += 1
            if done % 250 == 0:
                print(f"  {done}/{len(rows)}", flush=True)
            results.append(
                {
                    "id": row["id"],
                    "name": row.get("name", ""),
                    "call_sign": row.get("call_sign", ""),
                    "tier": row["_tier"],
                    "source_type": row.get("source_type", ""),
                    "stream_url": row["stream_url"],
                    **outcome,
                }
            )

    # Carry forward casualties from earlier sweeps. Once a row is dropped
    # from the built catalog it is no longer there to probe, so a report
    # written from scratch would forget it, and the next build would put it
    # straight back on the dial. A station leaves this list only by being
    # probed again and answering -- which is what --recheck-dead is for.
    probed = {r["id"] for r in results}
    carried = [row for row in _previous_dead(args.output) if row["id"] not in probed]
    dead = sorted(
        [r for r in results if r["verdict"] == "dead"] + carried,
        key=lambda r: (r["tier"], r["name"]),
    )
    # Stations that only answered at the Shoutcast mount: alive, but the
    # URL in the data points at the status page. These want editing, not
    # dropping, so they are reported apart from the casualties.
    previous_repairs = []
    if args.output.exists():
        previous_repairs = [
            row
            for row in json.loads(args.output.read_text(encoding="utf-8")).get("repaired", [])
            if row["id"] not in probed
        ]
    repaired = sorted(
        [r for r in results if r.get("repaired_url")] + previous_repairs,
        key=lambda r: (r["tier"], r.get("name", "")),
    )
    counts = {
        verdict: sum(1 for r in results if r["verdict"] == verdict)
        for verdict in ("ok", "playlist", "dead")
    }
    print(f"\n{counts}")
    print(f"  curated dead:  {sum(1 for r in dead if r['tier'] == 'curated')}")
    print(f"  imported dead: {sum(1 for r in dead if r['tier'] == 'imported')}")
    print(f"  alive only at the Shoutcast mount (URL wants editing): {len(repaired)}")

    args.output.write_text(
        json.dumps(
            {
                "schema": 1,
                "notes": (
                    "Stream reachability, written by tools/check_radio_streams.py. "
                    "tools/import_radio_catalog.py drops the imported ids listed "
                    "here; curated casualties are marked supported: false by hand "
                    "with a note. Re-probe with --recheck-dead before deleting "
                    "anything: a station can come back."
                ),
                "counts": counts,
                "repaired": [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "tier": r["tier"],
                        "stream_url": r["stream_url"],
                        "repaired_url": r["repaired_url"],
                    }
                    for r in repaired
                ],
                "dead": [
                    {
                        "id": r["id"],
                        "name": r.get("name", ""),
                        "tier": r["tier"],
                        "stream_url": r.get("stream_url", ""),
                        "detail": r.get("detail", ""),
                    }
                    for r in dead
                ],
            },
            indent=1,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
