# manual tests. i hate writing these.
import os
import sys
import pygame
import math

# add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import GameEngine
from game_types import GamePhase

def test_everything_functional():
    # dummy pygame init. hope this doesn't crash on this server.
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    pygame.init()
    
    # testing engine init
    # i swear if this fails after all that refactoring...
    eng = GameEngine(round_num=1)
    if not eng.map or not eng.player:
        print("engine init failed. typical.")
        return False
    
    # simulate some rounds
    # 60 ticks should be enough to see if it blows up
    dt = 1.0/60.0
    for i in range(60):
        eng.keys["w"] = True
        eng.update(dt)
        
    # test killing enemies
    for e in eng.enemies:
        e.health = 0
        e.state = e.state.__class__.DEAD
    
    eng._check_round_end()
    if eng.phase != GamePhase.ROUND_END:
        print("round end trigger failed. i'm done.")
        return False
        
    # test evolution
    # GA math is always a headache
    pools = eng.evolve_genomes(1)
    if not pools or 'tank' not in pools:
        print("evolution failed. great.")
        return False
        
    print("core logic seems ok. for now.")
    return True

if __name__ == "__main__":
    if test_everything_functional():
        sys.exit(0)
    else:
        sys.exit(1)
