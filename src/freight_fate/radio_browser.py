"""Radio Browser mirror client for bounded nearby and internet-only stations."""

from __future__ import annotations

import json
import math
import random
import re
import socket
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass

from .net import ssl_context
from .radio_url_safety import UnsafeStreamURL, validate_stream_url

USER_AGENT = "Freight-Fate/1.9 (+https://github.com/Orinks/Freight-Fate)"
MIRROR_LOOKUP_HOST = "all.api.radio-browser.info"
DIRECTORY_TIMEOUT_S = 5.0
DIRECTORY_QUERY_LIMIT = 300
NEARBY_DISTANCE_CAP_MI = 175.0
NEARBY_DIAL_LIMIT = 24
INTERNET_ONLY_RESERVE_DIVISOR = 4
SUPPORTED_CODECS = {"MP3", "AAC", "AAC+", "OGG", "OPUS"}
MIN_BITRATE_KBPS = 24
MAX_BITRATE_KBPS = 512


@dataclass(frozen=True)
class DirectoryStation:
    uuid: str
    name: str
    format: str
    codec: str
    bitrate: int
    stream_url: str
    lat: float | None
    lon: float | None
    distance_miles: float | None
    state: str
    city: str = ""
    internet_only: bool = False

    @classmethod
    def from_cache(cls, value: dict) -> DirectoryStation:
        known = {field: value[field] for field in cls.__dataclass_fields__ if field in value}
        return cls(**known)

    def to_cache(self) -> dict:
        return asdict(self)


def sanitize_directory_text(value, *, limit: int) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = "".join(" " if unicodedata.category(char).startswith("C") else char for char in text)
    text = re.sub(r"\s+", " ", text).strip(" \t\r\n,;|")
    return text[:limit].rstrip()


def _float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def distance_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = (math.radians(a[0]), math.radians(a[1]))
    lat2, lon2 = (math.radians(b[0]), math.radians(b[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 3958.8 * 2 * math.atan2(math.sqrt(value), math.sqrt(max(0.0, 1 - value)))


def _state_matches(row: dict, state_name: str, state_code: str) -> bool:
    state = sanitize_directory_text(row.get("state"), limit=80).casefold()
    iso = sanitize_directory_text(row.get("iso_3166_2"), limit=16).upper()
    return state == state_name.casefold() or iso == f"US-{state_code.upper()}"


def _station_format(row: dict, codec: str, bitrate: int) -> str:
    tags = []
    for raw in sanitize_directory_text(row.get("tags"), limit=120).split(","):
        tag = sanitize_directory_text(raw, limit=28)
        if tag and tag.casefold() not in {existing.casefold() for existing in tags}:
            tags.append(tag)
        if len(tags) == 3:
            break
    description = ", ".join(tags) if tags else "internet radio"
    return sanitize_directory_text(f"{description}; {codec}, {bitrate} kilobits", limit=96)


def normalize_stations(
    rows: Sequence[dict],
    *,
    state_name: str,
    state_code: str,
    position: tuple[float, float],
    resolver=None,
    distance_cap_miles: float = NEARBY_DISTANCE_CAP_MI,
    limit: int = NEARBY_DIAL_LIMIT,
) -> tuple[DirectoryStation, ...]:
    """Return a bounded mix of nearby and state-matched internet stations."""

    nearby = []
    internet_only = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        uuid = sanitize_directory_text(row.get("stationuuid"), limit=64).lower()
        if not re.fullmatch(r"[0-9a-f-]{32,36}", uuid):
            continue
        if sanitize_directory_text(row.get("countrycode"), limit=4).upper() != "US":
            continue
        if not _state_matches(row, state_name, state_code) or _int(row.get("lastcheckok")) != 1:
            continue
        codec = sanitize_directory_text(row.get("codec"), limit=16).upper()
        bitrate = _int(row.get("bitrate"))
        if codec not in SUPPORTED_CODECS or bitrate is None:
            continue
        if _int(row.get("hls")) == 1:
            # BASSHLS is optional, so HLS is not a dependable active-backend
            # transport. Ordinary HTTP audio streams work in stock BASS.
            continue
        if bitrate < MIN_BITRATE_KBPS or bitrate > MAX_BITRATE_KBPS:
            continue
        lat, lon = _float(row.get("geo_lat")), _float(row.get("geo_long"))
        credible_coordinates = bool(
            lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
        )
        distance = distance_miles(position, (lat, lon)) if credible_coordinates else None
        if distance is not None and distance > distance_cap_miles:
            continue
        name = sanitize_directory_text(row.get("name"), limit=60)
        if not name:
            continue
        raw_url = row.get("url_resolved") or row.get("url")
        try:
            url = (
                validate_stream_url(str(raw_url), resolver=resolver)
                if resolver is not None
                else validate_stream_url(str(raw_url))
            )
        except (UnsafeStreamURL, OSError):
            continue
        if urllib.parse.urlsplit(url).path.casefold().endswith((".m3u8", ".m3u")):
            continue
        state = sanitize_directory_text(row.get("state"), limit=40) or state_name
        station = DirectoryStation(
            uuid=uuid,
            name=name,
            format=_station_format(row, codec, bitrate),
            codec=codec,
            bitrate=bitrate,
            stream_url=url,
            lat=lat if credible_coordinates else None,
            lon=lon if credible_coordinates else None,
            distance_miles=distance,
            state=state,
            city=sanitize_directory_text(row.get("city"), limit=60),
            internet_only=not credible_coordinates,
        )
        (internet_only if station.internet_only else nearby).append(station)
    return _bounded_station_mix(nearby, internet_only, limit=limit)


def filter_cached_stations(
    stations: Sequence[DirectoryStation],
    *,
    position: tuple[float, float],
    state_name: str = "",
    resolver=None,
    distance_cap_miles: float = NEARBY_DISTANCE_CAP_MI,
    limit: int = NEARBY_DIAL_LIMIT,
) -> tuple[DirectoryStation, ...]:
    """Revalidate cached metadata and recalculate distance at the new center."""

    nearby = []
    internet_only = []
    for station in stations:
        uuid = sanitize_directory_text(station.uuid, limit=64).lower()
        codec = sanitize_directory_text(station.codec, limit=16).upper()
        bitrate = _int(station.bitrate)
        lat, lon = _float(station.lat), _float(station.lon)
        has_coordinates = bool(
            lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
        )
        if (
            not re.fullmatch(r"[0-9a-f-]{32,36}", uuid)
            or codec not in SUPPORTED_CODECS
            or bitrate is None
            or not MIN_BITRATE_KBPS <= bitrate <= MAX_BITRATE_KBPS
            or (
                station.internet_only
                and (
                    not sanitize_directory_text(station.state, limit=40)
                    or state_name
                    and sanitize_directory_text(station.state, limit=40).casefold()
                    != state_name.casefold()
                )
            )
            or (not station.internet_only and not has_coordinates)
        ):
            continue
        name = sanitize_directory_text(station.name, limit=60)
        if not name:
            continue
        try:
            url = (
                validate_stream_url(str(station.stream_url), resolver=resolver)
                if resolver is not None
                else validate_stream_url(str(station.stream_url))
            )
        except (UnsafeStreamURL, OSError):
            continue
        if urllib.parse.urlsplit(url).path.casefold().endswith((".m3u8", ".m3u")):
            continue
        distance = distance_miles(position, (lat, lon)) if has_coordinates else None
        if distance is not None and distance > distance_cap_miles:
            continue
        updated = DirectoryStation(
            uuid=uuid,
            name=name,
            format=sanitize_directory_text(station.format, limit=96),
            codec=codec,
            bitrate=bitrate,
            stream_url=url,
            lat=lat if has_coordinates else None,
            lon=lon if has_coordinates else None,
            distance_miles=distance,
            state=sanitize_directory_text(station.state, limit=40),
            city=sanitize_directory_text(station.city, limit=60),
            internet_only=not has_coordinates,
        )
        (internet_only if updated.internet_only else nearby).append(updated)
    return _bounded_station_mix(nearby, internet_only, limit=limit)


def _bounded_station_mix(
    nearby: Sequence[DirectoryStation],
    internet_only: Sequence[DirectoryStation],
    *,
    limit: int,
) -> tuple[DirectoryStation, ...]:
    """Deduplicate and reserve part of a bounded dial for each useful class."""

    maximum = max(0, limit)
    nearby_sorted = sorted(
        nearby,
        key=lambda station: (
            round(station.distance_miles or 0.0, 3),
            station.name.casefold(),
            station.uuid,
        ),
    )
    internet_sorted = sorted(
        internet_only,
        key=lambda station: (station.name.casefold(), station.uuid),
    )
    seen_uuid: set[str] = set()
    seen_url: set[str] = set()

    def unique(stations):
        result = []
        for station in stations:
            url_key = station.stream_url.casefold()
            if station.uuid in seen_uuid or url_key in seen_url:
                continue
            seen_uuid.add(station.uuid)
            seen_url.add(url_key)
            result.append(station)
        return result

    nearby_unique = unique(nearby_sorted)
    internet_unique = unique(internet_sorted)
    if maximum == 0:
        return ()
    if not nearby_unique:
        return tuple(internet_unique[:maximum])
    if not internet_unique or maximum == 1:
        return tuple(nearby_unique[:maximum])
    internet_reserve = max(1, maximum // INTERNET_ONLY_RESERVE_DIVISOR)
    selected_nearby = nearby_unique[: max(1, maximum - internet_reserve)]
    selected_internet = internet_unique[: maximum - len(selected_nearby)]
    remaining = maximum - len(selected_nearby) - len(selected_internet)
    if remaining:
        selected_nearby.extend(nearby_unique[len(selected_nearby) :][:remaining])
    return tuple((*selected_nearby, *selected_internet))


def discover_mirrors(
    *,
    lookup: Callable[..., Iterable[tuple]] = socket.getaddrinfo,
    reverse: Callable[[str], tuple[str, list[str], list[str]]] = socket.gethostbyaddr,
    shuffle: Callable[[list[str]], None] = random.shuffle,
) -> tuple[str, ...]:
    """Follow Radio Browser's documented DNS and reverse-DNS mirror discovery."""

    records = lookup(MIRROR_LOOKUP_HOST, 443, type=socket.SOCK_STREAM)
    hosts = []
    for record in records:
        address = record[4][0]
        try:
            host = reverse(address)[0].rstrip(".").lower()
        except OSError:
            continue
        if host.endswith(".api.radio-browser.info") and host not in hosts:
            hosts.append(host)
    shuffle(hosts)
    if not hosts:
        raise ConnectionError("no Radio Browser mirrors found")
    return tuple(hosts)


class RadioBrowserClient:
    def __init__(
        self,
        *,
        mirrors: Callable[[], tuple[str, ...]] = discover_mirrors,
        opener: Callable[..., object] = urllib.request.urlopen,
        timeout: float = DIRECTORY_TIMEOUT_S,
    ) -> None:
        self._mirrors = mirrors
        self._opener = opener
        self.timeout = timeout

    def _json(self, path: str) -> tuple[object, str]:
        last_error: Exception | None = None
        for host in self._mirrors():
            request = urllib.request.Request(
                f"https://{host}{path}",
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            try:
                with self._opener(request, timeout=self.timeout, context=ssl_context()) as response:
                    return json.loads(response.read().decode("utf-8")), host
            except (OSError, UnicodeError, ValueError, urllib.error.URLError) as exc:
                last_error = exc
        raise ConnectionError("all Radio Browser mirrors failed") from last_error

    def stations_for_state(self, state_name: str) -> tuple[list[dict], str]:
        query = urllib.parse.urlencode(
            {
                "countrycode": "US",
                "state": state_name,
                "stateExact": "true",
                "hidebroken": "true",
                "order": "clickcount",
                "reverse": "true",
                "limit": str(DIRECTORY_QUERY_LIMIT),
            }
        )
        value, host = self._json(f"/json/stations/search?{query}")
        if not isinstance(value, list):
            raise ValueError("station response is not a list")
        return value, host

    def record_click(self, station_uuid: str) -> None:
        safe_uuid = sanitize_directory_text(station_uuid, limit=36)
        if not re.fullmatch(r"[0-9a-f-]{32,36}", safe_uuid):
            return
        self._json(f"/json/url/{safe_uuid}")
