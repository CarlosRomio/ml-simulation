from random import Random

from agents.agent import Agent
from environment.resources import MaterialKind, MaterialResource
from environment.world import World
from simulation.simulation import Simulation


def test_human_collects_material_into_inventory_without_eating_it():
    world = World(width=5, height=5, food_count=0, rng=Random(4))
    agent = Agent(x=2, y=2, rng=Random(1))
    world.get_cell(2, 2).resource = MaterialResource(MaterialKind.WOOD, quantity=2)
    simulation = Simulation(world, agent, seed_spawn_count=0)
    hunger_before = agent.hunger
    energy_before = agent.energy

    simulation.step()

    assert agent.inventory.quantity_of(MaterialKind.WOOD) == 1
    assert world.get_cell(2, 2).resource.quantity == 1
    assert agent.hunger > hunger_before
    assert agent.energy <= energy_before
    assert simulation.diagnostic_history_by_agent[id(agent)][0]["collected_resource_type"] == "WOOD"
    assert simulation.ecology_history[-1]["wood_units_collected_by_humans"] == 1
    assert simulation.metrics_by_agent[id(agent)].food_collected == 0


def test_human_keeps_collecting_material_while_standing_on_deposit():
    world = World(width=5, height=5, food_count=0, rng=Random(4))
    agent = Agent(x=2, y=2, rng=Random(1))
    world.get_cell(2, 2).resource = MaterialResource(MaterialKind.WOOD, quantity=3)
    simulation = Simulation(world, agent, seed_spawn_count=0)

    simulation.run(2)

    assert agent.inventory.quantity_of(MaterialKind.WOOD) == 2
    assert world.get_cell(2, 2).resource.quantity == 1


def test_full_inventory_does_not_destroy_material_resource():
    world = World(width=5, height=5, food_count=0, rng=Random(4))
    agent = Agent(x=2, y=2, rng=Random(1))
    agent.inventory.add(MaterialKind.STONE, 10)  # weight 20, capacity is full
    node = MaterialResource(MaterialKind.WOOD, quantity=2)
    world.get_cell(2, 2).resource = node
    simulation = Simulation(world, agent, seed_spawn_count=0)

    simulation.step()

    assert world.get_cell(2, 2).resource is node
    assert agent.inventory.quantity_of(MaterialKind.WOOD) == 0
