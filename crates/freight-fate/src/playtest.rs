//! The headless playtest harness and the drive tools (port of
//! `tests/playtest_harness.py`, `tools/playtest_break.py`,
//! `tools/playtest_road.py` and `tools/playtest_sandbox.py`).
//!
//! # Why this lives in the library
//!
//! The Python harness sat beside the tests, and the tools imported it by
//! putting `tests/` on `sys.path`. Rust has no such back door: an
//! integration test cannot reach another integration test's code, and the
//! `freightfate` binary cannot reach either. The 119 transcript test files
//! and the `--break-scenario` battery drive exactly the same rig, so the rig
//! is a library module both can `use`.
//!
//! * [`harness`] -- [`PlaytestHarness`], [`PlaytestResult`], the transcript
//!   assertions. This is what a transcript test codes against.
//! * [`menu`] -- reading and driving a menu without knowing its type.
//! * [`sandbox`] -- the throwaway data directory a manual playtest is
//!   reckless in (`tools/playtest_sandbox.py`).
//! * [`road`] -- find a road feature and hand over the wheel at it
//!   (`tools/playtest_road.py`).
//! * [`breaker`] -- the adversarial battery's rig and registry
//!   (`tools/playtest_break.py`), with the scenarios in
//!   [`break_scenarios`].
//!
//! Everything here runs headless and isolated unless a caller deliberately
//! asks for a window: dummy SDL drivers, no speech, and a throwaway
//! `FREIGHT_FATE_DATA_DIR` so the operator's real settings, saves and
//! keyring are never touched.

pub mod break_scenarios;
pub mod breaker;
pub mod harness;
pub mod menu;
pub mod observer;
pub mod road;
pub mod sandbox;

pub use breaker::{run_scenario, scenario_names, scenarios, Outcome, Rig, RigOptions, Verdict};
pub use harness::{key_event, PlaytestHarness, PlaytestResult, RouteSetup, StartDelivery};
pub use menu::{menu_labels_of, menu_rows};

/// The harness's own copy of the conversion the Python modules spelled out
/// at every call site.
pub const MPH_PER_MPS: f64 = 2.23694;
