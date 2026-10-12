import random

from agents.agent import Agent
from agents.factory import AgentFactory
from agents.species import Species
from animals.factory import HerbivoreFactory
from animals.herbivore import Herbivore
from environment.resources import Plant, PlantState, Water
from environment.world import World
from simulation.simulation import Simulation


def test_agent_represents_human_not_herbivore():
    agent = Agent(x=1, y=1)
    assert agent.species is Species.HUMAN


def test_human_factory_creates_only_human_agents():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, rng=random.Random(2))
    agents = AgentFactory.create_agents(world, 3, 3, seed=10)
    assert len(agents) == 3
    assert all(agent.species is Species.HUMAN for agent in agents)


def test_herbivore_factory_creates_separate_entities_and_avoids_humans():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, rng=random.Random(2))
    human = Agent(x=4, y=4)
    animals = HerbivoreFactory.create(world, 3, seed=10, occupied_positions={(human.x,human.y)})
    assert all(isinstance(animal, Herbivore) for animal in animals)
    assert (human.x,human.y) not in {(animal.x,animal.y) for animal in animals}


def test_herbivore_consumes_mature_plant_and_restores_hunger():
    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    world.get_cell(2, 1).resource = Plant(state=PlantState.MATURE)
    animal = Herbivore(x=1, y=1, rng=random.Random(1))
    animal.needs.hunger = 60
    simulation = Simulation(world, agents=[Agent(x=0,y=0)], herbivores=[animal], seed_spawn_count=0)
    simulation.step()
    # O animal pode levar alguns passos para alcançar a planta.
    simulation.run(steps=5)
    assert animal.hunger < 62


def test_water_remains_a_non_food_resource_for_humans():
    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    world.get_cell(1, 1).resource = Water(drink_amount=30)
    agent = Agent(x=1, y=1)
    agent.needs.thirst = 50
    agent.needs.thirst_per_step = 0
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    simulation.step()
    assert isinstance(world.get_cell(1, 1).resource, Water)
    assert agent.thirst == 20
    assert simulation.metrics.food_collected == 0


def test_human_can_attack_adjacent_herbivore_when_hungry():
    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    human = Agent(x=2,y=2)
    human.needs.hunger = 60
    human.hunt_target = (3,2)
    animal = Herbivore(x=3,y=2)
    simulation = Simulation(world, agents=[human], herbivores=[animal], seed_spawn_count=0)
    # Force an adjacent, stationary encounter for a deterministic combat test.
    human.choose_action = lambda nearby_cells, world: (0,0)
    simulation.step()
    assert animal.health < 100
    assert simulation.attacks == 1


def test_human_sprints_two_cells_and_spends_stamina_when_chasing():
    world = World(width=8, height=5, food_count=0, obstacle_count=0)
    human = Agent(x=1, y=2, vision_radius=6)
    human.needs.hunger = 60
    animal = Herbivore(x=6, y=2)
    simulation = Simulation(world, agents=[human], herbivores=[animal], seed_spawn_count=0)
    simulation.step()
    assert human.x >= 3
    assert human.energy < 100
