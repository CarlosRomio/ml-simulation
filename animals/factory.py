"""Criação de populações animais em células livres."""
import random
from random import Random
from animals.herbivore import Herbivore
from environment.world import World


class HerbivoreFactory:
    @staticmethod
    def create(world: World, count: int, *, vision_radius: int = 4, seed: int | None = None,
               occupied_positions: set[tuple[int, int]] | None = None) -> list[Herbivore]:
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
        return [Herbivore(x,y,vision_radius=vision_radius,
                          rng=Random(seed + 7919*(i+1)) if seed is not None else None)
                for i,(x,y) in enumerate(positions)]


class CarnivoreFactory:
    """Cria carnívoros em células livres sem sobreposição com outras entidades."""
    @staticmethod
    def create(world: World, count: int, *, vision_radius: int = 5, seed: int | None = None,
               occupied_positions: set[tuple[int, int]] | None = None):
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
        return [Carnivore(x,y,vision_radius=vision_radius,
                          rng=Random(seed + 104729*(i+1)) if seed is not None else None)
                for i,(x,y) in enumerate(positions)]
