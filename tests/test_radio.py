import pytest

from freight_fate.radio import (
    DEFAULT_RADIO_CATALOG,
    SAFE_FALLBACK_STATION_ID,
    SAFE_ROUTE_PLAYLIST,
    RadioPlaybackError,
    RadioState,
    estimate_signal,
    load_radio_catalog,
    truck_position,
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


def station_ids(stations):
    return [station.id for station in stations]


def test_catalog_loads_structured_regional_and_afn_stations():
    catalog = load_radio_catalog()
    ids = station_ids(catalog)
    afn = [station for station in catalog if station.source_type == "afn"]
    locals_ = [station for station in catalog if station.source_type == "local"]

    assert len(catalog) >= 20
    assert SAFE_ROUTE_PLAYLIST in ids
    assert SAFE_FALLBACK_STATION_ID in ids
    assert len(afn) >= 5
    assert {
        "afn-aviano",
        "afn-bavaria",
        "afn-benelux",
        "afn-tokyo",
        "afn-guantanamo-bay",
        "afn-incirlik",
        "afn-kaiserslautern",
        "afn-humphreys",
        "afn-daegu",
        "afn-bahrain",
        "afn-naples",
        "afn-rota",
        "afn-sigonella",
        "afn-souda-bay",
        "afn-spangdahlem",
        "afn-stuttgart",
        "afn-vicenza",
        "afn-wiesbaden",
    } <= set(ids)
    assert len({station.region for station in locals_}) >= 7
    assert all(station.stream_url for station in afn + locals_)
    assert all(station.stream_format for station in afn + locals_)
    assert all(station.supported for station in locals_)
    assert sum(1 for station in afn if station.supported) >= 15
    assert all(station.lat is not None and station.lon is not None for station in locals_)
    assert all(station.range_miles > 0 for station in locals_)


def test_radio_defaults_to_streamer_safe_builtin_station():
    radio = RadioState()

    assert radio.enabled is True
    assert radio.current_station().id == SAFE_ROUTE_PLAYLIST
    assert radio.volume == 0.25
    assert radio.streamer_safe is True
    assert radio.real_streams_enabled is False
    assert not any(station.source_type == "afn" for station in radio.available_stations())
    assert "streamer-safe" in radio.status_text()
    assert "always available" in radio.status_text()


def test_real_stream_station_requires_opt_in_and_streamer_safe_off():
    radio = RadioState(real_streams_enabled=True, streamer_safe=True)
    assert not any(station.source_type == "afn" for station in radio.available_stations())

    radio.streamer_safe = False

    assert any(station.id == "afn-tokyo" for station in radio.available_stations())
    assert all(
        not station.safe_for_streaming
        for station in radio.available_stations()
        if station.real_stream
    )


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


def test_regional_station_filtering_uses_simulated_truck_position():
    radio = RadioState(
        real_streams_enabled=True,
        streamer_safe=False,
        position=(47.61, -122.33),
    )
    ids = station_ids(radio.available_stations())

    assert "kexp-seattle" in ids
    assert "wbur-boston" not in ids
    kexp = next(station for station in radio.available_stations() if station.id == "kexp-seattle")
    assert estimate_signal(kexp, radio.position).signal_label == "strong signal"


def test_tuning_uses_receivable_stations_not_global_catalog():
    radio = RadioState(
        real_streams_enabled=True,
        streamer_safe=False,
        position=(47.61, -122.33),
    )
    backend = RecordingBackend()

    seen = []
    for _ in range(4):
        action = radio.tune(1, backend)
        seen.append(action.station.id)

    assert "kexp-seattle" in seen
    assert "wbur-boston" not in seen


def test_no_regional_signal_still_has_safe_and_afn_fallback_choices():
    # Interior Nevada on US-50: real radio darkness even after the
    # 623-city coverage fill (central South Dakota is SDPB country now).
    radio = RadioState(
        real_streams_enabled=True,
        streamer_safe=False,
        position=(38.9, -116.6),
    )
    stations = radio.available_stations()

    assert any(station.id == SAFE_ROUTE_PLAYLIST for station in stations)
    assert any(station.source_type == "afn" for station in stations)
    assert not any(station.source_type == "local" for station in stations)


def test_radio_falls_back_when_backend_cannot_play_selected_station():
    radio = RadioState(
        enabled=True,
        station_id="afn-tokyo",
        real_streams_enabled=True,
        streamer_safe=False,
    )
    backend = RecordingBackend(fail_ids={"afn-tokyo"})

    action = radio.play(backend)

    assert action.fallback_used is True
    assert action.station.id == SAFE_FALLBACK_STATION_ID
    assert radio.station_id == SAFE_FALLBACK_STATION_ID
    assert backend.played == [(SAFE_FALLBACK_STATION_ID, 0.25)]
    assert "unavailable" in action.message
    assert "fallback" in action.message


def test_driving_radio_backend_plays_real_stream_url():
    from freight_fate.radio import RadioStation
    from freight_fate.states.driving_core import _DrivingRadioBackend

    class Audio:
        def __init__(self):
            self.streams = []

        def play_radio_stream(self, url, fade_ms=1500):
            self.streams.append((url, fade_ms))

    class Ctx:
        def __init__(self):
            self.audio = Audio()

    class Driving:
        def __init__(self):
            self.ctx = Ctx()
            self.volume_applied = False

        def _apply_radio_volume(self):
            self.volume_applied = True

    driving = Driving()
    backend = _DrivingRadioBackend(driving)
    station = RadioStation(
        "test-stream",
        "Test Stream",
        "TEST",
        "music",
        "fixture",
        stream_url="https://example.test/live.mp3",
        real_stream=True,
    )

    backend.play_station(station, 0.25)

    assert driving.volume_applied
    assert driving.ctx.audio.streams == [("https://example.test/live.mp3", 900)]


def test_spoken_status_includes_signal_source_safety_and_volume():
    radio = RadioState(
        real_streams_enabled=True,
        streamer_safe=False,
        station_id="kexp-seattle",
        position=(47.61, -122.33),
        volume=0.35,
    )

    text = radio.status_text()

    assert "KEXP" in text
    assert "strong signal" in text
    assert "Volume 35 percent" in text
    assert "streamer-safe off" in text
    assert "Source:" in text


def test_truck_position_uses_route_geometry(world):
    route = world.route_from_cities(["Seattle", "Portland"])
    position = truck_position(route, route.miles / 2, world)

    assert position is not None
    lat, lon = position
    assert 44.0 <= lat <= 48.5
    assert -124.0 <= lon <= -121.0


@pytest.mark.parametrize("station", DEFAULT_RADIO_CATALOG)
def test_catalog_entries_have_spoken_identity(station):
    assert station.id
    assert station.name
    assert station.call_sign
    assert station.format
    assert station.source
