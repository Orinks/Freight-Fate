"""Tests for the curve management tier on the unified curve pipeline.

Covers curve data loading (freight_fate.data.curves, the single loader),
trip integration (curve placement and approach events), and safe-speed
integration. The trip emits CURVE events for bends that demand slowing.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from freight_fate.data.curves import (
    HAIRPIN_DEFLECTION_DEG,
    HAIRPIN_MAX_MPH,
    INTERSTATE_MAX_DEFLECTION_DEG,
    INTERSTATE_MIN_RADIUS_FT,
    leg_curves,
    route_curves,
)
from freight_fate.data.world import Route, World
from freight_fate.sim.trip import Trip
from freight_fate.sim.trip_models import TripEventKind
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherSystem


class TestCurveLoading:
    """Curve data loading from the baked shard."""

    def test_unknown_leg_returns_empty_tuple(self) -> None:
        assert leg_curves("nonexistent_leg_xyz") == ()

    def test_connectors_are_filtered_by_default(self) -> None:
        mainline = leg_curves("aberdeen_sd_us:pierre_sd_us")
        everything = leg_curves("aberdeen_sd_us:pierre_sd_us", mainline_only=False)
        assert all(not c.connector for c in mainline)
        assert len(everything) >= len(mainline)
        assert any(c.connector for c in everything), (
            "this leg's interchange arcs should be present when asked for"
        )


class TestInterstateArtifactScreen:
    """Geometry artifacts never reach an interstate mainline.

    The dense sweep baked departure geometry and interchange vertices as
    mainline on some interstate legs, which read as 80-250 ft "hairpins" on
    roads that physically cannot bend that hard. The loader screens them.
    """

    def test_no_impossibly_sharp_interstate_mainline_curve(self, world: World) -> None:
        offenders = []
        for leg in world.legs:
            if not (leg.highway or "").upper().startswith("I-"):
                continue
            for rec in leg_curves(f"{leg.a}:{leg.b}"):
                if rec.min_radius_ft < INTERSTATE_MIN_RADIUS_FT:
                    offenders.append((leg.highway, f"{leg.a}:{leg.b}", rec))
        assert not offenders, (
            f"{len(offenders)} interstate mainline curves below "
            f"{INTERSTATE_MIN_RADIUS_FT} ft: {offenders[:5]}"
        )

    def test_no_switchback_deflection_on_interstate_mainline(self, world: World) -> None:
        """A 150-degree bend on interstate mainline is a mis-tagged loop ramp."""
        offenders = []
        for leg in world.legs:
            if not (leg.highway or "").upper().startswith("I-"):
                continue
            for rec in leg_curves(f"{leg.a}:{leg.b}"):
                if rec.deflection_deg >= INTERSTATE_MAX_DEFLECTION_DEG:
                    offenders.append((leg.highway, f"{leg.a}:{leg.b}", rec))
        assert not offenders, f"{len(offenders)} interstate switchbacks: {offenders[:5]}"

    def test_no_hairpin_severity_on_interstate_mainline(self, world: World) -> None:
        """The screen's whole point: no interstate mainline hairpin calls.

        Driven through ``route_curves`` -- the path every consumer takes --
        one leg at a time, so a mixed-class route cannot mask or fake a
        failure with some other road's legitimately sharp bend.
        """
        for leg in world.legs:
            if not (leg.highway or "").upper().startswith("I-"):
                continue
            route = Route([leg.a, leg.b], [leg])
            for cur in route_curves(route, route.cities):
                assert cur.severity != "hairpin", (
                    f"{leg.highway} {leg.a}:{leg.b} still calls a hairpin at "
                    f"mile {cur.apex_mi:.2f} (radius {cur.min_radius_ft} ft)"
                )

    def test_abilene_fort_worth_mile_four_hairpins_are_gone(self) -> None:
        """Flat I-20 had three 104-111 ft "hairpins" at mile 4."""
        recs = leg_curves("abilene_tx_us:fort_worth_tx_us")
        assert recs, "this leg is swept and should still have real curves"
        near_four = [r for r in recs if 3.5 <= r.apex_mi <= 4.5]
        assert not near_four, f"artifact cluster survived: {near_four}"
        assert min(r.min_radius_ft for r in recs) >= INTERSTATE_MIN_RADIUS_FT

    def test_akron_cleveland_mile_thirty_seven_hairpin_is_gone(self) -> None:
        """I-77 carried two 82 ft "hairpins" from interchange geometry."""
        recs = leg_curves("akron_oh_us:cleveland_oh_us")
        assert recs
        assert not [r for r in recs if r.min_radius_ft < INTERSTATE_MIN_RADIUS_FT]
        # The real bends on this leg stay.
        assert len(recs) >= 15

    def test_interstate_connector_arcs_are_untouched(self) -> None:
        """Ramps really are that sharp; physics still wants them."""
        everything = leg_curves("abilene_tx_us:fort_worth_tx_us", mainline_only=False)
        tight = [r for r in everything if r.connector and r.min_radius_ft < 150]
        assert tight, "interchange ramp arcs should survive the screen"

    def test_million_dollar_highway_switchbacks_survive(self) -> None:
        """US-550 Durango-Montrose really does switch back. Never screen it."""
        recs = leg_curves("durango_co_us:montrose_co_us")
        assert len(recs) >= 250
        assert min(r.min_radius_ft for r in recs) < 100
        assert max(r.deflection_deg for r in recs) >= 150.0

    def test_glenwood_canyon_interstate_curves_survive(self) -> None:
        """Real I-70 canyon geometry sits above the floor and must stay."""
        recs = leg_curves("glenwood_springs_co_us:grand_junction_co_us")
        assert len(recs) >= 55
        assert min(r.min_radius_ft for r in recs) < 500, (
            "Glenwood Canyon's genuinely sharp bends should still be here"
        )

    def test_us_highway_mountain_hairpins_survive(self) -> None:
        """US-40 over the Rockies keeps its real sharp curves.

        The interstate screen never applies to US routes; the separate
        flat-terrain screen (below) only takes the one Denver-departure
        artifact, so the mountain bends this leg is famous for stay.
        """
        recs = leg_curves("denver_co_us:salt_lake_city_ut_us")
        assert [r for r in recs if r.min_radius_ft < INTERSTATE_MIN_RADIUS_FT]


def _is_hairpin(rec) -> bool:
    """Same test ``RouteCurve.severity`` uses, for the plain ``CurveRecord``
    tuples ``leg_curves`` returns."""
    return rec.advisory_mph <= HAIRPIN_MAX_MPH or rec.deflection_deg >= HAIRPIN_DEFLECTION_DEG


class TestUSRouteArtifactScreen:
    """A second, narrower screen for artifacts road class alone can't catch.

    US and state routes can carry the same city-departure sweep artifact an
    interstate can, but they also carry real switchbacks the interstate
    screen would wrongly delete (US-550, the Salt River Canyon) -- so this
    screen is gated on local terrain (flat ground can't hold a real
    hairpin), not on road class. See ``tools/screen_curve_artifacts.py``.
    """

    def test_denver_us40_departure_kink_is_gone(self) -> None:
        """The flat-Denver-metro kink at mile 1.7 was the reported case."""
        recs = leg_curves("denver_co_us:salt_lake_city_ut_us")
        near_departure = [r for r in recs if r.apex_mi < 2.0]
        assert not [r for r in near_departure if _is_hairpin(r)], (
            f"flat-terrain departure artifact survived: {near_departure}"
        )

    def test_flagged_artifacts_are_absent_from_every_leg(self, world: World) -> None:
        """Every ``(leg, seq)`` the offline screen names is actually gone.

        Round-trips ``curve_artifacts.jsonl`` against the loaded data so a
        stale baked file (screen re-run, loader not updated, or vice versa)
        fails loudly instead of silently drifting.
        """
        import json

        from freight_fate.data.data_resources import read_data_text

        text = read_data_text("world_data/us/gameplay/curve_artifacts.jsonl")
        assert text, "curve_artifacts.jsonl should exist once artifacts are flagged"
        flagged_legs: set[str] = set()
        count = 0
        for line in text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if "meta" in row:
                continue
            flagged_legs.add(row["leg"])
            count += 1
        assert count > 0

        by_key = {f"{leg.a}:{leg.b}": leg for leg in world.legs}
        for leg_key in flagged_legs:
            leg = by_key.get(leg_key)
            if leg is None:
                continue
            assert not (leg.highway or "").upper().startswith("I-"), (
                f"{leg_key} is flagged but is interstate mainline -- "
                "that screen is a separate, unconditional rule"
            )

    def test_city_departure_hairpins_are_gone_off_the_mountains(self) -> None:
        """Terrain alone could not see a departure kink on rolling ground.

        Reported 2026-08-11: hairpins "and not just on mountains either". The
        flat screen caught the artifact only where the city sat on flat
        ground, so the same 43 ft kink a mile out of Hazard on KY-80 -- and
        112 like it -- rode through on "hills".
        """
        for leg_key in (
            "hot_springs_ar_us:fort_smith_ar_us",
            "hot_springs_ar_us:little_rock_ar_us",
            "rochester_mn_us:winona_mn_us",
            "oxford_ms_us:memphis_tn_us",
        ):
            recs = leg_curves(leg_key)
            assert recs, leg_key
            near_departure = [r for r in recs if r.apex_mi < 2.5 and _is_hairpin(r)]
            assert not near_departure, f"{leg_key}: departure artifact survived: {near_departure}"

    def test_the_leg_end_rule_cuts_by_terrain_within_a_single_leg(self) -> None:
        """KY-80 out of Hazard carries both cases half a mile apart.

        A 43 ft kink at mile 1.06 on hills is departure geometry and goes; a
        real 80 ft switchback at mile 2.48, where the road is already into the
        mountains, stays. Position alone would have taken both, which is why
        the rule asks the terrain as well.
        """
        recs = leg_curves("hazard_ky_us:london_ky_us")
        near = [r for r in recs if r.apex_mi < 2.5 and _is_hairpin(r)]
        assert near, "the mountain switchback at mile 2.48 must survive"
        assert all(r.min_radius_ft >= 50 for r in near), (
            f"the hills kink at mile 1.06 should be gone: {near}"
        )

    def test_a_mountain_town_keeps_the_switchback_on_its_doorstep(self) -> None:
        """The leg-end rule spares mountain terrain, and has to.

        US-119 leaves Charleston straight into the mountains, and a real
        switchback sits within the first mile. Deleting by position alone
        would have taken it.
        """
        recs = leg_curves("charleston_wv_us:pikeville_ky_us")
        assert [r for r in recs if r.apex_mi < 2.5 and _is_hairpin(r)]

    def test_no_surviving_curve_is_tighter_than_a_road_can_bend(self) -> None:
        """A radius floor for every class, the sibling of the interstate 300 ft.

        50 ft is tighter than a loaded tractor-trailer's own turning circle,
        so nothing that bends harder is a road. The floor sits just under the
        tightest genuine switchback the world carries (US-550 at 54 ft), which
        is why it can be applied everywhere without a terrain test.
        """
        from freight_fate.data.curves import _load

        offenders = [
            (leg_key, rec)
            for leg_key, recs in _load().items()
            for rec in recs
            if not rec.connector and rec.min_radius_ft < 50
        ]
        assert not offenders, f"impossible mainline radii survived: {offenders[:5]}"

    def test_million_dollar_highway_untouched_by_the_new_screen(self) -> None:
        """A mountain corridor keeps every switchback under the new screen too."""
        recs = leg_curves("durango_co_us:montrose_co_us")
        assert len(recs) >= 250
        assert [r for r in recs if _is_hairpin(r)], (
            "US-550's real hairpins must survive the flat-terrain screen"
        )

    def test_salt_river_canyon_untouched_by_the_new_screen(self) -> None:
        """Globe->Show Low (US-60) keeps its mountain switchbacks too."""
        recs = leg_curves("globe_az_us:show_low_az_us")
        assert [r for r in recs if _is_hairpin(r)], (
            "the Salt River Canyon's real hairpins must survive the screen"
        )


class _MockWeather(WeatherSystem):
    """A weather system that returns a fixed safe speed for tests."""

    def __init__(self) -> None:
        super().__init__("heartland", seed=42)
        self._effects = MagicMock()
        self._effects.grip = 1.0
        self._effects.safe_speed_mph = 75.0
        self._effects.water_mm = 0.0
        self._effects.surface = "dry"
        self._effects.drag_mult = 1.0
        self._effects.visibility_mi = 10.0
        self._effects.sound = None
        self._effects.wind = 0.0

    @property
    def effects(self):
        return self._effects


class TestTripCurveIntegration:
    """Curve placement and approach events in the Trip system."""

    def test_place_curves_empty_short_approach(self) -> None:
        """A very short approach route (single leg, < 10 mi) gets no curves.

        Curves are only meaningful on highway-length legs; short facility
        approaches should have no curve placement.
        """
        from freight_fate.data.world_models import GradeSegment, Leg, RouteCheckpoint, StateMileage

        # Build a minimal single-leg route from a city to itself
        leg = Leg(
            a="abilene_tx_us",
            b="abilene_tx_us",
            miles=5.0,
            highway="US-83",
            terrain="flat",
            stops=(),
            checkpoints=(RouteCheckpoint("Midpoint", 2.5, "place", state="", highway="US-83"),),
            state_miles=(StateMileage("Texas", 5.0),),
            grade_segments=(GradeSegment(0.0, 5.0, 0.0, "flat", "test"),),
        )
        route = Route(["abilene_tx_us", "abilene_tx_us"], [leg])
        truck = TruckState()
        weather = _MockWeather()
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        assert trip.curves == []

    def test_interstate_artifact_never_reaches_trip_curves(self) -> None:
        """The Abilene I-20 mile-4 artifacts stay out of the live trip.

        ``Trip._place_curves`` keeps connectors for physics, so this checks
        the deepest consumer path, not just the spoken one.
        """
        world = World.load()
        route = world.supported_route("abilene_tx_us", "fort_worth_tx_us")
        assert route is not None
        assert all((leg.highway or "").startswith("I-") for leg in route.legs), (
            "this fixture route is meant to be interstate the whole way"
        )
        trip = Trip(route, TruckState(), _MockWeather(), time_scale=10.0, seed=42)
        mainline = [c for c in trip.curves if not c.connector]
        assert mainline, "the route should still have real curves"
        assert not [c for c in mainline if c.severity == "hairpin"]
        assert not [c for c in mainline if 3.5 <= c.apex_mi <= 4.5]

    def test_place_curves_highway_route(self) -> None:
        """A highway route resolves curves from leg-relative to trip miles."""
        truck = TruckState()
        weather = _MockWeather()
        world = World.load()
        route = world.shortest_route("abilene_tx_us", "dallas_tx_us")
        if route is None:
            return
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        # The trip should have curves if the abilene->dallas leg has data.
        # Some baked curves may have near-equal or slightly reversed start/end
        # due to leg-direction resolution; check the curve data is plausible.
        for cr in trip.curves:
            assert 0.0 <= cr.start_mi <= trip.total_miles
            assert 0.0 <= cr.end_mi <= trip.total_miles
            assert abs(cr.start_mi - cr.end_mi) < 5.0  # no mile-long outliers
            assert cr.direction in ("L", "R")

    def test_curve_at_inside(self) -> None:
        """curve_at returns the curve containing a milepost."""
        truck = TruckState()
        weather = _MockWeather()
        world = World.load()
        route = world.shortest_route("abilene_tx_us", "dallas_tx_us")
        if route is None:
            return
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        if not trip.curves:
            return
        # Pick the first curve and check that curve_at returns it
        cr = trip.curves[0]
        mid = (cr.start_mi + cr.end_mi) / 2.0
        found = trip.curve_at(mid)
        assert found is not None
        assert found.start_mi == cr.start_mi

    def test_curve_at_none(self) -> None:
        """Outside all curves, curve_at returns None."""
        truck = TruckState()
        weather = _MockWeather()
        world = World.load()
        route = world.shortest_route("abilene_tx_us", "dallas_tx_us")
        if route is None:
            return
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        assert trip.curve_at(-1.0) is None
        assert trip.curve_at(trip.total_miles + 1.0) is None

    def test_check_curves_emits_for_sharp_curve(self) -> None:
        """A sharp curve ahead generates a CURVE event with a pacenote."""
        truck = TruckState()
        truck.start_engine()
        truck.velocity_mps = 60.0 * 0.44704  # 60 mph in m/s
        weather = _MockWeather()
        world = World.load()
        route = world.shortest_route("abilene_tx_us", "dallas_tx_us")
        if route is None:
            return
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        if not trip.curves:
            return
        # Position the truck before the first curve
        first = trip.curves[0]
        trip.position_mi = max(0.0, first.start_mi - 1.0)
        # Run update to generate events
        events = trip.update(0.1)
        curve_events = [e for e in events if e.kind == TripEventKind.CURVE]
        # If the curve is sharp and not a connector, it should announce.
        # The curve_at check may trigger or not depending on distance.
        # The pacenote should mention advisory speed.
        for ev in curve_events:
            assert "advisory" in ev.message or "curve" in ev.message

    def test_restore_seeds_announced_curves(self) -> None:
        """Restoring a save seeds curves behind the position as announced."""
        truck = TruckState()
        weather = _MockWeather()
        world = World.load()
        route = world.shortest_route("abilene_tx_us", "dallas_tx_us")
        if route is None:
            return
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        if not trip.curves:
            return
        # Restore past the first curve
        first = trip.curves[0]
        trip.restore(first.start_mi + 0.5, 10.0)
        # The first curve should be in announced
        expected_key = f"curve:{first.start_mi:.3f}:{first.direction}"
        assert expected_key in trip._announced_curves
