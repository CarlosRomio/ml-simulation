
from configuration.simulation_config import SimulationConfig
from scenarios.factory import ScenarioFactory


def test_same_seed_creates_same_scenario():
    config = SimulationConfig(
        width=30,
        height=30,
        food_density=0.02,
        obstacle_density=0.01,
    )

    scenario_a = ScenarioFactory.create(config, seed=42)
    scenario_b = ScenarioFactory.create(config, seed=42)

    assert scenario_a == scenario_b


def test_worlds_from_same_scenario_are_independent():
    config = SimulationConfig(
        width=30,
        height=30,
        food_density=0.02,
        obstacle_density=0.01,
    )

    scenario = ScenarioFactory.create(config, seed=42)

    world_a = scenario.to_world()
    world_b = scenario.to_world()

    x, y, _ = scenario.food_positions[0]

    world_a.collect_resource(x, y)

    assert world_a.get_cell(x, y).resource is None
    assert world_b.get_cell(x, y).resource is not None


if __name__ == "__main__":
    test_same_seed_creates_same_scenario()
    test_worlds_from_same_scenario_are_independent()
    print("Todos os testes de cenário passaram!")
