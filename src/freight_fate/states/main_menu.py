"""Main menu, profile selection, name entry, settings, and help screens."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pygame

from .. import __version__, updater
from ..achievements import ACHIEVEMENTS, earned_ids
from ..data.regions import REGION_LABELS
from ..models.profile import DEFAULT_CITY, Profile, ProfileIntegrityError
from ..music import select_menu_music_sequence
from ..settings import TIME_SCALES
from .base import MenuItem, MenuState, State
from .main_menu_help import (
    HELP_PAGES as HELP_PAGES,
)
from .main_menu_help import (
    HelpState,
)
from .main_menu_help import (
    controls_help_page as controls_help_page,
)
from .update import UpdateChecker, UpdateCheckState, UpdatePromptState

_last_invalid_saves: list[Path] = []


def pending_notice_state(ctx) -> State | None:
    """The next one-time save notice the player has not heard yet, if any."""
    if ctx.profile.migration_notice_pending:
        from .save_notice import SaveMigrationNoticeState

        return SaveMigrationNoticeState(ctx)
    if ctx.profile.integrity_notice_pending:
        from .save_notice import SaveModifiedNoticeState

        return SaveModifiedNoticeState(ctx)
    return None


def enter_world(ctx) -> None:
    """Resume a saved mid-trip delivery if there is one, else the terminal hub."""
    ctx.push_state(pending_notice_state(ctx) or _world_entry_state(ctx))


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
            profile = Profile.load(path)
        except ProfileIntegrityError:
            _last_invalid_saves.append(path)
        except Exception:
            continue
        else:
            # Loading may have converted a legacy file in place; report the
            # path the career actually lives at now.
            saves.append((profile.path, profile))
    return saves


def _career_location(profile: Profile) -> str:
    from ..data.world import get_world
    from ..models.jobs import facility_text

    trip = profile.active_trip or {}
    job = trip.get("job", {})
    destination = job.get("destination")
    # Spoken fields exist in post-slug payloads; legacy payloads fall back to
    # origin/destination, which there hold the old speakable display name.
    if trip.get("kind") == "pickup_drive":
        origin = str(job.get("origin_spoken") or job.get("origin") or profile.current_city)
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
            str(job.get("destination_spoken") or destination),
            str(job.get("destination_locality", "")),
        )
        return f"{loaded} {facility}"
    if destination:
        facility = facility_text(
            str(job.get("destination_type", "metro_market")),
            str(job.get("destination_location", "")),
            str(job.get("destination_spoken") or destination),
            str(job.get("destination_locality", "")),
        )
        return f"on the road to {facility}"
    try:
        terminal = get_world().home_terminal(profile.current_city)
        return f"at {terminal.name} in {get_world().spoken_city(profile.current_city)}"
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

    @classmethod
    def arm_update_check(cls, settings) -> None:
        """Start a fresh silent check for the next main-menu update cycle."""
        if not updater.is_frozen():
            return
        cls._update_checker = UpdateChecker(settings)
        cls._update_prompted = False

    def enter(self) -> None:
        super().enter()
        profile = self.ctx.profile
        if profile is None:
            saves = _loadable_saves()
            profile = saves[0][1] if saves else None
        sequence = select_menu_music_sequence(profile)
        self.ctx.play_music_sequence("menu", sequence)
        cls = MainMenuState
        if cls._update_checker is None:
            cls.arm_update_check(self.ctx.settings)

    def update(self, dt: float) -> None:
        super().update(dt)
        cls = MainMenuState
        checker = cls._update_checker
        if cls._update_prompted or checker is None or not checker.done.is_set():
            return
        cls._update_prompted = True
        info = checker.result
        if info is not None and info.tag != self.ctx.settings.skipped_update:
            self.ctx.push_state(UpdatePromptState(self.ctx, info))

    def announce_entry(self) -> None:
        warning = ""
        if _last_invalid_saves:
            count = len(_last_invalid_saves)
            warning = (
                f"{count} saved career could not be read and was moved aside. "
                if count == 1
                else f"{count} saved careers could not be read and were moved aside. "
            )
        self.ctx.say(
            f"Welcome to Freight Fate, version {updater.spoken_version(__version__)}. "
            f"An audio trucking adventure across America. {warning}"
            f"{self.current_text()}",
        )

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        saves = _loadable_saves()
        if saves:
            latest_path, latest_profile = saves[0]
            items.append(
                MenuItem(
                    f"Continue latest career: "
                    f"{_career_summary(latest_path, latest_profile, include_saved=False)}",
                    self._continue,
                    help=f"Load the newest save for {latest_profile.name}.",
                )
            )
            items.append(
                MenuItem(
                    "Choose career",
                    self._load_menu,
                    help="Choose any saved career instead of only the newest one.",
                )
            )
            items.append(
                MenuItem(
                    "Manage careers", self._manage_careers, help="Reset or delete saved careers."
                )
            )
        items.append(MenuItem("New career", self._new_game, help="Start a fresh trucking career."))
        items.append(
            MenuItem(
                "Achievements",
                self._achievements,
                help="Review earned and locked achievements for a saved career.",
            )
        )
        items.append(
            MenuItem(
                "Drivers online",
                self._drivers_online,
                help="Hear who is hauling right now on the public orinks.net "
                "drivers board. Viewing the board shares nothing about you.",
            )
        )
        items.append(
            MenuItem("How to play", self._help, help="Learn the controls and the goal of the game.")
        )
        items.append(
            MenuItem(
                "Settings",
                self._settings,
                help="Units, transmission mode, volumes, weather, voices, "
                "online sharing, update channel, and trip pacing.",
            )
        )
        items.append(
            MenuItem(
                "Report a problem",
                self._report_issue,
                help="Open the Freight Fate bug report page on GitHub in your web browser.",
            )
        )
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
            self.ctx.say(
                f"Welcome back, {p.name}. You are parked at "
                f"{terminal.name} in {self.ctx.world.spoken_city(p.current_city)} "
                f"with {p.money:,.0f} dollars.",
                interrupt=True,
            )
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

    def _drivers_online(self) -> None:
        from .online_states import DriversOnlineState

        self.ctx.push_state(DriversOnlineState(self.ctx))

    def _report_issue(self) -> None:
        import webbrowser

        url = f"https://github.com/{updater.REPO}/issues/new?template=bug_report.yml"
        try:
            opened = webbrowser.open(url)
        except Exception:
            opened = False
        if not opened:
            self.ctx.say(
                "Could not open a web browser. You can report problems at "
                f"github.com/{updater.REPO}/issues.",
                interrupt=True,
            )
            return
        self.ctx.say(
            "Opening the bug report page in your web browser. "
            "Please attach your game log to the report: it is the file game.log "
            "inside the logs folder, next to the game itself. If you restarted "
            "the game after the problem happened, attach game.prev.log instead. "
            "That is the log from the previous run.",
            interrupt=True,
        )


class AchievementCareerState(MenuState):
    title = "Achievements"
    intro_help = (
        "Choose a saved career to review achievements. Enter opens "
        "that driver's earned and locked achievements. Escape goes back."
    )

    def announce_entry(self) -> None:
        if not self.items or self.items[0].text == "Back":
            self.ctx.say(
                "Achievements. No saved careers yet. Start a career, "
                "then come back after the road has opinions."
            )
            return
        self.ctx.say(f"Achievements. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items = []
        for _path, profile in _loadable_saves():
            earned = len(earned_ids(profile))
            total = len(ACHIEVEMENTS)
            items.append(
                MenuItem(
                    f"{profile.name}: {earned} of {total} earned",
                    lambda p=profile: self._pick(p),
                    help=f"Review achievements for {profile.name}.",
                )
            )
        items.append(MenuItem("Back", self.go_back))
        return items

    def _pick(self, profile: Profile) -> None:
        self.ctx.push_state(AchievementsState(self.ctx, profile))


class AchievementsState(MenuState):
    intro_help = (
        "Use up and down arrows to review achievements. Earned and "
        "locked entries are both shown. Enter repeats the selected "
        "entry. Escape goes back."
    )

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
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        earned = earned_ids(self.profile)
        items = [
            MenuItem(
                self._summary_label, self._summary, help="Hear the total earned achievement count."
            )
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
            items.append(MenuItem(label, lambda text=label: self.ctx.say(text), help=help_text))
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
    intro_help = (
        "Use up and down arrows to choose a saved career. Enter loads "
        "the selected career. Escape goes back."
    )

    def build_items(self) -> list[MenuItem]:
        items = []
        for path, profile in _loadable_saves():
            label = _career_summary(path, profile)
            items.append(
                MenuItem(
                    label,
                    lambda p=profile: self._pick(p),
                    help=f"Load {profile.name}, {_career_location(profile)}.",
                )
            )
        items.append(MenuItem("Back", self.go_back))
        return items

    def _pick(self, profile: Profile) -> None:
        self.ctx.profile = profile
        self.ctx.say(f"Welcome back, {profile.name}.")
        self.ctx.replace_state(pending_notice_state(self.ctx) or _world_entry_state(self.ctx))


class ManageCareersState(MenuState):
    title = "Manage careers"
    intro_help = (
        "Use up and down arrows to choose a saved career. Enter opens "
        "reset and delete actions. Escape goes back."
    )

    def build_items(self) -> list[MenuItem]:
        items = []
        for path, profile in _loadable_saves():
            label = _career_summary(path, profile)
            items.append(
                MenuItem(
                    label,
                    lambda p=path, prof=profile: self._manage(p, prof),
                    help=f"Manage {profile.name}. Reset starts the career over; "
                    "delete removes the save.",
                )
            )
        items.append(MenuItem("Back", self.go_back))
        return items

    def _manage(self, path: Path, profile: Profile) -> None:
        self.ctx.push_state(CareerActionsState(self.ctx, path, profile))


class CareerActionsState(MenuState):
    title = "Career actions"
    intro_help = (
        "Choose an action for this saved career. Reset and delete both "
        "ask for confirmation. Escape goes back."
    )

    def __init__(self, ctx, path: Path, profile: Profile) -> None:
        super().__init__(ctx)
        self.path = path
        self.profile = profile

    def announce_entry(self) -> None:
        self.ctx.say(
            f"Actions for {_career_summary(self.path, self.profile)}. {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "Reset this career",
                self._reset,
                help="Start this driver over with a fresh truck, money, "
                "career stats, market, and hours of service clock.",
            ),
            MenuItem(
                "Delete this career",
                self._delete,
                help="Permanently remove this saved career file.",
            ),
            MenuItem("Back", self.go_back),
        ]

    def _reset(self) -> None:
        self.ctx.push_state(
            ConfirmCareerActionState(self.ctx, self.path, self.profile, action="reset")
        )

    def _delete(self) -> None:
        self.ctx.push_state(
            ConfirmCareerActionState(self.ctx, self.path, self.profile, action="delete")
        )


class ConfirmCareerActionState(MenuState):
    title = "Confirm career action"
    open_sound_key = "ui/error"
    intro_help = "Use up and down arrows. Enter confirms the selected option. Escape cancels."

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
            detail = (
                "Resetting starts this driver over at "
                f"{self.ctx.world.spoken_city(self.profile.current_city)} with a fresh truck, "
                "starting money, no active trip, and no delivery history."
            )
        else:
            detail = "Deleting permanently removes this saved career."
        self.ctx.say(
            f"Confirm {self._action_label} for {self.profile.name}. {detail} {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                f"Yes, {self._action_label} {self.profile.name}",
                self._confirm,
                help=f"Confirm and {self._action_label} this saved career.",
            ),
            MenuItem(
                "No, keep this career", self.go_back, help="Cancel and return to career actions."
            ),
        ]

    def _confirm(self) -> None:
        name = self.profile.name
        if self.action == "reset":
            fresh = Profile(name=name, current_city=self.profile.current_city)
            fresh.save()
            message = (
                f"{name} reset. The career starts over at "
                f"{self.ctx.world.spoken_city(fresh.current_city)} "
                f"with {fresh.money:,.0f} dollars."
            )
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
        self.ctx.say("New career. Type your driver name, then press Enter. Press Escape to cancel.")

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
        return [
            "New career",
            "",
            f"Driver name: {self.name}_",
            "Press Enter to confirm, Escape to cancel, F2 to review.",
        ]


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
    intro_help = (
        "Pick the part of the country where your trucking career "
        "begins. Use up and down arrows, Home and End, or type a "
        "letter to jump to a region. Enter opens that region's cities. "
        "Escape goes back to name entry."
    )

    def __init__(self, ctx, driver_name: str) -> None:
        super().__init__(ctx)
        self.driver_name = driver_name
        by_region: dict[str, list[str]] = {}
        for city in ctx.world.cities.values():
            by_region.setdefault(city.region, []).append(city.key)
        for keys in by_region.values():
            keys.sort(key=lambda k: ctx.world.cities[k].name)
        self._cities_by_region = by_region
        self._regions = sorted(by_region, key=_region_menu_name)
        default = (
            ctx.world.cities[DEFAULT_CITY].region if DEFAULT_CITY in ctx.world.cities else None
        )
        if default in self._regions:
            self.index = self._regions.index(default)

    def announce_entry(self) -> None:
        self.ctx.say(
            "Home region. Pick the part of the country where your "
            f"career starts. {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        for region in self._regions:
            name = _region_menu_name(region)
            count = len(self._cities_by_region[region])
            noun = "city" if count == 1 else "cities"
            items.append(
                MenuItem(
                    f"{name} ({count} {noun})",
                    lambda r=region: self._pick_region(r),
                    help=f"Open {name} to choose a starting city. {count} {noun} available.",
                )
            )
        return items

    def _pick_region(self, region: str) -> None:
        self.ctx.push_state(
            HomeCityState(self.ctx, self.driver_name, region, self._cities_by_region[region])
        )


class HomeCityState(MenuState):
    """Pick the home terminal city within a chosen region."""

    title = "Home terminal"
    intro_help = (
        "Pick the city where your trucking career begins. Use up and "
        "down arrows, Home and End, or type a letter to jump to a "
        "city. Enter confirms your home terminal. Escape goes back to "
        "the region list."
    )

    def __init__(self, ctx, driver_name: str, region: str, city_names: list[str]) -> None:
        super().__init__(ctx)
        self.driver_name = driver_name
        self.region = region
        self._cities = list(city_names)
        if DEFAULT_CITY in self._cities:
            self.index = self._cities.index(DEFAULT_CITY)

    def announce_entry(self) -> None:
        region = _region_menu_name(self.region)
        self.ctx.say(
            f"{region} terminals. Pick the city where your career starts. {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        for key in self._cities:
            city = self.ctx.world.cities[key]
            terminal = self.ctx.world.home_terminal(key)
            place = city.spoken_qualified
            items.append(
                MenuItem(
                    place,
                    lambda k=key: self._pick(k),
                    help=f"Start at {terminal.spoken_name} in {place}.",
                )
            )
        return items

    def _pick(self, city: str) -> None:
        from .city import CityMenuState

        name = self.driver_name
        existing = {p.stem.lower() for p in Profile.list_saves()}
        profile = Profile(name=name, current_city=city)
        terminal = self.ctx.world.home_terminal(city)
        self.ctx.profile = profile
        profile.save()
        self.ctx.pop_state()  # this city picker
        self.ctx.pop_state()  # region picker
        self.ctx.pop_state()  # name entry
        self.ctx.push_state(CityMenuState(self.ctx))
        loaded_over = (
            f"Loaded over existing driver named {name}. " if name.lower() in existing else ""
        )
        self.ctx.say(
            f"{loaded_over}Welcome aboard, {name}. Your truck is parked at "
            f"{terminal.spoken_name} in the {self.ctx.world.spoken_city(city)} "
            f"service area with {profile.money:,.0f} dollars and a full tank. "
            "Your first stop is the dispatch board.",
            interrupt=True,
        )


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
        ("Online", "online"),
        ("Updates", "updates"),
        ("Problem reports", "reports"),
    )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(label, lambda key=key: self._open(key), help=f"Open {label.lower()} settings.")
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
        "online": "Online",
        "updates": "Updates",
        "reports": "Problem reports",
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
                    lambda: (
                        f"Units: {'imperial, miles' if s.imperial_units else 'metric, kilometers'}"
                    ),
                    lambda: self._toggle_units(1),
                    help="Switch distance and speed readouts between miles and kilometers.",
                ),
                MenuItem(
                    lambda: (
                        f"Transmission: {'automatic' if s.automatic_transmission else 'manual'}"
                    ),
                    lambda: self._toggle_transmission(1),
                    help="Automatic shifts for you. Manual uses the clutch "
                    "with W and Q to shift up and down.",
                ),
                MenuItem(
                    lambda: f"Automatic direction changes: {s.automatic_direction_changes}",
                    lambda: self._cycle_automatic_direction_changes(1),
                    help="Simple changes between forward and reverse when you keep "
                    "holding the control after the truck stops. Deliberate waits "
                    "for you to release the control and press it again. This only "
                    "affects automatic transmission.",
                ),
                MenuItem(
                    lambda: f"Trip pacing: {self._pace_label()}",
                    lambda: self._cycle_pace(1),
                    help="Controls how quickly game time and distance pass "
                    "at highway speed. The clock always slows to near real "
                    "time while you accelerate, brake, or maneuver, and runs "
                    "at double pace while parked with the parking brake set.",
                ),
                MenuItem(
                    lambda: f"Hours of service: {self._hos_label()}",
                    lambda: self._cycle_hos(1),
                    help="Realistic enforces full hours rules and normal "
                    "road hazards. Relaxed eases the hours limits and "
                    "makes road hazards rare, so you can focus on "
                    "driver responsibility: hours, fueling, and repairs.",
                ),
                MenuItem(
                    lambda: f"Lane drift: {self._steering_label()}",
                    lambda: self._cycle_steering(1),
                    help="Choose whether lane drift is off, light, or realistic.",
                ),
                MenuItem(
                    lambda: f"Speed keeper: {'on' if s.speed_keeper else 'off'}",
                    lambda: self._toggle_speed_keeper(1),
                    help="In low-speed zones where adaptive cruise is unavailable, "
                    "such as facility roads, gates, and work zones, automatic "
                    "speed control uses the keeper, then switches back to adaptive "
                    "cruise on open roads. Braking cancels the whole session.",
                ),
                MenuItem(
                    lambda: f"Controller: {'enabled' if s.controller_enabled else 'disabled'}",
                    lambda: self._toggle_controller(1),
                    help="Accept game-controller input alongside the keyboard. "
                    "The keyboard always stays active. The first connected "
                    "controller is used automatically.",
                ),
                MenuItem(
                    lambda: f"Haptics: {'enabled' if s.haptics_enabled else 'disabled'}",
                    lambda: self._toggle_haptics(1),
                    help="Rumble feedback on the controller for hazards, hard "
                    "braking, and the rumble strip. Has no effect without a "
                    "controller connected.",
                ),
                MenuItem("Back", self.go_back),
            ]
        if self.category == "audio":
            return [
                MenuItem(
                    lambda: f"Master volume: {round(s.master_volume * 100)} percent",
                    lambda: self._volume("master_volume", 0.1),
                    help="Overall game volume.",
                ),
                MenuItem(
                    lambda: f"Gameplay cues volume: {round(s.sfx_volume * 100)} percent",
                    lambda: self._volume("sfx_volume", 0.1),
                    help="Horn, alerts, road, facility, and gameplay cue sounds.",
                ),
                MenuItem(
                    lambda: f"Weather sounds volume: {round(s.weather_volume * 100)} percent",
                    lambda: self._volume("weather_volume", 0.1),
                    help="Rain, wind, thunder, snow, and fog sounds.",
                ),
                MenuItem(
                    lambda: f"Engine sounds volume: {round(s.engine_volume * 100)} percent",
                    lambda: self._volume("engine_volume", 0.1),
                    help="Engine start, shutdown, and running engine sounds.",
                ),
                MenuItem(
                    lambda: f"Music volume: {round(s.music_volume * 100)} percent",
                    lambda: self._volume("music_volume", 0.1),
                    help="Background music volume.",
                ),
                MenuItem(
                    lambda: f"Menu and UI sounds volume: {round(s.ui_volume * 100)} percent",
                    lambda: self._volume("ui_volume", 0.1),
                    help="Menu movement, selection, warning, and cash sounds.",
                ),
                MenuItem("Back", self.go_back),
            ]
        if self.category == "speech":
            items = [
                MenuItem(label, (lambda a=action: a(1)), help=help_text)
                for label, action, help_text in self._speech_control_specs()
            ]
            items.append(MenuItem("Back", self.go_back))
            return items
        if self.category == "online":
            from ..online_presence import OnlineIdentity

            return [
                MenuItem(
                    lambda: (
                        "orinks.net account: connected"
                        if OnlineIdentity.load() is not None
                        else "Set up orinks.net account"
                    ),
                    self._online_account_setup,
                    help="Connect the game to your orinks.net account without turning on Profile "
                    "sharing or Cloud backup.",
                ),
                MenuItem(
                    # The identity check lives INSIDE the label so it is
                    # fresh on every read: a captured build-time value went
                    # stale the moment setup completed (or the identity file
                    # changed on disk) and misreported "on" while dormant.
                    lambda: (
                        (
                            "Profile sharing: off requested"
                            if s.profile_sharing_pending_off
                            else f"Profile sharing: {'on' if s.online_presence else 'off'}"
                        )
                        if OnlineIdentity.load() is not None
                        else "Profile sharing: not set up"
                    ),
                    lambda: self._toggle_online_presence(1),
                    help="Profile sharing is one optional public setting for your driver profile, "
                    "official achievements, automatic road-journal posts, updates feed, "
                    "and on-duty board activity. Nothing is shared until you set it up: "
                    "Set up the orinks.net account first. Cloud saves remain private and separate.",
                ),
                MenuItem(
                    lambda: (
                        f"Back up saves to your orinks.net account: {'on' if s.cloud_saves else 'off'}"
                        if OnlineIdentity.load() is not None
                        else "Back up saves to your orinks.net account: not set up"
                    ),
                    lambda: self._toggle_cloud_saves(1),
                    help="After each game save, upload that career to your "
                    "own orinks.net account so you can restore it on another "
                    "computer. Backups are private to your account and never "
                    "appear as public downloads. Uses the same orinks.net account sign-in.",
                ),
                MenuItem(
                    "Restore a cloud backup",
                    self._cloud_backup_menu,
                    help="List the careers backed up to your orinks.net account "
                    "and bring one onto this computer.",
                ),
                MenuItem(
                    lambda: f"Discord presence: {'on' if s.discord_presence else 'off'}",
                    lambda: self._toggle_discord_presence(1),
                    help="Show broad activity in Discord, like the main menu, "
                    "driving a route, or resting. Only general game status "
                    "is shared, never your save files or personal details. "
                    "Has no effect if Discord is not running. Works without "
                    "a driver profile.",
                ),
                MenuItem("Back", self.go_back),
            ]
        if self.category == "reports":
            return [
                MenuItem(
                    "Where the game log is saved",
                    self._say_log_location,
                    help="The game keeps a log of the session, including "
                    "everything it said out loud. Sending it with a bug "
                    "report shows exactly what you heard.",
                ),
                MenuItem("Back", self.go_back),
            ]
        return [
            MenuItem(
                lambda: (
                    "Update channel: "
                    f"{'developer snapshots' if self._channel() == 'dev' else 'stable releases'}"
                ),
                lambda: self._toggle_update_channel(1),
                help="Choose stable releases or developer snapshots.",
            ),
            MenuItem(
                "Check for updates",
                self._check_updates,
                help="Look for a new version of the game right now.",
            ),
            MenuItem("Back", self.go_back),
        ]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT:
            self._adjust(1)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT:
            self._adjust(-1)
        else:
            super().handle_event(event)

    def adjust(self, direction: int) -> None:
        # D-pad left/right on a controller maps to the same per-item adjust.
        self._adjust(direction)

    def _adjust(self, direction: int) -> None:
        if self.category == "speech":
            actions = [action for _, action, _ in self._speech_control_specs()]
        else:
            actions = {
                "gameplay": [
                    self._toggle_units,
                    self._toggle_transmission,
                    self._cycle_automatic_direction_changes,
                    self._cycle_pace,
                    self._cycle_hos,
                    self._cycle_steering,
                    self._toggle_speed_keeper,
                    self._toggle_controller,
                    self._toggle_haptics,
                ],
                "audio": [
                    lambda d: self._volume("master_volume", 0.1 * d),
                    lambda d: self._volume("sfx_volume", 0.1 * d),
                    lambda d: self._volume("weather_volume", 0.1 * d),
                    lambda d: self._volume("engine_volume", 0.1 * d),
                    lambda d: self._volume("music_volume", 0.1 * d),
                    lambda d: self._volume("ui_volume", 0.1 * d),
                ],
                # Account setup and restore are actions, so left/right does
                # nothing on those rows instead of changing a nearby toggle.
                "online": [
                    lambda _d: None,
                    self._toggle_online_presence,
                    self._toggle_cloud_saves,
                    lambda _d: None,
                    self._toggle_discord_presence,
                ],
                "updates": [self._toggle_update_channel],
                # Reading the log's location is an action, not a value to
                # step through, so left/right does nothing on that row.
                "reports": [lambda _d: None],
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
            (
                lambda: f"Speech verbosity: {['terse', 'normal', 'chatty'][s.speech_verbosity]}",
                self._cycle_verbosity,
                "Controls how often driving status reminders speak.",
            ),
            (
                lambda: (
                    f"Menu position announcements: {'on' if s.announce_menu_position else 'off'}"
                ),
                self._toggle_menu_position,
                "When on, menus say the position, like 3 of 10, after each option. "
                "Turn off to hear only the option.",
            ),
            (
                lambda: f"Driving event voice: {self._event_voice_label()}",
                self._cycle_event_voice,
                "Speaks road events through the main voice or a separate SAPI or "
                "OneCore voice, so a screen reader cannot cut them off.",
            ),
        ]
        if speech.supports_rate:
            specs.append(
                (
                    lambda: f"Speech rate: {round(s.speech_rate * 100)} percent",
                    lambda d: self._adjust_speech("speech_rate", 0.1 * d),
                    "How fast the game's voice speaks, where the voice allows it.",
                )
            )
        if speech.supports_pitch:
            specs.append(
                (
                    lambda: f"Speech pitch: {round(s.speech_pitch * 100)} percent",
                    lambda d: self._adjust_speech("speech_pitch", 0.1 * d),
                    "How high or low the game's voice sounds.",
                )
            )
        if speech.supports_volume:
            specs.append(
                (
                    lambda: f"Speech volume: {round(s.speech_volume * 100)} percent",
                    lambda d: self._adjust_speech("speech_volume", 0.1 * d),
                    "Loudness of the game's voice, separate from sound volume.",
                )
            )
        if speech.voice_names():
            specs.append(
                (
                    lambda: f"Speech voice: {s.speech_voice or 'default'}",
                    self._cycle_voice,
                    "Which installed voice the game speaks with.",
                )
            )
        specs.append(
            (
                lambda: f"Weather source: {'real world' if s.real_weather else 'simulated'}",
                self._toggle_real_weather,
                "Real world uses live city conditions when available.",
            )
        )
        specs.append(
            (
                lambda: (
                    "Live weather controls calendar: "
                    f"{'on' if s.live_weather_controls_calendar else 'off'}"
                ),
                self._toggle_live_weather_calendar,
                "When on, live weather uses today's real date and season. When off, "
                "the career date advances at midnight and seasons pass while weather "
                "conditions still come from the real world.",
            )
        )
        return specs

    def _toggle_speed_keeper(self, _d: int = 1) -> None:
        self.ctx.settings.speed_keeper = not self.ctx.settings.speed_keeper
        self._announce()

    def _pace_label(self) -> str:
        scale = self.ctx.settings.time_scale
        return {10.0: "relaxed", 20.0: "standard", 40.0: "fast"}.get(scale, f"{scale:g} times")

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
        self.ctx.settings.automatic_transmission = not self.ctx.settings.automatic_transmission
        self._announce()

    def _cycle_automatic_direction_changes(self, d: int) -> None:
        modes = ["simple", "deliberate"]
        try:
            i = modes.index(self.ctx.settings.automatic_direction_changes)
        except ValueError:
            i = 0
        self.ctx.settings.automatic_direction_changes = modes[(i + d) % len(modes)]
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
        self.ctx.apply_volumes()
        self._announce()

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

    def _toggle_online_presence(self, _d: int) -> None:
        from ..online_presence import OnlineIdentity
        from .online_states import OnlineSetupState, ProfileSharingSyncState

        s = self.ctx.settings
        if OnlineIdentity.load() is None:
            # Not set up yet: the spoken disclosure and browser confirmation
            # happen in the setup state; it flips the setting on success.
            # The setting alone shares nothing without an identity.
            self.ctx.push_state(OnlineSetupState(self.ctx))
            return
        target = False if s.profile_sharing_pending_off else not s.online_presence
        self.ctx.push_state(ProfileSharingSyncState(self.ctx, target))

    def _toggle_cloud_saves(self, _d: int) -> None:
        from ..online_presence import OnlineIdentity
        from .cloud_save_states import CloudBackupConsentState

        s = self.ctx.settings
        if OnlineIdentity.load() is None:
            # Cloud backup rides the same account credentials as the board;
            # without them the setting would be inert, so point at the setup
            # item instead of flipping a switch that does nothing.
            self.ctx.say(
                "Cloud backup uses the same orinks.net sign-in as your driver "
                "profile. Choose Set up orinks.net account on this menu first, "
                "then turn cloud backup on.",
                interrupt=True,
            )
            return
        if not s.cloud_saves:
            self.ctx.push_state(CloudBackupConsentState(self.ctx))
            return
        s.cloud_saves = False
        s.save()
        self.ctx.apply_cloud_saves()
        self._announce()

    def _online_account_setup(self) -> None:
        from .online_states import OnlineSetupState

        self.ctx.push_state(OnlineSetupState(self.ctx))

    def _cloud_backup_menu(self) -> None:
        from .cloud_save_states import CloudBackupState

        self.ctx.push_state(CloudBackupState(self.ctx))

    def _toggle_controller(self, _d: int) -> None:
        self.ctx.settings.controller_enabled = not self.ctx.settings.controller_enabled
        self.ctx.apply_controller()
        self._announce()

    def _toggle_haptics(self, _d: int) -> None:
        self.ctx.settings.haptics_enabled = not self.ctx.settings.haptics_enabled
        self.ctx.apply_haptics()
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

    def _toggle_live_weather_calendar(self, _d: int) -> None:
        turning_off = self.ctx.settings.live_weather_controls_calendar
        self.ctx.settings.live_weather_controls_calendar = (
            not self.ctx.settings.live_weather_controls_calendar
        )
        profile = self.ctx.profile
        if turning_off and profile is not None and profile.has_started_career():
            from ..sim.season import real_clock_game_hours

            profile.anchor_calendar_to(real_clock_game_hours())
            profile.save()
        self._announce()

    def _channel(self) -> str:
        return updater.resolve_channel(
            self.ctx.settings.update_channel, updater.load_build_info(__version__)
        )

    def _toggle_update_channel(self, _d: int) -> None:
        self.ctx.settings.update_channel = "stable" if self._channel() == "dev" else "dev"
        self._announce()

    def _check_updates(self) -> None:
        self.ctx.push_state(UpdateCheckState(self.ctx))

    def _log_location_lines(self) -> list[str]:
        """Where this session's log is, in words a player can act on.

        The log already records every spoken line, so it is the most useful
        thing a player can attach to a bug report -- but nothing in the game
        ever mentioned it, so nobody sent one. Read from the path logging
        actually opened, so a folder the game could not write to reports
        honestly instead of naming a file that is not there.
        """
        from ..app import active_log_path

        path = active_log_path()
        if path is None:
            return [
                "This copy of the game is not writing a log file. Packaged "
                "downloads always write one; a copy run from the source code "
                "prints to its console window instead."
            ]
        out = [
            f"The game log is saved as {path}.",
            "It records this session, including everything the game said out loud, "
            "so attaching it to a bug report shows exactly what you heard.",
        ]
        previous = path.with_name(f"{path.stem}.prev{path.suffix}")
        if previous.exists():
            out.append(
                f"The session before this one was kept beside it as {previous.name}, "
                "so restarting the game to check something does not lose it."
            )
        out.append(
            "Both files stay on this computer. The game never sends them anywhere, "
            "so attach one yourself when you report a problem."
        )
        return out

    def _say_log_location(self) -> None:
        self.ctx.say(" ".join(self._log_location_lines()))

    def lines(self) -> list[str]:
        # Spoken-only information would be invisible to a low-vision player
        # reading the window, so the log's location is mirrored on screen.
        out = super().lines()
        if self.category == "reports":
            out += ["", *self._log_location_lines()]
        return out

    def go_back(self) -> None:
        # Settings are saved as each change is made; just return to the
        # category list (the top-level picker says "Settings saved" on exit).
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
