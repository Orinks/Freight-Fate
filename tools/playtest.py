"""Play a headless delivery and print the spoken transcript.

Freight Fate is audio-first, so the reviewable signal from a playthrough is the
transcript of everything the game says, not a screenshot. This drives the real
game states (no window, no speech) through the shared playtest harness and
prints that transcript -- handy for eyeballing a change end to end, or for
verifying a specific corridor after editing route data.

Usage::

    uv run python tools/playtest.py                       # new-career delivery
    uv run python tools/playtest.py --route "Newark->New York"
    uv run python tools/playtest.py --route "New York->Philadelphia" --events-only

``--route`` drives one supported corridor directly (skipping the menus); without
it a fresh career takes whatever the dispatch board offers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The reusable harness lives beside the tests; it forces the headless
# (dummy video/audio, no speech) environment on import.
sys.path.insert(0, str(ROOT / "tests"))


class _Monkeypatch:
    """Minimal stand-in for pytest's monkeypatch (harness only uses setattr)."""

    def setattr(self, obj: object, name: str, value: object) -> None:
        setattr(obj, name, value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Headless transcript playtest.")
    parser.add_argument(
        "--route",
        help="Drive a specific supported route, e.g. 'Newark->New York'. "
        "Omit to run a new-career delivery.",
    )
    parser.add_argument("--job-rank", type=int, default=0, help="New-career job pick.")
    parser.add_argument("--route-rank", type=int, default=0, help="New-career route pick.")
    parser.add_argument(
        "--events-only",
        action="store_true",
        help="Print only the GPS/event cues, not every spoken line.",
    )
    args = parser.parse_args(argv)

    from playtest_harness import PlaytestHarness

    with PlaytestHarness(_Monkeypatch()) as harness:
        if args.route:
            origin, _, destination = args.route.partition("->")
            if not destination:
                raise SystemExit("--route must be 'From->To'")
            result = harness.start_route(origin.strip(), destination.strip())
        else:
            result = harness.start_delivery(job_rank=args.job_rank, route_rank=args.route_rank)
        driving = harness.driving
        assert driving is not None
        header = (
            f"{driving.job.origin} -> {driving.job.destination} "
            f"via {', '.join(driving.trip.route.highways)} "
            f"({driving.trip.total_miles:.0f} mi)"
        )
        harness.drive_delivery_to_completion()

    print("=" * 70)
    print(f"PLAYTEST: {header}")
    print("=" * 70)
    for line in result.transcript:
        if args.events_only and not line.startswith("[event]"):
            continue
        print(line)
    print(
        f"\nDelivered to {result.destination}; "
        f"career deliveries {result.deliveries}; "
        f"{result.remaining_miles:.0f} mi remaining."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
