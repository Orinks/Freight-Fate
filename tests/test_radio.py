import pytest

from freight_fate.radio import (
    DEFAULT_RADIO_CATALOG,
    SAFE_FALLBACK_STATION_ID,
    SAFE_ROUTE_PLAYLIST,
    RadioPlaybackError,
    RadioState,
)
from freight_fate.settings import Settings


class RecordingBackend:
    def __init__(self, *, fail_ids=()):
        self.fail_ids = set(fail_ids)
        self.played = []
        self.stopped = 0

    def play_station(self, station, volume):
        if station.id in self.fail_ids:
            raise RadioPlaybackError("station failed")
        self.played.append((station.id, volume))

    def stop_radio(self):
        self.stopped += 1


def test_radio_defaults_to_streamer_safe_builtin_station():
    radio = RadioState()

    assert radio.enabled is True
    assert radio.current_station().id == SAFE_ROUTE_PLAYLIST
    assert radio.volume == 0.25
    assert radio.streamer_safe is True
    assert radio.real_streams_enabled is False
    assert "afn-pacific" not in [station.id for station in radio.available_stations()]
    assert "streamer-safe" in radio.status_text()


def test_real_stream_station_requires_opt_in_and_streamer_safe_off():
    radio = RadioState(real_streams_enabled=True, streamer_safe=True)
    assert "afn-pacific" not in [station.id for station in radio.available_stations()]

    radio.streamer_safe = False

    assert "afn-pacific" in [station.id for station in radio.available_stations()]


def test_radio_persists_enabled_station_and_volume():
    settings = Settings()
    settings.radio_enabled = False
    settings.radio_station_id = "ff-night-line"
    settings.radio_volume = 0.4
    settings.radio_streamer_safe = False
    settings.radio_real_streams = True
    settings.save()

    loaded = Settings.load()
    radio = RadioState.from_settings(loaded)

    assert radio.enabled is False
    assert radio.station_id == "ff-night-line"
    assert radio.volume == 0.4
    assert radio.streamer_safe is False
    assert radio.real_streams_enabled is True


def test_radio_falls_back_when_backend_cannot_play_selected_station():
    radio = RadioState(
        enabled=True,
        station_id="afn-pacific",
        real_streams_enabled=True,
        streamer_safe=False,
    )
    backend = RecordingBackend(fail_ids={"afn-pacific"})

    action = radio.play(backend)

    assert action.fallback_used is True
    assert action.station.id == SAFE_FALLBACK_STATION_ID
    assert radio.station_id == SAFE_FALLBACK_STATION_ID
    assert backend.played == [(SAFE_FALLBACK_STATION_ID, 0.25)]
    assert "unavailable" in action.message


def test_tuning_skips_real_streams_until_they_are_safe_to_offer():
    radio = RadioState()
    backend = RecordingBackend()

    action = radio.tune(1, backend)

    assert action.station.real_stream is False
    assert action.station.safe_for_streaming is True
    assert "afn-pacific" not in [played[0] for played in backend.played]


@pytest.mark.parametrize("station", DEFAULT_RADIO_CATALOG)
def test_catalog_entries_have_spoken_identity(station):
    assert station.id
    assert station.name
    assert station.call_sign
    assert station.format
    assert station.source
