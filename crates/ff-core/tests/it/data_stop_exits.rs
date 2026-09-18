//! The interchange that serves each stop, as the bake decided it
//! (`tools/snap_stops_to_interchanges.py`): an identity carried on the stop,
//! not a mile marker searched near at run time.

use ff_core::data::world::get_world;
use ff_core::data::world_parsing::parse_stop;
use ff_core::sim::trip_route_helpers::{nearest_exit_label, served_interchange, stop_exit_label};

fn bare(exit_ref: &str) -> String {
    exit_ref
        .split_whitespace()
        .collect::<String>()
        .to_uppercase()
}

#[test]
fn test_parse_stop_reads_the_match_and_old_data_has_none() {
    let raw = |extra: serde_json::Value| {
        let mut stop = serde_json::json!({
            "name": "Flying J Travel Center",
            "type": "travel_center",
            "at_mi": 5.6,
            "source": "test",
        });
        let fields = stop.as_object_mut().expect("object");
        fields.extend(extra.as_object().expect("object").clone());
        stop
    };
    let old = parse_stop(&raw(serde_json::json!({})), 60.0, "a", "b").expect("parses");
    assert_eq!((old.exit_ref.as_str(), old.interchange_mi), ("", None));

    let matched = raw(serde_json::json!({"exit_ref": "153", "interchange_mi": 7.0}));
    let matched = parse_stop(&matched, 60.0, "a", "b").expect("parses");
    assert_eq!(matched.exit_ref, "153");
    assert_eq!(matched.interchange_mi, Some(7.0));

    // Number only: the leg records no interchange for that exit.
    let numbered = parse_stop(&raw(serde_json::json!({"exit_ref": "48A"})), 60.0, "a", "b");
    assert_eq!(numbered.expect("parses").interchange_mi, None);

    let off_the_leg = raw(serde_json::json!({"exit_ref": "153", "interchange_mi": 61.0}));
    let err = parse_stop(&off_the_leg, 60.0, "a", "b").unwrap_err();
    assert!(err.to_string().contains("interchange_mi"), "{err}");
}

#[test]
fn test_every_matched_stop_names_a_record_on_its_own_leg() {
    // `parse_stop` cannot check this: the corridor is the lazy half of a leg.
    let world = get_world();
    for leg in &world.legs {
        for stop in &leg.stops {
            let Some(mi) = stop.interchange_mi else {
                continue;
            };
            let served = served_interchange(leg, stop).unwrap_or_else(|| {
                panic!(
                    "{} to {}: {} is matched to mile {mi}, where the leg records no interchange",
                    leg.a, leg.b, stop.name
                )
            });
            assert_eq!(
                bare(&served.exit_ref),
                bare(&stop.exit_ref),
                "{} to {}: {}",
                leg.a,
                leg.b,
                stop.name
            );
        }
    }
}

#[test]
fn test_the_match_reaches_the_ramps_the_mile_marker_missed() {
    // Measured 2026-09-17 on the loaded map, after the twin and plaza
    // screens: 1,308 stops carry an exit number, and for 447 of them the
    // mile marker had named another exit; 828 are matched to a record, 476
    // of those read a ramp control, and the 0.15 mile search reached 59 of
    // the 476. Floors, so a re-bake that loses the fields fails here.
    let world = get_world();
    let (mut matched, mut numbered, mut read, mut read_by_mile_marker, mut renamed) =
        (0usize, 0usize, 0usize, 0usize, 0usize);
    for leg in &world.legs {
        for stop in &leg.stops {
            if !stop.exit_ref.is_empty() {
                numbered += 1;
                let by_mile_marker = nearest_exit_label(leg, stop.at_mi, 2.0);
                if !by_mile_marker.is_empty() && by_mile_marker != stop_exit_label(leg, stop, 2.0) {
                    renamed += 1;
                }
            }
            let Some(served) = served_interchange(leg, stop) else {
                continue;
            };
            matched += 1;
            if served.ramp_control.is_empty() {
                continue;
            }
            read += 1;
            let near = leg
                .interchanges()
                .iter()
                .any(|ix| !ix.ramp_control.is_empty() && (ix.at_mi - stop.at_mi).abs() <= 0.15);
            if near {
                read_by_mile_marker += 1;
            }
        }
    }
    println!(
        "{numbered} stops carry an exit number, {renamed} of them renamed; {matched} matched \
         to a record, {read} of those read a ramp control, {read_by_mile_marker} of which the \
         0.15 mile search also reached"
    );
    assert!(numbered >= 1200, "{numbered} stops carry an exit number");
    assert!(matched >= 800, "{matched} stops matched to a record");
    assert!(read >= 450, "{read} matched stops read a ramp control");
    // The point of the change: the mile marker reached a fraction of these.
    assert!(
        read_by_mile_marker * 4 <= read,
        "{read_by_mile_marker} of {read}"
    );
}

#[test]
fn test_the_flying_j_at_albuquerque_exit_153_reads_its_own_light() {
    // The store is on 98th Street at I-40 exit 153. Its mile marker is 1.4
    // miles from the interchange's, so the 0.15 mile search found nothing
    // and the dice decided how the ramp ended.
    let world = get_world();
    let leg = world
        .legs
        .iter()
        .find(|leg| leg.a == "albuquerque_nm_us" && leg.b == "phoenix_az_us")
        .expect("the Albuquerque to Phoenix leg");
    let stop = leg
        .stops
        .iter()
        .find(|stop| stop.name.starts_with("Flying J Travel Center") && stop.at_mi < 10.0)
        .expect("the Albuquerque Flying J");
    let served = served_interchange(leg, stop).expect("matched to its interchange");
    assert_eq!(served.exit_ref, "153");
    assert_eq!(served.ramp_control, "signal");
    assert!((served.at_mi - stop.at_mi).abs() > 0.15);
    assert_eq!(stop_exit_label(leg, stop, 2.0), "exit 153");
}
