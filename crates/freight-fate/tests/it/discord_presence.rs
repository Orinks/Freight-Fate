//! Port of `tests/test_discord_presence.py`: the optional Discord Rich
//! Presence service.
//!
//! These cover the behaviour that must hold regardless of whether Discord is
//! even installed: pure formatting, the disabled path, a missing/unavailable
//! RPC, de-duplication and throttling of updates, and clean shutdown. A fake
//! RPC client and an injected clock keep every test deterministic and free of
//! real sockets.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use freight_fate::discord_presence::{
    driving_presence, format_activity, ActivityPayload, DiscordPresence, DiscordPresenceOptions,
    PresenceState, RpcClient, RpcFactory, DEFAULT_CLIENT_ID, MAX_FIELD_LEN,
};
use freight_fate::net::testing::ManualClock;

/// A stand-in for the RPC client recording every call.
#[derive(Default)]
struct FakeRpcState {
    connect_error: Option<String>,
    update_error: Option<String>,
    connects: usize,
    updates: Vec<ActivityPayload>,
    cleared: usize,
    closed: usize,
}

#[derive(Clone, Default)]
struct FakeRpc(Arc<Mutex<FakeRpcState>>);

impl FakeRpc {
    fn new() -> Self {
        Self::default()
    }

    fn with_connect_error(msg: &str) -> Self {
        let me = Self::new();
        me.0.lock().unwrap().connect_error = Some(msg.to_string());
        me
    }

    fn with_update_error(msg: &str) -> Self {
        let me = Self::new();
        me.0.lock().unwrap().update_error = Some(msg.to_string());
        me
    }

    fn connects(&self) -> usize {
        self.0.lock().unwrap().connects
    }

    fn updates(&self) -> Vec<ActivityPayload> {
        self.0.lock().unwrap().updates.clone()
    }

    fn cleared(&self) -> usize {
        self.0.lock().unwrap().cleared
    }

    fn closed(&self) -> usize {
        self.0.lock().unwrap().closed
    }

    fn factory(&self) -> RpcFactory {
        let me = self.clone();
        Arc::new(move |_cid: &str| Ok(Box::new(me.clone()) as Box<dyn RpcClient>))
    }
}

impl RpcClient for FakeRpc {
    fn connect(&mut self) -> Result<(), String> {
        let mut st = self.0.lock().unwrap();
        st.connects += 1;
        match &st.connect_error {
            Some(e) => Err(e.clone()),
            None => Ok(()),
        }
    }

    fn update(&mut self, payload: &ActivityPayload) -> Result<(), String> {
        let mut st = self.0.lock().unwrap();
        if let Some(e) = &st.update_error {
            return Err(e.clone());
        }
        st.updates.push(payload.clone());
        Ok(())
    }

    fn clear(&mut self) -> Result<(), String> {
        self.0.lock().unwrap().cleared += 1;
        Ok(())
    }

    fn close(&mut self) -> Result<(), String> {
        self.0.lock().unwrap().closed += 1;
        Ok(())
    }
}

/// A synchronous (non-threaded) service wired to a fake RPC and clock.
fn make_presence(
    rpc: &FakeRpc,
    clock: &Arc<ManualClock>,
    enabled: bool,
    min_interval_s: f64,
) -> DiscordPresence {
    DiscordPresence::new(DiscordPresenceOptions {
        enabled,
        client_id: Some("test-app-id".to_string()),
        min_interval_s,
        clock: clock.clock(),
        rpc_factory: Some(rpc.factory()),
        session_start: Some(1234.0),
        threaded: false,
    })
}

// -- application id -----------------------------------------------------------

#[test]
fn test_default_client_id_is_the_registered_freight_fate_app() {
    assert_eq!(DEFAULT_CLIENT_ID, "1519334426453082162");
    assert!(DEFAULT_CLIENT_ID.chars().all(|c| c.is_ascii_digit()));
}

#[test]
fn test_default_client_id_is_used_when_no_override_is_supplied() {
    std::env::remove_var("FREIGHT_FATE_DISCORD_APP_ID");
    let captured = Arc::new(Mutex::new(Vec::<String>::new()));
    let factory: RpcFactory = {
        let captured = Arc::clone(&captured);
        Arc::new(move |client_id: &str| {
            captured.lock().unwrap().push(client_id.to_string());
            Ok(Box::new(FakeRpc::new()) as Box<dyn RpcClient>)
        })
    };
    let presence = DiscordPresence::new(DiscordPresenceOptions {
        min_interval_s: 0.0,
        rpc_factory: Some(factory),
        threaded: false,
        ..DiscordPresenceOptions::default()
    });
    presence.start();
    presence.update(Some(PresenceState::activity("In the main menu")));
    presence.shutdown();

    assert_eq!(
        *captured.lock().unwrap(),
        vec![DEFAULT_CLIENT_ID.to_string()]
    );
}

// -- formatting ---------------------------------------------------------------

#[test]
fn test_format_activity_maps_fields_and_includes_start() {
    let payload = format_activity(
        &PresenceState::new("Driving a route", "Chicago to Dallas"),
        Some(1234.0),
    );
    assert_eq!(payload.details, "Driving a route");
    assert_eq!(payload.state.as_deref(), Some("Chicago to Dallas"));
    assert_eq!(payload.start, Some(1234));
}

#[test]
fn test_format_activity_omits_empty_state_line() {
    let payload = format_activity(&PresenceState::activity("In the main menu"), None);
    assert_eq!(payload.details, "In the main menu");
    assert!(payload.state.is_none());
    assert!(payload.start.is_none());
}

#[test]
fn test_format_activity_truncates_to_discord_limit() {
    let long_detail = "x".repeat(500);
    let payload = format_activity(&PresenceState::new(&"A".repeat(500), &long_detail), None);
    assert!(payload.details.chars().count() <= MAX_FIELD_LEN);
    assert!(payload.state.as_ref().unwrap().chars().count() <= MAX_FIELD_LEN);
    assert!(payload.details.ends_with('…'));
}

#[test]
fn test_driving_presence_is_privacy_safe_and_concise() {
    let state = driving_presence(
        "delivery",
        "Chicago",
        "Dallas",
        "steel coils",
        0.42,
        true,
        "Standard rig",
    );
    assert_eq!(state.activity, "Driving: Chicago to Dallas");
    assert!(state.detail.contains("steel coils"));
    assert!(state.detail.contains("40% there")); // rounded to nearest 5%
    assert!(state.detail.contains("Standard rig"));
    // Nothing private leaks into the strings.
    let blob = format!("{}{}", state.activity, state.detail).to_lowercase();
    assert!(!blob.contains("save") && !blob.contains('/') && !blob.contains('\\'));
}

#[test]
fn test_driving_presence_stopped_and_pickup_phrasing() {
    let stopped = driving_presence("delivery", "Reno", "Boise", "lumber", 0.9, false, "");
    assert!(stopped.activity.starts_with("Stopped"));

    let pickup = driving_presence("pickup", "Tampa", "Miami", "produce", 0.1, true, "");
    assert!(pickup.activity.to_lowercase().contains("pickup"));
    assert!(pickup.detail.contains("produce"));
}

#[test]
fn test_driving_presence_clamps_fraction() {
    assert!(driving_presence("delivery", "A", "B", "x", -1.0, true, "")
        .detail
        .contains("0% there"));
    assert!(driving_presence("delivery", "A", "B", "x", 2.0, true, "")
        .detail
        .contains("100% there"));
}

// -- disabled mode ------------------------------------------------------------

#[test]
fn test_disabled_never_touches_rpc() {
    let rpc = FakeRpc::new();
    let clock = ManualClock::new();
    let presence = make_presence(&rpc, &clock, false, 15.0);
    presence.start();
    presence.update(Some(PresenceState::activity("In the main menu")));
    presence.shutdown();
    assert!(!presence.enabled());
    assert_eq!(rpc.connects(), 0);
    assert!(rpc.updates().is_empty());
}

// -- missing dependency / unavailable Discord ---------------------------------

#[test]
fn test_missing_dependency_leaves_service_dormant() {
    // rpc_factory=None models the RPC client being absent entirely.
    let presence = DiscordPresence::new(DiscordPresenceOptions {
        rpc_factory: None,
        threaded: false,
        ..DiscordPresenceOptions::default()
    });
    assert!(!presence.enabled());
    presence.start();
    presence.update(Some(PresenceState::activity("In the main menu")));
    presence.shutdown(); // must not panic
}

#[test]
fn test_discord_closed_is_handled_and_retried_after_backoff() {
    let rpc = FakeRpc::with_connect_error("Discord not running");
    let clock = ManualClock::new();
    let presence = make_presence(&rpc, &clock, true, 15.0);
    presence.start();
    presence.update(Some(PresenceState::activity("In the main menu")));
    assert_eq!(rpc.connects(), 1); // tried once
    assert!(rpc.updates().is_empty()); // nothing sent; no crash
    assert!(!presence.connected());

    // Within the backoff window it does not hammer the socket.
    presence.update(Some(PresenceState::activity("At the terminal")));
    assert_eq!(rpc.connects(), 1);

    // After the backoff window it tries again.
    clock.advance(31.0);
    presence.update(Some(PresenceState::activity("Driving a route")));
    assert_eq!(rpc.connects(), 2);
    presence.shutdown();
}

#[test]
fn test_update_failure_drops_connection_for_reconnect() {
    let rpc = FakeRpc::with_update_error("pipe closed");
    let clock = ManualClock::new();
    let presence = make_presence(&rpc, &clock, true, 15.0);
    presence.start();
    presence.update(Some(PresenceState::activity("Driving a route")));
    assert_eq!(rpc.connects(), 1);
    assert!(!presence.connected()); // disconnected after the failed update
    presence.shutdown(); // never panics
}

// -- throttling / de-duplication ---------------------------------------------

#[test]
fn test_identical_state_is_not_resent() {
    let rpc = FakeRpc::new();
    let clock = ManualClock::new();
    let presence = make_presence(&rpc, &clock, true, 15.0);
    presence.start();
    presence.update(Some(PresenceState::new(
        "Driving a route",
        "Chicago to Dallas",
    )));
    presence.update(Some(PresenceState::new(
        "Driving a route",
        "Chicago to Dallas",
    )));
    presence.update(Some(PresenceState::new(
        "Driving a route",
        "Chicago to Dallas",
    )));
    assert_eq!(rpc.updates().len(), 1);
    presence.shutdown();
}

#[test]
fn test_changes_are_throttled_then_flushed() {
    let rpc = FakeRpc::new();
    let clock = ManualClock::new();
    let presence = make_presence(&rpc, &clock, true, 15.0);
    presence.start();
    presence.update(Some(PresenceState::activity("In the main menu")));
    assert_eq!(rpc.updates().len(), 1);

    // A new state inside the throttle window is held back, not sent.
    clock.advance(5.0);
    presence.update(Some(PresenceState::activity("At the terminal")));
    assert_eq!(rpc.updates().len(), 1);

    // Once the window passes, the latest state flushes on the next report.
    clock.advance(11.0);
    presence.update(Some(PresenceState::activity("Driving a route")));
    assert_eq!(rpc.updates().len(), 2);
    assert_eq!(rpc.updates().last().unwrap().details, "Driving a route");
    presence.shutdown();
}

#[test]
fn test_first_update_sends_immediately() {
    let rpc = FakeRpc::new();
    let clock = ManualClock::new();
    let presence = make_presence(&rpc, &clock, true, 15.0);
    presence.start();
    presence.update(Some(PresenceState::activity("In the main menu")));
    assert_eq!(rpc.updates().len(), 1);
    assert_eq!(rpc.updates()[0].details, "In the main menu");
    presence.shutdown();
}

// -- shutdown cleanup ---------------------------------------------------------

#[test]
fn test_shutdown_clears_and_closes_the_rpc() {
    let rpc = FakeRpc::new();
    let clock = ManualClock::new();
    let presence = make_presence(&rpc, &clock, true, 15.0);
    presence.start();
    presence.update(Some(PresenceState::activity("Driving a route")));
    presence.shutdown();
    assert_eq!(rpc.cleared(), 1);
    assert_eq!(rpc.closed(), 1);
    assert!(!presence.connected());
}

#[test]
fn test_shutdown_is_idempotent_and_safe_without_start() {
    let presence = make_presence(&FakeRpc::new(), &ManualClock::new(), true, 15.0);
    presence.shutdown();
    presence.shutdown(); // no error on a second call or when never started
}

#[test]
fn test_set_enabled_toggles_runtime_state() {
    let rpc = FakeRpc::new();
    let clock = ManualClock::new();
    let presence = make_presence(&rpc, &clock, true, 15.0);
    presence.start();
    presence.update(Some(PresenceState::activity("Driving a route")));
    assert_eq!(rpc.updates().len(), 1);

    presence.set_enabled(false);
    assert!(!presence.enabled());
    assert_eq!(rpc.cleared(), 1); // disabling tears the presence down
    presence.update(Some(PresenceState::activity("At the terminal")));
    assert_eq!(rpc.updates().len(), 1); // ignored while disabled

    // Re-enabling reconnects and re-shows the last reported state at once.
    presence.set_enabled(true);
    assert_eq!(rpc.updates().len(), 2);
    assert_eq!(rpc.updates().last().unwrap().details, "Driving a route");

    // A fresh distinct state flushes after the throttle window.
    clock.advance(20.0);
    presence.update(Some(PresenceState::activity("At the terminal")));
    assert_eq!(rpc.updates().len(), 3);
    assert_eq!(rpc.updates().last().unwrap().details, "At the terminal");
    presence.shutdown();
}

// -- threaded path smoke ------------------------------------------------------

#[test]
fn test_threaded_service_sends_and_shuts_down() {
    let rpc = FakeRpc::new();
    let presence = DiscordPresence::new(DiscordPresenceOptions {
        client_id: Some("test-app-id".to_string()),
        min_interval_s: 0.0,
        rpc_factory: Some(rpc.factory()),
        threaded: true,
        ..DiscordPresenceOptions::default()
    });
    presence.start();
    presence.update(Some(PresenceState::activity("In the main menu")));
    // Give the worker a moment to connect and push the first update.
    let deadline = Instant::now() + Duration::from_secs(2);
    while rpc.updates().is_empty() && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(10));
    }
    presence.shutdown();
    assert!(rpc.connects() >= 1);
    assert!(!rpc.updates().is_empty());
    assert_eq!(rpc.closed(), 1);
}

// -- quitting never waits on a handshake that will not come -------------------

/// An RPC whose handshake blocks until the test releases it.
///
/// Discord's IPC handshake is a blocking pipe read with no timeout, and
/// Discord stops answering handshakes for a while when a game is launched
/// several times in quick succession. A worker parked in that read is the
/// real shape this models.
#[derive(Clone)]
struct BlockingConnectRpc {
    inner: FakeRpc,
    entered: Arc<AtomicBool>,
    released: Arc<AtomicBool>,
}

impl BlockingConnectRpc {
    fn new() -> Self {
        Self {
            inner: FakeRpc::new(),
            entered: Arc::new(AtomicBool::new(false)),
            released: Arc::new(AtomicBool::new(false)),
        }
    }

    fn factory(&self) -> RpcFactory {
        let me = self.clone();
        Arc::new(move |_cid: &str| Ok(Box::new(me.clone()) as Box<dyn RpcClient>))
    }

    /// Block until the worker is inside the handshake.
    fn await_handshake(&self) {
        let deadline = Instant::now() + Duration::from_secs(5);
        while !self.entered.load(Ordering::SeqCst) && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(5));
        }
        assert!(
            self.entered.load(Ordering::SeqCst),
            "the worker never reached the handshake"
        );
    }

    fn release(&self) {
        self.released.store(true, Ordering::SeqCst);
    }
}

impl RpcClient for BlockingConnectRpc {
    fn connect(&mut self) -> Result<(), String> {
        self.entered.store(true, Ordering::SeqCst);
        while !self.released.load(Ordering::SeqCst) {
            thread::sleep(Duration::from_millis(5));
        }
        self.inner.connect()
    }

    fn update(&mut self, payload: &ActivityPayload) -> Result<(), String> {
        self.inner.update(payload)
    }

    fn clear(&mut self) -> Result<(), String> {
        self.inner.clear()
    }

    fn close(&mut self) -> Result<(), String> {
        self.inner.close()
    }
}

#[test]
fn test_quitting_does_not_wait_on_a_handshake_that_never_answers() {
    let rpc = BlockingConnectRpc::new();
    let presence = DiscordPresence::new(DiscordPresenceOptions {
        client_id: Some("test-app-id".to_string()),
        min_interval_s: 0.0,
        rpc_factory: Some(rpc.factory()),
        threaded: true,
        ..DiscordPresenceOptions::default()
    });
    presence.start();
    presence.update(Some(PresenceState::activity("In the main menu")));
    rpc.await_handshake();

    let began = Instant::now();
    presence.shutdown();
    let waited = began.elapsed();
    rpc.release();
    assert!(
        waited < Duration::from_millis(500),
        "quitting waited {waited:?} on a worker with no presence to clear"
    );
}

#[test]
fn test_a_late_handshake_never_shows_a_presence_after_quitting() {
    let rpc = BlockingConnectRpc::new();
    let presence = DiscordPresence::new(DiscordPresenceOptions {
        client_id: Some("test-app-id".to_string()),
        min_interval_s: 0.0,
        rpc_factory: Some(rpc.factory()),
        threaded: true,
        ..DiscordPresenceOptions::default()
    });
    presence.start();
    presence.update(Some(PresenceState::activity("In the main menu")));
    rpc.await_handshake();
    presence.shutdown();

    // Discord answers after the player has already quit: the reply is dropped
    // rather than used to show them still playing.
    rpc.release();
    let deadline = Instant::now() + Duration::from_secs(2);
    while rpc.inner.connects() == 0 && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(5));
    }
    thread::sleep(Duration::from_millis(100));
    assert!(
        rpc.inner.updates().is_empty(),
        "a presence was shown after quitting: {:?}",
        rpc.inner.updates()
    );
    assert!(!presence.connected());
}

/// The other half: a worker that *does* hold a live client is still waited
/// for, and its presence still cleared, so nothing was traded away for the
/// quick quit above.
#[test]
fn test_quitting_still_clears_a_presence_the_worker_is_showing() {
    let rpc = FakeRpc::new();
    let presence = DiscordPresence::new(DiscordPresenceOptions {
        client_id: Some("test-app-id".to_string()),
        min_interval_s: 0.0,
        rpc_factory: Some(rpc.factory()),
        threaded: true,
        ..DiscordPresenceOptions::default()
    });
    presence.start();
    presence.update(Some(PresenceState::activity("Driving a route")));
    let deadline = Instant::now() + Duration::from_secs(2);
    while rpc.updates().is_empty() && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(10));
    }
    assert!(presence.connected(), "the worker never connected");
    presence.shutdown();
    assert_eq!(rpc.cleared(), 1);
    assert_eq!(rpc.closed(), 1);
}

#[test]
fn test_a_late_handshake_never_shows_a_presence_after_switching_it_off() {
    let rpc = BlockingConnectRpc::new();
    let presence = DiscordPresence::new(DiscordPresenceOptions {
        client_id: Some("test-app-id".to_string()),
        min_interval_s: 0.0,
        rpc_factory: Some(rpc.factory()),
        threaded: true,
        ..DiscordPresenceOptions::default()
    });
    presence.start();
    presence.update(Some(PresenceState::activity("In the main menu")));
    rpc.await_handshake();

    // Settings, Online, Discord status: off. Unlike quitting, this clears the
    // stop flag again afterwards, so the worker has to read the switch itself.
    let began = Instant::now();
    presence.set_enabled(false);
    let waited = began.elapsed();
    assert!(
        waited < Duration::from_millis(500),
        "switching Discord status off froze the game for {waited:?}"
    );

    rpc.release();
    let deadline = Instant::now() + Duration::from_secs(2);
    while rpc.inner.connects() == 0 && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(5));
    }
    thread::sleep(Duration::from_millis(100));
    assert!(
        rpc.inner.updates().is_empty(),
        "a presence was shown after the player turned it off: {:?}",
        rpc.inner.updates()
    );
    assert!(!presence.connected());
    assert!(!presence.enabled());
}

/// The board and Discord must name the tractor the driver is IN. For a
/// company driver that is the fleet assignment, not the profile's raw
/// `truck` field -- which is save-compat storage and had the drivers board
/// naming Brandon's old yard mule while he drove the presidential sleeper
/// (reported 2026-08-31).
#[test]
fn test_presence_names_the_fleet_assignment_not_the_stored_truck() {
    use ff_core::models::career::LEVEL_XP;
    use ff_core::models::profile::Profile;
    use freight_fate::states::driving::DrivingState;

    let mut profile = Profile::new();
    profile.career.xp = LEVEL_XP[16]; // level 17: "first pick of the yard"
    profile.truck = "yard_mule".to_string();

    let label = DrivingState::presence_truck_label(&profile);
    assert_ne!(label, "yard mule", "the stored truck leaked into presence");
    assert_ne!(label, "", "no tractor label resolved at all");
    let assigned = profile.active_truck_key();
    let expected = ff_core::models::trucks::TRUCK_CATALOG
        .get(assigned.as_str())
        .map(|t| t.label)
        .unwrap();
    assert_eq!(label, expected);
}
