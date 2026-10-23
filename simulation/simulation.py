from math import dist
import random
from random import Random

from agents.agent import Agent
from agents.needs import AgentNeeds
from agents.species import Species
from animals.herbivore import Herbivore
from animals.carnivore import Carnivore
from animals.hunting_policy import (
    human_prey_is_too_risky, nearby_human_count, select_prey_candidate,
)
from agents.navigation.bfs import find_path
from agents.perception import Perception
from environment.world import World
from environment.resources import MaterialKind, MaterialResource, Water, Plant, PlantState, Food
from environment.storage import Storage
from environment.shelter import Shelter
from metrics.tracker import SimulationMetrics
from configuration.social_behavior_config import SocialBehaviorConfig
from configuration.physiology_config import DEFAULT_PHYSIOLOGY_CONFIG, PhysiologyConfig
from configuration.species_physiology import adjusted_hunger_rate
from agents.stamina_policy import recovery_amount, should_rest_for_stamina, should_run
from simulation.reproduction import LifeHistoryState, LIFE_HISTORY_CONFIG, ReproductionSystem
from simulation.carnivore_decisions import evaluate_human_threat
from simulation.health_recovery import recover_health_during_rest


FOOD_ENERGY = 35.0
ENERGY_PER_STEP = 1.0  # custo de estamina por célula percorrida
RUN_STAMINA_COST = 8.0
ATTACK_STAMINA_COST = 8.0
ATTACK_DAMAGE = 30.0
CARNIVORE_ATTACK_DAMAGE = 35.0
SHELTER_PREDATION_DAMAGE_MULTIPLIER = 0.25
MEAT_HUNGER_REDUCTION = 70.0
MEAT_STAMINA_REWARD = 25.0


def _target_progress_fields(
    target: object,
    intent: object,
    position_before: tuple[int, int],
    position_after: tuple[int, int],
    *,
    need_satisfied: bool = False,
) -> dict[str, object]:
    """Campos observacionais de progresso; não participam das decisões."""
    if not isinstance(target, (tuple, list)) or len(target) < 2:
        return {
            "target_intent_before_action": str(intent or "NONE"),
            "target_x_before_action": "", "target_y_before_action": "",
            "target_distance_before_action": "", "target_distance_after_action": "",
            "target_distance_progress": "", "target_in_interaction_range": False,
            "target_reached": False, "need_satisfied_this_step": bool(need_satisfied),
        }
    target_position = (int(target[0]), int(target[1]))
    distance_before = abs(target_position[0] - position_before[0]) + abs(target_position[1] - position_before[1])
    distance_after = abs(target_position[0] - position_after[0]) + abs(target_position[1] - position_after[1])
    return {
        "target_intent_before_action": str(intent or "NONE"),
        "target_x_before_action": target_position[0],
        "target_y_before_action": target_position[1],
        "target_distance_before_action": distance_before,
        "target_distance_after_action": distance_after,
        "target_distance_progress": distance_before - distance_after,
        "target_in_interaction_range": distance_after <= 1,
        "target_reached": distance_after == 0,
        "need_satisfied_this_step": bool(need_satisfied),
    }


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

            # Animais adicionados depois da inicialização da simulação também
            # passam pelo ciclo de reprodução em cada passo. Registrar o estado
            # de vida e o ID aqui evita AttributeError em process_step().
            existing_ids = set(self._carnivore_ids.values())
            next_number = 1
            while f"C{next_number:03d}" in existing_ids:
                next_number += 1
            carnivore_id = f"C{next_number:03d}"
            carnivore.agent_id = carnivore_id
            carnivore.life_history = LifeHistoryState(
                individual_id=carnivore_id,
                sex="M",
                age_steps=0,
            )
            self._carnivore_ids[id(carnivore)] = carnivore_id
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
        # IDs de auditoria persistem durante a execução, mesmo após mortes.
        self._herbivore_ids = {id(item): f"V{index + 1:03d}" for index, item in enumerate(self.herbivores)}
        self._carnivore_ids = {id(item): f"C{index + 1:03d}" for index, item in enumerate(self.carnivores)}
        # IDs estáveis também ficam no objeto para a interface poder selecionar
        # qualquer espécie sem depender de índices recalculados a cada quadro.
        for animal in self.herbivores:
            animal.agent_id = self._herbivore_ids[id(animal)]
        for animal in self.carnivores:
            animal.agent_id = self._carnivore_ids[id(animal)]
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
        # Mantém separado o humano controlável da entidade inspecionada na UI.
        # A inspeção pode apontar para qualquer espécie; controles humanos continuam
        # usando observed_agent para não passar animais a APIs exclusivas de humanos.
        self.observed_agent = self.agent
        self.observed_individual = self.agent
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
        self.reproduction = ReproductionSystem()
        self.reproduction_events = self.reproduction.events
        # Populações iniciais são fundadores adultos para permitir reprodução em
        # experimentos curtos; descendentes começam com idade zero.
        for species, group, prefix, id_map in (
            (Species.HUMAN, self.agents, "H", None),
            (Species.HERBIVORE, self.herbivores, "V", self._herbivore_ids),
            (Species.CARNIVORE, self.carnivores, "C", self._carnivore_ids),
        ):
            maturity = LIFE_HISTORY_CONFIG[species].maturity_steps
            for index, individual in enumerate(group):
                individual_id = (individual.agent_id if species is Species.HUMAN else id_map[id(individual)])
                individual.life_history = LifeHistoryState(
                    individual_id=individual_id,
                    sex="F" if index % 2 == 0 else "M",
                    age_steps=maturity,
                )
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
        # Diagnóstico de caça: observações por carnívoro/passo, sem alterar decisões.
        self.carnivore_hunt_history: list[dict[str, object]] = []
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
                    # O contador pode não existir para pares criados dinamicamente
                    # (ex.: agentes adicionados após a inicialização). Nunca indexar
                    # diretamente um defaultdict-like que na prática é um dict comum.
                    "cumulative_close_steps_for_pair": self.social_pair_encounters.get(pair, 0),
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

    def _enrich_resource_access_records(
        self, current_activity_records: dict[tuple[str, str], dict],
        carnivore_diagnostics_this_step: dict[int, dict[str, object]],
    ) -> None:
        """Acrescenta contexto de acesso a recursos aos registros já gerados.

        A instrumentação é observacional: não altera seleção de ação, navegação ou
        consumo. Distâncias são Manhattan; disponibilidade em campo de visão não
        implica que exista uma rota caminhável até o recurso.
        """
        water_positions = self.world.get_water_positions()
        mature_plant_positions = [
            (cell.x, cell.y)
            for row in self.world.grid for cell in row
            if isinstance(cell.resource, Plant) and cell.resource.state == PlantState.MATURE
        ]
        food_positions = mature_plant_positions + [
            (cell.x, cell.y)
            for row in self.world.grid for cell in row
            if isinstance(cell.resource, Food)
        ]
        prey_positions = (
            [(agent.x, agent.y) for agent in self.alive_agents]
            + [(animal.x, animal.y) for animal in self.alive_herbivores]
        )
        human_diagnostics = {
            agent.agent_id or f"H{id(agent)}": (
                self.diagnostic_history_by_agent[id(agent)][-1]
                if self.diagnostic_history_by_agent.get(id(agent)) else {}
            )
            for agent in self.agents
        }
        individuals = (
            [("HUMAN", agent.agent_id or f"H{id(agent)}", agent) for agent in self.agents]
            + [("HERBIVORE", f"V{index:03d}", animal) for index, animal in enumerate(self.herbivores, 1)]
            + [("CARNIVORE", f"C{index:03d}", animal) for index, animal in enumerate(self.carnivores, 1)]
        )

        def distance(a: tuple[int, int], b: tuple[int, int]) -> int:
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        def nearest_distance(position: tuple[int, int], candidates: list[tuple[int, int]]) -> int | str:
            return min((distance(position, candidate) for candidate in candidates), default="")

        for species, individual_id, individual in individuals:
            record = current_activity_records.get((species, individual_id))
            if record is None:
                continue
            position = (individual.x, individual.y)
            vision = int(getattr(individual, "vision_radius", 0))
            water_near = sum(distance(position, candidate) <= vision for candidate in water_positions)
            plants_near = sum(distance(position, candidate) <= vision for candidate in mature_plant_positions)
            food_near = sum(distance(position, candidate) <= vision for candidate in food_positions)
            prey_near = sum(distance(position, candidate) <= vision for candidate in prey_positions)

            target = getattr(individual, "target", None)
            target_position = None
            if species == "HERBIVORE" and record.get("resource_access_target_x_before_action") not in (None, ""):
                try:
                    target_position = (
                        int(record["resource_access_target_x_before_action"]),
                        int(record["resource_access_target_y_before_action"]),
                    )
                except (TypeError, ValueError):
                    target_position = None
            elif isinstance(target, (tuple, list)) and len(target) >= 2:
                try:
                    target_position = (int(target[0]), int(target[1]))
                except (TypeError, ValueError):
                    target_position = None
            target_distance = distance(position, target_position) if target_position else ""
            target_path = getattr(individual, "path", []) or []
            target_path_steps = max(0, len(target_path) - 1) if target_path else ""
            target_intent = str(getattr(individual, "target_intent", "") or record.get("behavior_intent", ""))
            target_kind = "NONE"
            captured_target_kind = str(record.get("resource_access_target_kind_before_action", "") or "").upper()
            if species == "HERBIVORE" and captured_target_kind in {"WATER", "FOOD", "OTHER", "NONE"}:
                target_kind = captured_target_kind
            elif target_position is not None:
                target_cell = self.world.get_cell(*target_position)
                if target_position in water_positions or target_intent == "SEEK_WATER":
                    target_kind = "WATER"
                elif target_position in food_positions or target_intent == "SEEK_FOOD":
                    target_kind = "FOOD"
                elif target_intent in {"HUNT", "HUNT_PREY"} or species == "CARNIVORE":
                    target_kind = "PREY"
                elif isinstance(target_cell.resource, (Plant, Food)):
                    target_kind = "FOOD"
                elif isinstance(target_cell.resource, MaterialResource):
                    target_kind = "MATERIAL"
                else:
                    target_kind = "OTHER"

            diagnostic = human_diagnostics.get(individual_id, {}) if species == "HUMAN" else {}
            drank_water = bool(diagnostic.get("drank_water", False)) if species == "HUMAN" else (
                float(record.get("thirst_before", individual.thirst) or 0)
                - float(record.get("thirst_after", individual.thirst) or 0) > 0.25
            )
            food_acquired = False
            if species == "HUMAN":
                food_consumed = float(diagnostic.get("food_consumed", 0) or 0) > 0
                food_acquired = (
                    bool(diagnostic.get("collected_food", False))
                    or float(diagnostic.get("collected_food_quantity", 0) or 0) > 0
                    or float(diagnostic.get("storage_food_withdrawn", 0) or 0) > 0
                )
            elif species == "HERBIVORE":
                food_consumed = float(record.get("hunger_before", individual.hunger) or 0) - float(record.get("hunger_after", individual.hunger) or 0) > 1.0
                food_acquired = food_consumed
            else:
                hunt_record = carnivore_diagnostics_this_step.get(id(individual), {})
                food_consumed = bool(hunt_record.get("prey_killed", False))
                food_acquired = food_consumed

            hunger = float(getattr(individual, "hunger", 0.0))
            thirst = float(getattr(individual, "thirst", 0.0))
            thirst_threshold = 35.0 if species == "CARNIVORE" else (45.0 if species == "HERBIVORE" else 25.0)
            hunger_threshold = 30.0 if species == "CARNIVORE" else (35.0 if species == "HERBIVORE" else 25.0)
            at_water = position in water_positions
            at_food = position in food_positions
            record.update({
                "resource_need_priority": "THIRST" if thirst >= thirst_threshold else ("HUNGER" if hunger >= hunger_threshold else "NONE"),
                "resource_need_priority_before_action": record.get(
                    "resource_need_priority_before_action",
                    "THIRST" if float(record.get("thirst_before", thirst) or 0) >= thirst_threshold else
                    "HUNGER" if float(record.get("hunger_before", hunger) or 0) >= hunger_threshold else "NONE",
                ),
                "nearest_water_distance_manhattan": nearest_distance(position, water_positions),
                "nearest_mature_plant_distance_manhattan": nearest_distance(position, mature_plant_positions),
                "nearest_food_distance_manhattan": nearest_distance(position, food_positions),
                "nearest_prey_distance_manhattan": nearest_distance(position, prey_positions) if species == "CARNIVORE" else "",
                "water_sources_in_vision": water_near,
                "mature_plants_in_vision": plants_near,
                "food_sources_in_vision": food_near,
                "prey_in_vision": prey_near if species == "CARNIVORE" else "",
                "selected_target_kind": target_kind,
                "selected_target_x": target_position[0] if target_position else "",
                "selected_target_y": target_position[1] if target_position else "",
                "selected_target_distance_manhattan": target_distance,
                "selected_target_path_steps": target_path_steps,
                "selected_target_path_available": bool(target_path) or (target_position == position) or (target_kind == "PREY" and target_distance != "" and target_distance <= 1),
                "at_water_source": at_water,
                "at_food_source": at_food,
                "water_consumption_succeeded": bool(drank_water),
                "food_acquisition_succeeded": bool(food_acquired),
                "food_consumption_succeeded": bool(food_consumed),
                "urgent_thirst_without_water_in_vision": thirst >= thirst_threshold and water_near == 0,
                "urgent_hunger_without_food_in_vision": hunger >= hunger_threshold and food_near == 0 and not (species == "CARNIVORE" and prey_near > 0),
            })
            if drank_water:
                record["resource_access_outcome"] = "DRANK_WATER"
            elif food_consumed:
                record["resource_access_outcome"] = "ATE_FOOD_OR_PREY"
            elif food_acquired:
                record["resource_access_outcome"] = "ACQUIRED_FOOD"
            elif thirst >= thirst_threshold and water_near == 0:
                record["resource_access_outcome"] = "HIGH_THIRST_NO_WATER_IN_VISION"
            elif hunger >= hunger_threshold and food_near == 0 and (species != "CARNIVORE" or prey_near == 0):
                record["resource_access_outcome"] = "HIGH_HUNGER_NO_FOOD_OR_PREY_IN_VISION"
            elif target_kind in {"WATER", "FOOD", "PREY"}:
                record["resource_access_outcome"] = f"TARGETING_{target_kind}"
            elif thirst >= thirst_threshold and not at_water:
                record["resource_access_outcome"] = "THIRST_PRIORITY_NO_SUCCESS"
            elif hunger >= hunger_threshold and not at_food:
                record["resource_access_outcome"] = "HUNGER_PRIORITY_NO_SUCCESS"
            else:
                record["resource_access_outcome"] = "NO_URGENT_RESOURCE_NEED"

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
        """Resolve intended moves and retain goals after transient occupancy blocks."""
        order = list(self.alive_agents)
        self.rng.shuffle(order)
        occupied = {(a.x, a.y): a for a in self.alive_agents}
        herbivore_positions = {(h.x, h.y) for h in self.alive_herbivores}
        carnivore_positions = {(c.x, c.y) for c in self.alive_carnivores}
        animal_positions = herbivore_positions | carnivore_positions
        moved_by_id: dict[int, bool] = {id(a): False for a in order}

        def record_block(agent: Agent, reason: str) -> None:
            metrics = self.metrics_by_agent[id(agent)]
            metrics.blocked_movement_attempts += 1
            self.blocked_movement_attempts += 1
            agent.last_movement_block_reason = reason
            if reason in {"AGENT", "ANIMAL"}:
                metrics.blocked_by_agent_attempts += 1
                self.blocked_by_agent_attempts += 1
            else:
                metrics.blocked_by_environment_attempts += 1
                self.blocked_by_environment_attempts += 1
            # Ocupação é transitória: preserva objetivo/rota para que a decisão
            # seguinte tente recalcular o caminho considerando os ocupantes atuais.
            # Obstáculos do mapa, por outro lado, invalidam a rota existente.
            if reason == "OBSTACLE":
                agent.target = None
                agent.path.clear()

        for agent in order:
            action = actions[id(agent)]
            if action == (0, 0):
                continue
            if action not in {(0, -1), (0, 1), (-1, 0), (1, 0)}:
                original_dx, original_dy = action
                # Ações de movimento são sempre vetores unitários. Se uma rota
                # persistente ficou dessincronizada após uma corrida, recupera
                # o próximo passo da rota; como fallback, reduz o vetor a um
                # passo ortogonal em direção ao destino.
                next_step = None
                if agent.path:
                    current_path_position = (agent.x, agent.y)
                    try:
                        index = agent.path.index(current_path_position)
                        if index + 1 < len(agent.path):
                            next_step = agent.path[index + 1]
                    except ValueError:
                        next_step = agent.path[0]
                if next_step is not None:
                    delta = (next_step[0] - agent.x, next_step[1] - agent.y)
                    if abs(delta[0]) + abs(delta[1]) == 1:
                        action = delta
                if action not in {(0, -1), (0, 1), (-1, 0), (1, 0)}:
                    action = ((0, 1) if original_dy > 0 else (0, -1) if original_dy < 0
                              else ((1, 0) if original_dx > 0 else (-1, 0)))
            metrics = self.metrics_by_agent[id(agent)]
            metrics.movement_attempts += 1
            dx, dy = action
            destination = (agent.x + dx, agent.y + dy)
            current = (agent.x, agent.y)
            occupied.pop(current, None)

            if destination in occupied:
                occupied[current] = agent
                record_block(agent, "AGENT")
                continue
            if destination in animal_positions:
                occupied[current] = agent
                record_block(agent, "ANIMAL")
                continue
            if not self.world.is_walkable(*destination):
                occupied[current] = agent
                record_block(agent, "OBSTACLE")
                continue

            moved = False
            block_reason = ""
            distance = agent.run_distance if agent.running and agent.energy >= self.physiology_config.stamina_run_cost else 1
            for _ in range(distance):
                move_action = action
                if agent.target_intent == "EXPLORATION" and agent.path:
                    current_path_position = (agent.x, agent.y)
                    try:
                        path_index = agent.path.index(current_path_position)
                        path_next = agent.path[path_index + 1] if path_index + 1 < len(agent.path) else None
                    except ValueError:
                        # choose_action remove o início da rota antes de devolver
                        # o primeiro vetor; nesse caso o próximo waypoint é path[0].
                        path_next = agent.path[0]
                    if path_next is not None:
                        path_delta = (path_next[0] - agent.x, path_next[1] - agent.y)
                        if abs(path_delta[0]) + abs(path_delta[1]) == 1:
                            move_action = path_delta
                next_position = (agent.x + move_action[0], agent.y + move_action[1])
                if next_position in occupied:
                    block_reason = "AGENT"
                    break
                if next_position in animal_positions:
                    block_reason = "ANIMAL"
                    break
                if not self.world.is_walkable(*next_position):
                    block_reason = "OBSTACLE"
                    break
                if not self.world.move_agent(agent, move_action):
                    block_reason = "OBSTACLE"
                    break
                moved = True

            if moved:
                occupied.pop(current, None)
                occupied[(agent.x, agent.y)] = agent
                moved_by_id[id(agent)] = True
            else:
                occupied[current] = agent
            if block_reason:
                record_block(agent, block_reason)

        return moved_by_id

    def _resolve_herbivore_movement(
        self,
        animal: Herbivore,
        action: tuple[int, int],
        occupied_agents: set[tuple[int, int]],
        occupied_animals: set[tuple[int, int]],
    ) -> bool:
        """Move um herbívoro e registra o primeiro bloqueio encontrado."""
        animal.last_movement_block_reason = ""
        if action == (0, 0):
            return False
        start = (animal.x, animal.y)
        max_distance = animal.run_distance if animal.running and animal.needs.energy >= self.physiology_config.stamina_run_cost else 1
        if animal.path and getattr(animal, "target", None) is not None and (not isinstance(animal, Herbivore) or animal.exploration_target is None):
            current_path_position = (animal.x, animal.y)
            if current_path_position in animal.path:
                remaining_steps = len(animal.path) - animal.path.index(current_path_position) - 1
            else:
                remaining_steps = len(animal.path)
            max_distance = min(max_distance, max(1, remaining_steps))
        moved = False
        for _ in range(max_distance):
            move_action = action
            if isinstance(animal, Herbivore) and getattr(animal, "exploration_target", None) is not None and animal.path:
                current_path_position = (animal.x, animal.y)
                try:
                    path_index = animal.path.index(current_path_position)
                except ValueError:
                    path_index = -1
                if 0 <= path_index < len(animal.path) - 1:
                    path_next = animal.path[path_index + 1]
                    move_action = (path_next[0] - animal.x, path_next[1] - animal.y)
            destination = (animal.x + move_action[0], animal.y + move_action[1])
            if destination in occupied_agents:
                animal.last_movement_block_reason = "AGENT"
                break
            if destination in occupied_animals and destination != (animal.x, animal.y):
                animal.last_movement_block_reason = "ANIMAL"
                break
            if not self.world.is_walkable(*destination):
                animal.last_movement_block_reason = "OBSTACLE"
                break
            if not self.world.move_agent(animal, move_action):
                animal.last_movement_block_reason = "OBSTACLE"
                break
            moved = True
        if moved:
            occupied_animals.discard(start)
            occupied_animals.add((animal.x, animal.y))
        return moved

    def _sleep_wake_reason(self, individual) -> str:
        """Retorna o motivo de interromper o sono por necessidade ou ameaça."""
        config = self.physiology_config

        if individual.hunger >= config.sleep_wake_hunger_threshold:
            return "HUNGER"

        # Humanos sem alimento armazenado precisam acordar para procurar comida.
        if (
            individual.hunger >= 35.0
            and getattr(individual, "inventory", None) is not None
            and individual.inventory.food_quantity < 1.0
        ):
            return "HUNGER"

        if individual.thirst >= min(
            40.0, config.sleep_wake_thirst_threshold
        ):
            return "THIRST"

        # Carnívoros famintos interrompem o sono quando detectam uma presa.
        if isinstance(individual, Carnivore) and individual.hunger >= 30.0:
            prey = self.alive_agents + self.alive_herbivores

            for target in prey:
                distance = (
                    abs(target.x - individual.x)
                    + abs(target.y - individual.y)
                )

                if distance <= individual.vision_radius:
                    return "PREY_NEARBY"

        # Ameaças próximas interrompem o sono.
        radius = config.sleep_wake_predator_radius

        for predator in self.alive_carnivores:
            if predator is individual:
                continue

            distance = (
                abs(predator.x - individual.x)
                + abs(predator.y - individual.y)
            )

            if distance <= radius:
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

        carnivore_diagnostics_this_step: dict[int, dict[str, object]] = {}
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
            agent.last_movement_block_reason = ""
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
            # A busca por parceiro é uma prioridade exploratória: não substitui
            # caça, água ou alimento quando a necessidade já é relevante.
            if ("choose_action" not in agent.__dict__ and not agent.is_sleeping
                    and agent.hunger < 30.0 and agent.thirst < 30.0
                    and agent.needs.fatigue < 75.0 and agent.energy > 35.0
                    and agent.target_intent not in {"SEEK_FOOD", "SEEK_WATER", "HUNT"}):
                occupied = ({(item.x, item.y) for item in self.alive_agents}
                            | {(item.x, item.y) for item in self.alive_herbivores}
                            | {(item.x, item.y) for item in self.alive_carnivores})
                mate_action = self.reproduction.seek_action(agent, self.alive_agents, self.world, occupied)
                if mate_action is not None:
                    actions[id(agent)] = mate_action
                    agent.last_behavior_intent = "SEEK_MATE"
            if agent.target is not None:
                target_distance = abs(agent.target[0] - agent.x) + abs(agent.target[1] - agent.y)
            else:
                target_distance = 0
            urgent_target = (
                (agent.target_intent == "SEEK_WATER" and agent.thirst >= 55.0)
                or (agent.target_intent == "SEEK_FOOD" and agent.hunger >= 60.0)
            )
            exploring_with_stamina = (
                agent.target_intent == "EXPLORATION"
                and agent.target is not None
                and target_distance >= 3
                and agent.energy >= max(45.0, self.physiology_config.stamina_run_minimum)
                and agent.needs.fatigue < 60.0
            )
            # Caçar não é, por si só, uma emergência fisiológica: corrida de caça
            # respeita a reserva normal. Só necessidades críticas liberam a reserva.
            urgent_for_stamina = (
                (agent.target_intent == "SEEK_WATER" and agent.thirst >= 90.0)
                or (agent.target_intent == "SEEK_FOOD" and agent.hunger >= 90.0)
                or agent.hunger >= 95.0 or agent.thirst >= 95.0
            )
            wants_to_run = (
                (agent.target_intent in {"HUNT", "SEEK_FOOD", "SEEK_WATER"} and target_distance >= 3)
                or exploring_with_stamina
            )
            if not agent.is_sleeping and agent.energy >= self.physiology_config.stamina_run_minimum:
                agent.running = bool(wants_to_run and should_run(
                    energy=agent.energy, max_energy=agent.max_energy,
                    fatigue=agent.needs.fatigue, urgent=urgent_for_stamina,
                    currently_running=agent.last_activity == "RUNNING",
                    config=self.physiology_config,
                ))
            else:
                agent.running = False
            expected_effort = (
                self.physiology_config.stamina_run_cost
                if wants_to_run and target_distance >= 2 else 0.0
            )
            if should_rest_for_stamina(
                energy=agent.energy, max_energy=agent.max_energy,
                urgent=urgent_for_stamina, currently_resting=agent.last_activity == "RESTING",
                config=self.physiology_config, expected_effort=expected_effort,
            ) and not agent.is_sleeping:
                actions[id(agent)] = (0, 0)
                agent._rest_selected = True
                agent._waiting_selected = False
                agent.running = False

        # Snapshot do alvo antes do movimento para medir progresso sem inferir o
        # alvo a partir do estado posterior à interação.
        target_snapshots = {
            id(agent): (agent.target, agent.target_intent) for agent in alive_at_start
        }

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
                agent.rest(recovery_amount(rest_amount, agent.energy, agent.max_energy, self.physiology_config))
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
            hunger_extra = adjusted_hunger_rate(hunger_extra, agent.species, agent.attributes)
            if activity == "WAITING":
                energy_before_wait_recovery = agent.energy
                agent.needs.restore_energy(recovery_amount(
                    activity_config.stamina_wait_recovery, agent.energy, agent.max_energy, activity_config
                ))
                rest_energy_recovered = agent.energy - energy_before_wait_recovery
            elif activity == "SLEEPING":
                energy_before_sleep_recovery = agent.energy
                agent.needs.restore_energy(recovery_amount(
                    activity_config.stamina_sleep_recovery, agent.energy, agent.max_energy, activity_config
                ))
                rest_energy_recovered = agent.energy - energy_before_sleep_recovery
            health_before_needs = agent.health
            agent.needs.advance_step(
                hunger_extra=hunger_extra, thirst_extra=thirst_extra, fatigue_delta=fatigue_delta
            )
            health_recovered_this_step, health_recovery_block_reason = recover_health_during_rest(
                agent.needs, activity, 0.25 + 0.5 * agent.attributes.constitution
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
                "movement_block_reason": agent.last_movement_block_reason,
                "distance": displacement,
                "health_before": physiology_before[key]["health"],
                "health_after_physiology": health_after_physiology,
                "health_recovered_this_step": health_recovered_this_step,
                "health_recovery_source": activity if health_recovered_this_step > 0 else "NONE",
                "health_recovery_block_reason": health_recovery_block_reason,
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
                "action_reason": agent.last_behavior_intent or activity,
                "decision_action_id": (agent.last_decision_trace or {}).get("action_id", ""),
                "decision_score": (agent.last_decision_trace or {}).get("score", ""),
                "moved": bool(moved), "distance": float(displacement),
                "movement_block_reason": agent.last_movement_block_reason,
                **_target_progress_fields(
                    target_snapshots.get(key, (None, "NONE"))[0],
                    target_snapshots.get(key, (None, "NONE"))[1],
                    before[key], after_move,
                    need_satisfied=bool(
                        (target_snapshots.get(key, (None, "NONE"))[1] == "SEEK_WATER" and drank_water)
                        or (target_snapshots.get(key, (None, "NONE"))[1] == "SEEK_FOOD" and consumed_food > 0)
                        or (target_snapshots.get(key, (None, "NONE"))[1] == "HUNT" and consumed_food > 0)
                    ),
                ),
                "stamina_before": energy_before[key], "stamina_after": agent.energy,
                "stamina_spent_movement": movement_energy_cost,
                "stamina_recovered_rest": rest_energy_recovered,
                "stamina_recovered": rest_energy_recovered,
                "stamina_recovery_source": activity if activity in {"WAITING", "RESTING", "SLEEPING"} else "NONE",
                "decision_trace": agent.last_decision_trace or {},
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
                    "behavior_intent": "KILLED_BY_HUNTING", "action_reason": "KILLED_BY_HUNTING", "decision_action_id": "", "decision_score": "",
                    "moved": False, "distance": 0.0,
                    "stamina_before": prey.needs.energy, "stamina_after": prey.needs.energy,
                    "stamina_spent_movement": 0.0, "stamina_recovered_rest": 0.0,
                    "stamina_recovered": 0.0, "stamina_recovery_source": "NONE", "decision_trace": {},
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
        # Herbívoros devem planejar contra todas as entidades animais ocupantes,
        # incluindo carnívoros; posições são atualizadas conforme cada herbívoro se move.
        occupied_animals = (
            {(h.x, h.y) for h in self.alive_herbivores}
            | {(c.x, c.y) for c in self.alive_carnivores}
        )
        for animal in list(self.alive_herbivores):
            animal._sleep_interruption_event = ""
            animal.last_movement_block_reason = ""
            animal.last_navigation_block_reason = ""
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
                  and animal.hunger < self.physiology_config.sleep_wake_hunger_threshold
                  and animal.thirst < self.physiology_config.sleep_wake_thirst_threshold
                  and not nearby_threats):
                animal.is_sleeping = True
                animal.last_sleep_interruption_reason = ""
                action = (0, 0)
                activity = "SLEEPING"
            elif (should_rest_for_stamina(
                    energy=animal.needs.energy, max_energy=animal.needs.max_energy,
                    urgent=(bool(getattr(animal, "fleeing", False)) or animal.hunger >= 95.0 or animal.thirst >= 95.0),
                    currently_resting=animal.last_activity == "RESTING",
                    config=self.physiology_config,
                    expected_effort=(self.physiology_config.stamina_run_cost
                        if (getattr(animal, "exploration_target", None) is not None
                            or getattr(animal, "target", None) is not None) else 0.0),
                  ) and animal.hunger < 95.0 and animal.thirst < 95.0 and not nearby_threats):
                animal.running = False
                action = (0, 0)
                activity = "RESTING"
            else:
                other_animals = occupied_animals - {(animal.x, animal.y)}
                # Compatibilidade com testes/extensões que substituem choose_action
                # por uma função de dois argumentos na instância.
                if "choose_action" in animal.__dict__:
                    action = animal.choose_action(self.world, threat_positions)
                else:
                    action = animal.choose_action(
                        self.world,
                        threat_positions,
                        occupied_positions=occupied_agents | other_animals,
                        occupied_agent_positions=occupied_agents,
                        occupied_animal_positions=other_animals,
                    )
                if ("choose_action" not in animal.__dict__ and isinstance(animal, Herbivore) and not animal.fleeing
                        and animal.hunger < 30.0 and animal.thirst < 30.0
                        and animal.needs.fatigue < 75.0 and animal.energy > 35.0):
                    occupied = ({(item.x, item.y) for item in self.alive_agents}
                                | {(item.x, item.y) for item in self.alive_herbivores}
                                | {(item.x, item.y) for item in self.alive_carnivores})
                    mate_action = self.reproduction.seek_action(animal, self.alive_herbivores, self.world, occupied)
                    if mate_action is not None:
                        action = mate_action
                        animal.last_behavior_intent = "SEEK_MATE"
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
                exploring_with_stamina = (
                    isinstance(animal, Herbivore)
                    and getattr(animal, "exploration_target", None) is not None
                    and animal.needs.energy >= max(40.0, self.physiology_config.stamina_run_minimum)
                    and animal.needs.fatigue < 60.0
                )
                wants_to_run = bool((urgent and (animal.fleeing if isinstance(animal, Herbivore) else target_distance >= 2))
                    or exploring_with_stamina)
                urgent_for_stamina = bool(
                    (isinstance(animal, Herbivore) and animal.fleeing)
                    or animal.hunger >= 95.0 or animal.thirst >= 95.0
                )
                animal.running = bool(wants_to_run and should_run(
                    energy=animal.needs.energy, max_energy=animal.needs.max_energy,
                    fatigue=animal.needs.fatigue, urgent=urgent_for_stamina,
                    currently_running=animal.last_activity == "RUNNING",
                    config=self.physiology_config,
                ))
                if animal.running and action != (0, 0):
                    activity = "RUNNING"
            # Captura o alvo escolhido antes do movimento/consumo. A planta pode ser
            # removida no mesmo passo em que o herbívoro a come; inferir o alvo só
            # depois da ação perde justamente o evento de sucesso.
            resource_target = getattr(animal, "target", None)
            resource_target_intent = "SEEK_RESOURCE"
            resource_target_kind = "NONE"
            resource_target_x = ""
            resource_target_y = ""
            if isinstance(resource_target, (tuple, list)) and len(resource_target) >= 2:
                try:
                    resource_target_x, resource_target_y = int(resource_target[0]), int(resource_target[1])
                    target_resource = self.world.get_cell(resource_target_x, resource_target_y).resource
                    if isinstance(target_resource, Water):
                        resource_target_kind = "WATER"
                        resource_target_intent = "SEEK_WATER"
                    elif isinstance(target_resource, Food) or (
                        isinstance(target_resource, Plant) and target_resource.state == PlantState.MATURE
                    ):
                        resource_target_kind = "FOOD"
                        resource_target_intent = "SEEK_FOOD"
                    else:
                        resource_target_kind = "OTHER"
                except (TypeError, ValueError, IndexError):
                    resource_target_x, resource_target_y = "", ""
                    resource_target_kind = "NONE"
            resource_need_before_action = (
                "THIRST" if before_state["thirst"] >= 45.0 else
                "HUNGER" if before_state["hunger"] >= 35.0 else "NONE"
            )
            before_move = (animal.x, animal.y)
            if action != (0, 0):
                moved = self._resolve_herbivore_movement(
                    animal, action, occupied_agents, occupied_animals
                )
                if not moved:
                    activity = "WAITING"
                    animal.running = False
            animal.last_activity = activity

            resource = self.world.get_cell(animal.x, animal.y).resource
            need_satisfied_this_step = False
            collected_plant = None
            if activity != "SLEEPING":
                if isinstance(resource, Water) and animal.thirst > 0:
                    thirst_before = animal.thirst
                    animal.drink(resource.drink_amount)
                    need_satisfied_this_step = animal.thirst < thirst_before
                    self._record_water_event("herbivores", thirst_before, animal.thirst)
                elif isinstance(resource, Plant) and resource.state == PlantState.MATURE and animal.hunger >= 20:
                    collected_plant = self.world.collect_resource(animal.x, animal.y)
                    if collected_plant is not None:
                        self._record_collection_event(collected_plant, "herbivore")
                        animal.eat(35.0)
                        need_satisfied_this_step = True
            stamina_before_recovery = animal.needs.energy
            if activity == "RUNNING" and (animal.x, animal.y) != before_move:
                animal.needs.energy = max(0.0, animal.needs.energy - self.physiology_config.stamina_run_cost)
            elif (animal.x, animal.y) != before_move:
                animal.needs.energy = max(0.0, animal.needs.energy - ENERGY_PER_STEP * (abs(animal.x-before_move[0])+abs(animal.y-before_move[1])))
            elif activity == "RESTING":
                animal.needs.restore_energy(recovery_amount(self.physiology_config.stamina_rest_recovery, animal.needs.energy, animal.needs.max_energy, self.physiology_config))
            elif activity == "WAITING":
                animal.needs.restore_energy(recovery_amount(self.physiology_config.stamina_wait_recovery, animal.needs.energy, animal.needs.max_energy, self.physiology_config))
            elif activity == "SLEEPING":
                animal.needs.restore_energy(recovery_amount(self.physiology_config.stamina_sleep_recovery, animal.needs.energy, animal.needs.max_energy, self.physiology_config))
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
            hunger_extra = adjusted_hunger_rate(hunger_extra, animal.species, animal.attributes)
            animal.needs.advance_step(hunger_extra=hunger_extra, thirst_extra=thirst_extra, fatigue_delta=fatigue_delta)
            health_recovered_this_step, health_recovery_block_reason = recover_health_during_rest(
                animal.needs, activity, 0.25 + 0.5 * animal.attributes.constitution
            )
            if activity == "SLEEPING" and animal.needs.fatigue <= self.physiology_config.sleep_end_threshold:
                animal.is_sleeping = False
            animal.alive = animal.needs.alive
            self.physiology_activity_history.append({
                "step": self.steps + 1, "simulated_minute": self.simulated_minutes + 1,
                "individual_type": "HERBIVORE", "individual_id": f"V{self.herbivores.index(animal)+1:03d}",
                "x": animal.x, "y": animal.y, "activity": activity,
                "resource_access_target_kind_before_action": resource_target_kind,
                "resource_access_target_x_before_action": resource_target_x,
                "resource_access_target_y_before_action": resource_target_y,
                "resource_need_priority_before_action": resource_need_before_action,
                "behavior_intent": "FLEE" if animal.fleeing else ("SEEK_RESOURCE" if animal.target else activity),
                "action_reason": (
                    "SLEEPING" if activity == "SLEEPING" else
                    "AT_WATER" if isinstance(self.world.get_cell(animal.x, animal.y).resource, Water) and animal.thirst > 0 else
                    "LOW_STAMINA" if activity == "RESTING" else
                    "AT_TARGET" if animal.target is not None and abs(animal.target[0]-animal.x)+abs(animal.target[1]-animal.y) <= 1 else
                    "MOVING_TO_TARGET" if animal.target is not None else
                    "FLEEING" if animal.fleeing else
                    "EXPLORING" if activity in {"WALKING", "RUNNING"} else "NO_ACTION"
                ),
                "moved": (animal.x, animal.y) != before_pos,
                "distance": float(abs(animal.x-before_pos[0])+abs(animal.y-before_pos[1])),
                **_target_progress_fields(
                    resource_target, resource_target_intent, before_pos, (animal.x, animal.y),
                    need_satisfied=bool(
                        (resource_target_intent == "SEEK_WATER" and need_satisfied_this_step and isinstance(resource, Water))
                        or (resource_target_intent == "SEEK_FOOD" and need_satisfied_this_step and collected_plant is not None)
                    ),
                ),
                "movement_block_reason": animal.last_movement_block_reason,
                "navigation_block_reason": animal.last_navigation_block_reason,
                "navigation_plan_status": animal.last_navigation_plan_status,
                "navigation_plan_reason": animal.last_navigation_plan_reason,
                "navigation_plan_path_found_attempts": animal.navigation_plan_status_counts.get("PATH_FOUND", 0),
                "navigation_plan_already_at_goal_attempts": animal.navigation_plan_status_counts.get("ALREADY_AT_GOAL", 0),
                "navigation_plan_temporarily_blocked_attempts": animal.navigation_plan_status_counts.get("TEMPORARILY_BLOCKED", 0),
                "navigation_plan_invalid_start_attempts": animal.navigation_plan_status_counts.get("INVALID_START", 0),
                "navigation_plan_invalid_goal_attempts": animal.navigation_plan_status_counts.get("INVALID_GOAL", 0),
                "navigation_plan_unreachable_attempts": animal.navigation_plan_status_counts.get("UNREACHABLE", 0),
                "stamina_before": before_state["stamina"], "stamina_after": animal.needs.energy,
                "stamina_spent_movement": ((self.physiology_config.stamina_run_cost if activity == "RUNNING" else ENERGY_PER_STEP * abs(animal.x-before_pos[0])+ENERGY_PER_STEP * abs(animal.y-before_pos[1])) if activity in {"WALKING", "RUNNING"} else 0.0),
                "stamina_recovered_rest": stamina_recovered_activity,
                "stamina_recovered": stamina_recovered_activity,
                "stamina_recovery_source": activity if activity in {"WAITING", "RESTING", "SLEEPING"} else "NONE",
                "decision_trace": {},
                "stamina_spent_combat": 0.0,
                "hunger_metabolic_cost": animal.needs.hunger_per_step + hunger_extra,
                "thirst_metabolic_cost": animal.needs.thirst_per_step + thirst_extra,
                "fatigue_delta": fatigue_delta,
                "fatigue_before": before_state["fatigue"], "fatigue_after": animal.needs.fatigue,
                "hunger_before": before_state["hunger"], "hunger_after": animal.hunger,
                "thirst_before": before_state["thirst"], "thirst_after": animal.thirst,
                "health_before": before_state["health"], "health_after": animal.health,
                "health_recovered_this_step": health_recovered_this_step,
                "health_recovery_source": activity if health_recovered_this_step > 0 else "NONE",
                "health_recovery_block_reason": health_recovery_block_reason,
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
            carnivore_target_before_action = getattr(carnivore, "target", None)
            if carnivore_target_before_action is None:
                # A patrulha usa exploration_target, enquanto target fica None.
                # Capturamos o objetivo persistente para medir exploração real.
                carnivore_target_before_action = getattr(carnivore, "exploration_target", None)
                carnivore_target_intent_before_action = "EXPLORATION"
            else:
                target_resource = self.world.get_cell(*carnivore_target_before_action).resource
                carnivore_target_intent_before_action = (
                    "SEEK_WATER" if isinstance(target_resource, Water) else "HUNT"
                )
            before_state = {
                "health": carnivore.health, "hunger": carnivore.hunger,
                "thirst": carnivore.thirst, "stamina": carnivore.needs.energy,
                "fatigue": carnivore.needs.fatigue,
            }
            test_target = getattr(carnivore, "test_target_agent", None)
            if test_target is not None and test_target.alive:
                prey_positions = [(test_target.x, test_target.y)]
                available_humans = [test_target] if isinstance(test_target, Agent) else []
                available_herbivores = []
            else:
                available_humans = list(self.alive_agents)
                available_herbivores = list(self.alive_herbivores)
                prey_positions = ([(a.x, a.y) for a in available_humans]
                                  + [(h.x, h.y) for h in available_herbivores])
            def nearest_distance(individuals):
                return min((abs(item.x-carnivore.x) + abs(item.y-carnivore.y) for item in individuals), default=None)
            visible_humans = [item for item in available_humans
                              if abs(item.x-carnivore.x) + abs(item.y-carnivore.y) <= carnivore.vision_radius]
            visible_herbivores = [item for item in available_herbivores
                                  if abs(item.x-carnivore.x) + abs(item.y-carnivore.y) <= carnivore.vision_radius]
            # Preserva a identidade da presa entre passos. Só abandona o alvo se
            # ele morreu, saiu do campo de visão ou deixou de ser uma opção válida.
            previous_prey = next((item for item in available_humans + available_herbivores
                                   if id(item) == carnivore.hunt_target_object_id and item.alive
                                   and abs(item.x-carnivore.x) + abs(item.y-carnivore.y) <= carnivore.vision_radius), None)
            # A escolha de presa considera risco de defesa coletiva, não apenas distância.
            # Se não houver alvo seguro, o carnívoro pode explorar em vez de iniciar
            # uma aproximação que provavelmente terminará em confronto desfavorável.
            selected_prey = None
            selected_prey_score = None
            selected_prey_nearby_humans = 0
            target_selection_reason = "NO_HUNT_NEED"
            if carnivore.hunger >= 30.0 and carnivore.thirst < 50.0:
                selected_prey, selected_prey_score, selected_prey_nearby_humans, target_selection_reason = select_prey_candidate(
                    carnivore, visible_humans, visible_herbivores, available_humans,
                    current_target=previous_prey, hunger=carnivore.hunger,
                )
            previous_prey = selected_prey
            carnivore.preferred_hunt_target = (selected_prey.x, selected_prey.y) if selected_prey else None
            carnivore.hunt_target_object_id = id(selected_prey) if selected_prey else None
            decision_prey_positions = [(selected_prey.x, selected_prey.y)] if selected_prey else []
            water_positions = self.world.get_water_positions()
            water_distance_before = min((abs(x-carnivore.x)+abs(y-carnivore.y) for x, y in water_positions), default=None)
            hunt_record = {
                "step": self.steps + 1,
                "simulated_minute": self.simulated_minutes + 1,
                "individual_type": "CARNIVORE",
                "individual_id": self._carnivore_ids.setdefault(
                    id(carnivore), f"C{len(self._carnivore_ids) + 1:03d}"
                ),
                "x_before": carnivore.x, "y_before": carnivore.y,
                "health_before": carnivore.health, "hunger_before": carnivore.hunger,
                "thirst_before": carnivore.thirst, "stamina_before": carnivore.needs.energy,
                "fatigue_before": carnivore.needs.fatigue,
                "hunger_threshold_for_hunt": 30.0,
                "prey_count_total": len(available_humans) + len(available_herbivores),
                "prey_count_humans": len(available_humans),
                "prey_count_herbivores": len(available_herbivores),
                "visible_humans": len(visible_humans),
                "visible_herbivores": len(visible_herbivores),
                "nearest_human_distance": nearest_distance(available_humans),
                "nearest_herbivore_distance": nearest_distance(available_herbivores),
                "nearest_prey_distance": min((d for d in (nearest_distance(available_humans), nearest_distance(available_herbivores)) if d is not None), default=None),
                "nearest_water_distance": water_distance_before,
                "selected_target_x": "", "selected_target_y": "", "selected_target_distance_before_move": "",
                "selected_prey_type": "", "selected_prey_id": "",
                "selected_prey_risk_score": selected_prey_score if selected_prey_score is not None else "",
                "selected_prey_nearby_humans": selected_prey_nearby_humans,
                "target_selection_reason": target_selection_reason,
                "personality_risk_aversion": float(getattr(carnivore.personality, "risk_aversion", 0.5)),
                "personality_aggressiveness": float(getattr(carnivore.personality, "aggressiveness", 0.5)),
                "personality_persistence": float(getattr(carnivore.personality, "persistence", 0.5)),
                "health_fraction_before_action": carnivore.health / carnivore.needs.max_health,
                "human_threat_count_within_2": 0,
                "human_threat_count_adjacent": 0,
                "retreat_decision": False,
                "retreat_reason": "NOT_EVALUATED",
                "retreat_attempted": False,
                # retreat_success é preenchido pela auditoria após observar a
                # janela futura; o movimento imediato é registrado separadamente.
                "retreat_success": False,
                "retreat_outcome": "NOT_ATTEMPTED",
                "retreat_followup_steps": 0,
                "retreat_failure_reason": "",
                "retreat_immediate_distance_increased": False,
                "retreat_min_human_distance_before": "",
                "retreat_min_human_distance_after": "",
                "health_recovery_eligible": False,
                "health_recovered_this_step": 0.0,
                "health_recovery_source": "NONE",
                "health_recovery_block_reason": "NOT_EVALUATED",
                "selected_prey_x_before_action": "", "selected_prey_y_before_action": "",
                "selected_prey_distance_before_action": "", "selected_prey_distance_after_move": "",
                "selected_prey_distance_progress": "",
                "x_after_move": carnivore.x, "y_after_move": carnivore.y,
                "activity": "", "distance_moved": 0,
                "adjacent_prey_count": 0, "attack_skipped_reason": "NOT_EVALUATED",
                "attack_attempted": False, "attack_target_type": "", "attack_target_id": "",
                "attack_damage": 0.0, "prey_killed": False,
                "hunger_before_eating": "", "hunger_after_eating": "", "hunger_reduction_from_meat": 0.0,
                "defense_attacks_received": 0, "damage_received_from_defense": 0.0,
                "nearby_human_defenders": 0, "attack_risk_score": "",
                "attack_nearby_humans": 0, "attack_selection_reason": "NOT_EVALUATED",
                "health_after": carnivore.health, "hunger_after": carnivore.hunger,
                "thirst_after": carnivore.thirst, "stamina_after": carnivore.needs.energy,
                "damage_causes": "", "termination_cause": "RUNNING",
            }
            if previous_prey is not None:
                hunt_record["selected_prey_type"] = "HUMAN" if isinstance(previous_prey, Agent) else "HERBIVORE"
                hunt_record["selected_prey_id"] = (previous_prey.agent_id if isinstance(previous_prey, Agent)
                    else self._herbivore_ids.setdefault(id(previous_prey), f"V{len(self._herbivore_ids) + 1:03d}"))
            carnivore_diagnostics_this_step[id(carnivore)] = hunt_record
            nearby_threats = []  # carnívoros não tratam presas como ameaça durante o sono
            wake_reason = self._sleep_wake_reason(carnivore) if carnivore.is_sleeping else ""
            if wake_reason:
                carnivore.is_sleeping = False
                carnivore.last_sleep_interruption_reason = wake_reason
                carnivore._sleep_interruption_event = wake_reason
            if carnivore.is_sleeping:
                action = (0, 0); activity = "SLEEPING"
            elif (carnivore.needs.fatigue >= self.physiology_config.sleep_start_threshold
                  and carnivore.hunger < self.physiology_config.sleep_wake_hunger_threshold
                  and carnivore.thirst < self.physiology_config.sleep_wake_thirst_threshold
                  and not any(
                            abs(px - carnivore.x) + abs(py - carnivore.y)
                            <= carnivore.vision_radius
                            for px, py in prey_positions
                        )):
                carnivore.is_sleeping = True
                carnivore.last_sleep_interruption_reason = ""
                action = (0, 0); activity = "SLEEPING"
            elif (carnivore.hunger >= 30.0 and carnivore.thirst < 50.0
                  and any(abs(px - carnivore.x) + abs(py - carnivore.y) <= carnivore.vision_radius
                          for px, py in prey_positions)
                  and (carnivore.needs.energy < self.physiology_config.stamina_attack_cost
                       or not any(abs(px - carnivore.x) + abs(py - carnivore.y) <= 1
                                  for px, py in prey_positions))
                  and should_rest_for_stamina(
                      energy=carnivore.needs.energy, max_energy=carnivore.needs.max_energy,
                      urgent=False, currently_resting=carnivore.last_activity == "RESTING",
                      config=self.physiology_config,
                      expected_effort=self.physiology_config.stamina_run_cost * min(carnivore.run_distance, 4) / 4.0,
                  )):
                # Recupera antes da perseguição, mantendo reserva para o ataque.
                carnivore.running = False
                action = (0, 0); activity = "RESTING"
            elif (should_rest_for_stamina(
                    energy=carnivore.needs.energy, max_energy=carnivore.needs.max_energy,
                    urgent=(carnivore.thirst >= 95.0),
                    currently_resting=carnivore.last_activity == "RESTING",
                    config=self.physiology_config,
                    expected_effort=self.physiology_config.stamina_run_cost * min(carnivore.run_distance, 4) / 4.0,
                  ) and carnivore.thirst < 95.0
                  and not any(abs(px - carnivore.x) + abs(py - carnivore.y) <= 1 for px, py in prey_positions)):
                carnivore.running = False
                action = (0, 0); activity = "RESTING"
            else:
                action = carnivore.choose_action(self.world, decision_prey_positions)
                hunt_record["hunt_stagnation_steps"] = getattr(carnivore, "hunt_stagnation_steps", 0)
                hunt_record["hunt_target_switches"] = getattr(carnivore, "hunt_target_switches", 0)
                hunt_record["hunt_position_history_size"] = len(getattr(carnivore, "_hunt_position_history", ()))
                hunt_record["hunt_target_x"] = carnivore.target[0] if carnivore.target else ""
                hunt_record["hunt_target_y"] = carnivore.target[1] if carnivore.target else ""
                if ("choose_action" not in carnivore.__dict__ and carnivore.hunger < 25.0 and carnivore.thirst < 35.0
                        and carnivore.needs.fatigue < 75.0 and carnivore.energy > 35.0
                        and not visible_humans and not visible_herbivores):
                    occupied = ({(item.x, item.y) for item in self.alive_agents}
                                | {(item.x, item.y) for item in self.alive_herbivores}
                                | {(item.x, item.y) for item in self.alive_carnivores})
                    mate_action = self.reproduction.seek_action(carnivore, self.alive_carnivores, self.world, occupied)
                    if mate_action is not None:
                        action = mate_action
                        carnivore.last_behavior_intent = "SEEK_MATE"
                activity = "WAITING" if action == (0, 0) else "WALKING"
                target = getattr(carnivore, "target", None)
                # Resolve o alvo espacial para uma presa concreta antes de mover.
                if target is not None and carnivore.hunger >= 30 and carnivore.thirst < 50:
                    matching_prey = next((item for item in available_humans + available_herbivores
                                          if (item.x, item.y) == target), None)
                    if matching_prey is not None:
                        carnivore.hunt_target_object_id = id(matching_prey)
                        is_human = isinstance(matching_prey, Agent)
                        prey_id = (matching_prey.agent_id if is_human else
                                   self._herbivore_ids.setdefault(id(matching_prey), f"V{len(self._herbivore_ids) + 1:03d}"))
                        hunt_record.update({
                            "selected_prey_type": "HUMAN" if is_human else "HERBIVORE",
                            "selected_prey_id": prey_id,
                            "selected_prey_x_before_action": matching_prey.x,
                            "selected_prey_y_before_action": matching_prey.y,
                            "selected_prey_distance_before_action": abs(matching_prey.x-before_pos[0]) + abs(matching_prey.y-before_pos[1]),
                            "_selected_prey_object_id": id(matching_prey),
                        })
                target_distance = (abs(target[0]-carnivore.x)+abs(target[1]-carnivore.y)) if target else 0
                patrol_distance = (
                    abs(carnivore.exploration_target[0] - carnivore.x)
                    + abs(carnivore.exploration_target[1] - carnivore.y)
                    if target is None and getattr(carnivore, "exploration_target", None) is not None else 0
                )
                urgent = (carnivore.hunger >= 30 and target_distance >= 2) or (carnivore.thirst >= 55 and target_distance >= 2)
                exploring_with_stamina = (
                    target is None and patrol_distance >= 3
                    and carnivore.needs.energy >= max(40.0, self.physiology_config.stamina_run_minimum)
                    and carnivore.needs.fatigue < 60.0
                )
                wants_to_run = bool((urgent and target_distance >= 2) or exploring_with_stamina)
                urgent_for_stamina = carnivore.hunger >= 95.0 or carnivore.thirst >= 95.0
                carnivore.running = bool(wants_to_run and should_run(
                    energy=carnivore.needs.energy, max_energy=carnivore.needs.max_energy,
                    fatigue=carnivore.needs.fatigue, urgent=urgent_for_stamina,
                    currently_running=carnivore.last_activity == "RUNNING",
                    config=self.physiology_config,
                ))
                if carnivore.running and action != (0,0): activity = "RUNNING"
            # Se já está ao alcance de um grupo humano, recua quando a fome não é
            # crítica ou a saúde está baixa. Isso evita receber vários golpes antes
            # de conseguir atacar no mesmo tick (a defesa humana ocorre primeiro).
            nearby_humans_for_risk = [human for human in available_humans if human.alive
                and abs(human.x-carnivore.x) + abs(human.y-carnivore.y) <= 2]
            adjacent_humans_for_risk = [human for human in nearby_humans_for_risk
                if abs(human.x-carnivore.x) + abs(human.y-carnivore.y) <= 1]
            adjacent_herbivores_for_risk = [herb for herb in self.alive_herbivores
                if abs(herb.x-carnivore.x) + abs(herb.y-carnivore.y) <= 1]
            risk_aversion = float(getattr(carnivore.personality, "risk_aversion", 0.5))
            aggressiveness = float(getattr(carnivore.personality, "aggressiveness", 0.5))
            persistence = float(getattr(carnivore.personality, "persistence", 0.5))
            retreat_decision = evaluate_human_threat(
                health=carnivore.health,
                max_health=carnivore.needs.max_health,
                hunger=carnivore.hunger,
                risk_aversion=risk_aversion,
                aggressiveness=aggressiveness,
                persistence=persistence,
                nearby_human_count=len(nearby_humans_for_risk),
                adjacent_human_count=len(adjacent_humans_for_risk),
                adjacent_herbivore_count=len(adjacent_herbivores_for_risk),
            )
            hunt_record.update({
                "human_threat_count_within_2": retreat_decision.nearby_human_count,
                "human_threat_count_adjacent": retreat_decision.adjacent_human_count,
                "retreat_decision": retreat_decision.should_retreat,
                "retreat_reason": retreat_decision.reason,
                "health_fraction_before_action": retreat_decision.health_fraction,
            })
            should_flee_human_group = retreat_decision.should_retreat
            if should_flee_human_group:
                hunt_record["retreat_min_human_distance_before"] = min(
                    (abs(human.x-carnivore.x) + abs(human.y-carnivore.y)
                     for human in nearby_humans_for_risk), default=""
                )
                occupied_for_escape = ({(a.x, a.y) for a in self.alive_agents}
                    | {(h.x, h.y) for h in self.alive_herbivores}
                    | {(c.x, c.y) for c in self.alive_carnivores if c is not carnivore})
                escape_options = []
                for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                    nx, ny = carnivore.x + dx, carnivore.y + dy
                    if (nx, ny) in occupied_for_escape or not self.world.is_walkable(nx, ny):
                        continue
                    distances = [abs(nx-human.x) + abs(ny-human.y) for human in nearby_humans_for_risk]
                    escape_options.append((min(distances), sum(distances), -ny, -nx, (dx, dy)))
                if escape_options:
                    escape_options.sort(reverse=True)
                    action = escape_options[0][-1]
                    hunt_record["retreat_attempted"] = True
                    carnivore.target = None
                    carnivore.path = []
                    carnivore.exploration_target = None
                    carnivore.running = should_run(
                        energy=carnivore.needs.energy, max_energy=carnivore.needs.max_energy,
                        fatigue=carnivore.needs.fatigue, urgent=True,
                        currently_running=carnivore.last_activity == "RUNNING",
                        config=self.physiology_config,
                    )
                    activity = "RUNNING" if carnivore.running else "WALKING"
                    hunt_record["target_selection_reason"] = "FLEE_HUMAN_GROUP"
                    hunt_record["nearby_human_defenders"] = len(nearby_humans_for_risk)
                else:
                    hunt_record["retreat_reason"] = "NO_SAFE_ESCAPE_CELL"
            if action != (0, 0):
                # O predador tem uma arrancada mais rápida que a fuga normal:
                # até cinco células por passo, seguindo o caminho calculado (não
                # repetindo cegamente o mesmo vetor e colidindo com obstáculos).
                can_sprint = carnivore.running and carnivore.needs.energy >= self.physiology_config.stamina_run_minimum
                max_distance = carnivore.run_distance if can_sprint else 1
                for path_index in range(1, max_distance + 1):
                    if carnivore.path and len(carnivore.path) > path_index and carnivore.path[0] == (before_pos[0], before_pos[1]):
                        next_position = carnivore.path[path_index]
                        move_action = (next_position[0] - carnivore.x, next_position[1] - carnivore.y)
                    else:
                        move_action = action
                    nx, ny = carnivore.x + move_action[0], carnivore.y + move_action[1]
                    occupied_now = ({(a.x,a.y) for a in self.alive_agents}
                        | {(h.x,h.y) for h in self.alive_herbivores if h is not carnivore}
                        | {(c.x,c.y) for c in self.alive_carnivores if c is not carnivore})
                    if (nx,ny) in occupied_now or not self.world.is_walkable(nx,ny): break
                    if not self.world.move_agent(carnivore, move_action): break
                if (carnivore.x, carnivore.y) == before_pos:
                    activity = "WAITING"
                    carnivore.running = False
                    # Se a rota de exploração foi bloqueada por outra entidade,
                    # abandona o waypoint para não insistir indefinidamente nela.
                    if carnivore.target is None:
                        carnivore.exploration_target = None
                        carnivore.path = []
            carnivore.last_activity = activity
            hunt_record["selected_target_x"] = carnivore.target[0] if carnivore.target is not None else ""
            hunt_record["selected_target_y"] = carnivore.target[1] if carnivore.target is not None else ""
            hunt_record["selected_target_distance_before_move"] = (
                abs(carnivore.target[0]-before_pos[0]) + abs(carnivore.target[1]-before_pos[1])
                if carnivore.target is not None else ""
            )
            hunt_record["x_after_move"] = carnivore.x
            hunt_record["y_after_move"] = carnivore.y
            hunt_record["activity"] = activity
            hunt_record["distance_moved"] = abs(carnivore.x-before_pos[0])+abs(carnivore.y-before_pos[1])
            selected_prey_object_id = hunt_record.pop("_selected_prey_object_id", None)
            if selected_prey_object_id is not None:
                selected_prey = next((item for item in available_humans + available_herbivores
                                      if id(item) == selected_prey_object_id), None)
                if selected_prey is not None:
                    distance_after = abs(selected_prey.x-carnivore.x) + abs(selected_prey.y-carnivore.y)
                    distance_before = int(hunt_record["selected_prey_distance_before_action"])
                    hunt_record["selected_prey_distance_after_move"] = distance_after
                    hunt_record["selected_prey_distance_progress"] = distance_before - distance_after
            resource = self.world.get_cell(carnivore.x, carnivore.y).resource
            if activity != "SLEEPING":
                if isinstance(resource, Water) and carnivore.thirst > 0:
                    thirst_before = carnivore.thirst
                    carnivore.drink(resource.drink_amount)
                    self._record_water_event("carnivores", thirst_before, carnivore.thirst)
            displacement = abs(carnivore.x-before_pos[0])+abs(carnivore.y-before_pos[1])
            if hunt_record.get("retreat_attempted"):
                min_distance_after = min(
                    (abs(human.x-carnivore.x) + abs(human.y-carnivore.y)
                     for human in nearby_humans_for_risk), default=None
                )
                before_distance = hunt_record.get("retreat_min_human_distance_before", "")
                hunt_record["retreat_min_human_distance_after"] = (
                    min_distance_after if min_distance_after is not None else ""
                )
                hunt_record["retreat_immediate_distance_increased"] = bool(
                    min_distance_after is not None and before_distance != ""
                    and min_distance_after > float(before_distance)
                )
            stamina_before_recovery = carnivore.needs.energy
            carnivore_movement_stamina_spent = 0.0
            if activity == "RUNNING" and displacement:
                # Uma arrancada de até três células custa 6 unidades: mais cara
                # que caminhar, mas sustentável o bastante para permitir perseguições.
                carnivore_movement_stamina_spent = min(
                    carnivore.needs.energy, self.physiology_config.stamina_run_cost * displacement / 4.0
                )
                carnivore.needs.energy = max(0.0, carnivore.needs.energy-carnivore_movement_stamina_spent)
            elif displacement:
                carnivore_movement_stamina_spent = ENERGY_PER_STEP * displacement
                carnivore.needs.energy = max(0.0, carnivore.needs.energy-ENERGY_PER_STEP*displacement)
            elif activity == "RESTING":
                carnivore.needs.restore_energy(recovery_amount(self.physiology_config.stamina_rest_recovery, carnivore.needs.energy, carnivore.needs.max_energy, self.physiology_config))
            elif activity == "WAITING":
                carnivore.needs.restore_energy(recovery_amount(self.physiology_config.stamina_wait_recovery, carnivore.needs.energy, carnivore.needs.max_energy, self.physiology_config))
            elif activity == "SLEEPING":
                carnivore.needs.restore_energy(recovery_amount(self.physiology_config.stamina_sleep_recovery, carnivore.needs.energy, carnivore.needs.max_energy, self.physiology_config))
            stamina_recovered_activity = max(0.0, carnivore.needs.energy - stamina_before_recovery)
            # Perfil de fadiga próprio dos carnívoros. Pausas curtas recuperam
            # fadiga, e o sono recupera mais rapidamente do que no perfil geral.
            # Isso evita que perseguições/exploração os deixem fatigados por
            # centenas de minutos antes de conseguirem voltar a operar bem.
            activity_costs = {
                "WAITING": (self.physiology_config.hunger_wait_cost, self.physiology_config.thirst_wait_cost, self.physiology_config.carnivore_fatigue_wait_per_step),
                "WALKING": (self.physiology_config.hunger_walk_cost, self.physiology_config.thirst_walk_cost, self.physiology_config.carnivore_fatigue_walk_per_step),
                "RUNNING": (self.physiology_config.hunger_run_cost, self.physiology_config.thirst_run_cost, self.physiology_config.carnivore_fatigue_run_per_step),
                "RESTING": (self.physiology_config.hunger_rest_cost, self.physiology_config.thirst_rest_cost, -self.physiology_config.carnivore_fatigue_rest_recovery),
                "SLEEPING": (self.physiology_config.hunger_rest_cost, self.physiology_config.thirst_rest_cost,
                    -(self.physiology_config.carnivore_fatigue_shelter_sleep_recovery if isinstance(self.world.get_cell(carnivore.x, carnivore.y).structure, Shelter)
                      else self.physiology_config.carnivore_fatigue_sleep_recovery)),
            }
            hunger_extra, thirst_extra, fatigue_delta = activity_costs[activity]
            hunger_extra = adjusted_hunger_rate(hunger_extra, carnivore.species, carnivore.attributes)
            carnivore.needs.advance_step(hunger_extra=hunger_extra, thirst_extra=thirst_extra, fatigue_delta=fatigue_delta)
            health_recovered_this_step, recovery_block_reason = recover_health_during_rest(
                carnivore.needs, activity, 0.35 + 0.65 * carnivore.attributes.constitution
            )
            hunt_record.update({
                "health_recovery_eligible": recovery_block_reason == "RECOVERED",
                "health_recovered_this_step": health_recovered_this_step,
                "health_recovery_source": activity if health_recovered_this_step > 0 else "NONE",
                "health_recovery_block_reason": recovery_block_reason,
            })
            if activity == "SLEEPING" and carnivore.needs.fatigue <= self.physiology_config.sleep_end_threshold:
                carnivore.is_sleeping = False
            carnivore.alive = carnivore.needs.alive
            self.physiology_activity_history.append({
                "step": self.steps + 1, "simulated_minute": self.simulated_minutes + 1,
                "individual_type": "CARNIVORE", "individual_id": self._carnivore_ids.setdefault(
                    id(carnivore), f"C{len(self._carnivore_ids) + 1:03d}"
                ),
                "x": carnivore.x, "y": carnivore.y, "activity": activity,
                "target_agent_id": hunt_record.get("selected_prey_id", ""),
                "behavior_intent": (
                    "SEEK_WATER" if carnivore.thirst >= 50 else
                    "HUNT" if carnivore.hunger >= 30 else
                    "SEEK_WATER" if carnivore.thirst >= 35 else activity
                ),
                "action_reason": (
                    "SLEEPING" if activity == "SLEEPING" else
                    "AT_WATER" if isinstance(self.world.get_cell(carnivore.x, carnivore.y).resource, Water) and carnivore.thirst > 0 else
                    "LOW_STAMINA" if activity == "RESTING" else
                    "AT_PREY" if carnivore.target is not None and abs(carnivore.target[0]-carnivore.x)+abs(carnivore.target[1]-carnivore.y) <= 1 and carnivore.hunger >= 30 else
                    "MOVING_TO_TARGET" if carnivore.target is not None else
                    "EXPLORING" if activity in {"WALKING", "RUNNING"} else "NO_ACTION"
                ),
                "moved": displacement > 0, "distance": float(displacement),
                **_target_progress_fields(
                    carnivore_target_before_action, carnivore_target_intent_before_action,
                    before_pos, (carnivore.x, carnivore.y),
                    need_satisfied=bool(
                        (carnivore_target_intent_before_action == "HUNT" and (
                            bool(hunt_record.get("prey_killed", False))
                            or float(hunt_record.get("hunger_reduction_from_meat", 0) or 0) > 0
                        ))
                        or (carnivore_target_intent_before_action == "SEEK_WATER"
                            and isinstance(self.world.get_cell(carnivore.x, carnivore.y).resource, Water)
                            and before_state["thirst"] > carnivore.thirst)
                    ),
                ),
                "stamina_before": before_state["stamina"], "stamina_after": carnivore.needs.energy,
                "stamina_spent_movement": carnivore_movement_stamina_spent,
                "stamina_recovered_rest": stamina_recovered_activity,
                "stamina_recovered": stamina_recovered_activity,
                "stamina_recovery_source": activity if activity in {"WAITING", "RESTING", "SLEEPING"} else "NONE",
                "decision_trace": {},
                "stamina_spent_combat": 0.0,
                "hunger_metabolic_cost": carnivore.needs.hunger_per_step + hunger_extra,
                "thirst_metabolic_cost": carnivore.needs.thirst_per_step + thirst_extra,
                "fatigue_delta": fatigue_delta,
                "fatigue_before": before_state["fatigue"], "fatigue_after": carnivore.needs.fatigue,
                "hunger_before": before_state["hunger"], "hunger_after": carnivore.hunger,
                "thirst_before": before_state["thirst"], "thirst_after": carnivore.thirst,
                "health_before": before_state["health"], "health_after": carnivore.health,
                "health_recovered_this_step": health_recovered_this_step,
                "health_recovery_source": activity if health_recovered_this_step > 0 else "NONE",
                "health_recovery_block_reason": recovery_block_reason,
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
            hunt_record.update({
                "health_after": carnivore.health, "hunger_after": carnivore.hunger,
                "thirst_after": carnivore.thirst, "stamina_after": carnivore.needs.energy,
                "damage_causes": ";".join(carnivore.needs.last_damage_causes),
                "termination_cause": "RUNNING" if carnivore.alive else (carnivore.needs.last_damage_cause or "HEALTH_DEPLETED"),
            })
            self.carnivore_hunt_history.append(hunt_record)

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
                defense_damage = 20.0 * agent.attributes.relative_multiplier(agent.species, "strength", strength=0.5)
                damage_taken = target.needs.damage(defense_damage, cause="DEFENSE")
                diagnostic = carnivore_diagnostics_this_step.get(id(target))
                if diagnostic is not None:
                    diagnostic["defense_attacks_received"] = int(diagnostic["defense_attacks_received"]) + 1
                    diagnostic["damage_received_from_defense"] = float(diagnostic["damage_received_from_defense"]) + damage_taken
                self.human_defense_attacks += 1
                target.alive = target.needs.alive
                if not target.alive:
                    self.carnivores_killed += 1

        # Carnívoros atacam a presa adjacente mais próxima: primeiro humanos,
        # depois herbívoros. Cada indivíduo só pode receber um ataque por tick.
        attacked_this_step: set[int] = set()
        for carnivore in self.alive_carnivores:
            diagnostic = carnivore_diagnostics_this_step.get(id(carnivore))
            # A recuperação ocorrida neste passo não pode financiar um ataque
            # simultâneo: o indivíduo precisa chegar ao início do passo com reserva.
            if carnivore.last_activity == "RESTING" or carnivore.last_activity == "SLEEPING":
                continue
            test_target = getattr(carnivore, "test_target_agent", None)
            available_targets = (
                [test_target] if test_target is not None and test_target.alive
                else self.alive_agents + self.alive_herbivores
            )
            physically_adjacent_targets = [
                target for target in available_targets
                if abs(target.x-carnivore.x) + abs(target.y-carnivore.y) <= 1
            ]
            adjacent_targets = [target for target in physically_adjacent_targets if id(target) not in attacked_this_step]
            risk_humans = list(self.alive_agents)
            if isinstance(test_target, Agent) and test_target not in risk_humans:
                risk_humans.append(test_target)
            preferred_adjacent = next((target for target in adjacent_targets
                if id(target) == carnivore.hunt_target_object_id), None)
            selected_attack_target, attack_risk_score, attack_nearby_humans, attack_selection_reason = select_prey_candidate(
                carnivore,
                [target for target in adjacent_targets if isinstance(target, Agent)],
                [target for target in adjacent_targets if not isinstance(target, Agent)],
                risk_humans,
                current_target=preferred_adjacent,
                hunger=carnivore.hunger,
            )
            target = selected_attack_target
            if diagnostic is not None:
                diagnostic["adjacent_prey_count"] = len(physically_adjacent_targets)
                diagnostic["attack_risk_score"] = attack_risk_score if attack_risk_score is not None else ""
                diagnostic["attack_nearby_humans"] = attack_nearby_humans
                diagnostic["attack_selection_reason"] = attack_selection_reason
                if carnivore.hunger < 30.0:
                    diagnostic["attack_skipped_reason"] = "NOT_HUNGRY"
                elif carnivore.needs.energy < self.physiology_config.stamina_attack_cost:
                    diagnostic["attack_skipped_reason"] = "LOW_STAMINA"
                elif target is None and any(human_prey_is_too_risky(item, risk_humans, carnivore.hunger)
                                            for item in adjacent_targets):
                    diagnostic["attack_skipped_reason"] = "PREY_DEFENSE_RISK"
                elif target is None and physically_adjacent_targets:
                    diagnostic["attack_skipped_reason"] = "TARGET_ALREADY_ATTACKED_THIS_STEP"
                elif target is None:
                    diagnostic["attack_skipped_reason"] = "NO_ADJACENT_PREY"
                else:
                    diagnostic["attack_skipped_reason"] = "ATTACKED"
            if carnivore.hunger < 30.0 or carnivore.needs.energy < self.physiology_config.stamina_attack_cost or target is None:
                continue
            damage = CARNIVORE_ATTACK_DAMAGE * carnivore.attributes.relative_multiplier(
                carnivore.species, "strength", strength=0.5
            )
            if isinstance(target, Agent) and isinstance(
                self.world.get_cell(target.x, target.y).structure, Shelter
            ):
                # O abrigo reduz bastante o dano, mas não torna o ocupante invulnerável.
                damage *= SHELTER_PREDATION_DAMAGE_MULTIPLIER
            health_before_attack = target.health
            carnivore.needs.energy = max(0.0, carnivore.needs.energy - self.physiology_config.stamina_attack_cost)
            combat_stamina_spent[id(carnivore)] = combat_stamina_spent.get(id(carnivore), 0.0) + self.physiology_config.stamina_attack_cost
            actual_damage = target.needs.damage(damage, cause="PREDATION")
            if diagnostic is not None:
                diagnostic["attack_attempted"] = True
                diagnostic["attack_target_type"] = "HUMAN" if isinstance(target, Agent) else "HERBIVORE"
                diagnostic["attack_target_id"] = (
                    target.agent_id if isinstance(target, Agent)
                    else self._herbivore_ids.setdefault(id(target), f"V{len(self._herbivore_ids) + 1:03d}")
                )
                diagnostic["attack_damage"] = actual_damage
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
                if diagnostic is not None:
                    diagnostic["prey_killed"] = True
                    diagnostic["hunger_before_eating"] = carnivore.hunger
                if isinstance(target, Agent):
                    target_metrics = self.metrics_by_agent[id(target)]
                    target_metrics.termination_cause = "PREDATION"
                    self.humans_killed_by_carnivores += 1
                else:
                    self.animals_killed += 1
                hunger_before_eating = carnivore.hunger
                carnivore.eat(MEAT_HUNGER_REDUCTION)
                if diagnostic is not None:
                    diagnostic["hunger_before_eating"] = hunger_before_eating
                    diagnostic["hunger_after_eating"] = carnivore.hunger
                    diagnostic["hunger_reduction_from_meat"] = hunger_before_eating - carnivore.hunger
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
        self._enrich_resource_access_records(current_activity_records, carnivore_diagnostics_this_step)
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
                if isinstance(individual, Carnivore):
                    hunt_record = carnivore_diagnostics_this_step.get(id(individual))
                    if hunt_record is not None:
                        hunt_record.update({
                            "health_after": individual.health, "hunger_after": individual.hunger,
                            "thirst_after": individual.thirst, "stamina_after": individual.needs.energy,
                            "damage_causes": ";".join(individual.needs.last_damage_causes),
                            "termination_cause": "RUNNING" if individual.alive else (individual.needs.last_damage_cause or "HEALTH_DEPLETED"),
                        })
                        if not individual.alive and hunt_record["attack_skipped_reason"] == "NOT_EVALUATED":
                            hunt_record["attack_skipped_reason"] = (
                                "KILLED_BY_DEFENSE_BEFORE_ATTACK"
                                if float(hunt_record["damage_received_from_defense"] or 0) > 0
                                else "DIED_BEFORE_ATTACK"
                            )

        self.reproduction.process_step(self)
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
