//! Caltrans Lane Closure System (LCS) CSV parser.
//!
//! One row per closure, columns named by the header row (the layout all
//! twelve district feeds shared on 2026-09-24; the JSON twin nests the same
//! fields). A row becomes a construction event only when it describes the
//! road a truck drives, right now:
//!
//! - `facility` is `Mainline` or `Conventional Hwy`. Ramps, connectors, rest
//!   areas and HOV-only closures are dropped: snapped onto the route they
//!   would coned off the road itself.
//! - The closure window holds `now` (or its end is open), and Caltrans has
//!   neither picked it up (`isCode1098`) nor cancelled it (`isCode1022`).
//! - The row names its route. A closure with no route could be on any road
//!   within the search radius, and the route filter lets an unnamed road
//!   through.
//! - It is not a stale incident: see [`INCIDENT_STALE_AFTER_S`].
//! - `Traffic Break` rows (a patrol car holding traffic for minutes) are
//!   dropped; they are over before a zone could be placed.

use std::collections::HashMap;

use super::{construction_severity, TrafficEvent};

/// Incident closures (`Accident Investigation`, `Spill-Accident Clean up`)
/// still open after this long are records nobody closed out, not closures.
/// Calibrated against the twelve feeds of 2026-09-24: the genuine incident
/// closures had run 6 and 17 hours, the stale ones 108 to 1,517 days (a full
/// closure of southbound I-5 through Los Angeles "under investigation" since
/// June among them). A week sits well inside that gap and still believes a
/// multi-day incident.
pub const INCIDENT_STALE_AFTER_S: f64 = 7.0 * 24.0 * 3600.0;

const INCIDENT_WORK: &[&str] = &["Accident Investigation", "Spill-Accident Clean up"];

/// Split a CSV document into rows of fields (RFC 4180: quoted fields may
/// hold commas, doubled quotes and line breaks).
fn csv_rows(text: &str) -> Vec<Vec<String>> {
    let mut rows = Vec::new();
    let mut row = Vec::new();
    let mut field = String::new();
    let mut quoted = false;
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        if quoted {
            if c != '"' {
                field.push(c);
            } else if chars.peek() == Some(&'"') {
                field.push('"');
                chars.next();
            } else {
                quoted = false;
            }
            continue;
        }
        match c {
            '"' => quoted = true,
            ',' => row.push(std::mem::take(&mut field)),
            '\r' => {}
            '\n' => {
                row.push(std::mem::take(&mut field));
                rows.push(std::mem::take(&mut row));
            }
            _ => field.push(c),
        }
    }
    if !field.is_empty() || !row.is_empty() {
        row.push(field);
        rows.push(row);
    }
    rows
}

/// The route as the world names it: Caltrans writes state routes `SR-14`,
/// the map `CA-14`.
fn world_route(route: &str) -> String {
    match route.strip_prefix("SR-") {
        Some(number) => format!("CA-{number}"),
        None => route.to_string(),
    }
}

/// The closure kind the zone builder understands, or None to drop the row.
fn closure_kind(type_of_closure: &str, lanes_closed: &str) -> Option<&'static str> {
    let travel_lane_closed = lanes_closed
        .split(',')
        .any(|lane| lane.trim().parse::<u32>().is_ok() || lane.trim() == "All");
    match type_of_closure {
        "Traffic Break" => None,
        "Full" => Some("full closure"),
        "One-Way Traffic" => Some("alternating"),
        _ if !travel_lane_closed => Some("shoulder"),
        _ => Some("single lane"),
    }
}

/// `2 of 4 lanes closed`, `all lanes closed` or `shoulder closed`.
fn lanes_text(closure: &str, lanes_closed: &str, total: &str) -> String {
    if closure == "full closure" || lanes_closed.trim() == "All" {
        return "all lanes closed".into();
    }
    if closure == "shoulder" {
        return "shoulder closed".into();
    }
    let closed = lanes_closed
        .split(',')
        .filter(|lane| lane.trim().parse::<u32>().is_ok())
        .count();
    match total.trim().parse::<u32>() {
        Ok(total) if total > 0 => format!("{closed} of {total} lanes closed"),
        _ => format!("{closed} lanes closed"),
    }
}

/// Parse a district's LCS CSV into the construction events in effect at
/// `now_epoch` (seconds since the Unix epoch, the feed's own clock).
pub fn parse_lcs_csv(body: &[u8], now_epoch: f64) -> Vec<TrafficEvent> {
    let text = String::from_utf8_lossy(body);
    let mut rows = csv_rows(&text).into_iter();
    let Some(header) = rows.next() else {
        return Vec::new();
    };
    let columns: HashMap<&str, usize> = header
        .iter()
        .enumerate()
        .map(|(i, name)| (name.trim(), i))
        .collect();
    let mut events = Vec::new();
    for row in rows {
        let get = |name: &str| -> &str {
            columns
                .get(name)
                .and_then(|&i| row.get(i))
                .map(|v| v.trim())
                .unwrap_or("")
        };
        let flag = |name: &str| get(name) == "true";
        let epoch = |name: &str| get(name).parse::<f64>().ok();

        let id = get("index");
        let route = get("beginRoute");
        if id.is_empty() || route.is_empty() {
            continue;
        }
        if !matches!(get("facility"), "Mainline" | "Conventional Hwy") {
            continue;
        }
        if flag("isCode1098") || flag("isCode1022") {
            continue;
        }
        let Some(start) = epoch("closureStartEpoch") else {
            continue;
        };
        let open_ended = flag("isClosureEndIndefinite");
        let in_effect = start <= now_epoch
            && (open_ended || epoch("closureEndEpoch").is_some_and(|end| now_epoch <= end));
        if !in_effect {
            continue;
        }
        let work = get("typeOfWork");
        if INCIDENT_WORK.contains(&work) && now_epoch - start > INCIDENT_STALE_AFTER_S {
            continue;
        }
        let lanes_closed = get("lanesClosed");
        let Some(closure) = closure_kind(get("typeOfClosure"), lanes_closed) else {
            continue;
        };

        let point = |lat: &str, lon: &str| -> Option<(f64, f64)> {
            Some((get(lat).parse().ok()?, get(lon).parse().ok()?))
        };
        let (latitude, longitude) = match (
            point("beginLatitude", "beginLongitude"),
            point("endLatitude", "endLongitude"),
        ) {
            (Some(a), Some(b)) => (Some((a.0 + b.0) / 2.0), Some((a.1 + b.1) / 2.0)),
            (Some(p), None) | (None, Some(p)) => (Some(p.0), Some(p.1)),
            (None, None) => (None, None),
        };

        // Postmiles restart at each county line and carry a realignment
        // prefix, so they measure the closure only within one county and
        // one alignment.
        let from = get("beginLocationName");
        let to = get("endLocationName");
        let same_postmile_run = get("beginCounty") == get("endCounty")
            && get("beginPostmilePrefix") == get("endPostmilePrefix");
        let location_text = match (
            get("beginPostmile").parse::<f64>(),
            get("endPostmile").parse::<f64>(),
        ) {
            (Ok(b), Ok(e)) if same_postmile_run => format!("Between milepost {b} and {e}"),
            _ => format!("Between {from} and {to}"),
        };
        let stamp = |date: &str, time: &str| format!("{} {}", get(date), get(time));

        events.push(TrafficEvent {
            id: id.to_string(),
            event_type: "construction".into(),
            severity: construction_severity(closure).into(),
            description: format!("{work}, {from} to {to}"),
            county: get("beginCounty").to_string(),
            latitude,
            longitude,
            start_time: Some(stamp("closureStartDate", "closureStartTime")),
            estimated_end: Some(if open_ended {
                String::new()
            } else {
                stamp("closureEndDate", "closureEndTime")
            }),
            lanes_affected: Some(lanes_text(closure, lanes_closed, get("totalExistingLanes"))),
            road_name: world_route(route),
            location_text,
            work_type: "construction".into(),
            closure: closure.into(),
        });
    }
    events
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Real rows from the twelve district feeds of 2026-09-24, one per
    /// case the parser decides; the header is the feeds' own.
    const FIXTURE: &str = include_str!("fixtures/lcs_sample.csv");
    /// The feeds' `recordEpoch` that morning (2026-09-24 18:03 UTC).
    const NOW: f64 = 1_790_272_983.0;

    fn by_id(events: &[TrafficEvent], prefix: &str) -> Option<TrafficEvent> {
        events.iter().find(|e| e.id.starts_with(prefix)).cloned()
    }

    #[test]
    fn keeps_closures_on_the_road_in_effect_now() {
        let events = parse_lcs_csv(FIXTURE.as_bytes(), NOW);
        let ids: Vec<&str> = events.iter().map(|e| e.id.as_str()).collect();
        assert_eq!(
            ids,
            vec![
                "C5DA-0077-2026-09-24-06:01:00",
                "C1PB-0004-2026-09-24-07:01:00",
                "C80XA-0033-2026-09-24-05:01:00",
                "C1FA-0004-2026-09-24-08:01:00",
                "C101JD-0004-2026-09-24-05:01:00",
                "T36HA-0001-2025-07-03-18:01:00",
                "T39BA-0001-2012-11-14-05:01:00",
            ],
            "{events:#?}"
        );
    }

    #[test]
    fn a_mainline_lane_closure_reads_as_the_world_names_it() {
        let events = parse_lcs_csv(FIXTURE.as_bytes(), NOW);
        let i5 = by_id(&events, "C5DA-0077").unwrap();
        assert_eq!(i5.road_name, "I-5");
        assert_eq!(i5.closure, "single lane");
        assert_eq!(i5.severity, "medium");
        assert_eq!(i5.lanes_affected.as_deref(), Some("1 of 4 lanes closed"));
        assert_eq!(i5.location_text, "Between milepost 56.6 and 59.01");
        assert_eq!(i5.county, "Los Angeles");
        assert!(i5.latitude.is_some() && i5.longitude.is_some());

        // State routes are CA-, not SR-; shoulders do not count as lanes.
        let sr1 = by_id(&events, "C1PB-0004").unwrap();
        assert_eq!(sr1.road_name, "CA-1");
        assert_eq!(sr1.lanes_affected.as_deref(), Some("2 of 4 lanes closed"));
        // A shoulder-only closure is shoulder work; one-way traffic is
        // alternating; a moving closure takes a lane.
        assert_eq!(by_id(&events, "C101JD-0004").unwrap().closure, "shoulder");
        assert_eq!(by_id(&events, "C1FA-0004").unwrap().closure, "alternating");
        assert_eq!(by_id(&events, "C80XA-0033").unwrap().closure, "single lane");
        // An open-ended closure has no end time; a permanent road closure is
        // a full closure.
        let open = by_id(&events, "T36HA-0001").unwrap();
        assert_eq!(open.estimated_end.as_deref(), Some(""));
        let closed_for_good = by_id(&events, "T39BA-0001").unwrap();
        assert_eq!(closed_for_good.closure, "full closure");
        assert_eq!(closed_for_good.severity, "high");
    }

    #[test]
    fn drops_what_is_not_the_road_or_not_now() {
        let events = parse_lcs_csv(FIXTURE.as_bytes(), NOW);
        for (id, why) in [
            ("C80OA-0035", "an on-ramp"),
            ("C101AD-0002", "starts tonight"),
            ("C101AD-0001", "ended last night"),
            ("C80MA-0004", "cancelled"),
            ("C1LC-0007", "picked up"),
            ("P39AA-0004", "a traffic break"),
            ("T5SA-0001", "an accident open since June"),
            ("T232BA-0001", "names no route"),
        ] {
            assert!(by_id(&events, id).is_none(), "{id} kept though {why}");
        }
        // The same stale incident, read the week it was filed, is believed.
        let june = 1_780_901_100.0 + 3600.0;
        assert!(by_id(&parse_lcs_csv(FIXTURE.as_bytes(), june), "T5SA-0001").is_some());
    }

    #[test]
    fn csv_quoting_and_empty_bodies() {
        let rows = csv_rows("a,\"b, c\",\"say \"\"hi\"\"\"\r\n1,2,3");
        assert_eq!(
            rows,
            vec![vec!["a", "b, c", "say \"hi\""], vec!["1", "2", "3"]]
        );
        assert!(parse_lcs_csv(b"", NOW).is_empty());
        assert!(parse_lcs_csv(b"index,beginRoute\n", NOW).is_empty());
    }
}
