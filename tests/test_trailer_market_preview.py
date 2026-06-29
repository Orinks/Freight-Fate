"""Trailer-fit and business preview text on the dispatch board."""

from freight_fate.models.business import (
    COMPANY_DRIVER,
    INDEPENDENT_AUTHORITY,
    LEASED_OWNER_OPERATOR,
)
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.states.city import JobBoardState


def _bulk_job() -> Job:
    return Job(
        CARGO_CATALOG["bulk"],
        20.0,
        "Chicago",
        "Chicago Bulk Terminal",
        "Indianapolis",
        180.0,
        1400.0,
        8.0,
        origin_type="mine_quarry",
        destination_location="Indianapolis Construction Yard",
        destination_type="construction_materials_yard",
    )


def _labels(app, profile: Profile) -> list[str]:
    app.ctx.profile = profile
    app.push_state(JobBoardState(app.ctx, [_bulk_job()]))
    return [item.text for item in app.state.items]


def test_company_driver_bulk_job_uses_carrier_trailer_support():
    from freight_fate.app import App

    app = App()
    try:
        profile = Profile(name="Company Driver", current_city="Chicago")
        profile.business_status = COMPANY_DRIVER
        labels = _labels(app, profile)

        row = labels[0]
        assert "Job 1 of 1" in row
        assert "Carrier trailer provided" in row
        assert "Estimated driver pay before advances" in row
        assert "Locked job" not in row
    finally:
        app.shutdown()


def test_owner_operator_hears_missing_trailer_gate_and_preview():
    from freight_fate.app import App

    app = App()
    try:
        profile = Profile(name="Leased Owner", current_city="Chicago")
        profile.business_status = LEASED_OWNER_OPERATOR
        profile.trailer_programs = ["dry_van"]
        labels = _labels(app, profile)

        row = labels[0]
        assert row.startswith("Locked job 1 of 1")
        assert "Needs Bulk trailer program" in row
        assert "Gross revenue" in row
        assert "Estimated take-home before advances" in row
        assert "business costs" in row
    finally:
        app.shutdown()


def test_own_authority_owned_trailer_row_shows_direct_market_fit():
    from freight_fate.app import App

    app = App()
    try:
        profile = Profile(name="Authority Driver", current_city="Chicago")
        profile.business_status = INDEPENDENT_AUTHORITY
        profile.trailer_programs = ["dry_van"]
        profile.owned_trailers = ["bulk"]
        labels = _labels(app, profile)

        row = labels[0]
        assert row.startswith("Job 1 of 1")
        assert "Owned trailer: Bulk" in row
        assert "Direct gross" in row
        assert "owned-trailer reserve" in row
        assert "Estimated take-home before advances" in row
        assert "Locked job" not in row
    finally:
        app.shutdown()
