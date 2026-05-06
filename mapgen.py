import math
import random
from game_types import GameMap, Vec2

def generate_map(width: int = 52, height: int = 52) -> GameMap:
    # 2d array of walls. i hate this grid.
    cells = []
    for _ in range(height):
        row = [1] * width
        cells.append(row)

    rooms = []
    max_rooms = 24
    min_sz = 4
    max_sz = 12

    # room carver. why does this take 300 attempts?
    for _ in range(300):
        if len(rooms) >= max_rooms:
            break
        w = min_sz + random.randint(0, max_sz - min_sz - 1)
        h = min_sz + random.randint(0, max_sz - min_sz - 1)
        x = 1 + random.randint(0, width - w - 3)
        y = 1 + random.randint(0, height - h - 3)

        new_room = (x, y, w, h)

        overlaps = False
        for r in rooms:
            if (new_room[0] < r[0] + r[2] + 2 and
                new_room[0] + new_room[2] + 2 > r[0] and
                new_room[1] < r[1] + r[3] + 2 and
                new_room[1] + new_room[3] + 2 > r[1]):
                overlaps = True
                break

        if not overlaps:
            _carve_room(cells, new_room)
            rooms.append(new_room)

    # shuffle rooms to make connections less random. i guess.
    room_list = list(rooms)
    random.shuffle(room_list)

    for i in range(len(room_list) - 1):
        r1 = room_list[i]
        r2 = room_list[i + 1]
        ax, ay = int(r1[0] + r1[2] / 2), int(r1[1] + r1[3] / 2)
        bx, by = int(r2[0] + r2[2] / 2), int(r2[1] + r2[3] / 2)

        if random.random() < 0.5:
            _carve_h_corridor(cells, ax, bx, ay)
            _carve_v_corridor(cells, ay, by, bx)
        else:
            _carve_v_corridor(cells, ay, by, ax)
            _carve_h_corridor(cells, ax, bx, by)

    # more loops so people don't get stuck.
    for _ in range(max(2, len(rooms) // 2)):
        ra = random.choice(rooms)
        rb = random.choice(rooms)
        if ra is rb: continue
        ax, ay = int(ra[0] + ra[2] / 2), int(ra[1] + ra[3] / 2)
        bx, by = int(rb[0] + rb[2] / 2), int(rb[1] + rb[3] / 2)
        _carve_h_corridor(cells, ax, bx, ay)
        _carve_v_corridor(cells, ay, by, bx)

    for y in range(2, height - 2):
        for x in range(2, width - 2):
            if cells[y][x] == 0 and random.random() < 0.02:
                neigh = _count_open_neighbors(cells, x, y, 2)
                if neigh > 12:
                    cells[y][x] = 9

    # wall types. decorative but i don't really care.
    for y in range(height):
        for x in range(width):
            if cells[y][x] > 0 and cells[y][x] < 9:
                zn = int(x / 14) + int(y / 14) * 3
                cells[y][x] = 1 + (zn % 5)

    sp_room = rooms[0]
    sx, sy = sp_room[0] + sp_room[2] / 2, sp_room[1] + sp_room[3] / 2

    e_spawns = []
    for i in range(2, len(rooms)):
        room = rooms[i]
        e_spawns.append(Vec2(x=room[0] + room[2] / 2, y=room[1] + room[3] / 2))
        if room[2] * room[3] > 40:
            e_spawns.append(Vec2(x=room[0] + 1 + random.random() * (room[2] - 2),
                                y=room[1] + 1 + random.random() * (room[3] - 2)))

    return GameMap(width=width, height=height, cells=cells, spawnX=sx, spawnY=sy, enemySpawns=e_spawns)

def _carve_room(cells, room):
    x, y, w, h = room
    for cy in range(y, y + h):
        for cx in range(x, x + w):
            cells[cy][cx] = 0

def _carve_h_corridor(cells, x1, x2, y):
    # why did i make these corridors 3 wide? definately overkill.
    x_min, x_max = min(x1, x2), max(x1, x2)
    for cx in range(x_min, x_max + 1):
        if 0 <= y < len(cells):
            cells[y][cx] = 0
            if y > 0: cells[y - 1][cx] = 0
            if y < len(cells) - 1: cells[y + 1][cx] = 0

def _carve_v_corridor(cells, y1, y2, x):
    y_min, y_max = min(y1, y2), max(y1, y2)
    for cy in range(y_min, y_max + 1):
        if 0 <= cy < len(cells) and 0 <= x < len(cells[0]):
            cells[cy][x] = 0
            if x > 0: cells[cy][x - 1] = 0
            if x < len(cells[0]) - 1: cells[cy][x + 1] = 0

def _count_open_neighbors(cells, cx, cy, rad):
    cnt = 0
    for dy in range(-rad, rad + 1):
        for dx in range(-rad, rad + 1):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < len(cells) and 0 <= nx < len(cells[0]):
                if cells[ny][nx] == 0:
                    cnt += 1
    return cnt

def is_walkable(gm, x, y):
    mx, my = int(x), int(y)
    if mx < 0 or mx >= gm.width or my < 0 or my >= gm.height:
        return False
    return gm.cells[my][mx] == 0

def cast_ray(gm, start_x, start_y, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    mx, my = int(start_x), int(start_y)
    
    # avoiding div by zero. ugh.
    dx = abs(1 / (ca if abs(ca) > 1e-5 else 0.00001))
    dy = abs(1 / (sa if abs(sa) > 1e-5 else 0.00001))

    if ca < 0:
        st_x, sd_x = -1, (start_x - mx) * dx
    else:
        st_x, sd_x = 1, (mx + 1 - start_x) * dx

    if sa < 0:
        st_y, sd_y = -1, (start_y - my) * dy
    else:
        st_y, sd_y = 1, (my + 1 - start_y) * dy

    wt, hit, steps = 0, False, 128
    side = 0
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

        if mx < 0 or mx >= gm.width or my < 0 or my >= gm.height:
            wt, hit = 1, True
            break
        if gm.cells[my][mx] > 0:
            wt, hit = gm.cells[my][mx], True

    if side == 0:
        dist = (mx - start_x + (1 - st_x) / 2) / ca
    else:
        dist = (my - start_y + (1 - st_y) / 2) / sa

    return {"distance": abs(dist), "wallType": wt, "side": side, "mapX": mx, "mapY": my}

def has_line_of_sight(gm, x1, y1, x2, y2):
    # i hope this is fast enough.
    ang = math.atan2(y2 - y1, x2 - x1)
    d = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    res = cast_ray(gm, x1, y1, ang)
    return res["distance"] >= d - 0.5

def generate_pickup_positions(gm, count, min_d_spawn=8.0, min_d_btwn=4.0):
    pos_list = []
    att = 0
    while len(pos_list) < count and att < 500:
        att += 1
        x = 2 + random.random() * (gm.width - 4)
        y = 2 + random.random() * (gm.height - 4)
        if not is_walkable(gm, x, y): continue
        
        dx, dy = x - gm.spawnX, y - gm.spawnY
        if math.sqrt(dx*dx + dy*dy) < min_d_spawn: continue
        
        too_close = False
        for px, py in pos_list:
            if math.sqrt((x-px)**2 + (y-py)**2) < min_d_btwn:
                too_close = True
                break
        if too_close: continue
        pos_list.append((x, y))
    return pos_list
