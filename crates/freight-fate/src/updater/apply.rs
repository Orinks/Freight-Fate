//! Download, unpack and apply an update: the archive handling, the
//! detached apply scripts (the exact `.bat` / `.sh` templates) and their
//! spawn. Re-exported from `crate::updater`.

use std::fs;
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

use super::{
    install_target_in, running_appimage_path, Platform, UpdateInfo, UpdaterEnv, APP_NAME,
    USER_AGENT,
};
use crate::net::{self, NetError, Tier};

/// Why a download stopped short.
#[derive(Debug)]
pub enum DownloadError {
    /// `UpdateCancelled`: the player backed out.
    Cancelled,
    Net(NetError),
    Io(io::Error),
}

impl std::fmt::Display for DownloadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DownloadError::Cancelled => f.write_str("update cancelled"),
            DownloadError::Net(e) => write!(f, "{e}"),
            DownloadError::Io(e) => write!(f, "{e}"),
        }
    }
}

impl std::error::Error for DownloadError {}

impl From<NetError> for DownloadError {
    fn from(e: NetError) -> Self {
        DownloadError::Net(e)
    }
}

impl From<io::Error> for DownloadError {
    fn from(e: io::Error) -> Self {
        DownloadError::Io(e)
    }
}

/// Fetch the release archive into `dest_dir`.
///
/// `progress(done_bytes, total_bytes)` is called as data arrives;
/// `cancelled` is checked between chunks.
pub fn download(
    info: &UpdateInfo,
    dest_dir: &Path,
    mut progress: Option<&mut dyn FnMut(u64, u64)>,
    cancelled: Option<&AtomicBool>,
) -> Result<PathBuf, DownloadError> {
    let dest = dest_dir.join(&info.asset_name);
    let mut response = net::agent(Tier::GitHub)
        .get(&info.asset_url)
        .header("User-Agent", USER_AGENT)
        .call()
        .map_err(NetError::from)?;
    let status = response.status().as_u16();
    if status >= 400 {
        return Err(NetError::http(status).into());
    }
    let total = response
        .headers()
        .get("content-length")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.trim().parse::<u64>().ok())
        .filter(|n| *n > 0)
        .unwrap_or(info.asset_size.max(0) as u64);
    let mut file = fs::File::create(&dest)?;
    let mut reader = response.body_mut().as_reader();
    let mut buf = vec![0u8; 65536];
    let mut done: u64 = 0;
    loop {
        if cancelled.is_some_and(|flag| flag.load(Ordering::SeqCst)) {
            return Err(DownloadError::Cancelled);
        }
        let n = reader.read(&mut buf)?;
        if n == 0 {
            break;
        }
        file.write_all(&buf[..n])?;
        done += n as u64;
        if let Some(progress) = progress.as_deref_mut() {
            progress(done, total);
        }
    }
    file.flush()?;
    Ok(dest)
}

/// Unpack the release archive; returns the new app folder inside it.
pub fn extract(archive: &Path, staging: &Path, env: &UpdaterEnv) -> io::Result<PathBuf> {
    fs::create_dir_all(staging)?;
    let name = archive
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default();
    if name.ends_with(".tar.gz") {
        let file = fs::File::open(archive)?;
        let decoder = flate2::read::GzDecoder::new(file);
        let mut tar = tar::Archive::new(decoder);
        tar.set_preserve_permissions(true);
        tar.unpack(staging)?;
    } else if env.platform == Platform::MacOs {
        // ditto preserves the executable bits and bundle symlinks that a
        // plain unzip would drop
        let status = Command::new("ditto")
            .args(["-x", "-k"])
            .arg(archive)
            .arg(staging)
            .status()?;
        if !status.success() {
            return Err(io::Error::other(format!("ditto failed: {status}")));
        }
    } else {
        let file = fs::File::open(archive)?;
        let mut zip = zip::ZipArchive::new(file)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
        zip.extract(staging)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
    }
    extracted_root(staging, &name, env)
}

/// The new app folder inside an unpacked archive.
///
/// Windows and Linux archives hold a plain `FreightFate` folder; the
/// macOS archive holds the `FreightFate.app` bundle (`ditto
/// --keepParent` in `tools/build_release.py`).
pub fn extracted_root(staging: &Path, archive_name: &str, env: &UpdaterEnv) -> io::Result<PathBuf> {
    if env.platform == Platform::MacOs {
        let bundle = staging.join(format!("{APP_NAME}.app"));
        if bundle.is_dir() {
            return Ok(bundle);
        }
    }
    let new_root = staging.join(APP_NAME);
    if !new_root.is_dir() {
        let archive_name = if archive_name.is_empty() {
            "the archive"
        } else {
            archive_name
        };
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            format!("{APP_NAME} folder missing from {archive_name}"),
        ));
    }
    Ok(new_root)
}

/// `tempfile.mkdtemp(prefix="freightfate-update-")`.
pub fn make_staging_dir() -> io::Result<PathBuf> {
    let base = std::env::temp_dir();
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    for attempt in 0..100u32 {
        let dir = base.join(format!(
            "{}-update-{}-{nanos}-{attempt}",
            APP_NAME.to_ascii_lowercase(),
            std::process::id()
        ));
        match fs::create_dir(&dir) {
            Ok(()) => return Ok(dir),
            Err(e) if e.kind() == io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(e),
        }
    }
    Err(io::Error::other("could not create a staging directory"))
}

/// The runnable update staged from a downloaded release asset.
///
/// An .AppImage download IS the update -- one file, nothing to unpack.
/// Archives unpack into the staging dir and yield the new app folder.
pub fn stage_update(archive: &Path, staging: &Path, env: &UpdaterEnv) -> io::Result<PathBuf> {
    if path_name(archive).ends_with(".AppImage") {
        return Ok(archive.to_path_buf());
    }
    let new_root = extract(archive, &staging.join("unpacked"), env)?;
    match fs::remove_file(archive) {
        Ok(()) => {}
        Err(e) if e.kind() == io::ErrorKind::NotFound => {}
        Err(e) => return Err(e),
    }
    Ok(new_root)
}

fn path_name(path: &Path) -> String {
    path.file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default()
}

fn dir_writable(path: &Path) -> bool {
    let probe = path.join(format!(".{}-update-probe", APP_NAME.to_ascii_lowercase()));
    if fs::write(&probe, b"").is_err() {
        return false;
    }
    fs::remove_file(&probe).is_ok()
}

/// Whether `apply_and_restart` can install this staged update by itself.
///
/// False means the player must finish the install manually: an AppImage
/// swap needs the .AppImage's own folder to be writable, and a folder
/// update can never be applied to an AppImage run -- the mounted payload
/// is read-only and disposable; the .AppImage file is the install.
pub fn can_auto_apply(new_root: &Path, env: &UpdaterEnv) -> bool {
    let appimage = running_appimage_path(env.appimage.as_deref());
    if path_name(new_root).ends_with(".AppImage") && new_root.is_file() {
        return appimage
            .as_deref()
            .and_then(Path::parent)
            .is_some_and(dir_writable);
    }
    appimage.is_none()
}

/// Park an update that needs a manual install somewhere describable.
///
/// The staging dir lives under the system temp folder; a single-file
/// update moves to the home folder instead, so the spoken location is
/// one the player can find again (and that survives a reboot). Folder
/// updates stay where they were unpacked.
pub fn stash_for_manual_install(new_root: &Path, home: Option<&Path>) -> PathBuf {
    if !new_root.is_file() {
        return new_root.to_path_buf();
    }
    let Some(home) = home else {
        return new_root.to_path_buf();
    };
    let dest = home.join(path_name(new_root));
    let moved = (|| -> io::Result<()> {
        if dest.exists() {
            fs::remove_file(&dest)?;
        }
        match fs::rename(new_root, &dest) {
            Ok(()) => Ok(()),
            Err(_) => {
                // shutil.move across devices: copy then remove
                fs::copy(new_root, &dest)?;
                fs::remove_file(new_root)
            }
        }
    })();
    if moved.is_err() {
        return new_root.to_path_buf();
    }
    dest
}

const WINDOWS_SCRIPT: &str = r#"@echo off
:wait
tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL
if not errorlevel 1 (
  ping -n 2 127.0.0.1 >NUL
  goto wait
)
robocopy "{src}\_internal" "{dst}\_internal" /MIR /R:10 /W:1 >NUL
robocopy "{src}" "{dst}" /E /XD _internal saves /R:10 /W:1 >NUL
start "" "{dst}\{exe}"
rmdir /s /q "{staging}"
del "%~f0"
"#;

const POSIX_SCRIPT: &str = r#"#!/bin/sh
# Keep portable saves under {dst}/saves intact even if a bad archive includes
# a top-level saves folder.
while kill -0 {pid} 2>/dev/null; do sleep 1; done
rm -rf "{dst}/_internal"
rm -rf "{src}/saves"
cp -a "{src}/." "{dst}/"
rm -rf "{staging}"
"{dst}/{exe}" &
rm -f "$0"
"#;

const APPIMAGE_SCRIPT: &str = r#"#!/bin/sh
# Swap the .AppImage file itself; the mounted payload it runs from is
# read-only (or a throwaway extraction) and must never be touched. The
# new file is staged next to the target so the final rename is atomic,
# and the relaunch runs the new AppImage, whose own AppRun rebuilds the
# library search path.
while kill -0 {pid} 2>/dev/null; do sleep 1; done
cp "{src}" "{dst}.update-new" || exit 1
chmod +x "{dst}.update-new"
mv -f "{dst}.update-new" "{dst}" || exit 1
rm -rf "{staging}"
"{dst}" &
rm -f "$0"
"#;

const MACOS_SCRIPT: &str = r#"#!/bin/sh
# Swap the whole app bundle. Saves live in ~/Library/Application Support,
# never inside the bundle. The old bundle is parked beside the install until
# the new one is in place, so a failed copy cannot leave the player with no
# game at all.
while kill -0 {pid} 2>/dev/null; do sleep 1; done
rm -rf "{dst}.old"
mv "{dst}" "{dst}.old"
if mv "{src}" "{dst}" 2>/dev/null || cp -R "{src}" "{dst}"; then
  rm -rf "{dst}.old"
else
  mv "{dst}.old" "{dst}"
fi
rm -rf "{staging}"
open "{dst}"
rm -f "$0"
"#;

/// The helper script that swaps in the update once the game exits.
pub fn write_apply_script(
    new_root: &Path,
    install: &Path,
    staging: &Path,
    pid: u32,
    env: &UpdaterEnv,
) -> io::Result<PathBuf> {
    let windows = env.platform == Platform::Windows;
    let exe = format!("{APP_NAME}{}", if windows { ".exe" } else { "" });
    let template = if path_name(new_root).ends_with(".AppImage") {
        // install is the running .AppImage file itself, not a folder.
        APPIMAGE_SCRIPT
    } else if windows {
        WINDOWS_SCRIPT
    } else if env.platform == Platform::MacOs && install.extension().is_some_and(|e| e == "app") {
        MACOS_SCRIPT
    } else {
        POSIX_SCRIPT
    };
    let text = template
        .replace("{pid}", &pid.to_string())
        .replace("{src}", &new_root.display().to_string())
        .replace("{dst}", &install.display().to_string())
        .replace("{staging}", &staging.display().to_string())
        .replace("{exe}", &exe);
    let suffix = if windows { ".bat" } else { ".sh" };
    let parent = staging.parent().unwrap_or(staging);
    let script = parent.join(format!(
        "{}-apply-{pid}{suffix}",
        APP_NAME.to_ascii_lowercase()
    ));
    fs::write(&script, text)?;
    #[cfg(unix)]
    if !windows {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&script, fs::Permissions::from_mode(0o755))?;
    }
    Ok(script)
}

/// [`apply_and_restart`] with the spawn injected: `spawn` receives the
/// command line (`cmd /c script` or `/bin/sh script`). Returns the script
/// path, or `None` when an AppImage update was refused because this is not
/// an AppImage run.
pub fn apply_and_restart_with(
    new_root: &Path,
    staging: &Path,
    env: &UpdaterEnv,
    spawn: &mut dyn FnMut(Vec<String>) -> io::Result<()>,
) -> io::Result<Option<PathBuf>> {
    let install = if path_name(new_root).ends_with(".AppImage") {
        match running_appimage_path(env.appimage.as_deref()) {
            Some(path) => path,
            None => {
                log::warn!(
                    "Not an AppImage run; cannot swap {} in place",
                    new_root.display()
                );
                return Ok(None);
            }
        }
    } else {
        install_target_in(env)
    };
    let script = write_apply_script(new_root, &install, staging, env.pid, env)?;
    let command = if env.platform == Platform::Windows {
        vec![
            "cmd".to_string(),
            "/c".to_string(),
            script.display().to_string(),
        ]
    } else {
        vec!["/bin/sh".to_string(), script.display().to_string()]
    };
    spawn(command)?;
    log::info!("Update staged; apply script {} spawned", script.display());
    Ok(Some(script))
}

/// Spawn the detached apply script. The caller must then quit the game;
/// the script waits for this process to exit before touching files.
pub fn apply_and_restart(new_root: &Path, staging: &Path) -> io::Result<()> {
    let env = UpdaterEnv::current();
    apply_and_restart_with(new_root, staging, &env, &mut spawn_detached).map(|_| ())
}

/// `subprocess.Popen(..., detached)`: no window, no inherited handles, its
/// own process group.
fn spawn_detached(command: Vec<String>) -> io::Result<()> {
    let (program, args) = command
        .split_first()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "empty command"))?;
    let mut cmd = Command::new(program);
    cmd.args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        use windows_sys::Win32::System::Threading::{CREATE_NEW_PROCESS_GROUP, CREATE_NO_WINDOW};
        cmd.creation_flags(CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP);
    }
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        // start_new_session=True
        cmd.process_group(0);
    }
    cmd.spawn().map(|_| ())
}
