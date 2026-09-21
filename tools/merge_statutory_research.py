"""Turn the research group files into the curated Python literal."""

import json
import textwrap
from pathlib import Path

SCRATCH = Path(
    r"C:\Users\joshu\AppData\Local\Temp\claude\C--Users-joshu-Freight-fate\def536f9-56cb-4461-901f-3b58cf36fe4e\scratchpad"
)

# One group answered in USPS codes rather than spoken names, which silently
# ADDED four rows instead of replacing four -- the table read 53 states and
# the game went on falling back for the very four that had just been
# confirmed. Normalise before keying.
ABBR = {
    "AL": "Alabama",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}
rows = {}
for path in sorted(SCRATCH.glob("statutory_*.json")):
    for r in json.loads(path.read_text(encoding="utf-8")):
        name = str(r["state"]).strip()
        name = ABBR.get(name.upper(), name)
        r["state"] = name
        rows[name] = r


def wrap(text, indent=8, width=88):
    text = " ".join(str(text or "").split())
    if not text:
        return '""'
    # Never split a token: a URL broken across two string literals is a
    # citation nobody can follow.
    lines = textwrap.wrap(
        text, width=width - indent - 2, break_long_words=False, break_on_hyphens=False
    )
    if len(lines) == 1:
        return json.dumps(lines[0])
    pad = " " * (indent + 4)
    body = "".join(f"{pad}{json.dumps(line + ' ')}\n" for line in lines[:-1])
    tail = f"{pad}{json.dumps(lines[-1])}\n"
    return "(\n" + body + tail + " " * indent + ")"


out = []
for state in sorted(rows):
    r = rows[state]

    # The two research prompts named these fields differently
    # (business_district_mph vs business_mph). Reading only one spelling
    # turned four CONFIRMED states into empty rows that then declared
    # themselves as having no district default -- a research success
    # transcribed into the exact shape of a research failure.
    def pick(row, *names):
        for n in names:
            if row.get(n) is not None:
                return row[n]
        return None

    b = pick(r, "business_district_mph", "business_mph")
    res = pick(r, "residence_district_mph", "residence_mph")
    u = pick(r, "urban_district_mph", "urban_mph")
    # Catch a THIRD spelling before it costs another silent discard: if this
    # row carries any mph field we did not read, and we read nothing, the
    # transcription is wrong -- not the research.
    known = {
        "business_district_mph",
        "business_mph",
        "residence_district_mph",
        "residence_mph",
        "urban_district_mph",
        "urban_mph",
    }
    if b is None and res is None and u is None:
        stray = [k for k, v in r.items() if k.endswith("_mph") and k not in known and v is not None]
        if stray:
            raise SystemExit(
                f"{state}: no figure read, but the row carries {stray} -- "
                "add that spelling to pick() rather than shipping an empty row"
            )
    empty = b is None and res is None and u is None
    out.append(f'    "{state}": {{')
    out.append(f'        "business_mph": {b!r}, "residence_mph": {res!r}, "urban_mph": {u!r},')
    if empty:
        out.append('        "no_district_default": True,')
    out.append(f'        "citation": {wrap(r.get("citation"))},')
    out.append(f'        "title": {wrap(r.get("title"))},')
    out.append(f'        "url": {json.dumps(r.get("url", ""))},')
    out.append(f'        "rule_type": {json.dumps(r.get("rule_type", ""))},')
    out.append(f'        "signs_required": {bool(r.get("signs_required"))},')
    out.append(f'        "truck_note": {wrap(r.get("truck_note"))},')
    out.append(f'        "verified": {bool(r.get("verified"))},')
    out.append(f'        "notes": {wrap(r.get("notes"))},')
    out.append("    },")
print(f"# {len(rows)} states")
print("\n".join(out))
