"""World model: cities, freight locations, and the highway network.

Loads ``world.json`` and exposes a graph with Dijkstra-based route finding.
Route options are produced by re-running the search with already-used legs
penalized, giving genuinely different alternatives (fastest vs. detour).
"""

from __future__ import annotations

import heapq
import json
import zlib
from dataclasses import dataclass
from pathlib import Path

WORLD_PATH = Path(__file__).parent / "world.json"

# Alternate routes should feel like real dispatch choices, not graph leftovers.
# A little extra mileage is fine for traffic, weather, grades, or avoiding a
# metro corridor; hundreds of out-of-direction miles on a short lane are not.
ALTERNATE_ROUTE_EXTRA_RATIO = 0.22
ALTERNATE_ROUTE_MIN_EXTRA_MILES = 75.0
ALTERNATE_ROUTE_MAX_EXTRA_MILES = 550.0


@dataclass(frozen=True)
class Location:
    name: str
    type: str
    cargo: tuple[str, ...]
    id: str = ""
    city: str = ""
    locality: str = ""
    roles: tuple[str, ...] = ("shipper", "receiver")
    ships: tuple[str, ...] = ()
    receives: tuple[str, ...] = ()
    lat: float = 0.0
    lon: float = 0.0
    traits: tuple[str, ...] = ()
    source_note: str = ""
    spoken: str = ""
    template: bool = False
    min_level: int = 1

    @property
    def label(self) -> str:
        return LOCATION_TYPE_LABELS.get(self.type, self.type.replace("_", " "))

    @property
    def spoken_name(self) -> str:
        return self.spoken or f"{self.label}: {self.name}"

    @property
    def display_name(self) -> str:
        return self.name


@dataclass(frozen=True)
class HomeTerminal:
    name: str
    city: str
    state: str
    kind: str

    @property
    def label(self) -> str:
        return "company terminal" if self.kind == "terminal" else "company yard"

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"

    @property
    def service_area(self) -> str:
        return f"{self.city}, {self.state}"


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
    "likely": "likely truck parking",
    "limited": "limited truck parking",
    "unknown": "parking not verified",
    "none": "no truck parking",
}

STOP_CURATION_LEVELS = {"curated", "placeholder"}

STOP_DIRECTIONS = {"both", "forward", "reverse"}

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


@dataclass(frozen=True)
class Stop:
    name: str
    at_mi: float
    type: str = "travel_center"
    source: str = ""
    actions: tuple[str, ...] = ()
    services: tuple[str, ...] = ()
    parking: str = "unknown"
    directions: tuple[str, ...] = ("both",)
    curation: str = "curated"

    @property
    def label(self) -> str:
        return STOP_TYPE_LABELS.get(self.type, "stop")

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"

    @property
    def parking_label(self) -> str:
        return PARKING_CERTAINTY_LABELS[self.parking]

    @property
    def curated(self) -> bool:
        return self.curation == "curated"

    def applies_to_direction(self, forward: bool) -> bool:
        if "both" in self.directions:
            return True
        return ("forward" if forward else "reverse") in self.directions


@dataclass(frozen=True)
class RoutePoint:
    at_mi: float
    lat: float
    lon: float


@dataclass(frozen=True)
class ElevationSample:
    at_mi: float
    elevation_ft: float
    source: str = ""


@dataclass(frozen=True)
class GradeSegment:
    start_mi: float
    end_mi: float
    avg_grade_pct: float
    terrain: str
    source: str = ""


@dataclass(frozen=True)
class StateCrossing:
    at_mi: float
    from_state: str
    state: str
    place: str
    source: str = ""


@dataclass(frozen=True)
class RouteCheckpoint:
    name: str
    at_mi: float
    type: str = "place"
    state: str = ""
    highway: str = ""
    source: str = ""

    @property
    def label(self) -> str:
        if self.type == "highway_change":
            return "highway change"
        if self.type == "state_line":
            return "state line"
        return "corridor place"

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"


@dataclass(frozen=True)
class StateMileage:
    state: str
    miles: float


@dataclass(frozen=True)
class TollEvent:
    name: str
    at_mi: float
    road: str
    authority: str
    method: str
    amount: float
    estimated: bool = True
    source: str = ""

    @property
    def method_label(self) -> str:
        return TOLL_METHOD_LABELS.get(self.method, self.method.replace("_", " "))

    @property
    def spoken_name(self) -> str:
        return f"toll point: {self.name}"


@dataclass(frozen=True)
class City:
    name: str
    state: str
    region: str
    locations: tuple[Location, ...]
    lat: float = 0.0
    lon: float = 0.0
    market_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Leg:
    a: str
    b: str
    miles: float
    highway: str
    terrain: str  # flat | hills | mountain
    stops: tuple[Stop, ...]
    route_points: tuple[RoutePoint, ...] = ()
    elevation_samples: tuple[ElevationSample, ...] = ()
    grade_segments: tuple[GradeSegment, ...] = ()
    state_crossings: tuple[StateCrossing, ...] = ()
    checkpoints: tuple[RouteCheckpoint, ...] = ()
    state_miles: tuple[StateMileage, ...] = ()
    toll_events: tuple[TollEvent, ...] = ()

    def other(self, city: str) -> str:
        return self.b if city == self.a else self.a

    def metadata_complete(self, from_state: str, to_state: str) -> bool:
        """True when a leg has enough real corridor data for new freight."""
        if len(self.route_points) < 2:
            return False
        if not self.checkpoints:
            return False
        if not self.state_miles:
            return False
        if len(self.elevation_samples) < 2 or not self.grade_segments:
            return False
        curated_stops = [stop for stop in self.stops if stop.curated]
        if len(curated_stops) < minimum_curated_pois(self.miles):
            return False
        fuel_capable = [stop for stop in curated_stops if "fuel" in stop.actions]
        if len(fuel_capable) < minimum_fuel_capable_pois(self.miles):
            return False
        if any(
            not stop.source
            or not stop.actions
            or stop.parking == "unknown"
            for stop in curated_stops
        ):
            return False
        return from_state == to_state or bool(self.state_crossings)


@dataclass
class Route:
    """An ordered chain of legs from start to end."""

    cities: list[str]
    legs: list[Leg]

    @property
    def miles(self) -> float:
        return sum(leg.miles for leg in self.legs)

    @property
    def highways(self) -> list[str]:
        out: list[str] = []
        for leg in self.legs:
            if not out or out[-1] != leg.highway:
                out.append(leg.highway)
        return out

    @property
    def stops(self) -> list[str]:
        return [s.name for leg in self.legs for s in leg.stops if s.curated]

    @property
    def stop_details(self) -> list[Stop]:
        return [s for leg in self.legs for s in leg.stops if s.curated]

    @property
    def raw_stop_details(self) -> list[Stop]:
        return [s for leg in self.legs for s in leg.stops]

    @property
    def state_crossings(self) -> list[StateCrossing]:
        return [c for leg in self.legs for c in leg.state_crossings]

    @property
    def toll_events(self) -> list[TollEvent]:
        return [event for leg in self.legs for event in leg.toll_events]

    @property
    def estimated_tolls(self) -> float:
        return sum(event.amount for event in self.toll_events)

    @property
    def checkpoints(self) -> list[RouteCheckpoint]:
        return [c for leg in self.legs for c in leg.checkpoints]

    @property
    def terrain_summary(self) -> str:
        kinds = {leg.terrain for leg in self.legs}
        if kinds == {"flat"}:
            return "flat"
        if "mountain" in kinds:
            return "mountainous in places"
        return "rolling hills"

    def describe(self) -> str:
        via = " then ".join(self.highways)
        return (f"{self.miles:.0f} miles via {via}, "
                f"{len(self.legs)} leg{'s' if len(self.legs) != 1 else ''}, "
                f"terrain {self.terrain_summary}")

    def metadata_complete(self, world: World) -> bool:
        return all(world.leg_metadata_complete(leg) for leg in self.legs)


class World:
    def __init__(self, data: dict) -> None:
        self.cities: dict[str, City] = {}
        self._facilities_by_id: dict[str, Location] = {}
        for name, c in data["cities"].items():
            lat = float(c.get("lat", 0.0))
            lon = float(c.get("lon", 0.0))
            explicit_locs = tuple(
                _parse_location(loc, name, lat, lon)
                for loc in c["locations"]
            )
            tags = _market_tags_for_city(name, c, explicit_locs)
            locs = _expand_market_locations(name, lat, lon, explicit_locs, tags)
            self._validate_city_locations(name, locs)
            self.cities[name] = City(name, c["state"], c["region"], locs,
                                     lat, lon, tags)

        self.legs: list[Leg] = []
        for leg in data["legs"]:
            miles = float(leg["miles"])
            stops = tuple(_parse_stop(s, miles, leg["from"], leg["to"])
                          for s in leg.get("stops", ()))
            corridor = leg.get("corridor", {})
            route_points = tuple(
                _parse_route_point(p, miles, leg["from"], leg["to"])
                for p in corridor.get("route_points", ())
            )
            elevation_samples = tuple(
                _parse_elevation_sample(s, miles, leg["from"], leg["to"])
                for s in corridor.get("elevation_samples", ())
            )
            grade_segments = tuple(
                _parse_grade_segment(s, miles, leg["from"], leg["to"])
                for s in corridor.get("grade_segments", ())
            )
            state_crossings = tuple(
                _parse_state_crossing(c, miles, leg["from"], leg["to"],
                                      self.cities[leg["from"]].state)
                for c in corridor.get("state_crossings", ())
            )
            checkpoints = tuple(
                _parse_checkpoint(c, miles, leg["from"], leg["to"])
                for c in corridor.get("checkpoints", ())
            )
            state_miles = tuple(
                _parse_state_mileage(m, leg["from"], leg["to"])
                for m in corridor.get("state_miles", ())
            )
            toll_events = tuple(
                _parse_toll_event(e, miles, leg["from"], leg["to"], leg["highway"])
                for e in corridor.get("toll_events", ())
            )
            self.legs.append(
                Leg(leg["from"], leg["to"], miles, leg["highway"],
                    leg["terrain"], stops, route_points, elevation_samples,
                    grade_segments, state_crossings, checkpoints, state_miles,
                    toll_events)
            )
        self._adjacency: dict[str, list[Leg]] = {name: [] for name in self.cities}
        for leg in self.legs:
            self._adjacency[leg.a].append(leg)
            self._adjacency[leg.b].append(leg)

    def _validate_city_locations(self, city: str, locations: tuple[Location, ...]) -> None:
        if not locations:
            raise ValueError(f"{city} has no freight facilities")
        for location in locations:
            if location.type not in FREIGHT_LOCATION_TYPES:
                raise ValueError(
                    f"{city} facility {location.name!r} has unknown type {location.type!r}"
                )
            if not location.id:
                raise ValueError(f"{city} facility {location.name!r} has no stable id")
            if location.id in self._facilities_by_id:
                raise ValueError(f"Duplicate facility id {location.id!r}")
            if not location.spoken_name:
                raise ValueError(f"{city} facility {location.name!r} has no spoken name")
            if not location.source_note:
                raise ValueError(f"{city} facility {location.name!r} has no source note")
            if not location.ships and not location.receives:
                raise ValueError(f"{city} facility {location.name!r} has no cargo roles")
            self._facilities_by_id[location.id] = location

    @classmethod
    def load(cls, path: Path = WORLD_PATH) -> World:
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def city_names(self) -> list[str]:
        return sorted(self.cities)

    def neighbors(self, city: str) -> list[Leg]:
        return self._adjacency[city]

    def facility_location(self, city: str, location_name: str) -> Location:
        if city not in self.cities:
            raise KeyError(f"Unknown city: {city}")
        normalized_name = str(location_name or "").strip()
        for location in self.cities[city].locations:
            if location.name == normalized_name or location.id == normalized_name:
                return location
        if _is_legacy_market_name(city, normalized_name):
            return self.default_facility(city)
        raise KeyError(f"Unknown facility in {city}: {location_name}")

    def facility_by_id(self, facility_id: str) -> Location:
        try:
            return self._facilities_by_id[facility_id]
        except KeyError:
            raise KeyError(f"Unknown facility id: {facility_id}") from None

    def default_facility(self, city: str) -> Location:
        """Stable fallback for legacy jobs that only named a city."""
        if city not in self.cities:
            raise KeyError(f"Unknown city: {city}")
        locations = self.cities[city].locations
        preferred = (
            "company_yard",
            "terminal",
            "dry_warehouse",
            "warehouse",
            "distribution",
            "cross_dock",
        )
        for facility_type in preferred:
            for location in locations:
                if location.type == facility_type:
                    return location
        return locations[0]

    def home_terminal(self, city: str) -> HomeTerminal:
        """Return the player's dispatch yard for a service area.

        The world data mostly lists shippers and receivers rather than company
        yards, so explicit terminal facilities are preferred and every other
        city gets a stable fallback yard name.
        """
        if city not in self.cities:
            raise KeyError(f"Unknown city: {city}")
        city_obj = self.cities[city]
        for location in city_obj.locations:
            if location.type == "terminal":
                return HomeTerminal(location.name, city, city_obj.state, "terminal")
        for location in city_obj.locations:
            if location.type == "company_yard":
                return HomeTerminal(location.name, city, city_obj.state, "company_yard")
        return HomeTerminal(f"{city} Company Yard", city, city_obj.state, "company_yard")

    def facility_approach_route(self, city: str, location_name: str) -> Route:
        """A short, drivable local route from the company terminal to a facility."""
        location = self.facility_location(city, location_name)
        base_miles = FACILITY_APPROACH_MILES.get(location.type, 4.0)
        seed = zlib.crc32(f"{city}:{location.name}:{location.type}".encode())
        offset = (seed % 7) * 0.25
        miles = round(base_miles + offset, 1)
        road = FACILITY_APPROACH_ROADS.get(location.type, "facility access road")
        leg = Leg(city, city, miles, road, "flat", ())
        return Route([city, city], [leg])

    def shortest_route(self, start: str, end: str,
                       penalties: dict[Leg, float] | None = None,
                       require_metadata: bool = False) -> Route | None:
        """Dijkstra over leg miles, with optional per-leg penalty multipliers.

        ``require_metadata`` is for new dispatchable freight. The default keeps
        the historical full graph available for legacy saves and map integrity
        checks while supported freight routes are enriched lane by lane.
        """
        if start not in self.cities or end not in self.cities:
            raise KeyError(f"Unknown city: {start if start not in self.cities else end}")
        penalties = penalties or {}
        dist: dict[str, float] = {start: 0.0}
        prev: dict[str, tuple[str, Leg]] = {}
        heap: list[tuple[float, str]] = [(0.0, start)]
        visited: set[str] = set()
        while heap:
            d, city = heapq.heappop(heap)
            if city in visited:
                continue
            visited.add(city)
            if city == end:
                break
            for leg in self._adjacency[city]:
                if require_metadata and not self.leg_metadata_complete(leg):
                    continue
                nxt = leg.other(city)
                cost = leg.miles * penalties.get(leg, 1.0)
                nd = d + cost
                if nd < dist.get(nxt, float("inf")):
                    dist[nxt] = nd
                    prev[nxt] = (city, leg)
                    heapq.heappush(heap, (nd, nxt))
        if end not in prev and start != end:
            return None
        cities = [end]
        legs: list[Leg] = []
        cur = end
        while cur != start:
            parent, leg = prev[cur]
            legs.append(leg)
            cities.append(parent)
            cur = parent
        cities.reverse()
        legs.reverse()
        return Route(cities, legs)

    def route_from_cities(self, cities: list[str]) -> Route | None:
        """Rebuild a route from its city sequence (used by saved trips).

        Returns None if any hop is missing, so callers can fall back
        gracefully when a save references a road that no longer exists. This is
        intentionally the legacy/full graph path; new freight uses supported
        route helpers so missing metadata cannot silently invent conditions.
        """
        if len(cities) < 2:
            return None
        legs: list[Leg] = []
        for a, b in zip(cities, cities[1:], strict=False):
            leg = next((x for x in self._adjacency.get(a, ()) if x.other(a) == b), None)
            if leg is None:
                return None
            legs.append(leg)
        return Route(list(cities), legs)

    def leg_metadata_complete(self, leg: Leg) -> bool:
        return leg.metadata_complete(self.cities[leg.a].state, self.cities[leg.b].state)

    def supported_route(self, start: str, end: str,
                        penalties: dict[Leg, float] | None = None) -> Route | None:
        return self.shortest_route(start, end, penalties, require_metadata=True)

    def supported_route_options(self, start: str, end: str,
                                count: int = 3) -> list[Route]:
        return self.route_options(start, end, count, require_metadata=True)

    def route_options(self, start: str, end: str, count: int = 3,
                      require_metadata: bool = False) -> list[Route]:
        """Up to ``count`` distinct routes, fastest first."""
        routes: list[Route] = []
        penalties: dict[Leg, float] = {}
        seen: set[tuple[str, ...]] = set()
        best = self.shortest_route(start, end, require_metadata=require_metadata)
        if best is None:
            return routes
        max_miles = _max_alternate_miles(best.miles)
        for _ in range(count * 8):
            route = self.shortest_route(start, end, penalties,
                                        require_metadata=require_metadata)
            if route is None:
                break
            key = tuple(route.cities)
            if key not in seen and route.miles <= max_miles:
                seen.add(key)
                routes.append(route)
                if len(routes) >= count:
                    break
            for leg in route.legs:
                penalties[leg] = penalties.get(leg, 1.0) * 2.5
        routes.sort(key=lambda r: r.miles)
        return routes


_world: World | None = None


def _parse_location(raw: dict, city: str, city_lat: float, city_lon: float) -> Location:
    if not isinstance(raw, dict):
        raise ValueError(f"{city} facility must be an object")
    name = _clean_facility_name(city, str(raw.get("name", "")).strip())
    facility_type = str(raw.get("type", "")).strip()
    if facility_type not in FREIGHT_LOCATION_TYPES:
        raise ValueError(f"{city} facility {name!r} has unknown type {facility_type!r}")
    default_roles = FACILITY_CARGO_ROLES.get(facility_type, {})
    raw_cargo = tuple(
        str(cargo).strip()
        for cargo in raw.get("cargo", ())
        if str(cargo).strip()
    )
    default_cargo = _dedupe(
        default_roles.get("ships", ()) + default_roles.get("receives", ())
    )
    cargo = raw_cargo or default_cargo
    ships = _role_cargo(raw, "ships", cargo, default_roles.get("ships", ()))
    receives = _role_cargo(raw, "receives", cargo, default_roles.get("receives", ()))
    roles = tuple(
        role
        for role, values in (("shipper", ships), ("receiver", receives))
        if values
    )
    source_note = str(
        raw.get("source_note")
        or raw.get("source")
        or FACILITY_SOURCE_NOTES.get(facility_type, "Curated representative facility.")
    ).strip()
    spoken = str(raw.get("spoken_name") or raw.get("spoken") or "").strip()
    locality = str(raw.get("locality", "")).strip()
    traits = tuple(
        str(trait).strip()
        for trait in raw.get("traits", ())
        if str(trait).strip()
    )
    return Location(
        name=name,
        type=facility_type,
        cargo=cargo,
        id=str(raw.get("id") or _stable_facility_id(city, facility_type, name)).strip(),
        city=city,
        locality=locality,
        roles=roles,
        ships=ships,
        receives=receives,
        lat=float(raw.get("lat", city_lat)),
        lon=float(raw.get("lon", city_lon)),
        traits=traits,
        source_note=source_note,
        spoken=spoken,
        template=bool(raw.get("template", False)),
        min_level=int(raw.get("min_level", FACILITY_LEVEL_UNLOCKS.get(facility_type, 1))),
    )


def _expand_market_locations(city: str, lat: float, lon: float,
                             explicit_locations: tuple[Location, ...],
                             market_tags: tuple[str, ...]) -> tuple[Location, ...]:
    locations = list(explicit_locations)
    existing_types = {location.type for location in locations}
    existing_names = {location.name.lower() for location in locations}
    desired_types = list(BASE_MARKET_FACILITY_TYPES)
    for tag in market_tags:
        desired_types.extend(MARKET_TAG_FACILITY_TYPES.get(tag, ()))
    for facility_type in _dedupe(desired_types):
        if facility_type in existing_types:
            continue
        location = _template_location(city, lat, lon, facility_type, market_tags)
        if location.name.lower() in existing_names:
            location = _template_location(
                city, lat, lon, facility_type, market_tags,
                name_suffix=" Facility",
            )
        locations.append(location)
        existing_types.add(location.type)
        existing_names.add(location.name.lower())
    return tuple(locations)


def _template_location(city: str, lat: float, lon: float, facility_type: str,
                       market_tags: tuple[str, ...],
                       name_suffix: str = "") -> Location:
    template = FACILITY_NAME_TEMPLATES[facility_type]
    name = template.format(city=city) + name_suffix
    roles = FACILITY_CARGO_ROLES[facility_type]
    cargo = _dedupe(roles["ships"] + roles["receives"])
    source_note = (
        f"{FACILITY_SOURCE_NOTES[facility_type]} Generated offline as a "
        f"representative {city} metro-market facility; not a claim about a "
        "specific real-world shipper."
    )
    jitter_lat, jitter_lon = _jittered_coordinates(city, facility_type, lat, lon)
    return Location(
        name=name,
        type=facility_type,
        cargo=cargo,
        id=_stable_facility_id(city, facility_type, name),
        city=city,
        roles=("shipper", "receiver"),
        ships=roles["ships"],
        receives=roles["receives"],
        lat=jitter_lat,
        lon=jitter_lon,
        traits=("representative", "template") + market_tags,
        source_note=source_note,
        template=True,
        min_level=FACILITY_LEVEL_UNLOCKS.get(facility_type, 1),
    )


def _market_tags_for_city(city: str, raw_city: dict,
                          locations: tuple[Location, ...]) -> tuple[str, ...]:
    tags: set[str] = set(REGION_MARKET_TAGS.get(str(raw_city.get("region", "")), ()))
    tags.update(STATE_MARKET_TAGS.get(str(raw_city.get("state", "")), ()))
    tags.update(CITY_MARKET_TAGS.get(city, ()))
    for location in locations:
        tags.update(_tags_for_facility_type(location.type))
    return tuple(sorted(tags))


def _tags_for_facility_type(facility_type: str) -> tuple[str, ...]:
    return {
        "air_cargo": ("air",),
        "distribution": ("retail",),
        "food_terminal": ("food", "cold_chain"),
        "industrial_park": ("industrial",),
        "intermodal": ("intermodal",),
        "manufacturing": ("manufacturing",),
        "port": ("port",),
        "rail": ("intermodal",),
        "retail_distribution": ("retail",),
        "terminal": ("cross_dock",),
        "warehouse": ("retail",),
    }.get(facility_type, ())


def _role_cargo(raw: dict, key: str, cargo: tuple[str, ...],
                defaults: tuple[str, ...]) -> tuple[str, ...]:
    values = tuple(
        str(value).strip()
        for value in raw.get(key, ())
        if str(value).strip()
    )
    if values:
        return values
    plausible = tuple(value for value in cargo if value in defaults)
    return plausible or tuple(value for value in cargo if value)


def _clean_facility_name(city: str, name: str) -> str:
    if not name:
        raise ValueError(f"{city} has a facility without a name")
    lowered = name.lower()
    if any(marker in lowered for marker in RAW_FACILITY_TEXT_MARKERS):
        raise ValueError(f"{city} facility {name!r} exposes raw source text")
    return name


def _stable_facility_id(city: str, facility_type: str, name: str) -> str:
    return f"{_slug(city)}:{facility_type}:{_slug(name)}"


def _slug(text: str) -> str:
    out: list[str] = []
    pending_dash = False
    for char in text.lower():
        if char.isalnum():
            if pending_dash and out:
                out.append("-")
            out.append(char)
            pending_dash = False
        else:
            pending_dash = True
    return "".join(out).strip("-") or "facility"


def _dedupe(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


def _jittered_coordinates(city: str, facility_type: str, lat: float,
                          lon: float) -> tuple[float, float]:
    if lat == 0.0 and lon == 0.0:
        return lat, lon
    seed = zlib.crc32(f"{city}:{facility_type}".encode())
    lat_offset = ((seed & 0xFF) - 128) / 5000.0
    lon_offset = (((seed >> 8) & 0xFF) - 128) / 5000.0
    return round(lat + lat_offset, 5), round(lon + lon_offset, 5)


def _is_legacy_market_name(city: str, name: str) -> bool:
    normalized = name.strip().lower()
    city_lower = city.lower()
    return normalized in {
        "",
        city_lower,
        f"{city_lower} freight market",
        f"{city_lower} metro freight market",
    }


def _parse_stop(raw, leg_miles: float, from_city: str, to_city: str) -> Stop:
    if not isinstance(raw, dict):
        raise ValueError(
            f"{from_city} to {to_city} stop {raw!r} is missing explicit at_mi"
        )
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} has a stop without a name")
    lowered_name = name.lower()
    if any(marker in lowered_name for marker in RAW_POI_TEXT_MARKERS):
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} exposes raw OSM/source text"
        )
    if "at_mi" not in raw:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} is missing explicit at_mi"
        )
    at_mi = float(raw["at_mi"])
    if not 0.0 < at_mi < leg_miles:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has at_mi {at_mi}, "
            f"outside leg mileage 0-{leg_miles}"
        )
    stop_type = str(raw.get("type", "")).strip() or _classify_stop(name)
    if stop_type not in STOP_TYPE_LABELS:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown type {stop_type!r}"
        )
    source = str(raw.get("source", "")).strip()
    actions = tuple(str(action).strip() for action in raw.get(
        "actions", DEFAULT_POI_ACTIONS[stop_type]))
    if not actions:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has no actions")
    unknown = sorted(set(actions) - POI_ACTIONS)
    if unknown:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown actions {unknown}"
        )
    default_actions = set(DEFAULT_POI_ACTIONS[stop_type])
    disallowed = sorted(set(actions) - default_actions)
    if disallowed:
        source_backed = set(disallowed) <= SOURCE_BACKED_POI_ACTIONS
        if not source_backed:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} actions {disallowed} "
                f"do not match type {stop_type!r}"
            )
    services = tuple(
        str(service).strip()
        for service in raw.get("services", ())
        if str(service).strip()
    )
    parking = str(raw.get("parking", "")).strip() or _default_parking_certainty(
        stop_type, services, actions
    )
    if parking not in PARKING_CERTAINTY_LABELS:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown parking "
            f"certainty {parking!r}"
        )
    directions = tuple(
        str(direction).strip()
        for direction in raw.get("directions", ("both",))
        if str(direction).strip()
    )
    if not directions:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has no directions")
    unknown_directions = sorted(set(directions) - STOP_DIRECTIONS)
    if unknown_directions:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown directions "
            f"{unknown_directions}"
        )
    if "both" in directions and len(directions) > 1:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} mixes 'both' with "
            "direction-specific applicability"
        )
    curation = str(raw.get("curation", "")).strip() or _infer_stop_curation(name, source)
    if curation not in STOP_CURATION_LEVELS:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown curation "
            f"{curation!r}"
        )
    if curation == "curated" and _infer_stop_curation(name, source) == "placeholder":
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} looks synthetic but is "
            "marked curated"
        )
    for action in SOURCE_BACKED_POI_ACTIONS & set(actions):
        if action not in services:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} action {action!r} "
                "requires matching source-backed service metadata"
            )
        if not source:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} action {action!r} "
                "requires a source note"
            )
    return Stop(name, at_mi, stop_type, source, actions, services,
                parking, directions, curation)


def _parse_route_point(raw, leg_miles: float, from_city: str, to_city: str) -> RoutePoint:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} route point must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "route point",
                         allow_endpoints=True)
    lat = float(raw["lat"])
    lon = float(raw["lon"])
    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        raise ValueError(f"{from_city} to {to_city} route point has invalid coordinates")
    return RoutePoint(at_mi, lat, lon)


def _parse_elevation_sample(raw, leg_miles: float, from_city: str,
                            to_city: str) -> ElevationSample:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} elevation sample must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "elevation sample",
                         allow_endpoints=True)
    elevation_ft = float(raw["elevation_ft"])
    if not -300.0 <= elevation_ft <= 20_500.0:
        raise ValueError(
            f"{from_city} to {to_city} elevation sample has invalid elevation"
        )
    source = str(raw.get("source", "")).strip()
    return ElevationSample(at_mi, elevation_ft, source)


def _parse_grade_segment(raw, leg_miles: float, from_city: str,
                         to_city: str) -> GradeSegment:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} grade segment must be an object")
    if "start_mi" not in raw:
        raise ValueError(
            f"{from_city} to {to_city} grade segment is missing explicit start_mi"
        )
    start_mi = float(raw["start_mi"])
    if not 0.0 <= start_mi <= leg_miles:
        raise ValueError(
            f"{from_city} to {to_city} grade segment start has start_mi {start_mi}, "
            f"outside leg mileage 0-{leg_miles}"
        )
    end_mi = float(raw["end_mi"])
    if not 0.0 <= end_mi <= leg_miles or end_mi <= start_mi:
        raise ValueError(
            f"{from_city} to {to_city} grade segment has invalid range "
            f"{start_mi}-{end_mi}"
        )
    avg_grade_pct = float(raw["avg_grade_pct"])
    if not -15.0 <= avg_grade_pct <= 15.0:
        raise ValueError(
            f"{from_city} to {to_city} grade segment has unrealistic grade "
            f"{avg_grade_pct}"
        )
    terrain = str(raw.get("terrain", "")).strip() or "flat"
    if terrain not in {"flat", "hills", "mountain"}:
        raise ValueError(
            f"{from_city} to {to_city} grade segment has unknown terrain {terrain!r}"
        )
    source = str(raw.get("source", "")).strip()
    return GradeSegment(start_mi, end_mi, avg_grade_pct, terrain, source)


def _parse_state_crossing(raw, leg_miles: float, from_city: str, to_city: str,
                          default_from_state: str) -> StateCrossing:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} state crossing must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "state crossing")
    state = str(raw.get("state", "")).strip()
    if not state:
        raise ValueError(f"{from_city} to {to_city} has a state crossing without a state")
    from_state = str(raw.get("from_state", "")).strip() or default_from_state
    place = str(raw.get("place", "")).strip() or "state line"
    source = str(raw.get("source", "")).strip()
    return StateCrossing(at_mi, from_state, state, place, source)


def _parse_checkpoint(raw, leg_miles: float, from_city: str,
                      to_city: str) -> RouteCheckpoint:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} checkpoint must be an object")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} has a checkpoint without a name")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, f"checkpoint {name!r}")
    checkpoint_type = str(raw.get("type", "")).strip() or "place"
    state = str(raw.get("state", "")).strip()
    highway = str(raw.get("highway", "")).strip()
    source = str(raw.get("source", "")).strip()
    return RouteCheckpoint(name, at_mi, checkpoint_type, state, highway, source)


def _parse_state_mileage(raw, from_city: str, to_city: str) -> StateMileage:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} state mileage must be an object")
    state = str(raw.get("state", "")).strip()
    if not state:
        raise ValueError(f"{from_city} to {to_city} has state mileage without a state")
    miles = float(raw["miles"])
    if miles <= 0.0:
        raise ValueError(f"{from_city} to {to_city} state mileage must be positive")
    return StateMileage(state, miles)


def _parse_toll_event(raw, leg_miles: float, from_city: str, to_city: str,
                      default_road: str) -> TollEvent:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} toll event must be an object")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} toll event has no name")
    lowered_name = name.lower()
    if any(marker in lowered_name for marker in RAW_POI_TEXT_MARKERS):
        raise ValueError(
            f"{from_city} to {to_city} toll event {name!r} exposes raw OSM/source text"
        )
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city,
                         f"toll event {name!r}")
    road = str(raw.get("road", "")).strip() or default_road
    authority = str(raw.get("authority", "")).strip()
    method = str(raw.get("method", "")).strip()
    source = str(raw.get("source", "")).strip()
    if not authority:
        raise ValueError(f"{from_city} to {to_city} toll event {name!r} has no authority")
    if method not in TOLL_METHOD_LABELS:
        raise ValueError(
            f"{from_city} to {to_city} toll event {name!r} has unknown method {method!r}"
        )
    amount = float(raw["amount"])
    if amount < 0.0 or amount > 500.0:
        raise ValueError(
            f"{from_city} to {to_city} toll event {name!r} has invalid amount"
        )
    if not source:
        raise ValueError(f"{from_city} to {to_city} toll event {name!r} has no source")
    return TollEvent(
        name=name,
        at_mi=at_mi,
        road=road,
        authority=authority,
        method=method,
        amount=amount,
        estimated=bool(raw.get("estimated", True)),
        source=source,
    )


def _parse_at_mi(raw: dict, leg_miles: float, from_city: str, to_city: str,
                 label: str, *, allow_endpoints: bool = False) -> float:
    if "at_mi" not in raw:
        raise ValueError(f"{from_city} to {to_city} {label} is missing explicit at_mi")
    at_mi = float(raw["at_mi"])
    in_range = 0.0 <= at_mi <= leg_miles if allow_endpoints else 0.0 < at_mi < leg_miles
    if not in_range:
        raise ValueError(
            f"{from_city} to {to_city} {label} has at_mi {at_mi}, "
            f"outside leg mileage 0-{leg_miles}"
        )
    return at_mi


def _classify_stop(name: str) -> str:
    lower = name.lower()
    if "weigh" in lower:
        return "weigh_station"
    if "parking" in lower:
        return "truck_parking"
    if "rest area" in lower:
        return "public_rest_area"
    if "service plaza" in lower:
        return "service_plaza"
    if "truck" in lower:
        return "truck_stop"
    if any(word in lower for word in ("travel", "fuel", "plaza", "center")):
        return "travel_center"
    return "travel_center"


def _default_parking_certainty(
    stop_type: str,
    services: tuple[str, ...],
    actions: tuple[str, ...],
) -> str:
    if "parking" not in services and "park" not in actions:
        return "none"
    if stop_type in {"truck_stop", "travel_center", "service_plaza"}:
        return "likely"
    if stop_type in {"public_rest_area", "truck_parking"}:
        return "limited"
    return "unknown"


def _infer_stop_curation(name: str, source: str) -> str:
    text = f"{name} {source}".lower()
    synthetic_markers = (
        "corridor rest area",
        "corridor truck parking",
        "corridor fuel stop",
        "descriptive gameplay stop seeded",
        "seeded for offline route coverage",
        "no actionable overpass poi candidate",
    )
    return "placeholder" if any(marker in text for marker in synthetic_markers) else "curated"


def minimum_curated_pois(miles: float) -> int:
    if miles < POI_DENSITY_SHORT_LEG_MILES:
        return 1
    if miles <= POI_DENSITY_MEDIUM_LEG_MILES:
        return 2
    return 3


def minimum_fuel_capable_pois(miles: float) -> int:
    if miles < POI_DENSITY_SHORT_LEG_MILES:
        return 0
    return 1


def _max_alternate_miles(best_miles: float) -> float:
    extra = best_miles * ALTERNATE_ROUTE_EXTRA_RATIO
    extra = max(ALTERNATE_ROUTE_MIN_EXTRA_MILES,
                min(ALTERNATE_ROUTE_MAX_EXTRA_MILES, extra))
    return best_miles + extra


def get_world() -> World:
    """Shared world instance (the data is immutable)."""
    global _world
    if _world is None:
        _world = World.load()
    return _world
