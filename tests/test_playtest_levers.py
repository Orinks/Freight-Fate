"""Playtest levers: env-forced relocation, clock moves, and dispatch loads.

The levers exist for the alpha test book. Every test drives the real world
data so a lever proven here works for a tester at the keyboard.
"""

import pytest

from freight_fate import playtest_levers
from freight_fate.models.jobs import JobBoard
from freight_fate.models.profile import Profile
from freight_fate.playtest_levers import apply_continue_levers
from freight_fate.sim.timezones import city_zone, to_local


class _Ctx:
    """The slice of GameContext the levers touch."""

    def __init__(self, world, profile):
        self.world = world
        self.profile = profile
        self.spoken: list[str] = []
        self.saves = 0
        self.playtest_sandbox = False

    def say(self, text: str, interrupt: bool = True) -> None:
        self.spoken.append(text)

    def save_profile(self) -> None:
        self.saves += 1


@pytest.fixture
def parked_ctx(world):
    return _Ctx(world, Profile(name="Lever Test", current_city="denver_co_us"))


def test_no_levers_is_a_no_op(world, monkeypatch, parked_ctx):
    monkeypatch.delenv(playtest_levers.CITY_ENV, raising=False)
    monkeypatch.delenv(playtest_levers.CLOCK_ENV, raising=False)
    monkeypatch.delenv(playtest_levers.DEST_ENV, raising=False)

    notes = apply_continue_levers(parked_ctx)

    assert notes == []
    assert parked_ctx.saves == 0
    assert parked_ctx.playtest_sandbox is False


def test_clock_env_parsing(monkeypatch):
    for raw, expected in [("21", 21.0), ("21.5", 21.5), ("0", 0.0)]:
        monkeypatch.setenv(playtest_levers.CLOCK_ENV, raw)
        assert playtest_levers.forced_clock_hour() == expected
    for raw in ("banana", "24", "-1", ""):
        monkeypatch.setenv(playtest_levers.CLOCK_ENV, raw)
        assert playtest_levers.forced_clock_hour() is None


def test_force_city_relocates_into_a_sandbox_by_default(world, monkeypatch):
    """Owner design 2026-07-15: a lever run is temporary. The scenario plays
    in memory, nothing saves, and the real career resumes untouched."""
    ctx = _Ctx(world, Profile(name="Lever Test", current_city="Chicago"))
    ctx.profile.dispatch_board_cache = {"key": "stale"}
    monkeypatch.setenv(playtest_levers.CITY_ENV, "denver_co_us")
    monkeypatch.delenv(playtest_levers.PERSIST_ENV, raising=False)

    notes = apply_continue_levers(ctx)

    assert ctx.profile.current_city == "denver_co_us"
    assert ctx.profile.dispatch_board_cache is None
    assert ctx.playtest_sandbox is True
    assert ctx.saves == 0
    assert any("relocated to Denver" in note for note in notes)
    assert any("No miles driven, no money changed" in note for note in notes)
    assert any("sandbox" in note.lower() for note in notes)


def test_force_persist_makes_the_relocation_permanent(world, monkeypatch):
    ctx = _Ctx(world, Profile(name="Lever Test", current_city="Chicago"))
    monkeypatch.setenv(playtest_levers.CITY_ENV, "denver_co_us")
    monkeypatch.setenv(playtest_levers.PERSIST_ENV, "1")

    notes = apply_continue_levers(ctx)

    assert ctx.profile.current_city == "denver_co_us"
    assert ctx.playtest_sandbox is False
    assert ctx.saves == 1
    assert not any("sandbox" in note.lower() for note in notes)


def test_forced_dest_alone_still_sandboxes_a_parked_career(world, monkeypatch):
    ctx = _Ctx(world, Profile(name="Lever Test", current_city="denver_co_us"))
    monkeypatch.setenv(playtest_levers.DEST_ENV, "silverthorne_co_us")
    monkeypatch.delenv(playtest_levers.PERSIST_ENV, raising=False)

    notes = apply_continue_levers(ctx)

    assert ctx.playtest_sandbox is True
    assert ctx.saves == 0
    assert any("sandbox" in note.lower() for note in notes)


def test_save_profile_honors_the_playtest_sandbox():
    from types import SimpleNamespace

    from freight_fate.app import GameContext

    saved = []
    ctx = object.__new__(GameContext)
    ctx.profile = SimpleNamespace(save=lambda: saved.append(True))
    ctx.school_sandbox = False
    ctx.playtest_sandbox = True
    ctx.save_profile()
    assert saved == []

    ctx.playtest_sandbox = False
    ctx.save_profile()
    assert saved == [True]


def test_force_city_refuses_mid_load(world, monkeypatch):
    ctx = _Ctx(world, Profile(name="Lever Test", current_city="Chicago"))
    ctx.profile.active_trip = {"kind": "pickup"}
    monkeypatch.setenv(playtest_levers.CITY_ENV, "denver_co_us")

    notes = apply_continue_levers(ctx)

    assert ctx.profile.current_city == "Chicago"
    assert ctx.saves == 0
    assert any("load in progress" in note for note in notes)


def test_force_city_forgives_tester_spellings(world, monkeypatch):
    """Owner hit this live: PowerShell turns 'holbrook,az,us' into
    'holbrook az us', and commas are a natural way to type a slug anyway.
    Every reasonable spelling lands on the canonical key."""
    for spelling in ("holbrook,az,us", "holbrook az us", "Holbrook, AZ, US"):
        ctx = _Ctx(world, Profile(name="Lever Test", current_city="denver_co_us"))
        monkeypatch.setenv(playtest_levers.CITY_ENV, spelling)

        notes = apply_continue_levers(ctx)

        assert ctx.profile.current_city == "holbrook_az_us", spelling
        assert any("relocated to Holbrook" in note for note in notes), spelling


def test_force_city_unknown_city_stays_put(world, monkeypatch, parked_ctx):
    monkeypatch.setenv(playtest_levers.CITY_ENV, "atlantis")

    notes = apply_continue_levers(parked_ctx)

    assert parked_ctx.profile.current_city == "denver_co_us"
    assert any("no city called atlantis" in note for note in notes)


def test_force_city_already_there_speaks_only_the_sandbox_note(
    world, monkeypatch, parked_ctx
):
    monkeypatch.setenv(playtest_levers.CITY_ENV, "denver_co_us")
    monkeypatch.delenv(playtest_levers.PERSIST_ENV, raising=False)

    notes = apply_continue_levers(parked_ctx)

    # No relocation happened, but the lever is set, so the session is
    # still a sandbox and must say so.
    assert [n for n in notes if "sandbox" not in n.lower()] == []
    assert parked_ctx.playtest_sandbox is True
    assert parked_ctx.saves == 0


def test_force_clock_advances_to_local_hour(world, monkeypatch, parked_ctx):
    p = parked_ctx.profile
    p.fatigue = 55.0
    zone = city_zone(world.city(p.current_city))
    before_local = to_local(p.game_hours, zone) % 24.0
    before_hours = p.game_hours
    monkeypatch.setenv(playtest_levers.CLOCK_ENV, "21")

    notes = apply_continue_levers(parked_ctx)

    assert to_local(p.game_hours, zone) % 24.0 == pytest.approx(21.0)
    delta = p.game_hours - before_hours
    assert delta == pytest.approx((21.0 - before_local) % 24.0)
    assert delta > 0
    assert any("clock moved forward" in note for note in notes)
    # The clock only moves forward; a jump past a full break rests the driver.
    if delta >= 10.0:
        assert p.fatigue == 0.0
        assert any("full break" in note for note in notes)
    # The wait shows in the logbook as off duty, not as vanished time.
    segment = p.duty_log.segments[-1]
    assert segment.status == "off_duty"
    assert segment.start_hour == pytest.approx(before_hours)
    assert segment.end_hour == pytest.approx(p.game_hours)


def test_force_clock_already_at_hour_speaks_only_the_sandbox_note(
    world, monkeypatch, parked_ctx
):
    p = parked_ctx.profile
    zone = city_zone(world.city(p.current_city))
    local = to_local(p.game_hours, zone) % 24.0
    monkeypatch.setenv(playtest_levers.CLOCK_ENV, str(local))
    monkeypatch.delenv(playtest_levers.PERSIST_ENV, raising=False)

    notes = apply_continue_levers(parked_ctx)

    assert [n for n in notes if "sandbox" not in n.lower()] == []
    assert parked_ctx.saves == 0


def test_offer_to_builds_job_to_forced_destination(world):
    board = JobBoard(world, seed=7)

    job = board.offer_to("denver_co_us", "silverthorne_co_us", set())

    assert job is not None
    assert world.resolve_city_key(job.destination) == "silverthorne_co_us"
    assert job.distance_mi > 0
    assert job.pay > 0


def test_offer_to_unknown_destination_returns_none(world):
    board = JobBoard(world, seed=7)

    assert board.offer_to("denver_co_us", "atlantis", set()) is None


def test_forced_board_job_lands_on_the_board(world, monkeypatch):
    from freight_fate.states.city import _add_forced_board_job

    monkeypatch.setenv(playtest_levers.DEST_ENV, "silverthorne_co_us")
    ctx = _Ctx(world, Profile(name="Lever Test", current_city="denver_co_us"))
    board = JobBoard(world, seed=7)
    jobs = board.offers("denver_co_us", set(), count=3, level=1)

    note = _add_forced_board_job(ctx, board, jobs)

    dests = {world.resolve_city_key(job.destination) for job in jobs}
    assert "silverthorne_co_us" in dests
    assert "Playtest lever" in note


def test_forced_board_job_skips_when_already_offered(world, monkeypatch):
    from freight_fate.states.city import _add_forced_board_job

    monkeypatch.setenv(playtest_levers.DEST_ENV, "silverthorne_co_us")
    ctx = _Ctx(world, Profile(name="Lever Test", current_city="denver_co_us"))
    board = JobBoard(world, seed=7)
    jobs = board.offers("denver_co_us", set(), count=3, level=1)
    forced = board.offer_to("denver_co_us", "silverthorne_co_us", set())
    jobs.append(forced)
    count_before = len(jobs)

    note = _add_forced_board_job(ctx, board, jobs)

    assert len(jobs) == count_before
    assert "already offers" in note


def test_assigned_dispatch_hands_out_the_forced_load_first(world, monkeypatch):
    from freight_fate.states.city import JobBoardState

    monkeypatch.setenv(playtest_levers.DEST_ENV, "silverthorne_co_us")
    profile = Profile(name="Lever Test", current_city="denver_co_us")
    ctx = _Ctx(world, profile)
    board = JobBoard(world, seed=7)
    jobs = board.offers("denver_co_us", set(), count=4, level=1)
    forced = board.offer_to("denver_co_us", "silverthorne_co_us", set())
    assert forced is not None
    jobs.append(forced)
    jobs.sort(key=lambda j: j.distance_mi)

    state = JobBoardState(ctx, jobs)

    assert state.assigned_mode
    first = jobs[state._assigned_queue[0]]
    assert world.resolve_city_key(first.destination) == "silverthorne_co_us"
