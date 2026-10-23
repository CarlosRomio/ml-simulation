import csv
import json

from configuration.simulation_config import SimulationConfig
from agents.agent import Agent
from agents.needs import AgentNeeds
from animals.carnivore import Carnivore
from animals.herbivore import Herbivore
from environment.resources import Plant, PlantState, Water
from environment.world import World
from simulation.simulation import Simulation
from run_ecosystem_audit import derive_max_plants, run_audit, _target_progress_episodes


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
    assert "attribute_strength" in initial[0]
    assert "attribute_metabolic_efficiency" in initial[0]
    assert "gene_strength" in initial[0]
    assert "gene_metabolic_efficiency" in initial[0]
    assert initial[0]["attribute_strength"] == initial[0]["gene_strength"]
    assert sampled
    assert "decision_trace" in sampled[0]
    assert "action_reason" in sampled[0]
    assert (out / "action_reason_summary.csv").exists()
    assert "stamina_recovered" in sampled[0]
    assert len(population) == 2 * 9  # passo inicial + 8 passos
    assert summary
    assert manifest["workers"] == 2
    assert manifest["attribute_variation"] == config.attribute_variation
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



def test_plant_capacity_scales_with_world_area_from_reference_density():
    assert derive_max_plants(60, 60) == 300
    assert derive_max_plants(80, 80) == 533
    assert derive_max_plants(100, 100) == 833
    assert derive_max_plants(200, 200) == 3333
    assert derive_max_plants(120, 60) == 600


def test_audit_defaults_to_area_scaled_plant_capacity(tmp_path):
    config = SimulationConfig(
        width=20, height=10, food_density=0.02, obstacle_density=0,
        water_density=0, wood_density=0, stone_density=0,
        agent_count=1, herbivore_count=0, carnivore_count=0, vision_radius=3,
    )
    result = run_audit(
        runs=1, steps=2, seed=932, workers=1, config=config,
        output=tmp_path / "audit", sample_every=1, seed_spawn_count=0,
    )
    assert result["manifest"]["max_plants"] == 17
    assert result["manifest"]["plant_cap_policy"] == "area_scaled_from_reference_density"


def test_target_progress_episodes_measure_distance_and_need_satisfaction():
    records = [
        {
            "step": 1, "individual_type": "HUMAN", "individual_id": "H001",
            "target_intent_before_action": "SEEK_WATER", "target_x_before_action": 5,
            "target_y_before_action": 5, "target_distance_before_action": 3,
            "target_distance_after_action": 2, "target_distance_progress": 1,
            "target_in_interaction_range": False, "target_reached": False,
            "need_satisfied_this_step": False, "movement_block_reason": "",
        },
        {
            "step": 2, "individual_type": "HUMAN", "individual_id": "H001",
            "target_intent_before_action": "SEEK_WATER", "target_x_before_action": 5,
            "target_y_before_action": 5, "target_distance_before_action": 2,
            "target_distance_after_action": 0, "target_distance_progress": 2,
            "target_in_interaction_range": True, "target_reached": True,
            "need_satisfied_this_step": True, "movement_block_reason": "",
        },
        {
            "step": 3, "individual_type": "HUMAN", "individual_id": "H001",
            "target_intent_before_action": "NONE", "target_x_before_action": "",
            "target_y_before_action": "", "target_distance_before_action": "",
            "target_distance_after_action": "", "target_distance_progress": "",
            "target_in_interaction_range": False, "target_reached": False,
            "need_satisfied_this_step": False, "movement_block_reason": "",
        },
    ]

    episodes = _target_progress_episodes(2, 123, records)

    assert len(episodes) == 1
    episode = episodes[0]
    assert episode["duration_steps"] == 2
    assert episode["start_distance"] == 3
    assert episode["end_distance"] == 0
    assert episode["net_distance_progress"] == 3
    assert episode["positive_progress_steps"] == 2
    assert episode["target_reached"] is True
    assert episode["need_satisfied"] is True
    assert episode["outcome"] == "NEED_SATISFIED"


def test_herbivore_target_progress_classifies_water_intent():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, water_count=0)
    world.get_cell(5, 1).resource = Water()
    needs = AgentNeeds(
        max_energy=60.0, energy=60.0, hunger=10.0, thirst=60.0,
        hunger_per_step=0.0, thirst_per_step=0.0,
    )
    herbivore = Herbivore(1, 1, vision_radius=8, needs=needs)
    human = Agent(0, 7)
    human.choose_action = lambda nearby, route_world: (0, 0)
    simulation = Simulation(
        world, agents=[human], herbivores=[herbivore],
        seed_spawn_count=0, max_plants=0, social_behavior_enabled=False,
    )

    simulation.step()

    record = next(row for row in simulation.physiology_activity_history
                  if row["individual_type"] == "HERBIVORE")
    assert record["target_intent_before_action"] == "SEEK_WATER"
    assert record["resource_access_target_kind_before_action"] == "WATER"


def test_carnivore_target_progress_distinguishes_hunt_from_exploration():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, water_count=0)
    human = Agent(5, 6)
    carnivore = Carnivore(6, 6, vision_radius=1)
    carnivore.target = (5, 6)
    simulation = Simulation(
        world, agents=[human], carnivores=[carnivore], seed_spawn_count=0,
        max_plants=0, social_behavior_enabled=False,
    )

    simulation.step()
    hunt_record = next(row for row in simulation.physiology_activity_history
                       if row["individual_type"] == "CARNIVORE")
    assert hunt_record["target_intent_before_action"] == "HUNT"

    # A persistente exploration_target também deve ser registrada, mesmo que
    # Carnivore.target fique None durante a patrulha.
    carnivore.target = None
    carnivore.exploration_target = (2, 2)
    simulation.step()
    exploration_records = [row for row in simulation.physiology_activity_history
                           if row["individual_type"] == "CARNIVORE"]
    assert exploration_records[-1]["target_intent_before_action"] == "EXPLORATION"
    assert exploration_records[-1]["target_x_before_action"] == 2
    assert exploration_records[-1]["target_y_before_action"] == 2


def test_herbivore_target_progress_classifies_food_intent():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, water_count=0)
    world.get_cell(5, 1).resource = Plant(state=PlantState.MATURE)
    needs = AgentNeeds(
        max_energy=60.0, energy=60.0, hunger=60.0, thirst=10.0,
        hunger_per_step=0.0, thirst_per_step=0.0,
    )
    herbivore = Herbivore(1, 1, vision_radius=8, needs=needs)
    human = Agent(0, 7)
    human.choose_action = lambda nearby, route_world: (0, 0)
    simulation = Simulation(
        world, agents=[human], herbivores=[herbivore],
        seed_spawn_count=0, max_plants=0, social_behavior_enabled=False,
    )

    simulation.step()

    record = next(row for row in simulation.physiology_activity_history
                  if row["individual_type"] == "HERBIVORE")
    assert record["target_intent_before_action"] == "SEEK_FOOD"
    assert record["resource_access_target_kind_before_action"] == "FOOD"


def test_audit_caps_workers_to_number_of_runs(tmp_path):
    config = SimulationConfig(
        width=10, height=10, food_density=0.02, obstacle_density=0,
        water_density=0, wood_density=0, stone_density=0,
        agent_count=1, herbivore_count=0, carnivore_count=0, vision_radius=3,
    )
    result = run_audit(
        runs=1, steps=2, seed=933, workers=4, config=config,
        output=tmp_path / "audit", sample_every=1, seed_spawn_count=0, max_plants=10,
    )
    assert result["manifest"]["workers_requested"] == 4
    assert result["manifest"]["workers"] == 1
