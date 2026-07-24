import pytest

from freight_fate.radio import (
    DEFAULT_RADIO_CATALOG,
    DIRECTORY_SOURCE_TYPE,
    SAFE_FALLBACK_STATION_ID,
    SAFE_ROUTE_PLAYLIST,
    RadioPlaybackError,
    RadioState,
    estimate_signal,
    load_radio_catalog,
    truck_position,
)
from freight_fate.radio_browser import DirectoryStation
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


def _directory_station(
    *,
    uuid="12345678-1234-1234-1234-123456789abc",
    name="KTEST Community",
    distance=5.0,
):
    return DirectoryStation(
        uuid=uuid,
        name=name,
        format="community; MP3, 128 kilobits",
        codec="MP3",
        bitrate=128,
        stream_url="https://stream.example/live",
        lat=42.9,
        lon=-78.8,
        distance_miles=distance,
        state="New York",
        city="Buffalo",
    )


def test_catalog_contains_only_built_in_and_curated_offline_stations():
    catalog = load_radio_catalog()
    ids = station_ids(catalog)
    regional = [station for station in catalog if station.source_type == "regional"]

    assert len(catalog) >= 15
    assert SAFE_ROUTE_PLAYLIST in ids
    assert SAFE_FALLBACK_STATION_ID in ids
    assert len(regional) >= 10
    assert not any(station.real_stream for station in catalog)
    assert not any(station.stream_url for station in catalog)


def test_radio_defaults_to_streamer_safe_builtin_station():
    radio = RadioState()

    assert radio.enabled is True
    assert radio.current_station().id == SAFE_ROUTE_PLAYLIST
    assert radio.volume == 0.25
    assert radio.streamer_safe is True
    assert radio.real_streams_enabled is False
    assert not any(
        station.source_type == DIRECTORY_SOURCE_TYPE for station in radio.available_stations()
    )
    assert "streamer-safe" in radio.status_text()
    assert "always available" in radio.status_text()


def test_real_stream_station_requires_opt_in_and_streamer_safe_off():
    radio = RadioState(real_streams_enabled=True, streamer_safe=True)
    radio.replace_directory_stations((_directory_station(),))
    assert not any(
        station.source_type == DIRECTORY_SOURCE_TYPE for station in radio.available_stations()
    )

    radio.streamer_safe = False

    assert any(
        station.id == "radio-browser:12345678-1234-1234-1234-123456789abc"
        for station in radio.available_stations()
    )
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
    radio = RadioState(position=(47.61, -122.33))
    ids = station_ids(radio.available_stations())

    assert "ksnd-seattle" in ids
    assert "wsol-atlanta" not in ids
    station = next(
        station for station in radio.available_stations() if station.id == "ksnd-seattle"
    )
    assert estimate_signal(station, radio.position).signal_label == "strong signal"


def test_tuning_uses_receivable_stations_not_global_catalog():
    radio = RadioState(
        real_streams_enabled=True,
        streamer_safe=False,
        position=(47.61, -122.33),
    )
    radio.replace_directory_stations((_directory_station(name="Nearby Test"),))
    backend = RecordingBackend()

    seen = []
    for _ in range(len(radio.receivable_stations())):
        action = radio.tune(1, backend)
        seen.append(action.station.id)

    assert "radio-browser:12345678-1234-1234-1234-123456789abc" in seen
    assert "wsol-atlanta" not in seen


def test_no_regional_signal_still_has_safe_fallback_choices():
    # Interior Nevada on US-50: real radio darkness even after the
    # 623-city coverage fill (central South Dakota is SDPB country now).
    radio = RadioState(
        real_streams_enabled=True,
        streamer_safe=False,
        position=(38.9, -116.6),
    )
    stations = radio.available_stations()

    assert any(station.id == SAFE_ROUTE_PLAYLIST for station in stations)
    assert any(station.id == SAFE_FALLBACK_STATION_ID for station in stations)
    assert not any(station.source_type == "local" for station in stations)


def test_radio_falls_back_when_backend_cannot_play_selected_station():
    stream = _directory_station()
    radio = RadioState(
        catalog=DEFAULT_RADIO_CATALOG,
        enabled=True,
        real_streams_enabled=True,
        streamer_safe=False,
    )
    radio.replace_directory_stations((stream,))
    station_id = f"radio-browser:{stream.uuid}"
    radio.select_station(station_id)
    backend = RecordingBackend(fail_ids={station_id})

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
    stream = _directory_station(name="KTEST Buffalo")
    radio = RadioState(
        real_streams_enabled=True,
        streamer_safe=False,
        volume=0.35,
    )
    radio.replace_directory_stations((stream,))
    radio.select_station(f"radio-browser:{stream.uuid}")

    text = radio.status_text()

    assert "KTEST Buffalo" in text
    assert "nearby internet station" in text
    assert "Volume 35 percent" in text
    assert "streamer-safe off" in text
    assert "Source:" in text


def test_discovery_arrival_preserves_current_playback_and_stable_preference():
    radio = RadioState(
        enabled=True,
        station_id="radio-browser:12345678-1234-1234-1234-123456789abc",
        real_streams_enabled=True,
        streamer_safe=False,
    )
    assert radio.current_station().id == SAFE_FALLBACK_STATION_ID
    assert radio.preferred_station_id.endswith("123456789abc")

    radio.replace_directory_stations((_directory_station(),))

    assert radio.current_station().id == SAFE_FALLBACK_STATION_ID
    assert radio.preferred_station_id.endswith("123456789abc")
    assert any(station.id == radio.preferred_station_id for station in radio.available_stations())


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
