import random

import pytest

from agents.agent import Agent
from agents.cognition import ActionCandidate, DecisionEngine, ExperienceMemory, Personality
from agents.factory import AgentFactory
from environment.world import World


def test_personality_traits_are_validated_and_serializable():
    personality = Personality(
        curiosity=0.1,
        risk_aversion=0.2,
        sociability=0.3,
        aggressiveness=0.4,
        persistence=0.5,
        reward_sensitivity=0.6,
    )
    assert personality.to_dict()["curiosity"] == 0.1
    with pytest.raises(ValueError):
        Personality(curiosity=1.01)


def test_random_personality_is_reproducible_and_varied():
    first = Personality.randomized(random.Random(123))
    second = Personality.randomized(random.Random(123))
    third = Personality.randomized(random.Random(124))
    assert first == second
    assert first != third
    assert all(0.0 <= value <= 1.0 for value in first.to_dict().values())


def test_factory_creates_reproducible_personality_profiles():
    world_a = World(width=12, height=12, food_count=0, obstacle_count=0, rng=random.Random(1))
    world_b = World(width=12, height=12, food_count=0, obstacle_count=0, rng=random.Random(1))
    agents_a = AgentFactory.create_agents(world_a, 8, 4, seed=515)
    agents_b = AgentFactory.create_agents(world_b, 8, 4, seed=515)
    profiles_a = [agent.personality.to_dict() for agent in agents_a]
    profiles_b = [agent.personality.to_dict() for agent in agents_b]
    assert profiles_a == profiles_b
    assert len({tuple(profile.values()) for profile in profiles_a}) == len(profiles_a)


def test_decision_engine_penalizes_risk_more_for_cautious_personality():
    engine = DecisionEngine()
    risky = ActionCandidate("RISKY", "HUNT", expected_benefit=0.9, risk=0.9)
    safe = ActionCandidate("SAFE", "GATHER", expected_benefit=0.65, risk=0.05)
    cautious = Personality(risk_aversion=0.95, reward_sensitivity=0.5)
    bold = Personality(risk_aversion=0.05, reward_sensitivity=0.5)
    assert engine.evaluate(safe, cautious).score > engine.evaluate(risky, cautious).score
    assert engine.evaluate(risky, bold).score > engine.evaluate(safe, bold).score


def test_experience_memory_updates_running_mean_reward():
    memory = ExperienceMemory()
    memory.observe("FORAGE", 1.0)
    memory.observe("FORAGE", -0.5)
    assert memory.sample_count("FORAGE") == 2
    assert memory.expected_reward("FORAGE") == pytest.approx(0.25)
    with pytest.raises(ValueError):
        memory.observe("FORAGE", 2.0)


def test_learned_outcome_can_change_action_ranking():
    engine = DecisionEngine()
    personality = Personality()
    memory = ExperienceMemory()
    candidates = [
        ActionCandidate("FORAGE", "FORAGE", expected_benefit=0.5),
        ActionCandidate("REST", "REST", expected_benefit=0.55),
    ]
    before = engine.choose(candidates, personality, random.Random(1), memory)
    memory.observe("FORAGE", 1.0)
    memory.observe("FORAGE", 1.0)
    after = engine.choose(candidates, personality, random.Random(1), memory)
    assert before is not None and after is not None
    assert before.candidate.action_id == "REST"
    assert after.candidate.action_id == "FORAGE"


def test_agent_exploration_records_interpretable_decision_trace():
    world = World(width=7, height=7, food_count=0, obstacle_count=0)
    agent = Agent(3, 3, rng=random.Random(9))
    action = agent.choose_action([], world)
    assert action in {(0, -1), (0, 1), (-1, 0), (1, 0)}
    assert agent.last_decision_trace is not None
    assert agent.last_decision_trace["intent"] == "EXPLORATION"
    assert agent.last_decision_trace["alternatives"]
    agent.record_action_outcome(0.5)
    assert agent.experience_memory.sample_count("EXPLORE") == 1


def test_simulation_snapshot_exports_personality_traits():
    from simulation.simulation import Simulation

    world = World(width=8, height=8, food_count=0, obstacle_count=0)
    agent = Agent(3, 3, personality=Personality(
        curiosity=0.11, risk_aversion=0.22, sociability=0.33,
        aggressiveness=0.44, persistence=0.55, reward_sensitivity=0.66,
    ))
    simulation = Simulation(world, agents=[agent], seed_spawn_count=0)
    row = simulation.social_agent_history[0]
    assert row["personality_curiosity"] == 0.11
    assert row["personality_risk_aversion"] == 0.22
    assert row["personality_aggressiveness"] == 0.44
    assert row["personality_persistence"] == 0.55
    assert row["personality_reward_sensitivity"] == 0.66


def test_action_outcome_must_follow_cognitive_decision_and_cannot_be_duplicated():
    world = World(width=7, height=7, food_count=0, obstacle_count=0)
    agent = Agent(3, 3, rng=random.Random(19))
    with pytest.raises(RuntimeError):
        agent.record_action_outcome(0.5)
    agent.choose_action([], world)
    agent.record_action_outcome(0.5)
    with pytest.raises(RuntimeError):
        agent.record_action_outcome(0.5)


def test_cognitive_selector_prefers_food_when_hunger_is_urgent():
    from environment.resources import Food
    from agents.needs import AgentNeeds

    world = World(width=9, height=9, food_count=0, obstacle_count=0)
    world.get_cell(4, 2).resource = Food()
    needs = AgentNeeds(hunger=85.0, thirst=20.0, energy=100.0)
    personality = Personality(
        curiosity=0.1, risk_aversion=0.5, sociability=0.1,
        aggressiveness=0.1, persistence=0.5, reward_sensitivity=0.5,
    )
    agent = Agent(2, 2, needs=needs, personality=personality, rng=random.Random(12))

    agent.choose_action([], world)

    assert agent.target == (4, 2)
    assert agent.target_intent == "SEEK_FOOD"
    assert agent.last_decision_trace["action_id"] == "SEEK_FOOD"
    assert {item["action_id"] for item in agent.last_decision_trace["alternatives"]} >= {"SEEK_FOOD", "EXPLORE"}


def test_cognitive_selector_prefers_water_when_thirst_is_urgent():
    from environment.resources import Food, Water
    from agents.needs import AgentNeeds

    world = World(width=9, height=9, food_count=0, obstacle_count=0)
    world.get_cell(4, 2).resource = Water()
    world.get_cell(7, 7).resource = Food()
    needs = AgentNeeds(hunger=20.0, thirst=85.0, energy=100.0)
    personality = Personality(
        curiosity=0.1, risk_aversion=0.5, sociability=0.1,
        aggressiveness=0.1, persistence=0.5, reward_sensitivity=0.5,
    )
    agent = Agent(2, 2, needs=needs, personality=personality, rng=random.Random(13))

    agent.choose_action([], world)

    assert agent.target == (4, 2)
    assert agent.target_intent == "SEEK_WATER"
    assert agent.last_decision_trace["action_id"] == "SEEK_WATER"


def test_cognitive_selector_can_choose_rest_when_energy_is_low():
    from agents.needs import AgentNeeds

    world = World(width=7, height=7, food_count=0, obstacle_count=0)
    needs = AgentNeeds(hunger=20.0, thirst=20.0, energy=20.0)
    personality = Personality(
        curiosity=0.1, risk_aversion=0.5, sociability=0.1,
        aggressiveness=0.1, persistence=0.5, reward_sensitivity=0.5,
    )
    agent = Agent(3, 3, needs=needs, personality=personality, rng=random.Random(14))

    action = agent.choose_action([], world)

    assert action == (0, 0)
    assert agent.last_behavior_intent == "REST"
    assert agent.last_decision_trace["action_id"] == "REST"
