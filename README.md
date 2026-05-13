# DOOM.EVO
evolving neural network fps. the enemies learn from your mistakes.

## Overview
every enemy has a genome driving its neural network. you kill them, the survivors breed, next round is harder. if you're bad they stay bad. it's a dark mirror or whatever.

walls have textures now. ceiling has stars. the floor is grimy. i spent way too long on this.

## Setup
### Linux/Mac
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```
requires python 3.10+, pygame, numpy.

### Windows
install python. run `python main.py`. if it crashes that's a you problem.

## Configuration
all hardcoded in `game_types.py`. no config files because i hate writing parsers.
- `POPULATION_SIZE`: enemies per generation (default 5)
- `MUTATION_RATE_BASE`: how much their brains shuffle each round
- `ENEMY_CLASS_CONFIG`: base stats for tank/scout types

## Controls
| key | action |
|---|---|
| WASD | move |
| mouse | look |
| left click / space | shoot |
| P | pause |
| ESC | menu / quit |
| 1-6 | buy upgrades in shop |

## Upgrades
you get credits after each round. spend them between rounds:
- max health (+scaling cost)
- speed (+scaling cost)
- armor (+scaling cost, slows you down)
- rapid smg (200 cr)
- heavy shotgun (350 cr)
- revive one death (500 cr)

## Building binaries
```bash
python3 build.py
```
builds linux + windows binaries via pyinstaller. windows build requires wine.
the binary is ~40mb because numpy is bloated.

## Known Issues
- enemies clip into walls sometimes. it's a feature now.
- pathfinding is still "walk toward player and hope".
- armor reduces damage but rounding sucks so you always take at least 1.
- the starfield ceiling is cached so it won't kill performance. probably.

## Downloads
prebuilt binaries in the Releases tab. for the lazy.
