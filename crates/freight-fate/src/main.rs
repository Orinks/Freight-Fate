//! `freightfate`: the game's entry point (`freight_fate/__main__.py`).
//!
//! Switches: `--smoke` (boot, render five frames, exit 0 -- the CI build
//! check), `--headless` (no window, no speech), `--controller-diagnostics`
//! (the two-layer controller logger, see `controller::diagnostics`).

fn main() {
    let options = freight_fate::app::CliOptions::parse(std::env::args().skip(1));
    std::process::exit(freight_fate::app::main_with(options));
}
