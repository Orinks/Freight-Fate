# Freight Fate

An accessible cross-country trucking simulation game built with Python, featuring text-to-speech support and immersive audio experience.

## Features

- Cross-country route system with real-world distances
- Weather simulation affecting driving conditions
- Accessible interface with text-to-speech support
- Realistic trucking mechanics (fuel, cargo, time management)
- Economy system with earnings and upgrades
- Mission and challenge system
- Save/Load functionality

## Installation

1. Ensure you have Python 3.11 installed
2. Clone this repository
3. Create a virtual environment:
```bash
python -m venv venv
```

4. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Unix/MacOS:
```bash
source venv/bin/activate
```

5. Install the required dependencies:
```bash
pip install -r requirements.txt
```

6. Run the game:
```bash
python src/main.py
```

Note: The game requires Python 3.11 specifically due to dependency compatibility. Other versions may not work correctly.

## Project Structure

```
freight-fate/
├── src/
│   ├── main.py              # Main game entry point
│   ├── audio/               # Audio interface and sound management
│   │   └── sound_manager.py
│   ├── game/                # Core game mechanics
│   │   ├── truck.py        # Truck-related functionality
│   │   ├── weather.py      # Weather simulation
│   │   ├── economy.py      # Economy system
│   │   └── missions.py     # Mission generation and management
│   ├── data/               # Game data and configurations
│   │   ├── routes.py       # Route system implementation
│   │   └── cities.json     # City data and connections
│   └── utils/              # Utility functions
│       └── save_load.py    # Save/Load functionality
├── assets/                 # Game assets (sounds, data files)
│   └── sounds/
├── tests/                  # Unit tests
├── requirements.txt        # Project dependencies
└── README.md              # Project documentation
```

## Controls

- Arrow Keys: Navigate menus and control truck
- Enter/Space: Select/Confirm
- Escape: Back/Pause
- F1: Toggle accessibility mode
- M: Toggle music
- +/-: Adjust volume

## Requirements

- Python 3.11 or compatible
- Pygame 2.5.2 or later
- Screen reader compatible
- Sound output device

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT License](LICENSE)
