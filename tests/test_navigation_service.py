"""Testes do contrato de navegação compartilhado entre espécies."""
import random

from agents.navigation.service import NavigationService, NavigationStatus
from environment.obstacles import ObstacleType
from environment.resources import Plant, PlantState
from environment.world import World


def empty_world(width=7, height=5):
    return World(width=width, height=height, food_count=0, obstacle_count=0,
                 water_count=0, rng=random.Random(801))


def test_navigation_service_finds_path_with_existing_bfs_semantics():
    world = empty_world()
    world.get_cell(3, 2).obstacle = ObstacleType.ROCK
    service = NavigationService()

    path = service.find_path(world, (1, 2), (5, 2))

    assert path is not None
    assert path[0] == (1, 2)
    assert path[-1] == (5, 2)
    assert (3, 2) not in path


def test_navigation_service_routes_around_dynamic_occupancy():
    world = empty_world()
    service = NavigationService()

    path = service.find_path(
        world, (1, 2), (5, 2), blocked_positions={(2, 2)}
    )

    assert path is not None
    assert path[0] == (1, 2)
    assert path[-1] == (5, 2)
    assert (2, 2) not in path


def test_navigation_service_returns_next_delta_for_current_path_position():
    service = NavigationService()

    assert service.next_step([(1, 2), (2, 2), (2, 3)], (1, 2)) == (1, 0)
    assert service.next_step([(1, 2), (2, 2), (2, 3)], (2, 2)) == (0, 1)


def test_navigation_service_returns_none_when_path_is_stale_or_finished():
    service = NavigationService()

    assert service.next_step([(1, 2), (2, 2)], (4, 4)) is None
    assert service.next_step([(1, 2), (2, 2)], (2, 2)) is None
    assert service.next_step(None, (1, 2)) is None


def test_custom_pathfinder_remains_supported_without_dynamic_blockers():
    world = empty_world()
    expected = [(1, 1), (2, 1), (3, 1)]
    service = NavigationService(pathfinder=lambda _world, _start, _goal: expected)

    assert service.find_path(world, (1, 1), (3, 1)) == expected


def test_custom_pathfinder_route_is_rejected_if_it_crosses_dynamic_blocker():
    world = empty_world()
    expected = [(1, 1), (2, 1), (3, 1)]
    service = NavigationService(pathfinder=lambda _world, _start, _goal: expected)

    assert service.find_path(
        world, (1, 1), (3, 1), blocked_positions={(2, 1)}
    ) is None



def test_plan_route_distinguishes_invalid_goal_from_temporary_occupancy():
    world = empty_world()
    service = NavigationService()
    world.get_cell(3, 2).obstacle = ObstacleType.ROCK

    invalid = service.plan_route(world, (1, 2), (3, 2))
    occupied = service.plan_route(
        world, (1, 2), (5, 2), blocked_positions={(5, 2)}
    )

    assert invalid.status is NavigationStatus.INVALID_GOAL
    assert invalid.reason == "GOAL_NOT_WALKABLE"
    assert occupied.status is NavigationStatus.TEMPORARILY_BLOCKED
    assert occupied.reason == "GOAL_OCCUPIED"


def test_plan_route_distinguishes_dynamic_blockage_from_static_unreachable_goal():
    world = empty_world(width=5, height=5)
    service = NavigationService()
    # Bloqueio dinâmico de todas as saídas do início.
    dynamic = service.plan_route(
        world, (2, 2), (4, 2), blocked_positions={(2, 1), (2, 3), (1, 2), (3, 2)}
    )
    # Uma parede estática separa o destino do início.
    for y in range(world.height):
        world.get_cell(3, y).obstacle = ObstacleType.ROCK
    static = service.plan_route(world, (1, 2), (4, 2))

    assert dynamic.status is NavigationStatus.TEMPORARILY_BLOCKED
    assert static.status is NavigationStatus.UNREACHABLE


def test_plan_route_reports_already_at_goal_and_out_of_bounds():
    world = empty_world()
    service = NavigationService()

    arrived = service.plan_route(world, (2, 2), (2, 2))
    invalid = service.plan_route(world, (2, 2), (99, 2))

    assert arrived.status is NavigationStatus.ALREADY_AT_GOAL
    assert arrived.path == [(2, 2)]
    assert invalid.status is NavigationStatus.INVALID_GOAL
    assert invalid.reason == "OUT_OF_BOUNDS"


def test_navigation_can_leave_a_start_cell_that_became_non_walkable():
    """A célula inicial pode deixar de ser transitável enquanto o agente está nela."""
    world = empty_world()
    world.get_cell(1, 2).resource = Plant(state=PlantState.GROWING)
    service = NavigationService()

    result = service.plan_route(world, (1, 2), (5, 2))

    assert result.status.name == "PATH_FOUND"
    assert result.path is not None
    assert result.path[0] == (1, 2)
    assert result.path[-1] == (5, 2)
    assert (1, 2) in result.path
