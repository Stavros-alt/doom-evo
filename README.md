# DOOM.EVO
first-person shooter with evolving neural network enemies. i wrote this because i was bored and now i regret half the architectural decisions i made.

## Why this exists
i wanted to see if i could make enemies that actually learn instead of just walking in straight lines. they use a genetic algorithm, so if they keep killing you, it's because they're getting smarter. if you're bad at the game, they'll probably stay stupid. it's basically a mirror for your lack of skill.

## Setup
i'm assuming you're on linux or mac because i don't have the energy to deal with windows registry issues.

1. check if you have python 3.10+: `python3 --version`
2. run the binary if you just want to play: `./DOOM_EVO`
3. if you want to run from source for some reason:
   ```bash
   pip install -r requirements.txt
   python3 main.py
   ```

## Configuration
most things are hardcoded in `main.py` because i didn't feel like making a parser for a `.yaml` file.
- `SCREEN_WIDTH`/`HEIGHT`: change these if your monitor is from 2005.
- `LOW_QUALITY`: set to `True` if you're running this on a potato.

## Usage
- **WASD**: move. don't get stuck in corners, the pathfinding is... experimental.
- **Mouse**: look around. it's very sensitive, i should probably add a slider.
- **Left Click/Space**: shoot. you have limited ammo, don't waste it.
- **P**: pause. use this when you need a mental break.
- **ESC**: menu. 

## Known Issues
- pathfinding is basically "walk toward player and pray".
- some wall textures look like garbage if you look too close.
- if you're on windows, the binary might work, but i wouldn't bet my scholarship on it.
- the shop prices are completely arbitrary. i didn't balance them at all.
- sometimes enemies get stuck in walls. just kill them and move on.
