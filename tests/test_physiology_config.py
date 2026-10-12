from configuration.simulation_config import SimulationConfig
from experiments.runner import run_single_simulation


def test_physiology_config_reaches_agents_and_metrics():
    config = SimulationConfig(
        width=10,
        height=10,
        food_density=0.0,
        obstacle_density=0.0,
        water_density=0.0,
        agent_count=1,
        thirst_per_step=2.5,
        dehydration_threshold=60.0,
        dehydration_damage_per_step=4.0,
    )
    result = run_single_simulation(config, run_seed=4, max_steps=3, seed_spawn_count=0)
    metrics = result.all_agent_metrics[0]
# Starts at thirst 20; with no water, the configured per-step increase is visible.
    assert metrics.final_thirst == 27.5
    assert metrics.critical_thirst_steps == 0
