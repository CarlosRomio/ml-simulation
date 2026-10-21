import csv

from configuration.simulation_config import SimulationConfig
from experiments.runner import run_single_simulation
from run_ecosystem_audit import run_audit, _resource_access_episode_rows


def test_activity_records_include_resource_access_context():
    config = SimulationConfig(
        width=12, height=12, food_density=0.04, obstacle_density=0.0,
        water_density=0.04, wood_density=0.0, stone_density=0.0,
        agent_count=2, herbivore_count=2, carnivore_count=1, vision_radius=4,
    )
    result = run_single_simulation(config, run_seed=731, max_steps=4, seed_spawn_count=0)

    assert result.physiology_activity_history
    required = {
        "nearest_water_distance_manhattan",
        "nearest_food_distance_manhattan",
        "water_sources_in_vision",
        "food_sources_in_vision",
        "selected_target_kind",
        "selected_target_path_available",
        "water_consumption_succeeded",
        "food_acquisition_succeeded",
        "food_consumption_succeeded",
        "resource_access_outcome",
    }
    assert all(required.issubset(record) for record in result.physiology_activity_history)
    herbivore_records = [record for record in result.physiology_activity_history if record["individual_type"] == "HERBIVORE"]
    assert herbivore_records
    assert all({
        "resource_need_priority_before_action", "resource_access_target_kind_before_action",
        "resource_access_target_x_before_action", "resource_access_target_y_before_action",
    }.issubset(record) for record in herbivore_records)
    assert {record["individual_type"] for record in result.physiology_activity_history} >= {
        "HUMAN", "HERBIVORE", "CARNIVORE"
    }


def test_audit_exports_resource_access_summary_and_resource_events(tmp_path):
    config = SimulationConfig(
        width=12, height=12, food_density=0.04, obstacle_density=0.0,
        water_density=0.04, wood_density=0.0, stone_density=0.0,
        agent_count=2, herbivore_count=2, carnivore_count=1, vision_radius=4,
    )
    result = run_audit(
        runs=1, steps=5, seed=731, workers=1, config=config,
        output=tmp_path / "audit", sample_every=1, seed_spawn_count=0,
    )

    summary_path = tmp_path / "audit" / "resource_access_summary.csv"
    sampled_path = tmp_path / "audit" / "activity_sampled.csv"
    events_path = tmp_path / "audit" / "activity_events.csv"
    episodes_path = tmp_path / "audit" / "resource_access_episodes.csv"
    episode_summary_path = tmp_path / "audit" / "resource_access_episode_summary.csv"
    assert summary_path.exists() and sampled_path.exists() and events_path.exists()
    assert episodes_path.exists() and episode_summary_path.exists()

    with summary_path.open(newline="", encoding="utf-8-sig") as handle:
        summary = list(csv.DictReader(handle))
    assert {row["individual_type"] for row in summary} >= {"HUMAN", "HERBIVORE", "CARNIVORE"}
    assert "food_acquisition_successes" in summary[0]

    with sampled_path.open(newline="", encoding="utf-8-sig") as handle:
        sampled = list(csv.DictReader(handle))
    assert sampled
    assert "nearest_water_distance_manhattan" in sampled[0]
    assert "resource_access_outcome" in sampled[0]
    assert result["manifest"]["resource_access_diagnostics"]
    assert "resource_access_episodes.csv" in result["manifest"]["resource_access_diagnostics"]


def test_resource_access_episode_measures_steps_until_water_consumption():
    records = [
        {"step": 1, "individual_type": "HUMAN", "individual_id": "H001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "selected_target_distance_manhattan": 3, "selected_target_path_available": True, "resource_need_priority": "THIRST", "thirst_after": 60, "hunger_after": 10, "movement_block_reason": "", "water_consumption_succeeded": False},
        {"step": 2, "individual_type": "HUMAN", "individual_id": "H001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "selected_target_distance_manhattan": 2, "selected_target_path_available": True, "resource_need_priority": "THIRST", "thirst_after": 70, "hunger_after": 10, "movement_block_reason": "AGENT", "water_consumption_succeeded": False},
        {"step": 3, "individual_type": "HUMAN", "individual_id": "H001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "selected_target_distance_manhattan": 0, "selected_target_path_available": True, "resource_need_priority": "THIRST", "thirst_after": 65, "hunger_after": 10, "movement_block_reason": "", "water_consumption_succeeded": True},
    ]
    episodes = _resource_access_episode_rows(1, 731, records)
    assert len(episodes) == 1
    assert episodes[0]["successful"] is True
    assert episodes[0]["duration_steps"] == 2
    assert episodes[0]["blocked_by_agent"] == 1
    assert episodes[0]["min_distance_observed"] == 0


def test_resource_access_episode_marks_unresolved_target_as_censored_at_end():
    records = [
        {"step": 1, "individual_type": "HERBIVORE", "individual_id": "V001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "selected_target_distance_manhattan": 3, "selected_target_path_available": True, "resource_need_priority": "THIRST", "thirst_after": 60, "hunger_after": 10, "movement_block_reason": "", "water_consumption_succeeded": False},
        {"step": 2, "individual_type": "HERBIVORE", "individual_id": "V001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "selected_target_distance_manhattan": 2, "selected_target_path_available": True, "resource_need_priority": "THIRST", "thirst_after": 70, "hunger_after": 10, "movement_block_reason": "", "water_consumption_succeeded": False},
    ]
    episodes = _resource_access_episode_rows(1, 731, records)
    assert len(episodes) == 1
    assert episodes[0]["successful"] is False
    assert episodes[0]["outcome"] == "SIMULATION_END"
    assert episodes[0]["duration_steps"] == 1


def test_resource_access_episode_starts_only_with_matching_active_need():
    records = [
        {"step": 1, "individual_type": "HERBIVORE", "individual_id": "V001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "resource_need_priority": "NONE", "water_consumption_succeeded": False},
        {"step": 2, "individual_type": "HERBIVORE", "individual_id": "V001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "resource_need_priority": "THIRST", "water_consumption_succeeded": False},
        {"step": 3, "individual_type": "HERBIVORE", "individual_id": "V001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "resource_need_priority": "NONE", "water_consumption_succeeded": False},
        {"step": 4, "individual_type": "HERBIVORE", "individual_id": "V001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "resource_need_priority": "THIRST", "water_consumption_succeeded": True},
    ]
    episodes = _resource_access_episode_rows(1, 731, records)
    assert len(episodes) == 2
    assert episodes[0]["start_step"] == 2
    assert episodes[0]["end_step"] == 3
    assert episodes[0]["outcome"] == "NEED_NO_LONGER_PRIORITY"
    assert episodes[0]["duration_steps"] == 1
    assert episodes[0]["active_search_steps"] == 1
    assert episodes[1]["start_step"] == 4
    assert episodes[1]["successful"] is True
    assert episodes[1]["duration_steps"] == 0


def test_carnivore_food_target_is_not_counted_as_generic_resource_access():
    records = [
        {"step": 1, "individual_type": "CARNIVORE", "individual_id": "C001", "selected_target_kind": "FOOD", "selected_target_x": 4, "selected_target_y": 2, "resource_need_priority": "HUNGER", "food_consumption_succeeded": False},
        {"step": 2, "individual_type": "CARNIVORE", "individual_id": "C001", "selected_target_kind": "FOOD", "selected_target_x": 4, "selected_target_y": 2, "resource_need_priority": "HUNGER", "food_consumption_succeeded": True},
    ]
    assert _resource_access_episode_rows(1, 731, records) == []


def test_episode_summary_excludes_nonpriority_and_end_censored_episodes_from_success_rate():
    from run_ecosystem_audit import _resource_access_episode_summary

    episodes = [
        {"run": 1, "seed": 7, "individual_type": "HUMAN", "resource_kind": "WATER", "successful": True, "outcome": "SUCCESS", "duration_steps": 2, "blocked_by_agent": 0, "blocked_by_animal": 0, "blocked_by_obstacle": 0, "min_distance_observed": 0},
        {"run": 1, "seed": 7, "individual_type": "HUMAN", "resource_kind": "WATER", "successful": False, "outcome": "NEED_NO_LONGER_PRIORITY", "duration_steps": 4, "blocked_by_agent": 0, "blocked_by_animal": 0, "blocked_by_obstacle": 0, "min_distance_observed": 1},
        {"run": 1, "seed": 7, "individual_type": "HUMAN", "resource_kind": "WATER", "successful": False, "outcome": "SIMULATION_END", "duration_steps": 5, "blocked_by_agent": 0, "blocked_by_animal": 0, "blocked_by_obstacle": 0, "min_distance_observed": 2},
        {"run": 1, "seed": 7, "individual_type": "HUMAN", "resource_kind": "WATER", "successful": False, "outcome": "TARGET_LOST", "duration_steps": 3, "blocked_by_agent": 0, "blocked_by_animal": 0, "blocked_by_obstacle": 0, "min_distance_observed": 1},
    ]
    summary = _resource_access_episode_summary(episodes)[0]
    assert summary["episodes_total"] == 4
    assert summary["episodes_resolved"] == 2
    assert summary["episodes_excluded_from_success_rate"] == 2
    assert summary["success_rate"] == 0.5
    assert summary["mean_steps_to_success"] == 2


def test_resource_success_is_counted_even_if_need_priority_clears_on_success_step():
    records = [
        {"step": 1, "individual_type": "HUMAN", "individual_id": "H001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "selected_target_distance_manhattan": 1, "resource_need_priority": "THIRST", "water_consumption_succeeded": False},
        {"step": 2, "individual_type": "HUMAN", "individual_id": "H001", "selected_target_kind": "WATER", "selected_target_x": 4, "selected_target_y": 2, "selected_target_distance_manhattan": 0, "resource_need_priority": "NONE", "water_consumption_succeeded": True},
    ]
    episodes = _resource_access_episode_rows(1, 731, records)
    assert len(episodes) == 1
    assert episodes[0]["outcome"] == "SUCCESS"
    assert episodes[0]["duration_steps"] == 1
    assert episodes[0]["active_search_steps"] == 1


def test_herbivore_food_success_uses_pre_action_priority_and_target():
    """A plant can disappear and hunger can fall below threshold in the eating step."""
    records = [
        {
            "step": 17, "individual_type": "HERBIVORE", "individual_id": "V001",
            "selected_target_kind": "FOOD", "selected_target_x": 8, "selected_target_y": 9,
            "selected_target_distance_manhattan": 1,
            "resource_need_priority": "NONE", "resource_need_priority_before_action": "HUNGER",
            "food_acquisition_succeeded": True, "food_consumption_succeeded": True,
            "hunger_before": 48, "hunger_after": 14, "termination_cause": "RUNNING",
        }
    ]
    episodes = _resource_access_episode_rows(1, 7200, records)
    assert len(episodes) == 1
    assert episodes[0]["resource_kind"] == "FOOD"
    assert episodes[0]["outcome"] == "SUCCESS"
    assert episodes[0]["successful"] is True
    assert episodes[0]["start_step"] == episodes[0]["end_step"] == 17


def test_resource_summary_distinguishes_food_events_with_and_without_matching_attempt():
    from run_ecosystem_audit import _resource_access_summary

    records = [
        {
            "individual_type": "HERBIVORE", "resource_need_priority": "NONE",
            "resource_need_priority_before_action": "HUNGER", "selected_target_kind": "FOOD",
            "resource_access_target_kind_before_action": "FOOD",
            "food_acquisition_succeeded": True, "food_consumption_succeeded": True,
        },
        {
            "individual_type": "HERBIVORE", "resource_need_priority": "NONE",
            "resource_need_priority_before_action": "NONE", "selected_target_kind": "OTHER",
            "resource_access_target_kind_before_action": "OTHER",
            "food_acquisition_succeeded": True, "food_consumption_succeeded": True,
        },
    ]
    row = _resource_access_summary(1, 7200, records)[0]
    assert row["food_acquisition_successes"] == 2
    assert row["food_consumption_successes"] == 2
    assert row["food_acquisition_events_with_matching_priority_target"] == 1
    assert row["food_acquisition_events_without_matching_priority_target"] == 1
    assert row["food_consumption_events_with_matching_priority_target"] == 1
    assert row["food_consumption_events_without_matching_priority_target"] == 1
