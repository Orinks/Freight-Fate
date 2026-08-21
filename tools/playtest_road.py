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

``--find`` takes: downgrade, upgrade, zone, limit-drop, stop, curve,
interchange, toll, chain-law. ``--routes`` picks a named set (mountain,
rolling, flat, all) unless ``--from``/``--to`` name a pair.

``--routes random`` draws instead from the whole map, so a session is not
always testing the same ten corridors -- half the named ones are mountain,
which is how a playtest keeps landing in engine-brake country whatever it
meant to look at::

    uv run python tools/playtest_road.py --routes random --find limit-drop --scan
    uv run python tools/playtest_road.py --routes random --seed 42 --find curve

The draw prints its seed; passing it back gives the same roads (the work
zones on them are drawn per trip and will differ). ``--sample`` sets how many
routes it offers the search and ``--max-miles`` how long they may be.

The driving assists that change what the truck does on a grade are arguments
too -- ``--descent off|realistic|interactive``, ``--assists``,
``--predictive-cruise on|off``, ``--lane-keeping``, ``--transmission``, and
``--verbosity coaching|standard|quiet|urgent_only`` -- so a behaviour can be
compared across settings without editing your own. Anything not given falls
back to your real settings, so the playtest otherwise reproduces what a
player would actually get.
"""

from __future__ import annotations

import argparse
import os
import random
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
# ``--routes random`` is not a list: it is drawn from the whole map at run
# time. The named sets are ten hand-picked corridors and half of them are
# mountain, so playtest after playtest ran the same roads and kept landing on
# engine-brake country whatever the session was actually testing (owner,
# 2026-08-15). The draw prints its seed, so a road worth revisiting can be
# drawn again -- the work zones on it are a per-trip roll and will not repeat.
RANDOM_ROUTES = "random"
# Long hauls make a feature search crawl and put the interesting mile hours
# from the start. Past this the draw takes another pair instead; --max-miles
# lifts it for anyone who wants a coast-to-coast run.
RANDOM_MAX_MILES = 600.0
RANDOM_SAMPLE = 6  # how many pairs a random draw offers the search

FEATURES = (
    "downgrade",
    "upgrade",
    "zone",
    "limit-drop",
    "stop",
    "curve",
    "interchange",
    "toll",
    "chain-law",
)
SCAN_STEP_MI = 0.1
# How far before the feature the truck is placed: far enough that an advance
# warning has somewhere to land, close enough that you are not driving to it.
DEFAULT_LEAD_MI = 1.8


def random_pairs(world, *, count: int, max_miles: float, seed: int) -> list[tuple[str, str]]:
    """Supported city pairs drawn from the whole map, shortest first.

    Named the way the hand-picked sets are and the way a player would say
    them, so the banner, the scan lines and a ``--from``/``--to`` rerun all
    read as roads rather than as database keys. A name is only used when it
    resolves back to the same city; anything ambiguous keeps its key.
    Shortest first, so the search reaches a feature quickly and the drive
    starts near it rather than hours up the road.
    """
    rng = random.Random(seed)
    names = world.city_names()
    found: list[tuple[float, str, str]] = []
    seen: set[tuple[str, str]] = set()
    # Bounded: a draw must never hunt forever for its last pair on a map where
    # most random pairs are longer than the limit.
    for _ in range(count * 400):
        if len(found) >= count:
            break
        a, b = rng.sample(names, 2)
        key = (a, b) if a < b else (b, a)
        if key in seen:
            continue
        seen.add(key)
        route = world.supported_route(a, b)
        if route is None or route.miles > max_miles:
            continue
        found.append((route.miles, _speakable(world, a), _speakable(world, b)))
    found.sort()
    return [(a, b) for _, a, b in found]


def _speakable(world, key: str) -> str:
    """The city's spoken name where that still names this city, else the key.

    Two cities share a bare name often enough (Jackson, Portland) that a
    blind swap would silently point a rerun at the wrong road.
    """
    spoken = world.spoken_city(key)
    return spoken if world.resolve_city_key(spoken) == key else key


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


def _curve_hits(trip, origin, destination, max_advisory) -> list[Hit]:
    """Baked curves, tightest advisory first -- the pacenote's own source.

    Connector curves (ramps) are skipped: the interesting case is a mainline
    bend taken at speed, not the geometry of an exit you are already braking
    for.
    """
    hits = []
    for curve in getattr(trip, "curves", None) or []:
        if getattr(curve, "connector", False):
            continue
        advisory = float(getattr(curve, "advisory_mph", 0.0) or 0.0)
        if advisory <= 0.0 or advisory > max_advisory:
            continue
        at = float(curve.start_mi)
        limit, _ = trip.speed_limit_at(max(0.0, at - DEFAULT_LEAD_MI))
        side = "right" if getattr(curve, "direction", "") == "R" else "left"
        hits.append(
            Hit(
                origin,
                destination,
                at,
                trip.total_miles,
                # Rank by how much speed the bend actually asks you to give up.
                max(0.0, limit - advisory),
                max(0.0, float(curve.end_mi) - at),
                limit,
                f"{side} curve, advisory {advisory:.0f} "
                f"({getattr(curve, 'min_radius_ft', 0):.0f} ft radius)",
            )
        )
    return hits


def _interchange_hits(trip, origin, destination) -> list[Hit]:
    """Real signed exits, for testing the exit callout and ramp handling."""
    hits, offset = [], 0.0
    for i, leg in enumerate(trip.route.legs):
        forward = trip.route.cities[i] == leg.a
        for ic in getattr(leg, "interchanges", None) or []:
            at_leg = float(ic.at_mi) if forward else leg.miles - float(ic.at_mi)
            at = offset + at_leg
            if not 0.0 <= at < trip.total_miles:
                continue
            limit, _ = trip.speed_limit_at(max(0.0, at - DEFAULT_LEAD_MI))
            label = ic.name or (ic.destinations[0] if ic.destinations else "")
            hits.append(
                Hit(
                    origin,
                    destination,
                    at,
                    trip.total_miles,
                    0.0,
                    0.0,
                    limit,
                    f"exit {ic.exit_ref or '?'} {label}".strip(),
                )
            )
        offset += leg.miles
    return hits


def _toll_hits(trip, origin, destination) -> list[Hit]:
    hits, offset = [], 0.0
    for i, leg in enumerate(trip.route.legs):
        forward = trip.route.cities[i] == leg.a
        for toll in getattr(leg, "toll_events", None) or []:
            at_leg = float(getattr(toll, "at_mi", 0.0))
            at = offset + (at_leg if forward else leg.miles - at_leg)
            if not 0.0 <= at < trip.total_miles:
                continue
            limit, _ = trip.speed_limit_at(max(0.0, at - DEFAULT_LEAD_MI))
            cost = float(getattr(toll, "amount", 0.0) or 0.0)
            # Ticket-system entries carry no amount of their own -- the charge
            # settles at the exit -- so say that rather than printing $0.00.
            price = (
                f"${cost:.2f}"
                if cost
                else str(getattr(toll, "method_label", "") or "no charge here")
            )
            hits.append(
                Hit(
                    origin,
                    destination,
                    at,
                    trip.total_miles,
                    cost,
                    0.0,
                    limit,
                    f"toll {getattr(toll, 'name', '')}: {price}".strip(),
                )
            )
        offset += leg.miles
    return hits


def _chain_law_hits(trip, origin, destination) -> list[Hit]:
    """Chain-law areas. Whether the law is *up* depends on live weather, so
    pair this with --weather snow to make the pass actually demand chains."""
    hits = []
    for start_mi, end_mi in getattr(trip, "chain_law_areas", None) or []:
        limit, _ = trip.speed_limit_at(max(0.0, start_mi - DEFAULT_LEAD_MI))
        hits.append(
            Hit(
                origin,
                destination,
                start_mi,
                trip.total_miles,
                end_mi - start_mi,
                end_mi - start_mi,
                limit,
                "chain-law area (needs winter weather to be active)",
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
        elif feature == "curve":
            hits += _curve_hits(trip, origin, destination, args.max_advisory)
        elif feature == "interchange":
            hits += _interchange_hits(trip, origin, destination)
        elif feature == "toll":
            hits += _toll_hits(trip, origin, destination)
        elif feature == "chain-law":
            hits += _chain_law_hits(trip, origin, destination)
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

    s = ctx.settings
    # Settings first: DrivingState reads the gearbox and the assist choices in
    # its constructor, so an override applied afterwards would not take.
    if args.assists:
        s.apply_driving_assistance_preset(args.assists)
    if args.descent:
        s.descent_speed_control = args.descent
    if args.predictive_cruise:
        s.predictive_cruise = args.predictive_cruise == "on"
    if args.lane_keeping:
        s.lane_keeping = args.lane_keeping
    if args.curve_assist:
        s.curve_speed_assist = args.curve_assist == "on"
    if args.transmission:
        s.automatic_transmission = args.transmission == "automatic"
    if args.verbosity is not None:
        s.driving_speech = args.verbosity

    # The canonical key, not the display name the route sets are written in:
    # a career's current_city is a slug ("dallas_tx_us"), and cloud backup
    # refuses anything else as an unknown city. Left as the display name, every
    # playtest quietly threw a rejected upload at the server and told the
    # driver its backup was not accepted (2026-08-15).
    origin_key = ctx.world.resolve_city_key(hit.origin)
    destination_key = ctx.world.resolve_city_key(hit.destination)
    ctx.profile = Profile(name="Playtest", current_city=origin_key)
    # A bench career is not somebody's first drive. Without this the profile
    # defaults to tutorial_done=False, first-run teaching outranks the rung
    # by design (GameContext._ladder_applies), and the driving speech ladder
    # is switched OFF for the whole run -- so --verbosity quiet reported
    # "quiet" and changed nothing, and every rung sounded identical. Found
    # when the owner playtested the quiet rung and heard standard
    # (2026-08-17).
    ctx.profile.tutorial_done = True
    route = ctx.world.supported_route(hit.origin, hit.destination)
    # The job's endpoints are keys for the same reason. Delivering runs
    # ``profile.current_city = job.destination``, so a job built from the route
    # sets' display names puts the label straight back after the first drop --
    # which is why fixing only the line above was not enough: a playtest career
    # that actually completed a run still carried "Grand Junction". The spoken
    # fields keep the display names, so nothing reads a slug aloud.
    job = Job(
        CARGO_CATALOG[args.cargo_type],
        args.cargo,
        origin_key,
        "company yard",
        destination_key,
        route.miles,
        2500.0,
        14.0,
        destination_location=f"{hit.destination} freight market",
        origin_spoken=ctx.world.spoken_city(origin_key),
        destination_spoken=ctx.world.spoken_city(destination_key),
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
    print(f"    driving speech  : {s.driving_speech}")
    print(f"    units           : {'miles' if s.imperial_units else 'kilometers'}")
    print(f"    speed keeper    : {'on' if s.speed_keeper else 'off'}")
    print(f"    descent control : {getattr(s, 'descent_speed_control', 'n/a')}")
    print(f"    predictive cruise: {'on' if getattr(s, 'predictive_cruise', False) else 'off'}")
    print(f"    assists preset  : {getattr(s, 'driving_assistance_preset', 'n/a')}")
    print(f"    time scale      : {s.time_scale}")
    print("  grade ahead       :")
    for ahead in (0.0, 1.0, 2.0, 3.0, 5.0, 8.0):
        at = start_mi + ahead
        if at < trip.total_miles:
            print(f"    +{ahead:4.1f} mi      {trip.grade_at(at) * 100:+5.1f}%")


def run_headless(app, driving, args) -> None:
    """Drive it on the clock and print what happens -- no window, no speech."""
    import pygame

    from freight_fate.states.driving_damage import cargo_status_clause

    spoken: list[tuple[str, str]] = []
    # Stub the VOICE layer (ctx.speech.say/say_event), not ctx.say/say_event
    # themselves. The driving verbosity ladder's gate and the event pacer's
    # repeat/backlog handling both live *inside* GameContext.say/say_event --
    # replacing those methods (the old approach here) skipped both, so this
    # bench printed every line the game would say with no rung applied and
    # no repeat suppression running, not what a player at their real
    # ``--verbosity`` setting actually hears. By the time a line reaches the
    # voice layer it has already been gated and rendered to a plain string,
    # so the shim only needs (text, interrupt).
    # ``**_`` absorbs anything the voice backend's own say/say_event might
    # grow beyond that -- the shim must not crash the bench the first time
    # the backend gains a keyword.
    app.ctx.speech.say_event = lambda text, interrupt=False, **_: spoken.append(("event", text))
    app.ctx.speech.say = lambda text, interrupt=True, **_: spoken.append(("say", text))

    class NoKeys:
        def __getitem__(self, _key):
            return False

    pygame.key.get_pressed = lambda: NoKeys()
    app.push_state(driving)

    trip, truck = driving.trip, driving.truck
    print("\n  mile   mph  grade  gear  jake  brake   air   cruise  cargo  peak g")
    seen, last_report = 0, trip.position_mi - 1.0
    # What the freight actually felt, which no other column shows: the hardest
    # deceleration of the run and the worst overspeed through a bend are the
    # two inputs the cargo model reads, so a condition number that moved can
    # be traced to the manoeuvre that moved it.
    peak_decel_g = peak_corner_over = 0.0
    last_mph = truck.speed_mph
    for _ in range(int(60 * 60 * args.headless)):
        driving.update(1 / 60)
        decel_g = max(0.0, (last_mph - truck.speed_mph) / 2.23694 / 9.80665 * 60.0)
        last_mph = truck.speed_mph
        peak_decel_g = max(peak_decel_g, decel_g)
        peak_corner_over = max(peak_corner_over, float(truck.corner_overspeed_mph))
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
                f"   {truck.cargo_damage_pct:5.1f}  {peak_decel_g:5.2f}"
            )
        if trip.finished:
            break
    print(
        f"\nfinal: mile {trip.position_mi:.1f}, {truck.speed_mph:.1f} mph, "
        f"air {truck.air_pressure_psi:.0f} psi, brakes {truck.brake_temp_c:.0f}C, "
        f"cruise {driving._cruise_mph}"
    )
    print(
        f"cargo: {truck.cargo_damage_pct:.1f} percent "
        f"({cargo_status_clause(truck)}), peak decel {peak_decel_g:.2f} g, "
        f"worst bend {peak_corner_over:.0f} mph over advisory"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    from freight_fate.settings import DRIVING_SPEECH_MODES, LANE_KEEPING_MODES

    p = argparse.ArgumentParser(
        description="Drop into a chosen piece of road with the truck already set up."
    )
    p.add_argument("--from", dest="origin", help="origin city (use with --to)")
    p.add_argument("--to", dest="destination", help="destination city")
    p.add_argument(
        "--routes",
        default="mountain",
        choices=sorted([*ROUTE_SETS, RANDOM_ROUTES]),
        help="route set, or 'random' to draw from the whole map",
    )
    p.add_argument(
        "--seed",
        type=int,
        help="seed for --routes random: pins which roads are drawn, not the trip on them",
    )
    p.add_argument(
        "--sample",
        type=int,
        default=RANDOM_SAMPLE,
        help=f"how many routes --routes random draws (default {RANDOM_SAMPLE})",
    )
    p.add_argument(
        "--max-miles",
        type=float,
        default=RANDOM_MAX_MILES,
        help=f"longest route --routes random will draw (default {RANDOM_MAX_MILES:.0f})",
    )
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
    p.add_argument(
        "--max-advisory", type=float, default=45.0, help="curve search: slowest advisory to accept"
    )
    p.add_argument(
        "--descent", choices=("off", "realistic", "interactive"), help="descent speed control"
    )
    p.add_argument("--assists", help="driving assistance preset, e.g. realistic, all")
    p.add_argument("--predictive-cruise", choices=("on", "off"), help="grade preview for cruise")
    p.add_argument(
        "--lane-keeping",
        choices=LANE_KEEPING_MODES,
        help="lane keeping: full holds the lane and takes exits, off leaves both to you",
    )
    p.add_argument(
        "--curve-assist",
        choices=("on", "off"),
        help="curve speed assistance: off means you brake for the bends yourself",
    )
    p.add_argument("--transmission", choices=("automatic", "manual"), help="override the gearbox")
    p.add_argument("--verbosity", choices=DRIVING_SPEECH_MODES, help="driving speech rung override")
    p.add_argument("--weather", help="force a weather kind, e.g. rain, snow, clear")
    p.add_argument("--hour", type=float, help="clock hour to start at")
    p.add_argument("--headless", type=float, default=0.0, help="bench for N minutes, no window")
    p.add_argument("--log", help="transcript path (default logs/playtest.log)")
    p.add_argument(
        "--sandbox",
        action="store_true",
        help="drive in a throwaway data dir that cannot back up or publish anything",
    )
    args = p.parse_args(argv)
    if args.no_cruise:
        args.cruise = 0.0
    if not args.feature and args.at is None:
        args.feature = "downgrade"
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.sandbox:
        # Before anything resolves a save path: a playtest career belongs in a
        # data dir with no driver identity, so nothing it does reaches the
        # owner's cloud backups or public profile.
        from playtest_sandbox import audit, describe, prepare

        sandbox = prepare()
        print(describe(sandbox))
        if audit(sandbox):
            print("Refusing to drive: the sandbox is not isolated.", file=sys.stderr)
            return 1
        print()

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
    if args.origin and args.destination:
        pairs = [(args.origin, args.destination)]
    elif args.routes == RANDOM_ROUTES:
        seed = args.seed if args.seed is not None else random.randrange(1_000_000)
        pairs = random_pairs(world, count=args.sample, max_miles=args.max_miles, seed=seed)
        if not pairs:
            print(
                f"No supported route under {args.max_miles:.0f} miles came up; raise --max-miles."
            )
            return 1
        # The seed pins the ROADS, not the run: work zones are drawn per trip,
        # so the same seed finds the same corridors with a different set of
        # zone-driven limit drops on them each time.
        print(f"Random routes (same roads again with --seed {seed}):")
        for origin, destination in pairs:
            print(f"  {origin} -> {destination}")
        print()
    else:
        pairs = ROUTE_SETS[args.routes]
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
            hint = {
                "downgrade": "Loosen --min-pct / --min-run",
                "upgrade": "Loosen --min-pct / --min-run",
                "limit-drop": "Loosen --min-drop",
                "curve": "Raise --max-advisory",
                "toll": "Tolled corridors are mostly eastern turnpikes",
            }.get(args.feature, "Try another route")
            print(f"Nothing matched. {hint}, or try --routes all.")
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
    from freight_fate.settings import data_dir

    _configure_logging()
    # The session must not leak its --lane-keeping/--assists overrides into the
    # player's real settings: App.shutdown() saves settings on the way out,
    # which persisted a playtest's flags as the player's own choices
    # (owner-hit 2026-07-27: the steering override became the saved setting).
    settings_path = data_dir() / "settings.json"
    settings_before = settings_path.read_bytes() if settings_path.exists() else None
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
        # First call only: quitting to the main menu must reach the REAL menu
        # (with its working Exit), not respawn the drive with no way out.
        real_menu = main_menu.MainMenuState
        served = []

        class _DriveThenMenu(real_menu):
            """First construction hands over the staged drive; later ones the
            real menu. A subclass, not a function: game code also reaches
            MainMenuState for its classmethods (arm_update_check), and a bare
            function shim crashed the save-and-quit path."""

            def __new__(cls, ctx):
                if not served:
                    served.append(True)
                    # Not an instance of cls, so __init__ is skipped -- the
                    # drive is already fully built.
                    return driving
                return super().__new__(cls)

        main_menu.MainMenuState = _DriveThenMenu
        print("\n  G grade, J engine brake, K cruise, Down arrow brakes (hands cruise back).")
        print("  To leave: Escape pauses; quit to the main menu, then Exit as usual.")
        print(f"  Transcript: {log_path}\n")
        app.run()
        print(f"\nDone. Transcript written to {log_path}")
        return 0
    finally:
        app.shutdown()
        if settings_before is not None:
            settings_path.write_bytes(settings_before)
        elif settings_path.exists():
            settings_path.unlink()


if __name__ == "__main__":
    sys.exit(main())
