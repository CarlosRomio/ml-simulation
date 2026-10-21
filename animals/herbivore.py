"""Entidade animal herbívora, separada dos agentes humanos."""
from __future__ import annotations

import random
from random import Random

from agents.navigation.bfs import find_path
from agents.needs import AgentNeeds
from environment.resources import Plant, PlantState, Water
from environment.world import World


class Herbivore:
    def __init__(self, x: int, y: int, *, vision_radius: int = 4,
                 needs: AgentNeeds | None = None, rng: Random | None = None):
        if vision_radius < 0:
            raise ValueError("vision_radius não pode ser negativo")
        self.x, self.y = x, y
        self.vision_radius = vision_radius
        self.needs = needs if needs is not None else AgentNeeds(
            max_energy=60.0, energy=60.0, hunger=25.0, thirst=20.0,
            hunger_per_step=0.3, thirst_per_step=0.2,
        )
        self.alive = self.needs.alive
        self.is_sleeping = False
        self.last_activity = "WAITING"
        self.running = False
        self.last_sleep_interruption_reason = ""
        self._sleep_interruption_event = ""
        self.rng = rng if rng is not None else random
        self.target: tuple[int, int] | None = None
        self.path: list[tuple[int, int]] = []
        self.fleeing = False

    @property
    def health(self) -> float:
        return self.needs.health

    @property
    def energy(self) -> float:
        return self.needs.energy

    @property
    def fatigue(self) -> float:
        return self.needs.fatigue

    @property
    def hunger(self) -> float:
        return self.needs.hunger

    @property
    def thirst(self) -> float:
        return self.needs.thirst

    def choose_action(self, world: World, threat_positions: list[tuple[int, int]]) -> tuple[int, int]:
        """Foge de humanos e predadores próximos; caso contrário busca recursos."""
        if not self.alive:
            return (0, 0)
        threats = [(x, y) for x, y in threat_positions
                   if abs(x - self.x) + abs(y - self.y) <= 3]
        self.fleeing = bool(threats)
        if threats:
            tx, ty = min(threats, key=lambda p: abs(p[0]-self.x)+abs(p[1]-self.y))
            options = [(0,-1),(0,1),(-1,0),(1,0),(0,0)]
            valid = []
            old_dist = abs(tx-self.x)+abs(ty-self.y)
            for dx,dy in options:
                nx,ny=self.x+dx,self.y+dy
                if (dx,dy)!=(0,0) and world.is_walkable(nx,ny):
                    distance=abs(tx-nx)+abs(ty-ny)
                    if distance > old_dist:
                        valid.append((distance,(dx,dy)))
            if valid:
                return max(valid,key=lambda item:item[0])[1]
        # Necessidades guiam a seleção do recurso mais urgente.
        candidates=[]
        if self.thirst >= 45:
            candidates=world.get_water_positions()
        if not candidates and self.hunger >= 35:
            candidates=[(c.x,c.y) for row in world.grid for c in row
                        if isinstance(c.resource,Plant) and c.resource.state == PlantState.MATURE]
        if candidates:
            candidates.sort(key=lambda p: (abs(p[0]-self.x)+abs(p[1]-self.y),p[1],p[0]))
            for target in candidates:
                path=find_path(world,(self.x,self.y),target)
                if path and len(path)>1:
                    self.target=target; self.path=path
                    nx,ny=path[1]
                    return nx-self.x,ny-self.y
        # Exploração aleatória limitada por células caminháveis.
        options=[(0,-1),(0,1),(-1,0),(1,0)]
        self.rng.shuffle(options)
        for dx,dy in options:
            if world.is_walkable(self.x+dx,self.y+dy):
                return dx,dy
        return (0,0)

    def eat(self, amount: float = 35.0) -> None:
        self.needs.eat(amount)
        self.needs.restore_energy(amount * 0.25)

    def drink(self, amount: float = 35.0) -> None:
        self.needs.drink(amount)
