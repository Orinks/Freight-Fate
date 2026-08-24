//! Port of `tests/test_online_activation.py`: the device-code activation
//! flow (replaces clipboard paste).
//!
//! A fake transport keeps every test free of real sockets, matching the
//! pattern in `online_presence.rs`. The contract points that matter most:
//! 410 means "expired, get a new code" while 400 means "this device_code is
//! malformed and retrying it never helps" -- "error" is reserved for exactly
//! that 400 case, and everything else unrecognised (other HTTP statuses,
//! network trouble, an unparseable 200 body) is "retry" instead, so the two
//! must never collapse to the same status; an over-cap redeem also answers
//! 410, because the real reason lives on the website at claim time; and
//! `display_name` must survive a ready poll uncorrupted, because it is the
//! player's only signal that the code was claimed on the wrong account.

use std::sync::Mutex;

use serde_json::{json, Value};

use freight_fate::net::testing::ClosureTransport;
use freight_fate::net::{NetError, Transport};
use freight_fate::online_activation::{
    self, base_url, machine_key, poll_activation, spell_code, start_activation, Activation,
};

fn an_activation() -> Activation {
    Activation {
        device_code: "a".repeat(64),
        user_code: "WKQR-3468".to_string(),
        verification_uri: "https://orinks.net/activate".to_string(),
        verification_uri_complete: "https://orinks.net/activate?code=WKQR-3468".to_string(),
        expires_at: 0.0,
        interval: 3.0,
    }
}

fn replying(body: Value) -> impl Transport {
    ClosureTransport(
        move |_url: &str, _p: Option<&Value>, _h: &[(String, String)], _m: Option<&str>| {
            Ok(body.clone())
        },
    )
}

fn poll_raising(error: NetError) -> online_activation::PollResult {
    let transport = ClosureTransport(
        move |_url: &str, _p: Option<&Value>, _h: &[(String, String)], _m: Option<&str>| {
            Err(error.clone())
        },
    );
    poll_activation(&an_activation(), &transport)
}

fn data_dir() -> tempfile::TempDir {
    tempfile::tempdir().unwrap()
}

// -- spell_code ----------------------------------------------------------------

#[test]
fn test_spell_code_uses_phonetics_and_speaks_the_dash() {
    assert_eq!(
        spell_code("WKQR-3468"),
        "Whiskey, Kilo, Quebec, Romeo, dash, three, four, six, eight"
    );
}

#[test]
fn test_spell_code_accepts_an_undashed_code() {
    assert!(spell_code("WKQR3468").starts_with("Whiskey, Kilo"));
}

#[test]
fn test_spell_code_accepts_a_lowercase_code() {
    assert_eq!(
        spell_code("wkqr-3468"),
        "Whiskey, Kilo, Quebec, Romeo, dash, three, four, six, eight"
    );
}

#[test]
fn test_spell_code_covers_the_whole_activation_alphabet() {
    // ABCDEFGHJKMNPQRTUVWXY346789 -- deliberately excludes O I L S Z 0 1 2 5,
    // chosen so no two phonetic words could ever be confused for each other.
    let alphabet = "ABCDEFGHJKMNPQRTUVWXY346789";
    let spelled = spell_code(alphabet);
    let words: Vec<&str> = spelled.split(", ").collect();
    assert_eq!(words.len(), alphabet.len());
    let unique: std::collections::HashSet<&str> = words.iter().copied().collect();
    assert_eq!(unique.len(), words.len());
    assert!(words.iter().all(|w| !w.is_empty()));
}

// -- the device_code never leaves this module ----------------------------------

#[test]
fn test_activation_repr_never_carries_the_device_code() {
    // The polling secret must never reach a log line or the session
    // transcript. Keeping it out by convention is not enough: a Debug dump
    // is what a stray `log::warn!("... {:?}", activation)` would print, and
    // nothing would fail. Leaving it out of Debug makes the invariant
    // structural.
    let mut activation = an_activation();
    activation.device_code = format!("s3cret{}", "a".repeat(58));

    let text = format!("{activation:?}");

    assert!(!text.contains(&activation.device_code));
    assert!(!text.contains("s3cret"));
    // The player-facing code is not a secret and is still there, so a repr
    // remains useful for diagnosing which activation is in play.
    assert!(text.contains("WKQR-3468"));
}

// -- start_activation ------------------------------------------------------------

fn start_reply() -> Value {
    json!({
        "device_code": "a".repeat(64),
        "user_code": "WKQR-3468",
        "verification_uri": "https://orinks.net/activate",
        "verification_uri_complete": "https://orinks.net/activate?code=WKQR-3468",
        "expires_in": 600,
        "interval": 3,
    })
}

#[test]
fn test_start_returns_an_activation() {
    let seen = Mutex::new(String::new());
    let transport = ClosureTransport(
        |url: &str, _p: Option<&Value>, _h: &[(String, String)], _m: Option<&str>| {
            *seen.lock().unwrap() = url.to_string();
            Ok(start_reply())
        },
    );
    let dir = data_dir();
    let activation = start_activation(&transport, dir.path()).expect("an activation");
    assert!(seen
        .lock()
        .unwrap()
        .ends_with("/api/freight-fate/activate/start"));
    assert_eq!(activation.user_code, "WKQR-3468");
    assert_eq!(activation.interval, 3.0);
    assert!(activation.expires_at > 0.0);
}

#[test]
fn test_start_names_this_computer_so_the_list_does_not_fill_up() {
    // orinks.net capped an account at ten computers and counted activations,
    // so every unzipped build took another slot and a tester filled the list with
    // one PC (armstrong445, 2026-08-15). The server replaces a computer's entry
    // when the game names it; naming it is this call's job.
    let sent = Mutex::new(Value::Null);
    let transport = ClosureTransport(
        |_url: &str, payload: Option<&Value>, _h: &[(String, String)], _m: Option<&str>| {
            *sent.lock().unwrap() = payload.cloned().unwrap_or(Value::Null);
            Ok(start_reply())
        },
    );
    let dir = data_dir();
    assert!(start_activation(&transport, dir.path()).is_some());
    let key = sent.lock().unwrap()["machine_key"]
        .as_str()
        .unwrap()
        .to_string();
    // Opaque and bounded: the server compares it and nothing else, so it must
    // never carry a hostname a person could be named in.
    assert_eq!(key.len(), 32, "{key}");
    assert!(key.chars().all(|c| "0123456789abcdef".contains(c)), "{key}");
    let host = online_activation::hostname().to_lowercase();
    if !host.is_empty() {
        assert!(!key.to_lowercase().contains(&host));
    }
    // The same computer must answer the same, or the row it replaces is never
    // found and the list fills up exactly as before.
    assert_eq!(key, machine_key(dir.path()));
}

#[test]
fn test_start_returns_none_on_rate_limit_or_unavailable() {
    let dir = data_dir();
    for code in [429u16, 503] {
        let transport = ClosureTransport(
            move |_url: &str, _p: Option<&Value>, _h: &[(String, String)], _m: Option<&str>| {
                Err(NetError::http(code))
            },
        );
        assert!(start_activation(&transport, dir.path()).is_none());
    }
}

#[test]
fn test_start_returns_none_on_malformed_reply() {
    // A 200 missing an expected field must not raise into the caller.
    let dir = data_dir();
    let transport = replying(json!({"device_code": "a".repeat(64)})); // missing user_code and friends
    assert!(start_activation(&transport, dir.path()).is_none());
}

#[test]
fn test_start_never_raises_on_network_trouble() {
    let dir = data_dir();
    let transport = ClosureTransport(
        |_url: &str, _p: Option<&Value>, _h: &[(String, String)], _m: Option<&str>| {
            Err(NetError::other("OSError", "no route to host"))
        },
    );
    assert!(start_activation(&transport, dir.path()).is_none());
}

// -- poll_activation ---------------------------------------------------------------

#[test]
fn test_poll_ready_carries_the_display_name() {
    // The display name is the player's only signal that someone else claimed
    // their code -- the game speaks it, so it must survive the poll.
    let transport = ClosureTransport(
        |url: &str, payload: Option<&Value>, _h: &[(String, String)], _m: Option<&str>| {
            assert!(url.ends_with("/api/freight-fate/activate/poll"));
            assert_eq!(
                payload.cloned().unwrap(),
                json!({"device_code": an_activation().device_code})
            );
            Ok(json!({
                "status": "ready",
                "driver_id": "rig-hauler",
                "token": format!("ffd_{}", "b".repeat(64)),
                "display_name": "Rig Hauler",
            }))
        },
    );
    let result = poll_activation(&an_activation(), &transport);
    assert_eq!(result.status, "ready");
    assert_eq!(result.driver_id.as_deref(), Some("rig-hauler"));
    assert_eq!(result.token, Some(format!("ffd_{}", "b".repeat(64))));
    assert_eq!(result.display_name.as_deref(), Some("Rig Hauler"));
}

#[test]
fn test_poll_ready_without_an_identity_is_a_retry_not_a_claim() {
    // A "ready" body with no driver_id or token is not something the caller
    // can act on. Trusting it would save a null identity and tell the player
    // "Connected to orinks.net" while every later heartbeat sent no token at
    // all -- a silent, unactionable failure. "retry" instead of "error" because
    // a broken deploy or a rewriting middlebox is transient from the game's
    // side: polling should keep going until the code really expires.
    let token = format!("ffd_{}", "b".repeat(64));
    let bodies = [
        json!({"status": "ready"}),
        json!({"status": "ready", "driver_id": "rig-hauler"}),
        json!({"status": "ready", "token": token}),
        json!({"status": "ready", "driver_id": "", "token": token}),
        json!({"status": "ready", "driver_id": "rig-hauler", "token": ""}),
        json!({"status": "ready", "driver_id": null, "token": null, "display_name": "Rig Hauler"}),
    ];
    for body in bodies {
        let result = poll_activation(&an_activation(), &replying(body.clone()));
        assert_eq!(result.status, "retry", "{body}");
        assert!(result.driver_id.is_none());
        assert!(result.token.is_none());
    }
}

#[test]
fn test_poll_pending_carries_no_identity() {
    let result = poll_activation(&an_activation(), &replying(json!({"status": "pending"})));
    assert_eq!(result.status, "pending");
    assert!(result.driver_id.is_none());
    assert!(result.token.is_none());
    assert!(result.display_name.is_none());
}

#[test]
fn test_poll_maps_410_to_expired_and_400_to_corrupt() {
    // 410 means the code timed out and a new one will fix it. 400 means the
    // stored secret is malformed, which retrying the same code never fixes --
    // "error" is reserved for exactly this case and nothing else.
    assert_eq!(poll_raising(NetError::http(410)).status, "expired");
    assert_eq!(poll_raising(NetError::http(400)).status, "error");
}

#[test]
fn test_poll_over_cap_redeem_reads_as_expired() {
    // The server answers an over-cap redeem with 410 too -- the player learns
    // the real reason (too many computers) on the website at claim time, so the
    // game just treats it like any other timed-out code.
    assert_eq!(poll_raising(NetError::http(410)).status, "expired");
}

#[test]
fn test_poll_maps_503_to_retry_not_error() {
    // A 5xx is the server's own trouble, not a verdict on this device_code --
    // unlike a 400, the same code is worth polling again on the next tick.
    assert_eq!(poll_raising(NetError::http(503)).status, "retry");
}

#[test]
fn test_poll_maps_other_http_statuses_to_retry() {
    // Nothing except 400 and 410 is meaningful here; nothing else should be
    // "error" (terminal) either -- nearly anything else the server could answer
    // with is worth polling again rather than sending the player back through
    // a whole new activation code.
    for code in [401u16, 403, 404, 429, 500, 502] {
        assert_eq!(poll_raising(NetError::http(code)).status, "retry");
    }
}

#[test]
fn test_poll_never_raises_on_network_trouble() {
    // Polling runs on a timer while the player waits; a transient blip must
    // not crash the menu, and must not be presented as the terminal "error"
    // that only a malformed device_code (HTTP 400) gets -- the next poll, a
    // few seconds later, may well succeed on its own.
    let result = poll_raising(NetError::other("OSError", "connection reset"));
    assert_eq!(result.status, "retry");
}

#[test]
fn test_poll_never_raises_on_malformed_200() {
    let result = poll_activation(
        &an_activation(),
        &replying(json!({"status": "some-unexpected-shape"})),
    );
    assert_eq!(result.status, "retry");
}

#[test]
fn test_poll_never_raises_on_a_null_200_body() {
    // Regression: reply.get(...) ran unguarded on whatever the transport
    // returned, so a 200 with a non-mapping body (None here) raised straight
    // into the caller instead of coming back as a retryable result.
    let result = poll_activation(&an_activation(), &replying(Value::Null));
    assert_eq!(result.status, "retry");
}

#[test]
fn test_poll_never_raises_on_a_list_200_body() {
    let result = poll_activation(&an_activation(), &replying(json!(["not", "a", "mapping"])));
    assert_eq!(result.status, "retry");
}

#[test]
fn test_poll_never_raises_on_a_dict_missing_status() {
    let result = poll_activation(
        &an_activation(),
        &replying(json!({"driver_id": "rig-hauler"})),
    );
    assert_eq!(result.status, "retry");
}

#[test]
fn test_base_url_reused_from_online_presence() {
    // online_activation must not fork its own base_url -- one FREIGHT_FATE_ONLINE_URL
    // override has to redirect every Orinks endpoint the game talks to.
    assert_eq!(base_url(), freight_fate::online_presence::base_url());
}

#[test]
fn test_machine_key_is_stable_within_a_process() {
    let dir = data_dir();
    let first = machine_key(dir.path());
    let second = machine_key(dir.path());
    assert_eq!(first, second);
    assert_eq!(first.len(), 32);
}
