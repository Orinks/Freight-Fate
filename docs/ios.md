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
| Touch and hold the top half | Hold Up (throttle) until you lift |
| Touch and hold the bottom half | Hold Down (brake) until you lift |

Because the game screen takes touches directly, VoiceOver's scrub (two-finger
Z) reads there as a two-finger swipe; use a two-finger swipe down to go back.

## Driving gestures

While driving, the gestures below run their commands directly, with no menu in
between. Each one can be moved to any other command in Settings, Gameplay,
Controls, Touch gestures, the way keyboard keys and controller buttons can.

| Gesture | Default command |
|---|---|
| Hold the top half, tap with a second finger | Automatic speed control: adaptive cruise, or the speed keeper in low-speed zones |
| Hold the top half, swipe up / down with a second finger | Shift up / down |
| Hold the bottom half, tap with a second finger | Parking brake |
| Hold the bottom half, double tap with a second finger | Engine on or off |
| Tap | Speed |
| Swipe up / down | Raise / lower the cruise target |
| Two-finger tap | Status menu |
| Magic tap (two-finger double tap) | Pause |
| Three-finger swipe up | Route and location |
| Three-finger swipe down | Road ahead |

So to set cruise: hold the top half until you reach 20 miles per hour, tap
with a second finger, and lift. The other second-finger gestures (double tap
on the top half, and left, right, up and down swipes on the bottom half) start
out doing nothing, ready for any command you choose.

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

### An IPA for sideloading

To build for a real iPhone or iPad and produce an IPA without supplying an
Apple signing certificate or provisioning profile:

```bash
uv run python tools/build_ios.py --sideload
```

The output is `build/ios/FreightFate.ipa`, containing
`Payload/FreightFate.app`. Import that IPA into your sideloading tool, such as
[Sideloadly](https://sideloadly.io/), which signs and installs it using your
Apple account. The builder applies only an ad-hoc signature; the IPA needs
to be re-signed before a device can run it. Signing happens in the
sideloading tool, so the build script does not need your Apple credentials.

This option selects the device target automatically. A Simulator `.app`
cannot be made into a device build just by zipping it or changing its
extension. `--sideload` cannot be combined with signing credentials or the
Simulator's `--install` / `--launch` options. Add `--no-music` for a smaller
IPA without the music pack.

### An IPA signed with your own certificate

For a signed device IPA, pass a signing identity and a provisioning profile
for the bundle identifier `net.orinks.freightfate`:

```bash
uv run python tools/build_ios.py --device --ipa \
    --sign-identity "Apple Development: ..." \
    --provisioning-profile path/to/profile.mobileprovision
```

This also writes `build/ios/FreightFate.ipa`. For direct installation,
use a development or ad-hoc distribution profile that includes your device;
an App Store profile is for App Store Connect / TestFlight uploads, not
direct sideloading. See Apple's
[registered-device distribution guide](https://developer.apple.com/documentation/xcode/distributing-your-app-to-registered-devices).
Omit `--ipa` if you only need the signed `.app` bundle.

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
  double tap while you hold the bottom half to start the engine"), or its row
  on the three-finger tap command list when no gesture runs it. Pressing a
  key on a hardware keyboard, or a controller button, switches them back to
  key or button names until the screen is touched again.
- The Simulator has no BASS audio device, so only speech is heard there.
