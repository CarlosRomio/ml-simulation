"""Experimentos pareados para medir o efeito da disponibilidade de água."""
from __future__ import annotations

import csv
import math
import time
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import mean, stdev
from typing import Iterable

from configuration.simulation_config import SimulationConfig
from experiments.runner import ExperimentRunner, SimulationRunResult
from scenarios.factory import ScenarioFactory
from scenarios.scenario import Scenario


@dataclass(frozen=True)
class WaterCondition:
    name: str
    density: float


DEFAULT_WATER_CONDITIONS = (
    WaterCondition("sem_agua", 0.0),
    WaterCondition("agua_escassa", 0.003),
    WaterCondition("agua_moderada", 0.01),
    WaterCondition("agua_abundante", 0.02),
)

METRICS = (
    "survival_rate_pct",
    "food_per_population",
    "final_thirst_mean",
    "average_thirst_mean",
    "water_units_per_agent",
    "water_drinks_per_agent",
    "dehydration_deaths_per_run",
    "starvation_deaths_per_run",
    "agents_reaching_critical_thirst_pct",
    "critical_thirst_steps_per_agent",
    "dehydration_damage_steps_per_agent",
    "first_dehydration_damage_step_mean",
    "final_health_mean",
    "distance_per_agent",
    "blocked_moves_per_run",
)


def _mean_or_zero(values: Iterable[float]) -> float:
    values = list(values)
    return mean(values) if values else 0.0


def _run_metrics(result: SimulationRunResult, run_index: int, condition: WaterCondition) -> dict:
    agents = result.all_agent_metrics or [result.agent_metrics]
    count = max(1, len(agents))
    survived = sum(metric.termination_cause == "STEP_LIMIT" for metric in agents)
    return {
        "condition": condition.name,
        "water_density": condition.density,
        "run": run_index,
        "survival_rate_pct": 100.0 * survived / count,
        "surviving_agents": survived,
        "total_agents": count,
        "food_per_population": result.population_food_collected if result.all_agent_metrics else result.agent_metrics.food_collected,
        "food_per_agent": _mean_or_zero(m.food_collected for m in agents),
        "final_thirst_mean": _mean_or_zero(m.final_thirst for m in agents),
        "average_thirst_mean": _mean_or_zero(m.average_thirst for m in agents),
        "final_hunger_mean": _mean_or_zero(m.final_hunger for m in agents),
        "final_health_mean": _mean_or_zero(m.final_health for m in agents),
        "average_health_mean": _mean_or_zero(m.average_health for m in agents),
        "water_units_per_agent": _mean_or_zero(m.water_units_consumed for m in agents),
        "water_drinks_per_agent": _mean_or_zero(m.water_drinks for m in agents),
        "dehydration_deaths_per_run": sum(m.termination_cause == "DEHYDRATION" for m in agents),
        "starvation_deaths_per_run": sum(m.termination_cause == "STARVATION" for m in agents),
        "agents_reaching_critical_thirst_pct": 100.0 * sum(m.critical_thirst_steps > 0 for m in agents) / count,
        "critical_thirst_steps_per_agent": _mean_or_zero(m.critical_thirst_steps for m in agents),
        "dehydration_damage_steps_per_agent": _mean_or_zero(m.dehydration_damage_steps for m in agents),
        "first_dehydration_damage_step_mean": _mean_or_zero(
            m.first_dehydration_damage_step for m in agents
            if m.first_dehydration_damage_step is not None
        ),
        "distance_per_agent": _mean_or_zero(m.distance_travelled for m in agents),
        "blocked_moves_per_run": result.blocked_movement_attempts,
        "simulated_steps_mean": _mean_or_zero(m.steps for m in agents),
    }


def _summarize(condition: WaterCondition, rows: list[dict]) -> dict:
    row = {"condition": condition.name, "water_density": condition.density, "runs": len(rows)}
    for metric in METRICS:
        values = [float(item[metric]) for item in rows]
        avg = mean(values) if values else 0.0
        sd = stdev(values) if len(values) > 1 else 0.0
        # Approximate 95% CI for the mean across independent paired run seeds.
        margin = 1.96 * sd / math.sqrt(len(values)) if values else 0.0
        row[f"{metric}_mean"] = avg
        row[f"{metric}_stddev"] = sd
        row[f"{metric}_ci95_low"] = avg - margin
        row[f"{metric}_ci95_high"] = avg + margin
    return row


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_water_comparison(
    config: SimulationConfig,
    runs: int = 30,
    max_steps: int = 500,
    seed: int = 42,
    max_workers: int = 4,
    output_dir: str | Path = "results/water_comparison",
    conditions: tuple[WaterCondition, ...] = DEFAULT_WATER_CONDITIONS,
) -> dict:
    """Runs each condition with the same scenario layout and run seeds.

    Food and obstacle locations remain identical across conditions. Conditions
    differ only in how many water-source positions from the master scenario are
    enabled. This is a paired design that reduces environmental confounding.
    """
    if runs <= 0 or max_steps <= 0 or max_workers <= 0:
        raise ValueError("runs, max_steps e max_workers devem ser positivos.")
    if not conditions:
        raise ValueError("Informe ao menos uma condição experimental.")

    max_density = max(condition.density for condition in conditions)
    if any(condition.density < 0 for condition in conditions):
        raise ValueError("A densidade de água não pode ser negativa.")
    master_config = replace(config, water_density=max_density)
    master_config.validate()
    master_scenario = ScenarioFactory.create(master_config, seed=seed)

    raw_rows: list[dict] = []
    summary_rows: list[dict] = []
    per_condition: dict[str, list[dict]] = {}
    durations: dict[str, float] = {}

    for condition in conditions:
        condition_config = replace(config, water_density=condition.density)
        condition_config.validate()
        water_count = condition_config.water_count
        if water_count > len(master_scenario.water_positions):
            raise ValueError(
                f"A condição {condition.name} precisa de {water_count} fontes, "
                f"mas o cenário-base contém {len(master_scenario.water_positions)}."
            )
        scenario: Scenario = replace(
            master_scenario,
            water_positions=master_scenario.water_positions[:water_count],
        )
        runner = ExperimentRunner(
            config=condition_config,
            runs=runs,
            max_steps=max_steps,
            seed=seed + 10_000,
            max_workers=max_workers,
            scenario=scenario,
        )
        started = time.perf_counter()
        results = runner.run()
        durations[condition.name] = time.perf_counter() - started
        condition_rows = [
            _run_metrics(result, index, condition)
            for index, result in enumerate(results)
        ]
        per_condition[condition.name] = condition_rows
        raw_rows.extend(condition_rows)
        summary_rows.append(_summarize(condition, condition_rows))

    # Paired deltas use the same replicate index and compare against no water.
    baseline_name = next(
        (condition.name for condition in conditions if condition.density == 0),
        conditions[0].name,
    )
    baseline_by_run = {
        int(row["run"]): row for row in per_condition[baseline_name]
    }
    paired_rows: list[dict] = []
    for condition in conditions:
        if condition.name == baseline_name:
            continue
        for row in per_condition[condition.name]:
            baseline = baseline_by_run[int(row["run"])]
            delta = {
                "condition": condition.name,
                "baseline": baseline_name,
                "run": row["run"],
            }
            for metric in METRICS:
                delta[f"delta_{metric}"] = float(row[metric]) - float(baseline[metric])
            paired_rows.append(delta)

    for row in summary_rows:
        row["compute_seconds"] = durations[row["condition"]]
        row["runs_per_second"] = runs / durations[row["condition"]] if durations[row["condition"]] else 0.0

    output_path = Path(output_dir)
    _write_csv(output_path / "runs.csv", raw_rows)
    _write_csv(output_path / "summary.csv", summary_rows)
    _write_csv(output_path / "paired_deltas.csv", paired_rows)
    return {
        "summary": summary_rows,
        "runs": raw_rows,
        "paired_deltas": paired_rows,
        "durations": durations,
        "output_dir": str(output_path),
        "baseline": baseline_name,
    }
