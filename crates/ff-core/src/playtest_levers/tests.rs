//! Ported from `tests/test_playtest_levers.py` (the lever cases; the board
//! cases live in `models::jobs::tests`). Every test drives the real world data
//! so a lever proven here works for a tester at the keyboard.

use super::*;
use crate::data::world::get_world;
use crate::sim::timezones::{city_zone, to_local};

/// The slice of GameContext the levers touch.
struct Ctx {
    world: &'static World,
    profile: Profile,
    saves: usize,
    playtest_sandbox: bool,
}

impl Ctx {
    fn new(profile: Profile) -> Self {
        Ctx {
            world: get_world(),
            profile,
            saves: 0,
            playtest_sandbox: false,
        }
    }
}

impl LeverContext for Ctx {
    fn world(&self) -> &World {
        self.world
    }
    fn profile_mut(&mut self) -> &mut Profile {
        &mut self.profile
    }
    fn set_playtest_sandbox(&mut self, sandbox: bool) {
        self.playtest_sandbox = sandbox;
    }
    fn save_profile(&mut self) {
        self.saves += 1;
    }
}

/// The lever environment variables are process-global; one test at a time.
static LEVER_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

struct Env {
    _guard: std::sync::MutexGuard<'static, ()>,
}

impl Env {
    fn clear() -> Self {
        let guard = LEVER_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        for name in [CITY_ENV, CLOCK_ENV, DEST_ENV, PERSIST_ENV] {
            std::env::remove_var(name);
        }
        Env { _guard: guard }
    }
    fn set(&self, name: &str, value: &str) {
        std::env::set_var(name, value);
    }
}

impl Drop for Env {
    fn drop(&mut self) {
        for name in [CITY_ENV, CLOCK_ENV, DEST_ENV, PERSIST_ENV] {
            std::env::remove_var(name);
        }
    }
}

fn parked_ctx() -> Ctx {
    Ctx::new(Profile::named_in("Lever Test", "denver_co_us"))
}

#[test]
fn test_no_levers_is_a_no_op() {
    let _env = Env::clear();
    let mut ctx = parked_ctx();

    let notes = apply_continue_levers(&mut ctx);

    assert!(notes.is_empty());
    assert_eq!(ctx.saves, 0);
    assert!(!ctx.playtest_sandbox);
}

#[test]
fn test_clock_env_parsing() {
    let env = Env::clear();
    for (raw, expected) in [("21", 21.0), ("21.5", 21.5), ("0", 0.0)] {
        env.set(CLOCK_ENV, raw);
        assert_eq!(forced_clock_hour(), Some(expected));
    }
    for raw in ["banana", "24", "-1", ""] {
        env.set(CLOCK_ENV, raw);
        assert_eq!(forced_clock_hour(), None, "{raw:?}");
    }
}

/// Owner design 2026-07-15: a lever run is temporary. The scenario plays in
/// memory, nothing saves, and the real career resumes untouched.
#[test]
fn test_force_city_relocates_into_a_sandbox_by_default() {
    let env = Env::clear();
    let mut ctx = Ctx::new(Profile::named_in("Lever Test", "Chicago"));
    ctx.profile.dispatch_board_cache = Some(serde_json::json!({"key": "stale"}));
    env.set(CITY_ENV, "denver_co_us");

    let notes = apply_continue_levers(&mut ctx);

    assert_eq!(ctx.profile.current_city, "denver_co_us");
    assert!(ctx.profile.dispatch_board_cache.is_none());
    assert!(ctx.playtest_sandbox);
    assert_eq!(ctx.saves, 0);
    assert!(notes.iter().any(|n| n.contains("relocated to Denver")));
    assert!(notes
        .iter()
        .any(|n| n.contains("No miles driven, no money changed")));
    assert!(notes.iter().any(|n| n.to_lowercase().contains("sandbox")));
}

#[test]
fn test_force_persist_makes_the_relocation_permanent() {
    let env = Env::clear();
    let mut ctx = Ctx::new(Profile::named_in("Lever Test", "Chicago"));
    env.set(CITY_ENV, "denver_co_us");
    env.set(PERSIST_ENV, "1");

    let notes = apply_continue_levers(&mut ctx);

    assert_eq!(ctx.profile.current_city, "denver_co_us");
    assert!(!ctx.playtest_sandbox);
    assert_eq!(ctx.saves, 1);
    assert!(!notes.iter().any(|n| n.to_lowercase().contains("sandbox")));
}

#[test]
fn test_forced_dest_alone_still_sandboxes_a_parked_career() {
    let env = Env::clear();
    let mut ctx = parked_ctx();
    env.set(DEST_ENV, "silverthorne_co_us");

    let notes = apply_continue_levers(&mut ctx);

    assert!(ctx.playtest_sandbox);
    assert_eq!(ctx.saves, 0);
    assert!(notes.iter().any(|n| n.to_lowercase().contains("sandbox")));
}

#[test]
#[ignore = "needs app shell (App.shutdown honours ctx.playtest_sandbox)"]
fn test_quit_save_honors_the_playtest_sandbox() {}

#[test]
#[ignore = "needs app shell (GameContext.save_profile)"]
fn test_save_profile_honors_the_playtest_sandbox() {}

#[test]
fn test_force_city_refuses_mid_load() {
    let env = Env::clear();
    let mut ctx = Ctx::new(Profile::named_in("Lever Test", "Chicago"));
    ctx.profile.active_trip = Some(serde_json::json!({"kind": "pickup"}));
    env.set(CITY_ENV, "denver_co_us");

    let notes = apply_continue_levers(&mut ctx);

    assert_eq!(ctx.profile.current_city, "Chicago");
    assert_eq!(ctx.saves, 0);
    assert!(notes.iter().any(|n| n.contains("load in progress")));
}

/// Owner hit this live: PowerShell turns 'holbrook,az,us' into 'holbrook az
/// us', and commas are a natural way to type a slug anyway. Every reasonable
/// spelling lands on the canonical key.
#[test]
fn test_force_city_forgives_tester_spellings() {
    let env = Env::clear();
    for spelling in ["holbrook,az,us", "holbrook az us", "Holbrook, AZ, US"] {
        let mut ctx = parked_ctx();
        env.set(CITY_ENV, spelling);

        let notes = apply_continue_levers(&mut ctx);

        assert_eq!(ctx.profile.current_city, "holbrook_az_us", "{spelling}");
        assert!(
            notes.iter().any(|n| n.contains("relocated to Holbrook")),
            "{spelling}"
        );
    }
}

#[test]
fn test_force_city_unknown_city_stays_put() {
    let env = Env::clear();
    let mut ctx = parked_ctx();
    env.set(CITY_ENV, "atlantis");

    let notes = apply_continue_levers(&mut ctx);

    assert_eq!(ctx.profile.current_city, "denver_co_us");
    assert!(notes.iter().any(|n| n.contains("no city called atlantis")));
}

#[test]
fn test_force_city_already_there_speaks_only_the_sandbox_note() {
    let env = Env::clear();
    let mut ctx = parked_ctx();
    env.set(CITY_ENV, "denver_co_us");

    let notes = apply_continue_levers(&mut ctx);

    // No relocation happened, but the lever is set, so the session is
    // still a sandbox and must say so.
    assert!(notes.iter().all(|n| n.to_lowercase().contains("sandbox")));
    assert!(ctx.playtest_sandbox);
    assert_eq!(ctx.saves, 0);
}

#[test]
fn test_force_clock_advances_to_local_hour() {
    let env = Env::clear();
    let mut ctx = parked_ctx();
    ctx.profile.fatigue = 55.0;
    let zone = city_zone(ctx.world.city(&ctx.profile.current_city).unwrap());
    let before_local = to_local(ctx.profile.game_hours, zone).rem_euclid(24.0);
    let before_hours = ctx.profile.game_hours;
    env.set(CLOCK_ENV, "21");

    let notes = apply_continue_levers(&mut ctx);

    let p = &ctx.profile;
    assert!((to_local(p.game_hours, zone).rem_euclid(24.0) - 21.0).abs() < 1e-6);
    let delta = p.game_hours - before_hours;
    assert!((delta - (21.0 - before_local).rem_euclid(24.0)).abs() < 1e-6);
    assert!(delta > 0.0);
    assert!(notes.iter().any(|n| n.contains("clock moved forward")));
    // The clock only moves forward; a jump past a full break rests the driver.
    if delta >= 10.0 {
        assert_eq!(p.fatigue, 0.0);
        assert!(notes.iter().any(|n| n.contains("full break")));
    }
    // The wait shows in the logbook as off duty, not as vanished time.
    let segment = p.duty_log.segments.last().unwrap();
    assert_eq!(segment.status, "off_duty");
    assert!((segment.start_hour - before_hours).abs() < 1e-6);
    assert!((segment.end_hour - p.game_hours).abs() < 1e-6);
}

#[test]
fn test_force_clock_already_at_hour_speaks_only_the_sandbox_note() {
    let env = Env::clear();
    let mut ctx = parked_ctx();
    let zone = city_zone(ctx.world.city(&ctx.profile.current_city).unwrap());
    let local = to_local(ctx.profile.game_hours, zone).rem_euclid(24.0);
    env.set(CLOCK_ENV, &local.to_string());

    let notes = apply_continue_levers(&mut ctx);

    assert!(notes.iter().all(|n| n.to_lowercase().contains("sandbox")));
    assert_eq!(ctx.saves, 0);
}
