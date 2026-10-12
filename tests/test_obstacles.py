from environment.world import World
from environment.obstacles import ObstacleType
from agents.perception import Perception

def test_obstacles_are_created():
    world = World(
        width=10,
        height=10,
        food_count=10,
        obstacle_count=15,
    )

    obstacles = [
        cell for row in world.grid for cell in row if cell.obstacle is not None
    ]

    assert len(obstacles) == 15
    assert all(cell.obstacle in ObstacleType for cell in obstacles)


def test_obstacles_do_not_overlap_food():
    world = World(
        width=10,
        height=10,
        food_count=20,
        obstacle_count=15,
    )

    for row in world.grid:
        for cell in row:
            assert not (cell.obstacle is not None and cell.resource is not None), (
                f"Obstáculo e alimento na mesma célula " f"({cell.x}, {cell.y})"
            )


def test_agent_cannot_move_into_obstacle():
    world = World(
        width=5,
        height=5,
        food_count=0,
        obstacle_count=0,
    )

    agent = type("TestAgent", (), {})()
    agent.x = 1
    agent.y = 1

    world.get_cell(2, 1).obstacle = ObstacleType.ROCK

    moved = world.move_agent(agent, (1, 0))

    assert moved is False
    assert (agent.x, agent.y) == (1, 1)


def test_agent_can_move_to_free_cell():
    world = World(
        width=5,
        height=5,
        food_count=0,
        obstacle_count=0,
    )

    agent = type("TestAgent", (), {})()
    agent.x = 1
    agent.y = 1

    moved = world.move_agent(agent, (1, 0))

    assert moved is True
    assert (agent.x, agent.y) == (2, 1)


def test_reserved_cells_remain_free():
    reserved = {(2, 2), (3, 3)}

    world = World(
        width=10,
        height=10,
        food_count=10,
        obstacle_count=15,
        reserved_cells=reserved,
    )

    for x, y in reserved:
        cell = world.get_cell(x, y)

        assert cell.resource is None
        assert cell.obstacle is None


def test_obstacle_count_is_respected():
    world = World(
        width=10,
        height=10,
        food_count=20,
        obstacle_count=12,
    )

    count = sum(1 for row in world.grid for cell in row if cell.obstacle is not None)

    assert count == 12


def test_negative_obstacle_count_is_rejected():
    try:
        World(
            width=5,
            height=5,
            food_count=0,
            obstacle_count=-1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("World deveria rejeitar obstacle_count negativo")

def test_obstacle_blocks_line_of_sight():
    world = World(
        width=5,
        height=5,
        food_count=0,
        obstacle_count=0,
    )

    world.get_cell(2, 1).obstacle = ObstacleType.ROCK

    nearby = Perception().observe(world, 1, 1, radius=3)
    visible_positions = {(cell.x, cell.y) for cell in nearby}

    # O próprio obstáculo continua visível.
    assert (2, 1) in visible_positions

    # A célula diretamente atrás dele fica oculta.
    assert (3, 1) not in visible_positions


def test_cells_without_obstacles_remain_visible():
    world = World(
        width=5,
        height=5,
        food_count=0,
        obstacle_count=0,
    )

    nearby = Perception().observe(world, 2, 2, radius=2)
    visible_positions = {(cell.x, cell.y) for cell in nearby}

    assert (2, 2) in visible_positions
    assert (4, 2) in visible_positions
    assert (2, 4) in visible_positions

def run_tests():
    tests = [
        test_obstacles_are_created,
        test_obstacles_do_not_overlap_food,
        test_agent_cannot_move_into_obstacle,
        test_agent_can_move_to_free_cell,
        test_reserved_cells_remain_free,
        test_obstacle_count_is_respected,
        test_negative_obstacle_count_is_rejected,
        test_obstacle_blocks_line_of_sight,
        test_cells_without_obstacles_remain_visible,
    ]

    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")

    print("\nTodos os testes de obstáculos passaram!")


if __name__ == "__main__":
    run_tests()
