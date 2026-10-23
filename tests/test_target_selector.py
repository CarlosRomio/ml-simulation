"""Testes da separação entre seleção de objetivos e planejamento de rotas."""
import random

from agents.navigation.service import NavigationService
from agents.target_selector import TargetSelector
from environment.obstacles import ObstacleType
from environment.world import World


def empty_world(width=7, height=5):
    return World(
        width=width,
        height=height,
        food_count=0,
        obstacle_count=0,
        water_count=0,
        rng=random.Random(802),
    )


def test_target_selector_skips_out_of_bounds_and_non_walkable_goals():
    world = empty_world()
    world.get_cell(2, 2).obstacle = ObstacleType.ROCK
    service = NavigationService()
    selector = TargetSelector()
    attempted_goals = []

    def tracked_pathfinder(route_world, start, goal):
        attempted_goals.append(goal)
        return service.find_path(route_world, start, goal)

    selected = selector.nearest_reachable_target(
        world,
        (1, 2),
        [(99, 2), (2, 2), (5, 2)],
        tracked_pathfinder,
    )

    assert selected is not None
    assert selected[0] == (5, 2)
    assert (99, 2) not in attempted_goals
    assert (2, 2) not in attempted_goals
    assert attempted_goals == [(5, 2)]


def test_target_selector_preserves_manhattan_order_and_fallback():
    world = empty_world()
    # A parede impede chegar ao candidato mais próximo, mas não ao seguinte.
    for y in range(world.height):
        world.get_cell(3, y).obstacle = ObstacleType.ROCK
    selector = TargetSelector()
    service = NavigationService()

    selected = selector.nearest_reachable_target(
        world,
        (1, 2),
        [(4, 2), (2, 2)],
        service.find_path,
    )

    assert selected is not None
    assert selected[0] == (2, 2)
    assert selected[1][0] == (1, 2)
    assert selected[1][-1] == (2, 2)


def test_target_selector_can_plan_from_a_start_that_became_non_walkable():
    world = empty_world()
    world.get_cell(1, 2).obstacle = ObstacleType.ROCK
    selector = TargetSelector()
    service = NavigationService()

    selected = selector.nearest_reachable_target(
        world,
        (1, 2),
        [(5, 2)],
        service.find_path,
    )

    assert selected is not None
    assert selected[0] == (5, 2)
    assert selected[1][0] == (1, 2)
    assert selected[1][-1] == (5, 2)


def test_target_selector_ignores_current_position_as_a_movement_target():
    world = empty_world()
    selector = TargetSelector()
    service = NavigationService()

    selected = selector.nearest_reachable_target(
        world,
        (1, 2),
        [(1, 2)],
        service.find_path,
    )

    assert selected is None


def test_target_selection_contract_reports_invalid_candidate_then_selects_route():
    from agents.navigation.service import NavigationStatus

    world = empty_world()
    world.get_cell(2, 2).obstacle = ObstacleType.ROCK
    selector = TargetSelector()
    service = NavigationService()

    result = selector.select_reachable_target(
        world, (1, 2), [(2, 2), (5, 2)], service
    )

    assert result.succeeded
    assert result.target == (5, 2)
    assert [attempt.navigation.status for attempt in result.attempts] == [
        NavigationStatus.INVALID_GOAL,
        NavigationStatus.PATH_FOUND,
    ]
    assert result.attempts[0].navigation.reason == "GOAL_NOT_WALKABLE"
    assert result.navigation is not None
    assert result.navigation.path[0] == (1, 2)
    assert result.navigation.path[-1] == (5, 2)


def test_target_selection_contract_distinguishes_temporary_block_from_invalid_goal():
    from agents.navigation.service import NavigationStatus

    world = empty_world()
    selector = TargetSelector()
    service = NavigationService()

    result = selector.select_reachable_target(
        world,
        (1, 2),
        [(3, 2)],
        service,
        blocked_positions={(3, 2)},
    )

    assert not result.succeeded
    assert result.target is None
    assert len(result.attempts) == 1
    assert result.attempts[0].navigation.status is NavigationStatus.TEMPORARILY_BLOCKED
    assert result.attempts[0].navigation.reason == "GOAL_OCCUPIED"


def test_target_selection_contract_accepts_already_at_water_goal():
    from agents.navigation.service import NavigationStatus

    world = empty_world()
    selector = TargetSelector()
    service = NavigationService()

    result = selector.select_reachable_target(world, (1, 2), [(1, 2)], service)

    assert result.succeeded
    assert result.target == (1, 2)
    assert result.navigation is not None
    assert result.navigation.status is NavigationStatus.ALREADY_AT_GOAL
    assert result.navigation.path == [(1, 2)]


def test_target_selection_can_skip_extra_static_path_for_single_route_consumers():
    from agents.navigation.service import NavigationStatus

    world = empty_world()
    selector = TargetSelector()
    service = NavigationService()
    calls = []
    original_plan_route = service.plan_route

    def tracked_plan_route(*args, **kwargs):
        calls.append((args[2], kwargs))
        return original_plan_route(*args, **kwargs)

    service.plan_route = tracked_plan_route
    result = selector.select_reachable_target(
        world,
        (1, 2),
        [(5, 2)],
        service,
        capture_static_path=False,
    )

    assert result.succeeded
    assert result.target == (5, 2)
    assert len(calls) == 1
    assert result.attempts[0].static_path is None
    assert result.attempts[0].navigation.status is NavigationStatus.PATH_FOUND
    assert result.navigation is not None
    assert result.navigation.path == [(1, 2), (2, 2), (3, 2), (4, 2), (5, 2)]


def test_target_selection_skips_static_diagnostic_search_without_dynamic_blockers():
    world = empty_world()
    selector = TargetSelector()
    calls = []

    def tracked_pathfinder(route_world, start, goal):
        calls.append((start, goal))
        return NavigationService().find_path(route_world, start, goal)

    service = NavigationService(pathfinder=tracked_pathfinder)
    result = selector.select_reachable_target(
        world, (1, 2), [(5, 2)], service
    )

    assert result.succeeded
    assert result.attempts[0].static_path is None
    # Sem bloqueios, apenas plan_route precisa calcular o caminho.
    assert calls == [((1, 2), (5, 2))]


def test_target_selection_keeps_static_path_for_dynamic_block_diagnostics():
    world = empty_world()
    selector = TargetSelector()
    service = NavigationService()

    result = selector.select_reachable_target(
        world,
        (1, 2),
        [(5, 2)],
        service,
        blocked_positions={(2, 2)},
    )

    assert result.succeeded
    attempt = result.attempts[0]
    assert attempt.static_path is not None
    assert (2, 2) in attempt.blocked_steps
    assert (2, 2) not in attempt.navigation.path
