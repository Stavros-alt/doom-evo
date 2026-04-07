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


SAVE_FILE = "savegame.json"

SLOT_DEFAULTS = {
    "player_upgrades": {
        "maxHealth": 100,
        "maxSpeed": 3.5,
        "maxAmmo": 80,
        "armor": 0,
        "weapon": "default",
        "weaponLevel": 1,
    },
    "current_money": 0,
    "total_kills": 0,
    "highest_round": 0,
}


def _load_save():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                data = json.load(f)
                return {
                    "slots": data.get("slots", [None, None, None]),
                    "selected_slot": data.get("selected_slot", 0),
                }
        except Exception:
            pass
    return {"slots": [None, None, None], "selected_slot": 0}


def _get_slot_data(slot_idx):
    save = _load_save()
    return save["slots"][slot_idx] or SLOT_DEFAULTS.copy()


def _save_game(
    slot_idx, player_upgrades, current_money, total_kills, highest_round, all_slots=None
):
    save = _load_save()
    save["slots"][slot_idx] = {
        "player_upgrades": player_upgrades,
        "current_money": current_money,
        "total_kills": total_kills,
        "highest_round": highest_round,
    }
    save["selected_slot"] = slot_idx
    if all_slots is not None:
        all_slots[slot_idx] = save["slots"][slot_idx]
    with open(SAVE_FILE, "w") as f:
        json.dump(save, f)


def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("DOOM.EVO")
    clock = pygame.time.Clock()

    save_data = _load_save()
    current_slot = save_data["selected_slot"]
    all_slots = save_data["slots"]
    slot_data = _get_slot_data(current_slot)
    player_upgrades = slot_data["player_upgrades"]
    current_money = slot_data["current_money"]
    total_kills = slot_data["total_kills"]
    highest_round = slot_data["highest_round"]

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
                    if event.key == pygame.K_1:
                        current_slot = 0
                        slot_data = _get_slot_data(current_slot)
                        player_upgrades = slot_data["player_upgrades"]
                        current_money = slot_data["current_money"]
                        total_kills = slot_data["total_kills"]
                        highest_round = slot_data["highest_round"]
                        all_slots[0] = slot_data if slot_data != SLOT_DEFAULTS else None
                    elif event.key == pygame.K_2:
                        current_slot = 1
                        slot_data = _get_slot_data(current_slot)
                        player_upgrades = slot_data["player_upgrades"]
                        current_money = slot_data["current_money"]
                        total_kills = slot_data["total_kills"]
                        highest_round = slot_data["highest_round"]
                        all_slots[1] = slot_data if slot_data != SLOT_DEFAULTS else None
                    elif event.key == pygame.K_3:
                        current_slot = 2
                        slot_data = _get_slot_data(current_slot)
                        player_upgrades = slot_data["player_upgrades"]
                        current_money = slot_data["current_money"]
                        total_kills = slot_data["total_kills"]
                        highest_round = slot_data["highest_round"]
                        all_slots[2] = slot_data if slot_data != SLOT_DEFAULTS else None
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        show_menu = False
                        engine = GameEngine(round_num=1)
                        engine.mouse_locked = True
                        engine.mouse_held = False
                        pygame.event.set_grab(True)
                        pygame.mouse.set_visible(False)
                elif engine is not None:
                    if event.key == pygame.K_ESCAPE:
                        engine.mouse_locked = False
                        pygame.event.set_grab(False)
                        pygame.mouse.set_visible(True)
                        if engine is not None and engine.phase != GamePhase.PLAYING:
                            total_kills += engine.kill_count
                        _save_game(
                            current_slot,
                            player_upgrades,
                            current_money,
                            total_kills,
                            highest_round,
                            all_slots,
                        )
                        show_menu = True
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
            _draw_menu(
                screen, font_large, font_med, font_small, all_slots, current_slot
            )
            pygame.display.flip()
            clock.tick(TARGET_FPS)
            continue

        if engine is None:
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
                engine.kill_count,
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
                total_kills += engine.kill_count
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
                if engine.round > highest_round:
                    highest_round = engine.round
        elif engine.phase == GamePhase.SHOP:
            shop_timer += dt
            if shop_timer >= 0.5:
                if keys[pygame.K_1]:
                    if _buy_item(
                        ShopItemType.MAX_HEALTH, player_upgrades, current_money
                    ):
                        current_money -= SHOP_ITEMS[ShopItemType.MAX_HEALTH]["cost"]
                    shop_timer = 0
                elif keys[pygame.K_2]:
                    if _buy_item(
                        ShopItemType.MAX_SPEED, player_upgrades, current_money
                    ):
                        current_money -= SHOP_ITEMS[ShopItemType.MAX_SPEED]["cost"]
                    shop_timer = 0
                elif keys[pygame.K_3]:
                    if _buy_item(ShopItemType.ARMOR, player_upgrades, current_money):
                        current_money -= SHOP_ITEMS[ShopItemType.ARMOR]["cost"]
                    shop_timer = 0
                elif keys[pygame.K_4]:
                    if _buy_item(
                        ShopItemType.WEAPON_RAPID, player_upgrades, current_money
                    ):
                        current_money -= SHOP_ITEMS[ShopItemType.WEAPON_RAPID]["cost"]
                    shop_timer = 0
                elif keys[pygame.K_5]:
                    if _buy_item(
                        ShopItemType.WEAPON_SPREAD, player_upgrades, current_money
                    ):
                        current_money -= SHOP_ITEMS[ShopItemType.WEAPON_SPREAD]["cost"]
                    shop_timer = 0
                elif keys[pygame.K_6]:
                    if _buy_item(ShopItemType.REVIVE, player_upgrades, current_money):
                        current_money -= SHOP_ITEMS[ShopItemType.REVIVE]["cost"]
                    shop_timer = 0
                elif keys[pygame.K_RETURN]:
                    engine = GameEngine(
                        round_num=engine.round,
                        existing_genome_pools=saved_genome_pools,
                        player_upgrades=player_upgrades,
                    )
                    engine.money = current_money
                    engine.mouse_locked = True
                    engine.total_kills += engine.kill_count
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    shop_timer = 0
        elif engine.phase == GamePhase.DEAD:
            pass

        if running and engine.phase not in (GamePhase.PLAYING, GamePhase.SHOP):
            _save_game(
                current_slot,
                player_upgrades,
                current_money,
                total_kills,
                highest_round,
                all_slots,
            )

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
            engine.kill_count,
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
                surface, font_large, font_med, font_small, engine, current_money
            )

        screen.blit(
            pygame.transform.scale(surface, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0)
        )
        pygame.display.flip()

    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)
    pygame.quit()


def _draw_menu(screen, font_large, font_med, font_small, all_slots, selected_slot):
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

    slots_label = font_small.render("Select Save Slot (1-3):", True, (200, 200, 200))
    screen.blit(
        slots_label, (screen.get_width() // 2 - 100, screen.get_height() // 4 + 60)
    )

    for i in range(3):
        slot = all_slots[i]
        if slot is None:
            slot = SLOT_DEFAULTS.copy()
        y_pos = screen.get_height() // 4 + 90 + i * 70
        color = (0, 255, 100) if i == selected_slot else (120, 120, 120)
        highlight = (0, 80, 40) if i == selected_slot else (0, 0, 0)
        pygame.draw.rect(
            screen, highlight, (screen.get_width() // 2 - 180, y_pos - 5, 360, 60)
        )
        pygame.draw.rect(
            screen, color, (screen.get_width() // 2 - 180, y_pos - 5, 360, 60), 2
        )

        slot_text = f"Slot {i + 1}"
        has_data = all_slots[i] is not None
        if has_data:
            slot_text += f" | Round: {slot.get('highest_round', 0)} | ${slot.get('current_money', 0)}"
        else:
            slot_text += " (Empty)"
        text = font_small.render(
            slot_text, True, (255, 255, 255) if i == selected_slot else (180, 180, 180)
        )
        text_rect = text.get_rect(center=(screen.get_width() // 2, y_pos + 10))
        screen.blit(text, text_rect)

        if has_data:
            kills_text = font_small.render(
                f"Kills: {slot.get('total_kills', 0)}", True, (150, 150, 150)
            )
            kills_rect = kills_text.get_rect(
                center=(screen.get_width() // 2, y_pos + 30)
            )
            screen.blit(kills_text, kills_rect)

    prompt = font_small.render(
        "Press ENTER to start | 1/2/3 to select slot", True, (255, 255, 255)
    )
    prompt_rect = prompt.get_rect(
        center=(screen.get_width() // 2, screen.get_height() - 80)
    )
    screen.blit(prompt, prompt_rect)

    controls = [
        "WASD - Move / Strafe",
        "Mouse - Look",
        "Left Click / Space - Shoot",
        "P - Pause",
        "ESC - Menu",
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

    info = font_med.render(
        f"Kills: {engine.kill_count}  Score: {engine.score}", True, (255, 170, 0)
    )
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
        f"Round: {engine.round}  Kills: {engine.kill_count}  Score: {engine.score}",
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


def _draw_shop_overlay(surface, font_large, font_med, font_small, engine, money):
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    surface.blit(overlay, (0, 0))

    title = font_large.render(f"SHOP - ROUND {engine.round}", True, (255, 68, 0))
    title_rect = title.get_rect(center=(surface.get_width() // 2, 50))
    surface.blit(title, title_rect)

    money_text = font_med.render(f"Money: ${money}", True, (255, 221, 68))
    money_rect = money_text.get_rect(center=(surface.get_width() // 2, 90))
    surface.blit(money_text, money_rect)

    shop_items = [
        ("1", "Max Health +25", 50),
        ("2", "Speed +0.5", 75),
        ("3", "Armor +1 (blocks 10%)", 100),
        ("4", "Rapid Fire", 200),
        ("5", "Shotgun", 350),
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


SHOP_ITEMS = {
    ShopItemType.MAX_HEALTH: {"name": "Max Health +25", "cost": 50, "key": "1"},
    ShopItemType.MAX_SPEED: {"name": "Speed +0.5", "cost": 75, "key": "2"},
    ShopItemType.ARMOR: {"name": "Armor +1 (blocks 10%)", "cost": 100, "key": "3"},
    ShopItemType.WEAPON_RAPID: {"name": "Rapid Fire", "cost": 200, "key": "4"},
    ShopItemType.WEAPON_SPREAD: {"name": "Shotgun", "cost": 350, "key": "5"},
    ShopItemType.REVIVE: {"name": "Revive (100 HP)", "cost": 500, "key": "6"},
}


def _buy_item(item_type, upgrades, money):
    item = SHOP_ITEMS[item_type]
    if money >= item["cost"]:
        if item_type == ShopItemType.MAX_HEALTH:
            if upgrades.get("maxHealth", 100) >= 300:
                return False
            upgrades["maxHealth"] = upgrades.get("maxHealth", 100) + 25
        elif item_type == ShopItemType.MAX_SPEED:
            if upgrades.get("maxSpeed", 3.5) >= 6.0:
                return False
            upgrades["maxSpeed"] = upgrades.get("maxSpeed", 3.5) + 0.5
        elif item_type == ShopItemType.ARMOR:
            if upgrades.get("armor", 0) >= 5:
                return False
            upgrades["armor"] = upgrades.get("armor", 0) + 1
        elif item_type == ShopItemType.WEAPON_RAPID:
            if upgrades.get("weapon") == "rapid":
                return False
            upgrades["weapon"] = "rapid"
            upgrades["weaponLevel"] = upgrades.get("weaponLevel", 1) + 1
        elif item_type == ShopItemType.WEAPON_SPREAD:
            if upgrades.get("weapon") == "spread":
                return False
            upgrades["weapon"] = "spread"
            upgrades["weaponLevel"] = upgrades.get("weaponLevel", 1) + 1
        elif item_type == ShopItemType.REVIVE:
            if upgrades.get("revive", False):
                return False
            upgrades["revive"] = True
        return True
    return False


if __name__ == "__main__":
    main()
