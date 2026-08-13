"""Real-seconds breathing gaps for the routine road talkers.

Owner report 2026-08-13: in every driving mode the routine events -- limit
changes, traffic calls, zone chatter -- arrive back to back, because time
compression spends road 10-40x faster than a real cab and each system
announces on road distance. The owner kept the clock (career pacing is
balanced on it) and chose to space the ANNOUNCEMENTS in real seconds, the
same law the corner warnings already follow. Mechanics are untouched:
limits still bind, cruise still follows; only the narration breathes.
"""

import pytest

from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.road_event_pacing import (
    LIMIT_GAP_REAL_S,
    TRAFFIC_GAP_REAL_S,
    ZONE_GAP_REAL_S,
    RoadEventBreather,
)
from freight_fate.sim.traffic_manager import TrafficVehicle
from freight_fate.sim.trip import TripEventKind
from freight_fate.sim.trip_models import Zone


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_first_line_of_a_category_is_always_ready():
    b = RoadEventBreather(clock=FakeClock())
    assert b.ready("limit")
    assert b.ready("traffic")
    assert b.ready("zone")


def test_speaking_closes_the_window_for_the_gap():
    clock = FakeClock()
    b = RoadEventBreather(clock=clock)
    b.spoke("limit")
    clock.now += LIMIT_GAP_REAL_S - 0.5
    assert not b.ready("limit")
    clock.now += 1.0
    assert b.ready("limit")


def test_categories_are_independent():
    clock = FakeClock()
    b = RoadEventBreather(clock=clock)
    b.spoke("limit")
    assert b.ready("traffic")
    assert b.ready("zone")


def test_ready_never_consumes():
    b = RoadEventBreather(clock=FakeClock())
    assert b.ready("limit")
    assert b.ready("limit")  # polling twice is not speaking twice


def test_gap_constants_are_real_seconds_apart():
    # The gaps are the design's numbers; a drive-by refactor that halves
    # them silently reintroduces the chatter this exists to kill.
    assert pytest.approx(12.0) == LIMIT_GAP_REAL_S
    assert pytest.approx(10.0) == TRAFFIC_GAP_REAL_S
    assert pytest.approx(15.0) == ZONE_GAP_REAL_S


# --- Trip._check_speed_limit gating (Task 2) --------------------------------
#
# Trip wires the same RoadEventBreather (category "limit") into its posted-
# limit arrival line. These tests drive _check_speed_limit directly, the
# same way tests/test_weather_trip.py's speed-limit tests do, and control
# the breather's clock with the FakeClock above instead of the real one.


def _make_trip(world, start="Chicago", end="Indianapolis", seed=2):
    route = world.route_options(start, end)[0]
    truck = TruckState()
    truck.transmission.automatic = True
    truck.start_engine()
    weather = WeatherSystem("great_lakes", seed=1)
    trip = Trip(route, truck, weather, seed=seed)
    trip.traffic_manager.rolling_bubble = False
    trip._active_zone = None
    return trip


def _gps_cue_messages(trip):
    return [e.message for e in trip._events if e.kind == TripEventKind.GPS_CUE]


def _install_fake_clock(trip, monkeypatch):
    """Wire a FakeClock into trip._event_breather."""
    clock = FakeClock()
    monkeypatch.setattr(trip._event_breather, "_clock", clock)
    return clock


def test_two_limit_changes_inside_the_gap_speak_once_with_the_newest(world, monkeypatch):
    trip = _make_trip(world)
    clock = _install_fake_clock(trip, monkeypatch)

    # First posting change: the window is open (nothing spoken yet), so it
    # speaks immediately.
    trip._announced_speed_limit = 55.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 60.0)
    trip._events.clear()
    trip._check_speed_limit()
    first = _gps_cue_messages(trip)
    assert len(first) == 1
    assert "raised to" in first[0]

    # A second change 3 real seconds later is well inside LIMIT_GAP_REAL_S:
    # gated. It must not speak, and the gate leaves _announced_speed_limit
    # untouched so the miss is total, not a partial commit.
    clock.now += 3.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 65.0)
    trip._events.clear()
    trip._check_speed_limit()
    assert _gps_cue_messages(trip) == []
    assert trip._announced_speed_limit == 60.0

    # Once the window reopens, the next check announces the CURRENT posting
    # (65) directly -- the missed 65 is never separately spoken as a
    # follow-up to the (also unspoken) intermediate state.
    clock.now += LIMIT_GAP_REAL_S
    trip._events.clear()
    trip._check_speed_limit()
    reopened = _gps_cue_messages(trip)
    assert len(reopened) == 1
    assert "raised to" in reopened[0]
    assert trip._speed_value(65.0) in reopened[0]
    assert trip._speed_value(60.0) not in reopened[0]


def test_a_limit_bounce_inside_the_gap_never_speaks(world, monkeypatch):
    trip = _make_trip(world)
    clock = _install_fake_clock(trip, monkeypatch)
    trip.position_mi = 0.0

    # A drop small enough to stay routine (not the >10 mph urgent exemption).
    trip._announced_speed_limit = 55.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 45.0)
    trip._events.clear()
    trip._check_speed_limit()
    assert len(_gps_cue_messages(trip)) == 1

    # Within the gap the posting bounces straight back up -- the owner's
    # "dropping and coming straight back" complaint. Gated: nothing new
    # spoken, and _announced_speed_limit stays at 45 (untouched).
    clock.now += 3.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 55.0)
    trip._events.clear()
    trip._check_speed_limit()
    assert _gps_cue_messages(trip) == []
    assert trip._announced_speed_limit == 45.0

    # By the time the window opens, the reading has settled back to exactly
    # what was last spoken (45): current == last spoken, so the "if limit !=
    # announced" branch never triggers and nothing is said -- the bounce
    # stays fully dead, not merely delayed.
    clock.now += LIMIT_GAP_REAL_S
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 45.0)
    trip._events.clear()
    trip._check_speed_limit()
    assert _gps_cue_messages(trip) == []
    assert trip._announced_speed_limit == 45.0


def test_a_big_unannounced_drop_cuts_the_gap(world, monkeypatch):
    trip = _make_trip(world)
    clock = _install_fake_clock(trip, monkeypatch)
    trip.position_mi = 0.0

    # A routine change speaks and closes the window.
    trip._announced_speed_limit = 70.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 65.0)
    trip._events.clear()
    trip._check_speed_limit()
    assert len(_gps_cue_messages(trip)) == 1

    # 2 seconds later -- well inside LIMIT_GAP_REAL_S -- a serious,
    # never-preannounced drop (65 -> 45, a 20 mph cut) must cut the line: it
    # is ticket-relevant now, not something that can wait for the window.
    clock.now += 2.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 45.0)
    trip._events.clear()
    trip._check_speed_limit()
    urgent = _gps_cue_messages(trip)
    assert len(urgent) == 1
    assert "reduced to" in urgent[0]
    assert trip._speed_value(45.0) in urgent[0]
    assert trip._announced_speed_limit == 45.0


# --- Trip._check_npc_traffic_cues gating (Task 3) ---------------------------
#
# The traffic gate has to sit BEFORE ``traffic_manager.next_situation`` is
# ever called: that call is what marks a vehicle's key announced, so a gated
# call that still reached it would burn the announcement silently and the
# vehicle would never be spoken for, gap open or not.


def _npc(key: str, position_mi: float, speed_mph: float = 40.0) -> TrafficVehicle:
    return TrafficVehicle(
        key=key,
        position_mi=position_mi,
        speed_mph=speed_mph,
        target_speed_mph=speed_mph,
        relative_lane=0,
        intent="following",
        vehicle_class="car",
        lane=0,
    )


def test_two_traffic_situations_inside_the_gap_speak_once(world, monkeypatch):
    trip = _make_trip(world)
    clock = _install_fake_clock(trip, monkeypatch)
    manager = trip.traffic_manager

    vehicle_a = _npc("npc:a", position_mi=1.0)
    vehicle_b = _npc("npc:b", position_mi=3.5)
    manager.vehicles = [vehicle_a, vehicle_b]
    trip.position_mi = 0.0

    # Vehicle A is the only one in the 2.2-mile announcing window (B is
    # 3.5 mi out, past TRAFFIC_LOOKAHEAD_MI): the window is open, so it
    # speaks immediately.
    trip._events.clear()
    trip._check_npc_traffic_cues()
    first = _gps_cue_messages(trip)
    assert len(first) == 1
    assert manager.announced_vehicle_keys == {"npc:a"}

    # 3 fake seconds later -- well inside TRAFFIC_GAP_REAL_S -- the truck
    # has passed vehicle A (now more than its length behind, out of the
    # lead-vehicle window) and vehicle B has reached the 2.2-mile window.
    # The gate sits before next_situation is called at all, so the check
    # must return without touching the manager: vehicle B's key must not
    # be marked announced by a call that never spoke for it.
    clock.now += 3.0
    trip.position_mi = 1.4
    trip._events.clear()
    trip._check_npc_traffic_cues()
    assert _gps_cue_messages(trip) == []
    assert manager.announced_vehicle_keys == {"npc:a"}
    assert "npc:b" not in manager.announced_vehicle_keys

    # Once the window reopens, the check announces the CURRENT nearest
    # situation (vehicle B) directly.
    clock.now += TRAFFIC_GAP_REAL_S
    trip._events.clear()
    trip._check_npc_traffic_cues()
    reopened = _gps_cue_messages(trip)
    assert len(reopened) == 1
    assert manager.announced_vehicle_keys == {"npc:a", "npc:b"}


# --- Trip._check_zones ZONE_ENTER gating (Task 3) ----------------------------
#
# Only the colour line ("Entering ... zone" / "Work zone active. ...") gates.
# Zone bookkeeping (``_active_zone``, the construction grace start, the
# congestion injection) is mechanics, not narration, and stays untouched --
# only the announcement is held back. The construction-merge warning and the
# barrel-clock lane-closure system live in the driving state's own work-zone
# machinery (``driving_updates.DrivingUpdatesMixin._update_merge``) and are
# never routed through the breather at all.


def test_zone_entry_colour_breathes_but_merge_warnings_do_not(world, monkeypatch):
    trip = _make_trip(world)
    clock = _install_fake_clock(trip, monkeypatch)

    zone1 = Zone(2.0, 4.0, 45.0, "construction")
    zone2 = Zone(10.0, 12.0, 45.0, "construction")
    trip.zones = [zone1, zone2]

    trip.position_mi = 2.0
    trip._events.clear()
    trip._check_zones()
    first = [e for e in trip._events if e.kind == TripEventKind.ZONE_ENTER]
    assert len(first) == 1
    assert trip._active_zone is zone1

    # 3 fake seconds later -- well inside ZONE_GAP_REAL_S -- the truck
    # enters the second zone. The colour line is gated...
    clock.now += 3.0
    trip.position_mi = 10.0
    trip._events.clear()
    trip._check_zones()
    assert [e for e in trip._events if e.kind == TripEventKind.ZONE_ENTER] == []
    # ...but the zone mechanics (which zone governs the posted limit) still
    # track the truck's real position; only the narration is held back.
    assert trip._active_zone is zone2

    # The construction-merge warning is a different system entirely, and it
    # must keep speaking even while this trip's own "zone" window is closed.
    assert not trip._event_breather.ready("zone")

    from speech_capture import speech_stub

    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    spoken: list[str] = []
    try:
        app.ctx.profile = Profile(name="ZonePacing", current_city="Buffalo")
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
        d = DrivingState(app.ctx, job, route, phase="delivery")
        d.trip.traffic_manager.vehicles = []
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        d.truck.start_engine()
        d.truck.velocity_mps = 55.0 / 2.2369362920544

        # Close this (separate) trip's own "zone" window with a real-clock
        # spoke() -- proving the merge warning below never consults it.
        d.trip._event_breather.spoke("zone")
        assert not d.trip._event_breather.ready("zone")

        d.trip.position_mi = 4.5
        d.trip.zones.append(Zone(4.0, 5.0, 55.0, "construction merge", closed_side="left"))
        d.lane.lane = 1  # riding the lane that closes at the barrels
        for _ in range(200):
            d._update_merge(0.1)

        assert spoken and "closes at the work zone ahead" in spoken[0]
    finally:
        app.shutdown()


def test_a_limit_cutting_zone_entry_speaks_immediately_inside_the_gap(world, monkeypatch):
    """The merge taper posts one number and the work zone right behind it
    enforces a lower one. _active_zone_at does not filter the taper out, so
    the taper's own colour line already closed the "zone" window by the time
    the truck reaches the barrels a few real seconds later under
    compression. _check_speed_limit stays silent for as long as any zone is
    active, so if this line waited for the window, the driver would never
    hear the 45 at all."""
    trip = _make_trip(world)
    clock = _install_fake_clock(trip, monkeypatch)

    taper = Zone(2.0, 3.0, 55.0, "construction merge")
    work = Zone(3.0, 5.0, 45.0, "construction")
    trip.zones = [taper, work]

    trip.position_mi = 2.0
    trip._events.clear()
    trip._check_zones()
    first = [e for e in trip._events if e.kind == TripEventKind.ZONE_ENTER]
    assert len(first) == 1
    assert trip._active_zone is taper

    # A few real seconds later under compression -- well inside
    # ZONE_GAP_REAL_S -- the truck reaches the work zone proper. The window
    # is genuinely still shut...
    clock.now += 3.0
    assert not trip._event_breather.ready("zone")

    # ...but the entry speaks anyway: the limit dropped (55 -> 45).
    trip.position_mi = 3.0
    trip._events.clear()
    trip._check_zones()
    urgent = [e for e in trip._events if e.kind == TripEventKind.ZONE_ENTER]
    assert len(urgent) == 1
    assert trip._speed_value(45.0) in urgent[0].message
    assert trip._speed_value(55.0) not in urgent[0].message
    assert trip._active_zone is work


def test_a_same_limit_zone_entry_self_supersedes_once_the_window_reopens(world, monkeypatch):
    """A gated cosmetic entry (same or higher limit -- nothing ticket-
    relevant) must not vanish for good. Once the window reopens, the
    CURRENT zone's own entry is spoken from the regular tick -- current
    state, not a stale catch-up for whatever was gated."""
    trip = _make_trip(world)
    clock = _install_fake_clock(trip, monkeypatch)

    zone1 = Zone(2.0, 4.0, 45.0, "construction")
    zone2 = Zone(10.0, 12.0, 45.0, "construction")  # same limit: never urgent
    trip.zones = [zone1, zone2]

    trip.position_mi = 2.0
    trip._events.clear()
    trip._check_zones()
    assert len([e for e in trip._events if e.kind == TripEventKind.ZONE_ENTER]) == 1
    assert trip._active_zone is zone1

    # 3 fake seconds later -- inside the gap, same limit, not urgent -- the
    # entry for zone2 is gated, not spoken.
    clock.now += 3.0
    trip.position_mi = 10.0
    trip._events.clear()
    trip._check_zones()
    assert [e for e in trip._events if e.kind == TripEventKind.ZONE_ENTER] == []
    assert trip._active_zone is zone2
    assert not trip._zone_entry_spoken

    # The window reopens with zone2 still current (nothing newer replaced
    # it): the very next tick speaks for it, from the regular _check_zones
    # path -- not a special catch-up queue.
    clock.now += ZONE_GAP_REAL_S
    trip._events.clear()
    trip._check_zones()
    superseded = [e for e in trip._events if e.kind == TripEventKind.ZONE_ENTER]
    assert len(superseded) == 1
    assert superseded[0].data.get("zone") is zone2
    assert trip._zone_entry_spoken
    assert trip._active_zone is zone2
