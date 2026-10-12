from agents.agent import Agent
from agents.perception import Perception
from environment.obstacles import ObstacleType
from environment.resources import Food
from environment.world import World


def create_empty_world(width=7, height=7):
    return World(
        width=width,
        height=height,
        food_count=0,
        obstacle_count=0,
    )


def execute_agent_step(agent, world, perception):
    nearby_cells = perception.observe(
        world,
        agent.x,
        agent.y,
        radius=agent.vision_radius,
    )

    action = agent.choose_action(nearby_cells, world)

    if action == (0, 0):
        return False

    moved = world.move_agent(agent, action)

    if not moved:
        agent.target = None
        agent.path.clear()

    return moved


def test_agent_reaches_food():
    world = create_empty_world()
    perception = Perception()
    agent = Agent(x=1, y=1, vision_radius=6)

    world.get_cell(4, 1).resource = Food()

    for _ in range(10):
        if (agent.x, agent.y) == (4, 1):
            break

        execute_agent_step(agent, world, perception)

    assert (agent.x, agent.y) == (4, 1)
    assert agent.target == (4, 1)


def test_agent_routes_around_obstacle():
    world = create_empty_world()
    perception = Perception()
    agent = Agent(x=1, y=2, vision_radius=6)

    # Alimento do outro lado da rocha.
    world.get_cell(4, 2).resource = Food()
    world.get_cell(2, 2).obstacle = ObstacleType.ROCK

    for _ in range(15):
        if (agent.x, agent.y) == (4, 2):
            break

        execute_agent_step(agent, world, perception)

    assert (agent.x, agent.y) == (4, 2)

    # O agente não atravessou a rocha.
    assert world.get_cell(2, 2).obstacle is not None


def test_agent_abandons_unreachable_food():
    world = create_empty_world()
    perception = Perception()
    agent = Agent(x=1, y=3, vision_radius=6)

    # Alimento isolado por uma parede completa.
    world.get_cell(5, 3).resource = Food()

    for y in range(world.height):
        world.get_cell(3, y).obstacle = ObstacleType.ROCK

    nearby_cells = perception.observe(
        world,
        agent.x,
        agent.y,
        radius=agent.vision_radius,
    )

    action = agent.choose_action(nearby_cells, world)

    assert agent.target is None
    assert agent.path == []

    # Deve explorar uma célula transitável do lado em que está.
    assert action != (0, 0)
    assert world.is_walkable(
        agent.x + action[0],
        agent.y + action[1],
    )


def test_agent_prefers_less_visited_positions():
    world = create_empty_world()
    perception = Perception()
    agent = Agent(x=3, y=3, vision_radius=4)

    agent.visit_counts[(3, 2)] = 5  # Norte
    agent.visit_counts[(3, 4)] = 5  # Sul
    agent.visit_counts[(2, 3)] = 5  # Oeste
    agent.visit_counts[(4, 3)] = 0  # Leste

    nearby_cells = perception.observe(
        world, agent.x, agent.y, radius=agent.vision_radius
    )

    action = agent.choose_action(nearby_cells, world)

    assert action == (1, 0)


def run_tests():
    tests = [
        test_agent_reaches_food,
        test_agent_routes_around_obstacle,
        test_agent_abandons_unreachable_food,
        test_agent_prefers_less_visited_positions,
    ]

    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")

    print("\nTodos os testes de navegação do agente passaram!")


if __name__ == "__main__":
    run_tests()