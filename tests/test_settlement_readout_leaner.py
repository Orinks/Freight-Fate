"""R10: the settlement readout drops rows that report the unremarkable default.

The reviewable settlement list (``summary_lines``) used to carry rows that
said nothing happened -- "No new damage recorded", "Carrier charges are not
deducted from driver pay", a full fuel tank, zero truck damage, "No new
career messages". A blind player walks this list one row at a time, so each
empty row is a keypress spent on nothing. These pins hold the leaner list:
the rows appear only when they carry information.
"""

from freight_fate.models.business import COMPANY_DRIVER


def _job(
    *,
    destination_type="dry_warehouse",
    pay=2500.0,
    deadline=12.0,
    distance=78.0,
):
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    return Job(
        CARGO_CATALOG["electronics"],
        18.0,
        "New York",
        "New York pickup",
        "Philadelphia",
        distance,
        pay,
        deadline,
        origin_type="air_cargo",
        destination_location="Philadelphia receiver",
        destination_type=destination_type,
    )


def _settle(app, job, route_cities, *, damage=0.0, fuel_fraction=1.0):
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ArrivalState, DrivingState

    app.ctx.profile = Profile(name="Readout Audit", current_city=job.origin)
    app.ctx.profile.money = 1000.0
    app.ctx.profile.business_status = COMPANY_DRIVER
    route = app.ctx.world.route_from_cities(route_cities)
    driving = DrivingState(app.ctx, job, route, phase="delivery")
    if damage:
        driving.truck.damage_pct += damage
    driving.truck.fuel_gal = driving.truck.specs.fuel_tank_gal * fuel_fraction
    driving.trip.position_mi = driving.trip.total_miles
    driving.trip.update(0.0)
    app.ctx.push_state(ArrivalState(app.ctx, driving))
    return app.state.summary_lines


def test_clean_run_drops_the_zero_information_rows():
    from freight_fate.app import App

    app = App()
    try:
        lines = _settle(app, _job(), ["New York", "Philadelphia"], damage=0.0, fuel_fraction=1.0)
        joined = " ".join(lines)
        assert "No new damage recorded" not in joined
        assert "Carrier charges are not deducted from driver pay" not in joined
        assert "Fuel remaining" not in joined
        assert "Truck damage now" not in joined
        assert "No new career messages" not in joined
    finally:
        app.shutdown()


def test_damage_and_low_fuel_still_speak_when_they_matter():
    from freight_fate.app import App

    app = App()
    try:
        lines = _settle(app, _job(), ["New York", "Philadelphia"], damage=12.0, fuel_fraction=0.1)
        joined = " ".join(lines)
        assert "Truck damage added on this run" in joined
        assert "Fuel remaining" in joined
        assert "Truck damage now" in joined
    finally:
        app.shutdown()
