# Freight Fate on iPhone and iPad

The iOS game is the desktop game. The same Rust states and menus run under
SDL2's UIKit backend, and speech goes through Prism, which talks to VoiceOver
when it is running and to the system voice (AVSpeech) when it is not. The
screen is one full-screen touch area; in menus its gestures are the same key
presses the desktop game reads, at the wheel they run driving commands
directly, and game controllers work exactly as they do
on the desktop.

## Gestures

With VoiceOver on, the game screen is a direct-touch area: once VoiceOver
focus lands on it (it does at launch), your gestures go straight to the game.
VoiceOver's own standard actions are also answered.

Outside the drive, and for the gestures the drive leaves fixed:

| Gesture | Key |
|---|---|
| Tap | Comma (repeat the last line) |
| Double tap, or VoiceOver double tap | Enter |
| Swipe up / down | Up / Down |
| Swipe left / right | Left / Right |
| Two-finger tap | Tab |
| Two-finger swipe up | F1 (help) |
| Two-finger swipe down | Escape |
| Two-finger swipe left / right | Comma / Period |
| VoiceOver magic tap (two-finger double tap) | Space |
| Three-finger swipe up / down | Home / End |
| Three-finger swipe left / right | Page Up / Page Down |
| Three-finger tap | F2: while driving, the list of every driving command; in a name field, read the name back |
| Three-finger double tap | Show or hide the on-screen keyboard, for letter commands |
| Hold one finger anywhere | Hold Up (gas) until you lift |
| Tap, lift, then hold one finger anywhere within 0.28 seconds | Hold Down (brake) until you lift |
| Hold two fingers anywhere | Emergency brake until you lift |
| Hold three fingers anywhere | Horn until you lift |

Because the game screen takes touches directly, VoiceOver's scrub (two-finger
Z) reads there as a two-finger swipe; use a two-finger swipe down to go back.

## Driving gestures

While driving, the gestures below run their commands directly, with no menu in
between. Each one can be moved to any other command in Settings, Gameplay,
Controls, Touch gestures, the way keyboard keys and controller buttons can.

| Gesture | Default command |
|---|---|
| While holding gas, tap with a second finger | Automatic speed control: adaptive cruise, or the speed keeper in low-speed zones |
| While holding gas, swipe up / down with a second finger | Shift up / down |
| While holding gas, swipe left / right with a second finger | Steer or change lanes left / right |
| While holding brake, tap with a second finger | Parking brake |
| While holding brake, double tap with a second finger | Engine on or off |
| Tap | Speed |
| Swipe up / down | Raise / lower the cruise target |
| Two-finger tap | Status menu |
| Magic tap (two-finger double tap) | Pause |
| Three-finger swipe up | Route and location |
| Three-finger swipe down | Road ahead |

So to set cruise: hold anywhere until you reach 20 miles per hour, tap with a
second finger, and lift. The other second-finger gestures are ready for any
command you choose.

These stay fixed: the holds are the pedals, swipes left and right steer (or
change lanes with lane keeping on full), double tap is Enter, two-finger
swipe down pauses, two-finger swipe up is help, two-finger swipes left and
right review messages, and three-finger swipes left and right tune the radio.
Everything else is on the driving command list: a three-finger tap opens it,
swipe to a command, and double tap runs it and puts you back on the road.
Three-finger double tap still opens the on-screen keyboard.

VoiceOver's adjustable swipes (up and down with VoiceOver focus on the game)
also send Up and Down.

## Controllers

Any controller iOS supports (Xbox, PlayStation, MFi, Switch Pro) is read
through SDL2's GameController backend, with the same bindings, rumble and
controller settings as the desktop.

## Building

You need a Mac with Xcode, the pinned Rust toolchain, `uv`, and CMake.

```bash
rustup target add aarch64-apple-ios aarch64-apple-ios-sim
uv sync --group dev
uv run python tools/build_ios.py --install --launch   # Simulator
```

For a device, pass a signing identity and a provisioning profile for the
bundle identifier `net.orinks.freightfate`:

```bash
uv run python tools/build_ios.py --device \
    --sign-identity "Apple Development: ..." \
    --provisioning-profile path/to/profile.mobileprovision
```

The script builds the Rust game for the iOS target, bakes the world data,
downloads and verifies the BASS iOS frameworks (never committed), stages the
sound and music packs, writes `Info.plist`, and signs `build/ios/<sdk>/FreightFate.app`.

Prism compiles its VoiceOver/AVSpeech backend from source for iOS; the
`freight-fate` build script links the UIKit, AVFoundation and GameController
frameworks it and SDL2 need, plus clang's iOS runtime for `@available` checks.

## Platform notes

- Saves, settings and logs live in the app sandbox under
  `Library/Application Support/FreightFate`.
- The game does not update itself on iOS; the App Store or TestFlight does,
  so Settings has no Updates category. The main menu has no Quit (iOS closes
  apps, they do not quit themselves), and a two-finger swipe down there does
  nothing. Settings also leaves out Problem reports (the log is in the
  sandbox, out of reach) and the braille-only Output row (it needs NVDA or
  JAWS).
- Spoken prompts name the gesture for a control ("press a second-finger
  double tap while holding brake to start the engine"), or its row
  on the three-finger tap command list when no gesture runs it. Pressing a
  key on a hardware keyboard, or a controller button, switches them back to
  key or button names until the screen is touched again.
- The Simulator has no BASS audio device, so only speech is heard there.

## Manual VoiceOver test checklist

- Test with VoiceOver on and off; on iOS 17 or later confirm direct touch is silent on touch.
- Hold gas in the centre, corners, and edges; tap then hold for brake without firing single tap.
- Test every second-finger command, gas-hold lane changes, two-finger emergency brake, and three-finger horn.
- Verify magic tap, escape scrub, the haptics switch, and release feedback.
- Enter Practice gestures, verify double escape exits, and verify the first-drive practice offer appears once.
