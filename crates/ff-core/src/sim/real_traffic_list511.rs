//! list511 parser: the 511 sites' own list-page JSON plus map pins.
//!
//! fl511.com and 511ny.org publish work zones on a standard WZDx feed but no
//! incidents; the incident data rides the endpoints their own site pages use,
//! verified keyless 2026-08-20:
//!
//!   `POST /List/GetData/<layer>`  — DataTables-style list rows with the full
//!       event text (`id`, `roadwayName`, `description`, `severity`,
//!       `isFullClosure`, `laneDescription`, `locationDescription`,
//!       `county`, date strings).  Needs the paging fields and one column
//!       definition or `data` comes back empty; a page caps at 100 rows.
//!   `GET /map/mapIcons/<layer>`   — the map pins: `{"item2": [{"itemId":
//!       ..., "location": [lat, lon]}, ...]}`.  Joined on the event id to give
//!       the list rows coordinates.
//!
//! Split out of `real_traffic_parsers` to keep that module at a reviewable
//! size.  The fetch side (paging, the pin join) lives in `real_traffic`.
//!
//! Port of `freight_fate/sim/real_traffic_list511.py`.

use std::collections::HashMap;

use once_cell::sync::Lazy;
use regex::Regex;
use serde_json::Value;

use super::real_traffic_parsers::pyval::{str_or_empty, to_f64};
use super::real_traffic_parsers::{map_severity, TrafficEvent};

/// `id -> (lat, lon)` from the map-pin layer.
pub type PinLocations = HashMap<String, (f64, f64)>;

/// Parse incidents from list511 list rows plus map-pin locations.
///
/// `rows` are the `data` entries from `POST /List/GetData/<layer>`
/// (fetched 2026-08-20 from fl511.com and 511ny.org: `id`,
/// `roadwayName`, `description`, `severity`, `isFullClosure`,
/// `laneDescription`, `locationDescription`, `county`, date
/// strings).  `locations` maps event id to `(lat, lon)` from the
/// matching `/map/mapIcons/<layer>` fetch; rows without a pin keep
/// `None` coordinates and fall out of the distance filters.
pub fn parse_list511_events(
    rows: &[Value],
    locations: &PinLocations,
    _state: &str,
) -> Vec<TrafficEvent> {
    let mut events = Vec::new();
    for row in rows {
        let Some(row) = row.as_object() else {
            continue;
        };
        // `str(row.get("id") or row.get("DT_RowId") or "")`
        let mut event_id = str_or_empty(row.get("id"));
        if event_id.is_empty() {
            event_id = str_or_empty(row.get("DT_RowId"));
        }
        if event_id.is_empty() {
            continue;
        }
        let description = clean_list511_text(&str_or_empty(row.get("description")));
        if description.is_empty() {
            continue;
        }
        // Site severities are Minor/Moderate/Major (NY) and
        // Minor/Intermediate/Major (FL); a flagged full closure
        // outranks whatever the row says.
        let severity = if row.get("isFullClosure") == Some(&Value::Bool(true)) {
            "high"
        } else {
            map_severity(&str_or_empty(row.get("severity")))
        };
        let (lat, lon) = match locations.get(&event_id) {
            Some((lat, lon)) => (Some(*lat), Some(*lon)),
            None => (None, None),
        };
        // NY separates location parts with "|" ("West 179th Street|")
        let location_text = str_or_empty(row.get("locationDescription"));
        let location_text = location_text
            .split('|')
            .map(str::trim)
            .filter(|part| !part.is_empty())
            .collect::<Vec<_>>()
            .join(", ");
        let lanes = str_or_empty(row.get("laneDescription")).trim().to_string();
        let lanes = if lanes.is_empty() { None } else { Some(lanes) };
        let date = |key: &str| -> Option<String> {
            let text = str_or_empty(row.get(key));
            if text.is_empty() {
                None
            } else {
                Some(text)
            }
        };
        events.push(TrafficEvent {
            id: event_id,
            event_type: "incident".into(),
            severity: severity.into(),
            description,
            county: str_or_empty(row.get("county")),
            latitude: lat,
            longitude: lon,
            start_time: date("startDate"),
            estimated_end: date("endDate"),
            lanes_affected: lanes,
            road_name: str_or_empty(row.get("roadwayName")),
            location_text,
            ..TrafficEvent::default()
        });
    }
    events
}

/// Extract `id -> (lat, lon)` from a `/map/mapIcons` response.
///
/// Shape (fetched 2026-08-20): `{"item1": {...icon style...},
/// "item2": [{"itemId": "815973", "location": [lat, lon], ...}, ...]}`.
pub fn parse_list511_icon_locations(data: &Value) -> PinLocations {
    let mut locations = PinLocations::new();
    let Some(data) = data.as_object() else {
        return locations;
    };
    let Some(pins) = data.get("item2").and_then(Value::as_array) else {
        return locations;
    };
    for pin in pins {
        let Some(pin) = pin.as_object() else {
            continue;
        };
        let item_id = str_or_empty(pin.get("itemId"));
        let Some(loc) = pin.get("location").and_then(Value::as_array) else {
            continue;
        };
        if item_id.is_empty() || loc.len() < 2 {
            continue;
        }
        if let (Some(lat), Some(lon)) = (to_f64(&loc[0]), to_f64(&loc[1])) {
            locations.insert(item_id, (lat, lon));
        }
    }
    locations
}

static TAGS: Lazy<Regex> = Lazy::new(|| Regex::new(r"<[^>]+>").unwrap());
static SPACES: Lazy<Regex> = Lazy::new(|| Regex::new(r"\s+").unwrap());
static LAST_UPDATED: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"\s*Last updated at [^.]+\.$").unwrap());
static SOURCE_TAG: Lazy<Regex> = Lazy::new(|| Regex::new(r"\s*\[[^\]\[]*\]$").unwrap());

/// Reduce a list511 description to clean spoken text.
///
/// The sites embed HTML (a `cellSpacer` div duplicating the comment
/// field), trailing source tags like `[CARS CAD-262320295]`, and a
/// site-clock "Last updated at ..." sentence that would clash with the
/// game clock when read aloud.
pub fn clean_list511_text(text: &str) -> String {
    // re.sub(r"<div class='cellSpacer'>.*", "", text, flags=re.DOTALL)
    let text = match text.find("<div class='cellSpacer'>") {
        Some(index) => &text[..index],
        None => text,
    };
    let text = TAGS.replace_all(text, " ");
    let text = html_unescape(&text);
    let text = SPACES.replace_all(&text, " ").trim().to_string();
    let text = LAST_UPDATED.replace(&text, "").to_string();
    let text = SOURCE_TAG.replace(&text, "").to_string();
    text.trim().to_string()
}

/// `html.unescape` for the entities a 511 description can carry: the
/// XML five, the HTML typographic set the sites use, and numeric
/// references. (Python's table covers all of HTML5; these feeds only use
/// this subset.)
pub fn html_unescape(text: &str) -> String {
    const NAMED: &[(&str, &str)] = &[
        ("amp", "&"),
        ("lt", "<"),
        ("gt", ">"),
        ("quot", "\""),
        ("apos", "'"),
        ("nbsp", "\u{a0}"),
        ("ndash", "\u{2013}"),
        ("mdash", "\u{2014}"),
        ("hellip", "\u{2026}"),
        ("lsquo", "\u{2018}"),
        ("rsquo", "\u{2019}"),
        ("ldquo", "\u{201c}"),
        ("rdquo", "\u{201d}"),
        ("deg", "\u{b0}"),
        ("copy", "\u{a9}"),
        ("reg", "\u{ae}"),
        ("trade", "\u{2122}"),
        ("frac12", "\u{bd}"),
        ("frac14", "\u{bc}"),
        ("bull", "\u{2022}"),
        ("middot", "\u{b7}"),
    ];
    if !text.contains('&') {
        return text.to_string();
    }
    let mut out = String::with_capacity(text.len());
    let mut rest = text;
    while let Some(amp) = rest.find('&') {
        out.push_str(&rest[..amp]);
        let after = &rest[amp + 1..];
        // The entity body runs to the next ';' (at most 32 chars, like the
        // Python tokenizer's bound).
        let semi = after.find(';').filter(|i| *i <= 32);
        let mut replaced = None;
        if let Some(end) = semi {
            let body = &after[..end];
            if let Some(stripped) = body.strip_prefix('#') {
                let code = if let Some(hex) = stripped
                    .strip_prefix('x')
                    .or_else(|| stripped.strip_prefix('X'))
                {
                    u32::from_str_radix(hex, 16).ok()
                } else {
                    stripped.parse::<u32>().ok()
                };
                if let Some(ch) = code.and_then(char::from_u32) {
                    replaced = Some((ch.to_string(), end + 1));
                }
            } else if let Some((_, value)) = NAMED.iter().find(|(name, _)| *name == body) {
                replaced = Some((value.to_string(), end + 1));
            }
        }
        match replaced {
            Some((value, consumed)) => {
                out.push_str(&value);
                rest = &after[consumed..];
            }
            None => {
                out.push('&');
                rest = after;
            }
        }
    }
    out.push_str(rest);
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    // Fixtures are real list rows and map pins recorded 2026-08-20 from
    // POST https://fl511.com/List/GetData/Incidents,
    // POST https://511ny.org/List/GetData/Incidents, and the matching
    // GET /map/mapIcons/Incidents endpoints, trimmed to what the parser
    // reads.

    fn fl_crash() -> Value {
        json!({
            "DT_RowId": "815973",
            "id": 815973,
            "roadwayName": "SR-70",
            "description": "Multi-vehicle crash in Manatee County on SR-70 East, before Lorraine Rd. Left turn lane blocked. Last updated at 03:54 PM.",
            "severity": "Intermediate",
            "isFullClosure": false,
            "direction": "Eastbound",
            "laneDescription": "Left turn lane blocked",
            "locationDescription": null,
            "county": "Manatee",
            "startDate": "8/20/26, 3:15 PM",
            "endDate": null,
        })
    }

    fn ny_truck_restriction() -> Value {
        json!({
            "DT_RowId": "4496799",
            "id": 4496799,
            "roadwayName": "George Washington Bridge Upper Level",
            "description": "Truck restrictions on George Washington Bridge Upper Level westbound ramp from West 179th Street (New York) All lanes open until further notice. Trucks wider than 10 ft or longer than 110 ft are prohibited.<div class='cellSpacer'><i><b>Comments:</b></i> Until further notice. trucks wider than 10 ft or longer than 110 ft are prohibited.</div>",
            "severity": "Minor",
            "isFullClosure": false,
            "laneDescription": "All lanes open",
            "locationDescription": "West 179th Street|",
            "county": "New York",
            "startDate": "5/19/25, 6:27 AM",
            "endDate": null,
        })
    }

    fn ny_crash() -> Value {
        json!({
            "DT_RowId": "4674401",
            "id": 4674401,
            "roadwayName": "I-90 - NYS Thruway",
            "description": "Crash on I-90 - NYS Thruway eastbound at After Exit 41 (I-90) - Waterloo (Rte 414) starting 4:23 PM, 08/20/2026 [CARS CAD-262320295]",
            "severity": null,
            "isFullClosure": false,
            "laneDescription": null,
            "locationDescription": "After Exit 41 (I-90) - Waterloo (Rte 414)|",
            "county": "Seneca",
            "startDate": "8/20/26, 4:23 PM",
            "endDate": null,
        })
    }

    fn ny_road_closed() -> Value {
        json!({
            "DT_RowId": "4498570",
            "id": 4498570,
            "roadwayName": "NY 218",
            "description": "DOT Debris and Emergency maintenance and Road Closure on NY 218 both directions between Mountain House Lane (Cornwall) and Grant Road (Highlands) all lanes of 2 lanes closed until further notice<div class='cellSpacer'><i><b>Comments:</b></i> Until further notice</div>",
            "severity": "Major",
            "isFullClosure": true,
            "laneDescription": "all lanes closed",
            "locationDescription": "Mountain House Lane|Grant Road",
            "county": "Orange",
            "startDate": "5/20/26, 5:25 PM",
            "endDate": null,
        })
    }

    fn fl_icons() -> Value {
        json!({
            "item1": {"url": "/Generated/Content/Images/511/map_exclamationMarkOrangeBlue.svg"},
            "item2": [
                {"itemId": "815973", "location": [27.431793, -82.396087], "icon": {}, "title": ""},
            ],
        })
    }

    fn ny_icons() -> Value {
        json!({
            "item1": {"url": "/Generated/Content/Images/511/map_exclamationMarkOrangeBlue.svg"},
            "item2": [
                {"itemId": "4496799", "location": [40.84938, -73.939624], "icon": {}, "title": ""},
                {"itemId": "4674401", "location": [42.921147, -76.936964], "icon": {}, "title": ""},
            ],
        })
    }

    #[test]
    fn test_parse_florida_crash() {
        let locations = parse_list511_icon_locations(&fl_icons());
        let events = parse_list511_events(&[fl_crash()], &locations, "florida");
        assert_eq!(events.len(), 1);
        let event = &events[0];
        assert_eq!(event.id, "815973");
        assert_eq!(event.event_type, "incident");
        assert_eq!(event.severity, "medium");
        assert_eq!(event.road_name, "SR-70");
        assert_eq!(event.county, "Manatee");
        assert_eq!(event.latitude, Some(27.431793));
        assert_eq!(event.longitude, Some(-82.396087));
        assert_eq!(
            event.lanes_affected.as_deref(),
            Some("Left turn lane blocked")
        );
        // The site-clock sentence is stripped from the spoken text
        assert!(!event.description.contains("Last updated"));
        assert!(event.description.ends_with("Left turn lane blocked."));
        assert_eq!(event.start_time.as_deref(), Some("8/20/26, 3:15 PM"));
        assert_eq!(event.estimated_end, None);
    }

    #[test]
    fn test_parse_ny_html_stripped() {
        let locations = parse_list511_icon_locations(&ny_icons());
        let events = parse_list511_events(&[ny_truck_restriction()], &locations, "new york");
        let event = &events[0];
        assert!(!event.description.contains('<'));
        assert!(!event.description.contains("Comments"));
        assert!(event
            .description
            .starts_with("Truck restrictions on George Washington Bridge"));
        assert_eq!(event.severity, "low"); // Minor
                                           // Trailing "|" separator dropped from the location text
        assert_eq!(event.location_text, "West 179th Street");
        assert_eq!(event.latitude, Some(40.84938));
    }

    #[test]
    fn test_parse_ny_cad_suffix_and_null_severity() {
        let events = parse_list511_events(&[ny_crash()], &PinLocations::new(), "new york");
        let event = &events[0];
        assert!(!event.description.contains("[CARS"));
        assert!(event.description.ends_with("starting 4:23 PM, 08/20/2026"));
        assert_eq!(event.severity, "low");
        assert_eq!(event.lanes_affected, None);
    }

    #[test]
    fn test_full_closure_outranks_row_severity() {
        let events = parse_list511_events(&[ny_road_closed()], &PinLocations::new(), "new york");
        let event = &events[0];
        assert_eq!(event.severity, "high");
        assert_eq!(event.location_text, "Mountain House Lane, Grant Road");
    }

    #[test]
    fn test_missing_pin_keeps_event_without_coordinates() {
        let events = parse_list511_events(&[fl_crash()], &PinLocations::new(), "florida");
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].latitude, None);
        assert_eq!(events[0].longitude, None);
    }

    #[test]
    fn test_icon_locations_malformed() {
        assert!(parse_list511_icon_locations(&Value::Null).is_empty());
        assert!(parse_list511_icon_locations(&json!([])).is_empty());
        assert!(parse_list511_icon_locations(&json!({"item2": "nope"})).is_empty());
        assert!(parse_list511_icon_locations(
            &json!({"item2": [{"itemId": "1", "location": [null, null]}, "junk", {}]})
        )
        .is_empty());
    }

    #[test]
    fn test_empty_and_malformed_rows() {
        assert!(parse_list511_events(&[], &PinLocations::new(), "florida").is_empty());
        let rows = vec![
            json!({}),
            json!("junk"),
            json!({"id": null, "description": "x"}),
            json!({"id": 5, "description": ""}),
        ];
        assert!(parse_list511_events(&rows, &PinLocations::new(), "florida").is_empty());
    }

    #[test]
    fn html_unescape_covers_the_feed_entities() {
        assert_eq!(html_unescape("Tom &amp; Jerry &lt;3"), "Tom & Jerry <3");
        assert_eq!(html_unescape("a&#39;b &#x2014; c"), "a'b \u{2014} c");
        assert_eq!(html_unescape("plain & simple"), "plain & simple");
        assert_eq!(html_unescape("&unknown; stays"), "&unknown; stays");
    }
}
