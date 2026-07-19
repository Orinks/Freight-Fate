"""Harness sweep: one headless delivery per highway system, with transcript checks.

Runs the shared playtest harness across a corridor from each road system in
the shipped world (Interstate, US route, and each state system), scans every
transcript for speech regressions, and prints a per-corridor report. Exits
non-zero if any corridor fails to deliver or any check trips, so it can gate
a data regeneration or a speech change.

Usage::

    uv run python tools/playtest_sweep.py
    uv run python tools/playtest_sweep.py --show-transcripts
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from world_source import load_world

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

CHECKS = [
    ("TBD road name", re.compile(r"\bTBD\b")),
    ("zero-distance lead", re.compile(r"\bIn 0 (miles|kilometers)\b")),
    ("singular-mile plural", re.compile(r"\b1 miles\b")),
    ("doubled period", re.compile(r"\.\.")),
    ("doubled name", re.compile(r"\b(.{6,}?), \1\b")),
]


class _Monkeypatch:
    """Minimal stand-in for pytest's monkeypatch (harness only uses setattr)."""

    def setattr(self, obj: object, name: str, value: object) -> None:
        setattr(obj, name, value)


def corridors_by_system() -> list[tuple[str, str, str, str]]:
    """The shortest corridor from each highway-name system in the world."""
    data = load_world()
    best: dict[str, tuple[str, str, str, float]] = {}
    for leg in data["legs"]:
        highway = leg.get("highway") or "TBD"
        system = highway.split()[0].rstrip("0123456789").rstrip("-") or "TBD"
        miles = float(leg["miles"])
        if system not in best or miles < best[system][3]:
            best[system] = (leg["from"], leg["to"], highway, miles)
    return [
        (system, origin, destination, highway)
        for system, (origin, destination, highway, _miles) in sorted(best.items())
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Headless per-system transcript sweep.")
    parser.add_argument(
        "--show-transcripts",
        action="store_true",
        help="Print each corridor's full transcript, not just the findings.",
    )
    args = parser.parse_args(argv)

    from playtest_harness import PlaytestHarness

    failures = 0
    for system, origin, destination, highway in corridors_by_system():
        try:
            with PlaytestHarness(_Monkeypatch()) as harness:
                result = harness.start_route(origin, destination)
                harness.drive_delivery_to_completion()
        except Exception as exc:  # noqa: BLE001 -- report and keep sweeping
            print(f"== {system}: {origin} -> {destination}  FAILED TO DELIVER: {exc!r}")
            failures += 1
            continue
        findings = []
        for name, pattern in CHECKS:
            hits = [line for line in result.transcript if pattern.search(line)]
            if hits:
                findings.append((name, len(hits), hits[0]))
        verdict = "clean" if not findings else f"{len(findings)} finding(s)"
        print(f"== {system}: {origin} -> {destination} via {highway} -- {verdict}")
        for name, count, sample in findings:
            failures += 1
            print(f"   [{name}] x{count}: {sample[:140]}")
        if args.show_transcripts:
            for line in result.transcript:
                print(f"   | {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
