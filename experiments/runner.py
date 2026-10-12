
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from agents.agent import Agent
from configuration.simulation_config import SimulationConfig
from environment.world import World
from metrics.tracker import SimulationMetrics
from scenarios.scenario import Scenario
from simulation.simulation import Simulation

@dataclass
class SimulationRunResult:
    agent_metrics: SimulationMetrics
    final_plant_count: int
    seeds_spawned: int
    step_reached_plant_limit: int | None

@dataclass
class ExperimentSummary:
    total_runs: int
    survived_runs: int
    starvation_runs: int
    survival_rate: float

    average_steps: float
    average_simulated_time: float
    average_food_collected: float
    average_energy: float

    average_distance_travelled: float
    average_unique_positions_visited: float
    average_movement_steps: float
    average_idle_steps: float
    average_max_steps_without_food: float
    average_final_plant_count: float
    average_seeds_spawned: float
    average_step_reached_plant_limit: float
    average_agent_lifetime_steps: float

    runs_reached_plant_limit: int

def run_single_simulation(
    config: SimulationConfig,
    run_seed: int,
    max_steps: int,
    scenario: Scenario | None = None,
    seed_spawn_count: int = 1,
    max_plants: int = 100,
) -> SimulationRunResult:
    """Executa uma simulação e retorna métricas do agente e do ambiente."""
    rng = random.Random(run_seed)

    if scenario is None:
        start_x, start_y = config.start_position

        world = World(
            width=config.width,
            height=config.height,
            food_count=config.food_count,
            obstacle_count=config.obstacle_count,
            reserved_cells={(start_x, start_y)},
            rng=rng,
        )
    else:
        world = scenario.to_world()
        world.rng = random.Random(run_seed + 1_000_000)
        start_x, start_y = scenario.start_position

    agent = Agent(
        x=start_x,
        y=start_y,
        vision_radius=config.vision_radius,
        rng=rng,
    )

    simulation = Simulation(
        world=world,
        agent=agent,
        seed_spawn_count=seed_spawn_count,
        max_plants=max_plants,
    )
    simulation.run(max_steps)

    plant_counts = world.get_plant_counts()

    limit_step = next(
        (
            record["step"]
            for record in simulation.resource_history
            if record["total"] >= max_plants
        ),
        None,
    )

    return SimulationRunResult(
        agent_metrics=simulation.metrics,
        final_plant_count=plant_counts["total"],
        seeds_spawned=sum(simulation.seeds_spawned_history),
        step_reached_plant_limit=limit_step,
    )

class ExperimentRunner:
    def __init__(
        self,
        config: SimulationConfig,
        runs: int = 100,
        max_steps: int = 500,
        seed: int = 42,
        max_workers: int = 1,
        scenario: Scenario | None = None,
        seed_spawn_count: int = 1,
        max_plants: int = 100,
    ):
        if runs <= 0:
            raise ValueError("O número de execuções deve ser positivo.")

        if max_steps <= 0:
            raise ValueError("O limite de passos deve ser positivo.")

        if max_workers <= 0:
            raise ValueError("max_workers deve ser positivo.")

        if seed_spawn_count < 0:
            raise ValueError("seed_spawn_count não pode ser negativo.")

        if max_plants < 0:
            raise ValueError("max_plants não pode ser negativo.")

        config.validate()

        if scenario is not None:
            if (config.width, config.height) != (
                scenario.width,
                scenario.height,
            ):
                raise ValueError(
                    "As dimensões do cenário devem corresponder "
                    "às dimensões da configuração."
                )

            if config.start_position != scenario.start_position:
                raise ValueError(
                    "A posição inicial da configuração deve corresponder "
                    "à do cenário."
                )

        self.config = config
        self.runs = runs
        self.max_steps = max_steps
        self.seed = seed
        self.max_workers = max_workers
        self.scenario = scenario
        self.seed_spawn_count = seed_spawn_count
        self.max_plants = max_plants

        self.results: list[SimulationRunResult] = []

    def run(self) -> list[SimulationRunResult]:
        self.results = []

        tasks = [
            (
                self.config,
                self.seed + index,
                self.max_steps,
                self.scenario,
                self.seed_spawn_count,
                self.max_plants,
            )
            for index in range(self.runs)
        ]

        if self.max_workers == 1:
            self.results = [
                self._run_simulation_task(task)
                for task in tasks
            ]
        else:
            with ProcessPoolExecutor(
                max_workers=self.max_workers
            ) as executor:
                self.results = list(
                    executor.map(self._run_simulation_task, tasks)
                )

        return self.results

    def summarize(self) -> ExperimentSummary:
        if not self.results:
            raise RuntimeError(
                "Nenhum resultado disponível. Execute run() primeiro."
            )

        total = len(self.results)

        survived = sum(
            result.agent_metrics.termination_cause == "STEP_LIMIT"
            for result in self.results
        )

        starvation = sum(
            result.agent_metrics.termination_cause == "STARVATION"
            for result in self.results
        )

        def average_agent(attribute: str) -> float:
            return sum(
                getattr(result.agent_metrics, attribute)
                for result in self.results
            ) / total

        reached_limit = [
            result.step_reached_plant_limit
            for result in self.results
            if result.step_reached_plant_limit is not None
        ]

        return ExperimentSummary(
            total_runs=total,
            survived_runs=survived,
            starvation_runs=starvation,
            survival_rate=survived / total,

            average_steps=average_agent("steps"),
            average_simulated_time=average_agent(
                "simulated_time_seconds"
            ),
            average_food_collected=average_agent("food_collected"),
            average_energy=average_agent("average_energy"),

            average_distance_travelled=average_agent(
                "distance_travelled"
            ),
            average_unique_positions_visited=average_agent(
                "unique_positions_visited"
            ),
            average_movement_steps=average_agent("movement_steps"),
            average_idle_steps=average_agent("idle_steps"),
            average_max_steps_without_food=average_agent(
                "max_steps_without_food"
            ),

            average_final_plant_count=sum(
                result.final_plant_count for result in self.results
            ) / total,

            average_seeds_spawned=sum(
                result.seeds_spawned for result in self.results
            ) / total,

            average_step_reached_plant_limit=(
                sum(reached_limit) / len(reached_limit)
                if reached_limit
                else 0.0
            ),

            average_agent_lifetime_steps=average_agent("agent_lifetime_steps"),
            
            runs_reached_plant_limit=len(reached_limit),
        )


    def _run_simulation_task(
        self,
        task: tuple[
            SimulationConfig,
            int,
            int,
            Scenario | None,
            int,
            int,
        ],
    ) -> SimulationRunResult:
        (
            config,
            run_seed,
            max_steps,
            scenario,
            seed_spawn_count,
            max_plants,
        ) = task

        return run_single_simulation(
            config=config,
            run_seed=run_seed,
            max_steps=max_steps,
            scenario=scenario,
            seed_spawn_count=seed_spawn_count,
            max_plants=max_plants,
        )
