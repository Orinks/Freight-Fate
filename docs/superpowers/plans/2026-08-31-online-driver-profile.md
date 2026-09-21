# Online Driver Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build account-wide achievement deduplication, meaningful-play public-career switching, richer verified profiles, and automatic ten-career cloud retention on Career 1.9 and `dev.orinks.net` staging.

**Architecture:** The Rust game keeps one installation-wide achievement ledger while career saves remain authoritative for career progression. Verified save uploads carry meaningful-play intent; Convex atomically validates the save, merges account achievements, updates the current public-career snapshot, and evicts the least-recently-active eligible cloud slot when necessary. Public React pages render only server-derived verified facts.

**Tech Stack:** Rust, serde/serde_json, existing Freight Fate transport and transcript harness; Next.js, TypeScript, Convex, Vitest/convex-test, Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-31-online-driver-profile-design.md`

## Global Constraints

- Target `feat/career-1.9` in Freight Fate and `dev` in orinks-net.
- Deploy only to the `dev.orinks.net` staging environment; never mutate production.
- One player has one orinks.net account; do not add multi-account behavior.
- Career achievement progress remains career-specific; only the collection and public-post deduplication are account-wide.
- Profile sharing remains the publication gate; cloud backup remains independently private.
- Never delete local saves. The ten-career limit applies only to cloud slots.
- Use TDD, focused checks during each task, one full test run per repository at the final gate, and Conventional Commits.
- All spoken/menu changes require desktop accessibility review and transcript verification; React profile changes require accessibility-lead, headings/text-quality, keyboard, and Playwright axe verification.

---

### Task 1: Installation-wide achievement ledger

**Files:**
- Create: `crates/freight-fate/src/account_achievements.rs`
- Modify: `crates/freight-fate/src/lib.rs`
- Modify: `crates/freight-fate/src/app.rs`
- Modify: `crates/freight-fate/src/app/context.rs`
- Test: `crates/freight-fate/tests/it/account_achievements.rs`
- Modify: `crates/freight-fate/tests/it/main.rs`

**Interfaces:**
- Produces: `AccountAchievements::load(data_dir: &Path) -> Self`, `merge_profile(&mut self, profile: &Profile) -> io::Result<usize>`, and `record(&mut self, achievement_id: &str, earned_at_ms: Option<i64>) -> io::Result<bool>`.
- Produces: versioned `account-achievements.json` in the existing Freight Fate data directory, written atomically.
- Consumes: stable achievement IDs from `ff_core::achievements` and existing save discovery/loading APIs.

- [ ] **Step 1: Write failing persistence and migration tests**

```rust
#[test]
fn account_collection_unions_careers_without_changing_them() {
    let mut ledger = AccountAchievements::empty(temp.path());
    let first = profile_with_achievements("one", &["first_delivery"]);
    let second = profile_with_achievements("two", &["first_delivery", "night_owl"]);
    assert_eq!(ledger.merge_profile(&first).unwrap(), 1);
    assert_eq!(ledger.merge_profile(&second).unwrap(), 1);
    assert_eq!(ledger.ids(), ["first_delivery", "night_owl"]);
    assert_eq!(first.achievements, vec!["first_delivery"]);
}

#[test]
fn record_is_idempotent_and_keeps_the_earliest_known_time() {
    let mut ledger = AccountAchievements::empty(temp.path());
    assert!(ledger.record("night_owl", Some(200)).unwrap());
    assert!(!ledger.record("night_owl", Some(100)).unwrap());
    assert_eq!(ledger.earned_at("night_owl"), Some(100));
}
```

- [ ] **Step 2: Run the focused test and confirm it fails because the ledger module is absent**

Run: `cargo test -p freight-fate --test it account_achievements::`

- [ ] **Step 3: Implement the versioned ledger and atomic write path**

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
struct AccountAchievementFile {
    version: u32,
    achievements: BTreeMap<String, Option<i64>>,
}

pub fn record(&mut self, id: &str, earned_at_ms: Option<i64>) -> io::Result<bool> {
    let is_new = !self.file.achievements.contains_key(id);
    self.file.achievements.entry(id.to_owned())
        .and_modify(|old| *old = earliest(*old, earned_at_ms))
        .or_insert(earned_at_ms);
    self.save_atomic()?;
    Ok(is_new)
}
```

- [ ] **Step 4: Load the ledger during app initialization and silently import every readable local career once**

Record a migration version in the ledger so startup does not rescan on every launch. Log unreadable careers without blocking startup and never announce imported awards.

- [ ] **Step 5: Re-run the focused tests and commit**

Run: `cargo test -p freight-fate --test it account_achievements::`

Commit: `feat(online): add account-wide achievement ledger`

---

### Task 2: Account-new achievement posting

**Files:**
- Modify: `crates/freight-fate/src/app/context.rs`
- Modify: `crates/freight-fate/src/online_journal.rs`
- Test: `crates/freight-fate/tests/it/app_achievements.rs`
- Test: `crates/freight-fate/tests/it/online_journal.rs`

**Interfaces:**
- Consumes: `AccountAchievements::record` from Task 1.
- Produces: `queue_achievement` is called only when `record` returns `true`; career award speech remains unchanged.

- [ ] **Step 1: Write a failing cross-career duplicate-post test**

```rust
#[test]
fn achievement_earned_in_a_second_career_is_not_posted_twice() {
    let mut app = signed_in_app_with_two_careers();
    app.open_career("one");
    app.ctx.award_achievement("first_delivery");
    app.open_career("two");
    app.ctx.award_achievement("first_delivery");
    assert_eq!(app.ctx.services.journal.pending_achievement_ids(), ["first_delivery"]);
    assert!(app.ctx.profile.as_ref().unwrap().achievements.contains(&"first_delivery".into()));
}
```

- [ ] **Step 2: Run the focused tests and confirm two public events are currently queued**

Run: `cargo test -p freight-fate --test it achievement_earned_in_a_second_career`

- [ ] **Step 3: Gate public queueing on account novelty**

Award to the active career first. Then record in the account ledger. Queue the journal/Mastodon achievement event only for a new ledger insertion. A persistence failure logs and suppresses public posting rather than risking a duplicate.

- [ ] **Step 4: Add tests proving migration does not speak or post and ordinary career award speech still occurs**

- [ ] **Step 5: Run focused tests and commit**

Run: `cargo test -p freight-fate --test it app_achievements:: online_journal::`

Commit: `fix(online): deduplicate achievement posts across careers`

---

### Task 3: Meaningful-play upload intent

**Files:**
- Create: `crates/freight-fate/src/meaningful_play.rs`
- Modify: `crates/freight-fate/src/lib.rs`
- Modify: `crates/freight-fate/src/cloud_saves.rs`
- Modify: `crates/freight-fate/src/cloud_saves/api.rs`
- Modify: `crates/freight-fate/src/states/city/board.rs`
- Modify: `crates/freight-fate/src/states/city_pickup.rs`
- Modify: `crates/freight-fate/src/states/driving_menu_states/arrival.rs`
- Modify: `crates/freight-fate/src/states/city_garage.rs`
- Modify: `crates/freight-fate/src/states/city/terminal.rs`
- Test: `crates/freight-fate/tests/it/cloud_saves.rs`
- Test: `crates/freight-fate/tests/it/online_profile_switch.rs`

**Interfaces:**
- Produces: `MeaningfulPlayTracker::mark(save_name: &str, reason: MeaningfulPlayReason)` and `take_for_upload(save_name: &str) -> Option<MeaningfulPlayStamp>`.
- Extends `upload_save` payload with `meaningfulPlay: { operationId, occurredAt, reason } | null`.
- The operation ID is stable across retries of the same pending snapshot.

- [ ] **Step 1: Write failing tests for meaningful and non-meaningful actions**

```rust
#[test]
fn loading_and_browsing_do_not_mark_a_public_switch() { /* load, browse, assert null */ }

#[test]
fn accepting_a_job_marks_the_next_upload_once() { /* accept, snapshot twice, same operation id */ }

#[test]
fn unchanged_save_does_not_refresh_meaningful_play() { /* save without mutation, assert null */ }
```

- [ ] **Step 2: Run focused tests and confirm the upload has no meaningful-play metadata**

Run: `cargo test -p freight-fate --test it online_profile_switch:: cloud_saves::`

- [ ] **Step 3: Implement the tracker and mark only durable events named in the spec**

Use a closed enum for `job_accepted`, `drive_started`, `delivery_completed`, `equipment_changed`, `business_changed`, and `changed_save`. Do not mark career load, menu browsing, achievement review, or unchanged save.

- [ ] **Step 4: Preserve the stamp through offline retries and clear it only after server acceptance**

- [ ] **Step 5: Run focused tests and commit**

Commit: `feat(online): mark meaningful career play`

---

### Task 4: Convex account merge and richer verified snapshot

**Files (orinks-net `dev`):**
- Modify: `convex/schema.ts`
- Modify: `convex/freightFateSaves.ts`
- Modify: `convex/freightFate.ts`
- Modify: `convex/freightFateSaves.test.ts`
- Modify: `convex/freightFate.test.ts`
- Modify: `convex/freightFateSharedProfileValidation.ts`
- Modify: `convex/freightFateSharedProfileValidation.test.ts`

**Interfaces:**
- Extend `freightFateProfileSnapshots` with `saveName`, career identity/resume fields, `netWorth`, and `meaningfulPlayedAt`.
- Add `mergeVerifiedAchievements(ctx, driverId, payload, now) -> Promise<{ inserted: string[] }>`.
- Account achievement uniqueness remains the existing `by_driver_achievement` index.
- Update `freightFateDrivers.publicSaveName` only when an accepted upload contains new meaningful-play intent and Profile sharing is enabled.

- [ ] **Step 1: Write failing Convex tests for union, migration silence, and verified autoswitch**

```ts
test("verified careers merge achievements and meaningful play switches the public career", async () => {
  await upload("main", profile({ achievements: ["first_delivery"] }), meaningful("op-1"));
  await upload("experiment", profile({ achievements: ["first_delivery", "night_owl"] }), null);
  expect(await publicSaveName()).toBe("main");
  expect(await achievementKeys()).toEqual(["first_delivery", "night_owl"]);
});
```

- [ ] **Step 2: Run tests and confirm the current snapshot lacks the new fields**

Run in orinks-net: `npm test -- convex/freightFateSaves.test.ts convex/freightFate.test.ts`

- [ ] **Step 3: Add schema fields and derive all public values from the verified save**

Derive career name, carrier/employment status, level/title, rig, deliveries, miles, on-time and damage-free rates, safety facts, visited states/cities, longest haul, lifetime earnings, and business-status-aware net worth. Do not trust client display strings.

- [ ] **Step 4: Merge verified save achievements into the account table without creating journal events**

For unknown historical earned times, use the accepted snapshot time only as import metadata and mark the row as imported; never treat it as a newly earned public event.

- [ ] **Step 5: Apply meaningful-play autoswitch only after validation and make operation IDs idempotent**

- [ ] **Step 6: Run focused tests and commit in orinks-net**

Commit: `feat(freight-fate): enrich verified driver profiles`

---

### Task 5: Automatic rolling ten-career retention

**Files (orinks-net `dev`):**
- Modify: `convex/schema.ts`
- Modify: `convex/freightFateSaves.ts`
- Modify: `convex/freightFateSaves.test.ts`
- Modify: `app/api/freight-fate/saves/route.ts`

**Interfaces:**
- Set `MAX_SLOTS = 10`.
- Add `evictableSlot(driverId, protectedNames, now) -> Promise<string | null>` using accepted `meaningfulPlayedAt`, with deterministic creation-time fallback for legacy slots.
- Successful upload response adds optional `evictedSaveName`.

- [ ] **Step 1: Write failing tests for eleventh-slot eviction and protections**

Cover least-recent meaningful use, current public career protection, incoming-career protection, legacy fallback, content-row deletion, account-achievement survival, and rollback when no safe target exists.

- [ ] **Step 2: Run the focused save tests and confirm the eleventh slot currently returns `too_many_slots`**

Run: `npm test -- convex/freightFateSaves.test.ts`

- [ ] **Step 3: Replace rejection with atomic eligible-slot eviction**

Delete all revision metadata and content rows for the chosen slot inside the upload mutation before inserting the accepted new slot. If no safe target exists, return `retention_blocked` without mutation.

- [ ] **Step 4: Return `evictedSaveName` through the Next route and add API contract tests**

- [ ] **Step 5: Run focused tests and commit in orinks-net**

Commit: `feat(freight-fate): roll cloud careers at ten slots`

---

### Task 6: Game response, Online hub, and public profile UI

**Files (Freight Fate):**
- Modify: `crates/freight-fate/src/cloud_saves/api.rs`
- Modify: `crates/freight-fate/src/cloud_saves.rs`
- Modify: `crates/freight-fate/src/states/online_hub.rs`
- Create: `crates/freight-fate/src/states/account_achievements.rs`
- Modify: `crates/freight-fate/tests/it/cloud_saves.rs`
- Modify: `crates/freight-fate/tests/it/online_states.rs`
- Modify: `docs/user-manual.md`
- Modify: `CHANGELOG.md`
- Modify: `ROADMAP.md`

**Files (orinks-net `dev`):**
- Modify: `app/freight-fate/drivers/[driverId]/profile-view.tsx`
- Modify: `app/freight-fate/drivers/[driverId]/profile-view.test.tsx`
- Modify: `app/freight-fate/online/privacy/page.tsx`
- Modify: `app/freight-fate/online/privacy/page.test.tsx`

**Interfaces:**
- Parse `evictedSaveName` from accepted uploads and announce: `Cloud backup removed <name>, the least recently played cloud career. Your local career was not deleted.`
- Add Online hub item `Account achievements` without replacing the career achievements menu.
- Render one profile fact per semantic definition-list row; use headings for profile sections and ordinary lists for achievements.

- [ ] **Step 1: Write failing Rust transcript tests for eviction speech and the account-achievement menu**

- [ ] **Step 2: Write failing React tests for identity-first order, net worth, account-wide badge labeling, and absence of repetitive fiction disclaimers**

- [ ] **Step 3: Implement the Rust response/menu and website profile rendering**

- [ ] **Step 4: Update player documentation, privacy wording, changelog, and roadmap**

- [ ] **Step 5: Run focused Rust and web tests**

Run Freight Fate: `cargo test -p freight-fate --test it online_states:: cloud_saves::`

Run orinks-net: `npm test -- app/freight-fate/drivers/[driverId]/profile-view.test.tsx app/freight-fate/online/privacy/page.test.tsx`

- [ ] **Step 6: Run accessibility reviews**

Use the accessibility lead for the React profile, plus screen-reader/heading and text-quality specialists. Use the desktop accessibility specialist for the Rust spoken menu. Resolve every blocker before committing.

- [ ] **Step 7: Commit in each repository**

Freight Fate: `feat(online): show account-wide driver history`

orinks-net: `feat(freight-fate): show richer driver profiles`

---

### Task 7: Staging migration and end-to-end verification

**Files:**
- Create: `C:/Users/joshu/gh-projects/orinks-net/convex/freightFateProfileMigration.ts`
- Create: `C:/Users/joshu/gh-projects/orinks-net/convex/freightFateProfileMigration.test.ts`
- Modify: `docs/alpha-test-book.md`

**Interfaces:**
- Add an idempotent staging-only migration that scans verified snapshots, merges account achievements, assigns legacy meaningful-play fallback dates, and never emits public events.
- No production deployment command is permitted.

- [ ] **Step 1: Test the migration against seeded legacy and multi-career accounts**

Assert unioned achievements, no new driver events, preserved public career until meaningful play, and deterministic retention order.

- [ ] **Step 2: Run Freight Fate final verification exactly once**

Run: `cargo fmt --all --check`

Run: `cargo clippy --all-targets --locked -- -D warnings`

Run: `cargo test -p ff-core`

Run: `cargo test -p freight-fate`

Run: `cargo run -p freight-fate --bin freightfate -- --break-battery`

- [ ] **Step 3: Run orinks-net final verification exactly once**

Run in orinks-net: `npm run lint`

Run in orinks-net: `npm run typecheck`

Run in orinks-net: `npm test`

Run in orinks-net: `npm run build`

Run in orinks-net: `npx playwright test`

Record exact passing counts in the implementation report.

- [ ] **Step 4: Deploy Convex and Next changes only to the staging project serving `dev.orinks.net`**

Before deployment, print and verify the selected Vercel project, environment, Convex deployment, Git branch, and target hostname. Stop if any value names production.

- [ ] **Step 5: Perform a real staging flow**

Use two local careers sharing one test driver: earn the same achievement in both, confirm one account badge and one public accomplishment; perform meaningful play in the second and confirm its verified career identity appears; upload eleven careers and confirm the oldest eligible cloud career disappears while the local save and account badge remain.

- [ ] **Step 6: Perform web accessibility verification on the deployed public profile**

Verify heading order, definition-list reading order, link names, keyboard navigation, zoom/reflow, and screen-reader output. Confirm Profile sharing off hides every new field.

- [ ] **Step 7: Commit any staging-test documentation and push both reviewed branches**

Do not promote, merge, or deploy to production as part of this plan.
