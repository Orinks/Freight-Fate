# Countdowns, both directions -- 2026-09-30

Wall Drug and South of the Border each get one countdown per direction of
travel. Every `leg:` is written the way the driver reads the sign and `at_mi`
counts from that end; `tools/bake_billboards.py` mirrors the milepost onto a
leg stored the other way round and records which way the billboard faces.

Mileposts come from the baked legs: the Wall Drug stop (Exit 110) and the
interchange list for Wall; I-95 Exit 1 and the state crossing for South of
the Border, which sits on US 301/501 just south of the North Carolina line
(Exit 1 loops back to it; AARoads, "Interstate 95 South - Dillon to
Florence"). Each "next exit" sign stands between the attraction's exit and
the one before it, and at least two miles from any other callout so the
landmark spacing does not drop it.

## Wall Drug, westbound from Sioux Falls (Wall at mile 293.3)

The same three signs the Mitchell run already carries, at the same distances
out.

### Wall Drug (countdown, sign one)
- treatment: billboard
- leg: sioux_falls_sd_us -> rapid_city_sd_us
- at_mi: 93.3
- spoken: Billboard: Free ice water at Wall Drug. Only two hundred miles. You can make it.

### Wall Drug (countdown, sign two)
- treatment: billboard
- leg: sioux_falls_sd_us -> rapid_city_sd_us
- at_mi: 221.0
- spoken: Billboard: Wall Drug. Five-cent coffee, an eighty-foot dinosaur, and a jackalope you can sit on. Getting closer.

### Wall Drug (countdown, sign three)
- treatment: billboard
- leg: sioux_falls_sd_us -> rapid_city_sd_us
- at_mi: 292.4
- spoken: Billboard: Wall Drug, next exit. You have read the signs for two hundred miles. You know you are stopping.

## Wall Drug, eastbound from Rapid City (Wall at mile 55.7 on both legs)

### Wall Drug (eastbound countdown, sign one)
- treatment: billboard
- leg: rapid_city_sd_us -> sioux_falls_sd_us
- at_mi: 10.7
- spoken: Billboard: Free ice water at Wall Drug, forty-five miles. Free since nineteen thirty-six. Inflation never found it.

### Wall Drug (eastbound countdown, sign two)
- treatment: billboard
- leg: rapid_city_sd_us -> sioux_falls_sd_us
- at_mi: 35.7
- spoken: Billboard: Wall Drug, twenty miles. Five-cent coffee and homemade doughnuts, in a store that fills a whole block of Main Street.

### Wall Drug (eastbound countdown, sign three)
- treatment: billboard
- leg: rapid_city_sd_us -> sioux_falls_sd_us
- at_mi: 53.5
- spoken: Billboard: Wall Drug, next exit. You made it. The ice water is still free.

### Wall Drug (eastbound countdown, sign one)
- treatment: billboard
- leg: rapid_city_sd_us -> mitchell_sd_us
- at_mi: 10.7
- spoken: Billboard: Free ice water at Wall Drug, forty-five miles. Free since nineteen thirty-six. Inflation never found it.

### Wall Drug (eastbound countdown, sign two)
- treatment: billboard
- leg: rapid_city_sd_us -> mitchell_sd_us
- at_mi: 35.7
- spoken: Billboard: Wall Drug, twenty miles. Five-cent coffee and homemade doughnuts, in a store that fills a whole block of Main Street.

### Wall Drug (eastbound countdown, sign three)
- treatment: billboard
- leg: rapid_city_sd_us -> mitchell_sd_us
- at_mi: 53.8
- spoken: Billboard: Wall Drug, next exit. You made it. The ice water is still free.

## South of the Border, northbound (Exit 1 at mile 37.6 from Florence)

Signs one and two are the corridor-pool lines, moved here so they are only
read on the way to it.

### South of the Border (northbound, sign one)
- treatment: billboard
- leg: savannah_ga_us -> florence_sc_us
- at_mi: 150
- spoken: Billboard: South of the Border, coming up. Or is it? Keep driving to find out.

### South of the Border (northbound, sign two)
- treatment: billboard
- leg: florence_sc_us -> lumberton_nc_us
- at_mi: 15
- spoken: Billboard: The big sombrero tower ahead. Fireworks, tacos, and a lookout. You never sausage a place.

### South of the Border (northbound, sign three)
- treatment: billboard
- leg: florence_sc_us -> lumberton_nc_us
- at_mi: 35.6
- spoken: Billboard: South of the Border, next exit, right on the state line. Ride the elevator up the sombrero tower.

## South of the Border, southbound (Exit 1 at mile 20.4 from Lumberton)

### South of the Border (southbound, sign one)
- treatment: billboard
- leg: fayetteville_nc_us -> lumberton_nc_us
- at_mi: 12
- spoken: Billboard: South of the Border, coming up. Or is it? Keep driving to find out.

### South of the Border (southbound, sign two)
- treatment: billboard
- leg: lumberton_nc_us -> florence_sc_us
- at_mi: 5
- spoken: Billboard: The big sombrero tower ahead. Fireworks, tacos, and a lookout. You never sausage a place.

### South of the Border (southbound, sign three)
- treatment: billboard
- leg: lumberton_nc_us -> florence_sc_us
- at_mi: 20.0
- spoken: Billboard: South of the Border, next exit, right on the state line. Ride the elevator up the sombrero tower.

## Re-baked from earlier sheets

Written for the direction opposite to how their legs are stored, and baked
before the tool mirrored the milepost, so each stood at the wrong end of its
leg. Same copy. Bates House of Turkey is at Greenville, forty-three miles
south of Montgomery by the leg's own geometry, not ninety-five.

### Bates House of Turkey
- treatment: billboard
- leg: montgomery_al_us -> mobile_al_us
- at_mi: 41
- spoken: Billboard: Bates House of Turkey is ahead. It serves turkey sandwiches, turkey plates, turkey pie, and proof that Thanksgiving does not require permission from November.

### Cadillac Ranch
- treatment: billboard
- leg: amarillo_tx_us -> tucumcari_nm_us
- at_mi: 8
- spoken: Billboard: Cadillac Ranch is ahead. Ten Cadillacs are buried nose-down in a field with their tailfins to the sky, and you are invited to spray-paint them. Bring a can.

### Tucumcari Tonite
- treatment: billboard
- leg: amarillo_tx_us -> tucumcari_nm_us
- at_mi: 108
- spoken: Billboard: Stay in Tucumcari tonight, with two thousand motel rooms and a mile of neon on Route sixty-six. From fleabag to fo-tel, Tucumcari has you covered.
