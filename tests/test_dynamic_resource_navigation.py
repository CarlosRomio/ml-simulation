import random

from agents.agent import Agent
from agents.navigation.bfs import find_path
from environment.resources import Water
from environment.world import World
from simulation.simulation import Simulation
from run_ecosystem_audit import _is_audit_event, _resource_access_summary


def empty_world(width=7, height=7):
    return World(width=width, height=height, food_count=0, obstacle_count=0, rng=random.Random(1))


def test_pathfinder_routes_around_dynamically_occupied_cell():
    world = empty_world()
    path = find_path(world, (1, 2), (5, 2), blocked_positions={(2, 2)})

    assert path is not None
    assert path[0] == (1, 2)
    assert path[-1] == (5, 2)
    assert (2, 2) not in path


def test_thirsty_agent_replans_water_route_when_next_step_is_occupied():
    world = empty_world()
    water_position = (5, 2)
    world.get_cell(*water_position).resource = Water()
    agent = Agent(1, 2, vision_radius=6, rng=random.Random(2))
    agent.needs.thirst = 70.0
    agent.target = water_position
    agent.target_intent = "SEEK_WATER"
    agent.path = find_path(world, (1, 2), water_position) or []
    agent.occupied_positions = {(2, 2)}

    action = agent.choose_action([], world)

    assert action != (1, 0)
    assert agent.target == water_position
    assert agent.path
    assert agent.path[-1] == water_position
    assert (2, 2) not in agent.path


def test_blocked_move_by_agent_preserves_resource_goal_and_records_reason():
    world = empty_world()
    first = Agent(1, 2, rng=random.Random(3))
    second = Agent(2, 2, rng=random.Random(4))
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0, rng=random.Random(5))
    goal = (5, 2)
    first.target = goal
    first.target_intent = "SEEK_WATER"
    first.path = [(1, 2), (2, 2), (3, 2), (4, 2), goal]

    moved = simulation._resolve_movements({id(first): (1, 0), id(second): (0, 0)})

    assert moved[id(first)] is False
    assert first.last_movement_block_reason == "AGENT"
    assert first.target == goal
    assert first.path == [(1, 2), (2, 2), (3, 2), (4, 2), goal]


def test_blocked_move_by_animal_is_distinguished_from_agent():
    from animals.herbivore import Herbivore

    world = empty_world()
    agent = Agent(1, 2, rng=random.Random(6))
    herbivore = Herbivore(2, 2, rng=random.Random(7))
    simulation = Simulation(
        world, agents=[agent], herbivores=[herbivore], seed_spawn_count=0, rng=random.Random(8)
    )

    moved = simulation._resolve_movements({id(agent): (1, 0)})

    assert moved[id(agent)] is False
    assert agent.last_movement_block_reason == "ANIMAL"
    assert simulation.blocked_movement_attempts == 1


def test_movement_block_reason_is_exportable_as_an_audit_event():
    event_reason = _is_audit_event(
        {"activity": "WAITING", "movement_block_reason": "ANIMAL"},
        {"activity": "WAITING", "movement_block_reason": ""},
    )

    assert "MOVEMENT_BLOCKED_ANIMAL" in event_reason


def test_herbivore_replans_water_route_around_dynamically_occupied_cell():
    from animals.herbivore import Herbivore

    world = empty_world()
    target = (5, 2)
    world.get_cell(*target).resource = Water()
    herbivore = Herbivore(1, 2, vision_radius=6, rng=random.Random(21))
    herbivore.needs.thirst = 70.0

    action = herbivore.choose_action(
        world,
        [],
        occupied_positions={(2, 2)},
        occupied_animal_positions={(2, 2)},
    )

    assert action != (1, 0)
    assert herbivore.target == target
    assert herbivore.path
    assert (2, 2) not in herbivore.path
    assert herbivore.last_navigation_block_reason == "ANIMAL"


def test_herbivore_selects_alternative_water_source_when_nearest_is_occupied():
    from animals.herbivore import Herbivore

    world = empty_world()
    occupied_water = (2, 2)
    alternative_water = (5, 2)
    world.get_cell(*occupied_water).resource = Water()
    world.get_cell(*alternative_water).resource = Water()
    herbivore = Herbivore(1, 2, vision_radius=6, rng=random.Random(22))
    herbivore.needs.thirst = 70.0

    action = herbivore.choose_action(
        world,
        [],
        occupied_positions={occupied_water},
        occupied_animal_positions={occupied_water},
    )

    assert action != (1, 0)
    assert herbivore.target == alternative_water
    assert herbivore.path[-1] == alternative_water
    assert herbivore.last_navigation_block_reason == "ANIMAL"
    # A tentativa bloqueada não desaparece do diagnóstico quando uma fonte
    # alternativa é encontrada no mesmo passo.
    assert herbivore.navigation_plan_status_counts == {
        "TEMPORARILY_BLOCKED": 1,
        "PATH_FOUND": 1,
    }


def test_herbivore_movement_records_actual_animal_block():
    from animals.herbivore import Herbivore

    world = empty_world()
    herbivore = Herbivore(1, 2, rng=random.Random(23))
    other = Herbivore(2, 2, rng=random.Random(24))
    simulation = Simulation(
        world,
        agents=[Agent(5, 5, rng=random.Random(26))],
        herbivores=[herbivore, other],
        seed_spawn_count=0,
        rng=random.Random(25),
    )
    occupied_animals = {(herbivore.x, herbivore.y), (other.x, other.y)}

    moved = simulation._resolve_herbivore_movement(
        herbivore, (1, 0), set(), occupied_animals
    )

    assert moved is False
    assert herbivore.last_movement_block_reason == "ANIMAL"
    assert (herbivore.x, herbivore.y) == (1, 2)


def test_herbivore_water_search_uses_explicit_navigation_contract():
    from animals.herbivore import Herbivore

    world = empty_world()
    target = (5, 2)
    world.get_cell(*target).resource = Water()
    herbivore = Herbivore(1, 2, vision_radius=6, rng=random.Random(27))
    herbivore.needs.thirst = 70.0
    calls = []
    original_plan_route = herbivore.navigation.plan_route

    def tracked_plan_route(world_arg, start, goal, *, blocked_positions=None):
        calls.append((start, goal, set(blocked_positions or ())))
        return original_plan_route(
            world_arg, start, goal, blocked_positions=blocked_positions
        )

    herbivore.navigation.plan_route = tracked_plan_route
    herbivore.choose_action(
        world,
        [],
        occupied_positions={(2, 2)},
        occupied_animal_positions={(2, 2)},
    )

    assert calls
    assert calls[0][1] == target
    assert calls[0][2] == {(2, 2)}
    assert herbivore.target == target
    assert (2, 2) not in herbivore.path



def test_resource_access_summary_counts_navigation_plan_attempts_not_only_last_status():
    records = [
        {
            "individual_type": "HERBIVORE",
            "navigation_plan_path_found_attempts": 1,
            "navigation_plan_temporarily_blocked_attempts": 1,
            "navigation_plan_unreachable_attempts": 0,
        },
        {
            "individual_type": "HERBIVORE",
            "navigation_plan_path_found_attempts": 2,
            "navigation_plan_temporarily_blocked_attempts": 0,
            "navigation_plan_unreachable_attempts": 1,
        },
    ]

    summary = _resource_access_summary(1, 7200, records)
    herbivore = next(row for row in summary if row["individual_type"] == "HERBIVORE")

    assert herbivore["navigation_plan_path_found_attempts"] == 3
    assert herbivore["navigation_plan_temporarily_blocked_attempts"] == 1
    assert herbivore["navigation_plan_unreachable_attempts"] == 1
