# Freight Fate Roadmap

> **RELEASE SCOPE (amended 2026-07-27, owner + Josh):** the 1.9 line
> takes FIXES plus exactly the final slate Josh named -- (1) the easy
> multilane slice (wiring the already-baked lane counts into speech),
> (2) curve navigation with steering, (3) rumble strips (one system
> with curve nav), (4) the engine-ring spectra rebuild, and (5) the
> NPR translator radio batch. Nothing else: every other unchecked
> FEATURE bullet below targets the `feat/career-2.0` line, except the
> explicitly scoped 1.10 work below (2.0 worktree
> `.claude/worktrees/career-2.0`, created 2026-08-18; the `C:/dev/ff-2.0`
> path this note used to name never existed). The driving school stays
> gated off 1.9 (`DRIVING_SCHOOL_ENABLED`) and reopens on 2.0 to be
> finished.
> Track plan: `docs/plan-1.9-final-slate.md`.

> On September 11, the owner approved five corrections to existing 1.9 systems:
> commercial bobtail duty, braking estimates, component service limits, fuel
> weight, and reachable HOS rest stops. The weekly HOS cycle and full personal
> conveyance controls remain in the 1.10 plan.

> Current stable: **1.8.8.1** (hotfix shipped 2026-08-08). Next release: **1.9.0**, in
> flight on the `feat/career-1.9` branch -- driving realism between the exits
> (discrete lanes, ramp terminals, congestion, real surface streets) plus the
> highway-spider world expansion, roadside narration, and real time zones.
> `pyproject` is set to 1.9.0 so developer snapshots report it; the stable tag
> follows at release. Keep this file current: when a feature lands on the 1.9
> line, check it off here in the same change.

## Reading this roadmap

Start with the [1.9 release gate](#release-gate----what-stands-between-here-and-a-public-190),
including its cutover checklist, remaining bugs, and owner decisions.
The [1.10 plan](#110-planned----the-working-week-and-home) follows it.
The [detailed roadmap](docs/roadmap-details.md) preserves the implementation
record and full pending backlog. Section links below keep existing roadmap
bookmarks usable.

## 1.9 in flight (`feat/career-1.9`)

- [x] Ramp-end traffic lights keep one seeded 60 to 78 second plan per
      intersection, with a 7 second all-red so cross traffic clears before green.

- [x] Quiet speech keeps concise lane openings, confirmations, and status transitions; Urgent only omits routine costs and status, and suppressed categories skip review.

- [x] Keep traffic light approaches and changes brief: Light red, Light yellow,
      Light green; retain the distance countdown without "to the bar."

- [x] Start the route readout directly with the location or arrival information
      on facility approaches, city streets, and at the gate.

- [x] Keep the exit blinker repeating on the right until ramp entry, cancellation,
      or a missed exit; stop canceled-exit guidance until the driver signals again.

- [x] Validate the Windows portable snapshot on a clean Windows installation
      without a separately installed Visual C++ redistributable. CLOSED
      2026-09-20 by proof rather than by a boot: the packaging audit now reads
      EVERY normal import of the executable and of every DLL beside it and
      requires each one to be either a library the payload ships or a DLL
      Windows itself has (`WINDOWS_SYSTEM_DLLS`, plus the API sets the loader
      answers from its own schema). A build runner cannot establish this by
      running the game, because the runner HAS the C++ redistributable and
      the Windows SDK; the static rule holds on a machine that has neither.
      Read back from the real payload: the only redistributable import in the
      whole tree is `vcruntime140.dll` from the executable, and the build has
      staged the official CRT family beside it since the audit was written.
      Prism's bridges to the PC-Talker, ZDSR and BoYing screen readers are
      DELAY imports and stay exempt: without that reader installed the bridge
      does not resolve, which costs the bridge and never the launch.

- [x] Synthesized music source (no AI): a seeded composer with 14 styles on
      a career-path ladder, the restored 1.5 tracks, a Synthesized Roadhouse
      with no voiced breaks, the Synthesized dial rules and the
      streamer-safe lock, and tracker modules playable in radio playlists
      (a module that jumps back to its start ends after one pass, so the
      playlist moves on). The Tab radio screen says Freight Fate's own
      stations are off the dial in Synthesized mode.
      - [ ] Typed-in music seeds.
      - [ ] More synth voices per style.

- [x] Career balance integrity: a `MoneyGuard` shadow (balance bits XORed
      with a per-instance key) resyncs on every legitimate earn, spend, or
      load; a balance changed outside a transaction marks the career
      `integrity_modified` at the next audit and folds into the signed
      save, so a memory-edited total arrives as evidence instead of clean.

- [x] Reviewed cloud backups (game side): a marked career keeps backing up
      while it waits for review; declined, it stops backing up and the driver
      hears so once instead of retrying; accepted, its mark is cleared so
      later backups go up unmarked.
- [x] Moved careers (game side): a career marked only because it was copied
      from another computer tells the backup which earlier backup it arrived
      as, so the site can accept the move without a manual review.
- [x] Moved careers (site side): a marked career whose arrival matches a
      backup the site already holds unmarked is accepted without a manual
      review and listed once in the owner's digest.

### Release gate -- what stands between here and a public 1.9.0

The checklist below retains the recorded open release gates. Verification here
covers the September 11 corrections; other items have not been revalidated. The
[detailed backlog](docs/roadmap-details.md) retains the supporting notes and
[completed gate work](docs/roadmap-details.md#completed-19-release-gate-work).

#### Release cutover checklist

These steps remain open even where a related implementation bullet is checked:

- [x] Revert-the-revert on dev for the driving-assists withdrawal
      (2026-09-20, `d00faad1`), and public career selection the same
      way (`2b5cba9f`) now that its server side is on production.
      Both resolved toward feat/career-1.9.
- [x] The invariants-export regen against PRODUCTION (2026-09-20). It
      turned out none was owed: `ff-invariants --check` against the
      merged tree matches the file already on the staging line byte for
      byte, so the dev->main promotion carried the correct export
      (sourceSaveVersion 5 to 11, 60 achievements to 181, 9 levels to
      30, 2 trucks to 35). Verified by running the export and diffing
      it, not by assuming.
- [x] The cutover replay (2026-09-20) -- by differential, not by sample.
      Production reads were unavailable, so instead: every membership
      check in the new validator is LOOSER than production's (city,
      trucks, upgrades, achievements, market keys all went from "must be
      in the known set" to a shape check; `exactFields` now tolerates
      unknown keys; the money floor widened; the accepted version range
      widened from 4..5 to 4..11). The only added check is gated on five
      fields no 1.8 build writes, so it cannot fire on an existing save.
      The freshly-played-career half is covered better than a replay
      would: staging has run this exact validator against real 1.9
      careers for weeks.
- [x] Flip `DEFAULT_BASE_URL` back to production and drop the
      2026-08-staging key (2026-09-20). `tools/build_release.py`'s
      music-pack URL moved off the staging host in the same change --
      the `/downloads/music.pak` route ships on production now.
- [x] Convex deployed to production before any 1.9 build ships
      (2026-09-20, orinks-net `c3da9bc`), verified server-side: the
      driver directory answers with 164 public profiles rather than
      Vercel's green status. This nearly did not happen -- the staging
      rework left the Vercel build deploying a backend only on `dev`,
      so `main` would have shipped the new site against production's old
      Convex functions. Fixed in orinks-net `9925714` first.
- [ ] The radio stream sweep (`--recheck-dead`) runs before the release;
      the place-callouts ladder rides the release merge to dev.
- [ ] **The 1.9 stable-release path.** OWNER RULING 2026-09-20: 1.8 gets
      no further releases of any kind, and the next stable is 1.9. So
      `build.yml` was deleted rather than retired in stages -- it built
      the Python game (no `rustup` step, no `fetch_bass.py`, and
      `tools/build_release.py` runs its Python mode unless given
      `--rust`), and with 1.8 closed it had no job on either trigger: its
      nightly could not succeed against a Rust `dev`, and its tag trigger
      would have handed a `v1.9.0` to Nuitka. `build-career-1.9.yml` is
      the only workflow that builds the game now.
      * What is left to build: that workflow only cuts PRERELEASES today
        (`--prerelease`, `1.9-tester-*` tags, version from the date). A
        stable release needs the version and tag to come from a `v*.*.*`
        push, the prerelease flag dropped, and stable release notes.
      * Deliberately not written yet. Nothing can exercise it short of
        tagging a real release, and 1.9 is not close to stable. Write it
        when it is, against a workflow that has been running nightly by
        then rather than against guesses now.
      * [x] Also freed by the ruling, and DONE in the Python sunset
        (2026-09-21): `tools/build_release.py`'s Python/Nuitka mode,
        `tools/build_appimage.py`'s Python path and their tests are
        deleted. The Rust build is the only one; `--rust` is still
        accepted and does nothing.
- [x] The owner voice pass over seven achievement titles (2026-09-22).
      The category-description cut landed and the owner accepted all
      seven titles as-is. The physical-Mac VoiceOver listening pass was
      DROPPED as a release gate (2026-09-20, owner): there is no physical
      Mac to test on. Prism reaches VoiceOver the same way it reaches
      every other reader, and the native runner boots the packaged app
      before it ships, so that sub-gate could never have been cleared
      here anyway. Revive the Mac listen only if a Mac tester appears.
- [x] The Unreleased block is ready to cut stable notes from
      (2026-09-20). The four tester-line bullets are gone: the staging
      orinks.net copy, the Update channel developer-snapshots row, and
      the "1.9 updates look for tester builds" fix were dropped outright,
      and the "tester snapshots are ready to play" bullet was reworded
      rather than dropped -- it carried the only statement anywhere in
      the block that Intel Macs are unsupported. The two Linux bullets
      say "the release" instead of "each snapshot" for the same reason.
      * Both pairs settled from the code, not by preference. Curve speed
        assistance: `driving_updates/lanes.rs` raises the engine brake
        only where `retarder_warranted()` says the drums cannot hold the
        hill, so the "engine brake first" Added bullet described
        behaviour that was later corrected and is now one bullet saying
        engine brake on a steep downgrade, service brakes elsewhere.
      * The dispatch cap: nothing in `models/jobs/board.rs` filters on
        gross weight, cargo reaches 25 tons, and the board's own readout
        can say "over the gross-weight limit with current fuel" -- so
        "dispatched loads stay at or under 80,000 pounds" was false. It
        now says the board weighs each load against the limit and that
        fuel counts toward it, which agrees with the fuel bullet instead
        of contradicting it.
      * The third, the Learn game sounds collision entry explaining
        itself by the retired terse mode, was SETTLED earlier the same
        day: four entries named terse, and the rung table says a
        confirmation and a bend advisory only become a sound at Urgent
        only, so all four say Urgent only now.

#### Player-impacting release blockers

These items are part of the release-gate sweep:

- [x] Lane centering assist retired (2026-09-16): the settings row and
      preset writes are gone; lane keeping full already holds center.
- [x] Signal running is dice and tickets (2026-09-12): the crossroad's
      seeded traffic decides whether a blown red or stop sign meets nothing,
      a horn, a clip or a heavy broadside, and a flat seeded roll draws the
      red-light or stop-sign citation on the chain-law checkpoint rails.
- [x] The 2026-08-13 Dropbox tester findings are triaged (2026-09-01),
      and the line calling them untriaged was stale. Two of the three
      are settled: the doubled "middle lane" went with
      `MAX_DRIVABLE_LANES`, and the one-lane passing cop is fixed. One
      leftover is NOT a release blocker and lives in the detailed
      backlog: enforcement and passing-cop sounds cut the in-cab radio,
      a game-SFX-over-radio mix issue. The far-right lane of a
      five-lane road stays unreachable by design.
- [x] Cruise switches its traffic focus on the actual held-wheel lane
      crossing, keeping the origin lane until then and protecting traffic in
      the lane entered.
- [x] Braking estimates share the live brake-force calculation. Generic
      hazard warnings retain service-braking and reaction time; emergency
      braking has its own stopping estimate.

- [x] Testers hear sounds quieter at the quiet speech rung. CLOSED: the
      Aug 19 earcon duck covered say_event; the main say path (cruise/stop
      confirmations) now ducks the bed the same way when game sounds step
      back for speech is on. The cue levels were never low; the unducked
      road bed was masking them.
- [x] Departing straight into a hazard at route mile zero -- DONE,
      CLOSED 2026-09-22 at the current `origin/dev` tip (`e2d27d5b`),
      closing the 1.9 release gate at current tip coverage. The real-zone
      floor and the merge-free opening miles landed 2026-08-16. The Sep 16-17
      ship-line history already on `dev` includes `2cbd19ed`, `a378909c`,
      `fdcbe821`, `ba06486f`, later `4d2150cb` (2,416/5,037, about 48%),
      and `5f26a6d8`, among the follow-ups. At this tip,
      `data/facility_approaches.json` has 2,456 / 4,271 `turn_level`
      approaches (57.5%); its `generated.merge` metadata is dated 2026-09-20,
      and the all-49-state batch is present. This closes the gate at the
      documented coverage; it does not claim turn geometry for every facility.
      Builder side landed 2026-09-16: the turn-level route pass now takes
      cold storage, food processors, grocery DCs, grain elevators and ports,
      and a state batch merges into the checked-in file instead of
      rebuilding it (a prior chain is never demoted, untried facilities
      keep their rows). A 24-state Geofabrik route sweep on 2026-09-16
      raised the file from 1,415 to 1,647 chains of 5,037 facilities (28
      to 33 percent); 92 of the newly eligible types now carry turn-level
      streets. A California, New York and Texas sweep the same day took
      it to 1,713 chains (34 percent): California 103 to 130 of 316, New
      York 37 to 46 of 76, Texas 81 to 111 of 412. Every state on the map
      (48 plus DC) is in the extract set now.
      Leftovers worked 2026-09-17, all 49 extracts re-swept: 1,713 to 1,913
      chains (38 percent); California 130 to 135, New York 46 to 51, Texas
      111 to 128. Every one of the 88 CA/NY/TX "no connected path" failures
      was classified. 52 had a path and ran out of search budget, because
      the budget was sized from the facility's representative pin near the
      city centre while the route went to a sourced endpoint three to seven
      miles out. 22 were a town cut in two because its main street is a US
      highway OSM classes as trunk, or the only join is a link way. Both
      were builder bugs and are fixed; no threshold moved. The other 14 are
      correct refusals: 8 behind private yard roads, 2 reachable only by
      motorway, 2 across water, 1 inside a site, 1 too far from any road.
      The 44 "under the chain floor" rows are true negatives (the endpoint
      is within a few blocks of the city context) and stay refused. Also
      fixed: a path longer than eight streets kept the first eight out of
      the city centre and dropped the ones at the yard (109 of 287 CA/NY/TX
      chains; the kept part covered a median 68 percent of the path); it
      keeps the facility end now. One street heard several times under
      different route refs (271 of 1,713 chains) is one street now.
      What limits this layer now: reading the OSM tags of all 2,779
      "source-backed" endpoints back out of the extracts shows only 567 are
      freight sites. 906 are railway track (main lines named for their
      subdivision), 313 power-grid objects (a substation tagged
      substation=distribution matched "distribution"), 223 shops, 174 roads
      and bus stops, 128 public amenities, and 236 carry no industrial tag.
      The endpoint sweep matches substrings of the name plus every tag
      value. Only 317 of the 1,713 chains that existed before today lead to
      a freight site. The approach builder now screens the endpoint's own
      tags before it routes (read, positive list, in
      tools/facility_endpoint_screen.py) and records the refusal as the
      row's reason: 783 chainless rows are refused, and the screen can be
      switched off with one flag. Existing chains were not demoted.
      Steel, automotive and chemical endpoints: 193 were matched by name
      substring, 45 pass the screen plus a stated-trade rule (14 steel, 14
      automotive, 17 chemical), and 37 of those carry chains now.
      Endpoint re-sweep, also 2026-09-17, all 49 extracts: chains went from
      1,913 to 2,364 of 5,037 (47 percent), and the ones that end at a
      freight site from 517 to 1,722. Sourced endpoints that are freight
      sites went from 568 to 1,939 of 2,934. 1,224 railway lines,
      substations and shops were replaced by a freight site inside the
      6.4-mile city bound, 155 fallbacks were filled, and 995 found nothing
      better and carry the screen's refusal in their own row. 175 of the
      sites state no trade (a named industrial business standing in for a
      template cross-dock), and those rows say the trade is assumed. Every
      endpoint that already passed was kept byte for byte, and the 419
      estimated rows were not touched. 642 chains still end at a non-site:
      560 whose endpoint found no replacement, kept by owner ruling, and 82
      whose endpoint was replaced but whose new site no public road reaches
      (61 behind private yard roads, a motorway or water, 12 under the
      chain floor), kept with a stale_endpoint note until a chain replaces
      them.
      Yard roads, 2026-09-17 (owner ruling the same day): a chain may begin
      on the facility's own access=private road, at the facility end only,
      spoken as "a service road". The 142 rows whose cause was
      "disconnected" were re-routed: 89 gained a chain (52 new, 37 stale
      ones rebuilt), so chains stand at 2,416 of 5,037 (48 percent), 1,811
      of them to a freight site, and 45 are still stale. The other 53 stay
      refused: 47 are cut off even with private ways open (the Mississippi
      at Baton Rouge and New Orleans, the Connecticut at Hartford, a
      motorway or water elsewhere), 2 would need a private road mid-route
      or a gate on a public street, 1 has under half a mile of public
      street, and 3 have a private stretch past the cut (see below). A
      matcher/sibling facility-type widen is explicitly deferred past
      2026-10-04. The ruled-out private-yard and no-path leftovers remain
      honest refusals, not a data-PR target.
- [x] Re-sweep facility endpoints with a matcher that reads an object's own
      tags, not substrings of the tag dump. DONE 2026-09-17, by the owner's
      ruling that the 1,396 chains to non-sites stay until a re-sweep
      replaces them. tools/facility_endpoint_match.py states every rule
      and the kind of each value: the endpoint screen is the gate, the
      trade must be stated by a tag or by whole words of the name, rail
      yards serve the intermodal types and industrial=port the ports, and
      the 6.4-mile bound is the far-pin regeocode's, not tuned. A border
      screen reads admin_level=2 relation ways, because the Arizona extract
      holds the maquiladoras on the fence at Douglas. The re-sweep is a
      merge and can be re-run a state at a time. The approach builder
      rebuilds a chain whose endpoint was replaced and labels the ones it
      could not. Numbers are in the item above.
- [ ] 995 sourced endpoints are still not freight sites, 560 of them under
      a chain. Named sites ran out: OpenStreetMap names few warehouses in
      small towns. OWNER DECISION: 365 of the 995 have an UNNAMED
      building=warehouse, works or rail yard of their own family inside the
      bound (measured from the cached extracts, before two facilities
      compete for one building). The tag states the trade, so the match
      would be read, but a tool shed is a building=industrial too, and a
      floor area to keep sheds out has to be calibrated against named
      warehouses first. Recommended: yes for the warehouse and
      manufacturing families, with the floor reported and the row labelled
      unnamed. Not built.
- [x] Facility types the endpoint sweep had no rule for: grain elevators,
      quarries, construction materials yards, lumber and paper. DONE
      2026-09-20. Each family's site tag is scoped to its own family, the way
      a rail yard serves the intermodal types: a silo for elevators, quarry
      land for quarries and aggregate yards, craft=sawmill for sawmills. A
      silo is a STRUCTURE every farmyard has, so it opens the gate but must
      be NAMED as grain to count; bare "pit" is a barbecue and bare "paper" a
      stationer, so each carries its trade word. All 419 of these rows were
      fallbacks, so no row could be demoted by trying: 129 gained a sourced
      endpoint and every one passes the screen. The long synthetic approach
      test had already moved off Payson Quarry in the 2026-09-20 stand-in cut.
- [x] Route the sibling types the approach builder skipped: intermodal,
      rail, manufacturing, air cargo, food terminal and industrial park.
      DONE 2026-09-20. The stated blocker was a dozen tests pinning Chicago's
      first facility (Cicero Rail Hub) as the stock single-leg approach; read
      back, three tests reach it and each already branches on whether the
      facility has a chain, so nothing needed re-pointing.
- [x] Departure chains behind private yard roads. DONE 2026-09-17 on the
      owner's ruling: a truck leaves a yard over the yard's own road, so a
      chain may use access=private ways as one stretch at the facility end,
      never anywhere else, spoken as "a service road" and never by the
      private way's name, and the half-mile chain floor is held against
      public miles alone (tools/yard_roads.py states each rule and its
      kind). access=no, military, no-truck ways and gates on public streets
      stay refused. The private stretches found run 0.03 to 0.85 miles with
      a clear gap before 1.49, so the cut is one mile; the owner allowed
      three sites past it by name (Gary Works steel mill 1.49, Tampa cold
      storage 1.94, Port Tampa Bay bulk docks 1.97).
- [ ] Two endpoints reached only over five to eight miles of private road,
      left unbuilt by owner ruling 2026-09-17 because that reads like a
      wrong endpoint: Huntsville cross-dock (endpoint "Kuskokwin Building",
      tagged only building=warehouse, whose coordinates put it inside
      Redstone Arsenal, so the 4.86 miles are the arsenal's roads) and
      Ukiah company yard (endpoint "Retech Systems LLC", an industrial area
      with the trade assumed, 7.4 miles south of town beside US 101, which
      is a motorway there, so the graph's only join is 7.69 miles of
      private road). Both want an endpoint fix, not a routing one. San Diego cross-dock (2.06 miles of port road)
      also sits past the cut, unruled.
- [x] The public road graph honours barrier nodes and ways signed
      motor_vehicle=no or hgv=no (2026-09-20, owner ruling the same day).
      MEASURED FIRST, as this item asked: not one of the 2,314 existing
      chains needed a way signed against trucks, so nothing was demoted.
      The rule is two rules, judged apart. A truck sign is a FACT about the
      road -- there is no reading in which a loaded truck may drive up one --
      so it refuses a new chain AND drops an existing one, the only case
      where the merge lowers the chain count. An untagged barrier=gate is a
      GUESS: as often a farm gate standing open as a locked one, and at an
      industrial site usually the facility's own gate, which the 2026-09-17
      yard-road ruling already lets a loaded truck pass -- so it refuses a new
      chain and never takes an existing one away. The builder records WHICH
      rule closed a route (`truck_banned`, `gated`, `disconnected`) by asking
      connectivity three times with each rule opened in turn, so the split is
      in the data and re-judgeable without a sweep;
      `--no-truck-legal-public` restores the old search so the cost stays
      measurable. A gate AT the dock is still arrived at.
      Chains stand at 2,456 of 4,271 rows (2,314 before), sourced endpoints
      at 2,874, and 2,049 of them are freight sites.

#### World data and sound licensing blockers

World-data geometry for 1.9 (curves, refuse legs, far approach pins)
closed 2026-09-16 on feat/career-1.9. Departure chains are the last open
world-data item (see above): every state was re-swept 2026-09-17 with the
path failures fixed, the endpoint re-sweep landed the same day, and the
yard-road rule after it (2,416 chains, 48 percent, 1,811 of them to a
freight site). What is left is the third of sourced endpoints with no named
freight site in reach, the facility types with no matcher rule, and two
endpoints behind miles of private road.

- [x] ~250 legs' curves/limits/ramps still describe pre-repair geometry.
      CLOSED 2026-09-16: curves-only re-bake, refuse-collateral mismatch
      25 to 0, connectors and screens restored; curve inventory green.
- [x] 33 legs a truck router would refuse. CLOSED 2026-09-16: 25 adopted
      truck-legal geometry with paid miles synced to path length; 8 leftovers
      retired by owner decision. Refuse inventory 0.
- [x] 776 facility approach pins land too far out. CLOSED 2026-09-16: far
      pins regeocoded within city bounds (776 to 0); estimated-near-city
      labels landed. Residual estimated pins and the OSM source_backed
      quality follow-up are deferred; neither blocks far pins.
- [x] The Duff-shared sound cues flagged unlicensed by the provenance
      audit. N/A 2026-09-16 (owner): dropped from the release gate.
- [x] Street corners carry their measured angle (2026-09-20). The
      facility-approach rebuild writes the turn angle per junction: 8,454 of
      10,900 corners are READ from OSM geometry, against 5 before, so a
      sweeping junction is now genuinely faster than a square one and a
      switchback slower. The local-geometry layer still reports 0 read; it
      serves the retired city-service rows and nothing the game drives.
- [ ] Colorado's live traffic and construction are dead (CARS GraphQL
      retired; COtrip's WZDx feed wants a registered key, as do Ohio,
      Oregon, Texas, Virginia, Michigan and Illinois). PARKED for 1.9 Oct 4
      (owner): keyed WZDx states out of scope; keyless statewide feeds stay.
      The 2026-09-12 FHWA registry sweep put every keyless statewide feed
      in: 29 states carry live construction now, 15 of them new that day.

#### Owner decisions

These decisions remain with the owner: engine off at trip start;
the per-aid assistance-mode assessment; the two CONFIRMATION lines
silenced at quiet (2026-08-22 build); the two parked branches
(honest-brake-decel; the speech-ladder branch predates the Rust cutover
and needs triage before revival); public career following the opened
career (Shane's design ask).

The detailed backlog retains the remaining work and its recorded release scope.
Update each item where it is recorded; this reorganization does not change
its status or release decision.

### September 21 Prism from the prismer crate

- [x] Prism comes from the `prismer` crate (0.1.3 or later), compiled from
      source and linked into the executable, instead of the in-tree
      `prism`/`prism-sys` crates loading a vendored library at run time.
      The screen-reader client DLLs stay delay-loaded on Windows; Linux
      links the system's speech-dispatcher, so a Linux install needs it to
      start, and loses Prism's Orca backend (Ubuntu 22.04, the build host,
      has no glibmm 2.68). Found on the way and fixed upstream as
      trypsynth/prismer#2: the binding described version 3 of `PrismConfig`
      while Prism wrote version 4, overrunning the caller's stack. Prism's
      static backend anchors are MSVC-only, so `crates/freight-fate/build.rs`
      links the archive whole on Linux and macOS, and the nightly now fails
      when a platform's own backend (SAPI, AVSpeech, Speech Dispatcher) is
      missing from `--list-speech-backends`.
- [ ] Prism's backend anchors cover MSVC only; a GCC static link drops
      every backend unless linked whole. Reported with a standalone
      reproduction as ethindp/prism#130, fixed upstream 2026-09-22 by
      ethindp/prism#135 (anchors for GCC and Clang). Waiting on a `prismer`
      release that vendors it (0.1.3 does not); then drop the whole-archive
      link in `crates/freight-fate/build.rs` and dry-run the nightly.

### September 21 the Python sunset

- [x] The Python game is deleted (2026-09-21). The Rust workspace in
      `crates/` is the only game; the Python survives in git history
      (`v1.8.8.1` is its last release). The world data tree moved from
      `src/freight_fate/data/` to `data/`, sounds, packs and the BASS
      add-ons to `assets/`, and `src/` is gone. `tools/` stays Python, with
      the world loader as the `tools/ffworld/` package, and `pyproject.toml`
      is tooling only (`uv sync --group dev`). The installed game's layout
      did not change. The playtest launchers are game flags now:
      `freightfate --playtest-road --find <feature>` and
      `freightfate --playtest-sandbox --launch`; `tools/playtest_watch.py`
      still follows their logs.
- [ ] `av` and `scipy` are imported by `tools/encode_music_opus.py`,
      `tools/patch_loop_transients.py` and the `sound-test/` scripts but
      declared nowhere in `pyproject.toml`. Add them to a group (`tooling`
      fits) so a fresh checkout can run those tools.
- [ ] `sound-test/` carries old ruff lint and format debt, so the
      pre-commit ruff hooks exclude it (CI lints only `tests` and `tools`).
      Clean it up and drop the exclude.
- [ ] Port the "bear is CB voice only" source sweep. The Python game had a
      test that failed on the word outside a CB clause in any player-facing
      string; the Rust
      `test_bear_is_cb_voice_only_in_every_player_facing_string` is an
      ignored placeholder, so the `docs/ontology.md` rule is unenforced.

### September 11 trucking corrections

- [x] Commercial bobtail repositioning records driving time while moving and
      on-duty time while stopped, including terminal turnaround.
- [x] Tires, brakes, and engine warn at the 80-percent game maintenance
      threshold and require service at 100 percent. Garage and roadside
      recovery remain available to company drivers and owner-operators.
- [x] Remaining diesel contributes to gross weight. Dispatch previews use
      the assigned tractor, and fuel menus report full-tank weight margin.
- [x] HOS advice selects a compatible reachable rest stop and warns before
      the last usable exit. Interrupted warnings retry after pause or resume;
      completed warnings stay suppressed until the relevant reset.
- [x] Skip speech voices that fail to initialize and retain spoken agent
      readouts when sound output is busy. Native SAPI and OneCore checks pass.
      A live session with normal Windows access used NVDA and SAPI, completed
      a short drive and stop, and returned status and HOS readouts without
      speech errors. The earlier initialization failure reproduced in the
      restricted shell without the agent server.
- [x] The long half of a sleeper split (7 or more berth hours) pauses the
      14-hour window while it runs, as 49 CFR 395.1(g)(1)(iii)(B) excludes
      qualifying rest from the window; the short half counts until the pair
      is credited. Tester report 2026-09-11: 7 duty hours plus an 8-hour
      berth rest woke to a closed window.
- [x] `--agent-server --operator-keys` keeps the window up and lets the
      owner's keyboard reach the game, to drive alongside the agent; the
      repo's `.mcp.json` passes it. Without the switch the keys are still
      dropped at the door.
- [x] Achievement triggers audited (2026-09-20). 181 badges: 177 wired, 3
      deliberately retired into "first_day" and tested as such, and 2 --
      `thrifty_run` and `coffee_regular` -- that had never been awardable in
      either runtime: catalog copy from the day they were written, no award
      site, no test, no note. Both wired. The mileage one needed per-run fuel
      accounting that did not exist; `Trip.fuel_used_gal` reads it as the
      DROP in the tank each frame, so a refuel stop adds gallons without
      crediting the run with ones it did not spend.
      The same audit found a live bug: `first_dispatch_done` still read the
      retired `first_dispatch` badge, so it was false for every driver
      forever, and the dispatch board's recommended-load line fell through
      that dead check for anyone not on a company training profile. It reads
      `first_day` now, and the six tests that hand-seeded the retired badge
      to make their setup work seed the real one.
      A test now asserts every catalog badge is either awarded in shipping
      code or named as retired, and that a retired one is never awarded
      again. It reads source, so it proves REACHABILITY, not correctness.
- [ ] 130 of the 177 wired badges have no test naming them individually, so
      nothing proves they fire at the right MOMENT rather than merely being
      reachable. The trigger sites are concentrated (one arrival pass, one
      rest-stop pass), so this is a readable job, not an endless one.
- [ ] Complete the owner's listening pass and longer gameplay verification
      of wear thresholds and interrupted warnings. Captured live readouts and
      successful native calls do not establish what the owner heard.

- [x] `--list-speech-backends` names every screen reader and voice Prism finds
      on the machine it runs on, says which can speak right now, and which one
      the game would choose (2026-09-20). There has never been a list of
      approved readers in the game: `pick_backend` walks the registry in
      priority order and keeps the first whose own runtime check passes, so
      ZDSR, PC-Talker, BoYing, SenseReader, System Access and ZoomText are
      already chosen wherever they run. None of them can be installed here,
      which is why the switch exists: it moves the question to somebody who
      has one. Read here, the three Prism reaches through a delay-loaded SDK
      (ZDSR, PC-Talker, BoYing) register at priority 101, above JAWS.
- [x] Stabilized the curve-assistance test's empty-road fixture. It clears
      current vehicles and disables random traffic replenishment before the
      bend cases run. One full run reported cargo damage; focused and full
      reruns passed.
- [x] The clock key's arrival estimate on the departure streets adds the
      parked highway run at its route pace, and the speed readout names a
      lead vehicle that is setting the speed keeper's number (agent drive,
      Dallas to Sherman with every assist on, 2026-09-11).
- [x] Facility stopping assistance is a preset field again (owner ruling
      2026-09-11): Realistic off, Balanced and All assists on, hand changes
      read as Custom. The 2026-08-31 rest-stop merge had left it outside the
      presets while the manual promised Balanced stops at the destination.
- [x] The S key names mainline bends only (2026-09-12). It used to add a
      connector arc's advisory ("The bend here advises 40") at a
      highway-to-highway interchange, though connector arcs are excluded
      from the curve call, the curve servo and the cargo model by design,
      so the driver was told about a bend no assist acts on (I-30 to I-35
      at Fort Worth). D still answers with the connector's safe speed.
- [x] The curve servo holds a bend on a downgrade on one application
      (2026-09-18). Inside its hold band it let go, the hill carried the
      truck back over, and the snub came back as a new application ten
      times a second: 125 psi to the spring brakes in one bend of AZ-260,
      Camp Verde to Payson. With adaptive cruise holding the same bend it
      did the same on the band's edge. The pedal is feathered now: the snub
      scales with how far over the number the truck is, the hill is held
      tapering to a band under it, and the whole run makes 8 applications
      where it made 277. Judged across 140 grade, advisory and entry-speed
      cases.
- [x] The clock stays real until curve assistance has finished slowing
      for a bend (2026-09-18). The pacenote decompression lets go at the
      advisory plus its margin while the servo aims at the advisory itself,
      so the last 3 mph were shed on the compressed clock and took a full
      application (same AZ-260 trace).
- [x] A bend can be held at its own advisory (2026-09-19). The lane model's
      cornering ceiling was a flat 0.35 g, and advisories are priced at
      0.30 g plus up to 6 percent of built bank and then rounded to the
      nearest five, so the tightest bends ask 0.36 to 0.43 g at the very
      number the cab calls out: AZ-260's 146-foot hairpin, advisory 30, ran
      the truck wide at 30 whatever the driver or the assists steered. The
      ceiling now reads the bend's own advisory demand, screened at 0.49 g
      -- what the advisory formula can produce at the 15 mph floor -- so a
      row asking for more than the formula allows cannot raise it. Above the
      advisory the truck still understeers wide (agent drive, Camp Verde to
      Payson).
- [x] The assists allow for a liquid load (2026-09-20). `surge_decel_penalty_mps2`
      has answered "how much rate does this tank give back at the worst
      moment" since it was written, and only the ramp bar asked: the facility
      arrival, the curve servo and the speed keeper all priced their shed at
      the dry-van rate, so a part-filled tank arrived over every number. All
      three read it now, which is the CDL manuals' own rule -- with a liquid
      load you brake earlier -- taken from the truck's own model rather than
      a factor somebody picked. The surge physics itself was already right:
      `ZETA_LATERAL` equals the smooth-bore value whatever the baffles,
      matching FMCSA's Cargo Tank Incidents Study -- "in all cases, tank
      structure does not control side-to-side sloshing".
- [ ] A part-filled tank is priced as a FULL one by the roll models, not as
      worse than one. `roll_load_fraction` stops a half-empty tank reading as
      a light load, which was the bug; the truth is that the half-empty tank
      is the worst case of all, because the liquid climbs as it goes to the
      outside of the turn. Needs a fill-level curve for the rollover
      threshold: FMCSA's 2007 Cargo Tank Roll Stability Study is the place to
      look, and its PDF refuses a plain fetch (403), so it wants a proper
      read rather than a guessed de-rating.
- [x] The map stops inventing freight where it cannot see any (2026-09-20).
      Of 623 markets, 137 had no facility whose endpoint the freight-site
      screen accepts -- Nevada 11 of 15, Montana 9 of 15, Arizona 12 of 22 --
      and each was stamped with four or more invented warehouses anyway.
      They hold one company yard now; 766 generated facilities retired, and
      the screen's `passed` count did not move, which is the proof the cut
      took only fiction. A facility the world generates is also approached by
      a generated road: no snapped real street stands in for a site that is
      not there. Drive-throughs, parking aisles, fire lanes and permit-only
      ways left the routing graph in the same pass.
- [ ] Wholesale and trade sites are refused as retail. `shop=wholesale` is
      how OSM tags a distributor -- Shamrock Foodservice Warehouse in
      Billings is a bare node carrying it and nothing else -- and the screen
      refuses any `shop` object outright. Accepting the tag alone would also
      admit a Costco, so this needs a rule that separates the two, probably
      trade words in the name on top of the tag.
- [x] A street corner is priced for the load that is actually in the trailer
      (2026-09-20). The corner model derived its lateral from the 0.35 g
      rollover threshold of a LOADED combination and applied it whatever was
      on the fifth wheel, so a driver deadheading to a pickup was advised 9
      mph at a square corner -- the owner's report. UMTRI-83-10 Figure 38
      measures the threshold at -0.01 g per inch of payload centre-of-gravity
      height, and Figure 33 puts the empty van body's own centre at 60
      inches, which walks the loaded 0.35 g up to 0.70 g empty: the same
      square corner is 13.2 mph with nothing aboard, 9.4 mph full, and a
      ladder in between. A part-filled tank is still priced full, because
      slosh makes it the worse case, not the better one.
- [x] The destination-exit approach asks for the signal (2026-09-19). With
      the lane work the driver's, the signal alone commits the truck to the
      exit, and no line on the approach named it: the announcement and both
      distance anchors gave the lane and the ramp speed, and the first
      mention of a signal in a whole run was "The turn signal was not set"
      after the miss. The loop-back line had always named the control, so
      the gate was only ever explained once it had closed.
- [x] Two hidden badges, 181 in the catalog (2026-09-19). A mile held at the
      old national 55, nodding to the trucker game that still asks it of
      blind drivers and to Congress letting the limit go in 1995; and a load
      settled on October 4, which reads as ten-four. Both carry the invariants
      export, so the cloud validator's copy needs regenerating on staging
      before a build ships with them.
- [x] Losing the exit lane is spoken (2026-09-19). "Exit lane set." was a
      promise the drive could break in silence -- a lane change away or a
      quarter-lane wander left decays the alignment -- and the next word on
      it was "You missed the exit. You were not in the exit lane." at the
      gore. Debounced a second, because one frame past the pin that holds
      the alignment reads as lost and a truck on partial lane keeping would
      otherwise call the lane lost and set down a straight mile.

### September 12 live data and dispatch

- [x] Dispatch reads the state 511 construction reports onto each route
      option at the pickup departure, takes the next route when the road is
      closed or the delay outweighs the extra miles, and says why. Fifteen
      more states' feeds came in from the FHWA WZDx registry, all keyless;
      29 states carry live construction.
- [x] National Weather Service warnings ride the real weather toggle:
      dispatch plans around a blizzard, ice storm, hurricane or tornado
      warning, prices a winter storm, high wind, flash flood or dense fog
      warning into the route, and only mentions a thunderstorm; the cab reads
      a warning out as the truck drives into it, and a winter warning posts
      the chain law before the first flake. Driven live out of Pittsburgh.
- [x] Convenience stations the map had typed as travel centers with only
      assumed truck parking read as bobtail-only at load: no announcement,
      no exit signal, no rest stop with a trailer on. 242 stops, nine in ten
      kept; the sleep-gap corridors held.
- [x] The pumps charge this week's federal survey diesel price with each
      region's usual spread on top, on by default; Settings, World, Fuel
      prices switches back to simulated.
- [x] Company drivers get a load RELAYED from a nearby freight town when the
      board here is thin (few loads, poor pay, or half the freight of a market
      in range), deadhead paid and timed as part of the assignment, driven as
      one pickup drive that resumes from a save. The one-in-nine empty
      reposition is gone. Home-time relays wait for the 1.10 home terminal.
- [x] The agent server's `scenario` tool stages the sandbox career in any
      situation; the sandbox turns every live feed on. Driven live: Tonopah,
      relayed Las Vegas load assigned and accepted.

### September 12 profiles and the safety record

- [x] The public profile explains each badge: the invariants export carries
      every badge's description and category (hidden ones included, since a
      badge on a profile is earned) and orinks.net dev renders them under
      the title; the in-game driver profile speaks the description too. The
      song behind each badge stays out of the export.
- [x] Two safety-record gaps closed: the chain-law checkpoint citation was
      charged but never booked on the licence file, and an out-of-service
      order only ever counted on the trip, never on the career field the
      scale screening scores. Both reach the record now.
- [ ] The public safety record lists citations, serious violations, major
      offenses, claims, terminations and repossessions; out-of-service
      orders and fatigue events are scored but not shown, by the same rule
      that keeps fatigue private. Decide whether orders belong on the page.
- [x] The driving record bites through the carrier and the insurer, and is
      spoken (owner ask, 2026-09-12). Endorsements stay untied to the record
      (hazmat is a TSA threat assessment, 49 CFR 1572, criminal and
      immigration disqualifiers only; tank and doubles are knowledge tests,
      383.93). Citations now carry career times; the carrier's annual record
      review (391.25) is a fourth dispatch-trust input for company drivers
      (guarded over three citations or one serious violation in three years,
      termination at six or two, floors ASSUMED from common insurer hiring
      standards) with the age-out date spoken; the owner-operator insurance
      reserve carries a surcharge (a tenth per citation, a third per serious,
      capped at double, ASSUMED); the record line and the terminal greeting
      read the live consequence.
- [x] Endorsement freight reaches the drivers who hold it (owner approval
      2026-09-16). Staging had 1,186 deliveries and not one placarded or
      bulk-fuel load: the board offered a hazmat holder 1.2 percent placarded
      and 0.25 percent fuel map-wide, and both needed a chemical terminal at
      each end. A cargo that asks for a course-earned credential (hazmat,
      doubles, TWIC, LCV) now weighs four times at the shipper when the
      driver holds it and the shipper itself is favoured; fuel and placarded
      loads also ship from ports and elevators and land at plants, quarries,
      elevators, ports, airports and yards. Measured: placarded 10 percent
      and fuel 2.6 percent of a level-18 holder's offers map-wide, seven in
      ten Houston boards carry one; pinned in the jobs tests.
- [x] Roadside inspections (owner approval 2026-09-16). Nobody was ever
      inspected: the random roadside check fired only over hours, and the
      scale lane was a fifteen-minute wait that credited a pass. Now the
      lane is a Level 1 (CVSA levels; decal per Operational Policy 5,
      three months), a roving trooper runs a routine Level 3 on a legal
      driver at a rate that rides the safety-record band (clean 1x,
      watched 2x, targeted 4x, Roadcheck week 3x, relaxed halves), a
      critical item parks the truck until the roadside mechanic fixes
      it, and a walk-around row at the terminal and every stop reads
      the same items first. ASSUMED and adjustable in
      `sim/roadside_inspection.rs`: the wear percentages standing in
      for tread depth and brake stroke (75 citation, 90 out of
      service), the fines (150 equipment, 300 critical), the durations
      (45/30/15 minutes) and the 6,000-mile clean-driver interval (the
      real rate is about one per driver-year, which a career here
      never reaches). Same day, the rolling look: a pacing unit or a
      commercial-vehicle unit on the shoulder reads the tread and the
      hooked trailer's lamp or tire as it passes (never under the trailer)
      and pulls the truck in for a Level 2 walk-around, so most equipment
      pull-ins start with something seen, the way they do in life. Not
      built: Level 5, cargo securement (no data), and a CSA-style carrier
      score.
- [x] A career that is over stays readable (owner ruling 2026-09-12, over
      automatic deletion): the second major offense lands as a terminal
      notice, the greeting says the career is over, the buy-in waits for a
      clear CDL, the public profile carries a Career ended row with the last
      verified career behind it, and Close out this career (terminal menu,
      last row, confirmed) is how the game removes an ended career's save and its
      cloud backups. Real-life basis: 49 CFR 383.51 Table 1 lifetime
      disqualification, 49 CFR 384.225 55-year record retention.
- [ ] Two record gaps from the same research: the scale-house safety
      record scores lifetime counts where the real carrier score is a
      time-weighted 24 months, and driving under an out-of-service order is
      a disqualifying offense (383.51 Table 4) the game does not model.

### September 14 reputation reads the record

- [x] Reputation is the delivery ledger less the driving record inside a
      ONE-GAME-YEAR window (4 per citation, 10 per serious violation, 20 per
      major offense for life, capped at 60), read by every gate, the trust
      band, the pay bonus, the stats screen and the public profile (the save
      now carries `career.standing`; invariants regenerated on both sides).
      The raw ledger is untouched, so an aged-out record gives the points
      back. Owner ruling 2026-09-14 after Jess read 98 beside three serious
      violations. Cargo claims already hit the ledger directly and were left
      out of the penalty. The window is a year, not the review's three,
      because the clock only moves on the road: staging shows about a game
      day per delivery, so three years outlasts every career played.
- [x] Audit of every wait keyed to game time (2026-09-14): the hazmat (30
      days) and TWIC (20 days) background checks and the 60/120 day
      suspensions are reachable, and a suspension can be waited out at the
      terminal. The 391.25 carrier review and the insurer surcharge moved to
      the same one-game-year window as reputation (REVIEW_WINDOW_DAYS), so
      the equipment hold's age-out date is one a driver can reach; the 383.51
      licence ladder keeps its three years because it is the law, not the
      carrier. Lifetime counts (claims, terminations, repossessions, fatigue,
      out-of-service) stay lifetime by design.

### September 14 screens of lines

- [x] Four screens that answered with one long sentence are lists of lines
      on the shared readout screen (`SimpleMenuState::readout`): Time and
      weather, Trip status, Career plan, and the first-day briefing. The
      logbook drops its duplicated status and its heading row, splits the
      hours limits one per line, and reads entries newest first, led by the
      status. Business status rows, action results, and the driving readout
      keys stay single answers on purpose.
- [x] Every citation and violation booked at the wheel keeps its reason,
      fine, game hour and place as a record entry (the last 60), and Career
      stats opens them newest first. Counts from before this build read as
      "recorded before reasons were kept". The entries ride inside the
      record, which the cloud validator already knows as one top-level
      field, so no validator change was needed.
- [x] Whole hours are spoken whole ("3 hours", "1 hour") by the one helper
      every hours answer shares; the hours summary and the logbook read
      through it too.

### September 14 work zone approach

- [x] Automatic speed control follows the warning's two numbers: cruise
      eases to the taper's 55 first, then to the zone's 45 once the barrels
      are inside the larger of its braking window and the keeper's ease
      distance; the keeper, which takes the taper over at its start, sheds
      for the barrels from that moment instead of holding the taper's
      number until its 0.75-mile window opened. Measured at standard
      pacing: entry 47.2 before, 45.7 after (owner report).
- [x] The mile ahead of a work zone is spoken as the reduced-speed approach
      ("speed limit 55 from one mile out, then 45 through the work zone";
      entry "Reduced speed for construction"), matching how a real
      interstate work zone steps its limit down through its advance warning
      area. "Taper" now names only the short merge at its end, as in MUTCD
      Part 6, where the traffic-squeeze advisory still uses it.

### September 14 keyboard shortcuts and controller buttons

- [x] Every discrete driving control resolves through one table
      (`crates/freight-fate/src/bindings.rs`) the player edits from
      Settings, Gameplay, Controls: Keyboard shortcuts and Controller
      buttons, one row per control, Enter then a press to move it, refusals
      by name for a taken or fixed key, a reset row. Saved as two text fields
      in the settings file. The F1 help, the spoken "press X to" prompts, and
      the mastery counter that retires them all follow the moved key. Fixed
      by design: Escape, Enter, F1, the Control keys, Shift and the left
      bumper as the clutch, plus and minus, the radio dial keys, message
      review, Start and Back on the pad, and every menu key.
- [x] The How to play pages render every control name from the live table
      (`{{id}}` placeholders in `main_menu_help.rs`), following the device
      in use: the pad button when a controller is active and the control
      has one, else the keyboard key. The Controller page pins pad names.
- [x] The agent server's `press`, `hold`, `release` and `pedal` tools take a
      control's shortcut id as well as a key name, resolved against the
      sandbox player's own table, chord included.

### September 14 pause stays on duty

- [x] Pausing keeps the driver on the drivers list, shown as paused, instead
      of signing them off after twenty seconds and back on at resume (which
      read "went off duty" and "is on duty" to everyone's duty watch for a
      bathroom break). The game posts the pause once and sends no
      heartbeats while paused; the server holds a paused row for the
      thirty-minute idle window instead of the six-minute heartbeat one,
      so a pause left for good ages off like a parked truck, dated at the
      pause. Server side deployed first; builds before it keep the old
      behaviour.

### September 18 a night's parking on every road

- [x] A leg with no stop a loaded truck can sleep at takes the federal
      truck-parking inventory's rest areas on its own road, whatever its
      stop count. Two bobtail-only Kwik Trips had met the minimum for the
      65 miles of I-35 from Owatonna to Minneapolis while Heath Creek and
      New Market sat unlisted, and the cab answered "no sleep-capable route
      stop ahead". 22 rest areas on 14 legs; on the road means within the
      annotate pass's one-mile corridor bound, not the 20-mile search
      radius chain stops are offered from. The same run confirmed parking
      on 51 stops added or renamed since the July annotate pass.
- [x] F1 on a course row under Licenses and training says what the
      credential opens, as the board names the freight, and both roads to
      it: the carrier's sponsor level or the one level earlier it can be
      paid for, or course only with its level, cost, prerequisites and
      background-check wait. Earned and pending rows say it too. The row
      used to give cost and level and nothing about what the course was for.
- [x] Settings, Audio, Shuffle personal playlists: a playlist of the
      player's own files plays every track once per lap in a seeded
      random order, a new order each lap that never opens on the track
      that just ended; off resumes top to bottom. Asked for by Hailey on
      the drivers board: the Playlists folder was built for M3U stream
      lists and is being used for MP3 collections.
- [x] A playlist station sitting on a stream entry now reports the song it
      is playing, the same as a station on the dial. The song readout
      answered for every playlist that it sends no song information,
      which is only true of a file off the player's own disk.
- [ ] 196 legs still have no sleep stop a loaded truck can use and no
      inventory record on the road. US-12 Willmar to Minneapolis is one:
      its only stop is a Kwik Trip typed bobtail-only. Needs another
      source, state DOT rest-area lists or truck parking read from the OSM
      extracts, before the rest key can plan a stop on them.
- [ ] Inventory rest areas are one per carriageway (Heath Creek serves
      I-35 north, New Market I-35 south) and the map stores each as serving
      both directions, so a pair is announced twice within a mile. The
      runtime only knows forward and reverse relative to a leg; deriving
      that from the leg's heading and the record's route suffix is the fix.

### September 17 the dial follows the road

- [x] A station that fades out of range hands the dial to the strongest
      terrestrial station still in range, named in the same line; the route
      playlist is the landing only when nothing is on the air (Brandon,
      2026-09-17). Only a clean signal counts, at or above the static
      threshold, so the dial is not handed a station that fades again a few
      miles on, and a sibling site of the lost station is a handover, not a
      landing. A stream that will not open still goes through the existing
      two-strike fallback, and the line names what the radio actually landed
      on.

### September 17 truck stops listed twice

- [x] A chain truck stop listed twice on one leg is read as one stop, at
      load, across the whole map (`data::stop_twins`). The map import typed
      many chain truck stops as service plazas under the chain's bare name
      ("Flying J Travel Center"); the curated pass later added the same
      stores from the chains' own locators under their full names, with the
      exit and the ramp's control. Both stayed, a mile or three apart by mile
      marker, and the opposite-direction copy of 2026-09-16 carried the pairs
      to legs that had held only one. A driver signalling for the Flying J at
      Corfu seven miles out was armed for the bare record: no exit number, no
      stop sign for route-transition assistance to brake for, and the truck
      rolled through the stop. Found by the adversarial battery
      (`ramp_speed_control_handback`, odd from that copy until this screen).
      The rule: same chain, within four miles, a common direction, and either
      one record carries only the chain's name or both name the same place;
      two records that name different places are never merged. The
      better-documented record stays. Screened, not deleted, so the rule can
      be re-judged. It drops 90 records on 61 legs (Love's 54, Flying J 21,
      Pilot 15), and every leg keeps its to and from stops.
- [x] Where four miles comes from, measured 2026-09-17: for bare records
      beside a named record of the same chain, 77 pairs sit inside three
      miles (36 under one, 29 at one to two, 12 at two to three), then a
      trough of 8 at three to four, then a second rise that keeps going (27
      at four to six, 31 at six to ten), which is real neighbours an
      interchange or more apart. Four is the bottom of the trough. A false
      merge hides one of two same-chain stores under four miles apart and
      leaves the driver the other; a missed twin is a phantom exit.
- [x] `tools/reverse_pair_stops.py` no longer copies a store onto a partner
      leg that already lists it under another name (the same rule, mirrored),
      and a copy of a copy no longer stacks the source note: 257 of its 960
      copies carry the note twice, one per hop.
- [x] A chain truck stop the map import typed as a service plaza is read as
      a travel center, at load (`data::branded_plazas`). A service plaza is a
      toll road's own plaza on the highway, and the import had no such
      distinction to read, so the type was its default. The rule is a
      self-contradiction screen: the type says toll-road plaza and the name
      begins with a national truck-stop chain. A record whose own name also
      says service plaza or service area would stay. Measured 2026-09-17,
      after the twin screen: 1,317 records retyped (Love's 396, Pilot 356,
      Flying J 212, TA 137, Petro 117, Road Ranger 32, Sapp Brothers 32,
      ONE9 28, Stamart 3, Onvo 3, Roady's 1) and none kept. All 1,317 are
      sourced to the amenity query and none to a toll authority's listing;
      the 99 plazas that name themselves are separate records and are left
      alone. 29 of the retyped records sit on a leg that charges a toll, and
      each is a store at an interchange. The value is derived from the name,
      not read, and the data keeps the recorded type so the rule can be
      re-judged. "Sapp Brothers" joined the chain list, which only knew
      "Sapp Bros".
- [x] What the type changes, checked 2026-09-17: the spoken label and
      nothing else. Actions, assumed parking, vehicle access and loyalty are
      the same for both types. The exit number and the ramp's control are
      found by mile marker for every stop, so the retyped records were never
      short of them because of their type: 58% have a numbered exit within
      two miles and 5% a recorded ramp control within 0.15, against 62% and
      3% for the map's other travel centers. 312 of the ones with no exit
      number are on legs with no interchange records at all.
- [x] The chain truck stops carry their store (`tools/import_chain_locators.py`,
      2026-09-17). The terms-of-use check came first and ruled the locators
      out: Love's, TA and Petro, and Road Ranger forbid automated access, and
      Pilot Flying J (with ONE9) forbids copying its listing. Sapp Bros posts
      no terms; its one page lists 17 towns. So the store table is read from
      the cached OpenStreetMap state extracts: 1,764 stores, a town for 1,556
      (read from the address, branch or linked store page for 1,275, the
      curated record's own town for 39, derived from the nearest mapped town
      within two miles for 239 and labelled so),
      a store number for 897, a truck parking count for 8. No exits. Records
      match a store by coordinate inside 0.1 mile (1,462 records under it,
      none between 0.1 and 5 miles). A record with no coordinates matches the
      only store of its brand within 5 miles of its mile marker, or the one
      store carrying its own town's name. Of 1,726 bare records 1,326 are
      named, 126 are typed and sourced with no town to name them by, 52 match
      a store nothing says serves trucks, 77 found no store, 9 would repeat a
      name already on the leg, and 145 were twins. 164 twins deleted in all,
      38 kept records took the deleted twin's better mile marker, and 563
      records gained coordinates. The two load-time screens stay as the net:
      the twin screen now drops 2 records where it dropped 90, and the retype
      acts on 52 where it acted on 1,317 (counted with a Python mirror of both
      rules that reproduces the 90 and the 1,317 on the map before).
- [ ] Chain stops' mile markers are loose: a median of 0.9 miles and a 90th
      percentile of 3.4 from where the store projects onto the leg's own
      line, and 5 to 40 miles for about 110 curated records on long legs.
      Exit numbers and ramp controls are found by mile marker, so re-project
      each from the store coordinates it now carries. Exits and parking
      counts would need the chains' written consent to use their locators.
      Owner ruling 2026-09-17: not asking; the OpenStreetMap store table
      stands.
- [x] A stop carries the interchange that serves it, decided once when the
      data is built (`tools/snap_stops_to_interchanges.py`), and the exit
      number, the ramp's control and the ramp's advisory speed are looked up
      by that identity with no tolerance. The old lookup searched within 0.15
      miles of the stop's mile marker, which is a projection: measured on
      1,223 stops whose read coordinates put them beside a junction, it is
      within 0.15 miles of that junction for one in six and over a mile off
      for half. The stop gains `exit_ref` (read), `interchange_mi` (derived:
      the `at_mi` of the leg's record with that exit number) and
      `exit_source`. Evidence in order: the stop's own source names its exit
      (a chain's store listing) and the leg's record of that number lies
      within 5.3 miles, the measured 99th percentile of mile marker error;
      else read coordinates within 0.6 miles of a junction node on the leg's
      own highway (within 200 m of the leg's geometry, on a motorway or trunk
      way that shares the leg's route number, read from the cached state
      extracts in 48 seconds); else the same store under another name on the
      leg. 0.6 is where the distance cluster (peak at 0.20 to 0.25) meets the
      flat rate of stops that are merely somewhere along the road, which
      bounds chance snaps at 8%. The one check independent of the snap, a
      store's listed exit against its coordinate twin's snap, agrees 40
      times in 40. Measured 2026-09-17 on 3,936 stops reached by an exit:
      ramp control read from the map 133 (3.4%) to 574 (14.6%), seeded 3,803
      to 3,362, exit number spoken 1,926 (48.9%) to 2,230 (56.7%), and of the
      1,390 exit numbers now decided by identity the mile marker had named
      another exit 464 times. On the loaded map after the twin screen, 828
      stops are matched, 476 read a control, and the 0.15 mile search reached
      59 of those. The controls are still mostly assumed. A stop with no
      evidence keeps the old lookup. 485 opposite-direction copies carry
      coordinates that are their own mile marker again (a point on the source
      leg's line, written by `tools/reverse_pair_stops.py`) and are ignored
      as evidence; 48 stops name an exit their leg puts over 5.3 miles away
      (Love's Heyburn appears at mile 121.9 and again at 143.6 of Idaho Falls
      to Boise, and exit 211 is at 119.9) and are listed, not linked.
      Re-run the same day on the map after the store import, which gave 563
      more stops read coordinates: of 3,772 stops reached by an exit, 965
      carry their interchange, ramp controls read from the map go from 118
      (3.1%) to 616 (16.3%), exit numbers spoken from 1,797 (47.6%) to
      2,136 (56.6%), and the mile marker had named another exit for 527 of
      the 1,506 now decided by identity. 41 stops name an exit their leg
      puts elsewhere.
- [ ] What still leaves a truck stop's ramp to the seeded control, in order
      of size: 1,353 stops are on the 532 legs with no interchange records
      (the interchange build only reads Interstate shields); 390 snapped to
      an exit their leg does not record, because the build drops an exit
      within two miles of a richer neighbour, and should keep one that
      serves a truck stop; 375 matched records carry no control because the
      map tags none. Remove the copied coordinates and the 48 misplaced
      copies at the source, in `tools/reverse_pair_stops.py`.
- [x] The 320 service plazas with no chain name that do not name
      themselves a service plaza or service area are each typed as what
      OpenStreetMap says they are (`tools/nonchain_plazas.py`, with what it
      read committed beside it in `nonchain_plazas_evidence.json`). The type
      was never an import default: the import gave `service_plaza` to every
      `highway=services` feature, a tag U.S. mappers also put on truck-stop
      lots, convenience stores and now and then a welder. Each record's
      feature was looked up in the Geofabrik state extracts, read
      2026-09-17. Of 151 places with a same-named feature, 110 sit within
      0.0004 miles of the record (coordinate rounding) and the next is at
      0.025, so the cut is 0.001; past it a place is identified by name
      only, and never when the name is a multi-store brand. Corrected in the
      data, with what was read appended to `source`: 156 travel centers (134
      read from HGV fuel lanes, HGV parking or a truck scale, 22 derived
      from the name), 18 fuel stations (9 read, 9 derived), 1 public rest
      area, and 38 confirmed as service plazas (28 read from a toll
      authority's operator tag, 10 derived). Removed as not stops, 75
      records of 18 places, most of them a bare `highway=services` feature
      under another business's name: Horner Industrial Group 15, Bay 2 12 (a
      Nashville bus bay), Lucky Spot 8, Auto Repair 4, and a rest area on
      CT-15, where trucks are banned, listed 9 times on I-95 and I-91. Two
      legs now list no stop (Fortuna to Eureka, Stockton to San Francisco).
      The 32 records that only their name decides ("Flags West Truck
      Stop") are read as travel centers at load (`data::branded_plazas`).
      5 stay service plazas on no evidence: Modena Travel Plaza 2, Super S
      Travel Plaza, one QuikTrip, one Circle K. `tools/reverse_pair_stops.py` now
      asks a fuel-type stop for the access screen's evidence before copying
      it; the type alone had carried 4 of the removed records onto partner
      legs.
- [x] 21 convenience-brand records (QuikTrip 16, Casey's, Speedway, OnCue)
      have HGV fuel lanes and a truck scale mapped in OpenStreetMap, and the
      access screen still reads them bobtail-only because their services
      list no scale. Owner ruling 2026-09-17: left as they are. Their truck
      parking is only assumed, so they stay closed to a trailer.

### September 16 radio range and the cruise floor

- [x] Driving out of a station's range is announced and retuned again. The
      per-frame settings sync re-pointed the dial at the new position before
      the reception tick compared, so the tick saw the fallback on both sides:
      no line, no static, the dead stream left running at full volume, and
      the drivers board naming the Eagle while the cab played KVSC (owner,
      Willmar to Owatonna, 2026-09-16; inherited from the Python frame order).
      The tick and the board now go by the station the playback seam
      recorded.
- [x] A hazard that leaves the truck below cruise's holding speed no longer
      parks the armed session silently. The keeper bridges the crawl on open
      road, as it does the acceleration lane, and hands to adaptive cruise at
      20; with the keeper off the cab says once what the session waits for
      (owner, US-12 near Litchfield, 2026-09-16: "Well done" at 17 mph, then
      nothing).

### September 13 driver directory

- [x] A driver directory beside Drivers on duty, in the game and on
      orinks.net: every driver with a public profile, on duty first, then by
      when they were last on duty in round figures. The server stamps a
      driver's last-on-duty time once per session end (the sweep that ages
      a silent game off the board, or the game's own sign-off), never per
      heartbeat, so the live board stays as cheap as it was. Same audience
      as the board: public, consented, unflagged. Drivers whose last session
      ended before the stamp existed read as not seen on duty yet until
      their next one ends.

- [x] September 19 radio expansion: eight country songs, eight classic rock,
      eight blues, and Dashboard Glow for Night Line, with selected duet retakes.
      The music pack preserves its prior 380 entries and adds 25.
- [x] Lights Over Superior borrowed into the day menu rotation, by owner
      request, and still in the classic rock station playlist.
- [ ] Download and integrate the eight remaining jazz songs, then 19 station
      jingles, after the September 21 Suno allowance refresh.

- [x] Two owner-supplied instrumentals in the music pack: D-Major Medley
      in the menu rotation, From Bossa to Blues in the day drive pool (so
      the Roadhouse plays it). Pack re-pinned at 380 entries and
      republished.

### September 12 long sessions and speech

- [x] The three-second voice health probe re-published the whole speech
      snapshot each time, and the snapshot's event-voice options are built by
      acquiring every Prism backend. Prism 0.18.2's OneCore acquire leaks one
      USER object, two handles and about 30 KiB per call (measured with
      `cargo run -p prism --example handle_leak_probe`; NVDA, SAPI and the
      rest are clean after first use), so the game gained 1,200 USER objects
      and 2,400 handles an hour: the 10,000-object process limit and the
      desktop heap, which is the tester's low-memory warning and NVDA failing
      to restart beside the game. The probe now enumerates only when a voice
      changed, and the game's registry holds each Prism backend it acquires
      for the session instead of re-acquiring per request, which also covers
      a session with no screen reader running, where OneCore is the automatic
      main voice and the probe re-acquired it on every pass. 1.8 never
      enumerated outside the settings menu.
- [ ] Owner verifies the OneCore leak with Prism's author before anything
      goes upstream; no issue or PR from this side (owner rule 2026-09-12).
      Hand-off is the probe, which left the tree with the in-tree Prism
      crates on 2026-09-21: `git show f9c06a7f:crates/prism/examples/handle_leak_probe.rs`.
      Pinned 2026-09-12: the leak is in FREEING an
      acquired (registry-cached) OneCore instance, not in acquiring it
      (acquire-and-never-free is flat); prismatoid 0.16.7, which 1.8 runs,
      frees the same way and is clean, while 0.17.3 and 0.18.2 both leak
      (`FREIGHT_FATE_PRISM_PATH` points the probe at any build). The Rust
      game enumerates exactly as 1.8 does; the library under it changed.
      Holding each instance for the session sidesteps it on every version.

### September 19 keyless public data sources surveyed

Verdicts, licences and the requests behind them: `docs/data-sources.md`. The
map's 624 cities across 48 states and DC are what each source was judged
against.

- [x] The FHWA Jason's Law truck parking survey reads through
      `tools/ntad.py`, which keeps a snapshot on disk, re-runs offline, and
      carries the public-domain licence and the FHWA acknowledgment in the
      file. Paging off the ArcGIS `exceededTransferLimit` flag read 1,000 of
      1,915 records and reported success -- the GeoJSON responses never carry
      that flag -- so the fetch pages on length instead.
- [x] The federal work-zone registry was re-swept and holds nothing the
      September 12 sweep missed. Oklahoma answers (60 zones) but publishes its
      access token inside the URL, which is still a key; New Mexico still
      answers 503, a week on, so it is dead rather than briefly down.
- [ ] A driver can pull onto a CAT Scale at a truck stop, pay, and hear what
      each axle group weighs before a scale house tells them. 2,127 of them
      are mapped and branded, and the truck already knows its mass and axle
      load. Needs the owner's call on what a weigh costs and what the readout
      says.
- [ ] Where the state scale houses are is still unsolved. 78 of 1,283 legs
      carry one, every one of them found off an exit sign rather than looked
      for, and no keyless national source beats that -- OpenStreetMap's
      weighbridge tag holds 72 enforcement scales against 2,127 commercial
      ones, and the federal Weigh-in-Motion layer is 763 sensor sites nobody
      pulls into. Fifty state lists in fifty shapes is the only route.
- [x] Every grade the load screen clamps was read a second time against USGS
      3DEP and the clamp held up. `tools/screen_grades_3dep.py` sampled 9,484
      real elevations over the 1,271 clamped spans (keyless, public domain, 1
      to 10 m against the baked profile's SRTM 30 m; cached, so a re-run is
      offline and instant). 976 of them -- 77 percent -- are slopes 3DEP flatly
      contradicts, several with the sign reversed: the profile reads +9.5 where
      3DEP reads -6.5. The clamp is catching real noise.
- [x] Two elevation models agreeing does not make a slope real, which is the
      thing this screen was built to find out and the reason road class still
      leads terrain. 47 spans came back with 3DEP confirming the profile at 10
      to 13 percent on an interstate -- a grade no interstate holds. Both
      models read ground, and over three tenths of a mile the ground under a
      bridge is not the road on it. No second elevation source can close that;
      the class ceiling is the only thing that does.
- [x] Loosening the ceiling was scored against the 3DEP readings and rejected.
      Taking the looser of the two terrain labels, or dropping terrain where
      the labels disagree, or dropping terrain entirely, each recover about 70
      genuine grades and admit 386 to 543 artifacts. The rule stays as it is.
- [x] 1,106 grade spans now carry a measured slope instead of a profile
      reading or a clamp. Wolf Creek Pass, the redwood coast, Santiam and
      Canyon Creek were each held to 6 percent because HPMS returns one
      terrain verdict for a whole leg and called 500 to 800 sections "level";
      they now read what 3DEP measured over the same span. The world went from
      455 segments over 8 percent to 141, and from 1,271 clamped at load to
      242. Each re-sourced segment names 3DEP and keeps the profile's own
      number in its `source`, so the swap reverses by reading.
- [x] The 165 spans where 3DEP itself reads 10 to 13 percent on a road that
      cannot hold it were deliberately NOT written. They stay as the profile
      left them for the load screen to clamp, because baking a bridge deck in
      as a grade would put it beyond the one rule that catches it.
- [ ] Note for anyone sampling USGS: the single-point EPQS service answers an
      out-of-coverage point with HTTP 200 and the text `Call failed.`, so a
      reader that trusts the status stores that string as an elevation.
- [ ] California stays dark until a route-to-district lookup exists. Caltrans
      publishes lane closures per district with no key, but district 7 alone
      is 17.6 MB against an 8-second feed budget.
- [ ] Deferred for needing a key: Colorado, Illinois, Massachusetts, Michigan,
      Ohio, Oregon, Pennsylvania, Virginia, statewide Texas, California's WZDx
      feed, and EIA fuel prices. Not in the registry at all: Alabama,
      Arkansas, Montana, Nebraska, Rhode Island, South Carolina, South Dakota,
      Tennessee, West Virginia, Wyoming, DC.
- [x] The National Highway System and FHWA toll facility datasets were
      checked and left: the route graph already carries truck-restricted
      geometry, and `tools/toll_rates.py` already carries what a five-axle rig
      pays, which the toll inventory does not.

## 1.10 planned -- the working week and home

Design doc: `docs/eld-home-terminal-design.md`. The ELD grows from a daily
countdown into the system that shapes a driver's week, and the home
terminal becomes the anchor of that week instead of a spawn point.

- [ ] **70-hour/8-day cycle with the 34-hour restart.** A rolling on-duty
      ledger on `HosClock`, spoken through the existing ELD status line;
      restarts at the home terminal are free and full, road restarts cost
      motel money and comfort. The 1.10 centerpiece.
- [ ] **Home terminal persisted and consequential.** `home_terminal_city`
      on the profile (old saves default to the current city with a
      one-time spoken note), ELD readouts in home-terminal time,
      discounted garage work at your terminal, dispatch "gets you home"
      lane notes, and paid domicile relocation for owner-operators.
- [ ] **Local board (short-haul identity).** A second dispatch surface at
      the home terminal: short home-region runs, home every night, no
      cycle pressure, lower pay -- weighted toward new hires in the
      assigned-dispatch levels.

### Personal conveyance and duty-purpose correction

Regulatory baseline: [FMCSA personal-conveyance guidance](https://www.fmcsa.dot.gov/regulations/hours-service/personal-conveyance)
and [FMCSA ELD recording guidance](https://www.fmcsa.dot.gov/hours-service/elds/if-driver-permitted-use-commercial-motor-vehicle-cmv-personal-reasons-how-must).

- [x] **Commercial bobtail duty corrected in 1.9.** Driving empty to another
      city's dispatch board records driving/on-duty repositioning. Bobtail
      still means a tractor without a trailer; deadhead with an empty trailer
      remains a separate physical configuration.
- [ ] **Personal-conveyance first slice.** Add spoken Start personal
      conveyance and End personal conveyance actions to the ELD menu.
      Ask for a valid purpose and nearby destination: food, shower,
      lodging, or the nearest reasonable safe parking after a shipper or
      receiver releases the driver. Record the movement as off duty with
      a personal-conveyance annotation, reason, start and end locations,
      and distance; preserve it through save/resume.
- [ ] **Keep the clock and truck behavior honest.** Personal conveyance
      still consumes fuel, accumulates fatigue, and keeps all driving
      safety and enforcement active. It does not consume driving or
      on-duty hours, but a short move does not pause or extend an already
      running 14-hour window. Use a carrier policy distance limit rather
      than presenting it as a federal mileage rule; loaded versus empty
      is not the deciding test, though a carrier may set a stricter
      policy.
- [ ] **Reject commercial uses and handle the after-hours exception
      narrowly.** Do not permit personal conveyance to approach the next
      pickup, shop another dispatch board, return to a terminal after a
      dispatched trip, or travel for maintenance. Running out of hours
      alone does not qualify; the exception is leaving a shipper or
      receiver for the first reasonable safe parking location and then
      taking the required rest.
- [ ] **Make misuse reviewable.** The logbook and traffic-stop inspection
      must read the annotation and route evidence. A later enforcement
      slice can question repeated maximum-distance use or other suspicious
      patterns without turning legitimate personal trips into random
      punishment.
- [ ] **Yard moves are separate.** On-property facility movements record
      as on-duty yard time, not personal conveyance or ordinary highway
      driving.
- [ ] **Verify the complete spoken path.** Cover keyboard reachability,
      ELD start/end confirmations, logbook wording, save/resume, eligible
      and rejected destinations, HOS/fatigue behavior, and traffic-stop
      review with transcript-backed playtests. Update in-game help, the
      user manual, and the changelog when the feature lands.
- [ ] **Other ELD character events.** Daily log certification, carrier
      edit approve/reject prompts, a rare ELD-malfunction paper-log day,
      and the adverse-conditions +2-hour exception wired to live weather.

### Signalling a street turn

Deferred out of 1.9 (owner call 2026-08-10) rather than bolting a blinker
onto exit signalling.

- [ ] **A blinker for surface-street maneuvers.** X signals an announced
      highway exit and plays one panned `vehicle/signal_tone`; nothing
      signals a street corner. The map is not the blocker -- baked tier-1
      maneuvers already carry direction and distance, which is what feeds
      the `events/turn_left` and `turn_right` earcons. What is missing is
      the turn as a continuous act: `LaneKeeping` has a lateral offset and
      a lane index and no heading, the same gap that killed the quick-time
      turn in July. Needs a held tick that self-cancels at the corner and a
      rule about signalling before one, alongside whatever turn geometry
      the surface-intersection work (1.9, `docs/surface-roads-plan.md`
      phase 4) leaves behind. The self-cancel half of that now exists:
      `_update_steering_lane_cue` holds a cue on the audio clock's dead
      man's switch and ends it with a centred, quieter `vehicle/signal_tone`.
      Borrow it rather than building a second one.
- [ ] **Decide the two orphan sound assets in the same change.**
      `vehicle/turn_signal` is the repeating tick this feature wants and
      has never been wired to anything. `vehicle/lane_drift` is dead for a
      different reason -- the edge ladder took its job -- so it is a
      deletion, not a wiring job.


### Lanes and maneuvering

[Read this section in the detailed roadmap](docs/roadmap-details.md#lanes-and-maneuvering).

### Maneuvers, enforcement, and the working day

[Read this section in the detailed roadmap](docs/roadmap-details.md#maneuvers-enforcement-and-the-working-day).

### Career, dispatch, and business

[Read this section in the detailed roadmap](docs/roadmap-details.md#career-dispatch-and-business).

### Radio

[Read this section in the detailed roadmap](docs/roadmap-details.md#radio).

### World and narration

[Read this section in the detailed roadmap](docs/roadmap-details.md#world-and-narration).

## Shipped in 1.6.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-160).

## Realism and polish pass (1.7.0 shipped, 1.8.0 in flight)

[Read this section in the detailed roadmap](docs/roadmap-details.md#realism-and-polish-pass-170-shipped-180-in-flight).

### Player feedback round (accessibility/UX)

[Read this section in the detailed roadmap](docs/roadmap-details.md#player-feedback-round-accessibilityux).

### Driver economics

[Read this section in the detailed roadmap](docs/roadmap-details.md#driver-economics).

### Fatigue and driver responsibility

[Read this section in the detailed roadmap](docs/roadmap-details.md#fatigue-and-driver-responsibility).

### Driving feel

[Read this section in the detailed roadmap](docs/roadmap-details.md#driving-feel).

### Speed limits and speeding

[Read this section in the detailed roadmap](docs/roadmap-details.md#speed-limits-and-speeding).

### Realism north star (ongoing)

[Read this section in the detailed roadmap](docs/roadmap-details.md#realism-north-star-ongoing).

## Local city service drives (built for 1.8, releases with 1.9)

[Read this section in the detailed roadmap](docs/roadmap-details.md#local-city-service-drives-built-for-18-releases-with-19).

## Timed facility work and stop-menu settling (built for 1.8, releases with 1.9)

[Read this section in the detailed roadmap](docs/roadmap-details.md#timed-facility-work-and-stop-menu-settling-built-for-18-releases-with-19).

## In-cab logbook, Record of Duty Status (built for 1.8, releases with 1.9)

[Read this section in the detailed roadmap](docs/roadmap-details.md#in-cab-logbook-record-of-duty-status-built-for-18-releases-with-19).

### Design sketch

[Read this section in the detailed roadmap](docs/roadmap-details.md#design-sketch).

## State troopers and law enforcement

[Read this section in the detailed roadmap](docs/roadmap-details.md#state-troopers-and-law-enforcement).

### Design sketch

[Read this section in the detailed roadmap](docs/roadmap-details.md#design-sketch-1).

## Shipped in 1.5.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-150).

## Shipped in 1.4.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-140).

## Shipped in 1.2.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-120).

## Shipped in 1.1.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-110).

## Shipped in 1.0.0

[Read this section in the detailed roadmap](docs/roadmap-details.md#shipped-in-100).

### Driving mechanics (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#driving-mechanics-done).

### Weather system (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#weather-system-done).

### Route planning (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#route-planning-done).

### Economy and progression (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#economy-and-progression-done).

### Accessibility (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#accessibility-done).

### Technical (done)

[Read this section in the detailed roadmap](docs/roadmap-details.md#technical-done).

## Future ideas (post-1.0)

[Read this section in the detailed roadmap](docs/roadmap-details.md#future-ideas-post-10).

### Gameplay depth

[Read this section in the detailed roadmap](docs/roadmap-details.md#gameplay-depth).

### World

[Read this section in the detailed roadmap](docs/roadmap-details.md#world).

### In-cab radio (1.8 / 1.9 candidate)

[Read this section in the detailed roadmap](docs/roadmap-details.md#in-cab-radio-18--19-candidate).

### Business

[Read this section in the detailed roadmap](docs/roadmap-details.md#business).

### Platforms and community

[Read this section in the detailed roadmap](docs/roadmap-details.md#platforms-and-community).
