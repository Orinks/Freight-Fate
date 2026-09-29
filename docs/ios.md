# Freight Fate on iPhone and iPad

The iOS game is the desktop game. The same Rust states and menus run under
SDL2's UIKit backend, and speech goes through Prism, which talks to VoiceOver
when it is running and to the system voice (AVSpeech) when it is not. The
screen is one full-screen touch area; gestures on it become the same key
presses the desktop game reads, and game controllers work exactly as they do
on the desktop.

## Gestures

With VoiceOver on, the game screen is a direct-touch area: once VoiceOver
focus lands on it (it does at launch), your gestures go straight to the game.
VoiceOver's own standard actions are also answered.

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

While driving, the holds are the pedals, swipes left and right steer (or change
lanes with lane keeping on full), a two-finger tap opens the status menu, the
magic tap reads your speed, and three-finger swipes left and right tune the
radio. Everything else a letter key does is on the driving command list: a
three-finger tap opens it, swipe to a command, and double tap runs it and puts
you back on the road.

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
- The game does not update itself on iOS; the App Store or TestFlight does.
- The Simulator has no BASS audio device, so only speech is heard there.
