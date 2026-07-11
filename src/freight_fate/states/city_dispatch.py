"""Dispatch flow: job board, job details, pickup facility, and route planning."""

from __future__ import annotations

import math

from ..data.world import Route
from ..models.jobs import (
    Job,
    facility_text,
    job_from_payload,
    job_payload,
    plan_hos,
    route_drive_hours,
)
from ..music import select_menu_music_sequence
from ..sim.hos import LIMITS
from ..sim.timezones import appointment_text, city_zone
from ..sim.vehicle import TruckState
from .base import MenuItem, MenuState

PICKUP_CHECK_IN_MIN = 15.0
PICKUP_LOADING_MIN = 60.0


def _sleeps_needed(drive_h: float, first_shift_h: float, shift_h: float) -> int:
    """10-hour sleeps required to cover ``drive_h``, given the driving hours
    left in the current shift and full-shift capacity after each sleep."""
    if drive_h <= first_shift_h + 1e-9:
        return 0
    return max(1, math.ceil((drive_h - first_shift_h) / shift_h - 1e-9))


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


class JobBoardState(MenuState):
    title = "Dispatch board"
    intro_help = (
        "Each entry is one dispatch. Enter accepts the dispatch and "
        "creates a local deadhead pickup drive from your terminal to "
        "the named origin facility. Jobs name their origin and "
        "destination facilities, and cargo depends on the facility "
        "type. Tab repeats the freight market watch. Escape returns to "
        "the terminal."
    )

    def __init__(self, ctx, jobs: list[Job]) -> None:
        super().__init__(ctx)
        self.jobs = jobs
        self._confirm_risky_job: Job | None = None

    def announce_entry(self) -> None:
        n = len(self.jobs)
        if n == 0:
            self.ctx.say("Dispatch board. No jobs available right now. Press Escape to go back.")
        else:
            hos_note = self._hos_board_note()
            self.ctx.say(
                f"Dispatch board. {n} dispatch{'es' if n != 1 else ''} available. "
                f"{self.ctx.profile.market.summary()} {hos_note}" + self.current_text()
            )

    def build_items(self) -> list[MenuItem]:
        items = []
        for i, job in enumerate(self.jobs):
            items.append(
                MenuItem(
                    job.describe(i + 1, len(self.jobs)),
                    lambda j=job: self._accept(j),
                    help=(
                        f"Load offer from {job.origin_facility_text()} to "
                        f"{job.destination_facility_text()}. Route inspection after "
                        "pickup covers rest, fuel, toll, weather, and restrictions."
                    ),
                )
            )
        items.append(MenuItem("Back to terminal", self.go_back))
        return items

    def handle_event(self, event) -> None:
        import pygame

        if (
            event.type == pygame.KEYDOWN
            and event.key == pygame.K_F1
            and self.index < len(self.jobs)
        ):
            self.ctx.push_state(JobDetailState(self.ctx, self, self.jobs[self.index]))
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            self.ctx.say(self.ctx.profile.market.summary())
            return
        super().handle_event(event)

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
                f"Hours warning. The hours you have already used this shift mean "
                f"this dispatch needs an extra legal rest that fresh hours would "
                f"avoid. {p.hos.summary(self.ctx.settings.hos_mode)} "
                "Press Enter again to accept it anyway, or sleep first to clear "
                "the warning.",
                interrupt=True,
            )
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
            interrupt=True,
        )
        self.ctx.push_state(driving)
        self.ctx.award_achievement("first_dispatch")

    def _needs_hos_confirmation(self, job: Job) -> bool:
        return self._job_exceeds_current_hos(job) and self._confirm_risky_job is not job

    def _job_exceeds_current_hos(self, job: Job) -> bool:
        """True when hours already spent this shift force an extra 10-hour
        rest the job would not need on a fresh clock. Multi-shift routes
        budget their own sleeps into the deadline, so a rested driver is
        never warned just because the run is long."""
        p = self.ctx.profile
        mode = self.ctx.settings.hos_mode
        if mode not in LIMITS:
            return False
        route = self.ctx.world.supported_route(job.origin, job.destination)
        if route is None:
            return False
        drive_limit, duty_limit, _break_after = LIMITS[mode]
        # Pickup check-in and loading are on-duty work before the first route
        # mile; being over 30 non-driving minutes, they also reset the break
        # clock, so only the drive and duty limits matter here.
        pickup_work_min = PICKUP_CHECK_IN_MIN + PICKUP_LOADING_MIN
        drive_h = route_drive_hours(route, world=self.ctx.world)
        shift_h = drive_limit / 60.0
        fresh_first_h = min(drive_limit, duty_limit - pickup_work_min) / 60.0
        current_first_h = (
            max(
                0.0,
                min(
                    drive_limit - p.hos.driving_min,
                    duty_limit - p.hos.duty_min - pickup_work_min,
                ),
            )
            / 60.0
        )
        return _sleeps_needed(drive_h, current_first_h, shift_h) > _sleeps_needed(
            drive_h, fresh_first_h, shift_h
        )

    def _hos_board_note(self) -> str:
        if not self.jobs:
            return ""
        risky = sum(1 for job in self.jobs if self._job_exceeds_current_hos(job))
        if risky == len(self.jobs):
            return (
                "On your current hours, every listed dispatch would need an "
                "extra legal rest; sleeping first would clear that. "
            )
        if risky:
            return (
                f"On your current hours, {risky} dispatch{'es' if risky != 1 else ''} "
                f"would need an extra legal rest. "
            )
        return ""


class JobDetailState(MenuState):
    title = "Job details"
    intro_help = (
        "Use up and down arrows to review each job detail line; Home and End "
        "jump to the first and last row. Enter repeats detail lines, accepts "
        "when Accept this dispatch is selected, or returns when Back to "
        "dispatch board is selected. Escape also returns to the dispatch board."
    )

    def __init__(self, ctx, board: JobBoardState, job: Job) -> None:
        super().__init__(ctx)
        self.board = board
        self.job = job

    def enter(self) -> None:
        self.items = self.build_items()
        self.index = min(self.index, max(0, len(self.items) - 1))
        self.ctx.audio.play(self.open_sound_key)
        self.announce_entry()

    def announce_entry(self) -> None:
        self.ctx.say(f"Job details. {self.intro_help} {self.current_text()}")

    def current_help(self) -> str:
        return f"{self.intro_help} {super().current_help()}"

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                line,
                lambda line=line: self.ctx.say(line),
                help="This is a job detail line. Press Enter to repeat it.",
            )
            for line in self._detail_lines()
        ]
        locked = self.job.locked_reason(
            self.ctx.profile.career.endorsements, self.ctx.profile.career.level
        )
        if locked:
            items.append(
                MenuItem(
                    f"Cannot accept this dispatch: {locked}",
                    lambda locked=locked: self.ctx.say(locked),
                    help=f"This dispatch is locked. {locked}",
                )
            )
        else:
            items.append(
                MenuItem(
                    "Accept this dispatch",
                    self._accept,
                    help="Accept this dispatch and begin the pickup drive.",
                )
            )
        items.append(
            MenuItem(
                "Back to dispatch board",
                self.go_back,
                help="Return to the dispatch board without accepting this job.",
            )
        )
        return items

    def _accept(self) -> None:
        self.ctx.pop_state()
        self.board._accept(self.job)

    def _detail_lines(self) -> list[str]:
        job = self.job
        p = self.ctx.profile
        world = self.ctx.world
        dollars_per_mile = job.pay / max(job.distance_mi, 1.0)
        # The detail view is the "tell me more" surface, so it always names the
        # state -- board offers stay short, but a player who does not know
        # where Baton Rouge is can open the job and hear "..., Louisiana".
        origin_text = facility_text(
            job.origin_type,
            job.origin_location,
            world.spoken_city(job.origin, qualified=True),
            job.origin_locality,
        )
        destination_text = facility_text(
            job.destination_type,
            job.destination_location,
            world.spoken_city(job.destination, qualified=True),
            job.destination_locality,
        )
        lines = [
            f"Cargo: {job.cargo.label}.",
            f"Origin: {origin_text}.",
            f"Destination: {destination_text}.",
            f"Distance: {job.distance_mi:.0f} miles.",
            f"Pay: {job.pay:,.0f} dollars.",
            f"Dollars per mile: {dollars_per_mile:.2f}.",
            # The appointment reads in the receiver's local time, the way real
            # dispatch quotes it. "About" because the clock starts at pickup
            # departure, after check-in and loading.
            f"Deadline: {job.deadline_game_h:.0f} hours; deliver by about "
            f"{appointment_text(p.game_hours, job.deadline_game_h, city_zone(world.city(job.destination)))}.",
            f"Equipment: {job.equipment_text()}.",
        ]
        locked = job.locked_reason(p.career.endorsements, p.career.level)
        if locked:
            lines.append(f"Locked: {locked}")
        elif job.cargo.endorsement:
            lines.append(f"Endorsement: {job.cargo.endorsement.replace('_', ' ')}.")
        lines.append("Route details happen after pickup: rest, fuel, tolls, weather, and stops.")
        return lines


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
        return PresenceState(activity, f"{self.job.cargo.label} for {self.job.spoken_destination}")

    def enter(self) -> None:
        sequence = select_menu_music_sequence(self.ctx.profile)
        self.ctx.play_music_sequence("menu", sequence)
        super().enter()

    def announce_entry(self) -> None:
        self.ctx.audio.set_ambient("poi/facility_gate")
        if self.loaded:
            lead = (
                f"Loaded at {self.facility}. The trailer is sealed for "
                f"{self.job.spoken_destination}."
            )
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
        p.game_hours += PICKUP_CHECK_IN_MIN / 60.0
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
            f"ready for {self.job.spoken_destination}. Loading took "
            f"{PICKUP_LOADING_MIN:.0f} minutes. Depart when ready."
        )

    def _depart_for_destination(self) -> None:
        if not self.loaded:
            self.ctx.say("Load the cargo before departing for the destination.")
            return
        routes = self.ctx.world.supported_route_options(self.job.origin, self.job.destination)
        if not routes:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Dispatch cannot find a navigation itinerary for this load.")
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
        MainMenuState.arm_update_check(self.ctx.settings)
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
            f"Destination: {self.job.spoken_destination}",
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
                    provider.request(city.key, city.lat, city.lon)

    def announce_entry(self) -> None:
        self.ctx.say(
            f"Route planning to {self.job.spoken_destination}. "
            f"{len(self.routes)} route option{'s' if len(self.routes) != 1 else ''}. "
            + self.current_text()
        )

    def _via_text(self, route: Route) -> str:
        """The cities a route passes through, state-qualified so an unknown
        town still points the compass ("McCall, Idaho": ah, we head north).
        Long chains are capped for speech; F1 help reads the full list."""
        vias = [self.ctx.world.spoken_city(n, qualified=True) for n in route.cities[1:-1]]
        if not vias:
            return "passing no major cities"
        if len(vias) > 3:
            return f"through {', '.join(vias[:3])}, and {len(vias) - 3} more"
        return f"through {', '.join(vias)}"

    def build_items(self) -> list[MenuItem]:
        items = []
        for i, route in enumerate(self.routes):
            label = (
                f"Route {i + 1}: {route.describe()}, {self._via_text(route)}. "
                f"{route_planning_summary(route)}"
            )
            items.append(
                MenuItem(
                    label,
                    lambda r=route: self._start(r),
                    help=(
                        "Via "
                        + ", ".join(
                            [
                                self.ctx.world.spoken_city(n, qualified=True)
                                for n in route.cities[1:-1]
                            ]
                            or ["no major cities"]
                        )
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
                    parts.append(
                        f"{self.ctx.world.spoken_city(name, qualified=True)}: {kind.value}"
                    )
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
            interrupt=True,
        )
        self.ctx.push_state(driving)
