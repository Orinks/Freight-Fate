# Account-wide achievements and richer online driver profiles

Date: 2026-08-31

Status: Approved design, awaiting implementation planning

Target: Freight Fate Career 1.9 and the `dev.orinks.net` staging deployment only

## Purpose

Online driver profiles currently center one backed-up career, while achievements and public accomplishment posts remain career-specific. A player who uses several careers can therefore publish the same first-time accomplishment more than once. Profiles also omit basic identity context such as the career name and employer.

This design gives each player one account-wide achievement collection, enriches the public profile with a clearly labeled current-career snapshot, and limits private cloud storage to a rolling set of ten careers. Career progression remains independent. Production orinks.net and the stable 1.8 game line are out of scope.

## Product boundaries

- One Freight Fate player has one orinks.net account. Multi-account behavior is not supported or designed here.
- Achievement ownership is account-wide, but achievement progress and gameplay effects remain career-specific.
- Public career details come from one verified current-career snapshot.
- The current public career changes automatically after meaningful play, not merely after loading or browsing a career.
- Private cloud backup retains no more than ten careers at once. Local saves are never deleted by cloud retention.
- Leaderboards and CB-radio chat are separate follow-up projects.

## Account-wide achievement collection

The game maintains one installation-wide achievement collection outside individual career saves. It contains stable achievement IDs and the earliest trustworthy earned time when one is available.

Each career continues to store its own achievements and achievement statistics. Those fields drive career-specific menus, predicates, progress, and rewards. Earning a badge in one career does not mark that badge complete inside another career.

When a career earns an achievement, the game performs two independent operations:

1. Award the achievement to the career when that career has not earned it.
2. Insert the achievement into the installation-wide collection when the account has not earned it.

Only the second operation can create an account-level public accomplishment. Road-journal and Mastodon achievement posts are queued only when insertion into the account collection is new. Repeated career awards remain visible in that career but do not produce duplicate public posts.

The collection synchronizes with `dev.orinks.net` as a set union by achievement ID. Upload order and repeated requests are idempotent. The server retains account achievements independently of cloud career slots.

## Migration

On first use, the game scans readable local careers and imports their achievement IDs into the installation-wide collection. When connected, `dev.orinks.net` also unions achievement IDs from every accepted verified cloud career into the online account collection.

Migration imports are silent. They do not play achievement speech, add new review-log notices, or create road-journal or Mastodon posts. If an earned timestamp exists and can be trusted, the earliest timestamp is retained. Otherwise the entry is recorded as earned before account tracking began and is not given an invented date.

Signing out does not create a second local player collection. Reconnecting merges the same installation-wide collection into the player's one orinks.net account.

## Current-career selection

Loading a career, browsing its menus, reviewing its achievements, or quitting without changing it does not alter the public profile.

A career becomes the intended current public career after a durable meaningful-play event, including:

- accepting a job or beginning a drive;
- completing a delivery;
- buying, selling, repairing, or upgrading equipment;
- hiring or changing business status; or
- saving after persistent career state has genuinely changed.

The game records the intended switch locally and sends it with the next eligible cloud/profile update. `dev.orinks.net` changes the public career only after accepting and validating that career snapshot. Until then, the previously verified career remains public. Network failure queues a retry and never exposes a partial or rejected snapshot.

Profile sharing remains the publication gate. When sharing is off, meaningful play and cloud backup do not publish career identity or update the public profile.

## Public profile content

Information is presented in this order, with one fact per spoken line:

1. Driver account name.
2. Current career name.
3. Employment or business identity: company driver and carrier, or the applicable owner-operator and leased-carrier status.
4. Career level and title.
5. Current owned tractor or carrier-assigned tractor.
6. Career resume: lifetime deliveries and miles, on-time percentage, damage-free percentage, safety record, states and cities visited, longest haul, and lifetime career earnings.
7. Account-wide achievement total and the two or three most recently earned account achievements.
8. Recent road-journal activity.

Every career-specific statistic is labeled as belonging to the current career. Achievements are labeled as account-wide.

Current cash, net spendable balance, precise location, fatigue, hours-of-service state, active cargo details, and dispatcher standing remain private. Existing profile-sharing consent controls all newly public fields.

## Cloud career retention

Each account retains at most ten private cloud career slots. Each retained career continues to use the existing per-career revision history.

When accepting an upload for an eleventh career, the server automatically evicts the least recently meaningfully played cloud career and all of that career's stored revisions. Retention order uses the server-accepted meaningful-play time, not file modification time, login time, or a mere career load.

The career being uploaded and the currently verified public career are protected from eviction. If no safe target exists, or deletion fails, the new upload fails without changing existing slots. The server must not transiently accept an uncertain partial state.

After successful eviction, the game speaks which cloud career was removed and makes clear that its local save remains. Eviction never removes local careers, account-wide achievements, or already accepted account activity. Playing an evicted local career meaningfully can upload it again later, potentially evicting the then-least-recently-played cloud career.

## Data ownership and synchronization

The career save remains authoritative for career progression and statistics. The installation-wide collection provides offline account-achievement deduplication. `dev.orinks.net` is authoritative for the public account collection, accepted public career snapshot, cloud-retention order, and public rendering.

Client requests use stable operation identifiers so retries cannot duplicate achievement events, public posts, or eviction work. Server mutations atomically validate the incoming snapshot, merge account achievements, update meaningful-play recency, perform any required safe eviction, and select the accepted current career.

Public display is derived only from accepted, verified data. Client-provided display prose is not trusted; the server renders allowlisted fields and derives catalog names, level titles, carrier labels, equipment names, and achievement names from its compatible invariant/catalog data.

## Failure handling

- Offline account achievements persist locally and synchronize later.
- Duplicate achievement submissions are successful no-ops.
- A rejected career snapshot cannot change the current public career or retention order.
- Failure to evict prevents acceptance of an eleventh cloud career and leaves all existing careers intact.
- Failure to publish a journal or Mastodon event remains retryable, but an achievement already known to the account is never re-enqueued as new.
- Older clients and pre-feature profiles continue to render with their existing fields; missing account-collection data is backfilled without public announcements.
- Profile sharing off prevents public rendering and posting independently of private backup synchronization.

## Accessibility and player communication

All new profile and backup information remains keyboard and screen-reader accessible. Profile output uses one concise fact per spoken line, identity before statistics, and the game's canonical terminology.

The account-wide collection is available from the Online hub. The existing career achievements menu remains career-specific and identifies that scope. The cloud-backup menu identifies the ten-career limit and explains that automatic removal affects cloud copies only. Eviction speech names the removed career and confirms that its local save was not deleted.

No important state is conveyed only visually. Background synchronization stays quiet except for an actionable failure, a requested status review, or successful automatic cloud-career eviction.

## Verification

Implementation verification must cover:

- migration from legacy local careers and existing verified cloud careers;
- account union across several careers in different upload orders;
- career-specific achievement progress remaining independent;
- duplicate first-delivery and other common achievements producing no repeated account post;
- offline earning followed by online merge;
- retry and idempotency behavior for achievements, posts, and career switching;
- meaningful-play events switching the public career;
- loading, browsing, and unchanged saves not switching it;
- rejected and offline snapshots leaving the prior verified public career visible;
- profile-sharing-off behavior for every new field and post path;
- accurate company-driver, owner-operator, carrier, title, and rig rendering;
- percentages and minimum-data presentation for richer resume facts;
- automatic eleventh-career eviction, protected-career behavior, failure rollback, and re-upload of an evicted local career;
- account achievements surviving cloud-career eviction;
- pre-feature profile compatibility;
- spoken menus and profile output through the deterministic transcript harness;
- staging end-to-end checks against `dev.orinks.net`, with no production mutation.

## Deferred work

Realistic category-based leaderboards are intentionally deferred until verified richer profiles contain enough real staging data to set qualification floors. CB-radio-themed multiplayer chat is also a separate feasibility and design project with its own moderation, retention, rate-limit, real-time delivery, and accessibility requirements.
