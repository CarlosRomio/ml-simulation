import csv

import pytest

from agents.agent import Agent
from agents.needs import AgentNeeds
from configuration.simulation_config import SimulationConfig
from environment.resources import Water
from environment.world import World
from metrics.physiology_exporter import PhysiologyExporter
from simulation.simulation import Simulation


def test_energy_is_stamina_and_never_classifies_death_as_starvation():
    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    needs = AgentNeeds(energy=0.0, hunger=20.0, thirst=20.0)
    agent = Agent(1, 1, needs=needs)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)

    simulation.step()

    assert agent.alive
    assert simulation.metrics.termination_cause == "RUNNING"
    assert simulation.metrics.final_energy == 7.0  # recuperação adaptativa: bônus com reserva zerada


def test_movement_consumes_stamina_and_rest_recovers_it():
    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    agent = Agent(2, 2)
    agent.choose_action = lambda nearby_cells, world: (1, 0)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    simulation.step()
    assert agent.energy == 99.0
    assert simulation.diagnostic_history[-1]["movement_energy_cost"] == 1.0

    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation.step()
    assert agent.energy == 100.0
    assert simulation.diagnostic_history[-1]["rest_energy_recovered"] == 1.0


def test_first_lethal_physiological_cause_is_audited_without_false_secondary_damage():
    needs = AgentNeeds(
        health=1.0, hunger=89.0, thirst=89.0,
        hunger_per_step=1.0, thirst_per_step=1.0,
        starvation_threshold=90.0, dehydration_threshold=90.0,
        starvation_damage_per_step=1.0, dehydration_damage_per_step=1.0,
    )
    needs.advance_step()
    assert needs.health == 0.0
    assert set(needs.last_damage_causes) == {"STARVATION"}
    # A primeira causa letal consome a saúde restante; dano posterior não é efetivo.
    assert needs.damage_by_cause == {"STARVATION": 1.0}


def test_need_thresholds_cannot_exceed_their_scale():
    with pytest.raises(ValueError, match="starvation_threshold"):
        AgentNeeds(max_hunger=50, starvation_threshold=51)
    with pytest.raises(ValueError, match="dehydration_threshold"):
        AgentNeeds(max_thirst=50, dehydration_threshold=51)


def test_population_history_contains_separate_species_physiology():
    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    agent = Agent(1, 1)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    record = simulation.population_history[0]
    assert record["human_mean_health"] == 100.0
    assert record["human_mean_hunger"] == 20.0
    assert record["herbivore_mean_health"] == 0.0
    assert record["carnivore_mean_thirst"] == 0.0


def test_diagnostic_records_have_initial_state_and_each_step(tmp_path):
    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    agent = Agent(1, 1)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    simulation.step()
    output = PhysiologyExporter.export_individual_csv(simulation, tmp_path / "physiology.csv")

    with output.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [int(row["step"]) for row in rows] == [0, 1]
    assert float(rows[1]["health_before"]) == 100.0
    assert float(rows[1]["hunger_after"]) > float(rows[1]["hunger_before"])
    assert "movement_energy_cost" in rows[1]
    assert rows[1]["termination_cause"] == "RUNNING"


def test_config_validates_and_propagates_hunger_parameters():
    config = SimulationConfig(
        width=5, height=5, food_density=0, obstacle_density=0, water_density=0,
        hunger_per_step=1.5, starvation_threshold=70, starvation_damage_per_step=2.0,
    )
    config.validate()
    assert config.hunger_per_step == 1.5
    assert config.starvation_threshold == 70
    with pytest.raises(ValueError):
        SimulationConfig(width=5, height=5, starvation_threshold=101).validate()


def test_both_physiological_causes_are_recorded_when_both_apply_effective_damage():
    needs = AgentNeeds(
        health=1.5, hunger=89.0, thirst=89.0,
        hunger_per_step=1.0, thirst_per_step=1.0,
        starvation_threshold=90.0, dehydration_threshold=90.0,
        starvation_damage_per_step=1.0, dehydration_damage_per_step=1.0,
    )
    needs.advance_step()
    assert needs.health == 0.0
    assert set(needs.last_damage_causes) == {"STARVATION", "DEHYDRATION"}
    assert needs.damage_by_cause == {"STARVATION": 1.0, "DEHYDRATION": 0.5}


def test_population_history_continues_after_all_species_are_dead():
    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    needs = AgentNeeds(health=1.0, hunger=89.0, hunger_per_step=1.0, starvation_threshold=90.0)
    agent = Agent(1, 1, needs=needs)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    simulation.run(3)
    assert len(simulation.population_history) == simulation.steps + 1
    assert simulation.population_history[-1]["alive"] == 0


def test_population_exporter_writes_one_record_per_step(tmp_path):
    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    agent = Agent(1, 1)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    simulation.run(2)
    output = PhysiologyExporter.export_population_csv(simulation, tmp_path / "population.csv")
    with output.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [int(row["step"]) for row in rows] == [0, 1, 2]
    assert "human_all_mean_health" in rows[0]


def test_damage_totals_are_exposed_by_cause_in_individual_metrics():
    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    needs = AgentNeeds(health=10.0, hunger=89.0, hunger_per_step=1.0,
                       starvation_threshold=90.0, starvation_damage_per_step=2.0)
    agent = Agent(1, 1, needs=needs)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    simulation.step()
    assert simulation.metrics.damage_taken_by_cause["STARVATION"] == 2.0
    assert simulation.metrics.starvation_damage_steps == 1
    assert simulation.metrics.first_starvation_damage_step == 1


def test_experiment_result_preserves_step_zero_and_individual_history():
    from experiments.runner import run_single_simulation

    config = SimulationConfig(
        width=5, height=5, food_density=0, obstacle_density=0, water_density=0,
        agent_count=2,
    )
    result = run_single_simulation(config, run_seed=7, max_steps=3, seed_spawn_count=0)
    assert len(result.human_physiology_history) == 2
    assert all(history[0]["step"] == 0 for history in result.human_physiology_history)
    assert all(history[-1]["step"] <= 3 for history in result.human_physiology_history)
