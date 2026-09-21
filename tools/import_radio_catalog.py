"""Convert PR #150's automated station catalog into the imported dial tier.

The curated catalog (``radio_catalog.json``) is hand-maintained and always
wins. This tool layers the automated Radio Browser x Wikidata join built by
CatalystForChaos in PR #150 underneath it as ``radio_imported.json``: real
terrestrial broadcast stations with transmitter coordinates, receivable only
near their transmitter, every one gated behind the real-streams switch and
hidden in streamer-safe mode.

The ``local`` tier becomes geo-ranged terrestrial stations; the ``web`` tier
becomes an always-available "Web radio" dial band, kept in the source file's
listener-vote order so seeking into the band hears the popular ones first.
The satellite tier is skipped: it duplicates the curated AFN lineup.

An imported station whose call sign matches a curated station's call sign is
dropped here (and again at load time, in case the curated file grows between
rebuilds): one call sign is one place on the dial, and the curated entry
carries data this join cannot supply.

Run from the repository root::

    uv run python tools/import_radio_catalog.py
    uv run python tools/import_radio_catalog.py --check

Three cached inputs, all gitignored, all rebuildable:

``data/radio-cache/pr150_stations.json``
    The ``stations.json`` from PR #150. Re-fetch from the PR branch with
    ``git show pr150:src/freight_fate/data/radio/stations.json``.

``data/radio-cache/rb_us.json``
    A Radio Browser US snapshot, the source of the FCC-placed terrestrial
    stations. Rebuild with a search for ``countrycode=US&hidebroken=true``
    against ``de1.api.radio-browser.info``, ordered by clickcount.

``data/radio-cache/fcc_transmitters.json``
    Licensed transmitter sites. Rebuild with
    ``uv run python tools/fetch_fcc_transmitters.py``.

Two checked-in inputs, not cached:

``data/radio_stream_health.json``
    What ``tools/check_radio_streams.py`` last found: it keeps dead streams
    off the dial between sweeps, and carries the repaired address of a
    station that moved.

``data/radio_imported_overrides.json``
    The hand curation no rule derives -- a name the source mangled past any
    cleaner, a format its keyword tags do not give, a station the directory
    lists twice. Everything here is applied on top of what this tool builds,
    so a rebuild stops undoing a curator's judgement. An entry whose station
    is no longer built fails the run rather than sitting there unread.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "radio-cache" / "pr150_stations.json"
CURATED_PATH = ROOT / "data" / "radio_catalog.json"
DEFAULT_OUTPUT = ROOT / "data" / "radio_imported.json"
HEALTH_PATH = ROOT / "data" / "radio_stream_health.json"
OVERRIDES_PATH = ROOT / "data" / "radio_imported_overrides.json"
RADIO_BROWSER_PATH = ROOT / "data" / "radio-cache" / "rb_us.json"
FCC_PATH = ROOT / "data" / "radio-cache" / "fcc_transmitters.json"

RADIO_BROWSER_SOURCE_TEXT = "community radio directory, FCC transmitter site"

# Spoken in station lists and status lines; player language, no tooling names.
IMPORTED_SOURCE_TEXT = "community radio directory"

# Stream-technical noise in contributor-typed web station names ("(EU) 320k
# AAC"). None of it means anything to a listener, and a screen reader speaks
# all of it on every seek. Ported from PR #150's name hygiene, which the
# source file only applied to call-sign stations.
_NOISE_WORDS = re.compile(
    r"\b(?:aac\+?|mp3|ogg|opus|flac|hls|hd\d?|hi-?fi|stereo|kbps|kbit|"
    r"\d{2,3}\s?k(?:bps|bit|b)?|stream(?:ing)?)\b",
    re.IGNORECASE,
)
_NAME_SPLIT = re.compile(r"\s*(?:\||-\s*-\s*-|/{2,})\s*")
_MAX_NAME_CHARS = 60


def drop_unclosed_parenthetical(name: str) -> str:
    """ "NPR Syracuse University, NY (New" -> "NPR Syracuse University, NY".

    An unclosed parenthetical is a maintainer's note that got away --
    "KFLP All Agriculture (new link 2/2025" -- not part of the name, and a
    screen reader reads the stub out with it. Where the truncated text is
    worth keeping the closing bracket is put back by hand instead; see
    radio_imported_overrides.json.
    """
    if name.count("(") > name.count(")"):
        return name[: name.rindex("(")]
    return name


def restore_possessives(name: str) -> str:
    """ "Birmingham s Beautiful QEZ" -> "Birmingham's Beautiful QEZ".

    The upstream directory stripped every apostrophe, and the names were
    read aloud that way. A lone lowercase s after a word, with more name to
    follow, is the possessive it used to be. Both tiers carry these: the web
    tier has had the repair since it was written, the local tier read
    "Hampton s Jazz" out for a release longer.
    """
    return re.sub(r"\b([A-Za-z]{2,}) s\b(?=\s)", r"\1's", name)


def clean_web_name(raw: str) -> str:
    """A web station name with the stream jargon taken out."""
    name = _NAME_SPLIT.split(raw.strip())[0]
    name = _NOISE_WORDS.sub(" ", name)
    name = re.sub(r"[(\[][^A-Za-z0-9]*[)\]]", " ", name)
    name = restore_possessives(name)
    name = re.sub(r"\s+", " ", name).strip(" -|/,:;")
    if len(name) > _MAX_NAME_CHARS:
        head = name[:_MAX_NAME_CHARS]
        cut = max(head.rfind(","), head.rfind(" - "))
        name = (head[:cut] if cut > 20 else head).strip(" -,:;")
    return name or raw.strip()


def call_sign_base(call_sign: str) -> str:
    """The call sign without a -FM/-AM suffix: WNYC-FM and WNYC are one station."""
    return call_sign.split("-")[0].strip().upper()


def curated_call_signs(curated: dict) -> set[str]:
    # Minus the empty string: curated web stations are named, not lettered,
    # and "no call sign" must never reserve every call-sign-less import.
    return {call_sign_base(row.get("call_sign", "")) for row in curated["stations"]} - {""}


# normalize_stream_url and canonical_stream_url mirror ff_core::radio: this
# build-time collision check and the game's dial (which collapses a multi-site
# station like KZYX or WNPN to a single listing) must agree on what counts as
# "the same stream". Change one, change both.

_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.\-]*://", re.IGNORECASE)

# Live365 hands the same station out under its own name and under whichever
# CDN edge answered that day (ais-sa5.cdnstream1.com, das-edge14-live365-
# dal02.cdnstream.com, the legacy edge4.peta.live365.net), and at several
# bitrates off one station id. The mount name carries the id, so the id is
# the station: b09584_128mp3 and b09584_64aac are one station at two
# bitrates, not two stations.
_LIVE365_HOST_RE = re.compile(
    r"^(?:streaming\.live365\.com"
    r"|(?:ais|das)-[\w.-]*\.cdnstream1?\.com"
    r"|[\w-]+\.peta\.live365\.net)$",
    re.IGNORECASE,
)
_LIVE365_MOUNT_RE = re.compile(r"^([ab]\d{4,7})(?:_[0-9a-z]+)?$", re.IGNORECASE)
_LIVE365_CANONICAL_HOST = "streaming.live365.com"


def normalize_stream_url(url: str) -> str:
    """A stream URL with scheme and a trailing slash stripped, for dedup only.

    The same live stream is sometimes registered under both ``http://`` and
    ``https://`` (and sometimes with a bare trailing slash); an exact-string
    comparison treats those as different streams and let one station land on
    the dial twice under two names (WHYY 90.9, 2026-08-12 field report).
    Scheme and host are case-insensitive by spec, so only that part is
    folded -- a genuinely case-sensitive path is never merged with a
    different one. Live365 mounts fold further, onto the station id in the
    mount name: the directory carries the same station under several CDN
    edge hosts and bitrates, which put Radiostorm's At Work, Oldies and
    Comedy channels on the web band twice each. Never stored or spoken --
    comparison only. Mirrors ``ff_core::radio::normalize_stream_url`` so this build-time
    collision check and the game agree on what counts as "the same
    stream".
    """
    url = url.strip()
    match = _URL_SCHEME_RE.match(url)
    if match:
        url = url[match.end() :]
    url = url.rstrip("/")
    host, _, rest = url.partition("/")
    host = host.lower()
    if _LIVE365_HOST_RE.match(host):
        mount = _LIVE365_MOUNT_RE.match(rest.partition("?")[0])
        if mount:
            return f"{_LIVE365_CANONICAL_HOST}/{mount.group(1).lower()}"
    return f"{host}/{rest}" if rest else host


def canonical_stream_url(url: str) -> str:
    """A Live365 stream pointed at Live365's own address, not one CDN edge.

    The directory records whichever edge host answered the day it checked
    (``ais-edge104-live365-dal02.cdnstream.com``), sometimes carrying the
    checker's own player and ad-block tokens in the query. Those hostnames
    come and go; ``streaming.live365.com`` is the address the station
    publishes, and it redirects to a live edge at play time. Anything that
    is not a Live365 mount is returned exactly as it came in.
    """
    match = _URL_SCHEME_RE.match(url.strip())
    rest = url.strip()[match.end() :] if match else url.strip()
    host, _, path = rest.partition("/")
    if not _LIVE365_HOST_RE.match(host.lower()):
        return url
    mount = path.partition("?")[0].rstrip("/")
    if not _LIVE365_MOUNT_RE.match(mount):
        return url
    return f"https://{_LIVE365_CANONICAL_HOST}/{mount}"


# Leftovers the source file's name cleaning can strand at the front of a
# local station's name once a sibling frequency or call sign is stripped:
# conjunctions, separators, and dial positions written band-first ("FM 95.7"),
# which its number-first patterns never matched. Branding like "Jack FM 107.1"
# stays: only names that LEAD with junk, or contain nothing else, change.
_LEADING_JUNK = re.compile(r"^\s*(?:[&,\-/|:;]+|and\b)\s*", re.IGNORECASE)
_DIAL_ONLY = re.compile(r"^\s*(?:(?:FM|AM)?\s*\d{2,4}(?:\.\d)?\s*(?:FM|AM)?[\s&,\-/]*)+$", re.I)
_LEADING_BARE_FREQ = re.compile(r"^\s*\d{2,4}(?:\.\d)?\s+")


def clean_local_name(raw: str) -> str:
    """A local station name with stranded leading junk taken out.

    Returns "" when nothing but dial positions is left; the caller falls back
    to the call sign, and the readout then speaks the call sign once.
    """
    name = drop_unclosed_parenthetical(re.sub(r"\s+", " ", raw).strip())
    while True:
        stripped = _LEADING_JUNK.sub("", name)
        if stripped == name:
            break
        name = stripped
    if _DIAL_ONLY.match(name):
        return ""
    # "& 104.3 Cutten, CA" -> "Cutten, CA": a bare frequency stranded at the
    # front by the junk strip duplicates nothing a listener needs first.
    bare = _LEADING_BARE_FREQ.sub("", name)
    if bare != name and bare:
        name = _LEADING_JUNK.sub("", bare)
    return restore_possessives(name.strip(" -|/,:;&"))


def convert_station(row: dict) -> dict:
    """One PR #150 local-tier record in the curated catalog's schema."""
    band = row["band"]
    tags = (row.get("tags") or "").strip()
    station = {
        "id": f"rb-{row['id']}",
        # Spoken as letters either way, but a dash in the middle is read as
        # the word "dash" by some screen readers.
        "call_sign": row["call_sign"].replace("-", " "),
        # An emptied name falls back to the call sign; display_name then
        # speaks the call sign once instead of twice.
        "name": clean_local_name(row["name"]) or row["call_sign"].replace("-", " "),
        "format": tags or f"{band} radio",
        "source": IMPORTED_SOURCE_TEXT,
        "source_type": "imported",
        "station_type": "imported",
        # A Live365 station is stored at Live365's own address, never at
        # the CDN edge host that happened to answer when this was checked.
        "stream_url": canonical_stream_url(row["url"]),
        "stream_format": (row.get("codec") or "").lower(),
        "lat": row["lat"],
        "lon": row["lon"],
        "range_miles": row["radius_mi"],
        # The licensing of a directory stream is unknown, so imported
        # stations ride the same gates as every real stream: hidden in
        # streamer-safe mode, off until real streams are switched on.
        "safe_for_streaming": False,
        "real_stream": True,
        "supported": True,
    }
    if band == "FM":
        station["frequency_mhz"] = float(row["frequency"])
    return station


def convert_web_station(row: dict) -> dict:
    """One PR #150 web-tier record: no transmitter, receivable anywhere."""
    tags = (row.get("tags") or "").strip()
    return {
        "id": f"rb-web-{row['id']}",
        # No call sign: web stations are named, not lettered. display_name
        # and the dial sort both handle the empty string, and the sort's
        # stability is what preserves the listener-vote order below.
        "call_sign": "",
        "name": clean_web_name(row["name"]),
        "format": tags or "web radio",
        "source": IMPORTED_SOURCE_TEXT,
        "source_type": "web",
        "station_type": "web",
        "stream_url": canonical_stream_url(row["url"]),
        "stream_format": (row.get("codec") or "").lower(),
        "safe_for_streaming": False,
        "real_stream": True,
        "always_available": True,
        "supported": True,
    }


# An FCC call sign as it appears inside a contributor-typed station name:
# "103.5 KISS FM - WKSC-FM Chicago", "99.7 The Fox ... WRFX".
_CALL_IN_NAME = re.compile(r"\b([KW][A-Z]{2,3})(?:-(?:FM|AM|LP|LD|TV|HD\d))?\b")

# The FCC's own service labels. Translators and boosters rebroadcast a
# parent station on a few hundred watts; they belong on the dial, but at
# the range they actually cover, not a full-power station's.
_TRANSLATOR_SERVICES = {"FX", "FB", "FS"}

# Coverage radius by licensed power, in miles. These are the rough
# distances the FCC's own class definitions work out to for the protected
# contour -- a Class A at 6 kW reaches about 17 miles, a Class C at 100 kW
# about 55. Coarse on purpose: it is a band, not a terrain model, and it
# replaces the flat 40 miles every imported station used to get, which put
# a 250-watt translator on the dial three counties away.
_RANGE_BY_ERP_MI = (
    (0.1, 8.0),
    (1.0, 15.0),
    (6.0, 22.0),
    (25.0, 32.0),
    (50.0, 42.0),
)
_MAX_FM_RANGE_MI = 55.0
_AM_RANGE_MI = 25.0


def range_for(erp_kw: float | None, service: str) -> float:
    """How far out a licensed transmitter should still be hearable."""
    if service == "AM":
        return _AM_RANGE_MI
    if erp_kw is None:
        # Unstated power on an FM record is almost always a translator.
        return 10.0 if service in _TRANSLATOR_SERVICES else 22.0
    for ceiling, miles in _RANGE_BY_ERP_MI:
        if erp_kw < ceiling:
            return miles
    return _MAX_FM_RANGE_MI


def call_signs_in(name: str) -> list[str]:
    """Every call-sign-shaped token in a station name, in order.

    Station names carry brands shaped exactly like call signs -- "103.5
    KISS FM - WKSC-FM Chicago" offers KISS before it offers the real
    WKSC -- so the caller checks each against the licensed list rather
    than trusting the first hit.
    """
    return [match.group(1) for match in _CALL_IN_NAME.finditer(name.upper())]


def clean_terrestrial_name(raw: str) -> str:
    """A directory station's name with the stream jargon taken out first.

    Two things ride on this. The obvious one is that a screen reader should
    not read "(AAC+ Stream)" or "128 kbps mp3" out on every seek. The
    quieter one is that the jargon contains call-sign-shaped text: KBPS is
    a real Portland station, and "Ambient Sleeping Pill | 128 kbps mp3"
    was placed at its transmitter on the strength of the bitrate. Clean
    first, then read the call sign out of what is left.
    """
    name = _NOISE_WORDS.sub(" ", _NAME_SPLIT.split(raw.strip())[0])
    name = drop_unclosed_parenthetical(name)
    name = re.sub(r"\s+", " ", name).strip(" -|/,:;")
    return clean_local_name(name) or name


def convert_terrestrial(row: dict, site: dict) -> dict:
    """One Radio Browser station placed at its licensed transmitter site."""
    call_sign = site["call_sign"].replace("-", " ")
    tags = (row.get("tags") or "").strip()
    station = {
        "id": f"rb-fcc-{row['stationuuid']}",
        "call_sign": call_sign,
        "name": clean_terrestrial_name(row["name"]) or call_sign,
        "format": tags or ("AM radio" if site["service"] == "AM" else "FM radio"),
        "source": RADIO_BROWSER_SOURCE_TEXT,
        "source_type": "imported",
        "station_type": "imported",
        "stream_url": canonical_stream_url(row.get("url_resolved") or row["url"]),
        "stream_format": (row.get("codec") or "").lower(),
        "lat": site["lat"],
        "lon": site["lon"],
        "range_miles": range_for(site.get("erp_kw"), site["service"]),
        "market": site.get("community", ""),
        "state": site.get("state", ""),
        "safe_for_streaming": False,
        "real_stream": True,
        "supported": True,
    }
    frequency = (site.get("frequency") or "").split()
    if frequency and site["service"] != "AM":
        with contextlib.suppress(ValueError):
            station["frequency_mhz"] = float(frequency[0])
    return station


def terrestrial_rows(directory: list[dict], transmitters: dict) -> list[dict]:
    """Radio Browser US stations that resolve to a licensed transmitter.

    The existing local tier came from a Wikidata join, which only knows the
    stations Wikidata happens to cover and skews heavily to public radio.
    This widens it with the commercial music side of the dial -- the
    country, classic rock and hits stations a driver actually scans for --
    by reading the FCC call sign out of the station's own name and looking
    up where that transmitter stands.
    """
    rows = []
    for row in directory:
        name = clean_terrestrial_name(row.get("name", ""))
        site = next(
            (
                transmitters[call_sign]
                for call_sign in call_signs_in(name)
                if call_sign in transmitters
            ),
            None,
        )
        if site:
            rows.append(convert_terrestrial(row, site))
    return rows


def stream_health(path: Path) -> tuple[set[str], dict[str, str]]:
    """What the last reachability sweep found: dead ids, and repaired URLs.

    A station whose stream is gone is worse on the dial than one that was
    never there: tuning to it costs a screen reader user the tune, the
    wait, and a fallback hand-off. Rows the sweep could not reach are left
    out of the build entirely. Rows that only answered at their Shoutcast
    ``/;`` mount are kept, at that URL.
    """
    if not path.exists():
        return set(), {}
    health = json.loads(path.read_text(encoding="utf-8"))
    dead = {row["id"] for row in health.get("dead", []) if row.get("tier") == "imported"}
    repaired = {
        row["id"]: row["repaired_url"]
        for row in health.get("repaired", [])
        if row.get("tier") == "imported"
    }
    return dead, repaired


def hand_curation(path: Path) -> tuple[dict[str, dict], set[str]]:
    """The hand edits this build cannot derive: per-station fields, and drops.

    Some station names and formats are a judgement, not a rule -- a name the
    source mangled past any cleaner, or a station the directory lists twice
    under two hostnames. Those live in a checked-in file rather than as
    edits to the built catalog, so a rebuild stops undoing them.
    """
    if not path.exists():
        return {}, set()
    doc = json.loads(path.read_text(encoding="utf-8"))
    fields = {
        station_id: {key: value for key, value in row.items() if key != "why"}
        for station_id, row in doc.get("overrides", {}).items()
    }
    return fields, {row["id"] for row in doc.get("dropped", [])}


def apply_overrides(station: dict, overrides: dict[str, dict]) -> dict:
    """`station` with its hand-curated fields written over the built ones."""
    override = overrides.get(station["id"])
    if override:
        station.update(override)
    return station


def build(
    source: dict,
    curated: dict,
    health: tuple[set[str], dict[str, str]] = (set(), {}),
    terrestrial: list[dict] | None = None,
    curation: tuple[dict[str, dict], set[str]] = ({}, set()),
) -> dict:
    dead_ids, repaired_urls = health
    overrides, dropped_ids = curation
    reserved = curated_call_signs(curated)
    curated_urls = {
        normalize_stream_url(row.get("stream_url") or "")
        for row in curated["stations"]
        if row.get("stream_url")
    }
    stations = []
    dropped = 0
    seen_urls = set(curated_urls)
    dead_dropped = 0
    hand_dropped = 0
    for row in source["local"]:
        station = apply_overrides(convert_station(row), overrides)
        station["stream_url"] = repaired_urls.get(station["id"], station["stream_url"])
        if station["id"] in dropped_ids:
            hand_dropped += 1
            continue
        if station["id"] in dead_ids:
            dead_dropped += 1
            continue
        key = normalize_stream_url(station["stream_url"])
        if call_sign_base(row["call_sign"]) in reserved or key in seen_urls:
            dropped += 1
            continue
        seen_urls.add(key)
        stations.append(station)
    # The FCC-placed directory stations join the same local tier, under
    # the same rules: a curated call sign still wins, and a stream already
    # on the dial is still one station.
    added_terrestrial = 0
    for station in terrestrial or []:
        apply_overrides(station, overrides)
        station["stream_url"] = repaired_urls.get(station["id"], station["stream_url"])
        if station["id"] in dropped_ids:
            hand_dropped += 1
            continue
        key = normalize_stream_url(station["stream_url"])
        if call_sign_base(station["call_sign"]) in reserved or key in seen_urls:
            dropped += 1
            continue
        if station["id"] in dead_ids:
            dead_dropped += 1
            continue
        seen_urls.add(key)
        reserved.add(call_sign_base(station["call_sign"]))
        stations.append(station)
        added_terrestrial += 1
    stations.sort(key=lambda s: (s["call_sign"], s["id"]))
    web_dropped = 0
    for row in source["web"]:  # already in listener-vote order; keep it
        station = apply_overrides(convert_web_station(row), overrides)
        station["stream_url"] = repaired_urls.get(station["id"], station["stream_url"])
        if station["id"] in dropped_ids:
            hand_dropped += 1
            continue
        if station["id"] in dead_ids:
            dead_dropped += 1
            continue
        key = normalize_stream_url(station["stream_url"])
        if key in seen_urls:
            web_dropped += 1
            continue
        seen_urls.add(key)
        stations.append(station)
    dropped += web_dropped
    return {
        "schema": 1,
        "notes": (
            "Automated tier under the curated radio_catalog.json. Built by "
            "tools/import_radio_catalog.py from the PR #150 catalog "
            "(CatalystForChaos): Radio Browser stream URLs joined to Wikidata "
            "transmitter coordinates (CC0) on FCC call sign. Coverage radii "
            "are that catalog's per-band defaults, not FCC contours. Curated "
            "call signs win: collisions are dropped at build and load time. "
            "Streams tools/check_radio_streams.py could not reach are left out; "
            "see radio_stream_health.json. Names and formats a rule cannot "
            "derive, and stations the directory lists twice, come from "
            "radio_imported_overrides.json. Rows with id rb-fcc-* are Radio "
            "Browser stations placed at their FCC-licensed transmitter site, "
            "with coverage from licensed power rather than a per-band default."
        ),
        "counts": {
            "stations": len(stations),
            "dropped_collisions": dropped,
            "dropped_unreachable": dead_dropped,
            "dropped_by_hand": hand_dropped,
            "fcc_placed": added_terrestrial,
        },
        "stations": stations,
    }


def render(catalog: dict) -> str:
    return json.dumps(catalog, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--curated", type=Path, default=CURATED_PATH)
    parser.add_argument("--health", type=Path, default=HEALTH_PATH)
    parser.add_argument("--overrides", type=Path, default=OVERRIDES_PATH)
    parser.add_argument("--radio-browser", type=Path, default=RADIO_BROWSER_PATH)
    parser.add_argument("--fcc", type=Path, default=FCC_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the checked-in file matches a rebuild; write nothing",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        parser.error(f"missing input: {args.input}\nSee this tool's docstring for the source.")

    source = json.loads(args.input.read_text(encoding="utf-8"))
    curated = json.loads(args.curated.read_text(encoding="utf-8"))
    for path, fetcher in (
        (args.radio_browser, "a Radio Browser US snapshot (see this tool's docstring)"),
        (args.fcc, "uv run python tools/fetch_fcc_transmitters.py"),
    ):
        if not path.exists():
            # The caches are gitignored, so a clone does not have them. A
            # contributor editing the overrides file must not be blocked by
            # that -- but the skip is said out loud, because a check that
            # quietly passes on missing input reads as one that proved
            # something.
            if args.check:
                print(f"Skipped: {path} is not here. This check runs where the caches are.")
                return 0
            # Building without these silently drops 800-odd terrestrial
            # stations and reports the checked-in file as out of date,
            # which reads as a bug in the data rather than a missing cache.
            parser.error(f"missing input: {path}\nRebuild it with: {fetcher}")
    directory = json.loads(args.radio_browser.read_text(encoding="utf-8"))
    transmitters = json.loads(args.fcc.read_text(encoding="utf-8"))["transmitters"]
    terrestrial = terrestrial_rows(directory, transmitters)
    print(f"{len(terrestrial)} directory stations placed at a licensed transmitter")

    curation = hand_curation(args.overrides)
    catalog = build(source, curated, stream_health(args.health), terrestrial, curation)

    # An override for a station that is no longer built does nothing, and
    # silence would leave it there for the next reader to trust. Name it.
    overrides, dropped_ids = curation
    built_ids = {station["id"] for station in catalog["stations"]}
    stale = sorted((set(overrides) - built_ids) | (dropped_ids & built_ids))
    if stale:
        print(f"Stale entries in {args.overrides.name}:", file=sys.stderr)
        for station_id in stale:
            print(f"  {station_id}", file=sys.stderr)
        return 1
    print(
        f"{len(overrides)} hand-curated stations, "
        f"{catalog['counts']['dropped_by_hand']} dropped by hand"
    )
    text = render(catalog)

    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != text:
            print(
                f"Out of date: {args.output}\nRe-run tools/import_radio_catalog.py", file=sys.stderr
            )
            return 1
        print(f"{args.output.name} is up to date")
        return 0

    args.output.write_text(text, encoding="utf-8")
    counts = json.loads(text)["counts"]
    print(f"Wrote {args.output} ({counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
