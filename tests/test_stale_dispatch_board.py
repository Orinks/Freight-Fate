"""A cached dispatch board can outlive the world it was built from.

The board is stored in the save, so a player who updates the game mid-career
can open a board whose pickup facility no longer exists. Accepting the job is
the only step that resolves that facility, so before this was handled, Enter
on such a dispatch took the whole game down with a KeyError.
"""

from __future__ import annotations

from speech_capture import speech_stub

CITY = "Buffalo"
GONE = "Buffalo Gone-Away Cold Storage"
ENDORSEMENTS = {"refrigerated", "heavy_haul", "high_value"}


def _senior_profile(app):
    from freight_fate.models.career import LEVEL_XP
    from freight_fate.models.profile import Profile

    profile = Profile(name="Stale board", current_city=CITY)
    profile.career.xp = LEVEL_XP[-1]
    app.ctx.profile = profile
    return profile


def _offers(app, profile):
    from freight_fate.models.jobs import JobBoard

    return JobBoard(app.ctx.world, seed=7).offers(
        CITY, ENDORSEMENTS, level=30, market=profile.market
    )


def _cache_a_board_with_a_retired_pickup(app, city_state, profile):
    """Cache a board into the save, then retire one job's pickup facility."""
    from freight_fate.models.jobs import job_payload

    payloads = [job_payload(job) for job in _offers(app, profile)]
    payloads[0]["origin_location"] = GONE
    payloads[0]["origin_facility_id"] = "buffalo-gone-away-cold-storage"
    profile.dispatch_board_cache = {"key": city_state._dispatch_cache_key(), "jobs": payloads}
    return payloads


def test_a_board_naming_a_retired_pickup_is_rebuilt_from_the_current_world():
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState, board_offer_count

    app = App()
    try:
        profile = _senior_profile(app)
        city_state = CityMenuState(app.ctx)
        _cache_a_board_with_a_retired_pickup(app, city_state, profile)

        city_state._job_board()

        board = app.state
        offered = [job.origin_location for job in board.jobs]
        assert GONE not in offered
        # Rebuilt, not merely filtered: the player still gets a full board.
        assert len(board.jobs) == board_offer_count(profile.career.level)
        assert profile.dispatch_board_cache is not None
        assert all(
            payload["origin_location"] != GONE for payload in profile.dispatch_board_cache["jobs"]
        )
    finally:
        app.shutdown()


def test_accepting_a_retired_pickup_says_so_instead_of_crashing(monkeypatch):
    """The board rebuild above is the fix; this is the net under it.

    A JobDetailState opened before the board was rebuilt still holds the old
    job, so the accept path has to refuse on its own rather than raise.
    """
    from freight_fate.app import App
    from freight_fate.models.jobs import job_from_payload
    from freight_fate.states.city import CityMenuState, JobBoardState

    app = App()
    try:
        profile = _senior_profile(app)
        city_state = CityMenuState(app.ctx)
        payloads = _cache_a_board_with_a_retired_pickup(app, city_state, profile)
        stale_job = job_from_payload(payloads[0])

        board = JobBoardState(app.ctx, [stale_job])
        app.push_state(board, should_enter=False)
        spoken: list[str] = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

        board._accept(stale_job)

        said = " ".join(spoken).lower()
        assert "no longer on the network" in said
        assert "refresh" in said
        # Plain player language: nothing about facilities, keys, or saves.
        for jargon in ("keyerror", "facility_location", "world data", "cache"):
            assert jargon not in said
        # The trip must not have started, the dead offer is off the board,
        # and the stale cache is forgotten so the next build is a current one.
        assert profile.active_trip is None
        assert stale_job not in board.jobs
        assert profile.dispatch_board_cache is None
    finally:
        app.shutdown()
