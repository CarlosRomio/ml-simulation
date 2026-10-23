import csv
from types import SimpleNamespace

from configuration.simulation_config import SimulationConfig
from experiments.social_comparison import (
    DEFAULT_SOCIAL_CONDITIONS,
    SocialCondition,
    _activity_audit,
    run_social_comparison,
    resolve_worker_count,
)


def test_social_comparison_writes_paired_results_and_group_audit(tmp_path):
    config = SimulationConfig(
        width=15, height=15, food_density=0.03, obstacle_density=0.0,
        water_density=0.01, wood_density=0.01, stone_density=0.01,
        agent_count=3, herbivore_count=1, carnivore_count=0, vision_radius=5,
    )
    result = run_social_comparison(
        config=config, runs=2, max_steps=12, seed=19, max_workers=1,
        output_dir=tmp_path, affinity_threshold=0.3,
    )

    assert len(result["summary"]) == 3
    assert len(result["runs"]) == 6
    assert {row["steps_requested"] for row in result["runs"]} == {12}
    assert len(result["paired_deltas"]) == 4
    assert result["baseline"] == "A_CONTROLE"
    assert {row["seed"] for row in result["runs"] if row["run"] == 1} == {19}
    assert {row["seed"] for row in result["runs"] if row["run"] == 2} == {20}
    assert (tmp_path / "runs.csv").exists()
    assert (tmp_path / "summary.csv").exists()
    assert (tmp_path / "paired_deltas.csv").exists()
    assert (tmp_path / "group_history.csv").exists()
    assert (tmp_path / "group_events.csv").exists()
    assert (tmp_path / "agent_activity_history.csv").exists()
    assert (tmp_path / "activity_interval_summary.csv").exists()
    assert len(result["activity_interval_summary"]) > 0
    assert all("social_distance_travelled" in row for row in result["runs"])
    assert all("critical_hunger_steps" in row for row in result["runs"])
    assert all("food_collection_events" in row for row in result["runs"])
    assert all("food_units_collected" in row for row in result["runs"])
    assert all("food_search_agent_steps_per_100_agent_steps" in row for row in result["runs"])
    assert len(result["agent_activity_history"]) > 0
    assert {row["movement_category"] for row in result["agent_activity_history"]} <= {"SOCIAL", "NON_SOCIAL", "IDLE"}
    assert {row["behavior_intent"] for row in result["agent_activity_history"]} <= {
        "UNCLASSIFIED", "INITIAL", "REST_IN_SHELTER", "DRINK_WATER", "COLLECT_MATERIAL",
        "INTERACT_STORAGE", "SOCIAL_REUNION", "SOCIAL_APPROACH", "BUILD_SHELTER", "HUNT",
        "SEEK_FOOD", "SEEK_WATER", "GATHER_MATERIAL", "SEEK_SHELTER", "NAVIGATE_TARGET",
        "EXPLORATION", "SEEK_MATE",
    }
    for run_row in result["runs"]:
        activity_rows = [row for row in result["agent_activity_history"]
                         if row["condition"] == run_row["condition"] and row["run"] == run_row["run"]]
        assert run_row["food_collection_events"] == sum(bool(row["collected_food"]) for row in activity_rows)
        assert abs(run_row["food_units_collected"] - sum(float(row["collected_food_quantity"]) for row in activity_rows)) < 1e-6
        assert abs(run_row["food_collection_events_per_100_agent_steps"] -
                   100 * run_row["food_collection_events"] / max(1, len(activity_rows))) < 1e-6
    no_social_rows = [row for row in result["agent_activity_history"]
                      if row["condition"] == "B_SEM_INFLUENCIA_SOCIAL"]
    assert not any(row["decision"] == "SOCIAL_SKIPPED_PRIORITY" for row in no_social_rows)

    with (tmp_path / "agent_activity_history.csv").open(encoding="utf-8-sig", newline="") as stream:
        activity_rows = list(csv.DictReader(stream))
    assert len(activity_rows) == len(result["agent_activity_history"])
    assert {"decision", "distance", "collected_food", "collected_food_quantity", "behavior_intent",
            "health_before", "health_after", "health_delta", "hunger_delta", "thirst_delta", "energy_delta",
            "hunger_after", "thirst_after", "alive_after_step"} <= set(activity_rows[0])

    with (tmp_path / "runs.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 6
    assert {row["condition"] for row in rows} == {c.name for c in DEFAULT_SOCIAL_CONDITIONS}


def test_social_conditions_are_explicit_and_distinct():
    control, no_social, no_memory = DEFAULT_SOCIAL_CONDITIONS
    assert control.social_behavior_enabled and control.social_memory_enabled
    assert not no_social.social_behavior_enabled and not no_social.social_memory_enabled
    assert no_memory.social_behavior_enabled and not no_memory.social_memory_enabled
    assert len({c.name for c in (control, no_social, no_memory)}) == 3


def test_social_comparison_rejects_invalid_threshold(tmp_path):
    config = SimulationConfig(width=12, height=12, agent_count=2)
    try:
        run_social_comparison(config, runs=1, max_steps=1, output_dir=tmp_path,
                              affinity_threshold=1.1)
    except ValueError:
        pass
    else:
        raise AssertionError("Limiar acima de 1 deveria ser rejeitado")


def test_worker_count_auto_is_bounded_and_preserves_one_cpu():
    assert resolve_worker_count(0, runs=30, cpu_count=16) == 8
    assert resolve_worker_count(0, runs=4, cpu_count=8) == 4
    assert resolve_worker_count(0, runs=30, cpu_count=2) == 1


def test_worker_count_explicit_value_is_capped_by_number_of_runs():
    assert resolve_worker_count(6, runs=3, cpu_count=16) == 3
    assert resolve_worker_count(1, runs=30, cpu_count=16) == 1


def test_worker_count_rejects_negative_values():
    try:
        resolve_worker_count(-1, runs=3, cpu_count=8)
    except ValueError:
        pass
    else:
        raise AssertionError("Número negativo de workers deveria ser rejeitado")


def test_social_priority_audit_only_counts_explicitly_skipped_social_decisions():
    condition = SocialCondition("TEST", True, True, "test")
    diagnostics = {
        "step": 1, "moved": False, "distance": 0,
        "hunger_before": 30, "hunger_after_physiology": 31,
        "thirst_before": 10, "thirst_after_physiology": 11,
        "health_before": 100, "health_after": 100,
        "energy_before": 50, "energy_after": 49,
        "collected_food": False, "collected_food_quantity": 0,
        "food_consumed": 0, "drank_water": False,
        "termination_cause": "RUNNING", "damage_causes": [],
    }
    result = SimpleNamespace(
        social_decision_history=[
            {"agent_id": "H001", "step": 1, "decision": "SOCIAL_SKIPPED_PRIORITY", "reason": "HUNGER_PRIORITY"},
            {"agent_id": "H002", "step": 1, "decision": "OTHER_BEHAVIOR_PRIORITY", "reason": "SOCIAL_DRIVE_NOT_REACHED"},
        ],
        agent_ids=["H001", "H002"],
        human_physiology_history=[[dict(diagnostics)], [dict(diagnostics)]],
    )
    rows, totals = _activity_audit(result, 1, condition, 90, 90)
    assert rows[0]["social_skipped_priority"] is True
    assert rows[1]["social_skipped_priority"] is False
    assert totals["social_skipped_hunger_steps"] == 1
