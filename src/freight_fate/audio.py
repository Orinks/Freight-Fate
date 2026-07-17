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
import io
import logging
import os
from pathlib import Path

import pygame

from . import assets_pack
from .audio_fades import Fade, FadeScheduler
from .audio_loops import SustainLoop, to_seconds

log = logging.getLogger(__name__)

ASSETS = Path(__file__).parent / "assets" / "sounds"

# Reserved loop slots. The pygame backend maps them onto mixer channels;
# the BASS backend uses them as keys for its stream table.
CH_ENGINE = (0, 1, 2, 3)  # idle, low, mid, high crossfade ring (pygame only)
CH_ROAD = 4
CH_WEATHER = 5
CH_WEATHER_B = 6
CH_AMBIENT = 7
CH_HORN = 8
CH_REVERSE = 9
RESERVED = 9
NUM_CHANNELS = 32

# Horn sustain loop points (samples, at the asset's 44100 Hz). The horn is an
# attack -> sustain -> release sound: play the attack, loop this tuned interior
# region while the key/button is held, then let the release tail ring out.
HORN_LOOP_START = 11816
HORN_LOOP_END = 12379

# RPM centers for the pygame engine loop crossfade.
ENGINE_BANDS = (
    ("engine/idle", 620),
    ("engine/low", 1000),
    ("engine/mid", 1500),
    ("engine/high", 2100),
)

# BASS engine model: one idle loop, pitched up with RPM.
ENGINE_LOOP_KEY = "engine/idle"
ENGINE_RPM_IDLE = 600.0
ENGINE_RPM_MAX = 2200.0
ENGINE_FREQ_MAX_MULT = 1.75
ENGINE_SLIDE_MS = 120
ENGINE_LOOP_GAIN = 1.0

# Ignition crossfade. When the engine is deliberately started, the "engine/start"
# one-shot plays at full volume while the idle loop is held silent; near the tail
# of the clip the two crossfade over ENGINE_START_CROSSFADE_S seconds. Tune these
# to taste -- curve names are keys into ``audio_fades.CURVES`` (linear, ease_in,
# ease_out, ease_in_out, exponential, equal_power_in/out).
ENGINE_START_CROSSFADE_S = 0.3  # length of the tail blend
ENGINE_START_TAIL_ANCHOR = True  # blend ends at the clip's end; False = blend from t=0
ENGINE_START_FADE_OUT_CURVE = "equal_power_out"  # start.ogg 1.0 -> 0.0
ENGINE_START_FADE_IN_CURVE = "equal_power_in"  # engine loop 0.0 -> 1.0
ENGINE_START_ASSUMED_LEN_S = 2.0  # fallback if the clip length can't be queried
# Short fade-in for a silent (no-crank) engine loop start, e.g. resuming a trip
# whose engine was already running, or coming back from an in-trip menu.
ENGINE_RESUME_FADE_S = 0.25
# After the crank hands off, the loop starts at the crank's (full-load) volume so
# there is no dip, then eases down to its true off-throttle load over this window.
ENGINE_START_SETTLE_S = 0.6  # ease from crank level down to idle load
ENGINE_START_SETTLE_CURVE = "ease_out"  # key into audio_fades.CURVES

BASS_NO_SOUND_DEVICE = 0


def _asset_path(key: str, extensions: tuple[str, ...]) -> Path | None:
    """Loose-file lookup; source checkouts and asset tooling only."""
    for ext in extensions:
        path = ASSETS / f"{key}.{ext}"
        if path.exists():
            return path
    return None


def _asset_bytes(key: str, extensions: tuple[str, ...]) -> tuple[bytes, str] | None:
    """Bytes and extension for a sound key, from the shipped pack or loose files.

    Frozen builds carry the sounds packed into ``sounds.pak``
    (see ``assets_pack``); source checkouts read the editable
    ``assets/sounds`` tree.
    """
    pack = assets_pack.open_default()
    if pack is not None:
        for ext in extensions:
            data = pack.read(f"{key}.{ext}")
            if data is not None:
                return data, ext
    path = _asset_path(key, extensions)
    if path is not None:
        try:
            return path.read_bytes(), path.suffix.lstrip(".")
        except OSError:
            log.warning("Unreadable sound file: %s", path, exc_info=True)
    return None


def verify_sound_assets() -> None:
    """Raise if the canonical UI sound is unreadable (packed or loose).

    Used by the --smoke build check to prove frozen builds can read the
    shipped sound pack.
    """
    if _asset_bytes("ui/menu_select", ("ogg", "wav")) is None:
        raise RuntimeError("Sound assets are missing or unreadable: ui/menu_select")


def engine_freq_mult(rpm: float) -> float:
    """Playback-frequency multiplier for the BASS engine loop at ``rpm``.

    Linear from 1.0 at idle (600 RPM) to 1.75x at redline (2200 RPM),
    clamped at both ends.
    """
    t = (rpm - ENGINE_RPM_IDLE) / (ENGINE_RPM_MAX - ENGINE_RPM_IDLE)
    return max(1.0, min(ENGINE_FREQ_MAX_MULT, 1.0 + t * (ENGINE_FREQ_MAX_MULT - 1.0)))


def engine_load_gain(throttle: float) -> float:
    """Audible engine effort: present off-throttle, fuller under power.

    The load carries real feedback -- a truck holding speed uphill sits on
    more throttle and sounds fuller, and an automatic shift briefly unloads
    the engine. Both stay audible here. The floor sits at 0.68 (not 0.55) so
    coasting is not too quiet, while the 0.32 span keeps the load contour
    clearly perceptible. Pumping from accelerator release and adaptive-cruise
    corrections is handled upstream by smoothing the throttle before it
    reaches this envelope, not by flattening the range.
    """
    return 0.68 + 0.32 * max(0.0, min(1.0, throttle))


def _one_shot_category(key: str) -> str:
    if key.startswith("ui/"):
        return "ui"
    if key.startswith("weather/"):
        return "weather"
    if key.startswith("engine/"):
        return "engine"
    return "sfx"


def _loop_category(channel: int) -> str:
    if channel in CH_ENGINE:
        return "engine"
    if channel in (CH_WEATHER, CH_WEATHER_B):
        return "weather"
    return "sfx"


class _PygameBackend:
    """The original pygame.mixer implementation (engine band crossfade)."""

    name = "pygame"

    def __init__(self) -> None:
        self.enabled = False
        self.master_volume = 1.0
        self.sfx_volume = 0.8
        self.music_volume = 0.5
        self.weather_volume = 0.65
        self.engine_volume = 0.55
        self.ui_volume = 0.9
        self._cache: dict[str, pygame.mixer.Sound] = {}
        self._loops: dict[int, tuple[str, float]] = {}  # channel -> (key, base gain)
        # channel -> sustain-loop state (segment Sounds + phase); see
        # start_sustain_loop. Kept separate from _loops so per-frame update()
        # can re-queue the loop body for gapless repetition.
        self._sustains: dict[int, dict] = {}
        self._segment_cache: dict[tuple, tuple] = {}  # (key, start, end) -> (head, body, tail)
        self._music_track: str | None = None
        self._music_buffer: io.BytesIO | None = None  # streamed; must outlive playback
        self._engine_running = False
        self._engine_intro_gain = 1.0  # crossfade multiplier on the engine loop
        self._engine_intro_load = 0.0  # ignition load boost: 1.0 forces full load
        self._engine_starting = False  # True only during the ignition crossfade
        self._engine_last_rpm = ENGINE_RPM_IDLE
        self._fades = FadeScheduler()
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
            found = _asset_bytes(key, ("ogg", "wav"))
            if found is None:
                log.warning("Missing or unreadable sound: %s", key)
                return None
            try:
                snd = pygame.mixer.Sound(file=io.BytesIO(found[0]))
            except pygame.error:
                log.warning("Missing or unreadable sound: %s", key)
                return None
            self._cache[key] = snd
        return snd

    # -- one-shots ----------------------------------------------------------

    def play(self, key: str, volume: float = 1.0, pan: float = 0.0) -> None:
        snd = self._sound(key)
        if snd is None:
            return
        vol = max(
            0.0,
            min(1.0, volume * self._category_volume(_one_shot_category(key)) * self.master_volume),
        )
        snd.set_volume(vol)
        channel = snd.play()
        if channel is not None and pan:
            pan = max(-1.0, min(1.0, pan))
            left = vol * (1.0 - max(0.0, pan))
            right = vol * (1.0 + min(0.0, pan))
            channel.set_volume(left, right)

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
        if channel in self._sustains:
            del self._sustains[channel]
            pygame.mixer.Channel(channel).fadeout(fade_ms)
        if channel in self._loops:
            pygame.mixer.Channel(channel).fadeout(fade_ms)
            del self._loops[channel]

    def _build_segments(self, key: str, loop_start: int, loop_end: int):
        """Slice a decoded sound into (head, body, tail) Sounds; cached per key.

        ``head`` is the attack through the loop end (samples ``0:loop_end``),
        ``body`` is the loop region (``loop_start:loop_end``) tiled so it
        comfortably outlasts a frame -- that keeps the always-queued handoff
        in :meth:`_service_sustains` gapless even at low frame rates -- and
        ``tail`` is the release (``loop_end:``), or None if the loop ends at EOF.
        """
        cache_key = (key, loop_start, loop_end)
        cached = self._segment_cache.get(cache_key)
        if cached is not None:
            return cached
        snd = self._sound(key)
        if snd is None:
            return None
        try:
            import numpy

            arr = pygame.sndarray.array(snd)
        except Exception:
            log.warning("Could not slice %s for a sustain loop", key, exc_info=True)
            return None
        n = len(arr)
        start = max(0, min(loop_start, n))
        end = max(start + 1, min(loop_end, n))
        region = numpy.ascontiguousarray(arr[start:end])
        freq = pygame.mixer.get_init()[0] if pygame.mixer.get_init() else 44100
        reps = max(1, -(-int(freq * 0.1) // max(1, len(region))))  # ceil to ~100 ms
        tiled = numpy.tile(region, (reps, 1) if region.ndim == 2 else reps)
        head = pygame.sndarray.make_sound(numpy.ascontiguousarray(arr[:end]))
        body = pygame.sndarray.make_sound(numpy.ascontiguousarray(tiled))
        tail = pygame.sndarray.make_sound(numpy.ascontiguousarray(arr[end:])) if end < n else None
        segs = (head, body, tail)
        self._segment_cache[cache_key] = segs
        return segs

    def start_sustain_loop(
        self,
        channel: int,
        key: str,
        loop_start: float,
        loop_end: float,
        *,
        units: str = "samples",
        volume: float = 1.0,
    ) -> None:
        if not self.enabled:
            return
        current = self._sustains.get(channel)
        if current and current["key"] == key:
            # Already sounding on this channel: update gain while held, but
            # ignore the press entirely during the release tail so a repeat
            # press never restarts or stacks the sound.
            if current["phase"] == "sustain":
                current["gain"] = volume
                self._apply_sustain_volume(channel)
            return
        freq = pygame.mixer.get_init()[0] if pygame.mixer.get_init() else 44100
        start_i = int(round(to_seconds(loop_start, units, freq) * freq))
        end_i = int(round(to_seconds(loop_end, units, freq) * freq))
        segs = self._build_segments(key, start_i, end_i)
        if segs is None:
            return
        self.stop_loop(channel, fade_ms=0)
        head, body, tail = segs
        self._sustains[channel] = {
            "key": key,
            "gain": volume,
            "body": body,
            "tail": tail,
            "phase": "sustain",
        }
        self._apply_sustain_volume(channel)
        ch = pygame.mixer.Channel(channel)
        ch.play(head, loops=0)
        ch.queue(body)

    def release_sustain_loop(self, channel: int, fade_ms: int = 0) -> None:
        st = self._sustains.get(channel)
        if st is None:
            self.stop_loop(channel, fade_ms=fade_ms)
            return
        st["phase"] = "release"
        ch = pygame.mixer.Channel(channel)
        if st["tail"] is not None:
            # Replace the queued body with the tail so, once the current loop
            # iteration ends, the natural release plays out (<=1 body length of
            # latency). _service_sustains clears the slot when the tail ends.
            ch.queue(st["tail"])
        else:
            ch.fadeout(max(0, fade_ms))
            del self._sustains[channel]

    def _apply_sustain_volume(self, channel: int) -> None:
        st = self._sustains.get(channel)
        if not st:
            return
        vol = max(
            0.0,
            min(
                1.0,
                st["gain"] * self._category_volume(_loop_category(channel)) * self.master_volume,
            ),
        )
        pygame.mixer.Channel(channel).set_volume(vol)

    def _service_sustains(self) -> None:
        """Keep a body queued during sustain; retire the slot when a tail ends."""
        if not self._sustains:
            return
        for channel, st in list(self._sustains.items()):
            ch = pygame.mixer.Channel(channel)
            if st["phase"] == "sustain":
                if ch.get_busy() and ch.get_queue() is None:
                    ch.queue(st["body"])
                elif not ch.get_busy():  # ran dry; restart the loop
                    ch.play(st["body"], loops=0)
                    ch.queue(st["body"])
            elif not ch.get_busy():  # release tail finished
                del self._sustains[channel]

    def reverse_start(self) -> None:
        # The reverse loop is intentionally not played through pygame.mixer.
        return

    def reverse_stop(self) -> None:
        return

    def _apply_channel_volume(self, channel: int) -> None:
        if not self.enabled or channel not in self._loops:
            return
        _, gain = self._loops[channel]
        vol = max(
            0.0,
            min(1.0, gain * self._category_volume(_loop_category(channel)) * self.master_volume),
        )
        pygame.mixer.Channel(channel).set_volume(vol)

    # -- truck engine crossfade ----------------------------------------------

    def engine_start(self, play_start_sound: bool = True) -> None:
        if self._engine_running:
            return
        self._engine_running = True
        self._fades.clear()
        # The engine loop is held at intro gain 0 while the ignition one-shot
        # plays, then crossfaded up. A silent (resume) start skips the crank
        # and just eases the loop in.
        self._engine_intro_gain = 0.0
        self._engine_intro_load = 0.0
        if play_start_sound:
            self._begin_engine_start_crossfade()
        else:
            self._fades.add(
                Fade(
                    self._set_engine_intro_gain,
                    0.0,
                    1.0,
                    ENGINE_RESUME_FADE_S,
                    curve=ENGINE_START_FADE_IN_CURVE,
                )
            )
        for i, (key, _rpm) in enumerate(ENGINE_BANDS):
            self.start_loop(CH_ENGINE[i], key, volume=0.0, fade_ms=0)
        self.set_engine_rpm(ENGINE_RPM_IDLE, throttle=0.0)

    def _begin_engine_start_crossfade(self) -> None:
        """Play ``engine/start`` at full volume and blend into the loop at its tail."""
        self._engine_starting = True
        snd = self._sound("engine/start")
        channel = snd.play() if snd is not None else None
        if snd is None or channel is None:
            # No crank available (headless, no free channel): bring the loop up
            # promptly so the engine is still audible.
            self._fades.add(
                Fade(
                    self._set_engine_intro_gain,
                    0.0,
                    1.0,
                    ENGINE_RESUME_FADE_S,
                    on_done=self._end_engine_starting,
                )
            )
            return
        base = max(0.0, min(1.0, self._category_volume("engine") * self.master_volume))
        channel.set_volume(base)
        clip_len = snd.get_length()
        delay = max(0.0, clip_len - ENGINE_START_CROSSFADE_S) if ENGINE_START_TAIL_ANCHOR else 0.0
        # Boost the loop to full (crank) load through the handoff so it meets the
        # crank tail at the same level instead of the quieter off-throttle idle.
        self._engine_intro_load = 1.0
        self._fades.add(
            Fade(
                lambda m: channel.set_volume(base * m),
                1.0,
                0.0,
                ENGINE_START_CROSSFADE_S,
                curve=ENGINE_START_FADE_OUT_CURVE,
                delay_s=delay,
            )
        )
        self._fades.add(
            Fade(
                self._set_engine_intro_gain,
                0.0,
                1.0,
                ENGINE_START_CROSSFADE_S,
                curve=ENGINE_START_FADE_IN_CURVE,
                delay_s=delay,
                on_done=self._end_engine_starting,
            )
        )
        # Once the crossfade completes, ease the load boost back off so the loop
        # settles to its real off-throttle volume.
        self._fades.add(
            Fade(
                self._set_engine_intro_load,
                1.0,
                0.0,
                ENGINE_START_SETTLE_S,
                curve=ENGINE_START_SETTLE_CURVE,
                delay_s=delay + ENGINE_START_CROSSFADE_S,
            )
        )

    def _set_engine_intro_gain(self, gain: float) -> None:
        self._engine_intro_gain = max(0.0, min(1.0, gain))
        # Re-apply the band volumes at the last known RPM so the ramp is heard
        # immediately, regardless of when set_engine_rpm next runs.
        self.set_engine_rpm(self._engine_last_rpm)

    def _set_engine_intro_load(self, value: float) -> None:
        self._engine_intro_load = max(0.0, min(1.0, value))
        self.set_engine_rpm(self._engine_last_rpm)

    def _end_engine_starting(self) -> None:
        self._engine_starting = False

    def update(self, dt: float) -> None:
        self._fades.update(dt)
        self._service_sustains()

    def engine_stop(self, shutdown_sound: bool = True) -> None:
        if not self._engine_running:
            return
        self._engine_running = False
        self._fades.clear()
        self._engine_intro_gain = 1.0
        self._engine_intro_load = 0.0
        self._engine_starting = False
        for ch in CH_ENGINE:
            self.stop_loop(ch, fade_ms=250)
        if shutdown_sound:
            self.play("engine/shutdown")

    def set_engine_rpm(self, rpm: float, throttle: float = 0.0) -> None:
        """Crossfade the four engine loops around the current RPM."""
        if not (self.enabled and self._engine_running):
            return
        self._engine_last_rpm = rpm
        load_gain = engine_load_gain(throttle)
        # During the ignition handoff, boost load toward full so the loop meets
        # the crank tail; the boost eases back to 0 afterward.
        load_gain += self._engine_intro_load * (1.0 - load_gain)
        for i, (_key, center) in enumerate(ENGINE_BANDS):
            # triangular weight, 1.0 at band center, 0 beyond ~600 rpm away
            w = max(0.0, 1.0 - abs(rpm - center) / 620.0)
            self.set_loop_volume(
                CH_ENGINE[i], ENGINE_LOOP_GAIN * w * load_gain * self._engine_intro_gain
            )

    @property
    def engine_running(self) -> bool:
        return self._engine_running

    @property
    def engine_starting(self) -> bool:
        return self._engine_starting

    # -- music ----------------------------------------------------------------

    def play_music(self, track: str, fade_ms: int = 1500) -> None:
        if not self.enabled or self._music_track == track:
            return
        found = _asset_bytes(f"music/{track}", ("ogg", "wav"))
        if found is None:
            log.warning("Missing music track: %s", track)
            return
        data, ext = found
        try:
            buffer = io.BytesIO(data)
            pygame.mixer.music.load(buffer, namehint=ext)
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
            pygame.mixer.music.play(loops=0, fade_ms=fade_ms)
            self._music_track = track
            self._music_buffer = buffer
        except pygame.error:
            log.warning("Could not play music %s", track, exc_info=True)

    def stop_music(self, fade_ms: int = 1000) -> None:
        if not self.enabled or self._music_track is None:
            return
        pygame.mixer.music.fadeout(fade_ms)
        self._music_track = None

    # -- volume control ---------------------------------------------------------

    def _category_volume(self, category: str) -> float:
        return {
            "engine": self.engine_volume,
            "weather": self.weather_volume,
            "ui": self.ui_volume,
        }.get(category, self.sfx_volume)

    def set_volumes(
        self,
        master: float | None = None,
        sfx: float | None = None,
        music: float | None = None,
        weather: float | None = None,
        engine: float | None = None,
        ui: float | None = None,
    ) -> None:
        if master is not None:
            self.master_volume = max(0.0, min(1.0, master))
        if sfx is not None:
            self.sfx_volume = max(0.0, min(1.0, sfx))
        if music is not None:
            self.music_volume = max(0.0, min(1.0, music))
        if weather is not None:
            self.weather_volume = max(0.0, min(1.0, weather))
        if engine is not None:
            self.engine_volume = max(0.0, min(1.0, engine))
        if ui is not None:
            self.ui_volume = max(0.0, min(1.0, ui))
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
            BASS_ATTRIB_PAN,
            BASS_ATTRIB_VOL,
            BASS_POS_BYTE,
            BASS_ChannelBytes2Seconds,
            BASS_ChannelGetLength,
            BASS_ChannelSetAttribute,
            BASS_ChannelSlideAttribute,
        )
        from sound_lib.main import BassError, bass_call
        from sound_lib.output import Output
        from sound_lib.stream import FileStream

        self._FileStream = FileStream
        self._BassError = BassError
        self._bass_call = bass_call
        self._slide = BASS_ChannelSlideAttribute
        self._set_attr = BASS_ChannelSetAttribute
        self._get_length = BASS_ChannelGetLength
        self._bytes2seconds = BASS_ChannelBytes2Seconds
        self._POS_BYTE = BASS_POS_BYTE
        self._ATTRIB_FREQ = BASS_ATTRIB_FREQ
        self._ATTRIB_VOL = BASS_ATTRIB_VOL
        self._ATTRIB_PAN = BASS_ATTRIB_PAN

        self.master_volume = 1.0
        self.sfx_volume = 0.8
        self.music_volume = 0.5
        self.weather_volume = 0.65
        self.engine_volume = 0.55
        self.ui_volume = 0.9
        self._loops: dict[int, tuple[str, float, object]] = {}  # slot -> (key, gain, stream)
        self._sustains: dict[int, SustainLoop] = {}  # slot -> active sustain loop
        # slot -> (key, stream) still ringing out its release tail after a
        # release. Tracked so a repeat press cannot stack a second overlapping
        # sound on top of the tail.
        self._releasing: dict[int, tuple[str, object]] = {}
        self._retained: list = []  # streams kept alive until BASS finishes them
        self._music_track: str | None = None
        self._music_stream = None
        self._engine_running = False
        self._engine_stream = None
        self._engine_base_freq = 0.0
        self._engine_intro_stream = None  # ignition one-shot, kept for the crossfade
        self._engine_intro_gain = 1.0  # crossfade multiplier on the engine loop
        self._engine_intro_load = 0.0  # ignition load boost: 1.0 forces full load
        self._engine_starting = False  # True only during the ignition crossfade
        self._engine_last_rpm = ENGINE_RPM_IDLE
        self._fades = FadeScheduler()

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

    def _stream(self, data: bytes, label: str, looping: bool):
        """A fresh memory stream for one playback; autofreed once it stops.

        Memory streams sidestep BASS filename-encoding quirks entirely and
        work identically for packed and loose assets.
        """
        try:
            stream = self._FileStream(
                mem=True, file=data, length=len(data), autofree=True, unicode=False
            )
        except self._BassError:
            log.warning("Could not open stream: %s", label, exc_info=True)
            return None
        # BASS reads the buffer during playback; pin it to the wrapper so it
        # lives exactly as long as the stream object is retained.
        stream._ff_data = data
        if looping:
            stream.set_looping(True)
        return stream

    def _sfx_stream(self, key: str, looping: bool = False):
        found = _asset_bytes(key, ("ogg", "wav"))
        if found is None:
            log.warning("Missing sound: %s", key)
            return None
        return self._stream(found[0], key, looping)

    def _retain(self, stream) -> None:
        """Keep a reference until BASS finishes with the stream.

        ``Channel.__del__`` frees the BASS handle when the Python object is
        garbage collected, which would cut one-shots and fade-outs short the
        moment the last reference is dropped. Finished streams (autofreed by
        BASS) are pruned on each call.
        """
        alive = []
        for s in self._retained:
            try:
                if s.is_playing:
                    alive.append(s)
            except self._BassError:
                pass  # already stopped and autofreed
        alive.append(stream)
        self._retained = alive

    def _fade_out(self, stream, fade_ms: int) -> None:
        """Slide volume to -1: BASS stops (and autofrees) the channel at 0."""
        try:
            self._bass_call(
                self._slide, stream.handle, self._ATTRIB_VOL, -1.0, max(0, int(fade_ms))
            )
        except self._BassError:
            log.debug("Fade-out failed; stream already gone", exc_info=True)
            return
        self._retain(stream)  # keep it alive for the duration of the fade

    # -- one-shots ----------------------------------------------------------

    def play(self, key: str, volume: float = 1.0, pan: float = 0.0) -> None:
        stream = self._sfx_stream(key)
        if stream is None:
            return
        try:
            stream.set_volume(
                max(
                    0.0,
                    min(
                        1.0,
                        volume
                        * self._category_volume(_one_shot_category(key))
                        * self.master_volume,
                    ),
                )
            )
            if pan:
                self._bass_call(
                    self._set_attr, stream.handle, self._ATTRIB_PAN, max(-1.0, min(1.0, pan))
                )
            stream.play()
        except self._BassError:
            log.warning("Could not play %s", key, exc_info=True)
            return
        self._retain(stream)

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
        releasing = self._releasing.pop(channel, None)
        if releasing is not None:
            self._fade_out(releasing[1], fade_ms)  # cut the ringing-out tail too
        sustain = self._sustains.pop(channel, None)
        if sustain is not None:
            sustain.stop()
        entry = self._loops.pop(channel, None)
        if entry is not None:
            self._fade_out(entry[2], fade_ms)

    def _release_tail_playing(self, channel: int, key: str) -> bool:
        """True while ``channel`` is still ringing out a release tail of ``key``."""
        entry = self._releasing.get(channel)
        if entry is None:
            return False
        rkey, stream = entry
        try:
            playing = stream.is_playing
        except self._BassError:
            playing = False
        if not playing:
            self._releasing.pop(channel, None)
            return False
        return rkey == key

    def start_sustain_loop(
        self,
        channel: int,
        key: str,
        loop_start: float,
        loop_end: float,
        *,
        units: str = "samples",
        volume: float = 1.0,
    ) -> None:
        """Play ``key`` and loop only the interior ``[loop_start, loop_end)``.

        The attack (before ``loop_start``) plays once, then the region repeats
        seamlessly until :meth:`release_sustain_loop`. Loop points are in
        samples or seconds per ``units``. A repeat call while the same key is
        already sounding on ``channel`` -- held or ringing out its release tail
        -- is ignored, so presses never stack.
        """
        current = self._loops.get(channel)
        if current and current[0] == key and channel in self._sustains:
            self.set_loop_volume(channel, volume)
            return
        if self._release_tail_playing(channel, key):
            return
        if current:
            self.stop_loop(channel, fade_ms=0)
        stream = self._sfx_stream(key, looping=False)
        if stream is None:
            return
        try:
            sustain = SustainLoop(stream, loop_start, loop_end, units=units)
        except Exception:
            log.warning("Could not set loop points for %s", key, exc_info=True)
            return
        self._releasing.pop(channel, None)
        self._loops[channel] = (key, volume, stream)
        self._sustains[channel] = sustain
        try:
            stream.set_volume(0.0)
            stream.play()
        except self._BassError:
            del self._loops[channel]
            del self._sustains[channel]
            return
        self._apply_loop_volume(channel)

    def release_sustain_loop(self, channel: int, fade_ms: int = 0) -> None:
        """Stop looping ``channel`` and let its release tail play to the end.

        Playback continues from wherever it is, past the loop end, through the
        tail; BASS autofrees the stream at EOF. ``fade_ms`` optionally fades the
        tail out (0 keeps the natural release at full volume).
        """
        sustain = self._sustains.pop(channel, None)
        if sustain is None:
            # No sustain loop here; fall back to a plain stop so callers can use
            # release/stop interchangeably on a channel.
            self.stop_loop(channel, fade_ms=fade_ms)
            return
        sustain.release()
        entry = self._loops.pop(channel, None)
        if entry is None:
            return
        key, _gain, stream = entry
        if fade_ms > 0:
            self._fade_out(stream, fade_ms)
        else:
            # Hand the stream to the retain list so dropping the _loops
            # reference does not free it mid-tail; BASS autofrees it at EOF.
            self._retain(stream)
        # Remember the tail so a repeat press during it does not stack a horn.
        self._releasing[channel] = (key, stream)

    def reverse_start(self) -> None:
        self.start_loop(CH_REVERSE, "vehicle/reverse", volume=0.4, fade_ms=80)

    def reverse_stop(self) -> None:
        self.stop_loop(CH_REVERSE, fade_ms=80)

    def _apply_loop_volume(self, channel: int, fade_ms: int = 0) -> None:
        if channel not in self._loops:
            return
        _, gain, stream = self._loops[channel]
        vol = max(
            0.0,
            min(1.0, gain * self._category_volume(_loop_category(channel)) * self.master_volume),
        )
        try:
            if fade_ms > 0:
                self._bass_call(self._slide, stream.handle, self._ATTRIB_VOL, vol, int(fade_ms))
            else:
                stream.set_volume(vol)
        except self._BassError:
            del self._loops[channel]

    # -- truck engine: one loop, frequency tracks RPM ------------------------------

    def engine_start(self, play_start_sound: bool = True) -> None:
        if self._engine_running:
            return
        self._engine_running = True
        self._fades.clear()
        # Hold the loop silent while the ignition one-shot plays; crossfade it
        # up at the tail. A silent (resume) start skips the crank.
        self._engine_intro_gain = 0.0
        self._engine_intro_load = 0.0
        if play_start_sound:
            self._begin_engine_start_crossfade()
        else:
            self._fades.add(
                Fade(
                    self._set_engine_intro_gain,
                    0.0,
                    1.0,
                    ENGINE_RESUME_FADE_S,
                    curve=ENGINE_START_FADE_IN_CURVE,
                )
            )
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

    def _begin_engine_start_crossfade(self) -> None:
        """Play ``engine/start`` at full volume and blend into the loop at its tail."""
        self._engine_starting = True
        stream = self._sfx_stream("engine/start")
        if stream is None:
            self._fades.add(
                Fade(
                    self._set_engine_intro_gain,
                    0.0,
                    1.0,
                    ENGINE_RESUME_FADE_S,
                    on_done=self._end_engine_starting,
                )
            )
            return
        base = max(0.0, min(1.0, self._category_volume("engine") * self.master_volume))
        try:
            stream.set_volume(base)
            stream.play()
        except self._BassError:
            log.warning("Could not play engine/start", exc_info=True)
            self._fades.add(
                Fade(
                    self._set_engine_intro_gain,
                    0.0,
                    1.0,
                    ENGINE_RESUME_FADE_S,
                    on_done=self._end_engine_starting,
                )
            )
            return
        self._retain(stream)
        self._engine_intro_stream = stream
        clip_len = self._stream_length_s(stream)
        delay = max(0.0, clip_len - ENGINE_START_CROSSFADE_S) if ENGINE_START_TAIL_ANCHOR else 0.0
        # Boost the loop to full (crank) load through the handoff so it meets the
        # crank tail at the same level instead of the quieter off-throttle idle.
        self._engine_intro_load = 1.0

        def fade_crank(m: float) -> None:
            with contextlib.suppress(self._BassError):
                stream.set_volume(base * m)

        self._fades.add(
            Fade(
                fade_crank,
                1.0,
                0.0,
                ENGINE_START_CROSSFADE_S,
                curve=ENGINE_START_FADE_OUT_CURVE,
                delay_s=delay,
            )
        )
        self._fades.add(
            Fade(
                self._set_engine_intro_gain,
                0.0,
                1.0,
                ENGINE_START_CROSSFADE_S,
                curve=ENGINE_START_FADE_IN_CURVE,
                delay_s=delay,
                on_done=self._end_engine_starting,
            )
        )
        # Once the crossfade completes, ease the load boost back off so the loop
        # settles to its real off-throttle volume.
        self._fades.add(
            Fade(
                self._set_engine_intro_load,
                1.0,
                0.0,
                ENGINE_START_SETTLE_S,
                curve=ENGINE_START_SETTLE_CURVE,
                delay_s=delay + ENGINE_START_CROSSFADE_S,
            )
        )

    def _stream_length_s(self, stream) -> float:
        """Length of a stream in seconds, or a safe fallback."""
        try:
            length_bytes = self._bass_call(self._get_length, stream.handle, self._POS_BYTE)
            return float(self._bass_call(self._bytes2seconds, stream.handle, length_bytes))
        except self._BassError:
            return ENGINE_START_ASSUMED_LEN_S

    def _set_engine_intro_gain(self, gain: float) -> None:
        self._engine_intro_gain = max(0.0, min(1.0, gain))
        self.set_engine_rpm(self._engine_last_rpm)

    def _set_engine_intro_load(self, value: float) -> None:
        self._engine_intro_load = max(0.0, min(1.0, value))
        self.set_engine_rpm(self._engine_last_rpm)

    def _end_engine_starting(self) -> None:
        self._engine_starting = False

    def update(self, dt: float) -> None:
        self._fades.update(dt)

    def engine_stop(self, shutdown_sound: bool = True) -> None:
        self.reverse_stop()
        if not self._engine_running:
            return
        self._engine_running = False
        self._fades.clear()
        self._engine_intro_gain = 1.0
        self._engine_intro_load = 0.0
        self._engine_starting = False
        self._engine_intro_stream = None
        if self._engine_stream is not None:
            self._fade_out(self._engine_stream, 250)
            self._engine_stream = None
        if shutdown_sound:
            self.play("engine/shutdown")

    def set_engine_rpm(self, rpm: float, throttle: float = 0.0) -> None:
        """Slide the engine loop's playback frequency to track RPM."""
        if not (self._engine_running and self._engine_stream is not None):
            return
        self._engine_last_rpm = rpm
        target = self._engine_base_freq * engine_freq_mult(rpm)
        load_gain = engine_load_gain(throttle)
        # During the ignition handoff, boost load toward full so the loop meets
        # the crank tail; the boost eases back to 0 afterward.
        load_gain += self._engine_intro_load * (1.0 - load_gain)
        vol = max(
            0.0,
            min(
                1.0,
                ENGINE_LOOP_GAIN
                * load_gain
                * self.engine_volume
                * self.master_volume
                * self._engine_intro_gain,
            ),
        )
        try:
            self._bass_call(
                self._slide, self._engine_stream.handle, self._ATTRIB_FREQ, target, ENGINE_SLIDE_MS
            )
            self._engine_stream.set_volume(vol)
        except self._BassError:
            self._engine_stream = None

    @property
    def engine_running(self) -> bool:
        return self._engine_running

    @property
    def engine_starting(self) -> bool:
        return self._engine_starting

    # -- music ----------------------------------------------------------------

    def play_music(self, track: str, fade_ms: int = 1500) -> None:
        if self._music_track == track:
            return
        found = _asset_bytes(f"music/{track}", ("ogg", "wav"))
        if found is None:
            log.warning("Missing music track: %s", track)
            return
        if self._music_stream is not None:
            self._fade_out(self._music_stream, 800)
            self._music_stream = None
            self._music_track = None
        stream = self._stream(found[0], track, looping=False)
        if stream is None:
            return
        try:
            stream.set_volume(0.0)
            stream.play()
            self._bass_call(
                self._slide,
                stream.handle,
                self._ATTRIB_VOL,
                max(0.0, min(1.0, self.music_volume * self.master_volume)),
                max(0, int(fade_ms)),
            )
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

    def _category_volume(self, category: str) -> float:
        return {
            "engine": self.engine_volume,
            "weather": self.weather_volume,
            "ui": self.ui_volume,
        }.get(category, self.sfx_volume)

    def set_volumes(
        self,
        master: float | None = None,
        sfx: float | None = None,
        music: float | None = None,
        weather: float | None = None,
        engine: float | None = None,
        ui: float | None = None,
    ) -> None:
        if master is not None:
            self.master_volume = max(0.0, min(1.0, master))
        if sfx is not None:
            self.sfx_volume = max(0.0, min(1.0, sfx))
        if music is not None:
            self.music_volume = max(0.0, min(1.0, music))
        if weather is not None:
            self.weather_volume = max(0.0, min(1.0, weather))
        if engine is not None:
            self.engine_volume = max(0.0, min(1.0, engine))
        if ui is not None:
            self.ui_volume = max(0.0, min(1.0, ui))
        for ch in list(self._loops):
            self._apply_loop_volume(ch)
        if self._engine_stream is not None:
            try:
                self._engine_stream.set_volume(
                    max(
                        0.0,
                        min(
                            1.0,
                            ENGINE_LOOP_GAIN
                            * self.engine_volume
                            * self.master_volume
                            * self._engine_intro_gain,
                        ),
                    )
                )
            except self._BassError:
                self._engine_stream = None
        if self._music_stream is not None:
            try:
                self._music_stream.set_volume(
                    max(0.0, min(1.0, self.music_volume * self.master_volume))
                )
            except self._BassError:
                self._music_stream = None

    def shutdown(self) -> None:
        self._fades.clear()
        for ch in list(self._loops):
            self.stop_loop(ch, fade_ms=0)
        self.engine_stop(shutdown_sound=False)
        self.stop_music(fade_ms=0)
        self._retained.clear()
        with contextlib.suppress(self._BassError):
            self._output.free()
        self.enabled = False


class _NullBackend:
    """Last resort: every primitive is a no-op."""

    name = "none"
    enabled = False
    engine_running = False
    engine_starting = False

    def __init__(self) -> None:
        self.master_volume = 1.0
        self.sfx_volume = 0.8
        self.music_volume = 0.5
        self.weather_volume = 0.65
        self.engine_volume = 0.55
        self.ui_volume = 0.9

    def play(self, key: str, volume: float = 1.0, pan: float = 0.0) -> None: ...
    def start_loop(
        self, channel: int, key: str, volume: float = 1.0, fade_ms: int = 300
    ) -> None: ...
    def set_loop_volume(self, channel: int, volume: float) -> None: ...
    def stop_loop(self, channel: int, fade_ms: int = 300) -> None: ...
    def start_sustain_loop(
        self,
        channel: int,
        key: str,
        loop_start: float,
        loop_end: float,
        *,
        units: str = "samples",
        volume: float = 1.0,
    ) -> None: ...
    def release_sustain_loop(self, channel: int, fade_ms: int = 0) -> None: ...
    def engine_start(self, play_start_sound: bool = True) -> None: ...
    def engine_stop(self, shutdown_sound: bool = True) -> None: ...
    def set_engine_rpm(self, rpm: float, throttle: float = 0.0) -> None: ...
    def update(self, dt: float) -> None: ...
    def reverse_start(self) -> None: ...
    def reverse_stop(self) -> None: ...
    def play_music(self, track: str, fade_ms: int = 1500) -> None: ...
    def stop_music(self, fade_ms: int = 1000) -> None: ...
    def set_volumes(
        self,
        master: float | None = None,
        sfx: float | None = None,
        music: float | None = None,
        weather: float | None = None,
        engine: float | None = None,
        ui: float | None = None,
    ) -> None:
        if master is not None:
            self.master_volume = max(0.0, min(1.0, master))
        if sfx is not None:
            self.sfx_volume = max(0.0, min(1.0, sfx))
        if music is not None:
            self.music_volume = max(0.0, min(1.0, music))
        if weather is not None:
            self.weather_volume = max(0.0, min(1.0, weather))
        if engine is not None:
            self.engine_volume = max(0.0, min(1.0, engine))
        if ui is not None:
            self.ui_volume = max(0.0, min(1.0, ui))

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
                log.warning(
                    "sound_lib/BASS unavailable; falling back to pygame.mixer", exc_info=True
                )
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

    @property
    def weather_volume(self) -> float:
        return self._impl.weather_volume

    @property
    def engine_volume(self) -> float:
        return self._impl.engine_volume

    @property
    def ui_volume(self) -> float:
        return self._impl.ui_volume

    # -- one-shots and loops ------------------------------------------------------

    def play(self, key: str, volume: float = 1.0, pan: float = 0.0) -> None:
        """Play a one-shot. ``pan`` -1.0 = full left, 0 = center, 1.0 = right."""
        self._impl.play(key, volume, pan)

    def start_loop(self, channel: int, key: str, volume: float = 1.0, fade_ms: int = 300) -> None:
        self._impl.start_loop(channel, key, volume, fade_ms)

    def set_loop_volume(self, channel: int, volume: float) -> None:
        self._impl.set_loop_volume(channel, volume)

    def stop_loop(self, channel: int, fade_ms: int = 300) -> None:
        self._impl.stop_loop(channel, fade_ms)

    def start_sustain_loop(
        self,
        channel: int,
        key: str,
        loop_start: float,
        loop_end: float,
        *,
        units: str = "samples",
        volume: float = 1.0,
    ) -> None:
        """Loop only the interior ``[loop_start, loop_end)`` of ``key``.

        The attack before ``loop_start`` plays once, then the region repeats
        until :meth:`release_sustain_loop`, which lets the release tail after
        ``loop_end`` play out. Loop points are in ``"samples"`` or ``"seconds"``
        per ``units``. Ideal for held sounds (a horn, a siren) that should
        sustain naturally and ring out on release.
        """
        self._impl.start_sustain_loop(
            channel, key, loop_start, loop_end, units=units, volume=volume
        )

    def release_sustain_loop(self, channel: int, fade_ms: int = 0) -> None:
        """Stop looping ``channel`` and let its release tail play to the end."""
        self._impl.release_sustain_loop(channel, fade_ms)

    # -- truck engine ----------------------------------------------------------------

    def engine_start(self, play_start_sound: bool = True) -> None:
        """Start the engine audio.

        ``play_start_sound`` True (a deliberate ignition) plays the ignition
        one-shot and crossfades it into the idle loop at the clip's tail.
        Pass False to bring the running-engine loop up silently -- e.g. when
        resuming a saved trip whose engine was already on, or returning from an
        in-trip menu -- so the crank never replays.
        """
        self._impl.engine_start(play_start_sound)

    def engine_stop(self, shutdown_sound: bool = True) -> None:
        self.reverse_stop()
        self._impl.engine_stop(shutdown_sound)

    def update(self, dt: float) -> None:
        """Advance time-based audio fades. Call once per frame from the main loop."""
        self._impl.update(dt)

    def set_engine_rpm(self, rpm: float, throttle: float = 0.0) -> None:
        self._impl.set_engine_rpm(rpm, throttle)

    @property
    def engine_running(self) -> bool:
        return self._impl.engine_running

    @property
    def engine_starting(self) -> bool:
        """True while a deliberate ignition is still crossfading into the loop."""
        return self._impl.engine_starting

    # -- road / weather / ambience --------------------------------------------

    def set_road_noise(self, speed_mps: float) -> None:
        """Tire-on-asphalt loop whose volume tracks speed."""
        if not self.enabled:
            return
        gain = min(1.0, speed_mps / 30.0)
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
            self.start_loop(CH_WEATHER_B, "weather/wind", volume=min(1.0, intensity), fade_ms=1500)

    def set_ambient(self, key: str | None, volume: float = 1.0) -> None:
        if key is None:
            self.stop_loop(CH_AMBIENT, fade_ms=800)
        else:
            self.start_loop(CH_AMBIENT, key, volume=volume, fade_ms=800)

    def horn_start(self) -> None:
        self.start_sustain_loop(
            CH_HORN,
            "vehicle/horn",
            HORN_LOOP_START,
            HORN_LOOP_END,
            units="samples",
            volume=1.0,
        )

    def horn_stop(self) -> None:
        # Let the horn's natural release ring out instead of cutting it short.
        self.release_sustain_loop(CH_HORN, fade_ms=0)

    def reverse_start(self) -> None:
        self._impl.reverse_start()

    def reverse_stop(self) -> None:
        self._impl.reverse_stop()

    def stop_world(self) -> None:
        """Stop engine, road, weather, and ambience (leaving UI sfx alone)."""
        self.engine_stop(shutdown_sound=False)
        for ch in (CH_ROAD, CH_WEATHER, CH_WEATHER_B, CH_AMBIENT, CH_HORN):
            self.stop_loop(ch, fade_ms=400)

    # -- music ----------------------------------------------------------------

    def play_music(self, track: str, fade_ms: int = 1500) -> None:
        """Stream a music track, e.g. ``play_music("menu_theme")``."""
        self._impl.play_music(track, fade_ms)

    def stop_music(self, fade_ms: int = 1000) -> None:
        self._impl.stop_music(fade_ms)

    # -- volume control ---------------------------------------------------------

    def set_volumes(
        self,
        master: float | None = None,
        sfx: float | None = None,
        music: float | None = None,
        weather: float | None = None,
        engine: float | None = None,
        ui: float | None = None,
    ) -> None:
        self._impl.set_volumes(master, sfx, music, weather, engine, ui)

    def shutdown(self) -> None:
        self._impl.shutdown()
