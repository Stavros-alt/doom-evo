import math
import random
from game_types import (
    Player,
    Enemy,
    Bullet,
    Particle,
    GameMap,
    EnemyState,
    EnemyClass,
    GamePhase,
    Vec2,
    Pickup,
    PickupType,
    POPULATION_SIZE,
    ELITE_COUNT,
    MUTATION_RATE_BASE,
    MUTATION_SCALE_BASE,
    Generation,
    ENEMY_CLASS_CONFIG,
    CLASS_GENOME_KEYS,
    normalize_angle,
)
from mapgen import (
    generate_map,
    is_walkable,
    has_line_of_sight,
    generate_pickup_positions,
)
from neural import (
    random_genome,
    genome_to_network,
    forward_pass,
    evolve_population,
    dampen_outputs,
    mutate,
    crossover,
    get_attributes_from_genome,
    _tournament_select,
)

BULLET_SPEED = 20
PLAYER_BULLET_DAMAGE = 35
PLAYER_SHOOT_COOLDOWN = 0.25
PUNCH_DAMAGE = 25
PUNCH_RANGE = 1.5
PUNCH_COOLDOWN = 0.4

WEAPON_COOLDOWNS = {
    "default": 0.25,
    "rapid": 0.12,
    "spread": 0.7,
}
WEAPON_DAMAGE = {
    "default": 35,
    "rapid": 20,
    "spread": 30,
}
WEAPON_SPREAD = {
    "default": 1,
    "rapid": 1,
    "spread": 5,
}

_bullet_id_counter = 0
_enemy_id_counter = 0


class GameEngine:
    def __init__(self, round_num, existing_genome_pools=None, player_upgrades=None):
        global _bullet_id_counter, _enemy_id_counter

        self.map = generate_map(52, 52)

        upgrades = player_upgrades or {}
        base_hp = upgrades.get("maxHealth", 100)
        base_speed = upgrades.get("maxSpeed", 3.5)
        base_ammo = upgrades.get("maxAmmo", 80)
        armor = upgrades.get("armor", 0)
        weapon = upgrades.get("weapon", "default")
        weapon_lvl = upgrades.get("weaponLevel", 1)

        self.player = Player(
            x=self.map.spawnX,
            y=self.map.spawnY,
            angle=random.random() * math.pi * 2,
            health=base_hp,
            maxHealth=base_hp,
            ammo=60,
            maxAmmo=9999,
            speed=base_speed,
            turnSpeed=2.5,
            isShooting=False,
            isPunching=False,
            shootCooldown=0,
            punchCooldown=0,
            armor=armor,
            weaponType=weapon,
            weaponLevel=weapon_lvl,
            baseSpeed=base_speed,
            baseMaxHealth=base_hp,
            baseMaxAmmo=base_ammo,
        )

        # Genome pools: {"tank": [g1, g2, g3], "scout": [g4, g5, g6]}
        if existing_genome_pools and len(existing_genome_pools) > 0:
            self.genome_pools = dict(existing_genome_pools)
            for key in CLASS_GENOME_KEYS:
                if key not in self.genome_pools:
                    self.genome_pools[key] = [
                        random_genome() for _ in range(POPULATION_SIZE)
                    ]
                while len(self.genome_pools[key]) < POPULATION_SIZE:
                    self.genome_pools[key].append(random_genome())
        else:
            self.genome_pools = {
                key: [random_genome() for _ in range(POPULATION_SIZE)]
                for key in CLASS_GENOME_KEYS
            }

        self.round = round_num

        self.enemies = []
        self._spawn_enemies()

        self.pickups = []
        self._spawn_pickups()

        self.bullets = []
        self.particles = []
        self.money = 0
        self.keys = {}
        self.mouse_x = 0
        self.mouse_held = False
        self.mouse_locked = False
        self.flash_alpha = 0
        self.shoot_flash = 0
        self.score = 0

        # Fitness and damage tracked per enemy index
        num_enemies = len(self.enemies)
        self.fitnesses = [0.0] * num_enemies
        self.damage_dealt = [0] * num_enemies

        self.generation_history = []
        self.phase = GamePhase.PLAYING
        self.round_time = 0

    def _spawn_enemies(self):
        global _enemy_id_counter

        enemy_classes = [
            EnemyClass.TANK,
            EnemyClass.TANK,
            EnemyClass.TANK,
            EnemyClass.SCOUT,
            EnemyClass.SCOUT,
            EnemyClass.SCOUT,
        ]
        extra_enemies = max(0, self.round - 3) * 2
        for _ in range(extra_enemies):
            enemy_classes.append(random.choice([EnemyClass.TANK, EnemyClass.SCOUT]))

        # enemy caps. old code didnt have this but chromebooks die
        enemy_classes = enemy_classes[:8]
        if not enemy_classes:
           enemy_classes = [EnemyClass.TANK]

        spawn_points = list(self.map.enemySpawns)
        while len(spawn_points) < len(enemy_classes):
            x = 5 + random.random() * (self.map.width - 10)
            y = 5 + random.random() * (self.map.height - 10)
            if is_walkable(self.map, x, y):
                spawn_points.append(Vec2(x, y))

        random.shuffle(spawn_points)

        class_counts = {"tank": 0, "scout": 0, "regular": 0}

        for i, eclass in enumerate(enemy_classes):
            spawn = spawn_points[i % len(spawn_points)]
            ex = spawn.x + (random.random() - 0.5) * 2
            ey = spawn.y + (random.random() - 0.5) * 2
            if not is_walkable(self.map, ex, ey):
                ex = spawn.x
                ey = spawn.y

            class_key = eclass.value
            idx = class_counts[class_key]
            class_counts[class_key] += 1
            genome = self.genome_pools[class_key][
                idx % len(self.genome_pools[class_key])
            ]

            config = ENEMY_CLASS_CONFIG[eclass]
            attrs = get_attributes_from_genome(genome)

            self.enemies.append(
                Enemy(
                    id=_enemy_id_counter,
                    x=ex,
                    y=ey,
                    angle=random.random() * math.pi * 2,
                    health=config["hp"] * attrs["health_mult"],
                    maxHealth=config["hp"] * attrs["health_mult"],
                    speed=config["speed"] * attrs["speed_mult"],
                    state=EnemyState.PATROL,
                    enemyClass=eclass,
                    shootCooldown=config["shootCooldown"],
                    shootTimer=random.random() * config["shootCooldown"] * 1.5,
                    alertRadius=22,
                    attackRadius=28,
                    damage=config["damage"] * attrs["damage_mult"],
                    brain=genome_to_network(genome),
                    genome=genome,
                    distanceToPlayer=999,
                    angleToPlayer=0,
                    canSeePlayer=False,
                    strafeDir=1 if random.random() > 0.5 else -1,
                    strafeTimer=0,
                    dodgeTimer=0,
                    lastKnownPlayerX=ex,
                    lastKnownPlayerY=ey,
                    accuracy=config["accuracy"] * attrs["accuracy_mult"],
                    reactionTime=0.3,
                    reactionTimer=random.random() * 0.5,
                    flankAngle=random.random() * math.pi * 2,
                    stuckTimer=0,
                )
            )
            _enemy_id_counter += 1

    def _spawn_pickups(self):
        positions = generate_pickup_positions(self.map, 4, min_dist_from_spawn=5.0)
        pickup_types = [
            PickupType.HEALTH,
            PickupType.HEALTH,
            PickupType.AMMO,
            PickupType.AMMO,
        ]
        random.shuffle(pickup_types)

        for i, (px, py) in enumerate(positions):
            ptype = pickup_types[i] if i < len(pickup_types) else PickupType.HEALTH
            amount = 25 if ptype == PickupType.HEALTH else 20
            self.pickups.append(
                Pickup(x=px, y=py, pickupType=ptype, amount=amount, active=True)
            )

    def update(self, dt):
        if self.phase != GamePhase.PLAYING:
            return

        self.round_time += dt
        self.flash_alpha = max(0, self.flash_alpha - dt * 2)
        self.shoot_flash = max(0, self.shoot_flash - dt * 5)

        self._update_player(dt)
        self._update_enemies(dt)
        self._update_bullets(dt)
        self._update_particles(dt)
        self._check_round_end()

    def _update_player(self, dt):
        global _bullet_id_counter
        player = self.player
        game_map = self.map
        keys = self.keys

        if self.mouse_locked and self.mouse_x != 0:
            player.angle += self.mouse_x * 0.002
            self.mouse_x = 0
            while player.angle > math.pi:
                player.angle -= 2 * math.pi
            while player.angle < -math.pi:
                player.angle += 2 * math.pi

        cos = math.cos(player.angle)
        sin = math.sin(player.angle)
        mx = 0.0
        my = 0.0

        if keys.get("w"):
            mx += cos
            my += sin
        if keys.get("s"):
            mx -= cos
            my -= sin
        if keys.get("a"):
            mx += sin
            my -= cos
        if keys.get("d"):
            mx -= sin
            my += cos

        length = math.sqrt(mx * mx + my * my)
        if length > 0:
            mx = (mx / length) * player.speed * dt
            my = (my / length) * player.speed * dt

            nx = player.x + mx
            ny = player.y + my
            margin = 0.25
            if is_walkable(
                game_map,
                nx + (1 if mx > 0 else (-1 if mx < 0 else 0)) * margin,
                player.y,
            ):
                player.x = nx
            if is_walkable(
                game_map,
                player.x,
                ny + (1 if my > 0 else (-1 if my < 0 else 0)) * margin,
            ):
                player.y = ny

        # Pickup collection
        for pickup in self.pickups:
            if not pickup.active:
                continue
            dx = player.x - pickup.x
            dy = player.y - pickup.y
            if dx * dx + dy * dy < 0.64:
                if pickup.pickupType == PickupType.HEALTH:
                    player.health = min(player.maxHealth, player.health + pickup.amount)
                else:
                    player.ammo = min(player.maxAmmo, player.ammo + pickup.amount)
                pickup.active = False

        if player.shootCooldown > 0:
            player.shootCooldown -= dt

        if player.punchCooldown > 0:
            player.punchCooldown -= dt
            if player.punchCooldown <= 0:
                player.isPunching = False

        if (
            (keys.get("mouse0") or self.mouse_held)
            and player.shootCooldown <= 0
            and player.ammo > 0
        ):
            player.isShooting = True
            weapon_key = (
                player.weaponType
                if player.weaponType in WEAPON_COOLDOWNS
                else "default"
            )
            player.shootCooldown = WEAPON_COOLDOWNS[weapon_key]
            player.ammo -= 1
            self.shoot_flash = 1

            num_bullets = WEAPON_SPREAD[weapon_key]
            base_angle = player.angle
            base_damage = WEAPON_DAMAGE[weapon_key]

            for i in range(num_bullets):
                spread = 0
                if num_bullets > 1:
                    spread = (i - (num_bullets - 1) / 2) * 0.08
                angle = base_angle + spread

                self.bullets.append(
                    Bullet(
                        id=_bullet_id_counter,
                        x=player.x,
                        y=player.y,
                        angle=angle,
                        speed=BULLET_SPEED,
                        damage=base_damage,
                        fromPlayer=True,
                        life=2.0,
                    )
                )
                _bullet_id_counter += 1

            self._spawn_muzzle_particles(player.x, player.y, player.angle)
        elif (
            (keys.get("mouse0") or self.mouse_held)
            and player.punchCooldown <= 0
            and player.ammo <= 0
        ):
            player.isPunching = True
            player.punchCooldown = PUNCH_COOLDOWN

            cos_a = math.cos(player.angle)
            sin_a = math.sin(player.angle)
            punch_x = player.x + cos_a * PUNCH_RANGE * 0.5
            punch_y = player.y + sin_a * PUNCH_RANGE * 0.5

            for ei, enemy in enumerate(self.enemies):
                if enemy.state == EnemyState.DEAD:
                    continue
                dx = enemy.x - punch_x
                dy = enemy.y - punch_y
                if dx * dx + dy * dy < PUNCH_RANGE * PUNCH_RANGE:
                    enemy.health -= PUNCH_DAMAGE
                    self._spawn_hit_particles(enemy.x, enemy.y, (255, 34, 0))

                    if ei < len(self.damage_dealt):
                        self.damage_dealt[ei] += PUNCH_DAMAGE

                    if enemy.health <= 0:
                        enemy.state = EnemyState.DEAD
                        self.score += 100 * self.round
                        self.money += max(1, int(self.round * 1.5))
                        self._spawn_death_particles(enemy.x, enemy.y)

                        fi = next(
                            (
                                idx
                                for idx, e in enumerate(self.enemies)
                                if e.id == enemy.id
                            ),
                            -1,
                        )
                        if fi >= 0:
                            self.fitnesses[fi] += 50
        else:
            player.isShooting = False

    def _get_dampen_factor(self):
        if self.round <= 1:
            return 0.50
        elif self.round == 2:
            return 0.25
        return 0.0

    def _get_stat_multiplier(self):
        return 1.0 + (self.round - 1) * 0.155

    def _update_enemies(self, dt):
        global _bullet_id_counter
        enemies = self.enemies
        player = self.player
        game_map = self.map
        bullets = self.bullets

        stat_mult = self._get_stat_multiplier()

        for ei, enemy in enumerate(enemies):
            if enemy.state == EnemyState.DEAD:
                continue

            dx = player.x - enemy.x
            dy = player.y - enemy.y
            enemy.distanceToPlayer = math.sqrt(dx * dx + dy * dy)
            enemy.angleToPlayer = math.atan2(dy, dx)

            if enemy.reactionTimer > 0:
                enemy.reactionTimer -= dt

            attack_radius = enemy.attackRadius
            if enemy.distanceToPlayer < attack_radius:
                enemy.canSeePlayer = has_line_of_sight(
                    game_map, enemy.x, enemy.y, player.x, player.y
                )
            else:
                enemy.canSeePlayer = False

            if enemy.canSeePlayer:
                enemy.lastKnownPlayerX = player.x
                enemy.lastKnownPlayerY = player.y

            # enemy state, chase or patrol. whatever.
            if enemy.distanceToPlayer < enemy.alertRadius and enemy.canSeePlayer:
                enemy.state = EnemyState.CHASE
            else:
                enemy.state = EnemyState.PATROL

            if enemy.state == EnemyState.CHASE:
                inputs = self._build_nn_inputs(enemy, player)
                outputs = forward_pass(enemy.brain, inputs)

                turn_left = outputs[2]
                turn_right = outputs[3]
                shoot = outputs[4]

                nn_turn_speed = (turn_left - turn_right) * 2.2
                enemy.angle += nn_turn_speed * dt
            else:
                outputs = None  # not used for patrol
                shoot = 0

            old_x, old_y = enemy.x, enemy.y
            self._move_enemy(enemy, game_map, dt, outputs, player)

            # tracking positions for stuck stuff
            enemy.recent_positions.append((enemy.x, enemy.y))
            if len(enemy.recent_positions) > 20:
                enemy.recent_positions.pop(0)

            # clipping again? revert.
            if not is_walkable(game_map, enemy.x, enemy.y):
                enemy.x = old_x
                enemy.y = old_y
                # clipping still happens. ugh.

            # stuck detection
            moved_dist = math.sqrt((enemy.x - old_x) ** 2 + (enemy.y - old_y) ** 2)
            moving_intent = (
                (abs(outputs[0] - outputs[1]) > 0.15)
                if outputs
                else (enemy.state == EnemyState.PATROL)
            )
            min_move_threshold = 0.02 + enemy.speed * dt * 0.3
            if moving_intent and moved_dist < min_move_threshold:
                enemy.stuckTimer += dt
            else:
                enemy.stuckTimer = max(0, enemy.stuckTimer - dt * 2)

            # corner stuck
            corner_stuck = False
            if len(enemy.recent_positions) >= 20:
                start_pos = enemy.recent_positions[0]
                end_pos = enemy.recent_positions[-1]
                total_moved = math.sqrt(
                    (end_pos[0] - start_pos[0]) ** 2 + (end_pos[1] - start_pos[1]) ** 2
                )
                corner_stuck = total_moved < 0.5 and moving_intent

            stuck_threshold = 0.3 if enemy.speed > 3.0 else 0.7
            if enemy.stuckTimer > stuck_threshold or corner_stuck:
                back_dist = enemy.speed * dt * 2.0
                back_x = enemy.x - math.cos(enemy.angle) * back_dist
                back_y = enemy.y - math.sin(enemy.angle) * back_dist
                if is_walkable(game_map, back_x, back_y):
                    enemy.x = back_x
                    enemy.y = back_y
                # turn options for corners
                turn_options = [
                    math.pi / 2,
                    -math.pi / 2,
                    math.pi,
                    math.pi / 4,
                    -math.pi / 4,
                ]
                for turn in turn_options:
                    test_angle = enemy.angle + turn
                    test_x = enemy.x + math.cos(test_angle) * enemy.speed * dt
                    test_y = enemy.y + math.sin(test_angle) * enemy.speed * dt
                    if is_walkable(game_map, test_x, test_y):
                        enemy.angle = test_angle
                        break
                else:
                    enemy.angle += random.uniform(
                        -math.pi, math.pi
                    )  # random if none work
                enemy.stuckTimer = 0
                enemy.recent_positions.clear()  # reset tracking

            effective_shoot_cooldown = enemy.shootCooldown
            effective_damage = enemy.damage * stat_mult
            effective_accuracy = min(1.0, enemy.accuracy * stat_mult)

            shoot_threshold = 0.45  # lower threshold for more shooting

            enemy.shootTimer -= dt

            should_shoot = (
                shoot > shoot_threshold
                and enemy.canSeePlayer
                and enemy.reactionTimer <= 0
                and enemy.shootTimer <= 0
                and enemy.distanceToPlayer < attack_radius
                and effective_damage > 0
            )

            if (
                enemy.canSeePlayer
                and enemy.reactionTimer <= 0
                and enemy.shootTimer <= 0
                and enemy.distanceToPlayer < attack_radius
                and effective_damage > 0
            ):
                if not should_shoot:
                    should_shoot = shoot > 0.35

            if should_shoot:
                if not should_shoot:
                    should_shoot = shoot > 0.35

            if should_shoot:
                enemy.shootTimer = effective_shoot_cooldown

                spread = (1 - effective_accuracy) * 0.3
                aim_angle = math.atan2(player.y - enemy.y, player.x - enemy.x)
                final_angle = aim_angle + (random.random() - 0.5) * spread

                bullets.append(
                    Bullet(
                        id=_bullet_id_counter,
                        x=enemy.x,
                        y=enemy.y,
                        angle=final_angle,
                        speed=BULLET_SPEED * 0.8,
                        damage=int(effective_damage),
                        fromPlayer=False,
                        life=2.0,
                    )
                )
                _bullet_id_counter += 1

                self._spawn_muzzle_particles(enemy.x, enemy.y, final_angle)

            if enemy.strafeTimer > 0:
                enemy.strafeTimer -= dt
            else:
                enemy.strafeDir *= -1
                if enemy.enemyClass == EnemyClass.SCOUT:
                    enemy.strafeTimer = 0.3 + random.random() * 0.4
                else:
                    enemy.strafeTimer = 0.8 + random.random() * 1.5

    def _build_nn_inputs(self, enemy, player, _game_map=None):
        normalized_dist = min(1, enemy.distanceToPlayer / 20)
        angle_diff = normalize_angle(enemy.angleToPlayer - enemy.angle) / math.pi
        can_see = 1 if enemy.canSeePlayer else 0
        health_ratio = enemy.health / enemy.maxHealth if enemy.maxHealth > 0 else 0
        player_angle_to_enemy = (
            normalize_angle(
                math.atan2(enemy.y - player.y, enemy.x - player.x) - player.angle
            )
            / math.pi
        )
        dx = (enemy.lastKnownPlayerX - enemy.x) / 20
        dy = (enemy.lastKnownPlayerY - enemy.y) / 20
        strafe = enemy.strafeDir

        return [
            normalized_dist,
            angle_diff,
            can_see,
            health_ratio,
            player_angle_to_enemy,
            dx,
            dy,
            strafe,
        ]

    def _move_enemy(self, enemy, game_map, dt, outputs, player):
        if enemy.state == EnemyState.DEAD:
            return

        if enemy.state == EnemyState.PATROL:
            enemy.roamTimer += dt
            if enemy.roamTimer > 2.0:
                enemy.angle += (random.random() - 0.5) * 0.5
                enemy.roamTimer = 0.0
            forward_amount = enemy.speed * dt * 0.5
            strafe_amount = 0
            toward_player_x = math.cos(enemy.angle)
            toward_player_y = math.sin(enemy.angle)
            perp_x = -toward_player_y
            perp_y = toward_player_x
            vx = toward_player_x * forward_amount + perp_x * strafe_amount
            vy = toward_player_y * forward_amount + perp_y * strafe_amount
        else:
            # chasing with nn
            move_forward = outputs[0]
            move_back = outputs[1]
            strafe_out = outputs[5]

            toward_player_x = math.cos(enemy.angleToPlayer)
            toward_player_y = math.sin(enemy.angleToPlayer)
            perp_x = -toward_player_y
            perp_y = toward_player_x

            forward_amount = (move_forward - move_back) * enemy.speed * dt
            strafe_amount = strafe_out * enemy.speed * dt

            vx = toward_player_x * forward_amount + perp_x * strafe_amount
            vy = toward_player_y * forward_amount + perp_y * strafe_amount

        margin = 0.5 + enemy.speed * 0.1  # larger margin for fast enemies
        nx = enemy.x + vx
        ny = enemy.y + vy
        sign_vx = 1 if vx > 0 else (-1 if vx < 0 else 0)
        sign_vy = 1 if vy > 0 else (-1 if vy < 0 else 0)
        moved = False

        # check for walls ahead
        look_ahead = 1.0 + enemy.speed * dt * 2
        ahead_x = enemy.x + math.cos(enemy.angle) * look_ahead
        ahead_y = enemy.y + math.sin(enemy.angle) * look_ahead
        wall_ahead = not has_line_of_sight(game_map, enemy.x, enemy.y, ahead_x, ahead_y)

        if wall_ahead:
            # turn a bit to avoid wall
            enemy.angle += random.choice([-0.3, 0.3])

        if is_walkable(game_map, nx + sign_vx * margin, enemy.y):
            enemy.x = nx
            moved = True
        else:
            # Try larger angle adjustments
            for angle_adj in [0.2, -0.2, 0.4, -0.4, 0.6, -0.6, 0.8, -0.8]:
                test_angle = enemy.angle + angle_adj
                test_vx = math.cos(test_angle) * forward_amount + perp_x * strafe_amount
                test_nx = enemy.x + test_vx
                if is_walkable(game_map, test_nx + sign_vx * margin, enemy.y):
                    enemy.x = test_nx
                    enemy.angle = test_angle
                    moved = True
                    break
            if not moved:
                # Back off more
                back_vx = -vx * 0.7
                back_nx = enemy.x + back_vx
                if is_walkable(game_map, back_nx + sign_vx * margin, enemy.y):
                    enemy.x = back_nx
                    moved = True
                else:
                    # Force larger random direction
                    enemy.angle += (random.random() - 0.5) * 2.0

        if is_walkable(game_map, enemy.x, ny + sign_vy * margin):
            enemy.y = ny
            moved = True
        else:
            # same for y
            for angle_adj in [0.2, -0.2, 0.4, -0.4, 0.6, -0.6, 0.8, -0.8]:
                test_angle = enemy.angle + angle_adj
                test_vy = math.sin(test_angle) * forward_amount + perp_y * strafe_amount
                test_ny = enemy.y + test_vy
                if is_walkable(game_map, enemy.x, test_ny + sign_vy * margin):
                    enemy.y = test_ny
                    enemy.angle = test_angle
                    moved = True
                    break
            if not moved:
                back_vy = -vy * 0.7
                back_ny = enemy.y + back_vy
                if is_walkable(game_map, enemy.x, back_ny + sign_vy * margin):
                    enemy.y = back_ny
                    moved = True
                else:
                    enemy.angle += (random.random() - 0.5) * 2.0

        # Stuck detection
        enemy.stuckTimer += 0 if moved else dt
        if enemy.stuckTimer > 2.0:  # More sensitive, 2 seconds
            # Force random direction
            enemy.angle += (random.random() - 0.5) * 3.0  # More aggressive
            enemy.stuckTimer = 0

    def _update_bullets(self, dt):
        bullets = self.bullets
        game_map = self.map
        player = self.player
        enemies = self.enemies

        i = len(bullets) - 1
        while i >= 0:
            b = bullets[i]
            b.life -= dt

            b.x += math.cos(b.angle) * b.speed * dt
            b.y += math.sin(b.angle) * b.speed * dt

            hit = False

            if not is_walkable(game_map, b.x, b.y):
                self._spawn_hit_particles(b.x, b.y, (255, 102, 0))
                hit = True

            if not hit and b.fromPlayer:
                for ei, enemy in enumerate(enemies):
                    if enemy.state == EnemyState.DEAD:
                        continue
                    dx = enemy.x - b.x
                    dy = enemy.y - b.y
                    if dx * dx + dy * dy < 0.5:
                        enemy.health -= b.damage
                        self._spawn_hit_particles(b.x, b.y, (255, 34, 0))
                        hit = True

                        if ei < len(self.damage_dealt):
                            self.damage_dealt[ei] += b.damage

                        if enemy.health <= 0:
                            enemy.state = EnemyState.DEAD
                            self.score += 100 * self.round
                            self.money += max(
                                1, int((self.score / 10) * (self.round * 0.2))
                            )
                            self._spawn_death_particles(enemy.x, enemy.y)

                            fi = next(
                                (
                                    idx
                                    for idx, e in enumerate(enemies)
                                    if e.id == enemy.id
                                ),
                                -1,
                            )
                            if fi >= 0:
                                self.fitnesses[fi] += 50
                        break

            if not hit and not b.fromPlayer:
                dx = player.x - b.x
                dy = player.y - b.y
                if dx * dx + dy * dy < 0.5:
                    damage = b.damage
                    armor = player.armor
                    if armor > 0:
                        reduction = min(armor * 0.1, 0.8)
                        damage = int(damage * (1 - reduction))
                    player.health -= damage
                    self.flash_alpha = min(1, self.flash_alpha + 0.3)
                    hit = True

                    for fi in range(len(enemies)):
                        if enemies[fi].state != EnemyState.DEAD:
                            self.fitnesses[fi] = self.fitnesses[fi] + b.damage * 0.5

                    if player.health <= 0:
                        player.health = 0
                        self.phase = GamePhase.DEAD

            if hit or b.life <= 0:
                bullets.pop(i)
            i -= 1

            # bullet caps. old code didnt have this but chromebooks die
            if len(bullets) > 25:
               bullets.pop(0)

    def _update_particles(self, dt):
        particles = self.particles
        i = len(particles) - 1
        while i >= 0:
            p = particles[i]
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vx *= 0.95
            p.vy *= 0.95
            p.life -= dt
            if p.life <= 0:
                particles.pop(i)
            i -= 1

    def _check_round_end(self):
        if self.phase != GamePhase.PLAYING:
            return
        all_dead = all(e.state == EnemyState.DEAD for e in self.enemies)
        if all_dead:
            self.phase = GamePhase.ROUND_END
            for fi in range(len(self.enemies)):
                self.fitnesses[fi] = (
                    self.fitnesses[fi]
                    + (self.damage_dealt[fi] if fi < len(self.damage_dealt) else 0)
                    * 0.8
                )

            for fi, enemy in enumerate(self.enemies):
                proximity_score = max(0, 20 - enemy.distanceToPlayer) * 0.5
                self.fitnesses[fi] += proximity_score

                if enemy.canSeePlayer:
                    self.fitnesses[fi] += 5

    def evolve_genomes(self, mutation_round):
        mutation_rate = MUTATION_RATE_BASE + (
            -0.01 if mutation_round > 5 else 0.005 * (5 - mutation_round)
        )
        mutation_scale = MUTATION_SCALE_BASE * max(0.2, 1 - mutation_round * 0.07)

        new_pools = {}

        for class_key in CLASS_GENOME_KEYS:
            other_key = "scout" if class_key == "tank" else "tank"
            other_genomes = self.genome_pools.get(other_key, [])

            class_indices = [
                i for i, e in enumerate(self.enemies) if e.enemyClass.value == class_key
            ]
            class_genomes = [
                self.enemies[i].genome for i in class_indices if i < len(self.enemies)
            ]
            class_fitnesses = [
                self.fitnesses[i] for i in class_indices if i < len(self.fitnesses)
            ]

            if len(class_genomes) < 2:
                new_pools[class_key] = [
                    mutate(g, mutation_rate, mutation_scale) for g in class_genomes
                ]
                continue

            # Evolve with occasional cross-breeding
            paired = [
                {"genome": g, "fitness": f}
                for g, f in zip(class_genomes, class_fitnesses)
            ]
            paired.sort(key=lambda x: x["fitness"], reverse=True)

            new_pop = []
            for i in range(min(ELITE_COUNT, len(paired))):
                new_pop.append(list(paired[i]["genome"]))

            while len(new_pop) < len(class_genomes):
                p1 = _tournament_select(paired, 3)
                if random.random() < 0.2 and other_genomes:  # 20% chance cross-breed
                    p2_genome = random.choice(other_genomes)
                else:
                    p2 = _tournament_select(paired, 3)
                    p2_genome = p2["genome"]
                child = crossover(p1["genome"], p2_genome)
                child = mutate(child, mutation_rate, mutation_scale)
                new_pop.append(child)
                # cross-breeding might be messing everything up, i don't know

            new_pools[class_key] = new_pop

        all_fitnesses = self.fitnesses
        max_fit = max(all_fitnesses) if all_fitnesses else 0
        avg_fit = sum(all_fitnesses) / len(all_fitnesses) if all_fitnesses else 0

        self.generation_history.append(
            Generation(
                round=self.round,
                bestFitness=max_fit,
                avgFitness=avg_fit,
                population=POPULATION_SIZE * len(CLASS_GENOME_KEYS),
            )
        )

        return new_pools

    def _spawn_muzzle_particles(self, x, y, angle):
        # cut particles for fps on chromebooks. still looks ok
        for _ in range(1):
            spread = (random.random() - 0.5) * 0.08
            spd = 1.5 + random.random() * 1.0
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(angle + spread) * spd,
                    vy=math.sin(angle + spread) * spd,
                    life=0.08 + random.random() * 0.05,
                    maxLife=0.13,
                    color=(255, 221, 68),
                    size=0.04,
                )
            )

    def _spawn_hit_particles(self, x, y, color):
        # cut particles for fps on chromebooks. still looks ok
        for _ in range(3):
            a = random.random() * math.pi * 2
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(a) * (1 + random.random() * 2),
                    vy=math.sin(a) * (1 + random.random() * 2),
                    life=0.2 + random.random() * 0.2,
                    maxLife=0.4,
                    color=color,
                    size=0.05 + random.random() * 0.05,
                )
            )

    def _spawn_death_particles(self, x, y):
        # cut particles for fps on chromebooks. still looks ok
        for _ in range(8):
            a = random.random() * math.pi * 2
            speed = 1 + random.random() * 4
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(a) * speed,
                    vy=math.sin(a) * speed,
                    life=0.5 + random.random() * 0.5,
                    maxLife=1.0,
                    color=(255, 34, 0) if random.random() > 0.5 else (255, 136, 0),
                    size=0.08 + random.random() * 0.1,
                )
            )
