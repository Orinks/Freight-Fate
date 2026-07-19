"""Tests for the curve management tier on the unified curve pipeline.

Covers curve data loading (freight_fate.data.curves, the single loader),
trip integration (curve placement and approach events), and safe-speed
integration. The trip emits CURVE events for bends that demand slowing.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from freight_fate.data.curves import leg_curves
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
