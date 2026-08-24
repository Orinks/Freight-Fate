//! Shared helpers for the `data_*` integration tests: the session world and
//! the real data tree (`src/freight_fate/data`, resolved by walking up from
//! this crate's manifest directory, as the Python conftest did from the repo
//! root).
#![allow(dead_code)]

use std::path::{Path, PathBuf};

use ff_core::data::world::{get_world, World};
use ff_core::data::world_models::Route;

/// The Python package's `data/` folder in the source tree.
pub fn data_dir() -> PathBuf {
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    let dir = manifest
        .join("..")
        .join("..")
        .join("src")
        .join("freight_fate")
        .join("data");
    dir.canonicalize().unwrap_or(dir)
}

/// The shared world fixture (`conftest.world`).
pub fn world() -> &'static World {
    get_world()
}

/// `world.shortest_route(a, b)` that must exist.
pub fn shortest(world: &World, a: &str, b: &str) -> Route {
    world
        .shortest_route(a, b, None, false)
        .unwrap_or_else(|e| panic!("{a} -> {b}: {e}"))
        .unwrap_or_else(|| panic!("{a} -> {b}: no route"))
}

/// `world.supported_route(a, b)` that must exist.
pub fn supported(world: &World, a: &str, b: &str) -> Route {
    world
        .supported_route(a, b, None)
        .unwrap_or_else(|e| panic!("{a} -> {b}: {e}"))
        .unwrap_or_else(|| panic!("{a} to {b} is not dispatch-supported"))
}

/// Read and parse a JSON file under the data dir (BOM tolerant).
pub fn read_json(relative: &str) -> serde_json::Value {
    let path = data_dir().join(relative);
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(text.trim_start_matches('\u{feff}'))
        .unwrap_or_else(|e| panic!("{}: {e}", path.display()))
}
