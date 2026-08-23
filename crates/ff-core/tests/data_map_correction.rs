//! The 2026-08-23 map-data correction, asked of the Rust side.
//!
//! `data_baked.rs` already proves the baked container says the same thing as
//! the JSON tree. What it cannot prove is that either says the RIGHT thing,
//! and the failure mode this file exists for is the quiet one: the Rust
//! client shipping an older world than the Python tree carries, which reaches
//! a tester as a Rust bug rather than as stale data.
//!
//! So these are three facts a driver would notice, each the visible end of
//! one repair in that correction, checked through the loaders the runtime
//! itself uses -- and checked against the baked container, because that is
//! what a tester actually runs.

use std::path::{Path, PathBuf};

use ff_core::data::baked::{bake, BAKED_FILE_NAME};
use ff_core::data::curves;
use ff_core::data::world::World;
use once_cell::sync::OnceCell;

/// Nothing published for a truck is advised above this.
const ADVISORY_CEILING_MPH: i64 = 80;

static BAKED_DIR: OnceCell<PathBuf> = OnceCell::new();

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .expect("repo root")
        .to_path_buf()
}

fn json_dir() -> PathBuf {
    repo_root().join("src").join("freight_fate").join("data")
}

/// Bake the shipped tree once and point the process at the container, so
/// every read below goes through the shipped path rather than the JSON one.
///
/// The data root is resolved ONCE per process, and the baker touches it on
/// the way past -- so the environment variable has to be set before the bake,
/// not after it, or the whole binary pins itself to the JSON tree and the
/// baked half of these checks quietly stops being baked. Nothing reads the
/// container in between: the baker takes both paths explicitly.
fn baked_dir() -> &'static Path {
    BAKED_DIR.get_or_init(|| {
        let temp = Box::leak(Box::new(
            tempfile::tempdir().expect("a temp dir for the baked container"),
        ));
        let dir = temp.path().to_path_buf();
        std::env::set_var("FREIGHT_FATE_DATA_ROOT", &dir);
        bake(&json_dir(), &dir.join(BAKED_FILE_NAME)).expect("bake");
        dir
    })
}

fn baked_world() -> World {
    // The fixture FIRST, and on its own line: `World::load` resolves the data
    // root, which happens once per process, so calling it before the fixture
    // has set the variable pins the whole binary to the JSON tree. Reading
    // `baked_dir()` only as the second half of the assertion below is exactly
    // that mistake, because the load has already happened by then.
    let expected = baked_dir();
    let world = World::load().expect("the baked world loads");
    assert_eq!(
        world.data_dir(),
        expected,
        "the process data root should be the baked container's directory"
    );
    world
}

/// The leg between two cities, whichever way round the shard stores it.
fn leg_between(world: &World, a: &str, b: &str) -> std::sync::Arc<ff_core::data::world_models::Leg> {
    world
        .neighbors(a)
        .iter()
        .find(|leg| leg.a == b || leg.b == b)
        .unwrap_or_else(|| panic!("no leg between {a} and {b}"))
        .clone()
}

#[test]
fn chicago_to_indianapolis_books_the_road_it_drives() {
    // 176 legs booked, timed and fuelled for less road than they cover; this
    // one gained two miles. A leg short of its own road pays short too.
    // The baked container first: it sets the process data root, and a JSON
    // load taken before that would fix the root at the JSON tree for the
    // whole process and leave `baked_world` reading the wrong place.
    for world in [
        baked_world(),
        World::load_from_json(&json_dir()).expect("the JSON world loads"),
    ] {
        let leg = leg_between(&world, "chicago_il_us", "indianapolis_in_us");
        assert_eq!(leg.miles, 185.0, "Chicago to Indianapolis");
    }
}

#[test]
fn hickory_to_charlotte_names_the_road_under_the_truck() {
    // Five legs announced an interstate they never touch. This one is driven
    // on NC-16 and used to say I-40.
    // The baked container first: it sets the process data root, and a JSON
    // load taken before that would fix the root at the JSON tree for the
    // whole process and leave `baked_world` reading the wrong place.
    for world in [
        baked_world(),
        World::load_from_json(&json_dir()).expect("the JSON world loads"),
    ] {
        let leg = leg_between(&world, "hickory_nc_us", "charlotte_nc_us");
        assert_eq!(leg.highway, "NC-16", "Hickory to Charlotte");
    }
}

#[test]
fn no_bend_is_advised_above_the_ceiling() {
    // Advisories read as high as 115 before the re-bake -- a bend "advising"
    // a speed no truck may legally drive is not advice, it is noise.
    let _ = baked_dir();
    let mut worst: Option<(String, i64)> = None;
    let mut records = 0usize;
    for (leg_key, rows) in curves::load() {
        for row in rows {
            records += 1;
            if worst.as_ref().is_none_or(|(_, mph)| row.advisory_mph > *mph) {
                worst = Some((leg_key.clone(), row.advisory_mph));
            }
        }
    }
    assert!(records > 1000, "only {records} curve records loaded");
    let (leg_key, mph) = worst.expect("at least one curve");
    assert!(
        mph <= ADVISORY_CEILING_MPH,
        "{leg_key} advises {mph} mph, above the {ADVISORY_CEILING_MPH} ceiling"
    );
}
