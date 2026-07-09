# Sign sheet — I-40 / Route 66 (EDITABLE)

Corridor #2. The bake input -- read it, change anything, then I bake it onto the
real legs. Facts from public data (Route 66 / attraction records); copy invented.

**How to edit:** `treatment:` = `billboard` | `landmark` | `skip`. `leg:` /
`at_mi:` = real leg + miles from the leg's `from` city (**at_mi are ESTIMATES**,
change freely). `spoken:` = exact words, numbers spelled out, `Billboard:` lead
kept on billboards. `describe:` = optional pull-in read (banked for the future
pull-off; not baked).

Built legs on this corridor: `oklahoma_city_ok_us -> amarillo_tx_us` (258),
`amarillo_tx_us -> tucumcari_nm_us` (114), `albuquerque_nm_us -> tucumcari_nm_us`
(176), `gallup_nm_us -> flagstaff_az_us` (185), `flagstaff_az_us ->
kingman_az_us` (151).

---

### The Big Texan Steak Ranch
- treatment: billboard
- leg: oklahoma_city_ok_us -> amarillo_tx_us
- at_mi: 250
- spoken: Billboard: The Big Texan Steak Ranch ahead in Amarillo. Eat the seventy-two-ounce steak in one hour and the whole dinner is free. The graveyard of a thousand appetites.
- describe: The Big Texan, on old Route sixty-six in Amarillo, will give you a seventy-two-ounce steak dinner free if you finish it, sides and all, in one hour, up on a stage with a clock running and a crowd watching. Most who sit down do not get up a winner.

### Cadillac Ranch
- treatment: billboard
- leg: amarillo_tx_us -> tucumcari_nm_us
- at_mi: 8
- spoken: Billboard: Cadillac Ranch ahead. Ten Cadillacs buried nose-down in a field, tailfins to the sky, and you are invited to spray-paint them. Bring a can.
- describe: Cadillac Ranch, just west of Amarillo, is a row of ten old Cadillacs half-buried nose-first in a cattle field. Visitors have spray-painted them for decades, so the color changes by the hour and the paint is inches thick.

### Tucumcari Tonite
- treatment: billboard
- leg: amarillo_tx_us -> tucumcari_nm_us
- at_mi: 108
- spoken: Billboard: Tucumcari tonight. Two thousand motel rooms and a mile of neon on Route sixty-six. From fleebag to fo-tel, Tucumcari's got you covered.
- describe: The neon has promised "Tucumcari Tonite" for sixty years, and it is still right -- a whole mile of classic Route sixty-six motels lit up against the New Mexico dark.

### Cline's Corners
- treatment: billboard
- leg: albuquerque_nm_us -> tucumcari_nm_us
- at_mi: 60
- spoken: Billboard: Cline's Corners ahead. Fudge, moccasins, rubber tomahawks, and every polished rock you never needed. A New Mexico institution since the road was young.

### Wigwam Motel
- treatment: billboard
- leg: gallup_nm_us -> flagstaff_az_us
- at_mi: 90
- spoken: Billboard: Sleep in a wigwam tonight, in Holbrook. Concrete teepees, a classic car parked at every door, and the old question on the sign: have you slept in a wigwam lately?

### Jack Rabbit Trading Post
- treatment: billboard
- leg: gallup_nm_us -> flagstaff_az_us
- at_mi: 100
- spoken: Billboard: The Jack Rabbit Trading Post ahead. A giant rabbit out front, and a sign that says, simply, HERE IT IS.
- describe: That giant rabbit and its one-word sign, HERE IT IS, have pointed drivers off Route sixty-six since your grandparents drove by. See the rabbit, trade at the rabbit -- you'll find things you never knew you needed, probably not made in the good ol' U.S.A., but come anyway.

### Standin' on the Corner
- treatment: billboard
- leg: gallup_nm_us -> flagstaff_az_us
- at_mi: 123
- spoken: Billboard: Winslow, Arizona, ahead. Stand on the corner, and a girl in a flatbed Ford will most likely slow down to look. You know the song.

### Meteor Crater
- treatment: billboard
- leg: gallup_nm_us -> flagstaff_az_us
- at_mi: 140
- spoken: Billboard: Meteor Crater ahead. A hole in the desert nearly a mile wide, punched out by a rock from space. Bigger than it sounds. Much bigger.
- describe: Meteor Crater, near Winslow, is a bowl almost a mile across and some five hundred feet deep, blasted out about fifty thousand years ago by an iron meteorite. Astronauts trained on its rim for the trip to the moon. Sit and consider what would happen to civilization should another city-sized rock hit greater Sheboygan, or ... St. Louis, for Pete's sake.

### Grand Canyon Caverns
- treatment: billboard
- leg: flagstaff_az_us -> kingman_az_us
- at_mi: 95
- spoken: Billboard: Grand Canyon Caverns ahead, near Peach Springs. The largest dry cavern in the country, two hundred feet down, with a single motel room at the very bottom for the very brave.

### Entering the Navajo Nation
- treatment: landmark
- leg: gallup_nm_us -> flagstaff_az_us
- at_mi: 5
- spoken: You are entering the Navajo Nation, the largest reservation in the United States and a sovereign nation with its own government, reaching across parts of Arizona, New Mexico, and Utah. It even has its own timezone, I hope you've remembered that cause you might be late for dinner if you're stuck on Arizona time.
- verify: exact boundary crossing near Lupton on I-40 -- confirm against OSM boundary=aboriginal_lands before the final bake; the checkerboard makes the entry point fuzzy. Respectful, factual register -- never parody.

---

## Held / notes
- **Petrified Forest / Painted Desert** (national park, AZ) — check whether it
  already exists as a `national_park` landmark before adding; do not duplicate.
- The `amarillo -> albuquerque` DIRECT leg (288 mi) bypasses Tucumcari; the
  Cadillac Ranch / Tucumcari signs are on the Route 66 path only for now
  (multi-leg projection is a tool refinement).
- The Big Texan doubles as the **streamable 72-ounce steak mini-game** target
  (Liam) — same attraction, richer pull-in later.
- Done: pulled the generic forty-eight-ounce steak billboard from the pool
  (billboards.py on the 1.9 line) so it no longer competes with the Big Texan.

## Sources
Route 66 attraction records (South of the Border pivot noted: its I-95 segment
is not built, so this corridor went first). Facts only; sign copy invented.
