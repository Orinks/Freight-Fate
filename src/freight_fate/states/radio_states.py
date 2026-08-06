"""The radio screen: pick a band, pick a station, keep the ones you like.

Reachable from the pause menu and with Shift+M while driving. Everything the
dial can do is here as a spoken menu item, so a player who would rather not
memorise the driving keys never has to.
"""

from __future__ import annotations

import pygame

from ..sim.radio import band_text, frequency_text, signal_strength, station_text
from .base import MenuItem, MenuState

# A band can hold thousands of web stations. The list shows this many at a
# time so arrowing through it stays usable; favorites and the seek keys are
# how a player reaches a particular station, not scrolling to number four
# thousand.
STATION_PAGE = 40


class RadioState(MenuState):
    title = "Radio"
    intro_help = (
        "Choose a band, then a station. Enter tunes the station under the "
        "cursor. F adds or removes the station under the cursor from your "
        "favorites. While driving, M switches the radio on and off, I and O "
        "step down and up the dial, and Y changes band."
    )

    def __init__(self, ctx, driving) -> None:
        super().__init__(ctx)
        self.driving = driving
        self._offset = 0
        # Row index -> the station on that row, rebuilt with the items. The
        # favorite key reads this instead of parsing the label back.
        self._row_stations: dict[int, object] = {}

    @property
    def tuner(self):
        return self.driving.radio

    # -- items -----------------------------------------------------------------

    def build_items(self) -> list[MenuItem]:
        rows: list[tuple[MenuItem, object | None]] = []
        rows.extend(self._control_rows())
        rows.extend(self._favorite_rows())
        rows.extend(self._station_rows())
        rows.append((MenuItem("Back", self.go_back), None))

        self._row_stations = {
            index: station for index, (_, station) in enumerate(rows) if station is not None
        }
        return [item for item, _ in rows]

    def _control_rows(self) -> list[tuple[MenuItem, None]]:
        tuner = self.tuner
        return [
            (
                MenuItem(
                    lambda: f"Radio: {'on' if tuner.on else 'off'}",
                    self._toggle,
                    help="Switch the radio on or off. The same as pressing M while driving.",
                ),
                None,
            ),
            (
                MenuItem(
                    lambda: f"Band: {band_text(tuner.band)}",
                    self._next_band,
                    help="Step to the next band that has something on it. F M "
                    "and A M are the stations near you; web radio and "
                    "satellite reach you anywhere.",
                ),
                None,
            ),
            (
                MenuItem(
                    self._now_playing_label,
                    self._speak_now_playing,
                    help="Hear the full details of the station you are tuned to.",
                    select_sound=None,
                ),
                None,
            ),
        ]

    def _favorite_rows(self) -> list[tuple[MenuItem, object]]:
        return [
            (self._station_item(station, favorite=True), station)
            for station in self._favorite_stations()
        ]

    def _station_rows(self) -> list[tuple[MenuItem, object | None]]:
        tuner = self.tuner
        stations = tuner.stations_for(tuner.band)
        if not stations:
            return [
                (
                    MenuItem(
                        f"Nothing on {band_text(tuner.band)}",
                        self._explain_empty_band,
                        select_sound=None,
                    ),
                    None,
                )
            ]
        window = stations[self._offset : self._offset + STATION_PAGE]
        rows: list[tuple[MenuItem, object | None]] = [
            (self._station_item(station), station) for station in window
        ]
        remaining = len(stations) - self._offset - len(window)
        if remaining > 0:
            rows.append(
                (
                    MenuItem(
                        f"More stations: {remaining} left",
                        self._more,
                        help="Show the next block of stations on this band.",
                    ),
                    None,
                )
            )
        return rows

    def _station_item(self, station, *, favorite: bool = False) -> MenuItem:
        prefix = "Favorite: " if favorite else ""
        return MenuItem(
            lambda: f"{prefix}{self._station_label(station)}",
            lambda: self._tune(station),
            help=f"{station_text(station, self._strength(station))}. "
            "Enter listens. F adds or removes a favorite.",
        )

    def _station_label(self, station) -> str:
        """Short enough to arrow past, long enough to recognise."""
        if station.call_sign:
            dial = frequency_text(station)
            return f"{station.call_sign}, {dial}" if dial else station.call_sign
        return station.name

    def _now_playing_label(self) -> str:
        tuner = self.tuner
        if not tuner.on:
            return "Nothing playing"
        if tuner.station is None:
            return f"Nothing on {band_text(tuner.band)}"
        return f"Playing: {self._station_label(tuner.station)}"

    def _strength(self, station) -> float:
        tuner = self.tuner
        position = tuner.position
        return signal_strength(station, position[0], position[1])

    # -- actions ---------------------------------------------------------------

    def _toggle(self) -> None:
        self.driving._toggle_radio()
        self.refresh()

    def _next_band(self) -> None:
        self.driving._cycle_radio_band()
        self._offset = 0
        self.refresh(keep_index=False)

    def _speak_now_playing(self) -> None:
        self.driving._speak_radio_status()

    def _explain_empty_band(self) -> None:
        self.ctx.say(
            "No station on this band reaches you here. Try another band, or "
            "drive on: the next town brings its own."
        )

    def _more(self) -> None:
        self._offset += STATION_PAGE
        self.refresh(keep_index=False)
        self.ctx.say("More stations.")

    def _tune(self, station) -> None:
        if not self.driving._radio_available():
            return
        tuner = self.tuner
        tuner.on = True
        tuner.tune(station)
        self.driving._announce_station(station)
        self.refresh()

    # -- favorites -------------------------------------------------------------

    def _favorites(self) -> list[str]:
        profile = self.ctx.profile
        if profile is None:
            return []
        return list(getattr(profile, "radio_favorites", ()) or ())

    def _favorite_stations(self) -> list[object]:
        catalog = self.tuner.catalog
        found = (catalog.by_id(station_id) for station_id in self._favorites())
        # A favorite can outlive the station: catalogs get rebuilt and stations
        # go dark. Those rows quietly disappear rather than breaking the list.
        return [station for station in found if station is not None]

    def _toggle_favorite(self) -> None:
        profile = self.ctx.profile
        station = self._row_stations.get(self.index)
        if profile is None or station is None:
            self.ctx.say("That row is not a station.")
            return
        name = station.call_sign or station.name
        favorites = self._favorites()
        if station.id in favorites:
            favorites.remove(station.id)
            self.ctx.say(f"{name} removed from favorites.")
        else:
            favorites.append(station.id)
            self.ctx.say(f"{name} added to favorites.")
        profile.radio_favorites = favorites
        profile.save()
        self.refresh()

    # -- input -----------------------------------------------------------------

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
            self._toggle_favorite()
            return
        super().handle_event(event)
