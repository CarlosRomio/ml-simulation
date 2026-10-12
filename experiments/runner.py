
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from math import sqrt

from agents.factory import AgentFactory
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
    all_agent_metrics: list[SimulationMetrics] = field(default_factory=list)
    surviving_agents: int = 0
    total_agents: int = 1
    population_food_collected: int = 0
    blocked_movement_attempts: int = 0
    blocked_by_agent_attempts: int = 0
    blocked_by_environment_attempts: int = 0
    population_history: list[dict[str, int]] = field(default_factory=list)
    starvation_agents: int = 0

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
    agent_survival_rate: float = 1.0
    average_surviving_agents: float = 1.0
    average_population_food_collected: float = 0.0
    minimum_food_per_agent: float = 0.0
    maximum_food_per_agent: float = 0.0
    food_collection_stddev: float = 0.0
    average_starved_agents: float = 0.0
    average_final_health: float = 0.0
    average_final_hunger: float = 0.0
    average_final_thirst: float = 0.0
    average_water_drinks: float = 0.0
    average_water_units_consumed: float = 0.0
    average_deaths_by_dehydration: float = 0.0
    average_deaths_by_starvation: float = 0.0
    average_blocked_movement_attempts: float = 0.0
    average_blocked_by_agent_attempts: float = 0.0
    average_blocked_by_environment_attempts: float = 0.0
    average_population_alive_by_step: list[float] = field(default_factory=list)

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
            water_count=config.water_count,
            reserved_cells={(start_x, start_y)},
            rng=rng,
        )
    else:
        world = scenario.to_world()
        world.rng = random.Random(run_seed + 1_000_000)
        start_x, start_y = scenario.start_position

    agents = AgentFactory.create_agents(
        world=world,
        count=config.agent_count,
        vision_radius=config.vision_radius,
        preferred_position=(start_x, start_y),
        seed=run_seed + 2_000_000,
    )

    simulation = Simulation(
        world=world,
        agents=agents,
        seed_spawn_count=seed_spawn_count,
        max_plants=max_plants,
        rng=random.Random(run_seed + 3_000_000),
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

    all_metrics = [simulation.metrics_by_agent[id(agent)] for agent in simulation.agents]
    surviving_agents = sum(agent.alive for agent in simulation.agents)
    return SimulationRunResult(
        agent_metrics=simulation.metrics,
        final_plant_count=plant_counts["total"],
        seeds_spawned=sum(simulation.seeds_spawned_history),
        step_reached_plant_limit=limit_step,
        all_agent_metrics=all_metrics,
        surviving_agents=surviving_agents,
        total_agents=len(simulation.agents),
        population_food_collected=sum(m.food_collected for m in all_metrics),
        blocked_movement_attempts=simulation.blocked_movement_attempts,
        blocked_by_agent_attempts=simulation.blocked_by_agent_attempts,
        blocked_by_environment_attempts=simulation.blocked_by_environment_attempts,
        population_history=list(simulation.population_history),
        starvation_agents=sum(not agent.alive for agent in simulation.agents),
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

        # Uma execução sobrevive se pelo menos um agente chegar ao limite;
        # só é considerada inanição quando todos os agentes morrerem.
        def surviving_count(result: SimulationRunResult) -> int:
            if result.all_agent_metrics:
                return result.surviving_agents
            return int(result.agent_metrics.termination_cause == "STEP_LIMIT")

        survived = sum(surviving_count(result) > 0 for result in self.results)
        starvation = total - survived

        def metrics_for_result(result: SimulationRunResult) -> list[SimulationMetrics]:
            # Mantém compatibilidade com resultados construídos em testes antigos.
            return result.all_agent_metrics or [result.agent_metrics]

        all_metrics = [
            metrics for result in self.results for metrics in metrics_for_result(result)
        ]

        def average_agent(attribute: str) -> float:
            return sum(getattr(metrics, attribute) for metrics in all_metrics) / len(all_metrics)

        food_counts = [metrics.food_collected for metrics in all_metrics]
        food_mean = sum(food_counts) / len(food_counts)
        food_stddev = sqrt(sum((value - food_mean) ** 2 for value in food_counts) / len(food_counts))
        population_histories = [result.population_history for result in self.results if result.population_history]
        average_alive_by_step: list[float] = []
        if population_histories:
            history_length = min(len(history) for history in population_histories)
            average_alive_by_step = [
                sum(history[step_index]["alive"] for history in population_histories) / len(population_histories)
                for step_index in range(history_length)
            ]

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
            agent_survival_rate=(
                sum(surviving_count(result) for result in self.results)
                / sum((result.total_agents if result.all_agent_metrics else 1) for result in self.results)
                if sum((result.total_agents if result.all_agent_metrics else 1) for result in self.results) > 0
                else 0.0
            ),
            average_surviving_agents=(
                sum(surviving_count(result) for result in self.results) / total
            ),
            average_population_food_collected=(
                sum((result.population_food_collected if result.all_agent_metrics else result.agent_metrics.food_collected) for result in self.results) / total
            ),
            minimum_food_per_agent=min(food_counts),
            maximum_food_per_agent=max(food_counts),
            food_collection_stddev=food_stddev,
            average_starved_agents=sum(result.starvation_agents if result.all_agent_metrics else int(result.agent_metrics.termination_cause == "STARVATION") for result in self.results) / total,
            average_final_health=average_agent("final_health"),
            average_final_hunger=average_agent("final_hunger"),
            average_final_thirst=average_agent("final_thirst"),
            average_water_drinks=average_agent("water_drinks"),
            average_water_units_consumed=average_agent("water_units_consumed"),
            average_deaths_by_dehydration=sum(
                m.termination_cause == "DEHYDRATION" for m in all_metrics
            ) / total,
            average_deaths_by_starvation=sum(
                m.termination_cause == "STARVATION" for m in all_metrics
            ) / total,
            average_blocked_movement_attempts=sum(result.blocked_movement_attempts for result in self.results) / total,
            average_blocked_by_agent_attempts=sum(result.blocked_by_agent_attempts for result in self.results) / total,
            average_blocked_by_environment_attempts=sum(result.blocked_by_environment_attempts for result in self.results) / total,
            average_population_alive_by_step=average_alive_by_step,
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
