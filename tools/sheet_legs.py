"""Print every built leg touching a set of cities -- for signsheet headers.

Usage:
  uv run python tools/sheet_legs.py indio_ca_us blythe_ca_us phoenix_az_us ...

Given city slugs, lists all real world legs whose endpoints are BOTH in the
set (the corridor's internal legs) plus, optionally, legs reaching one hop
out. Output is ready to paste as a "Built legs" block in a Ready_*.md sheet.
"""

import json
import sys
from pathlib import Path

WORLD = Path(__file__).resolve().parents[1] / "src/freight_fate/data/world.json"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    one_hop = "--neighbors" in sys.argv
    if not args:
        print("give city slugs (optionally --neighbors)", file=sys.stderr)
        return 2
    cities = set(args)
    w = json.loads(WORLD.read_text(encoding="utf-8"))
    legs = w["legs"]
    internal, reaching = [], []
    for lg in legs:
        f, t = lg["from"], lg["to"]
        if f in cities and t in cities:
            internal.append(lg)
        elif one_hop and (f in cities or t in cities):
            reaching.append(lg)
    internal.sort(key=lambda lg: (lg["from"], lg["to"]))
    reaching.sort(key=lambda lg: (lg["from"], lg["to"]))

    def fmt(lg):
        return f"`{lg['from']} -> {lg['to']}` ({round(lg['miles'])})"

    print(f"# {len(internal)} internal legs among {len(cities)} cities")
    print(", ".join(fmt(lg) for lg in internal))
    if one_hop:
        print(f"\n# {len(reaching)} legs reaching one hop out")
        print(", ".join(fmt(lg) for lg in reaching))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
