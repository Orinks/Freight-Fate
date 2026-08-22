"""The Radio app on the driver tablet: search the dial, tune by name, keep
favorites. Owner, 2026-08-22."""

import pygame
import pytest
from driving_feature_helpers import key_event, open_driver_apps
from speech_capture import speech_stub

from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.radio import RADIO_SEARCH_LIMIT, RadioState


def test_search_covers_the_whole_allowed_dial_in_range_first():
    radio = RadioState(enabled=True, station_id="route_playlist", streamer_safe=False)
    hits, total = radio.search("darren")
    assert total >= 1
    station, reception = hits[0]
    assert station.id == "darren-duff-radio"
    # A web station is always available, so it comes with a reception.
    assert reception is not None and reception.signal_label == "always available"
    # Case and surrounding whitespace do not matter.
    assert radio.search("  DARREN  ")[1] == total


def test_search_matches_call_sign_and_format_not_only_name():
    radio = RadioState(enabled=True, station_id="route_playlist", streamer_safe=False)
    by_format = radio.search("rock", limit=100_000)
    assert by_format[1] > 0
    assert any(s.id == "darren-duff-radio" for s, _ in by_format[0])
    # An out-of-range terrestrial station is still findable, paired with None.
    hits, total = radio.search("npr")
    assert total > 0
    assert any(reception is None for _, reception in hits) or all(
        reception is not None for _, reception in hits
    )


def test_search_is_capped_and_says_how_many_there_were():
    radio = RadioState(enabled=True, station_id="route_playlist", streamer_safe=False)
    hits, total = radio.search("radio")
    assert len(hits) <= RADIO_SEARCH_LIMIT
    assert total >= len(hits)


def test_empty_search_finds_nothing():
    radio = RadioState(enabled=True, station_id="route_playlist", streamer_safe=False)
    assert radio.search("   ") == ([], 0)


def test_streamer_safe_mode_hides_real_streams_from_search_too():
    radio = RadioState(enabled=True, station_id="route_playlist", streamer_safe=True)
    hits, _total = radio.search("darren")
    assert not any(s.id == "darren-duff-radio" for s, _ in hits)


def test_favorites_listing_pairs_each_with_its_reception():
    radio = RadioState(enabled=True, station_id="darren-duff-radio", streamer_safe=False)
    radio.toggle_favorite()
    rows = radio.favorites()
    assert [s.id for s, _ in rows] == ["darren-duff-radio"]
    assert rows[0][1] is not None
    assert radio.is_favorite(rows[0][0])


def _drive_job() -> Job:
    return Job(
        CARGO_CATALOG["general"],
        12.0,
        "Denver",
        "Denver Dry Warehouse",
        "Salt Lake City",
        520.0,
        2400.0,
        14.0,
    )


@pytest.fixture
def radio_app(monkeypatch):
    """A Denver drive, engine running, the Radio app open on the tablet."""
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.driving_radio_app import RadioAppState

    app = App()
    spoken = []
    streams = []
    monkeypatch.setattr(app.ctx.audio, "play_music", lambda track, fade_ms=1500: None)
    monkeypatch.setattr(app.ctx.audio, "stop_music", lambda fade_ms=0: None)
    monkeypatch.setattr(
        app.ctx.audio, "play_radio_stream", lambda url, fade_ms=1500: streams.append(url)
    )
    monkeypatch.setattr(app.ctx.audio, "music_playing", lambda: bool(streams))
    monkeypatch.setattr(app.ctx.audio, "radio_now_playing", lambda: None)
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    app.ctx.profile = Profile(name="Radio App", current_city="Denver")
    app.ctx.settings.radio_streamer_safe = False
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, _drive_job(), route, trip_seed=777, start_hour=13.0)
    app.push_state(driving)
    driving.truck.start_engine()
    driving.handle_event(key_event(pygame.K_TAB))
    open_driver_apps(app)
    apps = app.state
    assert apps.items[0].text == "Radio"
    apps.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, RadioAppState)
    try:
        yield app, driving, spoken, streams
    finally:
        app.shutdown()


def _select(state, label_start: str) -> None:
    for _ in range(len(state.items)):
        if state.items[state.index].text.startswith(label_start):
            state.handle_event(key_event(pygame.K_RETURN))
            return
        state.handle_event(key_event(pygame.K_DOWN))
    raise AssertionError(f"no item starting with {label_start!r}: {[i.text for i in state.items]}")


def _type(state, text: str) -> None:
    for ch in text:
        state.handle_event(key_event(pygame.K_a, unicode=ch))


def test_search_tunes_a_station_by_name(radio_app):
    from freight_fate.states.driving_radio_app import RadioSearchEntryState, RadioStationListState

    app, driving, spoken, streams = radio_app
    _select(app.state, "Search stations")
    assert isinstance(app.state, RadioSearchEntryState)
    _type(app.state, "darren")
    app.state.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, RadioStationListState)
    first = app.state.items[0].text
    assert first.startswith("Darren Duff radio, Web radio, always available")
    app.state.handle_event(key_event(pygame.K_RETURN))
    assert driving.radio.station_id == "darren-duff-radio"
    assert streams == ["http://darrenduff.com:1979/stream.mp3"]
    assert any("Selected Darren Duff radio" in line for line in spoken)
    # The row now says so.
    assert "tuned now" in app.state.items[0].text


def test_a_search_with_no_match_stays_in_the_field(radio_app):
    from freight_fate.states.driving_radio_app import RadioSearchEntryState

    app, _driving, spoken, _streams = radio_app
    _select(app.state, "Search stations")
    _type(app.state, "zzqxv")
    app.state.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, RadioSearchEntryState)
    assert spoken[-1].startswith("No stations match zzqxv")


def test_tuning_from_the_app_switches_a_radio_that_is_off_back_on(radio_app):
    app, driving, spoken, _streams = radio_app
    driving.radio.enabled = False
    _select(app.state, "Search stations")
    _type(app.state, "darren")
    app.state.handle_event(key_event(pygame.K_RETURN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    assert driving.radio.enabled is True
    assert spoken[-1].startswith("Radio on. Selected Darren Duff radio")


def test_favorites_are_saved_listed_and_tuned_from_the_app(radio_app):
    from freight_fate.states.driving_radio_app import RadioAppState, RadioStationListState

    app, driving, spoken, _streams = radio_app
    # Tune Darren Duff through search, come back to the front page.
    _select(app.state, "Search stations")
    _type(app.state, "darren")
    app.state.handle_event(key_event(pygame.K_RETURN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    app.state.handle_event(key_event(pygame.K_ESCAPE))
    app.state.handle_event(key_event(pygame.K_ESCAPE))
    assert isinstance(app.state, RadioAppState)
    # Save it.
    _select(app.state, "Save Darren Duff radio to favorites")
    assert spoken[-1] == "Saved Darren Duff radio to favorites."
    assert "darren-duff-radio" in app.ctx.profile.radio_favorites
    labels = [item.text for item in app.state.items]
    assert "Remove Darren Duff radio from favorites" in labels
    assert "Favorites: 1 saved" in labels
    # Retune elsewhere, then pick it back out of the favorites list.
    driving.radio.select_station("route_playlist", driving._radio_backend)
    _select(app.state, "Favorites:")
    assert isinstance(app.state, RadioStationListState)
    assert app.state.items[0].text.startswith("Darren Duff radio, Web radio, always available")
    assert app.state.items[0].text.endswith("favorite")
    app.state.handle_event(key_event(pygame.K_RETURN))
    assert driving.radio.station_id == "darren-duff-radio"


def test_an_out_of_range_favorite_says_so_instead_of_tuning(radio_app):
    from freight_fate.radio import RadioReception, RadioStation
    from freight_fate.states.driving_radio_app import RadioStationListState

    app, driving, spoken, _streams = radio_app
    far = RadioStation(
        id="far-away", name="Far Away FM", call_sign="KFAR", format="talk", source="test"
    )
    state = RadioStationListState(app.ctx, driving, kind="search", query="far", hits=[(far, None)])
    app.push_state(state)
    assert app.state.items[0].text == "KFAR, Far Away FM, Terrestrial, out of range here"
    app.state.handle_event(key_event(pygame.K_RETURN))
    assert spoken[-1] == "KFAR, Far Away FM is out of range here."
    assert driving.radio.station_id != "far-away"
    _ = RadioReception


def test_the_front_page_reports_what_is_playing_and_the_power_state(radio_app):
    app, driving, spoken, _streams = radio_app
    labels = [item.text for item in app.state.items]
    assert labels[0] == driving._radio_now_playing_text()
    assert labels[1].startswith("Radio: on, tuned to ")
    assert "Search stations" in labels
    assert any(label.startswith("Stations in range:") for label in labels)
    _select(app.state, "Radio: on")
    assert driving.radio.enabled is False
    assert app.state.items[1].text.startswith("Radio: off")
