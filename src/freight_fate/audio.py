"""Runtime audio engine: sound effects, loops, engine audio, and music.

Two interchangeable backends sit behind the :class:`AudioEngine` facade:

* **BASS** (via ``sound_lib``) — the preferred backend. The truck engine is a
  single loop whose playback frequency tracks RPM in real time, smoothed with
  BASS attribute slides. With no audio device (headless CI) it initializes
  BASS's "no sound" device, so the full code path still runs silently.
* **pygame.mixer** — automatic fallback when sound_lib/BASS cannot
  initialize. Uses the classic four-band engine loop crossfade.

Set ``FREIGHT_FATE_AUDIO_BACKEND=pygame`` to skip BASS entirely.

Both backends degrade gracefully: if nothing can initialize, every method
becomes a no-op, so game logic never needs to check for audio availability.

Sound keys are paths relative to the bundled sound library, without
extension: ``play("ui/menu_select")`` plays
``freight_fate/assets/sounds/ui/menu_select.wav``.
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

import pygame

log = logging.getLogger(__name__)

ASSETS = Path(__file__).parent / "assets" / "sounds"

# Reserved loop slots. The pygame backend maps them onto mixer channels;
# the BASS backend uses them as keys for its stream table.
CH_ENGINE = (0, 1, 2, 3)  # idle, low, mid, high crossfade ring (pygame only)
CH_ROAD = 4
CH_WEATHER = 5
CH_WEATHER_B = 6
CH_AMBIENT = 7
RESERVED = 8
NUM_CHANNELS = 32

# RPM centers for the pygame engine loop crossfade.
ENGINE_BANDS = (("engine/idle", 620), ("engine/low", 1000),
                ("engine/mid", 1500), ("engine/high", 2100))

# BASS engine model: one idle loop, pitched up with RPM.
ENGINE_LOOP_KEY = "engine/idle"
ENGINE_RPM_IDLE = 600.0
ENGINE_RPM_MAX = 2200.0
ENGINE_FREQ_MAX_MULT = 2.2
ENGINE_SLIDE_MS = 120

BASS_NO_SOUND_DEVICE = 0


def engine_freq_mult(rpm: float) -> float:
    """Playback-frequency multiplier for the BASS engine loop at ``rpm``.

    Linear from 1.0 at idle (600 RPM) to ~2.2x at redline (2200 RPM),
    clamped at both ends.
    """
    t = (rpm - ENGINE_RPM_IDLE) / (ENGINE_RPM_MAX - ENGINE_RPM_IDLE)
    return max(1.0, min(ENGINE_FREQ_MAX_MULT,
                        1.0 + t * (ENGINE_FREQ_MAX_MULT - 1.0)))


class _PygameBackend:
    """The original pygame.mixer implementation (engine band crossfade)."""

    name = "pygame"

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

    # -- music ----------------------------------------------------------------

    def play_music(self, track: str, fade_ms: int = 1500) -> None:
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


class _BassBackend:
    """sound_lib (BASS) implementation: streams, slides, and a pitched engine.

    Raises on construction if sound_lib cannot be imported or BASS cannot
    initialize at all; the facade then falls back to pygame.mixer. With the
    dummy SDL audio driver (tests, CI) or when no device exists, BASS's
    "no sound" device keeps the whole pipeline running silently.
    """

    name = "bass"

    def __init__(self) -> None:
        from sound_lib.external.pybass import (
            BASS_ATTRIB_FREQ,
            BASS_ATTRIB_VOL,
            BASS_ChannelSlideAttribute,
        )
        from sound_lib.main import BassError, bass_call
        from sound_lib.output import Output
        from sound_lib.stream import FileStream

        self._FileStream = FileStream
        self._BassError = BassError
        self._bass_call = bass_call
        self._slide = BASS_ChannelSlideAttribute
        self._ATTRIB_FREQ = BASS_ATTRIB_FREQ
        self._ATTRIB_VOL = BASS_ATTRIB_VOL

        self.master_volume = 1.0
        self.sfx_volume = 0.8
        self.music_volume = 0.55
        self._loops: dict[int, tuple[str, float, object]] = {}  # slot -> (key, gain, stream)
        self._music_track: str | None = None
        self._music_stream = None
        self._engine_running = False
        self._engine_stream = None
        self._engine_base_freq = 0.0

        if os.environ.get("SDL_AUDIODRIVER", "").lower() == "dummy":
            self._output = Output(device=BASS_NO_SOUND_DEVICE)
        else:
            try:
                self._output = Output()
            except BassError:
                log.warning("No audio device; using the BASS no-sound device")
                self._output = Output(device=BASS_NO_SOUND_DEVICE)
        self.enabled = True

    # -- assets -------------------------------------------------------------

    def _stream(self, path: Path, looping: bool):
        """A fresh stream for one playback; autofreed once it stops."""
        try:
            stream = self._FileStream(file=str(path), autofree=True)
        except self._BassError:
            log.warning("Could not open stream: %s", path, exc_info=True)
            return None
        if looping:
            stream.set_looping(True)
        return stream

    def _sfx_stream(self, key: str, looping: bool = False):
        path = ASSETS / (key + ".wav")
        if not path.exists():
            log.warning("Missing sound: %s", path)
            return None
        return self._stream(path, looping)

    def _fade_out(self, stream, fade_ms: int) -> None:
        """Slide volume to -1: BASS stops (and autofrees) the channel at 0."""
        try:
            self._bass_call(self._slide, stream.handle, self._ATTRIB_VOL,
                            -1.0, max(0, int(fade_ms)))
        except self._BassError:
            log.debug("Fade-out failed; stream already gone", exc_info=True)

    # -- one-shots ----------------------------------------------------------

    def play(self, key: str, volume: float = 1.0) -> None:
        stream = self._sfx_stream(key)
        if stream is None:
            return
        try:
            stream.set_volume(max(0.0, min(1.0, volume * self.sfx_volume * self.master_volume)))
            stream.play()
        except self._BassError:
            log.warning("Could not play %s", key, exc_info=True)

    # -- loops on reserved slots ------------------------------------------------

    def start_loop(self, channel: int, key: str, volume: float = 1.0, fade_ms: int = 300) -> None:
        current = self._loops.get(channel)
        if current and current[0] == key:
            self.set_loop_volume(channel, volume)
            return
        if current:
            self.stop_loop(channel, fade_ms=min(fade_ms, 300))
        stream = self._sfx_stream(key, looping=True)
        if stream is None:
            return
        self._loops[channel] = (key, volume, stream)
        try:
            stream.set_volume(0.0)
            stream.play()
        except self._BassError:
            del self._loops[channel]
            return
        self._apply_loop_volume(channel, fade_ms)

    def set_loop_volume(self, channel: int, volume: float) -> None:
        if channel in self._loops:
            key, _, stream = self._loops[channel]
            self._loops[channel] = (key, volume, stream)
            self._apply_loop_volume(channel)

    def stop_loop(self, channel: int, fade_ms: int = 300) -> None:
        entry = self._loops.pop(channel, None)
        if entry is not None:
            self._fade_out(entry[2], fade_ms)

    def _apply_loop_volume(self, channel: int, fade_ms: int = 0) -> None:
        if channel not in self._loops:
            return
        _, gain, stream = self._loops[channel]
        vol = max(0.0, min(1.0, gain * self.sfx_volume * self.master_volume))
        try:
            if fade_ms > 0:
                self._bass_call(self._slide, stream.handle, self._ATTRIB_VOL,
                                vol, int(fade_ms))
            else:
                stream.set_volume(vol)
        except self._BassError:
            del self._loops[channel]

    # -- truck engine: one loop, frequency tracks RPM ------------------------------

    def engine_start(self) -> None:
        if self._engine_running:
            return
        self._engine_running = True
        self.play("engine/start")
        stream = self._sfx_stream(ENGINE_LOOP_KEY, looping=True)
        if stream is not None:
            try:
                self._engine_base_freq = stream.get_frequency()
                stream.set_volume(0.0)
                stream.play()
            except self._BassError:
                stream = None
        self._engine_stream = stream
        self.set_engine_rpm(ENGINE_RPM_IDLE, throttle=0.0)

    def engine_stop(self, shutdown_sound: bool = True) -> None:
        if not self._engine_running:
            return
        self._engine_running = False
        if self._engine_stream is not None:
            self._fade_out(self._engine_stream, 250)
            self._engine_stream = None
        if shutdown_sound:
            self.play("engine/shutdown")

    def set_engine_rpm(self, rpm: float, throttle: float = 0.0) -> None:
        """Slide the engine loop's playback frequency to track RPM."""
        if not (self._engine_running and self._engine_stream is not None):
            return
        target = self._engine_base_freq * engine_freq_mult(rpm)
        gain = 0.5 + 0.35 * throttle
        vol = max(0.0, min(1.0, gain * self.sfx_volume * self.master_volume))
        try:
            self._bass_call(self._slide, self._engine_stream.handle,
                            self._ATTRIB_FREQ, target, ENGINE_SLIDE_MS)
            self._engine_stream.set_volume(vol)
        except self._BassError:
            self._engine_stream = None

    @property
    def engine_running(self) -> bool:
        return self._engine_running

    # -- music ----------------------------------------------------------------

    def play_music(self, track: str, fade_ms: int = 1500) -> None:
        if self._music_track == track:
            return
        path = ASSETS / "music" / (track + ".ogg")
        if not path.exists():
            path = ASSETS / "music" / (track + ".wav")
        if not path.exists():
            log.warning("Missing music track: %s", track)
            return
        if self._music_stream is not None:
            self._fade_out(self._music_stream, 800)
            self._music_stream = None
            self._music_track = None
        stream = self._stream(path, looping=True)
        if stream is None:
            return
        try:
            stream.set_volume(0.0)
            stream.play()
            self._bass_call(self._slide, stream.handle, self._ATTRIB_VOL,
                            max(0.0, min(1.0, self.music_volume * self.master_volume)),
                            max(0, int(fade_ms)))
        except self._BassError:
            log.warning("Could not play music %s", track, exc_info=True)
            return
        self._music_stream = stream
        self._music_track = track

    def stop_music(self, fade_ms: int = 1000) -> None:
        if self._music_stream is None:
            return
        self._fade_out(self._music_stream, fade_ms)
        self._music_stream = None
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
        for ch in list(self._loops):
            self._apply_loop_volume(ch)
        if self._engine_stream is not None:
            try:
                self._engine_stream.set_volume(
                    max(0.0, min(1.0, 0.5 * self.sfx_volume * self.master_volume)))
            except self._BassError:
                self._engine_stream = None
        if self._music_stream is not None:
            try:
                self._music_stream.set_volume(
                    max(0.0, min(1.0, self.music_volume * self.master_volume)))
            except self._BassError:
                self._music_stream = None

    def shutdown(self) -> None:
        for ch in list(self._loops):
            self.stop_loop(ch, fade_ms=0)
        self.engine_stop(shutdown_sound=False)
        self.stop_music(fade_ms=0)
        with contextlib.suppress(self._BassError):
            self._output.free()
        self.enabled = False


class _NullBackend:
    """Last resort: every primitive is a no-op."""

    name = "none"
    enabled = False
    engine_running = False
    master_volume = 1.0
    sfx_volume = 0.8
    music_volume = 0.55

    def play(self, key: str, volume: float = 1.0) -> None: ...
    def start_loop(self, channel: int, key: str, volume: float = 1.0,
                   fade_ms: int = 300) -> None: ...
    def set_loop_volume(self, channel: int, volume: float) -> None: ...
    def stop_loop(self, channel: int, fade_ms: int = 300) -> None: ...
    def engine_start(self) -> None: ...
    def engine_stop(self, shutdown_sound: bool = True) -> None: ...
    def set_engine_rpm(self, rpm: float, throttle: float = 0.0) -> None: ...
    def play_music(self, track: str, fade_ms: int = 1500) -> None: ...
    def stop_music(self, fade_ms: int = 1000) -> None: ...
    def set_volumes(self, master: float | None = None, sfx: float | None = None,
                    music: float | None = None) -> None: ...
    def shutdown(self) -> None: ...


class AudioEngine:
    """Facade over the active backend; the rest of the game talks only to this."""

    def __init__(self) -> None:
        self._impl = self._pick_backend()
        log.info("Audio backend: %s", self._impl.name)

    @staticmethod
    def _pick_backend():
        pref = os.environ.get("FREIGHT_FATE_AUDIO_BACKEND", "").strip().lower()
        if pref in ("", "bass"):
            try:
                return _BassBackend()
            except Exception:
                log.warning("sound_lib/BASS unavailable; falling back to pygame.mixer",
                            exc_info=True)
        backend = _PygameBackend()
        if backend.enabled:
            return backend
        return _NullBackend()

    @property
    def enabled(self) -> bool:
        return self._impl.enabled

    @property
    def backend_name(self) -> str:
        return self._impl.name

    @property
    def master_volume(self) -> float:
        return self._impl.master_volume

    @property
    def sfx_volume(self) -> float:
        return self._impl.sfx_volume

    @property
    def music_volume(self) -> float:
        return self._impl.music_volume

    # -- one-shots and loops ------------------------------------------------------

    def play(self, key: str, volume: float = 1.0) -> None:
        self._impl.play(key, volume)

    def start_loop(self, channel: int, key: str, volume: float = 1.0, fade_ms: int = 300) -> None:
        self._impl.start_loop(channel, key, volume, fade_ms)

    def set_loop_volume(self, channel: int, volume: float) -> None:
        self._impl.set_loop_volume(channel, volume)

    def stop_loop(self, channel: int, fade_ms: int = 300) -> None:
        self._impl.stop_loop(channel, fade_ms)

    # -- truck engine ----------------------------------------------------------------

    def engine_start(self) -> None:
        self._impl.engine_start()

    def engine_stop(self, shutdown_sound: bool = True) -> None:
        self._impl.engine_stop(shutdown_sound)

    def set_engine_rpm(self, rpm: float, throttle: float = 0.0) -> None:
        self._impl.set_engine_rpm(rpm, throttle)

    @property
    def engine_running(self) -> bool:
        return self._impl.engine_running

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
        self._impl.play_music(track, fade_ms)

    def stop_music(self, fade_ms: int = 1000) -> None:
        self._impl.stop_music(fade_ms)

    # -- volume control ---------------------------------------------------------

    def set_volumes(self, master: float | None = None, sfx: float | None = None,
                    music: float | None = None) -> None:
        self._impl.set_volumes(master, sfx, music)

    def shutdown(self) -> None:
        self._impl.shutdown()
