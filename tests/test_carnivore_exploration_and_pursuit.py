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

    assert (carnivore.x, carnivore.y) == (9, 5)
    assert carnivore.last_activity == "RUNNING"
    assert carnivore.needs.energy == 100.0
    record = [row for row in simulation.physiology_activity_history
              if row["individual_type"] == "CARNIVORE"][-1]
    assert record["distance"] == 4.0
    assert record["stamina_spent_movement"] == 5.0


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
    assert abs(carnivore.x - 5) + abs(carnivore.y - 5) <= 5

def test_exploration_history_refreshes_position_recency():
    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    carnivore = Carnivore(10, 10)

    carnivore._recent_positions = [
        (10, 10),
        (9, 10),
        (8, 10),
    ]

    carnivore.choose_action(world, [])

    assert carnivore._recent_positions[-1] == (10, 10)
    assert carnivore._recent_positions.count((10, 10)) == 1
    assert len(carnivore._recent_positions) <= 16


def test_exploration_history_stays_bounded():
    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    carnivore = Carnivore(10, 10)

    carnivore._recent_positions = [
        (x, 0) for x in range(16)
    ]

    carnivore.choose_action(world, [])

    assert len(carnivore._recent_positions) <= 16
    assert carnivore._recent_positions[-1] == (10, 10)

def test_carnivore_pursuit_routes_to_adjacent_cell_not_through_prey_cell():
    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    carnivore = Carnivore(5, 5)

    action = carnivore.choose_action(world, [(10, 5)])

    assert action in {(1, 0), (-1, 0), (0, 1), (0, -1)}
    assert carnivore.target == (10, 5)
    assert carnivore.path
    assert carnivore.path[-1] != (10, 5)
    assert abs(carnivore.path[-1][0] - 10) + abs(carnivore.path[-1][1] - 5) == 1


def test_carnivore_tracks_repeated_hunt_positions_for_oscillation_recovery():
    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    carnivore = Carnivore(5, 5)
    carnivore._hunt_position_history = [(5, 5), (6, 5), (5, 5), (6, 5), (5, 5)]

    carnivore.choose_action(world, [(10, 5)])

    assert carnivore.hunt_stagnation_steps >= 1
    assert len(carnivore._hunt_position_history) <= 8


def test_carnivore_prefers_isolated_herbivore_over_human_group():
    from animals.hunting_policy import select_prey_candidate

    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    carnivore = Carnivore(5, 5, vision_radius=12)
    carnivore.needs.hunger = 55.0
    target_human = Agent(7, 5)
    defender = Agent(7, 6)
    isolated_herbivore = Herbivore(10, 5)

    selected, score, defenders, reason = select_prey_candidate(
        carnivore, [target_human, defender], [isolated_herbivore], [target_human, defender],
        current_target=None, hunger=carnivore.hunger,
    )

    assert selected is isolated_herbivore
    assert score is not None
    assert defenders == 0
    assert reason == "LOWEST_RISK_HERBIVORE"


def test_carnivore_declines_human_group_as_prey_when_hunger_is_not_critical():
    from animals.hunting_policy import select_prey_candidate

    carnivore = Carnivore(5, 5, vision_radius=12)
    carnivore.needs.hunger = 55.0
    first_human = Agent(7, 5)
    second_human = Agent(7, 6)

    selected, score, defenders, reason = select_prey_candidate(
        carnivore, [first_human, second_human], [], [first_human, second_human],
        current_target=None, hunger=carnivore.hunger,
    )

    assert selected is None
    assert score is None
    assert defenders == 0
    assert reason == "NO_SAFE_PREY"


def test_carnivore_can_consider_human_group_when_hunger_is_critical():
    from animals.hunting_policy import select_prey_candidate

    carnivore = Carnivore(5, 5, vision_radius=12)
    carnivore.needs.hunger = 85.0
    first_human = Agent(7, 5)
    second_human = Agent(7, 6)

    selected, score, defenders, reason = select_prey_candidate(
        carnivore, [first_human, second_human], [], [first_human, second_human],
        current_target=None, hunger=carnivore.hunger,
    )

    assert selected is not None
    assert score is not None
    assert defenders >= 1
    assert reason == "LOWEST_RISK_HUMAN"


def test_carnivore_retreats_from_adjacent_human_group_before_defense_hits():
    world = World(width=15, height=15, food_count=0, obstacle_count=0, water_count=0)
    first_human = Agent(5, 5)
    second_human = Agent(5, 6)
    first_human.choose_action = lambda nearby, world: (0, 0)
    second_human.choose_action = lambda nearby, world: (0, 0)
    herbivore = Herbivore(10, 10)
    herbivore.choose_action = lambda world, threats: (0, 0)
    carnivore = Carnivore(5, 4, vision_radius=12)
    carnivore.needs.hunger = 55.0
    simulation = Simulation(
        world, agents=[first_human, second_human], herbivores=[herbivore],
        carnivores=[carnivore], seed_spawn_count=0,
    )
    initial_health = carnivore.health

    simulation.step()

    assert abs(carnivore.x - first_human.x) + abs(carnivore.y - first_human.y) > 1
    assert carnivore.health == initial_health
    record = simulation.carnivore_hunt_history[-1]
    assert record["target_selection_reason"] == "FLEE_HUMAN_GROUP"
    assert record["retreat_decision"] is True
    assert record["retreat_attempted"] is True
    assert record["retreat_reason"] in {"WOUNDED_NEAR_HUMANS", "OUTNUMBERED_NEAR_HUMANS"}
    assert "retreat_success" in record
