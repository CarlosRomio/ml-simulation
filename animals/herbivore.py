"""Entidade animal herbívora, separada dos agentes humanos."""
from __future__ import annotations

import random
from random import Random

from agents.navigation.service import NavigationService
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
        # Instrumentação de navegação: tentativa de movimento bloqueada e
        # impedimento detectado durante o planejamento dinâmico são distintos.
        self.last_movement_block_reason = ""
        self.last_navigation_block_reason = ""
        self.navigation = NavigationService()

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

    def choose_action(
        self,
        world: World,
        threat_positions: list[tuple[int, int]],
        *,
        occupied_positions: set[tuple[int, int]] | None = None,
        occupied_agent_positions: set[tuple[int, int]] | None = None,
        occupied_animal_positions: set[tuple[int, int]] | None = None,
    ) -> tuple[int, int]:
        """Escolhe fuga ou recurso considerando a ocupação dinâmica do mundo."""
        self.last_navigation_block_reason = ""
        if not self.alive:
            return (0, 0)

        current = (self.x, self.y)
        blocked = set(occupied_positions or ())
        blocked.discard(current)
        agent_positions = set(occupied_agent_positions or ())
        animal_positions = set(occupied_animal_positions or ())
        agent_positions.discard(current)
        animal_positions.discard(current)

        def classify_block(position: tuple[int, int]) -> str:
            if position in agent_positions:
                return "AGENT"
            if position in animal_positions:
                return "ANIMAL"
            return "OBSTACLE"

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
                destination = (nx, ny)
                if (dx,dy)==(0,0):
                    continue
                if destination in blocked:
                    self.last_navigation_block_reason = self.last_navigation_block_reason or classify_block(destination)
                    continue
                if not world.is_walkable(nx,ny):
                    self.last_navigation_block_reason = self.last_navigation_block_reason or "OBSTACLE"
                    continue
                distance=abs(tx-nx)+abs(ty-ny)
                if distance > old_dist:
                    valid.append((distance,(dx,dy)))
            if valid:
                return max(valid,key=lambda item:item[0])[1]

        # Tenta primeiro o recurso correspondente à necessidade mais urgente.
        # Se todas as fontes dessa categoria estiverem ocupadas/inacessíveis,
        # tenta a outra necessidade antes de recorrer à exploração aleatória.
        resource_groups: list[tuple[str, list[tuple[int, int]]]] = []
        if self.thirst >= 45:
            resource_groups.append(("WATER", world.get_water_positions()))
        if self.hunger >= 35:
            food_positions = [
                (cell.x, cell.y)
                for row in world.grid for cell in row
                if isinstance(cell.resource, Plant) and cell.resource.state == PlantState.MATURE
            ]
            # Não substitui uma prioridade de sede por comida quando não há fome.
            if food_positions:
                resource_groups.append(("FOOD", food_positions))

        for kind, candidates in resource_groups:
            candidates = sorted(
                set(candidates),
                key=lambda p: (abs(p[0]-self.x)+abs(p[1]-self.y), p[1], p[0]),
            )
            for target in candidates:
                if target in blocked:
                    self.last_navigation_block_reason = self.last_navigation_block_reason or classify_block(target)
                    continue
                static_path = self.navigation.find_path(world, current, target)
                if not static_path:
                    self.last_navigation_block_reason = self.last_navigation_block_reason or "OBSTACLE"
                    continue
                blocked_steps = [step for step in static_path[1:] if step in blocked]
                if blocked_steps:
                    self.last_navigation_block_reason = self.last_navigation_block_reason or classify_block(blocked_steps[0])
                    path = self.navigation.find_path(world, current, target, blocked_positions=blocked)
                else:
                    path = static_path
                if not path:
                    self.last_navigation_block_reason = self.last_navigation_block_reason or "OBSTACLE"
                    continue
                self.target = target
                self.path = path
                next_action = self.navigation.next_step(path, current)
                if next_action is not None:
                    return next_action
                # Já está no recurso: permanece para beber/comer no ciclo atual.
                return (0, 0)

        # Não mantém um alvo que foi provado inalcançável no estado dinâmico
        # atual. Isso permite reconsiderar recursos no próximo passo.
        self.target = None
        self.path = []
        options=[(0,-1),(0,1),(-1,0),(1,0)]
        self.rng.shuffle(options)
        for dx,dy in options:
            destination = (self.x + dx, self.y + dy)
            if destination in blocked:
                self.last_navigation_block_reason = self.last_navigation_block_reason or classify_block(destination)
                continue
            if world.is_walkable(*destination):
                return dx,dy
            self.last_navigation_block_reason = self.last_navigation_block_reason or "OBSTACLE"
        return (0,0)

    def eat(self, amount: float = 35.0) -> None:
        self.needs.eat(amount)
        self.needs.restore_energy(amount * 0.25)

    def drink(self, amount: float = 35.0) -> None:
        self.needs.drink(amount)
