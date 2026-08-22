//! Port of `freight_fate/net.py` — shared HTTPS helpers: one verified TLS
//! client per timeout tier, and speakable descriptions of network failures.
//!
//! Frozen Python builds could ship an OpenSSL whose CA paths were baked in on
//! the build machine, so `net.py` layered certifi's bundle on top of the
//! platform store. The Rust build talks TLS through rustls with the platform
//! verifier: the operating system's own roots (corporate proxy roots on
//! Windows included) on every platform, with no bundle to go stale.
//!
//! This module also owns the two things every online module used to reach
//! for separately in Python: the [`Transport`] trait (the `_http_json`
//! callable the services and their tests inject) and the [`NetError`] taxonomy
//! that stands in for `urllib.error.HTTPError` / `URLError` / `ssl` /
//! `socket` exceptions, so [`describe_error`] can speak the same sentences.

use std::fmt;
use std::io;
use std::sync::{Arc, Condvar, Mutex};
use std::time::Duration;

use once_cell::sync::Lazy;
use serde_json::Value;
use ureq::tls::{RootCerts, TlsConfig};
use ureq::Agent;

use ff_core::sim::real_traffic::{HttpTransport, TransportError};

pub mod testing;

// -- timeout tiers --------------------------------------------------------------

/// One shared client per timeout tier. Python built a fresh `urlopen` per
/// request against a cached `ssl_context()`; here the agent (connection pool
/// plus TLS config) is the cached thing, and the timeout is the only thing
/// that differs between the callers.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Tier {
    /// orinks.net presence, activation, journal, cloud saves
    /// (`online_presence._REQUEST_TIMEOUT_S = 10`).
    Orinks,
    /// GitHub releases API and asset downloads (`updater.TIMEOUT = 15`).
    GitHub,
    /// Live weather and traffic feeds (`real_traffic.FETCH_TIMEOUT_S = 8`).
    Feeds,
}

impl Tier {
    /// The per-request timeout, in seconds, exactly as the Python module
    /// that owned each caller set it.
    pub fn timeout_s(self) -> f64 {
        match self {
            Tier::Orinks => 10.0,
            Tier::GitHub => 15.0,
            Tier::Feeds => 8.0,
        }
    }
}

fn build_agent(timeout_s: f64) -> Agent {
    let config = Agent::config_builder()
        .timeout_global(Some(Duration::from_secs_f64(timeout_s)))
        // Statuses are data here: the online modules read the server's JSON
        // error body out of a 4xx (Convex says *why* a paste was refused),
        // which an error-on-status client would have discarded.
        .http_status_as_error(false)
        .tls_config(
            TlsConfig::builder()
                .root_certs(RootCerts::PlatformVerifier)
                .build(),
        )
        .build();
    Agent::new_with_config(config)
}

static ORINKS_AGENT: Lazy<Agent> = Lazy::new(|| build_agent(Tier::Orinks.timeout_s()));
static GITHUB_AGENT: Lazy<Agent> = Lazy::new(|| build_agent(Tier::GitHub.timeout_s()));
static FEEDS_AGENT: Lazy<Agent> = Lazy::new(|| build_agent(Tier::Feeds.timeout_s()));

/// The shared client for a tier. `ssl_context()` in Python was
/// `lru_cache`d; these are built once per process the same way.
pub fn agent(tier: Tier) -> &'static Agent {
    match tier {
        Tier::Orinks => &ORINKS_AGENT,
        Tier::GitHub => &GITHUB_AGENT,
        Tier::Feeds => &FEEDS_AGENT,
    }
}

// -- the error taxonomy -----------------------------------------------------------

/// What went wrong with an HTTP request, in the families Python's exception
/// types drew for `describe_error`. Carries the server's status and body
/// for an HTTP-level refusal because the online modules read both.
#[derive(Debug, Clone)]
pub enum NetError {
    /// `urllib.error.HTTPError`: the server answered with a non-2xx status.
    Http { code: u16, body: Vec<u8> },
    /// `ssl.SSLCertVerificationError`.
    CertVerification(String),
    /// `ssl.SSLError` (any other TLS failure).
    Tls(String),
    /// `socket.gaierror`: DNS resolution failed.
    HostNotFound(String),
    /// `TimeoutError`.
    Timeout(String),
    /// `ConnectionError` (refused, reset, aborted, broken pipe).
    Connection(String),
    /// Anything else: `str(e)`, with the exception's type name as the
    /// fallback when the message is empty.
    Other { type_name: String, message: String },
}

impl NetError {
    /// An HTTP error with an empty body, the shape most tests build.
    pub fn http(code: u16) -> Self {
        NetError::Http {
            code,
            body: Vec::new(),
        }
    }

    /// An HTTP error whose body is the given JSON document.
    pub fn http_json(code: u16, body: &Value) -> Self {
        NetError::Http {
            code,
            body: serde_json::to_vec(body).unwrap_or_default(),
        }
    }

    /// `OSError("message")` and friends: a generic failure.
    pub fn other(type_name: &str, message: &str) -> Self {
        NetError::Other {
            type_name: type_name.to_string(),
            message: message.to_string(),
        }
    }

    /// The HTTP status when this is an HTTP-level refusal.
    pub fn http_code(&self) -> Option<u16> {
        match self {
            NetError::Http { code, .. } => Some(*code),
            _ => None,
        }
    }

    /// The server's JSON error body as an object (`{}` when there is none
    /// or it is not an object) -- `cloud_saves._error_body`.
    pub fn error_body(&self) -> serde_json::Map<String, Value> {
        match self {
            NetError::Http { body, .. } => match serde_json::from_slice::<Value>(body) {
                Ok(Value::Object(map)) => map,
                _ => serde_json::Map::new(),
            },
            _ => serde_json::Map::new(),
        }
    }

    /// The first 500 characters of the body, decoded leniently -- what the
    /// identity check logs so a player-attached log tells us why a paste was
    /// refused.
    pub fn body_excerpt(&self) -> String {
        match self {
            NetError::Http { body, .. } => {
                String::from_utf8_lossy(body).chars().take(500).collect()
            }
            _ => String::new(),
        }
    }
}

impl fmt::Display for NetError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            NetError::Http { code, .. } => write!(f, "HTTP Error {code}"),
            NetError::CertVerification(m)
            | NetError::Tls(m)
            | NetError::HostNotFound(m)
            | NetError::Timeout(m)
            | NetError::Connection(m) => f.write_str(m),
            NetError::Other { type_name, message } => {
                if message.is_empty() {
                    f.write_str(type_name)
                } else {
                    f.write_str(message)
                }
            }
        }
    }
}

impl std::error::Error for NetError {}

impl From<io::Error> for NetError {
    fn from(err: io::Error) -> Self {
        classify_io(&err)
    }
}

fn classify_io(err: &io::Error) -> NetError {
    use io::ErrorKind::*;
    let message = err.to_string();
    match err.kind() {
        TimedOut => NetError::Timeout(message),
        ConnectionRefused | ConnectionReset | ConnectionAborted | NotConnected | BrokenPipe => {
            NetError::Connection(message)
        }
        _ => {
            // rustls surfaces handshake failures as io errors wrapping its
            // own error type; the text is the only handle on which one.
            let lower = message.to_ascii_lowercase();
            if lower.contains("certificate")
                || lower.contains("unknownissuer")
                || lower.contains("unknown issuer")
                || lower.contains("invalid peer")
            {
                NetError::CertVerification(message)
            } else if lower.contains("tls")
                || lower.contains("handshake")
                || lower.contains("alert")
            {
                NetError::Tls(message)
            } else {
                NetError::Other {
                    type_name: "OSError".to_string(),
                    message,
                }
            }
        }
    }
}

impl From<ureq::Error> for NetError {
    fn from(err: ureq::Error) -> Self {
        match err {
            ureq::Error::StatusCode(code) => NetError::http(code),
            ureq::Error::Timeout(t) => NetError::Timeout(format!("timeout: {t}")),
            ureq::Error::HostNotFound => NetError::HostNotFound("getaddrinfo failed".to_string()),
            ureq::Error::ConnectionFailed => NetError::Connection("connection failed".to_string()),
            ureq::Error::Io(io_err) => classify_io(&io_err),
            ureq::Error::Tls(msg) => {
                let lower = msg.to_ascii_lowercase();
                if lower.contains("certificate") || lower.contains("verif") {
                    NetError::CertVerification(msg.to_string())
                } else {
                    NetError::Tls(msg.to_string())
                }
            }
            other => NetError::Other {
                type_name: "URLError".to_string(),
                message: other.to_string(),
            },
        }
    }
}

impl From<serde_json::Error> for NetError {
    fn from(err: serde_json::Error) -> Self {
        NetError::Other {
            type_name: "JSONDecodeError".to_string(),
            message: err.to_string(),
        }
    }
}

/// A short, speakable reason for a failed HTTP request.
///
/// Spoken to the player after lines like "Could not reach the update
/// server", so each message is a complete plain sentence.
pub fn describe_error(e: &NetError) -> String {
    match e {
        NetError::Http { code, .. } => format!("The server answered with error {code}."),
        NetError::CertVerification(_) => "The secure connection could not be verified.".to_string(),
        NetError::Tls(_) => "The secure connection failed.".to_string(),
        NetError::HostNotFound(_) => "The server address could not be found.".to_string(),
        NetError::Timeout(_) => "The connection timed out.".to_string(),
        NetError::Connection(_) => "The connection was refused or dropped.".to_string(),
        NetError::Other { type_name, message } => {
            let text = message.trim();
            if text.is_empty() {
                format!("{type_name}.")
            } else {
                format!("{text}.")
            }
        }
    }
}

// -- raw requests -------------------------------------------------------------------

/// One header list, in the order it is sent. A `Vec` rather than a map so
/// tests can assert on it the way the Python tests assert on the dict.
pub type Headers = Vec<(String, String)>;

/// The value of `name` in `headers`, matched case-insensitively.
pub fn header<'a>(headers: &'a [(String, String)], name: &str) -> Option<&'a str> {
    headers
        .iter()
        .find(|(k, _)| k.eq_ignore_ascii_case(name))
        .map(|(_, v)| v.as_str())
}

/// A raw HTTP reply: status plus the full body.
#[derive(Debug, Clone)]
pub struct RawResponse {
    pub status: u16,
    pub body: Vec<u8>,
}

/// Send one request on `tier`'s shared client. `method` is `GET` when
/// there is no body and `POST` when there is, unless overridden. A status
/// of 400 or above is returned as [`NetError::Http`] with the body attached,
/// which is how `urllib` raised `HTTPError`.
pub fn request(
    tier: Tier,
    method: Option<&str>,
    url: &str,
    body: Option<&[u8]>,
    headers: &[(String, String)],
) -> Result<RawResponse, NetError> {
    let agent = agent(tier);
    let method = method
        .map(|m| m.to_ascii_uppercase())
        .unwrap_or_else(|| if body.is_some() { "POST" } else { "GET" }.to_string());
    let mut response = match (method.as_str(), body) {
        ("GET", _) => {
            let mut req = agent.get(url);
            for (k, v) in headers {
                req = req.header(k.as_str(), v.as_str());
            }
            req.call()?
        }
        ("DELETE", None) => {
            let mut req = agent.delete(url);
            for (k, v) in headers {
                req = req.header(k.as_str(), v.as_str());
            }
            req.call()?
        }
        ("DELETE", Some(data)) => {
            let mut req = agent.delete(url).force_send_body();
            for (k, v) in headers {
                req = req.header(k.as_str(), v.as_str());
            }
            req.send(data)?
        }
        ("PUT", data) => {
            let mut req = agent.put(url);
            for (k, v) in headers {
                req = req.header(k.as_str(), v.as_str());
            }
            req.send(data.unwrap_or(&[]))?
        }
        ("PATCH", data) => {
            let mut req = agent.patch(url);
            for (k, v) in headers {
                req = req.header(k.as_str(), v.as_str());
            }
            req.send(data.unwrap_or(&[]))?
        }
        (_, data) => {
            let mut req = agent.post(url);
            for (k, v) in headers {
                req = req.header(k.as_str(), v.as_str());
            }
            req.send(data.unwrap_or(&[]))?
        }
    };
    let status = response.status().as_u16();
    let body = response
        .body_mut()
        .with_config()
        .limit(64 * 1024 * 1024)
        .read_to_vec()?;
    if status >= 400 {
        return Err(NetError::Http { code: status, body });
    }
    Ok(RawResponse { status, body })
}

/// `json.loads(resp.read().decode("utf-8"))`.
pub fn decode_json(body: &[u8]) -> Result<Value, NetError> {
    let text = std::str::from_utf8(body).map_err(|e| NetError::Other {
        type_name: "UnicodeDecodeError".to_string(),
        message: e.to_string(),
    })?;
    Ok(serde_json::from_str(text)?)
}

/// Send JSON (or GET when `payload` is `None`) and decode the JSON reply.
pub fn request_json(
    tier: Tier,
    method: Option<&str>,
    url: &str,
    payload: Option<&Value>,
    headers: &[(String, String)],
) -> Result<Value, NetError> {
    let data = match payload {
        Some(value) => Some(serde_json::to_vec(value)?),
        None => None,
    };
    let response = request(tier, method, url, data.as_deref(), headers)?;
    decode_json(&response.body)
}

// -- the injectable transport ----------------------------------------------------------

/// The `Transport` callable of `online_presence.py`: posts (or gets, when
/// `payload` is `None`) JSON and returns the decoded JSON reply. Injected in
/// tests; the default (`online_presence::DefaultTransport`) stamps the
/// game's User-Agent and talks to `Tier::Orinks`.
///
/// `method` is the `_http_delete` wrapper's `method="DELETE"`; `None` means
/// the usual POST-or-GET rule.
pub trait Transport: Send + Sync {
    fn call(
        &self,
        url: &str,
        payload: Option<&Value>,
        headers: &[(String, String)],
        method: Option<&str>,
    ) -> Result<Value, NetError>;
}

/// The `Transport` everything reaches for when none is injected.
pub type SharedTransport = Arc<dyn Transport>;

// -- the live-data transport --------------------------------------------------------------

/// [`HttpTransport`] for the live weather / traffic / parking providers in
/// `ff_core`, on the `Feeds` tier. Implemented once here and reused.
#[derive(Debug, Default, Clone, Copy)]
pub struct UreqTransport;

impl UreqTransport {
    fn send(
        &self,
        method: Option<&str>,
        url: &str,
        body: Option<&[u8]>,
        headers: &[(&str, &str)],
    ) -> Result<Vec<u8>, TransportError> {
        let owned: Headers = headers
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        match request(Tier::Feeds, method, url, body, &owned) {
            Ok(reply) => Ok(reply.body),
            Err(e) => Err(TransportError::new(describe_error(&e))),
        }
    }
}

impl HttpTransport for UreqTransport {
    fn get(
        &self,
        url: &str,
        headers: &[(&str, &str)],
        _timeout_s: f64,
    ) -> Result<Vec<u8>, TransportError> {
        self.send(Some("GET"), url, None, headers)
    }

    fn post(
        &self,
        url: &str,
        body: &[u8],
        headers: &[(&str, &str)],
        _timeout_s: f64,
    ) -> Result<Vec<u8>, TransportError> {
        self.send(Some("POST"), url, Some(body), headers)
    }
}

// -- a small shared thread primitive -----------------------------------------------------------

/// `threading.Event`: a flag a worker can wait on with a timeout. Every
/// background service here (presence, cloud saves, discord, journal) is
/// built from two of these -- `_wake` and `_stop` -- so they share one
/// implementation.
#[derive(Debug, Default)]
pub struct Event {
    state: Mutex<bool>,
    cv: Condvar,
}

impl Event {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn set(&self) {
        let mut guard = self.state.lock().unwrap_or_else(|e| e.into_inner());
        *guard = true;
        self.cv.notify_all();
    }

    pub fn clear(&self) {
        let mut guard = self.state.lock().unwrap_or_else(|e| e.into_inner());
        *guard = false;
    }

    pub fn is_set(&self) -> bool {
        *self.state.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Block until set or `timeout` elapses; returns whether it was set.
    pub fn wait(&self, timeout: Duration) -> bool {
        let guard = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if *guard {
            return true;
        }
        let (guard, _) = self
            .cv
            .wait_timeout_while(guard, timeout, |set| !*set)
            .unwrap_or_else(|e| e.into_inner());
        *guard
    }
}

/// `threading.Event.wait(seconds)` with a float timeout; negative or NaN
/// waits are treated as zero.
pub fn wait_seconds(event: &Event, seconds: f64) -> bool {
    let secs = if seconds.is_finite() && seconds > 0.0 {
        seconds
    } else {
        0.0
    };
    event.wait(Duration::from_secs_f64(secs))
}
