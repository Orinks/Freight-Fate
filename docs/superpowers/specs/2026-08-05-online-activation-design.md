# Activation codes replace the clipboard in orinks.net setup

Date: 2026-08-05
Status: approved, not yet implemented
Repos: `Freight-fate` (branch `dev`), `orinks-net` (branch `dev`)

## Why

Connecting a computer to orinks.net currently requires the player to copy a
Driver ID and a driver token in a browser and paste both into the game. The
game reads the clipboard and guesses which value it got, using
`looks_like_driver_id` and `looks_like_token` to sort them out.

That design assumes the browser and the game share a machine. Freight Fate is
now playable on AGNow, a streaming service that runs the Windows build under
Wine, and there the assumption fails: the game's clipboard belongs to the
server-side container, not to the player's computer. The player copies their
token in their own browser and the game never sees it.

The clipboard has also been a steady source of platform edge cases on its own
merits -- an X11 selection-target bug fixed on `dev` in 2b952f21, a macOS
crash risk that forced a `pbpaste` fallback, a Tk fallback that no release
build actually ships because `tools/build_release.py` does not pass Nuitka
`--enable-plugin=tk-inter`, and a still-live UTF-16 decoding bug described
below. Each fix has been narrow and another platform has produced another
case.

Rather than fix Wine as one more special case, this removes the clipboard from
the credential path entirely and replaces it with an activation code.

## What the player does

1. In the game, chooses **Set up this computer with orinks.net**.
2. The game speaks an activation code and opens `orinks.net/activate` in the
   player's browser, with the code already in the URL.
3. Signed in on orinks.net, the player names the computer and confirms.
4. The game says the account is connected. Nothing was typed and nothing was
   copied.

When the browser cannot be opened, the game speaks the code and the address
and keeps waiting, so the flow still completes from any second device.

On AGNow the browser step works: the AGNow client intercepts the game's
request to open a page and asks the player whether to open it locally. Only
the clipboard fails to bridge, which is precisely what this design stops
using.

## Scope

In scope:

- Remove clipboard reading and all clipboard text parsing from the credential
  path in the game.
- Add an activation-code flow across Convex, the website, and the game.
- Remove the "copy this token" affordance from the setup page.
- Fix the UTF-16 decode bug in the surviving clipboard read-back helper.

Out of scope, deliberately:

- Clipboard *writing* stays. The delivery summary copy, the message review
  copy, and the Mastodon link copy are one-way conveniences with no parsing
  and no failure mode worse than nothing happening. They are useless on AGNow
  and harmless there.
- Existing connected installs are not migrated and not logged out.

## Server design (`orinks-net`)

### Table

One new table in `convex/schema.ts`:

```ts
freightFateActivations: defineTable({
  // sha256 of the game's secret device code, never stored in the clear --
  // same discipline as freightFateDeviceTokens.tokenHash.
  deviceCodeHash: v.string(),
  // The short code the player hears and types. Unique while pending.
  userCode: v.string(),
  status: v.union(v.literal("pending"), v.literal("claimed")),
  // Set when the signed-in player claims the code.
  driverId: v.optional(v.string()),
  // Computer name, captured on the activate page at claim time.
  label: v.optional(v.string()),
  createdAt: v.number(),
  expiresAt: v.number(),
})
  .index("by_device_code", ["deviceCodeHash"])
  .index("by_user_code", ["userCode"])
  .index("by_expires_at", ["expiresAt"]),
```

There is deliberately **no `lastPolledAt`**. A write on every poll is the one
thing in this design that could move Database I/O, which is the Convex metric
this project has already exhausted once. The poll is a pure indexed read.

### Endpoints

Three operations, following the existing `lib/freight-fate-online.ts` layer
between REST routes and Convex, with routes under
`app/api/freight-fate/activate/`.

**Start** -- `POST /api/freight-fate/activate/start`, unauthenticated. Mints a
32-byte `device_code` and a short `user_code`, inserts the row, and returns:

```json
{
  "device_code": "<64 hex chars>",
  "user_code": "WKQR-3468",
  "verification_uri": "https://orinks.net/activate",
  "verification_uri_complete": "https://orinks.net/activate?code=WKQR-3468",
  "expires_in": 600,
  "interval": 3
}
```

`interval` is the *initial* poll spacing; the game backs off from it as
described under Polling.

**Claim** -- a Convex mutation called from the activate page, authenticated by
the Clerk session. Looks up the pending row by `userCode`, provisions the
player's driver if they do not have one (the same `provisionDriver` path the
setup page already uses), records the label, and sets `status: "claimed"` with
`driverId`.

Claim does **not** mint a token.

**Poll** -- `POST /api/freight-fate/activate/poll`, authenticated by the
`device_code` alone. Reads the row by `deviceCodeHash`:

| Row state | Response |
| --- | --- |
| Missing or `expiresAt` passed | `expired` |
| `status: "pending"` | `pending` |
| `status: "claimed"` | mint device token, return it once, delete the row |

Minting at poll rather than at claim is the security core of the design. A
plain token never rests in the database -- it exists for exactly one response
and is stored only as a hash on the new `freightFateDeviceTokens` row. It also
means someone who overhears a spoken activation code and claims it first gains
nothing: the token is returned only to the holder of the secret `device_code`,
and the real player's activation simply fails and can be retried.

### Code format

Eight characters from a 27-character alphabet -- the 36 alphanumerics with the
mishearable ones removed: `O`, `I`, `L`, `S` and `Z` from the letters, `0`,
`1`, `2` and `5` from the digits, leaving 21 letters and the digits `3`, `4`,
`6`, `7`, `8`, `9`. Formatted in two groups of four (`WKQR-3468`).
Case-insensitive on entry; the dash is optional on entry. That is roughly
2.8e11 combinations against a ten-minute window, which is ample.

Ten-minute expiry.

`userCode` must be unique among rows that are still pending. Start re-mints on
collision rather than failing, retrying a small fixed number of times.

### Rate limiting

The existing limiter in `convex/freightFateRateLimit.ts` keys counters by
`driverId`, which does not exist yet at start time. Therefore:

- **Start**: keyed by client IP at the route layer.
- **Claim**: keyed by Clerk `authSubject` through the existing limiter.
- **Poll**: not rate limited server-side, and not counted. A caller can only
  poll a code whose secret it already holds, so fast polling harms nobody and
  reveals nothing; adding a counter would mean a write per poll, which is
  exactly the cost this design avoids. Generic HTTP flooding is an edge
  concern, not a Convex correctness one.

### Cleanup

Expired rows are swept by extending the existing hourly cron in
`convex/crons.ts` (the rate-limit sweep) rather than adding a second cron. The
sweep is batched and uses the `by_expires_at` index.

## Website design (`orinks-net`)

### New page: `/activate`

A short vanity route -- one word, easy to speak, easy to type, hard to
mishear. It renders the code-entry form directly rather than redirecting.

- With `?code=` present, the field is pre-filled and the player only confirms.
- Without it, the player types the code.
- A computer-name field defaults to something sensible and is captured with
  the claim.
- On success: a confirmation telling the player to return to the game.
- On a code that is unknown, already claimed, or expired: a plain-language
  error saying to start setup again in the game.

Accessibility requirements for this page, which are contractual and not
aspirational: a form with a real `<label>` for both fields, validation errors
associated with `aria-describedby` and announced via a live region, a visible
focus ring, submit reachable and operable by keyboard alone, and the success
and error states announced rather than conveyed by color or position alone.
The existing `setup-client.test.tsx` is the pattern for covering this.

### Setup page change

The "copy this token" display and its copy buttons are removed. Once no game
build accepts a paste, a token on screen is a secret with nothing to do.

The device list stays exactly as it is: naming and revoking computers is
unchanged, and revoking is still just deleting the row.

## Game design (`Freight-fate`)

### Removed

From `src/freight_fate/states/online_states.py`:

- `read_clipboard_text()`
- `looks_like_driver_id()`, `looks_like_token()`
- `_TOKEN_PREFIX`, `_ID_CHARS`
- `OnlineSetupState._paste_id`, `._paste_token`
- The captured `_driver_id` / `_token` menu state and the **Connect and save**
  item -- polling completes the flow, so there is nothing left to confirm.

From `tests/test_online_clipboard.py`: the `looks_like_*` cases.

### Deliberately retained

`_clipboard_once()` stays. `write_clipboard_text()` verifies its write by
reading back through `_clipboard_holds()`, and on macOS that read-back is
`pbpaste`. The accurate statement is that the clipboard stops being a
*player-input channel* and that all parsing of clipboard text is gone -- not
that the read code disappears.

### Bug fixed in the retained path

`_clipboard_once()` tries `pygame.SCRAP_TEXT` then `"text/plain;charset=utf-8"`
and decodes whichever answers as UTF-8. Verified on Windows: the first maps to
`CF_TEXT`, but the second maps to `CF_UNICODETEXT` and returns **UTF-16LE**
bytes. The path survives today only because `_clean_clip` strips NULs, which
accidentally reassembles ASCII while silently dropping every non-ASCII
character. It is unreachable on native Windows because `CF_TEXT` answers
first, but reachable under Wine, where an X11 clipboard owner advertising only
`UTF8_STRING` can leave `CF_TEXT` empty. Fix: decode per format rather than
assuming UTF-8 for both.

### New module: `src/freight_fate/online_activation.py`

Pairing lives in its own module rather than growing `online_presence.py`,
which is already 726 lines. One purpose, two functions, one dependency:

```python
def start_activation(*, transport: Transport = _http_json) -> Activation | None
def poll_activation(activation, *, transport: Transport = _http_json) -> str
```

`Transport` is the same injected seam `online_presence` already uses, so tests
never touch the network.

### Menu

`OnlineSetupState` keeps a static menu, as its docstring requires -- players
build positional memory of spoken menus and `refresh()` preserves indices, not
item identity. Four items:

1. **Set up this computer with orinks.net** (label carries progress)
2. **Say my activation code again** (spells the code phonetically)
3. **Hear what gets shared**
4. **Cancel**

### Polling

A daemon thread posts outcomes to the existing `_outcome` mailbox that
`update()` already drains, matching the pattern the current `_connect` uses. A
`threading.Event` stops the worker when the player leaves the menu, so backing
out never leaves a thread polling into a dead state.

Interval: 3 seconds for the first 30 seconds, then 8 seconds, until the
ten-minute expiry. With the code pre-filled in the URL, a typical successful
setup costs five to eight polls.

### Spoken behavior and errors

Every case is spoken and none is a dead end:

| Case | Spoken outcome |
| --- | --- |
| Start fails (offline) | Could not reach orinks.net; try again |
| Waiting | The code, then "still waiting" once at five seconds |
| Browser would not open | Speaks the address and the code, keeps polling |
| Code expired | Says so, and to choose setup again for a new code |
| Already claimed elsewhere | Says so, and to choose setup again |
| Token save fails | The existing keyring-failure message, reused verbatim |

The `device_code` is never spoken and never written to the transcript. The
activation code is safe to speak: on its own it grants nothing.

`docs/ontology.md` gains an **activation code** row. Spoken text uses that
noun and no synonym -- never "pairing code", "device code", or "setup code".

## Cost

Convex writes per successful setup: one insert at start, one patch at claim,
one patch plus one device-token row at the consuming poll. Four small writes,
against roughly two today. Reads: one ~200-byte indexed row per poll, five to
eight times.

For scale: presence heartbeats fire every 150 seconds, so one player driving
for an hour costs 24 requests. A computer's entire lifetime activation cost is
less than twenty minutes of one player driving, and it happens once per
computer, ever. Vercel invocations follow the same numbers.

Clerk is unaffected: same account, same sign-in, same page the player already
visits. No new monthly active users.

## Multiple computers

`freightFateDeviceTokens` is unchanged -- one row per computer, revocable from
the device list. Activation only changes how each row's token reaches the
machine. Two things improve:

- The **label is captured at claim time**, so the player names the computer
  they are actually sitting at. Today a token is named on the website before
  anyone knows which machine will use it, and the names drift.
- The **first computer and the fifth are the same four steps**. Today they
  diverge: provision-and-copy versus add-device-and-copy.

## Compatibility

Existing installs keep working untouched. The legacy `driverTokenHash` and all
existing `freightFateDeviceTokens` rows are still accepted by
`acceptDriverToken`, so no player is logged out and no migration runs. What
disappears is the ability to connect a *new* computer by pasting, which is
replaced in the same release.

## Rollout

Order matters: **the whole flow is verified on a preview before anything
reaches production**, and then the website goes first. A game that starts an
activation against a server without the endpoint would strand new players with
no way to connect.

1. `orinks-net` `feat/activation-codes` to its preview. Walk the manual pass
   there.
2. Merge to `orinks-net` `dev` and re-check, since that is the branch the
   change will live on before release.
3. `orinks-net` to production.
4. Freight Fate to `dev`, reaching players through the nightly channel.
5. 1.9 picks it up at the next merge from `dev`.

## End-to-end testing on preview

Both halves must be testable together before anything reaches production.

### How the backends are split

`vercel.json` runs `npx convex deploy` before the Next.js build whenever
`CONVEX_DEPLOY_KEY` is set, and that key alone decides which deployment gets
written. Production holds a production deploy key; the Preview scope holds a
**preview** deploy key, which builds a fresh deployment named for the branch
and cannot write to production. Preview branches leave `CONVEX_URL` and
`NEXT_PUBLIC_CONVEX_URL` unset so the deploy fills them in, and `vercel.json`
names that variable explicitly rather than relying on framework detection.

This is worth stating because it was fixed as part of this work
(`orinks-net` `f4561aa`). The Preview scope previously held a *production*
key scoped to the `dev` branch, so every push to `dev` deployed Convex
functions straight to production while only the site was a preview. For a
schema change that is the difference between a test and an outage. If a deploy
ever lands somewhere unexpected, check which kind of key that scope holds
before looking anywhere else.

### What this branch needs

Nothing Convex-specific: `feat/activation-codes` inherits the preview deploy
key from the bare Preview scope like any other branch, and gets its own
deployment automatically.

Clerk is the one gap. Vercel has a branch-agnostic Preview value for
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` but **not** for `CLERK_SECRET_KEY`, so a
new preview branch has no server-side auth until that is set for its scope and
claim cannot work at all. Setting `CLERK_SECRET_KEY` once on the bare Preview
scope, from the development instance (`sk_test_`), removes the gap for every
future branch.

Clerk's development instance has test mode on by default: any
`you+clerk_test@example.com` address and any fictional phone number verify
with the code `424242`, sending nothing. That covers the sign-in half of the
manual pass without touching a real inbox.

The preview Convex deployment starts **empty** and is deleted five days after
creation on the Free plan. Empty is the right starting point here -- step 1 of
the manual pass is provisioning a driver from nothing.

The game points at the preview through the existing `FREIGHT_FATE_ONLINE_URL`
override:

```bash
FREIGHT_FATE_ONLINE_URL=https://<preview>.vercel.app uv run freight-fate
```

The manual pass to walk on preview:

1. Fresh install, no saved identity: start setup, hear a code, confirm in the
   browser, game connects.
2. Second computer: activate again, give it a different name, confirm both
   appear in the device list and both still work.
3. Let a code expire without claiming it; confirm the spoken recovery.
4. Enter a wrong code on the activate page; confirm the spoken error.
5. Cancel the menu mid-wait; confirm polling stops.
6. Claim a code from a second account; confirm the first game does not receive
   a token.

## Automated tests

**Game.** Using the injected `Transport`, so no network: start speaks the
code; a pending poll keeps waiting; a claimed poll adopts and saves the
identity; expiry speaks the recovery; an offline start speaks the failure;
cancelling stops the worker. Plus a UTF-16 read-back case for the clipboard
fix, and deletion of the `looks_like_*` cases.

**Convex**, alongside `convex/freightFate.test.ts`: claim binds the driver and
provisions one when absent; poll before claim is pending; poll after claim
mints exactly one token; poll after consume fails; expired rows are rejected;
a wrong `device_code` is rejected; claiming from a second account does not
leak a token to the first.

**Website**, following `setup-client.test.tsx`: pre-filled code path, manual
entry path, label capture, error states, and the accessibility requirements
listed above.

## Process obligations

- `CHANGELOG.md`: an entry under `## Unreleased`, player-facing language --
  this is CI-gated and the change touches `src/`.
- `ROADMAP.md`: a bullet in the current release-line section.
- `docs/ontology.md`: the **activation code** row, added in the same change.
- PR against `dev` in both repos, built from
  `.github/PULL_REQUEST_TEMPLATE.md`. Note that `orinks-net` PRs are locked by
  convention; that side pushes direct to `dev`.
