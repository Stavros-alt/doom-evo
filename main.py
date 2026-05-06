import os
import json
import pygame

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from game import GameEngine
from renderer import render_frame, render_hud, draw_minimap
from game_types import GamePhase, EnemyState, ShopItemType

# i should probably put these in a config file but i'm too lazy.
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 640
TARGET_FPS = 60

LOW_QUALITY = True
INTERNAL_WIDTH = 640
INTERNAL_HEIGHT = 480

SHOP_ITEMS = {
    ShopItemType.MAX_HEALTH: {"name": "Max Health +25", "cost": 50, "key": "1"},
    ShopItemType.MAX_SPEED: {"name": "Speed +0.5", "cost": 75, "key": "2"},
    ShopItemType.ARMOR: {"name": "Armor +1 (blocks 10%)", "cost": 100, "key": "3"},
    ShopItemType.WEAPON_RAPID: {"name": "Rapid SMG", "cost": 200, "key": "4"},
    ShopItemType.WEAPON_SPREAD: {"name": "Heavy Shotgun", "cost": 350, "key": "5"},
    ShopItemType.REVIVE: {"name": "Revive (100 HP)", "cost": 500, "key": "6"},
}

def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("DOOM.EVO")
    clock = pygame.time.Clock()

    # player stats. i hope these are balanced.
    p_upgrades = {
        "maxHealth": 100,
        "maxSpeed": 3.5,
        "maxAmmo": 80,
        "armor": 0,
        "weapon": "default",
        "weaponLevel": 1,
    }
    cur_money = 0

    engine = None
    show_m = True
    is_paused = False
    ev_timer = 0
    re_timer = 0
    sh_timer = 0
    last_mm_ticks = 0

    saved_pools = None

    f_large = pygame.font.Font(None, 48)
    f_med = pygame.font.Font(None, 32)
    f_small = pygame.font.Font(None, 24)

    run = True
    while run:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False

            elif event.type == pygame.KEYDOWN:
                if show_m:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        show_m = False
                        engine = GameEngine(round_num=1)
                        engine.mouse_locked = True
                        engine.mouse_held = False
                        pygame.event.set_grab(True)
                        pygame.mouse.set_visible(False)
                elif engine is not None:
                    if event.key == pygame.K_ESCAPE:
                        if engine.phase == GamePhase.PLAYING:
                            is_paused = True
                            engine.mouse_locked = False
                            pygame.event.set_grab(False)
                            pygame.mouse.set_visible(True)
                        elif engine.phase == GamePhase.DEAD or is_paused:
                            if engine.phase == GamePhase.DEAD:
                                # reset everything. i'm done.
                                p_upgrades = {
                                    "maxHealth": 100,
                                    "maxSpeed": 3.5,
                                    "maxAmmo": 80,
                                    "armor": 0,
                                    "weapon": "default",
                                    "weaponLevel": 1,
                                }
                                cur_money = 0
                            show_m = True
                            engine = None
                            pygame.event.set_grab(False)
                            pygame.mouse.set_visible(True)
                    elif event.key == pygame.K_p:
                        is_paused = not is_paused
                        if is_paused:
                            engine.mouse_locked = False
                            pygame.event.set_grab(False)
                            pygame.mouse.set_visible(True)
                        else:
                            engine.mouse_locked = True
                            pygame.event.set_grab(True)
                            pygame.mouse.set_visible(False)

            elif event.type == pygame.MOUSEMOTION:
                if engine is not None and engine.mouse_locked:
                    engine.mouse_x += event.rel[0]

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and engine is not None:
                    engine.mouse_held = True

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and engine is not None:
                    engine.mouse_held = False

            elif event.type == pygame.VIDEORESIZE:
                SCREEN_WIDTH, SCREEN_HEIGHT = event.w, event.h
                screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)

        if show_m:
            _draw_menu(screen, f_large, f_med, f_small)
            pygame.display.flip()
            clock.tick(TARGET_FPS)
            continue

        if is_paused:
            # frozen frame with overlay. 
            sf = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
            render_frame(sf, engine.map, engine.player, engine.enemies, engine.bullets, engine.particles, engine.pickups, engine.flash_alpha, LOW_QUALITY)
            render_hud(sf, engine.player, engine.round, engine.score, engine.player.isShooting, engine.shoot_flash, engine.player.isPunching, engine.money)
            draw_minimap(sf, INTERNAL_WIDTH, INTERNAL_HEIGHT, engine.map, engine.player, engine.enemies)
            _draw_pause_overlay(sf, f_large, f_med)
            
            # center and scale.
            screen.fill((0, 0, 0))
            sw, sh = screen.get_size()
            rat = INTERNAL_WIDTH / INTERNAL_HEIGHT
            if sw / sh > rat:
                dw, dh = int(sh * rat), sh
                ox, oy = (sw - dw) // 2, 0
            else:
                dw, dh = sw, int(sw / rat)
                ox, oy = 0, (sh - dh) // 2
            screen.blit(pygame.transform.scale(sf, (dw, dh)), (ox, oy))
            pygame.display.flip()
            clock.tick(TARGET_FPS)
            continue

        keys = pygame.key.get_pressed()
        engine.keys["w"] = keys[pygame.K_w]
        engine.keys["a"] = keys[pygame.K_a]
        engine.keys["s"] = keys[pygame.K_s]
        engine.keys["d"] = keys[pygame.K_d]
        engine.keys["q"] = keys[pygame.K_q]
        engine.keys["e"] = keys[pygame.K_e]
        engine.keys["ArrowUp"] = keys[pygame.K_UP]
        engine.keys["ArrowDown"] = keys[pygame.K_DOWN]
        engine.keys["ArrowLeft"] = keys[pygame.K_LEFT]
        engine.keys["ArrowRight"] = keys[pygame.K_RIGHT]

        dt = clock.tick(TARGET_FPS) / 1000.0

        if engine.phase == GamePhase.PLAYING:
            engine.update(dt)
        elif engine.phase == GamePhase.ROUND_END:
            re_timer += dt
            if re_timer >= 2.0:
                engine.phase = GamePhase.EVOLVING
                ev_timer = 0
        elif engine.phase == GamePhase.EVOLVING:
            ev_timer += dt
            if ev_timer >= 1.5:
                saved_pools = engine.evolve_genomes(engine.round)
                cur_money += engine.money
                engine = GameEngine(round_num=engine.round + 1, existing_genome_pools=saved_pools, player_upgrades=p_upgrades)
                engine.money = cur_money
                engine.phase = GamePhase.SHOP
                sh_timer = 0
                engine.mouse_locked = False
                pygame.event.set_grab(False)
                pygame.mouse.set_visible(True)
                re_timer, ev_timer = 0, 0
        elif engine.phase == GamePhase.SHOP:
            sh_timer += dt
            if sh_timer >= 0.5:
                # why am i using numbers for keys?
                if keys[pygame.K_1]:
                    c = _buy_item(ShopItemType.MAX_HEALTH, p_upgrades, cur_money)
                    if c: cur_money -= c; sh_timer = 0
                elif keys[pygame.K_2]:
                    c = _buy_item(ShopItemType.MAX_SPEED, p_upgrades, cur_money)
                    if c: cur_money -= c; sh_timer = 0
                elif keys[pygame.K_3]:
                    c = _buy_item(ShopItemType.ARMOR, p_upgrades, cur_money)
                    if c: cur_money -= c; sh_timer = 0
                elif keys[pygame.K_4]:
                    c = _buy_item(ShopItemType.WEAPON_RAPID, p_upgrades, cur_money)
                    if c: cur_money -= c; sh_timer = 0
                elif keys[pygame.K_5]:
                    c = _buy_item(ShopItemType.WEAPON_SPREAD, p_upgrades, cur_money)
                    if c: cur_money -= c; sh_timer = 0
                elif keys[pygame.K_6]:
                    c = _buy_item(ShopItemType.REVIVE, p_upgrades, cur_money)
                    if c: cur_money -= c; sh_timer = 0
                elif keys[pygame.K_RETURN]:
                    engine = GameEngine(round_num=engine.round, existing_genome_pools=saved_pools, player_upgrades=p_upgrades)
                    engine.money = cur_money
                    engine.mouse_locked = True
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    sh_timer = 0

        sf = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
        render_frame(sf, engine.map, engine.player, engine.enemies, engine.bullets, engine.particles, engine.pickups, engine.flash_alpha, LOW_QUALITY)
        render_hud(sf, engine.player, engine.round, engine.score, engine.player.isShooting, engine.shoot_flash, engine.player.isPunching, engine.money)
        draw_minimap(sf, INTERNAL_WIDTH, INTERNAL_HEIGHT, engine.map, engine.player, engine.enemies)

        if engine.phase == GamePhase.ROUND_END:
            _draw_round_end_overlay(sf, f_large, f_med, engine)
        elif engine.phase == GamePhase.EVOLVING:
            _draw_evolving_overlay(sf, f_large, f_med, engine)
        elif engine.phase == GamePhase.DEAD:
            _draw_dead_overlay(sf, f_large, f_med, engine)
        elif engine.phase == GamePhase.SHOP:
            _draw_shop_overlay(sf, f_large, f_med, f_small, engine, cur_money, p_upgrades)

        screen.fill((0, 0, 0))
        sw, sh = screen.get_size()
        rat = INTERNAL_WIDTH / INTERNAL_HEIGHT
        if sw / sh > rat:
            dw, dh = int(sh * rat), sh
            ox, oy = (sw - dw) // 2, 0
        else:
            dw, dh = sw, int(sw / rat)
            ox, oy = 0, (sh - dh) // 2
        screen.blit(pygame.transform.scale(sf, (dw, dh)), (ox, oy))
        pygame.display.flip()

    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)
    pygame.quit()

def _draw_menu(sc, f_l, f_m, f_s):
    sc.fill((5, 5, 8))
    t = f_l.render("DOOM.EVO", True, (255, 68, 0))
    sc.blit(t, t.get_rect(center=(sc.get_width() // 2, sc.get_height() // 4 - 40)))
    
    st = f_m.render("Neural Network FPS", True, (170, 170, 170))
    sc.blit(st, st.get_rect(center=(sc.get_width() // 2, sc.get_height() // 4 + 10)))

    ct = ["WASD - Move", "Mouse - Look", "Space - Shoot", "P - Pause", "ESC - Menu"]
    for i, text in enumerate(ct):
        c = f_s.render(text, True, (140, 140, 140))
        sc.blit(c, c.get_rect(center=(sc.get_width() // 2, sc.get_height() // 2 + 100 + i * 25)))

def _draw_round_end_overlay(sf, f_l, f_m, en):
    ov = pygame.Surface(sf.get_size(), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 150))
    sf.blit(ov, (0, 0))
    t = f_l.render(f"ROUND {en.round} COMPLETE", True, (0, 255, 68))
    sf.blit(t, t.get_rect(center=(sf.get_width() // 2, sf.get_height() // 3)))
    
    # let them know why they're waiting
    it = f_m.render("UPDATING GENOME POOLS...", True, (200, 200, 200))
    sf.blit(it, it.get_rect(center=(sf.get_width() // 2, sf.get_height() // 3 + 60)))

def _draw_evolving_overlay(sf, f_l, f_m, en):
    ov = pygame.Surface(sf.get_size(), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 180))
    sf.blit(ov, (0, 0))
    t = f_l.render("EVOLVING NEXT GEN...", True, (255, 68, 0))
    sf.blit(t, t.get_rect(center=(sf.get_width() // 2, sf.get_height() // 3)))

def _draw_dead_overlay(sf, f_l, f_m, en):
    ov = pygame.Surface(sf.get_size(), pygame.SRCALPHA)
    ov.fill((80, 0, 0, 180))
    sf.blit(ov, (0, 0))
    t = f_l.render("YOU DIED", True, (255, 0, 0))
    sf.blit(t, t.get_rect(center=(sf.get_width() // 2, sf.get_height() // 3)))
    
    pt = f_m.render("Press ESC for Menu", True, (200, 200, 200))
    sf.blit(pt, pt.get_rect(center=(sf.get_width() // 2, sf.get_height() // 2 + 20)))

def _draw_pause_overlay(sf, f_l, f_m):
    ov = pygame.Surface(sf.get_size(), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 160))
    sf.blit(ov, (0, 0))
    t = f_l.render("PAUSED", True, (255, 255, 255))
    sf.blit(t, t.get_rect(center=(sf.get_width() // 2, sf.get_height() // 3)))
    
    pt = f_m.render("Press P to Resume", True, (200, 200, 200))
    sf.blit(pt, pt.get_rect(center=(sf.get_width() // 2, sf.get_height() // 3 + 60)))

def _draw_shop_overlay(sf, f_l, f_m, f_s, en, mon, up):
    ov = pygame.Surface(sf.get_size(), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 200))
    sf.blit(ov, (0, 0))
    
    title = f_l.render(f"SHOP - PHASE {en.round}", True, (255, 68, 0))
    sf.blit(title, title.get_rect(center=(sf.get_width() // 2, 50)))
    
    m_txt = f_m.render(f"Credits: ${mon}", True, (255, 221, 68))
    sf.blit(m_txt, m_txt.get_rect(center=(sf.get_width() // 2, 90)))
    
    hp_p = up.get("maxHealthPurchases", 0)
    sp_p = up.get("maxSpeedPurchases", 0)
    ar_p = up.get("armorPurchases", 0)
    
    it = [
        ("1", f"Max Health +{15 / (1 + hp_p * 0.5):.1f}", int(100 * (1.5**hp_p))),
        ("2", f"Speed +{0.3 / (1 + sp_p * 0.5):.2f}", int(150 * (1.5**sp_p))),
        ("3", "Armor +1", int(200 * (1.5**ar_p))),
        ("4", "Rapid SMG", 200),
        ("5", "Heavy Shotgun", 350),
        ("6", "Revive", 500),
    ]

    sy = 140
    for key, name, cost in it:
        txt = f_s.render(f"[{key}] {name} - ${cost}", True, (200, 200, 200))
        sf.blit(txt, txt.get_rect(center=(sf.get_width() // 2, sy)))
        sy += 30

    # finally adding the prompt. i'm tired.
    pt = f_s.render("Press ENTER to start next round", True, (255, 255, 255))
    sf.blit(pt, pt.get_rect(center=(sf.get_width() // 2, sf.get_height() - 50)))

def _buy_item(it_type, up, mon):
    # i'm keeping this mess of ifs. it works.
    if it_type == ShopItemType.MAX_HEALTH:
        p = up.get("maxHealthPurchases", 0)
        c = int(100 * (1.5**p))
        if up.get("maxHealth", 100) < 350 and mon >= c:
            up["maxHealth"] = up.get("maxHealth", 100) + (15 / (1 + p * 0.5))
            up["maxHealthPurchases"] = p + 1
            return c
    elif it_type == ShopItemType.MAX_SPEED:
        p = up.get("maxSpeedPurchases", 0)
        c = int(150 * (1.5**p))
        if up.get("maxSpeed", 3.5) < 6.0 and mon >= c:
            up["maxSpeed"] = up.get("maxSpeed", 3.5) + (0.3 / (1 + p * 0.5))
            up["maxSpeedPurchases"] = p + 1
            return c
    elif it_type == ShopItemType.ARMOR:
        p = up.get("armorPurchases", 0)
        c = int(200 * (1.5**p))
        if up.get("armor", 0) < 5 and mon >= c:
            up["armor"] = up.get("armor", 0) + 1
            up["armorPurchases"] = p + 1
            up["maxSpeed"] = max(2.0, up.get("maxSpeed", 3.5) - 0.15)
            return c
    elif it_type == ShopItemType.WEAPON_RAPID:
        if up.get("weapon") != "rapid" and mon >= 200:
            up["weapon"] = "rapid"
            up["weaponLevel"] = up.get("weaponLevel", 1) + 1
            return 200
    elif it_type == ShopItemType.WEAPON_SPREAD:
        if up.get("weapon") != "spread" and mon >= 350:
            up["weapon"] = "spread"
            up["weaponLevel"] = up.get("weaponLevel", 1) + 1
            return 350
    elif it_type == ShopItemType.REVIVE:
        if not up.get("revive", False) and mon >= 500:
            up["revive"] = True
            return 500
    return False

if __name__ == "__main__":
    main()
