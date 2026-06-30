# HOS Regulations Design

## Goal

Bring Freight Fate closer to the FMCSA property-carrier hours-of-service rules
without turning driving into a compliance spreadsheet. The first playable slice
is sleeper-berth split rest. The design must also leave clean room for the
remaining regulations the game does not yet model: 60/70-hour cycle limits,
34-hour restart, adverse driving condition extensions, and short-haul
exceptions.

Source: FMCSA summary of hours-of-service regulations, reviewed June 29, 2026:
https://www.fmcsa.dot.gov/regulations/hours-service/summary-hours-service-regulations

## Current Game Model

Freight Fate already models the core shift rules:

- 11 hours of driving time.
- 14-hour duty window.
- 30-minute break after 8 cumulative driving hours.
- Full 10-hour sleep reset.
- ELD statuses for driving, on-duty-not-driving, off-duty, and sleeper berth.
- HOS warnings, fatigue, rest-stop menus, parking scarcity, inspections, fines,
  and out-of-service resets.

The current model intentionally skips split sleeper and cycle limits. That makes
sleeper split rest the lowest-risk realism upgrade because the save schema
already records duty status and rest actions.

## Player-Facing Scope

Both player HOS modes support the same sleeper-berth mechanic:

- Realistic keeps the FMCSA-style 11-hour and 14-hour shape.
- Relaxed keeps the same sleeper choices and split-pair rules, while retaining
  its existing gentler HOS limits.

The game should not mention internal developer-only HOS modes in player-facing
menus, help, manual text, or release notes.

## Sleeper Berth Meaning

Use the regulation term `sleeper berth`, not `sleeper birth`.

In Freight Fate, the sleeper berth is the bunk in the truck cab. Any legal
sleep-capable truck parking location can support sleeper-berth rest, including
travel centers, truck stops, public rest areas, and truck parking areas. The
game does not need a separate "sleeper facility" data flag.

Emergency shoulder sleep remains a fallback, not a planned sleeper split tool.
Emergency lot sleep at non-sleep stops remains a poor full reset and should not
create a clean split-rest period.

## Sleeper Split Rules

At any stop with the `sleep` action, the rest menu offers deliberate player
choices:

- Sleep 2 hours in sleeper berth.
- Sleep 3 hours in sleeper berth.
- Sleep 7 hours in sleeper berth.
- Sleep 8 hours in sleeper berth.
- Sleep 10 hours.

The full 10-hour sleep remains the simple reset: fresh HOS clock and fully
cleared fatigue.

The split-rest system recognizes these qualifying pairs:

- 8 hours in sleeper berth plus 2 hours off duty or sleeper berth.
- 7 hours in sleeper berth plus 3 hours off duty or sleeper berth.

The long period must be in sleeper berth. The shorter qualifying period may be
off duty or sleeper berth. The two qualifying periods must total at least 10
hours and neither qualifying period counts against the 14-hour duty window.

When a valid split pair completes, the HOS clock recalculates available driving
and duty time from the end of the first qualifying rest period, rather than
doing a full fresh-shift reset. This should give the player useful time back
without erasing the history of the shift.

## Status And Guidance

Player wording should explain planning consequences in short plain English:

- A stop callout can say "sleeper berth rest available" when a sleep-capable
  stop is upcoming.
- The rest menu help should say what each split option can pair with.
- HOS status should report a pending split when useful, such as "Sleeper split
  pending: pair this with 2 more hours off duty or sleeper berth."
- After a split completes, speak a short confirmation that the sleeper split was
  credited and say the current HOS summary.

Avoid legal jargon beyond the term "sleeper berth." Do not expose raw ledger
fields, source data, or internal mode names.

## Fatigue

Split rest should reduce fatigue proportionally but should not always make the
driver perfectly rested:

- 2-hour and 3-hour periods reduce fatigue modestly.
- 7-hour and 8-hour periods reduce fatigue substantially.
- A completed qualifying split may leave a small fatigue floor if neither period
  was a full 10-hour sleep.
- A full 10-hour sleep still clears fatigue completely.

The exact fatigue numbers can be tuned during implementation tests. The rule
should feel intuitive: more sleep helps more, but the full reset is still the
cleanest rest.

## Other Missing Regulations

The first implementation should not enforce these yet, but it must avoid data
model choices that block them.

### 60/70-Hour Cycle Limit

Future work should track on-duty time across multiple in-game days:

- 60 hours in 7 consecutive days for carriers not operating every day.
- 70 hours in 8 consecutive days for carriers operating every day.
- Freight Fate likely defaults to the 70-in-8 rule for long-haul career play.

The HOS ledger should preserve enough duty-status history to sum rolling on-duty
time later. Split-rest implementation should therefore store rest periods as
events or compact history entries, not only as current counters.

### 34-Hour Restart

Future work should allow 34 consecutive off-duty/sleeper hours to reset the
cycle clock. This is separate from the current 10-hour shift reset.

Implementation should keep full-sleep and split-sleep logic separate from
cycle-restart logic so a later 34-hour restart does not require rewriting shift
rest.

### Adverse Driving Conditions

Future work may grant up to two extra hours when the trip hits qualifying
unexpected weather or road conditions. Freight Fate already has weather and road
events, but the extension must be explicit and spoken so players understand why
time changed.

This should be a deliberate rule state, not a hidden blanket bonus. It should
only apply to relevant conditions and should not hide reckless planning.

### Short-Haul Exception

Future work may model a short-haul exception for local work. Since Freight Fate
currently centers on longer dispatches, this should wait until local delivery or
yard/regional jobs exist. Do not complicate current long-haul menus with
short-haul wording.

## Data Model Direction

Add a compact HOS history alongside existing counters. Each entry should record:

- status: driving, on-duty-not-driving, off-duty, or sleeper berth.
- duration in game minutes.
- whether the period was created by normal parking, emergency lot sleep,
  shoulder sleep, inspection out-of-service reset, or another action.
- enough timing order to evaluate split pairs and later rolling cycle limits.

Older saves without history should load safely by creating a history from the
current counters where possible, or by continuing with current counters only
until new events are recorded.

## Testing And Verification

Focused automated coverage should include:

- 8+2 split restores legal time without a full reset.
- 7+3 split restores legal time without a full reset.
- Long period must be sleeper berth.
- Short period can be off duty or sleeper berth.
- Full 10-hour sleep still performs the existing reset.
- Emergency lot and shoulder sleep do not create clean split-rest credit.
- Relaxed mode supports the same split-pair choices.
- Save/load preserves pending and completed split history.
- HOS warnings and summaries remain understandable with pending split state.

User-facing verification should include a manual or playtest-harness pass that
opens a rest menu at a sleep-capable stop, confirms the new choices are spoken,
takes a split period, and confirms the HOS status explains the pending or
completed split.

Accessibility impact: this feature changes spoken menus, help, and status text,
so verification must include an accessibility-agent pass for menu wording,
screen-reader flow, and status clarity.

## Out Of Scope For First Implementation

- Enforcing 60/70-hour cycle limits.
- Implementing 34-hour restart.
- Implementing adverse-condition extension.
- Implementing short-haul exception.
- Adding new external data sources for sleeper support.
- Making shoulder sleep a normal split-rest planning option.
