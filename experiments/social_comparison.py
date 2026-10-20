"""Comparação pareada de condições de comportamento social humano."""
from __future__ import annotations

import csv
import math
import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from typing import Iterable

from configuration.simulation_config import SimulationConfig
from experiments.runner import SimulationRunResult, run_single_simulation
from scenarios.factory import ScenarioFactory
from scenarios.scenario import Scenario


@dataclass(frozen=True)
class SocialCondition:
    name: str
    social_behavior_enabled: bool
    social_memory_enabled: bool
    description: str


DEFAULT_SOCIAL_CONDITIONS = (
    SocialCondition("A_CONTROLE", True, True, "Sociabilidade, afinidade e memória atuais"),
    SocialCondition("B_SEM_INFLUENCIA_SOCIAL", False, False, "Decisões sociais desativadas; métricas de proximidade continuam sendo observadas"),
    SocialCondition("C_SEM_MEMORIA", True, False, "Aproximação social ativa, sem memória espacial nem busca de reencontro"),
)

MAX_AUTO_WORKERS = 8


def resolve_worker_count(requested_workers: int, runs: int, cpu_count: int | None = None) -> int:
    """Resolve workers; zero selects a conservative automatic process count.

    Automatic mode leaves one logical CPU available when possible and caps the
    pool at eight workers to avoid excessive memory use from per-step histories.
    """
    if requested_workers < 0:
        raise ValueError("workers não pode ser negativo.")
    if runs < 1:
        raise ValueError("runs deve ser positivo.")
    if requested_workers > 0:
        return min(requested_workers, runs)
    available_cpus = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    automatic = max(1, min(MAX_AUTO_WORKERS, available_cpus - 1 if available_cpus > 1 else 1))
    return min(runs, automatic)


METRICS = (
    "human_survival_pct",
    "human_deaths_predation",
    "human_deaths_starvation_or_dehydration",
    "final_mean_pair_affinity",
    "final_strong_relationships",
    "close_encounters",
    "social_approach_decisions",
    "reunion_attempts",
    "reunion_successes",
    "reunion_success_rate_pct",
    "final_group_count",
    "max_group_size",
    "mean_group_count_per_step",
    "group_member_steps",
    "human_food_collected",
    "human_distance_travelled",
    "social_movement_steps",
    "social_distance_travelled",
    "non_social_movement_steps",
    "non_social_distance_travelled",
    "idle_steps",
    "food_collection_events",
    "food_units_collected",
    "food_search_agent_steps",
    "food_collection_events_per_100_agent_steps",
    "food_units_collected_per_100_agent_steps",
    "food_search_agent_steps_per_100_agent_steps",
    "social_movement_steps_per_100_agent_steps",
    "distance_per_100_agent_steps",
    "mean_health_alive",
    "mean_hunger_alive",
    "mean_thirst_alive",
    "mean_energy_alive",
    "mean_health_delta_alive",
    "mean_hunger_delta_alive",
    "mean_thirst_delta_alive",
    "mean_energy_delta_alive",
    "critical_hunger_steps_per_100_agent_steps",
    "critical_thirst_steps_per_100_agent_steps",
    "food_consumed_steps",
    "water_drink_steps",
    "social_skipped_hunger_steps",
    "social_skipped_thirst_steps",
    "social_skipped_energy_steps",
    "critical_hunger_steps",
    "critical_thirst_steps",
)


def _mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return mean(materialized) if materialized else 0.0


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        empty_headers = {
            "group_history.csv": ["condition", "run", "step", "affinity_threshold", "group_size", "members"],
            "group_events.csv": ["condition", "run", "step", "event", "members", "related_previous_groups"],
            "agent_activity_history.csv": [
                "condition", "run", "step", "agent_id", "alive_after_step", "decision", "decision_reason",
                "target_agent_id", "moved", "distance", "movement_category", "behavior_intent", "social_intent",
                "social_skipped_priority", "hunger_before", "hunger_after", "thirst_before",
                "thirst_after", "health_before", "health_after", "energy_before", "energy_after",
                "health_delta", "hunger_delta", "thirst_delta", "energy_delta", "damage_causes",
                "critical_hunger", "critical_thirst", "collected_food", "collected_food_quantity", "collected_resource_type", "food_consumed",
                "drank_water", "termination_cause",
            ],
        }
        headers = empty_headers.get(path.name)
        if headers:
            with path.open("w", newline="", encoding="utf-8-sig") as stream:
                csv.DictWriter(stream, fieldnames=headers).writeheader()
        else:
            path.write_text("", encoding="utf-8-sig")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _components(agent_ids: set[str], edges: set[tuple[str, str]]) -> list[tuple[str, ...]]:
    adjacency = {agent_id: set() for agent_id in agent_ids}
    for first, second in edges:
        if first in adjacency and second in adjacency:
            adjacency[first].add(second)
            adjacency[second].add(first)
    components = []
    unseen = set(agent_ids)
    while unseen:
        start = min(unseen)
        stack = [start]
        found = set()
        while stack:
            current = stack.pop()
            if current in found:
                continue
            found.add(current)
            stack.extend(adjacency[current] - found)
        unseen -= found
        if len(found) >= 2:
            components.append(tuple(sorted(found)))
    return sorted(components)


def _group_audit(
    result: SimulationRunResult, run_index: int, condition: SocialCondition, threshold: float,
) -> tuple[list[dict], list[dict], dict]:
    snapshots: dict[int, dict[str, bool]] = {}
    for row in result.social_agent_history:
        snapshots.setdefault(int(row["step"]), {})[str(row["agent_id"])] = bool(row["alive"])
    affinities: dict[int, list[dict]] = {}
    for row in result.social_history:
        affinities.setdefault(int(row["step"]), []).append(row)

    history_rows: list[dict] = []
    event_rows: list[dict] = []
    previous_groups: set[tuple[str, ...]] = set()
    group_count_values: list[int] = []
    max_group_size = 0
    group_member_steps = 0
    for step in sorted(snapshots):
        alive_ids = {agent_id for agent_id, alive in snapshots[step].items() if alive}
        edges = {
            tuple(sorted((str(row["agent_a_id"]), str(row["agent_b_id"]))))
            for row in affinities.get(step, [])
            if float(row["affinity_after"]) >= threshold
        }
        groups = set(_components(alive_ids, edges))
        group_count_values.append(len(groups))
        max_group_size = max(max_group_size, max((len(group) for group in groups), default=0))
        group_member_steps += sum(len(group) for group in groups)
        for group in sorted(groups):
            history_rows.append({
                "condition": condition.name, "run": run_index, "step": step,
                "affinity_threshold": threshold, "group_size": len(group),
                "members": ";".join(group),
            })
        formed = groups - previous_groups
        dissolved = previous_groups - groups
        for group in sorted(formed):
            related = [old for old in dissolved if set(old) & set(group)]
            event_rows.append({
                "condition": condition.name, "run": run_index, "step": step,
                "event": "MEMBERSHIP_CHANGE" if related else "FORMATION",
                "members": ";".join(group),
                "related_previous_groups": "|".join(";".join(old) for old in related),
            })
        for group in sorted(dissolved):
            if not any(set(group) & set(new) for new in formed):
                event_rows.append({
                    "condition": condition.name, "run": run_index, "step": step,
                    "event": "DISSOLUTION", "members": ";".join(group),
                    "related_previous_groups": "",
                })
        previous_groups = groups

    return history_rows, event_rows, {
        "final_group_count": len(previous_groups),
        "max_group_size": max_group_size,
        "mean_group_count_per_step": _mean(group_count_values),
        "group_member_steps": group_member_steps,
    }


def _reunion_audit(result: SimulationRunResult) -> tuple[int, int]:
    """Conta inícios de tentativas e sucesso observado em até 30 passos.

    Sucesso exige que o alvo real esteja a distância Manhattan <= 3 após o início
    da tentativa; chegar apenas à última posição conhecida não conta como sucesso.
    """
    positions: dict[tuple[str, int], tuple[int, int]] = {}
    for row in result.social_agent_history:
        positions[(str(row["agent_id"]), int(row["step"]))] = (int(row["x"]), int(row["y"]))
    decisions = sorted(result.social_decision_history, key=lambda row: (int(row["step"]), str(row["agent_id"])))
    attempts: list[tuple[str, str, int]] = []
    previous_state: dict[str, tuple[str, str]] = {}
    for row in decisions:
        agent_id = str(row["agent_id"])
        decision = str(row["decision"])
        target_id = str(row.get("target_agent_id", ""))
        state = (decision, target_id)
        if decision == "SOCIAL_REUNION" and target_id and previous_state.get(agent_id) != state:
            attempts.append((agent_id, target_id, int(row["step"])))
        previous_state[agent_id] = state

    successes = 0
    for agent_id, target_id, start_step in attempts:
        for step in range(start_step, start_step + 31):
            first = positions.get((agent_id, step))
            second = positions.get((target_id, step))
            if first is not None and second is not None:
                if abs(first[0] - second[0]) + abs(first[1] - second[1]) <= 3:
                    successes += 1
                    break
    return len(attempts), successes


def _run_task(task: tuple) -> SimulationRunResult:
    config, seed, steps, scenario, condition = task
    return run_single_simulation(
        config=config,
        run_seed=seed,
        max_steps=steps,
        scenario=scenario,
        seed_spawn_count=1,
        max_plants=100,
        social_behavior_enabled=condition.social_behavior_enabled,
        social_memory_enabled=condition.social_memory_enabled,
    )


def _activity_audit(
    result: SimulationRunResult,
    run_index: int,
    condition: SocialCondition,
    hunger_threshold: float,
    thirst_threshold: float,
) -> tuple[list[dict], dict[str, float]]:
    """Cruza decisões sociais e auditoria fisiológica para explicar o uso do tempo.

    A origem de cada ação é classificada como SOCIAL somente quando a decisão
    registrada foi aproximação ou busca de reencontro e houve deslocamento.
    As demais movimentações são agrupadas como NÃO_SOCIAL; isso não afirma que
    todas sejam coleta, pois a política pode estar caçando, descansando ou buscando água.
    """
    decisions = {
        (str(row.get("agent_id", "")), int(row.get("step", 0))): row
        for row in result.social_decision_history
    }
    rows: list[dict] = []
    totals = {
        "social_movement_steps": 0.0,
        "social_distance_travelled": 0.0,
        "non_social_movement_steps": 0.0,
        "non_social_distance_travelled": 0.0,
        "idle_steps": 0.0,
        "food_collection_events": 0.0,
        "food_units_collected": 0.0,
        "food_search_agent_steps": 0.0,
        "food_consumed_steps": 0.0,
        "water_drink_steps": 0.0,
        "social_skipped_hunger_steps": 0.0,
        "social_skipped_thirst_steps": 0.0,
        "social_skipped_energy_steps": 0.0,
        "critical_hunger_steps": 0.0,
        "critical_thirst_steps": 0.0,
    }
    for index, agent_rows in enumerate(result.human_physiology_history):
        agent_id = result.agent_ids[index] if index < len(result.agent_ids) else f"H{index + 1:03d}"
        for diagnostic in agent_rows:
            step = int(diagnostic.get("step", 0))
            if step <= 0:
                continue
            decision_row = decisions.get((agent_id, step), {})
            decision = str(decision_row.get("decision", "OTHER_BEHAVIOR_PRIORITY"))
            reason = str(decision_row.get("reason", ""))
            moved = bool(diagnostic.get("moved", False))
            distance = float(diagnostic.get("distance", 0.0) or 0.0)
            social_intent = decision in {"SOCIAL_APPROACH", "SOCIAL_REUNION"}
            movement_category = "IDLE"
            if moved:
                movement_category = "SOCIAL" if social_intent else "NON_SOCIAL"
                if movement_category == "SOCIAL":
                    totals["social_movement_steps"] += 1
                    totals["social_distance_travelled"] += distance
                else:
                    totals["non_social_movement_steps"] += 1
                    totals["non_social_distance_travelled"] += distance
            else:
                totals["idle_steps"] += 1

            hunger_after = float(diagnostic.get("hunger_after_physiology", diagnostic.get("hunger_after", 0.0)) or 0.0)
            thirst_after = float(diagnostic.get("thirst_after_physiology", diagnostic.get("thirst_after", 0.0)) or 0.0)
            energy_after = float(diagnostic.get("energy_after", diagnostic.get("energy_after_actions", 0.0)) or 0.0)
            skipped_hunger = decision == "SOCIAL_SKIPPED_PRIORITY" and reason in {"HUNGER_PRIORITY", "HUNGER_OR_FOOD_PRIORITY"}
            skipped_thirst = decision == "SOCIAL_SKIPPED_PRIORITY" and reason in {"THIRST_PRIORITY", "THIRST_OR_WATER_PRIORITY"}
            skipped_energy = decision == "SOCIAL_SKIPPED_PRIORITY" and reason in {"ENERGY_PRIORITY", "ENERGY_OR_REST_PRIORITY"}
            critical_hunger = hunger_after >= hunger_threshold
            critical_thirst = thirst_after >= thirst_threshold
            collected_food = bool(diagnostic.get("collected_food", False))
            food_consumed = float(diagnostic.get("food_consumed", 0.0) or 0.0)
            drank_water = bool(diagnostic.get("drank_water", False))
            collected_food_quantity = float(diagnostic.get("collected_food_quantity", 0.0) or 0.0)
            behavior_intent = str(diagnostic.get("behavior_intent", "UNCLASSIFIED"))
            totals["food_collection_events"] += int(collected_food)
            totals["food_units_collected"] += collected_food_quantity
            totals["food_search_agent_steps"] += int(behavior_intent == "SEEK_FOOD" and not collected_food)
            totals["food_consumed_steps"] += int(food_consumed > 0)
            totals["water_drink_steps"] += int(drank_water)
            totals["social_skipped_hunger_steps"] += int(skipped_hunger)
            totals["social_skipped_thirst_steps"] += int(skipped_thirst)
            totals["social_skipped_energy_steps"] += int(skipped_energy)
            totals["critical_hunger_steps"] += int(critical_hunger)
            totals["critical_thirst_steps"] += int(critical_thirst)
            rows.append({
                "condition": condition.name, "run": run_index, "step": step,
                "agent_id": agent_id,
                "alive_after_step": str(diagnostic.get("termination_cause", "RUNNING")) == "RUNNING",
                "decision": decision, "decision_reason": reason,
                "target_agent_id": decision_row.get("target_agent_id", ""),
                "moved": moved, "distance": round(distance, 4),
                "movement_category": movement_category, "behavior_intent": behavior_intent,
                "social_intent": social_intent,
                "social_skipped_priority": skipped_hunger or skipped_thirst or skipped_energy,
                "hunger_before": diagnostic.get("hunger_before", ""),
                "hunger_after": round(hunger_after, 4),
                "thirst_before": diagnostic.get("thirst_before", ""),
                "thirst_after": round(thirst_after, 4),
                "health_before": diagnostic.get("health_before", ""),
                "health_after": round(float(diagnostic.get("health_after", 0.0) or 0.0), 4),
                "energy_before": diagnostic.get("energy_before", ""),
                "energy_after": round(energy_after, 4),
                "health_delta": round(float(diagnostic.get("health_after", 0.0) or 0.0) - float(diagnostic.get("health_before", 0.0) or 0.0), 4),
                "hunger_delta": round(hunger_after - float(diagnostic.get("hunger_before", 0.0) or 0.0), 4),
                "thirst_delta": round(thirst_after - float(diagnostic.get("thirst_before", 0.0) or 0.0), 4),
                "energy_delta": round(energy_after - float(diagnostic.get("energy_before", 0.0) or 0.0), 4),
                "damage_causes": ";".join(diagnostic.get("damage_causes", []) or []),
                "critical_hunger": critical_hunger, "critical_thirst": critical_thirst,
                "collected_food": collected_food,
                "collected_food_quantity": collected_food_quantity,
                "collected_resource_type": diagnostic.get("collected_resource_type", "NONE"),
                "food_consumed": food_consumed, "drank_water": drank_water,
                "termination_cause": diagnostic.get("termination_cause", "RUNNING"),
            })
    return rows, totals


def _activity_interval_summary(activity_rows: list[dict], interval_steps: int) -> list[dict]:
    """Agrega actividad en ventanas temporais sem perder a resolução do CSV bruto."""
    buckets: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
    for row in activity_rows:
        interval_index = (int(row["step"]) - 1) // interval_steps
        buckets[(str(row["condition"]), int(row["run"]), interval_index)].append(row)

    output: list[dict] = []
    for (condition, run, interval_index), rows in sorted(buckets.items()):
        by_step: dict[int, list[dict]] = defaultdict(list)
        for row in rows:
            by_step[int(row["step"])].append(row)
        alive_needs = [
            (float(row["hunger_after"]), float(row["thirst_after"]), float(row["energy_after"]))
            for row in rows if row["alive_after_step"]
        ]
        alive_counts = [sum(bool(row["alive_after_step"]) for row in step_rows)
                        for step_rows in by_step.values()]
        mean_or_zero = lambda values: mean(values) if values else 0.0
        output.append({
            "condition": condition, "run": run,
            "interval_start_step": interval_index * interval_steps + 1,
            "interval_end_step": (interval_index + 1) * interval_steps,
            "agent_steps_observed": len(rows),
            "mean_alive_humans_per_step": round(mean_or_zero(alive_counts), 4),
            "mean_hunger_alive": round(mean_or_zero([v[0] for v in alive_needs]), 4),
            "mean_thirst_alive": round(mean_or_zero([v[1] for v in alive_needs]), 4),
            "mean_energy_alive": round(mean_or_zero([v[2] for v in alive_needs]), 4),
            "mean_health_alive": round(mean_or_zero([float(row["health_after"]) for row in rows if row["alive_after_step"]]), 4),
            "mean_health_delta_alive": round(mean_or_zero([float(row["health_delta"]) for row in rows if row["alive_after_step"]]), 4),
            "mean_hunger_delta_alive": round(mean_or_zero([float(row["hunger_delta"]) for row in rows if row["alive_after_step"]]), 4),
            "mean_thirst_delta_alive": round(mean_or_zero([float(row["thirst_delta"]) for row in rows if row["alive_after_step"]]), 4),
            "mean_energy_delta_alive": round(mean_or_zero([float(row["energy_delta"]) for row in rows if row["alive_after_step"]]), 4),
            "critical_hunger_agent_steps": sum(bool(row["critical_hunger"]) for row in rows),
            "critical_thirst_agent_steps": sum(bool(row["critical_thirst"]) for row in rows),
            "social_intent_steps": sum(bool(row["social_intent"]) for row in rows),
            "social_movement_steps": sum(row["movement_category"] == "SOCIAL" for row in rows),
            "social_distance_travelled": round(sum(float(row["distance"]) for row in rows if row["movement_category"] == "SOCIAL"), 4),
            "non_social_movement_steps": sum(row["movement_category"] == "NON_SOCIAL" for row in rows),
            "non_social_distance_travelled": round(sum(float(row["distance"]) for row in rows if row["movement_category"] == "NON_SOCIAL"), 4),
            "idle_steps": sum(row["movement_category"] == "IDLE" for row in rows),
            "food_collection_events": sum(bool(row["collected_food"]) for row in rows),
            "food_units_collected": round(sum(float(row.get("collected_food_quantity", 0.0) or 0.0) for row in rows), 4),
            "food_search_agent_steps": sum(row.get("behavior_intent") == "SEEK_FOOD" and not bool(row["collected_food"]) for row in rows),
            "food_collection_events_per_100_agent_steps": round(100 * sum(bool(row["collected_food"]) for row in rows) / max(1, len(rows)), 4),
            "food_units_collected_per_100_agent_steps": round(100 * sum(float(row.get("collected_food_quantity", 0.0) or 0.0) for row in rows) / max(1, len(rows)), 4),
            "food_search_agent_steps_per_100_agent_steps": round(100 * sum(row.get("behavior_intent") == "SEEK_FOOD" and not bool(row["collected_food"]) for row in rows) / max(1, len(rows)), 4),
            "social_movement_steps_per_100_agent_steps": round(100 * sum(row["movement_category"] == "SOCIAL" for row in rows) / max(1, len(rows)), 4),
            "distance_per_100_agent_steps": round(100 * sum(float(row["distance"]) for row in rows) / max(1, len(rows)), 4),
            "critical_hunger_steps_per_100_agent_steps": round(100 * sum(bool(row["critical_hunger"]) for row in rows) / max(1, len(rows)), 4),
            "critical_thirst_steps_per_100_agent_steps": round(100 * sum(bool(row["critical_thirst"]) for row in rows) / max(1, len(rows)), 4),
            "food_consumed_steps": sum(float(row["food_consumed"]) > 0 for row in rows),
            "water_drink_steps": sum(bool(row["drank_water"]) for row in rows),
            "social_skipped_hunger_steps": sum(row["decision"] == "SOCIAL_SKIPPED_PRIORITY" and row["decision_reason"] in {"HUNGER_PRIORITY", "HUNGER_OR_FOOD_PRIORITY"} for row in rows),
            "social_skipped_thirst_steps": sum(row["decision"] == "SOCIAL_SKIPPED_PRIORITY" and row["decision_reason"] in {"THIRST_PRIORITY", "THIRST_OR_WATER_PRIORITY"} for row in rows),
            "social_skipped_energy_steps": sum(row["decision"] == "SOCIAL_SKIPPED_PRIORITY" and row["decision_reason"] in {"ENERGY_PRIORITY", "ENERGY_OR_REST_PRIORITY"} for row in rows),
        })
    return output


def _run_row(result: SimulationRunResult, run_index: int, seed: int, max_steps: int,
             condition: SocialCondition, threshold: float,
             hunger_threshold: float = 90.0, thirst_threshold: float = 90.0) -> tuple[dict, list[dict], list[dict], list[dict]]:
    agents = result.all_agent_metrics or [result.agent_metrics]
    count = max(1, len(agents))
    deaths = [m.termination_cause for m in agents if m.termination_cause != "STEP_LIMIT"]
    final_step = max((int(row["step"]) for row in result.population_history), default=0)
    final_pairs: dict[tuple[str, str], float] = {}
    for row in sorted(result.social_history, key=lambda item: int(item["step"])):
        pair = tuple(sorted((str(row["agent_a_id"]), str(row["agent_b_id"]))))
        # Mantém o último valor observado de cada par, mesmo se um dos membros
        # morreu antes do fim da execução.
        final_pairs[pair] = float(row["affinity_after"])
    final_affinity = _mean(final_pairs.values())
    strong_relationships = sum(value >= threshold for value in final_pairs.values())
    attempts, successes = _reunion_audit(result)
    group_history, group_events, group_metrics = _group_audit(result, run_index, condition, threshold)
    activity_history, activity_metrics = _activity_audit(
        result, run_index, condition,
        hunger_threshold=hunger_threshold,
        thirst_threshold=thirst_threshold,
    )
    final_population = result.population_history[-1] if result.population_history else {}
    row = {
        "condition": condition.name, "condition_description": condition.description,
        "run": run_index, "seed": seed, "steps_requested": max_steps,
        "last_population_snapshot_step": final_step,
        "humans_initial": count, "humans_alive_final": result.surviving_agents,
        "human_survival_pct": 100.0 * result.surviving_agents / count,
        "human_deaths_predation": deaths.count("PREDATION"),
        "human_deaths_starvation_or_dehydration": sum(c in {"STARVATION", "DEHYDRATION", "STARVATION_AND_DEHYDRATION"} for c in deaths),
        "final_mean_pair_affinity": final_affinity,
        "final_strong_relationships": strong_relationships,
        "close_encounters": int(final_population.get("social_encounters_cumulative", 0)),
        "social_approach_decisions": sum(row.get("decision") == "SOCIAL_APPROACH" for row in result.social_decision_history),
        "reunion_attempts": attempts, "reunion_successes": successes,
        "reunion_success_rate_pct": 100.0 * successes / attempts if attempts else 0.0,
        **group_metrics,
        # human_food_collected permanece por compatibilidade histórica e conta eventos;
        # unidades efetivamente adicionadas ao inventário são registradas separadamente.
        "human_food_collected": sum(m.food_collected for m in agents),
        "human_food_collection_events": activity_metrics["food_collection_events"],
        "human_food_units_collected": activity_metrics["food_units_collected"],
        "human_distance_travelled": sum(m.distance_travelled for m in agents),
        **activity_metrics,
        "food_collection_events_per_100_agent_steps": 100 * activity_metrics["food_collection_events"] / max(1, len(activity_history)),
        "food_units_collected_per_100_agent_steps": 100 * activity_metrics["food_units_collected"] / max(1, len(activity_history)),
        "food_search_agent_steps_per_100_agent_steps": 100 * activity_metrics["food_search_agent_steps"] / max(1, len(activity_history)),
        "social_movement_steps_per_100_agent_steps": 100 * activity_metrics["social_movement_steps"] / max(1, len(activity_history)),
        "distance_per_100_agent_steps": 100 * sum(float(row["distance"]) for row in activity_history) / max(1, len(activity_history)),
        "mean_health_alive": _mean(float(row["health_after"]) for row in activity_history if row["alive_after_step"]),
        "mean_hunger_alive": _mean(float(row["hunger_after"]) for row in activity_history if row["alive_after_step"]),
        "mean_thirst_alive": _mean(float(row["thirst_after"]) for row in activity_history if row["alive_after_step"]),
        "mean_energy_alive": _mean(float(row["energy_after"]) for row in activity_history if row["alive_after_step"]),
        "mean_health_delta_alive": _mean(float(row["health_delta"]) for row in activity_history if row["alive_after_step"]),
        "mean_hunger_delta_alive": _mean(float(row["hunger_delta"]) for row in activity_history if row["alive_after_step"]),
        "mean_thirst_delta_alive": _mean(float(row["thirst_delta"]) for row in activity_history if row["alive_after_step"]),
        "mean_energy_delta_alive": _mean(float(row["energy_delta"]) for row in activity_history if row["alive_after_step"]),
        "critical_hunger_steps_per_100_agent_steps": 100 * activity_metrics["critical_hunger_steps"] / max(1, len(activity_history)),
        "critical_thirst_steps_per_100_agent_steps": 100 * activity_metrics["critical_thirst_steps"] / max(1, len(activity_history)),
        "final_mean_health_all_cohort": _mean(m.final_health for m in agents),
        "final_mean_hunger_all_cohort": _mean(m.final_hunger for m in agents),
        "final_mean_thirst_all_cohort": _mean(m.final_thirst for m in agents),
        "herbivores_alive_final": result.living_herbivores,
        "carnivores_alive_final": result.living_carnivores,
    }
    return row, group_history, group_events, activity_history


def _summary(condition: SocialCondition, rows: list[dict]) -> dict:
    summary = {"condition": condition.name, "condition_description": condition.description, "runs": len(rows)}
    for metric in METRICS:
        values = [float(row[metric]) for row in rows]
        avg = mean(values) if values else 0.0
        sd = stdev(values) if len(values) > 1 else 0.0
        margin = 1.96 * sd / math.sqrt(len(values)) if values else 0.0
        summary[f"{metric}_mean"] = avg
        summary[f"{metric}_stddev"] = sd
        summary[f"{metric}_ci95_low"] = avg - margin
        summary[f"{metric}_ci95_high"] = avg + margin
    return summary


def run_social_comparison(
    config: SimulationConfig,
    runs: int = 30,
    max_steps: int = 1000,
    seed: int = 123,
    max_workers: int = 1,
    output_dir: str | Path = "results/social_comparison",
    affinity_threshold: float = 0.5,
    conditions: tuple[SocialCondition, ...] = DEFAULT_SOCIAL_CONDITIONS,
    activity_interval_steps: int = 100,
) -> dict:
    if runs < 1 or max_steps < 1 or max_workers < 0:
        raise ValueError("runs e max_steps devem ser positivos; max_workers não pode ser negativo.")
    effective_workers = resolve_worker_count(max_workers, runs)
    if not 0.0 <= affinity_threshold <= 1.0:
        raise ValueError("affinity_threshold deve estar entre 0 e 1.")
    if not conditions or len({c.name for c in conditions}) != len(conditions):
        raise ValueError("As condições devem ser não vazias e ter nomes únicos.")
    if activity_interval_steps < 1:
        raise ValueError("activity_interval_steps deve ser positivo.")
    config.validate()

    # Cada réplica tem um único cenário mestre reutilizado em A/B/C. Isso pareia
    # ambiente, semente e posições iniciais; só a política social muda.
    seeds = [seed + index for index in range(runs)]
    scenarios = [ScenarioFactory.create(config, run_seed) for run_seed in seeds]
    raw_rows: list[dict] = []
    group_history_rows: list[dict] = []
    group_event_rows: list[dict] = []
    activity_history_rows: list[dict] = []
    summaries: list[dict] = []
    durations: dict[str, float] = {}
    rows_by_condition: dict[str, list[dict]] = {}

    for condition in conditions:
        tasks = [(config, run_seed, max_steps, scenario, condition)
                 for run_seed, scenario in zip(seeds, scenarios)]
        started = time.perf_counter()
        condition_rows = []
        if effective_workers == 1:
            results = map(_run_task, tasks)
            for index, (run_seed, result) in enumerate(zip(seeds, results), start=1):
                row, group_history, group_events, activity_history = _run_row(result, index, run_seed, max_steps, condition, affinity_threshold,
                                                             config.starvation_threshold, config.dehydration_threshold)
                condition_rows.append(row)
                group_history_rows.extend(group_history)
                group_event_rows.extend(group_events)
                activity_history_rows.extend(activity_history)
        else:
            with ProcessPoolExecutor(max_workers=effective_workers) as executor:
                results = executor.map(_run_task, tasks)
                for index, (run_seed, result) in enumerate(zip(seeds, results), start=1):
                    row, group_history, group_events, activity_history = _run_row(
                        result, index, run_seed, max_steps, condition, affinity_threshold,
                        config.starvation_threshold, config.dehydration_threshold,
                    )
                    condition_rows.append(row)
                    group_history_rows.extend(group_history)
                    group_event_rows.extend(group_events)
                    activity_history_rows.extend(activity_history)
        durations[condition.name] = time.perf_counter() - started
        rows_by_condition[condition.name] = condition_rows
        raw_rows.extend(condition_rows)
        summaries.append(_summary(condition, condition_rows))

    baseline = next((c.name for c in conditions if c.name == "A_CONTROLE"), conditions[0].name)
    baseline_rows = {int(row["run"]): row for row in rows_by_condition[baseline]}
    paired_rows = []
    paired_summary_rows = []
    for condition in conditions:
        if condition.name == baseline:
            continue
        condition_by_run = {int(row["run"]): row for row in rows_by_condition[condition.name]}
        condition_deltas: dict[str, list[float]] = {metric: [] for metric in METRICS}
        for run_index in sorted(baseline_rows):
            base = baseline_rows[run_index]
            current = condition_by_run[run_index]
            delta = {"condition": condition.name, "baseline": baseline, "run": run_index,
                     "seed": base["seed"]}
            for metric in METRICS:
                difference = float(current[metric]) - float(base[metric])
                delta[f"delta_{metric}"] = difference
                condition_deltas[metric].append(difference)
            paired_rows.append(delta)
        for metric, values in condition_deltas.items():
            avg = mean(values) if values else 0.0
            sd = stdev(values) if len(values) > 1 else 0.0
            margin = 1.96 * sd / math.sqrt(len(values)) if values else 0.0
            paired_summary_rows.append({
                "condition": condition.name, "baseline": baseline, "metric": metric,
                "paired_mean_delta": avg, "paired_delta_stddev": sd,
                "paired_delta_ci95_low": avg - margin,
                "paired_delta_ci95_high": avg + margin,
                "paired_runs": len(values),
            })

    for row in summaries:
        row["compute_seconds"] = durations[row["condition"]]
        row["runs_per_second"] = runs / durations[row["condition"]] if durations[row["condition"]] else 0.0

    output = Path(output_dir)
    _write_csv(output / "runs.csv", raw_rows)
    _write_csv(output / "summary.csv", summaries)
    _write_csv(output / "paired_deltas.csv", paired_rows)
    _write_csv(output / "paired_summary.csv", paired_summary_rows)
    _write_csv(output / "group_history.csv", group_history_rows)
    _write_csv(output / "group_events.csv", group_event_rows)
    interval_summary_rows = _activity_interval_summary(activity_history_rows, activity_interval_steps)
    _write_csv(output / "agent_activity_history.csv", activity_history_rows)
    _write_csv(output / "activity_interval_summary.csv", interval_summary_rows)
    return {"summary": summaries, "runs": raw_rows, "paired_deltas": paired_rows,
            "paired_summary": paired_summary_rows,
            "group_history": group_history_rows, "group_events": group_event_rows,
            "agent_activity_history": activity_history_rows,
            "activity_interval_summary": interval_summary_rows,
            "activity_interval_steps": activity_interval_steps,
            "durations": durations, "output_dir": str(output), "baseline": baseline,
            "affinity_threshold": affinity_threshold, "workers": effective_workers}
