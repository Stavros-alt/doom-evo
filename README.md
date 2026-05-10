# DOOM.EVO
evolving neural network shooter. i built this because i was bored and wanted to see if enemies could actually learn.

## Overview
the enemies aren't hardcoded. they use a genetic algorithm to evolve their neural networks based on how you play. if you keep winning, the next generation will be smarter. if you suck, they stay stupid. it's basically a mirror for your skill level.

## Why this exists
i was tired of static ai in games. every round, the "fittest" enemies survive and pass on their brain weights. after a few rounds, they'll start strafing, dodging, and actually aiming instead of just standing there. 

## Setup
### Linux/Mac (the only ones i care about)
1. get python 3.10+
2. `pip install -r requirements.txt`
3. `python3 main.py`

### Windows
you're on your own. it might work with `python main.py` if you have everything installed correctly. if it doesn't, don't ask me.

## Configuration
everything is in `game_types.py` or hardcoded. i don't have time for fancy config files.
- `POPULATION_SIZE`: how many enemies in a generation.
- `MUTATION_RATE_BASE`: how much their brains change.
- `ENEMY_CLASS_CONFIG`: stats like health and damage for different enemy types.

## Usage
- **WASD**: move. 
- **Mouse**: look. 
- **Left Click/Space**: shoot. 
- **P**: pause. 
- **ESC**: menu. 
- **1-6**: buy upgrades in the shop between rounds.

## Known Issues
- pathfinding is basically "walk toward player and pray".
- enemies sometimes clip into walls. i'm not fixing it today.
- if you buy a lot of armor, you used to be immortal. i fixed it, you'll still take at least 1 damage.
-Standalone binaries are in the Releases section if you're lazy.
