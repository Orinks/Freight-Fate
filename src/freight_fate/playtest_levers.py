"""Environment-variable playtest levers, never active in normal play.

These exist for the alpha test book: a tester relocates a parked career or
moves the clock forward so a scenario (a night snow run over the Rockies,
say) can be reached without hours of setup driving. Each lever speaks what
it did in plain language, moves no miles and no money, and refuses to touch
a career that has a load in progress. A future shared-profile event ledger
must record forced relocations and clock moves so shared saves stay honest
(docs/profile-invariants.md).

``FREIGHT_FATE_FORCE_CITY``
    Relocate a parked career to a city (slug or display name) when it is
    loaded from the main menu.
``FREIGHT_FATE_FORCE_CLOCK``
    Advance the career clock forward to the next occurrence of a local
    wall-clock hour (0-23) when the career is loaded. Ten or more hours
    of waiting counts as a full break, like sleeping at the terminal.
``FREIGHT_FATE_FORCE_DEST``
    Guarantee the dispatch board offers a load to a destination, and put
    that load first in line when dispatch assigns loads.
``FREIGHT_FATE_FORCE_PERSIST``
    Set to 1 to make a lever session permanent. WITHOUT it, any lever
    session is a SANDBOX (owner design 2026-07-15): the whole run plays on
    the loaded career in memory and nothing is ever saved -- quit, launch
    normally, and the career is exactly where it was, same city, same
    date, same money. A tester teleports somewhere, breaks whatever the
    scenario needs, and their real save never knows.
"""

from __future__ import annotations

import os
import re

CITY_ENV = "FREIGHT_FATE_FORCE_CITY"
CLOCK_ENV = "FREIGHT_FATE_FORCE_CLOCK"
DEST_ENV = "FREIGHT_FATE_FORCE_DEST"
PERSIST_ENV = "FREIGHT_FATE_FORCE_PERSIST"


def forced_city() -> str:
    return os.environ.get(CITY_ENV, "").strip()


def forced_clock_hour() -> float | None:
    raw = os.environ.get(CLOCK_ENV, "").strip()
    if not raw:
        return None
    try:
        hour = float(raw)
    except ValueError:
        return None
    if not 0.0 <= hour < 24.0:
        return None
    return hour


def forced_dispatch_destination() -> str:
    return os.environ.get(DEST_ENV, "").strip()


def persist_requested() -> bool:
    return os.environ.get(PERSIST_ENV, "").strip() not in ("", "0")


def apply_continue_levers(ctx) -> list[str]:
    """Relocation and clock levers, applied as a saved career resumes.

    Only a parked career with no accepted load moves; anything mid-trip
    keeps its state. Returns the spoken notes for the caller to queue
    after its own entry announcement (entry speech interrupts, and a
    lever note must never be lost to it).

    Any lever session is a sandbox unless ``FREIGHT_FATE_FORCE_PERSIST``
    says otherwise: ``ctx.playtest_sandbox`` goes True and ``save_profile``
    becomes a no-op for the whole run, so the career file on disk never
    learns the scenario happened.
    """
    p = ctx.profile
    city = forced_city()
    clock = forced_clock_hour()
    if not city and clock is None and not forced_dispatch_destination():
        return []
    if p.active_trip:
        if not city and clock is None:
            # A forced dispatch destination alone has nothing to do until
            # the board opens; it neither moves nor sandboxes a live load.
            return []
        return [
            "Playtest lever ignored: this career has a load in progress. "
            "Deliver or abandon it first."
        ]
    notes: list[str] = []
    if city:
        notes.extend(_apply_city(ctx, p, city))
    if clock is not None:
        notes.extend(_apply_clock(ctx, p, clock))
    if not persist_requested():
        ctx.playtest_sandbox = True
        notes.append(
            "Playtest sandbox: nothing this session is saved. Your career "
            "resumes untouched next time you play normally."
        )
    elif notes:
        ctx.save_profile()
    return notes


def resolve_city_forgiving(world, city: str) -> str:
    """Resolve a tester-typed city: exact slug or display name first, then a
    slugified retry so "holbrook,az,us", "Holbrook, AZ, US", and the
    PowerShell-array casualty "holbrook az us" all land on holbrook_az_us."""
    key = world.resolve_city_key(city)
    if key in world.cities:
        return key
    slugged = re.sub(r"[^a-z0-9]+", "_", city.lower()).strip("_")
    key = world.resolve_city_key(slugged)
    return key if key in world.cities else city


def _apply_city(ctx, p, city: str) -> list[str]:
    key = resolve_city_forgiving(ctx.world, city)
    if key not in ctx.world.cities:
        return [f"Playtest lever: no city called {city}. Staying put."]
    if key == ctx.world.resolve_city_key(p.current_city):
        return []
    p.current_city = key
    p.dispatch_board_cache = None
    return [
        f"Playtest lever: relocated to {ctx.world.spoken_city(key, qualified=True)}. "
        "No miles driven, no money changed."
    ]


def _apply_clock(ctx, p, hour: float) -> list[str]:
    from .sim.hos import clock_text, time_of_day
    from .sim.timezones import city_zone, to_local

    try:
        city_obj = ctx.world.city(p.current_city)
    except KeyError:
        return ["Playtest lever: cannot read the local clock here. Clock unchanged."]
    zone = city_zone(city_obj)
    local = to_local(p.game_hours, zone) % 24.0
    delta = (hour - local) % 24.0
    if delta < 0.05:
        return []
    start = p.game_hours
    p.game_hours += delta
    try:
        place = ctx.world.home_terminal(p.current_city).name
    except KeyError:
        place = ctx.world.spoken_city(p.current_city)
    p.duty_log.record("off_duty", start, p.game_hours, place, "playtest clock lever")
    p.market.advance_to(p.market_day())
    rested = ""
    if delta >= 10.0:
        # Ten-plus hours parked is a full break in any honest logbook.
        p.hos.sleep()
        p.fatigue = 0.0
        rested = " You waited out a full break; hours of service reset."
    return [
        f"Playtest lever: clock moved forward to {clock_text(hour)}, "
        f"{time_of_day(hour)} local.{rested}"
    ]
