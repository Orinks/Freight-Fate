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
