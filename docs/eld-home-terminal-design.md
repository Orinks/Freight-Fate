# ELD Depth and Home Terminal Design

This is the design plan for two interlocking 1.10-line features: making the
electronic logging device model the parts of the real regulation that shape
a driver's *week* (not just their day), and making the home terminal a
gameplay anchor instead of a spawn point. They ship together because in the
real rules they are the same system: a driver's home terminal sets the time
zone their logs are kept in and anchors the short-haul exemptions.

Everything here keeps the audio-first posture: every new state is a spoken
status line, every decision is a menu the screen reader can walk, and no
mechanic depends on reading a visual gauge.

## Where the system stands today

- `HosClock` (`src/freight_fate/sim/hos.py`) models the daily core: the
  11-hour driving limit, the 14-hour duty window, and the 30-minute break
  after 8 cumulative driving hours (`BREAK_MIN`), with spoken summaries and
  three player-selectable enforcement modes.
- `DutyLog` (same module) keeps a rolling Record of Duty Status; the in-cab
  logbook screen speaks it, and traffic stops read the recent entries.
- Fatigue is a separate meter with motel/sleeper rest; CB chatter and
  weigh-station enforcement already exist as pressure sources.
- The profile records `current_city` but has no persistent home terminal;
  the career start city is forgotten once you drive away.
- The timezone system keeps an absolute Eastern clock with local views --
  the ELD currently displays local time, not home-terminal time.

## Goals

1. **The week is the unit of play.** A rolling 70-hour/8-day cycle makes a
   hard week accumulate and makes the 34-hour restart a planning decision.
2. **Home has gravity, not a leash.** Restarting at your home terminal is
   free and restorative; restarting on the road costs money and comfort.
   Wandering is always allowed -- it just forgoes the perks.
3. **The ELD is a character.** Certification prompts, carrier edit
   requests, personal-conveyance judgment calls, and the occasional
   malfunction give the device texture beyond a countdown.
4. **Old saves keep working.** Every new field defaults sensibly; a 1.9
   save resumes mid-trip with a fresh cycle and its home terminal set to
   the career's current city (with a one-time spoken note).

## Phase 1 -- The 70-hour cycle and the 34-hour restart

The centerpiece. `HosClock` gains a rolling 8-day on-duty ledger:

- **Cycle math.** Sum of on-duty (driving + not-driving) hours over the
  trailing 8 days; at 70 hours no new driving until hours age out or a
  34-hour consecutive off-duty restart clears the ledger.
- **Spoken surfaces.** The ELD status line gains one clause ("42 of 70
  cycle hours used; restart clears Thursday morning"). The logbook gains a
  per-day cycle recap. Dispatch lane notes gain hour-awareness ("tight on
  cycle hours; this load fits with 6 to spare").
- **Restart as a decision.** Sleeping 34 consecutive hours anywhere clears
  the cycle. At the home terminal it is free (your own bed). On the road it
  costs motel nights or sleeper discomfort (reduced fatigue recovery), so
  routing your week home becomes the natural optimization.
- **Enforcement modes.** The existing relaxed/standard/realistic HOS modes
  scale the cycle the same way they scale the daily clock (relaxed shrinks
  the ledger's bite; realistic enforces it exactly).
- **Save compat.** The ledger serializes inside the existing `hos` payload;
  absent in old saves means an empty ledger (fresh cycle), matching how
  `HosClock.from_dict` already treats missing data.

## Phase 2 -- Home terminal as anchor

- **Persist it.** `Profile.home_terminal_city` (slug key), set at career
  creation from the chosen home city. Old saves default it to
  `current_city` on first 1.10 load with a one-time spoken note ("Your
  home terminal is on record as Fort Wayne; change it at any company
  terminal.").
- **ELD time zone.** The duty log and ELD readouts speak home-terminal
  time, matching the real regulation. One line of flavor with real
  teaching value; the local clock stays available on the time readout.
- **Free restarts at home.** See Phase 1. Add a "home for the reset"
  dispatch objective family: loads that route you home near cycle
  exhaustion carry a spoken note and small reputation reward.
- **Terminal services.** The home terminal's garage discounts repairs and
  washes (carrier goodwill for company drivers, your own tools after the
  owner-operator buy-in). Assigned fleet tractors are picked up and handed
  back there at upgrade time, which the fleet-tier system already stages.
- **Relocation.** Owner-operators may move their domicile at a real cost
  (a settlement fee and a fresh-relationships penalty); company drivers
  request a transfer, granted after a service streak.

## Phase 3 -- Local board and the short-haul identity

The real 150-air-mile short-haul exemption becomes an early-career texture
choice at the home terminal:

- **Local board.** A second dispatch surface offering short runs inside
  the home region: home every night (automatic overnight at the terminal),
  lighter paperwork (no log certification prompts), lower pay per mile,
  and no cycle pressure while the week stays local.
- **OTR board.** The existing board, full ELD regime, better money.
- **Progression fit.** Levels 1-7 (assigned dispatch) can weight local
  loads for new hires -- learn the truck close to home, then earn the long
  lanes; level 8's load choice then includes choosing which board to work.
- **Radius rule.** Straight-line distance from the home terminal decides
  eligibility, spoken plainly ("within your local radius").

## Phase 4 -- The ELD as a character

Smaller, staged events once the cycle exists:

- **Daily certification.** At shutdown or the first stop after midnight, a
  one-key "certify yesterday's log" prompt. Habitual non-certification
  surfaces at the next inspection as a violation note.
- **Carrier edits.** Occasionally dispatch proposes a log edit ("we marked
  your dock wait at Owensboro as on-duty; approve or reject"). Accepting a
  false edit risks an audit event later; rejecting a true one costs a
  little dispatcher goodwill. Rare, spoken, two-key resolution.
- **Personal conveyance.** A duty status usable after hours to bobtail to
  food, fuel, or parking without touching the clock; distance-limited, and
  a pattern of stretching it draws an enforcement question at the next
  stop.
- **Yard moves.** On-property moves at facilities log as yard time, not
  driving. Mostly automatic bookkeeping the facility states can set.
- **Malfunction event.** Rarely, the ELD drops out mid-trip: the game
  switches to spoken "paper log" mode (the player confirms status changes
  manually for the rest of the day), and a roadside stop during the outage
  reads tenser. Repairing at any terminal garage ends it. Frequency tuned
  very low; it is drama, not friction.
- **Adverse conditions exception.** When live weather turns severe
  mid-route, the ELD grants and logs "+2 hours driving, adverse
  conditions" -- weather finally talks to the clock.

## Sequencing and scope guards

Phase 1 and the Phase 2 persistence/restart work are the 1.10 centerpiece
and land together (the cycle is dull without the home restart, and home is
toothless without the cycle). The local board is next -- it reuses the
dispatch board plumbing. Phase 4 events are independent garnishes, each
one small and individually shippable.

Scope guards:

- No punishment for ignoring home: every home perk is a bonus, never a tax
  on staying out.
- No new meters to babysit: the cycle speaks through the existing ELD
  status key and logbook; certification and edits are single prompts.
- The dispatch game and freightverse driver exchange read the profile: new
  fields (`home_terminal_city`, cycle ledger) must be additive and
  optional in the exchange format.

## Verification

- Unit coverage in `tests/test_hos*.py` style: cycle accrual, aging-out,
  restart clearing, mode scaling, and save round-trips with and without
  the new fields.
- Harness playtests: a scripted "hard week" (five loads back to back)
  must produce the spoken cycle warnings, a forced restart decision, and
  a clean week after a home restart; transcripts checked with the usual
  regression scans.
- A stale-save fixture from 1.9 resumes cleanly, hears the one-time home
  terminal note, and shows an empty cycle ledger.
