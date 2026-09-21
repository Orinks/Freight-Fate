//! `ff-invariants` -- write the catalog snapshot the orinks.net cloud-save
//! validator is built from.
//!
//! ```text
//! ff-invariants <output>
//! ff-invariants <output> --check
//! ```
//!
//! The Rust half of `tools/export_profile_integrity_invariants.py`, argument
//! for argument: a positional output path and `--check`, so whatever runs the
//! Python exporter today can run this instead with nothing else changed. The
//! bytes are identical -- `crates/ff-core/tests/profile_integrity_export.rs`
//! holds them against a committed fixture rendered by the Python side.
//!
//! Why this is a binary at all: the validator decides whether a submitted
//! career is arithmetically possible. If the shipped export ever drifts from
//! what the game awards, the validator either rejects honest players or
//! accepts impossible careers -- so the export has to come out of the same
//! constants the build awards from ([`CatalogInputs::current`]), through a
//! command the release pipeline actually runs, not out of a test fixture.
//!
//! It is its own binary rather than a mode of `ff-bake` because the two write
//! different artifacts for different consumers: `ff-bake` packs the world
//! data the game reads, this renders a small file a server reads. Sharing
//! `--data-dir` would have been the only thing they shared, and `ff-bake`'s
//! `--out` semantics (a directory means `world.ffdata` inside it) are wrong
//! for a file with no fixed name.

use std::path::PathBuf;
use std::process::ExitCode;

use ff_core::profile_integrity_invariants::{rendered_invariants, world_data_root, CatalogInputs};

const USAGE: &str = "\
usage: ff-invariants <output> [--data-dir <dir>] [--check] [--quiet]

  <output>          where to write the invariants JSON
  --data-dir <dir>  the package data folder (src/freight_fate/data); the
                    shipped data root is used when this is not given
  --check           do not write: re-render and compare bytes with <output>
  --quiet           suppress the summary line
";

struct Args {
    out: PathBuf,
    data_dir: Option<PathBuf>,
    check: bool,
    quiet: bool,
}

fn parse_args() -> Result<Args, String> {
    let mut out: Option<PathBuf> = None;
    let mut data_dir: Option<PathBuf> = None;
    let mut check = false;
    let mut quiet = false;
    let mut argv = std::env::args().skip(1);
    while let Some(arg) = argv.next() {
        match arg.as_str() {
            "--data-dir" => {
                data_dir = Some(PathBuf::from(
                    argv.next().ok_or("--data-dir needs a directory")?,
                ));
            }
            "--check" => check = true,
            "--quiet" => quiet = true,
            "-h" | "--help" => return Err(USAGE.to_string()),
            other if other.starts_with("--") => {
                return Err(format!("unknown argument {other}\n\n{USAGE}"))
            }
            other => {
                if out.is_some() {
                    return Err(format!("unexpected second output path {other}\n\n{USAGE}"));
                }
                out = Some(PathBuf::from(other));
            }
        }
    }
    let out = out.ok_or_else(|| format!("an output path is required\n\n{USAGE}"))?;
    Ok(Args {
        out,
        data_dir,
        check,
        quiet,
    })
}

/// Compare ignoring line endings.
///
/// This writer emits LF on every platform, because the file is an artifact
/// that must not depend on who ran the export. The Python exporter does not:
/// `Path.write_text` translates newlines, so the same catalogs come out CRLF
/// on Windows and LF on Linux. The two files carry identical JSON and the
/// validator parses either, so `--check` must not call a Python-written file
/// stale over an invisible difference -- it is looking for a *catalog* that
/// moved. (Python's own `--check` is already newline-blind: `read_text`
/// translates on the way back in.)
fn same_content(left: &str, right: &str) -> bool {
    left.replace("\r\n", "\n") == right.replace("\r\n", "\n")
}

/// The first key whose rendered block differs, for a `--check` failure that
/// names the drift instead of only reporting it.
fn first_differing_key(existing: &str, fresh: &str) -> Option<String> {
    let key_of = |line: &str| -> Option<String> {
        let trimmed = line.trim_start();
        // Top-level keys sit at exactly two spaces of indent.
        if line.len() - trimmed.len() != 2 || !trimmed.starts_with('"') {
            return None;
        }
        trimmed[1..]
            .split_once("\":")
            .map(|(key, _)| key.to_string())
    };
    let mut key = None;
    for (left, right) in existing.lines().zip(fresh.lines()) {
        if let Some(found) = key_of(left) {
            key = Some(found);
        }
        if left != right {
            return key;
        }
    }
    key
}

fn run(args: &Args) -> Result<(), String> {
    let data_root = match &args.data_dir {
        Some(dir) => dir.join("world_data"),
        None => world_data_root(),
    };
    if !data_root.is_dir() {
        return Err(format!(
            "{} is not a directory -- point --data-dir at the package data folder",
            data_root.display()
        ));
    }
    let content = rendered_invariants(&data_root, &CatalogInputs::current())?;
    if args.check {
        let existing = std::fs::read_to_string(&args.out).map_err(|err| {
            format!(
                "{}: {err} (export it first, then --check)",
                args.out.display()
            )
        })?;
        if same_content(&existing, &content) {
            if !args.quiet {
                println!("{} matches the shipped catalogs", args.out.display());
            }
            return Ok(());
        }
        let existing = existing.replace("\r\n", "\n");
        let named = first_differing_key(&existing, &content)
            .map(|key| format!(" first difference under \"{key}\";"))
            .unwrap_or_default();
        return Err(format!(
            "{} is stale:{named} {} bytes on disk, {} bytes from the catalogs. Re-export it.",
            args.out.display(),
            existing.len(),
            content.len()
        ));
    }
    if let Some(parent) = args.out.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)
                .map_err(|err| format!("cannot create {}: {err}", parent.display()))?;
        }
    }
    std::fs::write(&args.out, content.as_bytes())
        .map_err(|err| format!("cannot write {}: {err}", args.out.display()))?;
    if !args.quiet {
        println!("{} bytes -> {}", content.len(), args.out.display());
    }
    Ok(())
}

fn main() -> ExitCode {
    let args = match parse_args() {
        Ok(args) => args,
        Err(message) => {
            eprintln!("{message}");
            return ExitCode::FAILURE;
        }
    };
    match run(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("ff-invariants: {message}");
            ExitCode::FAILURE
        }
    }
}
