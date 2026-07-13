"""Physics test bench: deterministic driving scenarios, plain-text reports.

Runs the real truck model (freight_fate.sim.vehicle) through scripted
scenarios -- mountain descents, runaway coasts, full-brake stop tests --
with a small scripted driver, and prints what happened as plain text:
peak brake temperature, fade onset, wear added, fuel burned, and the
moments the game would have cued the player (brake squeal, low air).

Everything is deterministic: no randomness, a fixed timestep, weather
taken straight from the fixed effects table. Two runs diff clean, so the
tuning loop is: change a constant in vehicle.py, re-run, read exactly
what moved. Output is screen-reader friendly -- one fact per line, no
tables, no decorative symbols.

Usage:
    uv run python tools/physics_bench.py                  # every scenario, summaries only
    uv run python tools/physics_bench.py --list           # scenario names and one-liners
    uv run python tools/physics_bench.py grade-no-jake    # one scenario, full event log
    uv run python tools/physics_bench.py --full           # every scenario, full event logs
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from freight_fate.sim.vehicle import TruckState  # noqa: E402
from freight_fate.sim.weather import EFFECTS, WeatherKind  # noqa: E402

DT = 0.1  # fixed physics timestep, seconds
TIMEOUT_S = 3600.0  # per-scenario wall guard; every scenario ends long before
BRAKES_WARM_C = 180.0  # spoken air-status threshold in driving_controls
SQUEAL_BRAKE = 0.4  # brake squeal cue thresholds in driving_updates
SQUEAL_MPH = 10.0
SQUEAL_COOLDOWN_S = 4.0
RUNAWAY_MPH = 80.0
MPH_PER_MPS = 2.23694
FT_PER_MI = 5280.0


@dataclass(frozen=True)
class Scenario:
    """One deterministic bench run.

    ``profile`` is a list of (miles, grade percent) segments driven in
    order; positive grade climbs, negative descends. When
    ``stop_from_mph`` is set the profile only supplies grade under the
    stop test: accelerate to that speed, then full service brake to a
    standstill and report the stopping distance.
    """

    name: str
    summary: str
    profile: tuple[tuple[float, float], ...]
    cargo_kg: float = 21_500.0  # reference full payload
    weather: WeatherKind = WeatherKind.CLEAR
    grip_override: float | None = None
    tire_wear: float = 0.0
    brake_wear: float = 0.0
    engine_wear: float = 0.0
    target_mph: float = 55.0
    jake: bool = False
    braking: str = "steady"  # steady, snub, or none
    stop_from_mph: float | None = None


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="flat-cruise",
        summary="Ten flat miles at highway speed; the fuel and heat baseline.",
        profile=((10.0, 0.0),),
        target_mph=62.0,
    ),
    Scenario(
        name="grade-jake-snub",
        summary="Six-mile 6 percent descent, loaded, jake on, snub braking.",
        profile=((1.0, 0.0), (6.0, -6.0), (2.0, 0.0)),
        target_mph=35.0,
        jake=True,
        braking="snub",
    ),
    Scenario(
        name="grade-no-jake",
        summary="The same descent with the jake off, dragging the service brakes.",
        profile=((1.0, 0.0), (6.0, -6.0), (2.0, 0.0)),
        target_mph=35.0,
        jake=False,
        braking="steady",
    ),
    Scenario(
        name="grade-jake-only",
        summary="The same descent on the jake alone; no service brakes at all.",
        profile=((1.0, 0.0), (6.0, -6.0), (2.0, 0.0)),
        target_mph=35.0,
        jake=True,
        braking="none",
    ),
    Scenario(
        name="grade-runaway",
        summary="Eight miles of 6 percent with no brakes of any kind; proof of the runaway.",
        profile=((1.0, 0.0), (8.0, -6.0), (1.0, 0.0)),
        target_mph=30.0,
        jake=False,
        braking="none",
    ),
    Scenario(
        name="grade-worn-brakes",
        summary="Descent on 60 percent worn shoes, jake off; fade arrives early.",
        profile=((1.0, 0.0), (6.0, -6.0), (2.0, 0.0)),
        brake_wear=60.0,
        target_mph=35.0,
        jake=False,
        braking="steady",
    ),
    Scenario(
        name="grade-overweight",
        summary="A 30 tonne payload down the 6 percent; over the brakes' rated gross.",
        profile=((1.0, 0.0), (6.0, -6.0), (2.0, 0.0)),
        cargo_kg=30_000.0,
        target_mph=35.0,
        jake=True,
        braking="snub",
    ),
    Scenario(
        name="snow-descent",
        summary="A 4 percent descent in snow, jake and snubs, creeping at 25.",
        profile=((1.0, 0.0), (5.0, -4.0), (2.0, 0.0)),
        weather=WeatherKind.SNOW,
        target_mph=25.0,
        jake=True,
        braking="snub",
    ),
    Scenario(
        name="stop-dry",
        summary="Full-brake stop from 60 on dry pavement; the braking baseline.",
        profile=((5.0, 0.0),),
        stop_from_mph=60.0,
    ),
    Scenario(
        name="stop-rain",
        summary="The same stop in rain.",
        profile=((5.0, 0.0),),
        weather=WeatherKind.RAIN,
        stop_from_mph=60.0,
    ),
    Scenario(
        name="stop-snow",
        summary="The same stop in snow.",
        profile=((5.0, 0.0),),
        weather=WeatherKind.SNOW,
        stop_from_mph=60.0,
    ),
    Scenario(
        name="stop-bald-rain",
        summary="The rain stop on 80 percent worn tires; bald rubber in the wet.",
        profile=((5.0, 0.0),),
        weather=WeatherKind.RAIN,
        tire_wear=80.0,
        stop_from_mph=60.0,
    ),
)


@dataclass
class RunResult:
    scenario: Scenario
    events: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)


def _clock(t_s: float) -> str:
    minutes, seconds = divmod(int(round(t_s)), 60)
    return f"{minutes}:{seconds:02d}"


def _grade_at(profile: tuple[tuple[float, float], ...], mile: float) -> float:
    edge = 0.0
    for miles, pct in profile:
        edge += miles
        if mile <= edge:
            return pct / 100.0
    return profile[-1][1] / 100.0


def _total_miles(profile: tuple[tuple[float, float], ...]) -> float:
    return sum(miles for miles, _ in profile)


def _build_truck(sc: Scenario) -> TruckState:
    truck = TruckState()
    truck.transmission.automatic = True
    truck.cargo_kg = sc.cargo_kg
    truck.tire_wear_pct = sc.tire_wear
    truck.brake_wear_pct = sc.brake_wear
    truck.engine_wear_pct = sc.engine_wear
    effects = EFFECTS[sc.weather]
    truck.grip = effects.grip if sc.grip_override is None else sc.grip_override
    truck.drag_mult = effects.drag_mult
    truck.set_air_ready(parking_brake=False)
    truck.start_engine()
    return truck


@dataclass
class _Driver:
    """Scripted driver: throttle P-control toward the target, one of three
    service-brake styles, and jake hysteresis. Deliberately simple -- the
    point is repeatability, not skill."""

    target_mph: float
    jake: bool
    braking: str
    snubbing: bool = field(default=False)
    jake_on: bool = field(default=False)

    def act(self, truck: TruckState) -> None:
        err = truck.speed_mph - self.target_mph
        if self.jake:
            if err >= -1.0:
                self.jake_on = True
            elif err <= -5.0:
                self.jake_on = False
        else:
            self.jake_on = False

        brake = 0.0
        if self.braking == "steady":
            if err > 1.0:
                brake = min(1.0, err / 15.0)
        elif self.braking == "snub":
            if not self.snubbing and err > 5.0:
                self.snubbing = True
            if self.snubbing:
                brake = 0.5
                if err < -3.0:
                    self.snubbing = False
                    brake = 0.0

        throttle = 0.0
        if brake == 0.0 and not self.jake_on and err < -1.0:
            throttle = min(1.0, -err / 4.0)

        truck.throttle = throttle
        truck.brake = brake
        truck.engine_brake = self.jake_on


@dataclass
class _Watcher:
    """Turns state transitions into report lines, mirroring the thresholds
    the game speaks or cues from (driving_controls air status, the
    driving_updates brake squeal)."""

    truck: TruckState
    events: list[str]
    launch_mph: float = 0.0  # gears below this speed are launch noise, not discipline
    launched: bool = False
    over_rev_said: bool = False
    heat_band: str = "cool"
    squeal_cooldown: float = 0.0
    air_warned: bool = False
    springs_said: bool = False
    fade_said: bool = False
    runaway_said: bool = False
    over_safe_said: bool = False
    brake_was_on: bool = False
    brake_applications: int = 0
    brake_held_s: float = 0.0
    jake_was_on: bool = False
    jake_held_s: float = 0.0
    peak_temp_c: float = 0.0
    peak_temp_mi: float = 0.0
    top_mph: float = 0.0
    top_mph_mi: float = 0.0
    fade_miles: float = 0.0
    lowest_moving_gear: int = 99

    def note(self, t_s: float, text: str) -> None:
        self.events.append(f"mile {self.truck.odometer_mi:.1f}  time {_clock(t_s)}  {text}")

    def tick(self, t_s: float, safe_speed_mph: float) -> None:
        tk = self.truck
        mph = tk.speed_mph

        if tk.brake_temp_c > self.peak_temp_c:
            self.peak_temp_c = tk.brake_temp_c
            self.peak_temp_mi = tk.odometer_mi
        if mph > self.top_mph:
            self.top_mph = mph
            self.top_mph_mi = tk.odometer_mi
        if mph >= self.launch_mph:
            self.launched = True
        if self.launched and 0 < tk.transmission.gear < self.lowest_moving_gear and mph > 5.0:
            self.lowest_moving_gear = tk.transmission.gear

        if (
            not self.over_rev_said
            and tk.engine_on
            and tk.rpm >= tk.specs.max_rpm * 0.98
        ):
            self.over_rev_said = True
            self.note(t_s, f"ENGINE PAST REDLINE ({tk.rpm:.0f} rpm): tearing itself apart")

        band = (
            "hot"
            if tk.brake_temp_c >= tk.specs.brake_fade_temp_c
            else "warm"
            if tk.brake_temp_c >= BRAKES_WARM_C
            else "cool"
        )
        if band != self.heat_band:
            if band == "warm" and self.heat_band == "cool":
                self.note(t_s, f"brakes warm ({tk.brake_temp_c:.0f} C); status would say so")
            elif band == "hot":
                self.note(t_s, f"brakes hot ({tk.brake_temp_c:.0f} C)")
            elif band == "cool" and self.heat_band != "cool":
                self.note(t_s, f"brakes back to cool ({tk.brake_temp_c:.0f} C)")
            self.heat_band = band

        onset = tk.brake_fade_onset_c
        if not self.fade_said and tk.brake_temp_c >= onset:
            self.fade_said = True
            self.note(t_s, f"BRAKE FADE ONSET ({onset:.0f} C): pedal force starts dropping")
        if tk.brake_temp_c >= onset:
            self.fade_miles += mph * DT / 3600.0

        self.squeal_cooldown = max(0.0, self.squeal_cooldown - DT)
        if (
            self.squeal_cooldown == 0.0
            and tk.brake >= SQUEAL_BRAKE
            and mph > SQUEAL_MPH
            and tk.brake_temp_c >= tk.specs.brake_fade_temp_c
        ):
            self.note(t_s, "cue: brake squeal (hot shoes worked past fade)")
            self.squeal_cooldown = SQUEAL_COOLDOWN_S

        if tk.air_low_warning and not self.air_warned:
            self.air_warned = True
            self.note(t_s, f"cue: low air warning ({tk.air_pressure_psi:.0f} psi)")
        if tk.spring_brakes_active and not self.springs_said:
            self.springs_said = True
            self.note(t_s, "spring brakes grab: air is gone")

        if mph >= RUNAWAY_MPH and not self.runaway_said:
            self.runaway_said = True
            self.note(t_s, f"RUNAWAY: {mph:.0f} mph and still building")
        if mph > safe_speed_mph + 5.0 and not self.over_safe_said:
            self.over_safe_said = True
            self.note(t_s, f"above the safe speed for conditions ({safe_speed_mph:.0f} mph)")

        braking_now = tk.brake > 0.01
        if braking_now and not self.brake_was_on:
            self.brake_applications += 1
        if braking_now:
            self.brake_held_s += DT
        self.brake_was_on = braking_now
        if tk.engine_brake:
            self.jake_held_s += DT
        self.jake_was_on = tk.engine_brake


def _run_route(sc: Scenario) -> RunResult:
    truck = _build_truck(sc)
    driver = _Driver(sc.target_mph, sc.jake, sc.braking)
    result = RunResult(sc)
    watch = _Watcher(truck, result.events, launch_mph=max(0.0, sc.target_mph - 5.0))
    effects = EFFECTS[sc.weather]
    total = _total_miles(sc.profile)
    wear0 = (truck.tire_wear_pct, truck.brake_wear_pct, truck.engine_wear_pct)
    fuel0 = truck.fuel_gal

    t = 0.0
    last_grade = _grade_at(sc.profile, 0.0)
    next_marker = 1.0
    watch.note(t, f"start; grade {last_grade * 100:+.1f} percent, target {sc.target_mph:.0f} mph")
    while truck.odometer_mi < total and t < TIMEOUT_S:
        grade = _grade_at(sc.profile, truck.odometer_mi)
        if grade != last_grade:
            word = "steepens" if grade < last_grade else "eases"
            watch.note(
                t, f"grade {word} to {grade * 100:+.1f} percent at {truck.speed_mph:.0f} mph"
            )
            last_grade = grade
        truck.grade = grade
        driver.act(truck)
        gear_change = truck.auto_shift()
        truck.update(DT)
        t += DT
        if gear_change is not None and truck.speed_mph > 5.0:
            watch.note(t, f"gear {gear_change} at {truck.speed_mph:.0f} mph, {truck.rpm:.0f} rpm")
        watch.tick(t, effects.safe_speed_mph)
        if truck.odometer_mi >= next_marker:
            watch.note(
                t,
                f"marker: {truck.speed_mph:.0f} mph, brakes {truck.brake_temp_c:.0f} C, "
                f"gear {truck.transmission.gear}",
            )
            next_marker += 1.0
        if truck.stalled:
            watch.note(t, "ENGINE STALLED; scenario ends")
            break

    result.summary = _summarize(sc, truck, watch, t, wear0, fuel0)
    return result


def _run_stop(sc: Scenario) -> RunResult:
    truck = _build_truck(sc)
    result = RunResult(sc)
    assert sc.stop_from_mph is not None
    watch = _Watcher(truck, result.events, launch_mph=max(0.0, sc.stop_from_mph - 5.0))
    effects = EFFECTS[sc.weather]
    wear0 = (truck.tire_wear_pct, truck.brake_wear_pct, truck.engine_wear_pct)
    fuel0 = truck.fuel_gal

    t = 0.0
    truck.grade = _grade_at(sc.profile, 0.0)
    watch.note(t, f"accelerating to {sc.stop_from_mph:.0f} mph before the stop")
    while truck.speed_mph < sc.stop_from_mph and t < TIMEOUT_S:
        truck.throttle = 1.0
        truck.brake = 0.0
        truck.auto_shift()
        truck.update(DT)
        t += DT

    mark_mi = truck.odometer_mi
    mark_t = t
    watch.note(t, f"full service brake at {truck.speed_mph:.0f} mph")
    while truck.speed_mph > 0.3 and t < TIMEOUT_S:
        truck.throttle = 0.0
        truck.brake = 1.0
        truck.auto_shift()
        truck.update(DT)
        t += DT
        watch.tick(t, effects.safe_speed_mph)

    distance_ft = (truck.odometer_mi - mark_mi) * FT_PER_MI
    watch.note(t, f"stopped: {distance_ft:.0f} feet in {t - mark_t:.1f} seconds")
    result.summary = _summarize(sc, truck, watch, t, wear0, fuel0)
    result.summary.insert(
        1,
        f"stopping distance {distance_ft:.0f} feet from {sc.stop_from_mph:.0f} mph "
        f"({t - mark_t:.1f} seconds)",
    )
    return result


def _summarize(
    sc: Scenario,
    truck: TruckState,
    watch: _Watcher,
    t: float,
    wear0: tuple[float, float, float],
    fuel0: float,
) -> list[str]:
    avg_mph = truck.odometer_mi / (t / 3600.0) if t > 0 else 0.0
    lines = [
        f"distance {truck.odometer_mi:.1f} miles in {_clock(t)}, average {avg_mph:.1f} mph, "
        f"top {watch.top_mph:.1f} mph at mile {watch.top_mph_mi:.1f}",
        f"peak brake temperature {watch.peak_temp_c:.0f} C at mile {watch.peak_temp_mi:.1f}",
        f"fuel used {fuel0 - truck.fuel_gal:.2f} gallons",
        "wear added: tires "
        f"{truck.tire_wear_pct - wear0[0]:.3f}, brakes {truck.brake_wear_pct - wear0[1]:.3f}, "
        f"engine {truck.engine_wear_pct - wear0[2]:.3f} percent",
    ]
    if watch.fade_miles > 0:
        lines.insert(2, f"{watch.fade_miles:.1f} miles ridden past brake fade onset")
    if watch.brake_applications:
        lines.append(
            f"service brake: {watch.brake_applications} applications, "
            f"held {_clock(watch.brake_held_s)} total"
        )
    else:
        lines.append("service brake: never touched")
    if watch.jake_held_s > 0:
        lines.append(f"jake brake engaged {_clock(watch.jake_held_s)} total")
    if watch.lowest_moving_gear < 99:
        lines.append(f"lowest gear while moving: {watch.lowest_moving_gear}")
    return lines


def run_scenario(sc: Scenario) -> RunResult:
    return _run_stop(sc) if sc.stop_from_mph is not None else _run_route(sc)


def _header(sc: Scenario) -> list[str]:
    truck_note = f"{sc.cargo_kg / 1000.0:.1f} tonne payload"
    grip = EFFECTS[sc.weather].grip if sc.grip_override is None else sc.grip_override
    wx = f"{sc.weather.value} (grip {grip:.2f})"
    wear_bits = []
    if sc.tire_wear:
        wear_bits.append(f"tires {sc.tire_wear:.0f} percent worn")
    if sc.brake_wear:
        wear_bits.append(f"brakes {sc.brake_wear:.0f} percent worn")
    if sc.engine_wear:
        wear_bits.append(f"engine {sc.engine_wear:.0f} percent worn")
    lines = [f"Scenario: {sc.name}", f"  {sc.summary}", f"  Load {truck_note}. Weather {wx}."]
    if wear_bits:
        lines.append("  Starting wear: " + ", ".join(wear_bits) + ".")
    return lines


def format_result(result: RunResult, *, full: bool) -> str:
    lines = _header(result.scenario)
    if full:
        lines.append("")
        lines.extend("  " + e for e in result.events)
    lines.append("")
    lines.append("  Summary:")
    lines.extend("  " + s for s in result.summary)
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", nargs="*", help="scenario names (default: all)")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    parser.add_argument("--full", action="store_true", help="print full event logs")
    args = parser.parse_args(argv)

    by_name = {sc.name: sc for sc in SCENARIOS}
    if args.list:
        for sc in SCENARIOS:
            print(f"{sc.name}: {sc.summary}")
        return 0

    picked = list(SCENARIOS)
    if args.scenario:
        missing = [n for n in args.scenario if n not in by_name]
        if missing:
            print("unknown scenario: " + ", ".join(missing))
            print("run with --list to see the names")
            return 2
        picked = [by_name[n] for n in args.scenario]

    # A single named scenario reads as a full log by default; a sweep
    # stays summaries-only unless --full asks otherwise.
    full = args.full or len(picked) == 1
    for sc in picked:
        print(format_result(run_scenario(sc), full=full))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
