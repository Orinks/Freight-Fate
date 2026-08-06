"""The radio catalog: how it is built, and what the shipped one has to hold."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from freight_fate.data.radio_catalog import (
    BAND_AM,
    BAND_FM,
    BAND_SATELLITE,
    BAND_WEB,
    CATALOG_PATH,
    RadioCatalog,
    load_catalog,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_builder():
    """Import tools/build_radio_catalog.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "build_radio_catalog", ROOT / "tools" / "build_radio_catalog.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


builder = _load_builder()


# -- the build tool ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw, band, frequency",
    [
        ("98.5", BAND_FM, 98.5),
        ("107.9", BAND_FM, 107.9),
        ("1230", BAND_AM, 1230),
        ("540", BAND_AM, 540),
        # A handful of Wikidata rows quote the frequency in hertz.
        ("98700000", BAND_FM, 98.7),
        ("1430000", BAND_AM, 1430),
        ("", None, None),
        (None, None, None),
        ("42", None, None),  # neither band
    ],
)
def test_frequencies_are_classified_across_the_units_the_sources_use(raw, band, frequency):
    """AM is quoted in kilohertz and FM in megahertz, mixed in one column."""
    assert builder._band_and_frequency(raw) == (band, frequency)


def test_names_are_stripped_of_what_a_screen_reader_should_not_read():
    assert builder._clean_name("\tHard Rock Radio FM") == "Hard Rock Radio FM"
    assert builder._clean_name("Mega St☆r New York") == "Mega Str New York"
    assert builder._clean_name("A​B") == "AB"
    assert builder._clean_name("  spaced   out  ") == "spaced out"


def test_a_station_name_does_not_repeat_the_call_sign_and_dial():
    # The readout already says "WGAO, 88.3 F M" before the name.
    assert builder._short_name('WGAO 88.1 "Power 88" (AAC)', "WGAO") == "Power 88"
    # The catalog can hold the suffixed form while the name uses the bare one.
    assert builder._short_name("KNCT - Simply Beautiful", "KNCT-FM") == "Simply Beautiful"
    # Nothing left means the name said nothing new.
    assert builder._short_name("WTSC-FM 91.1", "WTSC-FM") == ""


def test_a_name_that_is_a_paragraph_gets_cut_to_its_identity():
    long_name = "NOTICIAS Y DEPORTES - - - Lotus Communications - Los Angeles, California, EUA"
    short = builder._short_name(long_name, "KWKW")
    assert short == "NOTICIAS Y DEPORTES"
    assert len(short) <= builder._MAX_NAME_CHARS


def test_tags_are_trimmed_to_something_speakable():
    assert builder._format_tags("rock,classic rock,80s,90s,1970,1980") == (
        "rock, classic rock, 80s"
    )
    assert builder._format_tags("1930,1940,1950") is None  # decades only
    assert builder._format_tags("") is None


def test_the_catalog_renders_deterministically(tmp_path):
    catalog = {"version": 1, "local": [], "web": [], "satellite": []}
    assert builder.render(catalog) == builder.render(dict(catalog))


def test_an_overlay_wins_over_the_automatic_join(tmp_path):
    overlay = tmp_path / "overlay.json"
    overlay.write_text(
        json.dumps(
            [
                {"call_sign": "WAAA", "url": "https://curated.invalid/waaa", "radius_mi": 55.0},
                {"name": "Hand Picked", "url": "https://curated.invalid/web"},
            ]
        ),
        encoding="utf-8",
    )
    local = {"WAAA": {"votes": 3, "call_sign": "WAAA", "url": "https://auto.invalid/waaa"}}
    web: dict = {}

    applied = builder._apply_overlay(overlay, local, web)

    assert applied == 2
    assert local["WAAA"]["url"] == "https://curated.invalid/waaa"
    assert local["WAAA"]["radius_mi"] == 55.0
    assert web["https://curated.invalid/web"]["name"] == "Hand Picked"


# -- the loader --------------------------------------------------------------


def test_a_missing_catalog_yields_an_empty_one_rather_than_failing(tmp_path):
    assert load_catalog(tmp_path / "nope.json") == RadioCatalog()


def test_a_corrupt_catalog_yields_an_empty_one(tmp_path):
    path = tmp_path / "stations.json"
    path.write_text("{ not json", encoding="utf-8")
    assert load_catalog(path) == RadioCatalog()
    path.write_text('["a list, not an object"]', encoding="utf-8")
    assert load_catalog(path) == RadioCatalog()


def test_a_malformed_station_costs_that_station_and_nothing_else(tmp_path):
    path = tmp_path / "stations.json"
    path.write_text(
        json.dumps(
            {
                "local": [
                    {"id": "ok", "name": "Fine", "url": "https://x.invalid", "band": "FM"},
                    {"id": "", "name": "No id", "url": "https://x.invalid", "band": "FM"},
                    {"name": "No id key at all", "url": "https://x.invalid", "band": "FM"},
                    "not even an object",
                ]
            }
        ),
        encoding="utf-8",
    )
    catalog = load_catalog(path)
    assert [s.id for s in catalog.local] == ["ok"]


# -- the shipped catalog -----------------------------------------------------


def test_the_shipped_catalog_is_present_and_complete():
    catalog = load_catalog(CATALOG_PATH)
    assert len(catalog.local) > 500, "local stations are the whole point of the feature"
    assert catalog.web, "web stations are the fallback where nothing local reaches"
    assert catalog.satellite, "the satellite station is what a lost signal hands over to"


def test_every_shipped_station_carries_what_playing_it_needs():
    catalog = load_catalog(CATALOG_PATH)
    for station in catalog.all_stations:
        assert station.id and station.name and station.url
        assert station.url.startswith(("http://", "https://"))
        assert station.band in (BAND_FM, BAND_AM, BAND_WEB, BAND_SATELLITE)
        if station.is_broadcast:
            assert station.call_sign, f"{station.id} is on the dial with no call sign"
            assert station.frequency > 0.0
            assert station.radius_mi > 0.0
            assert station.radius_source in ("default", "fcc")
            assert -180.0 <= station.lon <= 180.0
            assert -90.0 <= station.lat <= 90.0


def test_no_shipped_stream_is_hls():
    """BASS cannot open an .m3u8 playlist, so those are dropped at build time."""
    catalog = load_catalog(CATALOG_PATH)
    assert not [s for s in catalog.all_stations if s.url.endswith(".m3u8")]


def test_shipped_station_ids_are_unique():
    catalog = load_catalog(CATALOG_PATH)
    ids = [s.id for s in catalog.all_stations]
    assert len(ids) == len(set(ids))


def test_one_call_sign_is_one_place_on_the_dial():
    catalog = load_catalog(CATALOG_PATH)
    call_signs = [s.call_sign for s in catalog.local]
    assert len(call_signs) == len(set(call_signs))
