"""Brand-derived truck-stop amenities.

Turns a truck stop's *name* into the real brand behind it, the service tier,
and the signature service that brand is known for -- tire care at Love's, the
repair shop at a TravelCenters of America, showers and fuel deals at
Pilot/Flying J. It is derived at runtime from the stop name, so it needs no
change to the world data: any new stop the map's truck-stop sweep discovers is
classified the moment it appears (a fresh Love's is a tire stop with no extra
tagging), and the amenities layer can never drift out of sync with the map.

The point, beyond flavor, is a planning decision: "I need tires, find me a
Love's" / "the rig needs the shop, find a TA". Brand identity teaches real
trucking knowledge just by playing, and later feeds a service-stop buff system
(fatigue, tire, wear, morale axes -- never the legal duty clock).

Everything here is player-facing speech: full brand names, no codes, no raw
map tags, no bare initialisms a screen reader would spell out.

Sources: public brand service listings -- Love's tire care / Speedco quick
lube, TravelCenters of America truck service and Petro Iron Skillet, the Pilot
Flying J shower network. Real brand names are used nominatively, matching the
stop-name conventions already in the world data. "Big Buck's" is an original
parody of the well-known Texas travel-center chain that famously bans big rigs;
the parody keeps the joke and drops the trademark.
"""

from __future__ import annotations

from dataclasses import dataclass

AMENITIES_SOURCE = (
    "Brand service identity derived at runtime from the stop name; grounded in "
    "public brand service listings (Love's/Speedco tire care, TravelCenters of "
    "America truck service, Pilot Flying J shower network)."
)

# Spoken label for each signature service key. Kept here (not shared with the
# generic POI service labels) because these are brand differentiators phrased
# for a driver, e.g. a Love's "specialty," not a bare checklist entry.
SIGNATURE_SERVICE_LABELS = {
    "tires": "tire care and quick lube",
    "showers": "showers",
    "repair": "a truck repair shop",
    "restaurant": "a sit-down restaurant",
    "barbecue": "smoked barbecue and brisket",
    "souvenirs": "souvenirs and road snacks",
    "cat_scale": "a Cat certified weigh scale",
    "laundry": "public laundry facilities",
    "game_room": "a game room",
    "barber": "a barber shop",
    "premium_wifi": "premium wifi",
    "check_cashing": "check cashing services",
    "def": "diesel exhaust fluid lanes",
    "atm": "ATM services",
}


@dataclass(frozen=True)
class Brand:
    """A recognized truck-stop brand and what it is known for.

    ``tier`` is a coarse class the future buff system reads: ``travel_center``
    for a full-service major chain, ``landmark`` for a destination stop like
    Big Buck's. ``signature`` lists the service keys this brand is the place to
    go for. ``bans_big_rigs`` marks a stop a Class-8 truck cannot pull into with
    a trailer (the Big Buck's gag) -- reachable only bobtail.
    """

    key: str
    spoken: str
    tier: str
    signature: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    bans_big_rigs: bool = False


# Ordered most-specific keyword first so a combined name (e.g. "TA Petro")
# resolves deterministically. Keywords are matched as lowercased substrings of
# the stop name; none is a bare initialism that could collide with a place name
# (mirrors the truck-POI keyword discipline in tools/enrich_routes_pois.py).
BRANDS: tuple[Brand, ...] = (
    Brand(
        "speedco",
        "Speedco",
        "travel_center",
        signature=("tires",),
        keywords=("speedco",),
    ),
    Brand(
        "loves",
        "Love's",
        "travel_center",
        signature=("tires",),
        keywords=("love's", "loves travel"),
    ),
    Brand(
        "petro",
        "Petro",
        "travel_center",
        signature=("repair", "restaurant"),
        keywords=("petro stopping", "petro travel"),
    ),
    Brand(
        "ta",
        "TravelCenters of America",
        "travel_center",
        signature=("repair",),
        keywords=("travelcenters", "ta travel", "ta petro"),
    ),
    Brand(
        "flying_j",
        "Flying J",
        "travel_center",
        signature=("showers", "cat_scale", "laundry", "premium_wifi", "game_room"),
        keywords=("flying j",),
    ),
    Brand(
        "pilot",
        "Pilot",
        "travel_center",
        signature=("showers", "cat_scale", "laundry", "premium_wifi"),
        keywords=("pilot",),
    ),
    Brand(
        "big_bucks",
        "Big Buck's",
        "landmark",
        signature=("barbecue", "souvenirs"),
        keywords=("big buck", "buc-ee", "bucee", "buckee"),
        bans_big_rigs=True,
    ),
)


def _join(parts: list[str]) -> str:
    """Join spoken fragments with an Oxford ``and`` (mirrors the driving HUD)."""
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def classify_brand(name: str) -> Brand | None:
    """Recognize the truck-stop brand from a stop name, or ``None`` if generic.

    Independent stops and unbranded rest areas return ``None`` -- they keep the
    plain listed services from the world data with no brand embellishment.
    """
    low = " ".join(str(name).lower().split())
    for brand in BRANDS:
        if any(keyword in low for keyword in brand.keywords):
            return brand
    return None


def signature_services(name: str) -> tuple[str, ...]:
    """The service keys a stop's brand is the place to go for (empty if generic).

    The service-planning and future buff systems read this to answer "which
    stop for tires / the shop / a shower" without re-parsing the name.
    """
    brand = classify_brand(name)
    return brand.signature if brand else ()


def spoken_amenities(name: str, stop_type: str = "") -> str:
    """A spoken clause about the brand's specialty, or ``""`` for a generic stop.

    Appended to the stop's listed services in the driving route info, so a Love's
    reads as a tire stop and a landmark like Big Buck's announces that big rigs
    cannot pull in. ``stop_type`` is accepted for future tier-aware phrasing.
    """
    brand = classify_brand(name)
    if brand is None:
        return ""
    phrase = _join(
        [SIGNATURE_SERVICE_LABELS.get(key, key.replace("_", " ")) for key in brand.signature]
    )
    if brand.tier == "landmark":
        clause = f"{brand.spoken} is a roadside landmark known for {phrase}"
        if brand.bans_big_rigs:
            clause += "; no big rigs allowed, so you can only stop here running bobtail"
        return clause
    if not phrase:
        return ""
    return f"{brand.spoken} specialty: {phrase}"


__all__ = [
    "AMENITIES_SOURCE",
    "SIGNATURE_SERVICE_LABELS",
    "Brand",
    "BRANDS",
    "classify_brand",
    "signature_services",
    "spoken_amenities",
]
