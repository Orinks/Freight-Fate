# Career Level Experience Polish Design

## Goal

Make the existing 30-level career ladder feel different as the player advances,
using spoken guidance, Career plan text, dispatch framing, and milestone
language. This slice should deepen the player experience without changing the
economy, save schema, level thresholds, or business unlock gates.

## Current Context

Freight Fate already has a complete 30-level career ladder from company driver
through leased-on owner-operator and own authority. The recent career training
arc improves the first company-driver hours, but later levels still rely on
fairly broad objective text. The next slice should make each level band feel
like a distinct career phase.

## Level Bands

The player-facing guidance should use these bands:

- Levels 1-3: first-week trust, safer freight, trainer support, and early
  service record.
- Levels 4-9: broader company lanes, reputation-building, endorsements, and
  reliable dispatch habits.
- Levels 10-13: senior company-driver identity, premium/specialized freight,
  and dispatch confidence.
- Levels 14-17: owner-operator preparation, cash cushion, buy-in readiness, and
  business-risk visibility.
- Levels 18-20: leased-on owner-operator operating discipline, margin, trailer
  programs, and reserve protection.
- Levels 21-24: authority prep, trailer strategy, direct-freight readiness, and
  working-capital discipline.
- Levels 25-30: own-authority/direct-freight growth, independent reputation,
  trailer fit, and profitable contracts.

## Design

Add a derived level-guidance layer, likely in a new
`src/freight_fate/models/career_level_guidance.py` module. It should read the
existing profile, career level, business status, money, reputation, deliveries,
and authority state, then return a small immutable guidance object with:

- title;
- terminal text;
- dispatch text;
- recommendation label;
- optional milestone text for level-up or rank review.

The layer must be save-compatible. It should not add fields to `Profile`, change
XP thresholds, or replace the existing business eligibility gates.

`career_objective()` should keep handling urgent practical states first, such as
low reputation, owner-operator buy-in readiness, authority readiness, and
authority activation. When no urgent gate dominates, it should delegate to the
new level-band guidance so levels 4-30 get more specific player-facing text.

## Speech And Accessibility

This design is audio-first. Any new milestone, recommendation, or level-band
guidance must be spoken through the existing terminal and dispatch-board paths,
not only shown visually in labels. Keyboard focus must stay predictable: if a
recommended dispatch row is focused automatically, the row label must explain
why it is recommended.

The guidance should avoid gamey wording. Prefer trucking language such as
"senior company lane," "business-prep load," "reserve-safe owner-operator
freight," "authority-readiness lane," and "direct freight with margin."

## Testing

Automated tests should cover representative levels and statuses rather than
manually grinding all 30 levels:

- company driver around levels 4, 10, and 14;
- owner-operator prep around levels 16-17;
- leased-on owner-operator around levels 18-20;
- authority prep around levels 21-24;
- own-authority around levels 25-30;
- low-reputation and ready-to-unlock states still override generic level
  guidance;
- terminal and dispatch-board speech include the derived guidance;
- one playtest or transcript proof confirms mid/late-career guidance is spoken.

## Out Of Scope

This slice does not change:

- XP thresholds;
- rank titles;
- delivery, reputation, money, trailer, or authority gates;
- settlement math;
- freight generation economics;
- save schema;
- full authority realism or new paperwork systems.

Those are separate future slices.
