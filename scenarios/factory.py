
import random

from configuration.simulation_config import SimulationConfig
from environment.obstacles import ObstacleType
from scenarios.scenario import Scenario


class ScenarioFactory:
    @staticmethod
    def create(
        config: SimulationConfig,
        seed: int,
    ) -> Scenario:
        config.validate()

        rng = random.Random(seed)

        start_position = config.start_position
        reserved_cells = {start_position}

        all_positions = [
            (x, y)
            for y in range(config.height)
            for x in range(config.width)
            if (x, y) not in reserved_cells
        ]

        required_cells = (config.food_count + config.obstacle_count + config.water_count
                          + config.wood_count + config.stone_count)

        if required_cells > len(all_positions):
            raise ValueError(
                "Não há células suficientes para comida e obstáculos."
            )

        selected = rng.sample(all_positions, required_cells)

        food_positions_raw = selected[:config.food_count]
        water_positions_raw = selected[config.food_count:config.food_count + config.water_count]
        obstacle_start = config.food_count + config.water_count
        obstacle_end = obstacle_start + config.obstacle_count
        obstacle_positions_raw = selected[obstacle_start:obstacle_end]
        wood_start = obstacle_end
        wood_end = wood_start + config.wood_count
        wood_positions_raw = selected[wood_start:wood_end]
        stone_positions_raw = selected[wood_end:wood_end + config.stone_count]

        food_positions = tuple(
            (x, y, 1.0)
            for x, y in food_positions_raw
        )

        obstacle_types = list(ObstacleType)

        obstacle_positions = tuple(
            (x, y, rng.choice(obstacle_types))
            for x, y in obstacle_positions_raw
        )

        return Scenario(
            width=config.width,
            height=config.height,
            food_positions=food_positions,
            obstacle_positions=obstacle_positions,
            water_positions=tuple(water_positions_raw),
            start_position=start_position,
            seed=seed,
            material_positions=tuple(
                [(x, y, "wood", float(rng.randint(2, 5))) for x, y in wood_positions_raw]
                + [(x, y, "stone", float(rng.randint(2, 5))) for x, y in stone_positions_raw]
            ),
        )
