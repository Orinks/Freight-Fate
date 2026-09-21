"""Bake curated roadside billboards (and respectful landmark callouts) onto legs
from an approved sign sheet -- the parody/curated sibling of bake_landmarks.py.

Where bake_landmarks.py DISCOVERS features from OSM, this one places AUTHORED
signs from a human-approved sheet at their attraction's real milepost. Reads a
sheet (data/spider/signsheets/<corridor>.md): one block per sign --

    ### <name>
    - treatment: billboard | landmark | skip
    - leg: <from_slug> -> <to_slug>
    - at_mi: <float>
    - spoken: <exact spoken text>
    - describe: <optional pull-in text; NOT baked -- kept in the sheet for the
      future pull-off interaction>

Each non-skip block becomes a leg corridor.landmarks record, MERGED into the
leg's existing landmarks: the OSM-derived ones are preserved, and any prior
curated record of the same name is replaced (idempotent re-bake). Billboards use
category 'billboard_sign' (rides chatter_billboards, like the random pool); the
respectful 'landmark' treatment uses 'highway_marker' (rides chatter_passes),
an existing curated category, until a dedicated monument category is added.

    python bake_billboards.py --sheet data/spider/signsheets/i90-south-dakota.md [--write]

Idempotent + additive; without --write it is a dry run.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from world_source import load_world, save_world

# Treatment -> baked landmark category. Both are CURATED categories that
# bake_landmarks.py must preserve when it overwrites a leg's OSM landmarks.
TREATMENT_CATEGORY = {
    "billboard": "billboard_sign",
    "landmark": "highway_marker",
}


def parse_sheet(text: str) -> list[dict]:
    """Parse '### name' blocks with '- key: value' fields into sign dicts."""
    signs: list[dict] = []
    cur: dict | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("### "):
            cur = {"name": line[4:].strip()}
            signs.append(cur)
        elif line.startswith("## ") or line.strip() == "---":
            cur = None  # left the sign section (held-for-later / sources)
        elif cur is not None:
            m = re.match(r"\s*-\s*([A-Za-z_]+):\s*(.*)$", line)
            if m:
                cur[m.group(1).lower()] = m.group(2).strip()
    return signs


def sign_record(sign: dict) -> tuple[str, str, dict] | None:
    """Build (from, to, landmark record) for a bakeable sign, or None to skip."""
    treatment = sign.get("treatment", "").lower()
    category = TREATMENT_CATEGORY.get(treatment)
    if category is None:  # skip / unknown
        return None
    leg = sign.get("leg", "")
    if "->" not in leg:
        raise ValueError(f"{sign['name']}: leg needs 'from_slug -> to_slug', got {leg!r}")
    a, b = (s.strip() for s in leg.split("->", 1))
    spoken = sign.get("spoken", "").strip()
    if not spoken:
        raise ValueError(f"{sign['name']}: missing spoken text")
    if any(ch.isdigit() for ch in spoken):
        raise ValueError(f"{sign['name']}: spoken text has a bare digit -- spell it out")
    rec = {
        "name": sign["name"],
        "category": category,
        "kind": "point",
        "at_mi": round(float(sign["at_mi"]), 1),
        "spoken": spoken,
    }
    return a, b, rec


def merge_into_leg(leg: dict, rec: dict) -> None:
    """Add rec to leg.corridor.landmarks, replacing a prior same-name curated one."""
    lms = leg.setdefault("corridor", {}).setdefault("landmarks", [])
    lms[:] = [
        lm
        for lm in lms
        if not (lm.get("name") == rec["name"] and lm.get("category") == rec["category"])
    ]
    lms.append(rec)
    lms.sort(key=lambda r: r["at_mi"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    d = load_world()
    legs_by_pair = {(lg["from"], lg["to"]): lg for lg in d["legs"]}

    signs = parse_sheet(Path(a.sheet).read_text(encoding="utf-8"))
    baked = skipped = 0
    for sign in signs:
        built = sign_record(sign)
        if built is None:
            skipped += 1
            continue
        frm, to, rec = built
        leg = legs_by_pair.get((frm, to)) or legs_by_pair.get((to, frm))
        if leg is None:
            raise SystemExit(f"ERROR: no leg {frm} <-> {to} for sign {rec['name']!r}")
        merge_into_leg(leg, rec)
        baked += 1
        print(f"  {rec['category']:14} {frm}->{to} @ {rec['at_mi']:>6} mi  {rec['name']}")

    print(f"\nbaked {baked} signs, skipped {skipped}")
    if a.write:
        save_world(d)
        print("WRITTEN to the world source -- now run: uv run python tools/index_world.py")
    else:
        print("(dry run -- pass --write to apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
