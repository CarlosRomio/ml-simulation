from math import dist
import random
from random import Random

from agents.agent import Agent
from agents.species import Species
from animals.herbivore import Herbivore
from animals.carnivore import Carnivore
from agents.navigation.bfs import find_path
from agents.perception import Perception
from environment.world import World
from environment.resources import Water, Plant, PlantState
from metrics.tracker import SimulationMetrics


FOOD_ENERGY = 35.0
ENERGY_PER_STEP = 1.0  # custo legado; caminhar não consome estamina
RUN_STAMINA_COST = 4.0
ATTACK_STAMINA_COST = 8.0
ATTACK_DAMAGE = 30.0
CARNIVORE_ATTACK_DAMAGE = 35.0
MEAT_HUNGER_REDUCTION = 70.0
MEAT_STAMINA_REWARD = 25.0


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
        self.animals_killed = 0
        self.carnivore_attacks = 0
        self.human_defense_attacks = 0
        self.carnivores_killed = 0
        self.humans_killed_by_carnivores = 0
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
    def alive_herbivores(self) -> list[Herbivore]:
        return [animal for animal in self.herbivores if animal.alive]

    @property
    def alive_carnivores(self) -> list[Carnivore]:
        return [animal for animal in self.carnivores if animal.alive]

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
            "herbivores_alive": len(self.alive_herbivores),
            "carnivores_alive": len(self.alive_carnivores),
        })

    def _advance_environment(self) -> None:
        self.steps += 1
        seeds_spawned = 0
        if self.steps % self.resource_update_interval == 0:
            self.world.advance_resources()
            occupied = (
                {(a.x, a.y) for a in self.alive_agents}
                | {(h.x, h.y) for h in self.alive_herbivores}
                | {(c.x, c.y) for c in self.alive_carnivores}
            )
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

    def step(self) -> None:
        alive_at_start = self.alive_agents
        if not alive_at_start and not self.alive_herbivores and not self.alive_carnivores:
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
            actions[id(agent)] = agent.choose_action(nearby, self.world)

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
                metrics.food_collected += 1
                self.food_collection_steps_by_agent[key].append(self.steps + 1)
                self._steps_without_food_by_agent[key] = 0
            else:
                self._steps_without_food_by_agent[key] += 1

            metrics.max_steps_without_food = max(
                metrics.max_steps_without_food,
                self._steps_without_food_by_agent[key],
            )
            if agent.running and moved:
                agent.consume_energy(RUN_STAMINA_COST)
            elif not moved:
                agent.rest(2.0)
            health_before_needs = agent.health
            agent.needs.advance_step()
            if agent.thirst >= agent.needs.dehydration_threshold:
                metrics.critical_thirst_steps += 1
            if agent.health < health_before_needs and agent.needs.last_damage_cause == "DEHYDRATION":
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
                "action": actions[key],
                "moved": moved,
                "distance": displacement,
            })
            if not agent.alive:
                metrics.termination_cause = (
                    "STARVATION" if agent.energy <= 0
                    else (agent.needs.last_damage_cause or "HEALTH_DEPLETED")
                )

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
                animal.drink(resource.drink_amount)
            elif isinstance(resource, Plant) and resource.state == PlantState.MATURE and animal.hunger >= 20:
                self.world.collect_resource(animal.x, animal.y)
                animal.eat(35.0)
            animal.needs.advance_step()
            animal.alive = animal.needs.alive

        # Carnívoros procuram presas vivas (humanos e herbívoros), sem ocupar
        # células de outras entidades. O combate é resolvido após o movimento.
        for carnivore in list(self.alive_carnivores):
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
                carnivore.drink(resource.drink_amount)
            carnivore.needs.advance_step()
            carnivore.alive = carnivore.needs.alive

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
            adjacent_targets = [
                target for target in (self.alive_agents + self.alive_herbivores)
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
            target.needs.damage(CARNIVORE_ATTACK_DAMAGE, cause="PREDATION")
            attacked_this_step.add(id(target))
            self.carnivore_attacks += 1
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

        self.steps += 1
        seeds_spawned = 0
        if self.steps % self.resource_update_interval == 0:
            self.world.advance_resources()
            occupied = ({(a.x, a.y) for a in self.alive_agents}
                        | {(h.x, h.y) for h in self.alive_herbivores}
                        | {(c.x, c.y) for c in self.alive_carnivores})
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
                metrics = self.metrics_by_agent[id(agent)]
                if metrics.termination_cause == "PREDATION":
                    continue
                metrics.termination_cause = (
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
