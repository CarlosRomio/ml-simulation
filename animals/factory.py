"""Criação de populações animais em células livres."""
import random
from random import Random
from animals.herbivore import Herbivore
from agents.attributes import IndividualAttributes, IndividualGenotype
from agents.species import Species
from environment.world import World


class HerbivoreFactory:
    @staticmethod
    def create(world: World, count: int, *, vision_radius: int = 12, seed: int | None = None,
               occupied_positions: set[tuple[int, int]] | None = None,
               attribute_variation: float = 0.12) -> list[Herbivore]:
        if count < 0:
            raise ValueError("A quantidade de herbívoros não pode ser negativa.")
        occupied_positions = occupied_positions or set()
        available = [(c.x,c.y) for row in world.grid for c in row
                     if c.resource is None and c.obstacle is None
                     and (c.x,c.y) not in occupied_positions]
        available.sort(key=lambda p:(p[1],p[0]))
        if count > len(available):
            raise ValueError("Não há células suficientes para criar os herbívoros.")
        rng=random.Random(seed)
        positions=rng.sample(available,count)
        animals = []
        for i, (x, y) in enumerate(positions):
            attributes_seed = None if seed is None else seed + 7_919 * (i + 1) + 531_771
            genotype = IndividualGenotype.species_founder(
                Species.HERBIVORE, Random(attributes_seed), variation=attribute_variation
            )
            attributes = genotype.express()
            animals.append(Herbivore(
                x, y, vision_radius=vision_radius,
                rng=Random(seed + 7919*(i+1)) if seed is not None else None,
                attributes=attributes,
                genotype=genotype,
            ))
        return animals


class CarnivoreFactory:
    """Cria carnívoros em células livres sem sobreposição com outras entidades."""
    @staticmethod
    def create(world: World, count: int, *, vision_radius: int = 12, seed: int | None = None,
               occupied_positions: set[tuple[int, int]] | None = None,
               attribute_variation: float = 0.12):
        from animals.carnivore import Carnivore
        if count < 0:
            raise ValueError("A quantidade de carnívoros não pode ser negativa.")
        occupied_positions = occupied_positions or set()
        available = [(c.x, c.y) for row in world.grid for c in row
                     if c.resource is None and c.obstacle is None
                     and (c.x,c.y) not in occupied_positions]
        available.sort(key=lambda p: (p[1],p[0]))
        if count > len(available):
            raise ValueError("Não há células suficientes para criar os carnívoros.")
        rng = random.Random(seed)
        positions = rng.sample(available, count)
        animals = []
        for i, (x, y) in enumerate(positions):
            attributes_seed = None if seed is None else seed + 104_729 * (i + 1) + 531_771
            genotype = IndividualGenotype.species_founder(
                Species.CARNIVORE, Random(attributes_seed), variation=attribute_variation
            )
            attributes = genotype.express()
            animals.append(Carnivore(
                x, y, vision_radius=vision_radius,
                rng=Random(seed + 104729*(i+1)) if seed is not None else None,
                attributes=attributes,
                genotype=genotype,
            ))
        return animals
