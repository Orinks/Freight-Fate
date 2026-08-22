"""Main menu, profile selection, name entry, settings, and help screens."""

from __future__ import annotations

import contextlib
from datetime import datetime
from pathlib import Path

import pygame

from .. import __version__, updater
from ..achievements import (
    ACHIEVEMENTS,
    achievements_in_category,
    categories,
    earned_ids,
    entry_text,
)
from ..models.profile import LegacyCareerError, Profile, ProfileIntegrityError
from ..models.start_options import apply_start_option, option_for_profile
from ..music import select_menu_music_sequence
from ..playtest_levers import apply_continue_levers
from ..settings import (
    DRIVING_ASSIST_FIELDS,
    DRIVING_ASSIST_PRESETS,
    DRIVING_SPEECH_MODES,
    LANE_KEEPING_MODES,
    LANE_KEEPING_TO_LEGACY,
    PLACE_CALLOUT_MODES,
    TIME_SCALES,
)
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
from .text_entry import TextEntryState
from .update import UpdateChecker, UpdateCheckState, UpdatePromptState

_last_invalid_saves: list[Path] = []
# Careers the load gate refused because they were created before the 1.9
# line. They must stay visible in the career list with a spoken label -- a
# missing career reads as data loss to a blind player -- so _loadable_saves
# collects them here for the menus to show alongside the loadable ones.
_legacy_saves: list[LegacyCareerError] = []

# Reused within a single _reuse_loadable_saves_scan() block (see below) so a
# state that asks several times in one pass -- MainMenuState.enter() calls
# _loadable_saves() three times: build_items, announce_entry's legacy-save
# check, and its own profile lookup -- pays for one save-directory scan
# instead of three. Outside such a block every call still rescans, so a
# state that lists saves after creating or deleting one never sees stale
# results.
_loadable_saves_cache: list[tuple[Path, Profile]] | None = None
_loadable_saves_cache_active = False


@contextlib.contextmanager
def _reuse_loadable_saves_scan():
    """Coalesce every _loadable_saves() call made inside this block.

    Reentrant: a nested call is a no-op, so this can wrap a method that also
    wraps itself (or calls another wrapped method) without the inner scope
    prematurely dropping the cache the outer scope is still relying on.
    """
    global _loadable_saves_cache_active, _loadable_saves_cache
    already_active = _loadable_saves_cache_active
    _loadable_saves_cache_active = True
    if not already_active:
        _loadable_saves_cache = None
    try:
        yield
    finally:
        if not already_active:
            _loadable_saves_cache_active = False
            _loadable_saves_cache = None


def pending_notice_state(ctx) -> State | None:
    """The next one-time save notice the player has not heard yet, if any."""
    if ctx.profile.migration_notice_pending:
        from .save_notice import SaveMigrationNoticeState

        return SaveMigrationNoticeState(ctx)
    if ctx.profile.integrity_notice_pending:
        from .save_notice import SaveModifiedNoticeState

        return SaveModifiedNoticeState(ctx)
    if ctx.profile.driving_record.notice_pending:
        from .save_notice import DrivingRecordNoticeState

        return DrivingRecordNoticeState(ctx)
    return None


def _first_state_after_career_creation(ctx) -> State:
    """The city menu, or the one-time orinks.net offer ahead of it."""
    from .city import CityMenuState
    from .online_offer import OnlineOfferState, should_offer_online

    if should_offer_online(ctx):
        return OnlineOfferState(ctx)
    # The welcome is spoken just before this state is pushed, so its entry
    # announcement queues behind it rather than cutting it off.
    return CityMenuState(ctx, queue_entry_announcement=True)


def enter_world(ctx, *, queue_entry_announcement: bool = False) -> None:
    """Resume a saved mid-trip delivery if there is one, else the terminal hub.

    ``queue_entry_announcement`` reaches the city menu only -- see
    ``_world_entry_state``. A resumed drive already queues its own entry lines
    (``DrivingState.enter`` always speaks with ``interrupt=False``), and a
    pending save notice is a separate, unrelated screen, so neither needs the
    flag threaded through.
    """
    ctx.push_state(
        pending_notice_state(ctx)
        or _world_entry_state(ctx, queue_entry_announcement=queue_entry_announcement)
    )


def _world_entry_state(ctx, *, queue_entry_announcement: bool = False) -> State:
    """Build the first playable state for the current profile."""
    from .city import CityMenuState, PickupFacilityState
    from .driving import DrivingState

    p = ctx.profile
    if p.active_trip:
        # A save from before local city-service drives were retired can still
        # carry one mid-trip. There is no route or phase left to resume it
        # with, so it drops the driver at the terminal instead of failing to
        # load -- this branch reads only that old snapshot shape and stays
        # even after every other city-service-drive code path is gone.
        if p.active_trip.get("kind") == "city_service_drive":
            p.active_trip = None
            ctx.save_profile()
            ctx.say(
                "Local service drives were retired in this update; you are parked at the terminal."
            )
            return CityMenuState(ctx, queue_entry_announcement=True)
        if p.active_trip.get("kind") == "pickup":
            state = PickupFacilityState.from_snapshot(ctx, p.active_trip)
        else:
            state = DrivingState.from_snapshot(ctx, p.active_trip)
        if state is not None:
            return state
        p.active_trip = None  # unreadable snapshot; do not retry every load
    # The welcome that names this driver (from Continue or Choose career) is
    # spoken just before this state is chosen, so its entry announcement
    # queues behind that line instead of cutting it off.
    return CityMenuState(ctx, queue_entry_announcement=queue_entry_announcement)


def _loadable_saves() -> list[tuple[Path, Profile]]:
    """Return readable saves in newest-first order.

    Inside a :func:`_reuse_loadable_saves_scan` block, the first real scan's
    result (and the ``_last_invalid_saves``/``_legacy_saves`` it populates)
    is reused for the rest of the block instead of rescanning the save
    directory again.
    """
    global _last_invalid_saves, _legacy_saves, _loadable_saves_cache
    if _loadable_saves_cache_active and _loadable_saves_cache is not None:
        return _loadable_saves_cache
    _last_invalid_saves = []
    _legacy_saves = []
    saves = []
    for path in Profile.list_saves():
        try:
            profile = Profile.load(path)
        except LegacyCareerError as legacy:
            _legacy_saves.append(legacy)
        except ProfileIntegrityError:
            _last_invalid_saves.append(path)
        except Exception:
            continue
        else:
            # Loading may have converted a legacy file in place; report the
            # path the career actually lives at now.
            saves.append((profile.path, profile))
    if _loadable_saves_cache_active:
        _loadable_saves_cache = saves
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

    @classmethod
    def arm_update_check(cls, settings) -> None:
        """Start a fresh silent check for the next main-menu update cycle."""
        if not updater.is_frozen():
            return
        cls._update_checker = UpdateChecker(settings)
        cls._update_prompted = False

    def enter(self) -> None:
        with _reuse_loadable_saves_scan():
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
        if self.ctx.settings.lane_keeping_unreadable:
            # Falling back to full lane keeping is the right answer and a
            # silent one is not: it deletes the destination-exit decision
            # outright, and nothing later in the drive would explain why.
            self.ctx.settings.lane_keeping_unreadable = False
            warning += (
                "Your lane keeping setting could not be read, so it is set to "
                "full: the truck holds the lane and takes your exits. Change it "
                "in Settings, Gameplay, Driving assistance. "
            )
        if not _loadable_saves() and _legacy_saves:
            # Every saved career predates 1.9, so there is no Continue item
            # where the player expects one. Say where the careers went before
            # that silence reads as data loss; once a 1.9 career exists, the
            # labels in Choose career carry the explanation instead.
            warning += (
                "Your saved careers are from an earlier version of Freight "
                "Fate; they are listed under Choose career. "
            )
        self.ctx.say(
            f"Welcome to Freight Fate, version {updater.spoken_version(__version__)}. "
            f"An audio trucking adventure across America. {warning}".rstrip()
        )
        self.ctx.say(self.current_text(), interrupt=False, review=False)

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
        if saves or _legacy_saves:
            # Careers from earlier versions cannot continue, but they still
            # belong on the list: even with nothing loadable, Choose career is
            # where a player finds them and hears what happened.
            items.append(
                MenuItem(
                    "Choose career",
                    self._load_menu,
                    help="Choose any saved career instead of only the newest one.",
                )
            )
        if saves:
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
                "Online",
                self._online_hub,
                help="The public drivers board, your orinks.net account, "
                "cloud backup and restore, and sharing choices like "
                "Mastodon and Discord, all in one place.",
            )
        )
        items.append(
            MenuItem("How to play", self._help, help="Learn the controls and the goal of the game.")
        )
        items.append(
            MenuItem(
                "Learn game sounds",
                self._learn_sounds,
                help="Play any sound the road uses and hear what it means, "
                "before you meet it at speed.",
            )
        )
        items.append(
            MenuItem(
                "Settings",
                self._settings,
                help="Units, transmission mode, volumes, weather, voices, "
                "update channel, and trip pacing.",
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
        self.ctx.push_state(ConfirmQuitState(self.ctx))

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
        lever_notes = apply_continue_levers(self.ctx)
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
        # This welcome is spoken first; a resumed drive already queues its own
        # lines, and only the plain city-menu hand-off needs telling not to
        # cut it off (see _world_entry_state).
        enter_world(self.ctx, queue_entry_announcement=True)
        for note in lever_notes:
            self.ctx.say(note, interrupt=False)

    def _load_menu(self) -> None:
        self.ctx.push_state(LoadDriverState(self.ctx))

    def _manage_careers(self) -> None:
        self.ctx.push_state(ManageCareersState(self.ctx))

    def _new_game(self) -> None:
        self.ctx.push_state(NameEntryState(self.ctx))

    def _help(self) -> None:
        self.ctx.push_state(HelpState(self.ctx))

    def _learn_sounds(self) -> None:
        from .learn_sounds import LearnSoundsState

        self.ctx.push_state(LearnSoundsState(self.ctx))

    def _achievements(self) -> None:
        self.ctx.push_state(AchievementCareerState(self.ctx))

    def _settings(self) -> None:
        self.ctx.push_state(SettingsState(self.ctx))

    def _online_hub(self) -> None:
        from .online_hub import OnlineHubState

        self.ctx.push_state(OnlineHubState(self.ctx))

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


class ConfirmQuitState(MenuState):
    """One spoken yes/no gate before Escape at the main menu exits the game."""

    title = "Quit Freight Fate?"
    open_sound_key = "ui/error"

    def announce_entry(self) -> None:
        self.ctx.say(f"Quit Freight Fate? {self.current_text()}", review=False)

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem("No, stay in Freight Fate", self.go_back),
            MenuItem("Yes, quit Freight Fate", self._yes),
        ]

    def _yes(self) -> None:
        self.ctx.quit()


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
    """The category menu: pick a category, then browse its achievements."""

    intro_help = (
        "Use up and down arrows to choose a category. Enter opens it "
        "and lists its achievements. Escape goes back."
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
            "Enter a category to browse it. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        earned = earned_ids(self.profile)
        items = [
            MenuItem(
                self._summary_label, self._summary, help="Hear the total earned achievement count."
            )
        ]
        for category in categories():
            achs = achievements_in_category(category.id)
            done = sum(1 for a in achs if a.id in earned)
            items.append(
                MenuItem(
                    f"{category.title}. {done} of {len(achs)}",
                    lambda c=category, a=achs: self._open_category(c, a),
                    help=category.description,
                )
            )
        items.append(MenuItem("Back", self.go_back))
        return items

    def _open_category(self, category, achs) -> None:
        self.ctx.push_state(AchievementCategoryState(self.ctx, self.profile, category, achs))

    def _summary_label(self) -> str:
        earned = len(earned_ids(self.profile))
        total = len(ACHIEVEMENTS)
        return f"Summary: {earned} of {total} earned"

    def _summary(self) -> None:
        earned = len(earned_ids(self.profile))
        total = len(ACHIEVEMENTS)
        self.ctx.say(f"{self.profile.name} has earned {earned} of {total} achievements.")


class AchievementCategoryState(MenuState):
    """One category's achievements: earned ones tell their story, locked
    ones show their goal, and hidden ones keep the secret until earned.
    """

    intro_help = (
        "Use up and down arrows to review this category's achievements. "
        "Enter repeats the selected entry. Escape goes back to the "
        "category list."
    )

    def __init__(self, ctx, profile: Profile, category, achs) -> None:
        super().__init__(ctx)
        self.profile = profile
        self.category = category
        self.achs = achs

    @property
    def title(self) -> str:  # type: ignore[override]
        return self.category.title

    def _earned_count(self) -> int:
        earned = earned_ids(self.profile)
        return sum(1 for a in self.achs if a.id in earned)

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.category.title}. {self._earned_count()} of {len(self.achs)} earned. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        earned = earned_ids(self.profile)
        items = []
        for achievement in self.achs:
            unlocked = achievement.id in earned
            name, description = entry_text(achievement, unlocked)
            if unlocked:
                label = f"Earned: {name} - {description}"
                help_text = description
            elif achievement.hidden:
                label = f"Locked: {name}"
                help_text = description
            else:
                # Locked, non-hidden entries show only the title; the
                # description stays hidden until the achievement is earned.
                label = f"Locked: {name}"
                help_text = "Keep playing to unlock it."
            items.append(MenuItem(label, lambda text=label: self.ctx.say(text), help=help_text))
        items.append(MenuItem("Back to the categories", self.go_back))
        return items


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
        # Careers the 1.9 load gate refused stay on the list with a spoken
        # label -- silently dropping them reads as data loss. Picking one
        # opens the notice that explains and offers a fresh start.
        for legacy in _legacy_saves:
            items.append(
                MenuItem(
                    f"{legacy.name}: career from an earlier version of Freight Fate",
                    lambda e=legacy: self._explain_legacy(e),
                    help="This career cannot continue in version 1.9. Enter "
                    "explains why and offers a new career; the save itself "
                    "is not touched.",
                )
            )
        items.append(MenuItem("Back", self.go_back))
        return items

    def _explain_legacy(self, legacy: LegacyCareerError) -> None:
        from .save_notice import LegacyCareerNoticeState

        self.ctx.push_state(LegacyCareerNoticeState(self.ctx, legacy.name))

    def _pick(self, profile: Profile) -> None:
        self.ctx.profile = profile
        lever_notes = apply_continue_levers(self.ctx)
        self.ctx.say(f"Welcome back, {profile.name}.")
        # The welcome above must be heard in full before the city menu's own
        # "Parked at..." announcement -- see _world_entry_state.
        self.ctx.replace_state(
            pending_notice_state(self.ctx)
            or _world_entry_state(self.ctx, queue_entry_announcement=True)
        )
        for note in lever_notes:
            self.ctx.say(note, interrupt=False)


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
            f"Actions for {_career_summary(self.path, self.profile)}. {self.current_text()}",
            interrupt=False,
            review=False,
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
            f"Confirm {self._action_label} for {self.profile.name}. {detail} {self.current_text()}",
            review=False,
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
            apply_start_option(fresh, option_for_profile(self.profile))
            fresh.save()
            message = (
                f"{name} reset. The career starts over at "
                f"{self.ctx.world.spoken_city(fresh.current_city)} "
                f"with {fresh.carrier_name} "
                f"and {fresh.money:,.0f} dollars."
            )
        else:
            self.path.unlink(missing_ok=True)
            if self.ctx.profile is not None and self.ctx.profile.path == self.path:
                self.ctx.profile = None
            message = f"{name} deleted."
        self.ctx.reset_to(MainMenuState(self.ctx))
        self.ctx.say(message, interrupt=True)


class NameEntryState(TextEntryState):
    """New-career driver name entry on the shared accessible text field."""

    MAX_LEN = 24
    heading = "New career"
    field_label = "Driver name"

    def enter(self) -> None:
        self.ctx.say(
            "New career. Type your driver name, then press Enter. "
            "Left and right arrows review the letters you have typed, "
            "Home and End jump to the start or end. Press Escape to cancel."
        )

    def _confirm(self) -> None:
        name = self.name.strip() or "Driver"
        self.ctx.audio.play("ui/menu_select")
        self.ctx.push_state(CareerStartState(self.ctx, name))


from .main_menu_career import (  # noqa: E402,F401
    CareerStartState,
    HomeCityState,
    HomeTerminalState,
    _region_menu_name,
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

    # Gameplay is now a category with its own submenu (Driving assistance,
    # Difficulty and hours of service, World and traffic, and Controls) rather
    # than a flat list -- it opens GameplaySettingsState. The rest are plain
    # category lists.
    CATEGORIES = (
        ("Gameplay", "gameplay"),
        ("Audio", "audio"),
        ("Speech", "speech"),
        ("Updates", "updates"),
        ("Problem reports", "reports"),
    )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(label, lambda key=key: self._open(key), help=f"Open {label.lower()} settings.")
            for label, key in self.CATEGORIES
        ]
        # The Online items moved to the main menu; this stays in the old spot
        # (after Speech) for a release or two so muscle memory still lands
        # somewhere useful.
        items.insert(
            3,
            MenuItem(
                "Online",
                self._open_online_hub,
                help="Online options have moved to the Online menu on the "
                "main menu. This opens that menu.",
            ),
        )
        items.append(MenuItem("Back", self.go_back))
        return items

    def _open(self, category: str) -> None:
        if category == "gameplay":
            self.ctx.push_state(GameplaySettingsState(self.ctx))
            return
        self.ctx.push_state(SettingsCategoryState(self.ctx, category))

    def _open_online_hub(self) -> None:
        from .online_hub import OnlineHubState

        self.ctx.push_state(OnlineHubState(self.ctx))

    def go_back(self) -> None:
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_back")
        # Popping first lets the revealed menu's own entry announcement play,
        # then "Settings saved." interrupts and wins -- said after the pop,
        # not before it, so it is not the one left cancelled by the other.
        self.ctx.pop_state()
        self.ctx.say("Settings saved.", interrupt=True)


# Spoken once to a player whose settings predate a layout, the first time they
# open the Gameplay submenu, one entry per settings layout version they missed.
# A blind player cannot see a menu change shape, so the words carry the whole
# change -- and the reassurance that nothing about their actual settings moved,
# which is true by construction: every move keeps the saved key it always had.
SETTINGS_LAYOUT_NOTICES = {
    1: (
        "Gameplay is now a category with its own submenu: Driving assistance, "
        "Difficulty and hours of service, World and traffic, and Controls. "
        "Weather, traffic, and parking sources moved into World and traffic, "
        "from what used to be Speech and weather. Nothing about your settings "
        "changed; this is just where to find them now."
    ),
    2: (
        "Two rows moved. Speed keeper is now in Driving assistance, with the "
        "rest of the driving help, instead of Controls. Lane and edge cue "
        "prominence is now called Lane and edge cue volume and lives in Audio, "
        "right under Gameplay cues volume, because that is the volume it "
        "layers on. Your choices came with them. Overspeed warning no longer "
        "has a row at all: it used to chime at the speed cruise itself holds, "
        "and now it stays quiet until you are genuinely heading for a ticket."
    ),
    3: (
        "Speech verbosity is now called Driving speech, in the Speech "
        "category, and it has two more steps than before. What used to be "
        "normal is now called standard, and what used to be terse is now "
        "called quiet -- your choice came with you. Standard and quiet both "
        "still speak every safety call, route instruction, and money "
        "consequence; quiet only trades confirmations and status updates for "
        "short sounds instead of words. A third choice sits below them: "
        "urgent only, which speaks the safety calls, what things cost, and "
        "the directions you cannot take back -- the turn itself, the exit, "
        "the stop you are pulling into -- while a heads-up about a bend or a "
        "town coming up becomes a short sound."
    ),
}


class GameplaySettingsState(MenuState):
    """The Gameplay parent: a submenu of submenus.

    Gameplay used to be one flat list long enough to lose things in. It is now
    a category that opens four smaller lists, each its own spoken screen, using
    the same per-category machinery as every other settings screen.
    """

    title = "Gameplay"
    intro_help = (
        "Gameplay settings are grouped into four screens. Use up and down "
        "arrows to pick one, Enter to open it, and Escape to go back. Each "
        "screen opens its own list of settings."
    )

    SUBCATEGORIES = (
        ("Driving assistance", "assistance"),
        ("Difficulty and hours of service", "difficulty"),
        ("World and traffic", "world"),
        ("Controls", "controls"),
    )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(label, lambda key=key: self._open(key), help=f"Open {label.lower()} settings.")
            for label, key in self.SUBCATEGORIES
        ]
        items.append(MenuItem("Back", self.go_back))
        return items

    def announce_entry(self) -> None:
        super().announce_entry()
        s = self.ctx.settings
        if s.settings_layout_notice_from >= 0:
            # Said once and only to a player whose settings moved under them,
            # oldest layout first so two moves arrive in the order they
            # happened. Queued behind the menu's own entry line rather than
            # interrupting it, and cleared to disk immediately so a mid-notice
            # quit does not replay it forever -- but a player who never reaches
            # this screen keeps the flag, and hears it whenever they arrive.
            owed = [
                text
                for version, text in sorted(SETTINGS_LAYOUT_NOTICES.items())
                if version > s.settings_layout_notice_from
            ]
            s.settings_layout_notice_from = -1
            s.save()
            for text in owed:
                self.ctx.say(text, interrupt=False, review=False)

    def _open(self, category: str) -> None:
        self.ctx.push_state(SettingsCategoryState(self.ctx, category))

    def go_back(self) -> None:
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_back")
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
        "assistance": "Driving assistance",
        "difficulty": "Difficulty and hours of service",
        "world": "World and traffic",
        "controls": "Controls",
        "audio": "Audio",
        "speech": "Speech",
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
        if self.category == "assistance":
            items = [
                MenuItem(
                    lambda: f"Driving assistance preset: {self._assist_preset_label()}",
                    lambda: self._cycle_assist_preset(1),
                    help="Realistic provides modern truck safety support. Balanced adds partial lane keeping, a firmer hand on descents, and stopping at your destination. All assists enables every available driving assist and sets lane keeping to full, so the truck holds the lane, a tap changes lanes, and your destination exit is taken for you. Changing an individual assist makes this Custom. You still choose routes, and handle yards and docks. Presets do not change trip pacing, hours rules, transmission, weather, or hazards.",
                )
            ]
            items.extend(
                MenuItem(
                    lambda field=field, label=label: (
                        f"{label}: "
                        + (
                            self._descent_level_label()
                            if field == "descent_speed_control"
                            else s.pedal_latch
                            if field == "pedal_latch"
                            else ("on" if getattr(s, field) else "off")
                        )
                    ),
                    lambda field=field: self._toggle_driving_assist(field),
                    help=help_text,
                )
                for field, label, help_text in self._driving_assist_specs()
            )
            items.append(
                MenuItem(
                    lambda: f"Lane keeping: {self._lane_keeping_label()}",
                    lambda: self._cycle_lane_keeping(1),
                    help="Formerly Lane drift. How much of the lane-holding "
                    "work the truck does. Full holds the lane for you, turns "
                    "Left and Right into tap lane changes, and takes your "
                    "exits, including the destination exit, without a signal. "
                    "Partial drifts gently with generous steering help; off "
                    "drifts like a real wheel and every exit needs its signal "
                    "and its exit lane. On partial or off the road sound "
                    "leans toward where the wheel should go -- follow it into "
                    "a bend and back to lane center -- and the road edge "
                    "answers with real textures: a stutter clipping the "
                    "rumble strip, a buzz fully on it, gravel off the "
                    "pavement. Realistic sets this to off, Balanced to "
                    "partial, All assists to full.",
                )
            )
            items.append(
                MenuItem(
                    lambda: f"Following gap: {self._acc_gap_label()}",
                    lambda: self._cycle_acc_gap(1),
                    help="How much room adaptive cruise leaves to the vehicle "
                    "ahead when it is following traffic. Close is two and a "
                    "half seconds, normal three, far three and a half. Bad "
                    "weather still opens the gap further whichever you pick, "
                    "so close never means close on ice. All three leave you "
                    "well clear of a following-too-close citation. This is "
                    "your preference rather than a difficulty, so the "
                    "assistance preset above does not change it.",
                )
            )
            # Lane and edge cue volume moved to Audio, next to the Gameplay
            # cues volume it scales. It is a volume, and a second volume
            # control hiding in the assists list is how it came to be a row
            # nobody could explain.
            items.append(MenuItem("Back", self.go_back))
            return items
        if self.category == "difficulty":
            return [
                MenuItem(
                    lambda: f"Driving mode: {self._pace_label()}",
                    lambda: self._cycle_pace(1),
                    help="Driving mode controls pacing and pressure. Relaxed "
                    "gives wider hazard response windows, gentler "
                    "collision damage and fatigue, calmer speech, and the most "
                    "time to respond. Standard keeps balanced pressure and moves "
                    "the clock twice as fast, so a driving day takes half as long "
                    "and decisions arrive sooner. Real time keeps Standard's "
                    "pressure and runs the driving clock at the speed of a real "
                    "clock, so a mile takes as long as it really would. With the "
                    "weather source set to real world it is the most true to "
                    "life the game gets. You can change it mid-drive from the "
                    "pause menu.",
                ),
                MenuItem(
                    lambda: f"Hours of service: {self._hos_label()}",
                    lambda: self._cycle_hos(1),
                    help="Realistic enforces full hours rules and normal "
                    "road hazards. Relaxed eases the hours limits and "
                    "makes road hazards rare, so you can focus on "
                    "driver responsibility: hours, fueling, and repairs.",
                ),
                # The overspeed warning no longer has a row. It armed at the
                # same 5-over pace predictive cruise itself holds, so it
                # chimed at drivers for a speed the truck picked, and the
                # setting existed to switch that off. It now arms above
                # cruise's pace and below the enforcement leeway, which
                # leaves nothing worth turning off.
                MenuItem("Back", self.go_back),
            ]
        if self.category == "world":
            return [
                MenuItem(
                    lambda: f"Weather source: {'real world' if s.real_weather else 'simulated'}",
                    lambda: self._toggle_real_weather(1),
                    help="Real world uses live city conditions when available.",
                ),
                MenuItem(
                    lambda: f"Traffic source: {'real time' if s.real_traffic else 'simulated'}",
                    lambda: self._toggle_real_traffic(1),
                    help="Real time uses live traffic incidents from state 511 "
                    "APIs when available.",
                ),
                MenuItem(
                    lambda: f"Parking source: {'real time' if s.real_parking else 'simulated'}",
                    lambda: self._toggle_real_parking(1),
                    help="Real time uses live truck parking availability from "
                    "TPIMS APIs when available.",
                ),
                MenuItem(
                    lambda: (
                        "Live weather controls calendar: "
                        f"{'on' if s.live_weather_controls_calendar else 'off'}"
                    ),
                    lambda: self._toggle_live_weather_calendar(1),
                    help="When on, live weather uses today's real date and "
                    "season. When off, the career date advances at midnight and "
                    "seasons pass while weather conditions still come from the "
                    "real world.",
                ),
                MenuItem("Back", self.go_back),
            ]
        if self.category == "controls":
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
                    help="Both styles change direction with a fresh press at a "
                    "standstill; a brake held through a stop just holds the "
                    "truck. Deliberate requires the release-and-press gesture "
                    "everywhere. This only affects automatic transmission.",
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
                    "braking, the rumble strip, and road seams. Has no effect "
                    "without a controller connected.",
                ),
                # The speed keeper moved to Driving assistance: it holds a speed
                # for you, which is what every other row on that screen does.
                # Controls is the keyboard, the controller, and the units the
                # numbers arrive in.
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
                    lambda: f"Lane and edge cue volume: {self._cue_loudness_label()}",
                    lambda: self._cycle_cue_loudness(1),
                    help="How loud the road cues are when you leave your line, "
                    "next to everything else: the rumble-strip and shoulder "
                    "textures, the lane locator you turn on with I while "
                    "driving, and the warning bars before a hairpin. It rides "
                    "on the Gameplay cues volume above rather than replacing "
                    "it, so this row moves those cues alone. Quieter keeps "
                    "them under the engine, standard matches it, and louder "
                    "cuts through for drivers who want no doubt about which "
                    "edge they are on.",
                ),
                MenuItem(
                    lambda: f"Lane guide sound: {'tone' if s.lane_guide_tone else 'road noise'}",
                    self._toggle_lane_guide_tone,
                    help="What leans toward the side you are drifting to. "
                    "Road noise is the road you are already hearing, which "
                    "moves toward the side you need to steer and goes quiet "
                    "when you are straight -- nothing is added to the cab. "
                    "Tone plays a soft note instead, for the same length of "
                    "time and panned the same way. It is there because on "
                    "some setups the road is too quiet under the engine to "
                    "tell which side it went to. Road noise is the default "
                    "and the one most drivers should stay on: a note held in "
                    "your ear is tiring over a long haul and can crowd out "
                    "the rest of what the cab is telling you.",
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
                    lambda: f"Engine voice: {s.engine_voice}",
                    lambda: self._toggle_engine_voice(1),
                    help=(
                        "Real plays the engine recorded from a working truck cab, "
                        "following the rpm through its range. Classic keeps the "
                        "original engine sound. Changes apply immediately, even "
                        "while driving."
                    ),
                ),
                MenuItem(
                    lambda: (
                        f"Engine brake voice: {'recorded' if s.jake_voice == 'real' else 'classic'}"
                    ),
                    lambda: self._toggle_jake_voice(1),
                    help=(
                        "Recorded is the real engine brake growl the road plays "
                        "today -- drivers call it the jake. Classic is the "
                        "synthesized growl from earlier versions. Changes apply "
                        "immediately, even while driving."
                    ),
                ),
                MenuItem(
                    lambda: f"Music volume: {round(s.music_volume * 100)} percent",
                    lambda: self._volume("music_volume", 0.1),
                    help="Menu and facility background music volume.",
                ),
                MenuItem(
                    lambda: f"In-cab radio volume: {round(s.radio_volume * 100)} percent",
                    lambda: self._volume("radio_volume", 0.1),
                    help="Music volume while driving. Kept lower by default so speech, engine, and safety cues stay clear.",
                ),
                MenuItem(
                    lambda: f"Radio streamer-safe mode: {'on' if s.radio_streamer_safe else 'off'}",
                    lambda: self._toggle_radio_streamer_safe(1),
                    help="Off plays the full dial, including real public streams and "
                    "personal playlists. Turn it on while streaming or recording to "
                    "keep the radio on built-in safe stations only.",
                ),
                MenuItem(
                    lambda: (
                        "Game sounds step back for speech: "
                        f"{'on' if s.duck_audio_for_speech else 'off'}"
                    ),
                    lambda: self._toggle_duck_for_speech(1),
                    help="While the road voice speaks, the engine, weather, and "
                    "radio drop to half volume, then come back. Warnings stay "
                    "easy to hear in a loud cab without the voice getting louder.",
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
                "difficulty": [
                    self._cycle_pace,
                    self._cycle_hos,
                ],
                "world": [
                    self._toggle_real_weather,
                    self._toggle_real_traffic,
                    self._toggle_real_parking,
                    self._toggle_live_weather_calendar,
                ],
                "controls": [
                    self._toggle_units,
                    self._toggle_transmission,
                    self._cycle_automatic_direction_changes,
                    self._toggle_controller,
                    self._toggle_haptics,
                ],
                "assistance": [
                    self._cycle_assist_preset,
                    *[
                        (lambda d, field=field: self._toggle_driving_assist(field, d))
                        for field, _, _ in self._driving_assist_specs()
                    ],
                    # The last row of this category was left out of the
                    # arrow-key path, so Left and Right did nothing on it
                    # while every other row answered. Every row added here
                    # after Lane keeping must be appended below it, in the
                    # same order build_items appends them.
                    self._cycle_lane_keeping,
                    self._cycle_acc_gap,
                ],
                "audio": [
                    lambda d: self._volume("master_volume", 0.1 * d),
                    lambda d: self._volume("sfx_volume", 0.1 * d),
                    self._cycle_cue_loudness,
                    self._toggle_lane_guide_tone,
                    lambda d: self._volume("weather_volume", 0.1 * d),
                    lambda d: self._volume("engine_volume", 0.1 * d),
                    self._toggle_engine_voice,
                    self._toggle_jake_voice,
                    lambda d: self._volume("music_volume", 0.1 * d),
                    lambda d: self._volume("radio_volume", 0.1 * d),
                    self._toggle_radio_streamer_safe,
                    self._toggle_duck_for_speech,
                    lambda d: self._volume("ui_volume", 0.1 * d),
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
                lambda: f"Driving speech: {s.driving_speech.replace('_', ' ')}",
                self._cycle_driving_speech,
                "How much the road tells you. Standard speaks every "
                "confirmation and status update in words, a driving tip "
                "once per leg, and a status readout when it changes; quiet "
                "cuts confirmations and status to short sounds; and urgent "
                "only also turns the heads-up about a bend or a town coming "
                "up into a short sound, keeping the safety calls, what "
                "things cost, and the turn itself. Billboards, place "
                "names and landmarks are not part of this -- they have "
                "their own switches below.",
            ),
            (
                lambda: f"Roadside chatter: {s.chatter_summary()}",
                self._set_all_chatter,
                "The ambient color spoken between navigation cues: parks, "
                "rivers, mountain passes, museums, and billboards. Right "
                "arrow turns everything on, Left arrow turns everything "
                "off, and the switches below fine-tune each kind. Safety "
                "and navigation announcements are never affected, and town "
                "names have their own Place callouts setting below.",
            ),
            (
                lambda: f"Speak parks and forests: {'on' if s.chatter_parks else 'off'}",
                lambda _d: self._toggle_chatter("chatter_parks"),
                "Callouts when the road enters a national park, national "
                "forest, or other protected public land.",
            ),
            (
                lambda: f"Speak river crossings: {'on' if s.chatter_rivers else 'off'}",
                lambda _d: self._toggle_chatter("chatter_rivers"),
                "Callouts when the road crosses a named river.",
            ),
            (
                lambda: f"Speak mountain passes: {'on' if s.chatter_passes else 'off'}",
                lambda _d: self._toggle_chatter("chatter_passes"),
                "Callouts approaching a named mountain pass, plus famous "
                "highway markers like the Loneliest Road in America.",
            ),
            (
                lambda: f"Speak museums and attractions: {'on' if s.chatter_museums else 'off'}",
                lambda _d: self._toggle_chatter("chatter_museums"),
                "Callouts for museums and roadside attractions near the route.",
            ),
            (
                lambda: f"Speak billboards: {'on' if s.chatter_billboards else 'off'}",
                lambda _d: self._toggle_chatter("chatter_billboards"),
                "Occasional roadside billboards, read as you pass them. "
                "Expect attorney ads and questionable tourist traps.",
            ),
            (
                lambda: f"Place callouts: {s.place_callouts}",
                self._cycle_place_callouts,
                "How much the co-driver says about places along the road. "
                "Sparse speaks only the town names that explain a speed "
                "limit change, like Entering Strawberry right before its 35. "
                "All adds the towns the route passes. Off silences place "
                "names entirely; speed limit announcements themselves are "
                "never affected.",
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
                "OneCore voice, so a screen reader cannot cut them off. The rate, "
                "pitch, volume, and voice rows below appear in this category only "
                "when the voice speaking to you supports them; with a screen "
                "reader running, those four are set in the screen reader itself.",
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
        # Weather, traffic, and parking sources, and the live-weather calendar,
        # used to live here. They are world simulation, not speech, so they
        # moved to Gameplay, World and traffic.
        return specs

    @staticmethod
    def _driving_assist_specs():
        return (
            (
                "automatic_emergency_braking",
                "Automatic emergency braking",
                "After a spoken hazard warning, the truck brakes automatically if you have not slowed enough.",
            ),
            (
                "lane_departure_warning",
                "Lane-departure warning",
                "Speaks and sounds a warning when the truck drifts toward a lane edge.",
            ),
            (
                "stop_and_go_assist",
                "Stop-and-go assistance",
                "Adaptive cruise can slow behind modeled traffic and resume while it remains safe.",
            ),
            # Nothing in the driving code reads this yet, and the row used to
            # promise steering help that never arrived. It stays as the slot
            # the help will land in, and says plainly that it is not doing
            # anything today -- a blind driver cannot see that the wheel is
            # unchanged, so the row has to tell them.
            (
                "lane_centering_assist",
                "Lane centering assistance",
                "Reserved for steering help toward the lane center, which the truck does not do yet: leaving this on or off makes no difference to how it steers today. Lane keeping is the row that decides how much of the lane work is yours, and Lane-departure warning is the one that speaks when you drift.",
            ),
            (
                "descent_speed_control",
                "Descent speed control",
                "Manages engine braking on descents. Balanced and Interactive capture a lower target when you brake. All assists also selects safe targets and uses stronger intervention.",
            ),
            (
                "exit_speed_assist",
                "Exit speed assistance",
                "Slows for an already-selected exit; you still confirm and take it.",
            ),
            (
                "destination_approach_assist",
                "Destination approach assistance",
                "Slows and stops at the selected facility arrival point; it never enters the yard or docks.",
            ),
            (
                "selected_stop_assist",
                "Planned rest-stop stopping assistance",
                "After T plans a sleep-capable route stop and X signals for its exit, this assistance stops at the entrance so the rest-stop menu can open. You still set the exit lane. It never chooses, signals, takes, or cancels an exit. Presets never change it.",
            ),
            (
                "curve_speed_assist",
                "Curve speed assistance",
                "Reduces speed workload for mapped curves; you still steer. It slows for the bend itself on the service brakes and never the engine brake; on a real downgrade it does raise the jake, because that is the grade's work and not the bend's.",
            ),
            (
                "route_transition_assist",
                "Route-transition assistance",
                "Helps manage speed and lane workload at confirmed route transitions.",
            ),
            # The speed keeper is an input-accessibility aid, not a driving
            # assist -- it lives in Gameplay, Controls, and there is exactly one
            # row for it. It used to appear here too, a second live control for
            # the one setting, which is a real hazard in a spoken list.
            (
                "pedal_latch",
                "Latching pedals",
                "Tap the accelerator or brake, then press again and hold for half a second: a click and a spoken confirmation latch the pedal so it stays applied hands-free. Press the same key once to take it back; the opposite pedal or any safety alert releases it instantly. Assists first, the default, lets cruise, the speed keeper, and curve assist manage speed over a latched throttle. Latch first treats the latch as a manual override those assists stand down for, the original behavior. Off turns latching pedals plain. Presets never change this.",
            ),
            (
                "predictive_cruise",
                "Predictive cruise",
                "Cruise reads the road a mile and a half ahead: it banks a little speed before a climb so the truck carries it up the hill, gives up the last few miles an hour at a crest instead of fighting for them, and stops adding speed it would only have to brake away before a descent. It says what it is doing the first time on each hill. Presets never change this.",
            ),
            (
                "curve_callouts",
                "Curve callouts",
                "A co-driver reads the road: bends that demand slowing are called before they arrive, like Sharp left, half a mile, advise 35. Bends you are already slow enough for stay silent. The U readout lists the next few either way. Presets never change this.",
            ),
            # The speed keeper holds a speed for you, so it belongs with the
            # rest of the driving help rather than in Controls, where it sat
            # among the keyboard, controller and units rows. Like the other
            # input-accessibility aids above it, presets never touch it.
            (
                "speed_keeper",
                "Speed keeper",
                "In low-speed zones where adaptive cruise is unavailable, such as facility roads, gates, and construction zones, pressing K holds your current speed so the accelerator does not need to stay held, then switches back to adaptive cruise on open roads. The keeper eases off early for the next turn or the next lower limit. Braking cancels the whole session. Presets never change this.",
            ),
        )

    def announce_entry(self) -> None:
        # Entry speaks the landing row through ``ctx.say`` rather than
        # ``speak_current``, so a row-specific notice attached only to the
        # latter is never heard by a player whose row is the one they land
        # on -- which is every player for Driving mode, the first row of
        # Difficulty and hours of service. Both notices are guarded by their
        # own counter, so running them here costs nothing on a visit that
        # arrows in from elsewhere.
        super().announce_entry()
        self._maybe_say_lane_keeping_rename()
        self._maybe_say_pace_retired()

    def speak_current(self) -> None:
        super().speak_current()
        self._maybe_say_lane_keeping_rename()
        self._maybe_say_pace_retired()

    def _maybe_say_pace_retired(self) -> None:
        """Tell a player who was on Realistic why their row now says Standard.

        Their game clock runs at half the rate they set it to, so a driving
        day now takes twice the real time it used to. Nothing else on the
        row would say so: the label reads Standard as though they had
        chosen it. Same budget and same queueing as the lane-keeping rename
        -- it follows the row announcement rather than interrupting it, so a
        player arrowing straight past loses it and hears it next visit.
        """
        s = self.ctx.settings
        if self.category != "difficulty" or s.pace_retired_notice_left <= 0:
            return
        if not self.items or not self.items[self.index].text.startswith("Driving mode"):
            return
        s.pace_retired_notice_left -= 1
        s.save()
        self.ctx.say(
            "This row used to offer Realistic, and yours was set to it. "
            "It has been retired: it was the fastest setting here, not the "
            "most true to life, and the name said the opposite of what it "
            "did. You are on Standard now, so the game clock runs at half "
            "the speed it did and a driving day takes twice the real time.",
            interrupt=False,
        )

    def _maybe_say_lane_keeping_rename(self) -> None:
        """Tell a returning player their Lane drift row is now Lane keeping.

        Only the real control says it, and only for a player whose settings
        file actually carried the old name. It queues behind the row
        announcement rather than interrupting it, which means a player who
        keeps arrowing loses it -- so the budget is three, and a lost
        announcement corrects itself on the next visit.
        """
        s = self.ctx.settings
        if self.category != "assistance" or s.lane_keeping_rename_notice_left <= 0:
            return
        if not self.items or not self.items[self.index].text.startswith("Lane keeping"):
            return
        s.lane_keeping_rename_notice_left -= 1
        s.save()
        was = LANE_KEEPING_TO_LEGACY.get(s.lane_keeping, "off")
        unchanged = {
            "full": "the truck still holds the lane and takes your exits",
            "partial": "the drift and the steering help are just as they were",
            "off": "you still hold the lane and take your own exits",
        }.get(s.lane_keeping, "the truck still holds the lane and takes your exits")
        self.ctx.say(
            f"This row used to be Lane drift, and yours read {was}. "
            f"Nothing about your driving changed: {unchanged}.",
            interrupt=False,
        )

    def _assist_preset_label(self) -> str:
        return {
            "realistic": "Realistic",
            "balanced": "Balanced",
            "all": "All assists",
            "custom": "Custom",
        }[self.ctx.settings.driving_assistance_preset]

    def _descent_level_label(self) -> str:
        return self.ctx.settings.descent_speed_control.title()

    def _cycle_assist_preset(self, direction: int) -> None:
        presets = tuple(DRIVING_ASSIST_PRESETS)
        current = self.ctx.settings.driving_assistance_preset
        index = presets.index(current) if current in presets else (-1 if direction > 0 else 0)
        lane_before = self.ctx.settings.lane_keeping
        self.ctx.settings.apply_driving_assistance_preset(
            presets[(index + direction) % len(presets)]
        )
        self._announce()
        if self.ctx.settings.lane_keeping != lane_before:
            note = (
                "Lane keeping full: the truck holds the lane, tap Left or Right to change lanes."
                if self.ctx.settings.lane_is_automated()
                else f"Lane keeping back to {self._lane_keeping_label()}."
            )
            self.ctx.say(note, interrupt=False)

    def _toggle_driving_assist(self, field: str, _direction: int = 1) -> None:
        if field == "pedal_latch":
            modes = ["assists first", "latch first", "off"]
            try:
                i = modes.index(self.ctx.settings.pedal_latch)
            except ValueError:
                i = 0
            self.ctx.settings.pedal_latch = modes[(i + _direction) % len(modes)]
            self._announce()
            return
        if field in (
            "curve_callouts",
            "predictive_cruise",
            "selected_stop_assist",
            "speed_keeper",
        ):
            # Input-accessibility aids and information layers, not realism
            # choices: they live outside the presets, so toggling one never
            # reads as Custom.
            setattr(self.ctx.settings, field, not getattr(self.ctx.settings, field))
            self._announce()
            return
        if field not in DRIVING_ASSIST_FIELDS:
            return
        was_custom = self.ctx.settings.driving_assistance_preset == "custom"
        if field == "descent_speed_control":
            levels = ("off", "realistic", "balanced", "interactive")
            current = levels.index(self.ctx.settings.descent_speed_control)
            self.ctx.settings.descent_speed_control = levels[(current + _direction) % len(levels)]
        else:
            setattr(self.ctx.settings, field, not getattr(self.ctx.settings, field))
        self.ctx.settings.refresh_driving_assistance_preset()
        self._announce()
        # Queue the preset note behind the toggle announcement (an interrupting
        # say here would cut off the new on/off state the player just changed),
        # and only on the change into Custom -- repeating it on every later
        # toggle is noise the preset row already answers.
        if self.ctx.settings.driving_assistance_preset == "custom" and not was_custom:
            self.ctx.say("Driving assistance preset: Custom.", interrupt=False)

    def _pace_label(self) -> str:
        scale = self.ctx.settings.time_scale
        return {10.0: "relaxed", 20.0: "standard", 1.0: "real time"}.get(scale, f"{scale:g} times")

    def _hos_label(self) -> str:
        return {
            "realistic": "realistic",
            "relaxed": "relaxed",
            "debug_off": "off (developer)",
        }.get(self.ctx.settings.hos_mode, "realistic")

    def _acc_gap_label(self) -> str:
        """The choice, and the number that makes it mean something.

        A sighted player could infer "close" from a picture of a road. This
        one is read aloud and nothing else on the row says how much room any
        of the words buys, so the seconds go in the label rather than being
        left to the help text.
        """
        from .driving_core import ACC_GAP_CHOICES, ACC_GAP_DEFAULT

        choice = self.ctx.settings.acc_following_gap
        seconds = ACC_GAP_CHOICES.get(choice, ACC_GAP_CHOICES[ACC_GAP_DEFAULT])
        spoken = f"{seconds:g}".replace(".5", " and a half")
        return f"{choice}, {spoken} seconds"

    def _cycle_acc_gap(self, d: int) -> None:
        from .driving_core import ACC_GAP_CHOICES, ACC_GAP_DEFAULT

        order = list(ACC_GAP_CHOICES)
        try:
            i = order.index(self.ctx.settings.acc_following_gap)
        except ValueError:
            i = order.index(ACC_GAP_DEFAULT)
        self.ctx.settings.acc_following_gap = order[(i + d) % len(order)]
        self._announce()

    def _lane_keeping_label(self) -> str:
        # The value carries its own meaning: a player cycling the row hears
        # what changes hands, not a bare difficulty word (owner ask
        # 2026-07-27). It has to, because "off" here means the hardest mode
        # while "off" on the rows around it means less help. The labels and
        # the loader's fallback share one source in settings.py.
        return self.ctx.settings.lane_keeping_label()

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

    def _cue_loudness_label(self) -> str:
        """The spoken value, in the words a volume row uses.

        The saved values are unchanged -- "subtle", "standard", "prominent" --
        so nobody's choice resets. What changes is that the row now says
        quieter or louder, which is what a player is actually choosing
        between. "Prominence" described the row to whoever wrote it, not to
        whoever hears it.
        """
        return {"subtle": "quieter", "standard": "standard", "prominent": "louder"}.get(
            self.ctx.settings.lane_cue_loudness, "standard"
        )

    def _toggle_lane_guide_tone(self, _d: int = 1) -> None:
        s = self.ctx.settings
        s.lane_guide_tone = not s.lane_guide_tone
        s.save()
        self._announce()

    def _cycle_cue_loudness(self, d: int) -> None:
        levels = ["subtle", "standard", "prominent"]
        try:
            i = levels.index(self.ctx.settings.lane_cue_loudness)
        except ValueError:
            i = 1
        self.ctx.settings.lane_cue_loudness = levels[(i + d) % len(levels)]
        self._announce()

    def _cycle_lane_keeping(self, d: int) -> None:
        modes = list(LANE_KEEPING_MODES)
        try:
            i = modes.index(self.ctx.settings.lane_keeping)
        except ValueError:
            i = 0
        self.ctx.settings.lane_keeping = modes[(i + d) % len(modes)]
        # Lane keeping is a preset field, so a hand-picked value is answered
        # by the preset row the same way any other assist is.
        self.ctx.settings.refresh_driving_assistance_preset()
        self._announce()

    def _toggle_engine_voice(self, _d: int = 1) -> None:
        """Flip between the recorded engine and the classic loop, live."""
        s = self.ctx.settings
        s.engine_voice = "classic" if s.engine_voice == "real" else "real"
        self.ctx.apply_volumes()  # re-voices a running engine in place
        self._announce()

    def _toggle_jake_voice(self, _d: int = 1) -> None:
        """Flip between the recorded jake and the classic synth, live."""
        s = self.ctx.settings
        s.jake_voice = "classic" if s.jake_voice == "real" else "real"
        self.ctx.apply_volumes()  # re-voices a sounding jake growl in place
        self._announce()

    def _toggle_radio_streamer_safe(self, _d: int) -> None:
        self.ctx.settings.radio_streamer_safe = not self.ctx.settings.radio_streamer_safe
        self.ctx.apply_active_radio_settings()
        self._announce()

    def _toggle_duck_for_speech(self, _d: int = 1) -> None:
        s = self.ctx.settings
        s.duck_audio_for_speech = not s.duck_audio_for_speech
        s.save()
        if not s.duck_audio_for_speech:
            # A duck held at the moment of the flip must not stick.
            self.ctx.audio.set_speech_duck(1.0)
        self._announce()

    def _toggle_controller(self, _d: int) -> None:
        self.ctx.settings.controller_enabled = not self.ctx.settings.controller_enabled
        self.ctx.apply_controller()
        self._announce()

    def _toggle_haptics(self, _d: int) -> None:
        self.ctx.settings.haptics_enabled = not self.ctx.settings.haptics_enabled
        self.ctx.apply_haptics()
        self._announce()

    def _cycle_driving_speech(self, d: int) -> None:
        s = self.ctx.settings
        i = DRIVING_SPEECH_MODES.index(s.driving_speech)
        s.driving_speech = DRIVING_SPEECH_MODES[(i + d) % len(DRIVING_SPEECH_MODES)]
        self._announce()

    def _cycle_place_callouts(self, d: int) -> None:
        s = self.ctx.settings
        i = PLACE_CALLOUT_MODES.index(s.place_callouts)
        s.place_callouts = PLACE_CALLOUT_MODES[(i + d) % len(PLACE_CALLOUT_MODES)]
        self._announce()

    def _set_all_chatter(self, d: int) -> None:
        # The master switch is directional like every other Left/Right
        # control: Right (or Enter) turns every chatter kind on, Left turns
        # every kind off.
        self.ctx.settings.set_all_chatter(d >= 0)
        self._announce()

    def _toggle_chatter(self, field: str) -> None:
        settings = self.ctx.settings
        setattr(settings, field, not getattr(settings, field))
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
        self.ctx.settings.save()
        self._announce()

    def _toggle_real_traffic(self, _d: int) -> None:
        self.ctx.settings.real_traffic = not self.ctx.settings.real_traffic
        self.ctx.settings.save()
        self._announce()

    def _toggle_real_parking(self, _d: int) -> None:
        self.ctx.settings.real_parking = not self.ctx.settings.real_parking
        self.ctx.settings.save()
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
