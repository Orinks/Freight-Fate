"""Runtime audio engine: sound effects, loops, engine audio, and music.

Two interchangeable backends sit behind the :class:`AudioEngine` facade:

* **BASS** (via ``sound_lib``) — the preferred backend. The truck engine is a
  multisample ring: one real cab loop per rpm band, crossfaded equal-power
  with per-band playback-rate tracking (BASS attribute slides). When the
  licensed cuts are absent it falls back to the single idle loop pitched up
  with RPM. With no audio device (headless CI) it initializes BASS's
  "no sound" device, so the full code path still runs silently.
* **pygame.mixer** — automatic fallback when sound_lib/BASS cannot
  initialize. Crossfades the same four bands at their native pitch.

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
import math
import os
import random
import struct
import sys
import threading
import time
import wave
from pathlib import Path

import pygame

from . import assets_pack, cab_filter
from .audio_fades import Fade, FadeScheduler
from .audio_loops import SustainLoop, to_seconds

log = logging.getLogger(__name__)

ASSETS = Path(__file__).parent / "assets" / "sounds"
# Licensed sound-library overlay (gitignored, never committed). A machine that
# owns the purchased libraries drops encoded assets here under the same keys;
# they take precedence over the committed tree, so a clean clone still runs on
# the synthesized fallbacks. Release builds bake the overlay into sounds.pak.
ASSETS_LICENSED = Path(__file__).parent / "assets" / "sounds-licensed"

# BASS addon plugins shipped with the game. BASSHLS teaches BASS to open
# HTTP Live Streaming radio URLs (the AFN 360 Global channels); core BASS
# already handles plain Shoutcast/Icecast streams on its own.
PLUGIN_LIB = Path(__file__).parent / "lib"


def _bass_plugin_names() -> tuple[str, ...]:
    if sys.platform == "win32":
        return ("basshls.dll",)
    if sys.platform == "darwin":
        return ("libbasshls.dylib",)
    return ("libbasshls.so",)


# Reserved loop slots. The pygame backend maps them onto mixer channels;
# the BASS backend uses them as keys for its stream table.
CH_ENGINE = (0, 1, 2, 3, 4)  # the engine band crossfade ring (pygame only)
CH_ROAD = 5
CH_WEATHER = 6
CH_WEATHER_B = 7
CH_AMBIENT = 8
CH_HORN = 9
CH_REVERSE = 10
CH_AIR = 11  # compressor charging the tanks below governor release
CH_BRAKE = 12  # brake-release air bleed: the hiss bed shaped per release
CH_JAKE = 13  # engine-brake growl: synthesized loop, stage- and rpm-keyed
CH_RADIO_FX = 14  # FM fringe hiss bed under a thinning station
CH_EDGE = 15  # edge-boundary ladder loops: clip / strip / shoulder textures
CH_ALERT = 16  # continuous alert tones: the stop bar's solid zone
CH_SIREN = 17  # the held enforcement siren, panned and levelled to the cruiser
CH_SCALE = 18  # weigh-station approach bed, swelling on real seconds
CH_SURGE = 19  # liquid running in a tank trailer: gated, silent on other freight
# Everything above must be inside the reservation. set_reserved(n) protects
# channels 0..n-1 from find_channel, and this sat at 14 while CH_RADIO_FX,
# CH_EDGE and CH_ALERT were added above it -- so on the pygame fallback a
# burst of one-shots could evict the FM fringe bed, the edge ladder, or the
# stop bar's held tone mid-warning. Guidance a blind driver is steering by
# must never be stealable: keep this one past the last named slot.
RESERVED = CH_SURGE + 1
NUM_CHANNELS = 32

# A held alert tone is a dead man's switch. Its owner re-asserts it every
# frame through hold_alert, and it stops on its own the moment that stops --
# a menu opening over the drive, the moment it warned about ending, an owner
# that lost track of it. A continuous tone in a blind player's headphones
# must never be able to outlive the thing it is warning about: the stop bar's
# solid tone once ran until the game was killed (Shane, 2026-08-03).
ALERT_HOLD_TIMEOUT_S = 0.4

# Horn sustain loop points (samples, at the asset's 44100 Hz). The horn is an
# attack -> sustain -> release sound: play the attack, loop this tuned interior
# region while the key/button is held, then let the release tail ring out.
HORN_LOOP_START = 11816
HORN_LOOP_END = 12379

# The multisample engine voice: one steady cab loop per band, cut from the
# real 896 recording at these native rpms. Both backends crossfade the ring
# with ``engine_band_weights``; the BASS backend additionally slides each
# band's playback rate to track rpm inside the band (see ENGINE_BAND_RATE_*).
ENGINE_BANDS = (
    ("engine/idle", 680.0),
    ("engine/low", 950.0),
    ("engine/mid", 1150.0),
    ("engine/midhigh", 1425.0),
    ("engine/high", 1900.0),
)
ENGINE_BAND_KEYS = frozenset(key for key, _native in ENGINE_BANDS)
# Crossfades live in a narrow window around each adjacent pair's GEOMETRIC
# midpoint (log-space), this fraction of the gap wide. Two things follow:
# a cut never plays far from its recorded speed (rate excursions stay under
# ~16 percent -- past that the moving formants smear, the launch-pull
# weirdness the owner heard), and the two members of a blend always track
# the same rpm honestly, so there is no clamped-versus-tracking pitch clash
# (the ~10 Hz "stop-start" beat at 1700-1800 under the old full-gap fade).
ENGINE_XFADE_LOG_FRAC = 0.30
# Safety clamp only -- the windows above keep normal tracking well inside.
# 0.78 covers the widest pair's window edge (the 950 cut entering at ~764);
# 1.30 up lets the 1800 cut reach redline (2200/1800 = 1.22).
ENGINE_BAND_RATE_MIN = 0.78
ENGINE_BAND_RATE_MAX = 1.30

# Legacy BASS engine model: one idle loop, pitched up with RPM. Still the
# fallback when the licensed multisample cuts are absent (a clean clone has
# only the synthesized engine/idle).
ENGINE_LOOP_KEY = "engine/idle"
# The classic voice: the 1.8.x recording under its own key, because the
# licensed overlay owns "engine/idle" -- when the rebuilt cuts are installed
# the shared key IS the rebuilt idle, and the Settings "classic" promise
# (the original engine sound) must not quietly follow it.
ENGINE_CLASSIC_LOOP_KEY = "engine_classic/idle"
ENGINE_RPM_IDLE = 600.0
ENGINE_RPM_MAX = 2200.0
ENGINE_FREQ_MAX_MULT = 1.75
ENGINE_SLIDE_MS = 120
# A large rpm jump is a shift re-entry: the engine is ALREADY at the new
# speed when the clutch hooks up, so the voice must step, not glide -- the
# 120 ms slide across a 400 rpm drop reads as a little meow on every shift,
# machine-gunned through a launch (owner's ear, 2026-07-22).
ENGINE_SLIDE_SNAP_MS = 25
ENGINE_SLIDE_SNAP_RPM = 150.0
ENGINE_LOOP_GAIN = 1.0
# Loop-repetition camouflage (owner + outside review, 2026-07-27): even a
# seam-clean 1-2 s loop is recognizable -- the ear locks onto its spectral
# fingerprint recurring at a perfectly fixed period. Each band's playback
# rate and gain take a slow, bounded random walk, so the loop period is
# never exactly the same twice and the recurrence stops landing where the
# ear predicted. Rate stays within ~5 cents (well under the formant-smear
# threshold); gain within ~0.5 dB. BASS ring only -- the pygame fallback
# has no per-channel rate control.
ENGINE_WOBBLE_RATE_MAX = 0.003  # +/- fraction of playback rate (~5 cents)
ENGINE_WOBBLE_RATE_STEP = 0.004  # random-walk speed, fraction per second
ENGINE_WOBBLE_GAIN_MAX = 0.06  # +/- fraction of band gain (~0.5 dB)
ENGINE_WOBBLE_GAIN_STEP = 0.10

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

# How far the ducked channels (engine, weather, and the music slot the radio
# rides) drop while the event voice speaks, when the Settings > Audio option
# is on: half volume, the modest broadcast-style duck -- the road stays
# present, the words win (XAG 105; speech priority research, R13).
SPEECH_DUCK_LEVEL = 0.5

BASS_NO_SOUND_DEVICE = 0

# Radio streaming (BASS only). Opening a URL blocks until the server answers;
# on a station that has gone dark that is the operating system's own TCP
# timeout, far longer than a player will wait and far too long to spend
# inside a frame. The connect runs on a worker thread, bounded by these.
# (Pattern from PR #150 by CatalystForChaos.)
RADIO_CONNECT_TIMEOUT_MS = 8000  # give up on a station that will not answer
RADIO_READ_TIMEOUT_MS = 10000  # and on one that answers then stalls
# How long shutdown waits for a connect still in flight before freeing BASS.
RADIO_SHUTDOWN_JOIN_S = 2.0


def _asset_path(key: str, extensions: tuple[str, ...]) -> Path | None:
    """Loose-file lookup; source checkouts and asset tooling only."""
    for root in (ASSETS_LICENSED, ASSETS):
        for ext in extensions:
            path = root / f"{key}.{ext}"
            if path.exists():
                return path
    return None


def _pack_carries_whole_ring(pack) -> bool:
    """Whether ``pack`` holds every engine band cut.

    Cached on the pack itself; membership only, so nothing is decompressed.
    """
    complete = getattr(pack, "_ff_whole_ring", None)
    if complete is None:
        complete = all(
            any(pack.has(f"{key}.{ext}") for ext in ("ogg", "wav")) for key in ENGINE_BAND_KEYS
        )
        pack._ff_whole_ring = complete
    return complete


# Sounds the game synthesizes at runtime rather than shipping. Registered
# under an ordinary sound key, so play/start_loop reach them through the same
# path as a packed asset on every backend. Deterministic by construction: the
# generator is pure arithmetic, so the same build always produces the same
# bytes. Used for the enforcement signature, whose whole job is to be a shape
# nothing else in the game -- and nothing a radio station can broadcast --
# already occupies.
_GENERATED: dict[str, tuple[bytes, str]] = {}

# Measured playing times, by sound key. See asset_length_s below.
_LENGTHS: dict[str, float] = {}


def register_generated_sound(key: str, data: bytes, ext: str = "wav") -> None:
    """Publish synthesized audio under ``key`` for every backend."""
    _GENERATED[key] = (data, ext)
    _LENGTHS.pop(key, None)  # anything measured before this was measuring nothing
    _CAB_SEALED.pop(key, None)  # and any sealed render of the old bytes with it


def generated_sound_keys() -> tuple[str, ...]:
    return tuple(sorted(_GENERATED))


def _asset_bytes(key: str, extensions: tuple[str, ...]) -> tuple[bytes, str] | None:
    """Bytes and extension for a sound key, from the shipped pack or loose files.

    Frozen builds carry the sounds packed into ``sounds.pak``
    (see ``assets_pack``); source checkouts read the editable
    ``assets/sounds`` tree.

    The engine bands are the one exception to pack-then-loose: they crossfade
    into each other, so they have to come from one recording. A pack that
    predates the checkout beside it would otherwise serve four bands from the
    pack and the fifth off disk, blending two different engines. Unless the
    pack carries the whole ring, the ring reads from the loose tree.
    """
    generated = _GENERATED.get(key)
    if generated is not None:
        return generated
    pack = assets_pack.open_default()
    if pack is not None and key in ENGINE_BAND_KEYS and not _pack_carries_whole_ring(pack):
        pack = None
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


# Engine band cuts with the sealed-cab transfer applied, by key. The transfer
# is deterministic and the cuts change only on a repack, so sealing each cut
# once per process is enough for every engine start after the first.
_CAB_SEALED: dict[str, tuple[bytes, str]] = {}


def _playback_bytes(key: str, extensions: tuple[str, ...]) -> tuple[bytes, str] | None:
    """Bytes for a sound as the player should HEAR it.

    The engine band cuts pass through the sealed-cab transfer
    (``cab_filter``, owner's ear 2026-08-13): the recorded voice reads as a
    truck heard from outside, and the cab between engine and ear is applied
    here, at load, rather than baked into assets -- feedback rounds are
    parameter tweaks. The classic voice's ogg keeps its old sound untouched,
    and non-engine keys pass straight through.
    """
    if key not in ENGINE_BAND_KEYS:
        return _asset_bytes(key, extensions)
    cached = _CAB_SEALED.get(key)
    if cached is not None:
        return cached
    found = _asset_bytes(key, extensions)
    if found is not None and found[1] == "wav":
        found = (cab_filter.seal_wav(found[0]), "wav")
    if found is not None:
        _CAB_SEALED[key] = found
    return found


def _wav_seconds(data: bytes) -> float:
    with contextlib.closing(wave.open(io.BytesIO(data), "rb")) as clip:
        rate = clip.getframerate()
        return clip.getnframes() / rate if rate > 0 else 0.0


def _ogg_seconds(data: bytes) -> float:
    """Playing time of an Ogg Vorbis stream, from its own page headers.

    The last page's granule position IS the final sample number, and the
    sample rate sits in the identification header on the first page, so the
    whole answer is two reads and a division -- no decoding, no backend, and
    the same number on a machine with no audio device at all.
    """
    first = data.find(b"OggS")
    if first < 0 or len(data) < first + 28:
        return 0.0
    packet = first + 27 + data[first + 26]  # page header, then its segment table
    if data[packet : packet + 7] != b"\x01vorbis":
        return 0.0
    (rate,) = struct.unpack_from("<I", data, packet + 12)
    last = data.rfind(b"OggS")
    if last < 0 or rate <= 0:
        return 0.0
    (granule,) = struct.unpack_from("<q", data, last + 6)
    return granule / rate if granule > 0 else 0.0


def asset_length_s(key: str) -> float:
    """How long the clip behind ``key`` sounds for, in seconds.

    Zero when the key resolves to nothing, or to a container this cannot
    measure. Cached, because callers ask about the same handful of keys
    repeatedly and the answer cannot change while the game is running.

    A one-shot handed to :meth:`AudioEngine.play` comes back with no handle,
    so a caller that needs to know when it has finished -- the Learn game
    sounds demo, which must not lay a second copy over the first -- has this
    and nothing else to go on.
    """
    cached = _LENGTHS.get(key)
    if cached is not None:
        return cached
    found = _asset_bytes(key, ("ogg", "wav"))
    seconds = 0.0
    if found is not None:
        data, ext = found
        try:
            seconds = _ogg_seconds(data) if ext == "ogg" else _wav_seconds(data)
        except Exception:  # noqa: BLE001 - an unreadable header is "unknown", never a crash
            log.warning("Could not measure the length of %s", key, exc_info=True)
            seconds = 0.0
    _LENGTHS[key] = seconds
    return seconds


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


def engine_band_weights(rpm: float, natives: tuple[float, ...]) -> tuple[float, ...]:
    """Crossfade weights for the engine band ring at ``rpm``.

    Below the first native rpm the first band carries alone, above the last
    the last does. Between neighbours, one band carries alone until the rpm
    enters the pair's narrow log-space window around their geometric
    midpoint (ENGINE_XFADE_LOG_FRAC of the gap); inside it the pair blends
    equal-power (the loops are uncorrelated recordings, so cos/sin keeps
    the summed level flat). The pure zones either side of each window are
    what keep every sounding cut close to its recorded speed.
    """
    n = len(natives)
    weights = [0.0] * n
    if rpm <= natives[0]:
        weights[0] = 1.0
    elif rpm >= natives[-1]:
        weights[-1] = 1.0
    else:
        for i in range(n - 1):
            if rpm <= natives[i + 1]:
                # Position within the gap in log space, remapped through the
                # centered window: below it the lower band is pure, above it
                # the upper band is pure.
                t = math.log(rpm / natives[i]) / math.log(natives[i + 1] / natives[i])
                half = ENGINE_XFADE_LOG_FRAC / 2.0
                s = (t - (0.5 - half)) / ENGINE_XFADE_LOG_FRAC
                if s <= 0.0:
                    weights[i] = 1.0
                elif s >= 1.0:
                    weights[i + 1] = 1.0
                else:
                    weights[i] = math.cos(s * math.pi / 2.0)
                    weights[i + 1] = math.sin(s * math.pi / 2.0)
                break
    return tuple(weights)


# Facility docks: big-room interiors get the warehouse loop, yards the gate.
_WAREHOUSE_FACILITY_TYPES = {"warehouse", "dry_warehouse", "cold_storage", "distribution"}


def facility_ambient_key(facility_type: str) -> str:
    if facility_type in _WAREHOUSE_FACILITY_TYPES:
        return "ambient/warehouse"
    return "poi/facility_gate"


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
    if key.startswith("enforcement/") or key == "events/police_siren":
        return "siren"
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
    if channel == CH_SIREN:
        # Off the shared sfx bus on purpose: a siren behind you is the one
        # sound in the game that must be raisable without dragging every
        # clunk, hiss and chime up with it.
        return "siren"
    return "sfx"


class _PygameBackend:
    """The original pygame.mixer implementation (engine band crossfade)."""

    name = "pygame"
    # While the event voice speaks, engine/weather/music step down to this
    # and back (see AudioEngine.set_speech_duck). Not a setting value:
    # settings own the volumes, this rides on top of them. A class default,
    # so the bare-__new__ backends tests build carry it too.
    speech_duck = 1.0

    def __init__(self) -> None:
        self.enabled = False
        self.master_volume = 1.0
        self.sfx_volume = 0.8
        self.music_volume = 0.5
        self.weather_volume = 0.65
        self.engine_volume = 0.55
        self.ui_volume = 0.9
        self.siren_volume = 1.0
        self._cache: dict[str, pygame.mixer.Sound] = {}
        self._loops: dict[int, tuple[str, float]] = {}  # channel -> (key, base gain)
        self._loop_pans: dict[int, float] = {}  # channel -> stereo pan, -1 left .. 1 right
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
        self._engine_last_throttle = 0.0
        self._engine_duck = 1.0  # shift-gap disengage: below the load floor
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
            found = _playback_bytes(key, ("ogg", "wav"))
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

    def set_loop_pan(self, channel: int, pan: float) -> None:
        self._loop_pans[channel] = max(-1.0, min(1.0, pan))
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
        self._loop_pans.pop(channel, None)

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
        pan = self._loop_pans.get(channel, 0.0)
        if pan:
            left = vol * (1.0 - max(0.0, pan))
            right = vol * (1.0 + min(0.0, pan))
            pygame.mixer.Channel(channel).set_volume(left, right)
        else:
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
        """Crossfade the engine band loops around the current RPM."""
        if not (self.enabled and self._engine_running):
            return
        self._engine_last_rpm = rpm
        self._engine_last_throttle = throttle
        load_gain = engine_load_gain(throttle)
        # During the ignition handoff, boost load toward full so the loop meets
        # the crank tail; the boost eases back to 0 afterward.
        load_gain += self._engine_intro_load * (1.0 - load_gain)
        weights = engine_band_weights(rpm, tuple(native for _key, native in ENGINE_BANDS))
        for i, w in enumerate(weights):
            self.set_loop_volume(
                CH_ENGINE[i],
                ENGINE_LOOP_GAIN * w * load_gain * self._engine_duck * self._engine_intro_gain,
            )

    def set_engine_duck(self, duck: float) -> None:
        """Shift-gap disengage: scale the engine bed below the load floor."""
        duck = max(0.0, min(1.0, duck))
        if duck == self._engine_duck:
            return
        self._engine_duck = duck
        self.set_engine_rpm(self._engine_last_rpm, self._engine_last_throttle)

    def set_road_noise(self, speed_mps: float) -> None:
        gain = min(1.0, speed_mps / 30.0)
        if gain < 0.02:
            self.stop_loop(CH_ROAD, fade_ms=500)
        else:
            self.start_loop(CH_ROAD, "vehicle/road", volume=gain, fade_ms=400)

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
        # Music ships as Opus (tools/encode_music_opus.py): far smaller for
        # background beds at the same perceived quality. Ogg stays in the
        # preference list so a partial migration and the effects tree, which
        # are still Vorbis, keep resolving.
        found = _asset_bytes(f"music/{track}", ("opus", "ogg", "wav"))
        if found is None:
            log.warning("Missing music track: %s", track)
            return
        data, ext = found
        try:
            buffer = io.BytesIO(data)
            pygame.mixer.music.load(buffer, namehint=ext)
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume * self.speech_duck)
            pygame.mixer.music.play(loops=0, fade_ms=fade_ms)
            self._music_track = track
            self._music_buffer = buffer
        except pygame.error:
            log.warning("Could not play music %s", track, exc_info=True)

    def play_radio_stream(self, url: str, fade_ms: int = 1500) -> None:
        raise RuntimeError("radio stream unavailable")

    def play_music_file(self, path: str, fade_ms: int = 1200) -> None:
        """Play one media file from disk on the music channel.

        Raises RuntimeError when the file cannot be read or decoded, so the
        radio layer can skip to the next playlist entry."""
        if not self.enabled:
            raise RuntimeError("audio disabled")
        try:
            with open(path, "rb") as f:
                data = f.read()
            buffer = io.BytesIO(data)
            pygame.mixer.music.load(buffer, namehint=path.rsplit(".", 1)[-1])
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume * self.speech_duck)
            pygame.mixer.music.play(loops=0, fade_ms=fade_ms)
        except (OSError, pygame.error) as exc:
            raise RuntimeError(f"could not play {path}") from exc
        self._music_track = f"file:{path}"
        self._music_buffer = buffer

    def music_playing(self) -> bool:
        return self._music_track is not None and bool(pygame.mixer.music.get_busy())

    def stop_music(self, fade_ms: int = 1000) -> None:
        if not self.enabled or self._music_track is None:
            return
        pygame.mixer.music.fadeout(fade_ms)
        self._music_track = None

    # -- volume control ---------------------------------------------------------

    def _category_volume(self, category: str) -> float:
        volume = {
            "engine": self.engine_volume,
            "weather": self.weather_volume,
            "ui": self.ui_volume,
            "siren": self.siren_volume,
        }.get(category, self.sfx_volume)
        if category in ("engine", "weather"):
            volume *= self.speech_duck
        return volume

    def set_speech_duck(self, duck: float) -> None:
        """Scale engine, weather, and music under the event voice, live."""
        duck = max(0.0, min(1.0, duck))
        if duck == self.speech_duck:
            return
        self.speech_duck = duck
        # Reapply everything the factor touches; set_volumes with no
        # arguments is exactly that pass.
        self.set_volumes()

    def set_volumes(
        self,
        master: float | None = None,
        sfx: float | None = None,
        music: float | None = None,
        weather: float | None = None,
        engine: float | None = None,
        ui: float | None = None,
        siren: float | None = None,
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
        if siren is not None:
            self.siren_volume = max(0.0, min(1.0, siren))
        if not self.enabled:
            return
        for ch in list(self._loops):
            self._apply_channel_volume(ch)
        if self._music_track is not None:
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume * self.speech_duck)

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
    # While the event voice speaks, engine/weather/music step down to this
    # and back (see AudioEngine.set_speech_duck). Not a setting value:
    # settings own the volumes, this rides on top of them. A class default,
    # so the bare-__new__ backends tests build carry it too.
    speech_duck = 1.0

    def __init__(self) -> None:
        from sound_lib.external.pybass import (
            BASS_ATTRIB_FREQ,
            BASS_ATTRIB_PAN,
            BASS_ATTRIB_VOL,
            BASS_CONFIG_NET_READTIMEOUT,
            BASS_CONFIG_NET_TIMEOUT,
            BASS_POS_BYTE,
            BASS_ChannelBytes2Seconds,
            BASS_ChannelGetLength,
            BASS_ChannelSetAttribute,
            BASS_ChannelSlideAttribute,
            BASS_SetConfig,
        )
        from sound_lib.main import BassError, bass_call
        from sound_lib.output import Output
        from sound_lib.stream import FileStream, URLStream

        BASS_SetConfig(BASS_CONFIG_NET_TIMEOUT, RADIO_CONNECT_TIMEOUT_MS)
        BASS_SetConfig(BASS_CONFIG_NET_READTIMEOUT, RADIO_READ_TIMEOUT_MS)

        self._FileStream = FileStream
        self._URLStream = URLStream
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
        self.siren_volume = 1.0
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
        # Multisample ring: (native_rpm, stream, base_freq) per resolved band.
        # Empty when running on the legacy single pitched loop.
        self._engine_bands: list[tuple[float, object, float]] = []
        # Player preference: True forces the legacy pitched loop even when
        # the multisample cuts are installed (Settings, "classic").
        self.engine_voice_classic = False
        self._engine_intro_stream = None  # ignition one-shot, kept for the crossfade
        self._engine_intro_gain = 1.0  # crossfade multiplier on the engine loop
        self._engine_intro_load = 0.0  # ignition load boost: 1.0 forces full load
        self._engine_starting = False  # True only during the ignition crossfade
        self._engine_last_rpm = ENGINE_RPM_IDLE
        self._engine_last_throttle = 0.0
        self._engine_duck = 1.0  # shift-gap disengage: below the load floor
        self._fades = FadeScheduler()
        self._engine_wobble: list[list[float]] = []
        self._wobble_rng = random.Random()
        # Radio connects happen on worker threads (see play_radio_stream);
        # every field below is guarded by _radio_lock. The generation counter
        # tells a finished worker whether its request is still the current
        # one; the pending slot is how an opened stream crosses back to the
        # game thread, which alone touches _music_stream.
        self._radio_lock = threading.Lock()
        self._radio_generation = 0
        self._radio_pending: tuple[str, int, object] | None = None  # (url, fade_ms, stream)
        self._radio_connecting_url: str | None = None
        self._radio_failed_url: str | None = None
        self._radio_threads: list[threading.Thread] = []

        if os.environ.get("SDL_AUDIODRIVER", "").lower() == "dummy":
            self._output = Output(device=BASS_NO_SOUND_DEVICE)
        else:
            try:
                self._output = Output()
            except BassError:
                log.warning("No audio device; using the BASS no-sound device")
                self._output = Output(device=BASS_NO_SOUND_DEVICE)
        self._log_output_device()
        self._load_plugins()
        self.enabled = True

    def _log_output_device(self) -> None:
        """Name the output device the game is about to play through.

        A player reporting silence is far more often pointed at the wrong
        device -- speech on one output, the game on the system default -- or
        muted, than missing a sound file. The log could not tell those apart
        without naming the device, so it names it.
        """
        try:
            index = self._output.get_device()
            names = self._output.get_device_names()
            name = names[index - 1] if 0 < index <= len(names) else "unknown"
        except Exception:  # diagnostics must never be the thing that fails
            log.info("Audio output device: could not be identified", exc_info=True)
            return
        if index != BASS_NO_SOUND_DEVICE:
            log.info("Audio output device %d: %s", index, name)
        elif os.environ.get("SDL_AUDIODRIVER", "").lower() == "dummy":
            # Asked for: headless runs, tests, and the release smoke check.
            log.info("Audio output: no-sound device, as asked for by this run")
        else:
            # Not asked for, and the reason a player hears nothing.
            log.warning("Audio output is the BASS no-sound device; nothing will be audible")

    def _load_plugins(self) -> None:
        """Load optional BASS addon plugins (currently BASSHLS).

        A missing or refused plugin is not an error: stations that need it
        simply fail to open and the radio falls back with a spoken note.
        """
        import sound_lib
        from sound_lib.external.pybass import BASS_UNICODE, BASS_PluginLoad

        lib_dirs = (PLUGIN_LIB, Path(sound_lib.__file__).parent / "lib")
        for name in _bass_plugin_names():
            for lib_dir in lib_dirs:
                path = lib_dir / name
                if not path.is_file():
                    continue
                # UTF-16 + BASS_UNICODE sidesteps ANSI-codepage install paths.
                if sys.platform == "win32":
                    handle = BASS_PluginLoad(
                        str(path).encode("utf-16-le") + b"\x00\x00", BASS_UNICODE
                    )
                else:
                    handle = BASS_PluginLoad(str(path), 0)
                if handle:
                    log.info("Loaded BASS plugin: %s", path)
                    break
                log.warning("BASS could not load plugin: %s", path)
            else:
                log.info("BASS plugin not present: %s", name)

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
        found = _playback_bytes(key, ("ogg", "wav"))
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

    def set_loop_pan(self, channel: int, pan: float) -> None:
        if channel not in self._loops:
            return
        stream = self._loops[channel][2]
        # A dying stream drops its pan silently; the volume path logs.
        with contextlib.suppress(self._BassError):
            self._bass_call(
                self._set_attr, stream.handle, self._ATTRIB_PAN, max(-1.0, min(1.0, pan))
            )

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
        self._engine_bands = []
        self._engine_wobble = []
        if not self.engine_voice_classic:
            for key, native in ENGINE_BANDS:
                band_stream = self._sfx_stream(key, looping=True)
                if band_stream is None:
                    continue
                try:
                    base_freq = band_stream.get_frequency()
                    band_stream.set_volume(0.0)
                    band_stream.play()
                except self._BassError:
                    continue
                self._engine_bands.append((native, band_stream, base_freq))
                self._engine_wobble.append([0.0, 0.0])  # [rate walk, gain walk]
        if len(self._engine_bands) < 2:
            # Not enough cuts for a crossfade ring (a clean clone carries only
            # the synthesized engine/idle): legacy single pitched loop.
            for _native, band_stream, _freq in self._engine_bands:
                with contextlib.suppress(self._BassError):
                    band_stream.stop()
            self._engine_bands = []
            stream = None
            if self.engine_voice_classic:
                stream = self._sfx_stream(ENGINE_CLASSIC_LOOP_KEY, looping=True)
                if stream is None:
                    log.warning(
                        "Classic engine cut %s is not in this build; "
                        "using %s pitched instead",
                        ENGINE_CLASSIC_LOOP_KEY,
                        ENGINE_LOOP_KEY,
                    )
            if stream is None:
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
        self.set_engine_rpm(self._engine_last_rpm, self._engine_last_throttle)

    def _set_engine_intro_load(self, value: float) -> None:
        self._engine_intro_load = max(0.0, min(1.0, value))
        self.set_engine_rpm(self._engine_last_rpm, self._engine_last_throttle)

    def _end_engine_starting(self) -> None:
        self._engine_starting = False

    def update(self, dt: float) -> None:
        self._collect_radio_stream()
        self._fades.update(dt)
        # Advance the per-band anti-repetition walks; set_engine_rpm applies
        # them. Diffusion scales with sqrt(dt) so the walk speed is frame-rate
        # independent; the clamp keeps each walk meandering inside its box.
        if self._engine_wobble and dt > 0.0:
            scale = math.sqrt(dt)
            for wob in self._engine_wobble:
                for i, (step, bound) in enumerate(
                    (
                        (ENGINE_WOBBLE_RATE_STEP, ENGINE_WOBBLE_RATE_MAX),
                        (ENGINE_WOBBLE_GAIN_STEP, ENGINE_WOBBLE_GAIN_MAX),
                    )
                ):
                    wob[i] += self._wobble_rng.uniform(-step, step) * scale
                    wob[i] = max(-bound, min(bound, wob[i]))

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
        for _native, stream, _freq in self._engine_bands:
            self._fade_out(stream, 250)
        self._engine_bands = []
        self._engine_wobble = []
        if self._engine_stream is not None:
            self._fade_out(self._engine_stream, 250)
            self._engine_stream = None
        if shutdown_sound:
            self.play("engine/shutdown")

    def set_engine_rpm(self, rpm: float, throttle: float = 0.0) -> None:
        """Track RPM: crossfade the multisample ring, or pitch the legacy loop.

        With the ring, each band's playback rate also slides toward
        ``rpm / native_rpm`` (clamped) so the pitch is continuous through a
        crossfade instead of stepping between the cuts' recorded speeds.
        """
        if not (self._engine_running and (self._engine_bands or self._engine_stream)):
            return
        # A step-sized rpm change (shift re-entry) snaps; wander glides.
        slide_ms = (
            ENGINE_SLIDE_SNAP_MS
            if abs(rpm - self._engine_last_rpm) > ENGINE_SLIDE_SNAP_RPM
            else ENGINE_SLIDE_MS
        )
        self._engine_last_rpm = rpm
        self._engine_last_throttle = throttle
        load_gain = engine_load_gain(throttle)
        # During the ignition handoff, boost load toward full so the loop meets
        # the crank tail; the boost eases back to 0 afterward.
        load_gain += self._engine_intro_load * (1.0 - load_gain)
        level = max(
            0.0,
            min(
                1.0,
                ENGINE_LOOP_GAIN
                * load_gain
                * self._engine_duck
                * self.engine_volume
                * self.speech_duck
                * self.master_volume
                * self._engine_intro_gain,
            ),
        )
        if self._engine_bands:
            natives = tuple(native for native, _stream, _freq in self._engine_bands)
            weights = engine_band_weights(rpm, natives)
            for (native, stream, base_freq), w, wob in zip(
                self._engine_bands, weights, self._engine_wobble, strict=True
            ):
                rate = max(ENGINE_BAND_RATE_MIN, min(ENGINE_BAND_RATE_MAX, rpm / native))
                rate *= 1.0 + wob[0]
                try:
                    self._bass_call(
                        self._slide,
                        stream.handle,
                        self._ATTRIB_FREQ,
                        base_freq * rate,
                        slide_ms,
                    )
                    stream.set_volume(level * w * (1.0 + wob[1]))
                except self._BassError:
                    self._engine_bands = []
                    return
            return
        target = self._engine_base_freq * engine_freq_mult(rpm)
        try:
            self._bass_call(
                self._slide, self._engine_stream.handle, self._ATTRIB_FREQ, target, slide_ms
            )
            self._engine_stream.set_volume(level)
        except self._BassError:
            self._engine_stream = None

    def set_engine_duck(self, duck: float) -> None:
        """Shift-gap disengage: scale the engine bed below the load floor."""
        duck = max(0.0, min(1.0, duck))
        if duck == self._engine_duck:
            return
        self._engine_duck = duck
        self.set_engine_rpm(self._engine_last_rpm, self._engine_last_throttle)

    def set_road_noise(self, speed_mps: float) -> None:
        gain = min(1.0, speed_mps / 30.0)
        if gain < 0.02:
            self.stop_loop(CH_ROAD, fade_ms=500)
            return

        self.start_loop(CH_ROAD, "vehicle/road", volume=gain, fade_ms=400)
        entry = self._loops.get(CH_ROAD)
        if entry is not None:
            _, _, stream = entry
            mult = 0.4 + 0.9 * min(1.0, speed_mps / 30.0)
            try:
                base_freq = getattr(stream, "_road_base_freq", None)
                if base_freq is None:
                    base_freq = stream.get_frequency()
                    stream._road_base_freq = base_freq
                target = base_freq * mult
                self._bass_call(self._slide, stream.handle, self._ATTRIB_FREQ, target, 120)
            except self._BassError:
                pass

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
        self._cancel_radio_connect()
        # Music ships as Opus (tools/encode_music_opus.py): far smaller for
        # background beds at the same perceived quality. Ogg stays in the
        # preference list so a partial migration and the effects tree, which
        # are still Vorbis, keep resolving.
        found = _asset_bytes(f"music/{track}", ("opus", "ogg", "wav"))
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
                max(0.0, min(1.0, self.music_volume * self.master_volume * self.speech_duck)),
                max(0, int(fade_ms)),
            )
        except self._BassError:
            log.warning("Could not play music %s", track, exc_info=True)
            return
        self._music_stream = stream
        self._music_track = track

    def play_radio_stream(self, url: str, fade_ms: int = 1500) -> None:
        """Tune a live internet stream, connecting off the game thread.

        Opening a URL blocks until the server answers, which on a dead or
        stalling station is seconds -- too long to spend inside a frame. The
        connect runs on a worker; update() collects the opened stream back on
        the game thread. A failed connect raises on the NEXT call for the
        same URL, which is exactly when the driving state's reconnect loop
        retries a silent radio -- the fallback machinery still gets its
        exception and speaks, just without the freeze.
        """
        # Same URL only dedupes while the stream is actually producing audio;
        # a stalled or dead connection must be torn down and recreated, or a
        # re-tune to the same station silently does nothing.
        if self._music_track == url and self.music_playing():
            return
        with self._radio_lock:
            if url == self._radio_connecting_url:
                return  # already on its way; silence is the caller's retry cue
            if self._radio_failed_url == url:
                # The last attempt never produced audio; say so now, and let
                # a later tune back to this station start a fresh attempt.
                self._radio_failed_url = None
                raise RuntimeError("radio stream unavailable")
            self._radio_generation += 1
            generation = self._radio_generation
            self._radio_pending = None
            self._radio_connecting_url = url
        if self._music_stream is not None:
            self._fade_out(self._music_stream, 800)
            self._music_stream = None
            self._music_track = None
        thread = threading.Thread(
            target=self._radio_worker,
            args=(url, generation, max(0, int(fade_ms))),
            name="radio-connect",
            daemon=True,
        )
        with self._radio_lock:
            self._radio_threads = [t for t in self._radio_threads if t.is_alive()]
            self._radio_threads.append(thread)
        thread.start()

    def _radio_worker(self, url: str, generation: int, fade_ms: int) -> None:
        """Open a stream off-thread, unless the driver has moved on since."""
        try:
            stream = self._URLStream(url=url, autofree=True)
        except Exception:  # BassError, but a bad URL can raise from ctypes too
            log.info("Radio stream unavailable: %s", url, exc_info=True)
            with self._radio_lock:
                if generation == self._radio_generation:
                    self._radio_failed_url = url
                    self._radio_connecting_url = None
            return
        with self._radio_lock:
            if generation == self._radio_generation:
                self._radio_pending = (url, fade_ms, stream)
                self._radio_connecting_url = None
                stream = None  # handed over to the game thread
        if stream is not None:  # a newer request already won
            with contextlib.suppress(Exception):
                stream.free()

    def _collect_radio_stream(self) -> None:
        """Wire up a stream a worker finished opening; game thread only."""
        with self._radio_lock:
            pending, self._radio_pending = self._radio_pending, None
        if pending is None:
            return
        url, fade_ms, stream = pending
        if self._music_track is not None:
            # Something else claimed the music channel while the station was
            # connecting (a menu bed, another tune); the late arrival loses.
            with contextlib.suppress(Exception):
                stream.free()
            return
        try:
            stream.set_volume(0.0)
            stream.play()
            self._bass_call(
                self._slide,
                stream.handle,
                self._ATTRIB_VOL,
                max(0.0, min(1.0, self.music_volume * self.master_volume * self.speech_duck)),
                fade_ms,
            )
        except self._BassError:
            log.warning("Could not play radio stream: %s", url, exc_info=True)
            with self._radio_lock:
                self._radio_failed_url = url
            return
        self._music_stream = stream
        self._music_track = url

    def _cancel_radio_connect(self) -> None:
        """Orphan any connect in flight; its stream is freed, not wired up."""
        with self._radio_lock:
            self._radio_generation += 1
            pending, self._radio_pending = self._radio_pending, None
            self._radio_connecting_url = None
            self._radio_failed_url = None
        if pending is not None:
            with contextlib.suppress(Exception):
                pending[2].free()

    def play_music_file(self, path: str, fade_ms: int = 1200) -> None:
        """Play one media file from disk on the music channel.

        Reads the bytes and decodes from memory like the shipped music does,
        so a NAS path is read once per track rather than streamed over SMB.
        Raises RuntimeError when the file cannot be read or decoded, so the
        radio layer can skip to the next playlist entry."""
        key = f"file:{path}"
        self._cancel_radio_connect()
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as exc:
            raise RuntimeError(f"could not read {path}") from exc
        if self._music_stream is not None:
            self._fade_out(self._music_stream, 800)
            self._music_stream = None
            self._music_track = None
        stream = self._stream(data, key, looping=False)
        if stream is None:
            raise RuntimeError(f"could not decode {path}")
        try:
            stream.set_volume(0.0)
            stream.play()
            self._bass_call(
                self._slide,
                stream.handle,
                self._ATTRIB_VOL,
                max(0.0, min(1.0, self.music_volume * self.master_volume * self.speech_duck)),
                max(0, int(fade_ms)),
            )
        except self._BassError as exc:
            raise RuntimeError(f"could not play {path}") from exc
        self._music_stream = stream
        self._music_track = key

    def music_playing(self) -> bool:
        if self._music_stream is None:
            return False
        try:
            return bool(self._music_stream.is_playing)
        except Exception:
            return False

    def stop_music(self, fade_ms: int = 1000) -> None:
        # Cancel before the early return: a radio still connecting has no
        # stream yet, and stopping the radio must orphan that connect too.
        self._cancel_radio_connect()
        if self._music_stream is None:
            return
        self._fade_out(self._music_stream, fade_ms)
        self._music_stream = None
        self._music_track = None

    # -- volume control ---------------------------------------------------------

    def _category_volume(self, category: str) -> float:
        volume = {
            "engine": self.engine_volume,
            "weather": self.weather_volume,
            "ui": self.ui_volume,
            "siren": self.siren_volume,
        }.get(category, self.sfx_volume)
        if category in ("engine", "weather"):
            volume *= self.speech_duck
        return volume

    def set_speech_duck(self, duck: float) -> None:
        """Scale engine, weather, and music under the event voice, live."""
        duck = max(0.0, min(1.0, duck))
        if duck == self.speech_duck:
            return
        self.speech_duck = duck
        # Reapply everything the factor touches; set_volumes with no
        # arguments is exactly that pass.
        self.set_volumes()

    def set_volumes(
        self,
        master: float | None = None,
        sfx: float | None = None,
        music: float | None = None,
        weather: float | None = None,
        engine: float | None = None,
        ui: float | None = None,
        siren: float | None = None,
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
        if siren is not None:
            self.siren_volume = max(0.0, min(1.0, siren))
        for ch in list(self._loops):
            self._apply_loop_volume(ch)
        # Reapply engine volume through the rpm path: it knows the current
        # model (multisample ring or legacy loop) and keeps the load contour.
        self.set_engine_rpm(self._engine_last_rpm, self._engine_last_throttle)
        if self._music_stream is not None:
            try:
                self._music_stream.set_volume(
                    max(0.0, min(1.0, self.music_volume * self.master_volume * self.speech_duck))
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
        # A connect still in flight holds a worker inside BASS; freeing BASS
        # underneath it is a crash. Give it a bounded moment to come back.
        with self._radio_lock:
            threads = [t for t in self._radio_threads if t.is_alive()]
        deadline = time.monotonic() + RADIO_SHUTDOWN_JOIN_S
        for thread in threads:
            thread.join(max(0.0, deadline - time.monotonic()))
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
        self.siren_volume = 1.0

    def play(self, key: str, volume: float = 1.0, pan: float = 0.0) -> None: ...
    def start_loop(
        self, channel: int, key: str, volume: float = 1.0, fade_ms: int = 300
    ) -> None: ...
    def set_loop_volume(self, channel: int, volume: float) -> None: ...
    def set_loop_pan(self, channel: int, pan: float) -> None: ...
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
    def set_road_noise(self, speed_mps: float) -> None: ...
    def update(self, dt: float) -> None: ...
    def reverse_start(self) -> None: ...
    def reverse_stop(self) -> None: ...
    def play_music(self, track: str, fade_ms: int = 1500) -> None: ...
    def play_radio_stream(self, url: str, fade_ms: int = 1500) -> None:
        raise RuntimeError("radio stream unavailable")

    def play_music_file(self, path: str, fade_ms: int = 1200) -> None:
        raise RuntimeError("audio disabled")

    def music_playing(self) -> bool:
        return False

    def stop_music(self, fade_ms: int = 1000) -> None: ...
    def set_volumes(
        self,
        master: float | None = None,
        sfx: float | None = None,
        music: float | None = None,
        weather: float | None = None,
        engine: float | None = None,
        ui: float | None = None,
        siren: float | None = None,
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
        if siren is not None:
            self.siren_volume = max(0.0, min(1.0, siren))

    def shutdown(self) -> None: ...


class AudioEngine:
    """Facade over the active backend; the rest of the game talks only to this."""

    def __init__(self) -> None:
        self._impl = self._pick_backend()
        self._banks: dict[str, list[str]] = {}  # base -> discovered numbered keys
        self._bank_order: dict[str, list[str]] = {}  # base -> remaining shuffled cuts
        self._last_bank_key: dict[str, str] = {}  # base -> cut played last
        self._asset_known: dict[str, bool] = {}  # key -> resolves anywhere
        self._logged_volumes: tuple[float | None, ...] | None = None
        self._alert_hold_key = ""  # continuous alert tone being re-asserted
        self._alert_hold_s = 0.0  # time left before the hold lapses
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

    def set_engine_duck(self, duck: float) -> None:
        """Shift-gap disengage: scale the engine bed below the load floor.

        1.0 is normal running; the drive loop drops it through a shift's
        torque interrupt so the engine genuinely falls away, then eases it
        back as the clutch hooks up.
        """
        impl_fn = getattr(self._impl, "set_engine_duck", None)
        if impl_fn is not None:
            impl_fn(duck)

    def set_speech_duck(self, duck: float) -> None:
        """Step engine, weather, and music (the radio's slot) down under the
        event voice and back: 1.0 is the normal mix, ``SPEECH_DUCK_LEVEL``
        while the road is talking. The player's volume settings are never
        touched -- the factor rides on top of them and every reapplication
        (a settings change, a new loop) keeps honoring it until the caller
        restores 1.0.
        """
        impl_fn = getattr(self._impl, "set_speech_duck", None)
        if impl_fn is not None:
            impl_fn(duck)

    def set_engine_voice(self, classic: bool) -> None:
        """Pick the engine voice: the recorded multisample ring or the
        classic single pitched loop (BASS backend; pygame has one model).

        Applies live -- a running engine re-voices in place at its current
        rpm without replaying the ignition crank, so the Settings toggle is
        an instant A/B.
        """
        impl = self._impl
        if getattr(impl, "engine_voice_classic", None) in (None, classic):
            if hasattr(impl, "engine_voice_classic"):
                impl.engine_voice_classic = classic
            return
        impl.engine_voice_classic = classic
        if self.engine_running:
            rpm = getattr(impl, "_engine_last_rpm", ENGINE_RPM_IDLE)
            throttle = getattr(impl, "_engine_last_throttle", 0.0)
            impl.engine_stop(shutdown_sound=False)
            impl.engine_start(play_start_sound=False)
            impl.set_engine_rpm(rpm, throttle)

    def has_asset(self, key: str) -> bool:
        """Whether a sound key resolves (pack, licensed overlay, or loose).

        Cached; call sites use it to prefer a licensed cue and fall back to
        the committed one -- or to stay silent where silence was the old
        behavior -- on a clean clone.
        """
        if key in _GENERATED:
            # Synthesized cues are published after this engine was built, so a
            # miss cached before registration must never be the final answer.
            return True
        cached = self._asset_known.get(key)
        if cached is None:
            cached = _asset_bytes(key, ("ogg", "wav")) is not None
            self._asset_known[key] = cached
        return cached

    def _bank_keys(self, base: str) -> list[str]:
        """Discover a numbered round-robin bank (``base_01``..) once, cached."""
        keys = self._banks.get(base)
        if keys is None:
            keys = []
            for i in range(1, 100):
                key = f"{base}_{i:02d}"
                if _asset_bytes(key, ("ogg", "wav")) is None:
                    break
                keys.append(key)
            self._banks[base] = keys
        return keys

    def play_bank(self, base: str, fallback: str, volume: float = 1.0, pan: float = 0.0) -> None:
        """Play one cut from a round-robin bank, or ``fallback`` if none exist.

        Real mechanical events never sound twice the same, so banked cuts
        (``base_01``..``base_NN``, the licensed overlay) play in a shuffled
        cycle -- every cut once before any repeats, never the same cut twice
        in a row. A clean clone without the bank keeps the single classic cue.
        """
        keys = self._bank_keys(base)
        if not keys:
            self.play(fallback, volume, pan)
            return
        order = self._bank_order.get(base)
        if not order:
            order = random.sample(keys, len(keys))
            # A fresh shuffle may lead with the cut that just played; swap it
            # to the back so no cut ever sounds twice in a row.
            if len(order) > 1 and order[0] == self._last_bank_key.get(base):
                order[0], order[-1] = order[-1], order[0]
            self._bank_order[base] = order
        key = order.pop(0)
        self._last_bank_key[base] = key
        # Per-trigger level jitter, ~±1.4 dB: no two clunks land identically.
        self.play(key, volume * random.uniform(0.85, 1.17), pan)

    def start_loop(self, channel: int, key: str, volume: float = 1.0, fade_ms: int = 300) -> None:
        self._impl.start_loop(channel, key, volume, fade_ms)

    def set_loop_volume(self, channel: int, volume: float) -> None:
        self._impl.set_loop_volume(channel, volume)

    def set_loop_pan(self, channel: int, pan: float) -> None:
        self._impl.set_loop_pan(channel, pan)

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

    # -- held alert tones ------------------------------------------------------

    def hold_alert(self, key: str, volume: float = 1.0, fade_ms: int = 60) -> None:
        """Sound the continuous alert tone ``key`` for the next moment only.

        Call this every frame for as long as the alert applies. The tone
        starts on the first call and stops itself a fraction of a second
        after the calls stop, so it can never be left ringing by a caller
        that returned early, ended, or lost the frame to a menu. Calling it
        again after a silencing transition brings the same tone back.
        """
        self.start_loop(CH_ALERT, key, volume=volume, fade_ms=fade_ms)
        self._alert_hold_key = key
        self._alert_hold_s = ALERT_HOLD_TIMEOUT_S

    def release_alert(self, fade_ms: int = 120) -> None:
        """Stop a held alert tone now, rather than waiting for it to lapse."""
        if not self._alert_hold_key:
            return
        self._alert_hold_key = ""
        self._alert_hold_s = 0.0
        self.stop_loop(CH_ALERT, fade_ms=fade_ms)

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
        # The held-alert watchdog. This runs from the app loop no matter which
        # screen is up, so a tone whose owner stopped updating goes quiet on
        # its own instead of running until the player quits the game.
        if self._alert_hold_s > 0.0:
            self._alert_hold_s -= dt
            if self._alert_hold_s <= 0.0:
                self.release_alert()

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
        """Tire-on-asphalt loop whose volume (and pitch under BASS) tracks speed."""
        self._impl.set_road_noise(speed_mps)

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
        """Stop engine, road, weather, ambience, and any held alert tone
        (leaving UI sfx alone)."""
        self.engine_stop(shutdown_sound=False)
        # A pause or an arrival cuts the alert now, without the watchdog's
        # fraction of a second of tone over the top of the menu.
        self.release_alert(fade_ms=200)
        for ch in (
            CH_ROAD,
            CH_WEATHER,
            CH_WEATHER_B,
            CH_AMBIENT,
            CH_HORN,
            CH_AIR,
            CH_JAKE,
            CH_RADIO_FX,
            # The edge texture is road noise like the rest: left out, a driver
            # who paused with a tire on the rumble strip took the strip into
            # the menu with them. It comes back on its own when the drive does.
            CH_EDGE,
        ):
            self.stop_loop(ch, fade_ms=400)

    # -- music ----------------------------------------------------------------

    def play_music(self, track: str, fade_ms: int = 1500) -> None:
        """Stream a music track, e.g. ``play_music("menu_theme")``."""
        self._impl.play_music(track, fade_ms)

    def play_radio_stream(self, url: str, fade_ms: int = 1500) -> None:
        """Stream a live radio URL when the active backend supports it."""
        self._impl.play_radio_stream(url, fade_ms)

    def play_music_file(self, path: str, fade_ms: int = 1200) -> None:
        """Play one local media file (a personal playlist entry) as music.

        Raises RuntimeError when the file cannot be read or decoded."""
        self._impl.play_music_file(path, fade_ms)

    def music_playing(self) -> bool:
        """Whether the music channel is still producing sound."""
        return self._impl.music_playing()

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
        siren: float | None = None,
    ) -> None:
        self._impl.set_volumes(master, sfx, music, weather, engine, ui, siren)
        # The other half of a silence report: a healthy backend playing at
        # zero looks exactly like a broken one until the levels are written
        # down. Logged on change only, so it cannot flood the file.
        levels = (master, sfx, music, weather, engine, ui, siren)
        if levels != self._logged_volumes:
            self._logged_volumes = levels
            log.info(
                "Volumes: master=%s sfx=%s music=%s weather=%s engine=%s ui=%s siren=%s",
                *levels,
            )

    def shutdown(self) -> None:
        self._impl.shutdown()
