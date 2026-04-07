from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import math


class EnemyState(Enum):
    IDLE = "idle"
    PATROL = "patrol"
    CHASE = "chase"
    ATTACK = "attack"
    STRAFE = "strafe"
    FLANK = "flank"
    DEAD = "dead"


class GamePhase(Enum):
    MENU = "menu"
    PLAYING = "playing"
    DEAD = "dead"
    ROUND_END = "roundEnd"
    EVOLVING = "evolving"
    SHOP = "shop"


class EnemyClass(Enum):
    TANK = "tank"
    SCOUT = "scout"
    REGULAR = "regular"


class PickupType(Enum):
    HEALTH = "health"
    AMMO = "ammo"


class ShopPhase(Enum):
    NONE = "none"
    SHOP = "shop"
    UPGRADE = "upgrade"


class ShopItemType(Enum):
    MAX_HEALTH = "max_health"
    MAX_SPEED = "max_speed"
    ARMOR = "armor"
    WEAPON_RAPID = "weapon_rapid"
    WEAPON_SPREAD = "weapon_spread"
    REVIVE = "revive"


@dataclass
class Vec2:
    x: float
    y: float


@dataclass
class Ray:
    angle: float
    distance: float
    wallType: int
    side: int
    mapX: int
    mapY: int


@dataclass
class Player:
    x: float
    y: float
    angle: float
    health: int
    maxHealth: int
    ammo: int
    maxAmmo: int
    speed: float
    turnSpeed: float
    isShooting: bool
    isPunching: bool
    shootCooldown: float
    punchCooldown: float
    armor: int = 0
    weaponType: str = "default"
    weaponLevel: int = 1
    baseSpeed: float = 3.5
    baseMaxHealth: int = 100
    baseMaxAmmo: int = 80


@dataclass
class NeuralNetwork:
    layers: List[int]
    weights: List[List[List[float]]]
    biases: List[List[float]]


@dataclass
class Enemy:
    id: int
    x: float
    y: float
    angle: float
    health: int
    maxHealth: int
    speed: float
    state: EnemyState
    enemyClass: EnemyClass
    shootCooldown: float
    shootTimer: float
    alertRadius: float
    attackRadius: float
    damage: int
    brain: NeuralNetwork
    genome: List[float]
    distanceToPlayer: float
    angleToPlayer: float
    canSeePlayer: bool
    strafeDir: int
    strafeTimer: float
    dodgeTimer: float
    lastKnownPlayerX: float
    lastKnownPlayerY: float
    accuracy: float
    reactionTime: float
    reactionTimer: float
    flankAngle: float
    stuckTimer: float


@dataclass
class Bullet:
    id: int
    x: float
    y: float
    angle: float
    speed: float
    damage: int
    fromPlayer: bool
    life: float


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    maxLife: float
    color: tuple
    size: float


@dataclass
class Pickup:
    x: float
    y: float
    pickupType: PickupType
    amount: int
    active: bool


@dataclass
class GameMap:
    width: int
    height: int
    cells: List[List[int]]
    spawnX: float
    spawnY: float
    enemySpawns: List[Vec2]


@dataclass
class Generation:
    round: int
    bestFitness: float
    avgFitness: float
    population: int


ENEMY_CLASS_CONFIG = {
    EnemyClass.TANK: {
        "hp": 200,
        "speed": 1.2,
        "damage": 30,
        "shootCooldown": 2.0,
        "accuracy": 0.3,
        "minimapColor": (255, 34, 0),
    },
    EnemyClass.SCOUT: {
        "hp": 40,
        "speed": 4.2,
        "damage": 8,
        "shootCooldown": 0.3,
        "accuracy": 0.6,
        "minimapColor": (255, 255, 0),
    },
}

CLASS_GENOME_KEYS = ["tank", "scout"]

POPULATION_SIZE = 3
ELITE_COUNT = 1
MUTATION_RATE_BASE = 0.05
MUTATION_SCALE_BASE = 0.3

LAYER_SIZES = [8, 12, 8, 6]


def get_genome_size() -> int:
    size = 0
    for l in range(1, len(LAYER_SIZES)):
        size += LAYER_SIZES[l] * (LAYER_SIZES[l - 1] + 1)
    return size


def normalize_angle(a: float) -> float:
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a
