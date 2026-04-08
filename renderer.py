import math
import pygame
import pygame.surfarray as surfarray
import numpy as np
from game_types import (
    Player,
    Enemy,
    GameMap,
    Bullet,
    Particle,
    EnemyState,
    EnemyClass,
    ENEMY_CLASS_CONFIG,
    Pickup,
    PickupType,
)

FOV = math.pi / 3
HALF_FOV = FOV / 2

WALL_COLORS = {
    1: ((139, 0, 0), (90, 0, 0)),
    2: ((74, 74, 106), (42, 42, 74)),
    3: ((107, 66, 38), (61, 32, 16)),
    4: ((45, 90, 39), (26, 51, 21)),
    5: ((107, 107, 42), (61, 61, 16)),
    9: ((136, 136, 136), (85, 85, 85)),
}

_ceiling_cache = {}
_floor_cache = {}
_font_cache = {}


def _get_font(size):
    if size not in _font_cache:
        _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


def _get_gradient_surf(w, h, top_color, bottom_color):
    key = (w, h, top_color, bottom_color)
    if key in _ceiling_cache:
        return _ceiling_cache[key]
    surf = pygame.Surface((w, h))
    arr = pygame.surfarray.pixels3d(surf)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        arr[:, y] = (r, g, b)
    del arr
    _ceiling_cache[key] = surf
    return surf


def render_frame(
    surface, game_map, player, enemies, bullets, particles, pickups, flash_alpha
):
    width, height = surface.get_size()

    ceil_surf = _get_gradient_surf(width, height // 2, (5, 5, 8), (26, 10, 10))
    surface.blit(ceil_surf, (0, 0))

    floor_h = height - height // 2
    floor_surf = _get_gradient_surf(width, floor_h, (26, 10, 0), (5, 5, 2))
    surface.blit(floor_surf, (0, height // 2))

    wall_pixels = np.zeros((width, height, 3), dtype=np.uint8)
    z_buffer = np.zeros(width, dtype=np.float64)

    for x in range(width):
        ray_angle = player.angle - HALF_FOV + (x / width) * FOV
        ray = _cast_ray(game_map, player.x, player.y, ray_angle)

        corrected_dist = ray["distance"] * math.cos(ray_angle - player.angle)
        if corrected_dist < 0.01:
            corrected_dist = 0.01
        z_buffer[x] = corrected_dist

        wall_height = min(height * 2, height / corrected_dist)
        wall_top = (height - wall_height) / 2

        colors = WALL_COLORS.get(ray["wallType"], WALL_COLORS[1])
        base_color = np.array(
            colors[1] if ray["side"] == 1 else colors[0], dtype=np.float64
        )

        fog = min(1.0, corrected_dist / 18.0)
        fog_factor = 1.0 - fog * 0.8

        texture_shift = ray["wallType"] * 17
        map_x = ray["mapX"]
        map_y = ray["mapY"]

        y_start = max(0, int(wall_top))
        y_end = min(height, int(wall_top + wall_height))

        if y_end > y_start:
            tex_coords = np.linspace(0, 1, y_end - y_start)
            scanline = (
                np.sin(tex_coords * 20 + texture_shift + map_x * 3.7 + map_y * 2.3)
                * 0.05
            )
            brightness = (1.0 - fog * 0.6 + scanline) * fog_factor
            brightness = np.clip(brightness, 0, 1)
            wall_pixels[x, y_start:y_end] = (
                base_color * brightness[:, np.newaxis]
            ).astype(np.uint8)

    wall_surf = pygame.surfarray.make_surface(wall_pixels)
    surface.blit(wall_surf, (0, 0))

    _render_sprites(surface, width, height, player, enemies, bullets, pickups, z_buffer)
    _render_particles(surface, width, height, player, particles, z_buffer)

    if flash_alpha > 0:
        flash_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        flash_surf.fill((255, 0, 0, int(flash_alpha * 255)))
        surface.blit(flash_surf, (0, 0))


def _cast_ray(game_map, start_x, start_y, angle):
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    map_x = int(start_x)
    map_y = int(start_y)
    delta_dist_x = abs(1 / (cos_a if abs(cos_a) > 1e-5 else 0.00001))
    delta_dist_y = abs(1 / (sin_a if abs(sin_a) > 1e-5 else 0.00001))
    if cos_a < 0:
        step_x = -1
        side_dist_x = (start_x - map_x) * delta_dist_x
    else:
        step_x = 1
        side_dist_x = (map_x + 1 - start_x) * delta_dist_x
    if sin_a < 0:
        step_y = -1
        side_dist_y = (start_y - map_y) * delta_dist_y
    else:
        step_y = 1
        side_dist_y = (map_y + 1 - start_y) * delta_dist_y
    side = 0
    wall_type = 0
    hit = False
    max_steps = 128
    while not hit and max_steps > 0:
        max_steps -= 1
        if side_dist_x < side_dist_y:
            side_dist_x += delta_dist_x
            map_x += step_x
            side = 0
        else:
            side_dist_y += delta_dist_y
            map_y += step_y
            side = 1
        if (
            map_x < 0
            or map_x >= game_map.width
            or map_y < 0
            or map_y >= game_map.height
        ):
            wall_type = 1
            hit = True
            break
        if game_map.cells[map_y][map_x] > 0:
            wall_type = game_map.cells[map_y][map_x]
            hit = True
    if side == 0:
        distance = (map_x - start_x + (1 - step_x) / 2) / cos_a
    else:
        distance = (map_y - start_y + (1 - step_y) / 2) / sin_a
    return {
        "distance": abs(distance),
        "wallType": wall_type,
        "side": side,
        "mapX": map_x,
        "mapY": map_y,
    }


def _render_sprites(
    surface, width, height, player, enemies, bullets, pickups, z_buffer
):
    sprites = []
    for e in enemies:
        if e.state == EnemyState.DEAD:
            continue
        dx = e.x - player.x
        dy = e.y - player.y
        dist = math.sqrt(dx * dx + dy * dy)
        sprites.append((e, dist, "enemy"))

    for b in bullets:
        dx = b.x - player.x
        dy = b.y - player.y
        dist = math.sqrt(dx * dx + dy * dy)
        sprites.append((b, dist, "bullet"))

    for p in pickups:
        if not p.active:
            continue
        dx = p.x - player.x
        dy = p.y - player.y
        dist = math.sqrt(dx * dx + dy * dy)
        sprites.append((p, dist, "pickup"))

    sprites.sort(key=lambda s: s[1], reverse=True)

    for ref, dist, stype in sprites:
        if dist < 0.3:
            continue

        dx = ref.x - player.x
        dy = ref.y - player.y

        sprite_angle = math.atan2(dy, dx) - player.angle
        sa = sprite_angle
        while sa > math.pi:
            sa -= 2 * math.pi
        while sa < -math.pi:
            sa += 2 * math.pi

        if abs(sa) > FOV:
            continue

        corrected_dist = dist * math.cos(sa)
        if corrected_dist < 0.01:
            continue
        sprite_height = min(height * 2, height / corrected_dist)
        sprite_top = (height - sprite_height) / 2
        screen_x = ((sa + HALF_FOV) / FOV) * width
        sprite_width = sprite_height
        start_x = int(screen_x - sprite_width / 2)

        if stype == "enemy":
            _draw_enemy_sprite(
                surface,
                ref,
                start_x,
                sprite_top,
                sprite_width,
                sprite_height,
                corrected_dist,
                z_buffer,
                width,
            )
        elif stype == "pickup":
            _draw_pickup_sprite(
                surface,
                ref,
                start_x,
                sprite_top,
                sprite_width,
                sprite_height,
                corrected_dist,
                z_buffer,
                width,
            )
        else:
            bx = int(screen_x)
            if 0 < bx < width and corrected_dist < z_buffer[bx]:
                size = max(2, int(height / corrected_dist * 0.015))
                if ref.fromPlayer:
                    trail_len = 0.4
                    trail_x = ref.x - math.cos(ref.angle) * trail_len
                    trail_y = ref.y - math.sin(ref.angle) * trail_len
                    trail_dx = trail_x - player.x
                    trail_dy = trail_y - player.y
                    trail_dist = math.sqrt(trail_dx * trail_dx + trail_dy * trail_dy)
                    trail_angle = math.atan2(trail_dy, trail_dx) - player.angle
                    tsa = trail_angle
                    while tsa > math.pi:
                        tsa -= 2 * math.pi
                    while tsa < -math.pi:
                        tsa += 2 * math.pi
                    if abs(tsa) < FOV:
                        trail_corrected = trail_dist * math.cos(tsa)
                        if trail_corrected > 0.01:
                            trail_sx = ((tsa + HALF_FOV) / FOV) * width
                            trail_sy = height / 2
                            pygame.draw.line(
                                surface,
                                (255, 200, 50, 150),
                                (int(trail_sx), trail_sy),
                                (bx, height // 2),
                                2,
                            )
                    pygame.draw.circle(
                        surface, (255, 255, 100), (bx, height // 2), size
                    )
                else:
                    pygame.draw.circle(surface, (255, 80, 50), (bx, height // 2), size)


def _draw_enemy_sprite(
    surface, enemy, start_x, top, w, h, dist, z_buffer, canvas_width
):
    fog = min(1, dist / 18)
    alpha_val = int((1 - fog * 0.5) * 255)

    config = ENEMY_CLASS_CONFIG.get(
        enemy.enemyClass, ENEMY_CLASS_CONFIG[EnemyClass.TANK]
    )
    body_color = config["minimapColor"]

    if enemy.enemyClass == EnemyClass.TANK:
        head_color = (200, 140, 120)
        shoulder_color = (
            int(body_color[0] * 0.7),
            int(body_color[1] * 0.7),
            int(body_color[2] * 0.7),
        )
        leg_color = (
            int(body_color[0] * 0.55),
            int(body_color[1] * 0.55),
            int(body_color[2] * 0.55),
        )
        head_tx_l, head_tx_r = 0.28, 0.72
        shoulder_tx_l, shoulder_tx_r = 0.10, 0.90
        torso_tx_l, torso_tx_r = 0.18, 0.82
        leg_tx_ranges = [(0.22, 0.42), (0.58, 0.78)]
        arm_tx_ranges = [(0.04, 0.20), (0.80, 0.96)]
        gun_tx_l, gun_tx_r = 0.38, 0.62
        gun_hl_tx_l, gun_hl_tx_r = 0.44, 0.56
        has_gun = True
        y_head_top = int(h * 0.04)
        y_head_bot = int(h * 0.22)
        y_shoulder_top = int(h * 0.20)
        y_shoulder_bot = int(h * 0.32)
        y_torso_top = int(h * 0.30)
        y_torso_bot = int(h * 0.65)
        y_leg_top = int(h * 0.62)
        y_leg_bot = int(h)
        y_arm_top = int(h * 0.30)
        y_arm_bot = int(h * 0.60)
        y_gun_center = int(h * 0.45)
        y_gun_half = int(h * 0.05)
        eye_tx_ranges = [(0.33, 0.42), (0.58, 0.67)]
        y_eye_top = int(h * 0.10)
        y_eye_bot = int(h * 0.17)
    elif enemy.enemyClass == EnemyClass.SCOUT:
        head_color = (230, 200, 140)
        shoulder_color = (
            int(body_color[0] * 0.85),
            int(body_color[1] * 0.85),
            int(body_color[2] * 0.85),
        )
        leg_color = (
            int(body_color[0] * 0.6),
            int(body_color[1] * 0.6),
            int(body_color[2] * 0.6),
        )
        head_tx_l, head_tx_r = 0.35, 0.65
        shoulder_tx_l, shoulder_tx_r = 0.25, 0.75
        torso_tx_l, torso_tx_r = 0.30, 0.70
        leg_tx_ranges = [(0.33, 0.46), (0.54, 0.67)]
        arm_tx_ranges = [(0.18, 0.30), (0.70, 0.82)]
        gun_tx_l, gun_tx_r = 0.43, 0.55
        gun_hl_tx_l, gun_hl_tx_r = 0.47, 0.51
        has_gun = True
        y_head_top = int(h * 0.10)
        y_head_bot = int(h * 0.28)
        y_shoulder_top = int(h * 0.28)
        y_shoulder_bot = int(h * 0.36)
        y_torso_top = int(h * 0.34)
        y_torso_bot = int(h * 0.60)
        y_leg_top = int(h * 0.58)
        y_leg_bot = int(h)
        y_arm_top = int(h * 0.34)
        y_arm_bot = int(h * 0.56)
        y_gun_center = int(h * 0.45)
        y_gun_half = int(h * 0.03)
        eye_tx_ranges = [(0.38, 0.44), (0.56, 0.62)]
        y_eye_top = int(h * 0.15)
        y_eye_bot = int(h * 0.21)
    else:
        head_color = (220, 160, 140)
        shoulder_color = (
            int(body_color[0] * 0.85),
            int(body_color[1] * 0.85),
            int(body_color[2] * 0.85),
        )
        leg_color = (
            int(body_color[0] * 0.65),
            int(body_color[1] * 0.65),
            int(body_color[2] * 0.65),
        )
        head_tx_l, head_tx_r = 0.32, 0.68
        shoulder_tx_l, shoulder_tx_r = 0.20, 0.80
        torso_tx_l, torso_tx_r = 0.25, 0.75
        leg_tx_ranges = [(0.30, 0.48), (0.52, 0.70)]
        arm_tx_ranges = [(0.12, 0.26), (0.74, 0.88)]
        gun_tx_l, gun_tx_r = 0.42, 0.58
        gun_hl_tx_l, gun_hl_tx_r = 0.47, 0.53
        has_gun = True
        y_head_top = int(h * 0.08)
        y_head_bot = int(h * 0.28)
        y_shoulder_top = int(h * 0.27)
        y_shoulder_bot = int(h * 0.35)
        y_torso_top = int(h * 0.33)
        y_torso_bot = int(h * 0.62)
        y_leg_top = int(h * 0.60)
        y_leg_bot = int(h)
        y_arm_top = int(h * 0.32)
        y_arm_bot = int(h * 0.58)
        y_gun_center = int(h * 0.45)
        y_gun_half = int(h * 0.04)
        eye_tx_ranges = [(0.37, 0.44), (0.56, 0.63)]
        y_eye_top = int(h * 0.15)
        y_eye_bot = int(h * 0.21)

    gun_color = (51, 51, 51)
    gun_highlight = (85, 85, 85)
    hp_green = (0, 255, 68)
    hp_red = (68, 0, 0)

    start_col = max(0, start_x)
    end_col = min(canvas_width, start_x + int(w))
    if end_col <= start_col:
        return

    visible = False
    for x in range(start_col, end_col):
        if dist < z_buffer[x]:
            visible = True
            break
    if not visible:
        return

    sprite_surf = pygame.Surface((end_col - start_col, int(h) + 5), pygame.SRCALPHA)

    hp_ratio = enemy.health / enemy.maxHealth if enemy.maxHealth > 0 else 0
    bar_w = int(w * 0.8)
    bar_x_start = int(w * 0.1)
    y_hp = max(0, int(top) - 4)
    y_mouth_top = int(h * 0.23)
    y_mouth_bot = int(h * 0.27)

    for x in range(start_col, end_col):
        if dist >= z_buffer[x]:
            continue
        tx = (x - start_x) / w if w > 0 else 0
        sx = x - start_col

        if head_tx_l < tx < head_tx_r:
            pygame.draw.line(
                sprite_surf,
                (*head_color, alpha_val),
                (sx, y_head_top),
                (sx, y_head_bot),
            )

        if enemy.canSeePlayer:
            for el, er in eye_tx_ranges:
                if el < tx < er:
                    pygame.draw.line(
                        sprite_surf,
                        (255, 50, 0, alpha_val),
                        (sx, y_eye_top),
                        (sx, y_eye_bot),
                    )

        if enemy.enemyClass != EnemyClass.SCOUT:
            if 0.38 < tx < 0.62:
                pygame.draw.line(
                    sprite_surf,
                    (120, 30, 20, alpha_val),
                    (sx, y_mouth_top),
                    (sx, y_mouth_bot),
                )

        if shoulder_tx_l < tx < shoulder_tx_r:
            pygame.draw.line(
                sprite_surf,
                (*shoulder_color, alpha_val),
                (sx, y_shoulder_top),
                (sx, y_shoulder_bot),
            )

        if torso_tx_l < tx < torso_tx_r:
            pygame.draw.line(
                sprite_surf,
                (*body_color, alpha_val),
                (sx, y_torso_top),
                (sx, y_torso_bot),
            )

        if 0.28 < tx < 0.72:
            pygame.draw.line(
                sprite_surf,
                (60, 20, 15, alpha_val),
                (sx, int(h * 0.58)),
                (sx, int(h * 0.62)),
            )

        for ll, lr in leg_tx_ranges:
            if ll < tx < lr:
                pygame.draw.line(
                    sprite_surf,
                    (*leg_color, alpha_val),
                    (sx, y_leg_top),
                    (sx, y_leg_bot),
                )

        for al, ar in arm_tx_ranges:
            if al < tx < ar:
                pygame.draw.line(
                    sprite_surf,
                    (*body_color, alpha_val),
                    (sx, y_arm_top),
                    (sx, y_arm_bot),
                )

        if has_gun:
            if gun_tx_l < tx < gun_tx_r:
                pygame.draw.line(
                    sprite_surf,
                    (*gun_color, alpha_val),
                    (sx, y_gun_center - y_gun_half),
                    (sx, y_gun_center + y_gun_half),
                )
                if gun_hl_tx_l < tx < gun_hl_tx_r:
                    pygame.draw.line(
                        sprite_surf,
                        (*gun_highlight, alpha_val),
                        (sx, y_gun_center - y_gun_half),
                        (sx, y_gun_center + y_gun_half),
                    )

        if 0.1 < tx < 0.9:
            rel_x = (x - start_x - bar_x_start) / bar_w if bar_w > 0 else 0
            if 0 < rel_x < 1:
                c = hp_green if rel_x < hp_ratio else hp_red
                pygame.draw.line(
                    sprite_surf, (*c, alpha_val), (sx, y_hp), (sx, y_hp + 3)
                )

    surface.blit(sprite_surf, (start_col, top))


def _draw_pickup_sprite(
    surface, pickup, start_x, top, w, h, dist, z_buffer, canvas_width
):
    fog = min(1, dist / 18)
    alpha_val = int((1 - fog * 0.5) * 255)

    start_col = max(0, start_x)
    end_col = min(canvas_width, start_x + int(w))
    if end_col <= start_col:
        return

    visible = False
    for x in range(start_col, end_col):
        if dist < z_buffer[x]:
            visible = True
            break
    if not visible:
        return

    sprite_surf = pygame.Surface((end_col - start_col, int(h) + 5), pygame.SRCALPHA)

    surf_w = end_col - start_col
    surf_h = int(h) + 5
    center_x = surf_w / 2

    if pickup.pickupType == PickupType.HEALTH:
        white = (255, 255, 255, alpha_val)
        red = (255, 0, 0, alpha_val)
        box_left = int(surf_w * 0.2)
        box_right = int(surf_w * 0.8)
        box_top = int(surf_h * 0.2)
        box_bottom = int(surf_h * 0.8)
        pygame.draw.rect(
            sprite_surf,
            white,
            (box_left, box_top, box_right - box_left, box_bottom - box_top),
        )
        cross_w = max(1, (box_right - box_left) // 5)
        pygame.draw.rect(
            sprite_surf,
            red,
            (center_x - cross_w // 2, box_top, cross_w, box_bottom - box_top),
        )
        pygame.draw.rect(
            sprite_surf,
            red,
            (
                box_left,
                (box_top + box_bottom) // 2 - cross_w // 2,
                box_right - box_left,
                cross_w,
            ),
        )
    else:
        ammo_color = (230, 120, 0, alpha_val)
        inner_color = (255, 180, 50, alpha_val)
        box_left = int(surf_w * 0.25)
        box_right = int(surf_w * 0.75)
        box_top = int(surf_h * 0.25)
        box_bottom = int(surf_h * 0.75)
        pygame.draw.rect(
            sprite_surf,
            ammo_color,
            (box_left, box_top, box_right - box_left, box_bottom - box_top),
        )
        inner_pad = 3
        pygame.draw.rect(
            sprite_surf,
            inner_color,
            (
                box_left + inner_pad,
                box_top + inner_pad,
                box_right - box_left - inner_pad * 2,
                box_bottom - box_top - inner_pad * 2,
            ),
        )

    surface.blit(sprite_surf, (start_col, top))


def _render_particles(surface, width, height, player, particles, z_buffer):
    if not particles:
        return
    for p in particles:
        dx = p.x - player.x
        dy = p.y - player.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.1:
            continue

        angle = math.atan2(dy, dx) - player.angle
        sa = angle
        while sa > math.pi:
            sa -= 2 * math.pi
        while sa < -math.pi:
            sa += 2 * math.pi
        if abs(sa) > FOV * 0.8:
            continue

        corrected_dist = dist * math.cos(sa)
        screen_x = ((sa + HALF_FOV) / FOV) * width
        bx = int(screen_x)
        if bx < 0 or bx >= width:
            continue
        if corrected_dist >= z_buffer[bx]:
            continue

        size = max(1, int((p.size / corrected_dist) * height * 0.1))
        life_ratio = p.life / p.maxLife if p.maxLife > 0 else 0
        alpha = int(life_ratio * 0.8 * 255)
        color = (
            p.color
            if isinstance(p.color, tuple) and len(p.color) == 3
            else (255, 255, 255)
        )
        pygame.draw.circle(surface, (*color, alpha), (bx, height // 2), size)


def render_hud(
    surface,
    player,
    round_num,
    score,
    is_shooting,
    shoot_flash,
    is_punching=False,
    money=0,
):
    width, height = surface.get_size()

    hud_rect = pygame.Surface((width, 80), pygame.SRCALPHA)
    hud_rect.fill((0, 0, 0, 191))
    surface.blit(hud_rect, (0, height - 80))

    hp_ratio = player.health / player.maxHealth if player.maxHealth > 0 else 0
    if hp_ratio > 0.6:
        hp_color = (0, 204, 68)
    elif hp_ratio > 0.3:
        hp_color = (255, 170, 0)
    else:
        hp_color = (255, 34, 0)

    pygame.draw.rect(surface, (34, 34, 34), (20, height - 60, 160, 18))
    pygame.draw.rect(surface, hp_color, (20, height - 60, int(160 * hp_ratio), 18))
    pygame.draw.rect(surface, (85, 85, 85), (20, height - 60, 160, 18), 1)

    font = _get_font(24)
    hp_text = font.render(f"HP: {player.health}", True, (255, 255, 255))
    surface.blit(hp_text, (28, height - 46))

    pygame.draw.rect(surface, (34, 34, 34), (20, height - 36, 160, 18))
    ammo_ratio = player.ammo / player.maxAmmo if player.maxAmmo > 0 else 0
    pygame.draw.rect(
        surface, (255, 170, 0), (20, height - 36, int(160 * ammo_ratio), 18)
    )
    pygame.draw.rect(surface, (85, 85, 85), (20, height - 36, 160, 18), 1)

    ammo_text = font.render(f"AMMO: {player.ammo}", True, (255, 255, 255))
    surface.blit(ammo_text, (28, height - 22))

    if player.armor > 0:
        armor_text = font.render(f"ARMOR: {player.armor}", True, (100, 150, 255))
        surface.blit(armor_text, (190, height - 46))

    weapon_name = (
        player.weaponType.upper() if player.weaponType != "default" else "PISTOL"
    )
    weapon_text = font.render(f"WEAPON: {weapon_name}", True, (255, 136, 0))
    surface.blit(weapon_text, (190, height - 22))

    font_bold = _get_font(28)
    round_text = font_bold.render(f"ROUND: {round_num}", True, (255, 68, 0))
    surface.blit(round_text, (width // 2 - 60, height - 55))

    score_text = font_bold.render(f"SCORE: {score}", True, (255, 170, 0))
    surface.blit(score_text, (width // 2 - 60, height - 35))

    if money > 0:
        money_text = font_bold.render(f"${money}", True, (255, 221, 68))
        surface.blit(money_text, (width - 100, height - 55))

    cx = width // 2
    cy = height // 2
    cross_size = 10 + (5 if shoot_flash > 0 else 0)
    cross_color = (255, 68, 0) if shoot_flash > 0 else (255, 255, 255)
    pygame.draw.line(
        surface, cross_color, (cx - cross_size, cy), (cx + cross_size, cy), 2
    )
    pygame.draw.line(
        surface, cross_color, (cx, cy - cross_size), (cx, cy + cross_size), 2
    )

    _draw_weapon(surface, width, height, is_shooting, shoot_flash, is_punching)


def _draw_weapon(surface, width, height, is_shooting, shoot_flash, is_punching=False):
    wx = width // 2
    wy = height - 10
    bob = math.sin(pygame.time.get_ticks() * 0.003) * 3
    kickback = -15 if is_shooting else 0

    if is_punching:
        punch_surf = pygame.Surface((80, 100), pygame.SRCALPHA)
        pygame.draw.ellipse(punch_surf, (210, 160, 130), (10, 20, 50, 40))
        pygame.draw.ellipse(punch_surf, (180, 130, 100), (15, 25, 40, 30))
        knuckle_color = (200, 150, 120)
        for i in range(4):
            pygame.draw.circle(punch_surf, knuckle_color, (20 + i * 10, 22), 4)
        forearm_color = (190, 140, 110)
        pygame.draw.rect(punch_surf, forearm_color, (25, 55, 20, 35))
        punch_bob = bob + kickback * 0.5
        surface.blit(punch_surf, (wx - 10, wy - 90 + punch_bob))
    else:
        gun_surf = pygame.Surface((60, 120), pygame.SRCALPHA)
        pygame.draw.rect(gun_surf, (51, 51, 51), (15, 30, 30, 60))
        pygame.draw.rect(gun_surf, (34, 34, 34), (22, 10, 16, 25))
        pygame.draw.rect(gun_surf, (17, 17, 17), (26, 0, 8, 15))
        pygame.draw.rect(gun_surf, (74, 48, 32), (18, 60, 24, 40))

        if shoot_flash > 0:
            alpha = int(shoot_flash * 255)
            pygame.draw.circle(gun_surf, (255, 238, 68, alpha), (30, 0), 12)
            pygame.draw.circle(gun_surf, (255, 255, 255, alpha), (30, 0), 5)

        surface.blit(gun_surf, (wx - 30, wy - 110 + bob + kickback))


def draw_minimap(surface, width, height, game_map, player, enemies):
    map_size = 150
    cell_size = map_size / game_map.width
    mx = width - map_size - 10
    my = 10

    bg = pygame.Surface((map_size, map_size), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 178))
    surface.blit(bg, (mx, my))

    mm = pygame.Surface((map_size, map_size), pygame.SRCALPHA)
    for y in range(game_map.height):
        for x in range(game_map.width):
            cell = game_map.cells[y][x]
            if cell > 0:
                color = (136, 136, 136) if cell == 9 else (85, 85, 85)
                cs = max(1, cell_size)
                pygame.draw.rect(mm, color, (x * cell_size, y * cell_size, cs, cs))

    px = player.x * cell_size
    py = player.y * cell_size
    pygame.draw.circle(mm, (0, 255, 136), (int(px), int(py)), 3)

    dir_x = px + math.cos(player.angle) * 3 * cell_size
    dir_y = py + math.sin(player.angle) * 3 * cell_size
    pygame.draw.line(mm, (0, 255, 136), (px, py), (dir_x, dir_y), 1)

    for e in enemies:
        if e.state == EnemyState.DEAD:
            continue
        color = ENEMY_CLASS_CONFIG.get(
            e.enemyClass, ENEMY_CLASS_CONFIG[EnemyClass.TANK]
        )["minimapColor"]
        ex = e.x * cell_size
        ey = e.y * cell_size
        pygame.draw.circle(mm, color, (int(ex), int(ey)), 2)

    pygame.draw.rect(mm, (68, 68, 68), (0, 0, map_size, map_size), 1)
    surface.blit(mm, (mx, my))
