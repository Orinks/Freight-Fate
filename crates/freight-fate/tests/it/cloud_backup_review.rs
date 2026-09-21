//! A career carrying the "changed outside the game" mark is held for the
//! owner's review before it backs up: the game says it is review-aware, stops
//! retrying a held or declined career, speaks the hold once, and clears the
//! mark when the server accepts the career after review.

use std::sync::Arc;

use serde_json::{json, Value};

use ff_core::models::profile::Profile;
use freight_fate::app::testing::TestApp;
use freight_fate::cloud_saves::{
    classify_upload_failure, rejection_status, save_slot_name, upload_save, CloudSaves,
    CloudSavesOptions, DEBOUNCE_S, RETRY_INTERVAL_S,
};
use freight_fate::net::testing::{FakeTransport, ManualClock};
use freight_fate::net::NetError;
use freight_fate::online_presence::OnlineIdentity;

fn identity() -> OnlineIdentity {
    OnlineIdentity::new("driver-testtest", &"t".repeat(48))
}

fn profile(name: &str, money: f64) -> Value {
    json!({"name": name, "money": money, "version": 7, "career": {"xp": 0.0}})
}

fn service(
    transport: &Arc<FakeTransport>,
    clock: &Arc<ManualClock>,
) -> (CloudSaves, tempfile::TempDir) {
    let dir = tempfile::tempdir().unwrap();
    let service = CloudSaves::new(CloudSavesOptions {
        enabled: true,
        identity: Some(identity()),
        clock: clock.clock(),
        transport: transport.clone(),
        threaded: false,
        data_dir: dir.path().to_path_buf(),
        ..CloudSavesOptions::default()
    });
    (service, dir)
}

fn drain(service: &CloudSaves, clock: &Arc<ManualClock>) {
    clock.advance(DEBOUNCE_S + 0.1);
    service.pump(false);
}

fn upload(transport: &FakeTransport) -> serde_json::Map<String, Value> {
    upload_save(
        &identity(),
        "Road Star",
        &profile("Road Star", 5000.0),
        Some(3),
        "Road Star",
        None,
        transport,
    )
}

#[test]
fn upload_says_it_understands_review() {
    let transport = FakeTransport::replying(json!({"ok": true, "revision": 4}));
    upload(&transport);
    assert_eq!(transport.posts()[0]["reviewAware"], true);
}

#[test]
fn upload_carries_the_clear_flag_only_when_the_server_sets_it() {
    let cleared =
        FakeTransport::replying(json!({"ok": true, "revision": 4, "clearIntegrityFlag": true}));
    assert_eq!(upload(&cleared)["clearIntegrityFlag"], true);

    let not =
        FakeTransport::replying(json!({"ok": true, "revision": 4, "clearIntegrityFlag": false}));
    assert!(!upload(&not).contains_key("clearIntegrityFlag"));
}

#[test]
fn held_and_declined_are_refusals_with_their_own_lines() {
    for reason in ["held_for_review", "review_declined"] {
        assert_eq!(classify_upload_failure(Some(reason)), "rejected");
    }
    assert_eq!(
        rejection_status("Road Star", Some("held_for_review")),
        "Road Star: backup waiting for review. This career was changed outside the game or \
copied from another computer, so it is checked by hand before it backs up. Your local \
career is safe."
    );
    assert_eq!(
        rejection_status("Road Star", Some("review_declined")),
        "Road Star: backup declined after review. Your local career is safe. Restoring your \
last cloud backup of it from the Online menu starts it backing up again."
    );
}

#[test]
fn a_held_career_speaks_once_and_is_not_retried() {
    let transport = FakeTransport::failing(NetError::http_json(
        423,
        &json!({"error": "held_for_review"}),
    ));
    let clock = ManualClock::new();
    let (service, _dir) = service(&transport, &clock);

    service.queue_backup("Road Star", profile("Road Star", 5000.0));
    drain(&service, &clock);
    let lines = service.take_announcements();
    assert_eq!(lines.len(), 1);
    assert!(lines[0].starts_with("Road Star: backup waiting for review."));

    // No backoff retry: the snapshot was dropped, not kept for later.
    clock.advance(RETRY_INTERVAL_S * 3.0);
    service.pump(false);
    assert_eq!(transport.request_count(), 1);

    // A second held save in the same session says nothing.
    service.queue_backup("Road Star", profile("Road Star", 5001.0));
    drain(&service, &clock);
    assert_eq!(transport.request_count(), 2);
    assert!(service.take_announcements().is_empty());
}

#[test]
fn an_accepted_review_clears_the_loaded_careers_mark_silently() {
    let mut app = TestApp::new();
    let mut career = Profile::named_in("Road Star", "Chicago");
    career.integrity_modified = true;
    career.integrity_notice_pending = true;
    app.ctx.profile = Some(career);

    let transport =
        FakeTransport::replying(json!({"ok": true, "revision": 1, "clearIntegrityFlag": true}));
    let clock = ManualClock::new();
    let (service, _dir) = service(&transport, &clock);
    app.ctx.services.cloud = service.clone();
    let slot = save_slot_name("Road Star");
    service.queue_backup(&slot, profile("Road Star", 5000.0));
    service.queue_backup("Someone Else", profile("Someone Else", 1.0));
    drain(&service, &clock);
    service.take_announcements(); // the ordinary all-clears
    app.clear_speech();

    app.tick(0.0);

    let loaded = app.ctx.profile.as_ref().unwrap();
    assert!(!loaded.integrity_modified);
    assert!(!loaded.integrity_notice_pending);
    let on_disk = Profile::load(&loaded.path()).unwrap();
    assert!(!on_disk.integrity_modified);
    assert!(app.main_lines().is_empty(), "{:?}", app.main_lines());
    assert!(service.take_absolved().is_empty());
}
