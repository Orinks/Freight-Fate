"""The Radio app on the driver tablet: search the dial, tune by name, keep
favorites.

The dial keys walk the band one station at a time and the Tab radio screen
only reports; neither lets a driver ask for a station by name, and with five
thousand web stations behind the terrestrial band that is the difference
between finding one and never hearing it. This app is three short lists and a
text field over the existing ``RadioState``: nothing here talks to the
network, and every tune goes through the same ``select_station`` the dial
uses, so the streamer-safe gate, the session's dead-stream ban, and the
engine-power rule all hold.

Owner, 2026-08-22: "add a way to search and tune into stations in the radio
tablet app ... and favorite stations in the app too."
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..radio import RADIO_SEARCH_LIMIT, RadioReception, RadioStation
from .base import MenuItem, MenuState
from .text_entry import TextEntryState

if TYPE_CHECKING:
    from .driving import DrivingState


def _hit_label(
    driving: DrivingState, station: RadioStation, reception: RadioReception | None
) -> str:
    """One spoken row: name, band, and how it comes in here."""
    radio = driving.radio
    bits = [station.display_name, radio.band_name(station)]
    if reception is None:
        bits.append("out of range here")
    else:
        bits.append(reception.signal_label)
    if station.id == radio.current_station().id:
        bits.append("tuned now")
    if radio.is_favorite(station):
        bits.append("favorite")
    return ", ".join(bits)


class RadioAppState(MenuState):
    """The app's front page: what is playing, and the three ways in."""

    title = "Radio"
    intro_help = (
        "Radio app. Enter on a station tunes it. Search stations asks for a "
        "name, call sign, or format and lists every match on the dial. "
        "Escape returns to Driver apps."
    )

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def enter(self) -> None:
        # The dial re-reads the Playlists folder here for the same reason the
        # Tab radio screen does: this is where a player comes looking.
        self.driving.radio.reload_personal_playlists()
        self.driving._sync_radio_settings()
        super().enter()

    def build_items(self) -> list[MenuItem]:
        d = self.driving
        radio = d.radio
        items = [
            MenuItem(
                lambda: d._radio_now_playing_text(),
                lambda: self.ctx.say(d._radio_now_playing_text()),
                help="What the tuned station says it is playing. Enter asks again.",
            ),
            MenuItem(
                lambda: (
                    f"Radio: {'on' if radio.enabled else 'off'}, "
                    f"tuned to {radio.current_station().display_name}"
                ),
                self._toggle_power,
                help="Enter switches the radio on or off.",
            ),
            MenuItem(
                self._favorite_label,
                self._toggle_favorite,
                help="Enter saves the tuned station to your favorites, or removes it.",
            ),
            MenuItem(
                lambda: f"Favorites: {len(radio.favorites())} saved",
                lambda: self.ctx.push_state(RadioStationListState(self.ctx, d, kind="favorites")),
                help="Open your saved stations. Enter on one tunes it.",
            ),
            MenuItem(
                "Search stations",
                lambda: self.ctx.push_state(RadioSearchEntryState(self.ctx, d)),
                help=(
                    "Type part of a station name, call sign, or format; every "
                    "match on the dial is listed, nearest signal first."
                ),
            ),
            MenuItem(
                lambda: f"Stations in range: {len(radio.receivable_stations())}",
                lambda: self.ctx.push_state(RadioStationListState(self.ctx, d, kind="range")),
                help="Open every station that comes in here. Enter on one tunes it.",
            ),
            MenuItem(
                "Back to Driver apps", self.go_back, help="Return to the driver tablet app list."
            ),
        ]
        return items

    def _favorite_label(self) -> str:
        radio = self.driving.radio
        station = radio.current_station()
        if station.fallback:
            return "Favorites: the safety fallback is always on the dial"
        if radio.is_favorite(station):
            return f"Remove {station.display_name} from favorites"
        return f"Save {station.display_name} to favorites"

    def _toggle_favorite(self) -> None:
        # The same toggle the O key uses, so the profile is written once.
        self.driving._toggle_radio_favorite()
        self.refresh()

    def _toggle_power(self) -> None:
        self.driving._toggle_radio()
        self.refresh()


class RadioStationListState(MenuState):
    """A tunable list: favorites, the stations in range, or a search's hits."""

    intro_help = (
        "Use up and down arrows to move through the stations. Enter tunes the "
        "current one. Escape goes back."
    )

    def __init__(
        self,
        ctx,
        driving: DrivingState,
        *,
        kind: str,
        query: str = "",
        hits: list[tuple[RadioStation, RadioReception | None]] | None = None,
        total: int = 0,
    ) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.kind = kind
        self.query = query
        self._hits = hits
        self._total = total

    @property
    def title(self) -> str:  # type: ignore[override]
        if self.kind == "favorites":
            return "Favorite stations"
        if self.kind == "range":
            return "Stations in range"
        return f"Stations matching {self.query}"

    def _rows(self) -> list[tuple[RadioStation, RadioReception | None]]:
        radio = self.driving.radio
        if self.kind == "favorites":
            return radio.favorites()
        if self.kind == "range":
            return [(r.station, r) for r in radio.receivable_stations()]
        return list(self._hits or ())

    def announce_entry(self) -> None:
        rows = self._rows()
        if self.kind == "search" and self._total > len(rows):
            # Capped, and said so: a list that quietly stops at forty reads
            # as "that is everything" to someone who cannot see a scrollbar.
            self.ctx.say(
                f"{self.title}. {self._total} matches; the first {len(rows)} are listed. "
                "Search for something more specific to narrow it."
            )
        elif not rows:
            self.ctx.say(f"{self.title}. Nothing here yet.")
        else:
            self.ctx.say(f"{self.title}. {len(rows)} stations.")
        self.ctx.say(f"{self.current_text()}", interrupt=False, review=False)

    def build_items(self) -> list[MenuItem]:
        d = self.driving
        items = [
            MenuItem(
                lambda station=station, reception=reception: _hit_label(d, station, reception),
                lambda station=station, reception=reception: self._tune(station, reception),
                help="Enter tunes this station.",
                select_sound=None,
            )
            for station, reception in self._rows()
        ]
        if not items:
            items.append(
                MenuItem(
                    "No stations here yet."
                    if self.kind != "favorites"
                    else "No favorites saved yet. Enter on a tuned station's row in the "
                    "Radio app saves it.",
                    lambda: self.ctx.say(self.current_text()),
                    help="Nothing to tune on this list.",
                )
            )
        items.append(MenuItem("Back", self.go_back, help="Go back."))
        return items

    def _tune(self, station: RadioStation, reception: RadioReception | None) -> None:
        if reception is None:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"{station.display_name} is out of range here.")
            return
        self.ctx.audio.play("ui/menu_select")
        message = self.driving._tune_radio_to(station.id)
        self.ctx.say(message)
        self.refresh()


class RadioSearchEntryState(TextEntryState):
    """Type part of a station name; Enter lists the matches."""

    MAX_LEN = 40
    heading = "Search stations"
    field_label = "Search"

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def enter(self) -> None:
        self.ctx.say(
            "Search stations. Type part of a station name, call sign, or format, "
            "then press Enter. Left and right arrows review the letters you have "
            "typed, Home and End jump to the start or end. Press Escape to cancel."
        )

    def _confirm(self) -> None:
        query = " ".join(self.name.split())
        if not query:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Type something to search for first.", review=False)
            return
        hits, total = self.driving.radio.search(query, limit=RADIO_SEARCH_LIMIT)
        if not hits:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"No stations match {query}. Try a shorter word.", review=False)
            return
        self.ctx.audio.play("ui/menu_select")
        self.ctx.push_state(
            RadioStationListState(
                self.ctx, self.driving, kind="search", query=query, hits=hits, total=total
            )
        )
