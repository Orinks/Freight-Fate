# ruff: noqa: F403,F405
from __future__ import annotations

import time

from ..models import enforcement
from ..models.career import standing_xp_rate, xp_rate_settlement_clause
from ..models.cargo_condition import cargo_condition_text, settle_cargo
from ..models.solvency import deductions_from_settlement
from ..sim.timezones import to_local
from .base import TimedMessageState
from .driving_core import *
from .driving_damage import (
    cargo_status_clause,
    damage_band_clause,
    damage_summary_line,
    preventable_damage_charge,
)

DELIVERY_SETTLEMENT_MAX_AVERAGE_MPH = 55.0
ROAD_GRIME_PER_MILE = 0.004
# Below this the settlement reports the tank; at or above it a near-full tank
# is the unremarkable default and the row is dropped (research doc R10). A
# quarter tank is the point a driver planning the next leg starts to care.
SETTLEMENT_LOW_FUEL_FRACTION = 0.25

# Plain "deliver into this city" badges (titles claim nothing extra). Mostly
# cities the jukebox got to first; each badge's song lives in the catalog.
SIMPLE_ARRIVAL_BADGES = {
    "phoenix_az_us": "phoenix_arrival",
    "wichita_ks_us": "wichita_arrival",
    "bakersfield_ca_us": "bakersfield_arrival",
    "las_vegas_nv_us": "vegas_arrival",
    "nashville_tn_us": "nashville_delivery",
    "el_paso_tx_us": "el_paso_arrival",
    "laredo_tx_us": "laredo_arrival",
    "baton_rouge_la_us": "baton_rouge_arrival",
    "sacramento_ca_us": "sacramento_arrival",
    "muskogee_ok_us": "muskogee_arrival",
    "kansas_city_mo_us": "kansas_city_arrival",
    "memphis_tn_us": "memphis_arrival",
    "saginaw_mi_us": "saginaw_arrival",
    "fort_worth_tx_us": "fort_worth_arrival",
    "san_antonio_tx_us": "san_antonio_arrival",
    "new_orleans_la_us": "new_orleans_arrival",
    "houston_tx_us": "houston_arrival",
    "winslow_az_us": "winslow_arrival",
    "chattanooga_tn_us": "chattanooga_arrival",
    # The song never settles which Jackson it means, so either one counts.
    "jackson_tn_us": "jackson_arrival",
    "jackson_ms_us": "jackson_arrival",
    "abilene_tx_us": "abilene_arrival",
}


def _settlement_hours(driving: DrivingState) -> float:
    driven_hours = driving.trip.game_minutes / 60.0
    minimum_hours = driving.job.distance_mi / DELIVERY_SETTLEMENT_MAX_AVERAGE_MPH
    return max(driven_hours, minimum_hours)


class DrivingStatusState(MenuState):
    """Live driving status, grouped into screens you open one at a time.

    A tabbed layout (Right/Left to cycle Route, Driver, Map) needs visible tabs
    to make sense, so each screen is its own spoken submenu instead, matching
    the rest of the game's menus.
    """

    title = "Driving status"
    intro_help = (
        "Use up and down arrows to pick a status screen, Enter to open it, and "
        "Escape to return to driving. Each screen lists its status lines."
    )
    SCREENS = (
        ("Route", "route"),
        ("Driver", "driver"),
        ("Map", "map"),
        ("Radio", "radio"),
        ("Driver apps", "apps"),
    )

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                label,
                lambda key=key: self._open(key),
                help=f"Open the {label.lower()} status screen.",
            )
            for label, key in self.SCREENS
        ]
        items.append(
            MenuItem("Back to driving", self.go_back, help="Close status and resume driving.")
        )
        return items

    def _open(self, screen: str) -> None:
        if screen == "apps":
            self.ctx.push_state(DriverAppsState(self.ctx, self.driving))
            return
        self.ctx.push_state(DrivingStatusScreenState(self.ctx, self.driving, screen))

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
        self.ctx.say("Back to driving.", interrupt=False)


class DrivingStatusScreenState(MenuState):
    """One screen of live driving status as a reviewable list of lines."""

    # The static intro_help this line carried is a property below now, so the
    # Map screen can mention opening a stop's details. The radio screen stays.
    TITLES = {
        "route": "Route",
        "driver": "Driver",
        "map": "Map",
        "radio": "Radio",
    }

    def __init__(self, ctx, driving: DrivingState, screen: str) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.screen = screen

    @property
    def title(self) -> str:  # type: ignore[override]
        return self.TITLES.get(self.screen, "Status")

    @property
    def intro_help(self) -> str:  # type: ignore[override]
        if self.screen == "map":
            return (
                "Use up and down arrows to review each line. Enter repeats the "
                "current line, or opens full details on a stop line. Escape "
                "goes back to the status screens."
            )
        return (
            "Use up and down arrows to review each line. Enter repeats the current "
            "line. Escape goes back to the status screens."
        )

    def build_items(self) -> list[MenuItem]:
        if self.screen == "map":
            items = self._map_items()
        else:
            items = [
                MenuItem(
                    line,
                    lambda line=line: self.ctx.say(line),
                    help="Repeat this status line.",
                )
                for line in self._lines()
            ]
        items.append(MenuItem("Back", self.go_back, help="Back to the status screens."))
        return items

    def _lines(self) -> list[str]:
        if self.screen == "driver":
            return self._driver_lines()
        # No map branch: build_items sends the Map screen through _map_items
        # now, so its stop lines can open a details view.
        if self.screen == "radio":
            return self._radio_lines()
        return self.driving.status_lines()

    def _driver_lines(self) -> list[str]:
        d = self.driving
        t = d.truck
        profile = self.ctx.profile
        hours_used = d.trip.game_minutes / 60.0
        deadline = d.job.deadline_game_h - hours_used
        deadline_text = (
            f"{deadline:.1f} hours before the deadline, due {_deadline_appointment(d)}"
            if deadline >= 0
            else f"{-deadline:.1f} hours past the deadline"
        )
        load_line = (
            f"Load: {d.job.weight_tons:.0f} tons of {d.job.cargo.label}, "
            f"gross {d.truck.gross_mass_kg / KG_PER_TON:.0f} tons, "
            # The player cannot see the trailer; the dock's verdict must not
            # be the first they hear of what the freight is in.
            f"freight {cargo_status_clause(d.truck)}"
        )
        # A tank load behaves unlike anything else on the roster, and the
        # driver cannot see the trailer -- so how it will behave is answerable
        # here, on demand, rather than only at pickup. Empty for other freight.
        tank_line = d.liquid_status_clause()
        time_line = (
            f"Time: {clock_text(d.trip.local_hour)} {d.trip.current_timezone.name}, {deadline_text}"
        )
        band = damage_band_clause(self.ctx.settings, t)
        damage_band_suffix = f", {band}" if band else ""
        # What is owed sits next to what is held, so a driver can ask the same
        # question mid-run that the terminal answers between them.
        from ..models.solvency import debt_line

        owed = debt_line(profile)
        # The trust line only joins the driving screen when it is doing
        # something. A driver in full trust already hears it on the career
        # stats screen and does not need it twice.
        trust = (
            enforcement.dispatch_trust_line(profile)
            if enforcement.standing_band(profile) != enforcement.TRUST_FULL
            else ""
        )
        lines = [
            f"Driver: {profile.name}",
            f"Money: {profile.money:,.0f} dollars",
            *([owed] if owed else []),
            load_line,
        ]
        if tank_line:
            lines.append(f"Tank: {tank_line}")
        lines += [
            f"Objective: {d._objective_text()}",
            # The band rides with the number: hearing "78 percent" without
            # "limp mode" leaves the player to work out why the truck is slow.
            f"Truck: fuel {t.fuel_fraction * 100:.0f} percent, "
            f"damage {t.damage_pct:.0f} percent{damage_band_suffix}",
            f"Transmission: {'automatic' if t.transmission.automatic else 'manual'}, {d._gear_text()}",
            f"Fatigue: {profile.fatigue:.0f} percent",
            # Where the driver stands is spoken when it changes and whenever it
            # is asked for, never on a timer.
            enforcement.standing_text(profile),
            *([trust] if trust else []),
            f"Hours: {d.hos.summary(self.ctx.settings.hos_mode).rstrip('.')}",
            time_line,
        ]
        return lines

    def _map_items(self) -> list[MenuItem]:
        d = self.driving
        route = d.route
        settings = self.ctx.settings

        def say_item(line: str) -> MenuItem:
            return MenuItem(
                line,
                lambda line=line: self.ctx.say(line),
                help="Repeat this status line.",
            )

        items = [
            # route.cities holds slug keys; speak the composed names instead.
            say_item(f"Route: {' to '.join(self.ctx.world.spoken_city(c) for c in route.cities)}"),
            say_item(f"Highways: {_join_phrase(route.highways)}"),
            say_item(
                f"Progress: {settings.distance_text(d.trip.position_mi)} driven, "
                f"{settings.distance_text(d.trip.remaining_miles)} remaining"
            ),
            say_item(f"Guidance: {d.trip.next_navigation_context(settings.imperial_units)}"),
        ]
        upcoming = [stop for stop in d.trip.stops if stop.at_mi >= d.trip.position_mi - 0.05][:5]
        if upcoming:
            for stop in upcoming:
                ahead = max(0.0, stop.at_mi - d.trip.position_mi)
                items.append(
                    MenuItem(
                        f"Stop in {settings.distance_text(ahead)}: "
                        f"{d.trip.planned_prefix(stop)}{stop.spoken_name}; "
                        f"{_poi_offers_text(stop)}.",
                        lambda stop=stop: self._open_stop(stop),
                        help="Press Enter for full details, distance, "
                        "estimated arrival, and stop planning.",
                    )
                )
        else:
            items.append(say_item("Stops: no more listed route stops before destination."))
        next_cues = [
            cue
            for cue in d.trip.navigation_cues
            if cue.at_mi > d.trip.position_mi + 0.05 and cue.kind != "rest_stop"
        ][:4]
        for cue in next_cues:
            ahead = max(0.0, cue.at_mi - d.trip.position_mi)
            speed = f" at {settings.speed_text(cue.speed_mph)}" if cue.speed_mph is not None else ""
            items.append(
                say_item(f"Map point in {settings.distance_text(ahead)}: {cue.text}{speed}.")
            )
        if route.estimated_tolls > 0:
            items.append(
                say_item(
                    f"Estimated carrier-paid toll exposure: {route.estimated_tolls:,.0f} dollars."
                )
            )
        planned = d.trip.planned_stop_label
        if planned:
            items.append(
                MenuItem(
                    f"Cancel planned stop at {planned}",
                    self._cancel_planned_stop,
                    help="Forget your planned stop. Announcements go back to normal.",
                )
            )
        return items

    def _open_stop(self, stop) -> None:
        from .driving_stop_detail import StopDetailState

        self.ctx.push_state(StopDetailState(self.ctx, self.driving, stop))

    def _cancel_planned_stop(self) -> None:
        self.driving.trip.planned_stop_key = None
        self.refresh()
        self.ctx.say("Planned stop canceled.")

    def _radio_lines(self) -> list[str]:
        d = self.driving
        # Opening the dial re-reads the Playlists folder: a playlist added or
        # repaired mid-run used to need a whole new drive before the radio
        # would look at the folder again, and this screen is where a player
        # goes to find out why their playlist is not on the dial.
        d.radio.reload_personal_playlists()
        d._sync_radio_settings()
        settings = self.ctx.settings
        position = d.radio.position
        lines = [
            d.radio.status_text(),
            *(
                ()
                if d.truck.engine_on
                else ("The engine is off, so the radio has no power right now.",)
            ),
            (
                "Streamer-safe mode is off: real public streams and personal playlists are on the dial."
                if not settings.radio_streamer_safe
                else "Streamer-safe mode is on: real public streams and personal playlists are hidden."
            ),
            "Page Down tunes to the next station and Page Up to the previous; "
            "the semicolon and apostrophe keys still work. Jump categories "
            "with Control held, or change the radio volume in 10 percent "
            "steps with Shift held, whether the radio is on or off. Press O "
            "to save the current station as a favorite. Press M to toggle "
            "radio from the cab.",
        ]
        if d.radio.favorite_ids:
            lines.append(f"Favorites saved: {len(d.radio.favorite_ids)}.")
        if position is not None:
            lines.append(f"Approximate truck radio position: {position[0]:.2f}, {position[1]:.2f}.")
        lines.append("Receivable stations:")
        lines.extend(
            d.radio.station_list_lines(limit=16, distance_text=self.ctx.settings.distance_text)
        )
        return lines


class DriverAppsState(MenuState):
    """Accessible driver tablet launcher."""

    title = "Driver apps"
    intro_help = (
        "Choose an app on the driver tablet. Enter opens the app, and Escape "
        "returns to the status screens."
    )
    APPS = (
        ("Navigation", "navigation", "Open GPS guidance, route progress, and exit context."),
        ("Weather", "weather", "Open conditions, forecast, and safe-speed guidance."),
        ("Traffic", "traffic", "Open traffic pace and reported slowdowns ahead."),
        ("Truck stops", "truck_stops", "Open upcoming route stops and available services."),
        ("Road chatter", "road_chatter", "Open local driver reports and general road chatter."),
        ("ELD", "eld", "Open hours-of-service and legal-stop guidance."),
    )

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                label,
                lambda key=key: self._open_app(key),
                help=help_text,
            )
            for label, key, help_text in self.APPS
        ]
        items.append(
            MenuItem(
                "Back to status screens", self.go_back, help="Return to the status screen list."
            )
        )
        return items

    def _open_app(self, app_key: str) -> None:
        self.ctx.push_state(DriverAppScreenState(self.ctx, self.driving, app_key))


class DriverAppScreenState(MenuState):
    """One driver tablet app as a reviewable spoken list."""

    intro_help = (
        "Use up and down arrows to review app lines. Enter repeats the current "
        "line. Escape returns to Driver apps."
    )
    TITLES = {
        "navigation": "Navigation",
        "weather": "Weather",
        "traffic": "Traffic",
        "truck_stops": "Truck stops",
        "road_chatter": "Road chatter",
        "eld": "ELD",
    }

    def __init__(self, ctx, driving: DrivingState, app_key: str) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.app_key = app_key
        self._weather_status = driving.weather.source_status if app_key == "weather" else None
        self._weather_refresh_failed = (
            driving.weather.live_weather_refresh_failed if app_key == "weather" else False
        )
        self._weather_refresh_issue_announced = False

    @property
    def title(self) -> str:  # type: ignore[override]
        return self.TITLES.get(self.app_key, "Driver app")

    def build_items(self) -> list[MenuItem]:
        if self.app_key == "weather":
            items = []
            for index in range(len(self._weather_lines())):

                def label(index=index):
                    return self._weather_lines()[index]

                items.append(
                    MenuItem(
                        label,
                        lambda label=label: self.ctx.say(label()),
                        help="Repeat this app line.",
                    )
                )
            items.append(
                MenuItem(
                    "Back to Driver apps",
                    self.go_back,
                    help="Return to the driver tablet app list.",
                )
            )
            return items
        items = [
            MenuItem(line, lambda line=line: self.ctx.say(line), help="Repeat this app line.")
            for line in self._lines()
        ]
        items.append(
            MenuItem(
                "Back to Driver apps", self.go_back, help="Return to the driver tablet app list."
            )
        )
        return items

    def update(self, dt: float) -> None:
        """Keep asynchronous live weather current while its app is open."""
        if self.app_key != "weather":
            return
        weather = self.driving.weather
        changed = weather.update(0.0)
        status = weather.source_status
        refresh_failed = weather.live_weather_refresh_failed
        refresh_failure_started = refresh_failed and not self._weather_refresh_failed
        if changed is None and status == self._weather_status and not refresh_failure_started:
            self._weather_refresh_failed = refresh_failed
            return
        previous_status = self._weather_status
        self._weather_status = status
        self._weather_refresh_failed = refresh_failed
        if status not in ("live", "last_known", "fallback"):
            return
        suppress_routine_refresh = (status == "last_known" and weather.live_weather_refreshing) or (
            status == "live"
            and previous_status == "last_known"
            and not self._weather_refresh_issue_announced
        )
        if (changed is not None or previous_status != status or refresh_failure_started) and not (
            suppress_routine_refresh
        ):
            prefix = "Weather updated" if changed is not None else "Weather status changed"
            self.ctx.say(
                f"{prefix}. {weather.report_lead(self.ctx.settings.imperial_units)}.",
                interrupt=False,
            )
            self._weather_refresh_issue_announced = status == "last_known" and refresh_failed
            # The active tablet consumed this provider update. Keep the paused
            # trip's source tracker aligned so returning to driving does not
            # repeat a generic readiness announcement.
            self.driving.trip._weather_source_status = status
            self.driving.trip._weather_refresh_issue_announced = (
                status == "last_known" and refresh_failed
            )
            if status in ("live", "fallback"):
                self.driving.trip._weather_location_refreshing = False
                self._weather_refresh_issue_announced = False

    def _lines(self) -> list[str]:
        if self.app_key == "weather":
            return self._weather_lines()
        if self.app_key == "traffic":
            return self._traffic_lines()
        if self.app_key == "truck_stops":
            return self._truck_stop_lines()
        if self.app_key == "road_chatter":
            return self._road_chatter_lines()
        if self.app_key == "eld":
            return self._eld_lines()
        return self._navigation_lines()

    def _navigation_lines(self) -> list[str]:
        d = self.driving
        settings = self.ctx.settings
        return [
            f"Navigation: {d.trip.next_navigation_context(settings.imperial_units)}",
            f"Route progress: {d.trip.progress_summary(settings.imperial_units)}",
            f"Next listed exit: {d.trip.next_exit_context()}",
        ]

    def _weather_lines(self) -> list[str]:
        d = self.driving
        settings = self.ctx.settings
        source = d.weather.source_label()
        if d.weather.live_weather_refreshing:
            source += ". Live weather is updating for your current location"
        elif d.weather.live_weather_refresh_failed:
            source += ". The latest live weather check failed"
        lines = [
            f"Weather source: {source}.",
            f"Observation age: {d.weather.observation_age_value()}.",
            f"Conditions: {d.weather.source_conditions(settings.imperial_units)}",
            f"Safe speed guidance: about {settings.speed_text(d.weather.effects.safe_speed_mph)}.",
        ]
        if d.weather.has_simulated_forecast:
            forecast = ", then ".join(kind.value for kind in d.weather.forecast(2))
            lines.append(f"Forecast ahead: {forecast}.")
        else:
            lines.append("Forecast ahead: unavailable for this weather source.")
        return lines

    def _traffic_lines(self) -> list[str]:
        d = self.driving
        settings = self.ctx.settings
        context = d.trip.traffic_context()
        lines = []
        if context is not None:
            lines.append(
                f"Traffic: {context.lead.reason}; pace about "
                f"{settings.speed_text(context.lead.speed_mph)}."
            )
        line = self._next_traffic_line()
        lines.append(
            line or f"Traffic: no reported pinch in the next {settings.distance_text(20.0)}."
        )
        return lines

    def _truck_stop_lines(self) -> list[str]:
        d = self.driving
        settings = self.ctx.settings
        stops = self._upcoming_stops(100.0, limit=3)
        if not stops:
            return [
                f"Truck stops: no listed route stop in the next {settings.distance_text(100.0)}."
            ]
        lines = []
        for stop in stops:
            ahead = max(0.0, stop.at_mi - d.trip.position_mi)
            lines.append(
                f"Truck stops: {stop.spoken_name} in "
                f"{settings.distance_text(ahead)}; {_poi_offers_text(stop)}."
            )
        return lines

    def _road_chatter_lines(self) -> list[str]:
        return [
            self._road_chatter_line(),
            "Road chatter: reports are informal and may be stale.",
        ]

    def _eld_lines(self) -> list[str]:
        d = self.driving
        lines = [f"ELD: {d.hos.summary(self.ctx.settings.hos_mode).rstrip('.')}"]
        context = d._hos_route_context()
        if context:
            lines.append(f"ELD route note: {context}")
        else:
            lines.append("ELD route note: no legal stop warning right now.")
        lines.append(
            "ELD keys: Alt A time at the wheel, Alt S when the break is due, "
            "Alt D what ends this shift."
        )
        return lines

    def _next_traffic_line(self) -> str | None:
        d = self.driving
        settings = self.ctx.settings
        pos = d.trip.position_mi
        traffic_manager = getattr(d.trip, "traffic_manager", None)
        vehicles = (
            traffic_manager.vehicles
            if traffic_manager is not None
            else getattr(d.trip, "npc_vehicles", [])
        )
        for lead in vehicles:
            ahead = lead.position_mi - pos
            if 0 <= ahead <= 20.0:
                return (
                    f"Traffic ahead: {lead.reason} in "
                    f"{settings.distance_text(ahead)}; reported pace "
                    f"{settings.speed_text(lead.speed_mph)}."
                )
        return None

    def _upcoming_stops(self, within_mi: float, *, limit: int) -> list:
        d = self.driving
        stops = []
        for stop in d.trip.stops:
            ahead = stop.at_mi - d.trip.position_mi
            if 0 <= ahead <= within_mi:
                stops.append(stop)
        return sorted(stops, key=lambda stop: stop.at_mi)[:limit]

    def _road_chatter_line(self) -> str:
        d = self.driving
        pos = d.trip.position_mi
        if self.ctx.settings.hos_mode in hos.HOS_NON_ENFORCED_MODES:
            return "Road chatter: enforcement reports are quiet in this mode."
        # Full detail whatever the enforcement-presence setting is: presence
        # governs ambience, and never information the player asked a key for.
        for patrol in getattr(d.trip, "posts", []):
            if patrol.end_mi < pos:
                continue
            ahead = max(0.0, patrol.watch_start_mi - pos)
            if ahead <= 25.0:
                return (
                    "Road chatter: drivers are talking about enforcement somewhere "
                    "ahead. Keep it legal."
                )
        return "Road chatter: no enforcement reports nearby."


class FacilityArrivalState(FacilityEngineMixin, MenuState):
    title = "Destination facility"
    open_sound_key = "facility/dock_gate"
    intro_help = "Use arrows to navigate, Enter to select. Dock and deliver completes the job."

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    @property
    def facility(self) -> str:
        return self.driving._destination_facility_text()

    @property
    def facility_truck(self):
        return self.driving.truck

    def presence(self):
        from ..discord_presence import PresenceState

        return PresenceState(
            "Delivering",
            f"{self.driving.job.cargo.label} to {self.driving.job.spoken_destination}",
        )

    def online_presence(self):
        return self.presence()

    def enter(self) -> None:
        sequence = select_menu_music_sequence(self.ctx.profile)
        self.ctx.play_music_sequence("menu", sequence)
        super().enter()

    def announce_entry(self) -> None:
        from ..audio import facility_ambient_key

        self.ctx.audio.set_ambient(facility_ambient_key(self.driving.job.destination_type))
        self.ctx.say(f"At {self.facility}. {self.current_text()}")

    @property
    def delivery_plan(self):
        """How the freight comes off here: dropped in the yard, or a live dock.

        Recomputed from the job rather than stored, exactly like the pickup
        side, so it survives a save and never disagrees with itself.
        """
        from ..models.trailer_yard import delivery_plan

        return delivery_plan(self.driving.job, self.ctx.profile)

    def build_items(self) -> list[MenuItem]:
        plan = self.delivery_plan
        if plan.is_drop_hook:
            primary = MenuItem(
                "Drop the loaded trailer and hook an empty",
                self._dock,
                help="The receiver takes the whole trailer. Drop it in their "
                "yard, hook an empty, and go -- quicker than a dock, and it "
                "is how you hand off a trailer with a write-up on it.",
            )
        else:
            primary = MenuItem(
                "Dock and deliver",
                self._dock,
                help="Back into the dock and complete this delivery.",
            )
        return [
            primary,
            self.facility_engine_item(),
            MenuItem(
                "Check paperwork",
                self._paperwork,
                help="Review pay, deadline, cargo condition, and charges.",
            ),
            MenuItem(
                "Check arrival status",
                self._status,
                help="Hear the facility, cargo, speed, and next step.",
            ),
        ]

    def _dock(self) -> None:
        d = self.driving
        if d.truck.speed_mph > DOCKING_MAX_MPH:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Stop before docking.")
            return
        d.truck.throttle = 0.0
        d.truck.brake = 1.0
        d.truck.set_parking_brake()
        plan = self.delivery_plan
        d._set_status(
            "In the yard. Dropping the trailer."
            if plan.is_drop_hook
            else "Docked. Unloading cargo."
        )

        def complete() -> None:
            _advance_rest_clock(d, plan.minutes)
            d.hos.on_duty(plan.minutes)
            # A dock wait is engine time too. The settlement already reports
            # the tank, so this one is felt rather than announced.
            d.truck.burn_idle_fuel_over_game_time(plan.minutes * 60.0)
            d._set_status(
                "Trailer dropped. Hooked to an empty, paperwork signed."
                if plan.is_drop_hook
                else "Unloaded. Delivery paperwork signed."
            )
            if plan.is_drop_hook:
                self.ctx.award_achievement("first_delivery_drop")
                if self._hooked_defect():
                    # The write-up leaves with the trailer, which is the only
                    # honest way to be rid of one.
                    self.ctx.award_achievement("dropped_the_bad_one")
            d._arrive()

        if plan.is_drop_hook:
            title = "Dropping the trailer"
            message = (
                f"Backing into the yard at {self.facility} and dropping the "
                f"loaded trailer with {d.job.weight_tons:.0f} tons of "
                f"{d.job.cargo.label} still in it. Gear down, lines off, "
                "hooking a clean empty for the next run."
            )
            status = "Dropping the trailer. Please wait."
        else:
            title = "Unloading cargo"
            message = (
                f"Docked at {self.facility}. Unloading "
                f"{d.job.weight_tons:.0f} tons of {d.job.cargo.label}; "
                "paperwork is being signed."
            )
            status = "Unloading cargo. Please wait."
        self.ctx.replace_state(
            TimedMessageState(
                self.ctx,
                title=title,
                message=message,
                status=status,
                seconds=UNLOADING_WAIT_S,
                on_complete=complete,
                sound_key="poi/dock_and_deliver",
            )
        )

    def _hooked_defect(self) -> str | None:
        from ..models.trailer_yard import pickup_plan

        plan = pickup_plan(self.driving.job, self.ctx.profile)
        return plan.trailer.defect if plan.trailer is not None else None

    def _paperwork(self) -> None:
        d = self.driving
        job = d.job
        hours = d.trip.game_minutes / 60.0
        remaining = job.deadline_game_h - hours
        trip_damage = max(0.0, d.truck.damage_pct - d.start_damage)
        estimated_pay = job.payout(hours, trip_damage)
        tolls = d.trip.toll_expense
        accessorials = carrier_accessorial_charges(job, self.ctx.profile)
        carrier_charges = tolls + charge_total(accessorials)
        # Only what a previous settlement could not collect. Speeding itself
        # is charged on the shoulder by the trooper who saw it, or not at all.
        driver_charges = self.ctx.profile.fines_owed
        net_estimated_pay = max(0.0, estimated_pay - driver_charges)
        advance_due = round(min(self.ctx.profile.pay_advance, net_estimated_pay), 2)
        net_estimated_pay = round(net_estimated_pay - advance_due, 2)
        advance_note = (
            f" A pay advance of {advance_due:,.0f} dollars will be repaid from this settlement."
            if advance_due > 0
            else ""
        )
        timing = (
            f"{remaining:.1f} hours remain before the deadline"
            if remaining >= 0
            else f"{-remaining:.1f} hours past the deadline"
        )
        if trip_damage > 1:
            cargo_condition = (
                f"Damage consideration: this run added {trip_damage:.0f} "
                "percent truck damage, which may reduce final pay."
            )
        else:
            cargo_condition = "Cargo condition: no new damage recorded."
        self.ctx.say(
            f"Paperwork for {self.facility}: {job.weight_tons:.0f} tons of "
            f"{job.cargo.label}. Rate sheet lists {job.pay:,.0f} dollars; "
            f"current gross payout is {estimated_pay:,.0f} dollars. "
            f"Carrier-paid or reimbursed charges recorded so far are "
            f"{carrier_charges:,.0f} dollars, including tolls "
            f"{tolls:,.0f} and accessorials {charge_summary(accessorials)}. "
            "Those charges do not reduce driver pay. "
            f"Fines carried over from earlier loads are "
            f"{driver_charges:,.0f} dollars, for estimated net driver pay "
            f"{net_estimated_pay:,.0f}.{advance_note} "
            f"{timing}. {cargo_condition} {self._finish_instruction()} to settle."
        )

    def _finish_instruction(self) -> str:
        """The action that ends this delivery, named the way the menu names it."""
        return "Drop the loaded trailer" if self.delivery_plan.is_drop_hook else "Dock and deliver"

    def _status(self) -> None:
        d = self.driving
        self.ctx.say(
            f"At {self.facility}. Hauling {d.job.weight_tons:.0f} tons of "
            f"{d.job.cargo.label}. Current speed "
            f"{self.ctx.settings.speed_text(d.truck.speed_mph)}. "
            f"{'Engine running' if d.truck.engine_on else 'Engine off'}. "
            f"Stop, then {self._finish_instruction()}."
        )

    def go_back(self) -> None:
        self.ctx.say(f"At destination. {self._finish_instruction()} to finish.")

    def lines(self) -> list[str]:
        return [
            self.title,
            "",
            f"Facility: {self.facility}",
            f"Speed: {self.ctx.settings.hud_speed_text(self.driving.truck.speed_mph)}",
            f"Engine: {'running' if self.driving.truck.engine_on else 'off'}",
            "Stopping required before delivery settlement.",
            "",
        ] + [("> " if i == self.index else "  ") + item.text for i, item in enumerate(self.items)]


class ArrivalState(MenuState):
    title = "Delivery complete"
    intro_help = (
        "Use up and down arrows to review the delivery summary. Enter repeats "
        "the current line. Escape continues."
    )

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.summary_parts: list[str] = []
        self._achievement_messages: list[str] = []
        self._new_achievement_names: list[str] = []
        self._announcements: list[str] = []
        self.summary_lines: list[str] = []
        self.terminal = ctx.world.home_terminal(driving.job.destination)
        self._settle()

    def _settle_bobtail(self, hours: float, trip_damage: float) -> None:
        """Empty reposition run: relocate to the destination city.

        A self-serve bobtail (owner-operators only) carries no pay. A
        carrier-ASSIGNED reposition (``job.assigned``) still pays -- at the
        reduced empty-mile rate ``make_reposition_job`` already baked into
        ``job.pay`` -- and still earns mileage XP the way any other
        completed drive does, because it IS a completed dispatch
        assignment, just an empty one.
        """
        d = self.driving
        p = self.ctx.profile
        job = d.job
        self.title = "Repositioned"
        p.current_city = job.destination
        driver_charges = p.fines_owed
        if driver_charges:
            p.money -= driver_charges
            p.fines_owed = 0.0
            self.summary_parts.append(
                f"Fines carried over from earlier loads: "
                f"{driver_charges:,.0f} dollars, now settled."
            )
        p.store_truck_condition(d.truck)
        announcements: list[str] = []
        if job.assigned:
            on_time = hours <= job.deadline_game_h
            p.money += job.pay
            previous_level = p.career.level
            standing = enforcement.standing_band(p)
            announcements = p.career.record_delivery(
                job.distance_mi,
                job.pay,
                on_time,
                trip_damage,
                standing_rate=standing_xp_rate(standing),
            )
            announcements.extend(self._handle_fleet_promotion(previous_level, announcements))
            pay_clause = (
                f"Dispatch paid the reposition at the reduced empty-mile rate: "
                f"{job.pay:,.0f} dollars. You now have {p.money:,.0f} dollars. "
            )
        else:
            pay_clause = "No load and no pay. "
        p.game_hours += hours
        p.market.advance_to(p.market_day())
        p.active_trip = None
        p.pay_advance_used_for_load = False
        self.ctx.save_profile()
        self.summary_parts.insert(
            0,
            (
                f"Bobtailed empty to {job.spoken_destination} in {hours:.1f} hours. "
                f"It is {clock_text(to_local(p.game_hours, d.trip.destination_timezone))}. "
                f"{pay_clause}"
                f"You are parked at {self.terminal.name} and can open the "
                f"{job.spoken_destination} dispatch board. "
                f"Fuel {d.truck.fuel_fraction * 100:.0f} percent."
            ),
        )
        if trip_damage > 1:
            self.summary_parts.append(
                f"The empty run added {trip_damage:.0f} percent truck damage. "
                "Visit the garage when you can."
            )
        self.summary_parts.extend(announcements)
        result = self.ctx.award_achievement("bobtail_done", announce=False)
        if result is not None:
            self.summary_parts.append(result.message)
        # The arrival screen and announcement read summary_lines, not parts.
        self.summary_lines = list(self.summary_parts)

    def _cargo_settlement_line(self, cargo) -> str:
        """What the receiver found, what it cost, and who carries the claim.

        Always in that order, and always with the money named, because this
        is the largest single thing that can happen to a run and the player
        has no way to see the trailer.
        """
        p = self.ctx.profile
        owner_op = is_owner_operator(p.business_status)
        claim_holder = (
            "The claim is against your own authority"
            if owner_op
            else "The carrier carries the claim, and it is on your record"
        )
        if self.driving._terse_speech():
            head = {
                "exception": "Exception on the bill.",
                "claim": "Freight claim.",
                "rejected": "Load refused.",
            }[cargo.outcome]
            claim = f" Claim {cargo.claim_value:,.0f} dollars." if cargo.claim_value >= 1.0 else ""
            return (
                f"{head} Load {cargo_condition_text(cargo.condition_pct)}, "
                f"{cargo.condition_pct:.0f} percent. Pay down "
                f"{cargo.pay_loss:,.0f} dollars.{claim}"
            )
        if cargo.rejected:
            return (
                "The receiver refused the load. It came off the trailer "
                f"{cargo_condition_text(cargo.condition_pct)} at "
                f"{cargo.condition_pct:.0f} percent, and a dock will not sign for "
                f"freight in that state. You are paid nothing for the haul: "
                f"{cargo.pay_loss:,.0f} dollars gone, and a claim of about "
                f"{cargo.claim_value:,.0f} dollars for the freight itself. "
                f"{claim_holder}."
            )
        if cargo.outcome == "claim":
            return (
                "The receiver took the load but wrote it up. It arrived "
                f"{cargo_condition_text(cargo.condition_pct)} at "
                f"{cargo.condition_pct:.0f} percent, which is a freight claim of "
                f"about {cargo.claim_value:,.0f} dollars. "
                f"{cargo.pay_loss:,.0f} dollars comes off this settlement. "
                f"{claim_holder}."
            )
        return (
            "The receiver noted an exception on the bill of lading: the load "
            f"arrived {cargo_condition_text(cargo.condition_pct)} at "
            f"{cargo.condition_pct:.0f} percent. That holds back "
            f"{cargo.pay_loss:,.0f} dollars of the haul. Brake and corner gently "
            "and the bill stays clean."
        )

    def _settle(self) -> None:
        d = self.driving
        p = self.ctx.profile
        job = d.job
        hours = _settlement_hours(d)
        trip_damage = max(0.0, d.truck.damage_pct - d.start_damage)
        if job.bobtail:
            self._settle_bobtail(hours, trip_damage)
            return
        gross_base = job.payout(hours, trip_damage)
        toll_expense = d.trip.toll_expense
        accessorials = carrier_accessorial_charges(job, p)
        carrier_charges = toll_expense + charge_total(accessorials)
        # What a previous load could not cover is no longer piled onto this
        # settlement whole. It is a balance owed, and a balance owed is
        # recovered at a capped share further down -- taking all of it here is
        # what made every settlement after the first shortfall pay zero.
        carried_balance = max(0.0, float(p.fines_owed))
        # Nothing is billed here for speeding a trooper did not see: that
        # charge is gone, and it was never anybody's to bill.
        driver_charges = 0.0
        # A company driver who brings a truck back damaged does not get a
        # clean settlement: the carrier eats the repair, and the driver eats
        # the deductible and the safety bonus. An owner-operator has already
        # paid the whole repair themselves, so nobody charges them twice.
        damage_deductible, damage_reputation_hit, damage_reason = (
            (0.0, 0.0, "") if is_owner_operator(p.business_status) else preventable_damage_charge(d)
        )
        driver_charges += damage_deductible
        # The dock inspects before it signs. Under the Carmack Amendment the
        # carrier owes the value of freight it damages, and a receiver may
        # refuse a bad load outright -- which is why this is the largest
        # consequence in the game and comes off the top of the haul.
        cargo = settle_cargo(d.truck.cargo_damage_pct, gross_base)
        driver_charges += cargo.pay_loss
        business = build_business_settlement(
            p.business_status,
            job,
            gross_base,
            on_time=hours <= job.deadline_game_h,
            driver_charges=driver_charges,
            carrier_key=getattr(p, "carrier_key", ""),
            owned_trailers=getattr(p, "owned_trailers", ()),
            reputation=p.career.reputation,
            transponder=has_weigh_station_transponder(p),
        )
        no_on_time_bonus_business = build_business_settlement(
            p.business_status,
            job,
            job.payout(hours, trip_damage, on_time_bonus=0.0),
            on_time=hours <= job.deadline_game_h,
            driver_charges=driver_charges,
            carrier_key=getattr(p, "carrier_key", ""),
            owned_trailers=getattr(p, "owned_trailers", ()),
            reputation=p.career.reputation,
            transponder=has_weigh_station_transponder(p),
        )
        reputation_before = p.career.reputation
        trust_bonus = (
            0.0
            if is_owner_operator(p.business_status)
            else reputation_pay_bonus(business.gross_pay, reputation_before)
        )
        deadline_business = build_business_settlement(
            p.business_status,
            job,
            job.payout(job.deadline_game_h, trip_damage),
            on_time=True,
            driver_charges=driver_charges,
            carrier_key=getattr(p, "carrier_key", ""),
            owned_trailers=getattr(p, "owned_trailers", ()),
            transponder=has_weigh_station_transponder(p),
        )
        gross_pay = business.gross_pay
        on_time_bonus_paid = max(0.0, gross_pay - no_on_time_bonus_business.gross_pay)
        early_bonus = max(0.0, gross_pay - deadline_business.gross_pay)
        # Anything this load could not cover is carried, not forgiven: a load
        # too cheap to pay its charges used to be told it paid them in full.
        # The carried balance from earlier loads is added back after collection
        # below, so it is never taken twice.
        p.fines_owed = business.uncollected_charges
        if not cargo.clean:
            self.summary_parts.append(self._cargo_settlement_line(cargo))
            p.career.reputation = max(0.0, p.career.reputation - cargo.reputation_hit)
            increment_stat(p, "cargo_claims")
        # A balance carried from an earlier load is NOT reported here. It is
        # recovered further down at the capped share, and says so there --
        # billing it in both places is what used to zero a settlement twice.
        if damage_deductible >= 1.0:
            p.career.reputation = max(0.0, p.career.reputation - damage_reputation_hit)
            increment_stat(p, "preventable_equipment_damage")
            self.summary_parts.append(
                f"Driver-responsibility charges: safety ruled the damage preventable, "
                f"{damage_reason}. The carrier covers the repair; your deductible is "
                f"{damage_deductible:,.0f} dollars and the safety bonus is void. "
                f"Reputation down {damage_reputation_hit:.0f}, and it is on your record."
            )
        if business.uncollected_charges > 0:
            paid_now = driver_charges - business.uncollected_charges
            self.summary_parts.append(
                f"This load only covered {paid_now:,.0f} dollars of those "
                f"charges, so {business.uncollected_charges:,.0f} dollars stays "
                "owed. A quarter of each settlement from here goes to it, never more."
            )
        # Tickets from being pulled over were already paid on the spot; report
        # them for transparency but don't deduct again at settlement.
        if d.speeding_tickets:
            self.summary_parts.append(
                f"On-the-spot speeding tickets this trip: {d.speeding_tickets}, "
                f"already paid, {d.ticket_fines_paid:,.0f} dollars."
            )
        # Engine brake citations were also paid on the spot; reported here for
        # the same transparency, never deducted again.
        if d.jake_zone_fines:
            self.summary_parts.append(
                f"Engine brake citations this trip: {d.jake_zone_fines}, "
                f"already paid, {d.jake_fines_paid:,.0f} dollars."
            )
        # Anything the trip did to your standing is said once more here, so a
        # suspension heard out on the road is not the last word on it.
        for line in d.record_events:
            self.summary_parts.append(line)
        if business.business_charges:
            self.summary_parts.append(
                f"Owner-operator business costs: {business.business_charge_summary}."
            )
        net_pay = business.net_before_advance
        # What the load earned the driver, before any advance comes back out of
        # it -- which is exactly what the business settlement already calls
        # net_before_advance. An advance is those same dollars paid early, so
        # lifetime earnings book the whole settlement; book only the remainder
        # and the advanced money becomes cash the career cannot account for,
        # which reads as an edited save to cloud upload screening.
        settled_pay = net_pay
        # A balance owed and an advance come out of the same capped share, so a
        # driver who is carrying both still finishes the run with money. With
        # nothing owed this is the arithmetic it has always been.
        collected, advance_repaid = deductions_from_settlement(
            carried_balance, p.pay_advance, net_pay
        )
        if collected > 0:
            net_pay = round(net_pay - collected, 2)
            self.summary_parts.append(
                f"Balance owed: {collected:,.0f} dollars of this settlement went "
                "to paying it down. A quarter of a settlement is the most that "
                "ever goes to it, so three quarters always reaches you."
            )
        if advance_repaid > 0:
            net_pay = round(net_pay - advance_repaid, 2)
            p.pay_advance = round(p.pay_advance - advance_repaid, 2)
            outstanding = (
                f" {p.pay_advance:,.0f} dollars of advance still outstanding."
                if p.pay_advance >= 1.0
                else ""
            )
            self.summary_parts.append(
                f"Pay advance repaid from this settlement: "
                f"{advance_repaid:,.0f} dollars.{outstanding}"
            )
        # What is left of the old balance rides on with whatever this load could
        # not cover.
        p.fines_owed = round(p.fines_owed + max(0.0, carried_balance - collected), 2)
        on_time = hours <= job.deadline_game_h
        p.money += net_pay
        p.current_city = job.destination
        from ..models.jobs import lane_key

        p.remember_lane(lane_key(self.ctx.world, job))
        # Tire, brake, and engine wear now come off the truck itself -- the
        # physics accrued them mile by mile during the run. Grime stays a
        # simple per-mile film; it has no physics to earn it.
        p.store_truck_condition(d.truck)
        road_grime_added = min(100.0, job.distance_mi * ROAD_GRIME_PER_MILE)
        p.road_grime_pct = min(100.0, p.road_grime_pct + road_grime_added)
        previous_level = p.career.level
        # Where the driver stands with the carrier, read after the money has
        # moved so a settlement that pays the balance down counts immediately.
        standing = enforcement.standing_band(p)
        announcements = p.career.record_delivery(
            job.distance_mi,
            # The whole settlement, not what survived the advance repayment.
            settled_pay,
            on_time,
            trip_damage,
            cargo_class_mult=xp_class_multiplier(job.cargo),
            standing_rate=standing_xp_rate(standing),
        )
        announcements.extend(self._handle_fleet_promotion(previous_level, announcements))
        xp_bonus_notes = []
        if xp_class_multiplier(job.cargo) > 1.0:
            xp_bonus_notes.append("demanding freight")
        streak_bonus = xp_streak_bonus(p.career.on_time_streak) if on_time else 0.0
        if streak_bonus > 0.0:
            xp_bonus_notes.append(f"a {p.career.on_time_streak}-delivery on-time streak")
        # The slower rate rides the line that is already there rather than
        # arriving as its own announcement, and it never names a multiplier: a
        # number the player cannot check turns every settlement into arithmetic.
        rate_clause = xp_rate_settlement_clause(standing)
        if xp_bonus_notes:
            tail = f", {rate_clause}" if rate_clause else ""
            self.summary_parts.append(
                f"Career experience bonus for {' and '.join(xp_bonus_notes)}{tail}."
            )
        elif rate_clause:
            self.summary_parts.append(f"Career experience is coming in {rate_clause}.")
        self._debt_settlement_lines()
        if trust_bonus >= 1.0:
            self.summary_parts.append(
                f"Dispatch trust bonus: {trust_bonus:,.0f} dollars for your "
                f"{reputation_before:.0f} reputation."
            )
        p.game_hours += hours
        p.market.advance_to(p.market_day())
        p.active_trip = None
        p.pay_advance_used_for_load = False
        self.ctx.save_profile()
        from ..online_journal import queue_career_milestones, queue_delivery

        occurred_at_ms = int(time.time() * 1000)
        if queue_delivery(
            self.ctx._app.journal,
            p,
            job,
            origin=self.ctx.world.spoken_city(job.origin),
            destination=self.ctx.world.spoken_city(job.destination),
            on_time=on_time,
            occurred_at_ms=occurred_at_ms,
            undamaged=trip_damage <= 1,
        ):
            self.ctx._app.journal.flush_async()
        if queue_career_milestones(
            self.ctx._app.journal,
            p,
            previous_level=previous_level,
            occurred_at_ms=occurred_at_ms,
        ):
            self.ctx._app.journal.flush_async()

        self.summary_parts.insert(
            0,
            (
                f"Delivered {job.weight_tons:.0f} tons of {job.cargo.label} to "
                f"{job.spoken_destination} in {hours:.1f} hours, "
                f"{'on time' if on_time else 'late'}. "
                f"It is {clock_text(to_local(p.game_hours, d.trip.destination_timezone))}. "
                f"{pay_label(p.business_status)} {gross_pay:,.0f} dollars. "
                f"Carrier-paid or reimbursed charges {carrier_charges:,.0f} dollars: "
                f"tolls {toll_expense:,.0f}, accessorials "
                f"{charge_summary(accessorials)}. "
                "These are billed to carrier settlement and not deducted from driver pay. "
                f"Business status: {business.status_label}. "
                f"Business costs {business.business_charge_total:,.0f} dollars. "
                f"Fines carried over {driver_charges:,.0f} dollars. "
                f"Net driver pay {net_pay:,.0f} "
                f"dollars, and you now have {p.money:,.0f}. "
                f"After unloading, dispatch has you parked at "
                f"{self.terminal.name} for the {job.spoken_destination} service area."
            ),
        )
        if on_time_bonus_paid >= 1.0:
            self.summary_parts.append(
                f"On-time delivery bonus: {on_time_bonus_paid:,.0f} dollars "
                "for hitting the delivery window."
            )
        if early_bonus >= 1.0:
            self.summary_parts.append(f"Early delivery bonus: {early_bonus:,.0f} dollars.")
        damage_line = damage_summary_line(self.ctx.settings, d.truck, trip_damage)
        if damage_line is not None:
            self.summary_parts.append(damage_line)
        wear_parts = []
        for added, meter in (
            (max(0.0, d.truck.tire_wear_pct - d.start_tire_wear), "tire wear"),
            (max(0.0, d.truck.brake_wear_pct - d.start_brake_wear), "brake wear"),
            (max(0.0, d.truck.engine_wear_pct - d.start_engine_wear), "engine wear"),
            (road_grime_added, "road grime"),
        ):
            if added >= 0.1:
                wear_parts.append(f"{added:.1f} percent {meter}")
        if wear_parts:
            joined = (
                ", ".join(wear_parts[:-1]) + f", and {wear_parts[-1]}"
                if len(wear_parts) > 1
                else wear_parts[0]
            )
            self.summary_parts.append(f"The run added {joined}.")
        self.summary_parts.extend(announcements)
        self._award_arrival_achievements(
            on_time=on_time,
            trip_damage=trip_damage,
            toll_expense=toll_expense,
            route_miles=d.route.miles,
            speeding_tickets=d.speeding_tickets,
            gross_pay=gross_pay,
        )
        achievement_summary = self._achievement_summary_line()
        if achievement_summary is not None:
            self.summary_parts.append(achievement_summary)
        self._queue_notable_share(
            on_time=on_time, previous_level=previous_level, occurred_at_ms=occurred_at_ms
        )
        timing = "On time" if on_time else "Late"
        bonus_lines = []
        if on_time_bonus_paid >= 1.0:
            bonus_lines.append(f"On-time delivery bonus: {on_time_bonus_paid:,.0f} dollars.")
        if early_bonus >= 1.0:
            bonus_lines.append(f"Early delivery bonus: {early_bonus:,.0f} dollars.")
        if not bonus_lines:
            bonus_lines.append("No delivery bonus on this run.")
        # Condition rows carry information only when something happened: a run
        # that added no damage, a near-full tank, and an undamaged truck are
        # the unremarkable default, and the review keys still reach the full
        # state on demand (research doc R10).
        condition_lines = []
        if trip_damage > 1:
            condition_lines.append(f"Truck damage added on this run: {trip_damage:.0f} percent.")
        if d.truck.fuel_fraction < SETTLEMENT_LOW_FUEL_FRACTION:
            condition_lines.append(f"Fuel remaining: {d.truck.fuel_fraction * 100:.0f} percent.")
        if d.truck.damage_pct >= 1.0:
            condition_lines.append(f"Truck damage now: {d.truck.damage_pct:.0f} percent.")
        # Achievements collapse to one row that names them; the full flavor
        # for each waits in the achievements menu and the message log, so the
        # settlement is not six paragraphs of comedy read at a parked truck
        # (research doc R9).
        career_lines = list(announcements)
        if achievement_summary is not None:
            career_lines.append(achievement_summary)
        advance_lines = []
        if advance_repaid > 0:
            advance_lines.append(f"Pay advance repaid: {advance_repaid:,.0f} dollars.")
        if p.pay_advance >= 1.0:
            advance_lines.append(f"Pay advance still outstanding: {p.pay_advance:,.0f} dollars.")
        # This load's own driver-responsibility charges (a damage deductible,
        # a freight claim) are a different thing from a balance carried in
        # from an earlier load, and each has to be able to read zero without
        # the other's number standing in for it. The reviewable list used to
        # print the first under the second's label, so a settlement that
        # quietly took money off a balance announced "Fines carried over from
        # earlier loads: 0 dollars".
        charge_lines = []
        if driver_charges >= 1.0:
            charge_lines.append(
                f"Driver-responsibility charges this load: {driver_charges:,.0f} dollars."
            )
        if collected >= 1.0:
            charge_lines.append(
                f"Balance owed: {collected:,.0f} dollars of this settlement paid it down, "
                f"leaving {p.fines_owed:,.0f} dollars owed."
            )
        if not charge_lines:
            charge_lines.append("No driver-responsibility charges and no balance owed.")
        business_cost_lines = []
        if business.business_charges:
            business_cost_lines = [
                f"Business costs: {business.business_charge_total:,.0f} dollars.",
                f"Business cost detail: {business.business_charge_summary}.",
            ]
        self.summary_lines = [
            f"Delivered {job.weight_tons:.0f} tons of {job.cargo.label} "
            f"to {job.spoken_destination}.",
            f"Trip time: {hours:.1f} hours, {timing.lower()}.",
            f"It is {clock_text(to_local(p.game_hours, d.trip.destination_timezone))}.",
            f"Parked at {self.terminal.name} for the {job.spoken_destination} service area.",
            f"{pay_label(p.business_status)}: {gross_pay:,.0f} dollars.",
            f"Carrier-paid or reimbursed charges: {carrier_charges:,.0f} "
            f"dollars, including tolls {toll_expense:,.0f} and "
            f"accessorials {charge_summary(accessorials)}.",
            f"Business status: {business.status_label}.",
            *business_cost_lines,
            *charge_lines,
            *advance_lines,
            f"Net driver pay: {net_pay:,.0f} dollars.",
            f"Money after settlement: {p.money:,.0f} dollars.",
            *bonus_lines,
            f"Route: {' to '.join(self.ctx.world.spoken_city(c) for c in d.route.cities)}.",
            f"Distance credited: {self.ctx.settings.distance_text(job.distance_mi)}.",
            *condition_lines,
            *career_lines,
        ]
        self._announcements = announcements

    def _debt_settlement_lines(self) -> None:
        """Say what a balance owed did to this settlement, and warn once a rung.

        Rungs move on the same discipline as the trust band: spoken when they
        change, never on a timer, and never repeated.
        """
        from ..models import solvency

        p = self.ctx.profile
        record = p.driving_record
        written_off = solvency.apply_hard_cap(p)
        if written_off >= 1.0:
            self.summary_parts.append(
                f"{p.carrier_name} wrote off {written_off:,.0f} dollars of what "
                "you owe. They hold the balance where it is rather than let it "
                "climb, because they would rather keep you working."
            )
        rung = solvency.debt_rung(p)
        if rung == int(record.debt_rung_heard):
            return
        was = int(record.debt_rung_heard)
        record.debt_rung_heard = rung
        if rung == 0:
            if was > 0:
                self.summary_parts.append(
                    "You are square with your carrier again. Nothing is owed, "
                    "and every settlement reaches you whole from here."
                )
            return
        line = solvency.debt_warning_line(p, terse=self.driving._terse_speech())
        if line:
            self.summary_parts.append(line)

    def _rewrite_unlock_promise(self, announcements: list[str] | None) -> None:
        """Stop a level-up promising a tractor the yard is not handing over."""
        from ..models.carrier_fleet import WITHHELD_UNLOCK_TAIL

        if not announcements:
            return
        unlock = self.ctx.profile.career.rank.unlock
        target = f"Unlock: {unlock}"
        for index, message in enumerate(announcements):
            if message.startswith("Level up!") and target in message:
                announcements[index] = message.replace(target, f"{target} {WITHHELD_UNLOCK_TAIL}")
                return

    def _handle_fleet_promotion(
        self, previous_level: int, announcements: list[str] | None = None
    ) -> list[str]:
        """Swap the carrier tractor when a level-up crosses a fleet tier.

        The carrier hands the new unit over road-ready, so the profile's
        equipment condition resets with it -- company repairs are carrier
        billed anyway, this just skips the paperwork.

        Unless the yard is not handing it over. A driver whose standing holds
        them below their level keeps the truck they are in, untouched: the
        road-ready reset belongs to the tractor changing hands, and handing
        someone a spotless lesser truck would tell them something happened
        when nothing did.
        """
        from ..models.carrier_fleet import (
            assigned_truck_key,
            equipment_held_back,
            fleet_tier_for_level,
            fleet_upgrade_announcement,
            withheld_promotion_text,
        )
        from ..models.trucks import TRUCK_CATALOG

        p = self.ctx.profile
        if p.owns_equipment() or p.career.level <= previous_level:
            return []
        if fleet_tier_for_level(previous_level).key == fleet_tier_for_level(p.career.level).key:
            return []
        if equipment_held_back(p):
            self._rewrite_unlock_promise(announcements)
            return [withheld_promotion_text(p)]
        model = TRUCK_CATALOG[assigned_truck_key(p)]
        p.truck_fuel_gal = model.specs.fuel_tank_gal
        p.truck_damage_pct = 0.0
        p.tire_wear_pct = 0.0
        p.road_grime_pct = 0.0
        for badge in ("fleet_upgrade",) + (
            ("fleet_flagship",) if fleet_tier_for_level(p.career.level).key == "first_pick" else ()
        ):
            result = self.ctx.award_achievement(badge, announce=False)
            if result is not None:
                self._achievement_messages.append(result.message)
                self._new_achievement_names.append(result.achievement.name)
        return [fleet_upgrade_announcement(p)]

    def _queue_notable_share(
        self, *, on_time: bool, previous_level: int, occurred_at_ms: int
    ) -> None:
        """Offer this delivery to the player's Mastodon account when it earned
        something worth telling: a new achievement, a level, or a streak milestone.
        Routine runs stay quiet, and the outbox itself is inert unless the
        player turned Mastodon sharing on and linked an account."""
        from ..online_journal import queue_mastodon_share

        p = self.ctx.profile
        job = self.driving.job
        reasons: list[dict] = []
        if p.career.level > previous_level:
            reasons.append({"type": "level", "level": int(p.career.level)})
        if self._new_achievement_names:
            reasons.append({"type": "achievements", "names": self._new_achievement_names[:10]})
        stats = p.achievement_stats if isinstance(p.achievement_stats, dict) else {}
        streak = int(stats.get("perfect_streak", 0))
        if streak in (5, 10, 25, 50, 100):
            reasons.append({"type": "streak", "count": streak})
        if queue_mastodon_share(
            self.ctx._app.mastodon,
            p,
            job,
            origin=self.ctx.world.spoken_city(job.origin),
            destination=self.ctx.world.spoken_city(job.destination),
            on_time=on_time,
            occurred_at_ms=occurred_at_ms,
            reasons=reasons,
        ):
            self.ctx._app.mastodon.flush_async()

    def _live_calendar(self) -> bool:
        """Whether live weather is driving the calendar right now.

        The same two-part answer the terminal's Time and weather readout uses:
        a provider has to be attached AND the player has to have left the
        calendar following it. Read defensively -- a trip built without a
        weather system must not crash a settlement.
        """
        weather = getattr(getattr(self, "driving", None), "trip", None)
        provider = getattr(getattr(weather, "weather", None), "provider", None)
        return provider is not None and bool(
            getattr(self.ctx.settings, "live_weather_controls_calendar", False)
        )

    def _achievement_summary_line(self) -> str | None:
        """One row naming the run's new achievements, not one paragraph each.

        The full flavor for every badge stays in the achievements menu and
        the message log, so the settlement reports the count and the names and
        leaves the story for a parked, unhurried read (research doc R9).
        """
        names = self._new_achievement_names
        if not names:
            return None
        if len(names) == 1:
            return f"New achievement! {names[0]}."
        return f"New achievements! {', '.join(names)}."

    def _award_arrival_achievements(
        self,
        *,
        on_time: bool,
        trip_damage: float,
        toll_expense: float,
        route_miles: float,
        speeding_tickets: int,
        gross_pay: float = 0.0,
    ) -> None:
        p = self.ctx.profile
        route = self.driving.route
        world = self.ctx.world
        states = {world.cities[city].state for city in route.cities}
        regions = {world.cities[city].region for city in route.cities}
        region_count = 0
        for region in regions:
            region_count = add_unique_stat(p, "regions_visited", region)

        ids = ["first_delivery"]
        # Rookie chain: spread across the first few runs instead of all
        # landing on delivery one, alongside first_delivery.
        if on_time and p.career.deliveries >= 2:
            ids.append("first_on_time")
        if trip_damage <= 1.0 and p.career.deliveries >= 3:
            ids.append("clean_delivery")
        if speeding_tickets == 0 and p.career.deliveries >= 4:
            ids.append("speed_limit_saint")
        if toll_expense > 0:
            ids.append("toll_paid")
        elif route_miles >= 300.0:
            ids.append("no_toll_long")
        if len(states) >= 2:
            ids.append("state_crossing")
        if len(states) >= 3:
            ids.append("multi_state")
        if len(regions) >= 3 or region_count >= 3:
            ids.append("three_regions")
        if route_miles >= 900.0:
            ids.append("long_haul")
        if p.career.deliveries >= 5:
            ids.append("five_deliveries")
        if p.career.deliveries >= 10:
            ids.append("ten_deliveries")
        if p.career.level >= 3:
            ids.append("level_three")
        if p.money >= 25_000.0:
            ids.append("twenty_five_grand")
        if p.career.total_miles >= 1_000.0:
            ids.append("thousand_miles")

        # -- Landmarks: direction, famous corridors, and city-arrival badges --
        origin, dest = route.cities[0], route.cities[-1]
        origin_lon = world.cities[origin].lon
        dest_lon = world.cities[dest].lon
        if dest_lon - origin_lon > 1.0:
            ids.append("eastbound_delivery")
        if origin_lon - dest_lon > 1.0:
            ids.append("westbound_delivery")
        if abs(dest_lon - origin_lon) >= 35.0:
            ids.append("coast_to_coast")
        route66 = {
            "chicago_il_us",
            "st_louis_mo_us",
            "tulsa_ok_us",
            "oklahoma_city_ok_us",
            "amarillo_tx_us",
            "albuquerque_nm_us",
            "flagstaff_az_us",
            "los_angeles_ca_us",
        }
        if origin in route66 and dest in route66:
            ids.append("route66_run")
        # Wall-clock badge conditions ("by Daybreak", "Midnight Freight") read
        # the destination's local clock, matching what the player just heard.
        arrival_hour = self.driving.trip.local_hour
        if dest in SIMPLE_ARRIVAL_BADGES:
            ids.append(SIMPLE_ARRIVAL_BADGES[dest])
        # Badges whose title names a condition, so the condition is enforced:
        if dest == "amarillo_tx_us" and 5.0 <= arrival_hour < 12.0:  # "by Daybreak"
            ids.append("amarillo_arrival")
        if dest == "tulsa_ok_us" and on_time:  # "Right on Schedule"
            ids.append("tulsa_arrival")
        if world.cities[dest].state == "Georgia" and is_night(arrival_hour):
            ids.append("georgia_arrival")  # "Midnight Freight"
        # Departures: the title puts the city in the rearview / "out of" it.
        if origin == "lubbock_tx_us":  # "in the Rearview"
            ids.append("lubbock_arrival")
        if origin == "detroit_mi_us":  # "Last Load Out of"
            ids.append("detroit_run")

        # -- Challenges: grind milestones, long hauls, spotless runs ----------
        if region_count >= 14:
            ids.append("all_regions")
        if p.career.deliveries >= 50:
            ids.append("fifty_deliveries")
        if p.career.deliveries >= 100:
            ids.append("hundred_deliveries")
        if p.career.total_miles >= 10_000.0:
            ids.append("ten_thousand_miles")
        if p.career.total_miles >= 50_000.0:
            ids.append("fifty_thousand_miles")
        if p.money >= 100_000.0:
            ids.append("hundred_grand")
        # Ladder milestones for the 30-level arc. "max_level" is the level-20
        # veteran badge (its copy has said "level twenty" since the ladder
        # grew past the old cap).
        level_badges = {
            5: "level_five",
            10: "level_ten",
            15: "level_fifteen",
            20: "max_level",
            25: "level_twenty_five",
            30: "level_thirty",
        }
        for milestone, badge in level_badges.items():
            if p.career.level >= milestone:
                ids.append(badge)
        if p.career.reputation >= 100.0:
            ids.append("top_reputation")
        if gross_pay >= 4_000.0:
            ids.append("big_payday")
        if route_miles >= 1_200.0 and on_time and trip_damage <= 1.0:
            ids.append("grueling_clean")
        if any(leg.terrain == "mountain" for leg in route.legs) and trip_damage <= 1.0:
            ids.append("mountain_clean")
        if len(route.legs) >= 4:
            ids.append("multi_leg_haul")
        # Five consecutive on-time, undamaged, ticket-free deliveries.
        stats = p.achievement_stats if isinstance(p.achievement_stats, dict) else {}
        p.achievement_stats = stats
        perfect = on_time and trip_damage <= 1.0 and speeding_tickets == 0
        streak = int(stats.get("perfect_streak", 0)) + 1 if perfect else 0
        stats["perfect_streak"] = streak
        if streak >= 5:
            ids.append("perfect_streak")

        # -- Landmarks, second verse: state, region, and timed city badges ----
        d = self.driving
        job = d.job
        hours = d.trip.game_minutes / 60.0
        dest_state = world.cities[dest].state
        dest_region = world.cities[dest].region
        state_badges = {
            "Virginia": "virginia_line",
            "Kentucky": "kentucky_delivery",
            "New Jersey": "jersey_delivery",
            "Wyoming": "wyoming_delivery",
            "North Dakota": "dakota_delivery",
            "South Dakota": "dakota_delivery",
            "Montana": "montana_delivery",
            "Maine": "new_england_delivery",
            "Vermont": "new_england_delivery",
            "New Hampshire": "new_england_delivery",
        }
        if dest_state in state_badges:
            ids.append(state_badges[dest_state])
        # Map coverage milestones across the 623-city network.
        city_count = add_unique_stat(p, "cities_delivered", dest)
        if city_count >= 25:
            ids.append("twenty_five_cities")
        if city_count >= 75:
            ids.append("seventy_five_cities")
        if city_count >= 150:
            ids.append("hundred_fifty_cities")
        state_count = add_unique_stat(p, "states_delivered", dest_state)
        if state_count >= 15:
            ids.append("fifteen_states")
        if state_count >= 30:
            ids.append("thirty_states")
        region_badges = {
            "appalachia": "appalachia_delivery",
            "pacific_northwest": "pnw_delivery",
        }
        if dest_region in region_badges:
            ids.append(region_badges[dest_region])
        if dest == "birmingham_al_us" and 6.0 <= arrival_hour < 11.0:  # morning run
            ids.append("birmingham_morning")
        if dest == "waco_tx_us" and trip_damage <= 1.0:  # "Just Fine"
            ids.append("waco_survivor")
        if dest == "gulfport_ms_us" and arrival_hour < 14.0:  # "by Two"
            ids.append("gulf_coast_by_two")
        if dest in {"santa_rosa_ca_us", "chico_ca_us"}:  # big-tree country
            ids.append("norcal_giants")
        triangle = {
            "dallas_tx_us",
            "fort_worth_tx_us",
            "houston_tx_us",
            "san_antonio_tx_us",
            "austin_tx_us",
        }
        if origin in triangle and dest in triangle:
            ids.append("texas_triangle")

        # -- Routes, second verse: compass runs and marathon dispatches -------
        origin_lat = world.cities[origin].lat
        dest_lat = world.cities[dest].lat
        if dest_lat - origin_lat >= 4.0:
            ids.append("true_north_run")
        if origin_lat - dest_lat >= 4.0:
            ids.append("southbound_run")
        if {"flat", "hills", "mountain"} <= {leg.terrain for leg in route.legs}:
            ids.append("all_terrain_route")
        if hours >= 24.0:
            ids.append("long_day_run")
        if stats.get("last_route") == [dest, origin]:
            ids.append("return_trip")
        stats["last_route"] = [origin, dest]

        # -- Cargo: what's in the box matters ---------------------------------
        endorsement_badges = {
            "refrigerated": "reefer_load",
            "heavy_haul": "heavy_haul_load",
            "high_value": "high_value_load",
        }
        if job.cargo.endorsement in endorsement_badges:
            ids.append(endorsement_badges[job.cargo.endorsement])
        if job.cargo.key in {"grain", "farm_inputs"}:
            ids.append("farm_load")
        if job.weight_tons >= 24.0:
            ids.append("max_gross_load")

        # -- Career, second verse: the numbers keep climbing ------------------
        if p.career.deliveries >= 25:
            ids.append("twenty_five_deliveries")
        if p.career.deliveries >= 200:
            ids.append("two_hundred_deliveries")
        if p.money >= 250_000.0:
            ids.append("quarter_million_bank")
        if p.career.total_earnings >= 500_000.0:
            ids.append("half_million_earned")
        if p.career.total_miles >= 100_000.0:
            ids.append("hundred_k_miles")
        if p.career.reputation >= 90.0:
            ids.append("rep_ninety")
        if p.game_hours >= 30.0 * 24.0:
            ids.append("month_on_road")
        # A career's home city is where its very first delivery loaded up.
        if p.career.deliveries == 1:
            stats.setdefault("home_city", origin)
        if p.career.deliveries >= 10 and dest == stats.get("home_city"):
            ids.append("home_return")

        # -- Seasons: the calendar rides shotgun ------------------------------
        from ..sim.season import date_text, is_friday_the_thirteenth, player_calendar_hours
        from ..sim.season import season as season_of

        # The calendar the player HEARS, not raw career time. These badges
        # answer to a date and a season the player was told, so reading the
        # un-offset career clock fired April's Fool in August with the
        # real-time calendar on (reported 2026-08-11), and called a delivery
        # a winter one while the live weather said otherwise.
        calendar_hours = player_calendar_hours(p, live_calendar=self._live_calendar())
        career_season = season_of(calendar_hours)
        if career_season == "winter":
            ids.append("winter_delivery")
        if add_unique_stat(p, "seasons_delivered", career_season) >= 4:
            ids.append("four_seasons")
        if dest_region == "desert_southwest" and career_season == "summer":
            ids.append("desert_summer")
        if date_text(calendar_hours) == "April 1":
            ids.append("april_first")

        # -- Deliveries, second verse: clocks, gauges, and close calls --------
        if on_time and hours >= 0.9 * job.deadline_game_h:
            ids.append("deadline_squeaker")
        if not on_time:
            ids.append("first_late")
        if arrival_hour < 4.0:
            ids.append("midnight_delivery")
        # Careers start at 6:00, so "before the roosters" means before that.
        if 3.0 <= d.trip.start_hour < 6.0:
            ids.append("dawn_run")
        if d.truck.fuel_fraction < 0.08:
            ids.append("fuel_fumes")
        if route_miles >= 300.0 and on_time and trip_damage <= 1.0 and speeding_tickets == 0:
            ids.append("spotless_long")
        if d.speeding_tickets >= 1:
            ids.append("first_ticket")
        if d.speeding_tickets >= 2:
            ids.append("second_ticket")

        # -- Dates worth noticing, and records worth keeping ------------------
        arrival_date = date_text(calendar_hours)
        if arrival_date == "December 25":
            ids.append("christmas_delivery")
        if arrival_date == "January 1" and arrival_hour < 3.0:
            ids.append("new_year_run")
        if is_friday_the_thirteenth(calendar_hours) and trip_damage <= 1.0:
            ids.append("friday_thirteenth")
        if job.distance_mi >= 1_000.0:
            ids.append("five_hundred_mile_run")
        if job.weight_tons >= 16.0:
            ids.append("sixteen_tons")
        if arrival_hour < 4.0 and increment_stat(p, "night_deliveries") >= 10:
            ids.append("night_shift_regular")
        # A clean licence is a running record, so a single ticket ends it: the
        # counter only advances on deliveries that came with none.
        if d.speeding_tickets == 0:
            if increment_stat(p, "ticket_free_deliveries") >= 50:
                ids.append("never_fought_the_law")
        else:
            reset_stat(p, "ticket_free_deliveries")
        # Everything that could have gone wrong, going wrong slowly.
        if (
            on_time
            and arrival_hour < 4.0
            and d.truck.fuel_fraction < 0.15
            and d.weather.effects.grip < 0.9
        ):
            ids.append("one_for_the_road")
        # The tractor and the band it came out of: slip-seating means a junior
        # driver meets a lot of iron.
        if add_unique_stat(p, "tractors_driven", p.active_truck_key()) >= 5:
            ids.append("five_tractors")
        if not p.owns_equipment():
            from ..models.carrier_fleet import FLEET_TIERS, fleet_tier_for_level

            tier = fleet_tier_for_level(int(p.career.level)).key
            if add_unique_stat(p, "fleet_tiers_driven", tier) >= len(FLEET_TIERS):
                ids.append("every_fleet_tier")

        for achievement_id in ids:
            result = self.ctx.award_achievement(achievement_id, announce=False)
            if result is not None:
                self._achievement_messages.append(result.message)
                self._new_achievement_names.append(result.achievement.name)
        self.ctx.save_profile()

    def enter(self) -> None:
        self.ctx.audio.stop_world()
        self.ctx.audio.play("ui/job_complete")
        if self._announcements or self._achievement_messages:
            self.ctx.audio.play("ui/level_up")
        self.ctx.audio.play("ui/cash")
        self.items = self.build_items()
        self.index = min(self.index, max(0, len(self.items) - 1))
        self.announce_entry()

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.title}. {self.current_text()}",
            interrupt=False,
        )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                line, lambda line=line: self.ctx.say(line), help="Repeat this settlement line."
            )
            for line in self.summary_lines
        ]
        items.append(
            MenuItem(
                "Copy delivery summary to clipboard",
                self._copy_summary,
                help="Copies the settlement lines above as plain text, so you "
                "can paste them into a post or message.",
                select_sound=None,
            )
        )
        items.append(MenuItem("Continue to " + self.terminal.name, self._continue))
        return items

    def _copy_summary(self) -> None:
        from .online_states import write_clipboard_text

        text = "\n".join([f"Freight Fate: {self.title}.", *self.summary_lines])
        if write_clipboard_text(text):
            self.ctx.audio.play("ui/menu_select")
            self.ctx.say("Delivery summary copied to clipboard.", interrupt=True, review=False)
        else:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "I could not copy to the clipboard. The summary lines above "
                "can still be read one at a time.",
                interrupt=True,
                review=False,
            )

    def go_back(self) -> None:
        self._continue()

    def _continue(self) -> None:
        from .city import CityMenuState

        self.ctx.replace_state(CityMenuState(self.ctx))

    def lines(self) -> list[str]:
        return (
            [self.title, ""]
            + self.summary_lines
            + [""]
            + [("> " if i == self.index else "  ") + item.text for i, item in enumerate(self.items)]
        )
