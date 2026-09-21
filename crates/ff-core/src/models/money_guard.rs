//! A runtime shadow of the career balance, kept so the number a memory
//! editor writes is not the number the game believes.
//!
//! The packed save and its HMAC signature catch a save edited on disk, and
//! the load gate's plausibility check catches a balance no career could
//! hold. Neither catches a balance rewritten while the game runs: a memory
//! scanner finds the live `money` field, writes 9,999,999, and the game
//! goes on signing the lie itself.
//!
//! `MoneyGuard` is the game's own copy of that balance, held differently:
//! the f64 bit pattern XORed with a per-instance key, never the plain
//! number. Every legitimate change goes through [`Profile::earn`] /
//! [`Profile::spend`] / [`Profile::set_money`], which move the shadow with
//! the field. A write the game did not make leaves the field and the shadow
//! disagreeing, and the next transaction or save notices.
//!
//! A divergence is a risk signal, not a conviction -- the same verdict path
//! the on-disk tamper marks already use applies (`integrity_modified`), so a
//! false positive costs the player a flag a human can clear, not a ban.

use std::fmt;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

/// Balances are whole cents; the shadow agrees with the field when they are
/// the same cent. Legit paths move both in one statement, so any tolerance
/// here only buys forgiveness for a torn write under the editor.
const CENT: f64 = 0.005;

static KEY_COUNTER: AtomicU64 = AtomicU64::new(0x9e3779b97f4a7c15);

/// A fresh masking key: uptime mixed with a counter. Not cryptographic --
/// the guard only has to keep the plain balance out of a scanner's first
/// search, not withstand a targeted read of the process.
fn fresh_key() -> u64 {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.subsec_nanos() as u64 ^ d.as_secs())
        .unwrap_or(0x5bd1e995);
    nanos.wrapping_mul(0x9e3779b97f4a7c15)
        ^ KEY_COUNTER.fetch_add(0x9e3779b97f4a7c15, Ordering::Relaxed)
}

/// The shadow balance. `Clone` copies the key too, so a duplicated profile
/// (driving school) still checks out against its own copy.
#[derive(Clone)]
pub struct MoneyGuard {
    key: u64,
    masked: u64,
    /// Set once a divergence has been seen; stays set so `to_dict` can fold
    /// it into `integrity_modified` even when nothing transacted afterwards.
    diverged: bool,
}

impl MoneyGuard {
    /// A guard seeded at `balance`: used when a profile is created or
    /// loaded, where the balance has already passed the load gate.
    pub fn seeded(balance: f64) -> Self {
        let key = fresh_key();
        MoneyGuard {
            key,
            masked: balance.to_bits() ^ key,
            diverged: false,
        }
    }

    /// The balance the shadow currently holds.
    pub fn balance(&self) -> f64 {
        f64::from_bits(self.masked ^ self.key)
    }

    /// Record a legitimate change of `delta` dollars.
    pub fn apply(&mut self, delta: f64) {
        self.masked = (self.balance() + delta).to_bits() ^ self.key;
    }

    /// Adopt `balance` wholesale: the career's money was deliberately set
    /// (start option, scenario lever, settlement correction), not nudged.
    pub fn resync(&mut self, balance: f64) {
        self.masked = balance.to_bits() ^ self.key;
    }

    /// Whether `observed` is still the balance the shadow holds.
    pub fn matches(&self, observed: f64) -> bool {
        (self.balance() - observed).abs() < CENT
    }

    /// Whether a divergence has been seen since the guard was seeded.
    pub fn diverged(&self) -> bool {
        self.diverged
    }

    /// Compare the live field with the shadow. On divergence the guard
    /// latches `diverged` and adopts the observed balance, so one edit is
    /// reported once rather than on every later transaction.
    pub fn check(&mut self, observed: f64) -> bool {
        if self.matches(observed) {
            return true;
        }
        self.diverged = true;
        self.resync(observed);
        false
    }
}

impl fmt::Debug for MoneyGuard {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("MoneyGuard")
            .field("balance", &self.balance())
            .field("diverged", &self.diverged)
            .finish()
    }
}

impl PartialEq for MoneyGuard {
    /// Equality is the balance the shadow holds, not the mask bits -- two
    /// equal careers keep different keys.
    fn eq(&self, other: &Self) -> bool {
        self.diverged == other.diverged && self.balance().to_bits() == other.balance().to_bits()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tracks_applied_deltas() {
        let mut guard = MoneyGuard::seeded(1_000.0);
        guard.apply(-250.0);
        guard.apply(40.0);
        assert!(guard.matches(790.0));
        assert!(guard.check(790.0));
        assert!(!guard.diverged());
    }

    #[test]
    fn catches_a_written_field() {
        let mut guard = MoneyGuard::seeded(1_000.0);
        assert!(!guard.check(9_999_999.0));
        assert!(guard.diverged());
        // Once resynced to the observed number it does not reflag.
        assert!(guard.check(9_999_999.0));
    }

    #[test]
    fn resync_adopts_without_flagging() {
        let mut guard = MoneyGuard::seeded(1_000.0);
        guard.resync(50.0);
        assert!(guard.matches(50.0));
        assert!(!guard.diverged());
    }
}
