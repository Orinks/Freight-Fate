"""Spoken roadside landmarks and billboards, and the chatter switches."""

import pytest
from speech_capture import speech_stub

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
        "billboard_sign",
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
    # Placed billboard signs ride the same billboards switch as the random pool.
    assert not s.chatter_enabled("billboard_sign")
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
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(calls))
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
        d._pending_ambient_events.clear()
        d._handle_trip_event(billboard)
        assert len(calls) == 2
    finally:
        app.shutdown()


# -- terse chatter -------------------------------------------------------------


CHATTER_CASES = (
    # switch, category, the baked line, the name the short form must keep
    ("chatter_parks", "national_park", "Entering Hot Springs National Park.", "Hot Springs"),
    ("chatter_rivers", "river", "Crossing the Cahaba River.", "Cahaba River"),
    ("chatter_passes", "mountain_pass", "Approaching Lone Pine Saddle.", "Lone Pine Saddle"),
    ("chatter_museums", "museum", "Cullman County Museum ahead.", "Cullman County Museum"),
    ("chatter_billboards", "billboard", "Billboard: Free ice water.", "Free ice water"),
)


def _chatter_event(category, spoken):
    kind = TripEventKind.BILLBOARD if category == "billboard" else TripEventKind.LANDMARK
    return TripEvent(kind, spoken, {"category": category})


@pytest.mark.parametrize(("switch", "category", "spoken", "name"), CHATTER_CASES)
def test_terse_speaks_every_chatter_category_its_switch_leaves_on(
    monkeypatch, switch, category, spoken, name
):
    """Owner, 2026-08-15: "Roadside chatter is pinned to the normal or terse
    setting. When terse, the individual settings don't mean anything."

    Terse used to mute roadside chatter wholesale, so a terse player had five
    switches that were on, looked live, and did nothing. The switch decides
    what is heard; verbosity decides how much is said about it."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        heard = []
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(heard, terse=True))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        app.ctx.settings.driving_speech = "quiet"
        app.ctx.settings.set_all_chatter(True)

        d._handle_trip_event(_chatter_event(category, spoken))

        assert len(heard) == 1, heard
        assert name in heard[0]
        # Short form, not the full line: the name and the fact, no framing.
        assert len(heard[0]) < len(spoken)
    finally:
        app.shutdown()


@pytest.mark.parametrize(("switch", "category", "spoken", "name"), CHATTER_CASES)
def test_terse_stays_silent_for_a_chatter_category_switched_off(
    monkeypatch, switch, category, spoken, name
):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        heard = []
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(heard, terse=True))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        app.ctx.settings.driving_speech = "quiet"
        app.ctx.settings.set_all_chatter(True)
        setattr(app.ctx.settings, switch, False)

        d._handle_trip_event(_chatter_event(category, spoken))

        assert heard == []
        # A muted callout is dropped whole: it never becomes the A-key replay.
        assert d._last_event_message != spoken
    finally:
        app.shutdown()


@pytest.mark.parametrize(("switch", "category", "spoken", "name"), CHATTER_CASES)
def test_normal_speech_still_hears_the_whole_chatter_line(
    monkeypatch, switch, category, spoken, name
):
    """The other axis is unchanged: normal mode still gets the full line."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        heard = []
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(heard))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        app.ctx.settings.driving_speech = "standard"
        app.ctx.settings.set_all_chatter(True)

        d._handle_trip_event(_chatter_event(category, spoken))

        assert heard == [spoken]
    finally:
        app.shutdown()


def test_a_switched_off_category_is_silent_in_terse_even_mid_drive(monkeypatch):
    """The switches are read at speak time, so flipping one mid-drive applies
    to the next callout rather than to the next trip."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        heard = []
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(heard, terse=True))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        app.ctx.settings.driving_speech = "quiet"
        app.ctx.settings.set_all_chatter(True)

        d._handle_trip_event(_chatter_event("river", "Crossing the Cahaba River."))
        assert heard == ["Cahaba River."]

        app.ctx.settings.chatter_rivers = False
        d._ambient_event_cooldown_s = 0.0
        d._pending_ambient_events.clear()
        d._handle_trip_event(_chatter_event("river", "Crossing the Elk River."))
        assert heard == ["Cahaba River."]
    finally:
        app.shutdown()


def test_village_callouts_keep_the_place_callouts_ladder(monkeypatch):
    """Town names are places, not chatter: they answer to place_callouts, and
    terse still leaves them out. Untouched by the chatter change."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        heard = []
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(heard, terse=True))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        app.ctx.settings.set_all_chatter(True)
        app.ctx.settings.place_callouts = "all"
        app.ctx.settings.driving_speech = "quiet"

        d._handle_trip_event(_chatter_event("village", "Passing Fairfield."))
        assert heard == []

        app.ctx.settings.driving_speech = "standard"
        d._ambient_event_cooldown_s = 0.0
        d._pending_ambient_events.clear()
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(heard))
        d._handle_trip_event(_chatter_event("village", "Passing Fairfield."))
        assert heard == ["Passing Fairfield."]

        app.ctx.settings.place_callouts = "off"
        d._ambient_event_cooldown_s = 0.0
        d._pending_ambient_events.clear()
        d._handle_trip_event(_chatter_event("village", "Passing Midfield."))
        assert heard == ["Passing Fairfield."]
    finally:
        app.shutdown()


def test_roadside_chatter_short_forms_keep_the_fact():
    """The renderer itself, on the shapes the bake actually produces."""
    from freight_fate.speech_text import roadside_chatter

    cases = {
        "Entering Hot Springs National Park.": "Hot Springs National Park.",
        "Crossing the Cahaba River.": "Cahaba River.",
        "Approaching Lone Pine Saddle.": "Lone Pine Saddle.",
        "Cullman County Museum ahead.": "Cullman County Museum.",
        # An initial inside a name is not a sentence end.
        "Museum ahead: Jamie L. Whitten Historical Center.": (
            "Jamie L. Whitten Historical Center."
        ),
        # Prose keeps its opening clause: the name and the fact.
        (
            "You are passing Ozark beside Fort Novosel, the home of Army Aviation, "
            "where every Army helicopter pilot learns to fly."
        ): "Ozark beside Fort Novosel.",
        # A billboard is its gag, with the framing dropped -- and a two-beat
        # gag keeps its punchline.
        "Billboard: Free ice water.": "Free ice water.",
        "Billboard: Eat here. Get gas.": "Eat here. Get gas.",
    }
    for spoken, expected in cases.items():
        message = roadside_chatter(spoken, "test")
        assert message.normal == spoken
        assert message.render(True) == expected
        assert len(message.render(True)) < len(spoken)


def test_every_baked_chatter_line_renders_a_shorter_terse_form(world):
    """No category ends up with an empty, longer, or fragmentary short form,
    and the named categories never lose the name."""
    from freight_fate.settings import CHATTER_CATEGORY_FIELDS
    from freight_fate.speech_text import roadside_chatter

    named = {"river", "mountain_pass", "museum", "national_park", "national_forest"}
    checked = 0
    for leg in world.legs:
        for landmark in leg.landmarks:
            if landmark.category not in CHATTER_CATEGORY_FIELDS:
                continue
            checked += 1
            message = roadside_chatter(f"{landmark.spoken}.", landmark.category)
            terse = message.render(True)
            assert terse and terse != "."
            assert len(terse) <= len(message.normal)
            if landmark.category in named:
                assert landmark.name in terse
    assert checked > 2_000
