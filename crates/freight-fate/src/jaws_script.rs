//! The optional JAWS script that makes the arrow keys fast.
//!
//! JAWS binds the arrows to its own reading scripts in every application. In
//! the game they find no text, wait for the screen to change, and send the
//! key on about four times a second, so held arrows lag and menus answer
//! slowly. `tools/jaws/freightfate.jss` is a JAWS application script for
//! `freightfate.exe` that sends each arrow on at once. This module puts it
//! where JAWS looks, only when the player asks.
//!
//! What it touches, and nothing else: `freightfate.jss` and its compiled
//! `freightfate.jsb`, in the player's own settings folder of each JAWS
//! version that is installed (`%APPDATA%\Freedom Scientific\JAWS\<version>\
//! Settings\<language>`), so no administrator rights are needed. The script
//! is compiled with the `scompile.exe` that version ships, so the compiled
//! file always matches the JAWS that will load it. A file of that name that
//! is not ours (it does not open with our header line) is left alone.
//!
//! The work is a file write and a process launch, so it runs on a short-lived
//! thread and the game loop only drains the finished sentence.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

/// The script's source, built into the game so an install needs no files.
const SCRIPT: &str = include_str!("../../../tools/jaws/freightfate.jss");

/// The script is named after the executable, which is how JAWS finds it.
const STEM: &str = "freightfate";

/// The header every script of ours opens with; the mark of a file to touch.
const OURS: &str = "; Freight Fate:";

/// A compile that has not finished by now is stuck.
const COMPILE_TIMEOUT: Duration = Duration::from_secs(20);

/// One JAWS version's settings folder for one language, with the compiler
/// that version ships.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Target {
    pub dir: PathBuf,
    pub compiler: PathBuf,
}

/// What happened in one target.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Outcome {
    Installed,
    Removed,
    /// A script of that name exists and is not ours; nothing was changed.
    Foreign,
    Failed,
    /// Removing, and there was nothing of ours to remove.
    Absent,
}

fn jss(dir: &Path) -> PathBuf {
    dir.join(format!("{STEM}.jss"))
}

fn jsb(dir: &Path) -> PathBuf {
    dir.join(format!("{STEM}.jsb"))
}

fn is_ours(path: &Path) -> bool {
    fs::read_to_string(path).is_ok_and(|text| text.starts_with(OURS))
}

/// Every place a script can go: each JAWS version that has a settings folder
/// of the player's own AND an installed compiler, in each language folder
/// (three lowercase letters, like `enu`) it holds.
pub fn find_targets(user_root: &Path, program_roots: &[PathBuf]) -> Vec<Target> {
    let mut targets = Vec::new();
    let Ok(versions) = fs::read_dir(user_root) else {
        return targets;
    };
    for version in versions.flatten() {
        let compiler = program_roots
            .iter()
            .map(|root| root.join(version.file_name()).join("scompile.exe"))
            .find(|path| path.is_file());
        let Some(compiler) = compiler else { continue };
        let Ok(languages) = fs::read_dir(version.path().join("Settings")) else {
            continue;
        };
        for language in languages.flatten() {
            let name = language.file_name().to_string_lossy().into_owned();
            let is_language = name.len() == 3 && name.bytes().all(|b| b.is_ascii_lowercase());
            if is_language && language.path().is_dir() {
                targets.push(Target {
                    dir: language.path(),
                    compiler: compiler.clone(),
                });
            }
        }
    }
    targets.sort_by(|a, b| a.dir.cmp(&b.dir));
    targets
}

/// The real roots on this machine: the player's JAWS settings, and the two
/// Program Files folders JAWS may be installed under.
pub fn machine_targets() -> Vec<Target> {
    let Some(appdata) = std::env::var_os("APPDATA") else {
        return Vec::new();
    };
    let user_root = PathBuf::from(appdata)
        .join("Freedom Scientific")
        .join("JAWS");
    let program_roots: Vec<PathBuf> = ["ProgramFiles", "ProgramFiles(x86)"]
        .iter()
        .filter_map(std::env::var_os)
        .map(|root| PathBuf::from(root).join("Freedom Scientific").join("JAWS"))
        .collect();
    find_targets(&user_root, &program_roots)
}

/// Whether any target already holds our script.
pub fn is_installed(targets: &[Target]) -> bool {
    targets.iter().any(|t| is_ours(&jss(&t.dir)))
}

/// Compile `source` with `compiler`; true when it exited cleanly and left a
/// compiled file behind.
fn compile_with_scompile(compiler: &Path, source: &Path) -> bool {
    let mut command = Command::new(compiler);
    command
        .arg(source)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        use windows_sys::Win32::System::Threading::CREATE_NO_WINDOW;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    let Ok(mut child) = command.spawn() else {
        return false;
    };
    let started = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                return status.success() && source.parent().is_some_and(|dir| jsb(dir).is_file());
            }
            Ok(None) if started.elapsed() < COMPILE_TIMEOUT => {
                thread::sleep(Duration::from_millis(50));
            }
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                return false;
            }
        }
    }
}

/// Put the script in one target. `compile` is `scompile.exe` in real use.
pub fn install_in(
    target: &Target,
    script: &str,
    compile: &dyn Fn(&Path, &Path) -> bool,
) -> Outcome {
    let source = jss(&target.dir);
    if source.exists() && !is_ours(&source) {
        return Outcome::Foreign;
    }
    if fs::write(&source, script).is_err() {
        return Outcome::Failed;
    }
    if compile(&target.compiler, &source) {
        Outcome::Installed
    } else {
        // A script that would not compile is worse than none.
        let _ = fs::remove_file(&source);
        let _ = fs::remove_file(jsb(&target.dir));
        Outcome::Failed
    }
}

/// Take our script out of one target.
pub fn remove_from(target: &Target) -> Outcome {
    let source = jss(&target.dir);
    if !source.exists() {
        return Outcome::Absent;
    }
    if !is_ours(&source) {
        return Outcome::Foreign;
    }
    let gone = fs::remove_file(&source).is_ok();
    let _ = fs::remove_file(jsb(&target.dir));
    if gone {
        Outcome::Removed
    } else {
        Outcome::Failed
    }
}

/// The one sentence that says what a run did, for the player.
pub fn summary(installing: bool, outcomes: &[Outcome]) -> String {
    let done = outcomes
        .iter()
        .any(|o| matches!(o, Outcome::Installed | Outcome::Removed));
    if outcomes.is_empty() {
        return "No JAWS installation was found to change.".to_string();
    }
    if done {
        return if installing {
            "JAWS arrow keys are set to faster. JAWS loads the script when the game window \
             is next in front; restart JAWS if the arrows feel the same."
                .to_string()
        } else {
            "JAWS arrow keys are back to default.".to_string()
        };
    }
    if outcomes.iter().any(|o| matches!(o, Outcome::Foreign)) {
        return "A JAWS script named freightfate is already there and is not the game's, \
                so it was left alone."
            .to_string();
    }
    if outcomes.iter().all(|o| matches!(o, Outcome::Absent)) {
        return "There was no game script to remove.".to_string();
    }
    "The JAWS script could not be set up, so nothing was changed.".to_string()
}

fn run(installing: bool, targets: &[Target]) -> String {
    let outcomes: Vec<Outcome> = targets
        .iter()
        .map(|target| {
            if installing {
                install_in(target, SCRIPT, &compile_with_scompile)
            } else {
                remove_from(target)
            }
        })
        .collect();
    summary(installing, &outcomes)
}

const UNKNOWN: u8 = 0;
const INSTALLED: u8 = 1;
const DEFAULT: u8 = 2;

/// The Settings row's service: asks for an install or a removal, hands the
/// game loop the finished sentence, and remembers what is installed.
#[derive(Clone)]
pub struct JawsScript {
    announcements: Arc<Mutex<Vec<String>>>,
    busy: Arc<AtomicBool>,
    state: Arc<AtomicU8>,
}

impl Default for JawsScript {
    fn default() -> Self {
        Self::new()
    }
}

impl JawsScript {
    pub fn new() -> Self {
        Self {
            announcements: Arc::new(Mutex::new(Vec::new())),
            busy: Arc::new(AtomicBool::new(false)),
            state: Arc::new(AtomicU8::new(UNKNOWN)),
        }
    }

    /// Whether our script is installed for this player. Asked of the disk
    /// once, then kept current by [`request`](Self::request).
    pub fn installed(&self) -> bool {
        if self.state.load(Ordering::Relaxed) == UNKNOWN {
            let now = if is_installed(&machine_targets()) {
                INSTALLED
            } else {
                DEFAULT
            };
            self.state.store(now, Ordering::Relaxed);
        }
        self.state.load(Ordering::Relaxed) == INSTALLED
    }

    /// Install (or remove) on a worker thread. A second request while one is
    /// running is dropped: the player hears the first one's sentence.
    pub fn request(&self, install: bool) {
        if self.busy.swap(true, Ordering::AcqRel) {
            return;
        }
        let this = self.clone();
        let spawned = thread::Builder::new()
            .name("jaws-script".to_string())
            .spawn(move || {
                let targets = machine_targets();
                let line = run(install, &targets);
                this.state.store(
                    if is_installed(&targets) {
                        INSTALLED
                    } else {
                        DEFAULT
                    },
                    Ordering::Relaxed,
                );
                if let Ok(mut lines) = this.announcements.lock() {
                    lines.push(line);
                }
                this.busy.store(false, Ordering::Release);
            });
        if spawned.is_err() {
            self.busy.store(false, Ordering::Release);
        }
    }

    /// The sentences finished since the last call, oldest first.
    pub fn take_announcements(&self) -> Vec<String> {
        self.announcements
            .lock()
            .map(|mut lines| std::mem::take(&mut *lines))
            .unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn target_in(root: &Path) -> Target {
        let dir = root.join("2026").join("Settings").join("enu");
        fs::create_dir_all(&dir).unwrap();
        Target {
            dir,
            compiler: PathBuf::from("scompile.exe"),
        }
    }

    /// A compiler that succeeds by writing the compiled file.
    fn good_compile(_compiler: &Path, source: &Path) -> bool {
        fs::write(jsb(source.parent().unwrap()), b"compiled").is_ok()
    }

    #[test]
    fn the_shipped_script_carries_the_mark_that_lets_us_recognise_it() {
        assert!(SCRIPT.starts_with(OURS));
    }

    #[test]
    fn install_writes_and_compiles_and_remove_takes_only_our_files() {
        let root = tempfile::tempdir().unwrap();
        let target = target_in(root.path());
        fs::write(target.dir.join("DEFAULT.JCF"), "the player's own").unwrap();

        assert_eq!(
            install_in(&target, SCRIPT, &good_compile),
            Outcome::Installed
        );
        assert!(is_installed(std::slice::from_ref(&target)));
        assert!(jsb(&target.dir).is_file());

        assert_eq!(remove_from(&target), Outcome::Removed);
        assert!(!jss(&target.dir).exists() && !jsb(&target.dir).exists());
        assert!(target.dir.join("DEFAULT.JCF").is_file());
        assert_eq!(remove_from(&target), Outcome::Absent);
    }

    #[test]
    fn a_script_that_is_not_ours_is_never_overwritten_or_removed() {
        let root = tempfile::tempdir().unwrap();
        let target = target_in(root.path());
        fs::write(jss(&target.dir), "; somebody else's script\n").unwrap();

        assert_eq!(install_in(&target, SCRIPT, &good_compile), Outcome::Foreign);
        assert_eq!(remove_from(&target), Outcome::Foreign);
        assert_eq!(
            fs::read_to_string(jss(&target.dir)).unwrap(),
            "; somebody else's script\n"
        );
    }

    #[test]
    fn a_compile_that_fails_leaves_nothing_behind() {
        let root = tempfile::tempdir().unwrap();
        let target = target_in(root.path());
        assert_eq!(install_in(&target, SCRIPT, &|_, _| false), Outcome::Failed);
        assert!(!jss(&target.dir).exists() && !jsb(&target.dir).exists());
    }

    #[test]
    fn targets_need_a_settings_folder_and_a_compiler_and_a_language_folder() {
        let user = tempfile::tempdir().unwrap();
        let program = tempfile::tempdir().unwrap();
        // 2026: settings folder and compiler. 2025: settings, no compiler
        // (uninstalled). 2024: compiler, no settings folder of the player's.
        for version in ["2026", "2025"] {
            fs::create_dir_all(user.path().join(version).join("Settings").join("enu")).unwrap();
        }
        fs::create_dir_all(user.path().join("2026").join("Settings").join("Sounds")).unwrap();
        fs::create_dir_all(user.path().join("2024")).unwrap();
        for version in ["2026", "2024"] {
            let dir = program.path().join(version);
            fs::create_dir_all(&dir).unwrap();
            fs::write(dir.join("scompile.exe"), b"").unwrap();
        }
        let found = find_targets(user.path(), &[program.path().to_path_buf()]);
        assert_eq!(found.len(), 1);
        assert!(found[0].dir.ends_with("Settings/enu") || found[0].dir.ends_with("Settings\\enu"));
        assert!(found[0].compiler.ends_with("scompile.exe"));
    }

    #[test]
    fn the_summary_says_what_happened_in_plain_words() {
        assert!(summary(true, &[]).starts_with("No JAWS installation"));
        assert!(summary(true, &[Outcome::Installed]).contains("faster"));
        assert!(summary(false, &[Outcome::Removed]).contains("default"));
        assert!(summary(true, &[Outcome::Foreign]).contains("left alone"));
        assert!(summary(true, &[Outcome::Failed]).contains("nothing was changed"));
        assert!(summary(false, &[Outcome::Absent]).contains("no game script"));
    }
}
