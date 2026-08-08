# Offering the orinks.net connection to a first-time player

Date: 2026-08-06
Status: approved, not yet implemented
Repo: `Freight-fate`, branch `dev`

## Why

Connecting a computer to orinks.net now takes one activation code and a
browser confirmation, but nothing tells a new player it exists. The setting
lives under Online on the main menu, and a player who never opens that menu
never learns there is cloud backup or a drivers board at all.

The fix is discoverability, not persuasion: offer it once, at a moment that
makes sense, and then leave the player alone.

## What this is not

**Online is optional and stays optional.** Freight Fate is fully playable
offline, and nothing here gates a career behind an account, a sign-in, or a
network round trip. A first-time player who wants to drive a truck must be
able to decline in one keypress and never think about it again.

This matters more than usual for this audience. A player working entirely by
ear cannot skim past a prompt; every word is time spent before the first mile.
An offer that repeats, or that buries the decline, costs them far more than it
costs a sighted player skipping a modal.

## When it appears

Immediately after career creation, before the first drive.

Career creation (`states/main_menu.py`, the city picker's confirm path) pops
its three pickers, pushes `CityMenuState`, and speaks "Welcome aboard, *name*
… Your first stop is the dispatch board." The offer sits between that and the
dispatch board, so the player hears it while they are already stopped and
oriented, and lands exactly where they were told they would.

It does **not** appear before career creation. Putting a browser round trip
and a sign-in in front of someone who launched a single-player game is the
wrong trade, and it would mean choosing an orinks.net driver name before the
in-game one exists.

## When it does not appear

- Once the player has seen it, ever. One offer per install.
- When an online identity already exists, whether or not the offer was seen.
  A second career on a connected computer must not ask again — the connection
  is per computer, not per career.

## The gate

A new per-install setting, `online_offer_seen`, default false. Set true the
first time the offer is shown, on either path out of it, before anything else
can interrupt.

Per-install, not per-profile: `Profile` already carries one-time flags
(`migration_notice_pending`, `integrity_notice_pending`), but those describe
something true of one save. This describes something true of this computer,
so it belongs in settings alongside the other online preferences.

## The state

`OnlineOfferState`, a `MenuState` built in the mould of
`SaveMigrationNoticeState` in `states/save_notice.py`:

- `announce_entry` speaks the offer, then the current item.
- Two items: **Set up now** and **Not now**.
- The cursor starts on **Not now**, and Escape takes that path too. For a
  one-shot consent prompt the low-effort answer should be the one that changes
  nothing. The player must never be able to get stuck here.
- Either path clears the gate and `replace_state`s onward, so the offer cannot
  reappear even if the game is closed mid-prompt.

Career creation pushes `OnlineOfferState` in place of `CityMenuState` when the
gate is open, and `CityMenuState` directly otherwise. The offer's own exit
paths put `CityMenuState` on the stack, so the destination is the same either
way.

## Saying yes

Goes straight into activation: `OnlineSetupState` with a new flag that starts
setup on entry, rather than dropping the player into a five-item menu where
they choose "Set up this computer with orinks.net" as a second confirmation.
They already said yes; asking twice is friction dressed as safety.

Everything else is reused unchanged — the spoken code, the phonetic spelling,
the copy item, the poll loop, and every error path.

Backing out of setup afterwards lands in the city menu, not back in the offer.

## Saying no

Speaks one short line naming where to find it later — Online, on the main menu
— and enters the world. Nothing else. No "are you sure", no second chance.

## What the copy must and must not claim

Connecting an account does **not** switch on cloud backup or the drivers
board. Both stay off until the player enables each one separately, which is
deliberate and documented in the activation spec.

So the offer must not be sold on them. A player who connects because they
heard "cloud backup", then never enables it, believes their career is
protected when nothing is being backed up — a worse outcome than never
offering at all.

The honest framing is what connecting actually does: it links this computer to
an orinks.net account, which is what lets cloud backup and the drivers board
be turned on later, from Online. Say that, name where Online is, and stop.

Use the canonical spoken nouns from `docs/ontology.md`. Add a row for this
prompt's concept in the same change if it needs one.

## Testing

- The offer appears after creating a first career, and the gate is set.
- It does not appear on a second career creation.
- It does not appear when an online identity already exists, even with the
  gate open.
- **Not now** reaches the city menu.
- Escape behaves exactly as **Not now**, including setting the gate.
- **Set up now** reaches `OnlineSetupState` with the activation already
  started — assert the start call happened, not merely that the state was
  pushed.
- The spoken offer names Online as the later route, and does not promise cloud
  backup or the drivers board as things connecting turns on.

Tests inject a transport so nothing touches the network, and run headless with
`FREIGHT_FATE_NO_SPEECH=1`.

## Process obligations

- `CHANGELOG.md`: an entry under `## Unreleased`, player-facing language —
  CI-gated, because `src/` changes.
- `ROADMAP.md`: a bullet in the current release-line section.
- `docs/ontology.md`: a row if this introduces a spoken concept.
