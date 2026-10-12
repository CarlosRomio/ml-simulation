"""Carnívoro independente: caça humanos ou herbívoros e busca água."""
from __future__ import annotations

import random
from random import Random

from agents.navigation.bfs import find_path
from agents.needs import AgentNeeds
from environment.resources import Water
from environment.world import World


class Carnivore:
    def __init__(self, x: int, y: int, *, vision_radius: int = 5,
                 needs: AgentNeeds | None = None, rng: Random | None = None):
        if vision_radius < 0:
            raise ValueError("vision_radius não pode ser negativo")
        self.x, self.y = x, y
        self.vision_radius = vision_radius
        self.needs = needs if needs is not None else AgentNeeds(
            max_health=120.0, health=120.0, max_energy=80.0, energy=80.0,
            hunger=35.0, thirst=20.0, hunger_per_step=0.3, thirst_per_step=0.2,
        )
        self.alive = self.needs.alive
        self.rng = rng if rng is not None else random
        self.target: tuple[int, int] | None = None
        self.path: list[tuple[int, int]] = []
        self.kills = 0

    @property
    def health(self) -> float:
        return self.needs.health

    @property
    def hunger(self) -> float:
        return self.needs.hunger

    @property
    def thirst(self) -> float:
        return self.needs.thirst

    def choose_action(self, world: World, prey_positions: list[tuple[int, int]]) -> tuple[int, int]:
        if not self.alive:
            return (0, 0)
        here = (self.x, self.y)
        if isinstance(world.get_cell(*here).resource, Water) and self.thirst > 0:
            return (0, 0)

        # Predadores priorizam água quando a sede está alta; caso contrário caçam.
        candidates: list[tuple[int, int]] = []
        if self.thirst >= 50:
            candidates = world.get_water_positions()
        if not candidates and self.hunger >= 30:
            candidates = [
                pos for pos in prey_positions
                if abs(pos[0] - self.x) + abs(pos[1] - self.y) <= self.vision_radius
            ]
        if not candidates and self.thirst >= 35:
            candidates = world.get_water_positions()

        if candidates:
            candidates.sort(key=lambda p: (abs(p[0]-self.x)+abs(p[1]-self.y), p[1], p[0]))
            for target in candidates:
                if abs(target[0] - self.x) + abs(target[1] - self.y) <= 1:
                    self.target, self.path = target, []
                    return (0, 0)
                path = find_path(world, here, target)
                if path and len(path) > 1:
                    self.target, self.path = target, path
                    nx, ny = path[1]
                    return nx-self.x, ny-self.y
        self.target, self.path = None, []
        options = [(0,-1),(0,1),(-1,0),(1,0)]
        self.rng.shuffle(options)
        for dx, dy in options:
            if world.is_walkable(self.x+dx, self.y+dy):
                return dx, dy
        return (0,0)

    def eat(self, hunger_reduction: float = 45.0) -> None:
        self.needs.eat(hunger_reduction)
        self.needs.restore_energy(15.0)

    def drink(self, amount: float = 30.0) -> None:
        self.needs.drink(amount)
