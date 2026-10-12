from agents.needs import AgentNeeds
from agents.agent import Agent


def test_needs_increase_over_time_and_damage_at_critical_levels():
    needs = AgentNeeds(
        hunger=89.0,
        thirst=89.0,
        hunger_per_step=1.0,
        thirst_per_step=1.0,
        starvation_threshold=90.0,
        dehydration_threshold=90.0,
        damage_per_step=5.0,
    )
    needs.advance_step()
    assert needs.hunger == 90.0
    assert needs.thirst == 90.0
    assert needs.health == 90.0


def test_food_and_water_reduce_their_corresponding_needs():
    needs = AgentNeeds(hunger=60.0, thirst=70.0)
    needs.eat(20.0)
    needs.drink(30.0)
    assert needs.hunger == 40.0
    assert needs.thirst == 40.0


def test_agent_keeps_legacy_energy_api_and_exposes_new_needs():
    agent = Agent(x=1, y=1, max_energy=80.0)
    assert agent.energy == 80.0
    assert agent.health == 100.0
    assert agent.hunger == 20.0
    assert agent.thirst == 20.0
    agent.consume_energy(10.0)
    assert agent.energy == 70.0
    agent.rest(5.0)
    assert agent.energy == 75.0


def test_dehydration_damage_can_be_configured_independently():
    needs = AgentNeeds(
        thirst=89.0,
        thirst_per_step=1.0,
        dehydration_threshold=90.0,
        damage_per_step=1.0,
        dehydration_damage_per_step=7.0,
    )
    needs.advance_step()
    assert needs.health == 93.0


def test_dehydration_damage_may_be_disabled_for_control_experiment():
    needs = AgentNeeds(
        thirst=89.0,
        thirst_per_step=1.0,
        dehydration_threshold=90.0,
        dehydration_damage_per_step=0.0,
    )
    needs.advance_step()
    assert needs.thirst == 90.0
    assert needs.health == 100.0


def test_invalid_dehydration_damage_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        AgentNeeds(dehydration_damage_per_step=-1.0)


def test_simulation_records_first_dehydration_damage_and_death_cause():
    from environment.world import World
    from simulation.simulation import Simulation

    needs = AgentNeeds(
        max_health=1.0,
        health=1.0,
        max_energy=1000.0,
        energy=1000.0,
        thirst=89.0,
        thirst_per_step=1.0,
        dehydration_threshold=90.0,
        damage_per_step=1.0,
    )
    agent = Agent(x=1, y=1, max_energy=1000.0, needs=needs)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(World(width=3, height=3, food_count=0), agent)

    simulation.step()

    metrics = simulation.metrics
    assert not agent.alive
    assert metrics.termination_cause == "DEHYDRATION"
    assert metrics.critical_thirst_steps == 1
    assert metrics.dehydration_damage_steps == 1
    assert metrics.first_dehydration_damage_step == 1
