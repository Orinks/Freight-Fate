//! The background watch on the drivers list: what it says when somebody
//! sets off or signs off, and what it keeps quiet about.

use std::sync::Arc;

use serde_json::{json, Value};

use freight_fate::duty_watch::{duty_change_text, DutyWatch, DutyWatchOptions, POLL_INTERVAL_S};
use freight_fate::net::testing::{FakeTransport, ManualClock};
use freight_fate::net::{NetError, SharedTransport};
use freight_fate::online_presence::OnlineIdentity;

fn driver(name: &str) -> Value {
    json!({
        "driverId": format!("{}-1234", name.to_lowercase().replace(' ', "-")),
        "displayName": name,
        "activity": "Driving",
        "detail": "",
        "updatedAt": 1_800_000_000_000.0_f64,
    })
}

fn board(drivers: &[Value]) -> Value {
    json!({"drivers": drivers})
}

/// A synchronous watch wired to a fake transport and a manual clock.
fn watch(transport: &Arc<FakeTransport>, clock: &Arc<ManualClock>, enabled: bool) -> DutyWatch {
    let shared: SharedTransport = transport.clone();
    DutyWatch::new(DutyWatchOptions {
        enabled,
        clock: clock.clock(),
        transport: shared,
        threaded: false,
        ..DutyWatchOptions::default()
    })
}

/// Move the clock past the poll interval and read again.
fn next_read(watch: &DutyWatch, clock: &ManualClock) {
    clock.advance(POLL_INTERVAL_S);
    watch.pump();
}

#[test]
fn test_off_by_default_never_reads_the_list() {
    let transport = FakeTransport::replying(board(&[driver("Road Star")]));
    let clock = ManualClock::new();
    let w = watch(&transport, &clock, false);
    w.start();
    next_read(&w, &clock);
    assert_eq!(transport.request_count(), 0);
    assert!(w.take_announcements().is_empty());
}

#[test]
fn test_the_first_read_seeds_quietly_then_arrivals_and_departures_speak() {
    let transport = FakeTransport::replying(board(&[driver("Road Star")]));
    let clock = ManualClock::new();
    let w = watch(&transport, &clock, true);
    w.start();
    // Road Star was already out when the watch began: not news.
    assert_eq!(transport.request_count(), 1);
    assert!(w.take_announcements().is_empty());

    transport.set_reply(Some(board(&[driver("Road Star"), driver("Night Owl")])));
    next_read(&w, &clock);
    assert_eq!(w.take_announcements(), vec!["Night Owl is on duty."]);

    transport.set_reply(Some(board(&[driver("Night Owl")])));
    next_read(&w, &clock);
    assert_eq!(w.take_announcements(), vec!["Road Star went off duty."]);

    // Nothing moved: nothing said.
    next_read(&w, &clock);
    assert!(w.take_announcements().is_empty());
}

#[test]
fn test_several_changes_in_one_read_are_one_line() {
    let transport = FakeTransport::replying(board(&[driver("Road Star"), driver("Big Rig Bill")]));
    let clock = ManualClock::new();
    let w = watch(&transport, &clock, true);
    w.start();
    w.take_announcements();

    transport.set_reply(Some(board(&[
        driver("Night Owl"),
        driver("Road Star"),
        driver("Dusty Miles"),
    ])));
    next_read(&w, &clock);
    assert_eq!(
        w.take_announcements(),
        vec!["Dusty Miles and Night Owl are on duty. Big Rig Bill went off duty."]
    );
}

#[test]
fn test_the_watch_reads_on_the_site_cache_clock_and_no_faster() {
    let transport = FakeTransport::replying(board(&[]));
    let clock = ManualClock::new();
    let w = watch(&transport, &clock, true);
    w.start();
    assert_eq!(transport.request_count(), 1);
    clock.advance(POLL_INTERVAL_S / 2.0);
    w.pump();
    w.pump();
    assert_eq!(
        transport.request_count(),
        1,
        "asked again inside the minute"
    );
    clock.advance(POLL_INTERVAL_S / 2.0);
    w.pump();
    assert_eq!(transport.request_count(), 2);
}

#[test]
fn test_the_player_is_never_told_about_themselves() {
    let transport = FakeTransport::replying(board(&[]));
    let clock = ManualClock::new();
    let w = watch(&transport, &clock, true);
    w.set_identity(Some(&OnlineIdentity::new("road-star-1234", "t")));
    w.start();

    transport.set_reply(Some(board(&[driver("Road Star"), driver("Night Owl")])));
    next_read(&w, &clock);
    assert_eq!(w.take_announcements(), vec!["Night Owl is on duty."]);

    transport.set_reply(Some(board(&[driver("Night Owl")])));
    next_read(&w, &clock);
    assert!(w.take_announcements().is_empty());
}

#[test]
fn test_an_unreachable_site_says_nothing_and_catches_up_when_it_answers() {
    let transport = FakeTransport::replying(board(&[driver("Road Star")]));
    let clock = ManualClock::new();
    let w = watch(&transport, &clock, true);
    w.start();
    w.take_announcements();

    transport.set_reply(None);
    transport.set_error(Some(NetError::other("OSError", "")));
    next_read(&w, &clock);
    // A failed read is not "everyone went off duty".
    assert!(w.take_announcements().is_empty());

    transport.set_error(None);
    transport.set_reply(Some(board(&[driver("Night Owl")])));
    next_read(&w, &clock);
    assert_eq!(
        w.take_announcements(),
        vec!["Night Owl is on duty. Road Star went off duty."]
    );
}

#[test]
fn test_turning_the_watch_off_and_on_seeds_afresh() {
    let transport = FakeTransport::replying(board(&[driver("Road Star")]));
    let clock = ManualClock::new();
    let w = watch(&transport, &clock, true);
    w.start();
    w.take_announcements();

    w.set_enabled(false);
    transport.set_reply(Some(board(&[driver("Night Owl")])));
    next_read(&w, &clock);
    assert!(w.take_announcements().is_empty());
    assert_eq!(transport.request_count(), 1, "read while off");

    // Back on: whoever is out now is the starting point, not a change.
    w.set_enabled(true);
    assert!(w.take_announcements().is_empty());
    transport.set_reply(Some(board(&[driver("Night Owl"), driver("Dusty Miles")])));
    next_read(&w, &clock);
    assert_eq!(w.take_announcements(), vec!["Dusty Miles is on duty."]);
}

#[test]
fn test_a_driver_without_a_name_is_still_announced() {
    let transport = FakeTransport::replying(board(&[]));
    let clock = ManualClock::new();
    let w = watch(&transport, &clock, true);
    w.start();
    transport.set_reply(Some(json!({"drivers": [{"driverId": "x-1"}]})));
    next_read(&w, &clock);
    assert_eq!(w.take_announcements(), vec!["A driver is on duty."]);
}

#[test]
fn test_duty_change_text_reads_as_one_sentence_per_direction() {
    let s = |v: &[&str]| v.iter().map(|n| n.to_string()).collect::<Vec<_>>();
    assert_eq!(duty_change_text(&[], &[]), None);
    assert_eq!(
        duty_change_text(&s(&["Road Star"]), &[]).unwrap(),
        "Road Star is on duty."
    );
    assert_eq!(
        duty_change_text(&s(&["Road Star", "Night Owl", "Dusty Miles"]), &[]).unwrap(),
        "Road Star, Night Owl and Dusty Miles are on duty."
    );
    assert_eq!(
        duty_change_text(&[], &s(&["Road Star", "Night Owl"])).unwrap(),
        "Road Star and Night Owl went off duty."
    );
}
