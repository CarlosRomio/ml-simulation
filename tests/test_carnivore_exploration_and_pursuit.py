from agents.agent import Agent
from animals.carnivore import Carnivore
from animals.herbivore import Herbivore
from environment.world import World
from simulation.simulation import Simulation


def test_carnivore_explores_toward_persistent_waypoint_without_visible_prey():
    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    carnivore = Carnivore(10, 10)

    action = carnivore.choose_action(world, [])
    first_target = carnivore.exploration_target

    assert first_target is not None
    assert first_target != (carnivore.x, carnivore.y)
    assert len(carnivore.path) > 2
    assert action in {(0, -1), (0, 1), (-1, 0), (1, 0)}

    # A segunda decisão mantém a patrulha, em vez de sortear uma nova direção.
    next_action = carnivore.choose_action(world, [])
    assert carnivore.exploration_target == first_target
    assert next_action == action


def test_carnivore_sprint_follows_path_and_moves_three_cells_toward_prey():
    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    human = Agent(0, 0)
    herbivore = Herbivore(10, 5)
    herbivore.choose_action = lambda world, threats: (0, 0)
    carnivore = Carnivore(5, 5)
    simulation = Simulation(
        world,
        agents=[human],
        herbivores=[herbivore],
        carnivores=[carnivore],
        seed_spawn_count=0,
    )

    simulation.step()

    assert (carnivore.x, carnivore.y) == (8, 5)
    assert carnivore.last_activity == "RUNNING"
    assert carnivore.needs.energy == 74.0
    record = [row for row in simulation.physiology_activity_history
              if row["individual_type"] == "CARNIVORE"][-1]
    assert record["distance"] == 3.0
    assert record["stamina_spent_movement"] == 6.0


def test_carnivore_uses_path_steps_instead_of_running_straight_into_obstacle():
    from environment.obstacles import ObstacleType

    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    world.get_cell(6, 5).obstacle = list(ObstacleType)[0]
    herbivore = Herbivore(9, 5)
    herbivore.choose_action = lambda world, threats: (0, 0)
    carnivore = Carnivore(5, 5)
    simulation = Simulation(world, agents=[Agent(0, 0)], herbivores=[herbivore], carnivores=[carnivore], seed_spawn_count=0)

    simulation.step()

    assert (carnivore.x, carnivore.y) != (5, 5)
    assert world.is_walkable(carnivore.x, carnivore.y)
    assert abs(carnivore.x - 5) + abs(carnivore.y - 5) <= 3
