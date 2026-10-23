from random import Random

from agents.agent import Agent
from agents.navigation.exploration import choose_exploration_waypoint
from agents.navigation.service import NavigationService
from environment.world import World


def test_waypoint_selector_chooses_a_distant_reachable_region():
    world = World(width=50, height=50, food_count=0, obstacle_count=0, water_count=0)
    start = (25, 25)
    plan = choose_exploration_waypoint(
        world, start, NavigationService().find_path, Random(123), {},
        min_distance=12, max_distance=22, candidate_limit=16,
    )

    assert plan is not None
    target, path = plan
    distance = abs(target[0] - start[0]) + abs(target[1] - start[1])
    assert 12 <= distance <= 22
    assert path[0] == start
    assert path[-1] == target
    assert all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(path, path[1:]))


def test_human_keeps_exploration_waypoint_persistent_between_decisions():
    world = World(width=50, height=50, food_count=0, obstacle_count=0, water_count=0)
    agent = Agent(25, 25, vision_radius=12, rng=Random(8))

    first_action = agent.choose_action([], world)
    first_target = agent.target
    first_path = list(agent.path)

    assert first_target is not None
    assert agent.target_intent == "EXPLORATION"
    assert len(first_path) > 2
    assert first_action in {(0, -1), (0, 1), (-1, 0), (1, 0)}

    # A decisão seguinte mantém o waypoint se a rota ainda for válida.
    second_action = agent.choose_action([], world)
    assert agent.target == first_target
    assert second_action in {(0, -1), (0, 1), (-1, 0), (1, 0)}
