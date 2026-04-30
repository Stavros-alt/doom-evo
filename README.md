# DOOM.EVO

A first-person shooter with evolving neural network enemies.

## Installation

```bash
pip install -r requirements.txt
```

## System Requirements

- Python 3.8+
- Minimum: Chromebook with integrated graphics, 4GB RAM
- Recommended: Desktop PC with dedicated GPU

## Performance Tips

For low-end hardware like Chromebooks:
- Set LOW_QUALITY=True in main.py (enabled by default)
- Reduce window size from default
- Game is designed to run locally; cloud execution may not work

## Running

```bash
python main.py
```

## Controls

WASD: Move/Strafe, Mouse: Look, Left Click/Space: Shoot, P: Pause, ESC: Menu.

Enemies evolve via genetic algorithm each round.
