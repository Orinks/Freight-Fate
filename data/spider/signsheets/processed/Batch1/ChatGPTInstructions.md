# Instructions for ChatGPT — Freight Fate roadside sign sheets

Upload this file together with a corridor sheet. Your job: expand the sheet
with real roadside attractions and write the spoken sign copy in the game's
voice. Output must drop straight into the sheet's format so it bakes without
hand-fixing.

## Output format (exact)

Every sign is a Markdown block with HYPHEN bullets — not asterisks:

```
### Sign Name
- treatment: billboard
- leg: from_slug -> to_slug
- at_mi: 42
- spoken: Billboard: the line the game reads aloud.
- describe: optional human note; not read in-game.
```

- Keep the sign name on the SAME line as `###`.
- Use `-` (hyphen) bullets. Asterisk bullets (`*`) do NOT parse.
- No citation footnotes, reference markers, or links anywhere (e.g. no
  `([site][3])`). Facts only; we don't bake sources.

## Hard rules

1. **Spell out ALL numbers in `spoken:`** — "nineteen forty-two", never "1942";
   "sixty-five feet", never "65 feet". A bare digit makes the sign fail to bake.
2. **Billboards lead with `Billboard:`** in the spoken text. Landmarks do NOT.
3. **Only place signs on BUILT legs.** Each sheet lists its built legs at the
   top ("Built legs in this corridor"). Use ONLY those `from_slug -> to_slug`
   pairs. If a place is off the built network, set `- treatment: skip` and add
   a `**** ` note saying which leg it needs. A skip is safe; a wrong leg is not.
4. **`at_mi` is miles from the `from` city** of the leg. Estimate honestly; we
   can nudge it at bake time. Keep it between 1 and the leg's length.

## Billboard vs landmark (the balance)

Default every sign to `treatment: billboard` — the parody "Billboard:" voice is
the game's signature. Use `treatment: landmark` ONLY for:

- **Reverence** — memorials, battlefields, civil-rights sites, tribal/Indigenous
  land, military posts. A joke here would be tasteless.
- **Raw geography/nature** — mountains, rivers, canyons, passes, salt flats,
  forests, deserts. No advertiser exists, so a billboard would feel fake.

If a place could plausibly have a funny billboard, make it a billboard. Aim for
roughly four billboards to each landmark.

## Voice

Dry, affectionate, roadside-Americana humor. Short. A traveler hears these while
driving, so lead with the hook. Real facts underneath the jokes. When unsure of
a fact (a festival's exact name, an attraction's current status), keep the joke
and add a `**** verify ...` note rather than inventing specifics.

## Notes you can leave

Lines starting with `**** ` are review notes for the humans — flag anything you
placed provisionally, any access/accuracy caveats, or ideas held for a leg that
doesn't exist yet. The baker ignores these lines.
