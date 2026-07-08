# Billboard Spider — implementation methodology

Sibling of [`highway-spider-methodology.md`](highway-spider-methodology.md).
The highway spider builds the road graph (nodes and legs); the billboard spider
decorates a **built** corridor with geographically-placed roadside billboards.
It creates no dispatch cities and no legs — it only bakes billboard landmarks
onto legs that already exist, so it can run over the current map today and as a
follow-on step when a new corridor seals.

The one-sentence version: **the unit of work is the real roadside attraction.**
Each attraction near a corridor becomes one placed billboard landmark on the
nearest leg, at a milepost a little before you reach it, carrying authored
parody copy and gated by the existing `chatter_billboards` switch. The spider
**surfaces the geography**; a human **writes the joke**. The map owner approves
one artifact per corridor: the sign sheet (yay/nay per line).

Why a spider and not a hand-keyed table: a billboard belongs at a real *spot*,
not "somewhere on I-90." Keying signs by highway shield (or shield+state) is too
coarse — Wall Drug must fire in western South Dakota, not on I-90 in
Massachusetts. Anchoring each sign to the attraction's real coordinate makes it
geographic by construction: it speaks because you are actually approaching the
thing.

---

## 1. End state — when a corridor's billboards are "done"

A corridor is **signed** when:

1. Every attraction in scope near its trace (section 3) has either an approved
   placed billboard or an explicit `skip` in the sign sheet.
2. Placed billboards respect the spacing rule (section 4.2) against each other
   and against existing landmarks, so a stretch never stacks into a wall.
3. Every placed sign passes the spoken-text lint (numbers spelled out, no map
   tags, real names nominative, invented ad copy, source-noted).
4. The world test suite passes and the leg/landmark counts are updated.

The billboard layer is **additive** — it never deletes or moves a leg — so it
carries none of the highway spider's save-compatibility risk from splits.

## 2. The rendering contract (one-time code change, the only "jump to 1.9")

Placed billboards ride the **existing** landmark path, so almost no code is
new. Verified in `sim/trip.py` and `states/driving_events.py`:

- `_place_landmarks` reads each `leg.landmarks` record (`at_mi`, `name`,
  `category`, `spoken`) and speaks it at its real milepost — the same rail the
  Loneliest Road `highway_marker`, museums, and river crossings already use.
- Both `LANDMARK` and `BILLBOARD` events are gated at speak time by
  `settings.chatter_enabled(category)` and muted by terse speech
  (`driving_events.py:50-57`). The gate keys off the **category** string.

So a placed billboard is a landmark record with `kind: "point"` and a category
that maps to `chatter_billboards`. The one-time mainline change (a small PR that
reaches `dev` through the routine dev↔1.9 sync — do it once, then the spider
only ever writes data):

1. **Add a distinct category `"billboard_sign"`** — NOT the existing
   `"billboard"`. The save-resume dedup at `trip.py:1071` classifies callouts by
   `category == "billboard"` into `_announced_billboards`, while placed
   landmarks are checked against `_announced_landmarks`. Reusing `"billboard"`
   would misfile a placed sign on resume and let it re-fire. A distinct category
   sidesteps that entirely.
2. **Map it to the billboards switch:** add `"billboard_sign":
   "chatter_billboards"` to `settings.py` `CHATTER_CATEGORY_FIELDS`. This is what
   makes the answer to "does the billboards verbosity switch speak these too?"
   **yes** — both the written pool billboards (`"billboard"`) and the placed
   ones (`"billboard_sign"`) resolve to `chatter_billboards`, and terse mutes
   both. Skip this mapping and `chatter_enabled` defaults unknown categories to
   *on* — they would speak but the switch could not mute them (a bug).
3. **Allow it as a bake category:** add `"billboard_sign"` to
   `world_parsing.py` `LANDMARK_CATEGORIES` (the strict allowlist that rejects
   unknown categories as bake bugs) and to the bake tool's mirror set.
4. **Match the spoken form:** the pool path prefixes `"Billboard: "`; placed
   landmarks speak `spoken` raw. Decide once whether placed signs carry the
   prefix (recommend: yes, bake the lead word into the tool so the two sources
   sound identical) and keep it consistent.

Everything after this is pure map data on `dev`.

## 3. Candidate sourcing — surfacing the attractions

Two feeds, merged and deduped, restricted to within a buffer of the corridor
trace (reuse the 2-mile checkpoint buffer).

### 3.1 The self-hosted Overpass filter (bulk)

Against the `ff-overpass` extract (see the self-hosted Overpass work), pull
roadside-relevant POIs along the trace: `tourism=attraction | theme_park | zoo |
viewpoint | museum`, `roadside`-flavored `man_made`/`artwork`, "world's
largest…" named oddities. This is the same dev-time bake shape as the OSM
roadside narration. Real billboards are not in OSM — the *attractions they
advertise* are.

### 3.2 The curated seed list (the famous ones OSM misses)

Iconic roadside-culture stops are under-tagged in OSM, so keep a curated,
source-noted table with real coordinates: `data/spider/billboards_seed.json`,
one row per attraction (`name`, `lat`, `lon`, `corridors`, `real_note`, an
optional `countdown: true` for marquee multi-sign approaches). Seed it from what
is already known (section 10). Adding a row is a reviewed edit, same discipline
as the corridor inventory.

### 3.3 Relevance and dedup

- Drop candidates already spoken as another landmark (a museum that fires as
  `museum` should not also get a billboard, unless the billboard is a distinct
  bit — owner call, flagged).
- Collapse duplicates within ~5 miles to the single best-known attraction.
- Cap per corridor by the spacing rule (4.2), not by a hard count; log anything
  dropped for spacing so coverage is honest.

## 4. Placement rules

### 4.1 Which leg, which milepost

Project the attraction coordinate onto the nearest leg's polyline (reuse
`position_on_route`). Place the sign a **lead distance before** the projection
along the direction of travel — default ~8–15 miles, so it reads as an approach.
Because legs are driven both directions, resolve the milepost per direction the
same way `_place_landmarks` already does (`_stop_offset_for_direction`), or place
one sign and let the existing direction resolution handle it; do not bake two.

### 4.2 Spacing

Reuse `LANDMARK_MIN_SPACING_MI`. A placed billboard within that distance of an
existing landmark or another placed billboard is dropped (best-known wins) — the
same thinning `_place_landmarks` applies to river clusters. This keeps signs
from stacking and keeps them behind real geography.

### 4.3 Marquee approach countdowns (optional, curated)

For a few legends (Wall Drug, South of the Border, Big Buck's), a single sign
undersells the real experience — those attractions really do post a countdown
for hundreds of miles. A seed row flagged `countdown: true` bakes a short escalating
series at, e.g., `at − {150, 60, 15}` miles, each its own `billboard_sign`
record, subject to the same spacing thinning. Use sparingly; most attractions
get one sign.

### 4.4 One per attraction, no repeats

Each attraction yields at most one sign per direction (or one countdown set).
The pool path already guarantees no text repeats within a trip; placed signs are
distinct records, so a corridor never passes the same billboard twice.

## 5. The copy — the authored gate

This is the step the spider cannot automate, and the reason the map owner's
artifact is a **sign sheet**, not a plan of nodes:

- For each surfaced attraction, Opus drafts the parody copy from the
  attraction's real facts (pulled with the candidate). Register: short enough to
  read at seventy, funny, the real attraction named **nominatively**, ad text
  **invented** (never lifted), numbers spelled out, no codes or map tags — the
  same rules `billboards.py` already enforces in tests.
- The owner reviews the sheet line by line: keep / reword / skip, and answers
  the trademark-closeness call per sign (how near to echo a real slogan — the
  standing Big Buck's / radio-licensing judgment).
- Approved copy plus its placement becomes the bake input.

Node creation in the highway spider always needs an explicit yay; here the
equivalent standing rule is: **no billboard copy is baked without an explicit
approval** on the sheet. Silence is not consent for a sign that will be heard.

## 6. Stages and tooling

```text
for corridor in signing order:
    TRACE:   reuse the highway spider's cached trace
    SURFACE: billboard_surface(corridor)     # read-only: 3.1 + 3.2, dedup, spacing
    DRAFT:   Opus writes parody copy per surfaced attraction  # the authored step
    APPROVE: owner marks the sign sheet yay/nay/reword        # the human gate
    BAKE:    billboard_bake(sheet)           # writes billboard_sign landmarks
    AUDIT:   index_world --check; world tests; spoken lint; spacing check
    SEAL:    billboards ledger updated; PR opened against dev
```

- `tools/billboard_surface.py` — read-only. Walks a trace, queries the Overpass
  extract + the seed list, applies relevance/dedup/spacing, emits the sign
  sheet (attraction, coords, target leg + milepost, real facts, blank copy
  slots). Never touches `world.json`.
- `tools/billboard_bake.py` — executes an approved sheet: inserts
  `billboard_sign` landmark records onto the target legs, re-projecting by
  coordinate, source-noting each. Idempotent (skips signs already present),
  additive (no leg edits), then `index_world`.
- `data/spider/billboards_seed.json` — the curated attraction table (3.2).
- `data/spider/billboards_coverage.json` — the ledger: per corridor, signs
  placed, attractions skipped and why, spacing drops, seal date.

## 7. The audit

Lighter than the highway audit, because nothing structural changes:

1. **Spoken-text lint.** Run the existing billboard/landmark spoken tests plus a
   scan of new copy for digits, initialisms, and raw OSM text.
2. **Spacing check.** No two `billboard_sign` records (or a sign and a landmark)
   within `LANDMARK_MIN_SPACING_MI` on the same stretch.
3. **Placement sanity.** Every `billboard_sign` projects within the buffer of
   its leg's polyline; `at_mi` within the leg; direction resolution symmetric.
4. **Switch check.** A tiny unit test that `chatter_enabled("billboard_sign")`
   follows `chatter_billboards`, and that terse speech mutes it — the guard that
   answers the verbosity question and prevents a future regression.
5. **Coverage.** Attractions in scope with no sign are either approved skips or
   spacing drops, all recorded — never silently missing.

## 8. Operating model and lanes

- **Fable** owns this methodology; rule changes are edits to this doc.
- **Opus** builds the Phase-0 tools, runs SURFACE, and drafts the copy.
- **The map owner** reviews sign sheets (keep/reword/skip, trademark calls) and
  merges corridor PRs.
- **Lanes:** the placed billboards are **map data → PRs to `dev`** (this revises
  the earlier "billboards are 1.9 code, never map PRs" note — that still holds
  for the corridor-agnostic pools and the state welcome signs, which stay in
  `billboards.py`/`state_welcome.py` on the 1.9 line). The one-time rendering
  contract (section 2) is a small mainline PR that reaches both lanes via the
  normal sync.
- **Mechanics:** branch per corridor off `dev`; data-only bake commits take
  `[skip changelog]`; each corridor PR carries one player-language changelog
  entry under Added ("New roadside billboards along Interstate 90 across South
  Dakota — Wall Drug's countdown starts a very long way out").

## 9. Risks and open questions

1. **Copy is the bottleneck, by design.** Surfacing is cheap; writing a good
   sign is not. Batch the DRAFT step (many attractions, one authoring pass) and
   let the owner cull; do not gate SURFACE on it.
2. **OSM attraction sparsity.** The self-hosted extract is POI-filtered; some
   legends will only come from the seed list. That is expected — the seed list
   is a first-class feed, not a fallback.
3. **Trademark / parody closeness.** Per-sign owner judgment, same as Big
   Buck's; the sheet prints the real name and the invented copy side by side so
   the call is explicit.
4. **Prefix / voice consistency.** The pool path and the placed path must sound
   the same (section 2.4); a mismatch is jarring. Pin it once in the bake tool.
5. **Direction facing.** A real billboard faces one way; the game speaks a
   landmark in both directions. Acceptable (you "notice the sign" either way),
   but flag any sign whose copy only makes sense approaching from one side and
   place it direction-resolved.
6. **Scope creep.** The seed list plus the Overpass filter define the universe;
   an attraction outside both does not exist for the spider until a reviewed
   seed edit adds it.

## 10. Seed list — starting attractions (from the 2026-07-08 drafts)

Rows to prime `billboards_seed.json` (attraction → corridor; copy authored at
DRAFT). The six already in `CORRIDOR_BILLBOARDS` migrate here as placed signs;
the rest are this session's drafted corridors:

- **I-90 / South Dakota** — Wall Drug (`countdown`).
- **I-95 / the Carolinas** — South of the Border (`countdown`).
- **I-10 / Arizona** — The Thing; Cabazon-style roadside dinosaurs.
- **I-15 / Mojave** — alien jerky; The Mad Greek.
- **I-40 / the Southwest** — Historic Route 66 markers; a cavern trap.
- **I-80 / Wyoming** — Little America; the giant porch swing.
- **I-70 / Kansas–Colorado** — the world's largest prairie dog / Prairie Dog
  Town; the Rockies "the plains were lying" gag.
- **I-75 & I-24 / Tennessee–Georgia** — See Rock City; Ruby Falls.
- **I-44 / Missouri** — Meramec Caverns (`countdown`); the Uranus fudge factory.
- **I-35 / Oklahoma–Texas** — Winstar casino; the Czech Stop kolaches; the
  35E/35W split gag.
- **I-94 / Dakotas** — Salem Sue (world's largest Holstein); the Enchanted
  Highway sculptures.
- **I-5 / California** — Pea Soup Andersen's; Harris Ranch (the cattle smell).
- **I-65 / Kentucky** — the Corvette museum (Bowling Green); Dinosaur World
  (Cave City).
- **I-84 / Oregon–Idaho** — Multnomah Falls; Idaho "famous potatoes."
- **US-101 / redwood coast** — Trees of Mystery (Paul Bunyan); the drive-thru
  tree; Confusion Hill.
- **I-4 / Florida** — Dinosaur World (Plant City); airboat / gator stops.
- **Big Buck's** — its own approach pool already drafted in
  `BIG_BUCKS_BILLBOARDS`; place as a `countdown` at each Big Buck's landmark
  once those are sited in the world.
