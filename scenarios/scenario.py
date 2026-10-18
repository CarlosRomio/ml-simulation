
from dataclasses import dataclass

from environment.obstacles import ObstacleType


@dataclass(frozen=True)
class Scenario:
    width: int
    height: int
    food_positions: tuple[tuple[int, int, float], ...]
    obstacle_positions: tuple[tuple[int, int, ObstacleType], ...]
    start_position: tuple[int, int]
    seed: int
    water_positions: tuple[tuple[int, int], ...] = ()
    plant_positions: tuple[tuple[int, int], ...] = ()
    material_positions: tuple[tuple[int, int, str, float], ...] = ()

    def to_world(self):
        from environment.resources import Food, MaterialKind, MaterialResource, Plant, PlantState, Water
        from environment.world import World
        
        world = World(
            width=self.width,
            height=self.height,
            food_count=0,
            obstacle_count=0,
            reserved_cells={self.start_position},
        )

        for x, y, quantity in self.food_positions:
            world.get_cell(x, y).resource = Food(quantity=quantity)

        for x, y in self.water_positions:
            world.get_cell(x, y).resource = Water()

        for x, y in self.plant_positions:
            world.get_cell(x, y).resource = Plant(state=PlantState.MATURE)

        for x, y, kind, quantity in self.material_positions:
            world.get_cell(x, y).resource = MaterialResource(
                kind=MaterialKind(kind), quantity=quantity
            )

        # Um depósito compartilhado começa no ponto de referência do cenário.
        # A estrutura não bloqueia movimento nem ocupa a camada de recursos.
        world.place_storage(*self.start_position)

        for x, y, obstacle_type in self.obstacle_positions:
            world.get_cell(x, y).obstacle = obstacle_type

        return world
