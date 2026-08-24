//! Invariants for the baked lane-count data layer (`corridor.lane_segments`)
//! and the per-leg `divided` flag (ports of `tests/test_lane_data.py` and
//! `tests/test_divided_data.py`).
//!
//! These guard the raw shard data directly rather than through the world
//! model, as the Python tests did.


use std::collections::HashSet;

use crate::data_support::data_dir;
use serde_json::Value;

const LANES_MIN: i64 = 1;
const LANES_MAX: i64 = 10;
const ALLOWED_KEYS: &[&str] = &[
    "start_mi",
    "end_mi",
    "lanes",
    "lanes_forward",
    "lanes_backward",
    "oneway",
    "source",
];

/// Every leg from every shard, in sorted shard order.
fn legs() -> Vec<Value> {
    let dir = data_dir().join("world_data").join("us").join("legs");
    let mut shards: Vec<_> = std::fs::read_dir(&dir)
        .unwrap()
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x == "json"))
        .collect();
    shards.sort();
    let mut out = Vec::new();
    for shard in shards {
        let text = std::fs::read_to_string(&shard).unwrap();
        let data: Value = serde_json::from_str(&text).unwrap();
        out.extend(data["legs"].as_array().unwrap().iter().cloned());
    }
    out
}

/// (leg_id, segments) for every leg that carries lane_segments.
fn legs_with_lanes() -> Vec<(String, Vec<Value>)> {
    legs()
        .into_iter()
        .filter_map(|leg| {
            let segs = leg
                .get("corridor")?
                .get("lane_segments")?
                .as_array()?
                .clone();
            if segs.is_empty() {
                return None;
            }
            Some((
                format!("{}:{}", leg["from"].as_str()?, leg["to"].as_str()?),
                segs,
            ))
        })
        .collect()
}

// -- test_lane_data.py -------------------------------------------------------

#[test]
fn test_some_legs_have_lane_data() {
    // The bake actually ran: a healthy fraction of legs carry lane data.
    let lane_legs = legs_with_lanes();
    assert!(
        lane_legs.len() >= 200,
        "only {} legs have lane_segments",
        lane_legs.len()
    );
}

#[test]
fn test_lane_segments_are_well_formed() {
    for (leg_id, segs) in legs_with_lanes() {
        assert!(!segs.is_empty(), "{leg_id}");
        let mut prev_end = -1.0;
        for s in &segs {
            let keys: HashSet<&str> = s.as_object().unwrap().keys().map(String::as_str).collect();
            let unexpected: Vec<&&str> =
                keys.iter().filter(|k| !ALLOWED_KEYS.contains(k)).collect();
            assert!(
                unexpected.is_empty(),
                "{leg_id}: unexpected keys {unexpected:?}"
            );
            let start = s["start_mi"].as_f64().unwrap();
            let end = s["end_mi"].as_f64().unwrap();
            assert!(
                0.0 <= start && start < end,
                "{leg_id}: bad span {start}->{end}"
            );
            // sorted and non-overlapping along the leg
            assert!(
                start >= prev_end - 0.05,
                "{leg_id}: segment overlap at {start} (prev end {prev_end})"
            );
            prev_end = end;
            let lanes = s["lanes"]
                .as_i64()
                .unwrap_or_else(|| panic!("{leg_id}: lanes not int"));
            assert!(
                (LANES_MIN..=LANES_MAX).contains(&lanes),
                "{leg_id}: lanes={lanes}"
            );
            for k in ["lanes_forward", "lanes_backward"] {
                if let Some(v) = s.get(k) {
                    let v = v
                        .as_i64()
                        .unwrap_or_else(|| panic!("{leg_id}: {k} not int"));
                    assert!((LANES_MIN..=LANES_MAX).contains(&v), "{leg_id}: {k}={v}");
                }
            }
            if let Some(oneway) = s.get("oneway") {
                assert_eq!(oneway, &Value::Bool(true), "{leg_id}: oneway={oneway:?}");
            }
        }
    }
}

#[test]
fn test_lane_sources_are_curated_not_raw_osm() {
    // Source notes credit OSM but never leak a raw tag into stored text.
    for (leg_id, segs) in legs_with_lanes() {
        for s in &segs {
            let src = s.get("source").and_then(Value::as_str).unwrap_or("");
            assert!(
                !src.is_empty() && src.contains("OpenStreetMap"),
                "{leg_id}: source missing/uncredited"
            );
            // a raw tag dump (lanes=3, highway=motorway) must never be the source
            assert!(
                !src.contains("lanes=") && !src.contains("highway="),
                "{leg_id}: raw tag in source"
            );
        }
    }
}

#[test]
fn test_acceptance_anchor_lane_counts() {
    // Acceptance spot checks from the brief: metro widens, rural stays 2.
    let by_id: std::collections::HashMap<String, Vec<Value>> =
        legs_with_lanes().into_iter().collect();
    type Predicate = fn(&[Value]) -> bool;
    let cases: [(&str, Predicate, &str); 2] = [
        (
            "albuquerque_nm_us:gallup_nm_us",
            |segs| segs.iter().any(|s| s["lanes"].as_i64().unwrap() >= 3),
            "I-40 through Albuquerque should widen to 3+ lanes",
        ),
        (
            "winslow_az_us:holbrook_az_us",
            |segs| segs.iter().any(|s| s["lanes"].as_i64().unwrap() == 2),
            "rural I-40 Arizona should be 2 lanes",
        ),
    ];
    for (leg_id, predicate, why) in cases {
        let segs = by_id
            .get(leg_id)
            .unwrap_or_else(|| panic!("{leg_id} has no lane data"));
        assert!(predicate(segs), "{why}");
    }
}

// -- test_divided_data.py ----------------------------------------------------
// Data layer only -- curve navigation (Track B) reads it; nothing does yet, so
// these guard the raw leg data directly. Honest absence: a genuinely mixed or
// too-thinly-matched leg carries NO `divided` key and the runtime's road-class
// inference stays the fallback.

#[test]
fn test_divided_is_bool_where_present() {
    for leg in legs() {
        if let Some(divided) = leg.get("divided") {
            assert!(
                divided.is_boolean(),
                "{}:{} divided not bool",
                leg["from"].as_str().unwrap(),
                leg["to"].as_str().unwrap()
            );
        }
    }
}

#[test]
fn test_a_healthy_share_of_legs_have_the_flag() {
    let legs = legs();
    let flagged = legs
        .iter()
        .filter(|leg| leg.get("divided").is_some())
        .count();
    // A clear majority resolve to true/false; the mixed middle omits.
    assert!(
        flagged as f64 >= 0.7 * legs.len() as f64,
        "only {flagged}/{} legs carry divided",
        legs.len()
    );
}

#[test]
fn test_interstates_that_resolve_are_mostly_divided() {
    // A flagged interstate leg is divided far more often than not (the few
    // undivided ones are legs tagged with an interstate but routed on a parallel
    // surface road -- real, but the class should still trend hard to divided).
    let inter: Vec<Value> = legs()
        .into_iter()
        .filter(|leg| {
            leg.get("highway")
                .and_then(Value::as_str)
                .unwrap_or("")
                .starts_with("I-")
                && leg.get("divided").is_some()
        })
        .collect();
    let divided = inter
        .iter()
        .filter(|leg| leg["divided"].as_bool().unwrap())
        .count();
    assert!(!inter.is_empty(), "no flagged interstate legs found");
    assert!(
        divided as f64 / inter.len() as f64 >= 0.9,
        "only {divided}/{} flagged interstates divided",
        inter.len()
    );
}
