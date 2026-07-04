# Forum Gameplay Polish Design

## Goal

Address forum feedback items 2 through 6 in one focused branch:

- Make dispatch job F1 useful by opening a structured, digestible job detail view.
- Make the two trucks easier to compare and explain whether upgrades carry across trucks.
- Make the horn loop while held.
- Add lightweight tire wear and truck cleaning maintenance so the garage matters more.
- Rebalance long-haul dispatch pay so longer trips are not obviously worse than short trips.
- Further reduce the stacked speech burst when a run starts.

Horn-required road hazards are out of scope for this pass. The player feedback asked for the horn to loop; new horn-specific hazard events can be considered later if desired.

## Dispatch Job Detail View

Pressing F1 on a dispatch-board job should push a reviewable job detail state instead of only speaking the existing one-line help. The view should present short lines:

- Cargo and equipment.
- Origin facility and destination facility.
- Distance.
- Pay and dollars per mile.
- Deadline.
- Endorsement or locked-state explanation when relevant.
- HOS or risk warning when the board already knows one.
- A note that route rest, fuel, toll, and weather details are inspected after pickup.

Enter accepts the job from the detail view. Escape returns to the dispatch board. The original job row stays concise for fast menu browsing.

## Looping Horn

Holding H should start the horn and releasing H should stop it. The horn should also stop when leaving the driving state so it cannot get stuck through pause/menu transitions.

This pass does not add new horn-required hazards. Existing hazards remain brake/avoidance events.

## Truck Identity And Upgrade Wording

The garage should make the two trucks easier to compare. The player should hear the practical tradeoff between the starter rig and the heavy hauler without needing to infer it from stats: acceleration, hauling strength, tank size, fuel appetite, and intended use.

Upgrades currently carry across trucks through the profile-wide `upgrades` dictionary. This pass should make that intentional in the UI copy: upgrades are treated as owned shop packages available to the fleet, not bolted permanently to one truck. A future per-truck upgrade system would be a larger save/schema change and is out of scope.

## Maintenance

Add lightweight maintenance fields that accrue during driving:

- Tire wear from miles, worsened modestly by hard braking, collisions, and rough events.
- Dirt/cleanliness from miles and weather, worsened by rain, snow, and dusty/windy conditions.

The garage should show these in status and offer clear actions:

- Replace tires or perform tire service when wear is meaningful.
- Wash truck when dirty.

The system should not punish perfect driving too harshly, but even clean driving should slowly create maintenance needs over long careers.

## Long-Haul Pay

Long-haul jobs should stop dipping to obviously poor rates such as around 3 dollars per mile when short trips offer much more. Keep short hauls attractive through convenience and fast turnover, but make long hauls pay fairly for time committed.

Use a distance-aware minimum pay or banded rate floor inside job generation. The dispatch row/detail view should expose dollars per mile so players can understand the offer without mental math.

## Startup Speech Cleanup

Starting or resuming a run should avoid stacked back-to-back messages. The initial drive announcement should be shorter and should not duplicate tutorial, air-brake, route, and control guidance in one burst. Terse mode should be especially quiet.

The goal is not to hide critical information. The first drive still needs orientation, but the player should get one concise starting status and then hear follow-up prompts only when they become relevant.

## Deferred Realism Follow-Up

Two feedback items should be handled in a later realism/data pass:

- Grades and mountain driving feeling too mild. This likely needs route elevation/grade data review, physics tuning, and clearer grade readouts.
- Truck speed limits and governed speeds. Current legal posted truck limits may allow 70 mph in some states, while many fleets govern trucks lower. A later pass should separate posted legal limits from optional company/governed speed behavior.

## Testing

Focused tests should cover:

- F1 on a dispatch job opens the detail view, and Enter/Escape behave correctly.
- Job detail lines include pay per mile and route-detail messaging.
- Truck menu/help text makes the two trucks' differences clear and says upgrades carry across the fleet.
- H keydown starts horn looping and keyup stops it.
- Tire wear and dirt accrue over driving and are serviceable in the garage.
- Long-haul generated jobs meet the new pay floor.
- Start-drive speech produces one concise initial announcement and avoids tutorial/air-brake pileups in terse mode.

Run focused tests first, then `uv run pytest -q` and `uv run ruff check src tests tools`.

## Accessibility Notes

This is a desktop/Pygame audio-first app, not a web app. Accessibility validation should focus on keyboard reachability, spoken/status clarity, and reviewable line structure.

The job detail view should avoid dense paragraph speech. Use short lines that can be read one at a time and replayed by moving through the menu/view. The horn loop must be fully keyboard operable with keydown and keyup, and must not get stuck after leaving driving.
