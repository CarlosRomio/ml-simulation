from agents.agent import Agent
from agents.perception import Perception
from environment.world import World


def test_agent_default_vision_radius():
    agent = Agent(x=7, y=7)
    assert agent.vision_radius == 4


def test_configurable_vision_radius():
    agent = Agent(x=7, y=7, vision_radius=2)
    assert agent.vision_radius == 2


def test_radius_four_returns_69_cells():
    world = World(width=15, height=15, food_count=0)
    perception = Perception()

    nearby = perception.observe(world, 7, 7, radius=4)

    assert len(nearby) == 69

def test_radius_zero_returns_current_cell():
    world = World(width=10, height=10, food_count=0)
    perception = Perception()

    nearby = perception.observe(world, 5, 5, radius=0)

    assert len(nearby) == 1
    assert nearby[0].x == 5
    assert nearby[0].y == 5


def test_vision_radius_cannot_be_negative():
    try:
        Agent(x=5, y=5, vision_radius=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("Era esperado um ValueError")


def test_perception_radius_cannot_be_negative():
    world = World(width=10, height=10, food_count=0)
    perception = Perception()

    try:
        perception.observe(world, 5, 5, radius=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("Era esperado um ValueError")


if __name__ == "__main__":
    test_agent_default_vision_radius()
    test_configurable_vision_radius()
    test_radius_four_returns_69_cells()
    test_radius_zero_returns_current_cell()
    test_vision_radius_cannot_be_negative()
    test_perception_radius_cannot_be_negative()

    print("Todos os testes de percepção passaram!")