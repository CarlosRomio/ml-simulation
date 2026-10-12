from agents.agent import Agent
from agents.needs import AgentNeeds
from environment.resources import Water
from environment.world import World
from metrics.tracker import SimulationMetrics
from simulation.simulation import Simulation


def test_hunger_and_thirst_progress_independently():
    needs = AgentNeeds(hunger=10, thirst=20, hunger_per_step=2, thirst_per_step=3)
    needs.advance_step()
    assert needs.hunger == 12
    assert needs.thirst == 23
    assert needs.health == 100


def test_dehydration_records_cause_of_damage():
    needs = AgentNeeds(thirst=89, thirst_per_step=1, dehydration_threshold=90, damage_per_step=5)
    needs.advance_step()
    assert needs.health == 95
    assert needs.last_damage_cause == "DEHYDRATION"


def test_water_is_walkable_persistent_and_not_collectible():
    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    water = Water()
    world.get_cell(1, 1).resource = water
    assert world.is_walkable(1, 1)
    assert world.collect_resource(1, 1) is None
    assert world.get_cell(1, 1).resource is water


def test_agent_drinks_from_water_and_metrics_record_consumption():
    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    world.get_cell(1, 1).resource = Water(drink_amount=30)
    agent = Agent(x=1, y=1, needs=AgentNeeds(thirst=70, thirst_per_step=0))
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    simulation.step()
    assert agent.thirst == 40
    assert world.get_cell(1, 1).resource is not None
    assert simulation.metrics.water_drinks == 1
    assert simulation.metrics.water_units_consumed == 30
    assert simulation.metrics.final_thirst == 40
    assert simulation.metrics.average_thirst >= 0


def test_water_density_is_validated_and_counted_in_config():
    from configuration.simulation_config import SimulationConfig
    config = SimulationConfig(width=20, height=20, water_density=0.1)
    assert config.water_count == 40
    config.validate()
