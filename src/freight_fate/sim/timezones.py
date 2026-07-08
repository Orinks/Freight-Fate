"""United States time zones and the local wall clock.

The career clock (``profile.game_hours``) and the trip clock
(``Trip.current_hour``) are a single absolute timeline defined as Eastern
Time; time compression only changes how fast that timeline advances. A time
zone is a pure display layer over it: the local wall clock at any place is
the absolute clock plus that place's fixed offset. Nothing that measures
durations -- hours of service, deadlines, seasons, market days -- ever
shifts; only what the player hears spoken as "the time" does.

Zones are derived offline and deterministically from coordinates the world
data already carries (cities and baked route points both have lat/lon plus a
state). Whole states resolve through a table; the states a zone boundary
splits (Tennessee, Kentucky, Indiana, the Florida panhandle, west Texas, and
friends) use curated longitude/latitude rules that track the real boundary at
game fidelity. Daylight saving time is deliberately not modeled: the career
calendar is abstract, and fixed standard offsets keep the spoken clock
predictable for screen reader players.
"""

from __future__ import annotations

from dataclasses import dataclass

from .hos import clock_text


@dataclass(frozen=True)
class TimeZone:
    key: str
    name: str  # spoken: "Central Time"
    offset_h: float  # hours relative to Eastern, the game's reference clock


EASTERN = TimeZone("eastern", "Eastern Time", 0.0)
CENTRAL = TimeZone("central", "Central Time", -1.0)
MOUNTAIN = TimeZone("mountain", "Mountain Time", -2.0)
PACIFIC = TimeZone("pacific", "Pacific Time", -3.0)
ALASKA = TimeZone("alaska", "Alaska Time", -4.0)
HAWAII = TimeZone("hawaii", "Hawaii Time", -5.0)

ZONES: dict[str, TimeZone] = {
    zone.key: zone for zone in (EASTERN, CENTRAL, MOUNTAIN, PACIFIC, ALASKA, HAWAII)
}

# States that sit entirely inside one zone, keyed by the full state name the
# world data uses. Arizona skips daylight saving in reality; with no DST in
# the model it is plain Mountain here.
_STATE_ZONES: dict[str, TimeZone] = {
    "Connecticut": EASTERN,
    "Delaware": EASTERN,
    "District of Columbia": EASTERN,
    "Georgia": EASTERN,
    "Maine": EASTERN,
    "Maryland": EASTERN,
    "Massachusetts": EASTERN,
    "New Hampshire": EASTERN,
    "New Jersey": EASTERN,
    "New York": EASTERN,
    "North Carolina": EASTERN,
    "Ohio": EASTERN,
    "Pennsylvania": EASTERN,
    "Rhode Island": EASTERN,
    "South Carolina": EASTERN,
    "Vermont": EASTERN,
    "Virginia": EASTERN,
    "West Virginia": EASTERN,
    "Alabama": CENTRAL,
    "Arkansas": CENTRAL,
    "Illinois": CENTRAL,
    "Iowa": CENTRAL,
    "Louisiana": CENTRAL,
    "Minnesota": CENTRAL,
    "Mississippi": CENTRAL,
    "Missouri": CENTRAL,
    "Oklahoma": CENTRAL,
    "Wisconsin": CENTRAL,
    "Arizona": MOUNTAIN,
    "Colorado": MOUNTAIN,
    "Montana": MOUNTAIN,
    "New Mexico": MOUNTAIN,
    "Utah": MOUNTAIN,
    "Wyoming": MOUNTAIN,
    "California": PACIFIC,
    "Washington": PACIFIC,
    "Alaska": ALASKA,
    "Hawaii": HAWAII,
}


def _florida(lat: float, lon: float) -> TimeZone:
    # The panhandle west of the Apalachicola River keeps Central time.
    return CENTRAL if lon < -85.1 else EASTERN


def _indiana(lat: float, lon: float) -> TimeZone:
    # The Gary and Evansville corners follow Chicago; the rest is Eastern.
    return CENTRAL if lon < -87.25 else EASTERN


def _kentucky(lat: float, lon: float) -> TimeZone:
    # Western Kentucky (Bowling Green, Paducah) is Central; Louisville and
    # Lexington are Eastern.
    return CENTRAL if lon < -86.0 else EASTERN


def _tennessee(lat: float, lon: float) -> TimeZone:
    # East Tennessee (Knoxville, Chattanooga) is Eastern; the boundary runs
    # just west of Chattanooga, so Nashville and Memphis are Central.
    return CENTRAL if lon < -85.5 else EASTERN


def _michigan(lat: float, lon: float) -> TimeZone:
    # Four western Upper Peninsula counties border Wisconsin's clock.
    return CENTRAL if lon < -89.5 and lat > 45.5 else EASTERN


def _north_dakota(lat: float, lon: float) -> TimeZone:
    # The southwest corner below the Missouri River is Mountain.
    return MOUNTAIN if lon < -102.25 and lat < 47.5 else CENTRAL


def _south_dakota(lat: float, lon: float) -> TimeZone:
    # West River (Rapid City) is Mountain; Pierre and eastward are Central.
    return MOUNTAIN if lon < -101.0 else CENTRAL


def _nebraska(lat: float, lon: float) -> TimeZone:
    # The panhandle from about Ogallala west is Mountain.
    return MOUNTAIN if lon < -101.4 else CENTRAL


def _kansas(lat: float, lon: float) -> TimeZone:
    # The four westernmost border counties (Goodland) are Mountain.
    return MOUNTAIN if lon < -101.5 else CENTRAL


def _texas(lat: float, lon: float) -> TimeZone:
    # Only El Paso and Hudspeth counties, in the far western wedge.
    return MOUNTAIN if lon < -104.9 else CENTRAL


def _idaho(lat: float, lon: float) -> TimeZone:
    # The panhandle north of the Salmon River follows Spokane's clock.
    return PACIFIC if lat > 45.5 else MOUNTAIN


def _oregon(lat: float, lon: float) -> TimeZone:
    # Ontario and most of Malheur County, on the Boise side of the desert.
    return MOUNTAIN if lon > -117.3 and lat < 44.5 else PACIFIC


def _nevada(lat: float, lon: float) -> TimeZone:
    # The West Wendover sliver on the Utah line runs on Mountain time.
    return MOUNTAIN if lon > -114.1 else PACIFIC


_SPLIT_STATE_ZONES = {
    "Florida": _florida,
    "Indiana": _indiana,
    "Kentucky": _kentucky,
    "Tennessee": _tennessee,
    "Michigan": _michigan,
    "North Dakota": _north_dakota,
    "South Dakota": _south_dakota,
    "Nebraska": _nebraska,
    "Kansas": _kansas,
    "Texas": _texas,
    "Idaho": _idaho,
    "Oregon": _oregon,
    "Nevada": _nevada,
}


def zone_for(lat: float, lon: float, state: str = "") -> TimeZone:
    """The time zone at a coordinate, using the state when one is known.

    With no usable state, rough boundary meridians decide -- good enough for
    the open road between known places. Missing geometry (0, 0) resolves to
    Eastern, the reference zone, so a synthetic or incomplete leg keeps the
    clock it always had.
    """
    split = _SPLIT_STATE_ZONES.get(state)
    if split is not None:
        return split(lat, lon)
    zone = _STATE_ZONES.get(state)
    if zone is not None:
        return zone
    if lat == 0.0 and lon == 0.0:
        return EASTERN
    if lon >= -85.5:
        return EASTERN
    if lon >= -102.0:
        return CENTRAL
    if lon >= -114.5:
        return MOUNTAIN
    return PACIFIC


def city_zone(city) -> TimeZone:
    """The zone a City (or anything with lat, lon, and state) lives in."""
    return zone_for(city.lat, city.lon, city.state)


def to_local(game_hours: float, zone: TimeZone) -> float:
    """Absolute (Eastern-reference) hours shifted onto a zone's wall clock.

    Not wrapped to a day: callers doing clock math keep the full timeline,
    and ``clock_text`` wraps for speech on its own.
    """
    return game_hours + zone.offset_h


def local_clock_text(game_hours: float, zone: TimeZone, *, with_zone: bool = False) -> str:
    """Spoken local wall clock, optionally naming the zone: '2:15 PM Central Time'."""
    text = clock_text(to_local(game_hours, zone))
    return f"{text} {zone.name}" if with_zone else text


def appointment_text(now_game_hours: float, hours_from_now: float, zone: TimeZone) -> str:
    """A future moment as a local appointment: '6 PM Central Time tomorrow'.

    The day qualifier counts local midnights between now and the moment, so
    "tomorrow" means what a driver parked at the receiver would mean by it.
    """
    local_now = to_local(now_game_hours, zone)
    local_due = local_now + max(0.0, hours_from_now)
    days_ahead = int(local_due // 24.0) - int(local_now // 24.0)
    base = f"{clock_text(local_due)} {zone.name}"
    if days_ahead <= 0:
        return base
    if days_ahead == 1:
        return f"{base} tomorrow"
    return f"{base} in {days_ahead} days"
