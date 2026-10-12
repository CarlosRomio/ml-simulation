import random

from agents.factory import AgentFactory
from configuration.simulation_config import SimulationConfig
from environment.world import World
from simulation.simulation import Simulation


def test_config_rejects_non_positive_agent_count():
    config = SimulationConfig(agent_count=0)
    try:
        config.validate()
    except ValueError:
        pass
    else:
        raise AssertionError("agent_count=0 deveria ser inválido")


def test_factory_creates_unique_valid_positions_reproducibly():
    world_a = World(width=12, height=12, food_count=10, obstacle_count=5, rng=random.Random(10))
    world_b = World(width=12, height=12, food_count=10, obstacle_count=5, rng=random.Random(10))

    agents_a = AgentFactory.create_agents(world_a, 8, 4, (6, 6), seed=123)
    agents_b = AgentFactory.create_agents(world_b, 8, 4, (6, 6), seed=123)

    positions_a = [(agent.x, agent.y) for agent in agents_a]
    positions_b = [(agent.x, agent.y) for agent in agents_b]

    assert positions_a == positions_b
    assert len(set(positions_a)) == len(positions_a)
    assert all(world_a.is_walkable(x, y) for x, y in positions_a)


def test_simulation_keeps_agents_in_distinct_cells():
    world = World(width=12, height=12, food_count=20, obstacle_count=5, rng=random.Random(7))
    agents = AgentFactory.create_agents(world, 8, 4, (6, 6), seed=77)
    simulation = Simulation(world=world, agents=agents, rng=random.Random(99))

    simulation.run(40)

    positions = [(agent.x, agent.y) for agent in agents if agent.alive]
    assert len(positions) == len(set(positions))
    assert len(simulation.agents) == 8
    assert len(simulation.metrics_by_agent) == 8


def test_single_agent_constructor_remains_compatible():
    world = World(width=8, height=8, food_count=0, obstacle_count=0)
    agents = AgentFactory.create_agents(world, 1, 3, (4, 4), seed=1)
    simulation = Simulation(world=world, agent=agents[0])

    assert simulation.agent is agents[0]
    assert simulation.agents == [agents[0]]
