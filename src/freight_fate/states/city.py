"""Terminal hub: dispatch board, garage, upgrades, trucks, and route selection."""

from __future__ import annotations

import zlib

from ..models.business import (
    AUTHORITY_ACTIVATION_COST,
    AUTHORITY_READY_RESERVE,
    INDEPENDENT_AUTHORITY,
    LEASED_OWNER_OPERATOR,
    OWNER_OPERATOR_BUY_IN,
    authority_activation_eligibility,
    authority_readiness_eligibility,
    business_path_label,
    business_status_summary,
    carrier_name,
    has_authority_readiness,
    is_owner_operator,
    next_business_unlock,
    owner_operator_eligibility,
    pay_label,
    status_label,
)
from ..models.economy import (
    pay_advance_grant,
    pay_advance_unavailable_reason,
)
from ..models.jobs import (
    CARGO_CATALOG,
    Job,
    JobBoard,
    job_from_payload,
    job_payload,
)
from ..models.trailers import (
    DEFAULT_TRAILER_PROGRAMS,
    TRAILER_CATALOG,
    TrailerType,
    compatible_with_programs,
    owned_trailer_for_cargo,
    required_program_text,
)
from ..models.trucks import TRUCK_CATALOG, UPGRADE_CATALOG, TruckModel, Upgrade
from ..music import select_menu_music_sequence
from ..sim.hos import clock_text, time_of_day
from .base import MenuItem, MenuState
from .city_garage import GarageState
from .city_pickup import (  # noqa: F401
    PickupFacilityState,
    RouteSelectState,
    pickup_snapshot,
    route_planning_summary,
)


def _record_city_duty(ctx, status: str, start_hour: float, end_hour: float,
                      note: str = "") -> None:
    p = ctx.profile
    if p is None:
        return
    terminal = ctx.world.home_terminal(p.current_city)
    p.duty_log.record(status, start_hour, end_hour, terminal.name, note)


def _job_payload(job: Job) -> dict:
    return job_payload(job)


def _job_from_payload(data: dict) -> Job:
    return job_from_payload(data)


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
        business = status_label(p.business_status)
        rank = p.career.rank
        self.ctx.say(
            f"Parked at {terminal.spoken_name} in the {p.current_city} "
            f"service area, {city.state}. {business.capitalize()} with "
            f"level {rank.level}, {rank.title}. "
            f"You have {p.money:,.0f} dollars. "
            f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem("Dispatch board", self._job_board,
                     help="Browse terminal dispatches from local freight "
                          "facilities, including ports, warehouses, food "
                          "terminals, intermodal yards, and distribution hubs."),
            MenuItem("Drive to city services", self._city_services,
                     help="Drive through the local service area to the garage, "
                          "truck dealer, or freight market office. Stop at the "
                          "destination, then press Enter to go inside."),
            MenuItem("Bobtail to a nearby city", self._bobtail,
                     help="Drive empty to a nearby city to shop its dispatch "
                          "board. Costs fuel and hours of service; no load, no "
                          "pay. Use it when local jobs are thin."),
            MenuItem(self._garage_label, self._garage,
                     help="Refuel and repair the active tractor at the terminal garage. "
                          "Company drivers use carrier-assigned equipment and the carrier account. "
                          "Owner-operators pay their own fuel and repairs."),
            MenuItem("Business status", self._business_status,
                     help="Review your carrier, rank, next business unlock, "
                          "and owner-operator buy-in when qualified."),
            MenuItem("Career stats", self._stats,
                     help="Hear your level, reputation, and lifetime numbers."),
            MenuItem("Truck status", self._truck_status,
                     help="Hear assigned or owned tractor status at a glance."),
            MenuItem("Time and weather", self._time_weather,
                     help="Hear the clock, the day of your career, and the "
                          "conditions outside."),
            MenuItem("Logbook", self._logbook,
                     help="Review your recent Record of Duty Status entries."),
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
        region = self.ctx.world.cities[p.current_city].region
        price = self.ctx.economy.fuel_price(region)
        return f"Garage: fuel {price:.2f} per gallon"

    def _garage(self) -> None:
        self.ctx.push_state(GarageState(self.ctx))

    def _business_status(self) -> None:
        self.ctx.push_state(BusinessStatusState(self.ctx))

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
        truck = TRUCK_CATALOG.get(p.active_truck_key(), TRUCK_CATALOG["rig"])
        fuel_pct = p.truck_fuel_gal / specs.fuel_tank_gal * 100
        damage = p.truck_damage_pct
        condition = ("excellent" if damage < 5 else "good" if damage < 20
                     else "worn" if damage < 50 else "poor")
        if not p.owns_equipment():
            lead = f"Assigned {carrier_name(p)} tractor: {truck.label}."
        else:
            lead = f"Owned tractor: {truck.label}."
        self.ctx.say(f"{lead} Fuel {fuel_pct:.0f} percent, "
                     f"{p.truck_fuel_gal:.0f} gallons of "
                     f"{specs.fuel_tank_gal:.0f}. "
                     f"Tractor condition {condition}, {damage:.0f} percent damage.")

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
        start = p.game_hours
        p.game_hours += 10.0
        _record_city_duty(self.ctx, "sleeper_berth", start, p.game_hours,
                          "terminal sleep")
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
        self.ctx.reset_to(MainMenuState(self.ctx))

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.say("Use Quit to main menu to leave the terminal. Progress is saved automatically.")


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
        "count": 5,
    }


def open_freight_market(ctx) -> list[Job]:
    p = ctx.profile
    board = JobBoard(ctx.world)
    market_changed = p.market.advance_to(p.market_day())
    key = dispatch_cache_key(p)
    cache = p.dispatch_board_cache if not market_changed else None
    if cache and cache.get("key") == key:
        jobs = [_job_from_payload(payload)
                for payload in cache.get("jobs", [])]
    else:
        jobs = board.offers(
            p.current_city,
            p.career.endorsements,
            level=p.career.level,
            market=p.market,
            carrier_key=getattr(p, "carrier_key", ""),
            direct_freight=p.business_status == INDEPENDENT_AUTHORITY,
        )
        p.dispatch_board_cache = {
            "key": key,
            "jobs": [_job_payload(job) for job in jobs],
        }
        ctx.save_profile()
    ctx.push_state(JobBoardState(ctx, jobs))
    return jobs


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
            items.append(MenuItem(
                f"{service.name}: {route.miles:.1f} miles",
                lambda key=service.key: self._start(key),
                help=(
                    f"Drive to {service.spoken_name}. "
                    "The destination opens only after you stop and press Enter."
                ),
            ))
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


class BusinessStatusState(MenuState):
    title = "Business status"
    intro_help = (
        "Use up and down arrows to review the business path. Enter repeats "
        "status, or buys into owner-operator status when qualified. Escape "
        "returns to the terminal."
    )

    def announce_entry(self) -> None:
        self.ctx.say(f"Business status. {business_status_summary(self.ctx.profile)} "
                     f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        p = self.ctx.profile
        items = [
            MenuItem(self._summary_label, self._summary,
                     help="Hear the current business status and tradeoffs."),
            MenuItem(self._rank_label, self._rank_status,
                     help="Hear your starter carrier, rank, and career stage."),
            MenuItem(self._next_unlock_label, self._next_unlock,
                     help="Hear the next career or business unlock."),
        ]
        if not is_owner_operator(p.business_status):
            ok, _reasons = owner_operator_eligibility(p)
            if ok:
                items.append(MenuItem(
                    f"Buy into leased-on owner-operator: {OWNER_OPERATOR_BUY_IN:,.0f} dollars",
                    self._become_owner_operator,
                    help="Buy your first tractor position and start running as "
                         "a leased-on owner-operator. Higher revenue, but your "
                         "business pays operating costs."))
            else:
                items.append(MenuItem(
                    "Owner-operator path locked", self._summary,
                    help="Hear the remaining requirements."))
        else:
            if p.business_status == INDEPENDENT_AUTHORITY:
                items.append(MenuItem(
                    "Own authority active", self._summary,
                    help="Direct freight is available. Settlement includes "
                         "insurance, compliance, and factoring costs."))
            elif has_authority_readiness(p):
                items.append(MenuItem(
                    "Authority prep reserve: set", self._summary,
                    help="This career has set aside the prep reserve for "
                         "own-authority startup."))
                ok, _reasons = authority_activation_eligibility(p)
                if ok:
                    items.append(MenuItem(
                        f"Activate own authority: {AUTHORITY_ACTIVATION_COST:,.0f} dollars",
                        self._activate_authority,
                        help="Start direct freight with higher gross revenue "
                             "and more business overhead."))
                else:
                    items.append(MenuItem(
                        "Own authority locked", self._next_unlock,
                        help="Hear the remaining own-authority requirements."))
            else:
                ok, _reasons = authority_readiness_eligibility(p)
                if ok:
                    items.append(MenuItem(
                        f"Commit {AUTHORITY_READY_RESERVE:,.0f} dollars "
                        "to authority prep",
                        self._set_authority_readiness,
                        help="Set aside money for the later own-authority "
                             "activation gate."))
                else:
                    items.append(MenuItem(
                        "Authority prep locked", self._next_unlock,
                        help="Hear the remaining authority prep requirements."))
        items.append(MenuItem("Back", self.go_back))
        return items

    def _summary_label(self) -> str:
        p = self.ctx.profile
        return f"Current status: {status_label(p.business_status)}"

    def _summary(self) -> None:
        self.ctx.say(business_status_summary(self.ctx.profile))

    def _rank_label(self) -> str:
        return "Carrier and rank"

    def _rank_status(self) -> None:
        self.ctx.say(business_path_label(self.ctx.profile))

    def _next_unlock_label(self) -> str:
        return "Next business unlock"

    def _next_unlock(self) -> None:
        self.ctx.say(next_business_unlock(self.ctx.profile))

    def _become_owner_operator(self) -> None:
        p = self.ctx.profile
        ok, reasons = owner_operator_eligibility(p)
        if not ok:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Owner-operator path locked. " + " ".join(reasons))
            self.refresh()
            return
        p.money -= OWNER_OPERATOR_BUY_IN
        assigned = p.active_truck_key()
        p.business_status = LEASED_OWNER_OPERATOR
        if assigned not in p.owned_trucks:
            p.owned_trucks.append(assigned)
        if not p.trailer_programs:
            p.trailer_programs = list(DEFAULT_TRAILER_PROGRAMS)
        p.truck = assigned
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"Leased-on owner-operator status unlocked. You paid "
            f"{OWNER_OPERATOR_BUY_IN:,.0f} dollars toward your first tractor "
            f"and kept {p.money:,.0f} dollars working capital. Future loads "
            "pay higher gross revenue, and your business pays fuel, repairs, "
            "maintenance reserve, insurance, trailer program, truck payment "
            "reserve, and settlement fees.")
        self.refresh()

    def _set_authority_readiness(self) -> None:
        p = self.ctx.profile
        ok, reasons = authority_readiness_eligibility(p)
        if not ok:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Authority prep locked. " + " ".join(reasons))
            self.refresh()
            return
        p.money -= AUTHORITY_READY_RESERVE
        p.authority_readiness = True
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"Authority prep reserve set aside: "
            f"{AUTHORITY_READY_RESERVE:,.0f} dollars. You have "
            f"{p.money:,.0f} dollars left. Own authority can unlock after "
            "the final delivery, reputation, trailer program, and cash gates. "
            "For now you remain leased on.")
        self.refresh()

    def _activate_authority(self) -> None:
        p = self.ctx.profile
        ok, reasons = authority_activation_eligibility(p)
        if not ok:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Own authority locked. " + " ".join(reasons))
            self.refresh()
            return
        p.money -= AUTHORITY_ACTIVATION_COST
        p.business_status = INDEPENDENT_AUTHORITY
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"Own authority active. Startup cost "
            f"{AUTHORITY_ACTIVATION_COST:,.0f} dollars. You have "
            f"{p.money:,.0f} dollars left. Dispatch now lists direct freight. "
            "Settlement includes insurance, compliance, trailer, truck, and "
            "factoring costs."
        )
        self.refresh()


class UpgradeShopState(MenuState):
    title = "Upgrades"
    intro_help = ("Each entry speaks the upgrade, its price, and what you already "
                  "own. Enter buys the next tier. Press F1 on an upgrade to hear "
                  "what it does. Escape returns to the garage.")

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(f"Upgrades. You have {p.money:,.0f} dollars. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        if not is_owner_operator(self.ctx.profile.business_status):
            return [
                MenuItem(
                    "Upgrades locked: carrier-assigned tractor",
                    self._locked,
                    help=(
                        "Company drivers use fleet-maintained equipment. "
                        "Performance upgrades unlock after the leased-on "
                        "owner-operator buy-in."
                    ),
                ),
                MenuItem("Back", self.go_back),
            ]
        items = [MenuItem(lambda u=u: self._label(u), lambda u=u: self._buy(u),
                          help=u.description)
                 for u in UPGRADE_CATALOG.values()]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _locked(self) -> None:
        self.ctx.audio.play("ui/error")
        self.ctx.say(
            "Upgrades are locked. Company drivers use carrier-assigned, "
            "fleet-maintained tractors. Ownership upgrades unlock after the "
            "leased-on owner-operator buy-in.")

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
        if not is_owner_operator(p.business_status):
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "Upgrades unlock after the leased-on owner-operator buy-in. "
                "The company tractor stays carrier-maintained for now.")
            return
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
    intro_help = ("Owner-operators can buy tractors or switch among tractors "
                  "they own. Company drivers use carrier-assigned equipment. "
                  "Escape returns to the garage.")

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(f"Trucks. You have {p.money:,.0f} dollars. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        if not is_owner_operator(self.ctx.profile.business_status):
            return [
                MenuItem(
                    "Truck ownership locked: carrier-assigned tractor",
                    self._locked,
                    help=(
                        "Company drivers do not buy tractors here. The carrier "
                        "assigns and maintains the company tractor until the "
                        "leased-on owner-operator buy-in."
                    ),
                ),
                MenuItem("Back", self.go_back),
            ]
        items = [MenuItem(lambda m=m: self._label(m), lambda m=m: self._pick(m),
                          help=m.description)
                 for m in TRUCK_CATALOG.values()]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _locked(self) -> None:
        self.ctx.audio.play("ui/error")
        self.ctx.say(
            "Truck ownership is locked. Company drivers run a carrier-assigned "
            "tractor. Buying and switching owned tractors unlocks after the "
            "leased-on owner-operator buy-in.")

    def _label(self, model: TruckModel) -> str:
        p = self.ctx.profile
        name = model.label.capitalize()
        if model.key == p.truck:
            return f"{name}: currently driving"
        if model.key in p.visible_owned_trucks():
            return f"{name}: owned, switch to it"
        return f"{name}: buy for {model.price:,.0f} dollars"

    def _pick(self, model: TruckModel) -> None:
        p = self.ctx.profile
        if model.key == p.truck:
            self.ctx.say(f"You are already driving the {model.label}.")
            return
        if not is_owner_operator(p.business_status):
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "Truck purchases unlock after the leased-on owner-operator buy-in. "
                "For now, the carrier assigns your company tractor.")
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
            self.ctx.say(
                f"You bought the {model.label} for {model.price:,.0f} dollars "
                f"and it is now your owned tractor. "
                f"You have {p.money:,.0f} dollars left.")
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


class TrailerProgramState(MenuState):
    title = "Trailers"
    intro_help = (
        "Company drivers use carrier-provided trailers. Owner-operators start "
        "with the dry van trailer program and can add specialty programs. "
        "Own-authority drivers can buy trailers outright. "
        "Escape returns to the garage."
    )

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(
            f"Trailers. You have {p.money:,.0f} dollars. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        p = self.ctx.profile
        if not is_owner_operator(p.business_status):
            return [
                MenuItem(
                    "Trailer programs locked: carrier-provided trailers",
                    self._locked,
                    help=(
                        "Company drivers do not lease or buy trailers. The "
                        "carrier supplies the right trailer for approved loads."
                    ),
                ),
                MenuItem("Back", self.go_back),
            ]
        items = [
            MenuItem(lambda t=t: self._label(t), lambda t=t: self._select(t),
                     help=t.description)
            for t in TRAILER_CATALOG.values()
        ]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _locked(self) -> None:
        self.ctx.audio.play("ui/error")
        self.ctx.say(
            "Trailer programs are locked. Company drivers use carrier-provided "
            "trailers, so no trailer lease is needed."
        )

    def _label(self, trailer: TrailerType) -> str:
        p = self.ctx.profile
        owned = set(p.visible_owned_trailers())
        if p.business_status == INDEPENDENT_AUTHORITY:
            if trailer.key in owned:
                return f"{trailer.label}: owned trailer"
            return f"{trailer.label}: buy trailer for {trailer.purchase_price:,.0f} dollars"
        programs = set(p.active_trailer_programs())
        if trailer.key in programs:
            if trailer.key in DEFAULT_TRAILER_PROGRAMS:
                return f"{trailer.label}: included carrier trailer program"
            return f"{trailer.label}: leased program active"
        return f"{trailer.label}: lease program for {trailer.lease_deposit:,.0f} dollars"

    def _select(self, trailer: TrailerType) -> None:
        if self.ctx.profile.business_status == INDEPENDENT_AUTHORITY:
            self._buy_trailer(trailer)
            return
        self._lease(trailer)

    def _lease(self, trailer: TrailerType) -> None:
        p = self.ctx.profile
        if not is_owner_operator(p.business_status):
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "Company drivers use carrier-provided trailers. Trailer "
                "programs unlock after the leased-on owner-operator buy-in."
            )
            return
        if trailer.key in p.active_trailer_programs():
            self.ctx.say(f"{trailer.label} trailer program is already active.")
            return
        if p.money < trailer.lease_deposit:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"Not enough money. {trailer.label} trailer program costs "
                f"{trailer.lease_deposit:,.0f} dollars and you have "
                f"{p.money:,.0f}."
            )
            return
        p.money -= trailer.lease_deposit
        p.trailer_programs = list(p.active_trailer_programs()) + [trailer.key]
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"{trailer.label} trailer program active for "
            f"{trailer.lease_deposit:,.0f} dollars. You have "
            f"{p.money:,.0f} dollars left. Matching cargo can now appear as "
            "available on the dispatch board."
        )
        self.refresh()

    def _buy_trailer(self, trailer: TrailerType) -> None:
        p = self.ctx.profile
        if p.business_status != INDEPENDENT_AUTHORITY:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "Trailer purchases unlock after own authority. Leased-on "
                "owner-operators can use trailer programs for now."
            )
            return
        if trailer.key in p.visible_owned_trailers():
            self.ctx.say(f"You already own a {trailer.label} trailer.")
            return
        if p.money < trailer.purchase_price:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"Not enough money. The {trailer.label} trailer costs "
                f"{trailer.purchase_price:,.0f} dollars and you have "
                f"{p.money:,.0f}."
            )
            return
        p.money -= trailer.purchase_price
        p.owned_trailers = list(p.visible_owned_trailers()) + [trailer.key]
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"{trailer.label} trailer purchased for "
            f"{trailer.purchase_price:,.0f} dollars. You have "
            f"{p.money:,.0f} dollars left. Matching direct freight now uses "
            "an owned-trailer reserve at settlement."
        )
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

    def announce_entry(self) -> None:
        n = len(self.jobs)
        if n == 0:
            self.ctx.say("Dispatch board. No jobs available right now. Press Escape to go back.")
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
                    "driver wages. "
                )
            self.ctx.say(f"Dispatch board. {n} dispatch{'es' if n != 1 else ''} available. "
                         f"{business_note}{self.ctx.profile.market.summary()} "
                         + self.current_text())

    def build_items(self) -> list[MenuItem]:
        items = []
        for i, job in enumerate(self.jobs):
            items.append(MenuItem(
                job.describe(
                    i + 1,
                    len(self.jobs),
                    pay_label=pay_label(self.ctx.profile.business_status),
                    trailer_note=self._trailer_note(job),
                ),
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
        locked = job.locked_reason(
            p.career.endorsements,
            p.career.level,
            trailer_programs=p.active_trailer_programs(),
            carrier_trailer_support=not is_owner_operator(p.business_status),
        )
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
                self.ctx.say(f"{locked} Keep delivering to level up and unlock it.")
            return
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


