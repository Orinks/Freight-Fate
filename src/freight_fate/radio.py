"""In-cab radio catalog, reception, safety gates, and playback state."""

from __future__ import annotations

import contextlib
import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Protocol

from .data.data_resources import read_data_text

log = logging.getLogger(__name__)

SAFE_ROUTE_PLAYLIST = "route_playlist"
SAFE_FALLBACK_STATION_ID = "ff-safety-satellite"
RADIO_CATALOG_RESOURCE = "radio_catalog.json"
RADIO_IMPORTED_RESOURCE = "radio_imported.json"
EARTH_RADIUS_MI = 3958.8
# Personal playlists: files dropped into the Playlists folder become
# stations on the dial. A folder, not a file picker, on purpose -- screen
# reader users manage folders in their file manager far more comfortably
# than in any in-game browse dialog. Both ubiquitous playlist formats are
# read, because which one a player has is decided by whatever exported it.
PERSONAL_PLAYLIST_SOURCE_TYPE = "playlist"
PLAYLISTS_DIR_NAME = "Playlists"
PLAYLIST_SUFFIXES = ("*.m3u", "*.m3u8", "*.pls")


@dataclass(frozen=True)
class RadioStation:
    id: str
    name: str
    call_sign: str
    format: str
    source: str
    source_type: str = "local"
    stream_url: str = ""
    stream_format: str = ""
    codec: str = ""
    lat: float | None = None
    lon: float | None = None
    range_miles: float = 0.0
    market: str = ""
    region: str = ""
    country: str = "US"
    safe_for_streaming: bool = True
    real_stream: bool = False
    always_available: bool = False
    fallback: bool = False
    supported: bool = True
    track_key: str = ""
    playlist: str = ""  # music.STATION_PLAYLISTS pool for built-in rotation
    host: str = ""  # music.STATION_HOST_SEGMENTS voice between songs
    notes: str = ""
    # FM physics fields. frequency_mhz drives the picket-fence flutter rate
    # (2v/lambda); 0.0 means unknown and the mid-band default applies --
    # wavelength varies only ~10 percent across 88-108, so a default is
    # honest. site_elev_ft is the tower site's ground elevation; None skips
    # the elevation term of the range model entirely.
    frequency_mhz: float = 0.0
    site_elev_ft: float | None = None
    # Personal playlist stations only: what the player's playlist file lists,
    # in playlist order. An entry is either a resolved media file path or an
    # internet station's URL (is_stream_entry tells them apart), because a
    # playlist may hold both and the order is the player's own.
    playlist_entries: tuple[str, ...] = ()

    @property
    def display_name(self) -> str:
        # Web stations have no call sign; they are named, not lettered.
        if not self.call_sign:
            return self.name
        # A name that only repeats the call sign is spoken once, not twice.
        if not self.name or self.name.upper() == self.call_sign.upper():
            return self.call_sign
        return f"{self.call_sign}, {self.name}"

    @property
    def satellite(self) -> bool:
        return self.source_type in {"afn", "satellite"}


@dataclass(frozen=True)
class RadioReception:
    station: RadioStation
    distance_miles: float | None
    signal: float
    reason: str
    fallback: bool = False

    @property
    def signal_label(self) -> str:
        if self.fallback:
            return "fallback"
        if self.station.always_available:
            return "always available"
        if self.signal >= 0.8:
            return "strong signal"
        if self.signal >= 0.45:
            return "fair signal"
        if self.signal > 0.0:
            return "fringe signal"
        return "out of range"


class RadioPlaybackBackend(Protocol):
    def play_station(self, station: RadioStation, volume: float) -> None: ...
    def stop_radio(self) -> None: ...


class RadioPlaybackError(RuntimeError):
    """Raised when a station cannot play and radio should fall back safely."""


@dataclass(frozen=True)
class RadioAction:
    message: str
    station: RadioStation
    enabled: bool
    reception: RadioReception
    fallback_used: bool = False


def load_radio_catalog() -> tuple[RadioStation, ...]:
    text = read_data_text(RADIO_CATALOG_RESOURCE)
    if text is None:
        raise FileNotFoundError("radio_catalog.json is missing from this build")
    data = json.loads(text)
    stations = tuple(_station_from_dict(row) for row in data["stations"])
    if not stations:
        raise ValueError("radio catalog is empty")
    ids = [station.id for station in stations]
    if len(ids) != len(set(ids)):
        raise ValueError("radio catalog contains duplicate station ids")
    return stations


def _station_from_dict(row: dict) -> RadioStation:
    return RadioStation(
        id=str(row["id"]),
        name=str(row["name"]),
        call_sign=str(row["call_sign"]),
        format=str(row["format"]),
        source=str(row["source"]),
        source_type=str(row.get("source_type", "local")),
        stream_url=str(row.get("stream_url", "")),
        stream_format=str(row.get("stream_format", "")),
        codec=str(row.get("codec", "")),
        lat=_optional_float(row.get("lat")),
        lon=_optional_float(row.get("lon")),
        range_miles=float(row.get("range_miles", 0.0)),
        market=str(row.get("market", "")),
        region=str(row.get("region", "")),
        country=str(row.get("country", "US")),
        safe_for_streaming=bool(row.get("safe_for_streaming", True)),
        real_stream=bool(row.get("real_stream", False)),
        always_available=bool(row.get("always_available", False)),
        fallback=bool(row.get("fallback", False)),
        supported=bool(row.get("supported", True)),
        track_key=str(row.get("track_key", "")),
        playlist=str(row.get("playlist", "")),
        host=str(row.get("host", "")),
        notes=str(row.get("notes", "")),
        frequency_mhz=float(row.get("frequency_mhz", 0.0)),
        site_elev_ft=_optional_float(row.get("site_elev_ft")),
    )


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _call_sign_base(call_sign: str) -> str:
    """WNYC-FM, "WNYC FM" and WNYC are one place on the dial."""
    return call_sign.replace("-", " ").split()[0].upper() if call_sign.strip() else ""


_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.\-]*://", re.IGNORECASE)


def normalize_stream_url(url: str) -> str:
    """A stream URL with scheme and a trailing slash stripped, for dedup only.

    The same live stream is sometimes registered under both ``http://`` and
    ``https://`` (and sometimes with a bare trailing slash); an exact-string
    comparison treats those as different streams and let one station land on
    the dial twice under two names (WHYY 90.9, 2026-08-12 field report).
    Scheme and host are case-insensitive by spec, so only that part is
    folded -- a genuinely case-sensitive path is never merged with a
    different one. Never stored or spoken -- comparison only. Shared with
    tools/import_radio_catalog.py's build-time collision check, so both
    layers agree on what counts as "the same stream".
    """
    url = url.strip()
    match = _URL_SCHEME_RE.match(url)
    if match:
        url = url[match.end() :]
    url = url.rstrip("/")
    host, _, rest = url.partition("/")
    return f"{host.lower()}/{rest}" if rest else host.lower()


def station_identity(station: RadioStation) -> str:
    """The station's identity for dial-listing purposes.

    Curated data can carry the same live stream under several rows on
    purpose -- real multi-site coverage, one row per transmitter/translator
    (KZYX Willits/Ukiah, WNPN/ripr Newport/Providence, KENW's three New
    Mexico sites, SDPB's statewide network). Those rows stay in the data
    unchanged: each still feeds its own reception physics. But they are one
    station, not several, so the dial lists them once, at whichever site is
    strongest from the truck's current position. Two rows sharing a
    normalized stream URL share an identity; a station with no stream URL
    (built-in, no real_stream) is never grouped -- its id already is one.
    """
    if station.stream_url:
        return normalize_stream_url(station.stream_url)
    return f"id:{station.id}"


def _identity_siblings(
    catalog: tuple[RadioStation, ...],
) -> dict[str, tuple[RadioStation, ...]]:
    """Every station sharing a dial identity with at least one other, keyed
    by that identity. Solo stations (the overwhelming majority) are left out
    entirely so every lookup against this map is a cheap membership check."""
    groups: dict[str, list[RadioStation]] = {}
    for station in catalog:
        groups.setdefault(station_identity(station), []).append(station)
    return {key: tuple(stations) for key, stations in groups.items() if len(stations) > 1}


def load_imported_stations(
    curated: tuple[RadioStation, ...],
) -> tuple[RadioStation, ...]:
    """The automated tier under the curated catalog, if this build carries one.

    tools/import_radio_catalog.py drops call-sign collisions when the file is
    built; the filter here repeats that against the curated catalog actually
    loaded, so hand-adding a curated station never puts its call sign on the
    dial twice while the imported file waits for a rebuild.
    """
    text = read_data_text(RADIO_IMPORTED_RESOURCE)
    if text is None:
        return ()
    reserved = {_call_sign_base(station.call_sign) for station in curated}
    return tuple(
        station
        for station in (_station_from_dict(row) for row in json.loads(text)["stations"])
        if _call_sign_base(station.call_sign) not in reserved
    )


def _full_catalog() -> tuple[RadioStation, ...]:
    curated = load_radio_catalog()
    stations = curated + load_imported_stations(curated)
    ids = [station.id for station in stations]
    if len(ids) != len(set(ids)):
        raise ValueError("imported stations collide with curated station ids")
    return stations


DEFAULT_RADIO_CATALOG: tuple[RadioStation, ...] = _full_catalog()


def personal_playlists_dir() -> Path:
    from .models.profile import data_dir

    return data_dir() / PLAYLISTS_DIR_NAME


def _absolute_anywhere(line: str) -> bool:
    """Absolute on the machine that wrote the playlist, not just on this one.

    A playlist copied off a Windows machine carries entries like
    ``C:\\music\\song.flac``, which POSIX does not read as absolute -- joining
    one to the playlist's own folder would invent a path nobody ever meant, and
    hide the real one when the track cannot be found. A drive letter or a UNC
    share is absolute wherever the playlist is read.
    """
    return PurePosixPath(line).is_absolute() or PureWindowsPath(line).is_absolute()


def is_stream_entry(entry: str) -> bool:
    """Whether a playlist entry names an internet station, not a file."""
    return entry.lower().startswith(("http://", "https://"))


def _resolve_entry(line: str, path: Path) -> str:
    """One playlist line as a stream URL or a fully resolved file path."""
    if is_stream_entry(line):
        return line
    entry = Path(line)
    if not _absolute_anywhere(line):
        entry = path.parent / entry
    return str(entry)


def _parse_m3u(path: Path) -> tuple[tuple[str, ...], str]:
    """Entries and the optional #PLAYLIST title from one M3U file.

    Relative entries resolve against the M3U's own folder, so a playlist
    exported next to its music keeps working when the folder moves. Stream
    URLs are entries like any other: a playlist exported from an internet
    radio app is nothing but stream URLs, and skipping them made the whole
    station vanish. They need no extra licensing gate -- personal playlist
    stations are already not safe_for_streaming, so they ride exactly the
    same streamer-safe switch the curated real streams do."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        log.warning("Could not read playlist %s", path.name, exc_info=True)
        return (), ""
    title = ""
    entries: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if line.upper().startswith("#PLAYLIST:"):
                title = line.split(":", 1)[1].strip()
            continue
        entries.append(_resolve_entry(line, path))
    return tuple(entries), title


def _parse_pls(path: Path) -> tuple[tuple[str, ...], str]:
    """Entries and a title from one PLS file.

    The format internet radio directories hand out: ``File1=``/``File2=``
    lines, numbered rather than ordered by position, with a matching
    ``Title1=``. A one-entry PLS is a single station and its Title1 is that
    station's own name, which is the best name the dial can give it; a
    multi-entry PLS titles each track instead, so there the file name wins."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        log.warning("Could not read playlist %s", path.name, exc_info=True)
        return (), ""
    files: dict[int, str] = {}
    titles: dict[int, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        match = re.fullmatch(r"(?i)(file|title)(\d+)", key)
        if not match or not value:
            continue
        target = files if match.group(1).lower() == "file" else titles
        target[int(match.group(2))] = value
    entries = tuple(_resolve_entry(files[n], path) for n in sorted(files))
    title = titles.get(min(files), "") if len(entries) == 1 and titles else ""
    return entries, title


def _parse_playlist_file(path: Path) -> tuple[tuple[str, ...], str]:
    if path.suffix.lower() == ".pls":
        return _parse_pls(path)
    return _parse_m3u(path)


def load_personal_playlists(directory: Path | None = None) -> tuple[RadioStation, ...]:
    """One dial station per playlist file in the player's Playlists folder.

    Creating the folder here is the feature's discoverability: an empty
    Playlists directory next to the saves invites dropping files in.
    Missing media is skipped at play time, not here -- a NAS that is asleep
    when the drive starts should not erase the station."""
    base = directory if directory is not None else personal_playlists_dir()
    try:
        base.mkdir(parents=True, exist_ok=True)
        candidates = sorted(
            (path for pattern in PLAYLIST_SUFFIXES for path in base.glob(pattern)),
            key=lambda path: path.name.lower(),
        )
    except OSError:
        log.warning("Could not read the Playlists folder %s", base, exc_info=True)
        return ()
    stations: list[RadioStation] = []
    used: set[str] = set()
    for path in candidates:
        entries, title = _parse_playlist_file(path)
        if not entries:
            # Silence used to be the whole diagnosis here: no station on the
            # dial, nothing in the log, nothing spoken.
            log.warning("Playlist %s has no usable entries; it gets no station", path.name)
            continue
        name = title or path.stem
        streams = sum(1 for entry in entries if is_stream_entry(entry))
        log.info(
            "Playlist %s loaded as %r: %d entries, %d files, %d streams",
            path.name,
            name,
            len(entries),
            len(entries) - streams,
            streams,
        )
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "playlist"
        sid = f"playlist-{slug}"
        n = 2
        while sid in used:
            sid = f"playlist-{slug}-{n}"
            n += 1
        used.add(sid)
        stations.append(
            RadioStation(
                id=sid,
                name=name,
                call_sign="Playlist",
                format="personal playlist",
                source=f"your playlist file {path.name}",
                source_type=PERSONAL_PLAYLIST_SOURCE_TYPE,
                # The streamer-safe promise is that nothing licensed can
                # reach the speakers; the game cannot vouch for personal
                # media, so these ride the same gate as real streams.
                safe_for_streaming=False,
                always_available=True,
                playlist_entries=entries,
            )
        )
    return tuple(stations)


# Saved stations pull forward to this dial group (RadioState._group): with
# thousands of stations on the dial, the driver's own picks sit right after
# their playlists, one category jump from anywhere.
FAVORITES_GROUP = 3
# Real ranged stations. Unlike every other group, order here is signal, not
# call sign: a category jump at the start of a run should land on the
# station that plays clean, not on whichever fringe call sign sorts first.
TERRESTRIAL_GROUP = 4


def _dial_group(station: RadioStation) -> int:
    """Dial order and category identity, shared by sort and category jump."""
    if station.id == SAFE_ROUTE_PLAYLIST:
        return 0
    if station.source_type == "built_in":
        return 1
    if station.source_type == PERSONAL_PLAYLIST_SOURCE_TYPE:
        return 2
    if station.fallback:
        return 8
    # Freight Fate's own music stations (playlist-backed, no stream) sit with
    # Roadhouse and Night Line: always on the dial, everywhere, in every mode.
    if station.playlist and not station.real_stream:
        return 1
    if station.source_type in {"local", "regional", "imported"}:
        return TERRESTRIAL_GROUP
    if station.source_type == "afn":
        return 5
    if station.source_type == "satellite":
        return 6
    if station.source_type == "international":
        return 7
    # Web radio sits last on the dial, past everything with a place or a
    # story: thousands of stations, in listener-vote order (the dial sort is
    # stable and their call signs are empty), one category jump to skip.
    if station.source_type == "web":
        return 9
    return 10


DIAL_CATEGORY_NAMES = {
    0: "Route playlist",
    1: "Freight Fate stations",
    2: "Your playlists",
    3: "Favorites",
    4: "Terrestrial",
    5: "AFN",
    6: "Satellite",
    7: "International",
    8: "Fallback",
    9: "Web radio",
    10: "Other stations",
}


def station_distance_miles(
    station: RadioStation,
    position: tuple[float, float] | None,
) -> float | None:
    if position is None or station.lat is None or station.lon is None:
        return None
    lat1, lon1 = (math.radians(position[0]), math.radians(position[1]))
    lat2, lon2 = (math.radians(station.lat), math.radians(station.lon))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_MI * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# FM is line-of-sight, and height is range: the 4/3-earth radio horizon is
# d_miles ~ 1.23 * sqrt(height_ft). Standing above a station's tower site
# extends its contour by that term -- the owner's ham anchor: from the
# Mogollon Rim (~7000 ft) both Phoenix (~1100 ft) and Flagstaff come in
# clearly at distances a flat radius refuses. Sitting BELOW the site is
# NEUTRAL, never a penalty: a mountain-top transmitter looks straight down
# into its valley (that height is why they put it there), and the published
# range already assumes ordinary low receivers. True canyon shadowing needs
# a path profile we do not carry -- roadmap follow-up, not a proxy that
# would punish every in-market listener under a mountain site.
RADIO_HORIZON_MI_PER_SQRT_FT = 1.23

# Compression compensation for ranged stations (owner design 2026-08-13):
# the truck spends road miles 10-40x faster than a real cab, so a real
# 40-mile FM contour was two real minutes of program. Doubling the reach
# keeps radio regional (no station spans three states) while a median
# station now survives about seven real minutes at Relaxed. Applied in
# _reach_mi so every consumer -- range check, signal curve, elevation
# lift -- agrees on one number.
RADIO_REACH_MULT = 2.0


def _reach_mi(station: RadioStation) -> float:
    return station.range_miles * RADIO_REACH_MULT


def effective_range_miles(station: RadioStation, elevation_ft: float | None) -> float:
    if elevation_ft is None or station.site_elev_ft is None or station.range_miles <= 0:
        return _reach_mi(station)
    lift = max(0.0, elevation_ft - station.site_elev_ft)
    return _reach_mi(station) + RADIO_HORIZON_MI_PER_SQRT_FT * math.sqrt(lift)


def estimate_signal(
    station: RadioStation,
    position: tuple[float, float] | None,
    elevation_ft: float | None = None,
) -> RadioReception:
    if station.always_available:
        return RadioReception(station, None, 1.0, "always available")
    if station.range_miles <= 0:
        return RadioReception(station, None, 1.0, "built-in")
    distance = station_distance_miles(station, position)
    if distance is None:
        return RadioReception(station, None, 0.0, "no truck position")
    range_miles = effective_range_miles(station, elevation_ft)
    if distance > range_miles:
        return RadioReception(station, distance, 0.0, "out of range")
    # Signal is intentionally simple and monotonic. Future FCC contours can
    # replace range_miles without changing the state/menu layer.
    signal = max(0.05, 1.0 - (distance / range_miles) ** 1.4)
    return RadioReception(station, distance, signal, "in range")


# Below this signal the audio starts to thin out. Entering the fringe the
# program holds a listenable level (worth chasing toward its city); past the
# static threshold it keeps sinking toward the deep floor while the noise
# rises to take its place -- the owner's ruling (2026-07-24): the two smear
# together, static going TO program level, never bombarding on top of a
# still-loud program. The deep floor keeps a trace of program in the noise
# while the station is technically in range. Retuned for the doubled reach
# (2026-08-13): with the contour twice as wide, the old 60%-of-range full-
# volume cutoff spent most of a station's new reach visibly fading, when
# the point of RADIO_REACH_MULT was more clean program, not more fringe.
# Clean program now holds through ~85% of the contour and static is pushed
# out to the outer edge, where it belongs.
SIGNAL_FULL_VOLUME = 0.20  # clean program through ~85% of the contour
SIGNAL_FRINGE_FLOOR = 0.3
SIGNAL_DEEP_FLOOR = 0.08
STATIC_SIGNAL_THRESHOLD = 0.12  # static smear lives in the outer edge only


def signal_volume_factor(reception: RadioReception) -> float:
    """How much of the radio volume the current signal supports.

    Satellite/built-in sources always play at full volume. Ranged stations
    hold full volume through most of their contour, fade toward the fringe
    floor as the truck drives away, keep sinking under the rising static in
    the deep fringe, and go silent past the range edge.
    """
    station = reception.station
    if reception.fallback or station.always_available or station.range_miles <= 0:
        return 1.0
    signal = reception.signal
    if signal <= 0.0:
        return 0.0
    if signal >= SIGNAL_FULL_VOLUME:
        return 1.0
    if signal >= STATIC_SIGNAL_THRESHOLD:
        return SIGNAL_FRINGE_FLOOR + (1.0 - SIGNAL_FRINGE_FLOOR) * (signal / SIGNAL_FULL_VOLUME)
    edge = SIGNAL_FRINGE_FLOOR + (1.0 - SIGNAL_FRINGE_FLOOR) * (
        STATIC_SIGNAL_THRESHOLD / SIGNAL_FULL_VOLUME
    )
    return max(SIGNAL_DEEP_FLOOR, edge * (signal / STATIC_SIGNAL_THRESHOLD) ** 0.8)


def truck_position(route, position_mi: float, world) -> tuple[float, float] | None:
    """Approximate current lat/lon from checked-in route/city coordinates."""
    if route is None or world is None or not getattr(route, "legs", None):
        return None
    remaining = max(0.0, float(position_mi))
    for i, leg in enumerate(route.legs):
        leg_miles = max(0.0, float(getattr(leg, "miles", 0.0)))
        if remaining <= leg_miles or i == len(route.legs) - 1:
            local = min(leg_miles, remaining)
            return _leg_position(route, leg, i, local, world)
        remaining -= leg_miles
    return None


def truck_elevation_ft(route, position_mi: float) -> float | None:
    """Current ground elevation from the leg's elevation samples, if any."""
    if route is None or not getattr(route, "legs", None):
        return None
    remaining = max(0.0, float(position_mi))
    for i, leg in enumerate(route.legs):
        leg_miles = max(0.0, float(getattr(leg, "miles", 0.0)))
        if remaining <= leg_miles or i == len(route.legs) - 1:
            local = min(leg_miles, remaining)
            return _leg_elevation(route, leg, i, local)
        remaining -= leg_miles
    return None


def _leg_elevation(route, leg, index: int, local_mi: float) -> float | None:
    samples = tuple(getattr(leg, "elevation_samples", ()) or ())
    if not samples:
        return None
    total = max(0.01, float(getattr(leg, "miles", 0.0)))
    forward = route.cities[index] == leg.a
    # Sample mileposts are leg-local in the a->b direction; a reversed
    # traversal reads the profile from the far end, same as route points.
    at = local_mi if forward else total - local_mi
    if len(samples) == 1 or at <= samples[0].at_mi:
        return samples[0].elevation_ft
    for prev, cur in zip(samples, samples[1:], strict=False):
        if at <= cur.at_mi:
            span = max(0.01, cur.at_mi - prev.at_mi)
            t = max(0.0, min(1.0, (at - prev.at_mi) / span))
            return prev.elevation_ft + (cur.elevation_ft - prev.elevation_ft) * t
    return samples[-1].elevation_ft


def _leg_position(route, leg, index: int, local_mi: float, world) -> tuple[float, float] | None:
    points = tuple(getattr(leg, "route_points", ()) or ())
    forward = route.cities[index] == leg.a
    if points:
        ordered = points if forward else tuple(reversed(points))
        total = max(0.01, float(getattr(leg, "miles", 0.0)))
        if len(ordered) == 1:
            return (ordered[0].lat, ordered[0].lon)
        last = ordered[0]
        for point in ordered[1:]:
            start = last.at_mi if forward else total - last.at_mi
            end = point.at_mi if forward else total - point.at_mi
            if end < start:
                start, end = end, start
            if start <= local_mi <= end:
                span = max(0.01, end - start)
                t = max(0.0, min(1.0, (local_mi - start) / span))
                return (
                    last.lat + (point.lat - last.lat) * t,
                    last.lon + (point.lon - last.lon) * t,
                )
            last = point
    a = world.cities.get(route.cities[index])
    b = world.cities.get(route.cities[index + 1])
    if a is None or b is None:
        return None
    t = 0.0 if leg.miles <= 0 else max(0.0, min(1.0, local_mi / leg.miles))
    return (a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t)


class RadioState:
    """Mutable in-cab radio state. Streamer-safe mode is the one licensing
    gate: off by default (owner ruling, 2026-08-12), so the full dial plays
    out of the box, and turning it on is the explicit choice a streamer
    makes to keep licensed audio off their broadcast."""

    def __init__(
        self,
        *,
        catalog: tuple[RadioStation, ...] = DEFAULT_RADIO_CATALOG,
        enabled: bool = True,
        station_id: str = SAFE_ROUTE_PLAYLIST,
        volume: float = 0.25,
        streamer_safe: bool = False,
        position: tuple[float, float] | None = None,
        favorite_ids: set[str] | None = None,
    ) -> None:
        self.catalog = catalog
        self.enabled = enabled
        self.station_id = station_id
        self.volume = self._clamp_volume(volume)
        self.streamer_safe = streamer_safe
        self.position = position
        self.elevation_ft: float | None = None
        self.favorite_ids: set[str] = set(favorite_ids or ())
        # Stations that refused to play this session: off the dial until the
        # next session rather than a dead stop on every pass of the band.
        self.unplayable_ids: set[str] = set()
        # Multi-site stations (KZYX, WNPN/ripr, KENW, SDPB...): every row
        # sharing a normalized stream URL, keyed by that identity. Built
        # once per catalog -- the catalog itself never changes after
        # construction -- so tuning and reception lookups stay O(sites),
        # not O(catalog), on every call.
        self._identity_siblings = _identity_siblings(catalog)

    @classmethod
    def from_settings(cls, settings, profile=None) -> RadioState:
        return cls(
            catalog=DEFAULT_RADIO_CATALOG + load_personal_playlists(),
            enabled=bool(getattr(settings, "radio_enabled", True)),
            station_id=str(getattr(settings, "radio_station_id", SAFE_ROUTE_PLAYLIST)),
            volume=float(getattr(settings, "radio_volume", 0.25)),
            streamer_safe=bool(getattr(settings, "radio_streamer_safe", False)),
            favorite_ids=set(getattr(profile, "radio_favorites", ()) or ()),
        )

    def reload_personal_playlists(self, directory: Path | None = None) -> None:
        """Re-read the Playlists folder so the dial matches it right now.

        Playlists used to be read once, when the drive began: a player who
        fixed a playlist file mid-run had to start another drive before the
        radio would even look again. The dial screen is the cheap place to
        re-read -- it opens rarely, and it is exactly where a player goes
        when their playlist is missing from the dial.
        """
        kept = tuple(
            station
            for station in self.catalog
            if station.source_type != PERSONAL_PLAYLIST_SOURCE_TYPE
        )
        stale = {station.id for station in self.catalog} - {station.id for station in kept}
        loaded = load_personal_playlists(directory)
        self.catalog = kept + loaded
        self._identity_siblings = _identity_siblings(self.catalog)
        # A playlist that would not play earlier deserves another chance once
        # its file has been edited; the session-long ban is for dead streams.
        self.unplayable_ids -= stale | {station.id for station in loaded}

    def apply_settings(self, settings) -> None:
        self.volume = self._clamp_volume(float(getattr(settings, "radio_volume", self.volume)))
        self.streamer_safe = bool(getattr(settings, "radio_streamer_safe", self.streamer_safe))

    def write_settings(self, settings) -> None:
        settings.radio_enabled = self.enabled
        settings.radio_station_id = self.station_id

    def update_position(
        self, position: tuple[float, float] | None, elevation_ft: float | None = None
    ) -> None:
        self.position = position
        self.elevation_ft = elevation_ft

    def receivable_stations(self) -> tuple[RadioReception, ...]:
        receptions = [
            estimate_signal(station, self.position, self.elevation_ft)
            for station in self.catalog
            if self._station_allowed(station)
        ]
        receivable = [
            reception
            for reception in receptions
            if reception.signal > 0.0 or reception.station.always_available
        ]
        receivable = self._collapse_identity_sites(receivable)
        receivable.sort(key=self._reception_sort_key)
        return tuple(receivable) or (self.fallback_reception(),)

    def _collapse_identity_sites(self, receptions: list[RadioReception]) -> list[RadioReception]:
        """One dial entry per multi-site identity: whichever site is loudest.

        KZYX/WNPN/KENW/SDPB-style entries are several real transmitters
        broadcasting the same stream; each keeps feeding its own reception
        physics, but only the strongest one currently in range gets a line
        on the dial -- the rest would just repeat it under a different name.
        """
        if not self._identity_siblings:
            return receptions
        solo: list[RadioReception] = []
        best: dict[str, RadioReception] = {}
        order: list[str] = []
        for reception in receptions:
            identity = station_identity(reception.station)
            if identity not in self._identity_siblings:
                solo.append(reception)
                continue
            current = best.get(identity)
            if current is None:
                order.append(identity)
                best[identity] = reception
            elif reception.signal > current.signal:
                best[identity] = reception
        return solo + [best[identity] for identity in order]

    def available_stations(self) -> tuple[RadioStation, ...]:
        return tuple(reception.station for reception in self.receivable_stations())

    def station_list_lines(self, limit: int = 12, distance_text=None) -> list[str]:
        lines = []
        for reception in self.receivable_stations()[:limit]:
            station = reception.station
            selected = "current, " if station.id == self.current_station().id else ""
            distance = ""
            if reception.distance_miles is not None:
                spoken = (
                    distance_text(reception.distance_miles)
                    if distance_text is not None
                    else f"{reception.distance_miles:.0f} miles"
                )
                distance = f", {spoken} away"
            lines.append(
                f"{selected}{station.display_name}: {station.format}, "
                f"{reception.signal_label}{distance}. Source: {station.source}."
            )
        return lines

    def current_station(self) -> RadioStation:
        station = self._station_by_id(self.station_id)
        if station is not None and self._station_allowed(station):
            reception = estimate_signal(station, self.position, self.elevation_ft)
            if reception.signal > 0.0 or station.always_available:
                handover = self._identity_handover(station, reception.signal)
                if handover is not None:
                    self.station_id = handover.id
                    return handover
                return station
        fallback = self.fallback_station()
        self.station_id = fallback.id
        return fallback

    def _identity_handover(
        self, station: RadioStation, current_signal: float
    ) -> RadioStation | None:
        """The stronger sibling site for a multi-site station, if one beats it now.

        Tuning in on KZYX/WNPN/KENW/SDPB-style entries points station_id at
        one literal site's id; as the truck moves, this keeps that id
        pointed at whichever site is actually loudest, so the tuned station
        just gets stronger the way any single station would -- it never
        needs a second dial entry to hand over to, and it never sits stuck
        on a fading site while a clearer one of the same identity is in
        range.
        """
        siblings = self._identity_siblings.get(station_identity(station))
        if not siblings:
            return None
        best_station, best_signal = station, current_signal
        for candidate in siblings:
            if candidate.id == station.id or not self._station_allowed(candidate):
                continue
            candidate_signal = estimate_signal(candidate, self.position, self.elevation_ft).signal
            if candidate_signal > best_signal:
                best_station, best_signal = candidate, candidate_signal
        return best_station if best_station.id != station.id else None

    def current_reception(self) -> RadioReception:
        station = self.current_station()
        if station.fallback:
            return self.fallback_reception()
        return estimate_signal(station, self.position, self.elevation_ft)

    def fallback_station(self) -> RadioStation:
        for station in self.catalog:
            if station.fallback and self._station_allowed(station):
                return station
        for station in self.catalog:
            if not station.real_stream and self._station_allowed(station):
                return station
        return self.catalog[0]

    def fallback_reception(self) -> RadioReception:
        station = self.fallback_station()
        return RadioReception(station, None, 1.0, "fallback", fallback=True)

    def status_text(self) -> str:
        reception = self.current_reception()
        station = reception.station
        state = "on" if self.enabled else "off"
        safety = "streamer-safe" if self.streamer_safe else "streamer-safe off"
        return (
            f"Radio {state}. {station.display_name}, {station.format}. "
            f"{reception.signal_label}. Volume {round(self.volume * 100)} percent. "
            f"{safety}. Source: {station.source}."
        )

    def toggle(self, backend: RadioPlaybackBackend | None = None) -> RadioAction:
        self.enabled = not self.enabled
        if not self.enabled:
            self._stop(backend)
            return RadioAction(
                "Radio off.",
                self.current_station(),
                enabled=False,
                reception=self.current_reception(),
            )
        self._power_on_retune()
        return self.play(backend, prefix="Radio on.")

    def _power_on_retune(self) -> None:
        """Power-on lands on a station that plays clean.

        The remembered station keeps the dial only while it still comes in
        at full volume -- playlists and other always-available choices
        always do. A fringe or out-of-range memory retunes to the strongest
        ranged signal on the dial instead (owner ruling, 2026-08-12).
        """
        reception = self.current_reception()
        if not reception.fallback and reception.signal >= SIGNAL_FULL_VOLUME:
            return
        ranged = [
            r
            for r in self.receivable_stations()
            if not r.fallback and not r.station.always_available and r.station.range_miles > 0
        ]
        if not ranged:
            return
        best = max(ranged, key=lambda r: r.signal)
        if reception.fallback or best.signal > reception.signal:
            self.station_id = best.station.id

    def tune(self, direction: int, backend: RadioPlaybackBackend | None = None) -> RadioAction:
        receptions = self.receivable_stations()
        current = self.current_station()
        ids = [reception.station.id for reception in receptions]
        try:
            index = ids.index(current.id)
        except ValueError:
            index = 0
        reception = receptions[(index + direction) % len(receptions)]
        self.station_id = reception.station.id
        if not self.enabled:
            return RadioAction(
                f"Radio off. Selected {self._station_phrase(reception)}.",
                reception.station,
                enabled=False,
                reception=reception,
            )
        return self.play(backend, prefix=f"Tuned to {reception.station.display_name}.")

    def tune_category(
        self, direction: int, backend: RadioPlaybackBackend | None = None
    ) -> RadioAction:
        """Jump to the first station of the previous/next dial category.

        Twenty-five AFN entries in a row buried the terrestrial section for
        anyone tuning linearly (owner, 2026-07-20); this is the escape. Only
        categories with a receivable station exist to jump to, and the spoken
        line leads with the category so the landing is oriented."""
        receptions = self.receivable_stations()
        groups: list[int] = []
        for reception in receptions:
            group = self._group(reception.station)
            if group not in groups:
                groups.append(group)
        current_group = self._group(self.current_station())
        if current_group in groups:
            index = groups.index(current_group)
            target = groups[(index + direction) % len(groups)]
        else:
            target = groups[0]
        reception = next(r for r in receptions if self._group(r.station) == target)
        self.station_id = reception.station.id
        label = DIAL_CATEGORY_NAMES.get(target, "Radio")
        if not self.enabled:
            return RadioAction(
                f"Radio off. {label}. Selected {self._station_phrase(reception)}.",
                reception.station,
                enabled=False,
                reception=reception,
            )
        return self.play(backend, prefix=f"{label}. Tuned to {reception.station.display_name}.")

    def select_station(
        self,
        station_id: str,
        backend: RadioPlaybackBackend | None = None,
    ) -> RadioAction:
        station = self._station_by_id(station_id)
        if station is None or not self._station_allowed(station):
            return self.play(backend, prefix="Radio fallback.")
        self.station_id = station.id
        if not self.enabled:
            return RadioAction(
                f"Radio off. Selected {self._station_phrase(estimate_signal(station, self.position, self.elevation_ft))}.",
                station,
                enabled=False,
                reception=self.current_reception(),
            )
        return self.play(backend, prefix=f"Selected {station.display_name}.")

    def play(
        self,
        backend: RadioPlaybackBackend | None = None,
        *,
        prefix: str = "",
    ) -> RadioAction:
        reception = self.current_reception()
        station = reception.station
        if not self.enabled:
            self._stop(backend)
            return RadioAction("Radio off.", station, enabled=False, reception=reception)
        if backend is None:
            return RadioAction(
                self._play_message(prefix, reception), station, enabled=True, reception=reception
            )
        try:
            backend.play_station(station, self.volume)
        except Exception:
            # A stream that refuses to play leaves the dial for the rest of
            # the session (it returns next session; streams have bad days),
            # and the radio hands over to the next station on the same band
            # rather than dropping the player to the silent fallback.
            original = reception
            self.mark_unplayable(original.station.id)
            replacement = self._same_band_replacement(original.station)
            if replacement is None:
                replacement = self.fallback_reception()
            self.station_id = replacement.station.id
            try:
                backend.play_station(replacement.station, self.volume)
            except Exception:
                self._stop(backend)
            return RadioAction(
                self._play_message(
                    "Radio fallback." if replacement.fallback else "Radio handover.",
                    replacement,
                    extra=self._refusal_clause(original.station),
                ),
                replacement.station,
                enabled=True,
                reception=replacement,
                fallback_used=True,
            )
        return RadioAction(
            self._play_message(prefix, reception), station, enabled=True, reception=reception
        )

    @staticmethod
    def _refusal_clause(station: RadioStation) -> str:
        """Why a station just left the dial, in the player's own terms.

        "Off the air" is true of a dead broadcast and false of a playlist:
        a playlist whose tracks will not open is a folder problem the player
        can go and fix, and saying so is the difference between a fixable
        fault and a mystery."""
        if station.source_type == PERSONAL_PLAYLIST_SOURCE_TYPE:
            return (
                f"None of the tracks in {station.display_name} would open; it is "
                "off the dial for the rest of this session."
            )
        return (
            f"{station.display_name} is off the air; it is "
            "off the dial for the rest of this session."
        )

    def mark_unplayable(self, station_id: str) -> None:
        """Take a station that refused to play off the dial for this session.

        A multi-site station's sites all serve the same stream URL, so a
        dead stream is dead at every site: the whole identity goes off the
        dial together, or the handover in current_station/receivable_stations
        would just find a sibling site pointed at the same dead URL and try
        it again.
        """
        self.unplayable_ids.add(station_id)
        station = self._station_by_id(station_id)
        if station is None:
            return
        siblings = self._identity_siblings.get(station_identity(station))
        if siblings:
            self.unplayable_ids.update(sibling.id for sibling in siblings)

    def _same_band_replacement(self, failed: RadioStation) -> RadioReception | None:
        """The next receivable station in the failed station's dial category."""
        group = _dial_group(failed)
        for reception in self.receivable_stations():
            if reception.fallback or reception.station.id == failed.id:
                continue
            if _dial_group(reception.station) == group:
                return reception
        return None

    def _station_allowed(self, station: RadioStation) -> bool:
        if not station.supported:
            return False
        if station.id in self.unplayable_ids:
            return False
        if not station.real_stream and station.source_type != PERSONAL_PLAYLIST_SOURCE_TYPE:
            return True
        # Real streams and personal media ride the same gate: the game
        # cannot vouch for their licensing, and streamer-safe mode is the
        # one switch that keeps such audio off a broadcast.
        return not self.streamer_safe

    def _station_by_id(self, station_id: str) -> RadioStation | None:
        for station in self.catalog:
            if station.id == station_id:
                return station
        return None

    @staticmethod
    def _clamp_volume(volume: float) -> float:
        return max(0.0, min(1.0, volume))

    @staticmethod
    def _station_phrase(reception: RadioReception) -> str:
        return (
            f"{reception.station.display_name}, {reception.station.format}, "
            f"{reception.signal_label}"
        )

    @staticmethod
    def _play_message(
        prefix: str,
        reception: RadioReception,
        *,
        extra: str = "",
    ) -> str:
        station = reception.station
        # A prefix like "Tuned to <station>." already names the station;
        # repeating the name right after would speak it twice in a row.
        name = "" if station.display_name in prefix else station.display_name
        parts = [
            part.rstrip(".")
            for part in (
                prefix,
                name,
                station.format,
                reception.signal_label,
                extra,
            )
            if part
        ]
        return ". ".join(parts) + "."

    def _group(self, station: RadioStation) -> int:
        """The station's dial group, with saved stations pulled forward.

        Only later categories promote: the route playlist, Freight Fate
        stations, and personal playlists already sit ahead of Favorites, and
        demoting them there would reorder the front of the dial for no gain.
        """
        group = _dial_group(station)
        if group > FAVORITES_GROUP and self._identity_ids(station) & self.favorite_ids:
            return FAVORITES_GROUP
        return group

    def _identity_ids(self, station: RadioStation) -> set[str]:
        """station.id plus every sibling site's id sharing its identity.

        A multi-site station is favorited or unfavorited as one station, not
        per site: whichever site happens to be loudest when the driver saves
        it should not be the only one that counts as saved once the truck
        moves on and a sibling site takes over the dial listing.
        """
        siblings = self._identity_siblings.get(station_identity(station))
        return {sibling.id for sibling in siblings} if siblings else {station.id}

    def toggle_favorite(self) -> str:
        """Save or unsave the current station; the spoken confirmation."""
        station = self.current_station()
        if station.fallback:
            return "The safety fallback is always on the dial."
        ids = self._identity_ids(station)
        if ids & self.favorite_ids:
            self.favorite_ids -= ids
            return f"Removed {station.display_name} from favorites."
        self.favorite_ids |= ids
        return f"Saved {station.display_name} to favorites."

    def _reception_sort_key(self, reception: RadioReception) -> tuple[int, float, str]:
        station = reception.station
        group = self._group(station)
        # Terrestrial runs strongest-first; every other group keeps call-sign
        # order (web radio relies on the sort staying stable -- its call
        # signs are empty and its catalog order is listener-vote order).
        signal = -reception.signal if group == TERRESTRIAL_GROUP else 0.0
        return (group, signal, station.call_sign)

    @staticmethod
    def _stop(backend: RadioPlaybackBackend | None) -> None:
        if backend is None:
            return
        with contextlib.suppress(Exception):
            backend.stop_radio()
