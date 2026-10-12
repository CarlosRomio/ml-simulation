import pytest

from agents.inventory import Inventory
from environment.resources import MaterialKind, MaterialResource
from environment.world import World


def test_inventory_tracks_weight_and_capacity():
    inventory = Inventory(capacity_weight=5)
    assert inventory.add(MaterialKind.WOOD, 3) == 3
    assert inventory.add(MaterialKind.STONE, 2) == 1
    assert inventory.current_weight == 5
    assert inventory.available_weight == 0
    assert inventory.add(MaterialKind.FIBER, 1) == 0


def test_inventory_removes_only_available_quantity():
    inventory = Inventory(capacity_weight=10)
    inventory.add(MaterialKind.WOOD, 3)
    assert inventory.remove(MaterialKind.WOOD, 2) == 2
    assert inventory.quantity_of(MaterialKind.WOOD) == 1
    assert inventory.remove(MaterialKind.WOOD, 5) == 1
    assert inventory.quantity_of(MaterialKind.WOOD) == 0


def test_inventory_rejects_invalid_capacity_and_quantities():
    with pytest.raises(ValueError):
        Inventory(capacity_weight=-1)
    inventory = Inventory()
    with pytest.raises(ValueError):
        inventory.add(MaterialKind.WOOD, -1)


def test_material_resource_requires_positive_quantity():
    with pytest.raises(ValueError):
        MaterialResource(MaterialKind.WOOD, 0)


def test_world_collects_material_deposit_partially():
    world = World(width=3, height=3, food_count=0)
    node = MaterialResource(MaterialKind.WOOD, quantity=4)
    world.get_cell(1, 1).resource = node

    collected = world.collect_resource(1, 1, quantity=1)
    assert isinstance(collected, MaterialResource)
    assert collected.quantity == 1
    assert world.get_cell(1, 1).resource.quantity == 3

    world.collect_resource(1, 1, quantity=3)
    assert world.get_cell(1, 1).resource is None


def test_world_material_counts_include_units_and_deposits():
    world = World(width=3, height=3, food_count=0)
    world.get_cell(0, 0).resource = MaterialResource(MaterialKind.WOOD, 4)
    world.get_cell(1, 0).resource = MaterialResource(MaterialKind.WOOD, 2)
    world.get_cell(2, 0).resource = MaterialResource(MaterialKind.STONE, 3)

    counts = world.get_material_counts()
    assert counts["wood_units"] == 6
    assert counts["wood_nodes"] == 2
    assert counts["stone_units"] == 3
    assert counts["stone_nodes"] == 1
