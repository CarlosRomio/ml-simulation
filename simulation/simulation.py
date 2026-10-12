
from math import dist

from agents.agent import Agent
from agents.perception import Perception
from environment.world import World
from metrics.tracker import SimulationMetrics


FOOD_ENERGY = 25.0
ENERGY_PER_STEP = 1.0


class Simulation:
    def __init__(
        self,
        world: World,
        agent: Agent,
        step_duration_seconds: float = 1.0,
        seed_spawn_count: int = 1,
        max_plants: int = 100,
        resource_update_interval: int = 1,
    ):
        if step_duration_seconds <= 0:
            raise ValueError(
                "A duração do passo deve ser positiva."
            )

        if seed_spawn_count < 0:
            raise ValueError(
                "A quantidade de sementes não pode ser negativa."
            )

        if max_plants < 0:
            raise ValueError(
                "O limite de plantas não pode ser negativo."
            )

        if resource_update_interval <= 0:
            raise ValueError(
                "O intervalo de atualização deve ser positivo."
            )

        self.world = world
        self.agent = agent
        self.steps = 0
        self.step_duration_seconds = step_duration_seconds

        self.seed_spawn_count = seed_spawn_count
        self.max_plants = max_plants
        self.resource_update_interval = resource_update_interval

        self.metrics = SimulationMetrics(
            initial_energy=agent.energy,
            final_energy=agent.energy,
            energy_sum=agent.energy,
            energy_samples=1,
        )

        initial_position = (agent.x, agent.y)

        self.energy_history: list[float] = [agent.energy]
        self.food_collection_steps: list[int] = []
        self.position_history: list[tuple[int, int]] = [
            initial_position
        ]
        self.diagnostic_history: list[dict] = []

        self.resource_history: list[dict[str, int]] = []
        self.seeds_spawned_history: list[int] = []

        self._record_resource_metrics(seeds_spawned=0)

        self._visited_positions: set[tuple[int, int]] = {
            initial_position
        }
        self._steps_without_food = 0

        self.perception = Perception()

    def _record_resource_metrics(self, seeds_spawned: int) -> None:
        counts = self.world.get_plant_counts()

        self.resource_history.append({
            "step": self.steps,
            **counts,
        })

        self.seeds_spawned_history.append(seeds_spawned)

    
    def _advance_environment(self) -> None:
        """Avança o ecossistema independentemente do estado do agente."""
        self.steps += 1

        seeds_spawned = 0

        if self.steps % self.resource_update_interval == 0:
            self.world.advance_resources()

            occupied_cells = (
                {(self.agent.x, self.agent.y)}
                if self.agent.alive
                else set()
            )

            seeds_spawned = self.world.spawn_seeds(
                count=self.seed_spawn_count,
                max_plants=self.max_plants,
                occupied_cells=occupied_cells,
            )

        self._record_resource_metrics(seeds_spawned)

        self.metrics.steps = self.steps
        self.metrics.simulated_time_seconds = (
            self.steps * self.step_duration_seconds
        )

    def step(self) -> None:
        if not self.agent.alive:
            self._advance_environment()
            return

        position_before = (self.agent.x, self.agent.y)
        energy_before = self.agent.energy

        nearby_cells = self.perception.observe(
            self.world,
            self.agent.x,
            self.agent.y,
            radius=self.agent.vision_radius,
        )

        action = self.agent.choose_action(
            nearby_cells,
            self.world,
        )

        if action == (0, 0):
            moved = False
        else:
            moved = self.world.move_agent(self.agent, action)

        if not moved:
            self.agent.target = None
            self.agent.path.clear()

        position_after_move = (self.agent.x, self.agent.y)

        displacement = dist(position_before, position_after_move)
        actually_moved = displacement > 0

        if actually_moved:
            self.metrics.movement_steps += 1
            self.metrics.distance_travelled += displacement
        else:
            self.metrics.idle_steps += 1

        collected_food = False

        resource = self.world.collect_resource(
            self.agent.x,
            self.agent.y,
        )

        if resource is not None:
            collected_food = True
            self.agent.eat(FOOD_ENERGY)
            self.metrics.food_collected += 1
            self.food_collection_steps.append(self.steps + 1)
            self._steps_without_food = 0
        else:
            self._steps_without_food += 1

        self.metrics.max_steps_without_food = max(
            self.metrics.max_steps_without_food,
            self._steps_without_food,
        )

        self.agent.consume_energy(ENERGY_PER_STEP)

        self.steps += 1
        self.metrics.agent_lifetime_steps += 1

        # Atualiza o ambiente em intervalos configuráveis.
        seeds_spawned = 0

        if self.steps % self.resource_update_interval == 0:
            self.world.advance_resources()

            occupied_cells = {(self.agent.x, self.agent.y)}

            seeds_spawned = self.world.spawn_seeds(
                count=self.seed_spawn_count,
                max_plants=self.max_plants,
                occupied_cells=occupied_cells,
            )

        self._record_resource_metrics(seeds_spawned)

        energy_after = self.agent.energy
        position_after = (self.agent.x, self.agent.y)

        self.energy_history.append(energy_after)
        self.position_history.append(position_after)
        self._visited_positions.add(position_after)

        self.metrics.steps = self.steps
        self.metrics.simulated_time_seconds = (
            self.steps * self.step_duration_seconds
        )
        self.metrics.final_energy = energy_after
        self.metrics.energy_sum += energy_after
        self.metrics.energy_samples += 1
        self.metrics.unique_positions_visited = len(
            self._visited_positions
        )

        self.diagnostic_history.append({
            "step": self.steps,
            "position_before": position_before,
            "position_after": position_after,
            "energy_before": energy_before,
            "energy_after": energy_after,
            "collected_food": collected_food,
            "action": action,
            "moved": actually_moved,
            "distance": displacement,
        })

        if not self.agent.alive:
            self.metrics.termination_cause = "STARVATION"


    def run(self, steps: int) -> None:
        if steps < 0:
            raise ValueError(
                "O número de passos não pode ser negativo."
            )

        if not self.agent.alive:
            self.metrics.termination_cause = "STARVATION"

        target_step = self.steps + steps

        while self.steps < target_step:
            self.step()

        if self.agent.alive:
            self.metrics.termination_cause = "STEP_LIMIT"
