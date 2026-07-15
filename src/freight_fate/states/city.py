"""Terminal hub: dispatch board, garage, upgrades, trucks, and route selection."""

from __future__ import annotations

import math
import zlib

from ..models.business import (
    INDEPENDENT_AUTHORITY,
    build_business_settlement,
    carrier_name,
    is_owner_operator,
    pay_label,
    status_label,
)
from ..models.career_objectives import career_objective
from ..models.career_training import (
    TrainingStage,
    is_company_training_profile,
    training_guidance,
    training_recommendation_score,
)
from ..models.dispatch_policy import (
    DECLINE_REPUTATION_PENALTY,
    SENIOR_LOAD_CHOICE_LEVEL,
    declines_remaining,
    dispatch_policy,
)
from ..models.economy import (
    pay_advance_grant,
    pay_advance_unavailable_reason,
)
from ..models.jobs import (
    CARGO_CATALOG,
    Job,
    JobBoard,
    board_offer_count,
    facility_text,
    job_from_payload,
    job_payload,
    normalize_job_cities,
    route_drive_hours,
)
from ..models.start_options import option_for_profile
from ..models.trailers import (
    compatible_with_programs,
    owned_trailer_for_cargo,
    required_program_text,
)
from ..models.trucks import TRUCK_CATALOG
from ..music import select_menu_music_sequence
from ..playtest_levers import forced_dispatch_destination
from ..sim.hos import LIMITS, clock_text, time_of_day
from ..sim.timezones import appointment_text, city_zone, to_local
from .base import MenuItem, MenuState
from .career_stats import CareerStatsState, fully_rested
from .city_garage import GarageState
from .city_pickup import (  # noqa: F401
    PICKUP_CHECK_IN_MIN,
    PICKUP_LOADING_MIN,
    PickupFacilityState,
    RouteSelectState,
    pickup_snapshot,
    route_planning_summary,
)


def _record_city_duty(ctx, status: str, start_hour: float, end_hour: float, note: str = "") -> None:
    p = ctx.profile
    if p is None:
        return
    terminal = ctx.world.home_terminal(p.current_city)
    p.duty_log.record(status, start_hour, end_hour, terminal.name, note)


def _sleeps_needed(drive_h: float, first_shift_h: float, shift_h: float) -> int:
    """10-hour sleeps required to cover ``drive_h``, given the driving hours
    left in the current shift and full-shift capacity after each sleep."""
    if drive_h <= first_shift_h + 1e-9:
        return 0
    return max(1, math.ceil((drive_h - first_shift_h) / shift_h - 1e-9))


def _job_payload(job: Job) -> dict:
    return job_payload(job)


def _job_from_payload(data: dict) -> Job:
    return job_from_payload(data)


# Empty-drive range for shopping another city's board.
BOBTAIL_RANGE_MI = 400.0


def first_dispatch_done(profile) -> bool:
    return "first_dispatch" in getattr(profile, "achievements", ())


def first_day_guidance_active(profile) -> bool:
    deliveries = int(getattr(profile.career, "deliveries", 0))
    return not first_dispatch_done(profile) and deliveries <= 0


def first_day_orientation_message(ctx, prefix: str = "") -> str:
    p = ctx.profile
    terminal = ctx.world.home_terminal(p.current_city)
    option = option_for_profile(p)
    location = f"{terminal.spoken_name} in the {p.current_city} service area"
    if option.is_owner_operator:
        return (
            f"{prefix}First-day briefing: you are leased to {option.carrier_name} "
            f"and parked at {location}. You own the starter tractor, have "
            f"{p.money:,.0f} dollars of working capital, and fuel, repairs, "
            "truck wear, trailer programs, and business reserves come out of "
            "your cash. Your first objective is to open the dispatch board, "
            "choose an unlocked load with a deadline you can protect, and get "
            "to the shipper without burning your cushion."
        )
    return (
        f"{prefix}First-day briefing: welcome aboard {option.carrier_name}. "
        f"Your assigned company tractor is parked at {location}; the carrier "
        "covers normal fuel, repairs, insurance, and trailer support. Your "
        f"starter dispatch style is {option.dispatch.summary()}. As a new "
        "hire, dispatch assigns your load and your route; you earn load "
        "choice with seniority, and refusing an assignment goes on your "
        "service record. Your first objective is to open the dispatch "
        "board, accept the assigned load, deadhead to the shipper, and "
        "deliver cleanly to start building your record with dispatch."
    )


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

    # Moving off the Sleep item withdraws its pending double-press
    # confirmation, so a stale "press Enter again" can never sleep you
    # silently later.
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
        business = status_label(p.business_status)
        rank = p.career.rank
        first_day = ""
        if first_day_guidance_active(p):
            guidance = training_guidance(p) if is_company_training_profile(p) else None
            if guidance is not None and guidance.stage is TrainingStage.FIRST_DISPATCH:
                first_day = (
                    " First-day objective: open the dispatch board and accept "
                    f"your assigned {guidance.recommendation_label} load. "
                    "Dispatch assigns both load and route while you are a "
                    "new hire."
                )
            elif not is_company_training_profile(p):
                first_day = (
                    " First-day objective: open the dispatch board and choose "
                    "an unlocked load without burning your cash cushion."
                )
            else:
                objective = career_objective(p)
                first_day = (
                    f" Career objective: {objective.terminal_text} "
                    f"Recommended dispatch: {objective.recommendation}."
                )
        elif not first_dispatch_done(p) and is_company_training_profile(p):
            objective = career_objective(p)
            first_day = (
                f" Career objective: {objective.terminal_text} "
                f"Recommended dispatch: {objective.recommendation}."
            )
        else:
            first_day = f" Career objective: {career_objective(p).terminal_text}"
        self.ctx.say(
            f"Parked at {terminal.spoken_name} in the {city.name} "
            f"service area, {city.state}. {business.capitalize()} with "
            f"level {rank.level}, {rank.title}. "
            f"You have {p.money:,.0f} dollars. "
            f"{first_day} {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                "Dispatch board",
                self._job_board,
                help="Open terminal dispatches from local freight "
                "facilities, including ports, warehouses, food "
                "terminals, intermodal yards, and distribution hubs. "
                "New company hires get dispatch's assigned load; load "
                "choice from the board opens with seniority.",
            ),
            MenuItem(
                "Drive to city services",
                self._city_services,
                help="Drive through the local service area to the garage, "
                "truck dealer, or freight market office. Stop at the "
                "destination, then press Enter to go inside.",
            ),
            MenuItem(
                "Bobtail to a nearby city",
                self._bobtail,
                help="Drive empty to a nearby city to see its dispatch "
                "board. Costs fuel and hours of service; no load, no "
                "pay. Use it when local freight is thin.",
            ),
            MenuItem(
                self._garage_label,
                self._garage,
                help="Refuel and repair the active tractor at the terminal garage. "
                "Company drivers use carrier-assigned equipment and the carrier account. "
                "Owner-operators pay their own fuel and repairs.",
            ),
            MenuItem(
                "Business status",
                self._business_status,
                help="Review your carrier, rank, next business unlock, "
                "and owner-operator buy-in when qualified.",
            ),
            MenuItem(
                "Career stats",
                self._stats,
                help="Review your level, reputation, lifetime numbers, and "
                "rest status, one line at a time.",
            ),
            MenuItem(
                "Endorsement courses",
                self._endorsement_courses,
                help="Pay for endorsement training yourself to unlock "
                "refrigerated, heavy-haul, or high-value freight before "
                "the carrier sponsors it at the listed level.",
            ),
            MenuItem(
                "Truck status",
                self._truck_status,
                help="Hear assigned or owned tractor status at a glance.",
            ),
            MenuItem(
                "Time and weather",
                self._time_weather,
                help="Hear the clock, the day of your career, and the conditions outside.",
            ),
            MenuItem(
                "Logbook", self._logbook, help="Review your recent Record of Duty Status entries."
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
        if self._show_first_day_briefing():
            items.insert(
                1,
                MenuItem(
                    "First-day briefing",
                    self._first_day_briefing,
                    help="Repeat your starter carrier, terminal, business costs, "
                    "and first dispatch objective.",
                ),
            )
        else:
            items.insert(
                1,
                MenuItem(
                    "Career plan",
                    self._career_plan,
                    help="Review the next practical career objective and how it "
                    "should shape dispatch choices.",
                ),
            )
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

    def _show_first_day_briefing(self) -> bool:
        p = self.ctx.profile
        if not first_day_guidance_active(p):
            return False
        if not is_company_training_profile(p):
            return True
        return training_guidance(p).stage is TrainingStage.FIRST_DISPATCH

    def _first_day_briefing(self) -> None:
        self.ctx.say(first_day_orientation_message(self.ctx), interrupt=True)

    def _career_plan(self) -> None:
        self.ctx.say(career_objective(self.ctx.profile).spoken_summary, interrupt=True)

    def _city_services(self) -> None:
        self.ctx.push_state(CityServiceSelectState(self.ctx))

    def _job_board(self) -> None:
        open_freight_market(self.ctx)

    def _dispatch_cache_key(self) -> dict:
        p = self.ctx.profile
        return dispatch_cache_key(p)

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

    def _business_status(self) -> None:
        self.ctx.push_state(BusinessStatusState(self.ctx))

    def _endorsement_courses(self) -> None:
        self.ctx.push_state(EndorsementCourseState(self.ctx))

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
        truck = TRUCK_CATALOG.get(p.active_truck_key(), TRUCK_CATALOG["rig"])
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
        if not p.owns_equipment():
            lead = f"Assigned {carrier_name(p)} tractor: {truck.label}."
        else:
            lead = f"Owned tractor: {truck.label}."
        compound = "winter" if p.tire_type == "winter" else "all-season"
        if not p.chains_owned:
            chains = "No snow chains aboard."
        elif p.chain_wear_pct >= 100:
            chains = "The snow chain set aboard is snapped scrap."
        elif p.chain_wear_pct >= 1:
            chains = f"Snow chains aboard, {p.chain_wear_pct:.0f} percent worn."
        else:
            chains = "Snow chains aboard and fresh."
        self.ctx.say(
            f"{lead} Fuel {fuel_pct:.0f} percent, "
            f"{p.truck_fuel_gal:.0f} gallons of "
            f"{specs.fuel_tank_gal:.0f}. "
            f"Tractor condition {condition}, {damage:.0f} percent damage. "
            f"Tire wear {p.tire_wear_pct:.0f} percent, {compound} compound. "
            f"Brake wear {p.brake_wear_pct:.0f} percent. "
            f"Engine wear {p.engine_wear_pct:.0f} percent. "
            f"Road grime {p.road_grime_pct:.0f} percent. "
            f"{chains}"
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
        start = p.game_hours
        p.game_hours += 10.0
        _record_city_duty(self.ctx, "sleeper_berth", start, p.game_hours, "terminal sleep")
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

    def _logbook(self) -> None:
        from .logbook import LogbookState

        self.ctx.push_state(LogbookState(self.ctx))

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


def dispatch_cache_key(p) -> dict:
    return {
        "city": p.current_city,
        "market_day": p.market_day(),
        "market_seed": p.market.seed,
        "market_state_day": p.market.day,
        "business_status": p.business_status,
        "carrier_key": getattr(p, "carrier_key", ""),
        "authority_readiness": bool(getattr(p, "authority_readiness", False)),
        "trailer_programs": sorted(getattr(p, "trailer_programs", ())),
        "level": p.career.level,
        "endorsements": sorted(p.career.endorsements),
        "count": board_offer_count(p.career.level),
        "force_dest": forced_dispatch_destination(),
    }


def open_freight_market(ctx) -> list[Job]:
    p = ctx.profile
    board = JobBoard(ctx.world)
    market_changed = p.market.advance_to(p.market_day())
    key = dispatch_cache_key(p)
    cache = p.dispatch_board_cache if not market_changed else None
    lever_note = ""
    if cache and cache.get("key") == key:
        # Cached payloads may predate the slug migration; normalize their
        # city references so a restored board keeps resolving.
        jobs = [
            normalize_job_cities(_job_from_payload(payload), ctx.world)
            for payload in cache.get("jobs", [])
        ]
    else:
        jobs = board.offers(
            p.current_city,
            p.career.endorsements,
            count=board_offer_count(p.career.level),
            level=p.career.level,
            market=p.market,
            carrier_key=getattr(p, "carrier_key", ""),
            direct_freight=p.business_status == INDEPENDENT_AUTHORITY,
        )
        lever_note = _add_forced_board_job(ctx, board, jobs)
        p.dispatch_board_cache = {
            "key": key,
            "jobs": [_job_payload(job) for job in jobs],
        }
        ctx.save_profile()
    ctx.push_state(JobBoardState(ctx, jobs))
    if lever_note:
        # Queued behind the board announcement, which interrupts.
        ctx.say(lever_note, interrupt=False)
    return jobs


def _add_forced_board_job(ctx, board: JobBoard, jobs: list[Job]) -> str:
    """FREIGHT_FATE_FORCE_DEST playtest lever: guarantee one load to the
    forced destination on a freshly built board. Returns the spoken note."""
    dest = forced_dispatch_destination()
    if not dest:
        return ""
    p = ctx.profile
    key = ctx.world.resolve_city_key(dest)
    if key not in ctx.world.cities:
        return f"Playtest lever: no city called {dest} to dispatch to."
    if key == ctx.world.resolve_city_key(p.current_city):
        return ""
    spoken = ctx.world.spoken_city(key, qualified=True)
    if any(ctx.world.resolve_city_key(job.destination) == key for job in jobs):
        return f"Playtest lever: the board already offers {spoken}."
    job = board.offer_to(
        p.current_city,
        key,
        p.career.endorsements,
        market=p.market,
        level=p.career.level,
        carrier_key=getattr(p, "carrier_key", ""),
        direct_freight=p.business_status == INDEPENDENT_AUTHORITY,
    )
    if job is None:
        return f"Playtest lever: no supported dispatch from here to {spoken}."
    jobs.append(job)
    jobs.sort(key=lambda j: j.distance_mi)
    return f"Playtest lever: added a load to {spoken} to the board."


class CityServiceSelectState(MenuState):
    title = "City services"
    intro_help = (
        "Pick a city service to drive to. The GPS gives local guidance. "
        "Stop at the destination, then press Enter to go inside."
    )

    def announce_entry(self) -> None:
        city = self.ctx.profile.current_city
        self.ctx.say(f"{city} services. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items = []
        for service in self.ctx.world.city_services(self.ctx.profile.current_city):
            route = self.ctx.world.city_service_route(service.city, service.key)
            items.append(
                MenuItem(
                    f"{service.name}: {route.miles:.1f} miles",
                    lambda key=service.key: self._start(key),
                    help=(
                        f"Drive to {service.spoken_name}. "
                        "The destination opens only after you stop and press Enter."
                    ),
                )
            )
        items.append(MenuItem("Back to terminal", self.go_back))
        return items

    def _start(self, service_key: str) -> None:
        from .driving import DRIVE_PHASE_CITY_SERVICE, DrivingState

        p = self.ctx.profile
        service = self.ctx.world.city_service(p.current_city, service_key)
        route = self.ctx.world.city_service_route(p.current_city, service_key)
        terminal = self.ctx.world.home_terminal(p.current_city)
        job = Job(
            CARGO_CATALOG["general"],
            0.0,
            p.current_city,
            terminal.name,
            p.current_city,
            route.miles,
            0.0,
            24.0,
            origin_type=terminal.kind,
            destination_location=service.name,
            destination_type=service.kind,
            bobtail=True,
        )
        driving = DrivingState(
            self.ctx,
            job,
            route,
            phase=DRIVE_PHASE_CITY_SERVICE,
            city_service_key=service.key,
        )
        p.active_trip = driving.snapshot()
        self.ctx.save_profile()
        self.ctx.say(
            f"GPS set for {service.spoken_name}, {route.miles:.1f} miles on "
            f"{route.highways[0]}. Stop there, then press Enter to go inside.",
            interrupt=True,
        )
        self.ctx.push_state(driving)

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()


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
                    help=f"Drive empty to {world.spoken_city(name)} to see its dispatch board.",
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


from .city_business import (  # noqa: E402,F401
    BusinessStatusState,
    EndorsementCourseState,
    TrailerProgramState,
    TruckShopState,
    UpgradeShopState,
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
        self._session_declined: set[int] = set()
        self._assigned_queue: list[int] = (
            self._assignment_queue() if dispatch_policy(ctx.profile).assigns_load else []
        )
        if self.assigned_mode:
            self.intro_help = (
                "Dispatch assigned this load. Enter on the assignment accepts "
                "it and creates a local deadhead pickup drive from your "
                "terminal to the named origin facility. Declining draws "
                "another load, but refusals cost reputation from a small "
                "budget that refills at your next promotion. Press F1 on the "
                "assignment to review the job details line by line. Escape "
                "returns to the terminal."
            )
        else:
            recommended = self._recommended_job_index()
            if recommended is not None and self._recommendation_label() is not None:
                self.index = recommended

    @property
    def assigned_mode(self) -> bool:
        """Dispatch picks the load: new company hires get an assignment,
        not a browsable board. Falls back to browsing when nothing on the
        board is unlocked, so the player can still hear what is there."""
        return bool(self._assigned_queue)

    def announce_entry(self) -> None:
        n = len(self.jobs)
        if n == 0:
            self.ctx.say("Dispatch board. No jobs available right now. Press Escape to go back.")
        elif self.assigned_mode:
            self._announce_assignment()
        else:
            status = self.ctx.profile.business_status
            if status == INDEPENDENT_AUTHORITY:
                business_note = (
                    "Listed amounts are direct freight gross. Insurance, "
                    "compliance, trailer, truck, and factoring costs come out "
                    "at settlement. "
                )
            elif is_owner_operator(status):
                business_note = (
                    "Listed amounts are owner-operator gross revenue. Trailer "
                    "program needs are listed on each job. "
                )
            else:
                business_note = (
                    "Listed amounts are carrier gross; your settlement pays "
                    "driver wages. Dispatch trusts you to pick your own "
                    "loads now; routing is still assigned until you run "
                    "your own truck. "
                )
            objective_text = ""
            training_label = self._training_recommendation_label()
            if training_label is not None:
                guidance = training_guidance(self.ctx.profile)
                objective_text = (
                    f"First-day objective: pick a {training_label} load. {guidance.dispatch_text} "
                )
            elif first_day_guidance_active(self.ctx.profile) and not is_company_training_profile(
                self.ctx.profile
            ):
                objective_text = (
                    "First-day objective: pick an unlocked load with a "
                    "deadline you can protect. Keep fuel, repairs, and "
                    "your cash cushion in mind. "
                )
            else:
                objective = career_objective(self.ctx.profile)
                recommendation = (
                    ""
                    if self._focused_recommendation_is_spoken()
                    else f"Recommended dispatch: {objective.recommendation}. "
                )
                objective_text = (
                    f"Career objective: {objective.title}. "
                    f"{objective.dispatch_text} "
                    f"{recommendation}"
                )
            self.ctx.say(
                f"Dispatch board. {n} dispatch{'es' if n != 1 else ''} available. "
                f"{business_note}{objective_text}"
                f"{self._hos_board_note()}"
                f"{self.ctx.profile.market.summary()} " + self.current_text()
            )

    def _announce_assignment(self) -> None:
        p = self.ctx.profile
        remaining = declines_remaining(p)
        if len(self._assigned_queue) < 2:
            decline_note = "No alternative freight is available to request."
        elif remaining > 0:
            decline_note = (
                f"You can decline {remaining} more assigned "
                f"load{'s' if remaining != 1 else ''} before your next "
                "promotion, but refusals cost standing with dispatch."
            )
        else:
            decline_note = (
                "You are out of declines until your next promotion, so "
                "dispatch expects you to run this load."
            )
        training_label = self._training_recommendation_label()
        if training_label is not None:
            objective_text = (
                f"First-day objective: run this {training_label} load "
                "cleanly to start building your record with dispatch. "
            )
        else:
            objective_text = f"Career objective: {career_objective(p).title}. "
        hos_note = (
            "This assignment may need a legal rest before delivery; you will "
            "get an hours warning at accept. "
            if self._job_exceeds_current_hos(self._assigned_job())
            else ""
        )
        self.ctx.say(
            "Dispatch board. Dispatch assigns your load and route while you "
            "are a new company hire; load choice opens at level "
            f"{SENIOR_LOAD_CHOICE_LEVEL}. Listed amounts are carrier gross; "
            f"your settlement pays driver wages. {objective_text}"
            f"{decline_note} {hos_note}{p.market.summary()} " + self.current_text()
        )

    def build_items(self) -> list[MenuItem]:
        if self.assigned_mode:
            return self._build_assignment_items()
        items = []
        for i, job in enumerate(self.jobs):
            locked = self._locked_reason(job)
            label = self._job_label(job, i + 1)
            if locked:
                label = label.replace("Job ", "Locked job ", 1)
            items.append(
                MenuItem(
                    label,
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

    def _build_assignment_items(self) -> list[MenuItem]:
        job = self._assigned_job()
        items = [
            MenuItem(
                f"Accept assigned dispatch: {self._describe_job(job)}",
                lambda j=job: self._accept(j),
                help=(
                    "Dispatch assigned this load; new hires run the load and "
                    "lane dispatch picks. Accepting creates a local deadhead "
                    "pickup drive from your terminal to the named origin "
                    "facility. Route inspection after pickup covers rest, fuel, "
                    "toll, weather, and restrictions."
                ),
            )
        ]
        remaining = declines_remaining(self.ctx.profile)
        if len(self._assigned_queue) > 1 and remaining > 0:
            items.append(
                MenuItem(
                    f"Decline and request another load: "
                    f"{remaining} decline{'s' if remaining != 1 else ''} left",
                    self._decline_assignment,
                    help=(
                        "Turn the assigned load down and let dispatch draw "
                        "another. Refusals cost reputation, and the decline "
                        "budget only refills when you reach the next level."
                    ),
                )
            )
        items.append(MenuItem("Back to terminal", self.go_back))
        return items

    def _assigned_job(self) -> Job:
        return self.jobs[self._assigned_queue[0]]

    def _declined_indices(self) -> set[int]:
        """Board indices dispatch already re-drew past, remembered with the
        cached board so leaving and reopening does not re-offer them."""
        declined = set(self._session_declined)
        cache = getattr(self.ctx.profile, "dispatch_board_cache", None)
        if isinstance(cache, dict):
            for index in cache.get("declined", ()):
                if isinstance(index, int | float):
                    declined.add(int(index))
        return declined

    def _remember_decline(self, index: int) -> None:
        self._session_declined.add(index)
        cache = getattr(self.ctx.profile, "dispatch_board_cache", None)
        if isinstance(cache, dict):
            declined = [int(i) for i in cache.get("declined", ()) if isinstance(i, int | float)]
            if index not in declined:
                declined.append(index)
            cache["declined"] = declined

    def _decline_assignment(self) -> None:
        p = self.ctx.profile
        if declines_remaining(p) <= 0:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "Dispatch has no patience left for refusals. Run this load; "
                "declines refill at your next promotion."
            )
            return
        p.career.dispatch_declines_used += 1
        p.career.reputation = max(0.0, p.career.reputation - DECLINE_REPUTATION_PENALTY)
        self._remember_decline(self._assigned_queue[0])
        self._assigned_queue = self._assignment_queue()
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.refresh(keep_index=False)
        remaining = declines_remaining(p)
        note = (
            f"You have {remaining} decline{'s' if remaining != 1 else ''} left."
            if remaining > 0
            else "That was your last decline until your next promotion."
        )
        self.ctx.say(
            "Load declined. The refusal goes on your service record with "
            f"dispatch. {note} New assignment: "
            f"{self._describe_job(self._assigned_job())}",
            interrupt=True,
        )

    def _describe_job(self, job: Job, index: int | None = None) -> str:
        p = self.ctx.profile
        business = build_business_settlement(
            p.business_status,
            job,
            job.pay,
            on_time=True,
            driver_charges=0.0,
            carrier_key=getattr(p, "carrier_key", ""),
            owned_trailers=p.visible_owned_trailers(),
            reputation=p.career.reputation,
        )
        return job.describe(
            index,
            len(self.jobs) if index is not None else None,
            pay_label=pay_label(p.business_status),
            trailer_note=self._trailer_note(job),
            display_pay=business.gross_pay,
            market_preview=self._market_preview(business),
        )

    def _job_label(self, job: Job, index: int) -> str:
        label = self._describe_job(job, index)
        if self._recommended_job_index() == index - 1:
            recommendation = self._recommendation_label()
            if recommendation is None:
                return label
            label = f"Recommended dispatch, {recommendation}: {label}"
        return label

    def _recommendation_label(self) -> str | None:
        training_label = self._training_recommendation_label()
        if training_label is not None:
            return training_label
        if first_dispatch_done(self.ctx.profile):
            return career_objective(self.ctx.profile).recommendation
        if is_company_training_profile(self.ctx.profile):
            return career_objective(self.ctx.profile).recommendation
        return None

    def _training_recommendation_label(self) -> str | None:
        p = self.ctx.profile
        if not is_company_training_profile(p):
            return None
        guidance = training_guidance(p)
        if guidance.stage is TrainingStage.FIRST_DISPATCH and not first_dispatch_done(p):
            return guidance.recommendation_label
        return None

    def _focused_recommendation_is_spoken(self) -> bool:
        return (
            self._recommendation_label() is not None and self._recommended_job_index() == self.index
        )

    def _scored_candidates(self) -> list[tuple[float, int]]:
        """(score, index) for each unlocked job; lower scores fit better."""
        p = self.ctx.profile
        candidates: list[tuple[float, int]] = []
        for index, job in enumerate(self.jobs):
            if self._locked_reason(job):
                continue
            if is_owner_operator(p.business_status):
                business = build_business_settlement(
                    p.business_status,
                    job,
                    job.pay,
                    on_time=True,
                    driver_charges=0.0,
                    carrier_key=getattr(p, "carrier_key", ""),
                    owned_trailers=p.visible_owned_trailers(),
                )
                candidates.append((-business.net_before_advance, index))
            else:
                if training_guidance(p).stage is not TrainingStage.NORMAL_GUIDANCE:
                    candidates.append((training_recommendation_score(p, job), index))
                else:
                    candidates.append((job.distance_mi, index))
        return candidates

    def _recommended_job_index(self) -> int | None:
        candidates = self._scored_candidates()
        if not candidates:
            return None
        return min(candidates)[1]

    def _assignment_queue(self) -> list[int]:
        """Unlocked jobs in the order dispatch would assign them, best first.

        Declined loads move to the back: dispatch re-offers them only after
        the fresh candidates run out, and reopening the board does not put a
        refused load straight back on the driver."""
        ordered = [index for _score, index in sorted(self._scored_candidates())]
        declined = self._declined_indices()
        fresh = [index for index in ordered if index not in declined]
        reoffered = [index for index in ordered if index in declined]
        queue = fresh + reoffered
        forced = forced_dispatch_destination()
        if forced and queue:
            # Playtest lever: dispatch assigns the forced-destination load
            # first, so a tester is not stuck with pot luck.
            key = self.ctx.world.resolve_city_key(forced)
            for i, index in enumerate(queue):
                if self.ctx.world.resolve_city_key(self.jobs[index].destination) == key:
                    queue.insert(0, queue.pop(i))
                    break
        return queue

    def _locked_reason(self, job: Job) -> str:
        p = self.ctx.profile
        return job.locked_reason(
            p.career.endorsements,
            p.career.level,
            trailer_programs=p.active_trailer_programs(),
            carrier_trailer_support=not is_owner_operator(p.business_status),
        )

    def _market_preview(self, business) -> str:
        if business.business_charge_total > 0:
            return (
                f"Estimated take-home before advances: "
                f"{business.net_before_advance:,.0f} dollars after "
                f"{business.business_charge_total:,.0f} dollars business costs."
            )
        return f"Estimated driver pay before advances: {business.net_before_advance:,.0f} dollars."

    def handle_event(self, event) -> None:
        import pygame

        if event.type == pygame.KEYDOWN and event.key == pygame.K_F1 and self.jobs:
            job = self._focused_job()
            if job is not None:
                self.ctx.push_state(JobDetailState(self.ctx, self, job))
                return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            self.ctx.say(self.ctx.profile.market.summary())
            return
        super().handle_event(event)

    def _focused_job(self) -> Job | None:
        """The job the current menu row refers to, in either board mode."""
        if self.assigned_mode:
            return self._assigned_job() if self.index == 0 else None
        if self.index < len(self.jobs):
            return self.jobs[self.index]
        return None

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

    def _accept(self, job: Job) -> None:
        p = self.ctx.profile
        locked = self._locked_reason(job)
        if locked:
            self.ctx.audio.play("ui/error")
            if "trailer program" in locked:
                if p.business_status == INDEPENDENT_AUTHORITY:
                    self.ctx.say(
                        f"{locked} Open Garage, Trailers to lease support or "
                        "buy a matching trailer."
                    )
                else:
                    self.ctx.say(f"{locked} Open Garage, Trailers to add it.")
            else:
                self.ctx.say(
                    f"{locked} Keep delivering to level up, or book the "
                    "endorsement course at the terminal."
                )
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

        try:
            route = self.ctx.world.facility_approach_route(job.origin, job.origin_location)
        except KeyError:
            # A cached board can outlive its facilities (a data update may
            # retire one, e.g. a template gated out by geography). Drop the
            # dead offer instead of crashing; the next board visit rebuilds.
            p.dispatch_board_cache = None
            self.jobs = [j for j in self.jobs if j is not job]
            self._assigned_queue = (
                self._assignment_queue() if dispatch_policy(p).assigns_load else []
            )
            self.refresh(keep_index=False)
            self.ctx.audio.play("ui/warning")
            self.ctx.say(
                "That load's facility is no longer on the network. Dispatch "
                "pulled the offer; the board will refresh with new loads.",
                interrupt=True,
            )
            return
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

    def _trailer_note(self, job: Job) -> str:
        p = self.ctx.profile
        if not is_owner_operator(p.business_status):
            return "Carrier trailer provided."
        if p.business_status == INDEPENDENT_AUTHORITY:
            owned = owned_trailer_for_cargo(job.cargo.key, p.visible_owned_trailers())
            if owned is not None:
                return (
                    f"Owned trailer: {owned.label}. Direct freight gross; "
                    "owned-trailer reserve at settlement."
                )
            if compatible_with_programs(job.cargo.key, p.active_trailer_programs()):
                return (
                    f"Trailer program: {required_program_text(job.cargo.key)}. "
                    "Direct freight gross; program charge at settlement."
                )
            return f"Needs {required_program_text(job.cargo.key)} trailer program or owned trailer."
        if compatible_with_programs(job.cargo.key, p.active_trailer_programs()):
            return f"Trailer program: {required_program_text(job.cargo.key)}."
        return f"Needs {required_program_text(job.cargo.key)} trailer program."


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
        locked = self.board._locked_reason(self.job)
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
        business = build_business_settlement(
            p.business_status,
            job,
            job.pay,
            on_time=True,
            driver_charges=0.0,
            carrier_key=getattr(p, "carrier_key", ""),
            owned_trailers=p.visible_owned_trailers(),
            reputation=p.career.reputation,
        )
        dollars_per_mile = business.gross_pay / max(job.distance_mi, 1.0)
        world = self.ctx.world
        # The detail view is the "tell me more" surface, so it always names the
        # state -- board offers stay short, but a player who does not know
        # where Baton Rouge is can open the job and hear "..., Louisiana".
        destination_text = facility_text(
            job.destination_type,
            job.destination_location,
            world.spoken_city(job.destination, qualified=True),
            job.destination_locality,
        )
        lines = [
            f"Cargo: {job.cargo.label}.",
            f"Origin: {job.origin_facility_text()}.",
            f"Destination: {destination_text}.",
            f"Distance: {job.distance_mi:.0f} miles.",
            f"{pay_label(p.business_status)}: {business.gross_pay:,.0f} dollars.",
            f"Dollars per mile: {dollars_per_mile:.2f}.",
            # The appointment reads in the receiver's local time, the way real
            # dispatch quotes it. "About" because the clock starts at pickup
            # departure, after check-in and loading.
            f"Deadline: {job.deadline_game_h:.0f} hours; deliver by about "
            f"{appointment_text(p.game_hours, job.deadline_game_h, city_zone(world.city(job.destination)))}.",
            f"Equipment: {job.equipment_text()}.",
            f"Trailer: {self.board._trailer_note(self.job)}",
        ]
        locked = self.board._locked_reason(job)
        if locked:
            lines.append(f"Locked: {locked}")
        elif job.cargo.endorsement:
            lines.append(f"Endorsement: {job.cargo.endorsement.replace('_', ' ')}.")
        lines.append("Route details happen after pickup: rest, fuel, tolls, weather, and stops.")
        return lines
