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

        # genome pools. i hate nested dicts but here we are.
        if existing_genome_pools and len(existing_genome_pools) > 0:
            self.genome_pools = dict(existing_genome_pools)
            for key in CLASS_GENOME_KEYS:
                if key not in self.genome_pools:
                    # why is this missing? fine, random it is.
                    self.genome_pools[key] = []
                    for _ in range(POPULATION_SIZE):
                        self.genome_pools[key].append(random_genome())
                
                while len(self.genome_pools[key]) < POPULATION_SIZE:
                    self.genome_pools[key].append(random_genome())
        else:
            self.genome_pools = {}
            for key in CLASS_GENOME_KEYS:
                pool = []
                for _ in range(POPULATION_SIZE):
                    pool.append(random_genome())
                self.genome_pools[key] = pool

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

        # tracking stats. hope i didn't break indices again
        num_enemies = len(self.enemies)
        self.fitnesses = [0.0] * num_enemies
        self.damage_dealt = [0] * num_enemies
        self.time_spent_seeing_player = [0.0] * num_enemies
        self.bullets_fired = [0] * num_enemies

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

        # enemy caps. chromebooks would explode otherwise
        enemy_classes = enemy_classes[:10]
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
            
            current_pool = self.genome_pools[class_key]
            genome = current_pool[idx % len(current_pool)]

            config = ENEMY_CLASS_CONFIG[eclass]
            attrs = get_attributes_from_genome(genome)

            self.enemies.append(
                Enemy(
                    id=_enemy_id_counter,
                    x=ex,
                    y=ey,
                    angle=random.random() * math.pi * 2,
                    health=int(config["hp"] * attrs["health_mult"]),
                    maxHealth=int(config["hp"] * attrs["health_mult"]),
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
        # spawn extra pickups so the player doesn't cry
        positions = generate_pickup_positions(self.map, 6, min_d_spawn=5.0)
        pickup_types = [
            PickupType.HEALTH,
            PickupType.HEALTH,
            PickupType.AMMO,
            PickupType.AMMO,
            PickupType.HEALTH,
            PickupType.AMMO,
        ]
        random.shuffle(pickup_types)

        for i, pos in enumerate(positions):
            px, py = pos
            ptype = pickup_types[i] if i < len(pickup_types) else PickupType.HEALTH
            amount = 30 if ptype == PickupType.HEALTH else 25
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
            player.angle += self.mouse_x * 0.0025
            self.mouse_x = 0
            while player.angle > math.pi:
                player.angle -= 2 * math.pi
            while player.angle < -math.pi:
                player.angle += 2 * math.pi

        cos_a = math.cos(player.angle)
        sin_a = math.sin(player.angle)
        move_x = 0.0
        move_y = 0.0

        if keys.get("w"):
            move_x += cos_a
            move_y += sin_a
        if keys.get("s"):
            move_x -= cos_a
            move_y -= sin_a
        if keys.get("a"):
            move_x += sin_a
            move_y -= cos_a
        if keys.get("d"):
            move_x -= sin_a
            move_y += cos_a

        mag = math.sqrt(move_x * move_x + move_y * move_y)
        if mag > 0:
            move_x = (move_x / mag) * player.speed * dt
            move_y = (move_y / mag) * player.speed * dt

            nx = player.x + move_x
            ny = player.y + move_y
            margin = 0.3
            if is_walkable(
                game_map,
                nx + (1 if move_x > 0 else (-1 if move_x < 0 else 0)) * margin,
                player.y,
            ):
                player.x = nx
            if is_walkable(
                game_map,
                player.x,
                ny + (1 if move_y > 0 else (-1 if move_y < 0 else 0)) * margin,
            ):
                player.y = ny

        # pickup collection. i should probably optimize this but it's fine
        for pickup in self.pickups:
            if not pickup.active:
                continue
            dist_sq = (player.x - pickup.x)**2 + (player.y - pickup.y)**2
            if dist_sq < 0.64:
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
            weapon_key = player.weaponType if player.weaponType in WEAPON_COOLDOWNS else "default"
            player.shootCooldown = WEAPON_COOLDOWNS[weapon_key]
            player.ammo -= 1
            self.shoot_flash = 1

            num_bullets = WEAPON_SPREAD[weapon_key]
            base_angle = player.angle
            base_damage = WEAPON_DAMAGE[weapon_key]

            for i in range(num_bullets):
                spread_val = 0
                if num_bullets > 1:
                    spread_val = (i - (num_bullets - 1) / 2) * 0.12
                final_angle = base_angle + spread_val

                self.bullets.append(
                    Bullet(
                        id=_bullet_id_counter,
                        x=player.x,
                        y=player.y,
                        angle=final_angle,
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

            cos_p = math.cos(player.angle)
            sin_p = math.sin(player.angle)
            punch_x = player.x + cos_p * PUNCH_RANGE * 0.6
            punch_y = player.y + sin_p * PUNCH_RANGE * 0.6

            for enemy_idx, enemy in enumerate(self.enemies):
                if enemy.state == EnemyState.DEAD:
                    continue
                dx = enemy.x - punch_x
                dy = enemy.y - punch_y
                if dx * dx + dy * dy < PUNCH_RANGE * PUNCH_RANGE:
                    enemy.health -= PUNCH_DAMAGE
                    self._spawn_hit_particles(enemy.x, enemy.y, (255, 34, 0))

                    if enemy_idx < len(self.damage_dealt):
                        self.damage_dealt[enemy_idx] += PUNCH_DAMAGE

                    if enemy.health <= 0:
                        enemy.state = EnemyState.DEAD
                        self.score += 100 * self.round
                        self.money += max(1, int(self.round * 2))
                        self._spawn_death_particles(enemy.x, enemy.y)

                        if enemy_idx < len(self.fitnesses):
                            self.fitnesses[enemy_idx] += 50
        else:
            player.isShooting = False

    def _get_dampen_factor(self):
        if self.round <= 1:
            return 0.40
        elif self.round == 2:
            return 0.20
        return 0.0

    def _get_stat_multiplier(self):
        # scaling getting harder. i'm tired of this math.
        return 1.0 + (self.round - 1) * 0.18

    def _update_enemies(self, dt):
        global _bullet_id_counter
        enemies = self.enemies
        player = self.player
        game_map = self.map
        bullets = self.bullets

        stat_mult = self._get_stat_multiplier()

        for enemy_idx, enemy in enumerate(enemies):
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
                if enemy_idx < len(self.time_spent_seeing_player):
                    self.time_spent_seeing_player[enemy_idx] += dt

            # chase or patrol. hope LoS works.
            if enemy.distanceToPlayer < enemy.alertRadius and (enemy.canSeePlayer or enemy.state == EnemyState.CHASE):
                enemy.state = EnemyState.CHASE
            else:
                enemy.state = EnemyState.PATROL

            if enemy.state == EnemyState.CHASE:
                inputs = self._build_nn_inputs(enemy, player)
                outputs = forward_pass(enemy.brain, inputs)

                turn_left = outputs[2]
                turn_right = outputs[3]
                shoot_val = outputs[4]

                nn_turn_speed = (turn_left - turn_right) * 2.5
                enemy.angle += nn_turn_speed * dt
            else:
                outputs = None
                shoot_val = 0

            old_x, old_y = enemy.x, enemy.y
            self._move_enemy(enemy, game_map, dt, outputs, player)

            # stuck detection. why do they keep hitting walls?
            enemy.recent_positions.append((enemy.x, enemy.y))
            if len(enemy.recent_positions) > 30:
                enemy.recent_positions.pop(0)

            if not is_walkable(game_map, enemy.x, enemy.y):
                enemy.x = old_x
                enemy.y = old_y

            moved_dist = math.sqrt((enemy.x - old_x) ** 2 + (enemy.y - old_y) ** 2)
            
            moving_intent = False
            if outputs:
                if abs(outputs[0] - outputs[1]) > 0.1 or abs(outputs[5]) > 0.1:
                    moving_intent = True
            elif enemy.state == EnemyState.PATROL:
                moving_intent = True

            min_move_threshold = 0.01 + enemy.speed * dt * 0.2
            if moving_intent and moved_dist < min_move_threshold:
                enemy.stuckTimer += dt
            else:
                enemy.stuckTimer = max(0, enemy.stuckTimer - dt * 2)

            corner_stuck = False
            if len(enemy.recent_positions) >= 30:
                start_p = enemy.recent_positions[0]
                end_p = enemy.recent_positions[-1]
                total_m = math.sqrt((end_p[0] - start_p[0])**2 + (end_p[1] - start_p[1])**2)
                corner_stuck = total_m < 0.4 and moving_intent

            st_threshold = 0.4 if enemy.speed > 3.0 else 0.8
            if enemy.stuckTimer > st_threshold or corner_stuck:
                back_dist = enemy.speed * dt * 2.5
                back_x = enemy.x - math.cos(enemy.angle) * back_dist
                back_y = enemy.y - math.sin(enemy.angle) * back_dist
                if is_walkable(game_map, back_x, back_y):
                    enemy.x = back_x
                    enemy.y = back_y
                
                t_options = [math.pi/2, -math.pi/2, math.pi, math.pi/4, -math.pi/4]
                random.shuffle(t_options)
                for turn in t_options:
                    test_a = enemy.angle + turn
                    test_x = enemy.x + math.cos(test_a) * enemy.speed * dt
                    test_y = enemy.y + math.sin(test_a) * enemy.speed * dt
                    if is_walkable(game_map, test_x, test_y):
                        enemy.angle = test_a
                        break
                else:
                    enemy.angle += random.uniform(-math.pi, math.pi)
                
                enemy.stuckTimer = 0
                enemy.recent_positions.clear()

            eff_cooldown = enemy.shootCooldown
            eff_damage = enemy.damage * stat_mult
            eff_accuracy = min(1.0, enemy.accuracy * stat_mult)

            enemy.shootTimer -= dt

            should_shoot = (
                shoot_val > 0.4
                and enemy.canSeePlayer
                and enemy.reactionTimer <= 0
                and enemy.shootTimer <= 0
                and enemy.distanceToPlayer < attack_radius
                and eff_damage > 0
            )

            if should_shoot:
                enemy.shootTimer = eff_cooldown
                if enemy_idx < len(self.bullets_fired):
                    self.bullets_fired[enemy_idx] += 1

                spr_val = (1 - eff_accuracy) * 0.35
                aim_a = math.atan2(player.y - enemy.y, player.x - enemy.x)
                fin_a = aim_a + (random.random() - 0.5) * spr_val

                self.bullets.append(
                    Bullet(
                        id=_bullet_id_counter,
                        x=enemy.x,
                        y=enemy.y,
                        angle=fin_a,
                        speed=BULLET_SPEED * 0.8,
                        damage=int(eff_damage),
                        fromPlayer=False,
                        life=2.0,
                    )
                )
                _bullet_id_counter += 1
                self._spawn_muzzle_particles(enemy.x, enemy.y, fin_a)

            if enemy.strafeTimer > 0:
                enemy.strafeTimer -= dt
            else:
                enemy.strafeDir *= -1
                if enemy.enemyClass == EnemyClass.SCOUT:
                    enemy.strafeTimer = 0.2 + random.random() * 0.5
                else:
                    enemy.strafeTimer = 0.6 + random.random() * 1.2

    def _build_nn_inputs(self, enemy, player):
        n_dist = min(1, enemy.distanceToPlayer / 20)
        a_diff = normalize_angle(enemy.angleToPlayer - enemy.angle) / math.pi
        c_see = 1 if enemy.canSeePlayer else 0
        h_ratio = enemy.health / enemy.maxHealth if enemy.maxHealth > 0 else 0
        p_angle = normalize_angle(math.atan2(enemy.y-player.y, enemy.x-player.x) - player.angle) / math.pi
        dx = (enemy.lastKnownPlayerX - enemy.x) / 20
        dy = (enemy.lastKnownPlayerY - enemy.y) / 20
        strf = enemy.strafeDir

        return [n_dist, a_diff, c_see, h_ratio, p_angle, dx, dy, strf]

    def _move_enemy(self, enemy, game_map, dt, outputs, player):
        if enemy.state == EnemyState.DEAD:
            return

        if enemy.state == EnemyState.PATROL:
            enemy.roamTimer += dt
            if enemy.roamTimer > 2.0:
                enemy.angle += (random.random() - 0.5) * 0.7
                enemy.roamTimer = 0.0
            f_amt = enemy.speed * dt * 0.5
            s_amt = 0
            t_x = math.cos(enemy.angle)
            t_y = math.sin(enemy.angle)
        else:
            move_f = outputs[0]
            move_b = outputs[1]
            strf_o = outputs[5]
            t_x = math.cos(enemy.angleToPlayer)
            t_y = math.sin(enemy.angleToPlayer)
            f_amt = (move_f - move_b) * enemy.speed * dt
            s_amt = strf_o * enemy.speed * dt

        p_x = -t_y
        p_y = t_x
        vx = t_x * f_amt + p_x * s_amt
        vy = t_y * f_amt + p_y * s_amt

        mgn = 0.4 + enemy.speed * 0.1
        nx = enemy.x + vx
        ny = enemy.y + vy
        
        # collision checks. i'm done with these.
        mov = False
        if is_walkable(game_map, nx + (1 if vx > 0 else -1 if vx < 0 else 0) * mgn, enemy.y):
            enemy.x = nx
            mov = True
        
        if is_walkable(game_map, enemy.x, ny + (1 if vy > 0 else -1 if vy < 0 else 0) * mgn):
            enemy.y = ny
            mov = True

        if not mov and enemy.state != EnemyState.PATROL:
             enemy.stuckTimer += dt

    def _update_bullets(self, dt):
        # iterate backwards or things blow up
        for i in range(len(self.bullets) - 1, -1, -1):
            b = self.bullets[i]
            b.life -= dt
            b.x += math.cos(b.angle) * b.speed * dt
            b.y += math.sin(b.angle) * b.speed * dt

            hit = False
            if not is_walkable(self.map, b.x, b.y):
                self._spawn_hit_particles(b.x, b.y, (255, 102, 0))
                hit = True

            if not hit and b.fromPlayer:
                for enemy_idx, enemy in enumerate(self.enemies):
                    if enemy.state == EnemyState.DEAD:
                        continue
                    dx, dy = enemy.x - b.x, enemy.y - b.y
                    if dx*dx + dy*dy < 0.6:
                        enemy.health -= b.damage
                        self._spawn_hit_particles(b.x, b.y, (255, 34, 0))
                        hit = True
                        if enemy_idx < len(self.damage_dealt):
                            self.damage_dealt[enemy_idx] += b.damage
                        if enemy.health <= 0:
                            enemy.state = EnemyState.DEAD
                            self.score += 100 * self.round
                            self.money += max(1, int(self.round * 1.5))
                            self._spawn_death_particles(enemy.x, enemy.y)
                            if enemy_idx < len(self.fitnesses):
                                self.fitnesses[enemy_idx] += 60
                        break

            if not hit and not b.fromPlayer:
                dx, dy = self.player.x - b.x, self.player.y - b.y
                if dx*dx + dy*dy < 0.6:
                    dmg = b.damage
                    if self.player.armor > 0:
                        red = min(self.player.armor * 0.1, 0.75)
                        dmg = int(dmg * (1 - red))
                    self.player.health -= dmg
                    self.flash_alpha = min(1, self.flash_alpha + 0.35)
                    hit = True
                    for fi in range(len(self.enemies)):
                        if self.enemies[fi].state != EnemyState.DEAD:
                            self.fitnesses[fi] += b.damage * 0.7
                    if self.player.health <= 0:
                        self.player.health = 0
                        self.phase = GamePhase.DEAD

            if hit or b.life <= 0:
                self.bullets.pop(i)

        # bullet cap. too many bullets = lag.
        if len(self.bullets) > 40:
           self.bullets = self.bullets[-40:]

    def _update_particles(self, dt):
        for i in range(len(self.particles) - 1, -1, -1):
            p = self.particles[i]
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vx *= 0.94
            p.vy *= 0.94
            p.life -= dt
            if p.life <= 0:
                self.particles.pop(i)

    def _check_round_end(self):
        if self.phase != GamePhase.PLAYING:
            return
        
        all_d = True
        for e in self.enemies:
            if e.state != EnemyState.DEAD:
                all_d = False
                break
        
        if all_d:
            self.phase = GamePhase.ROUND_END
            for fi in range(len(self.enemies)):
                # messy fitness math.
                d_bonus = (self.damage_dealt[fi] if fi < len(self.damage_dealt) else 0) * 1.2
                v_bonus = (self.time_spent_seeing_player[fi] if fi < len(self.time_spent_seeing_player) else 0) * 2.5
                s_bonus = (self.bullets_fired[fi] if fi < len(self.bullets_fired) else 0) * 5.0
                self.fitnesses[fi] += d_bonus + v_bonus + s_bonus
                
                en = self.enemies[fi]
                d_err = abs(en.distanceToPlayer - 10)
                self.fitnesses[fi] += max(0, 15 - d_err) * 1.5

    def evolve_genomes(self, m_round):
        m_rate = MUTATION_RATE_BASE + (-0.02 if m_round > 5 else 0.008 * (5 - m_round))
        m_scale = MUTATION_SCALE_BASE * max(0.15, 1 - m_round * 0.08)
        new_pools = {}

        for c_key in CLASS_GENOME_KEYS:
            c_indices = [i for i, e in enumerate(self.enemies) if e.enemyClass.value == c_key]
            c_genomes = [self.enemies[i].genome for i in c_indices]
            c_fits = [self.fitnesses[i] for i in c_indices]

            if len(c_genomes) < 2:
                # just mutate what we have i guess
                new_pools[c_key] = [mutate(g, m_rate, m_scale) for g in c_genomes]
                continue

            # sort by fitness. elitism.
            pairs = [{"genome": g, "fitness": f} for g, f in zip(c_genomes, c_fits)]
            pairs.sort(key=lambda x: x["fitness"], reverse=True)

            new_pop = []
            for i in range(min(ELITE_COUNT, len(pairs))):
                new_pop.append(list(pairs[i]["genome"]))

            while len(new_pop) < POPULATION_SIZE:
                p1 = _tournament_select(pairs, 3)
                p2 = _tournament_select(pairs, 3)
                ch = crossover(p1["genome"], p2["genome"])
                ch = mutate(ch, m_rate, m_scale)
                new_pop.append(ch)

            new_pools[c_key] = new_pop

        # log history. why do i keep track of this?
        all_f = self.fitnesses
        m_fit = max(all_f) if all_f else 0
        a_fit = sum(all_f) / len(all_f) if all_f else 0
        self.generation_history.append(Generation(round=self.round, bestFitness=m_fit, avgFitness=a_fit, population=POPULATION_SIZE * len(CLASS_GENOME_KEYS)))

        return new_pools

    def _spawn_muzzle_particles(self, x, y, angle):
        for _ in range(1):
            spd = 1.5 + random.random()
            self.particles.append(Particle(x=x, y=y, vx=math.cos(angle)*spd, vy=math.sin(angle)*spd, life=0.1, maxLife=0.13, color=(255, 221, 68), size=0.04))

    def _spawn_hit_particles(self, x, y, col):
        # todo: add more particles if not on a chromebook
        for _ in range(3):
            a = random.random() * math.pi * 2
            s = 1 + random.random() * 2
            self.particles.append(Particle(x=x, y=y, vx=math.cos(a)*s, vy=math.sin(a)*s, life=0.3, maxLife=0.4, color=col, size=0.05))

    def _spawn_death_particles(self, x, y):
        # death is messy.
        for _ in range(8):
            a = random.random() * math.pi * 2
            s = 1 + random.random() * 4
            self.particles.append(Particle(x=x, y=y, vx=math.cos(a)*s, vy=math.sin(a)*s, life=0.7, maxLife=1.0, color=(255, 34, 0), size=0.1))
