# Career Training Arc Design

## Goal

Make the company-driver career feel believable before the owner-operator arc
begins. A new company driver should feel like a licensed new hire building trust
with dispatch, not like a student in a tutorial or a player waiting for numbers
to unlock.

The owner-operator path remains the long-term goal: company driver, senior
company driver, leased-on owner-operator, and eventually own authority. The
training arc gives that path a realistic foundation.

## Core Design

Every company start begins with a trust-based training arc. The driver is
already licensed and working real freight, but they are new to the carrier.
Dispatch starts them on safer freight, watches the first service record, and
gradually opens better lanes as the driver proves reliable.

Carrier choice changes the flavor, not the existence, of probation:

- Northstar Freight Lines is balanced.
- Great Lakes Training Transport is the most guided and forgiving.
- Prairie Link Regional moves toward regional mileage sooner.
- Summit Value Logistics is more appointment- and performance-focused.

The owner-operator start remains the bypass for players who want the higher-risk
business path immediately.

## Early Career Stages

The first company-driver stages are:

- 0 deliveries: first-day orientation and one strongly recommended starter run.
- 1-2 deliveries: concise trainer reminders and safer dispatch suggestions.
- 3 deliveries: probation tone reduces and dispatch trust starts to show.
- 4-9 deliveries: dispatcher-trust phase with broader recommendations.
- 10 or more deliveries: normal company-driver career guidance.

The three-delivery gate should not require perfect service. Bad runs already
affect money, reputation, dispatch quality, and later gates. The game should not
trap the player in a tutorial loop.

## Dispatch Board Behavior

Training should influence recommendations more than hard locks. The board should
clearly identify safer early-career freight while still letting the world feel
open.

The first dispatch should strongly recommend a short, standard, forgiving load.
Deliveries 1-2 should favor short or regional loads with practical appointment
room. Deliveries 3-9 should keep highlighting reliable lanes while allowing
broader options as trust grows. At 10 or more deliveries, recommendation wording
should become normal career guidance.

Avoid player-facing phrases like "probation load." They sound gamey and less
like real dispatch language. Use phrases such as:

- Trainer-recommended.
- Good first-week run.
- Good lane to build your record.
- Low-risk dispatch.
- Short regional run with room on the appointment.
- Good service-record load.

Recommendation text must be spoken as part of dispatch-board feedback, not only
shown visually in menu labels.

## Speech And Feedback

Speech should taper as the player proves reliable:

- First day: full briefing with carrier, assigned equipment, carrier-paid costs,
  first dispatch goal, and service-record framing.
- First 1-2 deliveries: concise trainer reminders.
- Deliveries 3-9: short trust-building objective, usually one sentence.
- 10 or more deliveries: normal career objective only.

There is no rebuild-mode lecture if reputation drops. Reputation loss should
affect dispatch quality, unlocks, settlement outcomes, or business gates, but
the player already knows the basic job. The game should not start over-explaining
because of a bad run.

Players must still be able to ask for guidance. The existing first-day briefing
can become the normal career-plan action after first dispatch, so details remain
available on demand.

## Progression Gates

The early gates should stay simple and readable:

- First dispatch: open the board and take a reasonable starter run.
- Probation complete: 3 deliveries, without requiring perfection.
- Dispatcher trust: around 10 deliveries and acceptable reputation.
- Owner-operator prep: levels 14-17 keep working capital and risk visible.
- Leased-on owner-operator: keep the existing level 18, 35 deliveries,
  reputation 80, no pay advance, and buy-in plus working-capital requirements.

This keeps the progression grounded: ownership becomes a business decision after
skill, reputation, and cash have been built.

## Accessibility And Playtest Notes

The design is audio-first. Any recommendation, guidance taper, or gate reason
must be available through spoken feedback. Menu labels alone are not enough.

Playtest with scenario saves rather than grinding the whole ladder every time:

- New company driver at 0 deliveries.
- Company driver at 1-2 deliveries.
- Company driver at 3 deliveries.
- Company driver at 10 deliveries.
- Low-reputation company driver.
- Level 14-18 owner-operator prep driver.
- Leased-on owner-operator.
- Own-authority driver.

Manual playtesting should answer one primary question: does the first hour feel
like building trust with dispatch?

Automated tests should cover speech text, recommendation wording, guidance
tapering, and gate logic.
