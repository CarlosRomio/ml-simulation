
import random

from random import Random

from environment.cell import Cell
from environment.obstacles import ObstacleType
from environment.resources import Plant, PlantState


class World:
    def __init__(
        self,
        width: int = 10,
        height: int = 10,
        food_count: int = 10,
        obstacle_count: int = 0,
        reserved_cells: set[tuple[int, int]] | None = None,
        rng: Random | None = None,
    ):
        if width < 1 or height < 1:
            raise ValueError("As dimensões do mundo devem ser positivas.")

        if food_count < 0 or obstacle_count < 0:
            raise ValueError("Comida e obstáculos não podem ser negativos.")

        self.width = width
        self.height = height

        self.grid = [
            [Cell(x=x, y=y) for x in range(width)]
            for y in range(height)
        ]

        self.reserved_cells = (
            reserved_cells if reserved_cells is not None else set()
        )
        self.rng = rng if rng is not None else random

        for x, y in self.reserved_cells:
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError(
                    f"Célula reservada fora do mundo: ({x}, {y})"
                )

        if food_count + obstacle_count + len(self.reserved_cells) > (
            width * height
        ):
            raise ValueError(
                "Não há células suficientes para comida, "
                "obstáculos e posições reservadas."
            )

        self._place_food(food_count)
        self._place_obstacles(obstacle_count)

    def _place_food(self, food_count: int) -> None:
        available_cells = [
            cell
            for row in self.grid
            for cell in row
            if (cell.x, cell.y) not in self.reserved_cells
        ]

        if food_count > len(available_cells):
            raise ValueError(
                "A quantidade de comida excede "
                "o número de células disponíveis."
            )

        for cell in self.rng.sample(available_cells, food_count):
            cell.resource = Plant(state=PlantState.MATURE)

    def _place_obstacles(self, obstacle_count: int) -> None:
        available_cells = [
            cell
            for row in self.grid
            for cell in row
            if cell.resource is None
            and cell.obstacle is None
            and (cell.x, cell.y) not in self.reserved_cells
        ]

        if obstacle_count > len(available_cells):
            raise ValueError(
                "A quantidade de obstáculos excede "
                "o número de células disponíveis."
            )

        obstacle_types = list(ObstacleType)

        for cell in self.rng.sample(available_cells, obstacle_count):
            cell.obstacle = self.rng.choice(obstacle_types)

    def get_cell(self, x: int, y: int) -> Cell:
        if not (0 <= x < self.width):
            raise IndexError(f"Coordenada x inválida: {x}")

        if not (0 <= y < self.height):
            raise IndexError(f"Coordenada y inválida: {y}")

        return self.grid[y][x]

    def move_agent(self, agent, action: tuple[int, int]) -> bool:
        dx, dy = action

        if action not in {
            (0, -1),
            (0, 1),
            (-1, 0),
            (1, 0),
        }:
            raise ValueError(f"Ação inválida: {action}")

        new_x = agent.x + dx
        new_y = agent.y + dy

        if not self.is_walkable(new_x, new_y):
            return False

        agent.x = new_x
        agent.y = new_y

        return True

    def get_nearby_cells(
        self,
        x: int,
        y: int,
        radius: int = 1,
    ) -> list[Cell]:
        if radius < 0:
            raise ValueError("radius não pode ser negativo")

        nearby_cells = []

        min_x = max(0, x - radius)
        max_x = min(self.width - 1, x + radius)
        min_y = max(0, y - radius)
        max_y = min(self.height - 1, y + radius)

        for cell_y in range(min_y, max_y + 1):
            for cell_x in range(min_x, max_x + 1):
                if self._has_line_of_sight(x, y, cell_x, cell_y):
                    nearby_cells.append(self.get_cell(cell_x, cell_y))

        return nearby_cells

    def collect_resource(self, x: int, y: int):
        cell = self.get_cell(x, y)
        resource = cell.resource

        if resource is None or not resource.is_collectible:
            return None

        cell.resource = None
        return resource

    def advance_resources(self) -> None:
        """Avança o ciclo de vida dos recursos presentes no mundo."""
        for row in self.grid:
            for cell in row:
                resource = cell.resource

                if isinstance(resource, Plant):
                    resource.advance()

    def get_plant_counts(self) -> dict[str, int]:
        """Retorna a quantidade de plantas em cada estágio."""
        counts = {
            "seeds": 0,
            "growing": 0,
            "mature": 0,
            "total": 0,
        }

        for row in self.grid:
            for cell in row:
                plant = cell.resource

                if not isinstance(plant, Plant):
                    continue

                counts["total"] += 1

                if plant.state == PlantState.SEED:
                    counts["seeds"] += 1
                elif plant.state == PlantState.GROWING:
                    counts["growing"] += 1
                elif plant.state == PlantState.MATURE:
                    counts["mature"] += 1

        return counts

    def spawn_seeds(
        self,
        count: int = 1,
        max_plants: int = 100,
        occupied_cells: set[tuple[int, int]] | None = None,
    ) -> int:
        """Gera sementes em células elegíveis.

        Retorna a quantidade de sementes efetivamente geradas.
        """
        if count < 0:
            raise ValueError("A quantidade de sementes não pode ser negativa.")

        if max_plants < 0:
            raise ValueError("max_plants não pode ser negativo.")

        occupied_cells = occupied_cells or set()

        existing_plants = sum(
            isinstance(cell.resource, Plant)
            for row in self.grid
            for cell in row
        )

        available_capacity = max_plants - existing_plants
        seeds_to_spawn = min(count, max(0, available_capacity))

        available_cells = [
            cell
            for row in self.grid
            for cell in row
            if cell.resource is None
            and cell.obstacle is None
            and (cell.x, cell.y) not in self.reserved_cells
            and (cell.x, cell.y) not in occupied_cells
        ]

        seeds_to_spawn = min(seeds_to_spawn, len(available_cells))

        selected_cells = self.rng.sample(
            available_cells,
            seeds_to_spawn,
        )

        for cell in selected_cells:
            cell.resource = Plant()

        return len(selected_cells)

    def _has_line_of_sight(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
    ) -> bool:
        """Verifica se existe uma linha de visão livre entre duas células."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)

        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1

        error = dx - dy
        x, y = x0, y0

        while (x, y) != (x1, y1):
            double_error = 2 * error

            if double_error > -dy:
                error -= dy
                x += sx

            if double_error < dx:
                error += dx
                y += sy

            if (x, y) == (x1, y1):
                break

            if self.get_cell(x, y).obstacle is not None:
                return False

        return True

    def is_walkable(self, x: int, y: int) -> bool:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False

        return self.get_cell(x, y).is_walkable
