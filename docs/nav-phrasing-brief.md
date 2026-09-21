# Navigation phrasing brief: talk like a GPS, not like a database

Owner design session, 2026-07-20. **This ships independently of the lane
harvest — do not block it on that job.** For Phil (coding); no map work
required for the mainline half.

## The problem

**Corrected 2026-07-20 after tracing it in-engine.** My first reading was
that the leg key was leaking into speech. It is not. The corridor wording
is a **placeholder checkpoint name baked into the world data**, spoken
verbatim by the existing checkpoint cue. Rendered on a real trip:

```
Cullman -> Birmingham | I-65 | 51.0 mi | 1 checkpoint
   'Passing I-65 corridor between Cullman and Birmingham, Alabama on I-65.'
```

The sentence names a corridor as though it were a town and says I-65
twice. **246 checkpoints (7.3% of 3,380) carry these stubs.** The map
recipe's own invariant already forbids them: *"Everything named is spoken
... Never invent a place."* A corridor is not a place.

So this is a **data** fix first and a phrasing fix second: the stubs
should be deleted, not reworded. There is nothing to say about the
midpoint of I-65 between two cities, and saying nothing is the honest
result the recipe explicitly allows.

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

## Why the player rarely hears the towns he passes

Owner report, 2026-07-20: "I don't usually hear cities I'm passing on the
interstate." Measured, and he is right — the checkpoint layer is thin:

- **3,380 checkpoints across 1,287 legs**, and **480 legs carry exactly
  one.** Flagstaff → Kingman is 151 miles of I-40 and speaks a single
  callout, "Passing Seligman, Arizona on I-40," at mile 77.5.
- **8.5% sit at the exact leg midpoint** — a generated position, not a
  surveyed one, which is where the stubs cluster.

**Checkpoints and villages are different systems.** Checkpoints are the
older, sparse, hand-and-tool-curated layer. The village sweep
(2026-07-20) baked **26,894** real OSM places across 1,280 legs with
real offsets — roughly eight times the density, all real, none invented.

Recommended split once villages merge:

- **Delete the 246 stubs.** They are anti-information: they occupy the
  one callout a leg gets and spend it on a sentence with no referent.
- **Let villages carry "where am I passing."** That is what they are and
  there are enough of them to actually answer it.
- **Keep checkpoints for genuinely notable places** that deserve naming
  independent of settlement size.

This also removes the reason the corridor wording exists at all.

## Why this matters more than it sounds

For a sighted driver the corridor phrasing is merely clumsy. For a blind
driver, spoken navigation *is* the whole interface — there is no glance
at a sign to correct a confusing sentence. Wording that reads as
internal jargon costs orientation, not just polish.
