import random

from random import Random
from collections.abc import Callable

from environment.cell import Cell
from environment.world import World
from agents.navigation.bfs import find_path
from agents.needs import AgentNeeds
from environment.resources import Water
from agents.species import Species


Position = tuple[int, int]

Pathfinder = Callable[
    [World, Position, Position],
    list[Position] | None,
]


class Agent:
    def __init__(
        self,
        x: int,
        y: int,
        max_energy: float = 100.0,
        vision_radius: int = 4,
        rng: Random | None = None,
        needs: AgentNeeds | None = None,
        species: Species = Species.HUMAN,
    ):
        if vision_radius < 0:
            raise ValueError("vision_radius não pode ser negativo")

        self.x = x
        self.y = y
        self.species = Species(species)
        self.hunt_target: Position | None = None
        self.running = False

        self.target: Position | None = None
        self.path: list[Position] = []

        self.needs = needs if needs is not None else AgentNeeds(
            max_energy=max_energy,
            energy=max_energy,
        )
        self.alive = self.needs.alive

        self.vision_radius = vision_radius
        self.visit_counts: dict[Position, int] = {}

        self.rng = rng if rng is not None else random

    @property
    def max_energy(self) -> float:
        return self.needs.max_energy

    @max_energy.setter
    def max_energy(self, value: float) -> None:
        self.needs.max_energy = value
        self.needs.energy = min(self.needs.energy, value)

    @property
    def energy(self) -> float:
        return self.needs.energy

    @energy.setter
    def energy(self, value: float) -> None:
        self.needs.energy = max(0.0, min(self.needs.max_energy, value))

    @property
    def health(self) -> float:
        return self.needs.health

    @property
    def hunger(self) -> float:
        return self.needs.hunger

    @property
    def thirst(self) -> float:
        return self.needs.thirst

    def rest(self, amount: float = 5.0) -> None:
        if self.alive:
            self.needs.restore_energy(amount)

    def consume_energy(self, amount: float = 1.0) -> None:
        if not self.alive:
            return

        self.energy = max(0.0, self.energy - amount)

        # Energia é estamina: chegar a zero impede corrida, mas não mata.

    def eat(self, amount: float) -> None:
        if not self.alive:
            return

        self.needs.eat(amount)
        self.needs.restore_energy(amount * 0.6)

    def _clear_target(self) -> None:
        self.target = None
        self.path.clear()

    def _select_target(
        self,
        nearby_cells: list[Cell],
        world: World,
        pathfinder: Pathfinder,
    ) -> None:
        current_position = (self.x, self.y)

        if self.hunt_target is not None:
            path = pathfinder(world, current_position, self.hunt_target)
            if path is not None and len(path) > 1:
                self.target = self.hunt_target
                self.path = path
                return
            self.hunt_target = None

        # Necessidades competem por prioridade. Cada categoria é tentada em
        # ordem; se todos os alvos estiverem inacessíveis, tenta-se a próxima.
        target_groups: list[list[Position]] = []
        if self.thirst >= 40.0:
            target_groups.append(world.get_water_positions())
        food_positions = [
            (cell.x, cell.y)
            for row in world.grid
            for cell in row
            if cell.resource is not None
            and cell.resource.is_collectible
            and (cell.x, cell.y) != current_position
        ]
        target_groups.append(food_positions)
        if 25.0 <= self.thirst < 40.0:
            target_groups.append(world.get_water_positions())

        for candidates in target_groups:
            candidates = list(candidates)
            self.rng.shuffle(candidates)
            candidates.sort(
                key=lambda position: abs(position[0] - self.x) + abs(position[1] - self.y)
            )
            for candidate in candidates:
                path = pathfinder(world, current_position, candidate)
                if path is not None and len(path) > 1:
                    self.target = candidate
                    self.path = path
                    return

        self._clear_target()

    def choose_action(
        self,
        nearby_cells: list[Cell],
        world: World,
        pathfinder: Pathfinder = find_path,
    ) -> Position:
        self._record_position()
        current_position = (self.x, self.y)
        if self.thirst >= 1.0 and isinstance(world.get_cell(*current_position).resource, Water):
            return (0, 0)

        # O agente chegou ao destino.
        if self.target == current_position:
            self._clear_target()

        # Sede alta invalida um alvo de comida para permitir procurar água.
        if self.thirst >= 40.0 and self.target is not None:
            target_cell = world.get_cell(*self.target)
            if not isinstance(target_cell.resource, Water):
                self._clear_target()

        # Escolhe um alvo e calcula uma rota quando necessário.
        if self.target is None or not self.path:
            self._select_target(
                nearby_cells,
                world,
                pathfinder,
            )

        # Descarta a posição atual do início da rota.
        if self.path and self.path[0] == current_position:
            self.path.pop(0)

        # Executa o próximo movimento da rota.
        if self.path:
            next_x, next_y = self.path[0]

            return (
                next_x - self.x,
                next_y - self.y,
            )

        return self._choose_exploration_action(world)
    
    def _record_position(self) -> None:
        position = (self.x, self.y)
        self.visit_counts[position] = self.visit_counts.get(position, 0) + 1


    def _choose_exploration_action(self, world: World) -> Position:
        possible_actions = [
            (0, -1),
            (0, 1),
            (-1, 0),
            (1, 0),
        ]

        candidates = []

        for dx, dy in possible_actions:
            next_position = (self.x + dx, self.y + dy)

            if not world.is_walkable(*next_position):
                continue

            score = self._exploration_score(next_position)
            candidates.append(((dx, dy), score))

        if not candidates:
            return (0, 0)

        # Menor pontuação significa uma região menos explorada.
        min_score = min(score for _, score in candidates)

        least_explored = [
            action
            for action, score in candidates
            if score == min_score
        ]

        return self.rng.choice(least_explored)

    def _exploration_score(
        self,
        position: Position,
        radius: int = 2,
    ) -> float:
        center_x, center_y = position
        score = 0.0

        for (x, y), visits in self.visit_counts.items():
            distance = abs(x - center_x) + abs(y - center_y)

            if distance <= radius:
                # Visitas próximas pesam mais do que visitas distantes.
                score += visits / (distance + 1)

        return score
