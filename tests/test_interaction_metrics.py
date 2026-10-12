import random

from agents.agent import Agent
from environment.world import World
from simulation.simulation import Simulation


def test_population_history_records_initial_and_each_step():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, rng=random.Random(1))
    agents = [Agent(2, 2), Agent(5, 5)]
    simulation = Simulation(world, agents=agents, seed_spawn_count=0, rng=random.Random(2))
    simulation.run(3)

    assert len(simulation.population_history) == 4
    assert simulation.population_history[0]["step"] == 0
    assert simulation.population_history[0]["alive"] == 2
    assert simulation.population_history[-1]["step"] == 3
    assert simulation.population_history[-1]["alive"] == sum(agent.alive for agent in agents)


def test_blocked_move_by_occupied_cell_is_counted():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, rng=random.Random(1))
    first = Agent(2, 2)
    second = Agent(3, 2)
    first.choose_action = lambda nearby_cells, world: (1, 0)
    second.choose_action = lambda nearby_cells, world: (-1, 0)
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0, rng=random.Random(2))

    simulation.step()

    assert simulation.blocked_by_agent_attempts >= 1
    assert simulation.blocked_movement_attempts >= simulation.blocked_by_agent_attempts
    assert len({(agent.x, agent.y) for agent in simulation.alive_agents}) == len(simulation.alive_agents)
