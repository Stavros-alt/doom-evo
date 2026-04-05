import math
import random
from game_types import GameMap, Vec2


def generate_map(width: int = 48, height: int = 48) -> GameMap:
    cells = [[1] * width for _ in range(height)]

    rooms = []
    max_rooms = 20
    min_size = 4
    max_size = 10

    for _ in range(200):
        if len(rooms) >= max_rooms:
            break
        w = min_size + random.randint(0, max_size - min_size - 1)
        h = min_size + random.randint(0, max_size - min_size - 1)
        x = 1 + random.randint(0, width - w - 3)
        y = 1 + random.randint(0, height - h - 3)

        new_room = (x, y, w, h)

        overlaps = False
        for r in rooms:
            if (
                new_room[0] < r[0] + r[2] + 2
                and new_room[0] + new_room[2] + 2 > r[0]
                and new_room[1] < r[1] + r[3] + 2
                and new_room[1] + new_room[3] + 2 > r[1]
            ):
                overlaps = True
                break

        if not overlaps:
            _carve_room(cells, new_room)
            rooms.append(new_room)

    for i in range(len(rooms) - 1):
        a = rooms[i]
        b = rooms[i + 1]
        ax = int(a[0] + a[2] / 2)
        ay = int(a[1] + a[3] / 2)
        bx = int(b[0] + b[2] / 2)
        by = int(b[1] + b[3] / 2)

        if random.random() < 0.5:
            _carve_h_corridor(cells, ax, bx, ay)
            _carve_v_corridor(cells, ay, by, bx)
        else:
            _carve_v_corridor(cells, ay, by, ax)
            _carve_h_corridor(cells, ax, bx, by)

    for _ in range(max(1, len(rooms) // 3)):
        a = rooms[random.randint(0, len(rooms) - 1)]
        b = rooms[random.randint(0, len(rooms) - 1)]
        if a is b:
            continue
        ax = int(a[0] + a[2] / 2)
        ay = int(a[1] + a[3] / 2)
        bx = int(b[0] + b[2] / 2)
        by = int(b[1] + b[3] / 2)
        _carve_h_corridor(cells, ax, bx, ay)
        _carve_v_corridor(cells, ay, by, bx)

    for y in range(2, height - 2):
        for x in range(2, width - 2):
            if cells[y][x] == 0 and random.random() < 0.015:
                neighbors = _count_open_neighbors(cells, x, y, 2)
                if neighbors > 10:
                    cells[y][x] = 9

    for y in range(height):
        for x in range(width):
            if cells[y][x] == 1:
                zone = int(x / 16) + int(y / 16) * 3
                cells[y][x] = 1 + (zone % 5)

    spawn_room = rooms[0]
    spawn_x = spawn_room[0] + spawn_room[2] / 2
    spawn_y = spawn_room[1] + spawn_room[3] / 2

    enemy_spawns = []
    for i in range(2, len(rooms)):
        r = rooms[i]
        enemy_spawns.append(
            Vec2(
                x=r[0] + r[2] / 2,
                y=r[1] + r[3] / 2,
            )
        )
        if r[2] * r[3] > 40:
            enemy_spawns.append(
                Vec2(
                    x=r[0] + 1 + random.random() * (r[2] - 2),
                    y=r[1] + 1 + random.random() * (r[3] - 2),
                )
            )

    return GameMap(
        width=width,
        height=height,
        cells=cells,
        spawnX=spawn_x,
        spawnY=spawn_y,
        enemySpawns=enemy_spawns,
    )


def _carve_room(cells, room):
    x, y, w, h = room
    for cy in range(y, y + h):
        for cx in range(x, x + w):
            cells[cy][cx] = 0


def _carve_h_corridor(cells, x1, x2, y):
    min_x = min(x1, x2)
    max_x = max(x1, x2)
    for cx in range(min_x, max_x + 1):
        if 0 <= y < len(cells):
            cells[y][cx] = 0
            if y > 0:
                cells[y - 1][cx] = 0
            if y < len(cells) - 1:
                cells[y + 1][cx] = 0


def _carve_v_corridor(cells, y1, y2, x):
    min_y = min(y1, y2)
    max_y = max(y1, y2)
    for cy in range(min_y, max_y + 1):
        if 0 <= cy < len(cells) and 0 <= x < len(cells[0]):
            cells[cy][x] = 0
            if x > 0:
                cells[cy][x - 1] = 0
            if x < len(cells[0]) - 1:
                cells[cy][x + 1] = 0


def _count_open_neighbors(cells, cx, cy, radius):
    count = 0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            ny = cy + dy
            nx = cx + dx
            if 0 <= ny < len(cells) and 0 <= nx < len(cells[0]):
                if cells[ny][nx] == 0:
                    count += 1
    return count


def is_walkable(game_map: GameMap, x: float, y: float) -> bool:
    mx = int(x)
    my = int(y)
    if mx < 0 or mx >= game_map.width or my < 0 or my >= game_map.height:
        return False
    return game_map.cells[my][mx] == 0


def cast_ray(game_map: GameMap, start_x: float, start_y: float, angle: float):
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


def has_line_of_sight(
    game_map: GameMap, x1: float, y1: float, x2: float, y2: float
) -> bool:
    angle = math.atan2(y2 - y1, x2 - x1)
    dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    result = cast_ray(game_map, x1, y1, angle)
    return result["distance"] >= dist - 0.5


def generate_pickup_positions(
    game_map, count, min_dist_from_spawn=8.0, min_dist_between=4.0
):
    positions = []
    attempts = 0
    while len(positions) < count and attempts < 500:
        attempts += 1
        x = 2 + random.random() * (game_map.width - 4)
        y = 2 + random.random() * (game_map.height - 4)
        if not is_walkable(game_map, x, y):
            continue
        dx = x - game_map.spawnX
        dy = y - game_map.spawnY
        if math.sqrt(dx * dx + dy * dy) < min_dist_from_spawn:
            continue
        too_close = False
        for px, py in positions:
            ddx = x - px
            ddy = y - py
            if math.sqrt(ddx * ddx + ddy * ddy) < min_dist_between:
                too_close = True
                break
        if too_close:
            continue
        positions.append((x, y))
    return positions
