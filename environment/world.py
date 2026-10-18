
import random
from math import isfinite

from random import Random

from environment.cell import Cell
from environment.obstacles import ObstacleType
from environment.resources import MaterialKind, MaterialResource, Plant, PlantState, Water, Food
from environment.storage import Storage
from environment.shelter import Shelter


class World:
    def __init__(
        self,
        width: int = 10,
        height: int = 10,
        food_count: int = 10,
        obstacle_count: int = 0,
        reserved_cells: set[tuple[int, int]] | None = None,
        rng: Random | None = None,
        water_count: int = 0,
        wood_count: int = 0,
        stone_count: int = 0,
    ):
        if width < 1 or height < 1:
            raise ValueError("As dimensões do mundo devem ser positivas.")

        if min(food_count, obstacle_count, water_count, wood_count, stone_count) < 0:
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

        if food_count + obstacle_count + water_count + wood_count + stone_count + len(self.reserved_cells) > (
            width * height
        ):
            raise ValueError(
                "Não há células suficientes para recursos, obstáculos "
                "e posições reservadas."
            )

        self._place_food(food_count)
        self._place_obstacles(obstacle_count)
        self._place_water(water_count)
        self._place_materials(MaterialKind.WOOD, wood_count)
        self._place_materials(MaterialKind.STONE, stone_count)

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

    def _place_water(self, water_count: int) -> None:
        available_cells = [
            cell for row in self.grid for cell in row
            if cell.resource is None and cell.obstacle is None
            and (cell.x, cell.y) not in self.reserved_cells
        ]
        if water_count > len(available_cells):
            raise ValueError("Não há células suficientes para fontes de água.")
        for cell in self.rng.sample(available_cells, water_count):
            cell.resource = Water()

    def _place_materials(self, kind: MaterialKind, count: int) -> None:
        available_cells = [
            cell for row in self.grid for cell in row
            if cell.resource is None and cell.obstacle is None
            and (cell.x, cell.y) not in self.reserved_cells
        ]
        if count > len(available_cells):
            raise ValueError(f"Não há células suficientes para {kind.value}.")
        for cell in self.rng.sample(available_cells, count):
            # Cada depósito tem uma quantidade variável, para não tornar
            # todos os pontos de coleta idênticos. A semente do mundo controla isso.
            cell.resource = MaterialResource(kind=kind, quantity=self.rng.randint(2, 5))

    def place_storage(self, x: int, y: int, storage: Storage | None = None) -> Storage:
        """Coloca um abrigo com armazenamento compartilhado em célula caminhável."""
        cell = self.get_cell(x, y)
        if cell.obstacle is not None:
            raise ValueError("Não é possível colocar um depósito sobre um obstáculo.")
        if cell.structure is not None:
            raise ValueError("Já existe uma estrutura nesta célula.")
        # O ponto de armazenamento padrão agora é um abrigo completo.
        # Estruturas Storage explicitamente fornecidas continuam aceitas para
        # compatibilidade com cenários e testes especializados.
        cell.structure = storage if storage is not None else Shelter()
        return cell.structure

    def get_storage_positions(self) -> list[tuple[int, int]]:
        return [
            (cell.x, cell.y)
            for row in self.grid for cell in row
            if isinstance(cell.structure, Storage)
        ]

    def get_storage_counts(self) -> dict[str, float]:
        storages = [
            cell.structure for row in self.grid for cell in row
            if isinstance(cell.structure, Storage)
        ]
        return {
            "storage_count": float(len(storages)),
            "storage_food_units": sum(item.food_quantity for item in storages),
            "storage_wood_units": sum(item.quantity_of(MaterialKind.WOOD) for item in storages),
            "storage_stone_units": sum(item.quantity_of(MaterialKind.STONE) for item in storages),
            "storage_fiber_units": sum(item.quantity_of(MaterialKind.FIBER) for item in storages),
            "storage_weight": sum(item.current_weight for item in storages),
            "storage_capacity_weight": sum(item.capacity_weight for item in storages),
        }

    def get_material_counts(self) -> dict[str, float]:
        """Retorna unidades totais e número de depósitos por tipo de material."""
        counts: dict[str, float] = {}
        for kind in MaterialKind:
            counts[f"{kind.value}_units"] = 0.0
            counts[f"{kind.value}_nodes"] = 0.0
        for row in self.grid:
            for cell in row:
                resource = cell.resource
                if isinstance(resource, MaterialResource):
                    counts[f"{resource.kind.value}_units"] += resource.quantity
                    counts[f"{resource.kind.value}_nodes"] += 1
        return counts

    def get_water_positions(self) -> list[tuple[int, int]]:
        return [
            (cell.x, cell.y)
            for row in self.grid for cell in row
            if isinstance(cell.resource, Water)
        ]

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

    def collect_resource(self, x: int, y: int, quantity: float | None = None):
        cell = self.get_cell(x, y)
        resource = cell.resource

        if resource is None or not resource.is_collectible:
            return None

        if isinstance(resource, MaterialResource) and quantity is not None:
            if not isfinite(quantity) or quantity < 0:
                raise ValueError("A quantidade coletada deve ser finita e não negativa.")
            if quantity == 0:
                return None
            collected_quantity = min(float(quantity), resource.quantity)
            collected = MaterialResource(resource.kind, collected_quantity)
            resource.quantity -= collected_quantity
            if resource.quantity <= 1e-9:
                cell.resource = None
            return collected

        if isinstance(resource, Food) and quantity is not None:
            if not isfinite(quantity) or quantity < 0:
                raise ValueError("A quantidade coletada deve ser finita e não negativa.")
            if quantity == 0:
                return None
            collected_quantity = min(float(quantity), resource.quantity)
            collected = Food(collected_quantity)
            resource.quantity -= collected_quantity
            if resource.quantity <= 1e-9:
                cell.resource = None
            return collected

        cell.resource = None
        return resource

    def advance_resources(self) -> dict[str, int]:
        """Avança o ciclo de vida das plantas e retorna as transições ocorridas."""
        transitions = {"seed_to_growing": 0, "growing_to_mature": 0}
        for row in self.grid:
            for cell in row:
                resource = cell.resource
                if not isinstance(resource, Plant):
                    continue
                previous_state = resource.state
                resource.advance()
                if previous_state == PlantState.SEED and resource.state == PlantState.GROWING:
                    transitions["seed_to_growing"] += 1
                elif previous_state == PlantState.GROWING and resource.state == PlantState.MATURE:
                    transitions["growing_to_mature"] += 1
        return transitions

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
        """Gera sementes e retorna a quantidade efetivamente criada.

        Mantido como API simples por compatibilidade. Para auditoria detalhada,
        use :meth:`spawn_seeds_with_report`.
        """
        return self.spawn_seeds_with_report(
            count=count,
            max_plants=max_plants,
            occupied_cells=occupied_cells,
        )["spawned"]

    def spawn_seeds_with_report(
        self,
        count: int = 1,
        max_plants: int = 100,
        occupied_cells: set[tuple[int, int]] | None = None,
    ) -> dict[str, int]:
        """Gera sementes e explica qualquer diferença entre pedido e criação."""
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
        available_capacity = max(0, max_plants - existing_plants)
        allowed_by_cap = min(count, available_capacity)
        blocked_by_plant_cap = count - allowed_by_cap

        available_cells = [
            cell
            for row in self.grid
            for cell in row
            if cell.resource is None
            and cell.obstacle is None
            and (cell.x, cell.y) not in self.reserved_cells
            and (cell.x, cell.y) not in occupied_cells
        ]
        spawned_count = min(allowed_by_cap, len(available_cells))
        blocked_by_space = allowed_by_cap - spawned_count
        selected_cells = self.rng.sample(available_cells, spawned_count)

        for cell in selected_cells:
            cell.resource = Plant()

        return {
            "requested": count,
            "spawned": spawned_count,
            "blocked_by_plant_cap": blocked_by_plant_cap,
            "blocked_by_space": blocked_by_space,
        }

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
