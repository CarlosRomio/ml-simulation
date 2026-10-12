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
    assert agent.hunger == 0.0
    assert agent.thirst == 0.0
    agent.consume_energy(10.0)
    assert agent.energy == 70.0
    agent.rest(5.0)
    assert agent.energy == 75.0
