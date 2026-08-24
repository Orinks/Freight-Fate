//! API endpoints for all 50 US states (plus DC): the `STATE_APIS` registry
//! and its per-state notes. Split out of `real_traffic` to keep that file
//! under the thousand-line mark; the registry itself is unchanged.

// ---- The endpoint registry ------------------------------------------------

/// One state's 511 configuration.
///
/// `parser` selects the response format handler:
///   "ohgo"    — Ohio OHGO native JSON format
///   "iteris"  — Iteris/INRIX-platform 511 websites (shared `/Events` format)
///   "wzdx"    — Work Zone Data Exchange (GeoJSON FeatureCollection)
///   "cars"    — Castle Rock CARS GraphQL platform.  `events_endpoint` and
///                `construction_endpoint` hold the deployment's layer slug
///                for each fetch (slugs vary per site), and `bounds` is the
///                statewide "south,west,north,east" query box.
///   "list511" — The 511 site's own list JSON.  `events_endpoint` holds the
///                list layer name (e.g. "Incidents"); text rides
///                POST /List/GetData/<layer> and coordinates come from
///                GET /map/mapIcons/<layer>, joined on the event id.
///   "no_api"  — No working public 511 API.  Returns empty data so the
///                simulation falls back to procedurally generated construction
///                zones without log warnings.
///
/// `construction_parser` (optional) overrides `parser` for the
/// construction fetch only, for sites whose incidents and work zones live on
/// different platforms (Florida and New York: list511 incidents + WZDx zones).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StateApi {
    pub base_url: Option<&'static str>,
    pub events_endpoint: Option<&'static str>,
    pub construction_endpoint: Option<&'static str>,
    pub bounds: Option<&'static str>,
    pub name: &'static str,
    pub parser: &'static str,
    pub construction_parser: Option<&'static str>,
}

const fn no_api(name: &'static str) -> StateApi {
    StateApi {
        base_url: None,
        events_endpoint: None,
        construction_endpoint: None,
        bounds: None,
        name,
        parser: "no_api",
        construction_parser: None,
    }
}

const fn wzdx(base_url: &'static str, name: &'static str) -> StateApi {
    StateApi {
        base_url: Some(base_url),
        events_endpoint: Some("/api/wzdx"),
        construction_endpoint: Some("/api/wzdx"),
        bounds: None,
        name,
        parser: "wzdx",
        construction_parser: None,
    }
}

const fn cars(
    base_url: &'static str,
    events: &'static str,
    construction: &'static str,
    bounds: &'static str,
    name: &'static str,
) -> StateApi {
    StateApi {
        base_url: Some(base_url),
        events_endpoint: Some(events),
        construction_endpoint: Some(construction),
        bounds: Some(bounds),
        name,
        parser: "cars",
        construction_parser: None,
    }
}

const fn list511(base_url: &'static str, name: &'static str) -> StateApi {
    StateApi {
        base_url: Some(base_url),
        events_endpoint: Some("Incidents"),
        construction_endpoint: Some("/api/wzdx"),
        bounds: None,
        name,
        parser: "list511",
        construction_parser: Some("wzdx"),
    }
}

/// API endpoints for all 50 US states (plus DC), keyed by lower-case
/// state name.
///
/// States with no working public 511 API are listed with `parser: "no_api"` so
/// the coverage is explicit: unsupported states still return empty data
/// gracefully. The whole registry was live-swept 2026-08-09; per-state notes
/// below.
pub static STATE_APIS: &[(&str, StateApi)] = &[
    // ── OHGO ──────────────────────────────────────────────────────────────
    // publicapi.ohgo.com's keyless v1 endpoints are gone (404) and the
    // current API answers 401 without a registered key (checked 2026-08-09).
    // no_api keeps Ohio silently on simulated traffic until a key story
    // exists; the endpoints stay listed for when it does.
    (
        "ohio",
        StateApi {
            base_url: Some("https://publicapi.ohgo.com"),
            events_endpoint: Some("/v1/incidents"),
            construction_endpoint: Some("/v1/construction"),
            bounds: None,
            name: "Ohio OHGO",
            parser: "no_api",
            construction_parser: None,
        },
    ),
    // ── Castle Rock CARS GraphQL platform ────────────────────────────────
    // These sites serve their SPA shell for every REST path; the data rides
    // POST /api/graphql (MapFeatures query, verified live 2026-08-09).
    (
        "indiana",
        cars(
            "https://511in.org",
            "incidents",
            "construction",
            "37.7,-88.2,41.9,-84.6",
            "Indiana 511IN",
        ),
    ),
    (
        "minnesota",
        cars(
            "https://511mn.org",
            "incidents",
            "workZones",
            "43.4,-97.3,49.4,-89.4",
            "Minnesota 511MN",
        ),
    ),
    (
        "colorado",
        cars(
            "https://www.cotrip.org",
            "roadReports",
            "roadWork",
            "36.9,-109.1,41.1,-102.0",
            "Colorado COtrip",
        ),
    ),
    // ── WZDx standard (GeoJSON FeatureCollection) ────────────────────────
    // The old per-site /api/events endpoints are gone everywhere, but these
    // sites publish a live WZDx v4.x work-zone feed at /api/wzdx (verified
    // 2026-08-09), so both fetches read it; incidents simply don't appear.
    // Florida and New York (below) keep their WZDx work zones but now pull
    // incidents from the list511 endpoints instead.
    ("arizona", wzdx("https://az511.com", "Arizona AZ511")),
    (
        "connecticut",
        wzdx("https://ctroads.org", "Connecticut CTroads"),
    ),
    // ── list511: incidents from the site's list JSON, zones from WZDx ────
    // fl511.com and 511ny.org publish work zones at /api/wzdx but no
    // incidents there.  Their own list pages ride an open DataTables-style
    // JSON endpoint (POST /List/GetData/<layer>) carrying the full incident
    // text, and /map/mapIcons/<layer> supplies id -> [lat, lon] for the map
    // pins; the two join on the event id.  Both fetched keyless 2026-08-20:
    // FL 22 incidents, NY 105 incidents, shape {"recordsTotal": N,
    // "data": [{id, roadwayName, description, severity, isFullClosure,
    // laneDescription, county, ...}]}.  (Each site also documents a
    // developer API, but that one requires a registered key.)
    ("florida", list511("https://fl511.com", "Florida FL511")),
    ("georgia", wzdx("https://511ga.org", "Georgia 511GA")),
    ("idaho", wzdx("https://511.idaho.gov", "Idaho 511")),
    ("nevada", wzdx("https://nvroads.com", "Nevada NVRoads")),
    // See the florida note: same platform, verified keyless 2026-08-20.
    ("new york", list511("https://511ny.org", "New York 511NY")),
    (
        "north carolina",
        wzdx("https://drivenc.gov", "North Carolina DriveNC"),
    ),
    (
        "pennsylvania",
        wzdx("https://511pa.com", "Pennsylvania 511PA"),
    ),
    (
        "utah",
        wzdx("https://udottraffic.utah.gov", "Utah UDOT Traffic"),
    ),
    // 511wi.gov's old REST API is gone, but the site publishes a live WZDx
    // v4.2 feed at /api/wzdx (found 2026-08-09), so Wisconsin is back off
    // the no_api bench.
    ("wisconsin", wzdx("https://511wi.gov", "Wisconsin 511WI")),
    // ── Dead APIs (live-swept 2026-08-09; fallback to simulated data) ────
    // california: 511.ca.gov no longer resolves in DNS; no statewide feed found.
    ("california", no_api("California Caltrans 511")),
    // maryland: roads.maryland.gov 404s on /api/events and /api/wzdx.
    ("maryland", no_api("Maryland CHART")),
    // michigan: michigan.gov/mdot answers 403 on every API-looking path.
    ("michigan", no_api("Michigan MDOT")),
    // missouri: gatewayguide.com 404s on /api/events and /api/wzdx.
    ("missouri", no_api("Missouri Gateway Guide")),
    // new jersey: 511nj.org fronts a WAF that answers 403 Access Denied.
    ("new jersey", no_api("New Jersey 511NJ")),
    // oregon: tripcheck.com serves HTML for every path incl. the old
    // /WZDx_v4.json; TripCheck's real API requires a registered key.
    ("oregon", no_api("Oregon TripCheck")),
    // tennessee: tnsmartway.com DNS is dead; smartway.tn.gov is an SPA with
    // no public JSON endpoint found.
    ("tennessee", no_api("Tennessee SmartWay")),
    // texas: api.drivetexas.org answers 401 (key required) / HTML.
    ("texas", no_api("Texas DriveTexas")),
    // virginia: 511virginia.org redirects to the 511.vdot.virginia.gov SPA;
    // no public JSON endpoint found.
    ("virginia", no_api("Virginia 511")),
    // washington: wsdot.wa.gov's traveler API requires a registered access
    // code on every call.
    ("washington", no_api("Washington WSDOT")),
    // ── No known public 511 API (fallback to simulated data) ─────────────
    ("alabama", no_api("Alabama")),
    ("alaska", no_api("Alaska")),
    ("arkansas", no_api("Arkansas")),
    ("delaware", no_api("Delaware")),
    ("hawaii", no_api("Hawaii")),
    ("illinois", no_api("Illinois")),
    ("iowa", no_api("Iowa")),
    ("kansas", no_api("Kansas")),
    ("kentucky", no_api("Kentucky")),
    ("louisiana", no_api("Louisiana")),
    ("maine", no_api("Maine")),
    ("massachusetts", no_api("Massachusetts")),
    ("mississippi", no_api("Mississippi")),
    ("montana", no_api("Montana")),
    ("nebraska", no_api("Nebraska")),
    ("new hampshire", no_api("New Hampshire")),
    ("new mexico", no_api("New Mexico")),
    ("north dakota", no_api("North Dakota")),
    ("oklahoma", no_api("Oklahoma")),
    ("rhode island", no_api("Rhode Island")),
    ("south carolina", no_api("South Carolina")),
    ("south dakota", no_api("South Dakota")),
    ("vermont", no_api("Vermont")),
    ("west virginia", no_api("West Virginia")),
    ("wyoming", no_api("Wyoming")),
    // DC is not a state but is a distinct region on the map
    ("district of columbia", no_api("District of Columbia")),
];

/// The registry entry for a lower-case state key.
pub fn state_api(state_key: &str) -> Option<&'static StateApi> {
    STATE_APIS
        .iter()
        .find(|(key, _)| *key == state_key)
        .map(|(_, api)| api)
}
