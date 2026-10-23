import random

import pytest

from agents.attributes import IndividualAttributes, SPECIES_ATTRIBUTE_MEANS
from agents.factory import AgentFactory
from agents.species import Species
from animals.factory import CarnivoreFactory, HerbivoreFactory
from configuration.simulation_config import SimulationConfig
from environment.world import World


def test_species_attribute_profiles_are_distinct_and_normalized():
    human = IndividualAttributes.species_average(Species.HUMAN)
    herbivore = IndividualAttributes.species_average(Species.HERBIVORE)
    carnivore = IndividualAttributes.species_average(Species.CARNIVORE)

    assert human.intelligence > herbivore.intelligence
    assert herbivore.agility > human.agility
    assert carnivore.strength > herbivore.strength
    assert carnivore.olfaction > human.olfaction
    for attributes in (human, herbivore, carnivore):
        assert all(0.0 <= value <= 1.0 for value in attributes.to_dict().values())


def test_randomized_attributes_are_reproducible_and_vary_by_individual():
    first = IndividualAttributes.randomized(Species.CARNIVORE, random.Random(123), 0.12)
    same = IndividualAttributes.randomized(Species.CARNIVORE, random.Random(123), 0.12)
    other = IndividualAttributes.randomized(Species.CARNIVORE, random.Random(124), 0.12)

    assert first == same
    assert first != other
    assert IndividualAttributes.randomized(
        Species.HUMAN, random.Random(1), variation=0.0
    ).to_dict() == SPECIES_ATTRIBUTE_MEANS[Species.HUMAN]


def test_attribute_variation_can_be_configured_and_is_validated():
    assert SimulationConfig(attribute_variation=0.0).attribute_variation == 0.0
    with pytest.raises(ValueError, match="attribute_variation"):
        SimulationConfig(attribute_variation=-0.1).validate()


def test_human_factory_derives_capacity_and_perception_from_attributes():
    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    agents = AgentFactory.create_agents(
        world, count=8, vision_radius=6, seed=77, attribute_variation=0.12
    )

    assert len({agent.attributes for agent in agents}) > 1
    assert all(agent.needs.max_health > 0 for agent in agents)
    assert all(agent.needs.max_energy > 0 for agent in agents)
    assert all(agent.vision_radius >= 0 for agent in agents)
    assert all(agent.run_distance in (1, 2) for agent in agents)
    assert all(agent.needs.max_health == pytest.approx(
        100.0 * agent.attributes.relative_multiplier(Species.HUMAN, "constitution")
    ) for agent in agents)
    assert all(agent.needs.max_energy == pytest.approx(
        100.0 * agent.attributes.relative_multiplier(Species.HUMAN, "endurance")
    ) for agent in agents)


def test_animal_factories_create_individualized_species_attributes():
    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    herbivores = HerbivoreFactory.create(world, 8, seed=90, attribute_variation=0.12)
    occupied = {(animal.x, animal.y) for animal in herbivores}
    carnivores = CarnivoreFactory.create(
        world, 6, seed=91, occupied_positions=occupied, attribute_variation=0.12
    )

    assert len({animal.attributes for animal in herbivores}) > 1
    assert len({animal.attributes for animal in carnivores}) > 1
    assert all(animal.species is Species.HERBIVORE for animal in herbivores)
    assert all(animal.species is Species.CARNIVORE for animal in carnivores)
    assert all(animal.run_distance in (2, 3) for animal in carnivores)
    assert all(animal.needs.max_energy > 0 for animal in [*herbivores, *carnivores])


def test_genotype_is_separate_from_phenotype_and_expresses_current_values():
    from agents.attributes import IndividualGenotype

    genotype = IndividualGenotype.species_founder(
        Species.CARNIVORE, random.Random(404), variation=0.12
    )
    phenotype = genotype.express()

    assert phenotype.to_dict() == genotype.to_dict()
    assert set(phenotype.to_dict()) == set(genotype.to_dict())


def test_inherited_genotype_stays_between_parent_values_without_mutation():
    from agents.attributes import IndividualGenotype

    parent_a = IndividualGenotype(strength=0.2, agility=0.3)
    parent_b = IndividualGenotype(strength=0.8, agility=0.7)
    child = IndividualGenotype.inherit(
        parent_a, parent_b, random.Random(99), mutation_rate=0.0
    )

    assert child.strength == pytest.approx(0.5)
    assert child.agility == pytest.approx(0.5)
    for name, value in child.to_dict().items():
        assert 0.0 <= value <= 1.0


def test_genotype_mutation_is_reproducible_and_bounded():
    from agents.attributes import IndividualGenotype

    parent_a = IndividualGenotype(strength=0.98, agility=0.02)
    parent_b = IndividualGenotype(strength=0.98, agility=0.02)
    first = IndividualGenotype.inherit(
        parent_a, parent_b, random.Random(12), mutation_rate=1.0, mutation_strength=0.5
    )
    second = IndividualGenotype.inherit(
        parent_a, parent_b, random.Random(12), mutation_rate=1.0, mutation_strength=0.5
    )

    assert first == second
    assert all(0.0 <= value <= 1.0 for value in first.to_dict().values())


def test_factory_agents_keep_genotype_and_phenotype_consistent():
    world = World(width=20, height=20, food_count=0, obstacle_count=0, water_count=0)
    humans = AgentFactory.create_agents(world, count=3, vision_radius=5, seed=222)
    for individual in humans:
        assert individual.attributes == individual.genotype.express()

    occupied = {(individual.x, individual.y) for individual in humans}
    herbivores = HerbivoreFactory.create(world, 3, seed=223, occupied_positions=occupied)
    occupied.update((individual.x, individual.y) for individual in herbivores)
    carnivores = CarnivoreFactory.create(world, 3, seed=224, occupied_positions=occupied)
    for individual in [*herbivores, *carnivores]:
        assert individual.attributes == individual.genotype.express()
