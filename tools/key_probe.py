"""Show what the keyboard looks like to the game, screen reader and all.

Freight Fate polls its driving keys, and a screen reader that re-sends keys
as instant press-and-release pairs (JAWS does) makes a held arrow invisible
to a poll. This opens a bare window, logs every key event with its timing
and what SDL's own key state said at that moment, and reports what the
held-key tracker (``freight_fate.held_keys``) made of it -- so a player can
show exactly what their screen reader delivers, and we can size the fix to
it instead of guessing.

Usage::

    uv run python tools/key_probe.py             # 25 seconds, then it reports
    uv run python tools/key_probe.py --seconds 40
    uv run python tools/key_probe.py --speak     # also a long line per arrow press

Tab into the window when it opens, then press and hold each arrow key for a
few seconds. The probe finishes by itself after ``--seconds`` (Escape ends
it early), closes its window, and speaks its findings through the screen
reader as well as printing them. Every run writes its own timestamped log
in the current folder, flushed line by line, so nothing is lost if the
console is closed afterwards. With ``--speak``, every arrow press speaks a
long sentence with interrupt on, so the ear can tell whether the screen
reader cuts the previous one off.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import statistics
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from freight_fate.held_keys import HeldKeys  # noqa: E402

ARROWS = {
    pygame.K_UP: "Up",
    pygame.K_DOWN: "Down",
    pygame.K_LEFT: "Left",
    pygame.K_RIGHT: "Right",
}
LONG_LINE = (
    "This is a long sentence spoken with interrupt on, so that the next arrow "
    "press should cut it off before it reaches the very end of the line."
)
SYNTHETIC_GAP_MS = 25  # the tracker's own threshold, mirrored for the verdict


class Report:
    """Console plus a per-run log file, flushed on every line."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file = open(path, "w", encoding="utf-8")  # noqa: SIM115 -- closed in close()

    def line(self, text: str) -> None:
        print(text, flush=True)
        self._file.write(text + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


class Voice:
    """The game's own speech, or silence if it cannot start."""

    def __init__(self, enabled: bool) -> None:
        self._speech = None
        if not enabled:
            return
        try:
            from freight_fate.speech import Speech

            self._speech = Speech()
        except Exception:
            self._speech = None

    @property
    def name(self) -> str:
        return self._speech.backend_name if self._speech is not None else "none"

    def say(self, text: str, interrupt: bool = True) -> None:
        if self._speech is None:
            return
        with contextlib.suppress(Exception):
            self._speech.say(text, interrupt=interrupt)

    def say_and_wait(self, text: str) -> None:
        """Speak, then give the screen reader time to finish before we exit."""
        self.say(text, interrupt=True)
        if self._speech is not None:
            time.sleep(min(20.0, 1.0 + len(text.split()) / 2.5))

    def shutdown(self) -> None:
        if self._speech is not None:
            with contextlib.suppress(Exception):
                self._speech.shutdown()


def name_of(key: int) -> str:
    return ARROWS.get(key) or pygame.key.name(key)


def run_window(args, report: Report, voice: Voice) -> dict:
    """Open the window, collect events until the deadline or Escape, and
    return the raw measurements. The window is closed before returning so
    the console (and the screen reader) get focus back for the summary."""
    pygame.init()
    pygame.display.set_caption("Freight Fate key probe")
    screen = pygame.display.set_mode((720, 300))
    font = pygame.font.SysFont("Segoe UI, DejaVu Sans, Arial", 22)
    clock = pygame.time.Clock()
    tracker = HeldKeys()
    report.line(
        f"repeat delay {tracker.repeat_delay_ms} ms, repeat interval "
        f"{tracker.repeat_interval_ms} ms (from the operating system); "
        f"speech through {voice.name}"
    )
    report.line(f"collecting for {args.seconds} seconds; Escape ends early")
    voice.say(
        "Key probe ready. Tab into the probe window, then hold each arrow key for a few "
        f"seconds. It finishes by itself in {args.seconds} seconds.",
        interrupt=True,
    )

    data = {
        "last_down": {},
        "gaps_down_up": {},
        "spacing_downs": {},
        "counts": {},
        "longest_sdl_hold": {},
        "longest_tracker_hold": {},
        "events": 0,
        "focused": False,
    }
    sdl_hold_since: dict[int, int] = {}
    tracker_hold_since: dict[int, int] = {}
    last_event_at = None
    deadline = pygame.time.get_ticks() + args.seconds * 1000
    warned_ten = False
    status = "waiting for keys"
    running = True
    while running:
        clock.tick(60)
        now = pygame.time.get_ticks()
        tracker.begin_frame(now)
        if now >= deadline:
            running = False
        elif not warned_ten and deadline - now <= 10_000:
            warned_ten = True
            voice.say("Ten seconds left.", interrupt=False)
        for event in pygame.event.get():
            tracker.note(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.WINDOWFOCUSGAINED:
                data["focused"] = True
            elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                key = event.key
                if event.type == pygame.KEYDOWN and key == pygame.K_ESCAPE:
                    running = False
                    continue
                data["events"] += 1
                name = name_of(key)
                sdl_now = bool(pygame.key.get_pressed()[key])
                same_frame = " (same frame as the previous event)" if last_event_at == now else ""
                last_event_at = now
                if event.type == pygame.KEYDOWN:
                    data["counts"].setdefault(key, [0, 0])[0] += 1
                    previous = data["last_down"].get(key)
                    spacing = f", {now - previous} ms since the last press" if previous else ""
                    if previous:
                        data["spacing_downs"].setdefault(key, []).append(now - previous)
                    data["last_down"][key] = now
                    report.line(
                        f"{now:>8} DOWN {name}{spacing}; SDL now says "
                        f"{'down' if sdl_now else 'up'}{same_frame}"
                    )
                    if args.speak and key in ARROWS:
                        voice.say(f"{name}. {LONG_LINE}", interrupt=True)
                else:
                    data["counts"].setdefault(key, [0, 0])[1] += 1
                    pressed = data["last_down"].get(key)
                    gap = f" {now - pressed} ms after its press" if pressed is not None else ""
                    if pressed is not None:
                        data["gaps_down_up"].setdefault(key, []).append(now - pressed)
                    report.line(
                        f"{now:>8} UP   {name}{gap}; SDL now says "
                        f"{'down' if sdl_now else 'up'}{same_frame}"
                    )
        snapshot = tracker.snapshot()
        pressed_now = pygame.key.get_pressed()
        for key in ARROWS:
            for held, since, longest in (
                (bool(pressed_now[key]), sdl_hold_since, data["longest_sdl_hold"]),
                (bool(snapshot[key]), tracker_hold_since, data["longest_tracker_hold"]),
            ):
                if held and key not in since:
                    since[key] = now
                elif not held and key in since:
                    longest[key] = max(longest.get(key, 0), now - since.pop(key))
        held_names = [name for key, name in ARROWS.items() if snapshot[key]]
        sdl_names = [name for key, name in ARROWS.items() if pressed_now[key]]
        status = (
            f"game reads held: {', '.join(held_names) or 'nothing'}   "
            f"SDL reads held: {', '.join(sdl_names) or 'nothing'}"
        )
        screen.fill((16, 16, 24))
        lines = (
            "Freight Fate key probe -- hold the arrows; it finishes by itself",
            status,
            f"{max(0, (deadline - now) // 1000)} s left -- log: {report.path.name}",
        )
        for i, line in enumerate(lines):
            screen.blit(font.render(line, True, (230, 230, 230)), (20, 30 + i * 36))
        pygame.display.flip()

    end = pygame.time.get_ticks()
    for key in ARROWS:
        for since, longest in (
            (sdl_hold_since, data["longest_sdl_hold"]),
            (tracker_hold_since, data["longest_tracker_hold"]),
        ):
            if key in since:
                longest[key] = max(longest.get(key, 0), end - since.pop(key))
    pygame.quit()  # close the window first: focus goes back to the console
    return data


def summarize(data: dict, report: Report) -> list[str]:
    """Print the findings; return the spoken version (plain sentences)."""
    spoken: list[str] = []
    report.line("")
    report.line("summary")
    if not data["counts"]:
        text = (
            "No key events arrived. The probe window probably never had focus: "
            "tab or click into it next time."
            if not data["focused"]
            else "The window had focus but no key events arrived."
        )
        report.line(text)
        return [text]
    for key, (downs, ups) in data["counts"].items():
        name = name_of(key)
        gaps = data["gaps_down_up"].get(key, [])
        spacing = data["spacing_downs"].get(key, [])
        parts = [f"{name}: {downs} presses, {ups} releases"]
        if gaps:
            parts.append(f"release came a median {statistics.median(gaps):.0f} ms after its press")
        if spacing:
            parts.append(f"presses a median {statistics.median(spacing):.0f} ms apart")
        parts.append(f"longest hold SDL saw {data['longest_sdl_hold'].get(key, 0)} ms")
        parts.append(f"longest hold the game read {data['longest_tracker_hold'].get(key, 0)} ms")
        line = "; ".join(parts) + "."
        report.line(line)
        spoken.append(line.replace(" ms", " milliseconds").replace("SDL", "the keyboard layer"))
    every_gap = [g for gaps in data["gaps_down_up"].values() for g in gaps]
    if every_gap:
        if statistics.median(every_gap) <= SYNTHETIC_GAP_MS:
            verdict = (
                "Verdict: your screen reader re-sends each key as an instant press and "
                "release. The game never sees the key held by itself, and the tracker is "
                "what makes holding work."
            )
        else:
            verdict = (
                "Verdict: your keys reach the game as real holds. The release comes when "
                "your finger lifts, and the tracker changes nothing."
            )
        report.line(verdict)
        spoken.append(verdict)
    return spoken


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seconds", type=int, default=25, help="how long to collect (default 25)")
    parser.add_argument(
        "--speak", action="store_true", help="speak a long line on each arrow press"
    )
    parser.add_argument("--no-speech", action="store_true", help="print only; never speak")
    parser.add_argument("--log", help="log file (default: key_probe-<timestamp>.log here)")
    args = parser.parse_args()

    log_path = (
        Path(args.log) if args.log else Path(f"key_probe-{time.strftime('%Y%m%d-%H%M%S')}.log")
    )
    report = Report(log_path)
    report.line(f"key probe log: {log_path.resolve()}")
    voice = Voice(enabled=not args.no_speech)
    status = 0
    try:
        data = run_window(args, report, voice)
        spoken = summarize(data, report)
        report.line(f"log saved: {log_path.resolve()}")
        voice.say_and_wait(" ".join(spoken) + " The log is saved in the game folder.")
    except Exception:
        status = 1
        report.line("the probe hit an error:")
        for line in traceback.format_exc().rstrip().splitlines():
            report.line("  " + line)
        voice.say_and_wait("The key probe hit an error. The log has the details.")
    finally:
        report.close()
        voice.shutdown()
        with contextlib.suppress(Exception):
            pygame.quit()
    return status


if __name__ == "__main__":
    sys.exit(main())
