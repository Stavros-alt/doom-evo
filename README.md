# DOOM.EVO
a first-person shooter with evolving neural network enemies. it's built from scratch and it actually works. 

## Downloads
if you don't want to install python and deal with dependencies, just go to the **Releases** section on the sidebar on the right. i've uploaded standalone binaries for windows and linux there. just download and run.

## Why this exists
i wanted to see if i could make enemies that actually learn instead of just walking in straight lines. they use a genetic algorithm, so they evolve based on how you play. if they keep killing you, it's because the neural networks are working. if you're bad, they'll stay stupid. it's basically a mirror for your skill level.

## Source Setup
if you actually want to run it from source for some reason:
1. python 3.10+
2. `pip install -r requirements.txt`
3. `python3 main.py`

## Usage
- **WASD**: move. 
- **Mouse**: look. 
- **Left Click/Space**: shoot. 
- **P**: pause. 
- **ESC**: menu. 

## Notes
- pathfinding is "walk toward player and pray".
- shop prices are balanced. i spent way too much time on the math.
- sometimes enemies get stuck in walls. just kill them and move on.
