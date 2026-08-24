//! Nothing in a test process may reach the player's platform secret store.
//!
//! The driver token is filed under one fixed service name, not one derived
//! from the save directory, so pinning a temporary data directory buys
//! nothing: a store built over it still keys the OWNER's entry in Windows
//! Credential Manager. Only the process itself tells the game from a test.
//!
//! Nothing calls it from a test today -- a temporary data directory has no
//! `online.json`, so no Driver ID is ever looked up -- which makes this
//! latent rather than live. The linked-account case below is what one line
//! of a first-run flow would have made of it.
//!
//! Read `freight_fate::online_presence` for the mechanism, which is the
//! browser's and the network's: a capability `main()` grants, refused and
//! recorded everywhere else.

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::Arc;

use freight_fate::app::testing::TempDir;
use freight_fate::online_presence::{
    self, IdentityStore, MemoryStore, OnlineIdentity, SecretStore, TOKEN_SERVICE,
};

fn was_refused(user: &str) -> bool {
    online_presence::refused_secret_keys().contains(&format!("{TOKEN_SERVICE}/{user}"))
}

/// The capability itself: a test process is never the game.
#[test]
fn test_a_test_process_is_never_granted_the_platform_secret_store() {
    assert!(!online_presence::real_secret_store_allowed());
}

#[test]
fn test_reading_a_token_is_refused_and_recorded_instead_of_looked_up() {
    let store = online_presence::KeyringStore;
    let outcome = catch_unwind(|| store.get_password(TOKEN_SERVICE, "guard-read"));
    assert!(outcome.is_err(), "the platform store was read");
    assert!(
        was_refused("guard-read"),
        "{:?}",
        online_presence::refused_secret_keys()
    );
}

/// Writing matters more than reading: a stray `set_password` would overwrite
/// the owner's own posting secret with a test's invented one.
#[test]
fn test_writing_a_token_is_refused_and_recorded() {
    let store = online_presence::KeyringStore;
    let outcome = catch_unwind(|| store.set_password(TOKEN_SERVICE, "guard-write", "nonsense"));
    assert!(outcome.is_err(), "the platform store was written");
    assert!(
        was_refused("guard-write"),
        "{:?}",
        online_presence::refused_secret_keys()
    );
    let outcome = catch_unwind(|| store.delete_password(TOKEN_SERVICE, "guard-delete"));
    assert!(outcome.is_err(), "the platform store was deleted from");
    assert!(
        was_refused("guard-delete"),
        "{:?}",
        online_presence::refused_secret_keys()
    );
}

/// The same case discipline cannot catch: the store is reached from whatever
/// thread happens to be asking, and there is no per-thread seam that could
/// have covered one the test did not spawn.
#[test]
fn test_a_spawned_thread_cannot_escape_the_seam() {
    let worker = std::thread::Builder::new()
        .name("secret-store-guard-probe".to_string())
        .spawn(|| online_presence::KeyringStore.get_password(TOKEN_SERVICE, "guard-spawned"))
        .expect("the probe thread starts");
    let outcome = worker.join();

    assert!(
        outcome.is_err(),
        "a spawned thread read the platform store: {outcome:?}"
    );
    assert!(
        was_refused("guard-spawned"),
        "{:?}",
        online_presence::refused_secret_keys()
    );
}

/// What makes this seam real rather than theoretical: a temporary data
/// directory isolates the identity FILE, and not the secret behind it. The
/// moment a test writes an `online.json` -- which is all "link an account"
/// does -- the very next load reaches for the owner's Credential Manager
/// entry under the one fixed service name.
#[test]
fn test_a_linked_account_in_a_temporary_directory_still_keys_the_owners_entry() {
    let tmp = TempDir::new("secret-store-guard");
    let driver_id = "guard-linked-driver";
    std::fs::write(
        tmp.path().join("online.json"),
        serde_json::to_string(&serde_json::json!({ "driver_id": driver_id }))
            .expect("an identity file"),
    )
    .expect("write the identity file");

    let store = IdentityStore::platform(tmp.path());
    let outcome = catch_unwind(AssertUnwindSafe(|| store.load()));

    assert!(
        outcome.is_err(),
        "a temporary data directory reached the owner's secret store"
    );
    assert!(
        was_refused(driver_id),
        "{:?}",
        online_presence::refused_secret_keys()
    );
}

/// The real game's behaviour is unchanged, and so is every test that already
/// builds its store the right way: an in-memory store is untouched by the
/// capability, because unlike the keyring it really is the test's own.
#[test]
fn test_an_in_memory_store_still_holds_a_token() {
    let tmp = TempDir::new("secret-store-memory");
    let memory = MemoryStore::new();
    let store = IdentityStore::new(
        tmp.path(),
        Some(Arc::clone(&memory) as Arc<dyn SecretStore>),
    );
    let identity = OnlineIdentity::new("guard-memory-driver", &"t".repeat(32));
    store.save(&identity).expect("the identity saves");

    assert_eq!(store.load(), Some(identity));
    assert!(memory
        .passwords()
        .contains_key(&(TOKEN_SERVICE.to_string(), "guard-memory-driver".to_string())));
}
