"""Tests for the visualizer's one-step manual movement controls."""

import pytest

from agents.agent import Agent
from environment.world import World
from simulation.simulation import Simulation


def test_manual_control_moves_selected_agent_one_tile_per_command():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, water_count=0)
    agent = Agent(3, 3)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)

    assert simulation.set_manual_control(agent)
    assert simulation.queue_manual_action(1, 0)
    simulation.step()
    assert (agent.x, agent.y) == (4, 3)

    # A command is consumed once, even when manual mode remains active.
    simulation.step()
    assert (agent.x, agent.y) == (4, 3)


def test_manual_control_can_be_disabled_and_ai_resumes():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, water_count=0)
    agent = Agent(3, 3)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)

    assert simulation.set_manual_control(agent)
    assert simulation.set_manual_control(agent, False)
    assert simulation.manual_control_agent is None
    assert not simulation.queue_manual_action(0, 1)


def test_manual_control_rejects_non_cardinal_moves():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, water_count=0)
    agent = Agent(3, 3)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    simulation.set_manual_control(agent)

    with pytest.raises(ValueError):
        simulation.queue_manual_action(1, 1)
