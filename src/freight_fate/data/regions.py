"""Canonical region taxonomy and coordinate-based classification.

A city's ``region`` is *derived* from its state and coordinates at build time
and baked into ``world.json``. ``classify_region`` is the single source of
truth: the stored-equals-derived test asserts every city's stored region equals
``classify_region(state, lat, lon)``, so a misclassification (such as Reno being
tagged the Rockies) cannot recur as the map grows.

The taxonomy blends NOAA climate regions (which drive weather flavor) with USGS
physiographic provinces (which drive grades and hazards), refined for freight
character. See ``docs/osm-routing-plan.md`` for the full design and the rationale
behind each region.

The classifier is deliberately a state map plus a few coordinate split rules for
states that span more than one region, rather than a heavyweight GIS polygon
set: it is deterministic, dependency-free, has no runtime cost, and is exactly
testable against the known cities. Single-region assignments for large states
and the split thresholds are approximations refined as the map grows; the
per-city test is the guardrail.
"""

from __future__ import annotations

# Canonical region keys. Every runtime region table -- weather weights
# (sim/weather.py), hazards (sim/trip.py), fuel price (models/economy.py),
# market tags (data/world.py) -- plus the spoken labels below must cover each of
# these keys. The test in tests/test_regions.py enforces full coverage.
REGIONS: tuple[str, ...] = (
    "northeast",
    "appalachia",
    "great_lakes",
    "heartland",
    "southern_plains",
    "mid_south",
    "atlantic_southeast",
    "gulf_coast",
    "florida",
    "rockies",
    "great_basin",
    "desert_southwest",
    "california",
    "pacific_northwest",
)

# Spoken/displayed names, read aloud in the home-terminal picker, so they want
# natural phrasing ("at ... in the Great Basin", "... in California").
REGION_LABELS: dict[str, str] = {
    "northeast": "the Northeast",
    "appalachia": "Appalachia",
    "great_lakes": "the Great Lakes",
    "heartland": "the Heartland",
    "southern_plains": "the Southern Plains",
    "mid_south": "the Mid-South",
    "atlantic_southeast": "the Atlantic Southeast",
    "gulf_coast": "the Gulf Coast",
    "florida": "Florida",
    "rockies": "the Rockies",
    "great_basin": "the Great Basin",
    "desert_southwest": "the Desert Southwest",
    "california": "California",
    "pacific_northwest": "the Pacific Northwest",
}

# States that fall entirely within one region. States that span more than one
# region (Texas, Nevada, Tennessee, Pennsylvania, New York) are handled by
# coordinate split rules in ``classify_region`` and are intentionally absent
# here. The lower 48 are covered so future cities classify without code changes.
STATE_REGION: dict[str, str] = {
    # Northeast
    "Maine": "northeast",
    "New Hampshire": "northeast",
    "Vermont": "northeast",
    "Massachusetts": "northeast",
    "Rhode Island": "northeast",
    "Connecticut": "northeast",
    "New Jersey": "northeast",
    "Delaware": "northeast",
    # Maryland is split by longitude in classify_region (western MD -> appalachia).
    "District of Columbia": "northeast",
    # Appalachia
    "West Virginia": "appalachia",
    # Great Lakes / industrial Midwest
    "Ohio": "great_lakes",
    # Indiana is split by latitude in classify_region (Evansville -> mid_south).
    "Illinois": "great_lakes",
    "Michigan": "great_lakes",
    "Wisconsin": "great_lakes",
    "Minnesota": "great_lakes",
    # Heartland (corn belt + Missouri/Mississippi valley + northern plains)
    "Missouri": "heartland",
    "Iowa": "heartland",
    "Nebraska": "heartland",
    "North Dakota": "heartland",
    "South Dakota": "heartland",
    # Southern Plains
    "Kansas": "southern_plains",
    "Oklahoma": "southern_plains",
    # Mid-South (interior Dixie / Cumberland / Ozark fringe)
    "Kentucky": "mid_south",
    "Alabama": "mid_south",
    "Mississippi": "mid_south",
    "Arkansas": "mid_south",
    # Atlantic Southeast (Piedmont + southern Atlantic coastal plain).
    # Virginia and North Carolina are split by longitude in classify_region
    # (their western Blue Ridge / Great Valley -> appalachia).
    "South Carolina": "atlantic_southeast",
    "Georgia": "atlantic_southeast",
    # Gulf Coast
    "Louisiana": "gulf_coast",
    # Florida
    "Florida": "florida",
    # Rockies
    "Colorado": "rockies",
    "Wyoming": "rockies",
    "Montana": "rockies",
    "Utah": "rockies",
    # Great Basin (Snake River Plain + Basin and Range)
    "Idaho": "great_basin",
    # Desert Southwest
    "Arizona": "desert_southwest",
    "New Mexico": "desert_southwest",
    # California
    "California": "california",
    # Pacific Northwest
    "Oregon": "pacific_northwest",
    "Washington": "pacific_northwest",
}


def classify_region(state: str, lat: float, lon: float) -> str:
    """Return the canonical region for a city by state and coordinates.

    Multi-region states are split first by a coordinate threshold; every other
    state maps directly. Raises ``ValueError`` for an unmapped state so map
    expansion cannot silently mis-derive a region.
    """
    if state == "Texas":
        if lon <= -104.0:
            return "desert_southwest"  # El Paso and far-west Texas
        if lat <= 31.0:
            return "gulf_coast"  # Houston, San Antonio, south Texas
        return "southern_plains"  # Dallas, Amarillo, north Texas
    if state == "Nevada":
        # Reno and northern Nevada are Great Basin; Las Vegas is Mojave desert.
        return "great_basin" if lat >= 38.0 else "desert_southwest"
    if state == "Tennessee":
        # East Tennessee is Appalachian; middle and west are Mid-South.
        return "appalachia" if lon >= -85.0 else "mid_south"
    if state == "Pennsylvania":
        # Erie sits on the Lake Erie shore -- lake-effect Great Lakes country,
        # like Buffalo and Cleveland on either side -- not Appalachian.
        if lat >= 42.0:
            return "great_lakes"
        # Western Pennsylvania is Appalachian; the southeast is the Northeast.
        return "appalachia" if lon <= -78.0 else "northeast"
    if state == "Indiana":
        # Far-southern Indiana on the Ohio River (Evansville) is Mid-South;
        # the rest of the state is the industrial Great Lakes Midwest.
        return "mid_south" if lat <= 38.5 else "great_lakes"
    if state == "New York":
        # Western New York (Buffalo) is lake-effect Great Lakes country.
        return "great_lakes" if lon <= -78.0 else "northeast"
    if state == "North Carolina":
        # The western Blue Ridge (Asheville) is Appalachian; the Piedmont and
        # coastal plain are the Atlantic Southeast.
        return "appalachia" if lon <= -82.0 else "atlantic_southeast"
    if state == "Virginia":
        # West of the Blue Ridge -- the I-81 Great Valley (Roanoke, Harrisonburg,
        # Winchester) -- is Appalachian; the Piedmont and Tidewater are not.
        return "appalachia" if lon <= -78.0 else "atlantic_southeast"
    if state == "Maryland":
        # Western Maryland (Hagerstown, the Cumberland valley) is Appalachian;
        # the rest is the Northeast corridor.
        return "appalachia" if lon <= -77.5 else "northeast"
    try:
        return STATE_REGION[state]
    except KeyError:
        raise ValueError(
            f"No region mapping for state {state!r}; add it to STATE_REGION or "
            "a coordinate split rule in classify_region (see "
            "docs/osm-routing-plan.md)."
        ) from None
