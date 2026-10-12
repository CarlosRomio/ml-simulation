import random

from agents.agent import Agent
from animals.carnivore import Carnivore
from animals.factory import CarnivoreFactory, HerbivoreFactory
from animals.herbivore import Herbivore
from configuration.simulation_config import SimulationConfig
from environment.resources import Plant, PlantState, Water
from environment.world import World
from experiments.runner import run_single_simulation
from simulation.simulation import Simulation


def test_human_food_and_water_restore_needs_without_exceeding_bounds():
    needs_agent = Agent(x=1, y=1)
    needs_agent.needs.hunger = 70
    needs_agent.needs.thirst = 65
    needs_agent.needs.energy = 50
    needs_agent.eat(35)
    needs_agent.needs.drink(30)
    assert needs_agent.hunger == 35
    assert needs_agent.thirst == 35
    assert needs_agent.energy == 71


def test_human_seeks_water_when_thirst_is_high():
    world = World(width=7, height=3, food_count=0, obstacle_count=0, water_count=0)
    world.get_cell(6, 1).resource = Water()
    human = Agent(x=0, y=1, vision_radius=6, rng=random.Random(1))
    human.needs.thirst = 60
    action = human.choose_action(
        __import__("agents.perception", fromlist=["Perception"]).Perception().observe(
            world, human.x, human.y, human.vision_radius
        ), world
    )
    assert action == (1, 0)


def test_carnivore_factory_keeps_entities_in_distinct_cells():
    world = World(width=8, height=8, food_count=0, obstacle_count=0)
    humans = [(2, 2), (3, 3)]
    herbivores = HerbivoreFactory.create(
        world, 3, seed=1, occupied_positions=set(humans)
    )
    occupied = set(humans) | {(h.x, h.y) for h in herbivores}
    carnivores = CarnivoreFactory.create(
        world, 2, seed=2, occupied_positions=occupied
    )
    all_positions = occupied | {(c.x, c.y) for c in carnivores}
    assert len(all_positions) == 7


def test_carnivore_attacks_adjacent_human_and_records_predation_death():
    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    human = Agent(x=2, y=2)
    human.needs.health = 30
    human.choose_action = lambda nearby_cells, world: (0, 0)
    carnivore = Carnivore(x=3, y=2)
    simulation = Simulation(world, agents=[human], carnivores=[carnivore], seed_spawn_count=0)
    simulation.step()
    assert not human.alive
    assert simulation.metrics.termination_cause == "PREDATION"
    assert simulation.humans_killed_by_carnivores == 1
    assert simulation.carnivore_attacks == 1


def test_carnivore_can_attack_herbivore():
    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    human = Agent(x=0, y=0)
    animal = Herbivore(x=3, y=2)
    animal.choose_action = lambda world, human_positions: (0, 0)
    carnivore = Carnivore(x=2, y=2)
    simulation = Simulation(
        world, agents=[human], herbivores=[animal], carnivores=[carnivore],
        seed_spawn_count=0,
    )
    simulation.step()
    assert animal.health < 100
    assert simulation.carnivore_attacks == 1


def test_human_receives_large_hunger_reward_for_killing_herbivore():
    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    human = Agent(x=2, y=2)
    human.needs.hunger = 60
    human.choose_action = lambda nearby_cells, world: (0, 0)
    animal = Herbivore(x=3, y=2)
    animal.choose_action = lambda world, human_positions: (0, 0)
    simulation = Simulation(world, agents=[human], herbivores=[animal], seed_spawn_count=0)
    simulation.run(4)
    assert not animal.alive
    assert human.hunger < 5
    assert simulation.animals_killed == 1


def test_experiment_runner_instantiates_configured_carnivores_and_herbivores():
    config = SimulationConfig(
        width=12, height=12, food_density=0.03, obstacle_density=0,
        water_density=0.01, agent_count=2, herbivore_count=2, carnivore_count=1,
        vision_radius=4,
    )
    result = run_single_simulation(config, run_seed=42, max_steps=10, seed_spawn_count=0)
    assert result.total_agents == 2


def test_human_hunts_nearby_herbivore_when_local_food_is_unavailable():
    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    human = Agent(x=2, y=2, vision_radius=4)
    animal = Herbivore(x=3, y=2)
    human.choose_action = lambda nearby_cells, world: (0, 0)
    animal.choose_action = lambda world, human_positions: (0, 0)
    simulation = Simulation(world, agents=[human], herbivores=[animal], seed_spawn_count=0)
    simulation.step()
    assert simulation.attacks == 1


def test_needs_reach_critical_state_and_eventually_kill_agent_without_resources():
    world = World(width=5, height=5, food_count=0, obstacle_count=0, water_count=0)
    human = Agent(x=2, y=2)
    human.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent=human, seed_spawn_count=0)
    simulation.run(400)
    assert not human.alive
    assert human.health == 0
    assert simulation.metrics.termination_cause in {"STARVATION", "DEHYDRATION"}
    assert simulation.metrics.critical_thirst_steps > 0


def test_herbivore_flees_from_nearby_carnivore():
    world = World(width=7, height=7, food_count=0, obstacle_count=0)
    animal = Herbivore(x=3, y=3, rng=random.Random(4))
    action = animal.choose_action(world, [(4, 3)])
    assert action in {(-1, 0), (0, -1), (0, 1)}
