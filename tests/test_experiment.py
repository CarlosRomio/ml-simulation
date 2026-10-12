from simulation.experiment import run_experiment
from metrics.tracker import SimulationMetrics
from configuration.simulation_config import SimulationConfig
from experiments.runner import ExperimentRunner
from experiments.runner import SimulationRunResult

def test_experiment_summary_aggregates_behavior_metrics():
    config = SimulationConfig(
        width=5,
        height=5,
        food_density=0.0,
        obstacle_density=0.0,
    )

    runner = ExperimentRunner(
        config=config,
        runs=2,
        max_steps=10,
    )

    agent_metrics_1 = SimulationMetrics(
        steps=10,
        simulated_time_seconds=10.0,
        termination_cause="STEP_LIMIT",
        initial_energy=100.0,
        final_energy=80.0,
        food_collected=2,
        energy_sum=900.0,
        energy_samples=10,
        movement_steps=8,
        idle_steps=2,
        distance_travelled=8.0,
        unique_positions_visited=7,
        max_steps_without_food=4,
    )

    agent_metrics_2 = SimulationMetrics(
        steps=6,
        simulated_time_seconds=6.0,
        termination_cause="STARVATION",
        initial_energy=100.0,
        final_energy=0.0,
        food_collected=1,
        energy_sum=300.0,
        energy_samples=6,
        movement_steps=4,
        idle_steps=2,
        distance_travelled=4.0,
        unique_positions_visited=5,
        max_steps_without_food=3,
    )

    runner.results = [
        SimulationRunResult(
            agent_metrics=agent_metrics_1,
            final_plant_count=20,
            seeds_spawned=5,
            step_reached_plant_limit=8,
        ),
        SimulationRunResult(
            agent_metrics=agent_metrics_2,
            final_plant_count=30,
            seeds_spawned=9,
            step_reached_plant_limit=None,
        ),
    ]

    summary = runner.summarize()

    assert summary.total_runs == 2
    assert summary.survived_runs == 1
    assert summary.starvation_runs == 1  # compatibilidade: significa extinção da execução
    assert summary.extinction_runs == 1
    assert summary.survival_rate == 0.5

    assert summary.average_steps == 8.0
    assert summary.average_simulated_time == 8.0
    assert summary.average_food_collected == 1.5
    assert summary.average_energy == 70.0

    assert summary.average_distance_travelled == 6.0
    assert summary.average_unique_positions_visited == 6.0
    assert summary.average_movement_steps == 6.0
    assert summary.average_idle_steps == 2.0
    assert summary.average_max_steps_without_food == 3.5

    assert summary.average_final_plant_count == 25.0
    assert summary.average_seeds_spawned == 7.0
    assert summary.average_step_reached_plant_limit == 8.0
    assert summary.runs_reached_plant_limit == 1

def test_experiment_summary_requires_results():
    config = SimulationConfig(
        width=5,
        height=5,
        food_density=0.0,
        obstacle_density=0.0,
    )

    runner = ExperimentRunner(config=config, runs=2)

    try:
        runner.summarize()
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "O resumo deveria exigir resultados de execução."
        )


def test_experiment_runs_requested_number():
    results = run_experiment(
        runs=5,
        max_steps=20,
        seed=42,
    )

    assert results.runs == 5
    assert len(results.survival_steps) == 5
    assert len(results.food_collected) == 5
    assert 0 <= results.survived <= 5


def test_experiment_is_reproducible():
    first = run_experiment(
        runs=5,
        max_steps=50,
        seed=42,
    )

    second = run_experiment(
        runs=5,
        max_steps=50,
        seed=42,
    )

    assert first.survival_steps == second.survival_steps
    assert first.food_collected == second.food_collected
    assert first.survived == second.survived


def test_survival_rate():
    results = run_experiment(
        runs=4,
        max_steps=10,
        seed=42,
    )

    assert 0 <= results.survival_rate <= 100


if __name__ == "__main__":
    test_experiment_runs_requested_number()
    test_experiment_is_reproducible()
    test_survival_rate()

    print("Todos os testes de experimentos passaram!")
