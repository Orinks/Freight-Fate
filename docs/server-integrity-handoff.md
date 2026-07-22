# Server integrity handoff — validation gate, event ledger, and gated items

Audience: the orinks.net server implementer (Josh, or an agent working his
side). This is the working brief for everything the server owes the save
integrity design now that the client half has shipped. It assumes
`docs/profile-invariants.md` (the maintained validation list) and the design
notes in `docs/profile-sharing-integrity-design.md` (branch
`docs/profile-integrity`). Where those documents disagree with this one,
this one is newer; update them.

The one-sentence version of the whole architecture: **the client is never
trusted, the server is the only authority, and everything client-side is a
speed bump for casual editing** — deliberately. Freight Fate is open
source; any key or check that ships to a player's machine can be read out
of it. That is why the client marks instead of blocks, and why the server
must eventually *recompute* careers from an event ledger instead of
trusting claimed totals.

## 1. What the client now does (shipped, both save layers)

Local saves:

- Careers live in packed `.ffsave` containers: an 8-byte magic header
  (`FFSAVE1\0`) plus zlib-deflated JSON. Inside the JSON, the profile is
  signed with a per-install HMAC-SHA256 key (`profile.key`, next to the
  saves). The container stops Notepad; the HMAC stops naive re-saving.
- A save that fails its local signature **loads anyway** and gets a sticky
  `integrity_modified: true`, plus a one-time spoken notice. The flag is
  inside the signed payload, so hand-clearing it invalidates the signature
  and it comes right back. Mark, don't block: local single-player editing
  is the player's own business; the mark is what shared features read.
- A packed container with no signature at all is treated as tampered (the
  game never writes one). Plain unsigned `.json` saves keep amnesty as the
  honest pre-signing shape and convert on load; that amnesty is scheduled
  to retire a release or two after the container ships (see ROADMAP).
- Files too damaged to decode are quarantined (`.invalid` rename); the
  main menu says so in plain speech.

Cloud path (unchanged by this change, restated for completeness):

- Uploads strip the local signature; the canonical gzip content and its
  sha256 travel to the server. Downloads verify the server's Ed25519
  revision signature, then run `check_profile_invariants` client-side as
  defense in depth, then install with a fresh local HMAC.

What this means for the server: `integrity_modified` now arrives in
uploaded profiles, and it is the *only* new field pair
(`integrity_modified`, `integrity_notice_pending`, both booleans).

## 2. Semantics of `integrity_modified` — advisory, not proof

The flag has exactly two honest causes and one dishonest one:

1. The player copied their save to another computer (different
   `profile.key` → signature mismatch). Honest.
2. A crash or disk fault corrupted bytes inside the JSON while leaving it
   decodable. Rare, honest.
3. The save was edited. Dishonest.

Because 1 exists, the server MUST NOT hard-reject on the flag alone.
Treat it as a risk signal:

- `integrity_modified: false` — normal pipeline.
- `integrity_modified: true` — run the FULL validation gate (hard
  invariants + every plausibility rule + ledger replay once it exists) at
  the strictest setting rather than any sampled/cheap subset. Log the
  event with the driver id and build identity.
- Flagged AND validation fails → reject the upload with the usual coded
  reason. The client already speaks rejections in plain language.
- Flagged AND validation fully passes → accept, and grant **absolution**:
  include `clearIntegrityFlag: true` in the signed revision reply. The
  client, on its next verified restore, clears the local mark. This is
  the release valve that keeps honest machine-movers from being marked
  forever. Absolution must only ever ride a *fully validated, signed*
  revision — never a summary endpoint.

Client work for absolution is small and NOT yet written (roadmap bullet):
`restore_to_disk` clears the flag when the verified payload carries the
signal. Coordinate the field name with whoever wires it; `clearIntegrityFlag`
is the suggestion, camelCase to match the existing reply fields
(`saveName`, `contentHash`, `validatorVersion`, ...).

Enforcement points that should read the flag (or the server-side verdict
derived from it) once each feature exists: profile-sharing publish,
leaderboards, the player truck marketplace, any escrow or trade. One rule
everywhere: **an unabsolved modified profile can look at shared features
but cannot write into them.**

## 3. The event ledger — the real hardening

Today the gate judges *states* (is this money plausible for these miles?).
The ledger upgrades it to judging *histories*: the client records every
economically meaningful event; the server replays the events and derives
the state itself. An edited save then has to forge a *consistent history*,
under a signature chain the server controls. That is the "severely harden"
Josh asked for, and it is all server-auditable with zero secrets in the
open-source client.

### 3.1 Event record shape

Append-only JSON lines, carried inside the profile (new field, e.g.
`ledger`) or as a sidecar upload — implementer's choice, but the chain
rules below are fixed:

    {
      "seq": 481,                    // strictly increasing, no gaps
      "type": "delivery.completed",  // namespaced event type
      "at": {"game_h": 1042.5, "wall": "2026-07-19T18:04:11Z"},
      "data": { ... type-specific ... },
      "prev": "<sha256 of record 480, canonical form>",
      "hash": "<sha256 of this record minus 'hash', canonical form>"
    }

- Canonical form: sorted keys, `,`/`:` separators, ensure_ascii — the same
  conventions `cloud_content` already uses, so both sides agree byte-for-byte.
- `prev`/`hash` make the chain; record 0 uses `prev: null` and carries the
  career's origin (starting money, carrier, start city, save version).
- On every accepted upload the server stores (and signs into the revision
  reply) the chain head `(seq, hash)`. A later upload whose chain does not
  extend the last signed head is a **rewritten history** — the single
  strongest tamper signal the system will ever produce. Reject it, no
  absolution.

### 3.2 Replay rules

- The server derives: money, XP, deliveries, on-time counts, total miles,
  total earnings, owned trucks/trailers/upgrades, endorsements, and every
  gated item (section 4) — purely from events.
- Derived state vs claimed profile state: allow a small epsilon on floats
  (fuel-price rounding), zero tolerance on integers and item possession.
- Balance can never go below the game's own floor; every debit event must
  be affordable at replay time. Every credit must name its source event.
- Version drift: events carry the build identity implicitly via the upload
  metadata that already exists. Replay against the rules of
  `validatorVersion` current at *upload* time; bump `validator_version`
  when replay rules change, exactly like the plausibility rules today.
- Determinism boundary (the game's own law, see AGENTS.md): payouts, XP
  curves, and prices are deterministic data in the repo — the export in
  `tools/export_profile_integrity_invariants.py` already ships level
  curves, truck/upgrade prices, and achievement ids to the validator.
  Extend that export whenever replay needs a new curve; never hand-copy
  numbers into server code.

### 3.3 Event catalog (initial)

Keep types coarse — one event per *player-meaningful transaction*, not per
simulation tick. Suggested opening set, matching current mechanics:

- `career.started` (record 0)
- `delivery.completed` — job id/lane, miles, gross pay, on-time flag, XP
- `advance.taken` / `advance.repaid`
- `fuel.purchased` — gallons, price, stop slug
- `repair.performed` — truck key, wear deltas, cost
- `truck.purchased` / `truck.sold`, `trailer.purchased` / `trailer.sold`
- `upgrade.purchased` — key, tier, price
- `endorsement.purchased` — key, price (earned ones are derived, never events)
- `toll.paid`, `fine.paid` (trooper stops, overweight)
- `item.granted` — the gated-collectible workhorse, section 4
- `item.consumed` — punch used, membership visit, pass shown

Rule of thumb an agent can apply without asking: **if it moves money, XP,
inventory, or a gated counter, it is an event; if it only moves the truck,
it is not.** Fatigue, HOS, weather, position: not events (they are
plausibility-checked as states, and cheating them only cheats the cheater's
own single-player realism).

### 3.4 Compaction

Ledgers grow. When a chain exceeds a size threshold, the server may issue
a signed **checkpoint**: a record summarizing derived state at `seq` N,
signed server-side, which becomes the new record 0 for future replays.
Clients never compact — only the server can, because only its signature
makes the summary trustworthy. Old segments can be archived or dropped
after checkpointing.

## 4. Gated items: the Golden Antler playbook

This section is the standing guidance Norm asked for: every time the game
grows a Big Buck's buff, a membership, a pass, or any possession that is
special, scarce, or purchasable, the feature must land **ledger-ready**,
and the server gets its check from this recipe rather than a fresh design
each time.

### 4.1 The rule

**Possession implies acquisition.** A profile may carry a gated item only
with the event trail that grants it. No trail, no item — the profile fails
validation. `docs/profile-invariants.md` rule 2.7 is the maintained
statement; this section is how implementations comply.

### 4.2 What the client side must ship with any new gated item

(Enforce this in review; it is also written into the roadmap upkeep rules.)

1. A stable item key (`golden_antler`, `big_bucks_punch_card`,
   `golden_flare`, `golden_ez_pass`, ...), listed in the catalog export so
   the validator knows it exists and what it costs (price 0 + granting
   event type for non-purchasable ones).
2. An `item.granted` event emitted at the acquisition moment, with `data`
   naming: the item key, the granting cause (`purchase`, `achievement`,
   `promotion`, `quest`), the cost paid (0 allowed), and the cause's own
   reference (job id, achievement id, promo id).
3. If consumable/limited: `item.consumed` events, and the profile's
   remaining-count field derived as grants minus consumptions.
4. An entry (or explicit "no new fields" note) in
   `docs/profile-invariants.md`, same PR — the standing maintenance rule.

### 4.3 What the server checks, per item class

- **Purchasable, unlimited (punch cards):** the `item.granted` purchase
  event must be affordable at replay time; remaining punches =
  grants×10 − consumptions, in range. Pre-ledger fallback: money history
  could afford it (rule 2.7 as written today).
- **Purchasable, one-per-career (memberships, golden EZ pass):** as above,
  plus at most one live grant; a second grant without an intervening loss
  event fails.
- **Never-purchasable trophies (GOLDEN ANTLER, Golden Flare):** the grant
  event must cite a cause the server can verify from the same ledger (the
  qualifying achievement/quest events precede it in the chain). **Until
  the acquisition path ships in any client, a profile claiming the item
  fails, full stop** — this is already the maintained rule; keep it teeth-
  first for every future trophy: ship the rejection before the item.
- **Session buffs (Big Buck's meal buffs, truck-stop tiers):** short-lived
  and cheap — do not ledger each application; ledger the *purchase* if it
  costs money, and plausibility-check the buff fields as ordinary state.

### 4.4 Worked example — GOLDEN ANTLER (when its path ships)

Client emits, in chain order: the qualifying trail (whatever the design
lands on — e.g. `delivery.completed` events satisfying the hidden streak,
then `item.granted {key: golden_antler, cause: "promotion",
ref: "antler_streak_v1"}`). Server replay: verify the cited trail
satisfies `antler_streak_v1` (rules versioned with `validator_version`),
verify exactly one grant, then and only then accept a profile whose
inventory carries the antler. Any profile with the antler and no such
chain — including every profile today — fails validation and is barred
from shared features until the item is removed.

## 5. Suggested build order (server side)

1. **Read the flag** (§2): strict-validate flagged uploads, log verdicts.
   Small, ships value immediately.
2. **Absolution** (§2): `clearIntegrityFlag` in the signed reply, plus the
   tiny client patch in `restore_to_disk`. Kills the false-positive pain
   before anyone complains about it.
3. **Chain-head signing** (§3.1 last bullet) with an empty event set —
   i.e., start signing *save lineage* (revision N extends revision N−1)
   before any events exist. This alone detects rewound/forked careers.
4. **Ledger v1** (§3.2–3.3) behind `validator_version`: accept ledgers
   when present, replay-verify, require them from client builds new
   enough to write them. Big Buck's punch card is the ideal pilot item.
5. **Compaction** (§3.4) when real ledger sizes justify it.

## 6. Boundaries — decided, do not relitigate

- No save encryption, no private-repo key material, no compiled-in
  secrets. A key that ships to the player is public; the cost lands on
  honest players (unportable saves, undebuggable bug reports) and the
  cheater spends an afternoon. The server gate + ledger achieve the goal
  without any secret in the client.
- Local single-player cheating is out of scope forever. The design marks
  it (so shared features can care) and otherwise leaves the player alone.
- Spoken text for any new rejection/notice is player language, no jargon,
  and gets tested with a screen reader — the game's standing a11y rule.
