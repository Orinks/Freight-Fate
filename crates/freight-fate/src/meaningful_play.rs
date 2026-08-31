//! Pending intent that an accepted cloud snapshot may become the public career.

use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

static OPERATION_SEQUENCE: AtomicU64 = AtomicU64::new(1);

/// The closed set of gameplay events the server accepts as meaningful play.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MeaningfulPlayReason {
    JobAccepted,
    DriveStarted,
    DeliveryCompleted,
    EquipmentChanged,
    BusinessChanged,
    ChangedSave,
}

/// The retry-stable metadata attached to one pending meaningful upload.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MeaningfulPlayStamp {
    pub operation_id: String,
    pub occurred_at: i64,
    pub reason: MeaningfulPlayReason,
}

/// Thread-safe pending meaningful-play intents, one newest intent per save.
#[derive(Debug, Clone)]
pub struct MeaningfulPlayTracker {
    inner: Arc<TrackerInner>,
}

#[derive(Debug)]
struct TrackerInner {
    path: Option<PathBuf>,
    state: Mutex<TrackerState>,
}

#[derive(Debug, Default)]
struct TrackerState {
    pending: HashMap<String, MeaningfulPlayStamp>,
    loaded: bool,
}

impl Default for MeaningfulPlayTracker {
    fn default() -> Self {
        Self {
            inner: Arc::new(TrackerInner {
                path: None,
                state: Mutex::new(TrackerState {
                    loaded: true,
                    ..TrackerState::default()
                }),
            }),
        }
    }
}

impl MeaningfulPlayTracker {
    /// Load and persist pending intent beside the cloud sync ledger.
    pub fn new(data_dir: &Path) -> Self {
        Self {
            inner: Arc::new(TrackerInner {
                path: Some(data_dir.join("meaningful_play.json")),
                state: Mutex::new(TrackerState::default()),
            }),
        }
    }

    /// Replace this save's pending intent with a newly identified event.
    pub fn mark(&self, save_name: &str, reason: MeaningfulPlayReason) {
        let occurred_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis() as i64)
            .unwrap_or(0);
        let sequence = OPERATION_SEQUENCE.fetch_add(1, Ordering::Relaxed);
        let operation_id = format!(
            "{occurred_at:016x}-{:08x}-{sequence:016x}",
            std::process::id()
        );
        let mut state = self.inner.state.lock().unwrap();
        self.ensure_loaded(&mut state);
        state.pending.insert(
            save_name.to_string(),
            MeaningfulPlayStamp {
                operation_id,
                occurred_at,
                reason,
            },
        );
        self.persist(&state.pending);
    }

    /// Read the pending stamp without consuming it so retries reuse it.
    pub fn for_upload(&self, save_name: &str) -> Option<MeaningfulPlayStamp> {
        let mut state = self.inner.state.lock().unwrap();
        self.ensure_loaded(&mut state);
        state.pending.get(save_name).cloned()
    }

    /// Clear only the exact operation the server accepted.
    pub fn clear_if_accepted(&self, save_name: &str, operation_id: &str) {
        let mut state = self.inner.state.lock().unwrap();
        self.ensure_loaded(&mut state);
        if state
            .pending
            .get(save_name)
            .is_some_and(|stamp| stamp.operation_id == operation_id)
        {
            state.pending.remove(save_name);
            self.persist(&state.pending);
        }
    }

    fn ensure_loaded(&self, state: &mut TrackerState) {
        if state.loaded {
            return;
        }
        state.loaded = true;
        let Some(path) = &self.inner.path else {
            return;
        };
        let Ok(text) = fs::read_to_string(path) else {
            return;
        };
        let Ok(value) = serde_json::from_str::<serde_json::Value>(&text) else {
            return;
        };
        let Some(pending) = value.get("pending").and_then(|value| value.as_object()) else {
            return;
        };
        for (save_name, stamp) in pending {
            if let Ok(stamp) = serde_json::from_value::<MeaningfulPlayStamp>(stamp.clone()) {
                state.pending.insert(save_name.clone(), stamp);
            }
        }
    }

    fn persist(&self, pending: &HashMap<String, MeaningfulPlayStamp>) {
        let Some(path) = &self.inner.path else {
            return;
        };
        let result = (|| -> std::io::Result<()> {
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent)?;
            }
            let document = serde_json::json!({"version": 1, "pending": pending});
            let text = serde_json::to_string_pretty(&document)
                .map_err(|error| std::io::Error::new(std::io::ErrorKind::InvalidData, error))?;
            fs::write(path, text)
        })();
        if let Err(error) = result {
            log::debug!("Could not persist meaningful-play intent: {error}");
        }
    }
}
