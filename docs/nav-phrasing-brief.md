# Navigation phrasing brief: talk like a GPS, not like a database

Owner design session, 2026-07-20. **This ships independently of the lane
harvest — do not block it on that job.** For Phil (coding); no map work
required for the mainline half.

## The problem

The game currently announces something like "in 2 miles continue to the
Camp Verde, AZ / Payson, AZ corridor". That is the leg key read aloud.
It is the internal data model leaking into player speech, and the map
recipe's own invariant already forbids it: *"Everything named is spoken
... no slug keys, no 2-letter state codes, no raw OSM tags."*

What a driver — or a co-driver — actually says is:

> "Continue on AZ-260 toward Payson, 32 miles."

Same information, minus the schema.

## The mainline half needs no new data

Verified on the shipped world (2026-07-20): the leg for Camp Verde →
Payson already carries everything the sentence needs.

```
leg.a / leg.b : camp_verde_az_us / payson_az_us
leg.highway   : 'AZ-260'
leg.miles     : 58.0
```

The road number, the destination city, and the distance are all present.
This is a speech-layer change only.

Two things to get right:

- **Speak the shield, not the ref string.** "AZ-260" must reach the
  player as "Arizona 260" (or "State Route 260"), never as raw
  characters. That is [[project-highway-shield-speech]], already tracked
  — this work depends on it and should land with it.
- **Name the city, not the slug.** `payson_az_us` → "Payson". Where the
  destination is the route's final city, say so once rather than
  repeating it at every prompt.

## The interchange half IS gated on the harvest

The owner's second sentence — "stay left to stay on I-40 toward
Nashville; take the second lane to merge onto I-64 toward Richmond" —
needs data we have not collected:

- the city on the sign comes from `destination` / `destination:ref` on
  the `motorway_link` ways
- the lane ordinal comes from `turn:lanes` / `destination:lanes`
- the lane count comes from `lanes` / `lanes:forward`

All are specced in [[docs/lanes-harvest-brief.md]] (item 7 added
2026-07-20 for the `destination` tags specifically). Until that bake
lands, interchange callouts stay at the level of detail we can prove.

**The governing rule from that brief applies here too: never speak a
lane ordinal we did not harvest.** With only a count and a side, say the
side — "stay left" is honest on partial data; "take the second lane" is
not.

## Why this matters more than it sounds

For a sighted driver the corridor phrasing is merely clumsy. For a blind
driver, spoken navigation *is* the whole interface — there is no glance
at a sign to correct a confusing sentence. Wording that reads as
internal jargon costs orientation, not just polish.
