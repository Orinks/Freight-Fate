"""Main menu, profile selection, name entry, settings, and help screens."""

from __future__ import annotations

import pygame

from .. import __version__
from ..models.profile import Profile
from ..settings import TIME_SCALES
from .base import MenuItem, MenuState, State


class MainMenuState(MenuState):
    title = "Freight Fate"

    def enter(self) -> None:
        self.ctx.audio.play_music("menu_theme")
        super().enter()

    def announce_entry(self) -> None:
        self.ctx.say(
            f"Welcome to Freight Fate, version {__version__}. "
            f"An audio trucking adventure across America. {self.current_text()}",
        )

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        saves = Profile.list_saves()
        if saves:
            items.append(MenuItem("Continue", self._continue,
                                  help="Load your most recent driver profile."))
            if len(saves) > 1:
                items.append(MenuItem("Load driver", self._load_menu,
                                      help="Choose between saved driver profiles."))
        items.append(MenuItem("New career", self._new_game,
                              help="Start a fresh trucking career."))
        items.append(MenuItem("How to play", self._help,
                              help="Learn the controls and the goal of the game."))
        items.append(MenuItem("Settings", self._settings,
                              help="Units, transmission mode, volumes, and pacing."))
        items.append(MenuItem("Quit", self.ctx.quit, help="Exit the game."))
        return items

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.say("Press Enter on Quit to exit the game.")

    def _continue(self) -> None:
        from .city import CityMenuState

        path = Profile.list_saves()[0]
        self.ctx.profile = Profile.load(path)
        p = self.ctx.profile
        self.ctx.say(f"Welcome back, {p.name}. You are in {p.current_city} "
                     f"with {p.money:,.0f} dollars.", interrupt=True)
        self.ctx.push_state(CityMenuState(self.ctx))

    def _load_menu(self) -> None:
        self.ctx.push_state(LoadDriverState(self.ctx))

    def _new_game(self) -> None:
        self.ctx.push_state(NameEntryState(self.ctx))

    def _help(self) -> None:
        self.ctx.push_state(HelpState(self.ctx))

    def _settings(self) -> None:
        self.ctx.push_state(SettingsState(self.ctx))


class LoadDriverState(MenuState):
    title = "Load driver"

    def build_items(self) -> list[MenuItem]:
        items = []
        for path in Profile.list_saves():
            try:
                profile = Profile.load(path)
            except Exception:
                continue
            label = (f"{profile.name}: level {profile.career.level}, "
                     f"{profile.money:,.0f} dollars, in {profile.current_city}")
            items.append(MenuItem(label, lambda p=profile: self._pick(p)))
        items.append(MenuItem("Back", self.go_back))
        return items

    def _pick(self, profile: Profile) -> None:
        from .city import CityMenuState

        self.ctx.profile = profile
        self.ctx.say(f"Welcome back, {profile.name}.")
        self.ctx.pop_state()
        self.ctx.push_state(CityMenuState(self.ctx))


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
        from .city import CityMenuState

        name = self.name.strip() or "Driver"
        existing = {p.stem.lower() for p in Profile.list_saves()}
        profile = Profile(name=name)
        self.ctx.profile = profile
        profile.save()
        if name.lower() in existing:
            self.ctx.say(f"Loaded over existing driver named {name}.", interrupt=True)
        self.ctx.audio.play("ui/menu_select")
        self.ctx.say(
            f"Welcome aboard, {name}. Your career starts in {profile.current_city} "
            f"with {profile.money:,.0f} dollars and a full tank. "
            "Your first stop is the job board.", interrupt=True)
        self.ctx.pop_state()
        self.ctx.push_state(CityMenuState(self.ctx))

    def lines(self) -> list[str]:
        return ["New career", "", f"Driver name: {self.name}_",
                "Press Enter to confirm, Escape to cancel, F2 to review."]


HELP_PAGES = [
    ("The goal", [
        "You are an owner-operator truck driver building a freight career.",
        "Pick up jobs at city freight locations, choose a route,",
        "and deliver cargo across the country, on time and intact.",
        "Earn money and experience, level up, and unlock cargo endorsements.",
    ]),
    ("Menus", [
        "All menus use Up and Down arrows, Enter to select, Escape to go back.",
        "Home and End jump to the first and last option.",
        "Type a letter to jump to options starting with that letter.",
        "Press F1 in any menu for contextual help.",
    ]),
    ("Driving basics", [
        "E starts and stops the engine.",
        "Hold the Up arrow to accelerate, the Down arrow to brake.",
        "In automatic mode the truck shifts for itself.",
        "In manual mode, hold Left Shift for the clutch,",
        "then press 1 through 0 for gears one through ten, or N for neutral.",
        "J toggles the engine brake for long downhill grades.",
        "H sounds the horn.",
    ]),
    ("Driving information keys", [
        "Space speaks your speed, gear, and RPM.",
        "Tab speaks a full status report.",
        "F speaks fuel level and range. C speaks the clock and your deadline.",
        "R speaks route progress. V speaks the weather and the forecast.",
        "Escape opens the pause menu.",
    ]),
    ("On the road", [
        "Watch your speed: limits drop in construction and traffic zones.",
        "Hazards appear without warning. When you hear Brake now,",
        "slow below twenty five miles per hour quickly to avoid a collision.",
        "Rest stops are announced ahead. Stop there and press T",
        "to refuel and repair. Fuel prices vary by region.",
        "Running out of fuel means an expensive roadside rescue.",
    ]),
    ("Deliveries and money", [
        "Deliver before the deadline for a bonus. Late or damaged cargo pays less.",
        "Fragile cargo, like electronics and fresh food, punishes rough driving.",
        "Repair your truck in the city garage. Damage reduces engine power.",
        "Higher levels unlock longer hauls and special cargo endorsements.",
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
                     lambda: self._toggle_units(1)),
            MenuItem(lambda: f"Transmission: {'automatic' if s.automatic_transmission else 'manual'}",
                     lambda: self._toggle_transmission(1)),
            MenuItem(lambda: f"Trip pacing: {self._pace_label()}",
                     lambda: self._cycle_pace(1)),
            MenuItem(lambda: f"Master volume: {round(s.master_volume * 100)} percent",
                     lambda: self._volume("master_volume", 0.1)),
            MenuItem(lambda: f"Sound effects volume: {round(s.sfx_volume * 100)} percent",
                     lambda: self._volume("sfx_volume", 0.1)),
            MenuItem(lambda: f"Music volume: {round(s.music_volume * 100)} percent",
                     lambda: self._volume("music_volume", 0.1)),
            MenuItem(lambda: f"Speech verbosity: {['terse', 'normal', 'chatty'][s.speech_verbosity]}",
                     lambda: self._cycle_verbosity(1)),
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
        actions = [self._toggle_units, self._toggle_transmission, self._cycle_pace,
                   lambda d: self._volume("master_volume", 0.1 * d),
                   lambda d: self._volume("sfx_volume", 0.1 * d),
                   lambda d: self._volume("music_volume", 0.1 * d),
                   self._cycle_verbosity]
        if self.index < len(actions):
            actions[self.index](direction)

    def _pace_label(self) -> str:
        scale = self.ctx.settings.time_scale
        return {10.0: "relaxed", 20.0: "standard", 40.0: "fast"}.get(scale, f"{scale:g} times")

    def _announce(self) -> None:
        self.refresh()
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

    def _cycle_verbosity(self, d: int) -> None:
        self.ctx.settings.speech_verbosity = (self.ctx.settings.speech_verbosity + d) % 3
        self._announce()

    def go_back(self) -> None:
        self.ctx.settings.save()
        self.ctx.audio.play("ui/menu_back")
        self.ctx.say("Settings saved.")
        self.ctx.pop_state()
