"""Main menu, profile selection, name entry, settings, and help screens."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pygame

from .. import __version__, updater
from ..achievements import ACHIEVEMENTS, earned_ids
from ..data.regions import REGION_LABELS
from ..models.profile import DEFAULT_CITY, Profile, ProfileIntegrityError
from ..models.start_options import (
    all_start_options,
    apply_start_option,
    option_for_profile,
    start_option,
)
from ..music import select_menu_music_sequence
from ..settings import TIME_SCALES
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
    from ..models.jobs import facility_text

    trip = profile.active_trip or {}
    job = trip.get("job", {})
    destination = job.get("destination")
    if trip.get("kind") == "pickup_drive":
        origin = str(job.get("origin") or profile.current_city)
        facility = facility_text(
            str(job.get("origin_type", "metro_market")),
            str(job.get("origin_location", "")),
            origin,
            str(job.get("origin_locality", "")),
        )
        return f"driving to pickup at {facility}"
    if trip.get("kind") == "pickup" and destination:
        loaded = "loaded for" if trip.get("loaded") else "picking up for"
        facility = facility_text(
            str(job.get("destination_type", "metro_market")),
            str(job.get("destination_location", "")),
            str(destination),
            str(job.get("destination_locality", "")),
        )
        return f"{loaded} {facility}"
    if destination:
        facility = facility_text(
            str(job.get("destination_type", "metro_market")),
            str(job.get("destination_location", "")),
            str(destination),
            str(job.get("destination_locality", "")),
        )
        return f"on the road to {facility}"
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
    from ..models.business import status_label

    parts = [
        f"{profile.name}: level {profile.career.level}",
        f"{profile.carrier_name} {status_label(profile.business_status)}",
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
        super().enter()
        profile = self.ctx.profile
        if profile is None:
            saves = _loadable_saves()
            profile = saves[0][1] if saves else None
        sequence = select_menu_music_sequence(profile)
        self.ctx.play_music_sequence("menu", sequence)
        cls = MainMenuState
        if updater.is_frozen() and cls._update_checker is None:
            cls._update_checker = UpdateChecker(self.ctx.settings)

    def update(self, dt: float) -> None:
        super().update(dt)
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
            items.append(MenuItem("Manage careers", self._manage_careers,
                                  help="Reset or delete saved careers."))
        items.append(MenuItem("New career", self._new_game,
                              help="Start a fresh trucking career."))
        items.append(MenuItem("Achievements", self._achievements,
                              help="Review earned and locked achievements for "
                                   "a saved career."))
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

    def presence(self):
        from ..discord_presence import PresenceState

        return PresenceState("In the main menu")

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

    def _manage_careers(self) -> None:
        self.ctx.push_state(ManageCareersState(self.ctx))

    def _new_game(self) -> None:
        self.ctx.push_state(NameEntryState(self.ctx))

    def _help(self) -> None:
        self.ctx.push_state(HelpState(self.ctx))

    def _achievements(self) -> None:
        self.ctx.push_state(AchievementCareerState(self.ctx))

    def _settings(self) -> None:
        self.ctx.push_state(SettingsState(self.ctx))


class AchievementCareerState(MenuState):
    title = "Achievements"
    intro_help = ("Choose a saved career to review achievements. Enter opens "
                  "that driver's earned and locked achievements. Escape goes back.")

    def announce_entry(self) -> None:
        if not self.items or self.items[0].text == "Back":
            self.ctx.say("Achievements. No saved careers yet. Start a career, "
                         "then come back after the road has opinions.")
            return
        self.ctx.say(f"Achievements. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items = []
        for _path, profile in _loadable_saves():
            earned = len(earned_ids(profile))
            total = len(ACHIEVEMENTS)
            items.append(MenuItem(
                f"{profile.name}: {earned} of {total} earned",
                lambda p=profile: self._pick(p),
                help=f"Review achievements for {profile.name}."))
        items.append(MenuItem("Back", self.go_back))
        return items

    def _pick(self, profile: Profile) -> None:
        self.ctx.push_state(AchievementsState(self.ctx, profile))


class AchievementsState(MenuState):
    intro_help = ("Use up and down arrows to review achievements. Earned and "
                  "locked entries are both shown. Enter repeats the selected "
                  "entry. Escape goes back.")

    def __init__(self, ctx, profile: Profile) -> None:
        super().__init__(ctx)
        self.profile = profile

    @property
    def title(self) -> str:  # type: ignore[override]
        return f"Achievements for {self.profile.name}"

    def announce_entry(self) -> None:
        earned = len(earned_ids(self.profile))
        total = len(ACHIEVEMENTS)
        self.ctx.say(
            f"Achievements for {self.profile.name}. {earned} of {total} earned. "
            "Locked achievements are shown as goals, with no story spoilers. "
            f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        earned = earned_ids(self.profile)
        items = [
            MenuItem(self._summary_label, self._summary,
                     help="Hear the total earned achievement count.")
        ]
        for achievement in ACHIEVEMENTS:
            unlocked = achievement.id in earned
            if unlocked:
                label = f"Earned: {achievement.name} - {achievement.description}"
                help_text = f"{achievement.category}. {achievement.description}"
            else:
                # Locked entries show only the title; the description stays
                # hidden until the achievement is earned.
                label = f"Locked: {achievement.name}"
                help_text = f"{achievement.category}. Keep playing to unlock it."
            items.append(MenuItem(
                label,
                lambda text=label: self.ctx.say(text),
                help=help_text))
        items.append(MenuItem("Back", self.go_back))
        return items

    def _summary_label(self) -> str:
        earned = len(earned_ids(self.profile))
        total = len(ACHIEVEMENTS)
        return f"Summary: {earned} of {total} earned"

    def _summary(self) -> None:
        earned = len(earned_ids(self.profile))
        total = len(ACHIEVEMENTS)
        self.ctx.say(f"{self.profile.name} has earned {earned} of {total} achievements.")


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


class ManageCareersState(MenuState):
    title = "Manage careers"
    intro_help = ("Use up and down arrows to choose a saved career. Enter opens "
                  "reset and delete actions. Escape goes back.")

    def build_items(self) -> list[MenuItem]:
        items = []
        for path, profile in _loadable_saves():
            label = _career_summary(path, profile)
            items.append(MenuItem(
                label,
                lambda p=path, prof=profile: self._manage(p, prof),
                help=f"Manage {profile.name}. Reset starts the career over; "
                     "delete removes the save."))
        items.append(MenuItem("Back", self.go_back))
        return items

    def _manage(self, path: Path, profile: Profile) -> None:
        self.ctx.push_state(CareerActionsState(self.ctx, path, profile))


class CareerActionsState(MenuState):
    title = "Career actions"
    intro_help = ("Choose an action for this saved career. Reset and delete both "
                  "ask for confirmation. Escape goes back.")

    def __init__(self, ctx, path: Path, profile: Profile) -> None:
        super().__init__(ctx)
        self.path = path
        self.profile = profile

    def announce_entry(self) -> None:
        self.ctx.say(f"Actions for {_career_summary(self.path, self.profile)}. "
                     f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem("Reset this career", self._reset,
                     help="Start this driver over with a fresh truck, money, "
                          "career stats, market, and hours of service clock."),
            MenuItem("Delete this career", self._delete,
                     help="Permanently remove this saved career file."),
            MenuItem("Back", self.go_back),
        ]

    def _reset(self) -> None:
        self.ctx.push_state(ConfirmCareerActionState(
            self.ctx, self.path, self.profile, action="reset"))

    def _delete(self) -> None:
        self.ctx.push_state(ConfirmCareerActionState(
            self.ctx, self.path, self.profile, action="delete"))


class ConfirmCareerActionState(MenuState):
    title = "Confirm career action"
    open_sound_key = "ui/error"
    intro_help = ("Use up and down arrows. Enter confirms the selected option. "
                  "Escape cancels.")

    def __init__(self, ctx, path: Path, profile: Profile, *, action: str) -> None:
        super().__init__(ctx)
        self.path = path
        self.profile = profile
        self.action = action

    @property
    def _action_label(self) -> str:
        return "reset" if self.action == "reset" else "delete"

    def announce_entry(self) -> None:
        if self.action == "reset":
            detail = ("Resetting starts this driver over at "
                      f"{self.profile.current_city} with a fresh truck, "
                      "starting money, no active trip, and no delivery history.")
        else:
            detail = "Deleting permanently removes this saved career."
        self.ctx.say(
            f"Confirm {self._action_label} for {self.profile.name}. {detail} "
            f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(f"Yes, {self._action_label} {self.profile.name}",
                     self._confirm,
                     help=f"Confirm and {self._action_label} this saved career."),
            MenuItem("No, keep this career", self.go_back,
                     help="Cancel and return to career actions."),
        ]

    def _confirm(self) -> None:
        name = self.profile.name
        if self.action == "reset":
            fresh = Profile(name=name, current_city=self.profile.current_city)
            apply_start_option(fresh, option_for_profile(self.profile))
            fresh.save()
            message = (f"{name} reset. The career starts over at "
                       f"{fresh.current_city} with {fresh.carrier_name} "
                       f"and {fresh.money:,.0f} dollars.")
        else:
            self.path.unlink(missing_ok=True)
            if self.ctx.profile is not None and self.ctx.profile.path == self.path:
                self.ctx.profile = None
            message = f"{name} deleted."
        self.ctx.reset_to(MainMenuState(self.ctx))
        self.ctx.say(message, interrupt=True)


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
        self.ctx.push_state(CareerStartState(self.ctx, name))

    def lines(self) -> list[str]:
        return ["New career", "", f"Driver name: {self.name}_",
                "Press Enter to confirm, Escape to cancel, F2 to review."]


class CareerStartState(MenuState):
    title = "Career start"
    intro_help = (
        "Choose how this career starts. Company-driver starts use assigned "
        "carrier equipment and carrier-paid routine costs. The owner-operator "
        "start is higher risk: you control a starter tractor and pay operating "
        "costs from day one. Enter selects; Escape goes back to name entry."
    )

    def __init__(self, ctx, driver_name: str) -> None:
        super().__init__(ctx)
        self.driver_name = driver_name

    def announce_entry(self) -> None:
        self.ctx.say(
            "Career start. Pick a carrier or owner-operator start. "
            f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                f"{option.label}. {option.menu_summary}",
                lambda key=option.key: self._pick(key),
                help=option.help_text,
            )
            for option in all_start_options()
        ]

    def _pick(self, key: str) -> None:
        option = start_option(key)
        self.ctx.audio.play("ui/menu_select")
        self.ctx.push_state(HomeTerminalState(self.ctx, self.driver_name, option.key))


def _region_menu_name(region: str) -> str:
    """Region label suited to a menu item and first-letter jump.

    The spoken labels read naturally as prose ("in the Great Lakes"), but a
    list where every entry starts with "the" defeats type-ahead, so the leading
    article is dropped for menu display.
    """
    label = REGION_LABELS.get(region, region.replace("_", " "))
    return label[4:] if label.startswith("the ") else label


class HomeTerminalState(MenuState):
    """Pick the region of the country where a brand-new career begins.

    Region selection is the first of two levels: choosing a region opens a
    :class:`HomeCityState` listing only that region's cities. A short region
    list keeps the spoken navigation manageable as the map grows toward national
    coverage, instead of one long flat list of every city.
    """

    title = "Home region"
    intro_help = ("Pick the part of the country where your trucking career "
                  "begins. Use up and down arrows, Home and End, or type a "
                  "letter to jump to a region. Enter opens that region's cities. "
                  "Escape goes back to name entry.")

    def __init__(self, ctx, driver_name: str, start_key: str) -> None:
        super().__init__(ctx)
        self.driver_name = driver_name
        self.start_key = start_key
        option = start_option(start_key)
        by_region: dict[str, list[str]] = {}
        for city in ctx.world.cities.values():
            by_region.setdefault(city.region, []).append(city.name)
        for names in by_region.values():
            names.sort()
        self._cities_by_region = by_region
        self._regions = sorted(by_region, key=_region_menu_name)
        default_city = option.default_city if option.default_city in ctx.world.cities else DEFAULT_CITY
        default = ctx.world.cities[default_city].region \
            if default_city in ctx.world.cities else None
        if default in self._regions:
            self.index = self._regions.index(default)

    def announce_entry(self) -> None:
        option = start_option(self.start_key)
        self.ctx.say("Home region. Pick the part of the country where your "
                     f"{option.carrier_name} career starts. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        for region in self._regions:
            name = _region_menu_name(region)
            count = len(self._cities_by_region[region])
            noun = "city" if count == 1 else "cities"
            items.append(MenuItem(
                f"{name} ({count} {noun})",
                lambda r=region: self._pick_region(r),
                help=f"Open {name} to choose a starting city. "
                     f"{count} {noun} available."))
        return items

    def _pick_region(self, region: str) -> None:
        self.ctx.push_state(HomeCityState(
            self.ctx, self.driver_name, self.start_key, region,
            self._cities_by_region[region]))


class HomeCityState(MenuState):
    """Pick the home terminal city within a chosen region."""

    title = "Home terminal"
    intro_help = ("Pick the city where your trucking career begins. Use up and "
                  "down arrows, Home and End, or type a letter to jump to a "
                  "city. Enter confirms your home terminal. Escape goes back to "
                  "the region list.")

    def __init__(self, ctx, driver_name: str, start_key: str, region: str,
                 city_names: list[str]) -> None:
        super().__init__(ctx)
        self.driver_name = driver_name
        self.start_key = start_key
        self.region = region
        self._cities = list(city_names)
        option = start_option(start_key)
        if option.default_city in self._cities:
            self.index = self._cities.index(option.default_city)
        elif DEFAULT_CITY in self._cities:
            self.index = self._cities.index(DEFAULT_CITY)

    def announce_entry(self) -> None:
        region = _region_menu_name(self.region)
        self.ctx.say(f"{region} terminals. Pick the city where your career "
                     f"starts. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        for name in self._cities:
            city = self.ctx.world.cities[name]
            terminal = self.ctx.world.home_terminal(name)
            items.append(MenuItem(f"{name}, {city.state}",
                                  lambda n=name: self._pick(n),
                                  help=f"Start at {terminal.spoken_name} in "
                                       f"{name}, {city.state}."))
        return items

    def _pick(self, city: str) -> None:
        from .city import CityMenuState

        name = self.driver_name
        existing = {p.stem.lower() for p in Profile.list_saves()}
        option = start_option(self.start_key)
        profile = Profile(name=name, current_city=city)
        apply_start_option(profile, option)
        terminal = self.ctx.world.home_terminal(city)
        self.ctx.profile = profile
        profile.save()
        self.ctx.pop_state()   # this city picker
        self.ctx.pop_state()   # region picker
        self.ctx.pop_state()   # career start
        self.ctx.pop_state()   # name entry
        self.ctx.push_state(CityMenuState(self.ctx))
        loaded_over = (f"Loaded over existing driver named {name}. "
                       if name.lower() in existing else "")
        if option.is_owner_operator:
            message = (
                f"{loaded_over}Owner-operator start created for {name}. "
                f"You are leased to {option.carrier_name}, parked at "
                f"{terminal.spoken_name} in the {city} service area, with an "
                f"owned starter tractor and {profile.money:,.0f} dollars of "
                "working capital. Fuel, repairs, and business reserves are "
                "your responsibility from day one. "
                "Your first stop is the dispatch board."
            )
        else:
            message = (
                f"{loaded_over}Welcome aboard to {option.carrier_name}, {name}. "
                "Your assigned company tractor is parked at "
                f"{terminal.spoken_name} in the {city} service area with "
                f"{profile.money:,.0f} dollars and a full tank. "
                "Your first stop is the dispatch board."
            )
        self.ctx.say(message, interrupt=True)


HELP_PAGES = [
    ("The goal", [
        "A new career starts with a choice: company driver carrier or owner-operator start.",
        "Company drivers use assigned carrier equipment and carrier-paid routine costs.",
        "The owner-operator start skips ahead, but fuel, repairs, and business costs are yours.",
        "Start from your company terminal or yard in a metro service area.",
        "Each city stands for a wider freight area with many possible shippers.",
        "Accept freight from a specific shipper facility, deadhead to that pickup,",
        "check in and load the trailer there, then get your route to the destination,",
        "and deliver cargo across the country, on time and intact.",
        "Earn money and experience, level through 20 career ranks, and unlock better freight.",
        "On the company path, level 5 starts owner-operator preparation.",
        "At level 15, with enough deliveries, reputation, and working capital,",
        "Business status lets you buy into a leased-on owner-operator path.",
    ]),
    ("Menus", [
        "All menus use Up and Down arrows, Enter to select, Escape to go back.",
        "Home and End jump to the first and last option.",
        "Type a letter to jump to options starting with that letter.",
        "Press F1 in any menu for contextual help.",
        "Manage careers on the main menu lets you reset or delete saved careers,",
        "with a confirmation screen before anything destructive happens.",
        "Edited or corrupted career saves may be moved aside at the main menu.",
    ]),
    ("Settings", [
        "Settings are grouped into categories: Gameplay, Audio, Speech and",
        "weather, and Updates. Open a category to see its settings.",
        "Use Up and Down arrows to choose a setting inside a category.",
        "Use Right arrow or Enter to change the selected setting forward.",
        "Use Left arrow to change it backward. Escape goes back, and changes",
        "are saved as you make them.",
        "Gameplay settings change how the game feels, not your save progress.",
        "Units switches speed and distance between miles and kilometers.",
        "Transmission chooses automatic shifting or manual shifting.",
        "Trip pacing changes how quickly distance and game time pass while driving.",
        "Relaxed pacing gives you more real time to react.",
        "Standard pacing is the normal Freight Fate pace.",
        "Fast pacing makes long trips move quicker, but decisions arrive sooner.",
        "Hours of service changes how strict the legal driving clock is.",
        "Realistic uses the full driving, duty, break, and rest rules.",
        "Relaxed keeps the clock but gives a more forgiving schedule,",
        "with longer limits and fewer penalties during normal play.",
        "Lane drift adds an optional lane-position task while you drive.",
        "Off keeps the truck centered. Light adds gentle drift.",
        "Realistic adds stronger drift, rumble-strip warnings, and consequences.",
        "Discord presence shows your broad activity in Discord when it is running,",
        "like the main menu, driving a route, or resting, with the route and cargo.",
        "Only general game status is shared, never your saves or personal details.",
        "It is on by default and has no effect if Discord is closed.",
        "Speech settings include verbosity, the driving event voice, and a toggle",
        "for menu position announcements: turn it off to hear only the option,",
        "not its place like three of ten.",
        "Audio volumes have their own help text in the Audio category with F1.",
    ]),
    ("Driving basics", [
        "E starts the engine. To shut it down, slow below 5 miles per hour first.",
        "Air brakes need pressure before the truck can move.",
        "Start the engine and wait for air pressure to reach 100 psi.",
        "Press P to release or set the parking brake.",
        "If you hear low air, keep the parking brake set and let pressure build.",
        "Hard repeated braking can use air faster than gentle normal driving.",
        "Hold the Up arrow to accelerate, the Down arrow to brake.",
        "In automatic, once stopped, keep holding the Down arrow to back up slowly.",
        "Touch the Up arrow to brake and return to forward drive.",
        "Hold B for the emergency brake: the hardest possible stop,",
        "for hazards and rest stops you would otherwise overshoot.",
        "K sets adaptive cruise at your current speed with a three second clear-weather gap.",
        "Rain, snow, fog, or low visibility increase the following gap.",
        "It can slow for traffic ahead, but it does not steer for you.",
        "Plus and minus raise and lower the set cruise speed by five miles per hour,",
        "so you can dial it up to the speed you want once cruise is engaged;",
        "it will not hold more than five over the posted limit.",
        "Cruise will not engage on low-speed local roads, like facility access",
        "roads, construction, or heavy traffic; take those manually.",
        "Press K again or touch the brakes to cancel it.",
        "M toggles the in-cab radio. Left and right brackets tune receivable stations.",
        "Y speaks the radio station, signal or fallback state, volume, source, and streamer-safe status.",
        "The radio defaults to built-in safe music and stays quieter than road cues.",
        "Real public streams and AFN choices stay hidden until you opt in and turn streamer-safe mode off.",
        "In automatic mode the truck shifts for itself.",
        "In manual mode, hold Left Shift for the clutch,",
        "then press 1 through 0 for gears one through ten, or N for neutral.",
        "Manual transmission uses Backspace for reverse after pressing the clutch.",
        "J toggles the engine brake for long downhill grades.",
        "H sounds the horn.",
    ]),
    ("Driving information keys", [
        "Space speaks your speed, gear, RPM, air pressure, and brake state.",
        "S speaks the posted speed limit here, the zone if any, and how far over you are.",
        "Tab opens a driving status menu for speed, route, air tanks, weather, radio, and hours.",
        "F speaks fuel level and range.",
        "C speaks the clock, your deadline, and your hours of service.",
        "R speaks route progress, GPS context, and the next stop or maneuver.",
        "Shift R speaks the next listed highway exit for route context.",
        "Y speaks in-cab radio status. The Radio status screen lists receivable stations.",
        "L speaks lane position when lane drift is enabled.",
        "V speaks the weather and the forecast.",
        "A repeats the last route announcement, in case you missed it.",
        "U speaks what is coming up: imposed speed limits, patrols, stops, and exits ahead.",
        "Escape opens the pause menu.",
    ]),
    ("On the road", [
        "Loaded trips follow a route made from real highway corridors.",
        "Progress is not just city to city: GPS announces state lines,",
        "intermediate places, traffic, highway changes, and rest-stop exits.",
        "Grades and terrain come from the route you are driving.",
        "Weather, traffic, and construction still vary by time, place, and seed.",
        "Morning and afternoon rush hours can make metro corridors busier.",
        "Weather is not just flavor. Driving well over the safe speed for the",
        "conditions on a slick road risks losing traction; high winds and storms",
        "add drag that costs speed and fuel; and low visibility shortens how much",
        "warning you get before a hazard, so slow down in fog and heavy rain.",
        "Your career runs on a calendar that starts in spring and advances as you",
        "drive, rest, and sleep, so the season and weather shift through the year.",
        "The date and season are spoken with the clock on C, in the Tab status",
        "menu, and at the city terminal.",
        "Posted limits come from real map data and change along the corridor.",
        "A change is announced as reduced or raised, and named near a city.",
        "Watch your speed: limits also drop in construction and traffic zones.",
        "State troopers patrol some stretches. Speed badly inside a patrol and a",
        "CB radio chatter can warn you a few miles before a patrol window.",
        "Use U if you want to check upcoming patrols along with other guidance.",
        "trooper may light you up: signal with X, brake to a stop on the shoulder,",
        "and sit through a license and logbook check ending in an on-the-spot",
        "ticket or a warning. Ignoring the lights is logged as evasion, which",
        "costs far more. Speeding the patrols miss still adds a quieter charge",
        "at settlement.",
        "Some hazards come from traffic ahead, such as slow lead vehicles,",
        "merging traffic, lane restrictions, and queues.",
        "Highway stops use clear place names and list the actions available there.",
        "Depending on the stop, you may be able to fuel, eat, rest, save, inspect,",
        "or call for help.",
        "Toll roads, plazas, and electronic gantries are announced while driving.",
        "Tolls and approved company charges are paid or reimbursed at settlement.",
        "They are listed separately from costs you caused, like speeding fines.",
        "Service plazas on toll roads still behave like stops when fuel, food,",
        "breaks, or saves are available.",
        "When you hear Brake now, slow below twenty five miles per hour quickly",
        "to avoid a collision. These warnings are tied to road or traffic context.",
        "Hold B for the emergency brake when normal braking is not enough.",
        "Traffic pressure cues name exit lanes, merges, and target speeds.",
        "Signal early, leave a gap, and avoid forcing a tight merge.",
        "Rest stops sit at highway exits, announced a few miles out.",
        "The GPS adds one-mile exit cues and concise turn guidance.",
        "Press X to signal for the exit, move right for the exit lane,",
        "slow to forty five for the ramp,",
        "then brake to a stop for the rest stop menu:",
        "refuel, take a break, sleep, or save. Too fast and you miss the exit.",
        "Destination exits are announced with their signed exit and toward cities.",
        "Press X for the destination exit too, set the exit lane,",
        "then brake to the receiver gate.",
        "If you miss the destination exit, back up until it is ahead, then press X.",
        "Ordinary pass-by exits stay out of automatic speech;",
        "use Shift R when you want the next listed exit for context.",
        "T still opens the menu if you simply stop on the highway at one.",
        "If you miss a stop, slow down, back up carefully to it, stop, then press T.",
        "Fuel prices vary by region.",
        "Company-driver fuel and carrier repairs are billed to the carrier.",
        "Owner-operators pay fuel, repairs, and roadside rescue from the business.",
        "Running out of fuel means roadside rescue and lost time.",
        "If collisions leave the truck badly damaged, open the pause menu",
        "and call a roadside mechanic for a field repair.",
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
        "Driving past a limit risks inspections, fines, and out-of-service orders.",
        "Fatigue builds as you drive, faster at night. A drowsy driver",
        "yawns, drifts onto the rumble strip, and reacts late to hazards.",
        "Coffee stops ease fatigue a little, but only a thirty minute",
        "non-driving break satisfies the break rule.",
        "Late at night, truck parking may be full. Drive on, or risk",
        "a ticket and poor sleep on the shoulder.",
        "You can always find somewhere to sleep. Stopped on the open road with no",
        "stop nearby, the pause menu offers an emergency shoulder sleep: a legal",
        "ten-hour reset, but poor rest, with a possible parking ticket or minor",
        "damage, and the deadline keeps running.",
        "A basic break or fuel stop with no sleeper berth offers an emergency",
        "sleep in the lot: the same legal reset, cramped and poor.",
        "Proper sleeper stops still give the best, fully-rested ten-hour sleep.",
        "When a sleep or duty limit is closing in with no reachable stop, the game",
        "warns you and points you to the shoulder-sleep option.",
        "Settings can make hours rules gentler.",
    ]),
    ("Deliveries and money", [
        "The dispatch board lists freight for the current metro service area.",
        "As a company driver, listed pay is carrier gross. Your settlement pays",
        "driver wages and bonuses. Starter carriers use different wage floors,",
        "stop pay, pay share, on-time bonus, route mix, and freight emphasis.",
        "As an owner-operator, listed pay is gross revenue. Your business pays",
        "fuel, repairs, maintenance reserve, insurance, trailer program,",
        "truck payment reserve, and settlement fees.",
        "Level 5 starts the owner-operator preparation path.",
        "The leased-on owner-operator buy-in unlocks later, at level 15,",
        "when your deliveries, reputation, cash, and pay advances are ready.",
        "Level 20 completes the current owner-operator arc.",
        "At level 20, qualified owner-operators can set aside an authority",
        "prep reserve from Business status.",
        "Prepared owner-operators can later activate own authority from",
        "Business status when deliveries, reputation, trailer programs,",
        "cash, and reserves are ready.",
        "Own authority adds direct freight with higher gross revenue, plus",
        "insurance, compliance, trailer, truck, and factoring costs.",
        "A metro can contain ports, rail and intermodal ramps, air cargo areas,",
        "parcel hubs, grocery distribution centers, dry warehouses, cold storage,",
        "food processors, farms and grain elevators, manufacturing plants,",
        "steel and industrial sites, automotive suppliers, chemical terminals,",
        "construction yards, mines and quarries, lumber or paper facilities,",
        "cross-docks, and company yards.",
        "Each job names an origin facility and a destination facility.",
        "Cargo follows facility roles, so grain elevators ship different freight",
        "than parcel hubs, ports, warehouses, factories, or cold storage.",
        "Not every market supports every cargo equally.",
        "Regional freight patterns shape the board: ports see containers and bulk,",
        "agricultural regions see grain and food, industrial regions see steel,",
        "machinery, automotive, chemicals, lumber, and construction materials.",
        "Border and gateway metros often offer cross-dock logistics freight.",
        "After accepting a dispatch, leave the terminal bobtail or with an empty trailer.",
        "Pickup legs are local deadhead moves to the origin facility.",
        "At the pickup gate, stop to open the facility menu.",
        "Check in, then load at the assigned dock.",
        "Loading requires the truck to be stopped.",
        "Once loaded and sealed, dispatch gives you the destination route.",
        "GPS cues call out highway changes, state lines, places, and rest stops.",
        "The job is the load and destination; route choice happens after pickup.",
        "Deliver before the deadline for a bonus. Late or damaged cargo pays less.",
        "At the destination facility, stop, then dock and deliver.",
        "Delivery settlement reports gross pay, carrier-paid or reimbursed charges,",
        "business status, business costs, driver-responsibility",
        "charges, and net driver pay.",
        "After settlement, the truck is parked at the destination service-area terminal.",
        "Fragile cargo, like electronics and fresh food, punishes rough driving.",
        "Repair the active tractor in the terminal garage. Damage reduces engine power.",
        "Higher levels widen distance caps, improve low-end pay,",
        "unlock more facility variety, refrigerated, heavy-haul, and high-value freight,",
        "and track business ranks.",
        "Cargo markets drift day by day. The dispatch board calls out tight and loose",
        "markets; tight cargo pays well above the usual rate.",
    ]),
    ("Markets and route coverage", [
        "Freight Fate focuses on major freight areas instead of every town.",
        "The highway map connects those areas with drivable long-haul routes.",
        "Freight variety comes from the facilities inside each area.",
        "A load may route from Chicago to Los Angeles, but the work can be",
        "an intermodal ramp, cold storage, port terminal, parcel hub, or plant.",
        "New dispatches use routes with enough stops to make fuel, rest,",
        "and hours planning playable.",
        "Some common facilities are representative locations for the area.",
        "They still behave like named places with clear cargo roles.",
    ]),
    ("The garage", [
        "Every terminal garage refuels and repairs the active tractor.",
        "Company drivers use an assigned tractor and bill routine fuel and repairs to the carrier.",
        "Owner-operators pay the shop. If cash is short, the garage buys as much",
        "fuel or repair work as your money covers toward a full tank or full repair.",
        "The Upgrades menu sells permanent improvements: an engine tune,",
        "an aerodynamic kit, a long-range tank, and reinforced brakes.",
        "Upgrades and truck purchases unlock once you become a leased-on owner-operator.",
        "Engine tune gives more pulling power for heavy freight, hills, and mountain grades.",
        "Aerodynamic kit burns less fuel at highway speed; same tank, fewer gallons per mile.",
        "Long-range tank carries fifty more gallons; more fuel onboard, not better efficiency.",
        "Reinforced brakes keep stopping power longer on descents and emergency stops.",
        "The Trucks menu sells the heavy hauler: more torque and a bigger",
        "tank, but worse aerodynamics and a thirstier engine.",
        "After the owner-operator buy-in, switch between tractors you own at any garage.",
    ]),
]


def controls_help_page() -> int:
    """Index of the driving-keys page, so callers can open help straight to it."""
    for i, (title, _lines) in enumerate(HELP_PAGES):
        if title == "Driving information keys":
            return i
    return 0


class HelpState(State):
    """Page-by-page, line-by-line spoken manual."""

    def __init__(self, ctx, start_page: int = 0) -> None:
        super().__init__(ctx)
        self.page = max(0, min(start_page, len(HELP_PAGES) - 1))
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
    """Top-level settings: a category picker that opens per-category submenus.

    A tabbed multi-page layout reads poorly without a screen to show the tabs,
    so each category is its own spoken submenu instead, matching every other
    menu's navigation model.
    """

    title = "Settings"
    intro_help = (
        "Settings are grouped into categories. Use up and down arrows to pick a "
        "category, Enter to open it, and Escape to go back. Each category opens "
        "its own list of settings."
    )

    CATEGORIES = (
        ("Gameplay", "gameplay"),
        ("Audio", "audio"),
        ("Speech and weather", "speech"),
        ("Updates", "updates"),
    )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(label, lambda key=key: self._open(key),
                     help=f"Open {label.lower()} settings.")
            for label, key in self.CATEGORIES
        ]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _open(self, category: str) -> None:
        self.ctx.push_state(SettingsCategoryState(self.ctx, category))

    def go_back(self) -> None:
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_back")
        self.ctx.say("Settings saved.")
        self.ctx.pop_state()


class SettingsCategoryState(MenuState):
    """One category of settings as a spoken list.

    Up and down pick a setting; Right arrow or Enter changes it forward and Left
    changes it backward (the same per-item adjust model as the old tabbed
    screen, minus the tab switching). Escape returns to the settings categories,
    and each change is saved as it is made.
    """

    intro_help = (
        "Use up and down arrows to pick a setting. Right arrow or Enter changes "
        "the selected setting forward, and Left arrow changes it backward. "
        "Escape goes back to the settings categories."
    )

    TITLES = {
        "gameplay": "Gameplay",
        "audio": "Audio",
        "speech": "Speech and weather",
        "updates": "Updates",
    }

    def __init__(self, ctx, category: str) -> None:
        super().__init__(ctx)
        self.category = category

    @property
    def title(self) -> str:  # type: ignore[override]
        return self.TITLES.get(self.category, "Settings")

    def build_items(self) -> list[MenuItem]:
        s = self.ctx.settings
        if self.category == "gameplay":
            return [
                MenuItem(
                    lambda: f"Units: {'imperial, miles' if s.imperial_units else 'metric, kilometers'}",
                    lambda: self._toggle_units(1),
                    help="Switch distance and speed readouts between miles and kilometers."),
                MenuItem(
                    lambda: f"Transmission: {'automatic' if s.automatic_transmission else 'manual'}",
                    lambda: self._toggle_transmission(1),
                    help="Automatic shifts for you. Manual uses clutch and number keys."),
                MenuItem(lambda: f"Trip pacing: {self._pace_label()}",
                         lambda: self._cycle_pace(1),
                         help="Controls how quickly game time and distance pass."),
                MenuItem(lambda: f"Hours of service: {self._hos_label()}",
                         lambda: self._cycle_hos(1),
                         help="Realistic enforces full hours rules and normal "
                              "road hazards. Relaxed eases the hours limits and "
                              "makes road hazards rare, so you can focus on "
                              "driver responsibility: hours, fueling, and repairs."),
                MenuItem(lambda: f"Lane drift: {self._steering_label()}",
                         lambda: self._cycle_steering(1),
                         help="Choose whether lane drift is off, light, or realistic."),
                MenuItem(lambda: f"Discord presence: {'on' if s.discord_presence else 'off'}",
                         lambda: self._toggle_discord_presence(1),
                         help="Show broad activity in Discord, like the main menu, "
                              "driving a route, or resting. Only general game status "
                              "is shared, never your save files or personal details. "
                              "Has no effect if Discord is not running."),
                MenuItem("Back", self.go_back),
            ]
        if self.category == "audio":
            return [
                MenuItem(lambda: f"Master volume: {round(s.master_volume * 100)} percent",
                         lambda: self._volume("master_volume", 0.1),
                         help="Overall game volume."),
                MenuItem(lambda: f"Gameplay cues volume: {round(s.sfx_volume * 100)} percent",
                         lambda: self._volume("sfx_volume", 0.1),
                         help="Horn, alerts, road, facility, and gameplay cue sounds."),
                MenuItem(lambda: f"Weather sounds volume: {round(s.weather_volume * 100)} percent",
                         lambda: self._volume("weather_volume", 0.1),
                         help="Rain, wind, thunder, snow, and fog sounds."),
                MenuItem(lambda: f"Engine sounds volume: {round(s.engine_volume * 100)} percent",
                         lambda: self._volume("engine_volume", 0.1),
                         help="Engine start, shutdown, and running engine sounds."),
                MenuItem(lambda: f"Music volume: {round(s.music_volume * 100)} percent",
                         lambda: self._volume("music_volume", 0.1),
                         help="Menu and facility background music volume."),
                MenuItem(lambda: f"In-cab radio volume: {round(s.radio_volume * 100)} percent",
                         lambda: self._volume("radio_volume", 0.1),
                         help="Music volume while driving. Kept lower by default so speech, engine, and safety cues stay clear."),
                MenuItem(lambda: f"Radio streamer-safe mode: {'on' if s.radio_streamer_safe else 'off'}",
                         lambda: self._toggle_radio_streamer_safe(1),
                         help="When on, the radio uses only built-in safe stations and skips real public streams."),
                MenuItem(lambda: f"Radio real public streams: {'on' if s.radio_real_streams else 'off'}",
                         lambda: self._toggle_radio_real_streams(1),
                         help="Opt in to real public stream stations. Streamer-safe mode must also be off before they can play."),
                MenuItem(lambda: f"Menu and UI sounds volume: {round(s.ui_volume * 100)} percent",
                         lambda: self._volume("ui_volume", 0.1),
                         help="Menu movement, selection, warning, and cash sounds."),
                MenuItem("Back", self.go_back),
            ]
        if self.category == "speech":
            items = [MenuItem(label, (lambda a=action: a(1)), help=help_text)
                     for label, action, help_text in self._speech_control_specs()]
            items.append(MenuItem("Back", self.go_back))
            return items
        return [
            MenuItem(lambda: ("Update channel: "
                              f"{'developer snapshots' if self._channel() == 'dev' else 'stable releases'}"),
                     lambda: self._toggle_update_channel(1),
                     help="Choose stable releases or developer snapshots."),
            MenuItem("Check for updates", self._check_updates,
                     help="Look for a new version of the game right now."),
            MenuItem("Back", self.go_back),
        ]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT:
            self._adjust(1)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT:
            self._adjust(-1)
        else:
            super().handle_event(event)

    def _adjust(self, direction: int) -> None:
        if self.category == "speech":
            actions = [action for _, action, _ in self._speech_control_specs()]
        else:
            actions = {
                "gameplay": [
                    self._toggle_units, self._toggle_transmission,
                    self._cycle_pace, self._cycle_hos, self._cycle_steering,
                    self._toggle_discord_presence,
                ],
                "audio": [
                    lambda d: self._volume("master_volume", 0.1 * d),
                    lambda d: self._volume("sfx_volume", 0.1 * d),
                    lambda d: self._volume("weather_volume", 0.1 * d),
                    lambda d: self._volume("engine_volume", 0.1 * d),
                    lambda d: self._volume("music_volume", 0.1 * d),
                    lambda d: self._volume("radio_volume", 0.1 * d),
                    self._toggle_radio_streamer_safe,
                    self._toggle_radio_real_streams,
                    lambda d: self._volume("ui_volume", 0.1 * d),
                ],
                "updates": [self._toggle_update_channel],
            }[self.category]
        if self.index < len(actions):
            actions[self.index](direction)

    def _speech_control_specs(self):
        """Speech-category controls as (label, action, help) triples.

        Built dynamically so the menu and the left/right adjust handler stay in
        sync, and so rate, pitch, volume, and voice only appear when the active
        voices actually support them (a running screen reader does not)."""
        s = self.ctx.settings
        speech = self.ctx.speech
        specs = [
            (lambda: f"Speech verbosity: {['terse', 'normal', 'chatty'][s.speech_verbosity]}",
             self._cycle_verbosity,
             "Controls how often driving status reminders speak."),
            (lambda: f"Menu position announcements: {'on' if s.announce_menu_position else 'off'}",
             self._toggle_menu_position,
             "When on, menus say the position, like 3 of 10, after each option. "
             "Turn off to hear only the option."),
            (lambda: f"Driving event voice: {self._event_voice_label()}",
             self._cycle_event_voice,
             "Speaks road events through the main voice or a separate SAPI or "
             "OneCore voice, so a screen reader cannot cut them off."),
        ]
        if speech.supports_rate:
            specs.append((
                lambda: f"Speech rate: {round(s.speech_rate * 100)} percent",
                lambda d: self._adjust_speech("speech_rate", 0.1 * d),
                "How fast the game's voice speaks, where the voice allows it."))
        if speech.supports_pitch:
            specs.append((
                lambda: f"Speech pitch: {round(s.speech_pitch * 100)} percent",
                lambda d: self._adjust_speech("speech_pitch", 0.1 * d),
                "How high or low the game's voice sounds."))
        if speech.supports_volume:
            specs.append((
                lambda: f"Speech volume: {round(s.speech_volume * 100)} percent",
                lambda d: self._adjust_speech("speech_volume", 0.1 * d),
                "Loudness of the game's voice, separate from sound volume."))
        if speech.voice_names():
            specs.append((
                lambda: f"Speech voice: {s.speech_voice or 'default'}",
                self._cycle_voice,
                "Which installed voice the game speaks with."))
        specs.append((
            lambda: f"Weather source: {'real world' if s.real_weather else 'simulated'}",
            self._toggle_real_weather,
            "Real world uses live city conditions when available."))
        return specs

    def _pace_label(self) -> str:
        scale = self.ctx.settings.time_scale
        return {10.0: "relaxed", 20.0: "standard", 40.0: "fast"}.get(
            scale, f"{scale:g} times")

    def _hos_label(self) -> str:
        return {
            "realistic": "realistic",
            "relaxed": "relaxed",
            "debug_off": "off (developer)",
        }.get(self.ctx.settings.hos_mode, "realistic")

    def _steering_label(self) -> str:
        return {
            "off": "off",
            "light": "light",
            "realistic": "realistic",
        }.get(self.ctx.settings.steering_assist, "off")

    def _announce(self) -> None:
        self.refresh()
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_select")
        self.speak_current()

    def _announce_speech_preview(self, setting: str) -> None:
        self.refresh()
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_select")
        text = self.current_text()
        if not self.ctx.speech.say_adjustment_preview(setting, text):
            self.ctx.say(text)

    def _toggle_units(self, _d: int) -> None:
        self.ctx.settings.imperial_units = not self.ctx.settings.imperial_units
        self._announce()

    def _toggle_transmission(self, _d: int) -> None:
        self.ctx.settings.automatic_transmission = (
            not self.ctx.settings.automatic_transmission)
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
        self.ctx.settings.save()
        self._apply_audio_volumes()
        self._announce()

    def _apply_audio_volumes(self) -> None:
        self.ctx.apply_volumes()
        if self._driving_radio_active():
            self.ctx.audio.set_volumes(music=self.ctx.settings.radio_volume)

    def _driving_radio_active(self) -> bool:
        for state in reversed(self.ctx._app.states):
            radio = getattr(state, "radio", None)
            if radio is not None:
                return bool(getattr(radio, "enabled", False))
        return False

    def _cycle_hos(self, d: int) -> None:
        modes = ["realistic", "relaxed"]
        try:
            i = modes.index(self.ctx.settings.hos_mode)
        except ValueError:
            i = 0
        self.ctx.settings.hos_mode = modes[(i + d) % len(modes)]
        self._announce()

    def _cycle_steering(self, d: int) -> None:
        modes = ["off", "light", "realistic"]
        try:
            i = modes.index(self.ctx.settings.steering_assist)
        except ValueError:
            i = 0
        self.ctx.settings.steering_assist = modes[(i + d) % len(modes)]
        self._announce()

    def _toggle_discord_presence(self, _d: int) -> None:
        self.ctx.settings.discord_presence = not self.ctx.settings.discord_presence
        self.ctx.apply_presence()
        self._announce()

    def _toggle_radio_streamer_safe(self, _d: int) -> None:
        self.ctx.settings.radio_streamer_safe = not self.ctx.settings.radio_streamer_safe
        self._announce()

    def _toggle_radio_real_streams(self, _d: int) -> None:
        self.ctx.settings.radio_real_streams = not self.ctx.settings.radio_real_streams
        self._announce()

    def _cycle_verbosity(self, d: int) -> None:
        self.ctx.settings.speech_verbosity = (self.ctx.settings.speech_verbosity + d) % 3
        self._announce()

    def _toggle_menu_position(self, _d: int) -> None:
        s = self.ctx.settings
        s.announce_menu_position = not s.announce_menu_position
        self._announce()

    _EVENT_BACKEND_NAMES = {"OneCore": "Windows OneCore"}

    def _event_voice_label(self) -> str:
        s = self.ctx.settings
        if not s.sapi_events:
            return "main voice"
        return self._EVENT_BACKEND_NAMES.get(s.event_backend, s.event_backend)

    def _cycle_event_voice(self, d: int) -> None:
        s = self.ctx.settings
        # None = the main voice; the rest are the available separate voices.
        options = [None, *self.ctx.speech.event_backend_options()]
        current = s.event_backend if s.sapi_events else None
        i = options.index(current) if current in options else 0
        choice = options[(i + d) % len(options)]
        if choice is None:
            s.sapi_events = False
        else:
            s.sapi_events = True
            s.event_backend = choice
        self.ctx.settings.save()
        self.ctx.apply_speech()
        self._announce()

    def _adjust_speech(self, attr: str, delta: float) -> None:
        value = getattr(self.ctx.settings, attr)
        setattr(self.ctx.settings, attr, max(0.0, min(1.0, round(value + delta, 2))))
        self.ctx.settings.save()
        self.ctx.apply_speech()
        self._announce_speech_preview(attr)

    def _cycle_voice(self, d: int) -> None:
        voices = self.ctx.speech.voice_names()
        if not voices:
            return
        current = self.ctx.settings.speech_voice
        if current in voices:
            i = (voices.index(current) + d) % len(voices)
        else:
            i = 0 if d >= 0 else len(voices) - 1
        self.ctx.settings.speech_voice = voices[i]
        self.ctx.settings.save()
        self.ctx.apply_speech()
        self._announce_speech_preview("speech_voice")

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
        # Settings are saved as each change is made; just return to the
        # category list (the top-level picker says "Settings saved" on exit).
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
