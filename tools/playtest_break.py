"""Adversarial breaker battery: drive the sim in unreasonable ways, on purpose.

Every scenario here does something no sensible driver would do -- reverse down
the interstate, slam reverse at highway speed, coast a mountain in neutral,
dynamite the parking brake at 60, blow the new facility gate with assists
fighting each other, motel-rest through a deadline -- and then CHECKS the
invariants programmatically: does physics stay sane, does money/XP/HOS/rep
stay honest, and does the spoken text still tell a blind player the truth.
Run it after any feature lands to see what newly breaks.

Usage::

    uv run python tools/playtest_break.py             # run the whole battery
    uv run python tools/playtest_break.py --list      # name + one-line summary
    uv run python tools/playtest_break.py --scenario slam_reverse_at_speed
    uv run python tools/playtest_break.py --transcript  # dump spoken lines too

Scenarios are deterministic (fixed trip seed, patched weather, no random
hazards or patrols unless the scenario is about them) and self-contained:
each builds its own App + DrivingState the way the tests do, drives real
``DrivingState.update`` frames, and returns CLEAN or ODD with a one-line note.
ODD means "a discrepancy a human should look at", not necessarily a bug --
the point is that the battery notices when the answer CHANGES.

Everything runs headless and isolated: dummy SDL drivers, no speech, and a
throwaway FREIGHT_FATE_DATA_DIR so the operator's real settings, saves, and
keyring are never touched.

The scenarios themselves live in ``tools/playtest_break_scenarios/``, split
by system family (driving physics, assists, resources, career/economy,
dispatch/save-load, radio/weather, settings) to keep each file well under the
project's practical-file-size guideline. This module holds the shared rig,
the registry, and the CLI; scenario modules register into it by decorating
their functions with ``@scenario(name, description)`` from here.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path

# Run as ``python tools/playtest_break.py``, this module executes as
# ``__main__``. The scenario modules register into it with
# ``from playtest_break import ...``, which -- without this alias -- would
# import a SECOND, freshly re-executed copy of this file under the name
# ``playtest_break``: its own empty SCENARIOS dict would collect every
# registration while the running ``__main__`` copy's dict (the one ``main()``
# below reads) stayed empty. Aliasing the name in sys.modules first makes
# both names point at the one module object that is actually running.
sys.modules["playtest_break"] = sys.modules[__name__]

# Headless + isolated BEFORE anything imports pygame or freight_fate.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["FREIGHT_FATE_NO_SPEECH"] = "1"
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parents[1]
# The reusable menu-walking harness lives beside the tests (same trick as
# tools/playtest.py); several scenarios drive it directly for full menu-flow
# coverage (settlement, dispatch board, career stages).
sys.path.insert(0, str(ROOT / "tests"))


def _fresh_data_dir() -> None:
    """Point the game at a brand-new data dir for the next App/harness.

    The game saves settings mid-drive (radio sync, state exits), so a shared
    dir would leak one scenario's settings tweaks into the next scenario's
    App(). Every scenario must start from stock settings or its verdict
    depends on battery order.
    """
    os.environ["FREIGHT_FATE_DATA_DIR"] = tempfile.mkdtemp(prefix="ff-breaker-")


_fresh_data_dir()


class _Shim:
    """Minimal stand-in for pytest's monkeypatch (harness only uses setattr)."""

    def setattr(self, obj: object, name: str, value: object) -> None:
        setattr(obj, name, value)


MPH_PER_MPS = 2.23694
DT = 1 / 30.0  # coarse-but-stable frame step; halves the battery's wall time


@dataclass
class Outcome:
    name: str
    verdict: str  # CLEAN | ODD | ERROR
    note: str
    findings: list[str] = field(default_factory=list)
    transcript: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    run: object  # callable() -> Outcome


SCENARIOS: dict[str, Scenario] = {}


def scenario(name: str, description: str):
    """Decorator: register ``fn`` (a zero-arg ``() -> Outcome`` callable) by name."""

    def wrap(fn):
        SCENARIOS[name] = Scenario(name, description, fn)
        return fn

    return wrap


class _HeldKeys:
    """Stand-in for pygame.key.get_pressed(): membership in a held-key set."""

    def __init__(self, held: set[int]) -> None:
        self._held = held

    def __getitem__(self, key: int) -> bool:
        return key in self._held


class Rig:
    """One disposable App + DrivingState wired for deterministic abuse.

    Mirrors the test idiom (tests/test_engine_brake_zones.py): a real App, a
    fresh profile, a supported route, and direct ``DrivingState.update``
    frames with speech captured and pygame's key state faked.
    """

    def __init__(
        self,
        *,
        automatic: bool = True,
        business: str | None = None,
        tons: float = 12.0,
        seed: int = 4242,
        keep_patrols: bool = False,
    ) -> None:
        _fresh_data_dir()

        import pygame

        from freight_fate.app import App
        from freight_fate.models.jobs import CARGO_CATALOG, Job
        from freight_fate.models.profile import Profile
        from freight_fate.sim.weather import WeatherKind
        from freight_fate.states.driving import DrivingState

        self.pygame = pygame
        self.WeatherKind = WeatherKind
        self.app = App()
        ctx = self.app.ctx
        self.ctx = ctx
        ctx.settings.automatic_transmission = automatic
        ctx.settings.radio_enabled = False  # no station machinery, no network
        # A career's current_city is a slug ("buffalo_ny_us"). The world
        # resolves the old display name for routing, so a label here drives
        # fine and only shows up later, when a save made from this harness is
        # refused by cloud backup as an unknown city.
        profile = Profile(name="Breaker", current_city=ctx.world.resolve_city_key("Buffalo"))
        if business:
            profile.business_status = business
        ctx.profile = profile
        route = ctx.world.supported_route("Buffalo", "Rochester")
        job = Job(
            CARGO_CATALOG["general"],
            tons,
            "Buffalo",
            "company yard",
            "Rochester",
            route.miles,
            1000.0,
            12.0,
            destination_location="Rochester freight market",
        )
        self.job = job
        self.route = route
        self.d = DrivingState(ctx, job, route, trip_seed=seed, phase="delivery")
        self.d.tutorial = None
        self.d._departure_checked = True  # stay on the highway trip, no street chain
        trip = self.d.trip
        trip._hazard_check_mi = 1e18
        trip._inspection_check_mi = 1e18
        trip._conditions_check_mi = 1e18
        trip.traffic_manager.vehicles = []
        trip.traffic_pressures = []
        if not keep_patrols:
            trip.patrols = []
        # Pin the weather: current stays whatever the scenario sets.
        self.d.weather.current = WeatherKind.CLEAR
        self.d.weather.update = lambda *a, **k: None

        self.transcript: list[str] = []
        # Stub the VOICE layer, not ctx.say/say_event themselves. The driving
        # verbosity ladder's gate and the event pacer's repeat/backlog
        # handling both live *inside* GameContext.say/say_event -- replacing
        # those methods (the old approach here) skipped both, so every
        # transcript this rig ever produced showed what the game would say
        # with no rung applied and no repeat suppression running, not what a
        # player actually hears. Stubbing ctx.speech.say/say_event instead
        # (the same seam tests/test_driving_speech_ladder.py already proves)
        # leaves the real gate and pacer in the call path; by the time a
        # line reaches here it has already been gated against the rig's own
        # settings.driving_speech and rendered to a plain string.
        ctx.speech.say = self._recorder("")
        ctx.speech.say_event = self._recorder("[event] ")

        self.held: set[int] = set()
        self._orig_get_pressed = pygame.key.get_pressed
        pygame.key.get_pressed = lambda: _HeldKeys(self.held)
        self._last_game_minutes = 0.0
        self.problems: list[str] = []
        self._problem_keys: set[str] = set()

    # -- speech ----------------------------------------------------------------

    def _recorder(self, prefix: str):
        # ``**kwargs`` absorbs anything the voice backend's own say/say_event
        # might grow beyond (text, interrupt). A SpokenMessage pair never
        # reaches this point: GameContext.say/say_event already render it to
        # a plain string against the player's real rung before calling down
        # to the voice layer, so there is nothing left to resolve here.
        def _speak(text: str, interrupt: bool = True, **kwargs: object) -> None:
            self.transcript.append(f"{prefix}{text}")

        return _speak

    def said(self, phrase: str) -> int:
        return sum(1 for line in self.transcript if phrase in line)

    def lines_with(self, phrase: str) -> list[str]:
        return [line for line in self.transcript if phrase in line]

    # -- driving ---------------------------------------------------------------

    def prepare(self, *, speed_mph: float = 0.0, gear: int | None = None) -> None:
        t = self.d.truck
        t.start_engine()
        t.set_air_ready(parking_brake=False)
        t.velocity_mps = speed_mph / MPH_PER_MPS
        if gear is not None:
            t.transmission.gear = gear
        elif t.transmission.automatic and speed_mph > 5:
            t.transmission.gear = 8

    def press(self, key: int) -> None:
        event = self.pygame.event.Event(self.pygame.KEYDOWN, key=key, unicode="", mod=0)
        self.d.handle_event(event)

    def step(self, frames: int, dt: float = DT, until=None) -> int:
        """Run full DrivingState.update frames; returns frames actually run."""
        for i in range(frames):
            self.d.update(dt)
            if i % 10 == 0:
                self.check_invariants()
            if until is not None and until():
                self.check_invariants()
                return i + 1
        self.check_invariants()
        return frames

    # -- invariants ------------------------------------------------------------

    def _problem(self, key: str, text: str) -> None:
        if key not in self._problem_keys:
            self._problem_keys.add(key)
            self.problems.append(text)

    def check_invariants(self) -> None:
        t = self.d.truck
        trip = self.d.trip
        p = self.ctx.profile
        if not math.isfinite(t.velocity_mps):
            self._problem("speed", f"speed went non-finite: {t.velocity_mps}")
        if not math.isfinite(p.money):
            self._problem("money", f"money went non-finite: {p.money}")
        if not (0.0 <= trip.position_mi <= trip.total_miles + 1e-6):
            self._problem(
                "pos", f"position {trip.position_mi:.2f} outside [0, {trip.total_miles:.2f}]"
            )
        if trip.game_minutes < self._last_game_minutes - 1e-9:
            self._problem("clock", "trip clock ran backward")
        self._last_game_minutes = trip.game_minutes
        for label, value in (
            ("damage", t.damage_pct),
            ("tire wear", t.tire_wear_pct),
            ("brake wear", t.brake_wear_pct),
            ("engine wear", t.engine_wear_pct),
        ):
            if not (0.0 <= value <= 100.0 + 1e-6):
                self._problem(label, f"{label} out of range: {value}")
        if not (0.0 <= t.fuel_gal <= t.specs.fuel_tank_gal + 1e-6):
            self._problem("fuel", f"fuel out of range: {t.fuel_gal}")
        if not (0.0 <= p.fatigue <= 100.0 + 1e-6):
            self._problem("fatigue", f"fatigue out of range: {p.fatigue}")

    def close(self) -> None:
        self.pygame.key.get_pressed = self._orig_get_pressed
        self.app.shutdown()


def _outcome(name: str, rig: Rig | None, findings: list[str], clean_note: str) -> Outcome:
    """Fold rig invariant problems into the findings and pick the verdict."""
    if rig is not None:
        findings = list(findings) + [f"invariant: {p}" for p in rig.problems]
    verdict = "ODD" if findings else "CLEAN"
    note = findings[0] if findings else clean_note
    return Outcome(
        name,
        verdict,
        note,
        findings,
        rig.transcript if rig is not None else [],
    )


def _fabricated_curve(start_mi: float, advisory: int = 25, direction: str = "R"):
    from freight_fate.data.curves import RouteCurve

    return RouteCurve(
        start_mi=start_mi,
        apex_mi=start_mi + 0.1,
        end_mi=start_mi + 0.22,
        direction=direction,
        advisory_mph=advisory,
        min_radius_ft=250,
        deflection_deg=130.0,
    )


# Registering the scenario modules populates SCENARIOS via the @scenario
# decorator above; this import must come after every name the scenario
# modules rely on (Rig, Outcome, scenario, _outcome, _fabricated_curve,
# MPH_PER_MPS, DT, _Shim, _fresh_data_dir) is already defined.
import playtest_break_scenarios  # noqa: E402,F401

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_scenario(name: str) -> Outcome:
    sc = SCENARIOS[name]
    try:
        return sc.run()
    except Exception:
        return Outcome(name, "ERROR", "scenario crashed", [traceback.format_exc()], [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adversarial breaker battery.")
    parser.add_argument("--list", action="store_true", help="List scenarios and exit.")
    parser.add_argument("--scenario", help="Run one scenario by name.")
    parser.add_argument(
        "--transcript",
        action="store_true",
        help="Print each scenario's captured spoken transcript as well.",
    )
    args = parser.parse_args(argv)

    if args.list:
        width = max(len(name) for name in SCENARIOS)
        for name, sc in SCENARIOS.items():
            print(f"{name:<{width}}  {sc.description}")
        return 0

    names = [args.scenario] if args.scenario else list(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        raise SystemExit(f"unknown scenario: {', '.join(unknown)} (try --list)")

    outcomes: list[Outcome] = []
    for name in names:
        print(f"running {name} ...", flush=True)
        outcome = run_scenario(name)
        outcomes.append(outcome)
        for finding in outcome.findings:
            lines = finding.splitlines()
            # A traceback's first line says nothing; its last line is the error.
            shown = lines[0] if len(lines) == 1 else f"{lines[0]} ... {lines[-1]}"
            print(f"  [{outcome.verdict}] {shown[:300]}")
        if args.transcript:
            for line in outcome.transcript:
                print(f"    | {line}")

    print()
    print("=" * 100)
    print(f"{'scenario':<34} {'verdict':<8} note")
    print("-" * 100)
    for outcome in outcomes:
        note = outcome.note.replace("\n", " ")
        print(f"{outcome.name:<34} {outcome.verdict:<8} {note[:120]}")
    print("=" * 100)
    odd = sum(1 for o in outcomes if o.verdict == "ODD")
    err = sum(1 for o in outcomes if o.verdict == "ERROR")
    print(f"{len(outcomes)} scenarios: {len(outcomes) - odd - err} clean, {odd} odd, {err} errors")
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
