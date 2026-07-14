# ruff: noqa: F403,F405
from __future__ import annotations

import time

from ..sim.timezones import to_local
from .base import TimedMessageState
from .driving_core import *
from .driving_rest_states import ShoulderSleepConfirmationState

DELIVERY_SETTLEMENT_MAX_AVERAGE_MPH = 55.0
ROAD_GRIME_PER_MILE = 0.004

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

    intro_help = (
        "Use up and down arrows to review each line. Enter repeats the current "
        "line. Escape goes back to the status screens."
    )
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

    def build_items(self) -> list[MenuItem]:
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
        if self.screen == "map":
            return self._map_lines()
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
            "Load: no cargo, local city service drive"
            if d.phase == DRIVE_PHASE_CITY_SERVICE
            else f"Load: {d.job.weight_tons:.0f} tons of {d.job.cargo.label}, "
            f"gross {d.truck.gross_mass_kg / KG_PER_TON:.0f} tons"
        )
        time_line = (
            f"Time: {clock_text(d.trip.local_hour)} {d.trip.current_timezone.name}, "
            f"{hours_used:.1f} hours used"
            if d.phase == DRIVE_PHASE_CITY_SERVICE
            else f"Time: {clock_text(d.trip.local_hour)} {d.trip.current_timezone.name}, "
            f"{deadline_text}"
        )
        return [
            f"Driver: {profile.name}",
            f"Money: {profile.money:,.0f} dollars",
            load_line,
            f"Objective: {d._objective_text()}",
            f"Truck: fuel {t.fuel_fraction * 100:.0f} percent, damage {t.damage_pct:.0f} percent",
            f"Transmission: {'automatic' if t.transmission.automatic else 'manual'}, {d._gear_text()}",
            f"Fatigue: {profile.fatigue:.0f} percent",
            f"Hours: {d.hos.summary(self.ctx.settings.hos_mode).rstrip('.')}",
            time_line,
        ]

    def _map_lines(self) -> list[str]:
        d = self.driving
        route = d.route
        settings = self.ctx.settings
        lines = [
            f"Route: {' to '.join(route.cities)}",
            f"Highways: {_join_phrase(route.highways)}",
            f"Progress: {settings.distance_text(d.trip.position_mi)} driven, "
            f"{settings.distance_text(d.trip.remaining_miles)} remaining",
            f"Guidance: {d.trip.next_navigation_context(settings.imperial_units)}",
        ]
        upcoming = [stop for stop in d.trip.stops if stop.at_mi >= d.trip.position_mi - 0.05][:5]
        if upcoming:
            for stop in upcoming:
                ahead = max(0.0, stop.at_mi - d.trip.position_mi)
                lines.append(
                    f"Stop in {settings.distance_text(ahead)}: {stop.spoken_name}; "
                    f"{_poi_offers_text(stop)}."
                )
        else:
            lines.append("Stops: no more listed route stops before destination.")
        next_cues = [
            cue
            for cue in d.trip.navigation_cues
            if cue.at_mi > d.trip.position_mi + 0.05 and cue.kind != "rest_stop"
        ][:4]
        for cue in next_cues:
            ahead = max(0.0, cue.at_mi - d.trip.position_mi)
            speed = f" at {settings.speed_text(cue.speed_mph)}" if cue.speed_mph is not None else ""
            lines.append(f"Map point in {settings.distance_text(ahead)}: {cue.text}{speed}.")
        if route.estimated_tolls > 0:
            lines.append(
                f"Estimated carrier-paid toll exposure: {route.estimated_tolls:,.0f} dollars."
            )
        return lines

    def _radio_lines(self) -> list[str]:
        d = self.driving
        d._sync_radio_settings()
        settings = self.ctx.settings
        position = d.radio.position
        lines = [
            d.radio.status_text(),
            (
                "Real public streams: on, streamer-safe mode off"
                if settings.radio_real_streams and not settings.radio_streamer_safe
                else "Real public streams are hidden unless real streams are on and streamer-safe mode is off."
            ),
            "Tune with left and right brackets. Press M to toggle radio from the cab.",
        ]
        if position is not None:
            lines.append(f"Approximate truck radio position: {position[0]:.2f}, {position[1]:.2f}.")
        lines.append("Receivable stations:")
        lines.extend(d.radio.station_list_lines(limit=16))
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

    @property
    def title(self) -> str:  # type: ignore[override]
        return self.TITLES.get(self.app_key, "Driver app")

    def build_items(self) -> list[MenuItem]:
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
        source = (
            "live conditions from the weather service"
            if d.weather.live
            else "simulated route forecast"
        )
        lines = [
            f"Weather: {source}.",
            f"Current conditions: {d.weather.describe(settings.imperial_units)}",
            f"Safe speed guidance: about {settings.speed_text(d.weather.effects.safe_speed_mph)}.",
        ]
        if not d.weather.live:
            forecast = ", then ".join(kind.value for kind in d.weather.forecast(2))
            lines.append(f"Forecast ahead: {forecast}.")
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
        lines.append(line or "Traffic: no reported pinch in the next 20 miles.")
        return lines

    def _truck_stop_lines(self) -> list[str]:
        d = self.driving
        settings = self.ctx.settings
        stops = self._upcoming_stops(100.0, limit=3)
        if not stops:
            return ["Truck stops: no listed route stop in the next 100 miles."]
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
        for patrol in getattr(d.trip, "patrols", []):
            if patrol.end_mi < pos:
                continue
            ahead = max(0.0, patrol.start_mi - pos)
            if ahead <= 25.0:
                return (
                    "Road chatter: drivers are talking about enforcement somewhere "
                    "ahead. Keep it legal."
                )
        return "Road chatter: no enforcement reports nearby."


class PauseMenuState(MenuState):
    title = "Paused"

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def enter(self) -> None:
        self.ctx.audio.play("ui/pause")
        self.ctx.audio.stop_world()
        self.driving._reverse_cue_active = False
        super().enter()

    def presence(self):
        from ..discord_presence import PresenceState

        base = self.driving.presence()
        detail = base.detail if base is not None else ""
        return PresenceState("Paused", detail)

    def online_presence(self):
        # A paused player is not actively hauling, so they leave the public
        # drivers board as though they went off duty; the service's off-duty
        # grace absorbs a quick pause-and-resume without bouncing the row.
        # Discord presence (above) still shows "Paused" while the menu is up.
        return None

    def build_items(self) -> list[MenuItem]:
        drive_label = "pickup drive" if self.driving.phase == DRIVE_PHASE_PICKUP else "delivery"
        items = [
            MenuItem("Resume driving", self._resume, help=f"Return to the active {drive_label}."),
            MenuItem(
                "Trip status",
                self._status,
                help="Hear cargo, objective, route progress, and time used.",
            ),
            MenuItem(
                "Controls and help",
                self._controls,
                help="Open the how-to-play reference at the driving keys. "
                "Left and Right arrows change pages, Up and Down read "
                "line by line, Escape returns here.",
            ),
            MenuItem(
                self._mechanic_label,
                self._mechanic,
                help="A mobile mechanic patches the truck up enough to "
                "drive on. Costs much more than a garage repair, "
                "takes an hour and a half, and the bill is due even "
                "if it puts you in debt.",
            ),
            MenuItem(
                "Settings",
                self._settings,
                help="Change units, transmission, volumes, weather, "
                "voices, update channel, and trip pacing.",
            ),
        ]
        if self.driving.truck.chains_on:
            items.append(
                MenuItem(
                    f"Remove snow chains: about {CHAIN_REMOVE_MIN:.0f} minutes",
                    self._remove_chains,
                    help="Pull the chains off the drives and stow them. Do it "
                    "as soon as the road is bare again; chains grind apart "
                    "fast on pavement.",
                )
            )
        elif self.ctx.profile.chains_owned and self.ctx.profile.chain_wear_pct < 100:
            items.append(
                MenuItem(
                    self._install_chains_label,
                    self._install_chains,
                    help="Stop, kneel on the shoulder, and hang the chain set "
                    "on the drives. Chains bite snow and glare ice like "
                    "nothing else. Keep it near chain speed, about thirty "
                    "miles per hour, and pull them the moment the road is "
                    "bare. Installing in the dark takes longer and takes "
                    "more out of you.",
                )
            )
        items += [
            MenuItem(
                "Abandon job",
                self._abandon,
                help="Give up this job. Costs five hundred dollars and "
                "reputation, and returns you to the origin city.",
            ),
            MenuItem(
                "Quit to main menu",
                self._quit_to_menu,
                help="You can only save at a stop, so this drive is not "
                "saved in progress. It resumes from your last stop "
                "when you continue. Use Abandon job to drop the load.",
            ),
        ]
        if self.driving.emergency_shoulder_sleep_reason() is not None:
            items.insert(
                4,
                MenuItem(
                    "Emergency shoulder sleep",
                    self._emergency_shoulder_sleep,
                    help="Emergency-only poor sleep on the shoulder. Resets hours "
                    "of service, but fatigue remains, you may be ticketed, "
                    "minor truck damage can happen, and the deadline keeps "
                    "running.",
                ),
            )
        return items

    def go_back(self) -> None:
        self._resume()

    def _mechanic_label(self) -> str:
        damage = self.driving.truck.damage_pct
        if damage <= FIELD_REPAIR_DAMAGE_PCT:
            return "Call a roadside mechanic: not needed yet"
        repaired = damage - FIELD_REPAIR_DAMAGE_PCT
        cost = MECHANIC_CALLOUT_FEE + repaired * MECHANIC_RATE_PER_PCT
        return f"Call a roadside mechanic: {cost:,.0f} dollars"

    def _mechanic(self) -> None:
        d = self.driving
        damage = d.truck.damage_pct
        if damage <= FIELD_REPAIR_DAMAGE_PCT:
            self.ctx.say(
                "The truck is running well enough. A roadside mechanic "
                f"can help once damage is past "
                f"{FIELD_REPAIR_DAMAGE_PCT:.0f} percent."
            )
            return
        if d.truck.speed_mph > 3:
            self.ctx.say("Come to a complete stop first.")
            return
        p = self.ctx.profile
        repaired = damage - FIELD_REPAIR_DAMAGE_PCT
        cost = MECHANIC_CALLOUT_FEE + repaired * MECHANIC_RATE_PER_PCT
        carrier_paid = not player_pays_operating_costs(p.business_status)
        if not carrier_paid:
            p.money -= cost  # the rescue is never refused; money can go negative
        d.truck.damage_pct = FIELD_REPAIR_DAMAGE_PCT
        _advance_rest_clock(d, MECHANIC_WAIT_MIN)
        d.hos.on_duty(MECHANIC_WAIT_MIN)
        self.ctx.audio.play("ui/notify")
        self.refresh()
        billing = (
            "on the carrier breakdown account"
            if carrier_paid
            else f"for {cost:,.0f} dollars. You have {p.money:,.0f} dollars"
        )
        self.ctx.say(
            f"A mobile mechanic patched the truck up to "
            f"{FIELD_REPAIR_DAMAGE_PCT:.0f} percent damage {billing}. "
            f"The repair took an hour and a half: it is "
            f"{clock_text(d.trip.local_hour)}. {_deadline_text(d)}"
        )

    def _chain_night(self) -> bool:
        return is_night(self.driving.trip.local_hour)

    def _install_chains_label(self) -> str:
        minutes = CHAIN_INSTALL_MIN * (CHAIN_INSTALL_NIGHT_MULT if self._chain_night() else 1.0)
        when = " in the dark" if self._chain_night() else ""
        return f"Install snow chains{when}: about {minutes:.0f} minutes"

    def _install_chains(self) -> None:
        d = self.driving
        p = self.ctx.profile
        if d.truck.speed_mph > 3:
            self.ctx.say("Come to a complete stop first.")
            return
        night = self._chain_night()
        minutes = CHAIN_INSTALL_MIN * (CHAIN_INSTALL_NIGHT_MULT if night else 1.0)
        fatigue = CHAIN_INSTALL_NIGHT_FATIGUE if night else CHAIN_INSTALL_FATIGUE
        _advance_rest_clock(d, minutes, "on_duty_not_driving", "chain up")
        d.hos.on_duty(minutes)
        p.fatigue = min(100.0, p.fatigue + fatigue)
        d.truck.chains_on = True
        d._chains_fast_active = False
        self.ctx.audio.play("ui/notify")
        self.refresh()
        effort = (
            "Kneeling on a dark shoulder by headlamp, it takes everything "
            "your gloves have got. "
            if night
            else ""
        )
        bare = (
            " The road here is bare; they will grind apart fast until you "
            "reach the snow."
            if d.truck.surface not in ("snow", "ice")
            else ""
        )
        self.ctx.say(
            f"Chains hung on the drives in {minutes:.0f} minutes. {effort}"
            f"Keep it near {CHAIN_SAFE_MPH:.0f} miles per hour, and pull them "
            f"when the road turns bare.{bare} It is "
            f"{clock_text(d.trip.local_hour)}. {_deadline_text(d)}"
        )

    def _remove_chains(self) -> None:
        d = self.driving
        if d.truck.speed_mph > 3:
            self.ctx.say("Come to a complete stop first.")
            return
        _advance_rest_clock(d, CHAIN_REMOVE_MIN, "on_duty_not_driving", "remove chains")
        d.hos.on_duty(CHAIN_REMOVE_MIN)
        p = self.ctx.profile
        p.fatigue = min(100.0, p.fatigue + CHAIN_REMOVE_FATIGUE)
        d.truck.chains_on = False
        self.ctx.audio.play("ui/notify")
        self.refresh()
        wear = d.truck.chain_wear_pct
        state_word = (
            "They are about done; pick up a fresh set at a garage."
            if wear >= 75
            else f"The set is {wear:.0f} percent worn."
            if wear >= 1
            else "The set is still fresh."
        )
        self.ctx.say(
            f"Chains off and stowed in {CHAIN_REMOVE_MIN:.0f} minutes. "
            f"{state_word} It is {clock_text(d.trip.local_hour)}. {_deadline_text(d)}"
        )

    def _emergency_shoulder_sleep(self) -> None:
        reason = self.driving.emergency_shoulder_sleep_reason()
        if reason is None:
            self.ctx.say(
                "Emergency shoulder sleep is not available right now. "
                "Use a route stop for normal breaks and sleep."
            )
            self.refresh()
            return
        self.ctx.push_state(
            ShoulderSleepConfirmationState(
                self.ctx, self.driving, reason, self.driving.trip.position_mi
            )
        )

    def handle_controller(self, event, manager) -> None:
        # Start pauses and unpauses, so it resumes from the pause menu too.
        if (
            event.type == pygame.CONTROLLERBUTTONDOWN
            and event.button == pygame.CONTROLLER_BUTTON_START
        ):
            self._resume()
            return
        super().handle_controller(event, manager)

    def _resume(self) -> None:
        self.ctx.audio.play("ui/unpause")
        self.ctx.pop_state()
        self.ctx.say("Resumed.", interrupt=False)

    def _status(self) -> None:
        d = self.driving
        hours_used = d.trip.game_minutes / 60.0
        if d.phase == DRIVE_PHASE_PICKUP:
            self.ctx.say(
                f"Driving to pickup at {d._pickup_facility_text()}. "
                f"{d.job.weight_tons:.0f} tons of {d.job.cargo.label} are "
                f"assigned for {d.job.spoken_destination}. "
                f"{d._pickup_progress_summary()} {hours_used:.1f} hours used. "
                f"{d._air_status_text()}."
            )
            return
        self.ctx.say(
            f"Hauling {d.job.weight_tons:.0f} tons of {d.job.cargo.label} "
            f"to {d.job.spoken_destination}. "
            f"{d.trip.progress_summary(self.ctx.settings.imperial_units)} "
            f"{hours_used:.1f} hours used of {d.job.deadline_game_h:.0f}. "
            f"{d._air_status_text()}."
        )

    def _controls(self) -> None:
        from .main_menu import HelpState, controls_help_page

        self.ctx.push_state(HelpState(self.ctx, start_page=controls_help_page()))

    def _settings(self) -> None:
        from .main_menu import SettingsState

        self.ctx.push_state(SettingsState(self.ctx))

    def _abandon(self) -> None:
        # Abandoning is destructive and one keystroke away, so confirm first.
        self.ctx.push_state(AbandonJobConfirmationState(self.ctx, self.driving))

    def _quit_to_menu(self) -> None:
        from .main_menu import MainMenuState

        # Saving happens only at stops, so a mid-drive quit writes nothing: the
        # on-disk save still points at your last stop, and Continue resumes the
        # leg from there. In-progress leg driving is intentionally not preserved.
        drive_label = "pickup drive" if self.driving.phase == DRIVE_PHASE_PICKUP else "delivery"
        self.ctx.say(
            f"Returning to the title. You can only save at a stop, so this "
            f"{drive_label} will resume from your last stop, not from here.",
            interrupt=True,
        )
        self.ctx.reset_to(MainMenuState(self.ctx))


class AbandonJobConfirmationState(MenuState):
    """Yes/No guard in front of abandoning a job. Lands on "No" so giving up
    the load takes a deliberate arrow to "Yes"."""

    title = "Abandon job?"
    intro_help = (
        "Use up and down arrows to navigate, Enter to select. "
        "Escape cancels and returns to the pause menu."
    )

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.title} Abandoning gives up this load. You will pay a five "
            "hundred dollar penalty, take a reputation hit, and return to "
            f"{self.ctx.world.spoken_city(self.ctx.profile.current_city)}. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "No, keep driving",
                self.go_back,
                help="Return to the pause menu and keep this job.",
            ),
            MenuItem(
                "Yes, abandon the job",
                self._confirm,
                help="Give up this job. Costs five hundred dollars and "
                "reputation, and returns you to the origin city.",
            ),
        ]

    def _confirm(self) -> None:
        from .city import CityMenuState

        p = self.ctx.profile
        p.money -= 500.0
        p.career.reputation = max(0.0, p.career.reputation - 5.0)
        p.store_truck_condition(self.driving.truck)
        # the hours spent on the failed run still happened: keep the world
        # clock consistent with the HOS and fatigue already accrued
        p.game_hours += self.driving.trip.game_minutes / 60.0
        p.market.advance_to(p.market_day())
        p.active_trip = None
        p.pay_advance_used_for_load = False
        self.ctx.save_profile()
        self.ctx.pop_state()  # close this confirmation
        self.ctx.pop_state()  # close the pause menu
        self.ctx.replace_state(CityMenuState(self.ctx))
        # interrupt=True so this overrides any menu re-announcement during unwind
        self.ctx.say(
            f"Job abandoned. You paid a five hundred dollar penalty and "
            f"returned to {self.ctx.world.spoken_city(p.current_city)}.",
            interrupt=True,
        )


class FacilityArrivalState(MenuState):
    title = "Destination facility"
    open_sound_key = "facility/dock_gate"
    intro_help = "Use arrows to navigate, Enter to select. Dock and deliver completes the job."

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    @property
    def facility(self) -> str:
        return self.driving._destination_facility_text()

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

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "Dock and deliver",
                self._dock,
                help="Back into the dock and complete this delivery.",
            ),
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
        d._set_status("Docked. Unloading cargo.")

        def complete() -> None:
            _advance_rest_clock(d, UNLOADING_MIN)
            d.hos.on_duty(UNLOADING_MIN)
            d._set_status("Unloaded. Delivery paperwork signed.")
            d._arrive()

        self.ctx.replace_state(
            TimedMessageState(
                self.ctx,
                title="Unloading cargo",
                message=(
                    f"Docked at {self.facility}. Unloading "
                    f"{d.job.weight_tons:.0f} tons of {d.job.cargo.label}; "
                    "paperwork is being signed."
                ),
                status="Unloading cargo. Please wait.",
                seconds=UNLOADING_WAIT_S,
                on_complete=complete,
                sound_key="poi/dock_and_deliver",
            )
        )

    def _paperwork(self) -> None:
        d = self.driving
        job = d.job
        hours = d.trip.game_minutes / 60.0
        remaining = job.deadline_game_h - hours
        trip_damage = max(0.0, d.truck.damage_pct - d.start_damage)
        estimated_pay = job.payout(hours, trip_damage)
        tolls = d.trip.toll_expense
        accessorials = carrier_accessorial_charges(job)
        carrier_charges = tolls + charge_total(accessorials)
        driver_charges = _speeding_settlement_fine(d.speeding_strikes)
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
            f"Driver-responsibility charges are estimated at "
            f"{driver_charges:,.0f} dollars, for estimated net driver pay "
            f"{net_estimated_pay:,.0f}.{advance_note} "
            f"{timing}. {cargo_condition} Dock and deliver to settle."
        )

    def _status(self) -> None:
        d = self.driving
        self.ctx.say(
            f"At {self.facility}. Hauling {d.job.weight_tons:.0f} tons of "
            f"{d.job.cargo.label}. Current speed "
            f"{self.ctx.settings.speed_text(d.truck.speed_mph)}. "
            "Stop, then Dock and deliver."
        )

    def go_back(self) -> None:
        self.ctx.say("At destination. Dock and deliver to finish.")

    def lines(self) -> list[str]:
        return [
            self.title,
            "",
            f"Facility: {self.facility}",
            f"Speed: {self.driving.truck.speed_mph:.0f} mph",
            "Docking required before delivery settlement.",
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
        self._announcements: list[str] = []
        self.summary_lines: list[str] = []
        self.terminal = ctx.world.home_terminal(driving.job.destination)
        self._settle()

    def _settle_bobtail(self, hours: float, trip_damage: float) -> None:
        """Empty reposition run: relocate to the destination city, no pay."""
        d = self.driving
        p = self.ctx.profile
        job = d.job
        self.title = "Repositioned"
        p.current_city = job.destination
        driver_charges = _speeding_settlement_fine(d.speeding_strikes)
        if driver_charges:
            p.money -= driver_charges
            self.summary_parts.append(
                f"Driver-responsibility charges: speeding fines cost you "
                f"{driver_charges:,.0f} dollars."
            )
        p.store_truck_condition(d.truck)
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
                f"No load and no pay, but you are "
                f"parked at {self.terminal.name} and can open the {job.spoken_destination} "
                f"dispatch board. Fuel {d.truck.fuel_fraction * 100:.0f} percent."
            ),
        )
        if trip_damage > 1:
            self.summary_parts.append(
                f"The empty run added {trip_damage:.0f} percent truck damage. "
                "Visit the garage when you can."
            )
        result = self.ctx.award_achievement("bobtail_done", announce=False)
        if result is not None:
            self.summary_parts.append(result.message)
        # The arrival screen and announcement read summary_lines, not parts.
        self.summary_lines = list(self.summary_parts)

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
        accessorials = carrier_accessorial_charges(job)
        carrier_charges = toll_expense + charge_total(accessorials)
        driver_charges = _speeding_settlement_fine(d.speeding_strikes)
        business = build_business_settlement(
            p.business_status,
            job,
            gross_base,
            on_time=hours <= job.deadline_game_h,
            driver_charges=driver_charges,
            carrier_key=getattr(p, "carrier_key", ""),
            owned_trailers=getattr(p, "owned_trailers", ()),
            reputation=p.career.reputation,
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
        )
        gross_pay = business.gross_pay
        early_bonus = max(0.0, gross_pay - deadline_business.gross_pay)
        if driver_charges:
            self.summary_parts.append(
                f"Driver-responsibility charges: speeding fines cost you "
                f"{driver_charges:,.0f} dollars."
            )
        # Tickets from being pulled over were already paid on the spot; report
        # them for transparency but don't deduct again at settlement.
        if d.speeding_tickets:
            self.summary_parts.append(
                f"On-the-spot speeding tickets this trip: {d.speeding_tickets}, "
                f"already paid, {d.ticket_fines_paid:,.0f} dollars."
            )
        if business.business_charges:
            self.summary_parts.append(
                f"Owner-operator business costs: {business.business_charge_summary}."
            )
        net_pay = business.net_before_advance
        advance_repaid = round(min(p.pay_advance, net_pay), 2)
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
        on_time = hours <= job.deadline_game_h
        p.money += net_pay
        p.current_city = job.destination
        # Tire, brake, and engine wear now come off the truck itself -- the
        # physics accrued them mile by mile during the run. Grime stays a
        # simple per-mile film; it has no physics to earn it.
        p.store_truck_condition(d.truck)
        road_grime_added = min(100.0, job.distance_mi * ROAD_GRIME_PER_MILE)
        p.road_grime_pct = min(100.0, p.road_grime_pct + road_grime_added)
        previous_level = p.career.level
        announcements = p.career.record_delivery(
            job.distance_mi,
            net_pay,
            on_time,
            trip_damage,
            cargo_class_mult=xp_class_multiplier(job.cargo),
        )
        announcements.extend(self._handle_fleet_promotion(previous_level))
        xp_bonus_notes = []
        if xp_class_multiplier(job.cargo) > 1.0:
            xp_bonus_notes.append("demanding freight")
        streak_bonus = xp_streak_bonus(p.career.on_time_streak) if on_time else 0.0
        if streak_bonus > 0.0:
            xp_bonus_notes.append(f"a {p.career.on_time_streak}-delivery on-time streak")
        if xp_bonus_notes:
            self.summary_parts.append(
                f"Career experience bonus for {' and '.join(xp_bonus_notes)}."
            )
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
                f"Driver-responsibility charges {driver_charges:,.0f} dollars. "
                f"Net driver pay {net_pay:,.0f} "
                f"dollars, and you now have {p.money:,.0f}. "
                f"After unloading, dispatch has you parked at "
                f"{self.terminal.name} for the {job.spoken_destination} service area."
            ),
        )
        if early_bonus >= 1.0:
            self.summary_parts.append(f"Early delivery bonus: {early_bonus:,.0f} dollars.")
        if trip_damage > 1:
            self.summary_parts.append(
                f"The cargo run added {trip_damage:.0f} percent truck damage. "
                "Visit the garage when you can."
            )
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
            speeding_strikes=d.speeding_strikes,
            gross_pay=gross_pay,
        )
        self.summary_parts.extend(self._achievement_messages)
        timing = "On time" if on_time else "Late"
        bonus_text = (
            f"Early delivery bonus: {early_bonus:,.0f} dollars"
            if early_bonus >= 1.0
            else "No early delivery bonus on this run"
        )
        cargo_condition = (
            f"Truck damage added on this run: {trip_damage:.0f} percent"
            if trip_damage > 1
            else "No new damage recorded"
        )
        career_lines = announcements + self._achievement_messages
        if not career_lines:
            career_lines = ["No new career messages."]
        advance_lines = []
        if advance_repaid > 0:
            advance_lines.append(f"Pay advance repaid: {advance_repaid:,.0f} dollars.")
        if p.pay_advance >= 1.0:
            advance_lines.append(f"Pay advance still outstanding: {p.pay_advance:,.0f} dollars.")
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
            "Carrier charges are not deducted from driver pay.",
            f"Business status: {business.status_label}.",
            *business_cost_lines,
            f"Driver-responsibility charges: {driver_charges:,.0f} dollars.",
            *advance_lines,
            f"Net driver pay: {net_pay:,.0f} dollars.",
            f"Money after settlement: {p.money:,.0f} dollars.",
            bonus_text + ".",
            f"Route: {' to '.join(self.ctx.world.spoken_city(c) for c in d.route.cities)}.",
            f"Distance credited: {job.distance_mi:.0f} miles.",
            cargo_condition + ".",
            f"Fuel remaining: {d.truck.fuel_fraction * 100:.0f} percent.",
            f"Truck damage now: {d.truck.damage_pct:.0f} percent.",
            *career_lines,
        ]
        self._announcements = announcements

    def _handle_fleet_promotion(self, previous_level: int) -> list[str]:
        """Swap the carrier tractor when a level-up crosses a fleet tier.

        The carrier hands the new unit over road-ready, so the profile's
        equipment condition resets with it -- company repairs are carrier
        billed anyway, this just skips the paperwork.
        """
        from ..models.carrier_fleet import (
            assigned_truck_key,
            fleet_tier_for_level,
            fleet_upgrade_announcement,
        )
        from ..models.trucks import TRUCK_CATALOG

        p = self.ctx.profile
        if p.owns_equipment() or p.career.level <= previous_level:
            return []
        if fleet_tier_for_level(previous_level).key == fleet_tier_for_level(p.career.level).key:
            return []
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
        return [fleet_upgrade_announcement(p)]

    def _award_arrival_achievements(
        self,
        *,
        on_time: bool,
        trip_damage: float,
        toll_expense: float,
        route_miles: float,
        speeding_strikes: int,
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
        if on_time:
            ids.append("first_on_time")
        if trip_damage <= 1.0:
            ids.append("clean_delivery")
        if speeding_strikes == 0:
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
        perfect = on_time and trip_damage <= 1.0 and speeding_strikes == 0
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
        from ..sim.season import date_text
        from ..sim.season import season as season_of

        career_season = season_of(p.game_hours)
        if career_season == "winter":
            ids.append("winter_delivery")
        if add_unique_stat(p, "seasons_delivered", career_season) >= 4:
            ids.append("four_seasons")
        if dest_region == "desert_southwest" and career_season == "summer":
            ids.append("desert_summer")
        if date_text(p.game_hours) == "April 1":
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
        if (
            route_miles >= 300.0
            and on_time
            and trip_damage <= 1.0
            and speeding_strikes == 0
            and d.speeding_tickets == 0
        ):
            ids.append("spotless_long")
        if d.speeding_tickets >= 1:
            ids.append("first_ticket")
        if d.speeding_tickets >= 2:
            ids.append("second_ticket")

        for achievement_id in ids:
            result = self.ctx.award_achievement(achievement_id, announce=False)
            if result is not None:
                self._achievement_messages.append(result.message)
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
        items.append(MenuItem("Continue to " + self.terminal.name, self._continue))
        return items

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
