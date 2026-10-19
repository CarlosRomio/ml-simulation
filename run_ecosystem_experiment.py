"""Experimento reprodutível de interação entre humanos, herbívoros e carnívoros.

Executar: py -3.13 run_ecosystem_experiment.py

Além do resumo de console, grava CSVs auditáveis em results/ecosystem_experiment/:
- runs.csv: uma linha por execução;
- humans.csv: uma linha por humano em cada execução; `steps` e `simulated_time_seconds`
  são a duração observada do indivíduo; `experiment_steps` é a duração total da execução;
- population_history.csv: série temporal agregada por execução.
"""
from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from statistics import mean
import time

from configuration.simulation_config import SimulationConfig
from experiments.runner import SimulationRunResult, run_single_simulation

OUTPUT_DIR = Path("results/ecosystem_experiment")


def _mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _run_row(index: int, seed: int, result: SimulationRunResult) -> dict:
    metrics = result.all_agent_metrics or [result.agent_metrics]
    causes = [item.termination_cause for item in metrics]
    final_population = result.population_history[-1] if result.population_history else {}
    ecology = result.ecology_history
    ecology_sum = lambda key: sum(float(record.get(key, 0)) for record in ecology)
    return {
        "run": index,
        "seed": seed,
        "steps": result.agent_metrics.steps,
        "humans_initial": result.total_agents,
        "humans_alive_final": result.surviving_agents,
        "human_survival_rate": result.surviving_agents / result.total_agents if result.total_agents else 0.0,
        "human_deaths_predation": causes.count("PREDATION"),
        "human_deaths_starvation": sum(c in {"STARVATION", "STARVATION_AND_DEHYDRATION"} for c in causes),
        "human_deaths_dehydration": sum(c in {"DEHYDRATION", "STARVATION_AND_DEHYDRATION"} for c in causes),
        "human_deaths_both": causes.count("STARVATION_AND_DEHYDRATION"),
        "human_deaths_other": sum(c not in {"STEP_LIMIT", "RUNNING", "PREDATION", "STARVATION", "DEHYDRATION", "STARVATION_AND_DEHYDRATION"} for c in causes),
        # Cohort means include dead agents (whose final health is zero); this is
        # useful for whole-cohort accounting but must not be confused with survivors.
        "human_mean_final_health_all_cohort": _mean([m.final_health for m in metrics]),
        "human_mean_final_hunger_all_cohort": _mean([m.final_hunger for m in metrics]),
        "human_mean_final_thirst_all_cohort": _mean([m.final_thirst for m in metrics]),
        "human_mean_final_energy_all_cohort": _mean([m.final_energy for m in metrics]),
        "human_mean_final_health_survivors": _mean([m.final_health for m in metrics if m.final_health > 0]),
        "human_mean_final_hunger_survivors": _mean([m.final_hunger for m in metrics if m.final_health > 0]),
        "human_mean_final_thirst_survivors": _mean([m.final_thirst for m in metrics if m.final_health > 0]),
        "human_mean_final_energy_survivors": _mean([m.final_energy for m in metrics if m.final_health > 0]),
        "human_survivors_count_for_final_means": sum(m.final_health > 0 for m in metrics),
        "human_mean_health_over_time": _mean([m.average_health for m in metrics]),
        "human_mean_hunger_over_time": _mean([m.average_hunger for m in metrics]),
        "human_mean_thirst_over_time": _mean([m.average_thirst for m in metrics]),
        "human_food_collected": sum(m.food_collected for m in metrics),
        "human_food_consumed": sum(m.food_consumed for m in metrics),
        "human_water_drinks": sum(m.water_drinks for m in metrics),
        "human_water_thirst_reduction": sum(m.water_units_consumed for m in metrics),
        "human_distance_travelled": sum(m.distance_travelled for m in metrics),
        "human_steps_critical_hunger": sum(m.critical_hunger_steps for m in metrics),
        "human_steps_critical_thirst": sum(m.critical_thirst_steps for m in metrics),
        "herbivores_alive_final": result.living_herbivores,
        "herbivores_killed_by_humans": result.herbivores_killed,
        "herbivore_deaths_starvation": result.herbivores_died_by_starvation,
        "herbivore_deaths_dehydration": result.herbivores_died_by_dehydration,
        "carnivores_alive_final": result.living_carnivores,
        "carnivores_killed_by_humans": result.carnivores_killed,
        "carnivore_deaths_starvation": result.carnivores_died_by_starvation,
        "carnivore_deaths_dehydration": result.carnivores_died_by_dehydration,
        "human_hunt_attacks": result.human_hunt_attacks,
        "carnivore_attacks": result.carnivore_attacks,
        "human_defense_attacks": result.human_defense_attacks,
        "plants_final": result.final_plant_count,
        "wood_units_collected_by_humans": ecology_sum("wood_units_collected_by_humans"),
        "stone_units_collected_by_humans": ecology_sum("stone_units_collected_by_humans"),
        "fiber_units_collected_by_humans": ecology_sum("fiber_units_collected_by_humans"),
        "food_units_deposited_by_humans": ecology_sum("food_units_deposited_by_humans"),
        "food_units_withdrawn_by_humans": ecology_sum("food_units_withdrawn_by_humans"),
        "wood_units_deposited_by_humans": ecology_sum("wood_units_deposited_by_humans"),
        "stone_units_deposited_by_humans": ecology_sum("stone_units_deposited_by_humans"),
        "fiber_units_deposited_by_humans": ecology_sum("fiber_units_deposited_by_humans"),
        "storage_food_final": ecology[-1].get("storage_food_units", 0.0) if ecology else 0.0,
        "storage_wood_final": ecology[-1].get("storage_wood_units", 0.0) if ecology else 0.0,
        "storage_stone_final": ecology[-1].get("storage_stone_units", 0.0) if ecology else 0.0,
        "seeds_spawned": result.seeds_spawned,
        "plants_collected_by_humans": int(ecology_sum("plants_collected_by_humans")),
        "plants_collected_by_herbivores": int(ecology_sum("plants_collected_by_herbivores")),
        "plants_seed_to_growing": int(ecology_sum("plants_seed_to_growing")),
        "plants_growing_to_mature": int(ecology_sum("plants_growing_to_mature")),
        "seeds_spawn_requested": int(ecology_sum("seeds_spawn_requested")),
        "seeds_blocked_by_plant_cap": int(ecology_sum("seeds_blocked_by_plant_cap")),
        "seeds_blocked_by_space": int(ecology_sum("seeds_blocked_by_space")),
        "water_drinks_humans_observed": int(ecology_sum("water_drinks_humans")),
        "water_drinks_herbivores_observed": int(ecology_sum("water_drinks_herbivores")),
        "water_drinks_carnivores_observed": int(ecology_sum("water_drinks_carnivores")),
        "water_thirst_reduction_humans_observed": ecology_sum("water_thirst_reduction_humans"),
        "water_thirst_reduction_herbivores_observed": ecology_sum("water_thirst_reduction_herbivores"),
        "water_thirst_reduction_carnivores_observed": ecology_sum("water_thirst_reduction_carnivores"),
        "plants_reached_limit_step": result.step_reached_plant_limit,
        "final_mean_herbivore_health": final_population.get("herbivore_mean_health", 0.0),
        "final_mean_herbivore_hunger": final_population.get("herbivore_mean_hunger", 0.0),
        "final_mean_herbivore_thirst": final_population.get("herbivore_mean_thirst", 0.0),
        "final_mean_carnivore_health": final_population.get("carnivore_mean_health", 0.0),
        "final_mean_carnivore_hunger": final_population.get("carnivore_mean_hunger", 0.0),
        "final_mean_carnivore_thirst": final_population.get("carnivore_mean_thirst", 0.0),
        "final_social_close_pairs": final_population.get("social_close_pairs", 0),
        "final_social_mean_pair_affinity": final_population.get("social_mean_pair_affinity", 0.0),
        "final_social_relationships_over_0_2": final_population.get("social_relationships_over_0_2", 0),
        "social_encounters_cumulative": final_population.get("social_encounters_cumulative", 0),
    }


def main() -> None:
    runs = 20
    max_steps = 300
    base_seed = 10
    config = SimulationConfig(
        width=30, height=30, food_density=0.06, obstacle_density=0.01,
        water_density=0.02, agent_count=5, herbivore_count=8,
        carnivore_count=3, vision_radius=6,
    )
    config.validate()

    print("=== Experimento ecológico auditável (sem visualização) ===")
    print(f"Execuções: {runs}; passos por execução: {max_steps}")
    print(f"População inicial: {config.agent_count} humanos, {config.herbivore_count} herbívoros, {config.carnivore_count} carnívoros")
    print("Executando...")
    started = time.perf_counter()
    results = [
        run_single_simulation(config, run_seed=base_seed + index, max_steps=max_steps,
                             seed_spawn_count=1, max_plants=100)
        for index in range(runs)
    ]
    elapsed = time.perf_counter() - started

    human_metrics = [m for result in results for m in result.all_agent_metrics]
    human_count = sum(result.total_agents for result in results)
    human_survivors = sum(result.surviving_agents for result in results)
    causes = [m.termination_cause for m in human_metrics]
    combined = causes.count("STARVATION_AND_DEHYDRATION")

    print("\n=== Resultados agregados ===")
    print(f"Sobrevivência humana: {human_survivors / human_count:.1%}")
    print(f"Mortes humanas por predação: {causes.count('PREDATION')}")
    print(f"Mortes humanas por fome (inclui causa combinada): {sum(c in {'STARVATION', 'STARVATION_AND_DEHYDRATION'} for c in causes)}")
    print(f"Mortes humanas por desidratação (inclui causa combinada): {sum(c in {'DEHYDRATION', 'STARVATION_AND_DEHYDRATION'} for c in causes)}")
    print(f"Mortes por fome e desidratação no mesmo passo: {combined}")
    print(f"Ataques de caça humanos: {sum(r.human_hunt_attacks for r in results)}")
    print(f"Ataques de carnívoros: {sum(r.carnivore_attacks for r in results)}")
    print(f"Ataques defensivos humanos: {sum(r.human_defense_attacks for r in results)}")
    print(f"Herbívoros abatidos por humanos: {sum(r.herbivores_killed for r in results)}")
    print(f"Herbívoros mortos por fome/sede: {sum(r.herbivores_died_by_starvation + r.herbivores_died_by_dehydration for r in results)}")
    print(f"Carnívoros abatidos por humanos: {sum(r.carnivores_killed for r in results)}")
    print(f"Carnívoros mortos por fome/sede: {sum(r.carnivores_died_by_starvation + r.carnivores_died_by_dehydration for r in results)}")
    survivors = [m for m in human_metrics if m.final_health > 0]
    print("Médias finais da coorte inicial (mortos incluídos; saúde dos mortos = 0):")
    print(f"  Saúde: {_mean([m.final_health for m in human_metrics]):.2f}")
    print(f"  Fome: {_mean([m.final_hunger for m in human_metrics]):.2f}")
    print(f"  Sede: {_mean([m.final_thirst for m in human_metrics]):.2f}")
    print(f"  Energia: {_mean([m.final_energy for m in human_metrics]):.2f}")
    print(f"Médias finais apenas dos sobreviventes (n={len(survivors)}):")
    print(f"  Saúde: {_mean([m.final_health for m in survivors]):.2f}")
    print(f"  Fome: {_mean([m.final_hunger for m in survivors]):.2f}")
    print(f"  Sede: {_mean([m.final_thirst for m in survivors]):.2f}")
    print(f"  Energia: {_mean([m.final_energy for m in survivors]):.2f}")
    print(f"Herbívoros vivos ao final (média): {mean(r.living_herbivores for r in results):.2f}")
    print(f"Carnívoros vivos ao final (média): {mean(r.living_carnivores for r in results):.2f}")
    ecology_records = [record for result in results for record in result.ecology_history]
    def ecology_total(key: str) -> float:
        return sum(float(record.get(key, 0)) for record in ecology_records)

    print("\n=== Auditoria ecológica (totais das 20 execuções) ===")
    print(f"Plantas coletadas por humanos: {int(ecology_total('plants_collected_by_humans'))}")
    print(f"Alimento coletado / consumido: {ecology_total('food_units_collected_by_humans'):.0f} / {ecology_total('food_units_consumed_by_humans'):.0f}")
    print(f"Alimento depositado / retirado: {ecology_total('food_units_deposited_by_humans'):.0f} / {ecology_total('food_units_withdrawn_by_humans'):.0f}")
    print(f"Materiais depositados (madeira/pedra/fibra): {ecology_total('wood_units_deposited_by_humans'):.0f} / {ecology_total('stone_units_deposited_by_humans'):.0f} / {ecology_total('fiber_units_deposited_by_humans'):.0f}")
    final_storage = [result.ecology_history[-1] for result in results if result.ecology_history]
    if final_storage:
        print("Estoque médio final nos depósitos (alimento/madeira/pedra): "
              f"{mean(float(row.get('storage_food_units', 0)) for row in final_storage):.1f} / "
              f"{mean(float(row.get('storage_wood_units', 0)) for row in final_storage):.1f} / "
              f"{mean(float(row.get('storage_stone_units', 0)) for row in final_storage):.1f}")
    print(f"Unidades de madeira coletadas: {ecology_total('wood_units_collected_by_humans'):.0f}")
    print(f"Unidades de pedra coletadas: {ecology_total('stone_units_collected_by_humans'):.0f}")
    print(f"Plantas coletadas por herbívoros: {int(ecology_total('plants_collected_by_herbivores'))}")
    print(f"Transições semente -> crescimento: {int(ecology_total('plants_seed_to_growing'))}")
    print(f"Transições crescimento -> madura: {int(ecology_total('plants_growing_to_mature'))}")
    print(f"Sementes solicitadas: {int(ecology_total('seeds_spawn_requested'))}")
    print(f"Sementes criadas: {int(ecology_total('seeds_spawned'))}")
    print(f"Sementes bloqueadas pelo limite de plantas: {int(ecology_total('seeds_blocked_by_plant_cap'))}")
    print(f"Sementes bloqueadas por falta de espaço: {int(ecology_total('seeds_blocked_by_space'))}")
    print(f"Redução de sede humana registrada: {ecology_total('water_thirst_reduction_humans'):.2f}")
    final_social = [result.population_history[-1] for result in results if result.population_history]
    if final_social:
        print("\n=== Indicadores sociais finais ===")
        print(f"Pares próximos (distância <= 3), média final: {_mean([float(row.get('social_close_pairs', 0)) for row in final_social]):.2f}")
        print(f"Afinidade média entre pares, média final: {_mean([float(row.get('social_mean_pair_affinity', 0)) for row in final_social]):.3f}")
        print(f"Relações com afinidade >= 0,2, média final: {_mean([float(row.get('social_relationships_over_0_2', 0)) for row in final_social]):.2f}")
        print(f"Encontros próximos acumulados (soma das execuções): {sum(int(row.get('social_encounters_cumulative', 0)) for row in final_social)}")
    print(f"Tempo: {elapsed:.2f}s")

    run_rows = [_run_row(i + 1, base_seed + i, result) for i, result in enumerate(results)]
    human_rows = []
    population_rows = []
    physiology_rows = []
    ecology_rows = []
    social_rows = []
    social_agent_rows = []
    for run_index, result in enumerate(results, start=1):
        for agent_index, metrics in enumerate(result.all_agent_metrics, start=1):
            metric_data = asdict(metrics)
            individual_history = (
                result.human_physiology_history[agent_index - 1]
                if agent_index - 1 < len(result.human_physiology_history) else []
            )
            final_inventory = individual_history[-1] if individual_history else {}
            # Legacy metric name `water_units_consumed` is actually reduction
            # of the thirst variable, not finite physical water extraction.
            metric_data["water_thirst_reduction"] = metrics.water_units_consumed
            # `steps` in an individual record means the individual's observed
            # lifetime, not the duration of the enclosing experiment. Keep the
            # latter explicitly in experiment_steps to prevent ambiguity.
            experiment_steps = metrics.steps
            step_duration = (
                metrics.simulated_time_seconds / experiment_steps
                if experiment_steps > 0 else 1.0
            )
            metric_data["experiment_steps"] = experiment_steps
            metric_data["steps"] = metrics.agent_lifetime_steps
            metric_data["simulated_time_seconds"] = metrics.agent_lifetime_steps * step_duration
            metric_data["step_duration_seconds"] = step_duration
            human_rows.append({"run": run_index, "seed": base_seed + run_index - 1,
                               "agent_index": agent_index,
                               "agent_id": result.agent_ids[agent_index - 1] if agent_index - 1 < len(result.agent_ids) else f"H{agent_index:03d}",
                               **metric_data,
                               "final_inventory_weight": final_inventory.get("inventory_weight", 0.0),
                               "final_inventory_food": final_inventory.get("inventory_food", 0.0),
                               "final_inventory_wood": final_inventory.get("inventory_wood", 0.0),
                               "final_inventory_stone": final_inventory.get("inventory_stone", 0.0),
                               "final_inventory_fiber": final_inventory.get("inventory_fiber", 0.0),
                               "damage_taken_by_cause": ";".join(
                                   f"{cause}:{amount:.4f}" for cause, amount in metrics.damage_taken_by_cause.items())})
        for record in result.population_history:
            population_rows.append({"run": run_index, "seed": base_seed + run_index - 1, **record})
        for record in result.ecology_history:
            ecology_rows.append({"run": run_index, "seed": base_seed + run_index - 1, **record})
        for record in result.social_history:
            social_rows.append({"run": run_index, "seed": base_seed + run_index - 1, **record})
        for record in result.social_agent_history:
            social_agent_rows.append({"run": run_index, "seed": base_seed + run_index - 1, **record})
        for agent_index, history in enumerate(result.human_physiology_history, start=1):
            for record in history:
                physiology_rows.append({
                    "run": run_index, "seed": base_seed + run_index - 1,
                    "agent_index": agent_index,
                    "agent_id": result.agent_ids[agent_index - 1] if agent_index - 1 < len(result.agent_ids) else f"H{agent_index:03d}",
                    "position_before": str(record.get("position_before", "")),
                    "position_after": str(record.get("position_after", "")),
                    "action": str(record.get("action", "")),
                    "damage_causes": ";".join(record.get("damage_causes", [])),
                    "damage_by_cause": ";".join(
                        f"{cause}:{amount:.4f}" for cause, amount in record.get("damage_by_cause", {}).items()
                    ),
                    **{key: value for key, value in record.items()
                       if key not in {"position_before", "position_after", "action", "damage_causes", "damage_by_cause"}},
                })

    _write_csv(OUTPUT_DIR / "runs.csv", run_rows)
    _write_csv(OUTPUT_DIR / "humans.csv", human_rows)
    _write_csv(OUTPUT_DIR / "population_history.csv", population_rows)
    _write_csv(OUTPUT_DIR / "human_physiology_history.csv", physiology_rows)
    _write_csv(OUTPUT_DIR / "ecology_history.csv", ecology_rows)
    _write_csv(OUTPUT_DIR / "social_history.csv", social_rows)
    _write_csv(OUTPUT_DIR / "social_agents_history.csv", social_agent_rows)
    # Uma linha final por par, útil para consultar afinidade acumulada sem
    # precisar filtrar manualmente a série temporal completa.
    final_relationships = {}
    for record in social_rows:
        key = (record["run"], record["agent_a_id"], record["agent_b_id"])
        final_relationships[key] = record
    _write_csv(OUTPUT_DIR / "social_relationships_final.csv", list(final_relationships.values()))
    print(f"\nCSV de auditoria gravados em: {OUTPUT_DIR.resolve()}")
    print("  runs.csv — resumo por execução")
    print("  humans.csv — métricas individuais; steps/tempo são a vida do agente e experiment_steps é o horizonte da execução")
    print("  population_history.csv — série temporal de população e fisiologia agregada")
    print("  human_physiology_history.csv — estado, ações e dano de cada humano por passo")
    print("  ecology_history.csv — estoques, coleta de materiais, transições, água e regeneração por passo")
    print("  social_history.csv — distância e evolução da afinidade de cada par por passo")
    print("  social_agents_history.csv — estado social individual por passo, com IDs estáveis")
    print("  social_relationships_final.csv — último estado conhecido de cada relação")


if __name__ == "__main__":
    main()
