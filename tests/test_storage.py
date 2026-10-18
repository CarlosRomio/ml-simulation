from random import Random

import pytest

from agents.agent import Agent
from agents.inventory import Inventory
from environment.resources import MaterialKind, MaterialResource, Plant, PlantState
from environment.storage import Storage
from environment.world import World
from simulation.simulation import Simulation
from scenarios.scenario import Scenario


def test_storage_respects_capacity_and_material_weights():
    storage = Storage(capacity_weight=5)
    assert storage.deposit(MaterialKind.WOOD, 3) == 3
    assert storage.deposit(MaterialKind.STONE, 2) == 1
    assert storage.current_weight == 5
    assert storage.deposit_food(1) == 0
    assert storage.withdraw(MaterialKind.STONE, 10) == 1
    assert storage.current_weight == 3


def test_storage_rejects_invalid_capacity_or_quantities():
    with pytest.raises(ValueError):
        Storage(capacity_weight=-1)
    with pytest.raises(ValueError):
        Storage(food_quantity=-1)
    with pytest.raises(ValueError):
        Storage(capacity_weight=1, food_quantity=2)


def test_world_storage_is_walkable_and_counted_separately_from_resources():
    world = World(width=5, height=5, food_count=0, rng=Random(1))
    storage = world.place_storage(2, 2)
    assert world.get_cell(2, 2).structure is storage
    assert world.is_walkable(2, 2)
    assert world.get_cell(2, 2).resource is None
    assert world.get_storage_positions() == [(2, 2)]
    assert world.get_storage_counts()["storage_count"] == 1


def test_agent_deposits_carried_material_when_on_storage_without_resource_loss():
    world = World(width=5, height=5, food_count=0, rng=Random(1))
    storage = world.place_storage(2, 2)
    agent = Agent(2, 2)
    agent.inventory.add(MaterialKind.WOOD, 3)
    agent.inventory.add(MaterialKind.STONE, 2)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent, seed_spawn_count=0)

    simulation.step()

    assert agent.inventory.quantity_of(MaterialKind.WOOD) == 0
    assert agent.inventory.quantity_of(MaterialKind.STONE) == 0
    assert storage.quantity_of(MaterialKind.WOOD) == 3
    assert storage.quantity_of(MaterialKind.STONE) == 2
    row = simulation.ecology_history[-1]
    assert row["wood_units_deposited_by_humans"] == 3
    assert row["stone_units_deposited_by_humans"] == 2


def test_food_is_carried_then_consumed_only_when_hungry():
    world = World(width=5, height=5, food_count=0, rng=Random(1))
    agent = Agent(2, 2)
    world.get_cell(2, 2).resource = Plant(state=PlantState.MATURE)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent, seed_spawn_count=0)

    hunger_before = agent.hunger
    simulation.step()
    assert agent.inventory.food_quantity == 1
    assert agent.hunger > hunger_before
    assert simulation.metrics.food_consumed == 0

    agent.needs.hunger = 35
    simulation.step()
    assert agent.inventory.food_quantity == 0
    assert simulation.metrics.food_consumed == 1
    assert simulation.ecology_history[-1]["food_units_consumed_by_humans"] == 1


def test_agent_deposits_food_surplus_and_withdraws_food_when_hungry():
    world = World(width=5, height=5, food_count=0, rng=Random(1))
    storage = world.place_storage(2, 2)
    agent = Agent(2, 2)
    agent.inventory.add_food(4)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent, seed_spawn_count=0)

    simulation.step()
    assert agent.inventory.food_quantity == 1
    assert storage.food_quantity == 3

    agent.inventory.remove_food(1)
    agent.needs.hunger = 35
    simulation.step()
    assert storage.food_quantity == 2
    assert agent.inventory.food_quantity == 0
    assert simulation.metrics.food_consumed == 1


def test_scenario_world_places_shared_shelter_at_start_position():
    from environment.shelter import Shelter

    scenario = Scenario(
        width=5, height=5, food_positions=(), obstacle_positions=(),
        start_position=(2, 2), seed=4,
    )
    world = scenario.to_world()
    assert world.get_storage_positions() == [(2, 2)]
    assert isinstance(world.get_cell(2, 2).structure, Shelter)


def test_storage_partial_deposit_keeps_remainder_in_agent_inventory():
    world = World(width=5, height=5, food_count=0, rng=Random(2))
    storage = world.place_storage(2, 2, Storage(capacity_weight=2))
    agent = Agent(2, 2, inventory=Inventory(capacity_weight=10))
    agent.inventory.add(MaterialKind.WOOD, 4)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent, seed_spawn_count=0)

    simulation.step()

    assert storage.quantity_of(MaterialKind.WOOD) == 2
    assert agent.inventory.quantity_of(MaterialKind.WOOD) == 2
    assert storage.current_weight + agent.inventory.current_weight == 4


def test_storage_food_transfer_preserves_total_food():
    world = World(width=5, height=5, food_count=0, rng=Random(3))
    storage = world.place_storage(2, 2)
    agent = Agent(2, 2)
    agent.inventory.add_food(3)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent, seed_spawn_count=0)

    simulation.step()
    assert storage.food_quantity + agent.inventory.food_quantity == 3

    agent.needs.hunger = 35
    simulation.step()
    assert storage.food_quantity + agent.inventory.food_quantity + simulation.metrics.food_consumed == 3


def test_plant_is_not_removed_when_inventory_cannot_carry_food():
    world = World(width=5, height=5, food_count=0, rng=Random(4))
    plant = Plant(state=PlantState.MATURE)
    world.get_cell(2, 2).resource = plant
    agent = Agent(2, 2, inventory=Inventory(capacity_weight=0))
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent, seed_spawn_count=0)

    simulation.step()

    assert world.get_cell(2, 2).resource is plant
    assert agent.inventory.food_quantity == 0
