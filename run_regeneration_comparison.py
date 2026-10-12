"""Comparação controlada da regeneração de plantas.

O cenário, as sementes aleatórias e o horizonte são mantidos iguais entre
tratamentos. A única variável experimental alterada é seed_spawn_count.

Os itens iniciais do cenário são Food estáticos (não Plant); eles são iguais
em todos os tratamentos e funcionam como estoque inicial de alimento. O limite
max_plants aplica-se apenas às entidades Plant geradas pelo ciclo ecológico.
"""

import csv
import random
from pathlib import Path
from statistics import mean

from configuration.simulation_config import SimulationConfig
from environment.obstacles import ObstacleType
from experiments.runner import ExperimentRunner, SimulationRunResult
from scenarios.scenario import Scenario

SEED = 42
RUNS = 20
MAX_STEPS = 300
MAX_PLANTS = 100
MAX_WORKERS = 4

REGENERATION_RATES = [0, 1, 2]

WIDTH = 30
HEIGHT = 30
START_POSITION = (15, 15)
INITIAL_FOOD_ITEMS = 18
INITIAL_WATER_SOURCES = 18
INITIAL_MATURE_PLANTS = 54
OBSTACLE_COUNT = 9
INITIAL_HUMANS = 5
INITIAL_HERBIVORES = 8
INITIAL_CARNIVORES = 3

OUTPUT_DIR = Path("results") / "regeneration_comparison"
SUMMARY_PATH = OUTPUT_DIR / "regeneration_comparison.csv"
DETAILS_PATH = OUTPUT_DIR / "regeneration_runs.csv"
HISTORY_PATH = OUTPUT_DIR / "regeneration_ecology_history.csv"


def create_fixed_scenario() -> Scenario:
    """Cria cenário espacial determinístico, idêntico entre tratamentos."""
    rng = random.Random(SEED)
    positions = [
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if (x, y) != START_POSITION
    ]
    food_positions = rng.sample(positions, INITIAL_FOOD_ITEMS)
    food_set = set(food_positions)
    remaining_positions = [p for p in positions if p not in food_set]
    obstacle_positions = rng.sample(remaining_positions, OBSTACLE_COUNT)
    obstacle_set = set(obstacle_positions)
    water_candidates = [p for p in remaining_positions if p not in obstacle_set]
    water_positions = rng.sample(water_candidates, INITIAL_WATER_SOURCES)
    water_set = set(water_positions)
    plant_candidates = [
        p for p in remaining_positions
        if p not in obstacle_set and p not in water_set
    ]
    plant_positions = rng.sample(plant_candidates, INITIAL_MATURE_PLANTS)
    obstacle_types = list(ObstacleType)

    return Scenario(
        width=WIDTH,
        height=HEIGHT,
        food_positions=tuple((x, y, 1.0) for x, y in food_positions),
        obstacle_positions=tuple(
            (x, y, rng.choice(obstacle_types)) for x, y in obstacle_positions
        ),
        start_position=START_POSITION,
        seed=SEED,
        water_positions=tuple(water_positions),
        plant_positions=tuple(plant_positions),
    )


def _sum_history(results: list[SimulationRunResult], key: str) -> int:
    return sum(
        int(row.get(key, 0))
        for result in results
        for row in result.ecology_history
    )


def _average_history_value(
    results: list[SimulationRunResult], key: str
) -> float:
    per_run_means = [
        mean(float(row.get(key, 0)) for row in result.ecology_history)
        for result in results
        if result.ecology_history
    ]
    return mean(per_run_means) if per_run_means else 0.0


def build_summary_row(rate: int, results: list[SimulationRunResult]) -> dict:
    """Resume efeitos ecológicos primários e métricas de sobrevivência secundárias."""
    total_runs = len(results)
    saturation_steps = [
        result.step_reached_plant_limit
        for result in results
        if result.step_reached_plant_limit is not None
    ]
    final_counts = [result.final_plant_count for result in results]
    requested = _sum_history(results, "seeds_spawn_requested")
    spawned = _sum_history(results, "seeds_spawned")

    return {
        "seed_spawn_count": rate,
        "runs": total_runs,
        "max_steps": MAX_STEPS,
        "max_plants": MAX_PLANTS,
        "fixed_initial_food_items": INITIAL_FOOD_ITEMS,
        "fixed_initial_water_sources": INITIAL_WATER_SOURCES,
        "fixed_initial_mature_plants": INITIAL_MATURE_PLANTS,
        "initial_humans": INITIAL_HUMANS,
        "initial_herbivores": INITIAL_HERBIVORES,
        "initial_carnivores": INITIAL_CARNIVORES,
        "human_agent_survival_rate_secondary": (
            sum(result.surviving_agents for result in results)
            / sum(result.total_agents for result in results)
            if results and sum(result.total_agents for result in results) else 0.0
        ),
        "mean_surviving_humans": mean(result.surviving_agents for result in results),
        "mean_final_herbivores": mean(result.living_herbivores for result in results),
        "mean_final_carnivores": mean(result.living_carnivores for result in results),
        "mean_human_lifetime_steps": mean(
            metrics.agent_lifetime_steps
            for result in results
            for metrics in result.all_agent_metrics
        ),
        "mean_population_food_collected": mean(
            result.population_food_collected for result in results
        ),
        "mean_food_collected_per_human": mean(
            metrics.food_collected
            for result in results
            for metrics in result.all_agent_metrics
        ),
        "mean_final_human_hunger": mean(
            metrics.final_hunger
            for result in results
            for metrics in result.all_agent_metrics
        ),
        "mean_final_human_thirst": mean(
            metrics.final_thirst
            for result in results
            for metrics in result.all_agent_metrics
        ),
        "mean_final_human_energy": mean(
            metrics.final_energy
            for result in results
            for metrics in result.all_agent_metrics
        ),
        "mean_final_plant_count": mean(final_counts),
        "min_final_plant_count": min(final_counts),
        "max_final_plant_count": max(final_counts),
        "mean_plant_count_over_time": _average_history_value(results, "total"),
        "runs_reaching_plant_cap": len(saturation_steps),
        "fraction_runs_reaching_plant_cap": len(saturation_steps) / total_runs if total_runs else 0.0,
        "mean_step_reaching_plant_cap": mean(saturation_steps) if saturation_steps else "",
        "seed_spawn_requests_total": requested,
        "seeds_spawned_total": spawned,
        "seed_spawn_success_rate": spawned / requested if requested else 0.0,
        "seeds_blocked_by_plant_cap_total": _sum_history(results, "seeds_blocked_by_plant_cap"),
        "seeds_blocked_by_space_total": _sum_history(results, "seeds_blocked_by_space"),
        "seed_to_growing_total": _sum_history(results, "plants_seed_to_growing"),
        "growing_to_mature_total": _sum_history(results, "plants_growing_to_mature"),
        "plants_collected_by_humans_total": _sum_history(results, "plants_collected_by_humans"),
        "plants_collected_by_herbivores_total": _sum_history(results, "plants_collected_by_herbivores"),
    }


def build_detail_row(rate: int, index: int, result: SimulationRunResult) -> dict:
    history = result.ecology_history
    metrics = result.agent_metrics
    return {
        "seed_spawn_count": rate,
        "run": index + 1,
        "run_seed": SEED + index,
        "termination_cause_secondary": metrics.termination_cause,
        "first_human_lifetime_steps": metrics.agent_lifetime_steps,
        "first_human_food_collected": metrics.food_collected,
        "population_food_collected": result.population_food_collected,
        "mean_food_collected_per_human": mean(
            item.food_collected for item in result.all_agent_metrics
        ),
        "mean_final_human_hunger": mean(
            item.final_hunger for item in result.all_agent_metrics
        ),
        "mean_final_human_thirst": mean(
            item.final_thirst for item in result.all_agent_metrics
        ),
        "mean_final_human_energy": mean(
            item.final_energy for item in result.all_agent_metrics
        ),
        "mean_human_lifetime_steps": mean(
            item.agent_lifetime_steps for item in result.all_agent_metrics
        ),
        "final_plant_count": result.final_plant_count,
        "surviving_humans": result.surviving_agents,
        "living_herbivores": result.living_herbivores,
        "living_carnivores": result.living_carnivores,
        "seeds_requested": sum(int(row.get("seeds_spawn_requested", 0)) for row in history),
        "seeds_spawned": result.seeds_spawned,
        "seeds_blocked_by_plant_cap": sum(int(row.get("seeds_blocked_by_plant_cap", 0)) for row in history),
        "seeds_blocked_by_space": sum(int(row.get("seeds_blocked_by_space", 0)) for row in history),
        "plants_collected_by_humans": sum(int(row.get("plants_collected_by_humans", 0)) for row in history),
        "plants_collected_by_herbivores": sum(int(row.get("plants_collected_by_herbivores", 0)) for row in history),
        "step_reached_plant_cap": result.step_reached_plant_limit if result.step_reached_plant_limit is not None else "",
        "mean_plant_count": mean(float(row.get("total", 0)) for row in history) if history else 0.0,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scenario = create_fixed_scenario()
    config = SimulationConfig(
        width=WIDTH,
        height=HEIGHT,
        food_density=0.0,
        obstacle_density=0.0,
        agent_count=INITIAL_HUMANS,
        herbivore_count=INITIAL_HERBIVORES,
        carnivore_count=INITIAL_CARNIVORES,
    )

    summary_rows: list[dict] = []
    detail_rows: list[dict] = []
    history_rows: list[dict] = []

    for rate in REGENERATION_RATES:
        print(
            f"\nRegeneração: {rate} sementes/atualização; "
            f"{RUNS} execuções pareadas; {MAX_STEPS} passos; "
            f"{INITIAL_HUMANS} humanos, {INITIAL_HERBIVORES} herbívoros, "
            f"{INITIAL_CARNIVORES} carnívoros; {INITIAL_MATURE_PLANTS} plantas maduras iniciais; "
            f"{MAX_WORKERS} processos",
            flush=True,
        )
        runner = ExperimentRunner(
            config=config,
            runs=RUNS,
            max_steps=MAX_STEPS,
            seed=SEED,
            max_workers=MAX_WORKERS,
            scenario=scenario,
            seed_spawn_count=rate,
            max_plants=MAX_PLANTS,
        )
        results = runner.run()
        summary = build_summary_row(rate, results)
        summary_rows.append(summary)

        for index, result in enumerate(results):
            detail_rows.append(build_detail_row(rate, index, result))
            for row in result.ecology_history:
                history_rows.append({
                    "seed_spawn_count": rate,
                    "run": index + 1,
                    "run_seed": SEED + index,
                    **row,
                })

        print(
            f"  plantas finais médias: {summary['mean_final_plant_count']:.2f}; "
            f"criação/request: {summary['seed_spawn_success_rate']:.1%}; "
            f"coleta humana/herbívoros: "
            f"{summary['plants_collected_by_humans_total']}/"
            f"{summary['plants_collected_by_herbivores_total']}; "
            f"limite atingido: {summary['runs_reaching_plant_cap']}/{RUNS}; "
            f"passo médio do limite: {summary['mean_step_reaching_plant_cap']}",
            flush=True,
        )

    outputs = [
        (SUMMARY_PATH, summary_rows),
        (DETAILS_PATH, detail_rows),
        (HISTORY_PATH, history_rows),
    ]
    for path, rows in outputs:
        if not rows:
            continue
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    print("\nComparação concluída.")
    print(f"Resumo: {SUMMARY_PATH}")
    print(f"Execuções individuais: {DETAILS_PATH}")
    print(f"Histórico ecológico: {HISTORY_PATH}")


if __name__ == "__main__":
    main()
