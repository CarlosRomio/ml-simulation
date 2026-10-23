from agents.agent import Agent
from agents.needs import AgentNeeds
from animals.carnivore import Carnivore
from configuration.simulation_config import SimulationConfig
from environment.world import World
from run_ecosystem_audit import run_audit
from simulation.simulation import Simulation


def test_carnivore_hunt_diagnostics_capture_starvation_without_visible_prey():
    world = World(width=7, height=7, food_count=0, obstacle_count=0, water_count=0)
    human = Agent(0, 0)
    needs = AgentNeeds(
        max_health=120.0, health=1.0, max_energy=80.0, energy=80.0,
        hunger=89.0, thirst=20.0, hunger_per_step=1.0, thirst_per_step=0.0,
        starvation_threshold=90.0, starvation_damage_per_step=1.0,
    )
    carnivore = Carnivore(6, 6, vision_radius=1, needs=needs)
    simulation = Simulation(
        world, agents=[human], carnivores=[carnivore], seed_spawn_count=0,
    )

    simulation.step()

    assert len(simulation.carnivore_hunt_history) == 1
    record = simulation.carnivore_hunt_history[0]
    assert record["individual_id"] == "C001"
    assert record["visible_humans"] == 0
    assert record["visible_herbivores"] == 0
    assert record["attack_attempted"] is False
    assert record["termination_cause"] == "STARVATION"
    assert record["hunger_after"] >= 90.0


def test_ecosystem_audit_exports_carnivore_hunt_history_and_summary(tmp_path):
    config = SimulationConfig(
        width=12, height=12, food_density=0.03, obstacle_density=0.0,
        water_density=0.01, wood_density=0.0, stone_density=0.0,
        agent_count=2, herbivore_count=2, carnivore_count=1, vision_radius=4,
    )
    output = tmp_path / "audit"
    run_audit(
        runs=1, steps=8, seed=942, workers=1, config=config,
        output=output, sample_every=2, seed_spawn_count=0, max_plants=20,
    )

    import csv
    with (output / "carnivore_hunt_history.csv").open(encoding="utf-8-sig", newline="") as handle:
        history = list(csv.DictReader(handle))
    with (output / "carnivore_hunt_summary.csv").open(encoding="utf-8-sig", newline="") as handle:
        summary = list(csv.DictReader(handle))

    assert history
    assert summary
    assert {"nearest_prey_distance", "visible_humans", "visible_herbivores", "attack_attempted",
            "prey_killed", "hunger_reduction_from_meat", "termination_cause",
            "selected_prey_type", "selected_prey_id", "selected_prey_distance_progress",
            "selected_prey_risk_score", "selected_prey_nearby_humans", "target_selection_reason",
            "nearby_human_defenders", "attack_target_id", "attack_risk_score", "attack_nearby_humans",
            "attack_selection_reason", "attack_skipped_reason", "retreat_decision", "retreat_reason",
            "retreat_attempted", "retreat_success", "health_recovery_eligible",
            "health_recovered_this_step", "health_recovery_source", "health_recovery_block_reason"}.issubset(history[0])
    with (output / "runs.csv").open(encoding="utf-8-sig", newline="") as handle:
        run_rows = list(csv.DictReader(handle))
    assert {"herbivores_killed_by_humans", "herbivores_killed_by_carnivores",
            "carnivore_prey_killed_from_hunt_history", "carnivore_prey_killed_from_death_causes",
            "carnivore_kill_accounting_delta", "human_predation_accounting_delta",
            "herbivore_predation_accounting_delta", "carnivore_kill_accounting_valid"}.issubset(run_rows[0])
    assert int(run_rows[0]["carnivore_kill_accounting_delta"]) == 0
    assert int(run_rows[0]["carnivore_kill_accounting_valid"]) == 1
    assert summary[0]["individual_id"] == "C001"
    assert int(summary[0]["steps_observed"]) > 0
    with (output / "activity_summary.csv").open(encoding="utf-8-sig", newline="") as handle:
        activity_summary = list(csv.DictReader(handle))
    assert activity_summary
    assert {"health_recovered_this_step_sum", "health_recovery_steps",
            "health_recovery_blocked_damage_steps", "health_recovery_blocked_need_steps"}.issubset(activity_summary[0])
    assert {"hunt_episodes", "distinct_prey_targeted", "target_switches",
            "mean_selected_prey_distance_progress", "retreat_decisions", "retreat_attempts",
            "successful_retreats", "health_recovered_total", "health_recovery_steps"}.issubset(summary[0])


def test_audit_death_cause_counts_are_exclusive_and_keep_contributing_damage(tmp_path):
    config = SimulationConfig(
        width=12, height=12, food_density=0.03, obstacle_density=0.0,
        water_density=0.01, wood_density=0.0, stone_density=0.0,
        agent_count=1, herbivore_count=1, carnivore_count=1, vision_radius=4,
    )
    output = tmp_path / "audit_death_causes"
    run_audit(
        runs=1, steps=8, seed=1942, workers=1, config=config,
        output=output, sample_every=2, seed_spawn_count=0, max_plants=20,
    )
    import csv
    with (output / "carnivore_hunt_summary.csv").open(encoding="utf-8-sig", newline="") as handle:
        summary = list(csv.DictReader(handle))
    assert "starvation_damage_present_at_death" in summary[0]
    assert "dehydration_damage_present_at_death" in summary[0]
    # A living individual has no primary death cause and cannot be classified as
    # having died of starvation merely because of its physiological state.
    for row in summary:
        if not row["death_cause"]:
            assert row["starvation_death"] == "False"
            assert row["dehydration_death"] == "False"


def test_defense_death_with_starvation_damage_is_counted_as_defense_only():
    from run_ecosystem_audit import _count_deaths_by_primary_cause, _carnivore_hunt_summary

    terminal = {
        "individual_type": "CARNIVORE", "individual_id": "C001",
        "step": 44, "health_after": 0, "termination_cause": "DEFENSE",
        "damage_causes": "STARVATION;DEFENSE", "hunger_after": 95,
        "thirst_after": 30, "stamina_after": 2, "nearest_prey_distance": 1,
        "visible_humans": 1, "visible_herbivores": 0,
        "hunger_reduction_from_meat": 0, "attack_attempted": False,
        "prey_killed": False, "defense_attacks_received": 1,
        "damage_received_from_defense": 20,
    }
    deaths = {("CARNIVORE", "C001"): terminal}
    assert _count_deaths_by_primary_cause(deaths, "CARNIVORE", "DEFENSE") == 1
    assert _count_deaths_by_primary_cause(deaths, "CARNIVORE", "STARVATION") == 0

    summary = _carnivore_hunt_summary(1, 7200, [terminal])[0]
    assert summary["death_cause"] == "DEFENSE"
    assert summary["starvation_death"] is False
    assert summary["starvation_damage_present_at_death"] is True


def test_carnivore_hunt_summary_splits_episodes_when_prey_identity_changes():
    from run_ecosystem_audit import _carnivore_hunt_summary

    records = [
        {"individual_id": "C001", "step": 1, "selected_prey_id": "V001", "selected_prey_distance_progress": 1},
        {"individual_id": "C001", "step": 2, "selected_prey_id": "V001", "selected_prey_distance_progress": 0},
        {"individual_id": "C001", "step": 3, "selected_prey_id": "V002", "selected_prey_distance_progress": -1},
        {"individual_id": "C001", "step": 4, "selected_prey_id": "", "selected_prey_distance_progress": ""},
        {"individual_id": "C001", "step": 5, "selected_prey_id": "V002", "selected_prey_distance_progress": 2},
    ]

    summary = _carnivore_hunt_summary(1, 123, records)[0]

    assert summary["hunt_episodes"] == 3
    assert summary["distinct_prey_targeted"] == 2
    assert summary["target_switches"] == 1
    assert summary["mean_selected_prey_distance_progress"] == 0.5
    assert summary["steps_selected_prey_distance_increased"] == 1
    assert summary["steps_selected_prey_distance_unchanged"] == 1


def test_carnivore_kill_accounting_distinguishes_human_hunts_from_predation():
    from run_ecosystem_audit import _carnivore_kill_accounting

    records = [
        {"prey_killed": True, "attack_target_type": "HUMAN"},
        {"prey_killed": False, "attack_target_type": "HERBIVORE"},
        {"prey_killed": True, "attack_target_type": "HERBIVORE"},
    ]
    counts = _carnivore_kill_accounting(
        records,
        human_deaths_predation=1,
        herbivore_deaths_predation=1,
        herbivore_deaths_hunting=5,
    )

    assert counts["herbivores_killed_by_humans"] == 5
    assert counts["herbivores_killed_by_carnivores"] == 1
    assert counts["carnivore_prey_killed_from_hunt_history"] == 2
    assert counts["carnivore_prey_killed_from_death_causes"] == 2
    assert counts["carnivore_kill_accounting_delta"] == 0
    assert counts["human_predation_accounting_delta"] == 0
    assert counts["herbivore_predation_accounting_delta"] == 0
    assert counts["carnivore_kill_accounting_valid"] == 1


def test_carnivore_kill_accounting_detects_species_level_mismatch():
    from run_ecosystem_audit import _carnivore_kill_accounting

    counts = _carnivore_kill_accounting(
        [{"prey_killed": True, "attack_target_type": "HUMAN"}],
        human_deaths_predation=0,
        herbivore_deaths_predation=1,
        herbivore_deaths_hunting=0,
    )
    assert counts["carnivore_kill_accounting_delta"] == 0
    assert counts["human_predation_accounting_delta"] == 1
    assert counts["herbivore_predation_accounting_delta"] == -1
    assert counts["carnivore_kill_accounting_valid"] == 0


def test_retreat_outcome_requires_a_complete_safe_followup_window():
    from run_ecosystem_audit import _annotate_retreat_outcomes

    rows = [
        {"individual_id": "C001", "step": 10, "retreat_attempted": True,
         "nearest_human_distance": 3, "human_threat_count_within_2": 0,
         "defense_attacks_received": 0, "damage_received_from_defense": 0,
         "termination_cause": "RUNNING"},
        {"individual_id": "C001", "step": 11, "retreat_attempted": False,
         "nearest_human_distance": 4, "human_threat_count_within_2": 0,
         "defense_attacks_received": 0, "damage_received_from_defense": 0,
         "termination_cause": "RUNNING"},
        {"individual_id": "C001", "step": 12, "retreat_attempted": False,
         "nearest_human_distance": 5, "human_threat_count_within_2": 0,
         "defense_attacks_received": 0, "damage_received_from_defense": 0,
         "termination_cause": "RUNNING"},
        {"individual_id": "C001", "step": 13, "retreat_attempted": False,
         "nearest_human_distance": 4, "human_threat_count_within_2": 0,
         "defense_attacks_received": 0, "damage_received_from_defense": 0,
         "termination_cause": "RUNNING"},
    ]
    _annotate_retreat_outcomes(rows, window_steps=3, threat_radius=2)
    assert rows[0]["retreat_outcome"] == "SUCCESS"
    assert rows[0]["retreat_success"] is True
    assert rows[0]["retreat_followup_steps"] == 3


def test_retreat_fails_if_defensive_damage_occurs_during_followup():
    from run_ecosystem_audit import _annotate_retreat_outcomes

    rows = [
        {"individual_id": "C001", "step": 10, "retreat_attempted": True},
        {"individual_id": "C001", "step": 11, "nearest_human_distance": 4,
         "human_threat_count_within_2": 0, "defense_attacks_received": 1,
         "damage_received_from_defense": 10, "termination_cause": "RUNNING"},
        {"individual_id": "C001", "step": 12, "nearest_human_distance": 4,
         "human_threat_count_within_2": 0, "defense_attacks_received": 0,
         "damage_received_from_defense": 0, "termination_cause": "RUNNING"},
        {"individual_id": "C001", "step": 13, "nearest_human_distance": 4,
         "human_threat_count_within_2": 0, "defense_attacks_received": 0,
         "damage_received_from_defense": 0, "termination_cause": "RUNNING"},
    ]
    _annotate_retreat_outcomes(rows, window_steps=3, threat_radius=2)
    assert rows[0]["retreat_outcome"] == "FAILURE"
    assert rows[0]["retreat_success"] is False
    assert rows[0]["retreat_failure_reason"] == "DEFENSE_DAMAGE_DURING_FOLLOWUP"


def test_retreat_is_censored_when_simulation_ends_before_followup_window():
    from run_ecosystem_audit import _annotate_retreat_outcomes

    rows = [
        {"individual_id": "C001", "step": 10, "retreat_attempted": True},
        {"individual_id": "C001", "step": 11, "nearest_human_distance": 4,
         "human_threat_count_within_2": 0, "defense_attacks_received": 0,
         "damage_received_from_defense": 0, "termination_cause": "RUNNING"},
    ]
    _annotate_retreat_outcomes(rows, window_steps=3, threat_radius=2)
    assert rows[0]["retreat_outcome"] == "CENSORED"
    assert rows[0]["retreat_success"] is False
    assert rows[0]["retreat_followup_steps"] == 1


def test_retreat_can_succeed_when_humans_remain_in_risk_radius_but_cannot_attack():
    from run_ecosystem_audit import _annotate_retreat_outcomes

    rows = [
        {"individual_id": "C001", "step": 10, "retreat_attempted": True},
        {"individual_id": "C001", "step": 11, "nearest_human_distance": 2,
         "human_threat_count_within_2": 1, "human_threat_count_adjacent": 0,
         "defense_attacks_received": 0, "damage_received_from_defense": 0, "termination_cause": "RUNNING"},
        {"individual_id": "C001", "step": 12, "nearest_human_distance": 4,
         "human_threat_count_within_2": 0, "defense_attacks_received": 0,
         "damage_received_from_defense": 0, "termination_cause": "RUNNING"},
        {"individual_id": "C001", "step": 13, "nearest_human_distance": 4,
         "human_threat_count_within_2": 0, "defense_attacks_received": 0,
         "damage_received_from_defense": 0, "termination_cause": "RUNNING"},
    ]
    _annotate_retreat_outcomes(rows, window_steps=3, threat_radius=2)
    assert rows[0]["retreat_outcome"] == "SUCCESS"
    assert rows[0]["retreat_followup_threat_steps"] == 1
    assert rows[0]["retreat_followup_attack_range_steps"] == 0


def test_retreat_fails_if_agent_dies_during_followup_window():
    from run_ecosystem_audit import _annotate_retreat_outcomes

    rows = [
        {"individual_id": "C001", "step": 10, "retreat_attempted": True},
        {"individual_id": "C001", "step": 11, "nearest_human_distance": 4,
         "human_threat_count_within_2": 0, "defense_attacks_received": 0,
         "damage_received_from_defense": 0, "termination_cause": "RUNNING"},
        {"individual_id": "C001", "step": 12, "nearest_human_distance": 4,
         "human_threat_count_within_2": 0, "defense_attacks_received": 0,
         "damage_received_from_defense": 0, "termination_cause": "DEFENSE"},
    ]
    _annotate_retreat_outcomes(rows, window_steps=3, threat_radius=2)
    assert rows[0]["retreat_outcome"] == "FAILURE"
    assert rows[0]["retreat_failure_reason"] == "DIED_DURING_FOLLOWUP"
