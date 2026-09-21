"""Frame-time bench for the per-frame drive loop: how long one tick costs.

Builds the transcript suite's drive -- Denver to Cheyenne, trip seed 0,
start hour 12, engine running, parking brake off, accelerator held -- and
ticks it at a fixed 60 Hz step, timing every frame. Reports mean, median,
p99 and max frame time in microseconds.

This is the Python half of a like-for-like comparison with the Rust port;
the other half is ``crates/freight-fate/tests/it/bench_drive.rs``, which builds
the same drive from the same route at the same seed and ticks the same
number of frames. Both silence speech and run the null audio backend, so
what is timed is the simulation and nothing else. The method, the numbers
and the asymmetries that could not be removed are written up in
``docs/superpowers/rust-port-benchmarks.md``.

The run is pinned to an isolated, empty data directory and to default
settings, so it never reads the machine's real settings.json -- a bench
that inherits a personal time-compression setting is not measuring the
same drive as anything else. Nothing here is random beyond the trip seed,
which is pinned, so two runs of the same build differ only by scheduling
noise.

Usage:
    FREIGHT_FATE_NO_SPEECH=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \\
        uv run python tools/bench_drive.py
    ... --frames 12000 --warmup 600     # the defaults, spelled out
    ... --quiet                          # the numbers, no preamble

FF_BENCH_FRAMES and FF_BENCH_WARMUP override the counts from the
environment, which is how the Rust side takes them too.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile
from pathlib import Path

# The headless drivers must be set before pygame is imported, exactly as
# tests/conftest.py forces them: a bench must never open a window or speak.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FREIGHT_FATE_NO_SPEECH", "1")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# An isolated, empty save/settings directory, exactly as the Rust harness
# (app::testing::TestApp) gives itself. Without this the bench would load the
# developer's own settings.json -- which is how an early run of this tool
# measured a drive at time_scale 20 against a Rust drive at the default 10.
_DATA_DIR = Path(tempfile.mkdtemp(prefix="ff-bench-drive-")) / "data"
os.environ["FREIGHT_FATE_DATA_DIR"] = str(_DATA_DIR)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402

DT = 1.0 / 60.0  # the game's fixed frame step (app.FPS is 60)
# Frames thrown away before timing starts: the opening ticks of a drive do
# one-off work (the departure chain, the first zone and corridor lookups)
# that no later frame repeats.
DEFAULT_WARMUP = 600
# 12 000 frames is 200 seconds of play at 60 Hz. The ceiling is the route:
# past its end every frame is a parked truck rather than a drive, which would
# flatter the numbers. 12 000 leaves the run entirely on the road -- it ends
# at mile 42.988 of the 100.4, at 85.51 mph, still rolling. Both sides print
# that mile, and it is how a reader tells that the two runs did the same work
# rather than taking it on trust.
DEFAULT_FRAMES = 12_000


class HeldKeys:
    """``pygame.key.get_pressed()`` with a fixed set of keys held down."""

    def __init__(self, *pressed: int) -> None:
        self._pressed = set(pressed)

    def __getitem__(self, key: int) -> bool:
        return key in self._pressed


def peak_working_set_bytes() -> int | None:
    """This process's peak working set, or None off Windows.

    Reads the same kernel counter PowerShell's ``PeakWorkingSet64`` reads
    (``GetProcessMemoryInfo``), through ctypes so the bench needs no extra
    dependency. It is a peak, not a sample, so a spike between reads still
    shows up -- but it counts resident pages only, so anything paged out
    before the read is not in it.
    """
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    # K32GetProcessMemoryInfo is the kernel32 export of the psapi entry point;
    # argtypes are not optional here, since the pointer argument is silently
    # mangled without them and the call just returns false.
    query = ctypes.windll.kernel32.K32GetProcessMemoryInfo
    query.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    query.restype = wintypes.BOOL
    current_process = ctypes.windll.kernel32.GetCurrentProcess
    current_process.restype = wintypes.HANDLE

    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    if not query(current_process(), ctypes.byref(counters), counters.cb):
        return None
    return int(counters.PeakWorkingSetSize)


def stats(samples: list[float]) -> dict[str, float]:
    """Mean, median, p99, max in microseconds, plus the total in ms."""
    ordered = sorted(samples)
    count = len(ordered)
    total = sum(samples)

    def rank(quantile: float) -> float:
        # Nearest-rank, the same rule the Rust bench uses.
        index = max(0, math.ceil(quantile * count) - 1)
        return ordered[min(index, count - 1)]

    return {
        "mean_us": total / count,
        "median_us": rank(0.5),
        "p99_us": rank(0.99),
        "max_us": ordered[-1],
        "total_ms": total / 1000.0,
    }


def build_drive(app):
    """The transcript suite's drive: Denver to Cheyenne at trip seed 0."""
    from freight_fate.models.jobs import make_reposition_job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    profile = Profile(name="Prelude", current_city="Denver")
    # Past the walkthrough: the first-run tutorial is not what is being timed.
    profile.tutorial_done = True
    app.ctx.profile = profile
    world = app.ctx.world
    job = make_reposition_job(world, "Denver", "Cheyenne")
    if job is None:
        raise SystemExit("Denver to Cheyenne is not a supported reposition")
    route = world.shortest_route("Denver", "Cheyenne")
    if route is None:
        raise SystemExit("Denver to Cheyenne has no route")
    return DrivingState(app.ctx, job, route, trip_seed=0, phase="delivery", start_hour=12.0)


def run(frames: int, warmup: int, quiet: bool) -> int:
    from time import perf_counter

    from freight_fate.app import App
    from freight_fate.audio import _NullBackend
    from freight_fate.data.world import get_world
    from freight_fate.settings import Settings

    # Default settings with the one-time online offer already spent, which is
    # what TestApp writes before it builds the app. Everything the frame loop
    # reads off Settings -- time_scale above all -- is therefore the shipped
    # default on both sides.
    seeded = Settings()
    seeded.online_offer_seen = True
    seeded.save()

    started = perf_counter()
    get_world()  # the module-level cache; every later get_world() is a lookup
    world_load_ms = (perf_counter() - started) * 1000.0

    started = perf_counter()
    app = App()
    app_ms = (perf_counter() - started) * 1000.0
    # The same audio the Rust harness runs: the real facade (bank bookkeeping,
    # held-cue dead-man switches) over a backend that plays nothing. Without
    # this the bench would time BASS on one side and nothing on the other.
    app.audio._impl = _NullBackend()

    try:
        started = perf_counter()
        drive = build_drive(app)
        build_ms = (perf_counter() - started) * 1000.0

        drive.enter()
        # A truck that can actually move: tanks charged, parking brake off,
        # engine running. A parked drive would exercise a fraction of the frame.
        drive.truck.set_air_ready(parking_brake=False)
        drive.truck.start_engine()
        # Accelerator held for the whole run.
        held = HeldKeys(pygame.K_UP)
        pygame.key.get_pressed = lambda: held  # type: ignore[assignment]

        for _ in range(warmup):
            drive.update(DT)

        samples: list[float] = []
        append = samples.append
        clock = perf_counter
        update = drive.update
        for _ in range(frames):
            start = clock()
            update(DT)
            append((clock() - start) * 1_000_000.0)

        result = stats(samples)
        position_mi = drive.trip.position_mi
        speed_mph = drive.truck.speed_mph
        game_minutes = drive.trip.game_minutes
        # Anything the drive pushed on top of itself (a traffic stop, a rest
        # screen): the Rust side reports the same number, and a mismatch means
        # the two runs did not do the same work.
        pushed_states = len(app.states)
    finally:
        app.shutdown()

    peak = peak_working_set_bytes()

    if not quiet:
        print("bench_drive (python)")
    print(f"  warmup frames      {warmup}")
    print(f"  timed frames       {frames}")
    print(f"  dt                 {DT:.6f} s (60 Hz)")
    print(f"  world load         {world_load_ms:.1f} ms")
    print(f"  App()              {app_ms:.1f} ms")
    print(f"  DrivingState()     {build_ms:.1f} ms")
    print(f"  frame mean         {result['mean_us']:.2f} us")
    print(f"  frame median       {result['median_us']:.2f} us")
    print(f"  frame p99          {result['p99_us']:.2f} us")
    print(f"  frame max          {result['max_us']:.2f} us")
    print(f"  timed total        {result['total_ms']:.1f} ms")
    print(f"  end position       {position_mi:.3f} mi")
    print(f"  end speed          {speed_mph:.2f} mph")
    print(f"  end game minutes   {game_minutes:.3f}")
    print(f"  states pushed      {pushed_states}")
    if peak is not None:
        print(f"  peak working set   {peak / (1024 * 1024):.1f} MB")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--frames",
        type=int,
        default=int(os.environ.get("FF_BENCH_FRAMES", DEFAULT_FRAMES)),
        help="frames to time (default 18000, five minutes at 60 Hz)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=int(os.environ.get("FF_BENCH_WARMUP", DEFAULT_WARMUP)),
        help="frames to tick before timing starts (default 600)",
    )
    parser.add_argument("--quiet", action="store_true", help="numbers only")
    args = parser.parse_args(argv)
    if args.frames < 1:
        parser.error("--frames must be at least 1")
    if args.warmup < 0:
        parser.error("--warmup cannot be negative")
    return run(args.frames, args.warmup, args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
