# Truck-router refuse legs (Career 1.9 world-data)

Owner decision still needed on the leftovers below. On each of those legs the
loaded-semi truck profile cannot honestly follow the archived corridor inside
the 6 percent `tools/repair_geometry.py` adoption screen -- even when pinned
with intermediate vias. Refuse means the geometry cannot be truck-followed as
drawn; it is not merely "router ≠ old paid number." Either the road needs a
truck-legal path (with paid miles then set to that path), or the leg should be
retired/split. Pay and deadlines hang off mileage, so this is not a silent
auto-fix.

## Fixed (25) -- corridor-pinned truck geometry

Public Valhalla truck costing (`FF_VALHALLA_URL`, loaded-semi options) with
intermediate vias sampled from the archived corridor (or curated `route_via`)
lands inside the 6 percent screen. Geometry archive rewritten, and **paid /
settlement miles were synced to the adopted archive path length** (same source
of truth as the drive). The refuse screen is whether geometry can be
truck-followed honestly -- not whether the router disagrees with an old paid
number. Unconstrained A→B truck length still drifts on many of these -- a
future unconstrained `repair_geometry` pass will refuse again rather than
overwrite; that is expected until vias are first-class in that tool.

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

## Leftovers (8) -- still refuse

| leg | A→B drift | best corridor-via | why still refuse |
| --- | ---: | ---: | --- |
| hazard_ky_us:london_ky_us | +83.8% | +138% | Corridor (KY-80) is not truck-followable at paid length; pinned vias make the truck wander longer, not shorter. Mileage fix or retire/split needs owner. |
| evansville_in_us:clarksville_tn_us | +57.4% | +52.4% | I-69 corridor still ~52% long under truck costing; no via set lands inside 6%. |
| charleston_wv_us:pikeville_ky_us | +38.8% | +109% | US-119 archive pins do not yield a truck route near paid miles (often no route / long detour). |
| evansville_in_us:nashville_tn_us | +27.6% | +60.5% | US-431 corridor under truck costing stays ≥60% over paid. |
| chico_ca_us:santa_rosa_ca_us | +15.9% | +24.7% | Archive vias mostly fail (400) or lengthen further; unconstrained +15.9% over screen. |
| pikeville_ky_us:hazard_ky_us | +12.6% | +12.6% | KY-80 truck route stuck ~+12.6% over paid regardless of via count. |
| morristown_tn_us:london_ky_us | +42.9% | +11.5% | Best corridor pin still +11.5% (over 6% screen). |
| clarksville_tn_us:louisville_ky_us | -7.0% | +6.6% | Best corridor pin +6.6% -- just over the adoption screen. |

## Retirement options (pick per leftover, owner)

1. **Keep road, fix mileage** -- when the archived line is the intended road
   and the paid miles are stale. Use `tools/repair_leg_mileage.py` / curated
   mileage update, then re-enrich. Player-facing: pay and deadlines move.
2. **Adopt truck-legal geometry, then set paid miles to that path** -- when
   the curated corridor is car-only or otherwise HGV-hostile. Corridor-via
   Valhalla truck routing (as used for the 25) is the entrypoint; once the
   geometry can be truck-followed honestly, paid / settlement miles follow
   the adopted archive length. `tools/reroute_leg.py` changes miles and drops
   enrichment -- prefer a geometry-archive adopt plus mileage sync.
3. **Retire / split the leg** -- when neither road nor mileage should stand
   (corridor does not exist for trucks as drawn). Needs an owner call on
   network shape; do not silently drop a freight node pair.

## Out of scope here

- Jade's stop-completeness batches under
  `src/freight_fate/data/world_data/us/legs/*.json`
- Facility approach pin re-geocode (`facility_endpoints.json`)
- Curves-only re-bake over repaired geometry
