import csv
import json

from configuration.simulation_config import SimulationConfig
from run_ecosystem_audit import run_audit


def _read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_audit_runner_exports_baselines_sampled_data_events_and_aggregates(tmp_path):
    config = SimulationConfig(
        width=12, height=12, food_density=0.03, obstacle_density=0.01,
        water_density=0.02, wood_density=0.01, stone_density=0.01,
        agent_count=2, herbivore_count=2, carnivore_count=1, vision_radius=4,
    )
    result = run_audit(
        runs=2, steps=8, seed=930, workers=2, config=config,
        output=tmp_path / "audit", sample_every=2, seed_spawn_count=0, max_plants=20,
    )

    out = tmp_path / "audit"
    runs = _read_csv(out / "runs.csv")
    initial = _read_csv(out / "initial_states.csv")
    sampled = _read_csv(out / "activity_sampled.csv")
    population = _read_csv(out / "population_history.csv")
    summary = _read_csv(out / "activity_summary.csv")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

    assert len(runs) == 2
    assert len(initial) == 10  # 2 humanos + 2 herbívoros + 1 carnívoro, por execução
    assert {row["individual_type"] for row in initial} == {"HUMAN", "HERBIVORE", "CARNIVORE"}
    assert sampled
    assert "decision_trace" in sampled[0]
    assert "action_reason" in sampled[0]
    assert (out / "action_reason_summary.csv").exists()
    assert "stamina_recovered" in sampled[0]
    assert len(population) == 2 * 9  # passo inicial + 8 passos
    assert summary
    assert manifest["workers"] == 2
    assert result["manifest"]["runs"] == 2


def test_audit_summary_uses_full_activity_records_not_only_sampled_rows(tmp_path):
    config = SimulationConfig(
        width=10, height=10, food_density=0.02, obstacle_density=0,
        water_density=0, wood_density=0, stone_density=0,
        agent_count=1, herbivore_count=0, carnivore_count=0, vision_radius=3,
    )
    run_audit(
        runs=1, steps=6, seed=931, workers=1, config=config,
        output=tmp_path / "audit", sample_every=6, seed_spawn_count=0, max_plants=10,
    )
    summary = _read_csv(tmp_path / "audit" / "activity_summary.csv")
    sampled = _read_csv(tmp_path / "audit" / "activity_sampled.csv")
    total_full = sum(int(row["observations"]) for row in summary)
    assert total_full >= 6
    assert len(sampled) < total_full
