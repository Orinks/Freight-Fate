//! Completion receipts for warnings that persist an acknowledged marker.

use std::collections::HashMap;

const RECEIPT_LIMIT: usize = 32;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DeliveryStatus {
    Pending,
    Completed,
    Interrupted,
}

struct Receipt {
    text: String,
    done_at: f64,
    interrupted: bool,
}

#[derive(Default)]
pub(super) struct DeliveryReceipts {
    entries: HashMap<String, Receipt>,
}

impl DeliveryReceipts {
    pub(super) fn track(&mut self, key: &str, text: &str, done_at: f64) {
        if self.entries.len() >= RECEIPT_LIMIT && !self.entries.contains_key(key) {
            self.entries.retain(|_, receipt| !receipt.interrupted);
            if self.entries.len() >= RECEIPT_LIMIT {
                if let Some(oldest) = self
                    .entries
                    .iter()
                    .min_by(|a, b| a.1.done_at.total_cmp(&b.1.done_at))
                    .map(|(key, _)| key.clone())
                {
                    self.entries.remove(&oldest);
                }
            }
        }
        self.entries.insert(
            key.to_string(),
            Receipt {
                text: text.to_string(),
                done_at,
                interrupted: false,
            },
        );
    }

    pub(super) fn status(&mut self, key: &str, now: f64) -> Option<DeliveryStatus> {
        let status = self.entries.get(key).map(|receipt| {
            if receipt.interrupted {
                DeliveryStatus::Interrupted
            } else if now >= receipt.done_at {
                DeliveryStatus::Completed
            } else {
                DeliveryStatus::Pending
            }
        })?;
        if status != DeliveryStatus::Pending {
            self.entries.remove(key);
        }
        Some(status)
    }

    pub(super) fn has_pending(&self, now: f64) -> bool {
        self.entries
            .values()
            .any(|receipt| !receipt.interrupted && now < receipt.done_at)
    }

    pub(super) fn interrupt_pending(&mut self, now: f64) {
        for receipt in self.entries.values_mut() {
            if now < receipt.done_at {
                receipt.interrupted = true;
            }
        }
    }

    pub(super) fn resume_text(&mut self, text: &str, done_at: f64) {
        for receipt in self.entries.values_mut() {
            if receipt.interrupted && receipt.text == text {
                receipt.done_at = done_at;
                receipt.interrupted = false;
            }
        }
    }

    pub(super) fn forget(&mut self, key: &str) {
        self.entries.remove(key);
    }
}
