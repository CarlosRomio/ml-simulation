
from agents.agent import Agent
from environment.resources import Plant, PlantState
from environment.world import World
from simulation.simulation import Simulation


def test_resource_history_records_initial_state():
    world = World(width=10, height=10, food_count=3)
    agent = Agent(x=5, y=5)

    simulation = Simulation(
        world,
        agent,
        seed_spawn_count=0,
    )

    assert len(simulation.resource_history) == 1
    assert simulation.resource_history[0] == {
        "step": 0,
        "seeds": 0,
        "growing": 0,
        "mature": 3,
        "total": 3,
    }


def test_resource_history_records_every_step():
    world = World(width=10, height=10, food_count=3)
    agent = Agent(x=5, y=5)

    simulation = Simulation(
        world,
        agent,
        seed_spawn_count=0,
    )

    simulation.run(steps=3)

    assert len(simulation.resource_history) == simulation.steps + 1
    assert simulation.resource_history[0]["step"] == 0
    assert simulation.resource_history[-1]["step"] == simulation.steps


def test_seed_spawn_history_records_actual_spawn_count():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=2, y=2)

    simulation = Simulation(
        world,
        agent,
        seed_spawn_count=2,
        max_plants=2,
    )

    simulation.run(steps=2)

    assert len(simulation.seeds_spawned_history) == simulation.steps + 1
    assert simulation.seeds_spawned_history[0] == 0
    assert sum(simulation.seeds_spawned_history) <= 2


def test_resource_counts_match_world_state():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=2, y=2)

    world.get_cell(0, 0).resource = Plant(state=PlantState.SEED)
    world.get_cell(1, 0).resource = Plant(state=PlantState.GROWING)
    world.get_cell(2, 0).resource = Plant(state=PlantState.MATURE)

    simulation = Simulation(
        world,
        agent,
        seed_spawn_count=0,
    )

    counts = simulation.resource_history[0]

    assert counts["seeds"] == 1
    assert counts["growing"] == 1
    assert counts["mature"] == 1
    assert counts["total"] == 3


def test_environment_continues_after_agent_death():
    world = World(width=10, height=10, food_count=0)
    agent = Agent(x=5, y=5)
    agent.alive = False

    simulation = Simulation(
        world,
        agent,
        seed_spawn_count=1,
        max_plants=10,
    )

    simulation.run(steps=5)

    assert simulation.steps == 5
    assert len(simulation.resource_history) == 6
    assert sum(simulation.seeds_spawned_history) == 5
    assert not agent.alive


def test_dead_agent_does_not_consume_energy():
    world = World(width=10, height=10, food_count=0)
    agent = Agent(x=5, y=5)
    agent.alive = False
    energy_before = agent.energy

    simulation = Simulation(
        world,
        agent,
        seed_spawn_count=0,
    )

    simulation.run(steps=5)

    assert agent.energy == energy_before
    assert simulation.steps == 5
