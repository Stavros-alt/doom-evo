import math
import random
from game_types import NeuralNetwork, LAYER_SIZES


def create_network(genome=None):
    layers = LAYER_SIZES
    weights = []
    biases = []
    g_idx = 0
    g = genome if genome is not None else random_genome()

    for l in range(1, len(layers)):
        layer_weights = []
        layer_biases = []
        for n in range(layers[l]):
            neuron_weights = []
            for p in range(layers[l - 1]):
                neuron_weights.append(
                    g[g_idx] if g_idx < len(g) else random.uniform(-1, 1)
                )
                g_idx += 1
            layer_weights.append(neuron_weights)
            layer_biases.append(g[g_idx] if g_idx < len(g) else random.uniform(-1, 1))
            g_idx += 1
        weights.append(layer_weights)
        biases.append(layer_biases)

    return NeuralNetwork(layers=layers, weights=weights, biases=biases)


def random_genome():
    genome = []
    for l in range(1, len(LAYER_SIZES)):
        for n in range(LAYER_SIZES[l]):
            for p in range(LAYER_SIZES[l - 1]):
                genome.append(random.uniform(-1, 1))
            genome.append(random.uniform(-1, 1))
    return genome


def get_genome_size():
    size = 0
    for l in range(1, len(LAYER_SIZES)):
        size += LAYER_SIZES[l] * (LAYER_SIZES[l - 1] + 1)
    return size


def _relu(x):
    return max(0, x)


def _sigmoid(x):
    if x > 500:
        return 1.0
    if x < -500:
        return 0.0
    return 1 / (1 + math.exp(-x))


def forward_pass(network, inputs):
    activations = list(inputs)

    for l in range(len(network.weights)):
        new_activations = []
        for n in range(len(network.weights[l])):
            s = network.biases[l][n]
            for p in range(len(activations)):
                s += activations[p] * network.weights[l][n][p]
            is_output = l == len(network.weights) - 1
            new_activations.append(_sigmoid(s) if is_output else _relu(s))
        activations = new_activations

    return activations


def genome_to_network(genome):
    return create_network(genome)


def network_to_genome(network):
    genome = []
    for l in range(len(network.weights)):
        for n in range(len(network.weights[l])):
            for p in range(len(network.weights[l][n])):
                genome.append(network.weights[l][n][p])
            genome.append(network.biases[l][n])
    return genome


def crossover(parent1, parent2):
    child = []
    cross_point = random.randint(0, len(parent1) - 1)
    for i in range(len(parent1)):
        if random.random() < 0.7:
            child.append(parent1[i] if i < cross_point else parent2[i])
        else:
            alpha = random.random()
            child.append(alpha * parent1[i] + (1 - alpha) * parent2[i])
    return child


def _gaussian_random():
    u = random.random()
    while u == 0:
        u = random.random()
    v = random.random()
    while v == 0:
        v = random.random()
    return math.sqrt(-2.0 * math.log(u)) * math.cos(2.0 * math.pi * v)


def mutate(genome, mutation_rate, mutation_scale):
    result = []
    for g in genome:
        if random.random() < mutation_rate:
            delta = _gaussian_random() * mutation_scale
            if random.random() < 0.05:
                result.append(random.uniform(-1, 1))
            else:
                result.append(max(-3, min(3, g + delta)))
        else:
            result.append(g)
    return result


def evolve_population(genomes, fitnesses, mutation_rate, mutation_scale, elite_count):
    paired = [{"genome": g, "fitness": f} for g, f in zip(genomes, fitnesses)]
    paired.sort(key=lambda x: x["fitness"], reverse=True)

    new_pop = []

    for i in range(min(elite_count, len(paired))):
        new_pop.append(list(paired[i]["genome"]))

    while len(new_pop) < len(genomes):
        p1 = _tournament_select(paired, 3)
        p2 = _tournament_select(paired, 3)
        child = crossover(p1["genome"], p2["genome"])
        child = mutate(child, mutation_rate, mutation_scale)
        new_pop.append(child)

    return new_pop


def _tournament_select(population, k):
    best = population[random.randint(0, len(population) - 1)]
    for _ in range(1, k):
        candidate = population[random.randint(0, len(population) - 1)]
        if candidate["fitness"] > best["fitness"]:
            best = candidate
    return best


def dampen_outputs(outputs, dampen_factor):
    return [o * (1 - dampen_factor) + 0.5 * dampen_factor for o in outputs]
