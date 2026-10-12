from environment.resources import Plant, PlantState
from environment.world import World


def test_plant_counts_start_at_zero():
    world = World(width=5, height=5, food_count=0)

    assert world.get_plant_counts() == {
        "seeds": 0,
        "growing": 0,
        "mature": 0,
        "total": 0,
    }


def test_plant_counts_separate_each_lifecycle_stage():
    world = World(width=5, height=5, food_count=0)

    world.get_cell(0, 0).resource = Plant(
        state=PlantState.SEED
    )
    world.get_cell(1, 0).resource = Plant(
        state=PlantState.GROWING
    )
    world.get_cell(2, 0).resource = Plant(
        state=PlantState.MATURE
    )
    world.get_cell(3, 0).resource = Plant(
        state=PlantState.MATURE
    )

    assert world.get_plant_counts() == {
        "seeds": 1,
        "growing": 1,
        "mature": 2,
        "total": 4,
    }


def test_collected_plant_is_not_counted():
    world = World(width=5, height=5, food_count=0)
    world.get_cell(2, 2).resource = Plant(
        state=PlantState.MATURE
    )

    world.collect_resource(2, 2)

    assert world.get_plant_counts()["total"] == 0
