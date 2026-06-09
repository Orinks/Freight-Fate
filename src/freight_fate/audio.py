"""Runtime audio engine: sound effects, loops, engine crossfade, and music.

Built on ``pygame.mixer``. The engine degrades gracefully: if the mixer
cannot initialize (no audio device, CI) every method becomes a no-op, so
game logic never needs to check for audio availability.

Sound keys are paths relative to the bundled sound library, without
extension: ``play("ui/menu_select")`` plays
``freight_fate/assets/sounds/ui/menu_select.wav``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

log = logging.getLogger(__name__)

ASSETS = Path(__file__).parent / "assets" / "sounds"

# Reserved mixer channels (everything above these is for one-shot effects).
CH_ENGINE = (0, 1, 2, 3)  # idle, low, mid, high crossfade ring
CH_ROAD = 4
CH_WEATHER = 5
CH_WEATHER_B = 6
CH_AMBIENT = 7
RESERVED = 8
NUM_CHANNELS = 32

# RPM centers for the engine loop crossfade.
ENGINE_BANDS = (("engine/idle", 620), ("engine/low", 1000),
                ("engine/mid", 1500), ("engine/high", 2100))


class AudioEngine:
    def __init__(self) -> None:
        self.enabled = False
        self.master_volume = 1.0
        self.sfx_volume = 0.8
        self.music_volume = 0.55
        self._cache: dict[str, pygame.mixer.Sound] = {}
        self._loops: dict[int, tuple[str, float]] = {}  # channel -> (key, base gain)
        self._music_track: str | None = None
        self._engine_running = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 1024)
                pygame.mixer.init()
            pygame.mixer.set_num_channels(NUM_CHANNELS)
            pygame.mixer.set_reserved(RESERVED)
            self.enabled = True
        except pygame.error:
            log.warning("Audio device unavailable; running silent", exc_info=True)

    # -- assets -------------------------------------------------------------

    def _sound(self, key: str) -> pygame.mixer.Sound | None:
        if not self.enabled:
            return None
        snd = self._cache.get(key)
        if snd is None:
            path = ASSETS / (key + ".wav")
            try:
                snd = pygame.mixer.Sound(str(path))
            except (pygame.error, FileNotFoundError):
                log.warning("Missing or unreadable sound: %s", path)
                return None
            self._cache[key] = snd
        return snd

    # -- one-shots ----------------------------------------------------------

    def play(self, key: str, volume: float = 1.0) -> None:
        snd = self._sound(key)
        if snd is None:
            return
        snd.set_volume(max(0.0, min(1.0, volume * self.sfx_volume * self.master_volume)))
        snd.play()

    # -- loops on reserved channels ------------------------------------------

    def start_loop(self, channel: int, key: str, volume: float = 1.0, fade_ms: int = 300) -> None:
        snd = self._sound(key)
        if snd is None:
            return
        ch = pygame.mixer.Channel(channel)
        current = self._loops.get(channel)
        if current and current[0] == key:
            self.set_loop_volume(channel, volume)
            return
        ch.play(snd, loops=-1, fade_ms=fade_ms)
        self._loops[channel] = (key, volume)
        self._apply_channel_volume(channel)

    def set_loop_volume(self, channel: int, volume: float) -> None:
        if channel in self._loops:
            key, _ = self._loops[channel]
            self._loops[channel] = (key, volume)
            self._apply_channel_volume(channel)

    def stop_loop(self, channel: int, fade_ms: int = 300) -> None:
        if not self.enabled:
            return
        if channel in self._loops:
            pygame.mixer.Channel(channel).fadeout(fade_ms)
            del self._loops[channel]

    def _apply_channel_volume(self, channel: int) -> None:
        if not self.enabled or channel not in self._loops:
            return
        _, gain = self._loops[channel]
        vol = max(0.0, min(1.0, gain * self.sfx_volume * self.master_volume))
        pygame.mixer.Channel(channel).set_volume(vol)

    # -- truck engine crossfade ----------------------------------------------

    def engine_start(self) -> None:
        if self._engine_running:
            return
        self._engine_running = True
        self.play("engine/start")
        for i, (key, _rpm) in enumerate(ENGINE_BANDS):
            self.start_loop(CH_ENGINE[i], key, volume=0.0, fade_ms=900)
        self.set_engine_rpm(620, throttle=0.0)

    def engine_stop(self, shutdown_sound: bool = True) -> None:
        if not self._engine_running:
            return
        self._engine_running = False
        for ch in CH_ENGINE:
            self.stop_loop(ch, fade_ms=250)
        if shutdown_sound:
            self.play("engine/shutdown")

    def set_engine_rpm(self, rpm: float, throttle: float = 0.0) -> None:
        """Crossfade the four engine loops around the current RPM."""
        if not (self.enabled and self._engine_running):
            return
        base = 0.5 + 0.35 * throttle
        for i, (_key, center) in enumerate(ENGINE_BANDS):
            # triangular weight, 1.0 at band center, 0 beyond ~600 rpm away
            w = max(0.0, 1.0 - abs(rpm - center) / 620.0)
            self.set_loop_volume(CH_ENGINE[i], base * w)

    @property
    def engine_running(self) -> bool:
        return self._engine_running

    # -- road / weather / ambience --------------------------------------------

    def set_road_noise(self, speed_mps: float) -> None:
        """Tire-on-asphalt loop whose volume tracks speed."""
        if not self.enabled:
            return
        gain = min(0.9, speed_mps / 30.0)
        if gain < 0.02:
            self.stop_loop(CH_ROAD, fade_ms=500)
        else:
            self.start_loop(CH_ROAD, "vehicle/road", volume=gain, fade_ms=400)

    def set_weather(self, key: str | None, intensity: float = 1.0) -> None:
        """Play a weather ambience loop, e.g. ``weather/rain_light``."""
        if key is None:
            self.stop_loop(CH_WEATHER, fade_ms=1200)
        else:
            self.start_loop(CH_WEATHER, key, volume=min(1.0, intensity), fade_ms=1200)

    def set_wind(self, intensity: float) -> None:
        if intensity < 0.05:
            self.stop_loop(CH_WEATHER_B, fade_ms=1500)
        else:
            self.start_loop(CH_WEATHER_B, "weather/wind", volume=min(0.8, intensity), fade_ms=1500)

    def set_ambient(self, key: str | None, volume: float = 0.7) -> None:
        if key is None:
            self.stop_loop(CH_AMBIENT, fade_ms=800)
        else:
            self.start_loop(CH_AMBIENT, key, volume=volume, fade_ms=800)

    def stop_world(self) -> None:
        """Stop engine, road, weather, and ambience (leaving UI sfx alone)."""
        self.engine_stop(shutdown_sound=False)
        for ch in (CH_ROAD, CH_WEATHER, CH_WEATHER_B, CH_AMBIENT):
            self.stop_loop(ch, fade_ms=400)

    # -- music ----------------------------------------------------------------

    def play_music(self, track: str, fade_ms: int = 1500) -> None:
        """Stream a music track, e.g. ``play_music("menu_theme")``."""
        if not self.enabled or self._music_track == track:
            return
        path = ASSETS / "music" / (track + ".ogg")
        if not path.exists():
            path = ASSETS / "music" / (track + ".wav")
        if not path.exists():
            log.warning("Missing music track: %s", track)
            return
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
            pygame.mixer.music.play(loops=-1, fade_ms=fade_ms)
            self._music_track = track
        except pygame.error:
            log.warning("Could not play music %s", track, exc_info=True)

    def stop_music(self, fade_ms: int = 1000) -> None:
        if not self.enabled or self._music_track is None:
            return
        pygame.mixer.music.fadeout(fade_ms)
        self._music_track = None

    # -- volume control ---------------------------------------------------------

    def set_volumes(self, master: float | None = None, sfx: float | None = None,
                    music: float | None = None) -> None:
        if master is not None:
            self.master_volume = max(0.0, min(1.0, master))
        if sfx is not None:
            self.sfx_volume = max(0.0, min(1.0, sfx))
        if music is not None:
            self.music_volume = max(0.0, min(1.0, music))
        if not self.enabled:
            return
        for ch in list(self._loops):
            self._apply_channel_volume(ch)
        if self._music_track is not None:
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)

    def shutdown(self) -> None:
        if self.enabled:
            pygame.mixer.stop()
            pygame.mixer.music.stop()
