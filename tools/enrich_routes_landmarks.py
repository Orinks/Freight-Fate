# ruff: noqa: I001
"""Narratable roadside features from OpenStreetMap -- the SELECT filter.

This is the query-side, offline half of the OSM roadside-narration feature: pure
functions that decide whether an OSM element is worth speaking as ambient
roadside color ("Entering Coconino National Forest", "Crossing the Colorado
River", "Route 66 Museum ahead") and clean its name for speech. It is separate
from ``_truck_relevance`` in ``enrich_routes_pois``, which *drops* non-truck fuel
stations; this one *selects* landmarks. Kept standalone (no build-time imports,
no network) so it unit-tests with plain tag dicts and never disturbs a running
enrichment sweep.

The matching bake that actually queries the self-hosted Overpass and writes
``world.json`` is a separate map-pipeline step; it reuses ``overpass_query`` and
``classify_narratable_feature`` here. There are two filters, not one:

* This QUERY filter -- what we ask Overpass for and keep, at build time.
* The Overpass DB's IMPORT filter -- what tags the self-hosted instance even
  holds, decided when its ``.osm.pbf``/``.bz2`` extract is built. If the extract
  was trimmed to highways to fit RAM, none of these features are present and the
  bake finds nothing. ``osmium_tags_filter`` emits the exact tag set to KEEP so
  the import can be widened (targeted-wide, not full-planet).

Names come from the OSM ``name`` tag, spoken verbatim, so they are scrubbed of
raw tag markers and common abbreviations are expanded ("Mt." -> "Mount"). Unlike
hand-authored billboard copy, a real place name may legitimately carry digits
("Route 66 Museum"), which a screen reader reads correctly, so digits are kept.
"""

from __future__ import annotations

import re

# Category priority: when a leg's landmark budget is capped, keep the headline
# features first. A national park outranks a generic protected area; a mountain
# pass or river crossing (rare, evocative, route-relevant) outranks a museum.
_RANK = {
    "national_park": 100,
    "wilderness": 80,
    "national_forest": 70,
    "mountain_pass": 60,
    "river": 50,
    "museum": 40,
    "protected_area": 30,
}

# One source of truth for both the Overpass query and the DB import filter.
# (osm_type, key, value); ``nwr`` means node-or-way-or-relation.
NARRATABLE_OSM_TAGS = (
    ("relation", "boundary", "national_park"),
    ("relation", "boundary", "protected_area"),
    ("way", "leisure", "nature_reserve"),
    ("nwr", "tourism", "museum"),
    ("node", "mountain_pass", "yes"),
    ("way", "waterway", "river"),
)

_RAW_NAME_MARKERS = (
    "osm",
    "amenity=",
    "highway=",
    "boundary=",
    "node/",
    "way/",
    "relation/",
    "wikidata=",
)

# Abbreviations that read badly through a screen reader, expanded for speech.
# Deliberately excludes "St." (Saint vs Street is ambiguous) to avoid guessing.
_ABBREVIATIONS = (
    (re.compile(r"\bMt\.?(?=\s)"), "Mount"),
    (re.compile(r"\bMtn\.?\b"), "Mountain"),
    (re.compile(r"\bFt\.?(?=\s)"), "Fort"),
    (re.compile(r"\bNatl\.?\b"), "National"),
)


def clean_landmark_name(value: str) -> str:
    """A spoken-clean place name, or ``""`` if it is unusable.

    Collapses whitespace, rejects names carrying raw OSM tag markers, and
    expands screen-reader-hostile abbreviations. Real digits are preserved.
    """
    name = " ".join(str(value or "").replace("\n", " ").split()).strip()
    if len(name) < 2:
        return ""
    if any(marker in name.lower() for marker in _RAW_NAME_MARKERS):
        return ""
    for pattern, replacement in _ABBREVIATIONS:
        name = pattern.sub(replacement, name)
    return name[:80]


def _category(tags: dict[str, str], low_name: str) -> tuple[str, str] | tuple[None, None]:
    """Return ``(category, kind)`` for an OSM element, or ``(None, None)``.

    Name-led for US protected areas (the ``name`` suffix is more reliable than
    the boundary tag, which mislabels some forests and parks), tag-led for point
    features.
    """
    boundary = tags.get("boundary", "")
    # Zones (enter-a-region) -- name suffix wins so "Petrified Forest National
    # Park" is a park, not misfiled under forest by the word "forest".
    if low_name.endswith("national park"):
        return "national_park", "zone"
    if low_name.endswith(("national forest", "national grassland")):
        return "national_forest", "zone"
    if low_name.endswith("wilderness") or tags.get("protect_class") in {"1a", "1b"}:
        return "wilderness", "zone"
    if boundary == "national_park":
        return "national_park", "zone"
    if boundary == "protected_area" or tags.get("leisure") == "nature_reserve":
        return "protected_area", "zone"
    # Points (pass-a-spot).
    if tags.get("tourism") == "museum":
        return "museum", "point"
    if tags.get("mountain_pass") == "yes":
        return "mountain_pass", "point"
    if tags.get("waterway") == "river":
        return "river", "point"
    return None, None


def classify_narratable_feature(
    tags: dict[str, str], name: str | None = None
) -> dict[str, object] | None:
    """Classify an OSM element as a narratable landmark, or ``None`` to drop it.

    Returns ``{"category", "kind", "rank", "name"}`` where ``kind`` is ``"zone"``
    (protected areas, spoken on entry) or ``"point"`` (a spot you pass). An
    unnamed feature is dropped -- you cannot announce a nameless thing.
    """
    clean = clean_landmark_name(tags.get("name", "") if name is None else name)
    if not clean:
        return None
    category, kind = _category(tags, clean.lower())
    if category is None:
        return None
    return {"category": category, "kind": kind, "rank": _RANK[category], "name": clean}


def spoken_landmark_text(feature: dict[str, object]) -> str:
    """The ambient cue line for a classified landmark (player-facing speech)."""
    name = str(feature["name"])
    category = feature["category"]
    if feature["kind"] == "zone":
        return f"Entering {name}"
    if category == "museum":
        return f"{name} ahead" if "museum" in name.lower() else f"Museum ahead: {name}"
    if category == "river":
        base = name if "river" in name.lower() else f"{name} River"
        return f"Crossing the {base}"
    if category == "mountain_pass":
        return f"Approaching {name}"
    return f"{name} ahead"


def overpass_query(bbox: str, timeout_s: int = 60) -> str:
    """Overpass QL selecting every narratable category within ``bbox``.

    ``bbox`` is an Overpass area clause, e.g. a ``south,west,north,east`` tuple
    string. The bake fills it per corridor sample point.
    """
    body = "\n".join(
        f'  {osm_type}["{key}"="{value}"]({bbox});' for osm_type, key, value in NARRATABLE_OSM_TAGS
    )
    return f"[out:json][timeout:{timeout_s}];\n(\n{body}\n);\nout tags center;"


def osmium_tags_filter() -> str:
    """The tag set to KEEP when trimming an OSM extract for the import filter.

    Feeds ``osmium tags-filter`` when widening the self-hosted Overpass DB beyond
    a highways-only extract so these features actually exist to be queried.
    """
    prefix = {"node": "n", "way": "w", "relation": "r", "nwr": "nwr"}
    return " ".join(
        f"{prefix[osm_type]}/{key}={value}" for osm_type, key, value in NARRATABLE_OSM_TAGS
    )


__all__ = [
    "NARRATABLE_OSM_TAGS",
    "clean_landmark_name",
    "classify_narratable_feature",
    "spoken_landmark_text",
    "overpass_query",
    "osmium_tags_filter",
]
