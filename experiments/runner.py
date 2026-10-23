
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from math import sqrt

from agents.factory import AgentFactory
from animals.factory import HerbivoreFactory, CarnivoreFactory
from configuration.simulation_config import SimulationConfig
from environment.world import World
from environment.resources import MaterialKind
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
    population_history: list[dict[str, int | float]] = field(default_factory=list)
    ecology_history: list[dict[str, int | float]] = field(default_factory=list)
    human_physiology_history: list[list[dict]] = field(default_factory=list)
    physiology_activity_history: list[dict[str, object]] = field(default_factory=list)
    carnivore_hunt_history: list[dict[str, object]] = field(default_factory=list)
    reproduction_events: list[dict[str, object]] = field(default_factory=list)
    reproduction_diagnostics: list[dict[str, object]] = field(default_factory=list)
    agent_ids: list[str] = field(default_factory=list)
    social_history: list[dict[str, object]] = field(default_factory=list)
    social_agent_history: list[dict[str, object]] = field(default_factory=list)
    social_decision_history: list[dict[str, object]] = field(default_factory=list)
    starvation_agents: int = 0
    living_herbivores: int = 0
    living_carnivores: int = 0
    human_hunt_attacks: int = 0
    carnivore_attacks: int = 0
    herbivores_killed: int = 0
    humans_killed_by_carnivores: int = 0
    human_defense_attacks: int = 0
    carnivores_killed: int = 0
    herbivores_died_by_starvation: int = 0
    herbivores_died_by_dehydration: int = 0
    carnivores_died_by_starvation: int = 0
    carnivores_died_by_dehydration: int = 0
    initial_individual_states: list[dict[str, object]] = field(default_factory=list)

@dataclass
class ExperimentSummary:
    """Resumo agregado. starvation_runs é legado e significa extinção total da execução.

    Para mortes individuais por fome, consulte average_deaths_by_starvation.
    """
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
    extinction_runs: int = 0
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
    max_plants: int | None = None,
    social_behavior_enabled: bool = True,
    social_memory_enabled: bool = True,
) -> SimulationRunResult:
    """Executa uma simulação e retorna métricas do agente e do ambiente."""
    config.validate()
    if max_plants is None:
        max_plants = config.max_plants_capacity
    elif max_plants < 0:
        raise ValueError("max_plants não pode ser negativo.")

    rng = random.Random(run_seed)

    if scenario is None:
        start_x, start_y = config.start_position

        world = World(
            width=config.width,
            height=config.height,
            food_count=config.food_count,
            obstacle_count=config.obstacle_count,
            water_count=config.water_count,
            wood_count=config.wood_count,
            stone_count=config.stone_count,
            reserved_cells={(start_x, start_y)},
            rng=rng,
        )
        world.place_storage(start_x, start_y)
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
        hunger_per_step=config.hunger_per_step,
        thirst_per_step=config.thirst_per_step,
        starvation_threshold=config.starvation_threshold,
        dehydration_threshold=config.dehydration_threshold,
        starvation_damage_per_step=config.starvation_damage_per_step,
        dehydration_damage_per_step=config.dehydration_damage_per_step,
        attribute_variation=config.attribute_variation,
    )

    occupied_positions = {(agent.x, agent.y) for agent in agents}
    herbivores = HerbivoreFactory.create(
        world=world,
        count=config.herbivore_count,
        vision_radius=config.vision_radius,
        seed=run_seed + 4_000_000,
        occupied_positions=occupied_positions,
        attribute_variation=config.attribute_variation,
    )
    occupied_positions.update((animal.x, animal.y) for animal in herbivores)
    carnivores = CarnivoreFactory.create(
        world=world,
        count=config.carnivore_count,
        vision_radius=config.vision_radius,
        seed=run_seed + 5_000_000,
        occupied_positions=occupied_positions,
        attribute_variation=config.attribute_variation,
    )

    simulation = Simulation(
        world=world,
        agents=agents,
        herbivores=herbivores,
        carnivores=carnivores,
        seed_spawn_count=seed_spawn_count,
        max_plants=max_plants,
        rng=random.Random(run_seed + 3_000_000),
        social_behavior_enabled=social_behavior_enabled,
        social_memory_enabled=social_memory_enabled,
    )
    initial_individual_states: list[dict[str, object]] = []
    for index, individual in enumerate(simulation.agents, start=1):
        initial_individual_states.append({
            "individual_type": "HUMAN",
            "individual_id": individual.agent_id or f"H{index:03d}",
            "sex": individual.life_history.sex, "age_steps": individual.life_history.age_steps,
            "generation": individual.life_history.generation,
            "x": individual.x, "y": individual.y,
            "health": individual.health, "hunger": individual.hunger,
            "thirst": individual.thirst, "stamina": individual.energy,
            "fatigue": individual.needs.fatigue, "is_sleeping": individual.is_sleeping,
            **{f"attribute_{name}": value for name, value in individual.attributes.to_dict().items()},
            **{f"gene_{name}": value for name, value in individual.genotype.to_dict().items()},
        })
    for index, individual in enumerate(simulation.herbivores, start=1):
        initial_individual_states.append({
            "individual_type": "HERBIVORE", "individual_id": individual.life_history.individual_id,
            "sex": individual.life_history.sex, "age_steps": individual.life_history.age_steps,
            "generation": individual.life_history.generation,
            "x": individual.x, "y": individual.y,
            "health": individual.health, "hunger": individual.hunger,
            "thirst": individual.thirst, "stamina": individual.energy,
            "fatigue": individual.needs.fatigue, "is_sleeping": individual.is_sleeping,
            **{f"attribute_{name}": value for name, value in individual.attributes.to_dict().items()},
            **{f"gene_{name}": value for name, value in individual.genotype.to_dict().items()},
        })
    for index, individual in enumerate(simulation.carnivores, start=1):
        initial_individual_states.append({
            "individual_type": "CARNIVORE", "individual_id": individual.life_history.individual_id,
            "sex": individual.life_history.sex, "age_steps": individual.life_history.age_steps,
            "generation": individual.life_history.generation,
            "x": individual.x, "y": individual.y,
            "health": individual.health, "hunger": individual.hunger,
            "thirst": individual.thirst, "stamina": individual.energy,
            "fatigue": individual.needs.fatigue, "is_sleeping": individual.is_sleeping,
            **{f"attribute_{name}": value for name, value in individual.attributes.to_dict().items()},
            **{f"gene_{name}": value for name, value in individual.genotype.to_dict().items()},
        })

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
        ecology_history=list(simulation.ecology_history),
        agent_ids=[agent.agent_id for agent in simulation.agents],
        social_history=list(simulation.social_history),
        social_agent_history=list(simulation.social_agent_history),
        social_decision_history=list(simulation.social_decision_history),
        physiology_activity_history=list(simulation.physiology_activity_history),
        carnivore_hunt_history=list(simulation.carnivore_hunt_history),
        reproduction_events=list(simulation.reproduction_events),
        reproduction_diagnostics=list(simulation.reproduction.diagnostics),
        human_physiology_history=[
            [{
                "step": 0,
                "position_before": simulation.position_history_by_agent[id(agent)][0],
                "position_after": simulation.position_history_by_agent[id(agent)][0],
                "action": (0, 0), "moved": False, "distance": 0.0,
                "health_before": simulation.metrics_by_agent[id(agent)].initial_health,
                "health_after_physiology": simulation.metrics_by_agent[id(agent)].initial_health,
                "health_after": simulation.metrics_by_agent[id(agent)].initial_health,
                "energy_before": simulation.metrics_by_agent[id(agent)].initial_energy,
                "energy_after_actions": simulation.metrics_by_agent[id(agent)].initial_energy,
                "energy_after": simulation.metrics_by_agent[id(agent)].initial_energy,
                "movement_energy_cost": 0.0, "food_energy_recovered": 0.0,
                "rest_energy_recovered": 0.0, "energy_change_after_combat": 0.0,
                "hunger_before": simulation.metrics_by_agent[id(agent)].initial_hunger,
                "hunger_after_physiology": simulation.metrics_by_agent[id(agent)].initial_hunger,
                "hunger_after": simulation.metrics_by_agent[id(agent)].initial_hunger,
                "thirst_before": simulation.metrics_by_agent[id(agent)].initial_thirst,
                "thirst_after_physiology": simulation.metrics_by_agent[id(agent)].initial_thirst,
                "thirst_after": simulation.metrics_by_agent[id(agent)].initial_thirst,
                "collected_food": False, "collected_food_quantity": 0.0,
                "collected_resource_type": "NONE", "behavior_intent": "INITIAL",
                "inventory_weight": agent.inventory.current_weight,
                "inventory_food": agent.inventory.food_quantity,
                "food_consumed": 0.0,
                "storage_food_deposited": 0.0,
                "storage_food_withdrawn": 0.0,
                "inventory_wood": agent.inventory.quantity_of(MaterialKind.WOOD),
                "inventory_stone": agent.inventory.quantity_of(MaterialKind.STONE),
                "inventory_fiber": agent.inventory.quantity_of(MaterialKind.FIBER),
                "drank_water": False, "water_thirst_reduction": 0.0,
                "damage_causes": [], "damage_by_cause": {},
                "termination_cause": "RUNNING",
            }] + list(simulation.diagnostic_history_by_agent[id(agent)])
            for agent in simulation.agents
        ],
        starvation_agents=sum(
            simulation.metrics_by_agent[id(agent)].termination_cause
            in {"STARVATION", "STARVATION_AND_DEHYDRATION"}
            for agent in simulation.agents
        ),
        living_herbivores=len(simulation.alive_herbivores),
        living_carnivores=len(simulation.alive_carnivores),
        human_hunt_attacks=simulation.attacks,
        carnivore_attacks=simulation.carnivore_attacks,
        herbivores_killed=simulation.animals_killed,
        humans_killed_by_carnivores=simulation.humans_killed_by_carnivores,
        human_defense_attacks=simulation.human_defense_attacks,
        carnivores_killed=simulation.carnivores_killed,
        herbivores_died_by_starvation=simulation.herbivores_died_by_starvation,
        herbivores_died_by_dehydration=simulation.herbivores_died_by_dehydration,
        carnivores_died_by_starvation=simulation.carnivores_died_by_starvation,
        carnivores_died_by_dehydration=simulation.carnivores_died_by_dehydration,
        initial_individual_states=initial_individual_states,
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
        max_plants: int | None = None,
    ):
        if runs <= 0:
            raise ValueError("O número de execuções deve ser positivo.")

        if max_steps <= 0:
            raise ValueError("O limite de passos deve ser positivo.")

        if max_workers <= 0:
            raise ValueError("max_workers deve ser positivo.")

        if seed_spawn_count < 0:
            raise ValueError("seed_spawn_count não pode ser negativo.")

        config.validate()
        if max_plants is None:
            max_plants = config.max_plants_capacity
        elif max_plants < 0:
            raise ValueError("max_plants não pode ser negativo.")

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
            extinction_runs=starvation,
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
            average_starved_agents=sum(result.starvation_agents if result.all_agent_metrics else int(result.agent_metrics.termination_cause in {"STARVATION", "STARVATION_AND_DEHYDRATION"}) for result in self.results) / total,
            average_final_health=average_agent("final_health"),
            average_final_hunger=average_agent("final_hunger"),
            average_final_thirst=average_agent("final_thirst"),
            average_water_drinks=average_agent("water_drinks"),
            average_water_units_consumed=average_agent("water_units_consumed"),
            average_deaths_by_dehydration=sum(
                m.termination_cause in {"DEHYDRATION", "STARVATION_AND_DEHYDRATION"} for m in all_metrics
            ) / total,
            average_deaths_by_starvation=sum(
                m.termination_cause in {"STARVATION", "STARVATION_AND_DEHYDRATION"} for m in all_metrics
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
