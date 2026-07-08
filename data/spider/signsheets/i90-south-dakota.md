# Sign sheet — I-90, South Dakota (pilot, EDITABLE)

This is the bake input. Read it, change anything, then I bake it onto the real
legs. Facts from public data (Travel South Dakota, Wall Drug/Wikipedia); copy
invented.

**How to edit each block:**
- `treatment:` — `billboard` (parody sign) or `landmark` (respectful factual
  callout). Set to `skip` to drop the sign entirely.
- `leg:` / `at_mi:` — which real leg and how many miles from the leg's `from`
  city. **at_mi values are ESTIMATES** — change freely; the bake rounds/orders.
- `spoken:` — exactly what is said (billboards keep the `Billboard:` lead so
  placed signs sound like the random-pool ones). Numbers spelled out.
- `describe:` — OPTIONAL. The longer read you'd hear if you PULL IN (the
  two-piece model). Only stoppable destinations have one; the pull-off mechanic
  comes later, but the words are banked now.

Legs on this corridor: `sioux_falls_sd_us -> mitchell_sd_us` (73 mi) and
`mitchell_sd_us -> rapid_city_sd_us` (278 mi).

---

### Porter Sculpture Park
- treatment: billboard
- leg: sioux_falls_sd_us -> mitchell_sd_us
- at_mi: 32
- spoken: Billboard: A sixty-foot bull's head is staring at you from the prairie. That is Porter Sculpture Park. Pull over. It wants to be looked at.

### Corn Palace
- treatment: billboard
- leg: sioux_falls_sd_us -> mitchell_sd_us
- at_mi: 63
- spoken: Billboard: The Corn Palace, next exit. A building decorated entirely in corn. Redecorated every year. In corn. We cannot stress the corn enough.
- describe: The Corn Palace in Mitchell has wrapped its walls in murals made of real corn cobs, grasses, and grain for more than a hundred years, redesigned by artists almost every season. The decorations and motifs that are generally used here make it clear that corn is one of the king crops here in South Dakota.

### Dignity: Of Earth and Sky
- treatment: landmark
- leg: mitchell_sd_us -> rapid_city_sd_us
- at_mi: 70
- spoken: At the Missouri River overlook ahead stands Dignity, a fifty-foot steel statue of a Lakota woman holding a star quilt, honoring the Dakota and Lakota people.
- describe: Dignity, sculpted by Dale Lamphere, rises above the Missouri River near Chamberlain. Her star quilt, a symbol of honor and respect, is set with diamond shapes that catch the wind and light.

### Wall Drug (countdown, sign one)
- treatment: billboard
- leg: mitchell_sd_us -> rapid_city_sd_us
- at_mi: 28
- spoken: Billboard: Free ice water at Wall Drug. Only two hundred miles. You can make it.

### Wall Drug (countdown, sign two)
- treatment: billboard
- leg: mitchell_sd_us -> rapid_city_sd_us
- at_mi: 150
- spoken: Billboard: Wall Drug. Five-cent coffee, an eighty-foot dinosaur, and a jackalope you can sit on. Getting closer.

### Wall Drug (countdown, sign three)
- treatment: billboard
- leg: mitchell_sd_us -> rapid_city_sd_us
- at_mi: 222
- spoken: Billboard: Wall Drug, next exit. You have read the signs for two hundred miles. You know you are stopping.
- describe: Wall Drug began in the nineteen-thirties when a small-town druggist put up signs offering free ice water to travelers crossing the hot prairie. It grew into a whole block of shops, cafes, and Western oddities, and the free ice water is still free.

### 1880 Town
- treatment: billboard
- leg: mitchell_sd_us -> rapid_city_sd_us
- at_mi: 135
- spoken: Billboard: Eighteen-eighty Town ahead. A whole Old West village, plus a skeleton walking his pet dinosaur. History, roughly.

### Minuteman Missile National Historic Site
- treatment: landmark
- leg: mitchell_sd_us -> rapid_city_sd_us
- at_mi: 215
- spoken: Ahead is the Minuteman Missile National Historic Site, a preserved Cold War launch control center where the missiles once waited under the prairie.
- describe: For thirty years, a thousand Minuteman missiles stood ready beneath these plains. The site preserves a launch control center and a silo, kept exactly as they were, as a reminder of how close the Cold War came to the surface here. Hopefully, no one forgot one like you forgot your toothbrush at home last week.

---

## Held for later (not baked in this pass)
- **Badlands National Park** — near Wall; check whether it already exists as a
  `national_park` landmark before adding, to avoid a duplicate.
- **Rapid City / US-16 kitsch** (Reptile Gardens, Cosmos Mystery Area) — off the
  I-90 mainline; hold for a US-16 pass.
- Wall Drug also has two entries in `billboards.py` `CORRIDOR_BILLBOARDS` (I-90);
  those retire in favor of this placed countdown once the renderer converges.

## Sources
Travel South Dakota roadside-attractions guide; Wikipedia "Wall Drug";
Dignity/Minuteman site public descriptions. Facts only; sign copy invented.
