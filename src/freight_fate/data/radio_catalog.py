"""The in-cab radio station catalog: what stations exist and where they reach.

Built at development time by ``tools/build_radio_catalog.py`` from Radio
Browser (stream URLs) and Wikidata (transmitter coordinates), then checked in.
The game only ever reads it, and reads it offline: nothing here touches the
network. The one thing that does reach the internet is the audio stream
itself, and only after the player turns the radio on.

Three kinds of station, which is the whole reception model:

* **local** -- a real broadcaster with a transmitter position and a coverage
  radius. Receivable only near that transmitter, and it fades at the edge.
* **web** -- an internet-only station with no transmitter. Always receivable.
* **satellite** -- always receivable, and the fallback whenever a stream fails.

Release builds compile the catalog in via ``tools/bake_radio.py``; source
checkouts read the JSON. Same arrangement as the world data, and for the same
reason: packaged builds ship no editable data files.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).parent / "radio" / "stations.json"

BAND_FM = "FM"
BAND_AM = "AM"
BAND_WEB = "web"
BAND_SATELLITE = "satellite"
BROADCAST_BANDS = (BAND_FM, BAND_AM)


@dataclass(frozen=True)
class Station:
    """One tunable station.

    ``frequency`` is megahertz on FM and kilohertz on AM, matching how the
    numbers are said out loud; it is 0.0 for web and satellite stations, which
    have no place on a dial.
    """

    id: str
    name: str
    url: str
    band: str
    call_sign: str = ""
    frequency: float = 0.0
    codec: str = ""
    bitrate: int = 0
    tags: str = ""
    lat: float = 0.0
    lon: float = 0.0
    radius_mi: float = 0.0
    radius_source: str = ""

    @property
    def is_broadcast(self) -> bool:
        """True for a station with a transmitter, i.e. limited reception."""
        return self.band in BROADCAST_BANDS


@dataclass(frozen=True)
class RadioCatalog:
    local: tuple[Station, ...] = ()
    web: tuple[Station, ...] = ()
    satellite: tuple[Station, ...] = ()

    @property
    def all_stations(self) -> tuple[Station, ...]:
        return self.local + self.web + self.satellite

    def by_id(self, station_id: str) -> Station | None:
        for station in self.all_stations:
            if station.id == station_id:
                return station
        return None


def _station(raw: dict) -> Station | None:
    """One catalog record, or None when it is unusable.

    Tolerant on purpose: a malformed row costs the player that one station,
    never the radio.
    """
    try:
        station_id = str(raw["id"])
        name = str(raw["name"])
        url = str(raw["url"])
        band = str(raw["band"])
    except (KeyError, TypeError):
        return None
    if not (station_id and name and url and band):
        return None
    return Station(
        id=station_id,
        name=name,
        url=url,
        band=band,
        call_sign=str(raw.get("call_sign") or ""),
        frequency=float(raw.get("frequency") or 0.0),
        codec=str(raw.get("codec") or ""),
        bitrate=int(raw.get("bitrate") or 0),
        tags=str(raw.get("tags") or ""),
        lat=float(raw.get("lat") or 0.0),
        lon=float(raw.get("lon") or 0.0),
        radius_mi=float(raw.get("radius_mi") or 0.0),
        radius_source=str(raw.get("radius_source") or ""),
    )


def _stations(data: dict, key: str) -> tuple[Station, ...]:
    rows = data.get(key)
    if not isinstance(rows, list):
        return ()
    built = (_station(row) for row in rows if isinstance(row, dict))
    return tuple(station for station in built if station is not None)


def load_catalog(path: Path | None = None) -> RadioCatalog:
    """Read the catalog, preferring the baked-in module in frozen builds.

    An unreadable or missing catalog yields an empty one. The radio then has
    nothing to tune and says so, which is a better failure than a game that
    will not start.
    """
    data: dict | None = None
    if path is None:
        try:
            from . import _baked_radio
        except ImportError:
            path = CATALOG_PATH
        else:
            data = _baked_radio.load()
    if data is None:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            log.warning("Could not read the radio catalog at %s", path, exc_info=True)
            return RadioCatalog()
    if not isinstance(data, dict):
        log.warning("Radio catalog is not an object; ignoring it")
        return RadioCatalog()
    return RadioCatalog(
        local=_stations(data, "local"),
        web=_stations(data, "web"),
        satellite=_stations(data, "satellite"),
    )


_catalog: RadioCatalog | None = None


def get_radio_catalog() -> RadioCatalog:
    """Shared catalog instance (the data is immutable)."""
    global _catalog
    if _catalog is None:
        _catalog = load_catalog()
    return _catalog
