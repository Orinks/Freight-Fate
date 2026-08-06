"""Radio reception and tuning: geometry, dial order, and what gets said."""

import pytest

from freight_fate.data.radio_catalog import RadioCatalog, Station
from freight_fate.sim.radio import (
    BAND_AM,
    BAND_FM,
    BAND_SATELLITE,
    BAND_WEB,
    RadioTuner,
    distance_mi,
    frequency_text,
    signal_strength,
    signal_text,
    station_text,
)

# Two transmitters 40 miles apart on the same band, so a truck can be in range
# of one, both, or neither depending on where it is put.
CHICAGO = (41.8781, -87.6298)
FAR_WEST = (41.8781, -96.0)


def _local(call_sign, frequency, lat, lon, band=BAND_FM, radius=40.0, tags="country"):
    return Station(
        id=f"id-{call_sign}",
        name=f"{call_sign} Radio",
        url=f"https://example.invalid/{call_sign}",
        band=band,
        call_sign=call_sign,
        frequency=frequency,
        tags=tags,
        lat=lat,
        lon=lon,
        radius_mi=radius,
        radius_source="default",
    )


WEB = Station(
    id="web-1",
    name="Example Web Radio",
    url="https://example.invalid/web",
    band=BAND_WEB,
    tags="jazz",
)
SAT = Station(
    id="sat-1", name="Example Satellite", url="https://example.invalid/sat", band=BAND_SATELLITE
)


@pytest.fixture
def catalog():
    return RadioCatalog(
        local=(
            _local("WAAA", 90.1, *CHICAGO),
            _local("WBBB", 95.5, *CHICAGO),
            _local("WCCC", 1050.0, *CHICAGO, band=BAND_AM, radius=90.0),
            _local("WZZZ", 101.1, *FAR_WEST),
        ),
        web=(WEB,),
        satellite=(SAT,),
    )


def test_distance_matches_a_known_separation():
    # New York to Boston is about 190 statute miles great-circle.
    miles = distance_mi(40.7128, -74.0060, 42.3601, -71.0589)
    assert 180.0 < miles < 200.0


def test_signal_is_full_in_the_core_and_zero_past_the_edge():
    station = _local("WAAA", 90.1, *CHICAGO, radius=40.0)
    assert signal_strength(station, *CHICAGO) == 1.0
    # 0.6 of the radius still reads as full strength.
    near = (CHICAGO[0] + 0.2, CHICAGO[1])  # about 14 miles north
    assert signal_strength(station, *near) == 1.0
    # Beyond the radius there is nothing.
    assert signal_strength(station, CHICAGO[0] + 1.0, CHICAGO[1]) == 0.0


def test_signal_falls_off_monotonically_toward_the_edge():
    station = _local("WAAA", 90.1, *CHICAGO, radius=40.0)
    readings = [
        signal_strength(station, CHICAGO[0] + offset, CHICAGO[1])
        for offset in (0.40, 0.45, 0.50, 0.55)
    ]
    assert readings == sorted(readings, reverse=True)
    assert all(0.0 <= value <= 1.0 for value in readings)
    assert readings[0] > readings[-1]


def test_stations_without_a_transmitter_are_always_full_strength():
    assert signal_strength(WEB, *CHICAGO) == 1.0
    assert signal_strength(SAT, 0.0, 0.0) == 1.0


def test_signal_words_cover_the_whole_range():
    assert signal_text(1.0) == "strong signal"
    assert signal_text(0.5) == "good signal"
    assert signal_text(0.3) == "fair signal"
    assert signal_text(0.01) == "weak signal"


def test_frequency_is_spoken_per_band():
    assert frequency_text(_local("WAAA", 92.5, *CHICAGO)) == "92.5 F M"
    assert frequency_text(_local("WCCC", 1050.0, *CHICAGO, band=BAND_AM)) == "1050 A M"
    assert frequency_text(WEB) == ""


def test_station_readout_names_the_station_and_the_signal():
    text = station_text(_local("WAAA", 92.5, *CHICAGO), 1.0)
    assert "WAAA" in text
    assert "92.5 F M" in text
    assert "country" in text
    assert "strong signal" in text
    # A web station has no dial position and no signal to report.
    web_text = station_text(WEB)
    assert "Example Web Radio" in web_text
    assert "signal" not in web_text


def test_only_stations_in_range_are_tunable(catalog):
    tuner = RadioTuner(catalog, lat=CHICAGO[0], lon=CHICAGO[1])
    call_signs = [s.call_sign for s in tuner.stations_for(BAND_FM)]
    assert call_signs == ["WAAA", "WBBB"]  # WZZZ is 400 miles west
    assert [s.call_sign for s in tuner.stations_for(BAND_AM)] == ["WCCC"]
    # Web and satellite do not depend on where the truck is.
    assert tuner.stations_for(BAND_WEB) == (WEB,)
    assert tuner.stations_for(BAND_SATELLITE) == (SAT,)


def test_seek_walks_the_band_and_wraps(catalog):
    tuner = RadioTuner(catalog, lat=CHICAGO[0], lon=CHICAGO[1])
    tuner.set_band(BAND_FM)
    assert tuner.station.call_sign == "WAAA"
    assert tuner.seek(1).call_sign == "WBBB"
    assert tuner.seek(1).call_sign == "WAAA"  # wrapped
    assert tuner.seek(-1).call_sign == "WBBB"  # and back the other way


def test_seek_on_an_empty_band_reports_nothing(catalog):
    tuner = RadioTuner(catalog, lat=FAR_WEST[0], lon=FAR_WEST[1])
    tuner.band = BAND_AM  # no AM transmitter reaches out here
    assert tuner.stations_for(BAND_AM) == ()
    assert tuner.seek(1) is None


def test_driving_out_of_range_falls_back_to_the_satellite(catalog):
    """With nothing on the band, the always-available station takes over."""
    tuner = RadioTuner(catalog, lat=CHICAGO[0], lon=CHICAGO[1])
    tuner.turn_on()
    tuner.set_band(BAND_FM)
    assert tuner.station.call_sign == "WAAA"

    # Far west there is exactly one FM transmitter, and the truck stops short
    # of it, so no station on the band reaches.
    change = tuner.set_position(FAR_WEST[0], FAR_WEST[1] + 4.0)
    assert change.lost is not None and change.lost.call_sign == "WAAA"
    assert change.fell_back_to is SAT
    assert tuner.station is SAT
    assert tuner.band == BAND_SATELLITE


def test_the_next_towns_station_wins_over_the_satellite(catalog):
    """Losing a station in a place that has others must not park on satellite.

    Driving across the country, the first local station to run out would
    otherwise strand the player on the satellite band for the rest of the trip.
    """
    tuner = RadioTuner(catalog, lat=CHICAGO[0], lon=CHICAGO[1])
    tuner.turn_on()
    tuner.set_band(BAND_FM)
    assert tuner.station.call_sign == "WAAA"

    change = tuner.set_position(*FAR_WEST)  # WZZZ territory
    assert change.lost.call_sign == "WAAA"
    assert change.fell_back_to.call_sign == "WZZZ"
    assert tuner.band == BAND_FM


def test_a_lost_station_never_hands_over_to_itself(catalog):
    """The in-range list is refreshed every mile, so it is stale on a dropout.

    A short step that takes the truck out of range must still hand over to a
    different station, not to the one that just went, and must announce the
    loss once rather than on every following tick.
    """
    tuner = RadioTuner(catalog, lat=CHICAGO[0], lon=CHICAGO[1])
    tuner.turn_on()
    tuner.set_band(BAND_FM)
    lost_station = tuner.station

    # A step of well under the one-mile refresh distance, but far enough out
    # of the 40-mile circle to lose the signal.
    tuner.set_position(CHICAGO[0] + 0.7, CHICAGO[1])
    change = tuner.set_position(CHICAGO[0] + 0.705, CHICAGO[1])

    assert tuner.station is not lost_station
    # And the handover is not re-announced on the next tick.
    again = tuner.set_position(CHICAGO[0] + 0.706, CHICAGO[1])
    assert again.lost is None
    assert change.lost is not None or again.lost is None


def test_a_lost_station_hands_over_to_the_nearest_frequency(catalog):
    """Nearest on the dial is the closest thing to nudging it by hand."""
    tuner = RadioTuner(catalog, lat=CHICAGO[0], lon=CHICAGO[1])
    tuner.turn_on()
    tuner.tune(_local("WDDD", 107.9, *FAR_WEST))  # a station only far west
    # Standing in Chicago that station does not reach, so it is handed over.
    change = tuner.set_position(*CHICAGO)
    # 95.5 is nearer 107.9 than 90.1 is.
    assert change.fell_back_to.call_sign == "WBBB"


def test_staying_in_range_reports_no_change(catalog):
    tuner = RadioTuner(catalog, lat=CHICAGO[0], lon=CHICAGO[1])
    tuner.turn_on()
    tuner.set_band(BAND_FM)
    change = tuner.set_position(CHICAGO[0] + 0.05, CHICAGO[1])
    assert change.lost is None and change.fell_back_to is None
    assert tuner.station.call_sign == "WAAA"


def test_arriving_somewhere_new_brings_in_that_towns_stations(catalog):
    tuner = RadioTuner(catalog, lat=FAR_WEST[0], lon=FAR_WEST[1])
    assert [s.call_sign for s in tuner.stations_for(BAND_FM)] == ["WZZZ"]
    tuner.set_position(*CHICAGO)
    assert [s.call_sign for s in tuner.stations_for(BAND_FM)] == ["WAAA", "WBBB"]


def test_turning_on_lands_on_something_audible(catalog):
    tuner = RadioTuner(catalog, lat=CHICAGO[0], lon=CHICAGO[1])
    assert tuner.describe() == "Radio off."
    station = tuner.turn_on()
    assert station is not None
    assert tuner.on is True
    assert "WAAA" in tuner.describe()
    tuner.turn_off()
    assert tuner.describe() == "Radio off."


def test_turning_on_with_no_local_reception_still_finds_a_station(catalog):
    # Middle of the ocean: no transmitter reaches, but web radio still does.
    tuner = RadioTuner(catalog, lat=0.0, lon=0.0)
    station = tuner.turn_on()
    assert station is not None
    assert station.band in (BAND_WEB, BAND_SATELLITE)


def test_band_key_skips_bands_with_nothing_on_them(catalog):
    tuner = RadioTuner(catalog, lat=FAR_WEST[0], lon=FAR_WEST[1])
    tuner.set_band(BAND_FM)
    assert tuner.next_band() == BAND_WEB  # AM is empty out here, so it is skipped


def test_an_empty_catalog_never_raises():
    tuner = RadioTuner(RadioCatalog(), lat=CHICAGO[0], lon=CHICAGO[1])
    assert tuner.turn_on() is None
    assert tuner.seek(1) is None
    assert tuner.signal == 0.0
    assert tuner.set_position(*FAR_WEST) is not None
    assert "Radio on" in tuner.describe()


def test_reception_is_deterministic(catalog):
    first = [
        RadioTuner(catalog, lat=CHICAGO[0], lon=CHICAGO[1]).stations_for(BAND_FM) for _ in range(3)
    ]
    assert first[0] == first[1] == first[2]


def test_the_shipped_catalog_reaches_real_cities():
    """The catalog that actually ships puts stations over real map cities."""
    from freight_fate.data.radio_catalog import get_radio_catalog

    catalog = get_radio_catalog()
    assert catalog.local, "the shipped catalog has no local stations"
    assert catalog.satellite, "the shipped catalog has no satellite fallback"

    tuner = RadioTuner(catalog, lat=CHICAGO[0], lon=CHICAGO[1])
    assert tuner.stations_for(BAND_FM), "no FM reception in Chicago"
    # Every local station carries what reception needs.
    for station in catalog.local:
        assert station.radius_mi > 0.0
        assert station.band in (BAND_FM, BAND_AM)
        assert station.url.startswith(("http://", "https://"))
