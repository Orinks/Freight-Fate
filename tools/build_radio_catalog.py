"""Build the in-cab radio station catalog from open source data.

The game ships a checked-in catalog; this tool is how that file is produced
and refreshed. It joins three inputs:

* **Radio Browser** (``radiobrowser_us_stations.json``) -- the only source for
  a public stream URL. Free and open, no key, mirroring permitted.
* **Wikidata** (``wikidata_us_stations.json``, CC0) -- transmitter coordinates
  and broadcast frequency, joined on the FCC call sign parsed out of the Radio
  Browser station name. Radio Browser's own coordinates cover only about a
  fifth of US stations; Wikidata's cover about nine tenths.
* An optional **overlay** (``--overlay``) -- a curated list that wins over the
  automatic join, for stations whose stream URL or coverage is known better by
  hand than by the sources above.

Stations that carry a call sign and a transmitter position become *local*
stations: they are only receivable near that transmitter. Everything else
becomes a *web* station, receivable anywhere, plus one always-available
*satellite* station.

Coverage radius is a game constant today (see ``FM_RADIUS_MI`` /
``AM_RADIUS_MI``), recorded per station as ``radius_source: "default"``.
Real FCC contour data would replace it per station with
``radius_source: "fcc"`` without changing the format.

The source dumps live in the gitignored ``data/radio-cache/`` directory; see
its ``MANIFEST.md`` for what each one is and how to refresh it.

Run from the repository root::

    uv run python tools/build_radio_catalog.py
    uv run python tools/build_radio_catalog.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "radio-cache"
DEFAULT_RADIOBROWSER = CACHE_DIR / "radiobrowser_us_stations.json"
DEFAULT_WIKIDATA = CACHE_DIR / "wikidata_us_stations.json"
DEFAULT_OUTPUT = ROOT / "src" / "freight_fate" / "data" / "radio" / "stations.json"

CATALOG_VERSION = 1

# Coverage radii in statute miles. Deliberate game constants, not FCC figures:
# the FCC's own contour data is not machine-retrievable (every fcc.gov host
# refuses scripted access), so until a facility file is imported by hand every
# station is given the radius for its band. Measured against the game's 623
# cities, these put at least one local station in reach of 83 percent of them,
# median three -- close enough to real driving that the dial keeps changing,
# and the satellite station covers the rest.
FM_RADIUS_MI = 40.0
AM_RADIUS_MI = 90.0

# Always in range, and the fallback whenever a stream fails. AFN's internet
# radio is publicly streamable; see ROADMAP.md for the sourcing note.
SATELLITE_STATIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "afn-360-pacific",
        "name": "AFN 360 Pacific",
        "band": "satellite",
        "url": ("https://playerservices.streamtheworld.com/api/livestream-redirect/AFNP_OKN_SC"),
        "codec": "MP3",
        "tags": "military, variety, news",
    },
)

# FCC call signs are three or four letters starting with K or W, optionally
# followed by an -FM/-AM suffix. Anchored on word boundaries so "KISS FM" in a
# branding string does not read as call sign "KISS".
_CALL_SIGN = re.compile(r"\b([KW][A-Z]{2,3})(?:[- ]?(FM|AM))?\b")

# Broadcast bands. FM is quoted in megahertz, AM in kilohertz, but the source
# data mixes in a few values scaled to hertz, so a value is divided down until
# it could plausibly be one of the two.
_FM_MHZ = (87.0, 108.5)
_AM_KHZ = (520.0, 1710.0)


def _clean_name(raw: str) -> str:
    """A station name that is safe to speak.

    Contributor-typed names carry tabs, newlines, zero-width joiners, emoji and
    mojibake. A screen reader reads all of it, so anything that is not a
    letter, digit, mark or ordinary punctuation is dropped and the remaining
    whitespace collapsed. This is hygiene, not curation: no station is excluded
    for what it broadcasts.
    """
    text = unicodedata.normalize("NFKC", raw or "")
    kept = [
        ch
        for ch in text
        if unicodedata.category(ch)[0] in ("L", "N", "M", "P")
        or unicodedata.category(ch) in ("Sm", "Sc")
        or ch.isspace()
    ]
    return re.sub(r"\s+", " ", "".join(kept)).strip(" -|/,")


# Stream-technical noise contributors put in station names. None of it means
# anything to a listener, and all of it gets read out loud.
_NOISE_WORDS = re.compile(
    r"\b(?:aac\+?|mp3|ogg|opus|flac|hd\d?|hi-?fi|stereo|kbps|kbit|"
    r"\d{2,3}\s?k(?:bps)?|live|stream(?:ing)?|radio\s*stream)\b",
    re.IGNORECASE,
)
# A dial position the readout already gave. Only two shapes are stripped: one
# leading the name (what is left of "WGAO 88.1 Power 88" once the call sign
# goes), and one spelled out with its band. A bare number inside the name is
# left alone -- "Power 88" and "Hot 96.9" are what the station calls itself.
_LEADING_FREQUENCY = re.compile(r"^\s*\d{2,4}(?:\.\d)?\s*(?:fm|am|mhz|khz)?\b", re.IGNORECASE)
_BANDED_FREQUENCY = re.compile(r"\b\d{2,4}(?:\.\d)?\s*(?:fm|am|mhz|khz)\b", re.IGNORECASE)


# Contributors pack an owner, a city and a slogan into one name, separated by
# a pipe or a run of dashes. Only the first piece is the station's own name.
_NAME_SPLIT = re.compile(r"\s*(?:\||-\s*-\s*-|/{2,})\s*")
# Past this many characters a name stops being an identity and starts being a
# paragraph the driver has to sit through on every seek.
_MAX_NAME_CHARS = 60


def _short_name(raw: str, call_sign: str) -> str:
    """The station's name with what the readout already says taken out.

    A broadcast station is announced as call sign, then dial position, then
    name, so a name like "WGAO 88.1 Power 88 (AAC)" repeats both and adds the
    codec on top. What is left after the duplication goes is the branding,
    which is the part a listener wants. An empty result means the name carried
    nothing the readout did not already say, and the caller falls back to the
    call sign.
    """
    name = _NAME_SPLIT.split(_clean_name(raw))[0].strip()
    if call_sign:
        # Both forms: the catalog may hold "KNCT-FM" while the name says "KNCT".
        for form in (call_sign, call_sign.split("-")[0]):
            name = re.sub(
                rf"\b{re.escape(form)}(?:[- ]?(?:FM|AM|LP|HD\d?))?\b", " ", name, flags=re.I
            )
        name = _NOISE_WORDS.sub(" ", name)
        name = _BANDED_FREQUENCY.sub(" ", name)
        name = _LEADING_FREQUENCY.sub(" ", name.lstrip(" -|/,:;"))
    name = name.replace('"', " ").replace("'", " ")
    # Brackets can be left holding nothing once the call sign inside them goes.
    name = re.sub(r"[(\[][^A-Za-z0-9]*[)\]]", " ", name)
    name = re.sub(
        r"\b(?:a service of|brought to you by|owned by)\b\s*[(\[]?\s*[)\]]?", " ", name, flags=re.I
    )
    name = re.sub(r"\s+", " ", name).strip(" -|/,:;\"'()[]")
    if len(name) > _MAX_NAME_CHARS:
        head = name[:_MAX_NAME_CHARS]
        cut = max(head.rfind(","), head.rfind(" - "))
        name = (head[:cut] if cut > 20 else head).strip(" -,:;")
    return name


def _format_tags(raw: str) -> str | None:
    """Up to three genre words, for the station's spoken format.

    Radio Browser tags are an alphabetical free-for-all -- one station carries
    forty-eight of them, starting with the decades it plays. Read out in full
    that is unusable, so purely numeric tags are dropped and the first three of
    the rest are kept.
    """
    tags = [_clean_name(tag).lower() for tag in (raw or "").split(",")]
    words = [tag for tag in tags if tag and not tag.isdigit()]
    return ", ".join(words[:3]) or None


def _band_and_frequency(raw: Any) -> tuple[str | None, float | None]:
    """Classify a Wikidata frequency value as FM (MHz) or AM (kHz)."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, None
    for _ in range(4):  # a few records are quoted in hertz
        if value <= _AM_KHZ[1] * 1.5 or _FM_MHZ[0] <= value <= _FM_MHZ[1]:
            break
        value /= 1000.0
    if _FM_MHZ[0] <= value <= _FM_MHZ[1]:
        return "FM", round(value, 1)
    if _AM_KHZ[0] <= value <= _AM_KHZ[1]:
        return "AM", round(value)
    return None, None


def _sparql_value(row: dict, key: str) -> str | None:
    cell = row.get(key)
    return cell.get("value") if isinstance(cell, dict) else None


def _parse_point(wkt: str | None) -> tuple[float, float] | None:
    """Latitude/longitude from a GeoSPARQL ``Point(lon lat)`` literal."""
    if not wkt or not wkt.startswith("Point("):
        return None
    try:
        lon, lat = wkt[6:-1].split()
        return float(lat), float(lon)
    except ValueError:
        return None


def load_wikidata(path: Path) -> dict[str, dict]:
    """Call sign -> transmitter record, keyed by the full call sign.

    Base call signs ("WABC") are indexed too so a Radio Browser name without a
    band suffix still resolves, but an exact suffixed key always wins: an AM
    station and its FM sibling are two stations on two frequencies.
    """
    rows = json.loads(path.read_text(encoding="utf-8"))
    index: dict[str, dict] = {}
    for row in rows:
        call_sign = (_sparql_value(row, "callsign") or "").upper().strip()
        point = _parse_point(_sparql_value(row, "coord"))
        if not call_sign or point is None:
            continue
        band, frequency = _band_and_frequency(_sparql_value(row, "freq"))
        record = {
            "call_sign": call_sign,
            "lat": round(point[0], 5),
            "lon": round(point[1], 5),
            "band": band,
            "frequency": frequency,
        }
        index.setdefault(call_sign, record)
        base = call_sign.split("-")[0]
        # Prefer a variant that actually carries a frequency for the bare key.
        existing = index.get(base)
        if existing is None or (existing.get("band") is None and band is not None):
            index[base] = record
    return index


def _match_transmitter(name: str, wikidata: dict[str, dict]) -> dict | None:
    """The transmitter record for a station name, or None if it has no call sign."""
    match = _CALL_SIGN.search(name.upper())
    if match is None:
        return None
    base, suffix = match.group(1), match.group(2)
    for key in ([f"{base}-{suffix}"] if suffix else []) + [base]:
        record = wikidata.get(key)
        if record is not None and record.get("band"):
            return record
    return None


def _stream_url(station: dict) -> str:
    return (station.get("url_resolved") or station.get("url") or "").strip()


def _votes(station: dict) -> int:
    try:
        return int(station.get("votes") or 0)
    except (TypeError, ValueError):
        return 0


def _is_hls(station: dict) -> bool:
    """HLS (.m3u8) playlists; the BASS backend cannot open them.

    Radio Browser's own ``hls`` flag misses some, so the URL is checked too:
    a station flagged 0 whose stream is still an .m3u8 playlist would ship and
    then fail to play for every player who tuned it.
    """
    if station.get("hls") in (1, "1", True):
        return True
    url = _stream_url(station).lower().split("?", 1)[0]
    return url.endswith(".m3u8")


def build(
    radiobrowser_path: Path,
    wikidata_path: Path,
    overlay_path: Path | None = None,
) -> dict:
    """Join the sources into the catalog document."""
    stations = json.loads(radiobrowser_path.read_text(encoding="utf-8"))
    wikidata = load_wikidata(wikidata_path)

    local: dict[str, dict] = {}  # call sign -> best entry
    web: dict[str, dict] = {}  # stream url -> best entry
    skipped = {"hls": 0, "no_url": 0, "no_name": 0}

    for station in stations:
        if _is_hls(station):
            skipped["hls"] += 1
            continue
        url = _stream_url(station)
        if not url:
            skipped["no_url"] += 1
            continue
        name = _clean_name(station.get("name") or "")
        if not name:
            skipped["no_name"] += 1
            continue

        record = {
            "id": station.get("stationuuid") or url,
            "name": name,
            "url": url,
            "codec": (station.get("codec") or "").upper() or None,
            "bitrate": station.get("bitrate") or None,
            "tags": _format_tags(station.get("tags") or ""),
            "votes": _votes(station),
        }

        transmitter = _match_transmitter(station.get("name") or "", wikidata)
        if transmitter is None:
            keep = web.get(url)
            if keep is None or record["votes"] > keep["votes"]:
                record["band"] = "web"
                web[url] = record
            continue

        # One call sign is one place on the dial; keep the best-voted stream.
        call_sign = transmitter["call_sign"]
        keep = local.get(call_sign)
        if keep is not None and record["votes"] <= keep["votes"]:
            continue
        record.update(
            {
                # Falling back to the call sign makes the readout skip the
                # name entirely, which is right when it said nothing new.
                "name": _short_name(station.get("name") or "", call_sign) or call_sign,
                "call_sign": call_sign,
                "band": transmitter["band"],
                "frequency": transmitter["frequency"],
                "lat": transmitter["lat"],
                "lon": transmitter["lon"],
                "radius_mi": (FM_RADIUS_MI if transmitter["band"] == "FM" else AM_RADIUS_MI),
                "radius_source": "default",
            }
        )
        local[call_sign] = record

    overlay_applied = 0
    if overlay_path is not None:
        overlay_applied = _apply_overlay(overlay_path, local, web)

    catalog = {
        "version": CATALOG_VERSION,
        "defaults": {"fm_radius_mi": FM_RADIUS_MI, "am_radius_mi": AM_RADIUS_MI},
        "sources": {
            "streams": "Radio Browser (radio-browser.info), open data",
            "transmitters": "Wikidata (wikidata.org), CC0",
        },
        # Local stations sit in dial order; web stations lead with the ones
        # most listeners picked, which is the order seek should walk.
        "local": [
            _finalize(r)
            for r in sorted(
                local.values(),
                key=lambda r: (r["band"], r.get("frequency") or 0.0, r["call_sign"]),
            )
        ],
        "web": [
            _finalize(r)
            for r in sorted(
                web.values(),
                key=lambda r: (-r["votes"], r["name"], r["id"]),
            )
        ],
        "satellite": [dict(s) for s in SATELLITE_STATIONS],
    }
    catalog["counts"] = {
        "local": len(catalog["local"]),
        "web": len(catalog["web"]),
        "satellite": len(catalog["satellite"]),
        "skipped": skipped,
        "overlay_applied": overlay_applied,
    }
    return catalog


def _finalize(record: dict) -> dict:
    """Drop the sort-only vote count and any empty fields from a record."""
    return {k: v for k, v in record.items() if k != "votes" and v not in (None, "")}


def _apply_overlay(path: Path, local: dict[str, dict], web: dict[str, dict]) -> int:
    """Merge a curated station list over the automatic join.

    The overlay is a JSON list of partial station records. An entry with a
    ``call_sign`` updates (or adds) that local station; anything else is a web
    station keyed by ``url``. Curated values always win, so a hand-checked
    stream URL or a real measured radius survives a rebuild.
    """
    entries = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(entries, dict):
        entries = entries.get("stations", [])
    applied = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        call_sign = (entry.get("call_sign") or "").upper().strip()
        if call_sign:
            target = local.setdefault(call_sign, {"votes": 0, "call_sign": call_sign})
        else:
            url = (entry.get("url") or "").strip()
            if not url:
                continue
            target = web.setdefault(url, {"votes": 0, "band": "web", "id": url})
        target.update({k: v for k, v in entry.items() if v is not None})
        target.setdefault("id", call_sign or entry.get("url"))
        applied += 1
    return applied


def render(catalog: dict) -> str:
    """The catalog exactly as it is written to disk."""
    return json.dumps(catalog, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radiobrowser", type=Path, default=DEFAULT_RADIOBROWSER)
    parser.add_argument("--wikidata", type=Path, default=DEFAULT_WIKIDATA)
    parser.add_argument(
        "--overlay",
        type=Path,
        default=None,
        help="curated station list that wins over the automatic join",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the checked-in catalog matches the sources; write nothing",
    )
    args = parser.parse_args(argv)

    for path in (args.radiobrowser, args.wikidata):
        if not path.exists():
            parser.error(
                f"missing source dump: {path}\n"
                "See data/radio-cache/MANIFEST.md for how to fetch it."
            )

    catalog = build(args.radiobrowser, args.wikidata, args.overlay)
    text = render(catalog)

    if args.check:
        if not args.output.exists():
            print(f"Catalog is missing: {args.output}", file=sys.stderr)
            return 1
        if args.output.read_text(encoding="utf-8") != text:
            print(
                f"Catalog is out of date: {args.output}\n"
                "Re-run: uv run python tools/build_radio_catalog.py",
                file=sys.stderr,
            )
            return 1
        print(f"Catalog is up to date ({catalog['counts']})")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(f"Wrote {args.output} ({catalog['counts']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
