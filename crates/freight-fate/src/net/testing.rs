//! Test doubles shared by the online modules' tests: the `FakeTransport`
//! and manual `Clock` every Python test file re-declared, made once.
//! Part of the library (not `#[cfg(test)]`) so the integration tests in
//! `tests/` and the app-shell tests that come later can all use them.

use std::sync::{Arc, Mutex};

use serde_json::{json, Value};

use super::{NetError, Transport};
use ff_core::sim::real_traffic::Clock;

/// One recorded request: `(url, payload, headers)`, as the Python tests
/// unpacked them.
#[derive(Debug, Clone)]
pub struct RecordedRequest {
    pub url: String,
    pub payload: Option<Value>,
    pub headers: Vec<(String, String)>,
    pub method: Option<String>,
}

impl RecordedRequest {
    /// `headers["Authorization"]`-style lookup.
    pub fn header(&self, name: &str) -> Option<&str> {
        super::header(&self.headers, name)
    }
}

/// Records every request; replies with a fixed document, raises a fixed
/// error, or (when neither is set) answers `{"ok": true, "revision": n}`
/// with a counter -- the union of the `FakeTransport`s in
/// `test_online_presence.py` and `test_cloud_saves.py`.
#[derive(Debug, Default)]
pub struct FakeTransport {
    inner: Mutex<FakeInner>,
}

#[derive(Debug, Default)]
struct FakeInner {
    reply: Option<Value>,
    error: Option<NetError>,
    requests: Vec<RecordedRequest>,
    revision: i64,
    /// The presence-test default: `{"ok": true}` when no reply is set.
    ok_default: bool,
}

impl FakeTransport {
    /// `test_online_presence.FakeTransport()`: replies `{"ok": true}`.
    pub fn new() -> Arc<Self> {
        let me = Self::default();
        me.inner.lock().unwrap().ok_default = true;
        Arc::new(me)
    }

    /// `test_cloud_saves.FakeTransport()`: replies with an incrementing
    /// `{"ok": true, "revision": n}`.
    pub fn revisions() -> Arc<Self> {
        Arc::new(Self::default())
    }

    /// A transport that always answers `reply`.
    pub fn replying(reply: Value) -> Arc<Self> {
        let me = Self::new();
        me.set_reply(Some(reply));
        me
    }

    /// A transport that always fails with `error`.
    pub fn failing(error: NetError) -> Arc<Self> {
        let me = Self::new();
        me.set_error(Some(error));
        me
    }

    pub fn set_reply(&self, reply: Option<Value>) {
        self.inner.lock().unwrap().reply = reply;
    }

    pub fn set_error(&self, error: Option<NetError>) {
        self.inner.lock().unwrap().error = error;
    }

    /// Every request so far, oldest first.
    pub fn requests(&self) -> Vec<RecordedRequest> {
        self.inner.lock().unwrap().requests.clone()
    }

    /// The payloads of the requests that carried one (`FakeTransport.posts`).
    pub fn posts(&self) -> Vec<Value> {
        self.inner
            .lock()
            .unwrap()
            .requests
            .iter()
            .filter_map(|r| r.payload.clone())
            .collect()
    }

    pub fn request_count(&self) -> usize {
        self.inner.lock().unwrap().requests.len()
    }
}

impl Transport for FakeTransport {
    fn call(
        &self,
        url: &str,
        payload: Option<&Value>,
        headers: &[(String, String)],
        method: Option<&str>,
    ) -> Result<Value, NetError> {
        let mut inner = self.inner.lock().unwrap();
        inner.requests.push(RecordedRequest {
            url: url.to_string(),
            payload: payload.cloned(),
            headers: headers.to_vec(),
            method: method.map(str::to_string),
        });
        if let Some(error) = inner.error.clone() {
            return Err(error);
        }
        if let Some(reply) = inner.reply.clone() {
            return Ok(reply);
        }
        if inner.ok_default {
            return Ok(json!({"ok": true}));
        }
        inner.revision += 1;
        Ok(json!({"ok": true, "revision": inner.revision}))
    }
}

/// A transport driven by a closure, for tests that route on the request.
pub struct ClosureTransport<F>(pub F);

impl<F> Transport for ClosureTransport<F>
where
    F: Fn(&str, Option<&Value>, &[(String, String)], Option<&str>) -> Result<Value, NetError>
        + Send
        + Sync,
{
    fn call(
        &self,
        url: &str,
        payload: Option<&Value>,
        headers: &[(String, String)],
        method: Option<&str>,
    ) -> Result<Value, NetError> {
        (self.0)(url, payload, headers, method)
    }
}

/// A manually advanced monotonic clock (the tests' `Clock`), starting at
/// 1000.0 like the Python one.
#[derive(Debug)]
pub struct ManualClock {
    t: Mutex<f64>,
}

impl Default for ManualClock {
    fn default() -> Self {
        Self {
            t: Mutex::new(1000.0),
        }
    }
}

impl ManualClock {
    pub fn new() -> Arc<Self> {
        Arc::new(Self::default())
    }

    pub fn now(&self) -> f64 {
        *self.t.lock().unwrap()
    }

    pub fn set(&self, t: f64) {
        *self.t.lock().unwrap() = t;
    }

    pub fn advance(&self, seconds: f64) {
        *self.t.lock().unwrap() += seconds;
    }

    /// The `Clock` closure a service takes, reading this clock.
    pub fn clock(self: &Arc<Self>) -> Clock {
        let me = Arc::clone(self);
        Arc::new(move || me.now())
    }
}
