"""Seleção de destinos de exploração baseada em novidade espacial e rotas viáveis."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from random import Random

from environment.world import World
from agents.navigation.bfs import Position

Pathfinder = Callable[[World, Position, Position], list[Position] | None]


def choose_exploration_waypoint(
    world: World,
    start: Position,
    pathfinder: Pathfinder,
    rng: Random,
    visit_counts: Mapping[Position, int],
    recent_positions: Sequence[Position] = (),
    *,
    min_distance: int | None = None,
    max_distance: int | None = None,
    candidate_limit: int = 24,
) -> tuple[Position, list[Position]] | None:
    """Escolhe um waypoint distante, pouco visitado e alcançável.

    A amostragem limita o custo em mapas grandes. O destino é pontuado pela
    novidade da vizinhança, pela distância e pela recência; só depois são
    calculadas rotas para os melhores candidatos.
    """
    sx, sy = start
    world_span = max(world.width, world.height)
    min_distance = min_distance if min_distance is not None else max(8, world_span // 8)
    max_distance = max_distance if max_distance is not None else max(min_distance + 1, world_span // 2)
    max_distance = min(max_distance, world.width + world.height - 2)
    if max_distance <= min_distance:
        min_distance = max(1, max_distance // 2)
    recent = set(recent_positions)

    options: list[tuple[float, Position]] = []
    # Amostragem direta evita percorrer e pontuar cada célula do mapa em todo
    # passo de cada agente. A deduplicação preserva uma lista curta de destinos.
    sampled_positions: set[Position] = set()
    attempts = max(64, candidate_limit * 3)
    for _ in range(attempts):
        pos = (rng.randrange(world.width), rng.randrange(world.height))
        if pos in sampled_positions:
            continue
        sampled_positions.add(pos)
        x, y = pos
        distance = abs(x - sx) + abs(y - sy)
        if pos == start or pos in recent or not world.is_walkable(*pos):
            continue
        if not min_distance <= distance <= max_distance:
            continue

        local_visits = 0.0
        local_cells = 0
        for vy in range(max(0, y - 6), min(world.height, y + 7)):
            remaining = 6 - abs(vy - y)
            for vx in range(max(0, x - remaining), min(world.width, x + remaining + 1)):
                visits = visit_counts.get((vx, vy), 0)
                if visits:
                    local_distance = abs(vx - x) + abs(vy - y)
                    local_visits += visits / (1.0 + local_distance)
                    local_cells += 1
        novelty = 1.0 / (1.0 + local_visits + 0.15 * local_cells)
        distance_value = min(1.0, distance / max(1.0, max_distance))
        # Aumenta o peso da novidade espacial para evitar patrulhas em bolsões
        # já percorridos; mantém preferência por destinos distantes e desempate
        # estocástico pequeno para não sincronizar todos os indivíduos.
        score = 0.75 * novelty + 0.20 * distance_value + 0.05 * rng.random()
        options.append((score, pos))

    if not options:
        return None
    options.sort(key=lambda item: item[0], reverse=True)
    # Randomiza empates sem destruir a preferência por novidade.
    best = options[: max(candidate_limit * 3, candidate_limit)]
    rng.shuffle(best)
    best.sort(key=lambda item: item[0], reverse=True)

    for _, target in best[:candidate_limit]:
        path = pathfinder(world, start, target)
        if path and len(path) > 1:
            return target, path
    return None
