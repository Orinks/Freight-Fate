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
    # A local stream can rot off the air (WABE 2026-07-14), but going dark
    # is a documented state, never a silent one: unsupported locals carry
    # notes saying why, and the dial stays overwhelmingly alive.
    dark_locals = [station for station in locals_ if not station.supported]
    assert all(station.notes for station in dark_locals)
    assert len(dark_locals) <= len(locals_) // 10
    assert sum(1 for station in afn if station.supported) >= 15
    assert all(station.lat is not None and station.lon is not None for station in locals_)
    assert all(station.range_miles > 0 for station in locals_)


def test_radio_defaults_to_full_dial_on_builtin_station():
    radio = RadioState()

    assert radio.enabled is True
    assert radio.current_station().id == SAFE_ROUTE_PLAYLIST
    assert radio.volume == 0.25
    # Streamer-safe mode is the opt-out, not the default: the full dial,
    # real public streams included, is the out-of-the-box experience.
    assert radio.streamer_safe is False
    assert any(station.source_type == "afn" for station in radio.available_stations())
    assert "streamer-safe off" in radio.status_text()
    assert "always available" in radio.status_text()


def test_streamer_safe_mode_hides_real_streams():
    radio = RadioState(streamer_safe=True)
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
    settings.radio_streamer_safe = True
    settings.save()

    loaded = Settings.load()
    radio = RadioState.from_settings(loaded)

    assert radio.enabled is False
    assert radio.station_id == "ff-night-line"
    assert radio.volume == 0.4
    assert radio.streamer_safe is True


def test_regional_station_filtering_uses_simulated_truck_position():
    radio = RadioState(
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
        streamer_safe=False,
        position=(47.61, -122.33),
    )
    backend = RecordingBackend()
    receivable = {reception.station.id for reception in radio.receivable_stations()}

    # The guarantee is that the dial is drawn from what the truck can actually
    # receive. That is two claims, and neither needs the whole ring: the
    # receivable set carries Seattle and not Boston, and every press lands
    # inside that set. Together they say no amount of tuning reaches Boston.
    #
    # This used to walk all 5,092 receivable stations at 5.8 ms a press -- 33
    # seconds, 94 percent of this file's runtime after the catalog sweep was
    # collapsed, to re-derive what the set comparison already settles.
    assert "kexp-seattle" in receivable
    assert "wbur-boston" not in receivable

    seen = []
    for _ in range(50):
        action = radio.tune(1, backend)
        seen.append(action.station.id)

    assert seen, "tuning produced no station at all"
    off_dial = sorted(set(seen) - receivable)
    assert not off_dial, f"tuning reached stations the truck cannot receive: {off_dial}"


def test_ff_music_stations_receivable_everywhere_in_every_mode():
    # No truck position and streamer-safe on: the strictest possible dial
    # must still carry every Freight Fate original-music station.
    state = RadioState(position=None, streamer_safe=True)
    names = {reception.station.name for reception in state.receivable_stations()}
    for expected in (
        "The Rawhide 98.1",
        "Big Sky Country 99.3",
        "The Delta 94.3",
        "Nashville After Hours 92.9",
        "Freight Fate Roadhouse",
    ):
        assert expected in names, expected


def test_ff_music_stations_share_the_ff_dial_group():
    from freight_fate.radio import _dial_group

    playlist_backed = [
        station
        for station in DEFAULT_RADIO_CATALOG
        if station.playlist and not station.real_stream and station.id != SAFE_ROUTE_PLAYLIST
    ]
    assert len(playlist_backed) == 18
    assert {_dial_group(station) for station in playlist_backed} == {1}
    assert all(station.always_available for station in playlist_backed)


def test_no_regional_signal_still_has_safe_and_afn_fallback_choices():
    # The doubled radio reach (RADIO_REACH_MULT, 2026-08-13) closed the old
    # US-50 Nevada dead zone -- Reno and Las Vegas's community stations now
    # blanket the interior Great Basin. The Denali Highway is still real
    # radio darkness: no curated local station's doubled contour reaches
    # interior Alaska.
    radio = RadioState(
        streamer_safe=False,
        position=(63.2, -147.0),
    )
    stations = radio.available_stations()

    assert any(station.id == SAFE_ROUTE_PLAYLIST for station in stations)
    assert any(station.source_type == "afn" for station in stations)
    assert not any(station.source_type == "local" for station in stations)


def test_dead_stream_hands_over_inside_its_own_band():
    # A stream that refuses to play must not drop the player to the silent
    # fallback while its band still has stations: the radio hands over to
    # the next receivable station in the same dial category.
    radio = RadioState(
        enabled=True,
        station_id="afn-tokyo",
        streamer_safe=False,
    )
    backend = RecordingBackend(fail_ids={"afn-tokyo"})

    action = radio.play(backend)

    assert action.fallback_used is True
    assert action.station.id != "afn-tokyo"
    assert action.station.source_type == "afn"  # same band as the dead stream
    assert radio.station_id == action.station.id
    assert backend.played == [(action.station.id, 0.25)]
    assert "off the air" in action.message
    assert "handover" in action.message.lower()


def test_dead_stream_leaves_the_dial_for_the_session():
    radio = RadioState(
        enabled=True,
        station_id="afn-tokyo",
        streamer_safe=False,
    )
    backend = RecordingBackend(fail_ids={"afn-tokyo"})
    radio.play(backend)

    ids = {reception.station.id for reception in radio.receivable_stations()}
    assert "afn-tokyo" not in ids
    # Tuning back to it lands elsewhere instead of retrying the dead stream.
    action = radio.select_station("afn-tokyo", backend)
    assert action.station.id != "afn-tokyo"


def test_dead_stream_with_empty_band_still_reaches_the_fallback():
    radio = RadioState(
        enabled=True,
        station_id="afn-tokyo",
        streamer_safe=False,
    )
    afn_ids = {s.id for s in DEFAULT_RADIO_CATALOG if s.source_type == "afn"}
    backend = RecordingBackend(fail_ids=afn_ids)

    # Every AFN stream is dead: repeated failures burn through the band and
    # the last handover lands on the safe fallback station.
    action = radio.play(backend)
    for _ in range(len(afn_ids)):
        if action.station.source_type != "afn":
            break
        action = radio.play(backend)

    assert action.station.id == SAFE_FALLBACK_STATION_ID
    assert radio.station_id == SAFE_FALLBACK_STATION_ID


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


def test_catalog_entries_have_spoken_identity():
    """Every station in the catalog carries what the dial has to say.

    Swept in one test rather than parametrised per station. As a
    parametrisation this was 6,599 of the suite's 9,720 cases -- 68 percent of
    every collection, schedule and report the runner does, for 89 seconds of
    almost pure overhead on a check that reads a static table. It also stopped
    at the first bad station; a data sweep should hand back the whole list,
    because whoever regenerates the catalog wants to fix them in one pass.
    """
    problems: list[str] = []
    for station in DEFAULT_RADIO_CATALOG:
        where = station.id or station.name or "<unnamed station>"
        if not station.id:
            problems.append(f"{where}: no id")
        if not station.name:
            problems.append(f"{where}: no name")
        # Web stations are named, not lettered; everything else leads with a
        # call sign, and display_name copes with either shape.
        if not station.call_sign and station.source_type != "web":
            problems.append(f"{where}: no call sign and not a web station")
        if not station.display_name:
            problems.append(f"{where}: no display name")
        elif station.display_name.startswith(","):
            problems.append(f"{where}: display name starts with a comma")
        if not station.format:
            problems.append(f"{where}: no format")
        if not station.source:
            problems.append(f"{where}: no source")
    assert not problems, (
        f"{len(problems)} catalog entries are missing spoken identity:\n"
        + "\n".join(problems[:40])
        + (f"\n... and {len(problems) - 40} more" if len(problems) > 40 else "")
    )


def test_tuning_with_the_radio_off_says_what_happens_next():
    """Selecting a station while the radio is off is deliberate, not a dead key.

    A tester filed it as a bug (Darren, 2026-08-16) because the reply stopped
    at "Selected ...", which reads exactly like a station that failed to play.
    The pre-selection is real -- switching on lands on it -- so the sentence
    now says so. It names no control: the radio toggle is a keyboard key and
    the pad has none, and spoken advice must not name a control the driver
    may not have.
    """
    from freight_fate.radio import RADIO_OFF_SELECTION_HINT

    radio = RadioState(streamer_safe=False)
    radio.enabled = False
    backend = RecordingBackend()

    tuned = radio.tune(1, backend)
    assert tuned.message.startswith("Radio off.")
    assert RADIO_OFF_SELECTION_HINT in tuned.message
    assert not tuned.enabled
    assert backend.played == [], "a station picked while off must not play"

    jumped = radio.tune_category(1, backend)
    assert jumped.message.startswith("Radio off.")
    assert RADIO_OFF_SELECTION_HINT in jumped.message
    assert backend.played == []

    # The promise the sentence makes has to be true: switching on plays the
    # station that was picked, rather than retuning somewhere else.
    picked = radio.station_id
    switched = radio.toggle(backend)
    assert switched.enabled
    assert radio.station_id == picked
    assert backend.played and backend.played[-1][0] == picked


def test_the_hint_is_absent_once_the_radio_is_on():
    """It explains an unplayed selection; with the radio on there is none."""
    from freight_fate.radio import RADIO_OFF_SELECTION_HINT

    radio = RadioState(streamer_safe=False)
    assert radio.enabled
    message = radio.tune(1, RecordingBackend()).message
    assert RADIO_OFF_SELECTION_HINT not in message
