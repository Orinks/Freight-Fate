//! The installation-wide achievement collection.
//!
//! Career saves remain authoritative for career progress. This ledger only
//! records which catalog achievements this local player has earned anywhere.

use std::collections::BTreeMap;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

use ff_core::achievements::achievement_by_id;
use ff_core::models::profile::Profile;
use serde::{Deserialize, Serialize};

const FILE_NAME: &str = "account-achievements.json";
const FILE_VERSION: u32 = 1;
const LOCAL_PROFILE_MIGRATION_VERSION: u32 = 1;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AccountAchievementFile {
    version: u32,
    #[serde(default)]
    local_profile_migration_version: u32,
    #[serde(default)]
    achievements: BTreeMap<String, Option<i64>>,
}

impl Default for AccountAchievementFile {
    fn default() -> Self {
        Self {
            version: FILE_VERSION,
            local_profile_migration_version: 0,
            achievements: BTreeMap::new(),
        }
    }
}

/// The local account's union of every career's valid achievements.
#[derive(Debug, Clone)]
pub struct AccountAchievements {
    path: PathBuf,
    file: AccountAchievementFile,
}

impl AccountAchievements {
    /// Load this installation's ledger, leaving an unreadable file untouched
    /// and starting an empty in-memory collection for this run.
    pub fn load(data_dir: &Path) -> Self {
        let path = data_dir.join(FILE_NAME);
        let file = match fs::read_to_string(&path) {
            Ok(text) => match serde_json::from_str::<AccountAchievementFile>(&text) {
                Ok(file) if file.version == FILE_VERSION => file,
                Ok(file) => {
                    log::warn!(
                        "Ignoring unsupported account achievement ledger version {} at {}",
                        file.version,
                        path.display()
                    );
                    AccountAchievementFile::default()
                }
                Err(error) => {
                    log::warn!(
                        "Could not read account achievement ledger at {}: {error}",
                        path.display()
                    );
                    AccountAchievementFile::default()
                }
            },
            Err(error) if error.kind() == io::ErrorKind::NotFound => {
                AccountAchievementFile::default()
            }
            Err(error) => {
                log::warn!(
                    "Could not read account achievement ledger at {}: {error}",
                    path.display()
                );
                AccountAchievementFile::default()
            }
        };
        let achievements = file
            .achievements
            .into_iter()
            .filter(|(id, _)| {
                let valid = achievement_by_id(id).is_some();
                if !valid {
                    log::warn!("Ignoring unknown account achievement id {id:?}");
                }
                valid
            })
            .collect();
        Self {
            path,
            file: AccountAchievementFile {
                achievements,
                ..file
            },
        }
    }

    /// An unsaved ledger for a caller-controlled data directory.
    pub fn empty(data_dir: &Path) -> Self {
        Self {
            path: data_dir.join(FILE_NAME),
            file: AccountAchievementFile::default(),
        }
    }

    /// Every known achievement ID, in stable catalog-key order.
    pub fn ids(&self) -> Vec<String> {
        self.file.achievements.keys().cloned().collect()
    }

    /// The earliest trustworthy known earned time for one achievement.
    pub fn earned_at(&self, achievement_id: &str) -> Option<i64> {
        self.file
            .achievements
            .get(achievement_id)
            .copied()
            .flatten()
    }

    /// Add an achievement, returning whether this installation had not seen it.
    pub fn record(&mut self, achievement_id: &str, earned_at_ms: Option<i64>) -> io::Result<bool> {
        if achievement_by_id(achievement_id).is_none() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                format!("unknown achievement id {achievement_id:?}"),
            ));
        }

        let earned_at_ms = trustworthy_time(earned_at_ms);
        let is_new = !self.file.achievements.contains_key(achievement_id);
        let changed = match self.file.achievements.get_mut(achievement_id) {
            Some(existing) => {
                let earliest = earliest_time(*existing, earned_at_ms);
                if *existing == earliest {
                    false
                } else {
                    *existing = earliest;
                    true
                }
            }
            None => {
                self.file
                    .achievements
                    .insert(achievement_id.to_string(), earned_at_ms);
                true
            }
        };
        if changed {
            self.save_atomic()?;
        }
        Ok(is_new)
    }

    /// Merge one career's catalog achievements without changing that career.
    pub fn merge_profile(&mut self, profile: &Profile) -> io::Result<usize> {
        let mut inserted = 0;
        for achievement_id in &profile.achievements {
            if achievement_by_id(achievement_id).is_none() {
                log::warn!(
                    "Ignoring unknown achievement id {achievement_id:?} in career {:?}",
                    profile.name
                );
                continue;
            }
            if !self.file.achievements.contains_key(achievement_id) {
                self.file.achievements.insert(achievement_id.clone(), None);
                inserted += 1;
            }
        }
        if inserted > 0 {
            self.save_atomic()?;
        }
        Ok(inserted)
    }

    /// Import the careers in the existing save directory once, quietly.
    pub fn migrate_local_profiles(&mut self) -> io::Result<usize> {
        if self.file.local_profile_migration_version >= LOCAL_PROFILE_MIGRATION_VERSION {
            return Ok(0);
        }

        let mut inserted = 0;
        for path in Profile::list_saves() {
            match Profile::load(&path) {
                Ok(profile) => inserted += self.merge_profile(&profile)?,
                Err(error) => log::warn!(
                    "Skipping unreadable career {} while importing account achievements: {error}",
                    path.display()
                ),
            }
        }
        self.file.local_profile_migration_version = LOCAL_PROFILE_MIGRATION_VERSION;
        self.save_atomic()?;
        Ok(inserted)
    }

    fn save_atomic(&self) -> io::Result<()> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }
        let temp = self.path.with_extension("json.tmp");
        let text = serde_json::to_string_pretty(&self.file)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        fs::write(&temp, text)?;
        fs::rename(temp, &self.path)
    }
}

fn trustworthy_time(earned_at_ms: Option<i64>) -> Option<i64> {
    earned_at_ms.filter(|time| *time > 0)
}

fn earliest_time(first: Option<i64>, second: Option<i64>) -> Option<i64> {
    match (first, second) {
        (Some(first), Some(second)) => Some(first.min(second)),
        (Some(time), None) | (None, Some(time)) => Some(time),
        (None, None) => None,
    }
}
