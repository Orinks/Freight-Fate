"""Main menu, profile selection, name entry, settings, and help screens."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pygame

from .. import __version__, updater
from ..models.profile import DEFAULT_CITY, Profile, ProfileIntegrityError
from ..settings import TIME_SCALES
from ..sim.hos import HOS_MODES
from .base import MenuItem, MenuState, State
from .update import UpdateChecker, UpdateCheckState, UpdatePromptState

_last_invalid_saves: list[Path] = []


def enter_world(ctx) -> None:
    """Resume a saved mid-trip delivery if there is one, else the terminal hub."""
    ctx.push_state(_world_entry_state(ctx))


def _world_entry_state(ctx) -> State:
    """Build the first playable state for the current profile."""
    from .city import CityMenuState, PickupFacilityState
    from .driving import DrivingState

    p = ctx.profile
    if p.active_trip:
        if p.active_trip.get("kind") == "pickup":
            state = PickupFacilityState.from_snapshot(ctx, p.active_trip)
        else:
            state = DrivingState.from_snapshot(ctx, p.active_trip)
        if state is not None:
            return state
        p.active_trip = None  # unreadable snapshot; do not retry every load
    return CityMenuState(ctx)


def _loadable_saves() -> list[tuple[Path, Profile]]:
    """Return readable saves in newest-first order."""
    global _last_invalid_saves
    _last_invalid_saves = []
    saves = []
    for path in Profile.list_saves():
        try:
            saves.append((path, Profile.load(path)))
        except ProfileIntegrityError:
            _last_invalid_saves.append(path)
        except Exception:
            continue
    return saves


def _career_location(profile: Profile) -> str:
    from ..data.world import get_world

    trip = profile.active_trip or {}
    job = trip.get("job", {})
    destination = job.get("destination")
    if trip.get("kind") == "pickup_drive":
        facility = job.get("origin_location")
        return f"driving to pickup at {facility or destination}"
    if trip.get("kind") == "pickup" and destination:
        loaded = "loaded for" if trip.get("loaded") else "picking up for"
        return f"{loaded} {destination}"
    if destination:
        return f"on the road to {destination}"
    try:
        terminal = get_world().home_terminal(profile.current_city)
        return f"at {terminal.name} in {profile.current_city}"
    except KeyError:
        return f"in {profile.current_city}"


def _saved_label(path: Path) -> str:
    stamp = datetime.fromtimestamp(path.stat().st_mtime)
    hour = stamp.hour % 12 or 12
    am_pm = "AM" if stamp.hour < 12 else "PM"
    return f"{stamp:%b} {stamp.day}, {stamp.year} at {hour}:{stamp.minute:02d} {am_pm}"


def _career_summary(path: Path, profile: Profile, *, include_saved: bool = True) -> str:
    parts = [
        f"{profile.name}: level {profile.career.level}",
        f"{profile.money:,.0f} dollars",
        _career_location(profile),
        f"{profile.career.deliveries} deliveries",
    ]
    if include_saved:
        parts.append(f"last saved {_saved_label(path)}")
    return ", ".join(parts)


class MainMenuState(MenuState):
    title = "Freight Fate"

    # one startup update check per game session, shared across instances
    _update_checker: UpdateChecker | None = None
    _update_prompted = False

    def enter(self) -> None:
        self.ctx.audio.play_music("menu_theme")
        super().enter()
        cls = MainMenuState
        if updater.is_frozen() and cls._update_checker is None:
            cls._update_checker = UpdateChecker(self.ctx.settings)

    def update(self, dt: float) -> None:
        cls = MainMenuState
        checker = cls._update_checker
        if (cls._update_prompted or checker is None
                or not checker.done.is_set()):
            return
        cls._update_prompted = True
        info = checker.result
        if info is not None and info.tag != self.ctx.settings.skipped_update:
            self.ctx.push_state(UpdatePromptState(self.ctx, info))

    def announce_entry(self) -> None:
        warning = ""
        if _last_invalid_saves:
            count = len(_last_invalid_saves)
            warning = (f"{count} saved career failed its integrity check and "
                       f"was moved aside. " if count == 1 else
                       f"{count} saved careers failed integrity checks and "
                       f"were moved aside. ")
        self.ctx.say(
            f"Welcome to Freight Fate, version {__version__}. "
            f"An audio trucking adventure across America. {warning}"
            f"{self.current_text()}",
        )

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        saves = _loadable_saves()
        if saves:
            latest_path, latest_profile = saves[0]
            items.append(MenuItem(
                f"Continue latest career: "
                f"{_career_summary(latest_path, latest_profile, include_saved=False)}",
                self._continue,
                help=f"Load the newest save for {latest_profile.name}."))
            items.append(MenuItem("Choose career", self._load_menu,
                                  help="Choose any saved career instead of only the newest one."))
        items.append(MenuItem("New career", self._new_game,
                              help="Start a fresh trucking career."))
        items.append(MenuItem("How to play", self._help,
                              help="Learn the controls and the goal of the game."))
        items.append(MenuItem("Settings", self._settings,
                              help="Units, transmission mode, volumes, weather, "
                                   "voices, update channel, and trip pacing."))
        items.append(MenuItem("Quit", self.ctx.quit, help="Exit the game."))
        return items

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.say("Press Enter on Quit to exit the game.")

    def _continue(self) -> None:
        saves = _loadable_saves()
        if not saves:
            self.ctx.say("No saved careers found.")
            self.refresh()
            return
        self.ctx.profile = saves[0][1]
        p = self.ctx.profile
        if p.active_trip:
            self.ctx.say(f"Welcome back, {p.name}.", interrupt=True)
        else:
            terminal = self.ctx.world.home_terminal(p.current_city)
            self.ctx.say(f"Welcome back, {p.name}. You are parked at "
                         f"{terminal.name} in {p.current_city} "
                         f"with {p.money:,.0f} dollars.", interrupt=True)
        enter_world(self.ctx)

    def _load_menu(self) -> None:
        self.ctx.push_state(LoadDriverState(self.ctx))

    def _new_game(self) -> None:
        self.ctx.push_state(NameEntryState(self.ctx))

    def _help(self) -> None:
        self.ctx.push_state(HelpState(self.ctx))

    def _settings(self) -> None:
        self.ctx.push_state(SettingsState(self.ctx))


class LoadDriverState(MenuState):
    title = "Choose career"
    intro_help = ("Use up and down arrows to choose a saved career. Enter loads "
                  "the selected career. Escape goes back.")

    def build_items(self) -> list[MenuItem]:
        items = []
        for path, profile in _loadable_saves():
            label = _career_summary(path, profile)
            items.append(MenuItem(
                label,
                lambda p=profile: self._pick(p),
                help=f"Load {profile.name}, {_career_location(profile)}."))
        items.append(MenuItem("Back", self.go_back))
        return items

    def _pick(self, profile: Profile) -> None:
        self.ctx.profile = profile
        self.ctx.say(f"Welcome back, {profile.name}.")
        self.ctx.replace_state(_world_entry_state(self.ctx))


class NameEntryState(State):
    """Accessible text entry: characters are echoed as you type."""

    MAX_LEN = 24

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.name = ""

    def enter(self) -> None:
        self.ctx.say("New career. Type your driver name, then press Enter. "
                     "Press Escape to cancel.")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.ctx.audio.play("ui/menu_back")
            self.ctx.pop_state()
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._confirm()
        elif event.key == pygame.K_BACKSPACE:
            if self.name:
                removed, self.name = self.name[-1], self.name[:-1]
                self.ctx.say(f"Deleted {removed}. " + (self.name or "Empty."))
            else:
                self.ctx.audio.play("ui/error")
        elif event.key == pygame.K_F2:
            self.ctx.say(self.name if self.name else "Empty.")
        elif event.unicode and event.unicode.isprintable() and len(self.name) < self.MAX_LEN:
            self.name += event.unicode
            self.ctx.audio.play("ui/tick")
            spoken = "space" if event.unicode == " " else event.unicode
            self.ctx.say(spoken)

    def _confirm(self) -> None:
        name = self.name.strip() or "Driver"
        self.ctx.audio.play("ui/menu_select")
        self.ctx.push_state(HomeTerminalState(self.ctx, name))

    def lines(self) -> list[str]:
        return ["New career", "", f"Driver name: {self.name}_",
                "Press Enter to confirm, Escape to cancel, F2 to review."]


REGION_LABELS = {
    "northeast": "the Northeast",
    "midwest": "the Midwest",
    "south": "the South",
    "plains": "the Plains",
    "rockies": "the Rockies",
    "southwest": "the Southwest",
    "west_coast": "the West Coast",
    "northwest": "the Pacific Northwest",
}


class HomeTerminalState(MenuState):
    """Pick the home terminal city where a brand-new career begins."""

    title = "Home terminal"
    intro_help = ("Pick the city where your trucking career begins. Cities are "
                  "grouped by region. Use up and down arrows, Home and End, or "
                  "type a letter to jump to a city. Enter confirms your home "
                  "terminal. Escape goes back to name entry.")

    def __init__(self, ctx, driver_name: str) -> None:
        super().__init__(ctx)
        self.driver_name = driver_name
        cities = sorted(ctx.world.cities.values(),
                        key=lambda c: (REGION_LABELS.get(c.region, c.region), c.name))
        self._cities = [c.name for c in cities]
        if DEFAULT_CITY in self._cities:
            self.index = self._cities.index(DEFAULT_CITY)

    def announce_entry(self) -> None:
        self.ctx.say("Home terminal. Pick the city where your career starts. "
                     f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        for name in self._cities:
            city = self.ctx.world.cities[name]
            terminal = self.ctx.world.home_terminal(name)
            region = REGION_LABELS.get(city.region, city.region)
            items.append(MenuItem(f"{name}, {region}",
                                  lambda n=name: self._pick(n),
                                  help=f"Start at {terminal.spoken_name} in "
                                       f"{name}, {city.state}."))
        return items

    def _pick(self, city: str) -> None:
        from .city import CityMenuState

        name = self.driver_name
        existing = {p.stem.lower() for p in Profile.list_saves()}
        profile = Profile(name=name, current_city=city)
        terminal = self.ctx.world.home_terminal(city)
        self.ctx.profile = profile
        profile.save()
        self.ctx.pop_state()   # this picker
        self.ctx.pop_state()   # name entry
        self.ctx.push_state(CityMenuState(self.ctx))
        loaded_over = (f"Loaded over existing driver named {name}. "
                       if name.lower() in existing else "")
        self.ctx.say(
            f"{loaded_over}Welcome aboard, {name}. Your truck is parked at "
            f"{terminal.spoken_name} in the {city} service area with "
            f"{profile.money:,.0f} dollars and a full tank. "
            "Your first stop is the dispatch board.", interrupt=True)


HELP_PAGES = [
    ("The goal", [
        "You are an owner-operator truck driver building a freight career.",
        "Start from your company terminal or yard in the service area.",
        "Accept freight from the dispatch board, deadhead to the origin facility,",
        "check in and load the trailer there, then dispatch loads the navigation itinerary,",
        "and deliver cargo across the country, on time and intact.",
        "Earn money and experience, level up, and unlock better freight.",
    ]),
    ("Menus", [
        "All menus use Up and Down arrows, Enter to select, Escape to go back.",
        "Home and End jump to the first and last option.",
        "Type a letter to jump to options starting with that letter.",
        "Press F1 in any menu for contextual help.",
        "Edited or corrupted career saves may be moved aside at the main menu.",
    ]),
    ("Driving basics", [
        "E starts the engine. To shut it down, slow below 5 miles per hour first.",
        "Hold the Up arrow to accelerate, the Down arrow to brake.",
        "In automatic, once stopped, keep holding the Down arrow to back up slowly.",
        "Touch the Up arrow to brake and return to forward drive.",
        "Hold B for the emergency brake: the hardest possible stop,",
        "for hazards and rest stops you would otherwise overshoot.",
        "K sets adaptive cruise at your current speed with a three second clear-weather gap.",
        "Rain, snow, fog, or low visibility increase the following gap.",
        "It follows slower modeled traffic but does not steer for you.",
        "Press K again or touch the brakes to cancel it.",
        "In automatic mode the truck shifts for itself.",
        "In manual mode, hold Left Shift for the clutch,",
        "then press 1 through 0 for gears one through ten, or N for neutral.",
        "Manual transmission uses Backspace for reverse after pressing the clutch.",
        "J toggles the engine brake for long downhill grades.",
        "H sounds the horn.",
    ]),
    ("Driving information keys", [
        "Space speaks your speed, gear, and RPM.",
        "Tab speaks a full status report.",
        "F speaks fuel level and range.",
        "C speaks the clock, your deadline, and your hours of service.",
        "R speaks route progress, GPS context, and the next stop or maneuver.",
        "V speaks the weather and the forecast.",
        "Escape opens the pause menu.",
    ]),
    ("On the road", [
        "Loaded trips follow a navigation itinerary built from highway corridors.",
        "Progress is not just city to city: GPS announces state lines,",
        "intermediate places, traffic, highway changes, and rest-stop exits.",
        "Grades and terrain are route conditions, not random trip rolls.",
        "Weather, traffic, and construction still vary by time, place, and seed.",
        "Watch your speed: limits drop in construction and traffic zones.",
        "Some hazards come from modeled traffic ahead, such as slow lead vehicles,",
        "merging traffic, lane restrictions, and queues.",
        "Route POIs use clean place names and source-backed actions like fuel, break, sleep, save, or inspect.",
        "Repair, towing, and roadside assistance appear only when the POI metadata supports them.",
        "Current dispatch lanes require checked-in route geometry, grade data, state context, and actionable POIs.",
        "The broad map remains the enrichment target; unsupported lanes stay off the job board until completed.",
        "When you hear Brake now, slow below twenty five miles per hour quickly",
        "to avoid a collision. These warnings are tied to road or traffic context.",
        "Hold B for the emergency brake when normal braking is not enough.",
        "Rest stops sit at highway exits, announced a few miles out.",
        "The GPS adds one-mile exit cues and concise turn guidance.",
        "Press X to signal for the exit, slow to forty five for the ramp,",
        "then brake to a stop for the rest stop menu:",
        "refuel, take a break, sleep, or save. Too fast and you miss the exit.",
        "T still opens the menu if you simply stop on the highway at one.",
        "If you miss a stop, slow down, back up carefully to it, stop, then press T.",
        "Fuel prices vary by region.",
        "Running out of fuel means an expensive roadside rescue.",
        "If collisions leave the truck badly damaged, open the pause menu",
        "and call a roadside mechanic for a pricey field repair.",
    ]),
    ("Hours and rest", [
        "The ELD tracks driving, on-duty-not-driving, off-duty, and sleeper time.",
        "You may drive eleven hours after ten consecutive hours off duty,",
        "within a fourteen hour duty window after coming on duty.",
        "A thirty minute break is required after eight cumulative hours of driving.",
        "Any thirty consecutive non-driving minutes satisfy that break rule,",
        "including loading, fueling, inspection, or explicit rest-stop breaks.",
        "Spoken warnings come at two hours, one hour, and thirty minutes left.",
        "Sleeping ten hours at a rest stop, or at a terminal, starts a fresh shift.",
        "Driving past a limit risks route-backed inspections, fines, and out-of-service orders.",
        "Fatigue builds as you drive, faster at night. A drowsy driver",
        "yawns, drifts onto the rumble strip, and reacts late to hazards.",
        "Late at night, truck parking may be full. Drive on, or risk",
        "a ticket and poor sleep on the shoulder.",
        "Settings keeps a debug HOS bypass for accessibility and bug escape only.",
    ]),
    ("Deliveries and money", [
        "The dispatch board lists freight for the current metro service area",
        "from facilities such as ports,",
        "intermodal yards, warehouses, food terminals, industrial parks,",
        "air cargo areas, manufacturing plants, and retail distribution hubs.",
        "Each job names an origin facility and a destination facility.",
        "Cargo follows the facility type, so a food terminal offers",
        "different work than a port, warehouse, or factory.",
        "After accepting a dispatch, leave the terminal bobtail or with an empty trailer.",
        "Pickup legs are local deadhead moves to the origin facility.",
        "At the pickup gate, come to a full stop before the facility menu opens.",
        "Check in, then load at the assigned dock.",
        "Loading requires the truck to be stopped.",
        "Once loaded and sealed, dispatch starts the destination itinerary.",
        "GPS cues call out highway changes, state lines, places, and rest stops.",
        "The job is the load and destination; route choice is handled as navigation.",
        "Deliver before the deadline for a bonus. Late or damaged cargo pays less.",
        "At the destination facility, slow down, come to a full stop,",
        "then dock and deliver before the settlement is paid.",
        "After settlement, the truck is parked at the destination service-area terminal.",
        "Fragile cargo, like electronics and fresh food, punishes rough driving.",
        "Repair your truck in the terminal garage. Damage reduces engine power.",
        "Higher levels widen distance caps, improve low-end pay,",
        "and unlock refrigerated, heavy-haul, and high-value freight.",
        "Cargo markets drift day by day. The dispatch board calls out tight and loose",
        "markets; tight cargo pays well above the usual rate.",
    ]),
    ("The garage", [
        "Every terminal garage refuels and repairs your truck.",
        "If you cannot afford a full tank or full repair, the garage",
        "buys as much fuel or repair work as your money covers.",
        "The Upgrades menu sells permanent improvements: an engine tune,",
        "an aerodynamic kit, a long-range tank, and reinforced brakes.",
        "The Trucks menu sells the heavy hauler: more torque and a bigger",
        "tank, but worse aerodynamics and a thirstier engine.",
        "Switch between trucks you own at any garage, free of charge.",
    ]),
]


class HelpState(State):
    """Page-by-page, line-by-line spoken manual."""

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.page = 0
        self.line = -1  # -1 = page title

    def enter(self) -> None:
        self.ctx.say(
            "How to play. Left and Right arrows change pages. Up and Down arrows "
            "read line by line. Enter reads the whole page. Escape goes back. "
            + self._page_title())

    def _page_title(self) -> str:
        title, lines = HELP_PAGES[self.page]
        return f"Page {self.page + 1} of {len(HELP_PAGES)}: {title}. {len(lines)} lines."

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        title, lines = HELP_PAGES[self.page]
        if event.key == pygame.K_ESCAPE:
            self.ctx.audio.play("ui/menu_back")
            self.ctx.pop_state()
        elif event.key in (pygame.K_RIGHT, pygame.K_PAGEDOWN):
            self.page = (self.page + 1) % len(HELP_PAGES)
            self.line = -1
            self.ctx.audio.play("ui/menu_move")
            self.ctx.say(self._page_title())
        elif event.key in (pygame.K_LEFT, pygame.K_PAGEUP):
            self.page = (self.page - 1) % len(HELP_PAGES)
            self.line = -1
            self.ctx.audio.play("ui/menu_move")
            self.ctx.say(self._page_title())
        elif event.key == pygame.K_DOWN:
            self.line = min(self.line + 1, len(lines) - 1)
            self.ctx.say(lines[self.line])
        elif event.key == pygame.K_UP:
            self.line = max(self.line - 1, 0)
            self.ctx.say(lines[self.line])
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.ctx.say(f"{title}. " + " ".join(lines))

    def lines(self) -> list[str]:
        title, lines = HELP_PAGES[self.page]
        out = [f"How to play - {title} ({self.page + 1}/{len(HELP_PAGES)})", ""]
        for i, text in enumerate(lines):
            out.append(("> " if i == self.line else "  ") + text)
        return out


class SettingsState(MenuState):
    title = "Settings"
    intro_help = ("Use up and down arrows to pick a setting. Enter or Right arrow "
                  "changes it. Left arrow changes it the other way. Escape saves and goes back.")

    def build_items(self) -> list[MenuItem]:
        s = self.ctx.settings
        return [
            MenuItem(lambda: f"Units: {'imperial, miles' if s.imperial_units else 'metric, kilometers'}",
                     lambda: self._toggle_units(1),
                     help="Switch distance and speed readouts between miles "
                          "and kilometers."),
            MenuItem(lambda: f"Transmission: {'automatic' if s.automatic_transmission else 'manual'}",
                     lambda: self._toggle_transmission(1),
                     help="Automatic shifts for you. Manual uses clutch and "
                          "number keys while driving."),
            MenuItem(lambda: f"Trip pacing: {self._pace_label()}",
                     lambda: self._cycle_pace(1),
                     help="Controls how quickly game time and distance pass "
                          "during a drive."),
            MenuItem(lambda: f"Hours of service: {self._hos_label()}",
                     lambda: self._cycle_hos(1),
                     help="Realistic enforces 11 hours of driving, a 14 hour "
                          "duty window, and a 30-minute break after 8 hours. "
                          "Relaxed makes every limit 25 percent longer. Debug "
                          "bypass records the ELD clock but disables enforcement "
                          "as an accessibility and bug fallback."),
            MenuItem(lambda: f"Master volume: {round(s.master_volume * 100)} percent",
                     lambda: self._volume("master_volume", 0.1),
                     help="Overall game volume. Use Left and Right arrows "
                          "for smaller adjustments."),
            MenuItem(lambda: f"Sound effects volume: {round(s.sfx_volume * 100)} percent",
                     lambda: self._volume("sfx_volume", 0.1),
                     help="Engine, road, weather, menu, and alert sounds."),
            MenuItem(lambda: f"Music volume: {round(s.music_volume * 100)} percent",
                     lambda: self._volume("music_volume", 0.1),
                     help="Background music volume."),
            MenuItem(lambda: f"Speech verbosity: {['terse', 'normal', 'chatty'][s.speech_verbosity]}",
                     lambda: self._cycle_verbosity(1),
                     help="Controls how often driving status reminders speak."),
            MenuItem(lambda: ("Driving event voice: "
                              f"{'separate SAPI voice' if s.sapi_events else 'screen reader'}"),
                     lambda: self._toggle_sapi_events(1),
                     help="Speaks road events such as hazards, warnings, and "
                          "weather changes through a separate Windows SAPI "
                          "voice, so your screen reader cannot talk over "
                          "them. Turn off to hear everything through the "
                          "screen reader voice."),
            MenuItem(lambda: f"Weather source: {'real world' if s.real_weather else 'simulated'}",
                     lambda: self._toggle_real_weather(1),
                     help="Real world uses live conditions for each city from "
                          "Open-Meteo. Needs an internet connection; falls back "
                          "to simulated weather offline."),
            MenuItem(lambda: ("Update channel: "
                              f"{'developer snapshots' if self._channel() == 'dev' else 'stable releases'}"),
                     lambda: self._toggle_update_channel(1),
                     help="Stable releases are the finished, numbered "
                          "versions. Developer snapshots are nightly builds "
                          "of work in progress: new features sooner, but "
                          "rough edges."),
            MenuItem("Check for updates", self._check_updates,
                     help="Look for a new version of the game right now."),
            MenuItem("Back", self.go_back,
                     help="Save settings and return to the previous menu."),
        ]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT:
            self._adjust(1)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT:
            self._adjust(-1)
        else:
            super().handle_event(event)

    def _adjust(self, direction: int) -> None:
        actions = [self._toggle_units, self._toggle_transmission, self._cycle_pace,
                   self._cycle_hos,
                   lambda d: self._volume("master_volume", 0.1 * d),
                   lambda d: self._volume("sfx_volume", 0.1 * d),
                   lambda d: self._volume("music_volume", 0.1 * d),
                   self._cycle_verbosity, self._toggle_sapi_events,
                   self._toggle_real_weather, self._toggle_update_channel]
        if self.index < len(actions):
            actions[self.index](direction)

    def _pace_label(self) -> str:
        scale = self.ctx.settings.time_scale
        return {10.0: "relaxed", 20.0: "standard", 40.0: "fast"}.get(scale, f"{scale:g} times")

    def _hos_label(self) -> str:
        return {
            "realistic": "realistic",
            "relaxed": "relaxed",
            "debug_off": "debug bypass",
            "off": "debug bypass",
        }.get(self.ctx.settings.hos_mode, "realistic")

    def _announce(self) -> None:
        self.refresh()
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_select")
        self.speak_current()

    def _toggle_units(self, _d: int) -> None:
        self.ctx.settings.imperial_units = not self.ctx.settings.imperial_units
        self._announce()

    def _toggle_transmission(self, _d: int) -> None:
        self.ctx.settings.automatic_transmission = not self.ctx.settings.automatic_transmission
        self._announce()

    def _cycle_pace(self, d: int) -> None:
        scales = list(TIME_SCALES)
        try:
            i = scales.index(self.ctx.settings.time_scale)
        except ValueError:
            i = 1
        self.ctx.settings.time_scale = scales[(i + d) % len(scales)]
        self._announce()

    def _volume(self, attr: str, delta: float) -> None:
        value = getattr(self.ctx.settings, attr)
        setattr(self.ctx.settings, attr, max(0.0, min(1.0, round(value + delta, 2))))
        self.ctx.apply_volumes()
        self._announce()

    def _cycle_hos(self, d: int) -> None:
        modes = list(HOS_MODES)
        try:
            i = modes.index(self.ctx.settings.hos_mode)
        except ValueError:
            i = 0
        self.ctx.settings.hos_mode = modes[(i + d) % len(modes)]
        self._announce()

    def _cycle_verbosity(self, d: int) -> None:
        self.ctx.settings.speech_verbosity = (self.ctx.settings.speech_verbosity + d) % 3
        self._announce()

    def _toggle_sapi_events(self, _d: int) -> None:
        self.ctx.settings.sapi_events = not self.ctx.settings.sapi_events
        self._announce()

    def _toggle_real_weather(self, _d: int) -> None:
        self.ctx.settings.real_weather = not self.ctx.settings.real_weather
        self._announce()

    def _channel(self) -> str:
        return updater.resolve_channel(
            self.ctx.settings.update_channel,
            updater.load_build_info(__version__))

    def _toggle_update_channel(self, _d: int) -> None:
        self.ctx.settings.update_channel = (
            "stable" if self._channel() == "dev" else "dev")
        self._announce()

    def _check_updates(self) -> None:
        self.ctx.push_state(UpdateCheckState(self.ctx))

    def go_back(self) -> None:
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_back")
        self.ctx.say("Settings saved.")
        self.ctx.pop_state()
