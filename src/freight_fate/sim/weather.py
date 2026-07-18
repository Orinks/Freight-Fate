"""Dynamic weather with regional flavor, driving modifiers, and forecasts.

Weather evolves as a Markov chain over game time. Each condition carries
physics modifiers (grip, drag, visibility) and an ambience sound key.
A deterministic seed makes trips reproducible in tests.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from enum import Enum


class WeatherKind(Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    HEAVY_RAIN = "heavy rain"
    THUNDERSTORM = "thunderstorm"
    SNOW = "snow"
    ICE = "freezing rain"
    FOG = "fog"
    WIND = "high winds"


@dataclass(frozen=True)
class WeatherEffects:
    grip: float  # traction multiplier
    drag_mult: float  # aerodynamic drag multiplier (headwinds)
    visibility_mi: float
    sound: str | None  # ambience loop key, e.g. "weather/rain_light"
    wind: float  # 0..1 wind loop intensity
    safe_speed_mph: float
    water_mm: float = 0.0  # standing water depth; drives hydroplane onset
    surface: str = "dry"  # what the tires touch: dry, wet, snow, or ice


# Freezing rain never rolls in the random weather draw: it forms when rain
# falls into the narrow band just below freezing (see season.py) or when the
# live NWS feed reports it. Its grip is glare-ice territory -- a third of
# snow -- which is what makes it the one condition worth parking for.
EFFECTS: dict[WeatherKind, WeatherEffects] = {
    WeatherKind.CLEAR: WeatherEffects(1.00, 1.00, 10.0, None, 0.0, 70),
    WeatherKind.CLOUDY: WeatherEffects(1.00, 1.00, 8.0, None, 0.1, 70),
    WeatherKind.RAIN: WeatherEffects(0.80, 1.05, 4.0, "weather/rain_light", 0.2, 55, 1.5, "wet"),
    WeatherKind.HEAVY_RAIN: WeatherEffects(
        0.62, 1.12, 1.5, "weather/rain_heavy", 0.4, 45, 3.0, "wet"
    ),
    WeatherKind.THUNDERSTORM: WeatherEffects(
        0.58, 1.18, 1.0, "weather/rain_heavy", 0.6, 40, 4.0, "wet"
    ),
    WeatherKind.SNOW: WeatherEffects(0.45, 1.08, 2.0, "weather/snow_wind", 0.5, 35, 0.0, "snow"),
    WeatherKind.ICE: WeatherEffects(0.15, 1.02, 3.0, "weather/rain_light", 0.2, 20, 0.0, "ice"),
    WeatherKind.FOG: WeatherEffects(0.92, 1.00, 0.3, "weather/fog_horn", 0.1, 40, 0.0, "wet"),
    WeatherKind.WIND: WeatherEffects(0.90, 1.25, 7.0, None, 0.9, 55),
}

# Per-region likelihood weights for each condition.
REGION_WEIGHTS: dict[str, dict[WeatherKind, float]] = {
    "northeast": {
        WeatherKind.CLEAR: 4,
        WeatherKind.CLOUDY: 3,
        WeatherKind.RAIN: 2,
        WeatherKind.HEAVY_RAIN: 1,
        WeatherKind.THUNDERSTORM: 0.5,
        WeatherKind.SNOW: 1.5,
        WeatherKind.FOG: 1,
        WeatherKind.WIND: 0.5,
    },
    "appalachia": {
        WeatherKind.CLEAR: 3.5,
        WeatherKind.CLOUDY: 3,
        WeatherKind.RAIN: 2,
        WeatherKind.HEAVY_RAIN: 1,
        WeatherKind.THUNDERSTORM: 1,
        WeatherKind.SNOW: 1.5,
        WeatherKind.FOG: 2.5,
        WeatherKind.WIND: 1,
    },
    "great_lakes": {
        WeatherKind.CLEAR: 3.5,
        WeatherKind.CLOUDY: 3.5,
        WeatherKind.RAIN: 2,
        WeatherKind.HEAVY_RAIN: 1,
        WeatherKind.THUNDERSTORM: 1.5,
        WeatherKind.SNOW: 2.5,
        WeatherKind.FOG: 1,
        WeatherKind.WIND: 1.5,
    },
    "upper_midwest": {
        # Coldest tier: long snowy winters, lake-effect and northwoods snow.
        WeatherKind.CLEAR: 3,
        WeatherKind.CLOUDY: 3.5,
        WeatherKind.RAIN: 1.5,
        WeatherKind.HEAVY_RAIN: 0.5,
        WeatherKind.THUNDERSTORM: 1.5,
        WeatherKind.SNOW: 3.5,
        WeatherKind.FOG: 1,
        WeatherKind.WIND: 2,
    },
    "corn_belt": {
        # Continental interior: warm-season thunderstorms, less snow than the
        # lakeshore (no lake-effect), river-valley fog.
        WeatherKind.CLEAR: 3.5,
        WeatherKind.CLOUDY: 3,
        WeatherKind.RAIN: 2,
        WeatherKind.HEAVY_RAIN: 1,
        WeatherKind.THUNDERSTORM: 2,
        WeatherKind.SNOW: 1.5,
        WeatherKind.FOG: 1.5,
        WeatherKind.WIND: 1.5,
    },
    "heartland": {
        WeatherKind.CLEAR: 4,
        WeatherKind.CLOUDY: 2.5,
        WeatherKind.RAIN: 2,
        WeatherKind.HEAVY_RAIN: 1,
        WeatherKind.THUNDERSTORM: 2,
        WeatherKind.SNOW: 1,
        WeatherKind.FOG: 1,
        WeatherKind.WIND: 2,
    },
    "southern_plains": {
        WeatherKind.CLEAR: 5,
        WeatherKind.CLOUDY: 2,
        WeatherKind.RAIN: 1.5,
        WeatherKind.HEAVY_RAIN: 1,
        WeatherKind.THUNDERSTORM: 2.5,
        WeatherKind.SNOW: 0.3,
        WeatherKind.FOG: 0.5,
        WeatherKind.WIND: 3,
    },
    "mid_south": {
        WeatherKind.CLEAR: 4,
        WeatherKind.CLOUDY: 2.5,
        WeatherKind.RAIN: 2,
        WeatherKind.HEAVY_RAIN: 1.5,
        WeatherKind.THUNDERSTORM: 2,
        WeatherKind.SNOW: 0.4,
        WeatherKind.FOG: 1.5,
        WeatherKind.WIND: 0.7,
    },
    "atlantic_southeast": {
        WeatherKind.CLEAR: 4.5,
        WeatherKind.CLOUDY: 2.5,
        WeatherKind.RAIN: 2,
        WeatherKind.HEAVY_RAIN: 1.5,
        WeatherKind.THUNDERSTORM: 2.5,
        WeatherKind.SNOW: 0.2,
        WeatherKind.FOG: 1,
        WeatherKind.WIND: 0.6,
    },
    "gulf_coast": {
        WeatherKind.CLEAR: 4,
        WeatherKind.CLOUDY: 2.5,
        WeatherKind.RAIN: 2,
        WeatherKind.HEAVY_RAIN: 2,
        WeatherKind.THUNDERSTORM: 3,
        WeatherKind.SNOW: 0.05,
        WeatherKind.FOG: 1.5,
        WeatherKind.WIND: 0.8,
    },
    "florida": {
        WeatherKind.CLEAR: 4.5,
        WeatherKind.CLOUDY: 2.5,
        WeatherKind.RAIN: 2,
        WeatherKind.HEAVY_RAIN: 2,
        WeatherKind.THUNDERSTORM: 3.5,
        WeatherKind.SNOW: 0.0,
        WeatherKind.FOG: 0.8,
        WeatherKind.WIND: 0.8,
    },
    "rockies": {
        WeatherKind.CLEAR: 4,
        WeatherKind.CLOUDY: 2.5,
        WeatherKind.RAIN: 1,
        WeatherKind.HEAVY_RAIN: 0.5,
        WeatherKind.THUNDERSTORM: 1,
        WeatherKind.SNOW: 3,
        WeatherKind.FOG: 1,
        WeatherKind.WIND: 2,
    },
    "great_basin": {
        WeatherKind.CLEAR: 5.5,
        WeatherKind.CLOUDY: 1.5,
        WeatherKind.RAIN: 0.7,
        WeatherKind.HEAVY_RAIN: 0.3,
        WeatherKind.THUNDERSTORM: 0.8,
        WeatherKind.SNOW: 1.5,
        WeatherKind.FOG: 0.5,
        WeatherKind.WIND: 2.5,
    },
    "desert_southwest": {
        WeatherKind.CLEAR: 7,
        WeatherKind.CLOUDY: 1.5,
        WeatherKind.RAIN: 0.5,
        WeatherKind.HEAVY_RAIN: 0.4,
        WeatherKind.THUNDERSTORM: 1,
        WeatherKind.SNOW: 0.15,
        WeatherKind.FOG: 0.2,
        WeatherKind.WIND: 2,
    },
    "california": {
        WeatherKind.CLEAR: 5,
        WeatherKind.CLOUDY: 3,
        WeatherKind.RAIN: 1.3,
        WeatherKind.HEAVY_RAIN: 0.5,
        WeatherKind.THUNDERSTORM: 0.3,
        WeatherKind.SNOW: 0.1,
        WeatherKind.FOG: 2.5,
        WeatherKind.WIND: 1,
    },
    "pacific_northwest": {
        WeatherKind.CLEAR: 2.5,
        WeatherKind.CLOUDY: 4,
        WeatherKind.RAIN: 3.5,
        WeatherKind.HEAVY_RAIN: 1.5,
        WeatherKind.THUNDERSTORM: 0.5,
        WeatherKind.SNOW: 1,
        WeatherKind.FOG: 2,
        WeatherKind.WIND: 1,
    },
}

DEFAULT_WEIGHTS = REGION_WEIGHTS["heartland"]


def _forced_weather() -> WeatherKind | None:
    """A dev/testing override locking the weather to one condition, from
    ``FREIGHT_FATE_FORCE_WEATHER`` (e.g. ``snow``, ``heavy_rain``, ``fog``,
    ``wind``). Empty or unrecognized -> None (normal weather)."""
    name = os.environ.get("FREIGHT_FATE_FORCE_WEATHER", "").strip().lower()
    if not name:
        return None
    normalized = name.replace("_", " ")
    for kind in WeatherKind:
        if normalized in (kind.name.lower(), kind.value, kind.value.replace(" ", "_")):
            return kind
    return None


class WeatherSystem:
    """Evolving weather for the current region of a trip.

    With a ``provider`` (see :mod:`freight_fate.sim.real_weather`) attached,
    real current conditions for the tracked city take priority; the simulated
    Markov weather keeps running underneath as an offline fallback.
    """

    def __init__(
        self,
        region: str = "heartland",
        seed: int | None = None,
        provider=None,
        game_hours: float | None = None,
        live_weather_controls_calendar: bool = True,
    ) -> None:
        self._rng = random.Random(seed)
        self.region = region
        self.provider = provider
        self.live_weather_controls_calendar = live_weather_controls_calendar
        # Career clock at this point in the trip. When provided, weather is
        # season- and temperature-aware (snow only when cold, storms only when
        # warm); when None, the simulated draw is used as-is so seed-based
        # tests stay deterministic. It advances with the trip in update().
        self.game_hours = game_hours
        self.city: str | None = None
        self.city_coords: tuple[float, float] = (0.0, 0.0)
        self.live = False  # True while real-world data is driving conditions
        # With real weather enabled, start neutral and wait for live data rather
        # than showing a simulated warm-up condition that the real data would
        # immediately replace. Simulated weather only appears if the provider
        # turns out to be offline (see update()).
        self._forced = _forced_weather()  # dev/testing override, usually None
        self.current = (
            self._forced
            if self._forced is not None
            else WeatherKind.CLEAR
            if provider is not None
            else self._seasonal(self._sample(region))
        )
        self.minutes_until_change = self._rng.uniform(25, 70)
        self.thunder_cooldown = 0.0

    def _season_clock(self) -> float | None:
        """Clock that drives season and temperature.

        With live weather enabled (a provider is attached), seasons follow the
        real calendar so the reported season matches the live conditions;
        otherwise they follow the career clock, and are off entirely when no
        career clock was supplied.
        """
        if self.provider is not None and self.live_weather_controls_calendar:
            from .season import real_clock_game_hours

            return real_clock_game_hours()
        return self.game_hours

    def _observed_temperature(self) -> float | None:
        """The real station temperature in Celsius while live weather is driving
        conditions, or None (still loading, offline, or provider has no reading).

        Defensive about provider shape so test fakes and older providers without
        ``get_temperature`` simply fall back to the seasonal model."""
        if not self.live or self.provider is None or self.city is None:
            return None
        getter = getattr(self.provider, "get_temperature", None)
        if getter is None:
            return None
        try:
            return getter(self.city)
        except Exception:  # pragma: no cover - defensive
            return None

    def _temperature(self) -> float | None:
        """Outdoor temperature in Celsius. Prefers the real station observation
        while live weather is active, falling back to the seasonal model; None
        when seasons are off and no live reading is available."""
        observed = self._observed_temperature()
        if observed is not None:
            return observed
        clock = self._season_clock()
        if clock is None:
            return None
        from .season import temperature_c

        return temperature_c(self.region, clock)

    def _seasonal(self, kind: WeatherKind) -> WeatherKind:
        """Reconcile a simulated condition with the season's temperature."""
        # When live weather does not control the calendar, precipitation must
        # agree with the career season even if the real station is currently
        # reporting a wintry condition. This prevents summer snow and cold-
        # season thunderstorms in the career's independent calendar.
        if self.provider is not None and not self.live_weather_controls_calendar:
            clock = self._season_clock()
            if clock is None:
                temp = None
            else:
                from .season import temperature_c

                temp = temperature_c(self.region, clock)
        else:
            temp = self._temperature()
        if temp is None:
            return kind
        from .season import adjust_for_calendar

        return adjust_for_calendar(kind, temp, self._season_clock())

    def set_city(self, city: str, lat: float, lon: float) -> None:
        """Track the city whose real weather should apply (provider mode)."""
        self.city = city
        self.city_coords = (lat, lon)

    def _sample(self, region: str, near: WeatherKind | None = None) -> WeatherKind:
        weights = REGION_WEIGHTS.get(region, DEFAULT_WEIGHTS).copy()
        if near is not None:
            # weather tends to evolve gradually: boost "adjacent" conditions
            adjacency = {
                WeatherKind.CLEAR: [WeatherKind.CLOUDY, WeatherKind.WIND],
                WeatherKind.CLOUDY: [WeatherKind.CLEAR, WeatherKind.RAIN, WeatherKind.FOG],
                WeatherKind.RAIN: [WeatherKind.CLOUDY, WeatherKind.HEAVY_RAIN],
                WeatherKind.HEAVY_RAIN: [WeatherKind.RAIN, WeatherKind.THUNDERSTORM],
                WeatherKind.THUNDERSTORM: [WeatherKind.HEAVY_RAIN, WeatherKind.RAIN],
                WeatherKind.SNOW: [WeatherKind.CLOUDY, WeatherKind.SNOW],
                WeatherKind.ICE: [WeatherKind.RAIN, WeatherKind.SNOW, WeatherKind.CLOUDY],
                WeatherKind.FOG: [WeatherKind.CLOUDY, WeatherKind.CLEAR],
                WeatherKind.WIND: [WeatherKind.CLEAR, WeatherKind.CLOUDY],
            }
            for kind in adjacency.get(near, ()):
                weights[kind] = weights.get(kind, 0.5) * 3.0
            weights[near] = weights.get(near, 1.0) * 2.0
        kinds = list(weights)
        return self._rng.choices(kinds, [weights[k] for k in kinds])[0]

    def set_region(self, region: str) -> None:
        self.region = region

    def update(self, game_minutes: float) -> WeatherKind | None:
        """Advance by game minutes. Returns the new condition if it changed."""
        self.thunder_cooldown = max(0.0, self.thunder_cooldown - game_minutes)
        if self.game_hours is not None:
            self.game_hours += game_minutes / 60.0  # advance the career clock

        if self._forced is not None:
            # Locked condition for testing: ignore the provider and simulation.
            if self.current != self._forced:
                self.current = self._forced
                return self._forced
            return None

        changed = self._poll_provider()
        if self.live:
            return changed

        if self.provider is not None and not self._provider_offline():
            # Real weather is enabled and still loading: hold the current
            # condition (clear at the start of a drive) instead of running a
            # simulated warm-up. Only fall through to simulation when the
            # provider is genuinely offline.
            return None

        self.minutes_until_change -= game_minutes
        if self.minutes_until_change > 0:
            return None
        self.minutes_until_change = self._rng.uniform(25, 70)
        new = self._seasonal(self._sample(self.region, near=self.current))
        if new != self.current:
            self.current = new
            return new
        return None

    def _provider_offline(self) -> bool:
        """Whether the provider has no usable data and a fetch has failed.

        While a first fetch is still pending this is False, so the system holds
        steady instead of flickering through simulated weather. Providers that
        do not report availability (test fakes) are treated as still loading.
        """
        if self.provider is None or self.city is None:
            return False
        checker = getattr(self.provider, "unavailable", None)
        if checker is None:
            return False
        try:
            return bool(checker(self.city))
        except Exception:  # pragma: no cover - defensive
            return False

    def _poll_provider(self) -> WeatherKind | None:
        """Apply real-world conditions when a provider is attached.

        Returns the new condition if real data changed it; otherwise None.
        While real data is available the simulated transitions are paused.
        """
        if self.provider is None or self.city is None:
            return None
        lat, lon = self.city_coords
        self.provider.request(self.city, lat, lon)
        kind = self.provider.get(self.city)
        if kind is None:
            self.live = False
            return None
        self.live = True
        guarded = self._seasonal(kind)
        if guarded != self.current:
            self.current = guarded
            return guarded
        return None

    def should_thunder(self) -> bool:
        """Occasional thunder strikes during a thunderstorm."""
        if self.current is not WeatherKind.THUNDERSTORM or self.thunder_cooldown > 0:
            return False
        if self._rng.random() < 0.4:
            self.thunder_cooldown = self._rng.uniform(2.0, 6.0)
            return True
        return False

    @property
    def effects(self) -> WeatherEffects:
        return EFFECTS[self.current]

    @property
    def temperature_c(self) -> float | None:
        """Modeled outdoor temperature in Celsius, or None when seasons are off."""
        return self._temperature()

    @property
    def season(self) -> str | None:
        """Current season (real calendar with live weather, else career clock)."""
        clock = self._season_clock()
        if clock is None:
            return None
        from .season import season

        return season(clock)

    @property
    def date_text(self) -> str | None:
        """Calendar date (real with live weather, else the career clock), e.g.
        'March 21'; None when no clock is available."""
        clock = self._season_clock()
        if clock is None:
            return None
        from .season import date_text

        return date_text(clock)

    def forecast(self, segments: int = 3) -> list[WeatherKind]:
        """Probable conditions ahead (informational, not binding)."""
        rng = random.Random()
        rng.setstate(self._rng.getstate())
        out: list[WeatherKind] = []
        cur = self.current
        for _ in range(segments):
            weights = REGION_WEIGHTS.get(self.region, DEFAULT_WEIGHTS).copy()
            weights[cur] = weights.get(cur, 1.0) * 2.5
            kinds = list(weights)
            cur = self._seasonal(rng.choices(kinds, [weights[k] for k in kinds])[0])
            out.append(cur)
        return out

    def describe(self, imperial: bool = True) -> str:
        eff = self.effects
        parts = [self.current.value]
        temp_c = self._temperature()
        if temp_c is not None:
            if imperial:
                parts.append(f"{temp_c * 9 / 5 + 32:.0f} degrees")
            else:
                parts.append(f"{temp_c:.0f} degrees Celsius")
        if eff.visibility_mi < 2:
            if imperial:
                visibility = f"{eff.visibility_mi:g} miles"
            else:
                visibility = f"{eff.visibility_mi * 1.609344:g} kilometers"
            parts.append(f"visibility {visibility}")
        if self.current is WeatherKind.ICE:
            parts.append("ice on the road")
        elif eff.grip < 0.7:
            parts.append("slick roads")
        if eff.wind > 0.6:
            parts.append("strong crosswinds")
        return ", ".join(parts)
