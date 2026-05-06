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

# i hate color math. these are probably wrong.
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


def _get_font(sz):
    if sz not in _font_cache:
        _font_cache[sz] = pygame.font.Font(None, sz)
    return _font_cache[sz]


def _get_gradient_surf(w, h, c1, c2):
    k = (w, h, c1, c2)
    if k in _ceiling_cache:
        return _ceiling_cache[k]
    
    sf = pygame.Surface((w, h))
    px = pygame.surfarray.pixels3d(sf)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        px[:, y] = (r, g, b)
    del px
    _ceiling_cache[k] = sf
    return sf


def render_frame(
    surface, game_map, player, enemies, bullets, particles, pickups, flash_a, low_q=False
):
    width, height = surface.get_size()

    # background gradients. i hope this doesn't lag.
    c_sf = _get_gradient_surf(width, height // 2, (5, 5, 12), (32, 12, 12))
    surface.blit(c_sf, (0, 0))

    f_h = height - height // 2
    f_sf = _get_gradient_surf(width, f_h, (32, 12, 0), (8, 8, 4))
    surface.blit(f_sf, (0, height // 2))

    w_px = np.zeros((width, height, 3), dtype=np.uint8)
    z_buf = np.full(width, 1000.0, dtype=np.float64)

    for x in range(width):
        r_angle = player.angle - HALF_FOV + (x / width) * FOV
        ray = _cast_ray(game_map, player.x, player.y, r_angle)

        c_dist = ray["distance"] * math.cos(r_angle - player.angle)
        if c_dist < 0.05:
            c_dist = 0.05
        z_buf[x] = c_dist

        w_h = min(height * 2.5, height / c_dist)
        w_t = (height - w_h) / 2

        cls = WALL_COLORS.get(ray["wallType"], WALL_COLORS[1])
        b_col = np.array(cls[1] if ray["side"] == 1 else cls[0], dtype=np.float64)

        fg = min(1.0, c_dist / 20.0)
        fg_f = 1.0 - fg * 0.75

        t_shift = ray["wallType"] * 17
        mx, my = ray["mapX"], ray["mapY"]

        ys = max(0, int(w_t))
        ye = min(height, int(w_t + w_h))

        if ye > ys:
            if not low_q:
                tc = np.linspace(0, 1, ye - ys)
                sl = np.sin(tc * 25 + t_shift + mx * 4.1 + my * 2.7) * 0.06
                br = (1.0 - fg * 0.5 + sl) * fg_f
            else:
                br = np.full(ye - ys, (1.0 - fg * 0.5) * fg_f)
            
            br = np.clip(br, 0, 1)
            w_px[x, ys:ye] = (b_col * br[:, np.newaxis]).astype(np.uint8)

    w_sf = pygame.surfarray.make_surface(w_px)
    surface.blit(w_sf, (0, 0))

    _render_sprites(surface, width, height, player, enemies, bullets, pickups, z_buf)
    _render_particles(surface, width, height, player, particles, z_buf)

    if flash_a > 0:
        fl_sf = pygame.Surface((width, height), pygame.SRCALPHA)
        fl_sf.fill((255, 0, 0, int(min(1, flash_a) * 200)))
        surface.blit(fl_sf, (0, 0))


def _cast_ray(game_map, sx, sy, angle):
    ca, sa = math.cos(angle), math.sin(angle)
    mx, my = int(sx), int(sy)
    
    dx = abs(1 / (ca if abs(ca) > 1e-5 else 0.00001))
    dy = abs(1 / (sa if abs(sa) > 1e-5 else 0.00001))
    
    if ca < 0:
        st_x, sd_x = -1, (sx - mx) * dx
    else:
        st_x, sd_x = 1, (mx + 1 - sx) * dx
    
    if sa < 0:
        st_y, sd_y = -1, (sy - my) * dy
    else:
        st_y, sd_y = 1, (my + 1 - sy) * dy
    
    side, wt, hit = 0, 0, False
    steps = 128
    while not hit and steps > 0:
        steps -= 1
        if sd_x < sd_y:
            sd_x += dx
            mx += st_x
            side = 0
        else:
            sd_y += dy
            my += st_y
            side = 1
        
        if mx < 0 or mx >= game_map.width or my < 0 or my >= game_map.height:
            wt, hit = 1, True
            break
        if game_map.cells[my][mx] > 0:
            wt, hit = game_map.cells[my][mx], True
            
    if side == 0:
        dist = (mx - sx + (1 - st_x) / 2) / ca
    else:
        dist = (my - sy + (1 - st_y) / 2) / sa
        
    return {"distance": abs(dist), "wallType": wt, "side": side, "mapX": mx, "mapY": my}


def _render_sprites(surface, w, h, player, enemies, bullets, pickups, z_buf):
    sp = []
    for e in enemies:
        if e.state != EnemyState.DEAD:
            d = math.sqrt((e.x-player.x)**2 + (e.y-player.y)**2)
            sp.append((e, d, "enemy"))
            
    for b in bullets:
        d = math.sqrt((b.x-player.x)**2 + (b.y-player.y)**2)
        sp.append((b, d, "bullet"))
        
    for p in pickups:
        if p.active:
            d = math.sqrt((p.x-player.x)**2 + (p.y-player.y)**2)
            sp.append((p, d, "pickup"))

    sp.sort(key=lambda x: x[1], reverse=True)

    for ref, dist, stype in sp:
        if dist < 0.3: continue
        
        dx, dy = ref.x - player.x, ref.y - player.y
        ang = math.atan2(dy, dx) - player.angle
        
        while ang > math.pi: ang -= 2*math.pi
        while ang < -math.pi: ang += 2*math.pi
        
        if abs(ang) > FOV: continue
        
        c_dist = dist * math.cos(ang)
        if c_dist < 0.01: continue
        
        s_h = min(h * 2, h / c_dist)
        s_t = (h - s_h) / 2
        sx = ((ang + HALF_FOV) / FOV) * w
        s_w = s_h
        start_x = int(sx - s_w / 2)

        if stype == "enemy":
            _draw_enemy_sprite(surface, ref, start_x, s_t, s_w, s_h, c_dist, z_buf, w)
        elif stype == "pickup":
            _draw_pickup_sprite(surface, ref, start_x, s_t, s_w, s_h, c_dist, z_buf, w)
        else:
            bx = int(sx)
            if 0 < bx < w and c_dist < z_buf[bx]:
                sz = max(2, int(h / c_dist * 0.015))
                if ref.fromPlayer:
                    pygame.draw.circle(surface, (255, 255, 100), (bx, h // 2), sz)
                else:
                    pygame.draw.circle(surface, (255, 80, 50), (bx, h // 2), sz)


def _draw_enemy_sprite(surface, enemy, sx, top, w, h, dist, z_buf, canvas_w):
    fg = min(1, dist / 18)
    av = int((1 - fg * 0.5) * 255)
    conf = ENEMY_CLASS_CONFIG.get(enemy.enemyClass, ENEMY_CLASS_CONFIG[EnemyClass.TANK])
    b_col = conf["minimapColor"]

    st_col = max(0, int(sx))
    en_col = min(canvas_w, int(sx + w))
    if en_col <= st_col: return

    visible = False
    for x in range(st_col, en_col):
        if dist < z_buf[x]:
            visible = True
            break
    if not visible: return

    # restoring the little guys. i shouldn't have deleted this but i was tired.
    if enemy.enemyClass == EnemyClass.TANK:
        h_col = (200, 140, 120)
        s_col = (int(b_col[0]*0.7), int(b_col[1]*0.7), int(b_col[2]*0.7))
        l_col = (int(b_col[0]*0.55), int(b_col[1]*0.55), int(b_col[2]*0.55))
        h_tx_l, h_tx_r = 0.28, 0.72
        s_tx_l, s_tx_r = 0.10, 0.90
        t_tx_l, t_tx_r = 0.18, 0.82
        l_tx_rng = [(0.22, 0.42), (0.58, 0.78)]
        a_tx_rng = [(0.04, 0.20), (0.80, 0.96)]
        g_tx_l, g_tx_r = 0.38, 0.62
        has_g = True
        y_h_t, y_h_b = int(h*0.04), int(h*0.22)
        y_s_t, y_s_b = int(h*0.20), int(h*0.32)
        y_t_t, y_t_b = int(h*0.30), int(h*0.65)
        y_l_t, y_l_b = int(h*0.62), int(h)
        y_a_t, y_a_b = int(h*0.30), int(h*0.60)
        y_g_c = int(h*0.45)
        y_g_h = int(h*0.05)
        e_tx_rng = [(0.33, 0.42), (0.58, 0.67)]
        y_e_t, y_e_b = int(h*0.10), int(h*0.17)
    elif enemy.enemyClass == EnemyClass.SCOUT:
        h_col = (230, 200, 140)
        s_col = (int(b_col[0]*0.85), int(b_col[1]*0.85), int(b_col[2]*0.85))
        l_col = (int(b_col[0]*0.6), int(b_col[1]*0.6), int(b_col[2]*0.6))
        h_tx_l, h_tx_r = 0.35, 0.65
        s_tx_l, s_tx_r = 0.25, 0.75
        t_tx_l, t_tx_r = 0.30, 0.70
        l_tx_rng = [(0.33, 0.46), (0.54, 0.67)]
        a_tx_rng = [(0.18, 0.30), (0.70, 0.82)]
        g_tx_l, g_tx_r = 0.43, 0.55
        has_g = True
        y_h_t, y_h_b = int(h*0.10), int(h*0.28)
        y_s_t, y_s_b = int(h*0.28), int(h*0.36)
        y_t_t, y_t_b = int(h*0.34), int(h*0.60)
        y_l_t, y_l_b = int(h*0.58), int(h)
        y_a_t, y_a_b = int(h*0.34), int(h*0.56)
        y_g_c = int(h*0.45)
        y_g_h = int(h*0.03)
        e_tx_rng = [(0.38, 0.44), (0.56, 0.62)]
        y_e_t, y_e_b = int(h*0.15), int(h*0.21)
    else:
        h_col = (220, 160, 140)
        s_col = (int(b_col[0]*0.85), int(b_col[1]*0.85), int(b_col[2]*0.85))
        l_col = (int(b_col[0]*0.65), int(b_col[1]*0.65), int(b_col[2]*0.65))
        h_tx_l, h_tx_r = 0.32, 0.68
        s_tx_l, s_tx_r = 0.20, 0.80
        t_tx_l, t_tx_r = 0.25, 0.75
        l_tx_rng = [(0.30, 0.48), (0.52, 0.70)]
        a_tx_rng = [(0.12, 0.26), (0.74, 0.88)]
        g_tx_l, g_tx_r = 0.42, 0.58
        has_g = True
        y_h_t, y_h_b = int(h*0.08), int(h*0.28)
        y_s_t, y_s_b = int(h*0.27), int(h*0.35)
        y_t_t, y_t_b = int(h*0.33), int(h*0.62)
        y_l_t, y_l_b = int(h*0.60), int(h)
        y_a_t, y_a_b = int(h*0.32), int(h*0.58)
        y_g_c = int(h*0.45)
        y_g_h = int(h*0.04)
        e_tx_rng = [(0.37, 0.44), (0.56, 0.63)]
        y_e_t, y_e_b = int(h*0.15), int(h*0.21)

    s_sf = pygame.Surface((en_col - st_col, int(h) + 10), pygame.SRCALPHA)
    hp_r = enemy.health / enemy.maxHealth if enemy.maxHealth > 0 else 0

    for x in range(st_col, en_col):
        if dist >= z_buf[x]: continue
        tx = (x - sx) / w if w > 0 else 0
        cx = x - st_col

        # head
        if h_tx_l < tx < h_tx_r:
            pygame.draw.line(s_sf, (*h_col, av), (cx, y_h_t), (cx, y_h_b))
        
        # eyes. turning red when they see you.
        if enemy.canSeePlayer:
            for el, er in e_tx_rng:
                if el < tx < er:
                    pygame.draw.line(s_sf, (255, 50, 0, av), (cx, y_e_t), (cx, y_e_b))
        
        # shoulders and torso
        if s_tx_l < tx < s_tx_r:
            pygame.draw.line(s_sf, (*s_col, av), (cx, y_s_t), (cx, y_s_b))
        if t_tx_l < tx < t_tx_r:
            pygame.draw.line(s_sf, (*b_col, av), (cx, y_t_t), (cx, y_t_b))
        
        # limbs
        for ll, lr in l_tx_rng:
            if ll < tx < lr:
                pygame.draw.line(s_sf, (*l_col, av), (cx, y_l_t), (cx, y_l_b))
        for al, ar in a_tx_rng:
            if al < tx < ar:
                pygame.draw.line(s_sf, (*b_col, av), (cx, y_a_t), (cx, y_a_b))

        # gun. i hate drawing weapons.
        if has_g:
            if g_tx_l < tx < g_tx_r:
                pygame.draw.line(s_sf, (51, 51, 51, av), (cx, y_g_c - y_g_h), (cx, y_g_c + y_g_h))

        # tiny health bar above them. 
        if 0.1 < tx < 0.9:
            bw = int(w * 0.8)
            bx_s = int(w * 0.1)
            rel_x = (x - sx - bx_s) / bw if bw > 0 else 0
            if 0 < rel_x < 1:
                col = (0, 255, 68, av) if rel_x < hp_r else (68, 0, 0, av)
                pygame.draw.line(s_sf, col, (cx, 0), (cx, 3))
    
    surface.blit(s_sf, (st_col, top))


def _draw_pickup_sprite(surface, p, sx, top, w, h, dist, z_buf, canvas_w):
    fg = min(1, dist / 18)
    av = int((1 - fg * 0.5) * 255)
    
    st_col = max(0, int(sx))
    en_col = min(canvas_w, int(sx + w))
    if en_col <= st_col: return
    
    visible = False
    for x in range(st_col, en_col):
        if dist < z_buf[x]:
            visible = True
            break
    if not visible: return
    
    s_sf = pygame.Surface((en_col - st_col, int(h) + 5), pygame.SRCALPHA)
    
    for x in range(st_col, en_col):
        if dist >= z_buf[x]: continue
        tx = (x - sx) / w
        cx = x - st_col

        # making these boxes look like actual pickups again
        if p.pickupType == PickupType.HEALTH:
            if 0.2 < tx < 0.8:
                pygame.draw.line(s_sf, (255, 255, 255, av), (cx, int(h*0.2)), (cx, int(h*0.8)))
                # red cross
                if 0.45 < tx < 0.55:
                    pygame.draw.line(s_sf, (255, 0, 0, av), (cx, int(h*0.3)), (cx, int(h*0.7)))
                elif 0.35 < tx < 0.65:
                    pygame.draw.line(s_sf, (255, 0, 0, av), (cx, int(h*0.45)), (cx, int(h*0.55)))
        else:
            if 0.25 < tx < 0.75:
                pygame.draw.line(s_sf, (230, 120, 0, av), (cx, int(h*0.25)), (cx, int(h*0.75)))
                if 0.4 < tx < 0.6:
                    pygame.draw.line(s_sf, (255, 180, 50, av), (cx, int(h*0.35)), (cx, int(h*0.65)))
            
    surface.blit(s_sf, (st_col, top))


def _render_particles(surface, w, h, player, pt, z_buf):
    if not pt: return
    for p in pt:
        dx, dy = p.x - player.x, p.y - player.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < 0.1: continue
        
        ang = math.atan2(dy, dx) - player.angle
        while ang > math.pi: ang -= 2*math.pi
        while ang < -math.pi: ang += 2*math.pi
        if abs(ang) > FOV * 0.8: continue
        
        c_dist = dist * math.cos(ang)
        sx = ((ang + HALF_FOV) / FOV) * w
        bx = int(sx)
        if bx < 0 or bx >= w: continue
        if c_dist >= z_buf[bx]: continue
        
        sz = max(1, int((p.size / c_dist) * h * 0.1))
        alpha = int((p.life / p.maxLife) * 0.8 * 255)
        pygame.draw.circle(surface, (*p.color, alpha), (bx, h // 2), sz)


def render_hud(sf, player, rnd, score, shooting, flash, punching=False, money=0):
    w, h = sf.get_size()
    
    # semi-transparent bars
    b_bg = (20, 20, 25, 160)
    pygame.draw.rect(sf, b_bg, (15, h - 70, 180, 55), border_radius=4)
    
    hp_r = player.health / player.maxHealth if player.maxHealth > 0 else 0
    hp_c = (0, 255, 100) if hp_r > 0.6 else (255, 200, 0) if hp_r > 0.3 else (255, 50, 0)
    
    pygame.draw.rect(sf, (40, 10, 10), (25, h - 60, 160, 14), border_radius=2)
    pygame.draw.rect(sf, hp_c, (25, h - 60, int(160 * hp_r), 14), border_radius=2)
    
    fn = _get_font(22)
    sf.blit(fn.render(f"VITAL SIGNS: {int(player.health)}%", True, (255, 255, 255)), (25, h - 42))

    # ammo
    pygame.draw.rect(sf, (20, 20, 10), (25, h - 28, 160, 8), border_radius=1)
    am_r = player.ammo / player.maxAmmo if player.maxAmmo > 0 else 0
    pygame.draw.rect(sf, (200, 150, 0), (25, h - 28, int(160 * am_r), 8), border_radius=1)

    # right info
    pygame.draw.rect(sf, b_bg, (w - 200, h - 70, 185, 55), border_radius=4)
    sf.blit(fn.render(f"PHASE {rnd}", True, (255, 100, 0)), (w - 190, h - 62))
    sf.blit(fn.render(f"CREDITS: {money}", True, (255, 200, 0)), (w - 190, h - 42))

    wn = player.weaponType.upper() if player.weaponType != "default" else "MK-1 PISTOL"
    sf.blit(fn.render(wn, True, (150, 150, 150)), (w - 190, h - 25))

    # crosshair. i swear if i have to align this again...
    cx, cy = w // 2, h // 2
    cc = (255, 255, 255, 180) if not shooting else (255, 50, 0)
    pygame.draw.line(sf, cc, (cx - 8, cy), (cx + 8, cy), 1)
    pygame.draw.line(sf, cc, (cx, cy - 8), (cx, cy + 8), 1)
    pygame.draw.circle(sf, cc, (cx, cy), 2, 1)

    _draw_weapon(sf, w, h, shooting, flash, punching)


def _draw_weapon(sf, w, h, shooting, flash, punching=False):
    wx, wy = w // 2, h - 10
    bb = math.sin(pygame.time.get_ticks() * 0.003) * 3
    kb = -15 if shooting else 0

    if punching:
        p_sf = pygame.Surface((80, 100), pygame.SRCALPHA)
        pygame.draw.ellipse(p_sf, (210, 160, 130), (10, 20, 50, 40))
        for i in range(4):
            pygame.draw.circle(p_sf, (200, 150, 120), (20 + i * 10, 22), 4)
        sf.blit(p_sf, (wx - 10, wy - 90 + bb + kb * 0.5))
    else:
        g_sf = pygame.Surface((60, 120), pygame.SRCALPHA)
        pygame.draw.rect(g_sf, (51, 51, 51), (15, 30, 30, 60))
        pygame.draw.rect(g_sf, (34, 34, 34), (22, 10, 16, 25))
        if flash > 0:
            al = int(flash * 255)
            pygame.draw.circle(g_sf, (255, 238, 68, al), (30, 0), 12)
        sf.blit(g_sf, (wx - 30, wy - 110 + bb + kb))


def draw_minimap(sf, w, h, gm, player, en):
    rad = 60
    sz = rad * 2
    mx, my = w - sz - 15, 15

    cs = (sz * 0.8) / max(gm.width, gm.height)
    ox = (sz - gm.width * cs) / 2
    oy = (sz - gm.height * cs) / 2

    m_sf = pygame.Surface((sz, sz), pygame.SRCALPHA)
    pygame.draw.circle(m_sf, (0, 20, 10, 200), (rad, rad), rad)
    
    # grid
    for i in range(0, sz, 4):
        pygame.draw.line(m_sf, (0, 40, 20, 100), (0, i), (sz, i), 1)
        pygame.draw.line(m_sf, (0, 40, 20, 100), (i, 0), (i, sz), 1)

    for y in range(gm.height):
        for x in range(gm.width):
            c = gm.cells[y][x]
            if c > 0:
                col = (0, 150, 80, 180) if c == 9 else (0, 100, 50, 150)
                pygame.draw.rect(m_sf, col, (ox + x * cs, oy + y * cs, max(1, cs), max(1, cs)))

    px, py = ox + player.x * cs, oy + player.y * cs
    pygame.draw.circle(m_sf, (0, 255, 136), (int(px), int(py)), 3)
    
    # cone
    pts = [(px, py),
           (px + math.cos(player.angle - 0.4) * 15, py + math.sin(player.angle - 0.4) * 15),
           (px + math.cos(player.angle + 0.4) * 15, py + math.sin(player.angle + 0.4) * 15)]
    pygame.draw.polygon(m_sf, (0, 255, 136, 60), pts)

    for e in en:
        if e.state != EnemyState.DEAD:
            cl = ENEMY_CLASS_CONFIG.get(e.enemyClass, ENEMY_CLASS_CONFIG[EnemyClass.TANK])["minimapColor"]
            pygame.draw.circle(m_sf, (*cl, 200), (int(ox + e.x * cs), int(oy + e.y * cs)), 2)

    msk = pygame.Surface((sz, sz), pygame.SRCALPHA)
    pygame.draw.circle(msk, (255, 255, 255, 255), (rad, rad), rad)
    m_sf.blit(msk, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    
    pygame.draw.circle(sf, (0, 255, 100, 40), (mx + rad, my + rad), rad + 2, 3)
    pygame.draw.circle(sf, (0, 120, 50), (mx + rad, my + rad), rad, 2)
    sf.blit(m_sf, (mx, my))
