"""Regression tests for unambiguous ecosystem experiment exports."""
from experiments.runner import run_single_simulation
from configuration.simulation_config import SimulationConfig
from run_ecosystem_experiment import _run_row


def test_run_row_distinguishes_cohort_means_from_survivor_means():
    config = SimulationConfig(
        width=7, height=7, food_density=0, obstacle_density=0, water_density=0,
        agent_count=2, herbivore_count=0, carnivore_count=0,
    )
    result = run_single_simulation(config, run_seed=17, max_steps=1, seed_spawn_count=0)
    row = _run_row(1, 17, result)
    assert "human_mean_final_health_all_cohort" in row
    assert "human_mean_final_health_survivors" in row
    assert row["human_survivors_count_for_final_means"] == result.surviving_agents


def test_human_export_semantics_are_documented_in_script():
    from pathlib import Path
    script = Path(__file__).parents[1] / "run_ecosystem_experiment.py"
    source = script.read_text(encoding="utf-8")
    assert 'metric_data["experiment_steps"] = experiment_steps' in source
    assert 'metric_data["steps"] = metrics.agent_lifetime_steps' in source
    assert 'metric_data["simulated_time_seconds"] = metrics.agent_lifetime_steps * step_duration' in source



def test_human_export_names_water_thirst_reduction_explicitly():
    from pathlib import Path
    script = Path(__file__).parents[1] / "run_ecosystem_experiment.py"
    source = script.read_text(encoding="utf-8")
    assert 'metric_data["water_thirst_reduction"] = metrics.water_units_consumed' in source
    assert '"collected_resource_type": "NONE"' in (Path(__file__).parents[1] / "experiments" / "runner.py").read_text(encoding="utf-8")
