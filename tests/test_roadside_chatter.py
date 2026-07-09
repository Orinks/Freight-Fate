"""Spoken roadside landmarks and billboards, and the chatter switches."""

import pytest

from freight_fate.data.world_parsing import _parse_landmark
from freight_fate.settings import Settings
from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.trip import TripEvent, TripEventKind
from freight_fate.sim.trip_models import LANDMARK_MIN_SPACING_MI

RAW_MARKERS = ("osm_id", "amenity=", "highway=", "node/", "way/")


def _make_trip(world, start="Las Vegas", end="Ely, NV", seed=7):
    route = world.supported_route(start, end)
    assert route is not None
    return Trip(route, TruckState(), WeatherSystem("great_basin", seed=seed), seed=seed)


# -- data ------------------------------------------------------------------


def test_world_landmarks_are_loaded_and_clean(world):
    total = 0
    for leg in world.legs:
        for landmark in leg.landmarks:
            total += 1
            assert landmark.spoken
            assert landmark.kind in ("zone", "point")
            blob = f"{landmark.name} {landmark.spoken}".lower()
            assert not any(marker in blob for marker in RAW_MARKERS)
            assert 0.0 <= landmark.at_mi <= leg.miles
    assert total > 2_000  # the OSM bake is present, not a stub


def test_parse_landmark_rejects_bad_records():
    good = {
        "name": "Bronx River",
        "category": "river",
        "kind": "point",
        "at_mi": 3.0,
        "spoken": "Crossing the Bronx River",
    }
    assert _parse_landmark(good, 10.0, "a", "b").category == "river"
    with pytest.raises(ValueError):
        _parse_landmark({**good, "category": "volcano"}, 10.0, "a", "b")
    with pytest.raises(ValueError):
        _parse_landmark({**good, "kind": "blob"}, 10.0, "a", "b")
    with pytest.raises(ValueError):
        _parse_landmark({**good, "spoken": ""}, 10.0, "a", "b")
    with pytest.raises(ValueError):
        _parse_landmark({**good, "at_mi": 99.0}, 10.0, "a", "b")
    with pytest.raises(ValueError):
        _parse_landmark({**good, "name": "way/123 river"}, 10.0, "a", "b")


# -- trip scheduling ---------------------------------------------------------


def test_trip_schedules_landmarks_with_spacing(world):
    trip = _make_trip(world)
    assert trip.landmarks  # the Great Basin run passes real landmarks
    miles = [callout.at_mi for callout in trip.landmarks]
    assert miles == sorted(miles)
    gaps = [b - a for a, b in zip(miles, miles[1:], strict=False)]
    assert all(gap >= LANDMARK_MIN_SPACING_MI for gap in gaps)
    for callout in trip.landmarks:
        assert callout.spoken.endswith(".")
        assert callout.category != "billboard"


def test_trip_schedules_billboards_deterministically(world):
    first = _make_trip(world, seed=7)
    second = _make_trip(world, seed=7)
    different = _make_trip(world, seed=8)

    assert [c.spoken for c in first.billboards] == [c.spoken for c in second.billboards]
    assert first.billboards  # long highway run gets signs
    texts = [c.spoken for c in first.billboards]
    assert len(texts) == len(set(texts))  # a joke never repeats in one trip
    assert [c.spoken for c in different.billboards] != texts


def test_facility_approach_routes_stay_quiet(world):
    facility = world.city("Chicago").locations[0]
    route = world.facility_approach_route("Chicago", facility.name)
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=1)

    assert trip.landmarks == []
    assert trip.billboards == []


# -- emission ----------------------------------------------------------------


def test_landmark_emits_once_at_its_mile(world):
    trip = _make_trip(world)
    callout = trip.landmarks[0]
    trip.position_mi = callout.at_mi + 0.2
    trip._events = []
    trip._check_roadside_callouts()
    events = [e for e in trip._events if e.kind == TripEventKind.LANDMARK]
    assert [e.message for e in events] == [callout.spoken]
    assert events[0].data.get("category") == callout.category

    trip._events = []
    trip._check_roadside_callouts()
    assert not [e for e in trip._events if e.kind == TripEventKind.LANDMARK]


def test_overshot_callouts_are_skipped_silently(world):
    trip = _make_trip(world)
    callout = trip.landmarks[0]
    trip.position_mi = callout.at_mi + 5.0
    trip._events = []
    trip._check_roadside_callouts()
    assert not [e for e in trip._events if e.kind == TripEventKind.LANDMARK]
    assert callout.key in trip._announced_landmarks


def test_restore_does_not_replay_passed_callouts(world):
    trip = _make_trip(world)
    callout = trip.landmarks[0]
    trip.restore(callout.at_mi + 0.5, game_minutes=30.0)
    trip._events = []
    trip._check_roadside_callouts()
    assert not [e for e in trip._events if e.kind == TripEventKind.LANDMARK]


# -- settings ----------------------------------------------------------------


def test_chatter_settings_map_categories():
    s = Settings()
    assert s.chatter_summary() == "everything"
    for category in (
        "national_park",
        "national_forest",
        "wilderness",
        "protected_area",
        "river",
        "mountain_pass",
        "highway_marker",
        "museum",
        "billboard",
    ):
        assert s.chatter_enabled(category)

    s.chatter_parks = False
    assert not s.chatter_enabled("national_forest")
    assert not s.chatter_enabled("protected_area")
    assert s.chatter_enabled("river")
    assert s.chatter_summary() == "custom"

    s.set_all_chatter(False)
    assert s.chatter_summary() == "off"
    assert not s.chatter_enabled("billboard")
    # An unknown future category speaks rather than silently vanishing.
    assert s.chatter_enabled("meteor_crater")

    s.set_all_chatter(True)
    assert s.chatter_summary() == "everything"


def test_chatter_settings_survive_save_and_load():
    s = Settings()
    s.chatter_billboards = False
    s.chatter_rivers = False
    s.save()

    loaded = Settings.load()
    assert not loaded.chatter_billboards
    assert not loaded.chatter_rivers
    assert loaded.chatter_parks


# -- settings menu -----------------------------------------------------------


def test_settings_menu_speaks_and_flips_chatter_switches():
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsCategoryState

    app = App()
    try:
        menu = SettingsCategoryState(app.ctx, "speech")
        menu.items = menu.build_items()
        labels = [item.text for item in menu.items]
        master = labels.index("Roadside chatter: everything")
        billboard = labels.index("Speak billboards: on")

        menu.index = billboard
        menu.items[billboard].action()
        menu.items = menu.build_items()
        assert menu.items[billboard].text == "Speak billboards: off"
        assert not app.ctx.settings.chatter_billboards
        assert menu.items[master].text == "Roadside chatter: custom"

        # Left arrow on the master switch silences every kind at once.
        menu.index = master
        menu._adjust(-1)
        menu.items = menu.build_items()
        assert menu.items[master].text == "Roadside chatter: off"
        assert app.ctx.settings.chatter_summary() == "off"

        menu._adjust(1)
        menu.items = menu.build_items()
        assert menu.items[master].text == "Roadside chatter: everything"
        assert app.ctx.settings.chatter_parks
    finally:
        app.shutdown()


# -- driving handler ---------------------------------------------------------


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Chatter", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles,
        1000.0,
        12.0,
        destination_location="Rochester freight market",
    )
    return DrivingState(app.ctx, job, route, phase="delivery")


def test_chatter_switches_gate_spoken_callouts(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = []
        monkeypatch.setattr(
            app.ctx, "say_event", lambda text, interrupt=True: calls.append(text)
        )
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        river = TripEvent(
            TripEventKind.LANDMARK, "Crossing the White River.", {"category": "river"}
        )
        billboard = TripEvent(
            TripEventKind.BILLBOARD, "Billboard: Free ice water.", {"category": "billboard"}
        )

        d._handle_trip_event(river)
        assert calls[-1] == "Crossing the White River."

        app.ctx.settings.chatter_rivers = False
        d._ambient_event_cooldown_s = 0.0
        d._handle_trip_event(river)
        assert calls[-1] == "Crossing the White River."  # no new call: filtered
        assert len(calls) == 1
        # A muted callout never becomes the A-key replay either.
        assert d._last_event_message != "Crossing the White River." or calls == [
            "Crossing the White River."
        ]

        d._ambient_event_cooldown_s = 0.0
        d._handle_trip_event(billboard)
        assert calls[-1] == "Billboard: Free ice water."

        app.ctx.settings.chatter_billboards = False
        d._ambient_event_cooldown_s = 0.0
        d._pending_ambient_event = None
        d._handle_trip_event(billboard)
        assert len(calls) == 2

        # Terse speech mutes all roadside chatter regardless of switches.
        app.ctx.settings.set_all_chatter(True)
        app.ctx.settings.speech_verbosity = 0
        d._ambient_event_cooldown_s = 0.0
        d._pending_ambient_event = None
        d._handle_trip_event(river)
        assert len(calls) == 2
    finally:
        app.shutdown()
