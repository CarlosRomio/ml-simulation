from math import dist
import random
from random import Random

from agents.agent import Agent
from agents.needs import AgentNeeds
from agents.species import Species
from animals.herbivore import Herbivore
from animals.carnivore import Carnivore
from agents.navigation.bfs import find_path
from agents.perception import Perception
from environment.world import World
from environment.resources import MaterialKind, MaterialResource, Water, Plant, PlantState, Food
from environment.storage import Storage
from environment.shelter import Shelter
from metrics.tracker import SimulationMetrics
from configuration.social_behavior_config import SocialBehaviorConfig
from configuration.physiology_config import DEFAULT_PHYSIOLOGY_CONFIG, PhysiologyConfig


FOOD_ENERGY = 35.0
ENERGY_PER_STEP = 1.0  # custo de estamina por célula percorrida
RUN_STAMINA_COST = 8.0
ATTACK_STAMINA_COST = 8.0
ATTACK_DAMAGE = 30.0
CARNIVORE_ATTACK_DAMAGE = 35.0
SHELTER_PREDATION_DAMAGE_MULTIPLIER = 0.25
MEAT_HUNGER_REDUCTION = 70.0
MEAT_STAMINA_REWARD = 25.0


class Simulation:
    def build_shelter(self, agent: Agent) -> bool:
        """Constrói na posição atual por 5 madeiras e 2 pedras.

        Não consome materiais se a construção não puder ser realizada.
        """
        if agent not in self.agents or not agent.alive:
            return False
        cell = self.world.get_cell(agent.x, agent.y)
        if cell.structure is not None or cell.obstacle is not None or cell.resource is not None:
            return False
        if agent.inventory.quantity_of(MaterialKind.WOOD) < 5:
            return False
        if agent.inventory.quantity_of(MaterialKind.STONE) < 2:
            return False
        agent.inventory.remove(MaterialKind.WOOD, 5)
        agent.inventory.remove(MaterialKind.STONE, 2)
        cell.structure = Shelter(builder_id=id(agent))
        self.shelters_built += 1
        return True

    def spawn_test_carnivore_near(self, agent: Agent) -> Carnivore | None:
        """Cria um predador de teste ao lado do humano selecionado.

        O indivíduo tem saúde ampliada e necessidades lentas para permitir
        validar interações na janela sem alterar os parâmetros da população
        normal nem os experimentos ecológicos.
        """
        if agent not in self.agents or not agent.alive:
            return None
        occupied = (
            {(item.x, item.y) for item in self.agents}
            | {(item.x, item.y) for item in self.herbivores}
            | {(item.x, item.y) for item in self.carnivores}
        )
        candidates = [
            (agent.x, agent.y - 1),
            (agent.x + 1, agent.y),
            (agent.x, agent.y + 1),
            (agent.x - 1, agent.y),
        ]
        for x, y in candidates:
            if (x, y) in occupied or not self.world.is_walkable(x, y):
                continue
            cell = self.world.get_cell(x, y)
            if cell.resource is not None or cell.structure is not None:
                continue
            carnivore = Carnivore(
                x, y,
                needs=AgentNeeds(
                    max_health=300.0, health=300.0,
                    max_energy=80.0, energy=80.0,
                    hunger=60.0, thirst=10.0,
                    hunger_per_step=0.05, thirst_per_step=0.05,
                ),
                rng=Random(self.rng.randrange(0, 2**31)),
            )
            # O predador de teste foca o humano selecionado para tornar a
            # validação reproduzível mesmo quando há herbívoros por perto.
            carnivore.test_target_agent = agent
            self.carnivores.append(carnivore)
            return carnivore
        return None

    def __init__(
        self,
        world: World,
        agent: Agent | None = None,
        step_duration_seconds: float = 1.0,
        seed_spawn_count: int = 1,
        max_plants: int = 100,
        resource_update_interval: int = 1,
        *,
        agents: list[Agent] | None = None,
        herbivores: list[Herbivore] | None = None,
        carnivores: list[Carnivore] | None = None,
        rng: Random | None = None,
        social_config: SocialBehaviorConfig | None = None,
        social_behavior_enabled: bool = True,
        social_memory_enabled: bool = True,
        physiology_config: PhysiologyConfig | None = None,
    ):
        if step_duration_seconds <= 0:
            raise ValueError("A duração do passo deve ser positiva.")
        if seed_spawn_count < 0:
            raise ValueError("A quantidade de sementes não pode ser negativa.")
        if max_plants < 0:
            raise ValueError("O limite de plantas não pode ser negativo.")
        if resource_update_interval <= 0:
            raise ValueError("O intervalo de atualização deve ser positivo.")
        if agents is not None and agent is not None:
            raise ValueError("Informe 'agent' ou 'agents', não ambos.")

        selected_agents = list(agents) if agents is not None else ([agent] if agent else [])
        if not selected_agents:
            raise ValueError("A simulação precisa de pelo menos um agente.")
        if len({(item.x, item.y) for item in selected_agents}) != len(selected_agents):
            raise ValueError("Os agentes não podem iniciar na mesma célula.")
        for item in selected_agents:
            if not world.is_walkable(item.x, item.y):
                raise ValueError(f"Posição inicial inválida para agente: ({item.x}, {item.y}).")

        self.world = world
        self.agents = selected_agents
        # IDs determinísticos dentro da execução, usados pela interface e pelos
        # CSVs. IDs customizados são preservados quando únicos.
        used_agent_ids: set[str] = set()
        next_agent_number = 1
        for item in self.agents:
            if not item.agent_id or item.agent_id in used_agent_ids:
                while f"H{next_agent_number:03d}" in used_agent_ids:
                    next_agent_number += 1
                item.agent_id = f"H{next_agent_number:03d}"
                next_agent_number += 1
            used_agent_ids.add(item.agent_id)
        self.herbivores = list(herbivores or [])
        self.carnivores = list(carnivores or [])
        all_positions = ([(a.x, a.y) for a in self.agents]
                         + [(h.x, h.y) for h in self.herbivores]
                         + [(c.x, c.y) for c in self.carnivores])
        if len(set(all_positions)) != len(all_positions):
            raise ValueError("Agentes e herbívoros não podem iniciar na mesma célula.")
        for animal in self.herbivores:
            if not world.is_walkable(animal.x, animal.y):
                raise ValueError(f"Posição inicial inválida para herbívoro: ({animal.x}, {animal.y}).")
        for animal in self.carnivores:
            if not world.is_walkable(animal.x, animal.y):
                raise ValueError(f"Posição inicial inválida para carnívoro: ({animal.x}, {animal.y}).")
        self.attacks = 0
        self.shelters_built = sum(
            1 for row in world.grid for cell in row
            if isinstance(cell.structure, Shelter)
        )
        self.animals_killed = 0
        self.carnivore_attacks = 0
        # Eventos recentes para inspeção visual durante testes interativos.
        # Cada evento identifica o alvo, o dano efetivo e se havia abrigo.
        self.damage_events: list[dict] = []
        self.human_defense_attacks = 0
        self.carnivores_killed = 0
        self.humans_killed_by_carnivores = 0
        self.herbivores_died_by_starvation = 0
        self.herbivores_died_by_dehydration = 0
        self.carnivores_died_by_starvation = 0
        self.carnivores_died_by_dehydration = 0
        # Compatibilidade temporária com código e testes de agente único.
        self.agent = self.agents[0]
        # Agente explicitamente observado pela interface; não é uma média populacional.
        self.observed_agent = self.agent
        # Controle manual opcional para validação interativa na visualização.
        self.manual_control_agent: Agent | None = None
        self.manual_action: tuple[int, int] = (0, 0)
        self.manual_running = False
        self.steps = 0
        self.step_duration_seconds = step_duration_seconds  # parâmetro legado; não altera o relógio simulado
        self.physiology_config = physiology_config or DEFAULT_PHYSIOLOGY_CONFIG
        self.physiology_config.validate()
        for individual in self.agents + self.herbivores + self.carnivores:
            individual.physiology_config = self.physiology_config
        self.seed_spawn_count = seed_spawn_count
        self.max_plants = max_plants
        self.resource_update_interval = resource_update_interval
        self.rng = rng if rng is not None else world.rng
        self.perception = Perception()
        self.social_config = social_config or SocialBehaviorConfig()
        self.social_config.validate()
        self.social_behavior_enabled = social_behavior_enabled
        self.social_memory_enabled = social_memory_enabled

        self.metrics_by_agent: dict[int, SimulationMetrics] = {}
        self.energy_history_by_agent: dict[int, list[float]] = {}
        self.position_history_by_agent: dict[int, list[tuple[int, int]]] = {}
        self.food_collection_steps_by_agent: dict[int, list[int]] = {}
        self.diagnostic_history_by_agent: dict[int, list[dict]] = {}
        self._visited_positions_by_agent: dict[int, set[tuple[int, int]]] = {}
        self._steps_without_food_by_agent: dict[int, int] = {}
        self.blocked_movement_attempts = 0
        self.blocked_by_agent_attempts = 0
        self.blocked_by_environment_attempts = 0
        self.population_history: list[dict[str, int | float]] = []
        # Auditoria social em resolução por passo e por par de indivíduos.
        self.social_history: list[dict[str, object]] = []
        # Auditoria fisiológica unificada: humanos e animais, uma linha por indivíduo/passo.
        self.physiology_activity_history: list[dict[str, object]] = []
        self.social_agent_history: list[dict[str, object]] = []
        self.social_decision_history: list[dict[str, object]] = []
        self.social_pair_affinity: dict[tuple[str, str], float] = {}
        self.social_pair_encounters: dict[tuple[str, str], int] = {}
        self.social_encounters_total = 0
        self.social_close_pair_samples = 0
        for i, first in enumerate(self.agents):
            for second in self.agents[i + 1:]:
                pair = tuple(sorted((first.agent_id, second.agent_id)))
                self.social_pair_affinity[pair] = 0.0
                self.social_pair_encounters[pair] = 0
                first.social_affinities[second.agent_id] = 0.0
                second.social_affinities[first.agent_id] = 0.0
        self._record_social_agent_snapshot(step=0)

        for index, item in enumerate(self.agents):
            key = id(item)
            initial_position = (item.x, item.y)
            self.metrics_by_agent[key] = SimulationMetrics(
                initial_energy=item.energy,
                final_energy=item.energy,
                initial_health=item.health,
                final_health=item.health,
                initial_hunger=item.hunger,
                final_hunger=item.hunger,
                initial_thirst=item.thirst,
                final_thirst=item.thirst,
                health_sum=item.health,
                hunger_sum=item.hunger,
                thirst_sum=item.thirst,
                need_samples=1,
                energy_sum=item.energy,
                energy_samples=1,
                average_health=item.health,
                average_hunger=item.hunger,
                average_thirst=item.thirst,
                unique_positions_visited=1,
            )
            self.energy_history_by_agent[key] = [item.energy]
            self.position_history_by_agent[key] = [initial_position]
            self.food_collection_steps_by_agent[key] = []
            self.diagnostic_history_by_agent[key] = []
            self._visited_positions_by_agent[key] = {initial_position}
            self._steps_without_food_by_agent[key] = 0

        self.metrics = self.metrics_by_agent[id(self.agent)]
        self.energy_history = self.energy_history_by_agent[id(self.agent)]
        self.position_history = self.position_history_by_agent[id(self.agent)]
        self.food_collection_steps = self.food_collection_steps_by_agent[id(self.agent)]
        self.diagnostic_history = self.diagnostic_history_by_agent[id(self.agent)]

        self.resource_history: list[dict[str, int]] = []
        self.seeds_spawned_history: list[int] = []
        # Série ecológica combinando estoque observado e eventos ocorridos em cada passo.
        self.ecology_history: list[dict[str, int | float]] = []
        self._current_resource_events = self._empty_resource_events()
        self._record_resource_metrics(seeds_spawned=0)
        self._record_population_metrics()

    def set_manual_control(self, agent: Agent, enabled: bool = True) -> bool:
        """Ativa/desativa o controle manual de um humano da simulação."""
        if agent not in self.agents or not agent.alive:
            return False
        if enabled:
            self.manual_control_agent = agent
            self.manual_action = (0, 0)
            self.manual_running = False
            if agent.is_sleeping:
                agent.is_sleeping = False
                agent.last_sleep_interruption_reason = "MANUAL_CONTROL"
            agent.target = None
            agent.path.clear()
            agent.building_intent = False
        elif self.manual_control_agent is agent:
            self.manual_control_agent = None
            self.manual_action = (0, 0)
            self.manual_running = False
        return True

    def queue_manual_action(self, dx: int, dy: int, *, run: bool = False) -> bool:
        """Agenda um movimento cardinal para o próximo passo da simulação."""
        if self.manual_control_agent is None or not self.manual_control_agent.alive:
            return False
        if (dx, dy) not in {(0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)}:
            raise ValueError("O movimento manual deve ser uma direção cardinal.")
        self.manual_action = (dx, dy)
        self.manual_running = bool(run and (dx, dy) != (0, 0))
        return True

    @property
    def simulated_minutes(self) -> int:
        """Tempo decorrido no mundo; independe da velocidade real de execução."""
        return self.steps * self.physiology_config.minutes_per_step

    @property
    def simulated_time_label(self) -> str:
        total_minutes = self.simulated_minutes
        day_number = total_minutes // 1440 + 1
        hour = (total_minutes % 1440) // 60
        minute = total_minutes % 60
        return f"Dia {day_number}, {hour:02d}:{minute:02d}"

    @property
    def alive_agents(self) -> list[Agent]:
        return [agent for agent in self.agents if agent.alive]

    @property
    def alive_herbivores(self) -> list[Herbivore]:
        return [animal for animal in self.herbivores if animal.alive]

    @property
    def alive_carnivores(self) -> list[Carnivore]:
        return [animal for animal in self.carnivores if animal.alive]

    @property
    def population_survival_rate(self) -> float:
        return len(self.alive_agents) / len(self.agents)

    @staticmethod
    def _empty_resource_events() -> dict[str, int | float]:
        return {
            "plants_seed_to_growing": 0,
            "plants_growing_to_mature": 0,
            "plants_collected_by_humans": 0,
            "plants_collected_by_herbivores": 0,
            "food_items_collected_by_humans": 0,
            "food_units_collected_by_humans": 0.0,
            "food_units_consumed_by_humans": 0.0,
            "food_units_deposited_by_humans": 0.0,
            "food_units_withdrawn_by_humans": 0.0,
            "wood_units_deposited_by_humans": 0.0,
            "stone_units_deposited_by_humans": 0.0,
            "fiber_units_deposited_by_humans": 0.0,
            "wood_units_withdrawn_by_humans": 0.0,
            "stone_units_withdrawn_by_humans": 0.0,
            "fiber_units_withdrawn_by_humans": 0.0,
            "wood_units_collected_by_humans": 0.0,
            "stone_units_collected_by_humans": 0.0,
            "fiber_units_collected_by_humans": 0.0,
            "water_drinks_humans": 0,
            "water_drinks_herbivores": 0,
            "water_drinks_carnivores": 0,
            "water_thirst_reduction_humans": 0.0,
            "water_thirst_reduction_herbivores": 0.0,
            "water_thirst_reduction_carnivores": 0.0,
            "seeds_spawn_requested": 0,
            "seeds_spawned": 0,
            "seeds_blocked_by_plant_cap": 0,
            "seeds_blocked_by_space": 0,
        }

    def _record_resource_metrics(self, seeds_spawned: int) -> None:
        snapshot = {"step": self.steps, **self.world.get_plant_counts()}
        self.resource_history.append(snapshot)
        self.seeds_spawned_history.append(seeds_spawned)
        ecology_row = {
            **snapshot,
            **self.world.get_material_counts(),
            **self.world.get_storage_counts(),
            "water_sources": len(self.world.get_water_positions()),
            **self._current_resource_events,
        }
        self.ecology_history.append(ecology_row)

    def _interact_with_storage(self, agent: Agent) -> dict[str, float]:
        """Realiza transferências automáticas quando o agente está no depósito.

        Materiais são depositados. O alimento excedente é compartilhado,
        preservando uma porção portátil; quando a fome exige alimento e o
        inventário está vazio, uma porção é retirada do estoque comum.
        """
        cell = self.world.get_cell(agent.x, agent.y)
        storage = cell.structure
        transferred = {"food_deposited": 0.0, "food_withdrawn": 0.0,
                       "wood_deposited": 0.0, "stone_deposited": 0.0,
                       "fiber_deposited": 0.0, "wood_withdrawn": 0.0,
                       "stone_withdrawn": 0.0, "fiber_withdrawn": 0.0}
        if not isinstance(storage, Storage):
            return transferred

        for kind in MaterialKind:
            carried = agent.inventory.quantity_of(kind)
            if carried <= 0:
                continue
            accepted = storage.deposit(kind, carried)
            removed = agent.inventory.remove(kind, accepted)
            key = f"{kind.value}_deposited"
            transferred[key] += removed
            self._current_resource_events[f"{kind.value}_units_deposited_by_humans"] += removed

        if agent.hunger >= 35.0 and agent.inventory.food_quantity < 1.0:
            requested = min(1.0, storage.food_quantity, agent.inventory.available_weight)
            accepted = agent.inventory.add_food(requested)
            removed = storage.withdraw_food(accepted)
            transferred["food_withdrawn"] += removed
            self._current_resource_events["food_units_withdrawn_by_humans"] += removed
        elif agent.hunger < 35.0 and agent.inventory.food_quantity > 1.0:
            surplus = agent.inventory.food_quantity - 1.0
            accepted = storage.deposit_food(surplus)
            removed = agent.inventory.remove_food(accepted)
            transferred["food_deposited"] += removed
            self._current_resource_events["food_units_deposited_by_humans"] += removed
        return transferred

    def _record_collection_event(self, resource, collector: str) -> None:
        if isinstance(resource, Plant):
            key = (
                "plants_collected_by_humans"
                if collector == "human"
                else "plants_collected_by_herbivores"
            )
            self._current_resource_events[key] += 1
            if collector == "human":
                self._current_resource_events["food_units_collected_by_humans"] += 1.0
        elif isinstance(resource, Food) and collector == "human":
            self._current_resource_events["food_items_collected_by_humans"] += 1
            self._current_resource_events["food_units_collected_by_humans"] += resource.quantity
        elif isinstance(resource, MaterialResource) and collector == "human":
            key = f"{resource.kind.value}_units_collected_by_humans"
            self._current_resource_events[key] += resource.quantity

    def _record_water_event(self, species: str, thirst_before: float, thirst_after: float) -> None:
        drinks_key = f"water_drinks_{species}"
        units_key = f"water_thirst_reduction_{species}"
        self._current_resource_events[drinks_key] += 1
        self._current_resource_events[units_key] += max(0.0, thirst_before - thirst_after)

    @staticmethod
    def _mean_need(individuals, attribute: str) -> float:
        """Média do estado dos indivíduos vivos; zero quando não há vivos."""
        if not individuals:
            return 0.0
        return sum(float(getattr(item, attribute)) for item in individuals) / len(individuals)

    def _update_social_relationships(self, alive_agents: list[Agent]) -> None:
        """Atualiza familiaridade entre pares e grava uma linha auditável por par/passo.

        Permanecer próximo aumenta a afinidade lentamente; afastamento grande a
        reduz de forma gradual. Não há amizade instantânea nem cooperação implícita.
        """
        for index, first in enumerate(alive_agents):
            for second in alive_agents[index + 1:]:
                pair = tuple(sorted((first.agent_id, second.agent_id)))
                distance = abs(first.x - second.x) + abs(first.y - second.y)
                before = self.social_pair_affinity.get(pair, 0.0)
                close = distance <= 3
                if close:
                    sociability_factor = 0.5 + (first.sociability + second.sociability) / 2.0
                    after = min(1.0, before + self.social_config.affinity_gain_per_close_step * sociability_factor)
                    self.social_pair_encounters[pair] = self.social_pair_encounters.get(pair, 0) + 1
                    self.social_encounters_total += 1
                    self.social_close_pair_samples += 1
                    event = "CLOSE_ENCOUNTER"
                elif distance > 6:
                    after = max(0.0, before - self.social_config.affinity_decay_per_far_step)
                    event = "AFFINITY_DECAY" if after < before else "NO_CHANGE"
                else:
                    after = before
                    event = "NO_CHANGE"
                self.social_pair_affinity[pair] = after
                first.social_affinities[second.agent_id] = after
                second.social_affinities[first.agent_id] = after
                self.social_history.append({
                    "step": self.steps + 1,
                    "agent_a_id": pair[0],
                    "agent_b_id": pair[1],
                    "agent_a_x": first.x if first.agent_id == pair[0] else second.x,
                    "agent_a_y": first.y if first.agent_id == pair[0] else second.y,
                    "agent_b_x": second.x if second.agent_id == pair[1] else first.x,
                    "agent_b_y": second.y if second.agent_id == pair[1] else first.y,
                    "manhattan_distance": distance,
                    "within_social_range": close,
                    "affinity_before": round(before, 6),
                    "affinity_after": round(after, 6),
                    "affinity_delta": round(after - before, 6),
                    "cumulative_close_steps_for_pair": self.social_pair_encounters[pair],
                    "event": event,
                })

    def _record_social_decision(
        self, agent: Agent, step: int, position_before: tuple[int, int],
        action: tuple[int, int], moved: bool,
    ) -> None:
        # Só registramos bloqueio social quando a política do agente o marcou
        # explicitamente após avaliar contatos. Necessidades altas, isoladamente,
        # não provam que havia uma decisão social elegível a ser bloqueada.
        decision = dict(agent.last_social_decision)
        self.social_decision_history.append({
            "step": step,
            "agent_id": agent.agent_id,
            "decision": decision.get("decision", "OTHER_BEHAVIOR_PRIORITY"),
            "reason": decision.get("reason", "SOCIAL_DRIVE_NOT_REACHED"),
            "target_agent_id": decision.get("target_agent_id", ""),
            "target_affinity": decision.get("target_affinity", 0.0),
            "target_last_seen_age": decision.get("target_last_seen_age", -1),
            "target_x": decision.get("target_x", ""),
            "target_y": decision.get("target_y", ""),
            "x_before": position_before[0], "y_before": position_before[1],
            "x_after": agent.x, "y_after": agent.y,
            "action_dx": action[0], "action_dy": action[1],
            "moved": bool(moved),
            "sociability": round(agent.sociability, 6),
            "hunger": round(agent.hunger, 4),
            "thirst": round(agent.thirst, 4),
            "energy": round(agent.energy, 4),
        })

    def _record_social_agent_snapshot(self, step: int) -> None:
        alive = self.alive_agents
        for agent in self.agents:
            contacts = [
                other for other in alive if other is not agent
                and abs(other.x - agent.x) + abs(other.y - agent.y) <= 3
            ] if agent.alive else []
            known_affinities = [value for value in agent.social_affinities.values()]
            ranked = sorted(agent.social_affinities.items(), key=lambda item: (-item[1], item[0]))
            best_id, best_affinity = ranked[0] if ranked else ("", 0.0)
            self.social_agent_history.append({
                "step": step,
                "agent_id": agent.agent_id,
                "alive": agent.alive,
                "x": agent.x,
                "y": agent.y,
                "sociability": round(agent.sociability, 6),
                "personality_curiosity": round(agent.personality.curiosity, 6),
                "personality_risk_aversion": round(agent.personality.risk_aversion, 6),
                "personality_aggressiveness": round(agent.personality.aggressiveness, 6),
                "personality_persistence": round(agent.personality.persistence, 6),
                "personality_reward_sensitivity": round(agent.personality.reward_sensitivity, 6),
                "close_humans_count": len(contacts),
                "known_relationships_count": sum(value >= 0.2 for value in known_affinities),
                "mean_affinity": round(sum(known_affinities) / len(known_affinities), 6) if known_affinities else 0.0,
                "max_affinity": round(max(known_affinities, default=0.0), 6),
                "strongest_contact_id": best_id,
                "strongest_contact_affinity": round(best_affinity, 6),
            })

    def _record_population_metrics(self) -> None:
        all_pair_affinities = list(self.social_pair_affinity.values())
        close_pairs = sum(
            1 for i, first in enumerate(self.alive_agents)
            for second in self.alive_agents[i + 1:]
            if abs(first.x - second.x) + abs(first.y - second.y) <= 3
        )
        self.population_history.append({
            "step": self.steps,
            "alive": len(self.alive_agents),
            "dead": len(self.agents) - len(self.alive_agents),
            "food_collected": sum(m.food_collected for m in self.metrics_by_agent.values()),
            "herbivores_alive": len(self.alive_herbivores),
            "carnivores_alive": len(self.alive_carnivores),
            "human_mean_health": self._mean_need(self.alive_agents, "health"),
            "human_mean_hunger": self._mean_need(self.alive_agents, "hunger"),
            "human_mean_thirst": self._mean_need(self.alive_agents, "thirst"),
            "human_mean_energy": self._mean_need(self.alive_agents, "energy"),
            "human_mean_fatigue": self._mean_need(self.alive_agents, "fatigue"),
            "human_sleeping": sum(agent.is_sleeping for agent in self.alive_agents),
            "human_running": sum(agent.last_activity == "RUNNING" for agent in self.alive_agents),
            "human_all_mean_health": self._mean_need(self.agents, "health"),
            "human_all_mean_hunger": self._mean_need(self.agents, "hunger"),
            "human_all_mean_thirst": self._mean_need(self.agents, "thirst"),
            "human_all_mean_energy": self._mean_need(self.agents, "energy"),
            "herbivore_mean_health": self._mean_need(self.alive_herbivores, "health"),
            "herbivore_mean_hunger": self._mean_need(self.alive_herbivores, "hunger"),
            "herbivore_mean_thirst": self._mean_need(self.alive_herbivores, "thirst"),
            "herbivore_mean_energy": self._mean_need(self.alive_herbivores, "energy"),
            "herbivore_mean_fatigue": self._mean_need(self.alive_herbivores, "fatigue"),
            "herbivore_sleeping": sum(animal.is_sleeping for animal in self.alive_herbivores),
            "herbivore_running": sum(animal.last_activity == "RUNNING" for animal in self.alive_herbivores),
            "herbivore_all_mean_health": self._mean_need(self.herbivores, "health"),
            "herbivore_all_mean_hunger": self._mean_need(self.herbivores, "hunger"),
            "herbivore_all_mean_thirst": self._mean_need(self.herbivores, "thirst"),
            "carnivore_mean_health": self._mean_need(self.alive_carnivores, "health"),
            "carnivore_mean_hunger": self._mean_need(self.alive_carnivores, "hunger"),
            "carnivore_mean_thirst": self._mean_need(self.alive_carnivores, "thirst"),
            "carnivore_mean_energy": self._mean_need(self.alive_carnivores, "energy"),
            "carnivore_mean_fatigue": self._mean_need(self.alive_carnivores, "fatigue"),
            "carnivore_sleeping": sum(animal.is_sleeping for animal in self.alive_carnivores),
            "carnivore_running": sum(animal.last_activity == "RUNNING" for animal in self.alive_carnivores),
            "carnivore_all_mean_health": self._mean_need(self.carnivores, "health"),
            "carnivore_all_mean_hunger": self._mean_need(self.carnivores, "hunger"),
            "carnivore_all_mean_thirst": self._mean_need(self.carnivores, "thirst"),
            "social_close_pairs": close_pairs,
            "social_pair_count": len(all_pair_affinities),
            "social_mean_pair_affinity": round(sum(all_pair_affinities) / len(all_pair_affinities), 6) if all_pair_affinities else 0.0,
            "social_relationships_over_0_2": sum(value >= 0.2 for value in all_pair_affinities),
            "social_encounters_cumulative": self.social_encounters_total,
        })

    def _advance_environment(self) -> None:
        self.steps += 1
        seeds_spawned = 0
        if self.steps % self.resource_update_interval == 0:
            transitions = self.world.advance_resources()
            self._current_resource_events["plants_seed_to_growing"] += transitions["seed_to_growing"]
            self._current_resource_events["plants_growing_to_mature"] += transitions["growing_to_mature"]
            occupied = (
                {(a.x, a.y) for a in self.alive_agents}
                | {(h.x, h.y) for h in self.alive_herbivores}
                | {(c.x, c.y) for c in self.alive_carnivores}
            )
            spawn_report = self.world.spawn_seeds_with_report(
                count=self.seed_spawn_count,
                max_plants=self.max_plants,
                occupied_cells=occupied,
            )
            seeds_spawned = spawn_report["spawned"]
            self._current_resource_events["seeds_spawn_requested"] += spawn_report["requested"]
            self._current_resource_events["seeds_spawned"] += spawn_report["spawned"]
            self._current_resource_events["seeds_blocked_by_plant_cap"] += spawn_report["blocked_by_plant_cap"]
            self._current_resource_events["seeds_blocked_by_space"] += spawn_report["blocked_by_space"]
        self._record_resource_metrics(seeds_spawned)
        self._record_population_metrics()
        for metrics in self.metrics_by_agent.values():
            metrics.steps = self.steps
            metrics.simulated_time_seconds = self.simulated_minutes * 60.0

    def _resolve_movements(self, actions: dict[int, tuple[int, int]]) -> dict[int, bool]:
        """Resolve one intended move per agent without shared destination cells.

        Priority is shuffled once per step. Agents cannot enter a cell occupied
        by an agent that has not moved away yet; this also prevents swaps.
        """
        order = list(self.alive_agents)
        self.rng.shuffle(order)
        occupied = {(a.x, a.y): a for a in self.alive_agents}
        animal_positions = ({(h.x, h.y) for h in self.alive_herbivores}
                            | {(c.x, c.y) for c in self.alive_carnivores})
        moved_by_id: dict[int, bool] = {id(a): False for a in order}

        for agent in order:
            action = actions[id(agent)]
            if action == (0, 0):
                continue
            metrics = self.metrics_by_agent[id(agent)]
            metrics.movement_attempts += 1
            dx, dy = action
            destination = (agent.x + dx, agent.y + dy)
            current = (agent.x, agent.y)
            occupied.pop(current, None)

            if destination in occupied or destination in animal_positions:
                occupied[current] = agent
                metrics.blocked_movement_attempts += 1
                metrics.blocked_by_agent_attempts += 1
                self.blocked_movement_attempts += 1
                self.blocked_by_agent_attempts += 1
                agent.target = None
                agent.path.clear()
                continue

            if not self.world.is_walkable(*destination):
                occupied[current] = agent
                metrics.blocked_movement_attempts += 1
                metrics.blocked_by_environment_attempts += 1
                self.blocked_movement_attempts += 1
                self.blocked_by_environment_attempts += 1
                agent.target = None
                agent.path.clear()
                continue

            moved = False
            distance = 2 if agent.running and agent.energy >= self.physiology_config.stamina_run_cost else 1
            for _ in range(distance):
                next_position = (agent.x + dx, agent.y + dy)
                if next_position in occupied or next_position in animal_positions or not self.world.is_walkable(*next_position):
                    break
                if not self.world.move_agent(agent, action):
                    break
                moved = True
            if moved:
                occupied.pop(current, None)
                occupied[(agent.x, agent.y)] = agent
                moved_by_id[id(agent)] = True
            else:
                occupied[current] = agent
                metrics.blocked_movement_attempts += 1
                metrics.blocked_by_environment_attempts += 1
                self.blocked_movement_attempts += 1
                self.blocked_by_environment_attempts += 1
                agent.target = None
                agent.path.clear()

        return moved_by_id

    def _sleep_wake_reason(self, individual) -> str:
        """Retorna o motivo de interromper o sono por necessidade ou ameaça."""
        config = self.physiology_config
        if individual.hunger >= config.sleep_wake_hunger_threshold:
            return "HUNGER"
        if individual.hunger >= 35.0 and getattr(individual, "inventory", None) is not None and individual.inventory.food_quantity < 1.0:
            return "HUNGER"
        if individual.hunger >= 35.0 and not hasattr(individual, "inventory"):
            return "HUNGER"
        if individual.thirst >= min(40.0, config.sleep_wake_thirst_threshold):
            return "THIRST"
        radius = config.sleep_wake_predator_radius
        for predator in self.alive_carnivores:
            if predator is individual:
                continue
            if abs(predator.x - individual.x) + abs(predator.y - individual.y) <= radius:
                return "PREDATOR_NEARBY"
        return ""

    def _has_nearby_shelter(self, position: tuple[int, int], radius: int = 8) -> bool:
        x, y = position
        return any(
            isinstance(cell.structure, Shelter)
            and abs(cell.x - x) + abs(cell.y - y) <= radius
            for row in self.world.grid for cell in row
        )

    def _try_autonomous_shelter_build(self, agent: Agent) -> bool:
        """Constrói quando a política do agente definiu intenção de construção."""
        if (
            agent is self.manual_control_agent
            or not agent.alive
            or not getattr(agent, "building_intent", False)
            or agent.inventory.quantity_of(MaterialKind.WOOD) < 5
            or agent.inventory.quantity_of(MaterialKind.STONE) < 2
        ):
            return False
        cell = self.world.get_cell(agent.x, agent.y)
        if (
            cell.structure is not None or cell.obstacle is not None
            or cell.resource is not None
            or self._has_nearby_shelter((agent.x, agent.y), radius=8)
        ):
            agent.building_intent = False
            return False
        agent.inventory.remove(MaterialKind.WOOD, 5)
        agent.inventory.remove(MaterialKind.STONE, 2)
        cell.structure = Shelter(builder_id=id(agent))
        self.shelters_built += 1
        agent.building_intent = False
        agent.target = None
        agent.path.clear()
        return True

    def step(self) -> None:
        self._current_resource_events = self._empty_resource_events()
        alive_at_start = self.alive_agents
        if not alive_at_start and not self.alive_herbivores and not self.alive_carnivores:
            self._advance_environment()
            return

        before = {id(a): (a.x, a.y) for a in alive_at_start}
        energy_before = {id(a): a.energy for a in alive_at_start}
        physiology_before = {
            id(a): {"health": a.health, "hunger": a.hunger, "thirst": a.thirst, "energy": a.energy, "fatigue": a.needs.fatigue}
            for a in alive_at_start
        }
        damage_before = {id(a): dict(a.needs.damage_by_cause) for a in alive_at_start}
        actions: dict[int, tuple[int, int]] = {}
        self._update_social_relationships(alive_at_start)

        # All agents choose actions from the same pre-movement world state.
        # O humano sob controle manual ignora a decisão autônoma neste passo,
        # mas continua sujeito a colisões, necessidades e interações normais.
        for agent in alive_at_start:
            agent._sleep_blocked_this_step = False
            agent._sleep_interruption_event = ""
            if agent.is_sleeping:
                wake_reason = self._sleep_wake_reason(agent)
                if wake_reason:
                    agent.is_sleeping = False
                    agent.last_sleep_interruption_reason = wake_reason
                    agent._sleep_interruption_event = wake_reason
                    agent._sleep_blocked_this_step = True
                else:
                    agent._rest_selected = False
                    agent._sleep_selected = True
                    agent._waiting_selected = False
                    agent.running = False
                    agent.last_behavior_intent = "SLEEP"
                    actions[id(agent)] = (0, 0)
                    continue
            if agent is self.manual_control_agent:
                agent._rest_selected = False
                agent._sleep_selected = False
                agent._waiting_selected = self.manual_action == (0, 0)
                agent.running = bool(self.manual_running and agent.energy >= self.physiology_config.stamina_run_minimum)
                agent.last_social_decision = {
                    "decision": "MANUAL_CONTROL", "reason": "AUTONOMOUS_DECISION_BYPASSED",
                    "target_agent_id": "", "target_affinity": 0.0,
                    "target_last_seen_age": -1, "target_x": "", "target_y": "",
                }
                actions[id(agent)] = self.manual_action
                continue
            nearby = self.perception.observe(
                self.world, agent.x, agent.y, radius=agent.vision_radius
            )
            visible_animals = [h for h in self.alive_herbivores
                              if abs(h.x-agent.x)+abs(h.y-agent.y) <= agent.vision_radius]
            food_distances = [
                abs(cell.x - agent.x) + abs(cell.y - agent.y)
                for cell in nearby
                if cell.resource is not None and cell.resource.is_collectible
            ]
            nearest_food_distance = min(food_distances, default=None)
            nearest_prey_distance = min(
                (abs(h.x - agent.x) + abs(h.y - agent.y) for h in visible_animals),
                default=None,
            )
            # A carne reduz mais fome e recupera estamina; caçar passa a valer
            # quando a presa está perto da comida vegetal mais próxima.
            should_hunt = (
                agent.hunger >= 20.0
                and nearest_prey_distance is not None
                and (
                    nearest_food_distance is None
                    or nearest_prey_distance <= nearest_food_distance + 1
                )
            )
            if should_hunt and visible_animals:
                prey = min(visible_animals, key=lambda h: abs(h.x-agent.x)+abs(h.y-agent.y))
                agent.hunt_target = (prey.x, prey.y)
                agent.running = (abs(prey.x-agent.x)+abs(prey.y-agent.y) > 1
                    and agent.energy >= self.physiology_config.stamina_run_minimum)
            else:
                agent.hunt_target = None
                agent.running = False
            agent.occupied_positions = (
                {(other.x, other.y) for other in alive_at_start if other is not agent}
                | {(animal.x, animal.y) for animal in self.alive_herbivores}
                | {(animal.x, animal.y) for animal in self.alive_carnivores}
            )
            agent.unavailable_shelter_positions = {
                (other.x, other.y) for other in alive_at_start
                if other is not agent
                and isinstance(self.world.get_cell(other.x, other.y).structure, Shelter)
            }
            visible_social_agents = [
                other for other in alive_at_start
                if self.social_behavior_enabled
                and other is not agent
                and abs(other.x - agent.x) + abs(other.y - agent.y) <= agent.vision_radius
            ]
            current_step = self.steps + 1
            agent.social_reunion_affinity_threshold = self.social_config.reunion_affinity_threshold
            agent.social_reunion_max_distance = self.social_config.reunion_max_distance
            agent.social_neighbors = [(other.x, other.y) for other in visible_social_agents]
            agent.social_neighbor_affinities = {
                (other.x, other.y): agent.social_affinities.get(other.agent_id, 0.0)
                for other in visible_social_agents
            }
            agent.social_neighbor_ids = {
                (other.x, other.y): other.agent_id for other in visible_social_agents
            }
            if self.social_behavior_enabled and self.social_memory_enabled:
                for other in visible_social_agents:
                    agent.social_known_contacts[other.agent_id] = {
                        "x": other.x, "y": other.y, "last_seen_step": current_step,
                    }
                agent.social_known_contacts = {
                    contact_id: memory
                    for contact_id, memory in agent.social_known_contacts.items()
                    if current_step - int(memory.get("last_seen_step", current_step)) <= self.social_config.memory_ttl_steps
                    and any(other.agent_id == contact_id and other.alive for other in self.agents)
                }
                agent.social_candidate_contacts = []
                for contact_id, memory in agent.social_known_contacts.items():
                    age = current_step - int(memory.get("last_seen_step", current_step))
                    distance = abs(int(memory["x"]) - agent.x) + abs(int(memory["y"]) - agent.y)
                    if distance > self.social_config.reunion_max_distance:
                        continue
                    agent.social_candidate_contacts.append({
                        "agent_id": contact_id, "x": int(memory["x"]), "y": int(memory["y"]),
                        "affinity": agent.social_affinities.get(contact_id, 0.0),
                        "last_seen_age": age,
                        "visible": any(other.agent_id == contact_id for other in visible_social_agents),
                    })
            else:
                agent.social_known_contacts.clear()
                agent.social_candidate_contacts = []
            actions[id(agent)] = agent.choose_action(nearby, self.world)
            if not agent.is_sleeping and agent.energy >= self.physiology_config.stamina_run_minimum:
                if agent.target is not None:
                    target_distance = abs(agent.target[0] - agent.x) + abs(agent.target[1] - agent.y)
                else:
                    target_distance = 0
                urgent_target = (
                    agent.target_intent == "HUNT"
                    or (agent.target_intent == "SEEK_WATER" and agent.thirst >= 55.0)
                    or (agent.target_intent == "SEEK_FOOD" and agent.hunger >= 60.0)
                )
                agent.running = bool(urgent_target and target_distance >= 3)
            else:
                agent.running = False

        # Cada tecla corresponde a um único passo, evitando movimento contínuo
        # involuntário quando a simulação está em velocidade acelerada.
        self.manual_action = (0, 0)
        self.manual_running = False
        moved_by_id = self._resolve_movements(actions)
        for agent in alive_at_start:
            self._record_social_decision(
                agent=agent, step=self.steps + 1,
                position_before=before[id(agent)],
                action=actions.get(id(agent), (0, 0)),
                moved=moved_by_id.get(id(agent), False),
            )

        sampled_states: dict[int, tuple[float, float, float, float]] = {}

        # Collection is resolved after movement. Exclusive occupancy ensures
        # only one agent can collect a resource from a cell in this step.
        for agent in alive_at_start:
            key = id(agent)
            moved = moved_by_id.get(key, False)
            after_move = (agent.x, agent.y)
            displacement = dist(before[key], after_move)
            metrics = self.metrics_by_agent[key]

            if moved and displacement > 0:
                metrics.movement_steps += 1
                metrics.distance_travelled += displacement
            else:
                metrics.idle_steps += 1

            food_energy_recovered = 0.0
            movement_energy_cost = 0.0
            rest_energy_recovered = 0.0
            drank_water = False
            water_thirst_reduction = 0.0
            collected_resource_type = "NONE"
            collected_food_quantity = 0.0
            current_resource = self.world.get_cell(agent.x, agent.y).resource
            if isinstance(current_resource, Water) and agent.thirst > 0:
                drank_water = True
                before_thirst = agent.thirst
                agent.needs.drink(current_resource.drink_amount)
                metrics.water_drinks += 1
                consumed = before_thirst - agent.thirst
                water_thirst_reduction = consumed
                metrics.water_units_consumed += consumed
                self._record_water_event("humans", before_thirst, agent.thirst)

            collection_quantity = None
            if isinstance(current_resource, MaterialResource):
                capacity_units = agent.inventory.max_collectible_units(current_resource.kind)
                collection_quantity = min(1, capacity_units) if capacity_units > 0 else 0
            elif isinstance(current_resource, Food):
                collection_quantity = agent.inventory.available_weight
            elif isinstance(current_resource, Plant) and agent.inventory.max_food_units() < 1:
                collection_quantity = 0

            can_collect = not isinstance(current_resource, (MaterialResource, Food, Plant)) or collection_quantity is None or collection_quantity > 0
            resource = (
                self.world.collect_resource(agent.x, agent.y, quantity=collection_quantity)
                if can_collect else None
            )
            if resource is not None:
                if isinstance(resource, Plant):
                    collected_resource_type = "PLANT"
                    accepted_food = agent.inventory.add_food(1.0)
                    collected_food_quantity = accepted_food
                    if accepted_food < 1.0 - 1e-9:
                        raise RuntimeError("A planta foi removida sem caber integralmente no inventário.")
                elif isinstance(resource, Food):
                    collected_resource_type = "FOOD"
                    accepted_food = agent.inventory.add_food(resource.quantity)
                    collected_food_quantity = accepted_food
                    if accepted_food < resource.quantity - 1e-9:
                        raise RuntimeError("O alimento foi coletado além da capacidade do inventário.")
                elif isinstance(resource, MaterialResource):
                    collected_resource_type = resource.kind.value.upper()
                    agent.inventory.add_resource(resource)
                self._record_collection_event(resource, "human")

            collected_food = isinstance(resource, (Plant, Food))
            if collected_food:
                metrics.food_collected += 1
                self.food_collection_steps_by_agent[key].append(self.steps + 1)
                self._steps_without_food_by_agent[key] = 0

            self._try_autonomous_shelter_build(agent)
            storage_transfers = self._interact_with_storage(agent)
            consumed_food = 0.0
            food_energy_recovered = 0.0
            if agent.hunger >= 35.0 and agent.inventory.food_quantity >= 1.0:
                agent.inventory.remove_food(1.0)
                energy_before_food = agent.energy
                agent.eat(FOOD_ENERGY)
                food_energy_recovered = agent.energy - energy_before_food
                consumed_food = 1.0
                metrics.food_consumed += 1
                self._current_resource_events["food_units_consumed_by_humans"] += 1.0

            if collected_food or consumed_food > 0:
                self._steps_without_food_by_agent[key] = 0
            else:
                self._steps_without_food_by_agent[key] += 1

            metrics.max_steps_without_food = max(
                metrics.max_steps_without_food,
                self._steps_without_food_by_agent[key],
            )
            if agent.running and moved:
                energy_before_cost = agent.energy
                agent.consume_energy(self.physiology_config.stamina_run_cost)
                movement_energy_cost = energy_before_cost - agent.energy
            elif moved:
                energy_before_cost = agent.energy
                agent.consume_energy(ENERGY_PER_STEP * displacement)
                movement_energy_cost = energy_before_cost - agent.energy
            elif not agent._sleep_selected and (agent._rest_selected or (not agent._waiting_selected and actions.get(key, (0, 0)) == (0, 0))):
                energy_before_rest = agent.energy
                current_structure = self.world.get_cell(agent.x, agent.y).structure
                rest_amount = (
                    self.physiology_config.stamina_shelter_rest_recovery
                    if isinstance(current_structure, Shelter)
                    else self.physiology_config.stamina_rest_recovery
                )
                agent.rest(rest_amount)
                rest_energy_recovered = agent.energy - energy_before_rest

            if agent.is_sleeping or agent._sleep_selected:
                activity = "SLEEPING"
                agent.is_sleeping = True
            elif moved:
                activity = "RUNNING" if agent.running else "WALKING"
            elif agent._rest_selected or (not agent._waiting_selected and actions.get(key, (0, 0)) == (0, 0)):
                activity = "RESTING"
            else:
                activity = "WAITING"
            agent.last_activity = activity
            activity_config = self.physiology_config
            activity_costs = {
                "WAITING": (activity_config.hunger_wait_cost, activity_config.thirst_wait_cost, activity_config.fatigue_wait_per_step),
                "WALKING": (activity_config.hunger_walk_cost, activity_config.thirst_walk_cost, activity_config.fatigue_walk_per_step),
                "RUNNING": (activity_config.hunger_run_cost, activity_config.thirst_run_cost, activity_config.fatigue_run_per_step),
                "RESTING": (activity_config.hunger_rest_cost, activity_config.thirst_rest_cost, activity_config.fatigue_rest_per_step),
                "SLEEPING": (activity_config.hunger_rest_cost, activity_config.thirst_rest_cost,
                    - (activity_config.fatigue_shelter_sleep_recovery if isinstance(self.world.get_cell(agent.x, agent.y).structure, Shelter)
                       else activity_config.fatigue_sleep_recovery)),
            }
            hunger_extra, thirst_extra, fatigue_delta = activity_costs[activity]
            if activity == "WAITING":
                energy_before_wait_recovery = agent.energy
                agent.needs.restore_energy(activity_config.stamina_wait_recovery)
                rest_energy_recovered = agent.energy - energy_before_wait_recovery
            elif activity == "SLEEPING":
                energy_before_sleep_recovery = agent.energy
                agent.needs.restore_energy(activity_config.stamina_sleep_recovery)
                rest_energy_recovered = agent.energy - energy_before_sleep_recovery
            health_before_needs = agent.health
            agent.needs.advance_step(
                hunger_extra=hunger_extra, thirst_extra=thirst_extra, fatigue_delta=fatigue_delta
            )
            if activity == "SLEEPING" and agent.needs.fatigue <= activity_config.sleep_end_threshold:
                agent.is_sleeping = False
                agent.last_behavior_intent = "AWAKE"
            health_after_physiology = agent.health
            if agent.hunger >= agent.needs.starvation_threshold:
                metrics.critical_hunger_steps += 1
            if agent.thirst >= agent.needs.dehydration_threshold:
                metrics.critical_thirst_steps += 1
            if "STARVATION" in agent.needs.last_damage_causes:
                metrics.starvation_damage_steps += 1
                if metrics.first_starvation_damage_step is None:
                    metrics.first_starvation_damage_step = self.steps + 1
            if "DEHYDRATION" in agent.needs.last_damage_causes:
                metrics.dehydration_damage_steps += 1
                if metrics.first_dehydration_damage_step is None:
                    metrics.first_dehydration_damage_step = self.steps + 1
            agent.alive = agent.needs.alive
            metrics.agent_lifetime_steps += 1

            self.position_history_by_agent[key].append((agent.x, agent.y))
            self._visited_positions_by_agent[key].add((agent.x, agent.y))
            self.energy_history_by_agent[key].append(agent.energy)
            metrics.final_energy = agent.energy
            metrics.final_health = agent.health
            metrics.final_hunger = agent.hunger
            metrics.final_thirst = agent.thirst
            metrics.energy_sum += agent.energy
            metrics.energy_samples += 1
            metrics.health_sum += agent.health
            metrics.hunger_sum += agent.hunger
            metrics.thirst_sum += agent.thirst
            metrics.need_samples += 1
            metrics.average_health = metrics.health_sum / metrics.need_samples
            metrics.average_hunger = metrics.hunger_sum / metrics.need_samples
            metrics.average_thirst = metrics.thirst_sum / metrics.need_samples
            sampled_states[key] = (
                agent.energy, agent.health, agent.hunger, agent.thirst
            )
            metrics.unique_positions_visited = len(self._visited_positions_by_agent[key])
            self.diagnostic_history_by_agent[key].append({
                "step": self.steps + 1,
                "position_before": before[key],
                "position_after": (agent.x, agent.y),
                "energy_before": energy_before[key],
                "energy_after": agent.energy,
                "collected_food": collected_food,
                "collected_food_quantity": collected_food_quantity,
                "collected_resource_type": collected_resource_type,
                "behavior_intent": agent.last_behavior_intent,
                "inventory_weight": agent.inventory.current_weight,
                "inventory_food": agent.inventory.food_quantity,
                "food_consumed": consumed_food,
                "storage_food_deposited": storage_transfers["food_deposited"],
                "storage_food_withdrawn": storage_transfers["food_withdrawn"],
                "storage_wood_deposited": storage_transfers["wood_deposited"],
                "storage_stone_deposited": storage_transfers["stone_deposited"],
                "storage_fiber_deposited": storage_transfers["fiber_deposited"],
                "inventory_wood": agent.inventory.quantity_of(MaterialKind.WOOD),
                "inventory_stone": agent.inventory.quantity_of(MaterialKind.STONE),
                "inventory_fiber": agent.inventory.quantity_of(MaterialKind.FIBER),
                "drank_water": drank_water,
                "water_thirst_reduction": water_thirst_reduction,
                "action": actions[key],
                "moved": moved,
                "distance": displacement,
                "health_before": physiology_before[key]["health"],
                "health_after_physiology": health_after_physiology,
                "hunger_before": physiology_before[key]["hunger"],
                "hunger_after_physiology": agent.hunger,
                "thirst_before": physiology_before[key]["thirst"],
                "thirst_after_physiology": agent.thirst,
                "fatigue_before": physiology_before[key]["fatigue"],
                "fatigue_after_physiology": agent.needs.fatigue,
                "activity": activity,
                "simulated_minute": self.simulated_minutes + 1,
                "movement_energy_cost": movement_energy_cost,
                "food_energy_recovered": food_energy_recovered,
                "rest_energy_recovered": rest_energy_recovered,
                "energy_after_actions": agent.energy,
                "damage_causes": list(agent.needs.last_damage_causes),
            })
            self.physiology_activity_history.append({
                "step": self.steps + 1, "simulated_minute": self.simulated_minutes + 1,
                "individual_type": "HUMAN", "individual_id": agent.agent_id or f"H{id(agent)}",
                "x": agent.x, "y": agent.y, "activity": activity,
                "behavior_intent": agent.last_behavior_intent,
                "decision_action_id": (agent.last_decision_trace or {}).get("action_id", ""),
                "decision_score": (agent.last_decision_trace or {}).get("score", ""),
                "moved": bool(moved), "distance": float(displacement),
                "stamina_before": energy_before[key], "stamina_after": agent.energy,
                "stamina_spent_movement": movement_energy_cost,
                "stamina_recovered_rest": rest_energy_recovered,
                "stamina_spent_combat": 0.0,
                "hunger_metabolic_cost": agent.needs.hunger_per_step + hunger_extra,
                "thirst_metabolic_cost": agent.needs.thirst_per_step + thirst_extra,
                "fatigue_delta": fatigue_delta,
                "fatigue_before": physiology_before[key]["fatigue"], "fatigue_after": agent.needs.fatigue,
                "hunger_before": physiology_before[key]["hunger"], "hunger_after": agent.hunger,
                "thirst_before": physiology_before[key]["thirst"], "thirst_after": agent.thirst,
                "health_before": physiology_before[key]["health"], "health_after": agent.health,
                "damage_causes": ";".join(agent.needs.last_damage_causes),
                "sleeping_after_step": agent.is_sleeping,
                "sleep_interruption_reason": agent._sleep_interruption_event,
                "termination_cause": "RUNNING" if agent.alive else (agent.needs.last_damage_cause or "HEALTH_DEPLETED"),
            })
            if not agent.alive:
                causes = set(agent.needs.last_damage_causes)
                physiological_causes = causes.intersection({"STARVATION", "DEHYDRATION"})
                if physiological_causes == {"STARVATION", "DEHYDRATION"}:
                    metrics.termination_cause = "STARVATION_AND_DEHYDRATION"
                elif physiological_causes:
                    metrics.termination_cause = next(iter(physiological_causes))
                else:
                    metrics.termination_cause = agent.needs.last_damage_cause or "HEALTH_DEPLETED"

        # Custos de combate são registrados separadamente dos custos de locomoção.
        combat_stamina_spent: dict[int, float] = {}
        # Humanos atacam herbívoros adjacentes apenas quando estão caçando.
        for agent in self.alive_agents:
            if agent.hunt_target is None or agent.energy < self.physiology_config.stamina_attack_cost:
                continue
            prey = next((h for h in self.alive_herbivores
                         if abs(h.x-agent.x) + abs(h.y-agent.y) <= 1), None)
            if prey is None:
                continue
            agent.consume_energy(self.physiology_config.stamina_attack_cost)
            combat_stamina_spent[id(agent)] = combat_stamina_spent.get(id(agent), 0.0) + self.physiology_config.stamina_attack_cost
            prey_health_before = prey.health
            prey.needs.damage(ATTACK_DAMAGE, cause="HUNTING")
            self.attacks += 1
            if not prey.needs.alive:
                prey.alive = False
                agent.needs.eat(MEAT_HUNGER_REDUCTION)
                agent.needs.restore_energy(MEAT_STAMINA_REWARD)
                self.animals_killed += 1
                prey_id = f"V{self.herbivores.index(prey)+1:03d}"
                self.physiology_activity_history.append({
                    "step": self.steps + 1, "simulated_minute": self.simulated_minutes + 1,
                    "individual_type": "HERBIVORE", "individual_id": prey_id,
                    "x": prey.x, "y": prey.y, "activity": "DEAD",
                    "behavior_intent": "KILLED_BY_HUNTING", "decision_action_id": "", "decision_score": "",
                    "moved": False, "distance": 0.0,
                    "stamina_before": prey.needs.energy, "stamina_after": prey.needs.energy,
                    "stamina_spent_movement": 0.0, "stamina_recovered_rest": 0.0,
                    "stamina_spent_combat": 0.0, "hunger_metabolic_cost": 0.0,
                    "thirst_metabolic_cost": 0.0, "fatigue_delta": 0.0,
                    "fatigue_before": prey.needs.fatigue, "fatigue_after": prey.needs.fatigue,
                    "hunger_before": prey.hunger, "hunger_after": prey.hunger,
                    "thirst_before": prey.thirst, "thirst_after": prey.thirst,
                    "health_before": prey_health_before, "health_after": prey.health,
                    "damage_causes": "HUNTING", "sleeping_after_step": False,
                    "sleep_interruption_reason": "", "termination_cause": "HUNTING",
                })

        # Animais agem como entidades independentes, com fisiologia e corrida próprias.
        occupied_agents = {(a.x, a.y) for a in self.alive_agents}
        occupied_animals = {(h.x, h.y) for h in self.alive_herbivores}
        for animal in list(self.alive_herbivores):
            animal._sleep_interruption_event = ""
            before_pos = (animal.x, animal.y)
            before_state = {
                "health": animal.health, "hunger": animal.hunger,
                "thirst": animal.thirst, "stamina": animal.needs.energy,
                "fatigue": animal.needs.fatigue,
            }
            threat_positions = list(occupied_agents) + [
                (c.x, c.y) for c in self.alive_carnivores
            ]
            nearby_threats = [p for p in threat_positions
                if abs(p[0] - animal.x) + abs(p[1] - animal.y) <= 3]
            wake_reason = self._sleep_wake_reason(animal) if animal.is_sleeping else ""
            if wake_reason:
                animal.is_sleeping = False
                animal.last_sleep_interruption_reason = wake_reason
                animal._sleep_interruption_event = wake_reason
            if animal.is_sleeping:
                action = (0, 0)
                activity = "SLEEPING"
            elif (animal.needs.fatigue >= self.physiology_config.sleep_start_threshold
                  and animal.hunger < 35.0
                  and animal.thirst < 40.0
                  and not nearby_threats):
                animal.is_sleeping = True
                animal.last_sleep_interruption_reason = ""
                action = (0, 0)
                activity = "SLEEPING"
            elif (animal.needs.energy < 12.0 and animal.hunger < 45.0
                  and animal.thirst < 45.0 and not nearby_threats):
                action = (0, 0)
                activity = "RESTING"
            else:
                action = animal.choose_action(self.world, threat_positions)
                activity = "WAITING" if action == (0, 0) else "WALKING"
                target = getattr(animal, "target", None)
                target_distance = (abs(target[0] - animal.x) + abs(target[1] - animal.y)) if target else 0
                urgent = (
                    (isinstance(animal, Herbivore) and (animal.fleeing or animal.hunger >= 65 or animal.thirst >= 65))
                    or (isinstance(animal, Carnivore) and (
                        (animal.hunger >= 30 and target_distance >= 3)
                        or (animal.thirst >= 55 and target_distance >= 3)
                    ))
                )
                animal.running = bool(urgent and (animal.fleeing if isinstance(animal, Herbivore) else target_distance >= 2)
                    and animal.needs.energy >= self.physiology_config.stamina_run_minimum)
                if animal.running and action != (0, 0):
                    activity = "RUNNING"
            before_move = (animal.x, animal.y)
            if action != (0, 0):
                max_distance = 2 if animal.running and animal.needs.energy >= self.physiology_config.stamina_run_cost else 1
                for _ in range(max_distance):
                    nx, ny = animal.x + action[0], animal.y + action[1]
                    occupied_now = occupied_agents | (occupied_animals - {before_move})
                    if (nx, ny) in occupied_now or not self.world.is_walkable(nx, ny):
                        break
                    if not self.world.move_agent(animal, action):
                        break
                if (animal.x, animal.y) != before_move:
                    occupied_animals.discard(before_move)
                    occupied_animals.add((animal.x, animal.y))
                else:
                    activity = "WAITING"
                    animal.running = False
            animal.last_activity = activity

            resource = self.world.get_cell(animal.x, animal.y).resource
            if activity != "SLEEPING":
                if isinstance(resource, Water) and animal.thirst > 0:
                    thirst_before = animal.thirst
                    animal.drink(resource.drink_amount)
                    self._record_water_event("herbivores", thirst_before, animal.thirst)
                elif isinstance(resource, Plant) and resource.state == PlantState.MATURE and animal.hunger >= 20:
                    collected_plant = self.world.collect_resource(animal.x, animal.y)
                    if collected_plant is not None:
                        self._record_collection_event(collected_plant, "herbivore")
                        animal.eat(35.0)
            stamina_before_recovery = animal.needs.energy
            if activity == "RUNNING" and (animal.x, animal.y) != before_move:
                animal.needs.energy = max(0.0, animal.needs.energy - self.physiology_config.stamina_run_cost)
            elif (animal.x, animal.y) != before_move:
                animal.needs.energy = max(0.0, animal.needs.energy - ENERGY_PER_STEP * (abs(animal.x-before_move[0])+abs(animal.y-before_move[1])))
            elif activity == "RESTING":
                animal.needs.restore_energy(self.physiology_config.stamina_rest_recovery)
            elif activity == "WAITING":
                animal.needs.restore_energy(self.physiology_config.stamina_wait_recovery)
            elif activity == "SLEEPING":
                animal.needs.restore_energy(self.physiology_config.stamina_sleep_recovery)
            stamina_recovered_activity = max(0.0, animal.needs.energy - stamina_before_recovery)
            activity_costs = {
                "WAITING": (self.physiology_config.hunger_wait_cost, self.physiology_config.thirst_wait_cost, self.physiology_config.fatigue_wait_per_step),
                "WALKING": (self.physiology_config.hunger_walk_cost, self.physiology_config.thirst_walk_cost, self.physiology_config.fatigue_walk_per_step),
                "RUNNING": (self.physiology_config.hunger_run_cost, self.physiology_config.thirst_run_cost, self.physiology_config.fatigue_run_per_step),
                "RESTING": (self.physiology_config.hunger_rest_cost, self.physiology_config.thirst_rest_cost, self.physiology_config.fatigue_rest_per_step),
                "SLEEPING": (self.physiology_config.hunger_rest_cost, self.physiology_config.thirst_rest_cost,
                    -(self.physiology_config.fatigue_shelter_sleep_recovery if isinstance(self.world.get_cell(animal.x, animal.y).structure, Shelter)
                      else self.physiology_config.fatigue_sleep_recovery)),
            }
            hunger_extra, thirst_extra, fatigue_delta = activity_costs[activity]
            animal.needs.advance_step(hunger_extra=hunger_extra, thirst_extra=thirst_extra, fatigue_delta=fatigue_delta)
            if activity == "SLEEPING" and animal.needs.fatigue <= self.physiology_config.sleep_end_threshold:
                animal.is_sleeping = False
            animal.alive = animal.needs.alive
            self.physiology_activity_history.append({
                "step": self.steps + 1, "simulated_minute": self.simulated_minutes + 1,
                "individual_type": "HERBIVORE", "individual_id": f"V{self.herbivores.index(animal)+1:03d}",
                "x": animal.x, "y": animal.y, "activity": activity,
                "behavior_intent": "FLEE" if animal.fleeing else ("SEEK_RESOURCE" if animal.target else activity),
                "moved": (animal.x, animal.y) != before_pos,
                "distance": float(abs(animal.x-before_pos[0])+abs(animal.y-before_pos[1])),
                "stamina_before": before_state["stamina"], "stamina_after": animal.needs.energy,
                "stamina_spent_movement": ((self.physiology_config.stamina_run_cost if activity == "RUNNING" else ENERGY_PER_STEP * abs(animal.x-before_pos[0])+ENERGY_PER_STEP * abs(animal.y-before_pos[1])) if activity in {"WALKING", "RUNNING"} else 0.0),
                "stamina_recovered_rest": stamina_recovered_activity,
                "stamina_spent_combat": 0.0,
                "hunger_metabolic_cost": animal.needs.hunger_per_step + hunger_extra,
                "thirst_metabolic_cost": animal.needs.thirst_per_step + thirst_extra,
                "fatigue_delta": fatigue_delta,
                "fatigue_before": before_state["fatigue"], "fatigue_after": animal.needs.fatigue,
                "hunger_before": before_state["hunger"], "hunger_after": animal.hunger,
                "thirst_before": before_state["thirst"], "thirst_after": animal.thirst,
                "health_before": before_state["health"], "health_after": animal.health,
                "damage_causes": ";".join(animal.needs.last_damage_causes),
                "sleeping_after_step": animal.is_sleeping,
                "sleep_interruption_reason": animal._sleep_interruption_event,
                "termination_cause": "RUNNING" if animal.alive else (animal.needs.last_damage_cause or "HEALTH_DEPLETED"),
            })
            if was_alive := before_state["health"] > 0:
                if not animal.alive:
                    if "STARVATION" in animal.needs.last_damage_causes:
                        self.herbivores_died_by_starvation += 1
                    if "DEHYDRATION" in animal.needs.last_damage_causes:
                        self.herbivores_died_by_dehydration += 1

        # Carnívoros usam a mesma regra de corrida e sono, mas podem dormir apenas
        # quando não há presa próxima nem necessidade fisiológica urgente.
        for carnivore in list(self.alive_carnivores):
            carnivore._sleep_interruption_event = ""
            before_pos = (carnivore.x, carnivore.y)
            before_state = {
                "health": carnivore.health, "hunger": carnivore.hunger,
                "thirst": carnivore.thirst, "stamina": carnivore.needs.energy,
                "fatigue": carnivore.needs.fatigue,
            }
            test_target = getattr(carnivore, "test_target_agent", None)
            if test_target is not None and test_target.alive:
                prey_positions = [(test_target.x, test_target.y)]
            else:
                prey_positions = ([(a.x, a.y) for a in self.alive_agents]
                                  + [(h.x, h.y) for h in self.alive_herbivores])
            nearby_threats = []  # carnívoros não tratam presas como ameaça durante o sono
            wake_reason = self._sleep_wake_reason(carnivore) if carnivore.is_sleeping else ""
            if wake_reason:
                carnivore.is_sleeping = False
                carnivore.last_sleep_interruption_reason = wake_reason
                carnivore._sleep_interruption_event = wake_reason
            if carnivore.is_sleeping:
                action = (0, 0); activity = "SLEEPING"
            elif (carnivore.needs.fatigue >= self.physiology_config.sleep_start_threshold
                  and carnivore.hunger < 35.0
                  and carnivore.thirst < 40.0
                  and not any(abs(px-carnivore.x)+abs(py-carnivore.y) <= 3 for px,py in prey_positions)):
                carnivore.is_sleeping = True
                carnivore.last_sleep_interruption_reason = ""
                action = (0, 0); activity = "SLEEPING"
            elif (carnivore.needs.energy < 12.0 and carnivore.hunger < 45.0
                  and carnivore.thirst < 45.0 and not any(abs(px-carnivore.x)+abs(py-carnivore.y) <= 3 for px,py in prey_positions)):
                action = (0, 0); activity = "RESTING"
            else:
                action = carnivore.choose_action(self.world, prey_positions)
                activity = "WAITING" if action == (0, 0) else "WALKING"
                target = getattr(carnivore, "target", None)
                target_distance = (abs(target[0]-carnivore.x)+abs(target[1]-carnivore.y)) if target else 0
                urgent = (carnivore.hunger >= 30 and target_distance >= 3) or (carnivore.thirst >= 55 and target_distance >= 3)
                carnivore.running = bool(urgent and target_distance >= 2
                    and carnivore.needs.energy >= self.physiology_config.stamina_run_minimum)
                if carnivore.running and action != (0,0): activity = "RUNNING"
            if action != (0, 0):
                max_distance = 2 if carnivore.running and carnivore.needs.energy >= self.physiology_config.stamina_run_cost else 1
                for _ in range(max_distance):
                    nx, ny = carnivore.x + action[0], carnivore.y + action[1]
                    occupied_now = ({(a.x,a.y) for a in self.alive_agents}
                        | {(h.x,h.y) for h in self.alive_herbivores if h is not carnivore}
                        | {(c.x,c.y) for c in self.alive_carnivores if c is not carnivore})
                    if (nx,ny) in occupied_now or not self.world.is_walkable(nx,ny): break
                    if not self.world.move_agent(carnivore, action): break
                if (carnivore.x, carnivore.y) == before_pos:
                    activity = "WAITING"
                    carnivore.running = False
            carnivore.last_activity = activity
            resource = self.world.get_cell(carnivore.x, carnivore.y).resource
            if activity != "SLEEPING":
                if isinstance(resource, Water) and carnivore.thirst > 0:
                    thirst_before = carnivore.thirst
                    carnivore.drink(resource.drink_amount)
                    self._record_water_event("carnivores", thirst_before, carnivore.thirst)
            displacement = abs(carnivore.x-before_pos[0])+abs(carnivore.y-before_pos[1])
            stamina_before_recovery = carnivore.needs.energy
            if activity == "RUNNING" and displacement:
                carnivore.needs.energy = max(0.0, carnivore.needs.energy-self.physiology_config.stamina_run_cost)
            elif displacement:
                carnivore.needs.energy = max(0.0, carnivore.needs.energy-ENERGY_PER_STEP*displacement)
            elif activity == "RESTING":
                carnivore.needs.restore_energy(self.physiology_config.stamina_rest_recovery)
            elif activity == "WAITING":
                carnivore.needs.restore_energy(self.physiology_config.stamina_wait_recovery)
            elif activity == "SLEEPING":
                carnivore.needs.restore_energy(self.physiology_config.stamina_sleep_recovery)
            stamina_recovered_activity = max(0.0, carnivore.needs.energy - stamina_before_recovery)
            activity_costs = {
                "WAITING": (self.physiology_config.hunger_wait_cost, self.physiology_config.thirst_wait_cost, self.physiology_config.fatigue_wait_per_step),
                "WALKING": (self.physiology_config.hunger_walk_cost, self.physiology_config.thirst_walk_cost, self.physiology_config.fatigue_walk_per_step),
                "RUNNING": (self.physiology_config.hunger_run_cost, self.physiology_config.thirst_run_cost, self.physiology_config.fatigue_run_per_step),
                "RESTING": (self.physiology_config.hunger_rest_cost, self.physiology_config.thirst_rest_cost, self.physiology_config.fatigue_rest_per_step),
                "SLEEPING": (self.physiology_config.hunger_rest_cost, self.physiology_config.thirst_rest_cost,
                    -(self.physiology_config.fatigue_shelter_sleep_recovery if isinstance(self.world.get_cell(carnivore.x, carnivore.y).structure, Shelter)
                      else self.physiology_config.fatigue_sleep_recovery)),
            }
            hunger_extra, thirst_extra, fatigue_delta = activity_costs[activity]
            carnivore.needs.advance_step(hunger_extra=hunger_extra, thirst_extra=thirst_extra, fatigue_delta=fatigue_delta)
            if activity == "SLEEPING" and carnivore.needs.fatigue <= self.physiology_config.sleep_end_threshold:
                carnivore.is_sleeping = False
            carnivore.alive = carnivore.needs.alive
            self.physiology_activity_history.append({
                "step": self.steps + 1, "simulated_minute": self.simulated_minutes + 1,
                "individual_type": "CARNIVORE", "individual_id": f"C{self.carnivores.index(carnivore)+1:03d}",
                "x": carnivore.x, "y": carnivore.y, "activity": activity,
                "behavior_intent": "HUNT" if carnivore.hunger >= 30 else ("SEEK_WATER" if carnivore.thirst >= 55 else activity),
                "moved": displacement > 0, "distance": float(displacement),
                "stamina_before": before_state["stamina"], "stamina_after": carnivore.needs.energy,
                "stamina_spent_movement": ((self.physiology_config.stamina_run_cost if activity == "RUNNING" else ENERGY_PER_STEP * displacement) if activity in {"WALKING","RUNNING"} else 0.0),
                "stamina_recovered_rest": stamina_recovered_activity,
                "stamina_spent_combat": 0.0,
                "hunger_metabolic_cost": carnivore.needs.hunger_per_step + hunger_extra,
                "thirst_metabolic_cost": carnivore.needs.thirst_per_step + thirst_extra,
                "fatigue_delta": fatigue_delta,
                "fatigue_before": before_state["fatigue"], "fatigue_after": carnivore.needs.fatigue,
                "hunger_before": before_state["hunger"], "hunger_after": carnivore.hunger,
                "thirst_before": before_state["thirst"], "thirst_after": carnivore.thirst,
                "health_before": before_state["health"], "health_after": carnivore.health,
                "damage_causes": ";".join(carnivore.needs.last_damage_causes),
                "sleeping_after_step": carnivore.is_sleeping,
                "sleep_interruption_reason": carnivore._sleep_interruption_event,
                "termination_cause": "RUNNING" if carnivore.alive else (carnivore.needs.last_damage_cause or "HEALTH_DEPLETED"),
            })
            if not carnivore.alive:
                if "STARVATION" in carnivore.needs.last_damage_causes:
                    self.carnivores_died_by_starvation += 1
                if "DEHYDRATION" in carnivore.needs.last_damage_causes:
                    self.carnivores_died_by_dehydration += 1

        # Humanos podem se defender se um carnívoro entrar em alcance corpo a corpo.
        # Defesa não exige fome; ataque de caça a herbívoro continua sendo outra ação.
        for agent in self.alive_agents:
            if agent.energy < self.physiology_config.stamina_attack_cost:
                continue
            if any(abs(c.x-agent.x) + abs(c.y-agent.y) <= 1 for c in self.alive_carnivores):
                target = min(
                    (c for c in self.alive_carnivores
                     if abs(c.x-agent.x) + abs(c.y-agent.y) <= 1),
                    key=lambda c: abs(c.x-agent.x) + abs(c.y-agent.y),
                )
                agent.consume_energy(self.physiology_config.stamina_attack_cost)
                combat_stamina_spent[id(agent)] = combat_stamina_spent.get(id(agent), 0.0) + self.physiology_config.stamina_attack_cost
                target.needs.damage(20.0, cause="DEFENSE")
                self.human_defense_attacks += 1
                target.alive = target.needs.alive
                if not target.alive:
                    self.carnivores_killed += 1

        # Carnívoros atacam a presa adjacente mais próxima: primeiro humanos,
        # depois herbívoros. Cada indivíduo só pode receber um ataque por tick.
        attacked_this_step: set[int] = set()
        for carnivore in self.alive_carnivores:
            if carnivore.hunger < 30.0 or carnivore.needs.energy < self.physiology_config.stamina_attack_cost:
                continue
            test_target = getattr(carnivore, "test_target_agent", None)
            available_targets = (
                [test_target] if test_target is not None and test_target.alive
                else self.alive_agents + self.alive_herbivores
            )
            adjacent_targets = [
                target for target in available_targets
                if id(target) not in attacked_this_step
                and abs(target.x-carnivore.x) + abs(target.y-carnivore.y) <= 1
            ]
            # Prefere a presa mais próxima; em empate, herbívoros antes de humanos.
            adjacent_targets.sort(
                key=lambda target: (
                    abs(target.x-carnivore.x) + abs(target.y-carnivore.y),
                    1 if isinstance(target, Agent) else 0,
                    target.y, target.x,
                )
            )
            target = adjacent_targets[0] if adjacent_targets else None
            if target is None:
                continue
            damage = CARNIVORE_ATTACK_DAMAGE
            if isinstance(target, Agent) and isinstance(
                self.world.get_cell(target.x, target.y).structure, Shelter
            ):
                # O abrigo reduz bastante o dano, mas não torna o ocupante invulnerável.
                damage *= SHELTER_PREDATION_DAMAGE_MULTIPLIER
            health_before_attack = target.health
            carnivore.needs.energy = max(0.0, carnivore.needs.energy - self.physiology_config.stamina_attack_cost)
            combat_stamina_spent[id(carnivore)] = combat_stamina_spent.get(id(carnivore), 0.0) + self.physiology_config.stamina_attack_cost
            actual_damage = target.needs.damage(damage, cause="PREDATION")
            attacked_this_step.add(id(target))
            self.carnivore_attacks += 1
            if isinstance(target, Agent) and actual_damage > 0:
                self.damage_events.append({
                    "step": self.steps + 1,
                    "target_id": id(target),
                    "source": "Carnívoro de teste" if test_target is target else "Carnívoro",
                    "cause": "PREDATION",
                    "damage": actual_damage,
                    "health_before": health_before_attack,
                    "health_after": target.health,
                    "sheltered": isinstance(
                        self.world.get_cell(target.x, target.y).structure, Shelter
                    ),
                })
                # Mantém a janela responsiva e o histórico limitado em memória.
                if len(self.damage_events) > 100:
                    del self.damage_events[:-100]
            if not target.needs.alive:
                target.alive = False
                if isinstance(target, Agent):
                    target_metrics = self.metrics_by_agent[id(target)]
                    target_metrics.termination_cause = "PREDATION"
                    self.humans_killed_by_carnivores += 1
                else:
                    self.animals_killed += 1
                carnivore.eat(MEAT_HUNGER_REDUCTION)
            if isinstance(target, Agent):
                self.metrics_by_agent[id(target)].final_health = target.health

        # Corrige a amostra fisiológica do passo após caça e combate. Assim,
        # médias e valores finais refletem o estado real no fim do tick.
        for agent in alive_at_start:
            key = id(agent)
            old_energy, old_health, old_hunger, old_thirst = sampled_states[key]
            metrics = self.metrics_by_agent[key]
            metrics.energy_sum += agent.energy - old_energy
            metrics.health_sum += agent.health - old_health
            metrics.hunger_sum += agent.hunger - old_hunger
            metrics.thirst_sum += agent.thirst - old_thirst
            metrics.average_health = metrics.health_sum / metrics.need_samples if metrics.need_samples else 0.0
            metrics.average_hunger = metrics.hunger_sum / metrics.need_samples if metrics.need_samples else 0.0
            metrics.average_thirst = metrics.thirst_sum / metrics.need_samples if metrics.need_samples else 0.0
            metrics.final_energy = agent.energy
            metrics.final_health = agent.health
            metrics.final_hunger = agent.hunger
            metrics.final_thirst = agent.thirst
            for cause, cumulative in agent.needs.damage_by_cause.items():
                delta = cumulative - damage_before[key].get(cause, 0.0)
                if delta > 0:
                    metrics.damage_taken_by_cause[cause] = metrics.damage_taken_by_cause.get(cause, 0.0) + delta
            if self.diagnostic_history_by_agent[key]:
                diagnostic = self.diagnostic_history_by_agent[key][-1]
                diagnostic["health_after"] = agent.health
                diagnostic["hunger_after"] = agent.hunger
                diagnostic["thirst_after"] = agent.thirst
                diagnostic["energy_after"] = agent.energy
                diagnostic["energy_change_after_combat"] = agent.energy - diagnostic["energy_after_actions"]
                diagnostic["termination_cause"] = metrics.termination_cause if not agent.alive else "RUNNING"
                diagnostic["damage_causes"] = list(agent.needs.last_damage_causes)
                diagnostic["damage_by_cause"] = {
                    cause: cumulative - damage_before[key].get(cause, 0.0)
                    for cause, cumulative in agent.needs.damage_by_cause.items()
                    if cumulative - damage_before[key].get(cause, 0.0) > 0
                }
                if self.physiology_activity_history:
                    for activity_record in reversed(self.physiology_activity_history):
                        if activity_record.get("individual_type") == "HUMAN" and activity_record.get("individual_id") == (agent.agent_id or f"H{id(agent)}") and activity_record.get("step") == self.steps + 1:
                            activity_record["stamina_after"] = agent.energy
                            activity_record["stamina_spent_combat"] = combat_stamina_spent.get(id(agent), 0.0)
                            activity_record["health_after"] = agent.health
                            activity_record["damage_causes"] = ";".join(agent.needs.last_damage_causes)
                            activity_record["termination_cause"] = "RUNNING" if agent.alive else (agent.needs.last_damage_cause or "HEALTH_DEPLETED")
                            break

        current_activity_records = {
            (str(record.get("individual_type")), str(record.get("individual_id"))): record
            for record in self.physiology_activity_history
            if record.get("step") == self.steps + 1
        }
        for individual_type, individuals, prefix in (
            ("HERBIVORE", self.herbivores, "V"),
            ("CARNIVORE", self.carnivores, "C"),
        ):
            for index, individual in enumerate(individuals, start=1):
                individual_id = f"{prefix}{index:03d}"
                activity_record = current_activity_records.get((individual_type, individual_id))
                if activity_record is None:
                    continue
                activity_record["health_after"] = individual.health
                activity_record["damage_causes"] = ";".join(individual.needs.last_damage_causes)
                activity_record["termination_cause"] = "RUNNING" if individual.alive else (individual.needs.last_damage_cause or "HEALTH_DEPLETED")
                if id(individual) in combat_stamina_spent:
                    activity_record["stamina_after"] = individual.needs.energy
                    activity_record["stamina_spent_combat"] = combat_stamina_spent[id(individual)]

        self._record_social_agent_snapshot(step=self.steps + 1)
        self._advance_environment()

    def run(self, steps: int) -> None:
        if steps < 0:
            raise ValueError("O número de passos não pode ser negativo.")
        for agent in self.agents:
            if not agent.alive:
                metrics = self.metrics_by_agent[id(agent)]
                if metrics.termination_cause == "PREDATION":
                    continue
                causes = set(agent.needs.last_damage_causes)
                physiological_causes = causes.intersection({"STARVATION", "DEHYDRATION"})
                if physiological_causes == {"STARVATION", "DEHYDRATION"}:
                    metrics.termination_cause = "STARVATION_AND_DEHYDRATION"
                elif physiological_causes:
                    metrics.termination_cause = next(iter(physiological_causes))
                else:
                    metrics.termination_cause = agent.needs.last_damage_cause or "HEALTH_DEPLETED"
        target_step = self.steps + steps
        while self.steps < target_step:
            self.step()
        for agent in self.agents:
            metrics = self.metrics_by_agent[id(agent)]
            if agent.alive:
                metrics.termination_cause = "STEP_LIMIT"
