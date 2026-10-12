from types import SimpleNamespace

from run_regeneration_comparison import (
    INITIAL_FOOD_ITEMS,
    INITIAL_MATURE_PLANTS,
    INITIAL_HUMANS,
    INITIAL_HERBIVORES,
    INITIAL_CARNIVORES,
    INITIAL_WATER_SOURCES,
    MAX_PLANTS,
    build_summary_row,
    create_fixed_scenario,
)


def test_regeneration_scenario_is_deterministic_and_keeps_fixed_food_stock():
    first = create_fixed_scenario()
    second = create_fixed_scenario()

    assert first == second
    assert len(first.food_positions) == INITIAL_FOOD_ITEMS
    assert len(first.obstacle_positions) == 9
    assert len(first.water_positions) == INITIAL_WATER_SOURCES
    assert len(first.plant_positions) == INITIAL_MATURE_PLANTS
    food = {(x, y) for x, y, _ in first.food_positions}
    obstacles = {(x, y) for x, y, _ in first.obstacle_positions}
    water = set(first.water_positions)
    plants = set(first.plant_positions)
    assert food.isdisjoint(water)
    assert food.isdisjoint(plants)
    assert obstacles.isdisjoint(water)
    assert obstacles.isdisjoint(plants)
    assert water.isdisjoint(plants)
    assert first.start_position not in plants | water | obstacles | food
    world = first.to_world()
    assert world.get_plant_counts()["total"] == INITIAL_MATURE_PLANTS
    assert world.get_plant_counts()["mature"] == INITIAL_MATURE_PLANTS
    assert first.start_position == (15, 15)


def test_regeneration_comparison_uses_full_ecological_population():
    from configuration.simulation_config import SimulationConfig

    config = SimulationConfig(
        width=30,
        height=30,
        food_density=0.0,
        obstacle_density=0.0,
        agent_count=INITIAL_HUMANS,
        herbivore_count=INITIAL_HERBIVORES,
        carnivore_count=INITIAL_CARNIVORES,
    )
    assert (config.agent_count, config.herbivore_count, config.carnivore_count) == (5, 8, 3)


def test_summary_distinguishes_requested_spawn_from_successful_spawn():
    metrics = SimpleNamespace(
        termination_cause="STEP_LIMIT",
        steps=500,
        agent_lifetime_steps=500,
        food_collected=12,
        final_hunger=20.0,
        final_thirst=10.0,
        final_energy=90.0,
    )
    history = [
        {
            "step": 0,
            "total": 10,
            "seeds_spawn_requested": 0,
            "seeds_spawned": 0,
            "seeds_blocked_by_plant_cap": 0,
            "seeds_blocked_by_space": 0,
            "plants_seed_to_growing": 0,
            "plants_growing_to_mature": 0,
            "plants_collected_by_humans": 0,
            "plants_collected_by_herbivores": 0,
        },
        {
            "step": 1,
            "total": MAX_PLANTS,
            "seeds_spawn_requested": 2,
            "seeds_spawned": 1,
            "seeds_blocked_by_plant_cap": 1,
            "seeds_blocked_by_space": 0,
            "plants_seed_to_growing": 0,
            "plants_growing_to_mature": 0,
            "plants_collected_by_humans": 1,
            "plants_collected_by_herbivores": 0,
        },
    ]
    result = SimpleNamespace(
        agent_metrics=metrics,
        all_agent_metrics=[metrics],
        population_food_collected=12,
        final_plant_count=MAX_PLANTS,
        seeds_spawned=1,
        step_reached_plant_limit=1,
        ecology_history=history,
        surviving_agents=1,
        total_agents=1,
        living_herbivores=0,
        living_carnivores=0,
    )

    summary = build_summary_row(2, [result])

    assert summary["seed_spawn_requests_total"] == 2
    assert summary["seeds_spawned_total"] == 1
    assert summary["seed_spawn_success_rate"] == 0.5
    assert summary["seeds_blocked_by_plant_cap_total"] == 1
    assert summary["runs_reaching_plant_cap"] == 1
    assert summary["mean_step_reaching_plant_cap"] == 1
    assert summary["plants_collected_by_humans_total"] == 1
