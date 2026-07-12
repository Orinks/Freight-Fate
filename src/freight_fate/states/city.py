"""Terminal hub: the city menu and bobtail repositioning.

The garage screens live in ``city_garage`` and the dispatch, pickup, and
route-planning screens in ``city_dispatch``; this module re-exports them so
``states.city`` keeps its full public surface.
"""

from __future__ import annotations

import zlib

from ..models.economy import pay_advance_grant, pay_advance_unavailable_reason
from ..models.jobs import Job, JobBoard, job_from_payload, job_payload, normalize_job_cities
from ..models.trucks import TRUCK_CATALOG
from ..music import select_menu_music_sequence
from ..sim.hos import clock_text, time_of_day
from ..sim.timezones import city_zone, to_local
from .base import MenuItem, MenuState
from .career_stats import CareerStatsState, fully_rested
from .city_dispatch import (
    JobBoardState,
    JobDetailState,
    PickupFacilityState,
    RouteSelectState,
    pickup_snapshot,
    route_departure_summary,
    route_planning_summary,
)
from .city_garage import GarageState, TruckShopState, UpgradeShopState

__all__ = [
    "BOBTAIL_RANGE_MI",
    "BobtailDestState",
    "CityMenuState",
    "GarageState",
    "JobBoardState",
    "JobDetailState",
    "PickupFacilityState",
    "RouteSelectState",
    "TruckShopState",
    "UpgradeShopState",
    "pickup_snapshot",
    "route_departure_summary",
    "route_planning_summary",
]

# Empty-drive range for shopping another city's board.
BOBTAIL_RANGE_MI = 400.0


class CityMenuState(MenuState):
    """The hub screen while parked at a company terminal or yard."""

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._board = JobBoard(ctx.world)
        self._jobs_cache: list[Job] | None = None
        self._confirm_sleep_rested = False

    @property
    def title(self) -> str:  # type: ignore[override]
        p = self.ctx.profile
        if not p:
            return "Terminal"
        return self.ctx.world.home_terminal(p.current_city).name

    def enter(self) -> None:
        self._confirm_sleep_rested = False
        sequence = select_menu_music_sequence(self.ctx.profile)
        self.ctx.play_music_sequence("menu", sequence)
        self.ctx.audio.set_ambient("poi/facility_gate")
        super().enter()

    # Moving off the Sleep item withdraws its pending double-press confirmation,
    # so a stale "press Enter again" can never sleep you silently later.
    def move(self, delta: int) -> None:
        self._confirm_sleep_rested = False
        super().move(delta)

    def jump(self, index: int) -> None:
        self._confirm_sleep_rested = False
        super().jump(index)

    def exit(self) -> None:
        self.ctx.audio.set_ambient(None)

    def presence(self):
        from ..discord_presence import PresenceState

        p = self.ctx.profile
        city = self.ctx.world.spoken_city(p.current_city) if p and p.current_city else ""
        detail = f"{city} service area" if city else ""
        return PresenceState("At the terminal", detail)

    def announce_entry(self) -> None:
        p = self.ctx.profile
        city = self.ctx.world.city(p.current_city)
        terminal = self.ctx.world.home_terminal(p.current_city)
        self.ctx.say(
            f"Parked at {terminal.spoken_name} in the {city.name} "
            f"service area, {city.state}. You have {p.money:,.0f} dollars. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                "Dispatch board",
                self._job_board,
                help="Browse terminal dispatches from local freight "
                "facilities, including ports, warehouses, food "
                "terminals, intermodal yards, and distribution hubs.",
            ),
            MenuItem(
                "Bobtail to a nearby city",
                self._bobtail,
                help="Drive empty to a nearby city to shop its dispatch "
                "board. Costs fuel and hours of service; no load, no "
                "pay. Use it when local jobs are thin.",
            ),
            MenuItem(
                self._garage_label,
                self._garage,
                help="Refuel and repair your truck at the terminal garage. "
                "If cash is short, the garage does partial work.",
            ),
            MenuItem(
                "Career stats",
                self._stats,
                help="Review your level, reputation, lifetime numbers, and "
                "rest status, one line at a time.",
            ),
            MenuItem("Truck status", self._truck_status, help="Hear fuel and damage at a glance."),
            MenuItem(
                "Time and weather",
                self._time_weather,
                help="Hear the clock, the day of your career, and the conditions outside.",
            ),
            MenuItem(
                "Sleep 10 hours",
                self._sleep,
                help="A full night in the terminal bunk room: fresh hours of "
                "service and zero fatigue. The clock advances "
                "10 hours.",
            ),
            MenuItem("Save game", self._save, help="Write your career save to disk."),
            MenuItem(
                "Settings",
                self._settings,
                help="Change units, transmission, volumes, weather, "
                "voices, update channel, and trip pacing.",
            ),
            MenuItem(
                "Quit to main menu",
                self._to_main_menu,
                help="Save your career and return to the title menu.",
            ),
        ]
        if self._pay_advance_available():
            items.insert(
                3,
                MenuItem(
                    self._pay_advance_label,
                    self._request_pay_advance,
                    help="Draw cash against your next load when you are broke "
                    "and cannot afford fuel. Repaid automatically out of "
                    "your next delivery settlement.",
                ),
            )
        return items

    def _job_board(self) -> None:
        p = self.ctx.profile
        market_changed = p.market.advance_to(p.market_day())
        key = self._dispatch_cache_key()
        cache = p.dispatch_board_cache if not market_changed else None
        if cache and cache.get("key") == key:
            jobs = [
                normalize_job_cities(job_from_payload(payload), self.ctx.world)
                for payload in cache.get("jobs", [])
            ]
        else:
            jobs = self._board.offers(
                p.current_city, p.career.endorsements, level=p.career.level, market=p.market
            )
            p.dispatch_board_cache = {
                "key": key,
                "jobs": [job_payload(job) for job in jobs],
            }
            self.ctx.save_profile()
        self._jobs_cache = jobs
        self.ctx.push_state(JobBoardState(self.ctx, jobs))

    def _dispatch_cache_key(self) -> dict:
        p = self.ctx.profile
        return {
            "city": p.current_city,
            "market_day": p.market_day(),
            "market_seed": p.market.seed,
            "market_state_day": p.market.day,
            "level": p.career.level,
            "endorsements": sorted(p.career.endorsements),
            "count": 5,
        }

    def _bobtail(self) -> None:
        p = self.ctx.profile
        cands = sorted(self._board._candidates(p.current_city), key=lambda c: c[1])
        nearby = [c[0] for c in cands if c[1] <= BOBTAIL_RANGE_MI][:8]
        if not nearby:  # never strand a remote start: offer the nearest few
            nearby = [c[0] for c in cands[:3]]
        if not nearby:
            self.ctx.audio.play("ui/error")
            self.ctx.say("No nearby cities are reachable from here.")
            return
        self.ctx.push_state(BobtailDestState(self.ctx, nearby))

    def _garage_label(self) -> str:
        p = self.ctx.profile
        region = self.ctx.world.city(p.current_city).region
        price = self.ctx.economy.fuel_price(region)
        return f"Garage: fuel {price:.2f} per gallon"

    def _garage(self) -> None:
        self.ctx.push_state(GarageState(self.ctx))

    def _pay_advance_label(self) -> str:
        p = self.ctx.profile
        grant = pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load)
        if grant > 0:
            return f"Request pay advance: {grant:,.0f} dollars"
        return "Request pay advance"

    def _pay_advance_available(self) -> bool:
        p = self.ctx.profile
        return pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load) > 0

    def _request_pay_advance(self) -> None:
        p = self.ctx.profile
        grant = pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load)
        if grant <= 0:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                pay_advance_unavailable_reason(p.money, p.pay_advance, p.pay_advance_used_for_load)
            )
            return
        p.money += grant
        p.pay_advance = round(p.pay_advance + grant, 2)
        p.pay_advance_used_for_load = True
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Pay advance approved: {grant:,.0f} dollars against your next load. "
            f"It will be deducted at delivery. You have {p.money:,.0f} dollars, "
            f"with {p.pay_advance:,.0f} dollars of advance still to repay."
        )
        self.refresh()

    def _stats(self) -> None:
        self.ctx.push_state(CareerStatsState(self.ctx))

    def _truck_status(self) -> None:
        p = self.ctx.profile
        specs = p.truck_specs()
        truck = TRUCK_CATALOG.get(p.truck, TRUCK_CATALOG["rig"])
        fuel_pct = p.truck_fuel_gal / specs.fuel_tank_gal * 100
        damage = p.truck_damage_pct
        condition = (
            "excellent"
            if damage < 5
            else "good"
            if damage < 20
            else "worn"
            if damage < 50
            else "poor"
        )
        self.ctx.say(
            f"Driving the {truck.label}. "
            f"Fuel {fuel_pct:.0f} percent, {p.truck_fuel_gal:.0f} gallons "
            f"of {specs.fuel_tank_gal:.0f}. "
            f"Truck condition {condition}, {damage:.0f} percent damage. "
            f"Tire wear {p.tire_wear_pct:.0f} percent. "
            f"Road grime {p.road_grime_pct:.0f} percent."
        )

    def _time_weather(self) -> None:
        from ..sim.weather import WeatherSystem

        p = self.ctx.profile
        city = self.ctx.world.city(p.current_city)
        zone = city_zone(city)
        hour = to_local(p.game_hours, zone) % 24.0
        day = p.market_day() + 1
        desc, live = None, False
        provider = self.ctx.real_weather_provider()
        if provider is not None:
            # Keyed by the city key, not the spoken name: two cities can share
            # a spoken name but they are different places with different skies.
            provider.request(city.key, city.lat, city.lon)
            kind = provider.get(city.key)
            if kind is not None:
                desc, live = kind.value, True
        from ..sim.season import date_text, real_clock_game_hours, season

        # With live weather on, the season follows the real calendar so it
        # matches the real conditions; otherwise it follows the career clock.
        season_hours = real_clock_game_hours() if provider is not None else p.game_hours
        if desc is None:
            # deterministic per city and hour, so asking twice agrees
            seed = zlib.crc32(f"{city.key}:{int(p.game_hours)}".encode())
            desc = WeatherSystem(city.region, seed=seed, game_hours=season_hours).describe(
                self.ctx.settings.imperial_units
            )
        source = "Live weather" if live else "Weather"
        self.ctx.say(
            f"It is {clock_text(hour)} {zone.name}, {time_of_day(hour)}, "
            f"{date_text(season_hours)}, in {season(season_hours)}, "
            f"day {day} of your career. "
            f"{source} in {city.name}: {desc}."
        )

    def _sleep(self) -> None:
        p = self.ctx.profile
        if fully_rested(p) and not self._confirm_sleep_rested:
            self._confirm_sleep_rested = True
            self.ctx.audio.play("ui/warning")
            self.ctx.say(
                "You are already rested: fresh hours of service and no fatigue. "
                "Sleeping now would only move the clock forward 10 hours. "
                "Press Enter again to sleep anyway."
            )
            return
        self._confirm_sleep_rested = False
        before_fatigue = p.fatigue
        p.game_hours += 10.0
        p.hos.sleep()
        p.fatigue = 0.0
        p.market.advance_to(p.market_day())
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        zone = city_zone(self.ctx.world.city(p.current_city))
        hour = to_local(p.game_hours, zone) % 24.0
        self.ctx.say(
            f"You slept 10 hours and woke rested. It is "
            f"{clock_text(hour)}, {time_of_day(hour)}. "
            "Hours of service reset."
        )
        if before_fatigue < 70.0:
            self.ctx.award_achievement("sleep_before_exhaustion")

    def _save(self) -> None:
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say("Game saved.")

    def _settings(self) -> None:
        from .main_menu import SettingsState

        self.ctx.push_state(SettingsState(self.ctx))

    def _to_main_menu(self) -> None:
        from .main_menu import MainMenuState

        self.ctx.save_profile()
        self.ctx.say("Progress saved.")
        MainMenuState.arm_update_check(self.ctx.settings)
        self.ctx.reset_to(MainMenuState(self.ctx))

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.say(
            "Use Quit to main menu to leave the terminal. Progress is saved automatically."
        )


class BobtailDestState(MenuState):
    """Pick a nearby city to bobtail (drive empty) to, to shop its board."""

    title = "Bobtail to a nearby city"
    intro_help = (
        "Pick a nearby city to drive to empty. You will see its "
        "dispatch board on arrival. No load and no pay; this costs "
        "fuel and hours of service. Escape returns to the terminal."
    )

    def __init__(self, ctx, cities: list[str]) -> None:
        self._cities = cities
        super().__init__(ctx)

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        world = self.ctx.world
        here = self.ctx.profile.current_city
        for name in self._cities:
            route = world.supported_route(here, name)
            miles = route.miles if route is not None else 0.0
            city = world.city(name)
            label = f"{city.name}, {city.state} -- {self.ctx.settings.distance_text(miles)} empty"
            items.append(
                MenuItem(
                    label,
                    lambda n=name: self._start(n),
                    help=f"Drive empty to {world.spoken_city(name)} to shop its board.",
                )
            )
        items.append(MenuItem("Back to terminal", self.go_back))
        return items

    def _start(self, dest: str) -> None:
        from ..models.jobs import make_reposition_job
        from .driving import DrivingState

        p = self.ctx.profile
        job = make_reposition_job(self.ctx.world, p.current_city, dest)
        route = self.ctx.world.supported_route(p.current_city, dest)
        if job is None or route is None:
            self.ctx.audio.play("ui/error")
            self.ctx.say("No route to that city right now.")
            return
        driving = DrivingState(self.ctx, job, route)
        p.dispatch_board_cache = None
        p.active_trip = driving.snapshot()
        self.ctx.save_profile()
        spoken_dest = job.spoken_destination
        self.ctx.say(
            f"Bobtailing empty to {spoken_dest}, {route.miles:.0f} miles on "
            f"{route.highways[0]}. No load and no pay -- you will see the "
            f"{spoken_dest} dispatch board on arrival. Check in at the city "
            "terminal when you get there.",
            interrupt=True,
        )
        self.ctx.push_state(driving)
