"""Experimento reprodutível para calibrar sono, estamina, corrida e metabolismo.

Executar: py -3.13 run_physiology_experiment.py
Gera CSVs em results/physiology_calibration/.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean
import time

from configuration.simulation_config import SimulationConfig
from experiments.runner import run_single_simulation

OUTPUT_DIR = Path("results/physiology_calibration")
RUNS = 8
MAX_STEPS = 900  # 15 horas simuladas por execução
BASE_SEED = 6100


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = SimulationConfig(
        width=30, height=30, food_density=0.07, obstacle_density=0.01,
        water_density=0.02, wood_density=0.01, stone_density=0.01,
        agent_count=4, herbivore_count=8, carnivore_count=2, vision_radius=6,
    )
    config.validate()
    started = time.perf_counter()
    results = [
        run_single_simulation(config, run_seed=BASE_SEED + i, max_steps=MAX_STEPS,
                             seed_spawn_count=1, max_plants=100)
        for i in range(RUNS)
    ]
    elapsed = time.perf_counter() - started

    run_rows: list[dict] = []
    activity_rows: list[dict] = []
    activity_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for run_index, result in enumerate(results, start=1):
        human_metrics = result.all_agent_metrics
        activity = result.physiology_activity_history
        dead_records = [r for r in activity if float(r.get("health_after", 1) or 0) <= 0]
        def animal_deaths(individual_type: str, cause: str) -> int:
            return sum(
                r.get("individual_type") == individual_type
                and cause in str(r.get("damage_causes", "")).split(";")
                for r in dead_records
            )
        run_rows.append({
            "run": run_index, "seed": BASE_SEED + run_index - 1,
            "steps": MAX_STEPS, "simulated_hours": MAX_STEPS / 60,
            "humans_initial": result.total_agents,
            "humans_alive_final": result.surviving_agents,
            "human_survival_rate": result.surviving_agents / result.total_agents if result.total_agents else 0,
            "human_deaths_predation": sum(m.termination_cause == "PREDATION" for m in human_metrics),
            "human_deaths_starvation": sum(m.termination_cause in {"STARVATION", "STARVATION_AND_DEHYDRATION"} for m in human_metrics),
            "human_deaths_dehydration": sum(m.termination_cause in {"DEHYDRATION", "STARVATION_AND_DEHYDRATION"} for m in human_metrics),
            "mean_final_stamina_all_humans": mean(m.final_energy for m in human_metrics) if human_metrics else 0,
            "mean_final_hunger_all_humans": mean(m.final_hunger for m in human_metrics) if human_metrics else 0,
            "mean_final_thirst_all_humans": mean(m.final_thirst for m in human_metrics) if human_metrics else 0,
            "herbivores_alive_final": result.living_herbivores,
            "herbivore_deaths_hunting": animal_deaths("HERBIVORE", "HUNTING"),
            "herbivore_deaths_predation": animal_deaths("HERBIVORE", "PREDATION"),
            "herbivore_deaths_starvation": animal_deaths("HERBIVORE", "STARVATION"),
            "herbivore_deaths_dehydration": animal_deaths("HERBIVORE", "DEHYDRATION"),
            "carnivores_alive_final": result.living_carnivores,
            "carnivore_deaths_starvation": animal_deaths("CARNIVORE", "STARVATION"),
            "carnivore_deaths_dehydration": animal_deaths("CARNIVORE", "DEHYDRATION"),
            "carnivore_deaths_defense": animal_deaths("CARNIVORE", "DEFENSE"),
            "activity_rows": len(activity),
            "sleep_steps": sum(r.get("activity") == "SLEEPING" for r in activity),
            "run_steps": sum(r.get("activity") == "RUNNING" for r in activity),
            "rest_steps": sum(r.get("activity") == "RESTING" for r in activity),
            "sleep_interruptions_hunger": sum(r.get("sleep_interruption_reason") == "HUNGER" for r in activity),
            "sleep_interruptions_thirst": sum(r.get("sleep_interruption_reason") == "THIRST" for r in activity),
            "sleep_interruptions_predator": sum(r.get("sleep_interruption_reason") == "PREDATOR_NEARBY" for r in activity),
        })
        for record in activity:
            row = {"run": run_index, "seed": BASE_SEED + run_index - 1, **record}
            activity_rows.append(row)
            activity_groups[(str(record.get("individual_type", "")), str(record.get("activity", "")))].append(record)

    summary_rows = []
    for (individual_type, activity), records in sorted(activity_groups.items()):
        def avg(field: str) -> float:
            values = [float(r[field]) for r in records if r.get(field) not in (None, "")]
            return mean(values) if values else 0.0
        summary_rows.append({
            "individual_type": individual_type, "activity": activity,
            "observations": len(records),
            "mean_distance_per_step": avg("distance"),
            "mean_stamina_spent_movement": avg("stamina_spent_movement"),
            "mean_stamina_spent_combat": avg("stamina_spent_combat"),
            "mean_stamina_recovered": avg("stamina_recovered_rest"),
            "mean_hunger_metabolic_cost": avg("hunger_metabolic_cost"),
            "mean_thirst_metabolic_cost": avg("thirst_metabolic_cost"),
            "mean_fatigue_before": avg("fatigue_before"),
            "mean_fatigue_after": avg("fatigue_after"),
            "mean_fatigue_delta": avg("fatigue_after") - avg("fatigue_before"),
            "mean_hunger_delta": avg("hunger_after") - avg("hunger_before"),
            "mean_thirst_delta": avg("thirst_after") - avg("thirst_before"),
            "deaths_observed": sum(bool(r.get("damage_causes")) and float(r.get("health_after", 1)) <= 0 for r in records),
        })

    write_csv(OUTPUT_DIR / "runs.csv", run_rows)
    write_csv(OUTPUT_DIR / "activity_history.csv", activity_rows)
    write_csv(OUTPUT_DIR / "activity_summary.csv", summary_rows)

    total_humans = sum(row["humans_initial"] for row in run_rows)
    survivors = sum(row["humans_alive_final"] for row in run_rows)
    print("=== Experimento de calibração fisiológica ===")
    print(f"Execuções: {RUNS} x {MAX_STEPS} passos ({MAX_STEPS / 60:.1f} horas simuladas cada)")
    print(f"Sobrevivência humana: {survivors}/{total_humans} ({survivors / total_humans:.1%})")
    print(f"Mortes humanas por fome: {sum(r['human_deaths_starvation'] for r in run_rows)}")
    print(f"Mortes humanas por sede: {sum(r['human_deaths_dehydration'] for r in run_rows)}")
    print(f"Mortes de herbívoros por caça humana/predação/fome/sede: "
          f"{sum(r['herbivore_deaths_hunting'] for r in run_rows)}/"
          f"{sum(r['herbivore_deaths_predation'] for r in run_rows)}/"
          f"{sum(r['herbivore_deaths_starvation'] for r in run_rows)}/"
          f"{sum(r['herbivore_deaths_dehydration'] for r in run_rows)}")
    print(f"Mortes de carnívoros por defesa/fome/sede: "
          f"{sum(r['carnivore_deaths_defense'] for r in run_rows)}/"
          f"{sum(r['carnivore_deaths_starvation'] for r in run_rows)}/"
          f"{sum(r['carnivore_deaths_dehydration'] for r in run_rows)}")
    print(f"Passos em sono: {sum(r['sleep_steps'] for r in run_rows)}")
    print(f"Passos em corrida: {sum(r['run_steps'] for r in run_rows)}")
    print(f"Passos em descanso: {sum(r['rest_steps'] for r in run_rows)}")
    print(f"Linhas fisiológicas registradas: {len(activity_rows)}")
    print(f"CSV gerados em: {OUTPUT_DIR.resolve()}")
    print(f"Tempo de execução: {elapsed:.2f}s")
    print("Resumo por espécie e atividade:")
    for row in summary_rows:
        print(f"  {row['individual_type']:9s} {row['activity']:8s} n={row['observations']:6d} "
              f"dist={row['mean_distance_per_step']:.2f} stamina(-move/-combat/+)=({row['mean_stamina_spent_movement']:.2f}/{row['mean_stamina_spent_combat']:.2f}/{row['mean_stamina_recovered']:.2f}) "
              f"fatigue Δ={row['mean_fatigue_delta']:+.3f} hunger Δ={row['mean_hunger_delta']:+.3f}")


if __name__ == "__main__":
    main()
