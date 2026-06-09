"""City hub: job board, garage, career stats, and route selection."""

from __future__ import annotations

from ..data.world import Route
from ..models.jobs import Job, JobBoard
from .base import MenuItem, MenuState


class CityMenuState(MenuState):
    """The hub screen while parked in a city."""

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._board = JobBoard(ctx.world)
        self._jobs_cache: list[Job] | None = None

    @property
    def title(self) -> str:  # type: ignore[override]
        p = self.ctx.profile
        return f"{p.current_city}" if p else "City"

    def enter(self) -> None:
        self.ctx.audio.play_music("menu_theme")
        self.ctx.audio.set_ambient("ambient/truck_stop", volume=0.35)
        super().enter()

    def exit(self) -> None:
        self.ctx.audio.set_ambient(None)

    def announce_entry(self) -> None:
        p = self.ctx.profile
        city = self.ctx.world.cities[p.current_city]
        self.ctx.say(
            f"{p.current_city}, {city.state}. You have {p.money:,.0f} dollars. "
            f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem("Job board", self._job_board,
                     help="Browse delivery jobs leaving this city."),
            MenuItem(self._garage_label, self._garage,
                     help="Refuel and repair your truck. Costs vary by region."),
            MenuItem("Career stats", self._stats,
                     help="Hear your level, reputation, and lifetime numbers."),
            MenuItem("Truck status", self._truck_status,
                     help="Hear fuel and damage at a glance."),
            MenuItem("Save game", self._save, help="Write your progress to disk."),
            MenuItem("Settings", self._settings),
            MenuItem("Quit to main menu", self._to_main_menu),
        ]
        return items

    # -- actions -----------------------------------------------------------------

    def _job_board(self) -> None:
        p = self.ctx.profile
        jobs = self._board.offers(p.current_city, p.career.endorsements,
                                  level=p.career.level)
        self._jobs_cache = jobs
        self.ctx.push_state(JobBoardState(self.ctx, jobs))

    def _garage_label(self) -> str:
        p = self.ctx.profile
        region = self.ctx.world.cities[p.current_city].region
        price = self.ctx.economy.fuel_price(region)
        return f"Garage: fuel {price:.2f} per gallon"

    def _garage(self) -> None:
        self.ctx.push_state(GarageState(self.ctx))

    def _stats(self) -> None:
        self.ctx.say(self.ctx.profile.career.summary())

    def _truck_status(self) -> None:
        p = self.ctx.profile
        fuel_pct = p.truck_fuel_gal / 150.0 * 100
        damage = p.truck_damage_pct
        condition = ("excellent" if damage < 5 else "good" if damage < 20
                     else "worn" if damage < 50 else "poor")
        self.ctx.say(f"Fuel {fuel_pct:.0f} percent, {p.truck_fuel_gal:.0f} gallons. "
                     f"Truck condition {condition}, {damage:.0f} percent damage.")

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
        self.ctx.say("Use Quit to main menu to leave the city. Progress is saved automatically.")


class GarageState(MenuState):
    title = "Garage"

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(self._fuel_label, self._refuel,
                     help="Fill the tank at this region's diesel price."),
            MenuItem(self._repair_label, self._repair,
                     help="Restore the truck to full condition."),
            MenuItem("Back", self.go_back),
        ]

    def _region(self) -> str:
        return self.ctx.world.cities[self.ctx.profile.current_city].region

    def _fuel_label(self) -> str:
        p = self.ctx.profile
        need = 150.0 - p.truck_fuel_gal
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
        need = 150.0 - p.truck_fuel_gal
        if need < 1:
            self.ctx.say("The tank is already full.")
            return
        cost = self.ctx.economy.fuel_cost(self._region(), need)
        if p.money < cost:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"Not enough money. You need {cost:,.0f} dollars.")
            return
        p.money -= cost
        p.truck_fuel_gal = 150.0
        self.ctx.audio.play("vehicle/fuel_pump")
        self.ctx.say(f"Tank filled. {cost:,.0f} dollars. "
                     f"You have {p.money:,.0f} dollars left.")
        self.refresh()

    def _repair(self) -> None:
        p = self.ctx.profile
        if p.truck_damage_pct < 1:
            self.ctx.say("Nothing to repair.")
            return
        cost = self.ctx.economy.repair_cost(p.truck_damage_pct)
        if p.money < cost:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"Not enough money. Repairs cost {cost:,.0f} dollars.")
            return
        p.money -= cost
        p.truck_damage_pct = 0.0
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"Truck repaired. {cost:,.0f} dollars. "
                     f"You have {p.money:,.0f} dollars left.")
        self.refresh()


class JobBoardState(MenuState):
    title = "Job board"
    intro_help = ("Each entry is one delivery job. Enter accepts the job and moves on "
                  "to route planning. Escape returns to the city.")

    def __init__(self, ctx, jobs: list[Job]) -> None:
        super().__init__(ctx)
        self.jobs = jobs

    def announce_entry(self) -> None:
        n = len(self.jobs)
        if n == 0:
            self.ctx.say("Job board. No jobs available right now. Press Escape to go back.")
        else:
            self.ctx.say(f"Job board. {n} job{'s' if n != 1 else ''} available. "
                         + self.current_text())

    def build_items(self) -> list[MenuItem]:
        items = []
        for i, job in enumerate(self.jobs):
            items.append(MenuItem(
                job.describe(i + 1, len(self.jobs)),
                lambda j=job: self._accept(j),
                help="From " + job.origin_location + "."))
        items.append(MenuItem("Back to city", self.go_back))
        return items

    def _accept(self, job: Job) -> None:
        p = self.ctx.profile
        if job.cargo.endorsement and job.cargo.endorsement not in p.career.endorsements:
            self.ctx.audio.play("ui/error")
            self.ctx.say("You do not have the endorsement for this cargo yet. "
                         "Keep delivering to level up and unlock it.")
            return
        routes = self.ctx.world.route_options(job.origin, job.destination)
        self.ctx.say(f"Job accepted: {job.cargo.label} to {job.destination}.")
        self.ctx.push_state(RouteSelectState(self.ctx, job, routes))


class RouteSelectState(MenuState):
    title = "Route planning"
    intro_help = ("Pick a route. Shorter routes are faster but may cross mountains. "
                  "Press W on a route to hear the weather forecast along it. "
                  "Enter starts the drive.")

    def __init__(self, ctx, job: Job, routes: list[Route]) -> None:
        super().__init__(ctx)
        self.job = job
        self.routes = routes
        # start fetching live weather for cities on the routes so the data is
        # usually ready by the time the player asks for a forecast
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
            label = f"Route {i + 1}: {route.describe()}"
            items.append(MenuItem(label, lambda r=route: self._start(r),
                                  help="Via " + ", ".join(route.cities[1:-1] or ["no major cities"])))
        items.append(MenuItem("Back to job board", self.go_back))
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

        self.ctx.say(f"Departing {self.job.origin} for {self.job.destination} "
                     f"on {route.highways[0]}. Good luck out there.", interrupt=True)
        self.ctx.push_state(DrivingState(self.ctx, self.job, route))
