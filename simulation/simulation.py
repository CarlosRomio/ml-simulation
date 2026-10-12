from math import dist
import random
from random import Random

from agents.agent import Agent
from agents.perception import Perception
from environment.world import World
from environment.resources import Water
from metrics.tracker import SimulationMetrics


FOOD_ENERGY = 25.0
ENERGY_PER_STEP = 1.0


class Simulation:
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
        # Compatibilidade temporária com código e testes de agente único.
        self.agent = self.agents[0]
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
        self.population_history: list[dict[str, int]] = []

        for index, item in enumerate(self.agents):
            key = id(item)
            initial_position = (item.x, item.y)
            self.metrics_by_agent[key] = SimulationMetrics(
                initial_energy=item.energy,
                final_energy=item.energy,
                initial_health=item.health,
                final_health=item.health,
                final_hunger=item.hunger,
                final_thirst=item.thirst,
                energy_sum=item.energy,
                energy_samples=1,
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
        self._record_resource_metrics(seeds_spawned=0)
        self._record_population_metrics()

    @property
    def alive_agents(self) -> list[Agent]:
        return [agent for agent in self.agents if agent.alive]

    @property
    def population_survival_rate(self) -> float:
        return len(self.alive_agents) / len(self.agents)

    def _record_resource_metrics(self, seeds_spawned: int) -> None:
        self.resource_history.append({"step": self.steps, **self.world.get_plant_counts()})
        self.seeds_spawned_history.append(seeds_spawned)

    def _record_population_metrics(self) -> None:
        self.population_history.append({
            "step": self.steps,
            "alive": len(self.alive_agents),
            "dead": len(self.agents) - len(self.alive_agents),
            "food_collected": sum(m.food_collected for m in self.metrics_by_agent.values()),
        })

    def _advance_environment(self) -> None:
        self.steps += 1
        seeds_spawned = 0
        if self.steps % self.resource_update_interval == 0:
            self.world.advance_resources()
            occupied = {(a.x, a.y) for a in self.alive_agents}
            seeds_spawned = self.world.spawn_seeds(
                count=self.seed_spawn_count,
                max_plants=self.max_plants,
                occupied_cells=occupied,
            )
        self._record_resource_metrics(seeds_spawned)
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

            if destination in occupied:
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

            moved = self.world.move_agent(agent, action)
            if moved:
                occupied[destination] = agent
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

    def step(self) -> None:
        alive_at_start = self.alive_agents
        if not alive_at_start:
            self._advance_environment()
            return

        before = {id(a): (a.x, a.y) for a in alive_at_start}
        energy_before = {id(a): a.energy for a in alive_at_start}
        actions: dict[int, tuple[int, int]] = {}

        # All agents choose actions from the same pre-movement world state.
        for agent in alive_at_start:
            nearby = self.perception.observe(
                self.world, agent.x, agent.y, radius=agent.vision_radius
            )
            actions[id(agent)] = agent.choose_action(nearby, self.world)

        moved_by_id = self._resolve_movements(actions)

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

            current_resource = self.world.get_cell(agent.x, agent.y).resource
            if isinstance(current_resource, Water) and agent.thirst > 0:
                before_thirst = agent.thirst
                agent.needs.drink(current_resource.drink_amount)
                metrics.water_drinks += 1
                metrics.water_units_consumed += before_thirst - agent.thirst

            resource = self.world.collect_resource(agent.x, agent.y)
            collected_food = resource is not None
            if collected_food:
                agent.eat(FOOD_ENERGY)
                agent.needs.eat(25.0)
                metrics.food_collected += 1
                self.food_collection_steps_by_agent[key].append(self.steps + 1)
                self._steps_without_food_by_agent[key] = 0
            else:
                self._steps_without_food_by_agent[key] += 1

            metrics.max_steps_without_food = max(
                metrics.max_steps_without_food,
                self._steps_without_food_by_agent[key],
            )
            agent.consume_energy(ENERGY_PER_STEP)
            agent.needs.advance_step()
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
            metrics.unique_positions_visited = len(self._visited_positions_by_agent[key])
            self.diagnostic_history_by_agent[key].append({
                "step": self.steps + 1,
                "position_before": before[key],
                "position_after": (agent.x, agent.y),
                "energy_before": energy_before[key],
                "energy_after": agent.energy,
                "collected_food": collected_food,
                "action": actions[key],
                "moved": moved,
                "distance": displacement,
            })
            if not agent.alive:
                metrics.termination_cause = (
                    "STARVATION" if agent.energy <= 0
                    else (agent.needs.last_damage_cause or "HEALTH_DEPLETED")
                )

        self.steps += 1
        seeds_spawned = 0
        if self.steps % self.resource_update_interval == 0:
            self.world.advance_resources()
            occupied = {(a.x, a.y) for a in self.alive_agents}
            seeds_spawned = self.world.spawn_seeds(
                count=self.seed_spawn_count,
                max_plants=self.max_plants,
                occupied_cells=occupied,
            )
        self._record_resource_metrics(seeds_spawned)
        self._record_population_metrics()

        for metrics in self.metrics_by_agent.values():
            metrics.steps = self.steps
            metrics.simulated_time_seconds = self.steps * self.step_duration_seconds

    def run(self, steps: int) -> None:
        if steps < 0:
            raise ValueError("O número de passos não pode ser negativo.")
        for agent in self.agents:
            if not agent.alive:
                self.metrics_by_agent[id(agent)].termination_cause = (
                    "STARVATION" if agent.energy <= 0
                    else (agent.needs.last_damage_cause or "HEALTH_DEPLETED")
                )
        target_step = self.steps + steps
        while self.steps < target_step:
            self.step()
        for agent in self.agents:
            metrics = self.metrics_by_agent[id(agent)]
            if agent.alive:
                metrics.termination_cause = "STEP_LIMIT"
