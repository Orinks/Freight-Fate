"""Match an OpenStreetMap object to the freight facility types it can stand for.

Build-time only. `build_facility_endpoints.classify` is a thin wrapper over
:func:`match_roles`; `regeocode_far_facility_pins` reaches it the same way.

Why it was rewritten (2026-09-17). The first matcher built one string out of
the object's name PLUS every ``key=value`` tag and tested substrings of it. A
power substation (``substation=distribution``) became a cross-dock, a railway
main line (``usage=freight``, "... Industrial Lead") an industrial park, a
steel lattice tower (``material=steel``) a steel works, an airport a port.
Read back from the extracts, 567 of 2,779 sourced endpoints were freight
sites.

The rules now. Every value below is READ from the object: its primary-key
tags and the words of its own name. Nothing is inferred from a tag VALUE that
happens to contain a trade word, and nothing is guessed from position.

1. THE GATE (read). A pair (object, facility type) is a match only if
   ``facility_endpoint_screen.screen_endpoint`` accepts it. That module is the
   single statement of what can never be a truck destination (any highway,
   power, shop, tourism, leisure, historic, waterway, transit or pipeline
   object; any amenity but a post depot; any railway object but a yard; a
   former site) and of what is a freight site (``building`` = warehouse,
   industrial, factory, manufacture; ``landuse=industrial``;
   ``man_made=works``; any ``industrial=*``; a logistics office; a post
   depot). Its two stated exceptions are the ones this matcher relies on:
   rail yards and railway land serve the intermodal types, harbour and port
   land the port types. The rules are not forked here, so an endpoint this
   matcher writes is one the approaches builder will route to. Residential
   and retail land never reaches a rule: it carries none of the site tags.
2. THE TRADE (read). On top of the gate the object must say what it is, by a
   tag of its own or by WHOLE WORDS in its name, operator or brand ("steel"
   counts, "Steele" does not; "port of" counts, "airport" does not):

   * warehouse family (dry warehouse, warehouse, distribution, cross-dock,
     terminal, company yard): ``building=warehouse``, ``industrial`` =
     logistics, warehouse, warehousing, distribution, distributor or
     trucking, a logistics office that is also an industrial building or
     land (a courier's desk in a tower is not); or the words logistics, freight,
     warehouse, distribution, cross dock, trucking, cartage, truck or
     freight terminal. ``industrial=depot`` is NOT a rule: read back, it is
     bus garages and highway-department yards. Self storage is left out.
   * manufacturing: ``man_made=works``, ``building`` = factory or
     manufacture, ``industrial`` = factory or manufacturing; or the words
     manufacturing, factory, plant, works, mill, foundry, fabrication,
     industries and their kin.
   * industrial park: ``landuse=industrial`` whose name says industrial,
     business, commerce or logistics park, centre, district or complex.
   * intermodal, rail: ``railway=yard``; railway land named a yard, ramp or
     terminal; any accepted site named intermodal, transload or rail port.
     Passenger and transit yards (Amtrak, metro, light rail) are left out.
   * port: ``industrial=port``; or "port of", seaport, port authority, a
     marine, container, cargo, bulk or shipping terminal, on a site
     the gate accepts for a port (which includes ``landuse`` = port or
     harbour and a ``harbour`` tag). Harbour land ALONE is not a rule: read
     back, it is marinas and excursion-boat landings. Marinas, yacht clubs,
     cruise and ferry terminals are left out by name.
   * cold storage: ``industrial`` = refrigerated_warehouse or cold_storage; or
     cold storage, refrigerated, freezer, frozen, and the two operators whose
     whole business it is (Americold, Lineage).
   * food processor: a food ``industrial`` or ``product`` value; or foods,
     meats, packing, poultry, dairy, bakery, bottling and their kin.
   * grocery or retail distribution centre: a warehouse-family identity AND
     a grocer's or retailer's name (a CURATED list of national chains plus
     the words grocery, grocers, foods, supermarket).
   * food terminal: produce, food or farmers with terminal, market or
     distribution.
   * parcel hub: ``amenity=post_depot``; or UPS, FedEx, DHL, USPS, postal,
     parcel, package, sortation, fulfillment, Amazon.
   * air cargo: the words air cargo, cargo or air freight.
   * steel, automotive, chemical and petroleum: the screen's own trade rules
     (an ``industrial`` or ``product`` value of the right kind, or the trade
     word in the name). A scrap yard or auto wrecker named "... Auto Parts"
     is not an automotive plant.

   Two name vetoes, both read from the name. A UTILITY name (water, sewage,
   treatment, power, heating plant, landfill, recycling), a "former ..."
   name, or the name of a building turned to another use (lofts, museum,
   brewery, school, church) vetoes the warehouse, manufacturing, food, steel,
   automotive and chemical rules outright: ``man_made=works`` is put on
   treatment plants and ``building=warehouse`` kept on loft conversions often
   enough that the tag cannot be allowed to win. A CIVIC or service name
   (county, department, maintenance, transit, body shop ...) vetoes those
   rules unless BOTH a tag and the name state the trade ("County Food Bank
   Warehouse" on ``building=warehouse`` stays; "County Fleet Garage" goes).

3. THE ASSUMED TIER. For the warehouse and manufacturing families only, an
   accepted freight site that states NO trade of any family and whose name
   reads as a business (Inc, Co, Corporation, Industries, Supply ...) is
   offered last, and the record says the trade is ASSUMED. The facilities
   are templates ("Aberdeen Company Yard"), so a real industrial business in
   the right town is a truthful end for the street chain even though nobody
   claims it is a cross-dock. Builders, contractors and farms are left out.

RANK (derived). ``tier`` = 1 + (trade stated by tag) + (trade stated by
name), so 3 = both, 2 = one of them, 1 = the assumed tier. Candidates are
taken best tier first, then nearest. No distance threshold lives here.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from facility_endpoint_screen import (  # noqa: E402
    SITE_BUILDINGS,
    TRADE_RULES,
    screen_endpoint,
)

WAREHOUSE_TYPES = frozenset(
    {"dry_warehouse", "warehouse", "distribution", "cross_dock", "terminal", "company_yard"}
)
MANUFACTURING_TYPES = frozenset({"manufacturing", "manufacturing_plant"})
INTERMODAL_TYPES = frozenset({"intermodal_ramp", "intermodal", "rail"})
PORT_TYPES = frozenset({"port", "port_terminal"})
RETAIL_DC_TYPES = frozenset({"grocery_retail_dc", "retail_distribution"})
ASSUMED_TRADE_TYPES = WAREHOUSE_TYPES | MANUFACTURING_TYPES

TIER_ASSUMED = 1

WAREHOUSE_INDUSTRIAL = frozenset(
    {"logistics", "warehouse", "warehousing", "distribution", "distributor", "trucking"}
)
MANUFACTURING_INDUSTRIAL = frozenset({"factory", "manufacturing", "manufacture"})
COLD_INDUSTRIAL = frozenset({"refrigerated_warehouse", "cold_storage"})
FOOD_INDUSTRIAL = frozenset(
    {
        "food",
        "food_processing",
        "food_industry",
        "bakery",
        "dairy",
        "slaughterhouse",
        "poultry_processing",
        "meat_processing",
        "meat",
        "soft_drinks",
        "beverages",
        "sugar",
        "rice_mill",
        "confectionery",
    }
)
NOT_AUTOMOTIVE_INDUSTRIAL = frozenset({"scrap_yard", "auto_wrecker"})
LOGISTICS_OFFICES = frozenset({"logistics", "freight_forwarder"})


def _words(pattern: str) -> re.Pattern[str]:
    return re.compile(rf"\b(?:{pattern})\b")


WAREHOUSE_NAME = _words(
    r"logistics|freight|warehouses?|warehousing|distribution|distributing|distributors?|"
    r"cross[- ]?dock|trucking|cartage|truck (?:terminal|lines?)|motor (?:freight|lines?)|"
    r"freight (?:terminal|lines?)|supply chain|transfer (?:&|and) storage"
)
SELF_STORAGE_NAME = _words(
    r"self[- ]storage|mini[- ]storage|storage units?|public storage|u-haul|uhaul|extra space|"
    r"rv storage|boat storage"
)
MANUFACTURING_NAME = _words(
    r"manufacturing|manufacturers?|mfg|factory|plant|works|mills?|foundry|fabrication|"
    r"fabricators?|fabricating|industries|machining|machine (?:shop|works|company|co)|"
    r"plastics|packaging|castings?|forge|forgings?|assembly plant|tool (?:&|and) die"
)
UTILITY_NAME = _words(
    r"wastewater|sewage|sewer|septic|water|treatment|pump(?:ing)? station|substation|power|"
    r"generating|landfill|transfer station|recycling|salvage|towing|compressor station|"
    r"heating|chilling|chiller|cooling|steam|boiler|physical plant|central plant|utilities|"
    r"former|formerly|abandoned|vacant|defunct|demolished|"
    # A works or warehouse turned to another use keeps its building tag.
    r"lofts?|apartments?|condos?|condominiums?|museum|gallery|theat(?:er|re)|studios?|church|"
    r"ministries|temple|brewery|brewing|winery|distillery|cemetery|gym|fitness|club|"
    r"schools?|university|college|academy|institute|hotel|restaurant|library"
)
CIVIC_NAME = _words(
    r"fire|police|sheriff|county|city of|town of|village of|township|district|department|"
    r"public works|maintenance|fleet|garage|transit|bus|airport|airline|hangar|aviation|arts?|"
    r"hospital|clinic|medical|jail|prison|correctional|armory|national guard|army|navy|"
    r"air force|military|animal|humane|caltrans|dot|highway|road (?:&|and) bridge|parks?|"
    r"body shop|auto body|collision|repair|tires?|car wash"
)
INDUSTRIAL_PARK_NAME = _words(
    r"(?:industrial|business|commerce|logistics|distribution|trade) "
    r"(?:park|center|centre|district|complex|campus)"
)
INTERMODAL_TRADE_NAME = _words(
    r"intermodal|transload(?:ing)?|rail ?port|logistics park|container (?:yard|terminal)"
)
RAIL_YARD_NAME = _words(r"yard|ramp|terminal")
PASSENGER_RAIL_NAME = _words(
    r"amtrak|metro|metrolink|metra|transit|light rail|commuter|subway|streetcar|trolley|"
    r"passenger|museum|bart|marta|septa|mbta|njt|lirr|caltrain|sounder|trax|dart|max|"
    r"tourist|scenic|heritage|historic|zoo|miniature|maintenance facility|coach"
)
PORT_NAME = _words(
    r"port of|seaport|port authority|river ?port|"
    r"(?:marine|container|cargo|bulk|shipping|port|ocean|maritime) terminal"
)
NOT_PORT_NAME = _words(
    r"marina|yacht|cruise|ferry|ferries|landing|boat|boats|fishing|sailing|rowing|museum|"
    r"restaurant|aquarium"
)
COLD_NAME = _words(
    r"cold storage|refrigerated|refrigeration|freezers?|frozen|cold chain|americold|lineage"
)
FOOD_NAME = _words(
    r"foods?|meats?|packing|packers|poultry|dairy|dairies|creamery|bakery|bakeries|baking|"
    r"beef|pork|cannery|canning|flour|sugar|beverages?|bottling|bottlers|snacks?|frozen|"
    r"cheese|milk|produce|seafoods?|eggs?|tortillas?|potato(?:es)?|rice"
)
FOOD_PRODUCT = _words(
    r"food|foods|meat|poultry|dairy|milk|cheese|bread|flour|sugar|beverages?|soft_drinks|"
    r"snacks?|eggs?|frozen_food|pet_food"
)
GROCER_NAME = _words(
    r"grocery|groceries|grocers?|foods?|supermarkets?|walmart|wal-mart|sam's club|kroger|"
    r"target|costco|safeway|albertsons|publix|meijer|aldi|h-e-b|heb|sysco|us foods|"
    r"dollar general|dollar tree|family dollar|winco|hy-vee|wegmans|food lion|giant eagle|"
    r"shoprite|stop (?:&|and) shop|walgreens|cvs|lowe's|home depot|menards|kohl's|"
    r"tractor supply|big lots|ross|tj maxx|tjx|macy's|best buy|ace hardware|"
    r"associated (?:wholesale )?grocers|supervalu|unfi|c&s wholesale|spartannash|mclane|"
    r"gordon food service|performance food|core-mark|trader joe's|whole foods|save mart|"
    r"raley's|food 4 less|smart & final|winn-dixie|piggly wiggly|ingles|harris teeter|"
    r"hannaford|price chopper|fareway|schnucks|dierbergs|brookshire|united supermarkets"
)
FOOD_TERMINAL_NAME = _words(r"produce|food|foods|farmers")
FOOD_TERMINAL_KIND = _words(r"terminal|market|distribution")
PARCEL_NAME = _words(
    r"ups|fedex|dhl|usps|postal|parcel|packages?|sortation|sort (?:center|facility)|"
    r"fulfillment|amazon|ontrac|lasership|purolator"
)
AIR_CARGO_NAME = _words(r"air cargo|cargo|air ?freight")
BUSINESS_NAME = _words(
    r"inc|incorporated|llc|ltd|co|company|companies|corp|corporation|industries|industrial|"
    r"products|supply|systems|technologies|international|enterprises|group|usa|america|"
    r"holdings|solutions|materials|equipment|components|controls"
)
NOT_ASSUMED_NAME = _words(
    r"construction|contractors?|contracting|builders?|paving|excavating|excavation|roofing|"
    r"plumbing|landscap\w*|nursery|farms?|ranch|realty|properties|storage|rentals?|"
    r"parque|s\.?a\.? de c\.?v\.?"
)


@dataclass(frozen=True)
class RoleMatch:
    tier: int
    reason: str

    @property
    def kind(self) -> str:
        """Provenance of the TRADE claim: ``read`` from the object's tags or
        name, or ``assumed`` (a freight site that states no trade)."""
        return "assumed" if self.tier == TIER_ASSUMED else "read"


def naming_text(tags: dict[str, str]) -> str:
    """The object's own naming tags, lowercased, for whole-word tests."""
    return " ; ".join(tags.get(key, "") for key in ("name", "operator", "brand")).lower()


def match_roles(tags: dict[str, str], name: str) -> dict[str, RoleMatch]:
    """Every facility type this object can stand for, with its rank."""
    text = naming_text(tags) if any(tags.get(k) for k in ("name", "operator", "brand")) else ""
    text = text or name.lower()
    industrial = tags.get("industrial", "")
    utility = bool(UTILITY_NAME.search(text))
    civic = bool(CIVIC_NAME.search(text))
    self_storage = bool(SELF_STORAGE_NAME.search(text))
    out: dict[str, RoleMatch] = {}

    def offer(roles, by_tag: str, by_name: str, *, both: bool = False) -> None:
        if both and not (by_tag and by_name):
            return
        if not by_tag and not by_name:
            return
        tier = 1 + bool(by_tag) + bool(by_name)
        reason = "; ".join(part for part in (by_tag, by_name) if part)
        for role in roles:
            if screen_endpoint(role, name, tags)[0]:
                best = out.get(role)
                if best is None or tier > best.tier:
                    out[role] = RoleMatch(tier, reason)

    # Warehouse family.
    warehouse_tag = (
        "building=warehouse tag"
        if tags.get("building") == "warehouse"
        else f"industrial={industrial} tag"
        if industrial in WAREHOUSE_INDUSTRIAL
        else "logistics office tag"
        # A courier's desk in an office tower is a logistics office too: the
        # tag counts when the object is also a building or land of the trade.
        if tags.get("office") in LOGISTICS_OFFICES
        and (tags.get("building") in SITE_BUILDINGS or tags.get("landuse") == "industrial")
        else ""
    )
    warehouse_name = "freight or warehouse words in the name" if WAREHOUSE_NAME.search(text) else ""
    if not self_storage and not utility:
        offer(WAREHOUSE_TYPES, warehouse_tag, warehouse_name, both=civic)

    # Manufacturing.
    manufacturing_tag = (
        "man_made=works tag"
        if tags.get("man_made") == "works"
        else f"building={tags['building']} tag"
        if tags.get("building") in {"factory", "manufacture"}
        else f"industrial={industrial} tag"
        if industrial in MANUFACTURING_INDUSTRIAL
        else ""
    )
    manufacturing_name = (
        "manufacturing words in the name" if MANUFACTURING_NAME.search(text) else ""
    )
    if not utility:
        offer(MANUFACTURING_TYPES, manufacturing_tag, manufacturing_name, both=civic)
    if tags.get("landuse") == "industrial" and INDUSTRIAL_PARK_NAME.search(text):
        offer({"industrial_park"}, "landuse=industrial tag", "industrial park words in the name")

    # Intermodal and rail.
    if not PASSENGER_RAIL_NAME.search(text):
        rail_tag = (
            "railway=yard tag"
            if tags.get("railway") == "yard"
            else "landuse=railway tag"
            if tags.get("landuse") == "railway"
            else ""
        )
        if INTERMODAL_TRADE_NAME.search(text):
            offer(INTERMODAL_TYPES, rail_tag, "intermodal words in the name")
        elif tags.get("railway") == "yard":
            offer(INTERMODAL_TYPES, rail_tag, "")
        elif rail_tag and RAIL_YARD_NAME.search(text):
            # Railway land is often a corridor strip; only a named yard counts.
            offer(INTERMODAL_TYPES, "", "railway land named a yard, ramp or terminal")

    # Ports.
    if not NOT_PORT_NAME.search(text):
        offer(
            PORT_TYPES,
            "industrial=port tag" if industrial == "port" else "",
            "port words in the name" if PORT_NAME.search(text) else "",
        )

    # Cold storage, food, grocery and retail distribution.
    offer(
        {"cold_storage"},
        f"industrial={industrial} tag" if industrial in COLD_INDUSTRIAL else "",
        "cold storage words in the name" if COLD_NAME.search(text) else "",
    )
    product = tags.get("product", "").lower().replace(";", " ")
    food_tag = (
        f"industrial={industrial} tag"
        if industrial in FOOD_INDUSTRIAL
        else "food product tag"
        if FOOD_PRODUCT.search(product)
        else ""
    )
    if not utility:
        offer(
            {"food_processor"},
            food_tag,
            "food words in the name" if FOOD_NAME.search(text) else "",
            both=civic,
        )
    if (warehouse_tag or warehouse_name) and GROCER_NAME.search(text) and not self_storage:
        offer(RETAIL_DC_TYPES, warehouse_tag, "a grocer's or retailer's name")
    if FOOD_TERMINAL_NAME.search(text) and FOOD_TERMINAL_KIND.search(text) and not civic:
        offer({"food_terminal"}, "", "food terminal words in the name")

    # Parcel and air cargo.
    offer(
        {"parcel_hub"},
        "amenity=post_depot tag" if tags.get("amenity") == "post_depot" else "",
        "parcel carrier words in the name" if PARCEL_NAME.search(text) else "",
    )
    offer({"air_cargo"}, "", "air cargo words in the name" if AIR_CARGO_NAME.search(text) else "")

    # Steel, automotive, chemical: the screen's trade rule IS the match.
    for role, (industrial_values, _product_words, name_words) in TRADE_RULES.items():
        if role == "automotive_plant" and industrial in NOT_AUTOMOTIVE_INDUSTRIAL:
            continue
        if civic and not name_words.search(text):
            continue  # a city's scrap yard is not a steel works
        if not utility and screen_endpoint(role, name, tags)[0]:
            by_tag = f"industrial={industrial} tag" if industrial in industrial_values else ""
            out[role] = RoleMatch(3 if by_tag else 2, by_tag or "trade stated by product or name")

    # The assumed tier: a freight site of no stated trade with a business name.
    states_a_trade = bool(out) or bool(industrial) or "aeroway" in tags or self_storage
    if (
        not states_a_trade
        and not utility
        and not civic
        and BUSINESS_NAME.search(text)
        and not NOT_ASSUMED_NAME.search(text)
    ):
        for role in ASSUMED_TRADE_TYPES:
            if screen_endpoint(role, name, tags)[0]:
                out[role] = RoleMatch(
                    TIER_ASSUMED, "freight site by tag with a business name; trade assumed"
                )
    return out
