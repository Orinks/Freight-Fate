"""In-cab radio catalog, reception, safety gates, and playback state."""

from __future__ import annotations

import contextlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .data.data_resources import read_data_text

SAFE_ROUTE_PLAYLIST = "route_playlist"
SAFE_FALLBACK_STATION_ID = "ff-safety-satellite"
RADIO_CATALOG_RESOURCE = "radio_catalog.json"
EARTH_RADIUS_MI = 3958.8
# Personal M3U playlists: files dropped into the Playlists folder become
# stations on the dial. A folder, not a file picker, on purpose -- screen
# reader users manage folders in their file manager far more comfortably
# than in any in-game browse dialog.
PERSONAL_PLAYLIST_SOURCE_TYPE = "playlist"
DIRECTORY_SOURCE_TYPE = "directory_nearby"
DIRECTORY_INTERNET_ONLY_SOURCE_TYPE = "directory_internet_only"
PUBLIC_DIRECTORY_SOURCE_TYPES = {
    DIRECTORY_SOURCE_TYPE,
    DIRECTORY_INTERNET_ONLY_SOURCE_TYPE,
}
PLAYLISTS_DIR_NAME = "Playlists"


def public_stream_availability(settings, *, backend_supported: bool) -> str:
    """Describe automatic nearby-station playback availability."""

    if settings.radio_streamer_safe:
        return "Streamer-safe on: public radio and personal playlists hidden."
    if not settings.online_services:
        return "Public stations unavailable: Online services off. Local radio remains."
    if not backend_supported:
        return "Public stations unavailable with this audio system. Local radio remains."
    return "Public radio discovery: available."


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
    approximate_distance_miles: float | None = None
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
    # Personal playlist stations only: the resolved media file paths from the
    # player's M3U file, in playlist order.
    playlist_files: tuple[str, ...] = ()

    @property
    def display_name(self) -> str:
        if not self.call_sign:
            return self.name
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
        if self.station.source_type == DIRECTORY_SOURCE_TYPE:
            return "nearby internet station"
        if self.station.source_type == DIRECTORY_INTERNET_ONLY_SOURCE_TYPE:
            return "internet-only station"
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
    )


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


DEFAULT_RADIO_CATALOG: tuple[RadioStation, ...] = load_radio_catalog()


def personal_playlists_dir() -> Path:
    from .models.profile import data_dir

    return data_dir() / PLAYLISTS_DIR_NAME


def _parse_m3u(path: Path) -> tuple[tuple[str, ...], str]:
    """Media file paths and the optional #PLAYLIST title from one M3U file.

    Relative entries resolve against the M3U's own folder, so a playlist
    exported next to its music keeps working when the folder moves. Stream
    URLs are skipped: internet radio stays in the curated catalog, where it
    carries source notes and streamer-safety review."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return (), ""
    title = ""
    files: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if line.upper().startswith("#PLAYLIST:"):
                title = line.split(":", 1)[1].strip()
            continue
        if line.lower().startswith(("http://", "https://")):
            continue
        entry = Path(line)
        if not entry.is_absolute():
            entry = path.parent / entry
        files.append(str(entry))
    return tuple(files), title


def load_personal_playlists(directory: Path | None = None) -> tuple[RadioStation, ...]:
    """One dial station per M3U file in the player's Playlists folder.

    Creating the folder here is the feature's discoverability: an empty
    Playlists directory next to the saves invites dropping files in.
    Missing media is skipped at play time, not here -- a NAS that is asleep
    when the drive starts should not erase the station."""
    base = directory if directory is not None else personal_playlists_dir()
    try:
        base.mkdir(parents=True, exist_ok=True)
        candidates = sorted(base.glob("*.m3u")) + sorted(base.glob("*.m3u8"))
    except OSError:
        return ()
    stations: list[RadioStation] = []
    used: set[str] = set()
    for path in candidates:
        files, title = _parse_m3u(path)
        if not files:
            continue
        name = title or path.stem
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
                playlist_files=files,
            )
        )
    return tuple(stations)


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
    if station.source_type in {"local", "regional"}:
        return 3
    if station.source_type == DIRECTORY_SOURCE_TYPE:
        return 4
    if station.source_type == DIRECTORY_INTERNET_ONLY_SOURCE_TYPE:
        return 5
    if station.source_type == "afn":
        return 6
    if station.source_type == "satellite":
        return 7
    return 9


DIAL_CATEGORY_NAMES = {
    0: "Route playlist",
    1: "Freight Fate stations",
    2: "Your playlists",
    3: "Terrestrial",
    4: "Nearby internet",
    5: "Internet-only",
    6: "AFN",
    7: "Satellite",
    8: "Fallback",
    9: "Other stations",
}


def station_distance_miles(
    station: RadioStation,
    position: tuple[float, float] | None,
) -> float | None:
    if station.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES:
        return station.approximate_distance_miles
    if position is None or station.lat is None or station.lon is None:
        return None
    lat1, lon1 = (math.radians(position[0]), math.radians(position[1]))
    lat2, lon2 = (math.radians(station.lat), math.radians(station.lon))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_MI * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_signal(
    station: RadioStation,
    position: tuple[float, float] | None,
) -> RadioReception:
    if station.source_type == DIRECTORY_SOURCE_TYPE:
        return RadioReception(
            station,
            station_distance_miles(station, position),
            1.0,
            "nearby internet",
        )
    if station.source_type == DIRECTORY_INTERNET_ONLY_SOURCE_TYPE:
        return RadioReception(station, None, 1.0, "internet only")
    if station.always_available:
        return RadioReception(station, None, 1.0, "always available")
    if station.range_miles <= 0:
        return RadioReception(station, None, 1.0, "built-in")
    distance = station_distance_miles(station, position)
    if distance is None:
        return RadioReception(station, None, 0.0, "no truck position")
    if distance > station.range_miles:
        return RadioReception(station, distance, 0.0, "out of range")
    # Signal is intentionally simple and monotonic. Future FCC contours can
    # replace range_miles without changing the state/menu layer.
    signal = max(0.05, 1.0 - (distance / station.range_miles) ** 1.4)
    return RadioReception(station, distance, signal, "in range")


# Below this signal the audio starts to thin out; the floor keeps a fringe
# station audible enough to be worth chasing toward its city.
SIGNAL_FULL_VOLUME = 0.6
SIGNAL_FRINGE_FLOOR = 0.3
STATIC_SIGNAL_THRESHOLD = 0.35


def signal_volume_factor(reception: RadioReception) -> float:
    """How much of the radio volume the current signal supports.

    Satellite/built-in sources always play at full volume. Ranged stations
    hold full volume through most of their contour, then fade toward a fringe
    floor as the truck drives away, and go silent past the range edge.
    """
    station = reception.station
    if reception.fallback or station.always_available or station.range_miles <= 0:
        return 1.0
    signal = reception.signal
    if signal <= 0.0:
        return 0.0
    if signal >= SIGNAL_FULL_VOLUME:
        return 1.0
    return SIGNAL_FRINGE_FLOOR + (1.0 - SIGNAL_FRINGE_FLOOR) * (signal / SIGNAL_FULL_VOLUME)


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
    """Mutable in-cab radio state with streamer-safe defaults."""

    def __init__(
        self,
        *,
        catalog: tuple[RadioStation, ...] = DEFAULT_RADIO_CATALOG,
        enabled: bool = True,
        station_id: str = SAFE_ROUTE_PLAYLIST,
        volume: float = 0.25,
        streamer_safe: bool = True,
        position: tuple[float, float] | None = None,
    ) -> None:
        self.catalog = catalog
        self.enabled = enabled
        self.station_id = station_id
        self.preferred_station_id = station_id
        self.volume = self._clamp_volume(volume)
        self.streamer_safe = streamer_safe
        self.position = position

    @classmethod
    def from_settings(cls, settings) -> RadioState:
        return cls(
            catalog=DEFAULT_RADIO_CATALOG + load_personal_playlists(),
            enabled=bool(getattr(settings, "radio_enabled", True)),
            station_id=str(getattr(settings, "radio_station_id", SAFE_ROUTE_PLAYLIST)),
            volume=float(getattr(settings, "radio_volume", 0.25)),
            streamer_safe=bool(getattr(settings, "radio_streamer_safe", True)),
        )

    def apply_settings(self, settings) -> None:
        self.volume = self._clamp_volume(float(getattr(settings, "radio_volume", self.volume)))
        self.streamer_safe = bool(getattr(settings, "radio_streamer_safe", self.streamer_safe))

    def write_settings(self, settings) -> None:
        settings.radio_enabled = self.enabled
        settings.radio_station_id = self.preferred_station_id

    def update_position(self, position: tuple[float, float] | None) -> None:
        self.position = position

    def replace_directory_stations(
        self,
        stations,
        *,
        preserve_station_ids: tuple[str, ...] = (),
    ) -> None:
        """Install one normalized runtime snapshot without touching saved careers."""

        preserved = [
            station
            for station_id in (self.station_id, *preserve_station_ids)
            if (station := self._station_by_id(station_id)) is not None
            and station.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES
        ]
        base = tuple(
            station
            for station in self.catalog
            if station.source_type not in PUBLIC_DIRECTORY_SOURCE_TYPES
        )
        discovered = tuple(
            RadioStation(
                id=f"radio-browser:{station.uuid}",
                name=station.name,
                call_sign="",
                format=station.format,
                source=(
                    "state-matched internet-only public station"
                    if station.internet_only
                    else "nearby public internet station"
                ),
                source_type=(
                    DIRECTORY_INTERNET_ONLY_SOURCE_TYPE
                    if station.internet_only
                    else DIRECTORY_SOURCE_TYPE
                ),
                stream_url=station.stream_url,
                stream_format="HLS" if station.stream_url.lower().endswith(".m3u8") else "stream",
                codec=station.codec,
                lat=station.lat,
                lon=station.lon,
                approximate_distance_miles=station.distance_miles,
                market=station.city,
                region=station.state,
                safe_for_streaming=False,
                real_stream=True,
                always_available=station.internet_only,
                notes="Discovered at runtime through Radio Browser.",
            )
            for station in stations
        )
        discovered_ids = {station.id for station in discovered}
        for station in preserved:
            if station.id in discovered_ids:
                continue
            # A location refresh must not replace audio the player already
            # chose or a stream that is still being prepared. Keep it on the
            # dial until playback commits or the pending tune is canceled.
            discovered += (station,)
            discovered_ids.add(station.id)
        self.catalog = base + discovered

    def receivable_stations(self) -> tuple[RadioReception, ...]:
        receptions = [
            estimate_signal(station, self.position)
            for station in self.catalog
            if self._station_allowed(station)
        ]
        receivable = [
            reception
            for reception in receptions
            if reception.signal > 0.0 or reception.station.always_available
        ]
        receivable.sort(key=self._reception_sort_key)
        return tuple(receivable) or (self.fallback_reception(),)

    def available_stations(self) -> tuple[RadioStation, ...]:
        return tuple(reception.station for reception in self.receivable_stations())

    def station_by_id(self, station_id: str) -> RadioStation | None:
        return self._station_by_id(station_id)

    def station_list_lines(self, limit: int = 12, distance_text=None) -> list[str]:
        lines = []
        for reception in self.receivable_stations()[:limit]:
            station = reception.station
            selected = ""
            if station.id == self.current_station().id:
                selected = "Playing now. " if self.enabled else "Selected; radio off. "
            distance = ""
            if reception.distance_miles is not None:
                spoken = (
                    distance_text(reception.distance_miles)
                    if distance_text is not None
                    else f"{reception.distance_miles:.0f} miles"
                )
                distance = f", {spoken} away"
            lines.append(
                f"{selected}{station.display_name}. Format: {station.format}. "
                f"{reception.signal_label}{distance}. Source: {station.source}."
            )
        return lines

    def current_station(self) -> RadioStation:
        station = self._station_by_id(self.station_id)
        if station is not None and self._station_allowed(station):
            reception = estimate_signal(station, self.position)
            if reception.signal > 0.0 or station.always_available:
                return station
        fallback = self.fallback_station()
        self.station_id = fallback.id
        return fallback

    def current_reception(self) -> RadioReception:
        station = self.current_station()
        if station.fallback:
            return self.fallback_reception()
        return estimate_signal(station, self.position)

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
        return self.play(backend, prefix="Radio on.")

    def tune(self, direction: int, backend: RadioPlaybackBackend | None = None) -> RadioAction:
        reception = self.next_reception(direction)
        self.station_id = reception.station.id
        self.preferred_station_id = reception.station.id
        if not self.enabled:
            return RadioAction(
                f"Radio off. Selected {self._station_phrase(reception)}.",
                reception.station,
                enabled=False,
                reception=reception,
            )
        return self.play(backend, prefix=f"Tuned to {reception.station.display_name}.")

    def next_reception(
        self,
        direction: int,
        *,
        from_station_id: str | None = None,
    ) -> RadioReception:
        """Return the next dial entry without changing the playing station."""

        receptions = self.receivable_stations()
        current_id = from_station_id or self.current_station().id
        ids = [reception.station.id for reception in receptions]
        try:
            index = ids.index(current_id)
        except ValueError:
            index = 0
        return receptions[(index + direction) % len(receptions)]

    def tune_category(
        self, direction: int, backend: RadioPlaybackBackend | None = None
    ) -> RadioAction:
        """Jump to the first station of the previous/next dial category.

        Twenty-five AFN entries in a row buried the terrestrial section for
        anyone tuning linearly (owner, 2026-07-20); this is the escape. Only
        categories with a receivable station exist to jump to, and the spoken
        line leads with the category so the landing is oriented."""
        reception, label = self.next_category_reception(direction)
        self.station_id = reception.station.id
        self.preferred_station_id = reception.station.id
        if not self.enabled:
            return RadioAction(
                f"Radio off. {label}. Selected {self._station_phrase(reception)}.",
                reception.station,
                enabled=False,
                reception=reception,
            )
        return self.play(backend, prefix=f"{label}. Tuned to {reception.station.display_name}.")

    def next_category_reception(
        self,
        direction: int,
        *,
        from_station_id: str | None = None,
    ) -> tuple[RadioReception, str]:
        """Return the next category landing without changing playback."""

        receptions = self.receivable_stations()
        groups: list[int] = []
        for reception in receptions:
            group = _dial_group(reception.station)
            if group not in groups:
                groups.append(group)
        current = self._station_by_id(from_station_id or "") or self.current_station()
        current_group = _dial_group(current)
        if current_group in groups:
            index = groups.index(current_group)
            target = groups[(index + direction) % len(groups)]
        else:
            target = groups[0]
        reception = next(r for r in receptions if _dial_group(r.station) == target)
        label = DIAL_CATEGORY_NAMES.get(target, "Radio")
        return reception, label

    def select_station(
        self,
        station_id: str,
        backend: RadioPlaybackBackend | None = None,
    ) -> RadioAction:
        station = self._station_by_id(station_id)
        if station is None or not self._station_allowed(station):
            return self.play(backend, prefix="Radio fallback.")
        self.station_id = station.id
        self.preferred_station_id = station.id
        if not self.enabled:
            return RadioAction(
                f"Radio off. Selected {self._station_phrase(estimate_signal(station, self.position))}.",
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
            original = reception
            fallback = self.fallback_reception()
            self.station_id = fallback.station.id
            try:
                backend.play_station(fallback.station, self.volume)
            except Exception:
                self._stop(backend)
            return RadioAction(
                self._play_message(
                    "Radio fallback.",
                    fallback,
                    extra=f"{original.station.display_name} is unavailable.",
                ),
                fallback.station,
                enabled=True,
                reception=fallback,
                fallback_used=True,
            )
        return RadioAction(
            self._play_message(prefix, reception), station, enabled=True, reception=reception
        )

    def _station_allowed(self, station: RadioStation) -> bool:
        if not station.supported:
            return False
        if station.source_type == PERSONAL_PLAYLIST_SOURCE_TYPE:
            # Personal media rides the streamer-safe gate like public streams
            # do because the game cannot vouch for its licensing. Your own
            # files do not depend on Online services.
            return not self.streamer_safe
        if not station.real_stream:
            return True
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

    @staticmethod
    def _reception_sort_key(reception: RadioReception) -> tuple:
        station = reception.station
        distance = reception.distance_miles if reception.distance_miles is not None else 0.0
        return (
            _dial_group(station),
            distance if station.source_type == DIRECTORY_SOURCE_TYPE else 0.0,
            station.call_sign.casefold(),
            station.name.casefold(),
            station.id,
        )

    @staticmethod
    def _stop(backend: RadioPlaybackBackend | None) -> None:
        if backend is None:
            return
        with contextlib.suppress(Exception):
            backend.stop_radio()
