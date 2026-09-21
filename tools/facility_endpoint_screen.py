"""Screen a sourced facility endpoint: is the OSM object a place a truck is sent?

Build-time only. `build_facility_approaches` asks this before it routes a
street chain to an endpoint, because a confident chain to the wrong door is
worse than the fallback.

Why it exists. `build_facility_endpoints.classify` matches substrings against
the object's name PLUS every ``key=value`` tag it carries, so the match is
often an accident of tagging rather than a fact about the place:

* ``substation=distribution`` makes a power substation a cross-dock, a dry
  warehouse and a company yard (279 endpoints);
* ``usage=freight`` or a name ending "Subdivision" makes a railway main line
  a logistics site (895 endpoints are ``railway=rail`` track);
* "port" is inside airport, transport and sports; "terminal" is a bus
  station, a ferry landing and a card reader; "mill" is a Miller, "assembly"
  an Assembly of God, "steel" a Steele Street.

Measured 2026-09-17 by reading the tags of all 2,779 source-backed endpoints
back out of the state extracts: see ``ROADMAP.md`` for the counts.

The rule is a POSITIVE list, read from the object's own tags, never from a
substring of the tag dump:

1. Refused outright: any ``highway``, ``power``, ``shop``, ``tourism``,
   ``leisure``, ``historic``, ``waterway`` or ``public_transport`` object
   (a ``barrier`` is NOT refused: a fenced industrial area is often drawn as
   its own fence, and a bare gate fails rule 2 anyway); any ``amenity``
   except a post depot; any ``railway`` except a yard; a pipeline; a
   lifecycle-prefixed site (``disused:``, ``abandoned:``, ``demolished:``).
2. Accepted as a freight site: ``building`` = warehouse, industrial, factory
   or manufacture; ``landuse=industrial``; ``man_made=works``; any
   ``industrial=*``; ``office`` = logistics or freight_forwarder;
   ``amenity=post_depot``. A rail yard or railway land also serves the
   intermodal types, a harbour or port area the port types, a silo the grain
   elevators, quarry land the quarries and aggregate yards, and
   ``craft=sawmill`` the lumber and paper sites (2026-09-20: those four
   families had no rule at all, so every one of their 419 rows was a
   fallback).
3. Steel, automotive and chemical facilities were matched by name substring,
   so they must ALSO say what they make: an ``industrial`` or ``product`` tag
   of the right kind, or the type's word in the NAME on a word boundary
   ("steel", never "Steele"; "mill" and "assembly" alone prove nothing).

This is a screen, not an edit: ``facility_endpoints.json`` keeps every
record, the refusal and its reason go in the approach row, and the rule can
be re-judged without a re-sweep. It cannot find a BETTER endpoint for a
facility whose match was wrong; that needs the endpoint sweep re-run with a
classifier that reads tags the way this does.
"""

from __future__ import annotations

import re

REFUSED_KEYS = (
    "highway",
    "power",
    "shop",
    "tourism",
    "leisure",
    "historic",
    "waterway",
    "public_transport",
    "pipeline",
)
LIFECYCLE_PREFIXES = ("disused:", "abandoned:", "demolished:", "razed:", "was:")
SITE_BUILDINGS = frozenset({"warehouse", "industrial", "factory", "manufacture"})
LOGISTICS_OFFICES = frozenset({"logistics", "freight_forwarder"})
INTERMODAL_TYPES = frozenset({"intermodal_ramp", "intermodal", "rail"})
PORT_TYPES = frozenset({"port", "port_terminal"})
# Four families whose sites state their trade with a tag the general list
# cannot hold: a grain elevator is a silo, a quarry is quarry land, an
# aggregate yard is often the pit it digs from, and a sawmill can carry only
# its craft. Each tag is scoped to its own family, the way a rail yard serves
# the intermodal types, so a farm silo never becomes a cross-dock.
ELEVATOR_TYPES = frozenset({"farm_elevator"})
QUARRY_TYPES = frozenset({"mine_quarry"})
MATERIALS_TYPES = frozenset({"construction_materials_yard"})
FOREST_TYPES = frozenset({"lumber_paper"})

# Types whose endpoint was matched by name substring: each must also state
# its trade, by tag value or by a whole word in the name.
TRADE_RULES: dict[str, tuple[frozenset[str], re.Pattern[str], re.Pattern[str]]] = {
    "steel_industrial": (
        frozenset({"steel_mill", "metal_processing", "scrap_yard", "foundry", "steelworks"}),
        re.compile(r"\b(steel|metal|iron|alumin(i)?um)\b"),
        re.compile(r"\b(steel|metals?|foundry|iron ?works|alumin(i)?um|forge|forging)\b"),
    ),
    "automotive_plant": (
        frozenset({"automotive_parts", "automobile_manufacturing", "automotive", "car_factory"}),
        re.compile(r"\b(automobiles?|cars?|vehicles?|trucks?)\b"),
        re.compile(r"\b(automotive|assembly plant|truck assembly|auto parts)\b"),
    ),
    "chemical_petroleum_terminal": (
        frozenset(
            {"petroleum_terminal", "refinery", "chemical", "oil", "oil_terminal", "tank_farm"}
        ),
        re.compile(r"\b(chemicals?|fertili[sz]er|petroleum|fuel|oil|gasoline)\b"),
        re.compile(
            r"\b(chemicals?|petroleum|petrochemicals?|refinery|refining|polymers?|"
            r"phosphates?|fertili[sz]er|tank farm|oil terminal)\b"
        ),
    ),
}
NAME_MATCHED_TYPES = frozenset(TRADE_RULES)


def screen_endpoint(facility_type: str, name: str, tags: dict[str, str] | None) -> tuple[bool, str]:
    """``(accepted, reason)``. ``reason`` is a plain sentence either way, and
    says what was READ from the object; nothing here is assumed."""
    if tags is None:
        return False, "The endpoint's source object is no longer in the local extract."
    for key in REFUSED_KEYS:
        if key in tags:
            return False, f"The sourced endpoint is a {_spoken(key)} object, not a freight site."
    if any(key.startswith(LIFECYCLE_PREFIXES) for key in tags):
        return False, "The sourced endpoint is tagged as a former site."
    amenity = tags.get("amenity")
    if amenity and amenity != "post_depot":
        return False, "The sourced endpoint is a public amenity, not a freight site."
    railway = tags.get("railway")
    if railway and railway != "yard":
        return False, "The sourced endpoint is railway track or a station, not a freight site."

    site = (
        tags.get("building") in SITE_BUILDINGS
        or tags.get("landuse") == "industrial"
        or tags.get("man_made") == "works"
        or "industrial" in tags
        or tags.get("office") in LOGISTICS_OFFICES
        or amenity == "post_depot"
    )
    if facility_type in INTERMODAL_TYPES:
        site = site or railway == "yard" or tags.get("landuse") == "railway"
    if facility_type in PORT_TYPES:
        site = site or tags.get("landuse") in {"port", "harbour"} or "harbour" in tags
    if facility_type in ELEVATOR_TYPES:
        site = site or tags.get("man_made") == "silo" or tags.get("building") == "silo"
    if facility_type in QUARRY_TYPES | MATERIALS_TYPES:
        site = site or tags.get("landuse") == "quarry" or tags.get("man_made") == "mineshaft"
    if facility_type in FOREST_TYPES:
        site = site or tags.get("craft") == "sawmill"
    if not site:
        return False, "The sourced endpoint carries no warehouse, industrial or works tag."

    rule = TRADE_RULES.get(facility_type)
    if rule is not None:
        industrial_values, product_words, name_words = rule
        stated = (
            tags.get("industrial") in industrial_values
            or bool(product_words.search(tags.get("product", "").lower().replace(";", " ")))
            or bool(name_words.search(name.lower()))
        )
        if not stated:
            return False, "The sourced endpoint is an industrial site of some other trade."
    return True, "The sourced endpoint is tagged as a warehouse, industrial or works site."


def _spoken(key: str) -> str:
    return {
        "highway": "road",
        "power": "power-grid",
        "shop": "retail",
        "public_transport": "transit",
    }.get(key, key)
