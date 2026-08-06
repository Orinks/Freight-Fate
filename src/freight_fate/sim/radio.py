"""In-cab radio: which stations reach the truck, and how the driver tunes them.

Pygame-free and deterministic, like the rest of ``sim``: no audio, no network,
no randomness. Given a position it answers which stations are receivable and
how strong each signal is; given a keypress it moves along the dial. Playing
the audio is the game layer's job (``AudioEngine.play_radio``).

Reception is geometry. A broadcast station covers a circle around its
transmitter; inside the inner part of that circle the signal is full, and from
there it falls off linearly to nothing at the edge. Web and satellite stations
have no transmitter and are always at full strength.

Leaving a station's coverage is a normal, announced event, not an error: the
radio says the station was lost and falls back to the satellite station, which
is always in range. The driver can seek back to whatever the next town offers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..data.radio_catalog import (
    BAND_AM,
    BAND_FM,
    BAND_SATELLITE,
    BAND_WEB,
    RadioCatalog,
    Station,
    get_radio_catalog,
)

EARTH_RADIUS_MI = 3958.8

# Fraction of the coverage radius that still carries a full-strength signal.
# Inside it the station simply sounds like a station; beyond it the driver can
# hear the reception going, which is the cue that the dial is about to change.
FULL_SIGNAL_FRACTION = 0.6

# How far the truck must move before the in-range list is recomputed. The list
# only changes over miles, and recomputing it every frame would walk the whole
# catalog sixty times a second for no audible difference.
RETUNE_DISTANCE_MI = 1.0

# Signal below this is too weak to hold; the station counts as lost.
SIGNAL_LOST = 0.0

# The bands a driver can select, in the order the band key walks them.
BANDS = (BAND_FM, BAND_AM, BAND_WEB, BAND_SATELLITE)

_BAND_NAMES = {
    BAND_FM: "F M",
    BAND_AM: "A M",
    BAND_WEB: "web radio",
    BAND_SATELLITE: "satellite",
}

# Spoken signal strength, strongest first. Screen reader users navigate by
# these words, so they stay a small fixed set.
_SIGNAL_WORDS = (
    (0.75, "strong signal"),
    (0.45, "good signal"),
    (0.2, "fair signal"),
    (0.0, "weak signal"),
)


def distance_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles."""
    rad = math.pi / 180.0
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_MI * math.asin(math.sqrt(min(1.0, a)))


def signal_strength(station: Station, lat: float, lon: float) -> float:
    """How well ``station`` comes in at a position, from 0.0 to 1.0.

    Web and satellite stations are always 1.0 -- they arrive over the same
    connection wherever the truck is.
    """
    if not station.is_broadcast:
        return 1.0
    radius = station.radius_mi
    if radius <= 0.0:
        return 0.0
    distance = distance_mi(lat, lon, station.lat, station.lon)
    if distance >= radius:
        return 0.0
    full = radius * FULL_SIGNAL_FRACTION
    if distance <= full:
        return 1.0
    return max(0.0, (radius - distance) / max(1e-6, radius - full))


def signal_text(strength: float) -> str:
    """The spoken words for a signal strength."""
    for threshold, words in _SIGNAL_WORDS:
        if strength >= threshold:
            return words
    return _SIGNAL_WORDS[-1][1]


def band_text(band: str) -> str:
    """The spoken name of a band.

    FM and AM are spelled out with spaces so a screen reader says the letters
    rather than trying to pronounce a word.
    """
    return _BAND_NAMES.get(band, band)


def frequency_text(station: Station) -> str:
    """The dial position, e.g. "92.5 F M" or "1050 A M"; empty off the dial."""
    if station.band == BAND_FM:
        return f"{station.frequency:.1f} {band_text(BAND_FM)}"
    if station.band == BAND_AM:
        return f"{station.frequency:.0f} {band_text(BAND_AM)}"
    return ""


def station_text(station: Station, strength: float = 1.0) -> str:
    """The full spoken identity of a station: who it is, where, and how well.

    A broadcast station leads with its call sign and dial position, because
    that is how a driver names a station out loud. Web and satellite stations
    have neither, so they lead with their name.
    """
    parts: list[str] = []
    if station.call_sign:
        parts.append(station.call_sign)
    dial = frequency_text(station)
    if dial:
        parts.append(dial)
    # The catalog already trims a name that only repeats the call sign, but an
    # older catalog or a hand-written overlay entry can still carry one.
    if station.name and station.name.upper() != station.call_sign.upper():
        parts.append(station.name)
    if station.band == BAND_SATELLITE:
        parts.append(band_text(BAND_SATELLITE))
    if station.tags:
        parts.append(station.tags)
    if station.is_broadcast:
        parts.append(signal_text(strength))
    return ", ".join(parts)


@dataclass(frozen=True)
class Reception:
    """What changed about reception when the truck moved."""

    lost: Station | None = None
    fell_back_to: Station | None = None


class RadioTuner:
    """The radio as the driver experiences it: a band, a station, a signal.

    Owns no audio. The driving state reads :attr:`station` and :attr:`signal`
    each frame and points the audio engine at the stream.
    """

    def __init__(
        self,
        catalog: RadioCatalog | None = None,
        *,
        lat: float = 0.0,
        lon: float = 0.0,
    ) -> None:
        self.catalog = catalog if catalog is not None else get_radio_catalog()
        self.on = False
        self.band = BAND_FM
        self.station: Station | None = None
        self._lat = lat
        self._lon = lon
        self._in_range: tuple[Station, ...] = ()
        self._computed_at: tuple[float, float] | None = None
        # Stations whose stream would not play this session. A dead stream is
        # a station you cannot receive, so it leaves the dial rather than
        # sitting there waiting to be tuned into the same failure again.
        self._unavailable: set[str] = set()
        self._recompute()

    # -- reception ------------------------------------------------------------

    @property
    def signal(self) -> float:
        """Signal strength of the tuned station, or 0.0 with nothing tuned."""
        if self.station is None:
            return 0.0
        return signal_strength(self.station, self._lat, self._lon)

    @property
    def in_range(self) -> tuple[Station, ...]:
        """Broadcast stations whose coverage reaches the truck, in dial order."""
        return self._in_range

    @property
    def position(self) -> tuple[float, float]:
        """Where the tuner believes the truck is."""
        return (self._lat, self._lon)

    def stations_for(self, band: str) -> tuple[Station, ...]:
        """Everything tunable on a band right now.

        One frequency holds one station, the way a real dial does: where two
        distant transmitters share a frequency, the stronger one here wins.
        Without this the dial reads out three different stations all called
        88.3, which is both wrong and confusing to arrow through.
        """
        if band == BAND_WEB:
            return tuple(s for s in self.catalog.web if s.id not in self._unavailable)
        if band == BAND_SATELLITE:
            return tuple(s for s in self.catalog.satellite if s.id not in self._unavailable)
        strongest: dict[float, Station] = {}
        for station in self._in_range:
            if station.band != band or station.id in self._unavailable:
                continue
            held = strongest.get(station.frequency)
            if held is None or signal_strength(station, self._lat, self._lon) > signal_strength(
                held, self._lat, self._lon
            ):
                strongest[station.frequency] = station
        return tuple(strongest[freq] for freq in sorted(strongest))

    def _recompute(self) -> None:
        """Refresh the in-range list for the current position."""
        lat, lon = self._lat, self._lon
        # A degree of latitude is about 69 miles and a degree of longitude
        # never more, so this box cannot exclude a station that is in range.
        span = 3.0
        self._in_range = tuple(
            station
            for station in self.catalog.local
            if abs(station.lat - lat) <= span
            and abs(station.lon - lon) <= span * 2.0
            and signal_strength(station, lat, lon) > SIGNAL_LOST
        )
        self._computed_at = (lat, lon)

    def set_position(self, lat: float, lon: float) -> Reception:
        """Move the truck. Returns what the driver should be told, if anything."""
        self._lat, self._lon = lat, lon
        anchor = self._computed_at
        moved = anchor is None or distance_mi(anchor[0], anchor[1], lat, lon) >= (
            RETUNE_DISTANCE_MI
        )
        if moved:
            self._recompute()
        station = self.station
        if station is None or not station.is_broadcast:
            return Reception()
        if signal_strength(station, lat, lon) > SIGNAL_LOST:
            return Reception()
        if not moved:
            # The in-range list is only refreshed every mile, which is fine
            # until a station drops -- at that moment it is stale exactly
            # where it matters, and the station that just went would still be
            # in it, so the radio would hand over to the one it just lost.
            self._recompute()
        return Reception(lost=station, fell_back_to=self.hand_over_from(station))

    def mark_unavailable(self, station: Station) -> None:
        """Take a station off the dial for this session.

        Called when its stream refuses to play. Without this the driver walks
        straight back into the same dead station every time they change band,
        because it is still sitting at its place on the dial.
        """
        self._unavailable.add(station.id)

    def hand_over_from(self, lost: Station) -> Station | None:
        """Tune whatever should replace a station that can no longer be heard.

        Used both when a signal fades out and when a stream refuses to play:
        from the driver's seat those are the same event, and both should land
        on the next thing worth listening to rather than on the satellite.
        """
        return self.tune(self._fallback_station(lost))

    def _fallback_station(self, lost: Station) -> Station | None:
        """Where a lost signal hands over.

        The next town first: if anything on the same band still reaches the
        truck, the nearest frequency to the one that just went is the closest
        thing to reaching over and nudging the dial. Only when the band is
        genuinely empty does the radio fall back to the satellite station, so
        driving across the country does not park the player on satellite the
        first time a local station runs out.
        """
        nearby = [s for s in self.stations_for(lost.band) if s.id != lost.id]
        if nearby:
            return min(nearby, key=lambda s: abs(s.frequency - lost.frequency))
        if self.catalog.satellite:
            return self.catalog.satellite[0]
        if self.catalog.web:
            return self.catalog.web[0]
        return None

    # -- tuning ---------------------------------------------------------------

    def set_band(self, band: str) -> Station | None:
        """Switch bands and land on that band's first station."""
        if band not in BANDS:
            return None
        self.band = band
        stations = self.stations_for(band)
        self.station = stations[0] if stations else None
        return self.station

    def next_band(self, step: int = 1) -> str:
        """Walk to the next band that has something on it, and tune it."""
        start = BANDS.index(self.band) if self.band in BANDS else 0
        for offset in range(1, len(BANDS) + 1):
            band = BANDS[(start + offset * (1 if step >= 0 else -1)) % len(BANDS)]
            if self.stations_for(band):
                self.set_band(band)
                return band
        return self.band

    def tune(self, station: Station | None) -> Station | None:
        """Tune a specific station, following it to its own band."""
        self.station = station
        if station is not None:
            self.band = station.band
        return station

    def seek(self, step: int = 1) -> Station | None:
        """Step along the current band, wrapping at the ends.

        With nothing tuned this lands on the first station of the band, so the
        seek keys work as a way in, not only as a way along.
        """
        stations = self.stations_for(self.band)
        if not stations:
            return None
        if self.station is None or self.station not in stations:
            self.station = stations[0]
            return self.station
        index = stations.index(self.station)
        self.station = stations[(index + (1 if step >= 0 else -1)) % len(stations)]
        return self.station

    # -- power ----------------------------------------------------------------

    def turn_on(self) -> Station | None:
        """Switch the radio on, tuning something if nothing is tuned yet."""
        self.on = True
        if self.station is None:
            for band in BANDS:
                if self.stations_for(band):
                    self.set_band(band)
                    break
        return self.station

    def turn_off(self) -> None:
        self.on = False

    def describe(self) -> str:
        """What the radio would say about itself right now."""
        if not self.on:
            return "Radio off."
        if self.station is None:
            return f"Radio on, nothing on {band_text(self.band)}."
        return station_text(self.station, self.signal)
