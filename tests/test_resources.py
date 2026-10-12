
from random import Random

from environment.resources import Plant, PlantState
from environment.world import World


def test_seed_allows_walkability_but_cannot_be_collected():
    world = World(width=5, height=5, food_count=0)
    cell = world.get_cell(2, 2)
    cell.resource = Plant()

    assert cell.is_walkable
    assert world.collect_resource(2, 2) is None
    assert cell.resource is not None


def test_plant_transitions_from_seed_to_growing():
    plant = Plant(seed_duration=2, growth_duration=3)

    plant.advance()
    assert plant.state == PlantState.SEED

    plant.advance()
    assert plant.state == PlantState.GROWING


def test_growing_plant_blocks_movement_and_cannot_be_collected():
    world = World(width=5, height=5, food_count=0)
    cell = world.get_cell(2, 2)
    cell.resource = Plant(state=PlantState.GROWING)

    assert not cell.is_walkable
    assert world.collect_resource(2, 2) is None
    assert cell.resource is not None


def test_plant_becomes_mature_after_growth_duration():
    plant = Plant(seed_duration=1, growth_duration=2)

    plant.advance()
    assert plant.state == PlantState.GROWING

    plant.advance()
    assert plant.state == PlantState.GROWING

    plant.advance()
    assert plant.state == PlantState.MATURE
    assert plant.is_collectible


def test_mature_plant_can_be_collected():
    world = World(width=5, height=5, food_count=0)
    cell = world.get_cell(2, 2)
    cell.resource = Plant(state=PlantState.MATURE)

    collected = world.collect_resource(2, 2)

    assert collected is not None
    assert cell.resource is None


def test_seed_spawning_respects_limit_and_occupied_cells():
    world = World(
        width=5,
        height=5,
        food_count=0,
        rng=Random(42),
    )

    spawned = world.spawn_seeds(
        count=5,
        max_plants=3,
        occupied_cells={(2, 2)},
    )

    assert spawned == 3

    plants = [
        cell.resource
        for row in world.grid
        for cell in row
        if isinstance(cell.resource, Plant)
    ]

    assert len(plants) == 3
    assert world.get_cell(2, 2).resource is None


def test_seed_spawning_is_reproducible():
    world_a = World(
        width=5,
        height=5,
        food_count=0,
        rng=Random(123),
    )
    world_b = World(
        width=5,
        height=5,
        food_count=0,
        rng=Random(123),
    )

    world_a.spawn_seeds(count=5, max_plants=10)
    world_b.spawn_seeds(count=5, max_plants=10)

    positions_a = {
        (cell.x, cell.y)
        for row in world_a.grid
        for cell in row
        if isinstance(cell.resource, Plant)
    }
    positions_b = {
        (cell.x, cell.y)
        for row in world_b.grid
        for cell in row
        if isinstance(cell.resource, Plant)
    }

    assert positions_a == positions_b
