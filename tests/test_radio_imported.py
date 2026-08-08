"""The imported station tier: automated catalog under the curated one."""

from freight_fate.radio import (
    DEFAULT_RADIO_CATALOG,
    RadioState,
    _call_sign_base,
    load_radio_catalog,
)

DALLAS = (32.7767, -96.797)

IMPORTED = tuple(s for s in DEFAULT_RADIO_CATALOG if s.source_type == "imported")


def test_imported_tier_loads_underneath_curated():
    assert len(IMPORTED) >= 800
    assert all(station.real_stream for station in IMPORTED)
    assert not any(station.safe_for_streaming for station in IMPORTED)
    assert all(station.stream_url.startswith(("http://", "https://")) for station in IMPORTED)
    assert all(station.lat is not None and station.lon is not None for station in IMPORTED)
    assert all(station.range_miles > 0 for station in IMPORTED)
    ids = [station.id for station in DEFAULT_RADIO_CATALOG]
    assert len(ids) == len(set(ids))


def test_curated_call_signs_always_win():
    curated_bases = {_call_sign_base(s.call_sign) for s in load_radio_catalog()}
    assert not any(_call_sign_base(s.call_sign) in curated_bases for s in IMPORTED)


def test_streamer_safe_mode_hides_every_imported_station():
    radio = RadioState(streamer_safe=True, real_streams_enabled=True, position=DALLAS)
    stations = radio.available_stations()
    assert not any(station.source_type == "imported" for station in stations)
    # The built-in stations still fill the dial for a streaming driver.
    assert any(not station.real_stream for station in stations)


def test_real_streams_switch_gates_the_imported_tier():
    radio = RadioState(streamer_safe=False, real_streams_enabled=False, position=DALLAS)
    assert not any(s.source_type == "imported" for s in radio.available_stations())


def test_imported_stations_come_in_near_their_transmitter():
    radio = RadioState(streamer_safe=False, real_streams_enabled=True, position=DALLAS)
    in_reach = [s for s in radio.available_stations() if s.source_type == "imported"]
    assert in_reach, "Dallas should receive imported broadcast stations"
    # And they stay local: none of them is receivable from the other coast.
    radio.update_position((47.6062, -122.3321))  # Seattle
    seattle_ids = {s.id for s in radio.available_stations()}
    assert not all(station.id in seattle_ids for station in in_reach)


def test_imported_station_spoken_text_is_clean():
    # Curated stations may speak their website as a source note; the imported
    # tier's spoken lines carry no URLs or stream jargon at all.
    radio = RadioState(
        catalog=IMPORTED, streamer_safe=False, real_streams_enabled=True, position=DALLAS
    )
    for line in radio.station_list_lines(limit=30):
        assert "http" not in line.lower()
        assert "\n" not in line and "\t" not in line
    for station in IMPORTED:
        assert "-" not in station.call_sign
        assert station.format
        assert station.source
