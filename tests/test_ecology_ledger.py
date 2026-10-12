"""Tests for auditable ecological stock-and-flow records."""
from random import Random

from agents.agent import Agent
from environment.resources import Plant, PlantState, Water
from environment.world import World
from simulation.simulation import Simulation


def test_advance_resources_reports_lifecycle_transitions():
    world = World(width=4, height=4, food_count=0, rng=Random(1))
    world.get_cell(0, 0).resource = Plant(
        state=PlantState.SEED, seed_duration=1, growth_duration=1
    )
    world.get_cell(1, 0).resource = Plant(
        state=PlantState.GROWING, seed_duration=1, growth_duration=1
    )

    transitions = world.advance_resources()

    assert transitions == {"seed_to_growing": 1, "growing_to_mature": 1}


def test_seed_spawn_report_distinguishes_plant_cap_from_space():
    cap_world = World(width=3, height=3, food_count=0, rng=Random(2))
    cap_world.get_cell(0, 0).resource = Plant(state=PlantState.SEED)
    report = cap_world.spawn_seeds_with_report(count=3, max_plants=1)

    assert report == {
        "requested": 3, "spawned": 0,
        "blocked_by_plant_cap": 3, "blocked_by_space": 0,
    }

    space_world = World(width=2, height=2, food_count=0, rng=Random(3))
    for row in space_world.grid:
        for cell in row:
            cell.resource = Water()
    report = space_world.spawn_seeds_with_report(count=2, max_plants=10)

    assert report == {
        "requested": 2, "spawned": 0,
        "blocked_by_plant_cap": 0, "blocked_by_space": 2,
    }


def test_ecology_history_has_one_row_per_step_and_initial_snapshot():
    world = World(width=7, height=7, food_count=0, water_count=2, rng=Random(4))
    agent = Agent(x=3, y=3)
    simulation = Simulation(
        world, agent, seed_spawn_count=1, max_plants=20, rng=Random(5)
    )

    assert len(simulation.ecology_history) == 1
    initial = simulation.ecology_history[0]
    assert initial["step"] == 0
    assert initial["total"] == 0
    assert initial["water_sources"] == 2
    assert initial["seeds_spawned"] == 0

    simulation.run(steps=4)

    assert len(simulation.ecology_history) == simulation.steps + 1
    assert [row["step"] for row in simulation.ecology_history] == list(range(5))
    assert all(row["total"] == row["seeds"] + row["growing"] + row["mature"]
               for row in simulation.ecology_history)
    # Estoque final = estoque anterior + regeneração - plantas efetivamente coletadas.
    for previous, current in zip(simulation.ecology_history, simulation.ecology_history[1:]):
        expected = (
            previous["total"] + current["seeds_spawned"]
            - current["plants_collected_by_humans"]
            - current["plants_collected_by_herbivores"]
        )
        assert current["total"] == expected


def test_ecology_ledger_counts_each_seed_request_and_actual_spawn():
    world = World(width=5, height=5, food_count=0, rng=Random(6))
    agent = Agent(x=2, y=2)
    simulation = Simulation(
        world, agent, seed_spawn_count=2, max_plants=3, rng=Random(7)
    )
    simulation.run(steps=4)

    rows = simulation.ecology_history[1:]
    assert sum(row["seeds_spawn_requested"] for row in rows) == 8
    assert sum(row["seeds_spawned"] for row in rows) <= 3
    assert sum(row["seeds_spawned"] for row in rows) == sum(simulation.seeds_spawned_history)
    assert all(
        row["seeds_spawned"] + row["seeds_blocked_by_plant_cap"]
        + row["seeds_blocked_by_space"] == row["seeds_spawn_requested"]
        for row in rows
    )
    assert all("water_thirst_reduction_humans" in row for row in rows)


def test_human_physiology_history_distinguishes_collection_and_drinking():
    world = World(width=7, height=7, food_count=0, water_count=1, rng=Random(8))
    agent = Agent(x=3, y=3)
    simulation = Simulation(world, agent, seed_spawn_count=0, rng=Random(9))
    simulation.run(steps=2)

    history = simulation.diagnostic_history_by_agent[id(agent)]
    assert len(history) == 2
    assert all("collected_resource_type" in row for row in history)
    assert all(row["collected_resource_type"] in {"NONE", "PLANT", "FOOD"} for row in history)
    assert all("drank_water" in row for row in history)
    assert all("water_thirst_reduction" in row for row in history)
