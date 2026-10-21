"""Testes do contrato de navegação compartilhado entre espécies."""
import random

from agents.navigation.service import NavigationService
from environment.obstacles import ObstacleType
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
