<<<<<<< HEAD
=======
# Project Structure

## Sound Files
Required sound files and their locations:
- assets/sounds/menu_nav.wav
- assets/sounds/menu_select.wav
- assets/sounds/menu_back.wav
- assets/sounds/music/menu.ogg
- assets/sounds/engine/idle.wav
- assets/sounds/engine/rev.wav
- assets/sounds/engine/start.wav
- assets/sounds/vehicle/gear_shift.wav
- assets/sounds/vehicle/brake.wav
- assets/sounds/vehicle/tire_screech.wav
- assets/sounds/vehicle/collision.wav
- assets/sounds/weather/rain_light.wav
- assets/sounds/weather/rain_heavy.wav
- assets/sounds/weather/thunder.wav
- assets/sounds/weather/wind.wav

Missing sound files will use placeholder sounds.

## Engine Sound System
- Uses three-channel system for engine sounds (low, mid, high RPM)
- Crossfades between channels based on RPM
- Required engine sound files:
  - engine/idle.wav - Base engine idle sound
  - engine/low.wav - Low RPM (600-1200)
  - engine/mid.wav - Mid RPM (1200-2000)
  - engine/high.wav - High RPM (2000-2500)
  - engine/start.wav - Engine startup sound
  - engine/rev.wav - Quick rev sound effect
- Missing files use generated placeholder tones at frequencies:
  - Low: 220 Hz (A3)
  - Mid: 440 Hz (A4)
  - High: 880 Hz (A5)

## Sound Triggers
- Engine start: On game start
- Engine idle: After engine start
- Engine rev: On throttle increase > 20%
- Brake: On brake pedal press
- Gear shift: On successful gear change
- Collision: On obstacle impact

## Audio Feedback
- Speed announcements every 5 seconds
- Units based on settings (mph or km/h)
- Location announcements when starting
- Gear changes announced
- Warnings for collisions and obstacles

## Environment Visualization
- Side-scrolling view with fixed vertical position
- Environment width: 2000 pixels
- Road centered at y=400
- Buildings vary by location type:
  - Warehouse: Main warehouse, office, storage
  - Terminal: Terminal building, control tower, loading docks
  - Distribution: Distribution center, storage, loading area

>>>>>>> main
# SRAL Library Usage

## Overview
SRAL (Screen Reader Abstraction Library) provides cross-platform text-to-speech functionality. The project uses two wrappers:
- `sral_wrapper.py`: Direct wrapper of SRAL C++ functions
- `sral_tts.py`: Higher-level wrapper implementing accessible_output3 interface

## Key Features
- Cross-platform support (Windows, MacOS, Linux)
- Multiple speech engine support (NVDA, SAPI, JAWS, etc)
- Speech control (pause, resume, stop)
- Automatic engine fallback

## Engine Selection
- Default: Uses first available engine
- Can exclude specific engines during initialization
- Engine IDs:
  - NONE = 0
  - NVDA = 2
  - SAPI = 4
  - JAWS = 8
  - SPEECH_DISPATCHER = 16
  - UIA = 32
  - AV_SPEECH = 64
  - NARRATOR = 128

## Usage Tips
- Always initialize SRAL before use
- Clean up with `__del__` when done
- Test speech output with short phrases first
- Handle initialization failures gracefully

## Dependencies
- Requires SRAL.dll in same directory as Python wrapper
- Linux needs libspeechd-dev and libx11-dev
<<<<<<< HEAD
=======

## Code Structure
- Always import pygame in any module that uses pygame classes directly (Rect, Surface, etc.)
- Don't rely on transitive pygame imports from other modules

## Vehicle Physics System
- Uses realistic force calculations including:
  - Engine force (based on torque curve, gear ratio, throttle)
  - Drag force (proportional to velocity squared)
  - Rolling resistance (proportional to velocity)
  - Brake force (constant when brakes applied)
- Engine RPM calculation:
  - In gear: Based on wheel speed and gear ratio
  - In neutral: Idle RPM + throttle-based increase
- Gear ratios affect both engine force and RPM
- Gear system:
  - Array indices match gear numbers (index 0 = 1st gear)
  - Neutral handled as gear 0 with special case
  - Clutch values: 0.0 = engaged, 1.0 = disengaged
  - Force scaling factor of 50.0 for gameplay feel
  - Gear shifting requires:
    1. Press clutch (LSHIFT) > 80%
    2. Press number key for target gear
    3. Release clutch to engage
  - Debug output shows gear changes and clutch state
  - Gear shifting sequence:
    - Clutch must be pressed > 80% to start shift
    - Shift takes 0.5 seconds to complete
    - Must hold clutch until shift completes
    - Releasing clutch too early cancels shift
>>>>>>> main
