"""Drop into a chosen piece of road, set up the way you want to test it.

Walking the menus to a specific hill, work zone, or limit drop takes minutes and
lands you somewhere slightly different every time. This starts the real game --
real window, real speech, real input, your real settings -- already rolling at a
road feature you named, with the truck and cruise in the state you asked for.
Every spoken line goes to a transcript, so the session can be read afterwards.

Its sibling ``tools/playtest.py`` drives a whole delivery headlessly and prints
the transcript; this one hands you the wheel at one spot and lets you drive it.

Find a feature and drive it::

    uv run python tools/playtest_road.py --find downgrade --cruise 70
    uv run python tools/playtest_road.py --from Denver --to "Grand Junction" \\
        --find downgrade --min-pct 5 --cruise 70 --cargo 20

Look before you drive (searches, prints, exits)::

    uv run python tools/playtest_road.py --find downgrade --scan
    uv run python tools/playtest_road.py --find zone --scan --routes rolling

Start at an exact mile, cruise off, empty trailer::

    uv run python tools/playtest_road.py --from Buffalo --to Albany --at 40 \\
        --no-cruise --cargo 0

Run it as a bench instead of driving it -- prints a speed/gear/jake trace and
every spoken line, no window, no speech::

    uv run python tools/playtest_road.py --find downgrade --cruise 70 --headless 8

``--find`` takes: downgrade, upgrade, zone, limit-drop, stop. ``--routes`` picks
a named set (mountain, rolling, flat, all) unless ``--from``/``--to`` name a
pair. Anything not given falls back to your real settings, so the playtest
reproduces what a player would actually get.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# Route sets swept when the caller does not name a pair. Hand-picked and small:
# a feature search is only useful if it finishes while you wait.
ROUTE_SETS: dict[str, list[tuple[str, str]]] = {
    "mountain": [
        ("Denver", "Grand Junction"),
        ("Albuquerque", "Denver"),
        ("Sacramento", "Reno"),
        ("Phoenix", "Flagstaff"),
        ("Seattle", "Spokane"),
    ],
    "rolling": [
        ("Knoxville", "Asheville"),
        ("Buffalo", "New York"),
        ("Charlotte", "Knoxville"),
    ],
    "flat": [
        ("Chicago", "Indianapolis"),
        ("Dallas", "Houston"),
    ],
}
ROUTE_SETS["all"] = [pair for pairs in ROUTE_SETS.values() for pair in pairs]

FEATURES = ("downgrade", "upgrade", "zone", "limit-drop", "stop")
SCAN_STEP_MI = 0.1
# How far before the feature the truck is placed: far enough that an advance
# warning has somewhere to land, close enough that you are not driving to it.
DEFAULT_LEAD_MI = 1.8


@dataclass
class Hit:
    """One found road feature, with what is needed to describe or drive it."""

    origin: str
    destination: str
    at_mi: float  # where the feature starts
    total_mi: float
    magnitude: float  # percent for grades, mph for limits and zones, else 0
    run_mi: float
    limit_mph: float
    label: str

    def describe(self) -> str:
        run = f", running {self.run_mi:.1f} mi" if self.run_mi >= 0.1 else ""
        return (
            f"{self.origin} -> {self.destination}  mile {self.at_mi:6.1f} of "
            f"{self.total_mi:.0f}  {self.label}{run}  (posted {self.limit_mph:.0f})"
        )


def load_world():
    """The world data on its own -- no App, and so no window.

    Searching is read-only, so booting the whole game to do it opened (and
    closed) a real window for every ``--scan``. The world loader is the only
    part a search actually needs.
    """
    from freight_fate.data.world import get_world

    return get_world()


def _build_trip(world, origin: str, destination: str):
    from freight_fate.sim.trip import Trip
    from freight_fate.sim.vehicle import TruckState
    from freight_fate.sim.weather import WeatherSystem

    route = world.supported_route(origin, destination)
    return route, Trip(route, TruckState(), WeatherSystem())


def _grade_hits(trip, origin, destination, sign, min_pct, min_run) -> list[Hit]:
    """Sustained grades in the requested direction."""
    hits: list[Hit] = []
    mi, start, run = 0.0, None, 0.0
    while mi < trip.total_miles:
        pct = trip.grade_at(mi) * 100.0 * sign
        if pct >= min_pct:
            if start is None:
                start = mi
            run += SCAN_STEP_MI
        else:
            if start is not None and run >= min_run:
                probe, worst = start, 0.0
                while probe < start + run:
                    worst = max(worst, trip.grade_at(probe) * 100.0 * sign)
                    probe += SCAN_STEP_MI
                limit, _ = trip.speed_limit_at(max(0.0, start - DEFAULT_LEAD_MI))
                word = "downgrade" if sign < 0 else "upgrade"
                hits.append(
                    Hit(
                        origin,
                        destination,
                        start,
                        trip.total_miles,
                        worst,
                        run,
                        limit,
                        f"{worst:.1f}% {word}",
                    )
                )
            start, run = None, 0.0
        mi += SCAN_STEP_MI
    return hits


def _zone_hits(trip, origin, destination) -> list[Hit]:
    hits = []
    for zone in getattr(trip, "zones", None) or []:
        limit, _ = trip.speed_limit_at(max(0.0, zone.start_mi - DEFAULT_LEAD_MI))
        hits.append(
            Hit(
                origin,
                destination,
                zone.start_mi,
                trip.total_miles,
                zone.limit_mph,
                max(0.0, zone.end_mi - zone.start_mi),
                limit,
                f"{zone.reason} zone, {zone.limit_mph:.0f} mph",
            )
        )
    return hits


def _limit_drop_hits(trip, origin, destination, min_drop) -> list[Hit]:
    """Places the posted limit falls by at least ``min_drop`` mph."""
    hits = []
    mi = SCAN_STEP_MI
    previous, _ = trip.speed_limit_at(0.0)
    while mi < trip.total_miles:
        limit, _ = trip.speed_limit_at(mi)
        drop = previous - limit
        if drop >= min_drop:
            hits.append(
                Hit(
                    origin,
                    destination,
                    mi,
                    trip.total_miles,
                    drop,
                    0.0,
                    previous,
                    f"limit drops {previous:.0f} to {limit:.0f}",
                )
            )
        previous = limit
        mi += SCAN_STEP_MI
    return hits


def _stop_hits(trip, origin, destination) -> list[Hit]:
    hits = []
    for stop in getattr(trip, "stops", None) or []:
        limit, _ = trip.speed_limit_at(max(0.0, stop.at_mi - DEFAULT_LEAD_MI))
        name = getattr(stop, "name", "") or getattr(stop, "key", "stop")
        hits.append(
            Hit(
                origin,
                destination,
                stop.at_mi,
                trip.total_miles,
                0.0,
                0.0,
                limit,
                f"{getattr(stop, 'type', 'stop')}: {name}",
            )
        )
    return hits


def find_feature(world, pairs, feature: str, args) -> list[Hit]:
    """Every matching feature across the given routes, best first."""
    hits: list[Hit] = []
    for origin, destination in pairs:
        try:
            _, trip = _build_trip(world, origin, destination)
        except Exception as exc:  # an unroutable pair must not kill the sweep
            print(f"  (skipped {origin} -> {destination}: {exc})")
            continue
        if feature in ("downgrade", "upgrade"):
            sign = -1 if feature == "downgrade" else 1
            hits += _grade_hits(trip, origin, destination, sign, args.min_pct, args.min_run)
        elif feature == "zone":
            hits += _zone_hits(trip, origin, destination)
        elif feature == "limit-drop":
            hits += _limit_drop_hits(trip, origin, destination, args.min_drop)
        elif feature == "stop":
            hits += _stop_hits(trip, origin, destination)
    if feature in ("downgrade", "upgrade"):
        hits.sort(key=lambda h: (-h.run_mi, -h.magnitude))
    else:
        hits.sort(key=lambda h: (-h.magnitude, h.at_mi))
    return hits


def build_driving(ctx, hit: Hit, args):
    """A DrivingState already rolling at the feature, set up as asked."""
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    ctx.profile = Profile(name="Playtest", current_city=hit.origin)
    route = ctx.world.supported_route(hit.origin, hit.destination)
    job = Job(
        CARGO_CATALOG[args.cargo_type],
        args.cargo,
        hit.origin,
        "company yard",
        hit.destination,
        route.miles,
        2500.0,
        14.0,
        destination_location=f"{hit.destination} freight market",
    )
    driving = DrivingState(
        ctx, job, route, phase="delivery", start_hour=args.hour if args.hour is not None else 9.0
    )

    trip, truck = driving.trip, driving.truck
    start_mi = max(0.0, min(trip.total_miles - 1.0, hit.at_mi - args.lead))
    trip.position_mi = start_mi
    if args.weather:
        from freight_fate.sim.weather import WeatherKind

        driving.weather.current = WeatherKind[args.weather.upper()]
    truck.start_engine()
    truck.set_air_ready(parking_brake=False)
    truck.velocity_mps = args.speed / 2.23694
    truck.transmission.gear = truck.transmission.num_gears
    truck.grade = trip.grade_at(start_mi)
    if args.cruise:
        # Engage the way K does, so the session is armed exactly as a player's
        # would be rather than a hand-set field the rest of the state does not
        # know about.
        driving._engage_cruise(args.cruise)
    return driving, start_mi


def _print_setup(ctx, driving, hit: Hit, start_mi: float, args) -> None:
    s = ctx.settings
    trip = driving.trip
    limit, reason = trip.speed_limit_at(start_mi)
    print(f"\n=== playtest: {hit.origin} -> {hit.destination} ===")
    print(f"  target            : {hit.label} at mile {hit.at_mi:.1f}")
    print(f"  starting at mile  : {start_mi:.1f} of {trip.total_miles:.0f}")
    print(f"  posted limit here : {limit:.0f} mph{f' ({reason})' if reason else ''}")
    print(f"  rolling at        : {args.speed:.0f} mph, {args.cargo:.0f} t aboard")
    print(f"  cruise            : {f'set {args.cruise:.0f} mph' if args.cruise else 'off'}")
    print("  your real settings:")
    print(f"    transmission    : {'automatic' if s.automatic_transmission else 'manual'}")
    print(
        f"    speech verbosity: {s.speech_verbosity} "
        f"({'terse' if s.speech_verbosity == 0 else 'normal'})"
    )
    print(f"    units           : {'miles' if s.imperial_units else 'kilometers'}")
    print(f"    speed keeper    : {'on' if s.speed_keeper else 'off'}")
    print(f"    time scale      : {s.time_scale}")
    print("  grade ahead       :")
    for ahead in (0.0, 1.0, 2.0, 3.0, 5.0, 8.0):
        at = start_mi + ahead
        if at < trip.total_miles:
            print(f"    +{ahead:4.1f} mi      {trip.grade_at(at) * 100:+5.1f}%")


def run_headless(app, driving, args) -> None:
    """Drive it on the clock and print what happens -- no window, no speech."""
    import pygame

    spoken: list[tuple[str, str]] = []
    app.ctx.say_event = lambda text, interrupt=False: spoken.append(("event", text))
    app.ctx.say = lambda text, interrupt=True: spoken.append(("say", text))

    class NoKeys:
        def __getitem__(self, _key):
            return False

    pygame.key.get_pressed = lambda: NoKeys()
    app.push_state(driving)

    trip, truck = driving.trip, driving.truck
    print("\n  mile   mph  grade  gear  jake  brake   air   cruise")
    seen, last_report = 0, trip.position_mi - 1.0
    for _ in range(int(60 * 60 * args.headless)):
        driving.update(1 / 60)
        while seen < len(spoken):
            kind, text = spoken[seen]
            seen += 1
            print(f"        [{kind}] {text}")
        if trip.position_mi - last_report >= 1.0:
            last_report = trip.position_mi
            print(
                f"{trip.position_mi:6.1f} {truck.speed_mph:5.1f} "
                f"{truck.grade * 100:+5.1f}  {truck.transmission.gear:4d}  "
                f"{'ON ' if truck.engine_brake else 'off'}  {truck.brake:5.2f} "
                f"{truck.air_pressure_psi:5.1f}   {driving._cruise_mph}"
            )
        if trip.finished:
            break
    print(
        f"\nfinal: mile {trip.position_mi:.1f}, {truck.speed_mph:.1f} mph, "
        f"air {truck.air_pressure_psi:.0f} psi, brakes {truck.brake_temp_c:.0f}C, "
        f"cruise {driving._cruise_mph}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Drop into a chosen piece of road with the truck already set up."
    )
    p.add_argument("--from", dest="origin", help="origin city (use with --to)")
    p.add_argument("--to", dest="destination", help="destination city")
    p.add_argument("--routes", default="mountain", choices=sorted(ROUTE_SETS), help="route set")
    p.add_argument("--find", dest="feature", choices=FEATURES, help="road feature to start at")
    p.add_argument("--at", type=float, help="start at this mile instead of searching")
    p.add_argument("--pick", type=int, default=0, help="which search result to use (0 = best)")
    p.add_argument("--scan", action="store_true", help="list what was found and exit")
    p.add_argument("--min-pct", type=float, default=3.0, help="grade search: minimum percent")
    p.add_argument("--min-run", type=float, default=1.0, help="grade search: minimum miles")
    p.add_argument("--min-drop", type=float, default=10.0, help="limit search: minimum mph drop")
    p.add_argument("--lead", type=float, default=DEFAULT_LEAD_MI, help="miles to start ahead of it")
    p.add_argument("--cruise", type=float, default=0.0, help="engage cruise at this speed")
    p.add_argument("--no-cruise", action="store_true", help="leave cruise off")
    p.add_argument("--speed", type=float, default=62.0, help="rolling speed at the start")
    p.add_argument("--cargo", type=float, default=20.0, help="payload in tons")
    p.add_argument("--cargo-type", default="general", help="cargo catalog key")
    p.add_argument("--weather", help="force a weather kind, e.g. rain, snow, clear")
    p.add_argument("--hour", type=float, help="clock hour to start at")
    p.add_argument("--headless", type=float, default=0.0, help="bench for N minutes, no window")
    p.add_argument("--log", help="transcript path (default logs/playtest.log)")
    args = p.parse_args(argv)
    if args.no_cruise:
        args.cruise = 0.0
    if not args.feature and args.at is None:
        args.feature = "downgrade"
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    log_path = Path(args.log) if args.log else ROOT / "logs" / "playtest.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["FREIGHT_FATE_LOG_FILE"] = str(log_path)
    os.environ.setdefault("FREIGHT_FATE_LOG", "INFO")
    if args.headless:
        os.environ.setdefault("FREIGHT_FATE_NO_SPEECH", "1")
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    # Pick the spot first, against the world data alone. Booting the game to
    # run a read-only search is what opened and closed a window on every
    # --scan; nothing below this block needs a window until we actually drive.
    world = load_world()
    pairs = (
        [(args.origin, args.destination)]
        if args.origin and args.destination
        else ROUTE_SETS[args.routes]
    )
    if args.at is not None:
        origin, destination = pairs[0]
        _, trip = _build_trip(world, origin, destination)
        limit, _ = trip.speed_limit_at(args.at)
        hit = Hit(origin, destination, args.at, trip.total_miles, 0.0, 0.0, limit, "chosen mile")
        args.lead = 0.0
    else:
        print(f"Searching {len(pairs)} route(s) for a {args.feature}...")
        hits = find_feature(world, pairs, args.feature, args)
        if not hits:
            print("Nothing matched. Loosen --min-pct / --min-run, or try --routes all.")
            return 1
        if args.scan:
            print(f"\n{len(hits)} found:\n")
            for i, found in enumerate(hits[:25]):
                print(f"  [{i:2d}] {found.describe()}")
            print("\nDrive one with --pick N (keeping the same --find/--routes).")
            return 0  # read-only: the game never started, so no window ever opened
        if args.pick >= len(hits):
            print(f"--pick {args.pick} out of range; {len(hits)} found.")
            return 1
        hit = hits[args.pick]

    from freight_fate.app import App, _configure_logging

    _configure_logging()
    app = App()
    try:
        driving, start_mi = build_driving(app.ctx, hit, args)
        _print_setup(app.ctx, driving, hit, start_mi, args)

        if args.headless:
            run_headless(app, driving, args)
            return 0

        import freight_fate.states.main_menu as main_menu

        # App.run() imports MainMenuState inside the function and pushes it, so
        # swapping the name there is what puts us on the road instead of in the
        # menu -- with the real loop, real speech, and real input behind it.
        main_menu.MainMenuState = lambda ctx: driving
        print("\n  G grade, J engine brake, K cruise, Down arrow brakes (hands cruise back).")
        print(f"  Transcript: {log_path}\n")
        app.run()
        print(f"\nDone. Transcript written to {log_path}")
        return 0
    finally:
        app.shutdown()


if __name__ == "__main__":
    sys.exit(main())
