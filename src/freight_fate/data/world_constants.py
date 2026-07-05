STOP_TYPE_LABELS = {
    "truck_stop": "truck stop",
    "travel_center": "travel center",
    "fuel_station": "truck fuel station",
    "service_plaza": "service plaza",
    "public_rest_area": "public rest area",
    "truck_parking": "truck parking",
    "weigh_station": "weigh station",
    "repair_shop": "repair shop",
}

PARKING_CERTAINTY_LABELS = {
    "confirmed": "confirmed truck parking",
    "likely": "",
    "limited": "limited truck parking",
    "unknown": "parking not verified",
    "none": "no truck parking",
}

STOP_CURATION_LEVELS = {"curated", "placeholder"}

STOP_DIRECTIONS = {"both", "forward", "reverse"}

# Alternate routes should feel like real dispatch choices, not graph leftovers.
# A little extra mileage is fine for traffic, weather, grades, or avoiding a
# metro corridor; hundreds of out-of-direction miles on a short lane are not.
ALTERNATE_ROUTE_EXTRA_RATIO = 0.22
ALTERNATE_ROUTE_MIN_EXTRA_MILES = 75.0
ALTERNATE_ROUTE_MAX_EXTRA_MILES = 550.0

POI_DENSITY_SHORT_LEG_MILES = 160.0
POI_DENSITY_MEDIUM_LEG_MILES = 320.0

POI_ACTIONS = {
    "park",
    "save",
    "break",
    "sleep",
    "fuel",
    "food",
    "repair",
    "roadside_assistance",
    "towing",
    "inspect",
}

RAW_POI_TEXT_MARKERS = (
    "osm_id",
    "openstreetmap id",
    "amenity=",
    "highway=",
    "operator=",
    "node/",
    "way/",
    "relation/",
)

TOLL_METHOD_LABELS = {
    "cash_card": "cash or card",
    "ticket_system": "ticket system",
    "transponder": "transponder",
    "open_road": "open-road tolling",
    "toll_by_plate": "toll by plate",
    "ezpass": "E-ZPass",
}

CITY_SERVICE_SOURCE_NOTES = {
    "freight_market": (
        "Representative city service POI derived from the metro freight market "
        "and checked-in facility taxonomy."
    ),
    "garage": ("Representative terminal garage service POI derived from the home terminal."),
    "truck_dealer": ("Representative truck dealer service POI for the metro service area."),
}

CITY_SERVICE_LABELS = {
    "freight_market": "freight market office",
    "garage": "garage",
    "truck_dealer": "truck dealer",
}

CITY_SERVICE_ORDER = ("freight_market", "garage", "truck_dealer")

CITY_SERVICE_SOURCE_TYPES = {"osm", "ors", "operator", "fallback"}

DEFAULT_POI_ACTIONS = {
    "truck_stop": ("park", "save", "fuel", "food", "break", "sleep"),
    "travel_center": ("park", "save", "fuel", "food", "break", "sleep"),
    "fuel_station": ("park", "save", "fuel", "break"),
    "service_plaza": ("park", "save", "fuel", "food", "break"),
    "public_rest_area": ("park", "save", "break", "sleep"),
    "truck_parking": ("park", "save", "break", "sleep"),
    "weigh_station": ("inspect",),
    "repair_shop": ("park", "save", "repair"),
}

SOURCE_BACKED_POI_ACTIONS = {"repair", "roadside_assistance", "towing"}

FREIGHT_LOCATION_TYPES = {
    "air_cargo",
    "automotive_plant",
    "chemical_petroleum_terminal",
    "cold_storage",
    "company_yard",
    "construction_materials_yard",
    "cross_dock",
    "distribution",
    "dry_warehouse",
    "farm_elevator",
    "food_terminal",
    "food_processor",
    "grocery_retail_dc",
    "industrial_park",
    "intermodal",
    "intermodal_ramp",
    "lumber_paper",
    "manufacturing",
    "manufacturing_plant",
    "mine_quarry",
    "parcel_hub",
    "port",
    "port_terminal",
    "rail",
    "retail_distribution",
    "steel_industrial",
    "terminal",
    "warehouse",
    "metro_market",
}

LOCATION_TYPE_LABELS = {
    "air_cargo": "air cargo area",
    "automotive_plant": "automotive plant",
    "chemical_petroleum_terminal": "chemical and petroleum terminal",
    "cold_storage": "cold storage",
    "company_yard": "company yard",
    "construction_materials_yard": "construction materials yard",
    "cross_dock": "cross-dock",
    "distribution": "distribution center",
    "dry_warehouse": "dry warehouse",
    "farm_elevator": "farm elevator",
    "food_terminal": "food terminal",
    "food_processor": "food processor",
    "grocery_retail_dc": "grocery and retail distribution center",
    "industrial_park": "industrial park",
    "intermodal": "intermodal yard",
    "intermodal_ramp": "intermodal ramp",
    "lumber_paper": "lumber and paper facility",
    "manufacturing": "manufacturing plant",
    "manufacturing_plant": "manufacturing plant",
    "metro_market": "metro freight market",
    "mine_quarry": "mine or quarry",
    "parcel_hub": "parcel hub",
    "port": "port",
    "port_terminal": "port terminal",
    "rail": "rail yard",
    "retail_distribution": "retail distribution hub",
    "steel_industrial": "steel and industrial plant",
    "terminal": "freight terminal",
    "warehouse": "warehouse",
}

FACILITY_APPROACH_MILES = {
    "air_cargo": 7.0,
    "automotive_plant": 4.5,
    "chemical_petroleum_terminal": 6.0,
    "cold_storage": 4.0,
    "company_yard": 2.5,
    "construction_materials_yard": 3.5,
    "cross_dock": 3.5,
    "distribution": 4.0,
    "dry_warehouse": 3.5,
    "farm_elevator": 5.0,
    "food_terminal": 3.5,
    "food_processor": 4.5,
    "grocery_retail_dc": 4.0,
    "industrial_park": 5.0,
    "intermodal": 6.0,
    "intermodal_ramp": 6.0,
    "lumber_paper": 5.5,
    "manufacturing": 4.5,
    "manufacturing_plant": 4.5,
    "metro_market": 3.0,
    "mine_quarry": 7.0,
    "parcel_hub": 4.0,
    "port": 8.0,
    "port_terminal": 8.0,
    "rail": 5.5,
    "retail_distribution": 4.0,
    "steel_industrial": 5.5,
    "terminal": 3.0,
    "warehouse": 3.5,
}

FACILITY_APPROACH_ROADS = {
    "air_cargo": "airport cargo access road",
    "automotive_plant": "assembly plant access road",
    "chemical_petroleum_terminal": "terminal access road",
    "cold_storage": "cold storage access road",
    "company_yard": "company yard access road",
    "construction_materials_yard": "materials yard access road",
    "cross_dock": "cross-dock access road",
    "distribution": "distribution center access road",
    "dry_warehouse": "warehouse access road",
    "farm_elevator": "elevator access road",
    "food_terminal": "food terminal access road",
    "food_processor": "food plant access road",
    "grocery_retail_dc": "distribution center access road",
    "industrial_park": "industrial park access road",
    "intermodal": "intermodal yard access road",
    "intermodal_ramp": "intermodal ramp access road",
    "lumber_paper": "mill access road",
    "manufacturing": "plant access road",
    "manufacturing_plant": "plant access road",
    "metro_market": "local freight access road",
    "mine_quarry": "quarry access road",
    "parcel_hub": "parcel hub access road",
    "port": "port access road",
    "port_terminal": "port terminal access road",
    "rail": "rail yard access road",
    "retail_distribution": "retail distribution access road",
    "steel_industrial": "industrial plant access road",
    "terminal": "terminal access road",
    "warehouse": "warehouse access road",
}

FACILITY_CARGO_ROLES: dict[str, dict[str, tuple[str, ...]]] = {
    "air_cargo": {
        "ships": ("electronics", "parcel", "general"),
        "receives": ("electronics", "parcel", "general"),
    },
    "automotive_plant": {
        "ships": ("automotive", "machinery"),
        "receives": ("steel", "machinery", "electronics", "general"),
    },
    "chemical_petroleum_terminal": {
        "ships": ("chemicals", "bulk"),
        "receives": ("chemicals", "bulk", "general"),
    },
    "cold_storage": {
        "ships": ("food", "refrigerated"),
        "receives": ("food", "refrigerated"),
    },
    "company_yard": {
        "ships": ("general", "retail", "parcel"),
        "receives": ("general", "retail", "parcel"),
    },
    "construction_materials_yard": {
        "ships": ("construction", "bulk", "lumber_paper"),
        "receives": ("construction", "bulk", "steel", "lumber_paper"),
    },
    "cross_dock": {
        "ships": ("general", "retail", "parcel", "container"),
        "receives": ("general", "retail", "parcel", "container"),
    },
    "distribution": {
        "ships": ("food", "general", "retail", "refrigerated", "parcel"),
        "receives": ("food", "general", "retail", "refrigerated", "parcel"),
    },
    "dry_warehouse": {
        "ships": ("general", "retail", "bulk", "machinery", "construction"),
        "receives": ("general", "retail", "bulk", "machinery", "construction"),
    },
    "farm_elevator": {
        "ships": ("grain", "bulk"),
        "receives": ("farm_inputs", "general"),
    },
    "food_terminal": {
        "ships": ("food", "refrigerated", "grain"),
        "receives": ("food", "refrigerated", "grain"),
    },
    "food_processor": {
        "ships": ("food", "refrigerated"),
        "receives": ("grain", "food", "refrigerated", "farm_inputs"),
    },
    "grocery_retail_dc": {
        "ships": ("retail", "food", "refrigerated", "general"),
        "receives": ("retail", "food", "refrigerated", "general"),
    },
    "industrial_park": {
        "ships": ("bulk", "machinery", "retail", "construction"),
        "receives": ("bulk", "machinery", "retail", "construction"),
    },
    "intermodal": {
        "ships": ("bulk", "container", "general", "automotive", "retail"),
        "receives": ("bulk", "container", "general", "automotive", "retail"),
    },
    "intermodal_ramp": {
        "ships": ("container", "general", "retail", "automotive", "parcel"),
        "receives": ("container", "general", "retail", "automotive", "parcel"),
    },
    "lumber_paper": {
        "ships": ("lumber_paper", "construction"),
        "receives": ("bulk", "machinery", "chemicals"),
    },
    "manufacturing": {
        "ships": ("bulk", "electronics", "machinery", "automotive"),
        "receives": ("bulk", "electronics", "machinery", "steel", "general"),
    },
    "manufacturing_plant": {
        "ships": ("machinery", "electronics", "general"),
        "receives": ("bulk", "steel", "electronics", "general"),
    },
    "metro_market": {
        "ships": ("general", "retail"),
        "receives": ("general", "retail"),
    },
    "mine_quarry": {
        "ships": ("bulk", "construction"),
        "receives": ("machinery", "chemicals", "farm_inputs"),
    },
    "parcel_hub": {
        "ships": ("parcel", "electronics", "general"),
        "receives": ("parcel", "electronics", "general"),
    },
    "port": {
        "ships": ("bulk", "container", "electronics", "machinery", "automotive"),
        "receives": ("bulk", "container", "electronics", "machinery", "automotive"),
    },
    "port_terminal": {
        "ships": ("container", "bulk", "automotive", "chemicals", "lumber_paper"),
        "receives": ("container", "bulk", "automotive", "chemicals", "lumber_paper"),
    },
    "rail": {
        "ships": ("bulk", "container", "machinery", "grain"),
        "receives": ("bulk", "container", "machinery", "grain"),
    },
    "retail_distribution": {
        "ships": ("general", "retail", "parcel"),
        "receives": ("general", "retail", "parcel"),
    },
    "steel_industrial": {
        "ships": ("steel", "machinery", "bulk"),
        "receives": ("bulk", "chemicals", "construction"),
    },
    "terminal": {
        "ships": ("electronics", "general", "retail", "parcel"),
        "receives": ("electronics", "general", "retail", "parcel"),
    },
    "warehouse": {
        "ships": ("bulk", "general", "machinery", "retail", "construction"),
        "receives": ("bulk", "general", "machinery", "retail", "construction"),
    },
}

FACILITY_SOURCE_NOTES = {
    "air_cargo": "Representative air-cargo facility; guided by FAF modal and commodity framing.",
    "automotive_plant": "Representative automotive facility; guided by FAF commodity and metro-market framing.",
    "chemical_petroleum_terminal": "Representative chemical or petroleum terminal; guided by FAF commodity framing.",
    "cold_storage": "Representative cold-storage facility; guided by FAF food flows and USDA refrigerated transport context.",
    "company_yard": "Representative company terminal or yard for the metro service area.",
    "construction_materials_yard": "Representative construction materials yard; guided by FAF construction-sector freight framing.",
    "cross_dock": "Representative cross-dock facility; guided by FAF metro logistics and border/gateway flows.",
    "distribution": "Curated representative distribution facility in the metro freight market.",
    "dry_warehouse": "Representative dry warehouse; guided by FAF metro-market freight flows.",
    "farm_elevator": "Representative farm elevator or ag terminal; guided by USDA grain truck indicators and FAF agriculture flows.",
    "food_terminal": "Curated representative food terminal in the metro freight market.",
    "food_processor": "Representative food processor; guided by FAF food flows and USDA agricultural transport context.",
    "grocery_retail_dc": "Representative grocery and retail DC; guided by FAF commodity and metro-market framing.",
    "industrial_park": "Curated representative industrial facility in the metro freight market.",
    "intermodal": "Curated representative intermodal facility in the metro freight market.",
    "intermodal_ramp": "Representative rail/intermodal ramp; guided by FAF all-mode freight flow framing.",
    "lumber_paper": "Representative lumber or paper facility; guided by FAF commodity framing.",
    "manufacturing": "Curated representative manufacturing facility in the metro freight market.",
    "manufacturing_plant": "Representative manufacturing plant; guided by FAF manufacturing-sector freight framing.",
    "metro_market": "Legacy bare-city load fallback for save compatibility.",
    "mine_quarry": "Representative mine or quarry; guided by FAF extraction-sector freight framing.",
    "parcel_hub": "Representative parcel hub; guided by metro logistics and air/intermodal freight patterns.",
    "port": "Curated representative port facility in the metro freight market.",
    "port_terminal": "Representative port terminal; guided by MARAD and BTS port performance datasets.",
    "rail": "Curated representative rail facility in the metro freight market.",
    "retail_distribution": "Curated representative retail distribution facility in the metro freight market.",
    "steel_industrial": "Representative steel or industrial facility; guided by FAF commodity framing.",
    "terminal": "Curated representative freight terminal in the metro freight market.",
    "warehouse": "Curated representative warehouse in the metro freight market.",
}

FACILITY_LEVEL_UNLOCKS = {
    "automotive_plant": 2,
    "chemical_petroleum_terminal": 4,
    "cold_storage": 2,
    "food_processor": 2,
    "lumber_paper": 2,
    "manufacturing_plant": 2,
    "mine_quarry": 3,
    "steel_industrial": 3,
}

BASE_MARKET_FACILITY_TYPES = (
    "company_yard",
    "dry_warehouse",
    "cross_dock",
    "grocery_retail_dc",
)

REGION_MARKET_TAGS = {
    "northeast": ("port", "intermodal", "industrial", "retail"),
    "appalachia": ("industrial", "mining", "manufacturing"),
    "great_lakes": ("intermodal", "manufacturing", "automotive", "agriculture"),
    "upper_midwest": ("agriculture", "food", "manufacturing", "intermodal"),
    "corn_belt": ("agriculture", "food", "manufacturing", "intermodal"),
    "heartland": ("agriculture", "intermodal", "food"),
    "southern_plains": ("energy", "agriculture", "intermodal", "retail"),
    "mid_south": ("parcel", "manufacturing", "food"),
    "atlantic_southeast": ("port", "manufacturing", "retail", "food"),
    "gulf_coast": ("port", "energy", "chemical", "food"),
    "florida": ("port", "food", "retail", "cold_chain"),
    "rockies": ("mining", "intermodal", "construction"),
    "great_basin": ("intermodal", "mining", "retail"),
    "desert_southwest": ("border", "construction", "food", "mining"),
    "california": ("port", "food", "retail", "intermodal"),
    "pacific_northwest": ("port", "lumber", "agriculture", "intermodal"),
}

STATE_MARKET_TAGS = {
    "Arkansas": ("agriculture", "food"),
    "California": ("port", "food", "cold_chain"),
    "Colorado": ("mining", "construction"),
    "Florida": ("port", "food", "cold_chain"),
    "Georgia": ("port", "food", "parcel"),
    "Idaho": ("agriculture", "food"),
    "Illinois": ("intermodal", "agriculture"),
    "Indiana": ("manufacturing", "automotive"),
    "Iowa": ("agriculture", "food"),
    "Kansas": ("agriculture", "manufacturing"),
    "Kentucky": ("parcel", "automotive"),
    "Louisiana": ("port", "energy"),
    "Michigan": ("automotive", "manufacturing"),
    "Minnesota": ("agriculture", "lumber"),
    "Missouri": ("agriculture", "intermodal"),
    "Nebraska": ("agriculture", "food"),
    "New Mexico": ("mining", "border"),
    "New York": ("port", "retail"),
    "North Carolina": ("manufacturing", "food"),
    "Ohio": ("manufacturing", "automotive"),
    "Oklahoma": ("energy", "agriculture"),
    "Oregon": ("port", "lumber", "food"),
    "Pennsylvania": ("industrial", "manufacturing"),
    "Tennessee": ("parcel", "manufacturing"),
    "Texas": ("energy", "border", "port", "retail"),
    "Utah": ("mining", "intermodal"),
    "Virginia": ("port", "manufacturing"),
    "Washington": ("port", "lumber", "food"),
    "Wisconsin": ("food", "manufacturing", "lumber"),
    "Wyoming": ("mining", "energy"),
}

CITY_MARKET_TAGS = {
    "Atlanta": ("air", "parcel", "food"),
    "Baltimore": ("port", "intermodal"),
    "Birmingham": ("steel", "manufacturing"),
    "Buffalo": ("border", "industrial"),
    "Charlotte": ("intermodal", "retail"),
    "Chicago": ("intermodal", "air", "food", "parcel"),
    "Cincinnati": ("intermodal", "manufacturing"),
    "Cleveland": ("steel", "port"),
    "Dallas": ("intermodal", "parcel", "retail"),
    "Denver": ("intermodal", "construction", "mining"),
    "Detroit": ("automotive", "border"),
    "El Paso": ("border", "cross_dock"),
    "Fresno": ("agriculture", "food", "cold_chain"),
    "Houston": ("port", "energy", "chemical"),
    "Indianapolis": ("parcel", "intermodal"),
    "Jacksonville": ("port", "cold_chain"),
    "Kansas City": ("intermodal", "agriculture"),
    "Las Vegas": ("retail", "construction"),
    "Los Angeles": ("port", "intermodal", "food", "air"),
    "Louisville": ("parcel", "air"),
    "Memphis": ("parcel", "air", "intermodal", "river_port"),
    "Miami": ("port", "air", "cold_chain"),
    "Milwaukee": ("port", "food"),
    "Minneapolis": ("agriculture", "lumber"),
    "New Orleans": ("port", "energy", "agriculture"),
    "New York": ("port", "air", "retail"),
    "Omaha": ("agriculture", "food"),
    "Philadelphia": ("port", "industrial"),
    "Phoenix": ("air", "retail", "construction"),
    "Pittsburgh": ("steel", "industrial"),
    "Portland": ("port", "lumber"),
    "Reno": ("intermodal", "retail"),
    "Richmond": ("port", "manufacturing"),
    "Sacramento": ("food", "agriculture"),
    "Salt Lake City": ("intermodal", "mining"),
    "San Antonio": ("border", "retail"),
    "San Diego": ("port", "border"),
    "Savannah": ("port", "intermodal"),
    "Seattle": ("port", "air", "lumber"),
    "Spokane": ("agriculture", "lumber"),
    "St. Louis": ("river_port", "agriculture", "intermodal"),
    "Tampa": ("port", "cold_chain"),
    "Tulsa": ("energy", "manufacturing"),
    "Wichita": ("manufacturing", "air"),
}

MARKET_TAG_FACILITY_TYPES = {
    "agriculture": ("farm_elevator", "food_processor"),
    "air": ("air_cargo",),
    "automotive": ("automotive_plant",),
    "border": ("cross_dock", "dry_warehouse"),
    "chemical": ("chemical_petroleum_terminal",),
    "cold_chain": ("cold_storage",),
    "construction": ("construction_materials_yard",),
    "cross_dock": ("cross_dock",),
    "energy": ("chemical_petroleum_terminal",),
    "food": ("food_processor", "cold_storage"),
    "industrial": ("steel_industrial", "manufacturing_plant"),
    "intermodal": ("intermodal_ramp",),
    "lumber": ("lumber_paper",),
    "manufacturing": ("manufacturing_plant",),
    "mining": ("mine_quarry",),
    "parcel": ("parcel_hub",),
    "port": ("port_terminal",),
    "retail": ("grocery_retail_dc",),
    "river_port": ("port_terminal", "farm_elevator"),
    "steel": ("steel_industrial",),
}

FACILITY_NAME_TEMPLATES = {
    "air_cargo": "{city} Air Cargo Center",
    "automotive_plant": "{city} Auto Assembly Supplier Park",
    "chemical_petroleum_terminal": "{city} Energy Terminal",
    "cold_storage": "{city} Cold Storage",
    "company_yard": "{city} Company Yard",
    "construction_materials_yard": "{city} Materials Yard",
    "cross_dock": "{city} Cross-Dock",
    "dry_warehouse": "{city} Dry Warehouse",
    "farm_elevator": "{city} Grain Elevator",
    "food_processor": "{city} Food Processing Plant",
    "grocery_retail_dc": "{city} Grocery Distribution Center",
    "intermodal_ramp": "{city} Intermodal Ramp",
    "lumber_paper": "{city} Lumber and Paper Yard",
    "manufacturing_plant": "{city} Manufacturing Plant",
    "mine_quarry": "{city} Quarry",
    "parcel_hub": "{city} Parcel Hub",
    "port_terminal": "{city} Port Terminal",
    "steel_industrial": "{city} Steel and Industrial Works",
}

RAW_FACILITY_TEXT_MARKERS = RAW_POI_TEXT_MARKERS + (
    "place_id",
    "wikidata=",
    "naics=",
)

__all__ = [name for name in globals() if not name.startswith("__")]
