import random

import pytest

from agents.agent import Agent
from agents.factory import AgentFactory
from environment.world import World
from simulation.simulation import Simulation


def test_agent_sociability_is_validated_and_stable():
    agent = Agent(2, 2, sociability=0.8)
    assert agent.sociability == 0.8
    with pytest.raises(ValueError):
        Agent(2, 2, sociability=1.1)


def test_factory_assigns_reproducible_individual_sociability():
    world_a = World(width=12, height=12, food_count=0, obstacle_count=0, rng=random.Random(1))
    world_b = World(width=12, height=12, food_count=0, obstacle_count=0, rng=random.Random(1))
    agents_a = AgentFactory.create_agents(world_a, 6, 4, seed=44)
    agents_b = AgentFactory.create_agents(world_b, 6, 4, seed=44)

    traits_a = [agent.sociability for agent in agents_a]
    traits_b = [agent.sociability for agent in agents_b]
    assert traits_a == traits_b
    assert [agent.agent_id for agent in agents_a] == [f"H{i:03d}" for i in range(1, 7)]
    assert all(0.15 <= trait <= 0.95 for trait in traits_a)
    assert len(set(traits_a)) > 1


def test_sociable_agent_moves_toward_human_when_needs_are_not_urgent():
    world = World(width=12, height=8, food_count=0, obstacle_count=0, rng=random.Random(2))
    agent = Agent(2, 2, sociability=0.9)
    other = Agent(8, 2)
    simulation = Simulation(world, agents=[agent, other], seed_spawn_count=0)
    agent.social_neighbors = [(other.x, other.y)]
    agent.occupied_positions = {(other.x, other.y)}

    action = agent.choose_action([], world)

    assert action in {(1, 0), (0, -1), (0, 1), (-1, 0)}
    assert agent.target is not None
    assert agent.path
    assert abs(agent.target[0] - other.x) + abs(agent.target[1] - other.y) == 1


def test_social_drive_does_not_override_urgent_hunger():
    world = World(width=12, height=8, food_count=0, obstacle_count=0, rng=random.Random(2))
    agent = Agent(2, 2, sociability=0.9)
    other = Agent(8, 2)
    agent.needs.hunger = 25.0
    agent.social_neighbors = [(other.x, other.y)]
    agent.occupied_positions = {(other.x, other.y)}

    agent.choose_action([], world)

    assert agent.target is None or abs(agent.target[0] - other.x) + abs(agent.target[1] - other.y) != 2


def test_low_sociability_does_not_seek_social_target():
    world = World(width=12, height=8, food_count=0, obstacle_count=0, rng=random.Random(2))
    agent = Agent(2, 2, sociability=0.2)
    other = Agent(8, 2)
    agent.social_neighbors = [(other.x, other.y)]
    agent.occupied_positions = {(other.x, other.y)}

    agent.choose_action([], world)

    assert agent.target_intent != "SOCIAL_APPROACH"


def test_simulation_updates_visible_social_neighbors_each_step():
    world = World(width=12, height=8, food_count=0, obstacle_count=0, rng=random.Random(3))
    first = Agent(2, 2, sociability=0.9)
    second = Agent(6, 2, sociability=0.9)
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0)

    simulation.step()

    assert (6, 2) in first.social_neighbors
    assert (2, 2) in second.social_neighbors


def test_simulation_assigns_stable_human_ids_and_tracks_pair_affinity():
    world = World(width=12, height=8, food_count=0, obstacle_count=0, rng=random.Random(31))
    first = Agent(2, 2, sociability=0.8)
    second = Agent(4, 2, sociability=0.7)
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0)

    assert first.agent_id == "H001"
    assert second.agent_id == "H002"
    assert first.social_affinities[second.agent_id] == 0.0

    simulation.step()

    affinity = first.social_affinities[second.agent_id]
    assert affinity > 0.0
    assert affinity == second.social_affinities[first.agent_id]
    assert simulation.social_history
    row = simulation.social_history[-1]
    assert {row["agent_a_id"], row["agent_b_id"]} == {"H001", "H002"}
    assert row["within_social_range"] is True
    assert row["affinity_after"] > row["affinity_before"]


def test_repeated_close_encounters_strengthen_affinity_and_are_audited():
    world = World(width=12, height=8, food_count=0, obstacle_count=0, rng=random.Random(32))
    first = Agent(2, 2, sociability=0.9)
    second = Agent(4, 2, sociability=0.9)
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0)
    initial = first.social_affinities[second.agent_id]

    simulation._update_social_relationships([first, second])
    once = first.social_affinities[second.agent_id]
    simulation._update_social_relationships([first, second])
    twice = first.social_affinities[second.agent_id]

    assert initial < once < twice
    assert simulation.social_pair_encounters[("H001", "H002")] == 2
    assert len(simulation.social_history) == 2


def test_large_separation_gradually_decays_affinity():
    world = World(width=20, height=8, food_count=0, obstacle_count=0, rng=random.Random(33))
    first = Agent(1, 1, sociability=0.9)
    second = Agent(15, 1, sociability=0.9)
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0)
    pair = ("H001", "H002")
    simulation.social_pair_affinity[pair] = 0.5
    first.social_affinities[second.agent_id] = 0.5
    second.social_affinities[first.agent_id] = 0.5

    simulation._update_social_relationships([first, second])

    assert first.social_affinities[second.agent_id] == pytest.approx(0.4995)
    assert simulation.social_history[-1]["event"] == "AFFINITY_DECAY"


def test_population_history_contains_social_metrics_and_agent_history_has_ids():
    world = World(width=12, height=8, food_count=0, obstacle_count=0, rng=random.Random(34))
    first = Agent(2, 2, sociability=0.8)
    second = Agent(4, 2, sociability=0.7)
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0)
    simulation.step()

    latest = simulation.population_history[-1]
    assert "social_close_pairs" in latest
    assert "social_mean_pair_affinity" in latest
    assert simulation.social_agent_history[0]["agent_id"] == "H001"
    assert any(row["agent_id"] == "H002" and row["step"] == 1 for row in simulation.social_agent_history)


def test_affinity_can_make_agent_prefer_known_human_over_nearer_stranger():
    world = World(width=14, height=8, food_count=0, obstacle_count=0, rng=random.Random(35))
    agent = Agent(2, 2, vision_radius=10, sociability=0.9)
    stranger = Agent(3, 2)
    familiar = Agent(8, 2)
    agent.social_neighbors = [(stranger.x, stranger.y), (familiar.x, familiar.y)]
    agent.occupied_positions = {(stranger.x, stranger.y), (familiar.x, familiar.y)}
    agent.social_neighbor_affinities = {(stranger.x, stranger.y): 0.05, (familiar.x, familiar.y): 0.8}

    agent.choose_action([], world)

    assert agent.target is not None
    assert abs(agent.target[0] - familiar.x) + abs(agent.target[1] - familiar.y) == 1


def test_social_behavior_config_allows_slower_affinity_decay():
    from configuration.social_behavior_config import SocialBehaviorConfig

    config = SocialBehaviorConfig(affinity_decay_per_far_step=0.0001)
    config.validate()
    world = World(width=20, height=8, food_count=0, obstacle_count=0, rng=random.Random(36))
    first = Agent(1, 1, sociability=0.9)
    second = Agent(15, 1, sociability=0.9)
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0, social_config=config)
    pair = ("H001", "H002")
    simulation.social_pair_affinity[pair] = 0.5
    first.social_affinities[second.agent_id] = 0.5
    second.social_affinities[first.agent_id] = 0.5

    simulation._update_social_relationships([first, second])

    assert first.social_affinities[second.agent_id] == pytest.approx(0.4999)


def test_agent_remembers_visible_contact_and_can_attempt_reunion_from_memory():
    world = World(width=20, height=8, food_count=0, obstacle_count=0, rng=random.Random(37))
    first = Agent(2, 2, vision_radius=4, sociability=0.9)
    second = Agent(6, 2, vision_radius=4, sociability=0.9)
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0)
    pair = ("H001", "H002")
    simulation.social_pair_affinity[pair] = 0.8
    first.social_affinities[second.agent_id] = 0.8
    second.social_affinities[first.agent_id] = 0.8

    # First step records the contact, then the second individual moves out of view.
    simulation.step()
    assert "H002" in first.social_known_contacts
    second.x, second.y = 14, 2
    first.social_neighbors = []
    first.social_candidate_contacts = [{
        "agent_id": "H002", "x": 8, "y": 2, "affinity": 0.8,
        "last_seen_age": 1, "visible": False,
    }]
    first._clear_target()
    first.occupied_positions = {(second.x, second.y)}
    first.choose_action([], world)

    assert first.last_social_decision["decision"] in {"SOCIAL_REUNION", "SOCIAL_TARGET_UNREACHABLE"}
    assert first.last_social_decision["target_agent_id"] == "H002"


def test_social_decision_history_audits_target_reason_and_actual_movement():
    world = World(width=12, height=8, food_count=0, obstacle_count=0, rng=random.Random(38))
    first = Agent(2, 2, sociability=0.9)
    second = Agent(8, 2, sociability=0.9)
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0)

    simulation.step()

    rows = [row for row in simulation.social_decision_history if row["agent_id"] == "H001"]
    assert len(rows) == 1
    assert "decision" in rows[0]
    assert "reason" in rows[0]
    assert "moved" in rows[0]
    assert "target_agent_id" in rows[0]
    assert rows[0]["step"] == 1


def test_social_behavior_config_rejects_invalid_memory_settings():
    from configuration.social_behavior_config import SocialBehaviorConfig

    with pytest.raises(ValueError):
        SocialBehaviorConfig(memory_ttl_steps=0).validate()
    with pytest.raises(ValueError):
        SocialBehaviorConfig(reunion_affinity_threshold=1.1).validate()


def test_social_relationship_update_handles_pair_without_preinitialized_counter():
    """Regression for KeyError when a pair appears without a counter entry."""
    world = World(width=12, height=8, food_count=0, obstacle_count=0, rng=random.Random(91))
    first = Agent(2, 2, agent_id="H001")
    second = Agent(4, 2, agent_id="H011")
    simulation = Simulation(world, agents=[first, second], seed_spawn_count=0)
    pair = tuple(sorted((first.agent_id, second.agent_id)))
    simulation.social_pair_encounters.pop(pair, None)

    simulation._update_social_relationships([first, second])

    assert simulation.social_history[-1]["cumulative_close_steps_for_pair"] == 1
    assert simulation.social_pair_encounters[pair] == 1
