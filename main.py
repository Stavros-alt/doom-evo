import os
import json
import pygame

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from game import GameEngine
from renderer import render_frame, render_hud, draw_minimap
from game_types import GamePhase, EnemyState, ShopItemType

SCREEN_WIDTH = 960
SCREEN_HEIGHT = 640
TARGET_FPS = 60


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

    player_upgrades = {
        "maxHealth": 100,
        "maxSpeed": 3.5,
        "maxAmmo": 80,
        "armor": 0,
        "weapon": "default",
        "weaponLevel": 1,
    }
    current_money = 0

    engine = None
    show_menu = True
    paused = False
    evolving_timer = 0
    round_end_timer = 0
    shop_timer = 0

    saved_genome_pools = None

    font_large = pygame.font.Font(None, 48)
    font_med = pygame.font.Font(None, 32)
    font_small = pygame.font.Font(None, 24)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if show_menu:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        show_menu = False
                        engine = GameEngine(round_num=1)
                        engine.mouse_locked = True
                        engine.mouse_held = False
                        pygame.event.set_grab(True)
                        pygame.mouse.set_visible(False)
                elif engine is not None:
                    if event.key == pygame.K_ESCAPE:
                        if engine.phase == GamePhase.PLAYING:
                            paused = True
                            engine.mouse_locked = False
                            pygame.event.set_grab(False)
                            pygame.mouse.set_visible(True)
                        elif engine.phase == GamePhase.DEAD or paused:
                            if engine.phase == GamePhase.DEAD:
                                # ugh, reset everything on death. why can't it just work?
                                player_upgrades = {
                                    "maxHealth": 100,
                                    "maxSpeed": 3.5,
                                    "maxAmmo": 80,
                                    "armor": 0,
                                    "weapon": "default",
                                    "weaponLevel": 1,
                                }
                                current_money = 0
                            show_menu = True
                            engine = None
                            pygame.event.set_grab(False)
                            pygame.mouse.set_visible(True)
                    elif event.key == pygame.K_p:
                        paused = not paused
                        if paused:
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
                SCREEN_WIDTH = event.w
                SCREEN_HEIGHT = event.h
                screen = pygame.display.set_mode(
                    (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE
                )

        if show_menu:
            _draw_menu(screen, font_large, font_med, font_small)
            pygame.display.flip()
            clock.tick(TARGET_FPS)
            continue

        if paused:
            # Still render the frozen frame + pause overlay
            surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            render_frame(
                surface,
                engine.map,
                engine.player,
                engine.enemies,
                engine.bullets,
                engine.particles,
                engine.pickups,
                engine.flash_alpha,
            )
            render_hud(
                surface,
                engine.player,
                engine.round,
                engine.score,
                engine.player.isShooting,
                engine.shoot_flash,
                engine.player.isPunching,
                engine.money,
            )
            draw_minimap(
                surface,
                SCREEN_WIDTH,
                SCREEN_HEIGHT,
                engine.map,
                engine.player,
                engine.enemies,
            )
            _draw_pause_overlay(surface, font_large, font_med)
            screen.blit(
                pygame.transform.scale(surface, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0)
            )
            pygame.display.flip()
            clock.tick(TARGET_FPS)
            continue

        # Read keys directly via get_pressed() — no event lag
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
            round_end_timer += dt
            if round_end_timer >= 2.0:
                engine.phase = GamePhase.EVOLVING
                evolving_timer = 0
        elif engine.phase == GamePhase.EVOLVING:
            evolving_timer += dt
            if evolving_timer >= 1.5:
                saved_genome_pools = engine.evolve_genomes(engine.round)
                current_money += engine.money
                engine = GameEngine(
                    round_num=engine.round + 1,
                    existing_genome_pools=saved_genome_pools,
                    player_upgrades=player_upgrades,
                )
                engine.money = current_money
                engine.phase = GamePhase.SHOP
                shop_timer = 0
                engine.mouse_locked = False
                pygame.event.set_grab(False)
                pygame.mouse.set_visible(True)
                round_end_timer = 0
                evolving_timer = 0
        elif engine.phase == GamePhase.SHOP:
            shop_timer += dt
            if shop_timer >= 0.5:
                if keys[pygame.K_1]:
                    cost = _buy_item(
                        ShopItemType.MAX_HEALTH, player_upgrades, current_money
                    )
                    if cost is not False:
                        current_money -= cost
                    shop_timer = 0
                elif keys[pygame.K_2]:
                    cost = _buy_item(
                        ShopItemType.MAX_SPEED, player_upgrades, current_money
                    )
                    if cost is not False:
                        current_money -= cost
                    shop_timer = 0
                elif keys[pygame.K_3]:
                    cost = _buy_item(ShopItemType.ARMOR, player_upgrades, current_money)
                    if cost is not False:
                        current_money -= cost
                    shop_timer = 0
                elif keys[pygame.K_4]:
                    cost = _buy_item(
                        ShopItemType.WEAPON_RAPID, player_upgrades, current_money
                    )
                    if cost is not False:
                        current_money -= cost
                    shop_timer = 0
                elif keys[pygame.K_5]:
                    cost = _buy_item(
                        ShopItemType.WEAPON_SPREAD, player_upgrades, current_money
                    )
                    if cost is not False:
                        current_money -= cost
                    shop_timer = 0
                elif keys[pygame.K_6]:
                    cost = _buy_item(
                        ShopItemType.REVIVE, player_upgrades, current_money
                    )
                    if cost is not False:
                        current_money -= cost
                    shop_timer = 0
                elif keys[pygame.K_RETURN]:
                    engine = GameEngine(
                        round_num=engine.round,
                        existing_genome_pools=saved_genome_pools,
                        player_upgrades=player_upgrades,
                    )
                    engine.money = current_money
                    engine.mouse_locked = True
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    shop_timer = 0
        elif engine.phase == GamePhase.DEAD:
            pass

        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        render_frame(
            surface,
            engine.map,
            engine.player,
            engine.enemies,
            engine.bullets,
            engine.particles,
            engine.pickups,
            engine.flash_alpha,
        )
        render_hud(
            surface,
            engine.player,
            engine.round,
            engine.score,
            engine.player.isShooting,
            engine.shoot_flash,
            engine.player.isPunching,
            engine.money,
        )
        draw_minimap(
            surface,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            engine.map,
            engine.player,
            engine.enemies,
        )

        if engine.phase == GamePhase.ROUND_END:
            _draw_round_end_overlay(surface, font_large, font_med, engine)
        elif engine.phase == GamePhase.EVOLVING:
            _draw_evolving_overlay(surface, font_large, font_med, engine)
        elif engine.phase == GamePhase.DEAD:
            _draw_dead_overlay(surface, font_large, font_med, engine)
        elif engine.phase == GamePhase.SHOP:
            _draw_shop_overlay(
                surface,
                font_large,
                font_med,
                font_small,
                engine,
                current_money,
                player_upgrades,
            )

        screen.blit(
            pygame.transform.scale(surface, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0)
        )
        pygame.display.flip()

    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)
    pygame.quit()


def _draw_menu(screen, font_large, font_med, font_small):
    screen.fill((5, 5, 8))

    title = font_large.render("DOOM.EVO", True, (255, 68, 0))
    title_rect = title.get_rect(
        center=(screen.get_width() // 2, screen.get_height() // 4 - 40)
    )
    screen.blit(title, title_rect)

    subtitle = font_med.render("Neural Network FPS", True, (170, 170, 170))
    sub_rect = subtitle.get_rect(
        center=(screen.get_width() // 2, screen.get_height() // 4 + 10)
    )
    screen.blit(subtitle, sub_rect)

    prompt = font_small.render("Press ENTER or SPACE to start", True, (255, 255, 255))
    prompt_rect = prompt.get_rect(
        center=(screen.get_width() // 2, screen.get_height() // 4 + 60)
    )
    screen.blit(prompt, prompt_rect)

    controls = [
        "WASD - Move / Strafe",
        "Mouse - Look",
        "Left Click / Space - Shoot",
        "P - Pause",
        "ESC - Menu / Pause",
    ]
    for i, text in enumerate(controls):
        ctrl = font_small.render(text, True, (140, 140, 140))
        ctrl_rect = ctrl.get_rect(
            center=(screen.get_width() // 2, screen.get_height() // 2 + 100 + i * 25)
        )
        screen.blit(ctrl, ctrl_rect)


def _draw_round_end_overlay(surface, font_large, font_med, engine):
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    surface.blit(overlay, (0, 0))

    text = font_large.render(f"ROUND {engine.round} COMPLETE", True, (0, 255, 68))
    rect = text.get_rect(center=(surface.get_width() // 2, surface.get_height() // 3))
    surface.blit(text, rect)

    info = font_med.render(f"Score: {engine.score}", True, (255, 170, 0))
    info_rect = info.get_rect(
        center=(surface.get_width() // 2, surface.get_height() // 3 + 50)
    )
    surface.blit(info, info_rect)


def _draw_evolving_overlay(surface, font_large, font_med, engine):
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surface.blit(overlay, (0, 0))

    text = font_large.render("EVOLVING NEXT GENERATION...", True, (255, 68, 0))
    rect = text.get_rect(center=(surface.get_width() // 2, surface.get_height() // 3))
    surface.blit(text, rect)

    if engine.generation_history:
        last = engine.generation_history[-1]
        info = font_med.render(
            f"Gen {last.round}: Best={last.bestFitness:.1f}  Avg={last.avgFitness:.1f}",
            True,
            (255, 255, 255),
        )
        info_rect = info.get_rect(
            center=(surface.get_width() // 2, surface.get_height() // 3 + 50)
        )
        surface.blit(info, info_rect)


def _draw_dead_overlay(surface, font_large, font_med, engine):
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((80, 0, 0, 180))
    surface.blit(overlay, (0, 0))

    text = font_large.render("YOU DIED", True, (255, 0, 0))
    rect = text.get_rect(center=(surface.get_width() // 2, surface.get_height() // 3))
    surface.blit(text, rect)

    info = font_med.render(
        f"Round: {engine.round}  Score: {engine.score}",
        True,
        (255, 170, 0),
    )
    info_rect = info.get_rect(
        center=(surface.get_width() // 2, surface.get_height() // 3 + 50)
    )
    surface.blit(info, info_rect)

    prompt = font_med.render("Press ESC for menu", True, (200, 200, 200))
    prompt_rect = prompt.get_rect(
        center=(surface.get_width() // 2, surface.get_height() // 2 + 40)
    )
    surface.blit(prompt, prompt_rect)


def _draw_pause_overlay(surface, font_large, font_med):
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surface.blit(overlay, (0, 0))

    text = font_large.render("PAUSED", True, (255, 255, 255))
    rect = text.get_rect(center=(surface.get_width() // 2, surface.get_height() // 3))
    surface.blit(text, rect)

    prompt = font_med.render("Press P to resume", True, (200, 200, 200))
    prompt_rect = prompt.get_rect(
        center=(surface.get_width() // 2, surface.get_height() // 3 + 50)
    )
    surface.blit(prompt, prompt_rect)


def _draw_shop_overlay(
    surface, font_large, font_med, font_small, engine, money, player_upgrades
):
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    surface.blit(overlay, (0, 0))

    title = font_large.render(f"SHOP - ROUND {engine.round}", True, (255, 68, 0))
    title_rect = title.get_rect(center=(surface.get_width() // 2, 50))
    surface.blit(title, title_rect)

    money_text = font_med.render(f"Money: ${money}", True, (255, 221, 68))
    money_rect = money_text.get_rect(center=(surface.get_width() // 2, 90))
    surface.blit(money_text, money_rect)

    # Calculate dynamic costs
    max_health_purchases = player_upgrades.get("maxHealthPurchases", 0)
    max_speed_purchases = player_upgrades.get("maxSpeedPurchases", 0)
    armor_purchases = player_upgrades.get("armorPurchases", 0)
    shop_items = [
        (
            "1",
            f"Max Health +{15 / (1 + max_health_purchases * 0.5):.1f}",
            int(100 * (1.5**max_health_purchases)),
        ),
        (
            "2",
            f"Speed +{0.3 / (1 + max_speed_purchases * 0.5):.2f}",
            int(150 * (1.5**max_speed_purchases)),
        ),
        ("3", "Armor +1 (blocks 10%)", int(200 * (1.5**armor_purchases))),
        ("4", "Rapid SMG", 200),
        ("5", "Heavy Shotgun", 350),
        ("6", "Revive (100 HP)", 500),
    ]

    start_y = 140
    for key, name, cost in shop_items:
        item_text = font_small.render(
            f"[{key}] {name} - ${cost}", True, (200, 200, 200)
        )
        item_rect = item_text.get_rect(center=(surface.get_width() // 2, start_y))
        surface.blit(item_text, item_rect)
        start_y += 30

    prompt = font_small.render("Press ENTER to continue", True, (255, 255, 255))
    prompt_rect = prompt.get_rect(
        center=(surface.get_width() // 2, surface.get_height() - 50)
    )
    surface.blit(prompt, prompt_rect)


def _buy_item(item_type, upgrades, money):
    # this function is a mess of ifs, but it works i guess
    if item_type == ShopItemType.MAX_HEALTH:
        purchases = upgrades.get("maxHealthPurchases", 0)
        cost = int(100 * (1.5**purchases))
        increment = 15 / (1 + purchases * 0.5)
        if upgrades.get("maxHealth", 100) >= 350:
            return False
        if money >= cost:
            upgrades["maxHealth"] = upgrades.get("maxHealth", 100) + increment
            upgrades["maxHealthPurchases"] = purchases + 1
            return cost
    elif item_type == ShopItemType.MAX_SPEED:
        purchases = upgrades.get("maxSpeedPurchases", 0)
        cost = int(150 * (1.5**purchases))
        increment = 0.3 / (1 + purchases * 0.5)
        if upgrades.get("maxSpeed", 3.5) >= 6.0:
            return False
        if money >= cost:
            upgrades["maxSpeed"] = upgrades.get("maxSpeed", 3.5) + increment
            upgrades["maxSpeedPurchases"] = purchases + 1
            return cost
    elif item_type == ShopItemType.ARMOR:
        purchases = upgrades.get("armorPurchases", 0)
        cost = int(200 * (1.5**purchases))
        if upgrades.get("armor", 0) >= 5:
            return False
        if money >= cost:
            upgrades["armor"] = upgrades.get("armor", 0) + 1
            upgrades["armorPurchases"] = purchases + 1
            # Weakness: high armor reduces speed
            upgrades["maxSpeed"] = max(2.0, upgrades.get("maxSpeed", 3.5) - 0.15)
            return cost
    elif item_type == ShopItemType.WEAPON_RAPID:
        if upgrades.get("weapon") == "rapid":
            return False
        cost = SHOP_ITEMS[item_type]["cost"]
        if money >= cost:
            upgrades["weapon"] = "rapid"
            upgrades["weaponLevel"] = upgrades.get("weaponLevel", 1) + 1
            return cost
    elif item_type == ShopItemType.WEAPON_SPREAD:
        if upgrades.get("weapon") == "spread":
            return False
        cost = SHOP_ITEMS[item_type]["cost"]
        if money >= cost:
            upgrades["weapon"] = "spread"
            upgrades["weaponLevel"] = upgrades.get("weaponLevel", 1) + 1
            return cost
    elif item_type == ShopItemType.REVIVE:
        if upgrades.get("revive", False):
            return False
        cost = SHOP_ITEMS[item_type]["cost"]
        if money >= cost:
            upgrades["revive"] = True
            return cost
    return False


if __name__ == "__main__":
    main()
