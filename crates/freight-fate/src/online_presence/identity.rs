//! Driver identity: the account-issued credentials, the platform secret
//! store behind the token, and the identity file on disk. Re-exported from
//! `crate::online_presence`.

use std::collections::HashMap;
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::Ordering;
use std::sync::{Arc, Mutex};

use serde_json::Value;

use crate::net::Headers;

// The name the driver token is filed under in the platform secret store. It is
// shown to the player if they ever browse Windows Credential Manager or the
// macOS Keychain, so it reads as a sentence, not a slug. Changing it strands
// every already-stored token, which then falls back to a re-paste.
pub const TOKEN_SERVICE: &str = "Freight Fate driver token";

/// The slice of the platform secret store the driver token needs. The
/// Python module patched its `keyring` attribute with a fake or `None`;
/// here the store is a trait object, and "no store at all" is `None`.
pub trait SecretStore: Send + Sync {
    fn set_password(&self, service: &str, user: &str, password: &str) -> Result<(), String>;
    fn get_password(&self, service: &str, user: &str) -> Result<Option<String>, String>;
    fn delete_password(&self, service: &str, user: &str) -> Result<(), String>;
}

/// The real platform store through the `keyring` crate: Windows Credential
/// Manager, the macOS Keychain, Secret Service on Linux.
#[derive(Debug, Default, Clone, Copy)]
pub struct KeyringStore;

impl SecretStore for KeyringStore {
    fn set_password(&self, service: &str, user: &str, password: &str) -> Result<(), String> {
        keyring::Entry::new(service, user)
            .and_then(|entry| entry.set_password(password))
            .map_err(|e| e.to_string())
    }

    fn get_password(&self, service: &str, user: &str) -> Result<Option<String>, String> {
        match keyring::Entry::new(service, user).and_then(|entry| entry.get_password()) {
            Ok(token) => Ok(Some(token)),
            Err(keyring::Error::NoEntry) => Ok(None),
            Err(e) => Err(e.to_string()),
        }
    }

    fn delete_password(&self, service: &str, user: &str) -> Result<(), String> {
        match keyring::Entry::new(service, user).and_then(|entry| entry.delete_credential()) {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(e) => Err(e.to_string()),
        }
    }
}

/// An in-memory stand-in for the platform secret store (the test suite's
/// `FakeKeyring`).
#[derive(Debug, Default)]
pub struct MemoryStore {
    passwords: Mutex<HashMap<(String, String), String>>,
}

impl MemoryStore {
    pub fn new() -> Arc<Self> {
        Arc::new(Self::default())
    }

    /// Every stored `(service, user) -> password`, for assertions.
    pub fn passwords(&self) -> HashMap<(String, String), String> {
        self.passwords.lock().unwrap().clone()
    }
}

impl SecretStore for MemoryStore {
    fn set_password(&self, service: &str, user: &str, password: &str) -> Result<(), String> {
        self.passwords.lock().unwrap().insert(
            (service.to_string(), user.to_string()),
            password.to_string(),
        );
        Ok(())
    }

    fn get_password(&self, service: &str, user: &str) -> Result<Option<String>, String> {
        Ok(self
            .passwords
            .lock()
            .unwrap()
            .get(&(service.to_string(), user.to_string()))
            .cloned())
    }

    fn delete_password(&self, service: &str, user: &str) -> Result<(), String> {
        self.passwords
            .lock()
            .unwrap()
            .remove(&(service.to_string(), user.to_string()));
        Ok(())
    }
}

/// The real headless-Linux shape: a store that answers, but every call
/// fails ("no recommended backend was available").
#[derive(Debug, Default, Clone, Copy)]
pub struct RefusingStore;

impl SecretStore for RefusingStore {
    fn set_password(&self, _: &str, _: &str, _: &str) -> Result<(), String> {
        Err("no recommended backend was available".to_string())
    }

    fn get_password(&self, _: &str, _: &str) -> Result<Option<String>, String> {
        Err("no recommended backend was available".to_string())
    }

    fn delete_password(&self, _: &str, _: &str) -> Result<(), String> {
        Err("no recommended backend was available".to_string())
    }
}

/// Whether this build can reach a platform secret store, and what it found.
///
/// In Python this checked that the compiled build still carried keyring's
/// backend entry points -- a failure nothing about playing would reveal. The
/// Rust build links its backends in at compile time, so the only question
/// left is whether this platform has one at all.
pub fn secret_store_report() -> (bool, String) {
    let expected = if cfg!(target_os = "windows") {
        Some("Windows")
    } else if cfg!(target_os = "macos") {
        Some("macOS")
    } else if cfg!(target_os = "linux") {
        Some("SecretService")
    } else {
        None
    };
    match expected {
        None => (
            true,
            format!(
                "no platform secret store is expected on {}",
                std::env::consts::OS
            ),
        ),
        Some(name) => (
            true,
            format!(
                "{name} backend is compiled into this build; the store in use is keyring::{name}"
            ),
        ),
    }
}

/// Account-issued credentials for posting presence.
///
/// Both values come from the Orinks activation flow: `driver_id` is public
/// (it names the profile page on Orinks); `driver_token` is the posting
/// secret, shown once at issuance, and never leaves this machine except
/// inside authenticated requests.
///
/// Only the public half is written to the identity file. The secret goes to
/// the platform store -- Windows Credential Manager, the macOS Keychain,
/// Secret Service or KWallet on Linux -- and only falls back to an
/// owner-only file beside it when the machine has no working store at all,
/// which is the normal state of a headless Linux box.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OnlineIdentity {
    pub driver_id: String,
    pub driver_token: String,
}

impl OnlineIdentity {
    pub fn new(driver_id: &str, driver_token: &str) -> Self {
        Self {
            driver_id: driver_id.to_string(),
            driver_token: driver_token.to_string(),
        }
    }

    /// `{"Authorization": "Bearer <token>"}`.
    pub fn auth_headers(&self) -> Headers {
        vec![(
            "Authorization".to_string(),
            format!("Bearer {}", self.driver_token),
        )]
    }
}

/// Where identities live and how they are stored: the data directory
/// (`online.json` and its `.token` fallback), the secret store, and the
/// process-lifetime token cache `OnlineIdentity._token_cache` kept.
///
/// Resolved tokens are cached by Driver ID for the life of the store. The
/// Online hub's menu labels call `load()` while the screen is drawn, so this
/// runs several times a frame; on Linux every miss would be a D-Bus round
/// trip to the keyring daemon. A hit also means the one-time migration has
/// already happened, so it is not retried on every frame either.
pub struct IdentityStore {
    data_dir: PathBuf,
    secret_store: Option<Arc<dyn SecretStore>>,
    token_cache: Mutex<HashMap<String, String>>,
    /// `os.name == "nt"` in Python: Windows refuses the plaintext fallback.
    plaintext_fallback_allowed: bool,
}

impl IdentityStore {
    /// A store over `data_dir` with the given secret store (`None` when the
    /// machine has no usable one at all).
    pub fn new(data_dir: &Path, secret_store: Option<Arc<dyn SecretStore>>) -> Self {
        Self {
            data_dir: data_dir.to_path_buf(),
            secret_store,
            token_cache: Mutex::new(HashMap::new()),
            plaintext_fallback_allowed: !cfg!(windows),
        }
    }

    /// The shipped configuration: the platform keyring over `data_dir`.
    pub fn platform(data_dir: &Path) -> Self {
        Self::new(data_dir, Some(Arc::new(KeyringStore)))
    }

    /// `OnlineIdentity.path()`: the public half on disk.
    pub fn path(&self) -> PathBuf {
        self.data_dir.join("online.json")
    }

    /// Where the token lives when no platform secret store answers.
    pub fn token_path(&self) -> PathBuf {
        self.data_dir.join("online.token")
    }

    /// Forget the process-lifetime token cache, as restarting the game would.
    pub fn clear_cache(&self) {
        self.token_cache.lock().unwrap().clear();
    }

    fn store_token(&self, driver_id: &str, token: &str) -> bool {
        let Some(store) = &self.secret_store else {
            return false;
        };
        match store.set_password(TOKEN_SERVICE, driver_id, token) {
            Ok(()) => true,
            Err(e) => {
                log::debug!("no usable secret store for the driver token: {e}");
                false
            }
        }
    }

    fn read_stored_token(&self, driver_id: &str) -> Option<String> {
        let store = self.secret_store.as_ref()?;
        match store.get_password(TOKEN_SERVICE, driver_id) {
            Ok(Some(token)) if !token.is_empty() => Some(token),
            Ok(_) => None,
            Err(e) => {
                log::debug!("could not read the driver token from the secret store: {e}");
                None
            }
        }
    }

    fn read_token_file(&self) -> Option<String> {
        let text = fs::read_to_string(self.token_path()).ok()?;
        let token = text.trim();
        if token.is_empty() {
            None
        } else {
            Some(token.to_string())
        }
    }

    fn write_identity_file(
        &self,
        identity: &OnlineIdentity,
        include_token: bool,
    ) -> io::Result<()> {
        let path = self.path();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let mut payload = serde_json::Map::new();
        payload.insert(
            "driver_id".to_string(),
            Value::from(identity.driver_id.as_str()),
        );
        if include_token {
            payload.insert(
                "driver_token".to_string(),
                Value::from(identity.driver_token.as_str()),
            );
        }
        let text = serde_json::to_string_pretty(&Value::Object(payload))
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
        // The fallback pair is one owner-only atomic record. Keeping the ID and
        // token together prevents a failed second write from mismatching them.
        let tmp = fresh_temp_path(&path);
        let result = (|| -> io::Result<()> {
            let mut opts = fs::OpenOptions::new();
            opts.write(true).create_new(true);
            #[cfg(unix)]
            {
                use std::os::unix::fs::OpenOptionsExt;
                opts.mode(0o600);
            }
            let mut file = opts.open(&tmp)?;
            file.write_all(text.as_bytes())?;
            file.sync_all()?;
            drop(file);
            fs::rename(&tmp, &path)
        })();
        if result.is_err() {
            let _ = fs::remove_file(&tmp);
        }
        result
    }

    fn remove_token_file(&self) {
        match fs::remove_file(self.token_path()) {
            Ok(()) => {}
            Err(e) if e.kind() == io::ErrorKind::NotFound => {}
            Err(e) => log::debug!("could not remove the fallback token file: {e}"),
        }
    }

    /// `OnlineIdentity.save()`.
    ///
    /// Makes the secret durable before removing a legacy plaintext copy from
    /// `online.json`. If neither destination works, the old file remains
    /// untouched and the player can retry without losing the one-time token.
    pub fn save(&self, identity: &OnlineIdentity) -> io::Result<()> {
        if self.store_token(&identity.driver_id, &identity.driver_token) {
            self.write_identity_file(identity, false)?;
            self.remove_token_file();
        } else {
            if !self.plaintext_fallback_allowed {
                return Err(io::Error::new(
                    io::ErrorKind::Unsupported,
                    "plaintext credential fallback is disabled on Windows",
                ));
            }
            self.write_identity_file(identity, true)?;
            self.remove_token_file();
        }
        self.token_cache
            .lock()
            .unwrap()
            .insert(identity.driver_id.clone(), identity.driver_token.clone());
        Ok(())
    }

    /// Move a token found outside the secret store into it.
    ///
    /// Builds before 1.8.7 wrote the token straight into `online.json`, and
    /// a machine with no store keeps it in `online.token`. Either way the
    /// first load that can do better cleans up after the old one, so nobody
    /// has to re-paste their credentials to get the safer storage.
    fn upgrade_storage(&self, identity: &OnlineIdentity, token_in_json: bool) {
        if token_in_json {
            if let Err(e) = self.save(identity) {
                log::debug!("could not move the driver token into the secret store: {e}");
            }
        } else if self.store_token(&identity.driver_id, &identity.driver_token) {
            self.remove_token_file();
        }
    }

    /// `OnlineIdentity.load()`: the stored identity, or `None` when there is
    /// none or it is malformed.
    pub fn load(&self) -> Option<OnlineIdentity> {
        let text = fs::read_to_string(self.path()).ok()?;
        let data: Value = serde_json::from_str(&text).ok()?;
        let driver_id = data.get("driver_id")?.as_str()?.to_string();
        let legacy_token = data
            .get("driver_token")
            .and_then(Value::as_str)
            .map(str::to_string);

        let cached = self.token_cache.lock().unwrap().get(&driver_id).cloned();
        let first_look = cached.is_none();
        let mut from_store = true;
        let driver_token = match cached {
            Some(token) => Some(token),
            None => {
                let mut token = self.read_stored_token(&driver_id);
                from_store = token.is_some();
                if token.is_none() {
                    token = self.read_token_file();
                }
                if token.is_none() {
                    token = legacy_token.clone();
                }
                token
            }
        };
        let driver_token = driver_token?;
        if driver_id.chars().count() < 8 || driver_token.chars().count() < 24 {
            return None;
        }
        let identity = OnlineIdentity {
            driver_id: driver_id.clone(),
            driver_token: driver_token.clone(),
        };
        if first_look {
            self.token_cache
                .lock()
                .unwrap()
                .insert(driver_id, driver_token);
            if !from_store {
                self.upgrade_storage(&identity, legacy_token.is_some());
            }
        }
        Some(identity)
    }
}

/// `tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=parent)`: a
/// name no other writer will pick.
fn fresh_temp_path(path: &Path) -> PathBuf {
    static COUNTER: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default();
    let nonce = COUNTER.fetch_add(1, Ordering::Relaxed);
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    path.with_file_name(format!(
        ".{name}.{}-{stamp}-{nonce}.tmp",
        std::process::id()
    ))
}
