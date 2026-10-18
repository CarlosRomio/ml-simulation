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


FOOD_ENERGY = 35.0
ENERGY_PER_STEP = 1.0  # custo de estamina por célula percorrida
RUN_STAMINA_COST = 4.0
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
        self.steps = 0
        self.step_duration_seconds = step_duration_seconds
        self.seed_spawn_count = seed_spawn_count
        self.max_plants = max_plants
        self.resource_update_interval = resource_update_interval
        self.rng = rng if rng is not None else world.rng
        self.perception = Perception()

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
            agent.target = None
            agent.path.clear()
            agent.building_intent = False
        elif self.manual_control_agent is agent:
            self.manual_control_agent = None
            self.manual_action = (0, 0)
        return True

    def queue_manual_action(self, dx: int, dy: int) -> bool:
        """Agenda um movimento cardinal para o próximo passo da simulação."""
        if self.manual_control_agent is None or not self.manual_control_agent.alive:
            return False
        if (dx, dy) not in {(0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)}:
            raise ValueError("O movimento manual deve ser uma direção cardinal.")
        self.manual_action = (dx, dy)
        return True

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

    def _record_population_metrics(self) -> None:
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
            "human_all_mean_health": self._mean_need(self.agents, "health"),
            "human_all_mean_hunger": self._mean_need(self.agents, "hunger"),
            "human_all_mean_thirst": self._mean_need(self.agents, "thirst"),
            "human_all_mean_energy": self._mean_need(self.agents, "energy"),
            "herbivore_mean_health": self._mean_need(self.alive_herbivores, "health"),
            "herbivore_mean_hunger": self._mean_need(self.alive_herbivores, "hunger"),
            "herbivore_mean_thirst": self._mean_need(self.alive_herbivores, "thirst"),
            "herbivore_all_mean_health": self._mean_need(self.herbivores, "health"),
            "herbivore_all_mean_hunger": self._mean_need(self.herbivores, "hunger"),
            "herbivore_all_mean_thirst": self._mean_need(self.herbivores, "thirst"),
            "carnivore_mean_health": self._mean_need(self.alive_carnivores, "health"),
            "carnivore_mean_hunger": self._mean_need(self.alive_carnivores, "hunger"),
            "carnivore_mean_thirst": self._mean_need(self.alive_carnivores, "thirst"),
            "carnivore_all_mean_health": self._mean_need(self.carnivores, "health"),
            "carnivore_all_mean_hunger": self._mean_need(self.carnivores, "hunger"),
            "carnivore_all_mean_thirst": self._mean_need(self.carnivores, "thirst"),
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
            metrics.simulated_time_seconds = self.steps * self.step_duration_seconds

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
            distance = 2 if agent.running and agent.energy >= RUN_STAMINA_COST else 1
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
            id(a): {"health": a.health, "hunger": a.hunger, "thirst": a.thirst, "energy": a.energy}
            for a in alive_at_start
        }
        damage_before = {id(a): dict(a.needs.damage_by_cause) for a in alive_at_start}
        actions: dict[int, tuple[int, int]] = {}

        # All agents choose actions from the same pre-movement world state.
        # O humano sob controle manual ignora a decisão autônoma neste passo,
        # mas continua sujeito a colisões, necessidades e interações normais.
        for agent in alive_at_start:
            if agent is self.manual_control_agent:
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
                agent.running = abs(prey.x-agent.x)+abs(prey.y-agent.y) > 1 and agent.energy >= RUN_STAMINA_COST
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
            actions[id(agent)] = agent.choose_action(nearby, self.world)

        # Cada tecla corresponde a um único passo, evitando movimento contínuo
        # involuntário quando a simulação está em velocidade acelerada.
        self.manual_action = (0, 0)
        moved_by_id = self._resolve_movements(actions)

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
                    if accepted_food < 1.0 - 1e-9:
                        raise RuntimeError("A planta foi removida sem caber integralmente no inventário.")
                elif isinstance(resource, Food):
                    collected_resource_type = "FOOD"
                    accepted_food = agent.inventory.add_food(resource.quantity)
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
                agent.consume_energy(RUN_STAMINA_COST)
                movement_energy_cost = energy_before_cost - agent.energy
            elif moved:
                energy_before_cost = agent.energy
                agent.consume_energy(ENERGY_PER_STEP * displacement)
                movement_energy_cost = energy_before_cost - agent.energy
            else:
                energy_before_rest = agent.energy
                current_structure = self.world.get_cell(agent.x, agent.y).structure
                rest_amount = 8.0 if isinstance(current_structure, Shelter) else 2.0
                agent.rest(rest_amount)
                rest_energy_recovered = agent.energy - energy_before_rest
            health_before_needs = agent.health
            agent.needs.advance_step()
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
                "collected_resource_type": collected_resource_type,
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
                "movement_energy_cost": movement_energy_cost,
                "food_energy_recovered": food_energy_recovered,
                "rest_energy_recovered": rest_energy_recovered,
                "energy_after_actions": agent.energy,
                "damage_causes": list(agent.needs.last_damage_causes),
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

        # Humanos atacam herbívoros adjacentes apenas quando estão caçando.
        for agent in self.alive_agents:
            if agent.hunt_target is None or agent.energy < ATTACK_STAMINA_COST:
                continue
            prey = next((h for h in self.alive_herbivores
                         if abs(h.x-agent.x) + abs(h.y-agent.y) <= 1), None)
            if prey is None:
                continue
            agent.consume_energy(ATTACK_STAMINA_COST)
            prey.needs.damage(ATTACK_DAMAGE, cause="HUNTING")
            self.attacks += 1
            if not prey.needs.alive:
                prey.alive = False
                agent.needs.eat(MEAT_HUNGER_REDUCTION)
                agent.needs.restore_energy(MEAT_STAMINA_REWARD)
                self.animals_killed += 1

        # Animais agem como entidades independentes e não entram em células ocupadas.
        occupied_agents = {(a.x, a.y) for a in self.alive_agents}
        occupied_animals = {(h.x, h.y) for h in self.alive_herbivores}
        for animal in list(self.alive_herbivores):
            before_pos = (animal.x, animal.y)
            threat_positions = list(occupied_agents) + [
                (c.x, c.y) for c in self.alive_carnivores
            ]
            action = animal.choose_action(self.world, threat_positions)
            nx, ny = animal.x + action[0], animal.y + action[1]
            if action != (0, 0) and (nx, ny) not in occupied_agents and (nx, ny) not in (occupied_animals - {before_pos}) and self.world.move_agent(animal, action):
                occupied_animals.discard(before_pos)
                occupied_animals.add((animal.x, animal.y))
            resource = self.world.get_cell(animal.x, animal.y).resource
            if isinstance(resource, Water) and animal.thirst > 0:
                thirst_before = animal.thirst
                animal.drink(resource.drink_amount)
                self._record_water_event("herbivores", thirst_before, animal.thirst)
            elif isinstance(resource, Plant) and resource.state == PlantState.MATURE and animal.hunger >= 20:
                collected_plant = self.world.collect_resource(animal.x, animal.y)
                if collected_plant is not None:
                    self._record_collection_event(collected_plant, "herbivore")
                    animal.eat(35.0)
            was_alive = animal.alive
            animal.needs.advance_step()
            animal.alive = animal.needs.alive
            if was_alive and not animal.alive:
                if "STARVATION" in animal.needs.last_damage_causes:
                    self.herbivores_died_by_starvation += 1
                if "DEHYDRATION" in animal.needs.last_damage_causes:
                    self.herbivores_died_by_dehydration += 1

        # Carnívoros procuram presas vivas (humanos e herbívoros), sem ocupar
        # células de outras entidades. O combate é resolvido após o movimento.
        for carnivore in list(self.alive_carnivores):
            test_target = getattr(carnivore, "test_target_agent", None)
            if test_target is not None and test_target.alive:
                prey_positions = [(test_target.x, test_target.y)]
            else:
                human_positions = [(a.x, a.y) for a in self.alive_agents]
                herbivore_positions = [(h.x, h.y) for h in self.alive_herbivores]
                prey_positions = human_positions + herbivore_positions
            action = carnivore.choose_action(self.world, prey_positions)
            destination = (carnivore.x + action[0], carnivore.y + action[1])
            occupied = (set(human_positions) | set(herbivore_positions)
                        | {(c.x, c.y) for c in self.alive_carnivores if c is not carnivore})
            if action != (0, 0) and destination not in occupied and self.world.is_walkable(*destination):
                self.world.move_agent(carnivore, action)
            resource = self.world.get_cell(carnivore.x, carnivore.y).resource
            if isinstance(resource, Water) and carnivore.thirst > 0:
                thirst_before = carnivore.thirst
                carnivore.drink(resource.drink_amount)
                self._record_water_event("carnivores", thirst_before, carnivore.thirst)
            was_alive = carnivore.alive
            carnivore.needs.advance_step()
            carnivore.alive = carnivore.needs.alive
            if was_alive and not carnivore.alive:
                if "STARVATION" in carnivore.needs.last_damage_causes:
                    self.carnivores_died_by_starvation += 1
                if "DEHYDRATION" in carnivore.needs.last_damage_causes:
                    self.carnivores_died_by_dehydration += 1

        # Humanos podem se defender se um carnívoro entrar em alcance corpo a corpo.
        # Defesa não exige fome; ataque de caça a herbívoro continua sendo outra ação.
        for agent in self.alive_agents:
            if agent.energy < ATTACK_STAMINA_COST:
                continue
            if any(abs(c.x-agent.x) + abs(c.y-agent.y) <= 1 for c in self.alive_carnivores):
                target = min(
                    (c for c in self.alive_carnivores
                     if abs(c.x-agent.x) + abs(c.y-agent.y) <= 1),
                    key=lambda c: abs(c.x-agent.x) + abs(c.y-agent.y),
                )
                agent.consume_energy(ATTACK_STAMINA_COST)
                target.needs.damage(20.0, cause="DEFENSE")
                self.human_defense_attacks += 1
                target.alive = target.needs.alive
                if not target.alive:
                    self.carnivores_killed += 1

        # Carnívoros atacam a presa adjacente mais próxima: primeiro humanos,
        # depois herbívoros. Cada indivíduo só pode receber um ataque por tick.
        attacked_this_step: set[int] = set()
        for carnivore in self.alive_carnivores:
            if carnivore.hunger < 30.0:
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
