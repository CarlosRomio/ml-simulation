"""Carnívoro independente: caça humanos ou herbívoros e busca água."""
from __future__ import annotations

import random
from random import Random

from agents.navigation.service import NavigationService
from agents.target_selector import TargetSelector
from agents.needs import AgentNeeds
from agents.attributes import IndividualAttributes, IndividualGenotype
from agents.species import Species
from environment.resources import Water
from environment.world import World


class Carnivore:
    def __init__(self, x: int, y: int, *, vision_radius: int = 5,
                 needs: AgentNeeds | None = None, rng: Random | None = None,
                 attributes: IndividualAttributes | None = None,
                 genotype: IndividualGenotype | None = None):
        if vision_radius < 0:
            raise ValueError("vision_radius não pode ser negativo")
        self.x, self.y = x, y
        self.species = Species.CARNIVORE
        self.genotype = genotype if genotype is not None else (
            IndividualGenotype.from_attributes(attributes) if attributes is not None
            else IndividualGenotype.species_founder(self.species, (rng if rng is not None else random), variation=0.0)
        )
        self.attributes = attributes if attributes is not None else IndividualAttributes.from_genotype(self.genotype)
        self.vision_radius = (self.attributes.adjusted_radius(self.species, vision_radius)
                              if attributes is not None else vision_radius)
        self.run_distance = 3 if self.attributes.agility >= 0.5 else 2
        constitution = self.attributes.relative_multiplier(self.species, "constitution")
        endurance = self.attributes.relative_multiplier(self.species, "endurance")
        self.needs = needs if needs is not None else AgentNeeds(
            max_health=120.0 * constitution, health=120.0 * constitution,
            max_energy=80.0 * endurance, energy=80.0 * endurance,
            hunger=35.0, thirst=20.0, hunger_per_step=0.3, thirst_per_step=0.2,
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
        # Exploração persistente: escolhe pontos de patrulha em vez de trocar
        # aleatoriamente de direção a cada passo.
        self.exploration_target: tuple[int, int] | None = None
        self._recent_positions: list[tuple[int, int]] = []
        self.kills = 0
        self.navigation = NavigationService()
        self.target_selector = TargetSelector()

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

    def choose_action(self, world: World, prey_positions: list[tuple[int, int]]) -> tuple[int, int]:
        if not self.alive:
            return (0, 0)
        here = (self.x, self.y)
        if isinstance(world.get_cell(*here).resource, Water) and self.thirst >= 1.0:
            return (0, 0)

        # Predadores priorizam água quando a sede está alta; caso contrário caçam.
        candidates: list[tuple[int, int]] = []
        seeking_water = False
        if self.thirst >= 50:
            candidates = world.get_water_positions()
            seeking_water = bool(candidates)
        if not candidates and self.hunger >= 30:
            candidates = [
                pos for pos in prey_positions
                if abs(pos[0] - self.x) + abs(pos[1] - self.y) <= self.vision_radius
            ]
        if not candidates and self.thirst >= 35:
            candidates = world.get_water_positions()
            seeking_water = bool(candidates)

        if candidates and seeking_water:
            # A política do carnívoro continua priorizando água a partir dos
            # limiares existentes (50 e, como fallback, 35). O contrato apenas
            # seleciona uma fonte alcançável e devolve a rota; não reordena a
            # prioridade entre hidratação e caça. Não capturamos um caminho
            # estático separado, evitando executar BFS duas vezes por fonte.
            selection = self.target_selector.select_reachable_target(
                world,
                here,
                candidates,
                self.navigation,
                capture_static_path=False,
            )
            if selection.succeeded and selection.target is not None and selection.navigation is not None:
                self.target = selection.target
                self.path = selection.navigation.path or []
                self.exploration_target = None
                next_action = self.navigation.next_step(self.path, here)
                if next_action is not None:
                    return next_action
        elif candidates:
            # A perseguição de presas permanece específica do carnívoro: ao
            # ficar adjacente, aguarda o sistema de combate em vez de ocupar
            # a célula da presa.
            candidates.sort(key=lambda p: (abs(p[0]-self.x)+abs(p[1]-self.y), p[1], p[0]))
            for target in candidates:
                distance = abs(target[0] - self.x) + abs(target[1] - self.y)
                if distance == 0 or distance == 1:
                    self.target, self.path = target, []
                    self.exploration_target = None
                    return (0, 0)
                path = self.navigation.find_path(world, here, target)
                if path and len(path) > 1:
                    self.target, self.path = target, path
                    self.exploration_target = None
                    next_action = self.navigation.next_step(path, here)
                    if next_action is not None:
                        return next_action

        # Sem presa ou água acessível, patrulha um ponto persistente e distante.
        # Isso evita o passeio aleatório de uma célula por vez e reduz retornos
        # imediatos às mesmas posições.
        self.target = None
        if here not in self._recent_positions:
            self._recent_positions.append(here)
            self._recent_positions = self._recent_positions[-16:]
        goal = self.exploration_target
        goal_path = None
        if goal is not None and goal != here and self.path and self.path[-1] == goal:
            # Reutiliza a rota enquanto o predador avança por ela; recalcular BFS
            # em cada minuto torna a exploração cara em mundos grandes.
            try:
                current_index = self.path.index(here)
                if current_index < len(self.path) - 1:
                    goal_path = self.path[current_index:]
            except ValueError:
                goal_path = None
        if goal_path is None and goal is not None and goal != here:
            goal_path = self.navigation.find_path(world, here, goal)
        if goal is None or goal == here or not goal_path or len(goal_path) < 2:
            max_distance = max(world.width, world.height)
            min_distance = min(5, max(2, max_distance // 10))
            max_distance = max(min_distance + 1, min(12, max_distance // 2))
            recent = set(self._recent_positions)
            options = [
                (cell.x, cell.y)
                for row in world.grid for cell in row
                if world.is_walkable(cell.x, cell.y)
                and (cell.x, cell.y) != here
                and (cell.x, cell.y) not in recent
                and min_distance <= abs(cell.x-self.x)+abs(cell.y-self.y) <= max_distance
            ]
            self.rng.shuffle(options)
            selected = None
            selected_path = None
            for candidate in options[:24]:
                path = self.navigation.find_path(world, here, candidate)
                if path and len(path) > 2:
                    selected, selected_path = candidate, path
                    break
            if selected is None:
                # Mundos pequenos ou muito obstruídos: usar qualquer destino
                # alcançável que não seja a própria célula.
                for candidate in options[24:48]:
                    path = self.navigation.find_path(world, here, candidate)
                    if path and len(path) > 1:
                        selected, selected_path = candidate, path
                        break
            self.exploration_target = selected
            goal_path = selected_path
        self.path = goal_path or []
        next_action = self.navigation.next_step(self.path, here)
        if next_action is not None:
            return next_action
        self.exploration_target = None
        return (0, 0)

    def eat(self, hunger_reduction: float = 45.0) -> None:
        self.needs.eat(hunger_reduction)
        self.needs.restore_energy(15.0)

    def drink(self, amount: float = 30.0) -> None:
        self.needs.drink(amount)
