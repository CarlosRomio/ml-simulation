
import csv
import random
from pathlib import Path

from configuration.simulation_config import SimulationConfig
from environment.obstacles import ObstacleType
from experiments.runner import ExperimentRunner
from scenarios.scenario import Scenario


SEED = 42
RUNS = 30
MAX_STEPS = 500
MAX_PLANTS = 100

REGENERATION_RATES = [0, 1, 2]

WIDTH = 30
HEIGHT = 30
START_POSITION = (15, 15)
INITIAL_PLANTS = 18
OBSTACLE_COUNT = 9

OUTPUT_DIR = Path("results")
SUMMARY_PATH = OUTPUT_DIR / "regeneration_comparison.csv"
DETAILS_PATH = OUTPUT_DIR / "regeneration_runs.csv"


def create_fixed_scenario() -> Scenario:
    """Cria uma configuração espacial reproduzível."""
    rng = random.Random(SEED)

    positions = [
        (x, y)
        for y in range(HEIGHT)
        for x in range(WIDTH)
        if (x, y) != START_POSITION
    ]

    plant_positions = rng.sample(positions, INITIAL_PLANTS)

    remaining_positions = [
        position
        for position in positions
        if position not in set(plant_positions)
    ]

    obstacle_positions = rng.sample(
        remaining_positions,
        OBSTACLE_COUNT,
    )

    obstacle_types = list(ObstacleType)

    return Scenario(
        width=WIDTH,
        height=HEIGHT,
        food_positions=tuple(
            (x, y, 1.0)
            for x, y in plant_positions
        ),
        obstacle_positions=tuple(
            (x, y, rng.choice(obstacle_types))
            for x, y in obstacle_positions
        ),
        start_position=START_POSITION,
        seed=SEED,
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    scenario = create_fixed_scenario()

    config = SimulationConfig(
        width=WIDTH,
        height=HEIGHT,
        food_density=0.0,
        obstacle_density=0.0,
    )

    summary_rows = []
    detail_rows = []

    for rate in REGENERATION_RATES:
        print(f"\nExecutando regeneração: {rate} sementes por atualização")

        runner = ExperimentRunner(
            config=config,
            runs=RUNS,
            max_steps=MAX_STEPS,
            seed=SEED,
            scenario=scenario,
            seed_spawn_count=rate,
            max_plants=MAX_PLANTS,
        )

        results = runner.run()
        summary = runner.summarize()

        summary_rows.append({
            "seed_spawn_count": rate,
            "total_runs": summary.total_runs,
            "survived_runs": summary.survived_runs,
            "starvation_runs": summary.starvation_runs,
            "survival_rate": summary.survival_rate,
            "average_steps": summary.average_steps,
            "average_food_collected": summary.average_food_collected,
            "average_energy": summary.average_energy,
            "average_final_plant_count": summary.average_final_plant_count,
            "average_seeds_spawned": summary.average_seeds_spawned,
            "runs_reached_plant_limit": summary.runs_reached_plant_limit,
            "average_step_reached_plant_limit": (
                summary.average_step_reached_plant_limit
            ),
            "average_agent_lifetime_steps": summary.average_agent_lifetime_steps,
        })

        for index, result in enumerate(results):
            metrics = result.agent_metrics

            detail_rows.append({
                "seed_spawn_count": rate,
                "run": index + 1,
                "run_seed": SEED + index,
                "termination_cause": metrics.termination_cause,
                "steps": metrics.steps,
                "food_collected": metrics.food_collected,
                "final_energy": metrics.final_energy,
                "final_plant_count": result.final_plant_count,
                "seeds_spawned": result.seeds_spawned,
                "step_reached_plant_limit": (
                    result.step_reached_plant_limit
                ),
                "agent_lifetime_steps": metrics.agent_lifetime_steps,
                "environment_steps": metrics.steps,
            })

        print(f"Sobrevivência: {summary.survival_rate:.1%}")
        print(f"Coleta média: {summary.average_food_collected:.2f}")
        print(
            "População final média: "
            f"{summary.average_final_plant_count:.2f}"
        )
        print(
            "Sementes geradas, em média: "
            f"{summary.average_seeds_spawned:.2f}"
        )
        print(
            "Execuções que atingiram o limite: "
            f"{summary.runs_reached_plant_limit}/{RUNS}"
        )

    with SUMMARY_PATH.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=summary_rows[0].keys(),
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    with DETAILS_PATH.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=detail_rows[0].keys(),
        )
        writer.writeheader()
        writer.writerows(detail_rows)

    print("\nExperimento concluído.")
    print(f"Resumo: {SUMMARY_PATH}")
    print(f"Resultados individuais: {DETAILS_PATH}")


if __name__ == "__main__":
    main()
