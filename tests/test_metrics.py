
from agents.agent import Agent
from environment.world import World
from metrics.tracker import SimulationMetrics
from simulation.simulation import Simulation


def test_metrics_initialization():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=2, y=2)
    simulation = Simulation(world, agent)

    assert simulation.metrics.steps == 0
    assert simulation.metrics.food_collected == 0
    assert simulation.metrics.initial_energy == 100.0
    assert simulation.metrics.final_energy == 100.0
    assert simulation.metrics.termination_cause == "RUNNING"

    assert simulation.metrics.simulated_time_seconds == 0.0
    assert simulation.metrics.average_energy == 100.0
    assert simulation.metrics.distance_travelled == 0.0
    assert simulation.metrics.unique_positions_visited == 0


def test_metrics_track_steps():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=2, y=2)
    simulation = Simulation(world, agent)

    simulation.step()
    simulation.step()

    assert simulation.metrics.steps == 2
    assert simulation.metrics.final_energy == 98.0
    assert simulation.metrics.simulated_time_seconds == 2.0


def test_metrics_track_starvation():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=2, y=2)
    simulation = Simulation(world, agent)

    agent.consume_energy(99)
    simulation.step()

    assert simulation.metrics.termination_cause == "STARVATION"
    assert simulation.metrics.final_energy == 0.0


def test_metrics_track_simulated_time():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=2, y=2)
    simulation = Simulation(
        world,
        agent,
        step_duration_seconds=2.5,
    )

    simulation.step()
    simulation.step()

    assert simulation.metrics.steps == 2
    assert simulation.metrics.simulated_time_seconds == 5.0


def test_metrics_track_energy_average():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=2, y=2)
    simulation = Simulation(world, agent)

    simulation.step()
    simulation.step()

    # Amostras: energia inicial, 99 e 98.
    assert simulation.metrics.average_energy == 99.0


def test_metrics_track_stationary_agent():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=2, y=2)

    # Força o agente a escolher a ação de ficar parado.
    agent.choose_action = lambda nearby_cells, world: (0, 0)

    simulation = Simulation(world, agent)
    simulation.step()
    simulation.step()

    assert simulation.metrics.movement_steps == 0
    assert simulation.metrics.idle_steps == 2
    assert simulation.metrics.distance_travelled == 0.0
    assert simulation.metrics.unique_positions_visited == 1


def test_metrics_track_unique_positions_and_distance():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=2, y=2)

    actions = iter([(1, 0), (-1, 0), (1, 0)])
    agent.choose_action = lambda nearby_cells, world: next(actions)

    simulation = Simulation(world, agent)
    simulation.run(3)

    # Caminho: (2,2) -> (3,2) -> (2,2) -> (3,2).
    assert simulation.metrics.distance_travelled == 3.0
    assert simulation.metrics.movement_steps == 3
    assert simulation.metrics.idle_steps == 0
    assert simulation.metrics.unique_positions_visited == 2


def test_metrics_track_max_steps_without_food():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=2, y=2)

    agent.choose_action = lambda nearby_cells, world: (0, 0)

    simulation = Simulation(world, agent)
    simulation.run(3)

    assert simulation.metrics.food_collected == 0
    assert simulation.metrics.max_steps_without_food == 3


def test_metrics_reset_food_interval_after_collection():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(x=1, y=1)

    # Mantém o agente parado. A comida está na posição inicial.
    from environment.resources import Food

    world.get_cell(1, 1).resource = Food(quantity=1.0)
    agent.choose_action = lambda nearby_cells, world: (0, 0)

    simulation = Simulation(world, agent)
    simulation.run(3)

    # Coleta no primeiro passo e fica sem comida nos dois seguintes.
    assert simulation.metrics.food_collected == 1
    assert simulation.metrics.max_steps_without_food == 2
