# DOOM.EVO

A first-person shooter where enemies are driven by neural networks that evolve across rounds using a genetic algorithm.

## Requirements

- Python 3.8+
- pygame
- numpy

## Installation

```bash
pip install pygame numpy
```

## Running

```bash
python main.py
```

## Controls

| Key | Action |
|-----|--------|
| WASD | Move / Strafe |
| Mouse | Look |
| Left Click / Space | Shoot |
| P | Pause |
| ESC | Menu |

## How It Works

Enemies are controlled by neural networks (8 inputs -> 12 -> 8 -> 6 outputs). Each round, the best-performing genomes are selected, crossed over, and mutated for the next generation. Over time, enemies learn to hunt more effectively.

## Gameplay Demo

![Doom Evo Gameplay](doom.gif)
