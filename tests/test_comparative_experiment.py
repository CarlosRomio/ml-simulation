import csv

from configuration.simulation_config import SimulationConfig
from experiments.comparison import WaterCondition, run_water_comparison


def test_water_comparison_creates_paired_csvs_and_summaries(tmp_path):
    config = SimulationConfig(
        width=20,
        height=20,
        food_density=0.02,
        obstacle_density=0.01,
        water_density=0.02,
        agent_count=2,
        vision_radius=4,
    )
    conditions = (
        WaterCondition("sem_agua", 0.0),
        WaterCondition("agua_escassa", 0.01),
        WaterCondition("agua_abundante", 0.02),
    )

    result = run_water_comparison(
        config=config,
        runs=2,
        max_steps=8,
        seed=7,
        max_workers=1,
        output_dir=tmp_path,
        conditions=conditions,
    )

    assert len(result["summary"]) == 3
    assert len(result["runs"]) == 6
    assert len(result["paired_deltas"]) == 4
    assert result["baseline"] == "sem_agua"
    assert (tmp_path / "runs.csv").exists()
    assert (tmp_path / "summary.csv").exists()
    assert (tmp_path / "paired_deltas.csv").exists()

    with (tmp_path / "runs.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 6
    assert {row["condition"] for row in rows} == {
        "sem_agua", "agua_escassa", "agua_abundante"
    }


def test_water_comparison_is_reproducible(tmp_path):
    config = SimulationConfig(
        width=15,
        height=15,
        food_density=0.02,
        obstacle_density=0.0,
        water_density=0.02,
        agent_count=1,
        vision_radius=3,
    )
    conditions = (
        WaterCondition("sem_agua", 0.0),
        WaterCondition("agua_abundante", 0.02),
    )

    first = run_water_comparison(
        config, runs=2, max_steps=5, seed=11, max_workers=1,
        output_dir=tmp_path / "first", conditions=conditions,
    )
    second = run_water_comparison(
        config, runs=2, max_steps=5, seed=11, max_workers=1,
        output_dir=tmp_path / "second", conditions=conditions,
    )

    stable_fields = (
        "condition", "run", "survival_rate_pct", "food_per_population",
        "final_thirst_mean", "water_units_per_agent", "water_drinks_per_agent",
    )
    assert [tuple(row[field] for field in stable_fields) for row in first["runs"]] == [
        tuple(row[field] for field in stable_fields) for row in second["runs"]
    ]


def test_water_comparison_rejects_invalid_run_counts(tmp_path):
    config = SimulationConfig(width=10, height=10, food_density=0.0, obstacle_density=0.0)
    try:
        run_water_comparison(config, runs=0, output_dir=tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("runs=0 deveria ser rejeitado")
