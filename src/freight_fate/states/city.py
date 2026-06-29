"""Terminal hub: dispatch board, garage, upgrades, trucks, and route selection."""

from __future__ import annotations

import zlib

from ..data.world import Route
from ..models.economy import (
    REPAIR_COST_PER_PCT,
    pay_advance_grant,
    pay_advance_unavailable_reason,
)
from ..models.jobs import (
    Job,
    JobBoard,
    job_from_payload,
    job_payload,
    plan_hos,
    route_required_hours,
)
from ..models.trucks import TRUCK_CATALOG, UPGRADE_CATALOG, TruckModel, Upgrade
from ..music import select_menu_music_sequence
from ..sim.hos import clock_text, time_of_day
from ..sim.vehicle import TruckState
from .base import MenuItem, MenuState

PICKUP_CHECK_IN_MIN = 15.0
PICKUP_LOADING_MIN = 60.0
TERMINAL_FUEL_MIN = 20.0
TERMINAL_REPAIR_MIN = 60.0


def _job_payload(job: Job) -> dict:
    return job_payload(job)


def _job_from_payload(data: dict) -> Job:
    return job_from_payload(data)


def pickup_snapshot(job: Job, *, checked_in: bool = False,
                    loaded: bool = False, air_brake: dict | None = None,
                    engine_on: bool = False) -> dict:
    data = {
        "kind": "pickup",
        "job": _job_payload(job),
        "checked_in": checked_in,
        "loaded": loaded,
        "engine_on": engine_on,
    }
    if air_brake is not None:
        data["air_brake"] = air_brake
    return data


def route_planning_summary(route: Route) -> str:
    hos_summary = plan_hos(route.miles, route).summary()
    fuel_stops = sum("fuel" in stop.actions for stop in route.stop_details)
    sleep_stops = sum("sleep" in stop.actions for stop in route.stop_details)
    toll_text = (
        f"Estimated carrier-paid toll exposure {route.estimated_tolls:,.0f} dollars."
        if route.estimated_tolls > 0 else
        "No sourced toll exposure on this itinerary."
    )
    return (
        f"{hos_summary} Fuel-capable stops: {fuel_stops}. "
        f"Sleep-capable stops: {sleep_stops}. {toll_text} "
        f"Terrain: {route.terrain_summary}. Parking notes are static confidence, "
        "not a guaranteed open space."
    )


def route_departure_summary(route: Route) -> str:
    toll_text = (
        f" Carrier toll estimate {route.estimated_tolls:,.0f} dollars."
        if route.estimated_tolls > 0 else
        ""
    )
    return (
        f"Loaded trip is {route.miles:.0f} miles via "
        f"{', then '.join(route.highways)}.{toll_text}"
    )


# Empty-drive range for shopping another city's board.
BOBTAIL_RANGE_MI = 400.0


class CityMenuState(MenuState):
    """The hub screen while parked at a company terminal or yard."""

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._board = JobBoard(ctx.world)
        self._jobs_cache: list[Job] | None = None

    @property
    def title(self) -> str:  # type: ignore[override]
        p = self.ctx.profile
        if not p:
            return "Terminal"
        return self.ctx.world.home_terminal(p.current_city).name

    def enter(self) -> None:
        sequence = select_menu_music_sequence(self.ctx.profile)
        self.ctx.play_music_sequence("menu", sequence)
        self.ctx.audio.set_ambient("poi/facility_gate")
        super().enter()

    def exit(self) -> None:
        self.ctx.audio.set_ambient(None)

    def presence(self):
        from ..discord_presence import PresenceState

        p = self.ctx.profile
        city = p.current_city if p else ""
        detail = f"{city} service area" if city else ""
        return PresenceState("At the terminal", detail)

    def announce_entry(self) -> None:
        p = self.ctx.profile
        city = self.ctx.world.cities[p.current_city]
        terminal = self.ctx.world.home_terminal(p.current_city)
        self.ctx.say(
            f"Parked at {terminal.spoken_name} in the {p.current_city} "
            f"service area, {city.state}. You have {p.money:,.0f} dollars. "
            f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem("Dispatch board", self._job_board,
                     help="Browse terminal dispatches from local freight "
                          "facilities, including ports, warehouses, food "
                          "terminals, intermodal yards, and distribution hubs."),
            MenuItem("Bobtail to a nearby city", self._bobtail,
                     help="Drive empty to a nearby city to shop its dispatch "
                          "board. Costs fuel and hours of service; no load, no "
                          "pay. Use it when local jobs are thin."),
            MenuItem(self._garage_label, self._garage,
                     help="Refuel and repair your truck at the terminal garage. "
                          "If cash is short, the garage does partial work."),
            MenuItem("Career stats", self._stats,
                     help="Hear your level, reputation, and lifetime numbers."),
            MenuItem("Truck status", self._truck_status,
                     help="Hear fuel and damage at a glance."),
            MenuItem("Time and weather", self._time_weather,
                     help="Hear the clock, the day of your career, and the "
                          "conditions outside."),
            MenuItem("Sleep 10 hours", self._sleep,
                     help="A full night in the terminal bunk room: fresh hours of "
                          "service and zero fatigue. The clock advances "
                          "10 hours."),
            MenuItem("Save game", self._save,
                     help="Write your career save to disk."),
            MenuItem("Settings", self._settings,
                     help="Change units, transmission, volumes, weather, "
                          "voices, update channel, and trip pacing."),
            MenuItem("Quit to main menu", self._to_main_menu,
                     help="Save your career and return to the title menu."),
        ]
        if self._pay_advance_available():
            items.insert(3, MenuItem(
                self._pay_advance_label, self._request_pay_advance,
                help="Draw cash against your next load when you are broke "
                     "and cannot afford fuel. Repaid automatically out of "
                     "your next delivery settlement."))
        return items

    def _job_board(self) -> None:
        p = self.ctx.profile
        market_changed = p.market.advance_to(p.market_day())
        key = self._dispatch_cache_key()
        cache = p.dispatch_board_cache if not market_changed else None
        if cache and cache.get("key") == key:
            jobs = [_job_from_payload(payload)
                    for payload in cache.get("jobs", [])]
        else:
            jobs = self._board.offers(p.current_city, p.career.endorsements,
                                      level=p.career.level, market=p.market)
            p.dispatch_board_cache = {
                "key": key,
                "jobs": [_job_payload(job) for job in jobs],
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
        region = self.ctx.world.cities[p.current_city].region
        price = self.ctx.economy.fuel_price(region)
        return f"Garage: fuel {price:.2f} per gallon"

    def _garage(self) -> None:
        self.ctx.push_state(GarageState(self.ctx))

    def _pay_advance_label(self) -> str:
        p = self.ctx.profile
        grant = pay_advance_grant(
            p.money, p.pay_advance, p.pay_advance_used_for_load)
        if grant > 0:
            return f"Request pay advance: {grant:,.0f} dollars"
        return "Request pay advance"

    def _pay_advance_available(self) -> bool:
        p = self.ctx.profile
        return pay_advance_grant(
            p.money, p.pay_advance, p.pay_advance_used_for_load) > 0

    def _request_pay_advance(self) -> None:
        p = self.ctx.profile
        grant = pay_advance_grant(
            p.money, p.pay_advance, p.pay_advance_used_for_load)
        if grant <= 0:
            self.ctx.audio.play("ui/error")
            self.ctx.say(pay_advance_unavailable_reason(
                p.money, p.pay_advance, p.pay_advance_used_for_load))
            return
        p.money += grant
        p.pay_advance = round(p.pay_advance + grant, 2)
        p.pay_advance_used_for_load = True
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Pay advance approved: {grant:,.0f} dollars against your next load. "
            f"It will be deducted at delivery. You have {p.money:,.0f} dollars, "
            f"with {p.pay_advance:,.0f} dollars of advance still to repay.")
        self.refresh()

    def _stats(self) -> None:
        self.ctx.say(self.ctx.profile.career.summary())

    def _truck_status(self) -> None:
        p = self.ctx.profile
        specs = p.truck_specs()
        truck = TRUCK_CATALOG.get(p.truck, TRUCK_CATALOG["rig"])
        fuel_pct = p.truck_fuel_gal / specs.fuel_tank_gal * 100
        damage = p.truck_damage_pct
        condition = ("excellent" if damage < 5 else "good" if damage < 20
                     else "worn" if damage < 50 else "poor")
        self.ctx.say(f"Driving the {truck.label}. "
                     f"Fuel {fuel_pct:.0f} percent, {p.truck_fuel_gal:.0f} gallons "
                     f"of {specs.fuel_tank_gal:.0f}. "
                     f"Truck condition {condition}, {damage:.0f} percent damage.")

    def _time_weather(self) -> None:
        from ..sim.weather import WeatherSystem

        p = self.ctx.profile
        city = self.ctx.world.cities[p.current_city]
        hour = p.game_hours % 24.0
        day = p.market_day() + 1
        desc, live = None, False
        provider = self.ctx.real_weather_provider()
        if provider is not None:
            provider.request(city.name, city.lat, city.lon)
            kind = provider.get(city.name)
            if kind is not None:
                desc, live = kind.value, True
        from ..sim.season import date_text, real_clock_game_hours, season

        # With live weather on, the season follows the real calendar so it
        # matches the real conditions; otherwise it follows the career clock.
        season_hours = real_clock_game_hours() if provider is not None else p.game_hours
        if desc is None:
            # deterministic per city and hour, so asking twice agrees
            seed = zlib.crc32(f"{city.name}:{int(p.game_hours)}".encode())
            desc = WeatherSystem(city.region, seed=seed,
                                 game_hours=season_hours).describe()
        source = "Live weather" if live else "Weather"
        self.ctx.say(f"It is {clock_text(hour)}, {time_of_day(hour)}, "
                     f"{date_text(season_hours)}, in {season(season_hours)}, "
                     f"day {day} of your career. "
                     f"{source} in {p.current_city}: {desc}.")

    def _sleep(self) -> None:
        p = self.ctx.profile
        before_fatigue = p.fatigue
        p.game_hours += 10.0
        p.hos.sleep()
        p.fatigue = 0.0
        p.market.advance_to(p.market_day())
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        hour = p.game_hours % 24.0
        self.ctx.say(f"You slept 10 hours and woke rested. It is "
                     f"{clock_text(hour)}, {time_of_day(hour)}. "
                     "Hours of service reset.")
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
        self.ctx.reset_to(MainMenuState(self.ctx))

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.say("Use Quit to main menu to leave the terminal. Progress is saved automatically.")


class BobtailDestState(MenuState):
    """Pick a nearby city to bobtail (drive empty) to, to shop its board."""

    title = "Bobtail to a nearby city"
    intro_help = ("Pick a nearby city to drive to empty. You will see its "
                  "dispatch board on arrival. No load and no pay; this costs "
                  "fuel and hours of service. Escape returns to the terminal.")

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
            city = world.cities[name]
            label = (f"{name}, {city.state} -- "
                     f"{self.ctx.settings.distance_text(miles)} empty")
            items.append(MenuItem(label, lambda n=name: self._start(n),
                                  help=f"Drive empty to {name} to shop its board."))
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
        self.ctx.say(
            f"Bobtailing empty to {dest}, {route.miles:.0f} miles on "
            f"{route.highways[0]}. No load and no pay -- you will see the {dest} "
            "dispatch board on arrival. Check in at the city terminal when you "
            "get there.",
            interrupt=True)
        self.ctx.push_state(driving)


class GarageState(MenuState):
    title = "Garage"

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(self._fuel_label, self._refuel,
                     help="Fill the tank at this region's diesel price. If cash "
                          "is short, buy as many gallons as you can afford."),
            MenuItem(self._repair_label, self._repair,
                     help="Restore the truck to full condition. If cash is short, "
                          "repair as much damage as you can afford."),
            MenuItem("Upgrades", self._upgrades,
                     help="Buy performance upgrades for your truck: more torque, "
                          "less drag, a bigger tank, stronger brakes."),
            MenuItem("Trucks", self._trucks,
                     help="Buy a new truck, or switch between trucks you own."),
            MenuItem("Back", self.go_back,
                     help="Return to the terminal menu."),
        ]

    def _region(self) -> str:
        return self.ctx.world.cities[self.ctx.profile.current_city].region

    def _tank_gal(self) -> float:
        return self.ctx.profile.truck_specs().fuel_tank_gal

    def _fuel_label(self) -> str:
        p = self.ctx.profile
        need = self._tank_gal() - p.truck_fuel_gal
        if need < 1:
            return "Fuel: tank is full"
        cost = self.ctx.economy.fuel_cost(self._region(), need)
        return f"Refuel {need:.0f} gallons for {cost:,.0f} dollars"

    def _repair_label(self) -> str:
        p = self.ctx.profile
        if p.truck_damage_pct < 1:
            return "Repairs: truck is in top shape"
        cost = self.ctx.economy.repair_cost(p.truck_damage_pct)
        return f"Repair {p.truck_damage_pct:.0f} percent damage for {cost:,.0f} dollars"

    def _refuel(self) -> None:
        p = self.ctx.profile
        tank = self._tank_gal()
        need = tank - p.truck_fuel_gal
        if need < 1:
            self.ctx.say("The tank is already full.")
            return
        cost = self.ctx.economy.fuel_cost(self._region(), need)
        if p.money < cost:
            price = self.ctx.economy.fuel_price(self._region())
            gallons = p.money / price if price > 0 else 0.0
            if gallons < 1:
                self.ctx.audio.play("ui/error")
                self.ctx.say("Not enough money for even one gallon of fuel.")
                return
            cost = self.ctx.economy.fuel_cost(self._region(), gallons)
            p.money -= cost
            p.truck_fuel_gal = min(tank, p.truck_fuel_gal + gallons)
            p.game_hours += TERMINAL_FUEL_MIN / 60.0
            p.hos.on_duty(TERMINAL_FUEL_MIN)
            self.ctx.save_profile()
            self.ctx.audio.play("vehicle/fuel_pump")
            self.ctx.say(f"Partial fuel: added {gallons:.0f} gallons for "
                         f"{cost:,.0f} dollars. "
                         f"You have {p.money:,.0f} dollars left.")
            self.ctx.award_achievement("route_refuel")
            self.refresh()
            return
        p.money -= cost
        p.truck_fuel_gal = tank
        p.game_hours += TERMINAL_FUEL_MIN / 60.0
        p.hos.on_duty(TERMINAL_FUEL_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("vehicle/fuel_pump")
        self.ctx.say(f"Tank filled. {cost:,.0f} dollars. "
                     f"You have {p.money:,.0f} dollars left.")
        self.ctx.award_achievement("route_refuel")
        self.refresh()

    def _repair(self) -> None:
        p = self.ctx.profile
        if p.truck_damage_pct < 1:
            self.ctx.say("Nothing to repair.")
            return
        cost = self.ctx.economy.repair_cost(p.truck_damage_pct)
        if p.money < cost:
            repairable = p.money / REPAIR_COST_PER_PCT
            if repairable < 1:
                self.ctx.audio.play("ui/error")
                self.ctx.say("Not enough money for one percent of repairs.")
                return
            cost = self.ctx.economy.repair_cost(repairable)
            p.money -= cost
            p.truck_damage_pct = max(0.0, p.truck_damage_pct - repairable)
            p.game_hours += TERMINAL_REPAIR_MIN / 60.0
            p.hos.on_duty(TERMINAL_REPAIR_MIN)
            self.ctx.save_profile()
            self.ctx.audio.play("ui/notify")
            self.ctx.say(f"Partial repairs fixed {repairable:.0f} percent damage "
                         f"for {cost:,.0f} dollars. "
                         f"You have {p.money:,.0f} dollars left.")
            self.ctx.award_achievement("garage_repair")
            self.refresh()
            return
        p.money -= cost
        p.truck_damage_pct = 0.0
        p.game_hours += TERMINAL_REPAIR_MIN / 60.0
        p.hos.on_duty(TERMINAL_REPAIR_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"Truck repaired. {cost:,.0f} dollars. "
                     f"You have {p.money:,.0f} dollars left.")
        self.ctx.award_achievement("garage_repair")
        self.refresh()

    def _upgrades(self) -> None:
        self.ctx.push_state(UpgradeShopState(self.ctx))

    def _trucks(self) -> None:
        self.ctx.push_state(TruckShopState(self.ctx))


class UpgradeShopState(MenuState):
    title = "Upgrades"
    intro_help = ("Each entry speaks the upgrade, its price, and what you already "
                  "own. Enter buys the next tier. Press F1 on an upgrade to hear "
                  "what it does. Escape returns to the garage.")

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(f"Upgrades. You have {p.money:,.0f} dollars. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items = [MenuItem(lambda u=u: self._label(u), lambda u=u: self._buy(u),
                          help=u.description)
                 for u in UPGRADE_CATALOG.values()]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _label(self, upgrade: Upgrade) -> str:
        owned = self.ctx.profile.upgrades.get(upgrade.key, 0)
        if owned >= upgrade.max_tier:
            tiers = f", tier {owned} of {upgrade.max_tier}" if upgrade.max_tier > 1 else ""
            return f"{upgrade.label}: owned{tiers}"
        price = upgrade.prices[owned]
        if upgrade.max_tier > 1:
            owned_part = f", tier {owned} owned" if owned else ""
            return (f"{upgrade.label}, tier {owned + 1} of {upgrade.max_tier}: "
                    f"{price:,.0f} dollars{owned_part}")
        return f"{upgrade.label}: {price:,.0f} dollars"

    def _buy(self, upgrade: Upgrade) -> None:
        p = self.ctx.profile
        owned = p.upgrades.get(upgrade.key, 0)
        if owned >= upgrade.max_tier:
            self.ctx.say(f"{upgrade.label} is already fully installed.")
            return
        price = upgrade.prices[owned]
        if p.money < price:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"Not enough money. {upgrade.label} costs {price:,.0f} dollars "
                         f"and you have {p.money:,.0f}.")
            return
        p.money -= price
        p.upgrades[upgrade.key] = owned + 1
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        tier_part = (f" tier {owned + 1}" if upgrade.max_tier > 1 else "")
        self.ctx.say(f"{upgrade.label}{tier_part} installed for {price:,.0f} dollars. "
                     f"You have {p.money:,.0f} dollars left.")
        self.ctx.award_achievement("first_upgrade")
        self.refresh()


class TruckShopState(MenuState):
    title = "Trucks"
    intro_help = ("Each entry speaks the truck, its price, and whether you own it. "
                  "Enter buys a truck you do not own, or switches to one you do. "
                  "Press F1 on a truck to hear its character. Escape returns to "
                  "the garage.")

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(f"Trucks. You have {p.money:,.0f} dollars. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items = [MenuItem(lambda m=m: self._label(m), lambda m=m: self._pick(m),
                          help=m.description)
                 for m in TRUCK_CATALOG.values()]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _label(self, model: TruckModel) -> str:
        p = self.ctx.profile
        name = model.label.capitalize()
        if model.key == p.truck:
            return f"{name}: currently driving"
        if model.key in p.owned_trucks:
            return f"{name}: owned, switch to it"
        return f"{name}: buy for {model.price:,.0f} dollars"

    def _pick(self, model: TruckModel) -> None:
        p = self.ctx.profile
        if model.key == p.truck:
            self.ctx.say(f"You are already driving the {model.label}.")
            return
        if model.key not in p.owned_trucks:
            if p.money < model.price:
                self.ctx.audio.play("ui/error")
                self.ctx.say(f"Not enough money. The {model.label} costs "
                             f"{model.price:,.0f} dollars and you have {p.money:,.0f}.")
                return
            p.money -= model.price
            p.owned_trucks.append(model.key)
            self.ctx.audio.play("ui/cash")
            self._switch_to(model)
            self.ctx.say(f"You bought the {model.label} for {model.price:,.0f} dollars "
                         f"and it is now your truck. You have {p.money:,.0f} dollars left.")
            if model.key == "heavy_hauler":
                self.ctx.award_achievement("heavy_hauler")
            return
        self.ctx.audio.play("vehicle/truck_door")
        self._switch_to(model)
        self.ctx.say(f"You are now driving the {model.label}.")

    def _switch_to(self, model: TruckModel) -> None:
        p = self.ctx.profile
        p.truck = model.key
        p.truck_fuel_gal = min(p.truck_fuel_gal, p.truck_specs().fuel_tank_gal)
        self.ctx.save_profile()
        self.refresh()


class JobBoardState(MenuState):
    title = "Dispatch board"
    intro_help = ("Each entry is one dispatch. Enter accepts the dispatch and "
                  "creates a local deadhead pickup drive from your terminal to "
                  "the named origin facility. Jobs name their origin and "
                  "destination facilities, and cargo depends on the facility "
                  "type. Escape returns to the terminal.")

    def __init__(self, ctx, jobs: list[Job]) -> None:
        super().__init__(ctx)
        self.jobs = jobs
        self._confirm_risky_job: Job | None = None

    def announce_entry(self) -> None:
        n = len(self.jobs)
        if n == 0:
            self.ctx.say("Dispatch board. No jobs available right now. Press Escape to go back.")
        else:
            self.ctx.say(f"Dispatch board. {n} dispatch{'es' if n != 1 else ''} available. "
                         f"{self.ctx.profile.market.summary()} "
                         + self.current_text())

    def build_items(self) -> list[MenuItem]:
        items = []
        for i, job in enumerate(self.jobs):
            items.append(MenuItem(
                job.describe(i + 1, len(self.jobs)),
                lambda j=job: self._accept(j),
                help=(
                    f"Load offer from {job.origin_facility_text()} to "
                    f"{job.destination_facility_text()}. Route inspection after "
                    "pickup covers rest, fuel, toll, weather, and restrictions."
                )))
        items.append(MenuItem("Back to terminal", self.go_back))
        return items

    def _accept(self, job: Job) -> None:
        p = self.ctx.profile
        locked = job.locked_reason(p.career.endorsements, p.career.level)
        if locked:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"{locked} Keep delivering to level up and unlock it.")
            return
        if self._needs_hos_confirmation(job):
            self._confirm_risky_job = job
            self.ctx.audio.play("ui/warning")
            self.ctx.say(
                f"Hours warning. This dispatch may not fit your current duty "
                f"clock before you need a legal rest. {p.hos.summary(self.ctx.settings.hos_mode)} "
                "Press Enter again to accept it anyway, or choose another load.",
                interrupt=True)
            return
        self._confirm_risky_job = None
        from .driving import DRIVE_PHASE_PICKUP, DrivingState

        route = self.ctx.world.facility_approach_route(job.origin, job.origin_location)
        terminal = self.ctx.world.home_terminal(p.current_city)
        driving = DrivingState(self.ctx, job, route, phase=DRIVE_PHASE_PICKUP)
        p.dispatch_board_cache = None
        p.active_trip = driving.snapshot()
        self.ctx.save_profile()
        self.ctx.say(
            f"Dispatch accepted from {terminal.name}. Deadhead "
            f"{route.miles:.1f} miles on {route.highways[0]} to pickup at "
            f"{job.origin_facility_text()}. "
            "Check in with the shipper when you arrive.",
            interrupt=True)
        self.ctx.push_state(driving)
        self.ctx.award_achievement("first_dispatch")

    def _needs_hos_confirmation(self, job: Job) -> bool:
        p = self.ctx.profile
        mode = self.ctx.settings.hos_mode
        remaining = p.hos.remaining_min(mode)
        if remaining is None:
            return False
        if self._confirm_risky_job is job:
            return False
        route = self.ctx.world.supported_route(job.origin, job.destination)
        if route is None:
            return False
        pickup_work_h = (PICKUP_CHECK_IN_MIN + PICKUP_LOADING_MIN) / 60.0
        needed_h = pickup_work_h + route_required_hours(route, world=self.ctx.world)
        return remaining / 60.0 < needed_h


class PickupFacilityState(MenuState):
    title = "Pickup facility"
    open_sound_key = "facility/dock_gate"
    intro_help = ("Use up and down arrows to navigate, Enter to select. "
                  "Check in at the origin facility, then load cargo only after "
                  "the truck is fully stopped. Escape repeats the pickup status.")

    def __init__(self, ctx, job: Job, *, checked_in: bool = False,
                 loaded: bool = False, driving=None, air_brake=None,
                 engine_on: bool = False) -> None:
        super().__init__(ctx)
        self.job = job
        self.checked_in = checked_in
        self.loaded = loaded
        self.driving = driving
        if driving is not None:
            self.truck = driving.truck
        else:
            self.truck = TruckState(specs=ctx.profile.truck_specs())
            self.truck.fuel_gal = min(ctx.profile.truck_fuel_gal,
                                      self.truck.specs.fuel_tank_gal)
            self.truck.damage_pct = ctx.profile.truck_damage_pct
            self.truck.restore_air_brake_snapshot(air_brake, default_ready=True)
            if engine_on:
                self.truck.start_engine()

    @classmethod
    def from_snapshot(cls, ctx, data: dict) -> PickupFacilityState | None:
        try:
            return cls(ctx, _job_from_payload(data["job"]),
                       checked_in=bool(data.get("checked_in", False)),
                       loaded=bool(data.get("loaded", False)),
                       air_brake=data.get("air_brake"),
                       engine_on=bool(data.get("engine_on", False)))
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def facility(self) -> str:
        return self.job.origin_facility_text()

    def presence(self):
        from ..discord_presence import PresenceState

        if self.loaded:
            activity = "Loaded and ready to roll"
        elif self.checked_in:
            activity = "Loading at the dock"
        else:
            activity = "At a pickup facility"
        return PresenceState(activity, f"{self.job.cargo.label} for {self.job.destination}")

    def enter(self) -> None:
        sequence = select_menu_music_sequence(self.ctx.profile)
        self.ctx.play_music_sequence("menu", sequence)
        super().enter()

    def announce_entry(self) -> None:
        self.ctx.audio.set_ambient("poi/facility_gate")
        if self.loaded:
            lead = (f"Loaded at {self.facility}. The trailer is sealed for "
                    f"{self.job.destination}.")
        elif self.checked_in:
            lead = (f"Checked in at {self.facility}. You are assigned a dock "
                    "for loading.")
        else:
            lead = (f"Arrived at pickup: {self.facility}. Check in with the "
                    "shipping office before loading.")
        self.ctx.say(f"{lead} {self.current_text()}")

    def exit(self) -> None:
        self.ctx.audio.set_ambient(None)

    def build_items(self) -> list[MenuItem]:
        if self.loaded:
            primary = MenuItem(
                "Depart for destination",
                self._depart_for_destination,
                help="Dispatch loads the navigation itinerary and starts the trip.")
        elif self.checked_in:
            primary = MenuItem(
                "Load cargo at dock",
                self._load,
                help="Back into the assigned dock and wait while the trailer is loaded.")
        else:
            primary = MenuItem(
                "Check in at shipping office",
                self._check_in,
                help="Confirm the pickup number and receive the dock assignment.")
        return [
            primary,
            MenuItem("Pickup status", self._status,
                     help="Hear the origin facility, cargo, destination, and "
                          "loading instruction."),
            MenuItem("Save and quit to main menu", self._save_and_quit,
                     help="Save this pickup objective so it resumes here later."),
            MenuItem("Cancel pickup and return to terminal", self._cancel,
                     help="Give up this job before departure and return to the "
                          "terminal dispatch board area."),
        ]

    def _save_state(self) -> None:
        self.ctx.profile.truck_fuel_gal = self.truck.fuel_gal
        self.ctx.profile.truck_damage_pct = self.truck.damage_pct
        self.ctx.profile.active_trip = pickup_snapshot(
            self.job, checked_in=self.checked_in, loaded=self.loaded,
            air_brake=self.truck.air_brake_snapshot(),
            engine_on=self.truck.engine_on)
        self.ctx.save_profile()

    def _check_in(self) -> None:
        p = self.ctx.profile
        p.game_hours += PICKUP_CHECK_IN_MIN / 60.0
        p.hos.on_duty(PICKUP_CHECK_IN_MIN)
        self.checked_in = True
        self._save_state()
        self.refresh(keep_index=False)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Checked in at {self.facility}. Dock assigned. "
            "Stop, then load cargo.")

    def _load(self) -> None:
        from .driving import DOCKING_MAX_MPH

        if not self.checked_in:
            self.ctx.say("Check in at the shipping office before loading.")
            return
        if self.truck.speed_mph > DOCKING_MAX_MPH:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Stop before loading.")
            return
        self.truck.throttle = 0.0
        self.truck.brake = 1.0
        p = self.ctx.profile
        p.game_hours += PICKUP_LOADING_MIN / 60.0
        p.hos.on_duty(PICKUP_LOADING_MIN)
        self.truck.set_parking_brake()
        self.loaded = True
        self._save_state()
        self.refresh(keep_index=False)
        self.ctx.audio.play("poi/dock_and_deliver")
        self.ctx.award_achievement("first_pickup")
        self.ctx.say(
            f"Loaded and sealed at {self.facility}. "
            f"{self.job.weight_tons:.0f} tons of {self.job.cargo.label} are "
            f"ready for {self.job.destination}. Loading took "
            f"{PICKUP_LOADING_MIN:.0f} minutes. Depart when ready.")

    def _depart_for_destination(self) -> None:
        if not self.loaded:
            self.ctx.say("Load the cargo before departing for the destination.")
            return
        routes = self.ctx.world.supported_route_options(
            self.job.origin, self.job.destination)
        if not routes:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Dispatch cannot find a navigation itinerary for this load.")
            return
        self.ctx.say(
            f"Route planning to {self.job.destination_facility_text()}. "
            f"{len(routes)} realistic supported route "
            f"option{'s' if len(routes) != 1 else ''} available.",
            interrupt=True)
        self.ctx.push_state(RouteSelectState(
            self.ctx,
            self.job,
            routes,
            back_label="Back to pickup facility",
            air_brake=self.truck.air_brake_snapshot(),
            engine_on=self.truck.engine_on,
        ))
    def _plan_route(self) -> None:
        self._depart_for_destination()

    def _status(self) -> None:
        state = ("loaded and sealed" if self.loaded else
                 "checked in, waiting to load" if self.checked_in else
                 "not checked in")
        brake = "parking brake set" if self.truck.parking_brake else "parking brake released"
        self.ctx.say(
            f"Pickup at {self.facility}: {state}. "
            f"Cargo is {self.job.weight_tons:.0f} tons of {self.job.cargo.label}. "
            f"Destination is {self.job.destination_facility_text()}. "
            f"Current speed {self.ctx.settings.speed_text(self.truck.speed_mph)}. "
            f"Air pressure {self.truck.air_pressure_psi:.0f} psi, {brake}.")

    def _save_and_quit(self) -> None:
        from .main_menu import MainMenuState

        self._save_state()
        self.ctx.say("Saved. Your pickup objective will resume here.",
                     interrupt=True)
        self.ctx.reset_to(MainMenuState(self.ctx))

    def _cancel(self) -> None:
        self.ctx.profile.active_trip = None
        self.ctx.profile.dispatch_board_cache = None
        self.ctx.save_profile()
        terminal = self.ctx.world.home_terminal(self.ctx.profile.current_city)
        self.ctx.say(f"Pickup canceled. Returned to {terminal.name}.",
                     interrupt=True)
        self.ctx.reset_to(CityMenuState(self.ctx))

    def go_back(self) -> None:
        self._status()

    def lines(self) -> list[str]:
        state = ("Loaded and sealed" if self.loaded else
                 "Checked in" if self.checked_in else "Check-in required")
        return [
            self.title,
            f"Facility: {self.facility}",
            f"Cargo: {self.job.weight_tons:.0f} tons of {self.job.cargo.label}",
            f"Destination: {self.job.destination}",
            f"Status: {state}",
            f"Speed: {self.truck.speed_mph:.0f} mph",
            f"Air: {self.truck.air_pressure_psi:.0f} psi   "
            f"{'parking set' if self.truck.parking_brake else 'parking released'}",
            "",
        ] + [
            ("> " if i == self.index else "  ") + item.text
            for i, item in enumerate(self.items)
        ]


class RouteSelectState(MenuState):
    title = "Route planning"
    intro_help = ("Pick a route. Shorter routes are faster but may cross mountains. "
                  "Press W on a route to hear the weather forecast along it. "
                  "Enter starts the drive.")

    def __init__(self, ctx, job: Job, routes: list[Route],
                 back_label: str = "Back to dispatch board",
                 air_brake=None,
                 engine_on: bool = False) -> None:
        super().__init__(ctx)
        self.job = job
        self.routes = routes
        self.back_label = back_label
        self.air_brake = air_brake
        self.engine_on = engine_on
        provider = ctx.real_weather_provider()
        if provider is not None:
            for route in routes:
                for name in route.cities:
                    city = ctx.world.cities[name]
                    provider.request(city.name, city.lat, city.lon)

    def announce_entry(self) -> None:
        self.ctx.say(f"Route planning to {self.job.destination}. "
                     f"{len(self.routes)} route option{'s' if len(self.routes) != 1 else ''}. "
                     + self.current_text())

    def build_items(self) -> list[MenuItem]:
        items = []
        for i, route in enumerate(self.routes):
            label = f"Route {i + 1}: {route.describe()}. {route_planning_summary(route)}"
            items.append(MenuItem(label, lambda r=route: self._start(r),
                                  help=(
                                      "Via "
                                      + ", ".join(route.cities[1:-1] or ["no major cities"])
                                      + ". Press W for weather."
                                  )))
        items.append(MenuItem(self.back_label, self.go_back))
        return items

    def handle_event(self, event) -> None:
        import pygame

        if (event.type == pygame.KEYDOWN and event.key == pygame.K_w
                and self.index < len(self.routes)):
            self._speak_forecast(self.routes[self.index])
            return
        super().handle_event(event)

    def _speak_forecast(self, route: Route) -> None:
        from ..sim.weather import WeatherSystem

        provider = self.ctx.real_weather_provider()
        if provider is not None:
            parts = []
            for name in route.cities[1:][:5]:
                kind = provider.get(name)
                if kind is not None:
                    parts.append(f"{name}: {kind.value}")
            if parts:
                self.ctx.say("Live weather along the route. " + ". ".join(parts) + ".")
                return
            self.ctx.say("Live weather is still loading. Try again in a moment, "
                         "or check V while driving.")
            return
        regions: list[str] = []
        for city_name in route.cities:
            region = self.ctx.world.cities[city_name].region
            if not regions or regions[-1] != region:
                regions.append(region)
        parts = []
        for region in regions[:4]:
            ws = WeatherSystem(region)
            parts.append(f"{region.replace('_', ' ')}: {ws.current.value}")
        self.ctx.say("Forecast along the route. " + ". ".join(parts) + ".")

    def _start(self, route: Route) -> None:
        from .driving import DrivingState

        driving = DrivingState(self.ctx, self.job, route)
        driving.truck.restore_air_brake_snapshot(self.air_brake, default_ready=True)
        if self.engine_on:
            driving.truck.start_engine()
        self.ctx.profile.active_trip = driving.snapshot()
        self.ctx.save_profile()
        next_context = driving.trip.next_navigation_context()
        self.ctx.say(
            f"Navigation set for {self.job.destination_facility_text()}. "
            f"{route_departure_summary(route)} {next_context} Departing now.",
            interrupt=True)
        self.ctx.push_state(driving)
