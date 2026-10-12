from environment.world import World
from environment.obstacles import ObstacleType
from agents.navigation.bfs import find_path


def create_empty_world(width=5, height=5):
    return World(
        width=width,
        height=height,
        food_count=0,
        obstacle_count=0,
    )


def test_finds_shortest_path_without_obstacles():
    world = create_empty_world()

    path = find_path(world, (0, 0), (3, 2))

    assert path is not None
    assert path[0] == (0, 0)
    assert path[-1] == (3, 2)

    # Distância mínima: 3 movimentos horizontais + 2 verticais.
    assert len(path) - 1 == 5


def test_finds_detour_around_obstacle():
    world = create_empty_world()
    world.get_cell(2, 1).obstacle = ObstacleType.ROCK

    path = find_path(world, (1, 1), (3, 1))

    assert path is not None
    assert path[0] == (1, 1)
    assert path[-1] == (3, 1)
    assert (2, 1) not in path

    # Precisa desviar por cima ou por baixo da rocha.
    assert len(path) - 1 == 4


def test_returns_none_when_goal_is_unreachable():
    world = create_empty_world()

    # Uma parede completa separa os dois lados do mapa.
    for y in range(world.height):
        world.get_cell(2, y).obstacle = ObstacleType.ROCK

    path = find_path(world, (0, 2), (4, 2))

    assert path is None


def test_returns_none_when_goal_is_obstacle():
    world = create_empty_world()
    world.get_cell(3, 3).obstacle = ObstacleType.TREE

    path = find_path(world, (0, 0), (3, 3))

    assert path is None


def test_returns_none_for_out_of_bounds_positions():
    world = create_empty_world()

    assert find_path(world, (-1, 0), (3, 3)) is None
    assert find_path(world, (0, 0), (5, 3)) is None


def test_path_contains_only_valid_moves():
    world = create_empty_world()
    world.get_cell(2, 1).obstacle = ObstacleType.ROCK
    world.get_cell(2, 2).obstacle = ObstacleType.TREE

    path = find_path(world, (0, 1), (4, 1))

    assert path is not None

    for current, next_position in zip(path, path[1:]):
        dx = abs(next_position[0] - current[0])
        dy = abs(next_position[1] - current[1])

        # Cada movimento deve avançar exatamente uma célula.
        assert dx + dy == 1

        cell = world.get_cell(*next_position)
        assert cell.obstacle is None


def run_tests():
    tests = [
        test_finds_shortest_path_without_obstacles,
        test_finds_detour_around_obstacle,
        test_returns_none_when_goal_is_unreachable,
        test_returns_none_when_goal_is_obstacle,
        test_returns_none_for_out_of_bounds_positions,
        test_path_contains_only_valid_moves,
    ]

    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")

    print("\nTodos os testes de navegação passaram!")


if __name__ == "__main__":
    run_tests()