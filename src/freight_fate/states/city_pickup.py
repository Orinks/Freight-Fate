# ruff: noqa: F821
"""Pickup facility and route-planning states for terminal dispatches."""

from __future__ import annotations

from ..data.world import Route
from ..models.dispatch_policy import dispatch_policy
from ..models.jobs import Job, job_from_payload, job_payload, plan_hos
from ..music import select_menu_music_sequence
from ..sim.vehicle import TruckState
from .base import MenuItem, MenuState, TimedMessageState

PICKUP_CHECK_IN_MIN = 15.0
PICKUP_LOADING_MIN = 60.0
PICKUP_LOADING_WAIT_S = 1.5


def pickup_snapshot(
    job: Job,
    *,
    checked_in: bool = False,
    loaded: bool = False,
    air_brake: dict | None = None,
    engine_on: bool = False,
) -> dict:
    data = {
        "kind": "pickup",
        "job": job_payload(job),
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
        if route.estimated_tolls > 0
        else "No sourced toll exposure on this itinerary."
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
        if route.estimated_tolls > 0
        else ""
    )
    return (
        f"Loaded trip is {route.miles:.0f} miles via {', then '.join(route.highways)}.{toll_text}"
    )


def start_loaded_drive(
    ctx, job: Job, route: Route, *, air_brake=None, engine_on: bool = False, lead: str = ""
) -> None:
    """Build the loaded delivery trip and depart, narrating ``lead`` first.

    Shared by the player-chosen route path (``RouteSelectState``) and the
    dispatch-assigned route path so air-brake and engine snapshots carry over
    identically on both.
    """
    from .driving import DrivingState

    driving = DrivingState(ctx, job, route)
    driving.truck.restore_air_brake_snapshot(air_brake, default_ready=True)
    if engine_on:
        driving.truck.start_engine()
    ctx.profile.active_trip = driving.snapshot()
    ctx.save_profile()
    next_context = driving.trip.next_navigation_context()
    ctx.say(f"{lead}{route_departure_summary(route)} {next_context} Departing now.", interrupt=True)
    ctx.push_state(driving)


class PickupFacilityState(MenuState):
    title = "Pickup facility"
    open_sound_key = "facility/dock_gate"
    intro_help = (
        "Use up and down arrows to navigate, Enter to select. "
        "Check in at the origin facility, then load cargo only after "
        "the truck is fully stopped. Escape repeats the pickup status."
    )

    def __init__(
        self,
        ctx,
        job: Job,
        *,
        checked_in: bool = False,
        loaded: bool = False,
        driving=None,
        air_brake=None,
        engine_on: bool = False,
    ) -> None:
        super().__init__(ctx)
        self.job = job
        self.checked_in = checked_in
        self.loaded = loaded
        self.driving = driving
        if driving is not None:
            self.truck = driving.truck
        else:
            self.truck = TruckState(specs=ctx.profile.truck_specs())
            self.truck.fuel_gal = min(ctx.profile.truck_fuel_gal, self.truck.specs.fuel_tank_gal)
            self.truck.damage_pct = ctx.profile.truck_damage_pct
            self.truck.restore_air_brake_snapshot(air_brake, default_ready=True)
            if engine_on:
                self.truck.start_engine()

    @classmethod
    def from_snapshot(cls, ctx, data: dict) -> PickupFacilityState | None:
        try:
            return cls(
                ctx,
                job_from_payload(data["job"]),
                checked_in=bool(data.get("checked_in", False)),
                loaded=bool(data.get("loaded", False)),
                air_brake=data.get("air_brake"),
                engine_on=bool(data.get("engine_on", False)),
            )
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
        from ..audio import facility_ambient_key

        self.ctx.audio.set_ambient(facility_ambient_key(self.job.origin_type))
        if self.loaded:
            lead = f"Loaded at {self.facility}. The trailer is sealed for {self.job.destination}."
            if getattr(self, "_just_loaded", False):
                lead += f" Loading took {PICKUP_LOADING_MIN:.0f} minutes."
                self._just_loaded = False
        elif self.checked_in:
            lead = f"Checked in at {self.facility}. You are assigned a dock for loading."
        else:
            lead = (
                f"Arrived at pickup: {self.facility}. Check in with the "
                "shipping office before loading."
            )
        self.ctx.say(f"{lead} {self.current_text()}")

    def exit(self) -> None:
        self.ctx.audio.set_ambient(None)

    def build_items(self) -> list[MenuItem]:
        if self.loaded:
            primary = MenuItem(
                "Depart for destination",
                self._depart_for_destination,
                help="Dispatch loads the navigation itinerary and starts the trip.",
            )
        elif self.checked_in:
            primary = MenuItem(
                "Load cargo at dock",
                self._load,
                help="Back into the assigned dock and wait while the trailer is loaded.",
            )
        else:
            primary = MenuItem(
                "Check in at shipping office",
                self._check_in,
                help="Confirm the pickup number and receive the dock assignment.",
            )
        return [
            primary,
            MenuItem(
                "Pickup status",
                self._status,
                help="Hear the origin facility, cargo, destination, and loading instruction.",
            ),
            MenuItem(
                "Save and quit to main menu",
                self._save_and_quit,
                help="Save this pickup objective so it resumes here later.",
            ),
            MenuItem(
                "Cancel pickup and return to terminal",
                self._cancel,
                help="Give up this job before departure and return to the "
                "terminal dispatch board area.",
            ),
        ]

    def _save_state(self) -> None:
        self.ctx.profile.truck_fuel_gal = self.truck.fuel_gal
        self.ctx.profile.truck_damage_pct = self.truck.damage_pct
        self.ctx.profile.active_trip = pickup_snapshot(
            self.job,
            checked_in=self.checked_in,
            loaded=self.loaded,
            air_brake=self.truck.air_brake_snapshot(),
            engine_on=self.truck.engine_on,
        )
        self.ctx.save_profile()

    def _check_in(self) -> None:
        p = self.ctx.profile
        start = p.game_hours
        p.game_hours += PICKUP_CHECK_IN_MIN / 60.0
        p.duty_log.record(
            "on_duty_not_driving", start, p.game_hours, self.facility, "shipper check-in"
        )
        p.hos.on_duty(PICKUP_CHECK_IN_MIN)
        self.checked_in = True
        self._save_state()
        self.refresh(keep_index=False)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"Checked in at {self.facility}. Dock assigned. Stop, then load cargo.")

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
        self.truck.set_parking_brake()
        self.ctx.push_state(
            TimedMessageState(
                self.ctx,
                title="Loading cargo",
                message=(
                    f"Loading {self.job.weight_tons:.0f} tons of "
                    f"{self.job.cargo.label} at {self.facility}. "
                    "Trailer doors open, dock crew working, brakes set."
                ),
                status="Loading cargo. Please wait.",
                seconds=PICKUP_LOADING_WAIT_S,
                on_complete=self._finish_load,
                sound_key="poi/dock_and_deliver",
            )
        )

    def _finish_load(self) -> None:
        p = self.ctx.profile
        start = p.game_hours
        p.game_hours += PICKUP_LOADING_MIN / 60.0
        p.duty_log.record("on_duty_not_driving", start, p.game_hours, self.facility, "loading")
        p.hos.on_duty(PICKUP_LOADING_MIN)
        self.loaded = True
        self._just_loaded = True
        self._save_state()
        self.ctx.award_achievement("first_pickup")
        self.ctx.pop_state()

    def _depart_for_destination(self) -> None:
        if not self.loaded:
            self.ctx.say("Load the cargo before departing for the destination.")
            return
        routes = self.ctx.world.supported_route_options(self.job.origin, self.job.destination)
        if not routes:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Dispatch cannot find a navigation itinerary for this load.")
            return
        if dispatch_policy(self.ctx.profile).assigns_route:
            # Company drivers run the lane dispatch gives them; routes are
            # already sorted best-first. Route choice is an owner-operator
            # freedom.
            start_loaded_drive(
                self.ctx,
                self.job,
                routes[0],
                air_brake=self.truck.air_brake_snapshot(),
                engine_on=self.truck.engine_on,
                lead=(f"Dispatch routed you to {self.job.destination_facility_text()}. "),
            )
            return
        self.ctx.say(
            f"Route planning to {self.job.destination_facility_text()}. "
            f"{len(routes)} realistic supported route "
            f"option{'s' if len(routes) != 1 else ''} available.",
            interrupt=True,
        )
        self.ctx.push_state(
            RouteSelectState(
                self.ctx,
                self.job,
                routes,
                back_label="Back to pickup facility",
                air_brake=self.truck.air_brake_snapshot(),
                engine_on=self.truck.engine_on,
            )
        )

    def _plan_route(self) -> None:
        self._depart_for_destination()

    def _status(self) -> None:
        state = (
            "loaded and sealed"
            if self.loaded
            else "checked in, waiting to load"
            if self.checked_in
            else "not checked in"
        )
        brake = "parking brake set" if self.truck.parking_brake else "parking brake released"
        self.ctx.say(
            f"Pickup at {self.facility}: {state}. "
            f"Cargo is {self.job.weight_tons:.0f} tons of {self.job.cargo.label}. "
            f"Destination is {self.job.destination_facility_text()}. "
            f"Current speed {self.ctx.settings.speed_text(self.truck.speed_mph)}. "
            f"Air pressure {self.truck.air_pressure_psi:.0f} psi, {brake}."
        )

    def _save_and_quit(self) -> None:
        from .main_menu import MainMenuState

        self._save_state()
        self.ctx.say("Saved. Your pickup objective will resume here.", interrupt=True)
        self.ctx.reset_to(MainMenuState(self.ctx))

    def _cancel(self) -> None:
        from .city import CityMenuState

        self.ctx.profile.active_trip = None
        self.ctx.profile.dispatch_board_cache = None
        self.ctx.save_profile()
        terminal = self.ctx.world.home_terminal(self.ctx.profile.current_city)
        self.ctx.say(f"Pickup canceled. Returned to {terminal.name}.", interrupt=True)
        self.ctx.reset_to(CityMenuState(self.ctx))

    def go_back(self) -> None:
        self._status()

    def lines(self) -> list[str]:
        state = (
            "Loaded and sealed"
            if self.loaded
            else "Checked in"
            if self.checked_in
            else "Check-in required"
        )
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
        ] + [("> " if i == self.index else "  ") + item.text for i, item in enumerate(self.items)]


class RouteSelectState(MenuState):
    title = "Route planning"
    intro_help = (
        "Pick a route. Shorter routes are faster but may cross mountains. "
        "Press W on a route to hear the weather forecast along it. "
        "Enter starts the drive."
    )

    def __init__(
        self,
        ctx,
        job: Job,
        routes: list[Route],
        back_label: str = "Back to dispatch board",
        air_brake=None,
        engine_on: bool = False,
    ) -> None:
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
        self.ctx.say(
            f"Route planning to {self.job.destination}. "
            f"{len(self.routes)} route option{'s' if len(self.routes) != 1 else ''}. "
            + self.current_text()
        )

    def build_items(self) -> list[MenuItem]:
        items = []
        for i, route in enumerate(self.routes):
            label = f"Route {i + 1}: {route.describe()}. {route_planning_summary(route)}"
            items.append(
                MenuItem(
                    label,
                    lambda r=route: self._start(r),
                    help=(
                        "Via "
                        + ", ".join(route.cities[1:-1] or ["no major cities"])
                        + ". Press W for weather."
                    ),
                )
            )
        items.append(MenuItem(self.back_label, self.go_back))
        return items

    def handle_event(self, event) -> None:
        import pygame

        if (
            event.type == pygame.KEYDOWN
            and event.key == pygame.K_w
            and self.index < len(self.routes)
        ):
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
            self.ctx.say(
                "Live weather is still loading. Try again in a moment, or check V while driving."
            )
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
        start_loaded_drive(
            self.ctx,
            self.job,
            route,
            air_brake=self.air_brake,
            engine_on=self.engine_on,
            lead=f"Navigation set for {self.job.destination_facility_text()}. ",
        )
