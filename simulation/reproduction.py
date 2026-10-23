"""Ciclo de vida e reprodução simplificados para experimentos evolutivos.

O tempo é medido em passos simulados. A configuração é deliberadamente abstrata:
permite observar gerações em execuções curtas sem afirmar equivalência biológica real.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.attributes import IndividualGenotype
from agents.species import Species
from agents.cognition.personality import Personality


@dataclass(frozen=True, slots=True)
class LifeHistoryConfig:
    maturity_steps: int
    gestation_steps: int
    cooldown_steps: int
    max_age_steps: int = 6000
    seek_hunger_below: float = 40.0
    seek_thirst_below: float = 40.0
    seek_energy_above: float = 25.0
    mating_energy_cost: float = 4.0


LIFE_HISTORY_CONFIG: dict[Species, LifeHistoryConfig] = {
    # Escalas abstratas de prototipagem, não idades biológicas reais.
    Species.HUMAN: LifeHistoryConfig(maturity_steps=500, gestation_steps=240, cooldown_steps=180),
    Species.HERBIVORE: LifeHistoryConfig(maturity_steps=220, gestation_steps=90, cooldown_steps=100),
    Species.CARNIVORE: LifeHistoryConfig(maturity_steps=280, gestation_steps=130, cooldown_steps=140),
}


@dataclass(slots=True)
class LifeHistoryState:
    individual_id: str = ""
    sex: str = "F"
    age_steps: int = 0
    generation: int = 0
    parent_ids: tuple[str, ...] = ()
    reproductive_cooldown: int = 0
    pregnancy_remaining: int = 0
    pregnancy_partner_id: str = ""
    pregnancy_partner_genotype: IndividualGenotype | None = None
    pregnancy_partner_personality: Personality | None = None
    offspring_count: int = 0

    @property
    def pregnant(self) -> bool:
        return self.pregnancy_remaining > 0


class ReproductionSystem:
    """Coordena elegibilidade, acasalamento, gestação e eventos de nascimento."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.births_by_species: dict[Species, int] = {species: 0 for species in Species}
        self.matings_by_species: dict[Species, int] = {species: 0 for species in Species}
        # Agregados por espécie e passo: permitem explicar ausência de reprodução
        # sem gerar uma linha por indivíduo em cada tick.
        self.diagnostics: list[dict[str, Any]] = []

    @staticmethod
    def config_for(individual: Any) -> LifeHistoryConfig:
        return LIFE_HISTORY_CONFIG[Species(individual.species)]

    def eligible(self, individual: Any) -> bool:
        if not getattr(individual, "alive", False):
            return False
        state: LifeHistoryState = individual.life_history
        config = self.config_for(individual)
        return (
            state.age_steps >= config.maturity_steps
            and state.reproductive_cooldown <= 0
            and state.pregnancy_remaining <= 0
            and individual.hunger < config.seek_hunger_below
            and individual.thirst < config.seek_thirst_below
            and individual.energy > config.seek_energy_above
            and individual.health >= individual.needs.max_health * 0.35
        )

    def seek_action(
        self,
        individual: Any,
        population: list[Any],
        world: Any,
        occupied_positions: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        """Retorna um passo em direção a parceiro elegível, se não houver urgência.

        O destino é uma célula adjacente ao parceiro, nunca a célula ocupada por ele.
        Retorna None quando a busca por parceiro não deve substituir a ação normal.
        """
        if not self.eligible(individual):
            return None
        here = (individual.x, individual.y)
        candidates = [
            other for other in population
            if other is not individual
            and self.eligible(other)
            and other.life_history.sex != individual.life_history.sex
        ]
        candidates.sort(key=lambda other: (
            abs(other.x - individual.x) + abs(other.y - individual.y),
            other.life_history.individual_id,
        ))
        if not candidates:
            return None

        from agents.navigation.service import NavigationService
        navigation = getattr(individual, "navigation", None) or NavigationService()
        for partner in candidates:
            distance = abs(partner.x - individual.x) + abs(partner.y - individual.y)
            if distance <= 1:
                individual.target = (partner.x, partner.y)
                individual.target_intent = "SEEK_MATE" if hasattr(individual, "target_intent") else "SEEK_MATE"
                individual.last_behavior_intent = "SEEK_MATE"
                return (0, 0)
            approach_cells = [
                (partner.x + dx, partner.y + dy)
                for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
            ]
            approach_cells = [
                pos for pos in approach_cells
                if world.is_walkable(*pos)
                and (pos not in occupied_positions or pos == here)
            ]
            approach_cells.sort(key=lambda pos: (
                abs(pos[0] - individual.x) + abs(pos[1] - individual.y), pos[1], pos[0]
            ))
            for goal in approach_cells:
                path = navigation.find_path(world, here, goal, blocked_positions=occupied_positions - {here})
                if path and len(path) > 1:
                    individual.target = goal
                    individual.path = path
                    if hasattr(individual, "target_intent"):
                        individual.target_intent = "SEEK_MATE"
                    individual.last_behavior_intent = "SEEK_MATE"
                    next_action = navigation.next_step(path, here)
                    if next_action is not None:
                        return next_action
        return None

    def process_step(self, simulation: Any) -> None:
        """Avança idade/gestação, realiza acasalamentos e cria descendentes."""
        groups: list[tuple[Species, list[Any], str]] = [
            (Species.HUMAN, simulation.agents, "H"),
            (Species.HERBIVORE, simulation.herbivores, "V"),
            (Species.CARNIVORE, simulation.carnivores, "C"),
        ]
        occupied = {
            (item.x, item.y)
            for _, group, _ in groups for item in group if getattr(item, "alive", False)
        }
        newborns: list[tuple[Species, Any]] = []
        event_start = len(self.events)
        blocked_births: dict[Species, int] = {species: 0 for species, _, _ in groups}

        for species, group, prefix in groups:
            config = LIFE_HISTORY_CONFIG[species]
            living = [item for item in group if getattr(item, "alive", False)]
            for item in living:
                state: LifeHistoryState = item.life_history
                state.age_steps += 1
                state.reproductive_cooldown = max(0, state.reproductive_cooldown - 1)
                if state.age_steps >= config.max_age_steps:
                    item.needs.damage(item.needs.max_health + 1.0, cause="OLD_AGE")
                    item.alive = False
                    self.events.append({"step": simulation.steps + 1, "event": "DEATH_OLD_AGE", "species": species.name, "individual_id": state.individual_id})
                    continue
                if state.pregnancy_remaining > 0:
                    state.pregnancy_remaining -= 1
                    if state.pregnancy_remaining == 0:
                        position = self._birth_position(item, simulation.world, occupied)
                        if position is None:
                            state.pregnancy_remaining = 1
                            blocked_births[species] += 1
                            self.events.append({
                                "step": simulation.steps + 1, "event": "BIRTH_BLOCKED",
                                "species": species.name, "individual_id": state.individual_id,
                                "parent_b": state.pregnancy_partner_id,
                                "reason": "NO_FREE_ADJACENT_CELL",
                            })
                            continue
                        partner_genotype = state.pregnancy_partner_genotype
                        if partner_genotype is None:
                            state.pregnancy_remaining = 1
                            blocked_births[species] += 1
                            self.events.append({
                                "step": simulation.steps + 1, "event": "BIRTH_BLOCKED",
                                "species": species.name, "individual_id": state.individual_id,
                                "parent_b": state.pregnancy_partner_id,
                                "reason": "MISSING_PARTNER_GENOTYPE",
                            })
                            continue
                        child_genotype = IndividualGenotype.inherit(
                            item.genotype, partner_genotype, simulation.rng,
                        )
                        partner_personality = state.pregnancy_partner_personality
                        if partner_personality is None:
                            partner_personality = Personality.randomized(simulation.rng)
                        child_personality = Personality.inherit(
                            item.personality, partner_personality, simulation.rng,
                        )
                        child_id = self._next_id(simulation, species, prefix)
                        child = self._create_child(simulation, species, position, child_genotype, child_id, item, partner_genotype, child_personality)
                        newborns.append((species, child))
                        occupied.add(position)
                        state.offspring_count += 1
                        state.reproductive_cooldown = config.cooldown_steps
                        self.births_by_species[species] += 1
                        self.events.append({
                            "step": simulation.steps + 1, "event": "BIRTH",
                            "species": species.name, "individual_id": child_id,
                            "parent_a": state.individual_id, "parent_b": state.pregnancy_partner_id,
                            "generation": child.life_history.generation, "sex": child.life_history.sex,
                            "x": position[0], "y": position[1],
                            **{f"gene_{name}": value for name, value in child.genotype.to_dict().items()},
                            **{f"personality_{name}": value for name, value in child.personality.to_dict().items()},
                        })
                        state.pregnancy_partner_id = ""
                        state.pregnancy_partner_genotype = None
                        state.pregnancy_partner_personality = None

            available = [item for item in living if item.alive and self.eligible(item)]
            # Cada indivíduo participa de no máximo um acasalamento por passo.
            paired: set[int] = set()
            for first in sorted(available, key=lambda item: item.life_history.individual_id):
                if id(first) in paired or first.life_history.sex != "F":
                    continue
                partners = [other for other in available if id(other) not in paired and other is not first and other.life_history.sex == "M" and abs(other.x-first.x)+abs(other.y-first.y) <= 1]
                if not partners:
                    continue
                second = min(partners, key=lambda item: item.life_history.individual_id)
                first.life_history.pregnancy_remaining = config.gestation_steps
                first.life_history.pregnancy_partner_id = second.life_history.individual_id
                first.life_history.pregnancy_partner_genotype = second.genotype
                first.life_history.pregnancy_partner_personality = second.personality
                first.life_history.reproductive_cooldown = config.cooldown_steps
                second.life_history.reproductive_cooldown = config.cooldown_steps
                first.needs.energy = max(0.0, first.needs.energy - config.mating_energy_cost)
                second.needs.energy = max(0.0, second.needs.energy - config.mating_energy_cost)
                paired.update((id(first), id(second)))
                self.matings_by_species[species] += 1
                self.events.append({
                    "step": simulation.steps + 1, "event": "MATING", "species": species.name,
                    "parent_a": first.life_history.individual_id,
                    "parent_b": second.life_history.individual_id,
                    "parent_a_x": first.x, "parent_a_y": first.y,
                    "parent_b_x": second.x, "parent_b_y": second.y,
                    "distance_manhattan": abs(first.x - second.x) + abs(first.y - second.y),
                    "parent_a_energy_after_cost": round(first.energy, 4),
                    "parent_b_energy_after_cost": round(second.energy, 4),
                    "gestation_steps": config.gestation_steps,
                    "cooldown_steps": config.cooldown_steps,
                })

        for species, child in newborns:
            if species is Species.HUMAN:
                from metrics.tracker import SimulationMetrics
                simulation.agents.append(child)
                key = id(child)
                simulation.metrics_by_agent[key] = SimulationMetrics(
                    initial_energy=child.energy, final_energy=child.energy,
                    initial_health=child.health, final_health=child.health,
                    initial_hunger=child.hunger, final_hunger=child.hunger,
                    initial_thirst=child.thirst, final_thirst=child.thirst,
                    health_sum=child.health, hunger_sum=child.hunger,
                    thirst_sum=child.thirst, need_samples=1,
                    energy_sum=child.energy, energy_samples=1,
                    average_health=child.health, average_hunger=child.hunger,
                    average_thirst=child.thirst, unique_positions_visited=1,
                )
                simulation.energy_history_by_agent[key] = [child.energy]
                simulation.position_history_by_agent[key] = [(child.x, child.y)]
                simulation.food_collection_steps_by_agent[key] = []
                simulation.diagnostic_history_by_agent[key] = []
                simulation._visited_positions_by_agent[key] = {(child.x, child.y)}
                simulation._steps_without_food_by_agent[key] = 0
            elif species is Species.HERBIVORE:
                simulation.herbivores.append(child)
                simulation._herbivore_ids[id(child)] = child.life_history.individual_id
            else:
                simulation.carnivores.append(child)
                simulation._carnivore_ids[id(child)] = child.life_history.individual_id

        # Um registro por espécie/passso resume elegibilidade e principais bloqueios.
        # Os motivos não são mutuamente exclusivos: um indivíduo pode estar, por
        # exemplo, simultaneamente imaturo e com fome elevada.
        current_events = self.events[event_start:]
        step_number = simulation.steps + 1
        for species, group, _prefix in groups:
            config = LIFE_HISTORY_CONFIG[species]
            living = [item for item in group if getattr(item, "alive", False)]
            states = [(item, item.life_history) for item in living]
            eligible = [item for item, _state in states if self.eligible(item)]
            self.diagnostics.append({
                "step": step_number,
                "species": species.name,
                "population_alive": len(living),
                "eligible_for_mating": len(eligible),
                "eligible_females": sum(item.life_history.sex == "F" for item in eligible),
                "eligible_males": sum(item.life_history.sex == "M" for item in eligible),
                "immature_count": sum(state.age_steps < config.maturity_steps for _item, state in states),
                "cooldown_count": sum(state.reproductive_cooldown > 0 for _item, state in states),
                "pregnant_count": sum(state.pregnancy_remaining > 0 for _item, state in states),
                "hunger_blocked_count": sum(item.hunger >= config.seek_hunger_below for item, _state in states),
                "thirst_blocked_count": sum(item.thirst >= config.seek_thirst_below for item, _state in states),
                "energy_blocked_count": sum(item.energy <= config.seek_energy_above for item, _state in states),
                "health_blocked_count": sum(item.health < item.needs.max_health * 0.35 for item, _state in states),
                "seeking_mate_count": sum(getattr(item, "last_behavior_intent", "") == "SEEK_MATE" for item in living),
                "matings_this_step": sum(1 for event in current_events if event.get("step") == step_number and event.get("species") == species.name and event.get("event") == "MATING"),
                "births_this_step": sum(1 for event in current_events if event.get("step") == step_number and event.get("species") == species.name and event.get("event") == "BIRTH"),
                "births_blocked_this_step": blocked_births[species],
                "deaths_old_age_this_step": sum(1 for event in current_events if event.get("step") == step_number and event.get("species") == species.name and event.get("event") == "DEATH_OLD_AGE"),
            })

    @staticmethod
    def _birth_position(parent: Any, world: Any, occupied: set[tuple[int, int]]) -> tuple[int, int] | None:
        candidates = [(parent.x + dx, parent.y + dy) for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))]
        for position in candidates:
            if position in occupied or not world.is_walkable(*position):
                continue
            cell = world.get_cell(*position)
            if cell.resource is not None or cell.structure is not None:
                continue
            return position
        return None

    @staticmethod
    def _next_id(simulation: Any, species: Species, prefix: str) -> str:
        if species is Species.HUMAN:
            number = len(simulation.agents) + 1
            existing = {item.life_history.individual_id for item in simulation.agents}
        elif species is Species.HERBIVORE:
            number = len(simulation.herbivores) + 1
            existing = {item.life_history.individual_id for item in simulation.herbivores}
        else:
            number = len(simulation.carnivores) + 1
            existing = {item.life_history.individual_id for item in simulation.carnivores}
        while f"{prefix}{number:03d}" in existing:
            number += 1
        return f"{prefix}{number:03d}"

    @staticmethod
    def _create_child(simulation: Any, species: Species, position: tuple[int, int], genotype: IndividualGenotype, child_id: str, mother: Any, partner_genotype: IndividualGenotype, personality: Personality | None = None) -> Any:
        from agents.agent import Agent
        from animals.herbivore import Herbivore
        from animals.carnivore import Carnivore
        attributes = genotype.express()
        personality = personality or Personality.randomized(simulation.rng)
        sex = simulation.rng.choice(("F", "M"))
        generation = mother.life_history.generation + 1
        parents = (mother.life_history.individual_id, mother.life_history.pregnancy_partner_id)
        state = LifeHistoryState(individual_id=child_id, sex=sex, age_steps=0, generation=generation, parent_ids=parents)
        if species is Species.HUMAN:
            child = Agent(*position, rng=simulation.rng, species=species, attributes=attributes, genotype=genotype, agent_id=child_id, personality=personality)
        elif species is Species.HERBIVORE:
            child = Herbivore(*position, rng=simulation.rng, attributes=attributes, genotype=genotype, personality=personality)
        else:
            child = Carnivore(*position, rng=simulation.rng, attributes=attributes, genotype=genotype, personality=personality)
        child.life_history = state
        # IDs de herbívoros/carnívoros também são consumidos pela UI e pela auditoria.
        child.agent_id = child_id
        return child
