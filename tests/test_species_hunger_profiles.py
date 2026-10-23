from random import Random

from agents.attributes import IndividualAttributes
from agents.factory import AgentFactory
from agents.species import Species
from animals.carnivore import Carnivore
from animals.herbivore import Herbivore
from configuration.physiology_config import PhysiologyConfig
from configuration.simulation_config import SimulationConfig
from environment.world import World


def _world():
    return World(width=12, height=12, food_count=0, obstacle_count=0, water_count=0)


def test_default_hunger_rates_are_lower_and_species_specific():
    herbivore = Herbivore(1, 1, rng=Random(1))
    carnivore = Carnivore(2, 2, rng=Random(2))

    assert SimulationConfig().hunger_per_step == 0.18
    assert herbivore.needs.hunger_per_step < 0.3
    assert carnivore.needs.hunger_per_step < herbivore.needs.hunger_per_step
    assert carnivore.needs.hunger_per_step > 0.0


def test_metabolic_efficiency_changes_hunger_rate_for_herbivores_and_carnivores():
    low_efficiency = IndividualAttributes(metabolic_efficiency=0.2)
    high_efficiency = IndividualAttributes(metabolic_efficiency=0.9)

    low_herbivore = Herbivore(1, 1, attributes=low_efficiency)
    high_herbivore = Herbivore(2, 2, attributes=high_efficiency)
    low_carnivore = Carnivore(3, 3, attributes=low_efficiency)
    high_carnivore = Carnivore(4, 4, attributes=high_efficiency)

    assert high_herbivore.needs.hunger_per_step < low_herbivore.needs.hunger_per_step
    assert high_carnivore.needs.hunger_per_step < low_carnivore.needs.hunger_per_step


def test_movement_hunger_costs_are_reduced_without_changing_thirst_costs():
    physiology = PhysiologyConfig()
    assert physiology.hunger_walk_cost == 0.005
    assert physiology.hunger_run_cost == 0.025
    assert physiology.thirst_walk_cost == 0.005
    assert physiology.thirst_run_cost == 0.025


def test_metabolic_efficiency_changes_human_hunger_rate_too():
    world = _world()
    agents = AgentFactory.create_agents(
        world, 2, vision_radius=2, seed=41, attribute_variation=0.2
    )
    for agent in agents:
        expected = SimulationConfig().hunger_per_step / agent.attributes.relative_multiplier(
            Species.HUMAN, "metabolic_efficiency"
        )
        assert abs(agent.needs.hunger_per_step - expected) < 1e-12
