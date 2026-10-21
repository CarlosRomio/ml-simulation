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
            "prey_killed", "hunger_reduction_from_meat", "termination_cause"}.issubset(history[0])
    assert summary[0]["individual_id"] == "C001"
    assert int(summary[0]["steps_observed"]) > 0


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
