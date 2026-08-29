//! Port of `freight_fate/updater.py` — the in-game auto-updater.
//!
//! Checks GitHub releases for a newer build, downloads the right archive for
//! this platform, and swaps it in with a tiny detached helper script that waits
//! for the game to exit, copies the new files over the install folder, and
//! relaunches.
//!
//! Channels mirror the release pipeline: `stable` follows tagged releases
//! (`v1.6.0`), `dev` follows snapshot prereleases. Public 1.8 snapshots use
//! `nightly-YYYYMMDD`. Career 1.9 packaged builds on the same `dev` / snapshot
//! setting follow a distinct family, `1.9-tester-YYYYMMDD`, so a 1.9 tester is
//! never offered a 1.8 nightly and a 1.8 snapshot never picks a 1.9 tester.
//! The packaged build carries a `build_info.json` next to the executable
//! (written by `tools/build_release.py`) recording its tag, channel, and build
//! date; that is how a snapshot knows a newer snapshot exists even though the
//! project version number has not changed.
//!
//! The 1.8 `dev` channel is not a one-way nightly track: once dev work is
//! promoted to a stable release, the nightly that follows is content-identical.
//! So when a stable release is at least as new (by date) as the newest nightly,
//! 1.8 dev followers are steered onto stable instead of the equivalent nightly.
//! Career 1.9 snapshot updates skip that steering so a 1.9 tester cannot be
//! pulled onto a 1.8 stable.
//!
//! Updates only apply to frozen packaged builds. Source checkouts are managed
//! by git and the updater stays out of the way.
//!
//! Everything the Python module read off `sys` and `os.environ` (the
//! platform, the executable path, `APPIMAGE`, the home folder, the pid) is
//! gathered once into an [`UpdaterEnv`] so tests can fake any of it the way
//! the pytest suite monkeypatched `updater.sys`.

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use once_cell::sync::Lazy;
use regex::Regex;
use serde_json::Value;

use crate::net::{self, NetError, Tier};

pub const REPO: &str = "Orinks/Freight-fate";
pub const APP_NAME: &str = "FreightFate";
pub const API_BASE: &str = "https://api.github.com/repos/Orinks/Freight-fate";
pub const USER_AGENT: &str = "FreightFate-updater";
/// Seconds, per HTTP request.
pub const TIMEOUT: f64 = 15.0;
const RELEASE_PAGE_SIZE: usize = 100;
const MAX_RELEASE_PAGES: usize = 10;

pub const CHANNELS: [&str; 2] = ["stable", "dev"];

// -- the process environment ---------------------------------------------------

/// `sys.platform`, as the updater branches on it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Platform {
    Windows,
    MacOs,
    Linux,
    Other,
}

impl Platform {
    pub fn current() -> Self {
        if cfg!(target_os = "windows") {
            Platform::Windows
        } else if cfg!(target_os = "macos") {
            Platform::MacOs
        } else if cfg!(target_os = "linux") {
            Platform::Linux
        } else {
            Platform::Other
        }
    }
}

/// The process facts the updater reads: platform, executable path, the
/// `APPIMAGE` variable, the home folder, and the pid.
#[derive(Debug, Clone)]
pub struct UpdaterEnv {
    pub platform: Platform,
    /// `sys.executable`.
    pub executable: PathBuf,
    /// `os.environ.get("APPIMAGE")`.
    pub appimage: Option<String>,
    /// `Path.home()`.
    pub home: Option<PathBuf>,
    pub pid: u32,
}

impl UpdaterEnv {
    /// The real process.
    pub fn current() -> Self {
        Self {
            platform: Platform::current(),
            executable: std::env::current_exe().unwrap_or_default(),
            appimage: std::env::var("APPIMAGE").ok(),
            home: home_dir(),
            pid: std::process::id(),
        }
    }

    /// A fake environment for tests: the given platform and executable,
    /// no `APPIMAGE`, no home, pid 4242.
    pub fn fake(platform: Platform, executable: &Path) -> Self {
        Self {
            platform,
            executable: executable.to_path_buf(),
            appimage: None,
            home: None,
            pid: 4242,
        }
    }
}

fn home_dir() -> Option<PathBuf> {
    if cfg!(windows) {
        std::env::var_os("USERPROFILE").map(PathBuf::from)
    } else {
        std::env::var_os("HOME").map(PathBuf::from)
    }
}

// -- build identity ---------------------------------------------------------

/// What this running copy of the game is.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BuildInfo {
    /// "v1.5.0", "nightly-20260611", or "1.9-tester-20260828"
    pub tag: String,
    /// "stable" or "dev"
    pub channel: String,
    /// "2026-06-11" (UTC date); "" when unknown
    pub built_at: String,
}

impl BuildInfo {
    pub fn new(tag: &str, channel: &str, built_at: &str) -> Self {
        Self {
            tag: tag.to_string(),
            channel: channel.to_string(),
            built_at: built_at.to_string(),
        }
    }
}

/// True when running as a packaged build rather than a source checkout.
///
/// A packaged build is the `FreightFate` executable sitting beside its
/// `build_info.json` (or the shipped `freight_fate` data folder, or an
/// `_internal` folder from the older PyInstaller layout). A `cargo run`
/// binary in `target/` has none of those and stays a source checkout.
pub fn is_frozen_in(env: &UpdaterEnv) -> bool {
    let root = install_root_in(env);
    let exe_name = env
        .executable
        .file_stem()
        .map(|s| s.to_string_lossy().to_ascii_lowercase())
        .unwrap_or_default();
    exe_name == APP_NAME.to_ascii_lowercase()
        && (root.join("build_info.json").exists()
            || root.join("freight_fate").exists()
            || root.join("_internal").exists())
}

pub fn is_frozen() -> bool {
    is_frozen_in(&UpdaterEnv::current())
}

/// The folder holding the executable (and `_internal`).
pub fn install_root_in(env: &UpdaterEnv) -> PathBuf {
    let exe = fs::canonicalize(&env.executable).unwrap_or_else(|_| env.executable.clone());
    exe.parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."))
}

pub fn install_root() -> PathBuf {
    install_root_in(&UpdaterEnv::current())
}

/// What the apply script replaces: the enclosing `.app` bundle on
/// macOS (the executable sits in `Contents/MacOS` inside it), else the
/// folder holding the executable.
pub fn install_target_in(env: &UpdaterEnv) -> PathBuf {
    let root = install_root_in(env);
    if env.platform == Platform::MacOs {
        let mut cursor: Option<&Path> = Some(root.as_path());
        while let Some(dir) = cursor {
            if dir.extension().is_some_and(|ext| ext == "app") {
                return dir.to_path_buf();
            }
            cursor = dir.parent();
        }
    }
    root
}

pub fn install_target() -> PathBuf {
    install_target_in(&UpdaterEnv::current())
}

/// Read build_info.json from the install folder. Returns `None` when
/// running from source. Frozen builds that predate the stamp fall back to a
/// stable identity derived from the package version.
pub fn load_build_info_in(env: &UpdaterEnv, version: &str) -> Option<BuildInfo> {
    if !is_frozen_in(env) {
        return None;
    }
    let path = install_root_in(env).join("build_info.json");
    let data: Option<Value> = fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok());
    match data {
        Some(data) => Some(build_info_from_dict(&data, version)),
        None => Some(BuildInfo::new(&format!("v{version}"), "stable", "")),
    }
}

/// `(version asked for, the answer)` -- `lru_cache(maxsize=1)`.
type BuildInfoCache = Option<(String, Option<BuildInfo>)>;

static BUILD_INFO_CACHE: Lazy<Mutex<BuildInfoCache>> = Lazy::new(|| Mutex::new(None));

/// [`load_build_info_in`] for the real process; cached, since menu labels
/// ask every frame and the answer never changes mid-session.
pub fn load_build_info(version: &str) -> Option<BuildInfo> {
    let mut cache = BUILD_INFO_CACHE.lock().unwrap_or_else(|e| e.into_inner());
    if let Some((cached_version, info)) = cache.as_ref() {
        if cached_version == version {
            return info.clone();
        }
    }
    let info = load_build_info_in(&UpdaterEnv::current(), version);
    *cache = Some((version.to_string(), info.clone()));
    info
}

/// `str(value)` of a JSON scalar, `""` for null/missing, for the stamp's
/// loosely typed fields.
fn stamp_str(value: Option<&Value>) -> String {
    match value {
        None | Some(Value::Null) => String::new(),
        Some(Value::String(s)) => s.clone(),
        Some(Value::Bool(false)) => String::new(),
        Some(other) => crate::online_presence::py_str(other),
    }
}

/// Normalize a packaged build stamp, preserving useful partial data.
pub fn build_info_from_dict(data: &Value, version: &str) -> BuildInfo {
    let Value::Object(map) = data else {
        return BuildInfo::new(&format!("v{version}"), "stable", "");
    };
    let mut tag = stamp_str(map.get("tag"));
    if tag.is_empty() {
        tag = format!("v{version}");
    }
    let mut channel = stamp_str(map.get("channel"));
    if !CHANNELS.contains(&channel.as_str()) {
        channel = if snapshot_date_of(&tag).is_empty() {
            "stable".to_string()
        } else {
            "dev".to_string()
        };
    }
    BuildInfo {
        tag,
        channel,
        built_at: stamp_str(map.get("built_at")),
    }
}

/// The effective update channel: the player's explicit choice, else
/// whatever channel this build came from.
pub fn resolve_channel(setting: &str, build: Option<&BuildInfo>) -> String {
    if CHANNELS.contains(&setting) {
        return setting.to_string();
    }
    if let Some(build) = build {
        if CHANNELS.contains(&build.channel.as_str()) {
            return build.channel.clone();
        }
    }
    "stable".to_string()
}

// -- release discovery ------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UpdateInfo {
    /// release tag to install
    pub tag: String,
    /// spoken name, e.g. "Freight Fate version 1.6.0"
    pub title: String,
    /// release notes flattened to speakable lines
    pub notes: Vec<String>,
    pub asset_name: String,
    pub asset_url: String,
    /// bytes
    pub asset_size: i64,
}

/// `_api_get`: one GitHub API request on the updater's tier.
pub fn api_get(path: &str) -> Result<Value, NetError> {
    let headers = vec![
        ("User-Agent".to_string(), USER_AGENT.to_string()),
        (
            "Accept".to_string(),
            "application/vnd.github+json".to_string(),
        ),
    ];
    net::request_json(
        Tier::GitHub,
        Some("GET"),
        &format!("{API_BASE}{path}"),
        None,
        &headers,
    )
}

static NUMBERS: Lazy<Regex> = Lazy::new(|| Regex::new(r"\d+").unwrap());

/// `'v1.6.0' -> [1, 6, 0, 0]`; `'1.8.6.dev0' -> [1, 8, 6, -1, 0]`.
///
/// The trailing sentinel orders a `.devN` pre-release below the release
/// it works toward and above the previous stable, so dev checkouts and
/// nightlies are offered the stable they were promoted into. Unparseable
/// text compares lowest.
pub fn parse_version(text: &str) -> Vec<i64> {
    let (base, dev) = match text.split_once(".dev") {
        Some((base, dev)) => (base, Some(dev)),
        None => (text, None),
    };
    let nums: Vec<i64> = NUMBERS
        .find_iter(base)
        .filter_map(|m| m.as_str().parse().ok())
        .collect();
    if nums.is_empty() {
        return vec![0];
    }
    let mut parts = nums;
    match dev {
        Some(dev) => {
            parts.push(-1);
            parts.extend(
                NUMBERS
                    .find_iter(dev)
                    .filter_map(|m| m.as_str().parse::<i64>().ok()),
            );
        }
        None => parts.push(0),
    }
    parts
}

/// Player-facing wording for a version: '1.8.6.dev0' becomes
/// '1.8.6 development build' so spoken menus never read packaging jargon.
pub fn spoken_version(version: &str) -> String {
    match version.split_once(".dev") {
        Some((base, _)) => format!("{base} development build"),
        None => version.to_string(),
    }
}

pub const APPIMAGE_SUFFIX: &str = "-linux-x86_64.AppImage";
pub const TARBALL_SUFFIX: &str = "-linux-x64.tar.gz";

/// The .AppImage file this process is running from, or `None`.
///
/// The AppImage runtime exports `APPIMAGE` with the file's absolute path.
/// This must be checked before any executable-path heuristics: the payload
/// runs from a read-only mount (or a throwaway extraction) under the temp
/// directory, whose paths mislead directory-based logic.
pub fn running_appimage_path(appimage: Option<&str>) -> Option<PathBuf> {
    let raw = appimage?;
    if raw.is_empty() {
        return None;
    }
    let path = PathBuf::from(raw);
    if path.is_file() {
        Some(path)
    } else {
        None
    }
}

pub fn platform_suffix(env: &UpdaterEnv) -> &'static str {
    match env.platform {
        Platform::Windows => "-windows-portable.zip",
        Platform::MacOs => "-macos.zip",
        _ => {
            if running_appimage_path(env.appimage.as_deref()).is_some() {
                APPIMAGE_SUFFIX
            } else {
                TARBALL_SUFFIX
            }
        }
    }
}

/// The `(name, url, size)` of this platform's archive, or `None`.
pub fn pick_asset(
    release: &Value,
    suffix: Option<&str>,
    env: &UpdaterEnv,
) -> Option<(String, String, i64)> {
    let suffix = suffix.unwrap_or_else(|| platform_suffix(env));
    let assets = release.get("assets").and_then(Value::as_array)?;
    for asset in assets {
        let name = asset.get("name").and_then(Value::as_str).unwrap_or("");
        if name.ends_with(suffix) {
            let url = asset
                .get("browser_download_url")
                .and_then(Value::as_str)?
                .to_string();
            let size = asset
                .get("size")
                .map(|v| match v {
                    Value::Number(n) => n.as_f64().map(|f| f as i64).unwrap_or(0),
                    Value::String(s) => s.trim().parse().unwrap_or(0),
                    _ => 0,
                })
                .unwrap_or(0);
            return Some((name.to_string(), url, size));
        }
    }
    None
}

static HEADING: Lazy<Regex> = Lazy::new(|| Regex::new(r"^#{1,6}\s+").unwrap());
static BULLET: Lazy<Regex> = Lazy::new(|| Regex::new(r"^[-*+]\s+").unwrap());
static LINK: Lazy<Regex> = Lazy::new(|| Regex::new(r"\[([^\]]+)\]\([^)]*\)").unwrap());
static EMPHASIS: Lazy<Regex> = Lazy::new(|| Regex::new(r"(\*\*|__|\*|_|`)").unwrap());

/// Release-notes markdown as plain, speakable lines.
pub fn flatten_markdown(body: Option<&str>) -> Vec<String> {
    let mut lines = Vec::new();
    for raw in body.unwrap_or("").lines() {
        let line = raw.trim();
        if line.is_empty() || line.chars().all(|c| matches!(c, '-' | '=' | '*' | '_')) {
            continue;
        }
        let line = HEADING.replace(line, ""); // headings
        let line = BULLET.replace(&line, ""); // bullets
        let line = LINK.replace_all(&line, "$1"); // links
        let line = EMPHASIS.replace_all(&line, ""); // emphasis/code
        if !line.is_empty() {
            lines.push(line.into_owned());
        }
    }
    lines
}

static NIGHTLY: Lazy<Regex> = Lazy::new(|| Regex::new(r"^nightly-(\d{8})$").unwrap());
static TESTER_19: Lazy<Regex> = Lazy::new(|| Regex::new(r"^1\.9-tester-(\d{8})$").unwrap());

/// `'nightly-20260611' -> '20260611'`; `''` when not a nightly tag.
pub fn nightly_date(tag: &str) -> String {
    NIGHTLY
        .captures(tag)
        .map(|c| c[1].to_string())
        .unwrap_or_default()
}

/// `'1.9-tester-20260828' -> '20260828'`; `''` when not a Career 1.9 tester tag.
pub fn tester_19_date(tag: &str) -> String {
    TESTER_19
        .captures(tag)
        .map(|c| c[1].to_string())
        .unwrap_or_default()
}

/// YYYYMMDD from a `nightly-` or `1.9-tester-` tag; `''` when neither.
fn snapshot_date_of(tag: &str) -> String {
    let tester = tester_19_date(tag);
    if !tester.is_empty() {
        tester
    } else {
        nightly_date(tag)
    }
}

fn version_major_minor_is_19(text: &str) -> bool {
    let parts = parse_version(text);
    parts.first() == Some(&1) && parts.get(1) == Some(&9)
}

/// Career 1.9 binaries (package version 1.9, or already on a 1.9-tester tag)
/// follow `1.9-tester-YYYYMMDD` on the snapshot channel. Everyone else stays
/// on public `nightly-YYYYMMDD`.
fn is_career_19_line(current_version: &str, build: Option<&BuildInfo>) -> bool {
    if version_major_minor_is_19(current_version) {
        return true;
    }
    let Some(build) = build else {
        return false;
    };
    !tester_19_date(&build.tag).is_empty() || version_major_minor_is_19(&build.tag)
}

fn tag_name(release: &Value) -> String {
    release
        .get("tag_name")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string()
}

fn is_prerelease(release: &Value) -> bool {
    crate::online_presence::truthy(release.get("prerelease"))
}

fn pick_update_asset(release: &Value, env: &UpdaterEnv) -> Option<(String, String, i64)> {
    let mut asset = pick_asset(release, None, env);
    if asset.is_none() && running_appimage_path(env.appimage.as_deref()).is_some() {
        // Releases published before the AppImage existed ship only the
        // tarball; still offer the update. The download flow parks it for
        // a manual install (can_auto_apply is False) instead of hiding it.
        asset = pick_asset(release, Some(TARBALL_SUFFIX), env);
    }
    asset
}

fn update_from_release(release: &Value, title: &str, env: &UpdaterEnv) -> Option<UpdateInfo> {
    let (name, url, size) = pick_update_asset(release, env)?;
    Some(UpdateInfo {
        tag: tag_name(release),
        title: title.to_string(),
        notes: flatten_markdown(release.get("body").and_then(Value::as_str)),
        asset_name: name,
        asset_url: url,
        asset_size: size,
    })
}

pub fn stable_update_from(
    release: &Value,
    current_version: &str,
    env: &UpdaterEnv,
) -> Option<UpdateInfo> {
    let tag = tag_name(release);
    if parse_version(&tag) <= parse_version(current_version) {
        return None;
    }
    let title = format!("Freight Fate version {}", tag.trim_start_matches('v'));
    update_from_release(release, &title, env)
}

fn snapshot_tag_date(tag: &str, career_19: bool) -> String {
    if career_19 {
        tester_19_date(tag)
    } else {
        nightly_date(tag)
    }
}

fn snapshot_releases_newest_first<'a>(
    releases: &'a [Value],
    career_19: bool,
    env: &UpdaterEnv,
) -> Vec<&'a Value> {
    let mut snapshots: Vec<&Value> = releases
        .iter()
        .filter(|r| {
            is_prerelease(r)
                && !snapshot_tag_date(&tag_name(r), career_19).is_empty()
                && pick_update_asset(r, env).is_some()
        })
        .collect();
    snapshots.sort_by_key(|r| std::cmp::Reverse(snapshot_tag_date(&tag_name(r), career_19)));
    snapshots
}

/// The highest-versioned non-prerelease in the list, or `None`.
fn latest_stable_release(releases: &[Value]) -> Option<&Value> {
    releases
        .iter()
        .filter(|r| !is_prerelease(r) && parse_version(&tag_name(r)) > vec![0])
        .max_by(|a, b| parse_version(&tag_name(a)).cmp(&parse_version(&tag_name(b))))
}

/// A release's date as `YYYYMMDD`: the nightly tag date for snapshots,
/// else the `published_at` date for tagged releases; '' when unknown.
fn release_date(release: Option<&Value>) -> String {
    let Some(release) = release else {
        return String::new();
    };
    let from_tag = snapshot_date_of(&tag_name(release));
    if !from_tag.is_empty() {
        return from_tag;
    }
    let published = release_timestamp(Some(release));
    if published.is_empty() {
        String::new()
    } else {
        published.chars().take(10).filter(|c| *c != '-').collect()
    }
}

/// This build's date as `YYYYMMDD`: the nightly tag date, else the
/// stamped build date; '' when unknown.
fn build_date(build: Option<&BuildInfo>) -> String {
    let Some(build) = build else {
        return String::new();
    };
    let from_tag = snapshot_date_of(&build.tag);
    if !from_tag.is_empty() {
        from_tag
    } else {
        build.built_at.replace('-', "")
    }
}

/// A release's full `published_at` (ISO 8601, sortable as text); ''
/// when unknown. Dates alone cannot order a same-day stable and nightly,
/// and both orderings really happen: the 04:00 UTC cron nightly precedes
/// an afternoon promotion, but a small-hours stable precedes that same
/// cron -- which then carries fixes merged in between (v1.8.5.1 day,
/// 2026-07-23: stable 01:07, nightly 03:58 with two backports, and the
/// date tie hid the nightly from every dev-channel player).
fn release_timestamp(release: Option<&Value>) -> String {
    let Some(release) = release else {
        return String::new();
    };
    stamp_str(release.get("published_at"))
}

/// The running build's publish moment, recovered from its own release.
///
/// build_info carries only a date, so the release list is the one source
/// of intra-day ordering for the copy the player is on.
fn build_timestamp(
    build: Option<&BuildInfo>,
    releases: &[Value],
    stable: Option<&Value>,
) -> String {
    let Some(build) = build else {
        return String::new();
    };
    if let Some(stable) = stable {
        if tag_name(stable) == build.tag {
            return release_timestamp(Some(stable));
        }
    }
    for release in releases {
        if tag_name(release) == build.tag {
            return release_timestamp(Some(release));
        }
    }
    String::new()
}

/// Whether `release` (a stable build) is an upgrade for the running copy.
///
/// A stable build compares by version (two builds can share a date but differ
/// in version); a nightly build compares by publish timestamp when both are
/// known, else by date, since the version number is typically unchanged
/// across the dev-to-stable promotion.
fn stable_newer_than_build(
    release: &Value,
    build: Option<&BuildInfo>,
    build_date: &str,
    build_ts: &str,
) -> bool {
    let tag = tag_name(release);
    if let Some(build) = build {
        if tag == build.tag {
            return false;
        }
        if nightly_date(&build.tag).is_empty() {
            return parse_version(&tag) > parse_version(&build.tag);
        }
    }
    let stable_ts = release_timestamp(Some(release));
    if !build_ts.is_empty() && !stable_ts.is_empty() {
        return stable_ts.as_str() > build_ts;
    }
    let stable_date = release_date(Some(release));
    !(!build_date.is_empty() && !stable_date.is_empty() && stable_date.as_str() <= build_date)
}

fn snapshot_newer_than_build(
    release: &Value,
    build: Option<&BuildInfo>,
    build_date: &str,
    build_ts: &str,
) -> bool {
    let tag = tag_name(release);
    if let Some(build) = build {
        if tag == build.tag {
            return false;
        }
        let snapshot_ts = release_timestamp(Some(release));
        if !build_ts.is_empty() && !snapshot_ts.is_empty() {
            return snapshot_ts.as_str() > build_ts;
        }
        let snap_date = snapshot_date_of(&tag);
        if !build_date.is_empty() && !snap_date.is_empty() && snap_date.as_str() <= build_date {
            return false;
        }
    }
    true
}

fn spoken_ymd(date: &str) -> String {
    format!("{}-{}-{}", &date[..4], &date[4..6], &date[6..])
}

/// The update to offer a dev-channel player.
///
/// On public 1.8 builds this is the newest `nightly-YYYYMMDD` snapshot, with
/// the usual steer-to-stable once a promotion postdates that nightly. Career
/// 1.9 packaged builds on the same channel look only at `1.9-tester-YYYYMMDD`
/// prereleases: they must not land on a 1.8 nightly or a 1.8 stable.
/// `stable` is the latest stable release (from `/releases/latest`); when
/// omitted it is derived from `releases`. Pass `current_version` so a 1.9
/// binary is recognized even before it is stamped with a tester tag.
pub fn dev_update_from(
    releases: &[Value],
    build: Option<&BuildInfo>,
    stable: Option<&Value>,
    env: &UpdaterEnv,
) -> Option<UpdateInfo> {
    snapshot_update_from(releases, build, "", stable, env)
}

pub fn snapshot_update_from(
    releases: &[Value],
    build: Option<&BuildInfo>,
    current_version: &str,
    stable: Option<&Value>,
    env: &UpdaterEnv,
) -> Option<UpdateInfo> {
    let career_19 = is_career_19_line(current_version, build);
    let snapshots = snapshot_releases_newest_first(releases, career_19, env);
    let latest_snapshot = snapshots.first().copied();
    let stable = if career_19 {
        None
    } else {
        stable.or_else(|| latest_stable_release(releases))
    };

    let build_date = build_date(build);
    let build_ts = build_timestamp(build, releases, stable);
    let snapshot_date_s = release_date(latest_snapshot);
    let stable_date = release_date(stable);
    let snapshot_ts = release_timestamp(latest_snapshot);
    let stable_ts = release_timestamp(stable);

    // Timestamps order a same-day stable and nightly; dates alone cannot,
    // and a date tie wrongly favored a small-hours stable over the 04:00
    // nightly that carried fixes merged between them (2026-07-23).
    let stable_leads = if !snapshot_ts.is_empty() && !stable_ts.is_empty() {
        stable_ts >= snapshot_ts
    } else {
        !stable_date.is_empty() && stable_date >= snapshot_date_s
    };

    if let Some(stable) = stable {
        if stable_leads {
            if stable_newer_than_build(stable, build, &build_date, &build_ts) {
                let tag = tag_name(stable);
                let title = format!("Freight Fate version {}", tag.trim_start_matches('v'));
                return update_from_release(stable, &title, env);
            }
            return None; // already on the newest stable; nothing newer on dev
        }
    }

    if let Some(snapshot) = latest_snapshot {
        if snapshot_newer_than_build(snapshot, build, &build_date, &build_ts) {
            let date = snapshot_tag_date(&tag_name(snapshot), career_19);
            let spoken = spoken_ymd(&date);
            return update_from_release(snapshot, &snapshot_title(career_19, &spoken), env);
        }
    }
    None
}

fn snapshot_title(career_19: bool, spoken: &str) -> String {
    if career_19 {
        format!("Freight Fate 1.9 tester snapshot {spoken}")
    } else {
        format!("Freight Fate developer snapshot {spoken}")
    }
}

fn release_pages(api: &dyn Fn(&str) -> Result<Value, NetError>) -> Result<Vec<Value>, NetError> {
    let mut releases = Vec::new();
    for page in 1..=MAX_RELEASE_PAGES {
        let path = format!("/releases?per_page={RELEASE_PAGE_SIZE}&page={page}");
        let response = api(&path)?;
        let page_releases = response.as_array().cloned().unwrap_or_default();
        let exhausted = page_releases.len() < RELEASE_PAGE_SIZE;
        releases.extend(page_releases);
        if exhausted {
            break;
        }
    }
    Ok(releases)
}

/// Query GitHub for a newer release on `channel` through `api`
/// (`_api_get`, injectable). Network trouble is the error; `Ok(None)` means
/// already up to date.
pub fn check_for_update_with(
    channel: &str,
    current_version: &str,
    build: Option<&BuildInfo>,
    env: &UpdaterEnv,
    api: &dyn Fn(&str) -> Result<Value, NetError>,
) -> Result<Option<UpdateInfo>, NetError> {
    if channel == "dev" {
        // Snapshot families share the release list. Read bounded 100-item
        // pages so daily releases cannot hide the player's family, while the
        // latest stable stays on its dedicated endpoint.
        let releases = release_pages(api)?;
        let stable = if is_career_19_line(current_version, build) {
            None
        } else {
            match api("/releases/latest") {
                Ok(stable) => Some(stable),
                Err(NetError::Http { code: 404, .. }) => None, // no stable release published yet
                Err(e) => return Err(e),
            }
        };
        return Ok(snapshot_update_from(
            &releases,
            build,
            current_version,
            stable.as_ref(),
            env,
        ));
    }
    let release = match api("/releases/latest") {
        Ok(release) => release,
        Err(NetError::Http { code: 404, .. }) => return Ok(None), // no stable release published yet
        Err(e) => return Err(e),
    };
    Ok(stable_update_from(&release, current_version, env))
}

/// [`check_for_update_with`] over the real GitHub API and process.
pub fn check_for_update(
    channel: &str,
    current_version: &str,
    build: Option<&BuildInfo>,
) -> Result<Option<UpdateInfo>, NetError> {
    check_for_update_with(
        channel,
        current_version,
        build,
        &UpdaterEnv::current(),
        &api_get,
    )
}

mod apply;

pub use apply::{
    apply_and_restart, apply_and_restart_with, can_auto_apply, download, extract, extracted_root,
    make_staging_dir, stage_update, stash_for_manual_install, write_apply_script, DownloadError,
};
