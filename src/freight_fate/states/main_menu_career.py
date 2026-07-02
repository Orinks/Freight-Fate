"""Career start, home region, and home city menu states."""

from __future__ import annotations

from ..data.regions import REGION_LABELS
from ..models.profile import DEFAULT_CITY, Profile
from ..models.start_options import all_start_options, apply_start_option, start_option
from .base import MenuItem, MenuState


def _region_menu_name(region: str) -> str:
    """Region label suited to a menu item and first-letter jump.

    The spoken labels read naturally as prose ("in the Great Lakes"), but a
    list where every entry starts with "the" defeats type-ahead, so the leading
    article is dropped for menu display.
    """
    label = REGION_LABELS.get(region, region.replace("_", " "))
    return label[4:] if label.startswith("the ") else label


class CareerStartState(MenuState):
    title = "Career start"
    intro_help = (
        "Pick how this career begins. Company starts use assigned carrier "
        "equipment. The carrier pays normal fuel, repairs, insurance, and "
        "trailer support. The owner-operator start is higher risk: you "
        "control a starter tractor and pay business costs from day one. Enter "
        "selects; Escape goes back to name entry."
    )

    def __init__(self, ctx, driver_name: str) -> None:
        super().__init__(ctx)
        self.driver_name = driver_name

    def announce_entry(self) -> None:
        self.ctx.say(f"Career start. Pick a carrier or owner-operator start. {self.current_text()}")

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
        default_city = (
            option.default_city if option.default_city in ctx.world.cities else DEFAULT_CITY
        )
        default = (
            ctx.world.cities[default_city].region if default_city in ctx.world.cities else None
        )
        if default in self._regions:
            self.index = self._regions.index(default)

    def announce_entry(self) -> None:
        option = start_option(self.start_key)
        self.ctx.say(
            "Home region. Pick the part of the country where your "
            f"{option.carrier_name} career starts. {self.current_text()}"
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
            HomeCityState(
                self.ctx, self.driver_name, self.start_key, region, self._cities_by_region[region]
            )
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

    def __init__(
        self, ctx, driver_name: str, start_key: str, region: str, city_names: list[str]
    ) -> None:
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
        self.ctx.say(
            f"{region} terminals. Pick the city where your career starts. {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        for name in self._cities:
            city = self.ctx.world.cities[name]
            terminal = self.ctx.world.home_terminal(name)
            items.append(
                MenuItem(
                    f"{name}, {city.state}",
                    lambda n=name: self._pick(n),
                    help=f"Start at {terminal.spoken_name} in {name}, {city.state}.",
                )
            )
        return items

    def _pick(self, city: str) -> None:
        from .city import CityMenuState, first_day_orientation_message

        name = self.driver_name
        existing = {p.stem.lower() for p in Profile.list_saves()}
        option = start_option(self.start_key)
        profile = Profile(name=name, current_city=city)
        apply_start_option(profile, option)
        self.ctx.profile = profile
        profile.save()
        self.ctx.pop_state()  # this city picker
        self.ctx.pop_state()  # region picker
        self.ctx.pop_state()  # career start
        self.ctx.pop_state()  # name entry
        self.ctx.push_state(CityMenuState(self.ctx))
        loaded_over = (
            f"Loaded over existing driver named {name}. " if name.lower() in existing else ""
        )
        message = first_day_orientation_message(self.ctx, loaded_over)
        self.ctx.say(message, interrupt=True)
