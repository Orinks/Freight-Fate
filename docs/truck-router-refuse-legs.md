# Truck-router refuse legs (Career 1.9 world-data)

Owner decision still needed: on each of these legs the loaded-semi truck
profile wants a route whose length disagrees with the curated paid miles by
more than the 6 percent `tools/repair_geometry.py` adoption screen. Either the
mileage is wrong, or the road the leg is on is not one an 80,000 lb rig should
be routed down. Pay and deadlines hang off mileage, so this is not a silent
auto-fix.

Measured originally as the refusals from the geometry-repair pass (40
refused, minus 7 already within a few metres of the corridor → **33**).

## Inventory

```bash
uv run python tools/inventory_world_data_blockers.py
# or re-check one leg against the public / local truck router:
uv run python tools/repair_geometry.py --only hazard_ky_us:london_ky_us
```

`repair_geometry.py` prints the router's length against the paid miles and
refuses rather than adopting. It does not rewrite stop JSON.

## The 33

| leg | router vs paid |
| --- | ---: |
| hazard_ky_us:london_ky_us | +83.6% |
| evansville_in_us:clarksville_tn_us | +57.2% |
| morristown_tn_us:london_ky_us | +42.7% |
| payson_az_us:winslow_az_us | -41.4% |
| charleston_wv_us:pikeville_ky_us | +38.7% |
| allentown_pa_us:trenton_nj_us | +33.6% |
| portland_me_us:montpelier_vt_us | +29.4% |
| evansville_in_us:nashville_tn_us | +27.5% |
| wenatchee_wa_us:everett_wa_us | -27.3% |
| las_vegas_nv_us:phoenix_az_us | +21.6% |
| charleston_sc_us:florence_sc_us | +18.1% |
| coos_bay_or_us:roseburg_or_us | -16.2% |
| hartford_ct_us:providence_ri_us | +15.9% |
| chico_ca_us:santa_rosa_ca_us | +15.8% |
| pikeville_ky_us:hazard_ky_us | +12.5% |
| spokane_wa_us:boise_id_us | -11.7% |
| austin_tx_us:kerrville_tx_us | -11.6% |
| albany_ny_us:bridgeport_ct_us | +11.6% |
| tampa_fl_us:miami_fl_us | +11.4% |
| paintsville_ky_us:pikeville_ky_us | +10.8% |
| charlotte_nc_us:knoxville_tn_us | -9.7% |
| denver_co_us:salt_lake_city_ut_us | +9.2% |
| charlotte_nc_us:lumberton_nc_us | -9.1% |
| williamsport_pa_us:harrisburg_pa_us | -7.7% |
| augusta_ga_us:savannah_ga_us | +7.5% |
| roanoke_va_us:raleigh_nc_us | +7.5% |
| elizabethtown_ky_us:evansville_in_us | +7.3% |
| clarksville_tn_us:louisville_ky_us | -7.3% |
| muskegon_mi_us:traverse_city_mi_us | -7.2% |
| south_bend_in_us:fort_wayne_in_us | +7.2% |
| denver_co_us:albuquerque_nm_us | +7.1% |
| rochester_ny_us:new_york_ny_us | -6.6% |
| santa_ana_ca_us:lancaster_ca_us | +6.4% |

## Retirement options (pick per leg, owner)

1. **Keep road, fix mileage** — when the archived line is the intended road
   and the paid miles are stale. Use `tools/repair_leg_mileage.py` / curated
   mileage update, then re-enrich. Player-facing: pay and deadlines move.
2. **Keep mileage, reroute onto a truck-legal road** — when the curated
   corridor is car-only or otherwise HGV-hostile. `tools/reroute_leg.py` is
   the entrypoint; length must land inside the adoption screen.
3. **Retire / split the leg** — when neither road nor mileage should stand
   (corridor does not exist for trucks as drawn). Needs an owner call on
   network shape; do not silently drop a freight node pair.

Do not fold these into the pre-repair curve re-bake: the 33 have empty
overlap with the curve-mismatch set (geometry was never adopted for them).

## Out of scope here

- Jade's stop-completeness batches under
  `src/freight_fate/data/world_data/us/legs/*.json`
- Facility approach pin re-geocode (`facility_endpoints.json`)
- Curves-only re-bake over repaired geometry
