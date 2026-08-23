"""Cap baked curve advisories at the top of the table they come from.

The bake computes its advisory by solving AASHTO's point-mass control for V.
That control's friction table is published for 20 through 80 mph and stops
there, because no US road is designed above 80 -- the highest posted limit in
the country is the 85 on Texas SH-130. Run unclamped on a gentle bend the
formula reads out 115, which is not a claim about a road; it is arithmetic
past the edge of its own table.

MEASURED before the fix: 21,076 of 63,873 baked rows (33 percent) carried an
advisory above 80, the worst at 115, on radii from 1,517 to 2,999 ft.

Nothing a driver can hear moves. An advisory above the posted limit never
fires a pacenote, never counts as corner overspeed and never eases cruise, so
115 and 80 behave identically under a truck. The point is that the stored
number means what it says, and no future consumer can read one of these as a
real advisory plaque.

WHY CLAMP RATHER THAN RECOMPUTE. The advisory is a pure function of radius,
so re-deriving the whole column looked tempting -- and it is wrong. The bake
computes the advisory from the UNROUNDED apex radius and then stores the
radius rounded, so recomputing from the stored integer moves 95 rows that sit
on a 5 mph boundary (a 112.6 ft apex stored as 113 reads 20 mph as baked and
25 mph recomputed). Those rows are correct as they stand. Clamping touches
only rows above the cap and leaves every other byte alone, which is also what
makes the pass idempotent and its diff reviewable.

The same cap lives in ``tools/straw_curve_sample.py`` (so a fresh sweep is
born clamped) and in ``data/curves.py`` (so the load-time repricing for
superelevation cannot climb back over it). This tool exists for the rows
already on disk.

Usage
-----
    uv run python tools/clamp_curve_advisories.py --report
    uv run python tools/clamp_curve_advisories.py --write
    uv run python tools/clamp_curve_advisories.py --check   # exit 1 if stale
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from straw_curve_sample import ADVISORY_MAX_MPH  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CURVES = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "gameplay" / "curves.jsonl"


def clamp() -> tuple[str, int, int, int]:
    """``(new shard text, rows, rows clamped, worst advisory seen)``."""
    lines = CURVES.read_text(encoding="utf-8").splitlines()
    meta_line = next((line for line in lines if line.startswith('{"meta"')), None)
    rows = [json.loads(line) for line in lines if line.strip() and not line.startswith('{"meta"')]

    clamped = 0
    worst = 0
    for row in rows:
        advisory = int(row["advisory_mph"])
        worst = max(worst, advisory)
        if advisory > ADVISORY_MAX_MPH:
            row["advisory_mph"] = ADVISORY_MAX_MPH
            clamped += 1

    payload = "\n".join(
        json.dumps(r, sort_keys=True) for r in sorted(rows, key=lambda r: (r["leg"], r["seq"]))
    )
    meta = json.loads(meta_line)["meta"] if meta_line else {"schema": 1}
    meta["data_version"] = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    meta.setdefault("params", {})["advisory_max_mph"] = ADVISORY_MAX_MPH
    text = json.dumps({"meta": meta}, sort_keys=True) + "\n" + payload + "\n"
    return text, len(rows), clamped, worst


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="rewrite curves.jsonl")
    ap.add_argument("--check", action="store_true", help="exit 1 if any row is over the cap")
    ap.add_argument("--report", action="store_true", help="print the count, no write")
    args = ap.parse_args()

    text, total, clamped, worst = clamp()
    print(
        f"{total} curve rows | {clamped} above {ADVISORY_MAX_MPH} mph "
        f"({100 * clamped / total:.1f}%), worst {worst}"
    )
    if args.check:
        if CURVES.read_text(encoding="utf-8") != text:
            print(f"STALE: rows still carry an advisory above {ADVISORY_MAX_MPH}")
            return 1
        print("up to date")
        return 0
    if args.write:
        CURVES.write_text(text, encoding="utf-8")
        print(f"wrote {CURVES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
