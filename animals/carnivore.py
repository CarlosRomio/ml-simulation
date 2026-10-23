"""Carnívoro independente: caça humanos ou herbívoros e busca água."""
from __future__ import annotations

import random
from random import Random

from agents.navigation.service import NavigationService
from agents.navigation.exploration import choose_exploration_waypoint
from agents.target_selector import TargetSelector
from agents.needs import AgentNeeds
from agents.attributes import IndividualAttributes, IndividualGenotype
from agents.species import Species
from agents.cognition.personality import Personality
from configuration.species_physiology import DEFAULT_HUNGER_PER_STEP, adjusted_hunger_rate
from environment.resources import Water
from environment.world import World


class Carnivore:
    def __init__(self, x: int, y: int, *, vision_radius: int = 12,
                 needs: AgentNeeds | None = None, rng: Random | None = None,
                 attributes: IndividualAttributes | None = None,
                 genotype: IndividualGenotype | None = None,
                 personality: Personality | None = None):
        if vision_radius < 0:
            raise ValueError("vision_radius não pode ser negativo")
        self.x, self.y = x, y
        self.species = Species.CARNIVORE
        self.genotype = genotype if genotype is not None else (
            IndividualGenotype.from_attributes(attributes) if attributes is not None
            else IndividualGenotype.species_founder(self.species, (rng if rng is not None else random), variation=0.0)
        )
        self.attributes = attributes if attributes is not None else IndividualAttributes.from_genotype(self.genotype)
        self.personality = personality if personality is not None else Personality.randomized(
            (rng if rng is not None else random)
        )
        self.vision_radius = (max(vision_radius - 2, self.attributes.adjusted_radius(self.species, vision_radius))
                              if attributes is not None else vision_radius)
        self.run_distance = 5 if self.attributes.agility >= 0.5 else 4
        constitution = self.attributes.relative_multiplier(self.species, "constitution")
        endurance = self.attributes.relative_multiplier(self.species, "endurance")
        self.needs = needs if needs is not None else AgentNeeds(
            max_health=120.0 * constitution, health=120.0 * constitution,
            max_energy=110.0 * endurance, energy=110.0 * endurance,
            hunger=35.0, thirst=20.0,
            hunger_per_step=adjusted_hunger_rate(DEFAULT_HUNGER_PER_STEP[self.species], self.species, self.attributes),
            thirst_per_step=0.2,
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
        self.visit_counts: dict[tuple[int, int], int] = {}
        # Histórico separado para detectar oscilação durante perseguições.
        self._hunt_position_history: list[tuple[int, int]] = []
        self.hunt_stagnation_steps = 0
        self.hunt_target_switches = 0
        self._last_hunt_target: tuple[int, int] | None = None
        # Identidade da presa atual, mantida pela simulação entre passos.
        self.hunt_target_object_id: int | None = None
        self.preferred_hunt_target: tuple[int, int] | None = None
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
        self.visit_counts[here] = self.visit_counts.get(here, 0) + 1
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
            # Mantém continuidade espacial do alvo quando a presa se desloca entre
            # células próximas. Sem identidade de presa no contrato legado, usamos
            # continuidade de posição como heurística conservadora.
            unique_candidates = sorted(set(candidates), key=lambda p: (p[1], p[0]))
            previous_target = self._last_hunt_target or self.target
            nearby_to_previous = [
                pos for pos in unique_candidates
                if previous_target is not None
                and abs(pos[0] - previous_target[0]) + abs(pos[1] - previous_target[1]) <= 3
            ]
            preferred = self.preferred_hunt_target
            nearest = min(
                unique_candidates,
                key=lambda p: (abs(p[0] - self.x) + abs(p[1] - self.y), p[1], p[0]),
            )
            nearest_distance = abs(nearest[0] - self.x) + abs(nearest[1] - self.y)
            if preferred in unique_candidates:
                preferred_distance = abs(preferred[0] - self.x) + abs(preferred[1] - self.y)
                # Mantém a presa atual salvo se outra estiver materialmente mais
                # próxima (3+ células), evitando troca por pequenas variações.
                target = preferred if preferred_distance <= nearest_distance + 3 else nearest
            elif nearby_to_previous:
                target = min(
                    nearby_to_previous,
                    key=lambda p: (
                        abs(p[0] - previous_target[0]) + abs(p[1] - previous_target[1]),
                        abs(p[0] - self.x) + abs(p[1] - self.y), p[1], p[0],
                    ),
                )
            else:
                target = nearest
            if self._last_hunt_target is not None and target != self._last_hunt_target:
                self.hunt_target_switches += 1
            self._last_hunt_target = target
            self.target = target
            self.exploration_target = None

            here = (self.x, self.y)
            self._hunt_position_history.append(here)
            self._hunt_position_history = self._hunt_position_history[-8:]
            recent_window = self._hunt_position_history[-6:]
            repeated = sum(position == here for position in recent_window) >= 3
            oscillating = (
                len(self._hunt_position_history) >= 3
                and self._hunt_position_history[-1] == self._hunt_position_history[-3]
                and self._hunt_position_history[-1] != self._hunt_position_history[-2]
            )
            if repeated or oscillating:
                self.hunt_stagnation_steps += 1
            else:
                self.hunt_stagnation_steps = max(0, self.hunt_stagnation_steps - 1)

            distance = abs(target[0] - self.x) + abs(target[1] - self.y)
            if distance <= 1:
                self.path = []
                return (0, 0)

            # Planeja até uma célula adjacente, nunca até a célula ocupada pela
            # presa. Quando há oscilação, penaliza rotas que repetem posições
            # recentes e prefere uma aproximação lateral alcançável.
            approach_cells = [
                (target[0] + dx, target[1] + dy)
                for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
                if world.is_walkable(target[0] + dx, target[1] + dy)
            ]
            recent = set(self._hunt_position_history[-6:])
            routes = []
            for approach in approach_cells:
                if approach == target or approach == here:
                    if approach == here:
                        continue
                path = self.navigation.find_path(world, here, approach)
                if not path or len(path) < 2:
                    continue
                lookahead = path[1: min(len(path), max(3, self.run_distance + 1))]
                revisits = sum(position in recent for position in lookahead)
                routes.append((len(path) + (revisits * (8 if self.hunt_stagnation_steps else 2)),
                               revisits, approach[1], approach[0], path))
            if routes:
                routes.sort(key=lambda item: item[:4])
                self.path = routes[0][4]
                next_action = self.navigation.next_step(self.path, here)
                if next_action is not None:
                    return next_action
            self.path = []

        # Sem presa ou água acessível, patrulha um ponto persistente e distante.
        # Isso evita o passeio aleatório de uma célula por vez e reduz retornos
        # imediatos às mesmas posições.
        self.target = None
        # Atualiza a recência: uma revisita torna a posição a mais recente.
        if here in self._recent_positions:
            self._recent_positions.remove(here)

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
            plan = choose_exploration_waypoint(
                world, here,
                lambda route_world, start, goal: self.navigation.find_path(route_world, start, goal),
                self.rng, self.visit_counts, self._recent_positions,
                min_distance=max(8, self.vision_radius),
                max_distance=max(18, min(max(world.width, world.height) // 2, 45)),
                candidate_limit=24,
            )
            if plan is not None:
                selected, selected_path = plan
            else:
                selected, selected_path = None, None
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
