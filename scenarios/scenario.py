
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


    def to_world(self):
        from environment.cell import Cell
        from environment.resources import Food
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

        for x, y, obstacle_type in self.obstacle_positions:
            world.get_cell(x, y).obstacle = obstacle_type

        return world
