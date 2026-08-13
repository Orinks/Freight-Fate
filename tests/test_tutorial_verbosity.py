"""First-run guidance ignores verbosity until the walkthrough is done (R15).

Terse speech is a filter on running commentary, and first-run teaching is
not commentary. Terse mode used to silence the first-drive walkthrough
outright: a brand-new player who picked terse before their first drive --
exactly the player who hates chatty games -- was never told the status,
help, or hazard keys exist, and could not pull information they were never
told about. The gate is ``tutorial_done`` itself, not verbosity history:
the walkthrough speaks in full whatever the speech mode, and finishing it
then flipping terse on resurrects nothing.
"""

from __future__ import annotations

from types import SimpleNamespace

from freight_fate.settings import Settings
from freight_fate.states.driving_core import Tutorial


class _Ctx:
    def __init__(self, *, terse: bool) -> None:
        self.settings = Settings()
        self.settings.speech_verbosity = 0 if terse else 1
        self.settings.automatic_transmission = True
        self.profile = SimpleNamespace(tutorial_done=False)
        self.spoken: list[str] = []
        self.saved = 0

    def say(self, text: str, interrupt: bool = True, review: bool = True) -> None:
        self.spoken.append(str(text))

    def control_hint(self, action: str) -> str:
        return action.upper()

    def save_profile(self) -> None:
        self.saved += 1


def _walk_through(ctx: _Ctx) -> Tutorial:
    tutorial = Tutorial(ctx)
    tutorial.begin()
    tutorial.on_engine_started()
    tutorial.on_parking_brake_released()
    tutorial.update(1 / 60, SimpleNamespace(speed_mph=25.0, parking_brake=False))
    return tutorial


def test_a_terse_player_hears_the_whole_walkthrough() -> None:
    normal = _Ctx(terse=False)
    terse = _Ctx(terse=True)
    _walk_through(normal)
    _walk_through(terse)
    assert terse.spoken == normal.spoken
    assert len(terse.spoken) == 4


def test_the_walkthrough_still_teaches_the_pull_keys_in_terse() -> None:
    ctx = _Ctx(terse=True)
    _walk_through(ctx)
    keys_line = ctx.spoken[-1]
    # The lines every push-message retirement leans on: the player can pull
    # speed, status, and the full controls on demand -- but only if they
    # were told the keys exist.
    for hint in ("SPEED", "STATUS_MENU", "HELP", "EMERGENCY_BRAKE"):
        assert hint in keys_line
    assert "hazard warnings" in keys_line


def test_reminders_speak_in_terse_too() -> None:
    ctx = _Ctx(terse=True)
    tutorial = Tutorial(ctx)
    tutorial.begin()
    ctx.spoken.clear()

    tutorial.update(26.0, SimpleNamespace(speed_mph=0.0, parking_brake=True))

    assert ctx.spoken == ["Reminder: press ENGINE to start the engine."]


def test_finishing_the_walkthrough_persists_the_gate() -> None:
    ctx = _Ctx(terse=True)
    _walk_through(ctx)
    assert ctx.profile.tutorial_done is True
    assert ctx.saved == 1


def test_the_gate_is_tutorial_done_itself_not_verbosity_history() -> None:
    """A finished walkthrough plus a later flip to terse resurrects nothing,
    and a fresh terse career still gets the walkthrough: the driving state
    builds a Tutorial on tutorial_done alone, never on the speech mode."""
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.settings.speech_verbosity = 0
        app.ctx.profile = Profile(name="Vet", current_city="Buffalo")
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

        app.ctx.profile.tutorial_done = True
        veteran = DrivingState(app.ctx, job, route, phase="delivery")
        assert veteran.tutorial is None

        app.ctx.profile.tutorial_done = False
        first_timer = DrivingState(app.ctx, job, route, phase="delivery")
        assert first_timer.tutorial is not None
    finally:
        app.shutdown()
