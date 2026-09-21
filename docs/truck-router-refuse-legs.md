# Truck-router refuse legs (Career 1.9 world-data)

All eight leftovers were retired from the career network (owner option 3).
On each of those legs the loaded-semi truck profile could not follow the
archived corridor inside the 6 percent `tools/repair_geometry.py` adoption
screen, even when pinned with intermediate vias. Edges were dropped rather
than remileaged or resplit. Pay and deadlines hang off mileage, so the owner
made the call by hand.

## Fixed (25): corridor-pinned truck geometry

Public Valhalla truck costing (`FF_VALHALLA_URL`, loaded-semi options) with
intermediate vias sampled from the archived corridor (or curated `route_via`)
lands inside the 6 percent screen. The geometry archive was rewritten, and
paid and settlement miles were synced to the adopted archive path length, the
same source of truth as the drive. The refuse screen asks whether a truck can
follow the geometry; it does not compare the router against an old paid
number. Unconstrained A to B truck length still drifts on many of these, so a
future unconstrained `repair_geometry` pass will refuse again rather than
overwrite. That is expected until vias are first-class in that tool.

Measured 2026-09-16 against `https://valhalla1.openstreetmap.de`.

| leg | via mode | router vs paid |
| --- | --- | ---: |
| payson_az_us:winslow_az_us | archive_3 | +0.3% |
| allentown_pa_us:trenton_nj_us | archive_2 | +4.6% |
| portland_me_us:montpelier_vt_us | archive_2 | -0.0% |
| wenatchee_wa_us:everett_wa_us | archive_2 | +0.4% |
| las_vegas_nv_us:phoenix_az_us | archive_2 | +3.5% |
| charleston_sc_us:florence_sc_us | archive_2 | -0.3% |
| coos_bay_or_us:roseburg_or_us | archive_2 | +0.5% |
| hartford_ct_us:providence_ri_us | archive_2 | +0.2% |
| spokane_wa_us:boise_id_us | archive_2 | +0.4% |
| austin_tx_us:kerrville_tx_us | archive_3 | +0.1% |
| albany_ny_us:bridgeport_ct_us | archive_2 | -1.9% |
| tampa_fl_us:miami_fl_us | archive_2 | +2.4% |
| charlotte_nc_us:knoxville_tn_us | route_via | +1.3% |
| denver_co_us:salt_lake_city_ut_us | archive_2 | +0.2% |
| charlotte_nc_us:lumberton_nc_us | archive_2 | +2.4% |
| williamsport_pa_us:harrisburg_pa_us | archive_3 | +0.7% |
| augusta_ga_us:savannah_ga_us | archive_2 | -0.2% |
| roanoke_va_us:raleigh_nc_us | archive_2 | -0.7% |
| elizabethtown_ky_us:evansville_in_us | archive_2 | +2.2% |
| muskegon_mi_us:traverse_city_mi_us | archive_2 | +1.8% |
| south_bend_in_us:fort_wayne_in_us | archive_2 | +0.7% |
| denver_co_us:albuquerque_nm_us | archive_2 | +0.5% |
| rochester_ny_us:new_york_ny_us | archive_2 | +0.5% |
| santa_ana_ca_us:lancaster_ca_us | archive_2 | +2.7% |
| paintsville_ky_us:pikeville_ky_us | archive_6 | +5.7% |

## Retired (8): dropped from the career network

Owner chose option 3 (retire). Directed edges removed from
`world_source/legs/{KY,TN,IN,WV,CA}.json` on 2026-09-16; no new via/split
cities. Connectivity alts already existed (prior dry-run). Geometry archive
and gameplay jsonl rows for these leg ids scrubbed. Matching directed edges
also dropped from `world_data/us/legs/{KY,TN,IN,WV,CA}.json` (whole-edge
removal only; stop arrays on remaining legs untouched). Full `index_world`
not run.

| leg | prior A→B drift | prior best corridor-via | retired |
| --- | ---: | ---: | --- |
| hazard_ky_us:london_ky_us | +83.8% | +138% | yes |
| evansville_in_us:clarksville_tn_us | +57.4% | +52.4% | yes |
| charleston_wv_us:pikeville_ky_us | +38.8% | +109% | yes |
| evansville_in_us:nashville_tn_us | +27.6% | +60.5% | yes |
| chico_ca_us:santa_rosa_ca_us | +15.9% | +24.7% | yes |
| pikeville_ky_us:hazard_ky_us | +12.6% | +12.6% | yes |
| morristown_tn_us:london_ky_us | +42.9% | +11.5% | yes |
| clarksville_tn_us:louisville_ky_us | -7.0% | +6.6% | yes |

## Retirement options (historical)

1. Keep road, fix mileage: when the archived line is the intended road and
   the paid miles are stale. Use `tools/repair_leg_mileage.py` / curated
   mileage update, then re-enrich. Player-facing: pay and deadlines move.
2. Adopt truck-legal geometry, then set paid miles to that path: when the
   curated corridor is car-only or otherwise HGV-hostile. Corridor-via
   Valhalla truck routing (as used for the 25) is the entrypoint; once a
   truck can follow the geometry, paid and settlement miles follow the
   adopted archive length. `tools/reroute_leg.py` changes miles and drops
   enrichment, so prefer a geometry-archive adopt plus mileage sync.
3. Retire or split the leg: when neither road nor mileage should stand (the
   corridor does not exist for trucks as drawn). Applied to all 8 leftovers
   above: edges dropped, and no split cities were added.

## Out of scope here

- Jade's stop-completeness batches under
  `src/freight_fate/data/world_data/us/legs/*.json`
- Facility approach pin re-geocode (`facility_endpoints.json`)
- Curves-only re-bake over repaired geometry
