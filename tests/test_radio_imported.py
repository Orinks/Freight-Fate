"""The imported station tier: automated catalog under the curated one."""

import re

from freight_fate.radio import (
    DEFAULT_RADIO_CATALOG,
    RadioState,
    _call_sign_base,
    load_radio_catalog,
)

DALLAS = (32.7767, -96.797)

IMPORTED = tuple(s for s in DEFAULT_RADIO_CATALOG if s.source_type == "imported")
WEB = tuple(s for s in DEFAULT_RADIO_CATALOG if s.source_type == "web")


def test_imported_tier_loads_underneath_curated():
    assert len(IMPORTED) >= 800
    assert all(station.real_stream for station in IMPORTED)
    assert not any(station.safe_for_streaming for station in IMPORTED)
    assert all(station.stream_url.startswith(("http://", "https://")) for station in IMPORTED)
    assert all(station.lat is not None and station.lon is not None for station in IMPORTED)
    assert all(station.range_miles > 0 for station in IMPORTED)
    ids = [station.id for station in DEFAULT_RADIO_CATALOG]
    assert len(ids) == len(set(ids))


def test_web_tier_is_always_available_and_gated():
    assert len(WEB) >= 4500
    assert all(station.always_available for station in WEB)
    assert all(station.real_stream for station in WEB)
    assert not any(station.safe_for_streaming for station in WEB)
    assert all(station.name for station in WEB)
    assert not any(station.call_sign for station in WEB)
    # display_name copes with the missing call sign: no leading comma.
    assert not any(station.display_name.startswith(",") for station in WEB)


def test_imported_urls_never_duplicate_the_dial():
    # The curated catalog may reuse a network stream across its own entries;
    # the imported tier must not collide with curated URLs or itself.
    curated_urls = {s.stream_url for s in load_radio_catalog() if s.stream_url}
    imported_urls = [s.stream_url for s in IMPORTED + WEB]
    assert len(imported_urls) == len(set(imported_urls))
    assert not curated_urls.intersection(imported_urls)


def test_web_station_names_carry_no_stream_jargon():
    jargon = re.compile(r"\b(?:kbps|kbit|aac|mp3|\d{2,3}\s?kb?)\b", re.IGNORECASE)
    for station in WEB:
        assert not jargon.search(station.name), station.name


def test_web_band_sits_last_on_the_dial_and_jumpable():
    from freight_fate.radio import DIAL_CATEGORY_NAMES, _dial_group

    groups = {_dial_group(s) for s in WEB}
    assert groups == {8}
    assert DIAL_CATEGORY_NAMES[8] == "Web radio"
    # Everything with a place or a story sorts ahead of the web band.
    assert all(_dial_group(s) < 8 for s in DEFAULT_RADIO_CATALOG if s.source_type not in {"web"})
    radio = RadioState(streamer_safe=False, real_streams_enabled=True, position=DALLAS)
    stations = radio.available_stations()
    first_web = next(i for i, s in enumerate(stations) if s.source_type == "web")
    assert all(s.source_type == "web" for s in stations[first_web:])


def test_streamer_safe_mode_hides_the_web_tier_too():
    radio = RadioState(streamer_safe=True, real_streams_enabled=True, position=DALLAS)
    assert not any(s.source_type == "web" for s in radio.available_stations())


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
