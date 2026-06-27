"""In-cab radio catalog, safety gates, and playback state."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Protocol

SAFE_ROUTE_PLAYLIST = "route_playlist"
SAFE_FALLBACK_STATION_ID = "ff-safety-satellite"


@dataclass(frozen=True)
class RadioStation:
    id: str
    name: str
    call_sign: str
    format: str
    source: str
    track_key: str = ""
    stream_url: str = ""
    safe_for_streaming: bool = True
    real_stream: bool = False
    fallback: bool = False

    @property
    def display_name(self) -> str:
        return f"{self.call_sign}, {self.name}"


DEFAULT_RADIO_CATALOG: tuple[RadioStation, ...] = (
    RadioStation(
        id=SAFE_ROUTE_PLAYLIST,
        name="Freight Fate Roadhouse",
        call_sign="FFR",
        format="original road music",
        source="built-in royalty-free Freight Fate music",
    ),
    RadioStation(
        id="ff-night-line",
        name="Freight Fate Night Line",
        call_sign="FFN",
        format="quiet night-driving music",
        source="built-in royalty-free Freight Fate music",
        track_key="night_haul",
    ),
    RadioStation(
        id=SAFE_FALLBACK_STATION_ID,
        name="Safe Satellite Fallback",
        call_sign="SAT",
        format="silent fallback",
        source="built-in silent fallback",
        fallback=True,
    ),
    RadioStation(
        id="afn-pacific",
        name="AFN Pacific",
        call_sign="AFN",
        format="public internet stream",
        source="external public stream, opt-in only",
        stream_url="https://playerservices.streamtheworld.com/api/livestream-redirect/AFNPACIFIC.mp3",
        safe_for_streaming=False,
        real_stream=True,
    ),
)


class RadioPlaybackBackend(Protocol):
    def play_station(self, station: RadioStation, volume: float) -> None: ...
    def stop_radio(self) -> None: ...


class RadioPlaybackError(RuntimeError):
    """Raised when a station cannot play and radio should fall back safely."""


@dataclass(frozen=True)
class RadioAction:
    message: str
    station: RadioStation
    enabled: bool
    fallback_used: bool = False


class RadioState:
    """Mutable in-cab radio state with streamer-safe defaults."""

    def __init__(
        self,
        *,
        catalog: tuple[RadioStation, ...] = DEFAULT_RADIO_CATALOG,
        enabled: bool = True,
        station_id: str = SAFE_ROUTE_PLAYLIST,
        volume: float = 0.25,
        real_streams_enabled: bool = False,
        streamer_safe: bool = True,
    ) -> None:
        self.catalog = catalog
        self.enabled = enabled
        self.station_id = station_id
        self.volume = self._clamp_volume(volume)
        self.real_streams_enabled = real_streams_enabled
        self.streamer_safe = streamer_safe

    @classmethod
    def from_settings(cls, settings) -> RadioState:
        return cls(
            enabled=bool(getattr(settings, "radio_enabled", True)),
            station_id=str(getattr(settings, "radio_station_id", SAFE_ROUTE_PLAYLIST)),
            volume=float(getattr(settings, "radio_volume", 0.25)),
            real_streams_enabled=bool(getattr(settings, "radio_real_streams", False)),
            streamer_safe=bool(getattr(settings, "radio_streamer_safe", True)),
        )

    def apply_settings(self, settings) -> None:
        self.volume = self._clamp_volume(float(getattr(settings, "radio_volume", self.volume)))
        self.real_streams_enabled = bool(
            getattr(settings, "radio_real_streams", self.real_streams_enabled))
        self.streamer_safe = bool(getattr(settings, "radio_streamer_safe", self.streamer_safe))

    def write_settings(self, settings) -> None:
        settings.radio_enabled = self.enabled
        settings.radio_station_id = self.station_id

    def available_stations(self) -> tuple[RadioStation, ...]:
        stations = [
            station for station in self.catalog
            if self._station_allowed(station)
        ]
        return tuple(stations) or (self.fallback_station(),)

    def current_station(self) -> RadioStation:
        station = self._station_by_id(self.station_id)
        if station is not None and self._station_allowed(station):
            return station
        fallback = self.fallback_station()
        self.station_id = fallback.id
        return fallback

    def fallback_station(self) -> RadioStation:
        for station in self.catalog:
            if station.fallback:
                return station
        return self.catalog[0]

    def status_text(self) -> str:
        station = self.current_station()
        state = "on" if self.enabled else "off"
        safety = "streamer-safe" if self.streamer_safe else "streamer-safe off"
        return (
            f"Radio {state}. {station.display_name}, {station.format}. "
            f"Volume {round(self.volume * 100)} percent. {safety}. "
            f"Source: {station.source}."
        )

    def toggle(self, backend: RadioPlaybackBackend | None = None) -> RadioAction:
        self.enabled = not self.enabled
        if not self.enabled:
            self._stop(backend)
            return RadioAction("Radio off.", self.current_station(), enabled=False)
        return self.play(backend, prefix="Radio on.")

    def tune(self, direction: int, backend: RadioPlaybackBackend | None = None) -> RadioAction:
        stations = self.available_stations()
        current = self.current_station()
        try:
            index = stations.index(current)
        except ValueError:
            index = 0
        station = stations[(index + direction) % len(stations)]
        self.station_id = station.id
        if not self.enabled:
            return RadioAction(
                f"Radio off. Selected {station.display_name}, {station.format}.",
                station,
                enabled=False,
            )
        return self.play(backend, prefix=f"Tuned to {station.display_name}.")

    def play(
        self,
        backend: RadioPlaybackBackend | None = None,
        *,
        prefix: str = "",
    ) -> RadioAction:
        station = self.current_station()
        if not self.enabled:
            self._stop(backend)
            return RadioAction("Radio off.", station, enabled=False)
        if backend is None:
            return RadioAction(self._play_message(prefix, station), station, enabled=True)
        try:
            backend.play_station(station, self.volume)
        except Exception:
            fallback = self.fallback_station()
            self.station_id = fallback.id
            try:
                backend.play_station(fallback, self.volume)
            except Exception:
                self._stop(backend)
            return RadioAction(
                self._play_message(
                    "Radio fallback.",
                    fallback,
                    extra=f"{station.display_name} is unavailable.",
                ),
                fallback,
                enabled=True,
                fallback_used=True,
            )
        return RadioAction(self._play_message(prefix, station), station, enabled=True)

    def _station_allowed(self, station: RadioStation) -> bool:
        if not station.real_stream:
            return True
        return self.real_streams_enabled and not self.streamer_safe

    def _station_by_id(self, station_id: str) -> RadioStation | None:
        for station in self.catalog:
            if station.id == station_id:
                return station
        return None

    @staticmethod
    def _clamp_volume(volume: float) -> float:
        return max(0.0, min(1.0, volume))

    @staticmethod
    def _play_message(prefix: str, station: RadioStation, *, extra: str = "") -> str:
        parts = [part for part in (prefix, station.display_name, station.format, extra) if part]
        return ". ".join(parts) + "."

    @staticmethod
    def _stop(backend: RadioPlaybackBackend | None) -> None:
        if backend is None:
            return
        with contextlib.suppress(Exception):
            backend.stop_radio()
