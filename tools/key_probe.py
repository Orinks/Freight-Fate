"""Show what the keyboard looks like to the game, screen reader and all.

Freight Fate polls its driving keys, and a screen reader that re-sends keys
as instant press-and-release pairs (JAWS does) makes a held arrow invisible
to a poll. This opens a bare window, logs every key event with its timing
and what SDL's own key state said at that moment, and reports what the
held-key tracker (``freight_fate.held_keys``) made of it -- so a player can
show exactly what their screen reader delivers, and we can size the fix to
it instead of guessing.

Usage::

    uv run python tools/key_probe.py           # log to the console and key_probe.log
    uv run python tools/key_probe.py --speak   # also speak a long line per arrow press

Click or tab into the window, then press and hold the arrow keys for a few
seconds each; Escape quits and prints a summary in plain words. With
``--speak``, every arrow press speaks a long sentence with interrupt on, so
the ear can tell whether the screen reader cuts the previous one off.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--speak", action="store_true", help="speak a long line on each arrow press"
    )
    parser.add_argument("--log", default="key_probe.log", help="log file (default: key_probe.log)")
    args = parser.parse_args()

    speech = None
    if args.speak:
        from freight_fate.speech import Speech

        speech = Speech()

    pygame.init()
    pygame.display.set_caption("Freight Fate key probe")
    screen = pygame.display.set_mode((720, 300))
    font = pygame.font.SysFont("Segoe UI, DejaVu Sans, Arial", 22)
    clock = pygame.time.Clock()
    tracker = HeldKeys()
    log_file = open(args.log, "w", encoding="utf-8")  # noqa: SIM115 -- closed below

    def emit(line: str) -> None:
        print(line, flush=True)
        log_file.write(line + "\n")

    emit(
        f"key probe: repeat delay {tracker.repeat_delay_ms} ms, repeat interval "
        f"{tracker.repeat_interval_ms} ms (from the operating system)"
    )
    emit("hold the arrow keys for a few seconds each; Escape to finish")

    last_down: dict[int, int] = {}
    gaps_down_up: dict[int, list[int]] = {}
    spacing_downs: dict[int, list[int]] = {}
    counts: dict[int, list[int]] = {}
    longest_sdl_hold: dict[int, int] = {}
    longest_tracker_hold: dict[int, int] = {}
    sdl_hold_since: dict[int, int] = {}
    tracker_hold_since: dict[int, int] = {}
    status = "waiting for keys"
    running = True
    while running:
        clock.tick(60)
        now = pygame.time.get_ticks()
        tracker.begin_frame(now)
        for event in pygame.event.get():
            tracker.note(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                key = event.key
                if event.type == pygame.KEYDOWN and key == pygame.K_ESCAPE:
                    running = False
                    continue
                name = ARROWS.get(key) or pygame.key.name(key)
                sdl_now = bool(pygame.key.get_pressed()[key])
                if event.type == pygame.KEYDOWN:
                    counts.setdefault(key, [0, 0])[0] += 1
                    previous = last_down.get(key)
                    spacing = f", {now - previous} ms since the last press" if previous else ""
                    if previous:
                        spacing_downs.setdefault(key, []).append(now - previous)
                    last_down[key] = now
                    emit(
                        f"{now:>8} DOWN {name}{spacing}; SDL now says {'down' if sdl_now else 'up'}"
                    )
                    if speech is not None and key in ARROWS:
                        speech.say(f"{name}. {LONG_LINE}", interrupt=True)
                else:
                    counts.setdefault(key, [0, 0])[1] += 1
                    pressed = last_down.get(key)
                    gap = f" {now - pressed} ms after its press" if pressed is not None else ""
                    if pressed is not None:
                        gaps_down_up.setdefault(key, []).append(now - pressed)
                    emit(f"{now:>8} UP   {name}{gap}; SDL now says {'down' if sdl_now else 'up'}")
        snapshot = tracker.snapshot()
        pressed_now = pygame.key.get_pressed()
        for key in ARROWS:
            for held, since, longest in (
                (bool(pressed_now[key]), sdl_hold_since, longest_sdl_hold),
                (bool(snapshot[key]), tracker_hold_since, longest_tracker_hold),
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
        for i, line in enumerate(
            (
                "Freight Fate key probe -- hold the arrows, Escape to finish",
                status,
                f"log: {args.log}",
            )
        ):
            screen.blit(font.render(line, True, (230, 230, 230)), (20, 30 + i * 36))
        pygame.display.flip()

    for key in ARROWS:
        for since, longest in (
            (sdl_hold_since, longest_sdl_hold),
            (tracker_hold_since, longest_tracker_hold),
        ):
            if key in since:
                longest[key] = max(longest.get(key, 0), pygame.time.get_ticks() - since.pop(key))

    emit("")
    emit("summary")
    if not counts:
        emit("no key events arrived. Was the probe window focused?")
    for key, (downs, ups) in counts.items():
        name = ARROWS.get(key) or pygame.key.name(key)
        gaps = gaps_down_up.get(key, [])
        spacing = spacing_downs.get(key, [])
        parts = [f"{name}: {downs} presses, {ups} releases"]
        if gaps:
            parts.append(f"release came a median {statistics.median(gaps):.0f} ms after its press")
        if spacing:
            parts.append(f"presses a median {statistics.median(spacing):.0f} ms apart")
        parts.append(f"longest hold SDL saw {longest_sdl_hold.get(key, 0)} ms")
        parts.append(f"longest hold the game read {longest_tracker_hold.get(key, 0)} ms")
        emit("; ".join(parts) + ".")
    verdict = None
    if any(gaps for gaps in gaps_down_up.values()):
        every_gap = [g for gaps in gaps_down_up.values() for g in gaps]
        if statistics.median(every_gap) <= 25:
            verdict = (
                "Your screen reader re-sends each key as an instant press and release: "
                "the game never sees the key held by itself, and the tracker is what "
                "makes holding work."
            )
        else:
            verdict = (
                "Your keys reach the game as real holds: the release comes when your "
                "finger lifts, and the tracker changes nothing."
            )
        emit(verdict)
    log_file.close()
    if speech is not None:
        if verdict:
            speech.say(verdict, interrupt=True)
        pygame.time.wait(6000)  # let the verdict finish before speech shuts down
        speech.shutdown()
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
