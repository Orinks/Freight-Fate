"""The imported station tier: automated catalog under the curated one."""

import re

from freight_fate.radio import (
    DEFAULT_RADIO_CATALOG,
    RadioState,
    _call_sign_base,
    canonical_stream_url,
    load_radio_catalog,
    normalize_stream_url,
)

DALLAS = (32.7767, -96.797)

CURATED_IDS = frozenset(s.id for s in load_radio_catalog())
IMPORTED = tuple(s for s in DEFAULT_RADIO_CATALOG if s.source_type == "imported")
# The automated web tier only: the curated catalog carries a handful of web
# stations of its own now (Radiostorm's four channels), and those are held
# to the curated catalog's standards, not the directory's.
WEB = tuple(s for s in DEFAULT_RADIO_CATALOG if s.source_type == "web" and s.id not in CURATED_IDS)


def test_imported_tier_loads_underneath_curated():
    # Floors, not exact counts. The tier shrinks when a reachability sweep
    # drops streams that have gone off the air (634 of them on 2026-08-18)
    # and grows when directory stations are placed at their FCC transmitter
    # (828 the same day). It should stay a tier, not dwindle to a handful.
    assert len(IMPORTED) >= 1200
    assert all(station.real_stream for station in IMPORTED)
    assert not any(station.safe_for_streaming for station in IMPORTED)
    assert all(station.stream_url.startswith(("http://", "https://")) for station in IMPORTED)
    assert all(station.lat is not None and station.lon is not None for station in IMPORTED)
    assert all(station.range_miles > 0 for station in IMPORTED)
    ids = [station.id for station in DEFAULT_RADIO_CATALOG]
    assert len(ids) == len(set(ids))


def test_web_tier_is_always_available_and_gated():
    # Lower than it once was on purpose: a commercial FM whose stream the
    # directory listed as web radio belongs near its transmitter, not
    # everywhere at once, so ~500 moved to the terrestrial tier.
    assert len(WEB) >= 3500
    assert all(station.always_available for station in WEB)
    assert all(station.real_stream for station in WEB)
    assert not any(station.safe_for_streaming for station in WEB)
    assert all(station.name for station in WEB)
    assert not any(station.call_sign for station in WEB)
    # display_name copes with the missing call sign: no leading comma.
    assert not any(station.display_name.startswith(",") for station in WEB)


def test_imported_urls_never_duplicate_the_dial():
    # The curated catalog may reuse a network stream across its own entries;
    # the imported tier must not collide with curated URLs or itself, even
    # when the only difference is scheme, a trailing slash, or which CDN
    # edge the directory happened to record. The dial's own rule is the one
    # under test here -- an independent copy of it in this file would let
    # the two drift apart and pass while the dial still doubled a station.
    curated_urls = {
        normalize_stream_url(s.stream_url) for s in load_radio_catalog() if s.stream_url
    }
    imported_urls = [normalize_stream_url(s.stream_url) for s in IMPORTED + WEB]
    assert len(imported_urls) == len(set(imported_urls))
    assert not curated_urls.intersection(imported_urls)


def test_one_live365_station_is_one_stream_whatever_url_it_arrived_as():
    # Radio Browser records a Live365 station under whichever edge answered
    # that day, and at whichever bitrate mount, so Radiostorm's At Work,
    # Oldies and Comedy channels each reached the web band twice. The mount
    # name carries the station id; that id is the station.
    canonical = normalize_stream_url("https://streaming.live365.com/b09584_128mp3")
    assert canonical == "streaming.live365.com/b09584"
    for alias in (
        "http://streaming.live365.com/b09584_128mp3",
        "http://streaming.live365.com/b09584_64aac",
        "https://ais-sa5.cdnstream1.com/b09584_128mp3",
        "https://das-edge14-live365-dal02.cdnstream.com/b09584",
        "https://streaming.live365.com/b09584?listenerId=Live365-AdBlock",
    ):
        assert normalize_stream_url(alias) == canonical, alias
    # A different station id stays a different station, and the fold never
    # reaches past Live365: two unrelated hosts sharing a path stay apart.
    assert normalize_stream_url("https://streaming.live365.com/b09585_128mp3") != canonical
    assert normalize_stream_url(
        "https://ice41.securenetsystems.net/1069_128"
    ) != normalize_stream_url("https://das-edge27-sa23-lax02.cdnstream.com/1069_128")


FCC_PLACED = tuple(s for s in IMPORTED if s.id.startswith("rb-fcc-"))


def test_directory_stations_sit_at_their_licensed_transmitter():
    # The old local tier came from a Wikidata join and skewed hard to public
    # radio; this is the commercial music half of the dial, placed where the
    # FCC says the transmitter actually stands.
    assert len(FCC_PLACED) >= 500
    assert all(s.lat is not None and s.lon is not None for s in FCC_PLACED)
    assert all(s.call_sign for s in FCC_PLACED)
    assert all(s.range_miles > 0 for s in FCC_PLACED)
    # Continental US plus Alaska and Hawaii, and nothing in the ocean off
    # the coast of Africa: a transposed sign puts a station at (0, 0).
    assert all(17.0 < s.lat < 72.0 for s in FCC_PLACED)
    assert all(-180.0 < s.lon < -64.0 for s in FCC_PLACED)


def test_a_translator_does_not_reach_as_far_as_a_full_power_station():
    # Every imported station used to get a flat 40 miles, which put a
    # 250-watt translator on the dial three counties from its tower.
    from import_radio_catalog import range_for

    assert range_for(0.05, "FX") < range_for(6.0, "FM") < range_for(100.0, "FM")
    assert range_for(None, "FX") < range_for(None, "FM")
    assert range_for(1.0, "AM") == range_for(50.0, "AM")
    # And the real data spreads across the bands rather than piling on one.
    assert len({s.range_miles for s in FCC_PLACED}) >= 4


def test_live365_stations_are_stored_at_live365s_own_address():
    # The directory recorded whichever CDN edge answered on the day it
    # checked, tokens and all. Those hostnames come and go, and folding the
    # duplicates took away the twin that used to carry the stable address.
    assert (
        canonical_stream_url("http://ais-edge104-live365-dal02.cdnstream.com/a89824")
        == "https://streaming.live365.com/a89824"
    )
    assert (
        canonical_stream_url(
            "https://ais-edge105-live365-dal02.cdnstream.com/a02627?filetype=.mp3&_=1"
        )
        == "https://streaming.live365.com/a02627"
    )
    # The mount is kept exactly: a bitrate variant is still its own mount.
    assert (
        canonical_stream_url("http://streaming.live365.com/a86427_2")
        == "https://streaming.live365.com/a86427_2"
    )
    # Everything that is not a Live365 mount comes back untouched, including
    # the numeric mounts other broadcasters run on the same CDN.
    for other in (
        "https://ice41.securenetsystems.net/KAJN",
        "http://das-edge27-sa23-lax02.cdnstream.com/1069_128",
        "http://crystalout.surfernetwork.com:8001/KADA_MP3",
    ):
        assert canonical_stream_url(other) == other
    for station in IMPORTED + WEB:
        host = station.stream_url.split("//", 1)[-1].split("/", 1)[0].lower()
        assert "live365" not in host or host == "streaming.live365.com", station.stream_url


def test_radiostorm_channels_are_curated_and_listed_once():
    # radiostorm.com publishes four channels; the directory carried them
    # under six rows with contributor-typed names and genres ("Comedy 104"
    # tagged as Canadian talk). Curated rows win, one per channel.
    curated = [s for s in load_radio_catalog() if s.id.startswith("radiostorm-")]
    assert {s.name for s in curated} == {
        "Radiostorm At Work 104",
        "Radiostorm Rock 104",
        "Radiostorm Oldies 104",
        "Radiostorm Comedy 104",
    }
    assert all(s.source_type == "web" for s in curated)
    assert all(s.always_available and s.real_stream and s.supported for s in curated)
    assert not any(s.safe_for_streaming for s in curated)
    identities = [normalize_stream_url(s.stream_url) for s in curated]
    assert len(identities) == len(set(identities))
    # One dial listing each, and the directory's own rows for those four
    # channels are gone. The Star 104 sister channels the directory carries
    # (80s, Classic Country, Classic R&B, Christmas Hits) are different
    # channels, not duplicates, and stay where they are.
    radio = RadioState(streamer_safe=False, position=DALLAS)
    listed = [
        s
        for s in radio.available_stations()
        if normalize_stream_url(s.stream_url) in set(identities)
    ]
    assert len(listed) == 4, [s.name for s in listed]
    assert {s.id for s in listed} == {s.id for s in curated}


def test_terrestrial_names_never_lead_with_dial_junk():
    # "& FM 95.7 & FM 93.1" reached a real drive's readout (2026-08-07):
    # the source cleaner strands conjunctions and band-first frequencies.
    for station in IMPORTED:
        assert not station.name.startswith(("&", ",", "-", "/", "and ", "And ")), station.name
        assert not re.fullmatch(
            r"(?:(?:FM|AM)\s*)?\d{2,4}(?:\.\d)?\s*(?:FM|AM)?", station.name, re.IGNORECASE
        ), station.name


def test_a_name_that_repeats_the_call_sign_speaks_once():
    doubled = [s for s in IMPORTED if s.name.upper() == s.call_sign.upper()]
    assert doubled, "the catalog carries call-sign-only stations"
    for station in doubled[:20]:
        assert station.display_name == station.call_sign


def test_web_station_names_carry_no_stream_jargon():
    jargon = re.compile(r"\b(?:kbps|kbit|aac|mp3|\d{2,3}\s?kb?)\b", re.IGNORECASE)
    for station in WEB:
        assert not jargon.search(station.name), station.name


def test_web_band_sits_last_on_the_dial_and_jumpable():
    from freight_fate.radio import DIAL_CATEGORY_NAMES, _dial_group

    groups = {_dial_group(s) for s in WEB}
    assert groups == {9}
    assert DIAL_CATEGORY_NAMES[9] == "Web radio"
    # Everything with a place or a story sorts ahead of the web band.
    assert all(_dial_group(s) < 9 for s in DEFAULT_RADIO_CATALOG if s.source_type not in {"web"})
    radio = RadioState(streamer_safe=False, position=DALLAS)
    stations = radio.available_stations()
    first_web = next(i for i, s in enumerate(stations) if s.source_type == "web")
    assert all(s.source_type == "web" for s in stations[first_web:])


def test_streamer_safe_mode_hides_the_web_tier_too():
    radio = RadioState(streamer_safe=True, position=DALLAS)
    assert not any(s.source_type == "web" for s in radio.available_stations())


def test_unreachable_streams_are_off_the_dial():
    # A dead stream is worse than a missing one: tuning to it costs a tune,
    # a wait, and a fallback hand-off. The sweep's casualties are dropped
    # from the imported build and flagged unsupported when curated.
    import json
    from pathlib import Path

    health_path = Path("data/radio_stream_health.json")
    if not health_path.exists():  # a build without a sweep is still valid
        return
    health = json.loads(health_path.read_text(encoding="utf-8"))
    dead_imported = {r["id"] for r in health["dead"] if r["tier"] == "imported"}
    assert dead_imported, "the sweep found casualties to pin"
    assert not {s.id for s in IMPORTED + WEB} & dead_imported

    dead_curated = {r["id"] for r in health["dead"] if r["tier"] == "curated"}
    by_id = {s.id: s for s in load_radio_catalog()}
    for station_id in dead_curated:
        assert not by_id[station_id].supported, station_id

    # Shoutcast survivors kept their row and took the mount URL instead.
    for row in health["repaired"]:
        station = by_id.get(row["id"]) or next(
            (s for s in IMPORTED + WEB if s.id == row["id"]), None
        )
        if station is not None:
            assert station.stream_url == row["repaired_url"], station.id


def test_a_curated_web_station_does_not_reserve_every_call_sign_less_import():
    # Web stations are named, not lettered. Curating four of them put an
    # empty string in the reserved call-sign set, which matched every
    # imported web station and silently emptied the whole band.
    from freight_fate.radio import load_imported_stations

    curated = load_radio_catalog()
    assert any(not s.call_sign for s in curated), "the curated catalog carries web stations"
    imported = load_imported_stations(curated)
    assert len([s for s in imported if s.source_type == "web"]) >= 3500


def test_curated_call_signs_always_win():
    curated_bases = {_call_sign_base(s.call_sign) for s in load_radio_catalog()}
    assert not any(_call_sign_base(s.call_sign) in curated_bases for s in IMPORTED)


def test_streamer_safe_mode_hides_every_imported_station():
    radio = RadioState(streamer_safe=True, position=DALLAS)
    stations = radio.available_stations()
    assert not any(station.source_type == "imported" for station in stations)
    # The built-in stations still fill the dial for a streaming driver.
    assert any(not station.real_stream for station in stations)


def test_imported_tier_plays_out_of_the_box():
    radio = RadioState(position=DALLAS)
    assert any(s.source_type == "imported" for s in radio.available_stations())


def test_imported_stations_come_in_near_their_transmitter():
    radio = RadioState(streamer_safe=False, position=DALLAS)
    in_reach = [s for s in radio.available_stations() if s.source_type == "imported"]
    assert in_reach, "Dallas should receive imported broadcast stations"
    # And they stay local: none of them is receivable from the other coast.
    radio.update_position((47.6062, -122.3321))  # Seattle
    seattle_ids = {s.id for s in radio.available_stations()}
    assert not all(station.id in seattle_ids for station in in_reach)


def test_imported_station_spoken_text_is_clean():
    # Curated stations may speak their website as a source note; the imported
    # tier's spoken lines carry no URLs or stream jargon at all.
    radio = RadioState(catalog=IMPORTED, streamer_safe=False, position=DALLAS)
    for line in radio.station_list_lines(limit=30):
        assert "http" not in line.lower()
        assert "\n" not in line and "\t" not in line
    for station in IMPORTED:
        assert "-" not in station.call_sign
        assert station.format
        assert station.source
