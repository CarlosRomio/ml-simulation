"""Auditoria experimental paralela do ecossistema.

Exemplo:
  py -3.13 run_ecosystem_audit.py --profile pilot
  py -3.13 run_ecosystem_audit.py --profile full --workers 4
  py -3.13 run_ecosystem_audit.py --profile full --width 100 --height 100

Cada execução usa uma semente independente e escreve shards localmente no worker,
evitando transferir históricos gigantes entre processos. O CSV de atividades é
amostrado; resumos estatísticos usam todos os registros gerados pela simulação.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
from dataclasses import asdict
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from statistics import mean, median

from configuration.simulation_config import SimulationConfig
from configuration.physiology_config import DEFAULT_PHYSIOLOGY_CONFIG
from experiments.runner import run_single_simulation

DEFAULT_OUTPUT = "results/ecosystem_audit"


def _csv_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})


def _write_iterable_csv(path: Path, rows, fields: list[str] | None = None) -> None:
    """Escreve linhas sem acumular o conjunto inteiro em memória."""
    path.parent.mkdir(parents=True, exist_ok=True)
    iterator = iter(rows)
    first = next(iterator, None)
    if fields is None:
        fields = list(first.keys()) if first else ["run"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        if first is not None:
            writer.writerow({key: _csv_value(value) for key, value in first.items()})
        for row in iterator:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})


def _merge_csv_shards(shards: list[Path], destination: Path, fallback_fields: list[str] | None = None) -> None:
    """Concatena CSVs de shards mantendo apenas um cabeçalho."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8-sig") as output:
        writer = None
        for shard in shards:
            if not shard.exists() or shard.stat().st_size == 0:
                continue
            with shard.open("r", newline="", encoding="utf-8-sig") as source:
                reader = csv.DictReader(source)
                if reader.fieldnames is None:
                    continue
                if writer is None:
                    writer = csv.DictWriter(output, fieldnames=reader.fieldnames, extrasaction="ignore")
                    writer.writeheader()
                for row in reader:
                    writer.writerow(row)
        if writer is None and fallback_fields:
            fallback_writer = csv.DictWriter(output, fieldnames=fallback_fields, extrasaction="ignore")
            fallback_writer.writeheader()


def _mean_field(rows: list[dict], field: str) -> float:
    values = []
    for row in rows:
        value = row.get(field)
        if value in (None, ""):
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return mean(values) if values else 0.0


def _activity_summary(run_index: int, seed: int, records: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        groups[(str(record.get("individual_type", "")), str(record.get("activity", "")))].append(record)

    output = []
    numeric_fields = (
        "distance", "stamina_spent_movement", "stamina_spent_combat",
        "stamina_recovered_rest", "stamina_recovered", "health_recovered_this_step",
        "hunger_metabolic_cost", "thirst_metabolic_cost", "fatigue_before", "fatigue_after", "fatigue_delta",
        "hunger_before", "hunger_after", "thirst_before", "thirst_after",
        "stamina_before", "stamina_after",
    )
    for (species, activity), group in sorted(groups.items()):
        row = {"run": run_index, "seed": seed, "individual_type": species,
               "activity": activity, "observations": len(group)}
        for field in numeric_fields:
            values = []
            for record in group:
                value = record.get(field)
                if value in (None, ""):
                    continue
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    continue
            row[f"{field}_mean"] = mean(values) if values else 0.0
            row[f"{field}_sum"] = sum(values)
        row["moved_observations"] = sum(bool(r.get("moved")) for r in group)
        row["low_stamina_observations"] = sum(
            float(r.get("stamina_after", 100) or 0) <= 10 for r in group
        )
        row["critical_hunger_observations"] = sum(
            float(r.get("hunger_after", 0) or 0) >= 80 for r in group
        )
        row["critical_thirst_observations"] = sum(
            float(r.get("thirst_after", 0) or 0) >= 80 for r in group
        )
        row["sleep_interruptions"] = sum(bool(r.get("sleep_interruption_reason")) for r in group)
        row["health_recovery_steps"] = sum(float(r.get("health_recovered_this_step", 0) or 0) > 0 for r in group)
        row["health_recovery_blocked_damage_steps"] = sum(
            str(r.get("health_recovery_block_reason", "")) == "DAMAGE_THIS_STEP" for r in group
        )
        row["health_recovery_blocked_need_steps"] = sum(
            str(r.get("health_recovery_block_reason", "")) == "CRITICAL_NEED" for r in group
        )
        row["deaths_observed"] = sum(
            float(r.get("health_after", 100) or 0) <= 0
            and str(r.get("termination_cause", "RUNNING")) not in {"RUNNING", ""}
            for r in group
        )
        output.append(row)
    return output



def _target_progress_episodes(run_index: int, seed: int, records: list[dict]) -> list[dict]:
    """Agrupa passos consecutivos com alvo em episódios de progresso observável."""
    by_individual: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        by_individual[(str(record.get("individual_type", "")), str(record.get("individual_id", "")))].append(record)

    episodes: list[dict] = []
    for (species, individual_id), individual_rows in sorted(by_individual.items()):
        individual_rows.sort(key=lambda row: int(row.get("step", 0) or 0))
        current: list[dict] = []
        current_signature = None

        def finish(end_reason: str) -> None:
            nonlocal current, current_signature
            if not current:
                return
            first, last = current[0], current[-1]
            progresses = []
            for row in current:
                try:
                    progresses.append(float(row.get("target_distance_progress", 0) or 0))
                except (TypeError, ValueError):
                    progresses.append(0.0)
            reached = any(str(row.get("target_reached", "")).lower() in {"true", "1"} for row in current)
            in_range = any(str(row.get("target_in_interaction_range", "")).lower() in {"true", "1"} for row in current)
            need_satisfied = any(str(row.get("need_satisfied_this_step", "")).lower() in {"true", "1"} for row in current)
            start_distance = first.get("target_distance_before_action", "")
            end_distance = last.get("target_distance_after_action", "")
            episodes.append({
                "run": run_index, "seed": seed, "individual_type": species,
                "individual_id": individual_id,
                "target_intent": str(first.get("target_intent_before_action", "NONE") or "NONE"),
                "target_agent_id": first.get("target_agent_id", ""),
                "target_x_start": first.get("target_x_before_action", ""),
                "target_y_start": first.get("target_y_before_action", ""),
                "target_x_end": last.get("target_x_before_action", ""),
                "target_y_end": last.get("target_y_before_action", ""),
                "start_step": int(first.get("step", 0) or 0),
                "end_step": int(last.get("step", 0) or 0),
                "duration_steps": len(current),
                "start_distance": start_distance, "end_distance": end_distance,
                "net_distance_progress": (
                    float(start_distance) - float(end_distance)
                    if start_distance not in (None, "") and end_distance not in (None, "") else ""
                ),
                "positive_progress_steps": sum(value > 0 for value in progresses),
                "zero_progress_steps": sum(value == 0 for value in progresses),
                "negative_progress_steps": sum(value < 0 for value in progresses),
                "movement_blocked_steps": sum(bool(row.get("movement_block_reason")) for row in current),
                "target_reached": reached, "target_in_interaction_range": in_range,
                "need_satisfied": need_satisfied,
                "outcome": "NEED_SATISFIED" if need_satisfied else "TARGET_REACHED" if reached else end_reason,
            })
            current = []
            current_signature = None

        for row in individual_rows:
            x = row.get("target_x_before_action", "")
            y = row.get("target_y_before_action", "")
            intent = str(row.get("target_intent_before_action", "NONE") or "NONE")
            has_target = x not in (None, "") and y not in (None, "")
            if not has_target:
                finish("TARGET_CLEARED")
                continue
            # Presas são móveis: para carnívoros em caça, uma mudança de
            # coordenada não significa que a identidade do objetivo mudou.
            if species == "CARNIVORE" and intent == "HUNT":
                prey_id = str(row.get("target_agent_id", "") or "")
                signature = (intent, prey_id) if prey_id else (intent,)
            else:
                signature = (intent, int(x), int(y))
            if current and (signature != current_signature or int(row.get("step", 0) or 0) != int(current[-1].get("step", 0) or 0) + 1):
                finish("TARGET_CHANGED")
            if not current:
                current_signature = signature
            current.append(row)
        finish("OBSERVATION_END")
    return episodes


def _target_progress_summary(run_index: int, seed: int, episodes: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for episode in episodes:
        groups[(str(episode["individual_type"]), str(episode["target_intent"]))].append(episode)
    rows = []
    for (species, intent), group in sorted(groups.items()):
        durations = [int(row["duration_steps"]) for row in group]
        progress = [float(row["net_distance_progress"]) for row in group if row["net_distance_progress"] not in (None, "")]
        rows.append({
            "run": run_index, "seed": seed, "individual_type": species,
            "target_intent": intent, "episodes": len(group),
            "mean_duration_steps": mean(durations) if durations else 0.0,
            "episodes_reached_target": sum(bool(row["target_reached"]) for row in group),
            "episodes_satisfied_need": sum(bool(row["need_satisfied"]) for row in group),
            "episodes_in_interaction_range": sum(bool(row["target_in_interaction_range"]) for row in group),
            "positive_progress_steps": sum(int(row["positive_progress_steps"]) for row in group),
            "zero_progress_steps": sum(int(row["zero_progress_steps"]) for row in group),
            "negative_progress_steps": sum(int(row["negative_progress_steps"]) for row in group),
            "movement_blocked_steps": sum(int(row["movement_blocked_steps"]) for row in group),
            "mean_net_distance_progress": mean(progress) if progress else 0.0,
        })
    return rows


def _combine_target_progress_summaries(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(str(row["individual_type"]), str(row["target_intent"]))].append(row)
    combined = []
    sum_fields = (
        "episodes", "episodes_reached_target", "episodes_satisfied_need",
        "episodes_in_interaction_range", "positive_progress_steps", "zero_progress_steps",
        "negative_progress_steps", "movement_blocked_steps",
    )
    for (species, intent), group in sorted(groups.items()):
        item = {"individual_type": species, "target_intent": intent}
        for field in sum_fields:
            item[field] = sum(int(row.get(field, 0) or 0) for row in group)
        episode_count = item["episodes"]
        item["mean_duration_steps"] = (
            sum(float(row.get("mean_duration_steps", 0) or 0) * int(row.get("episodes", 0) or 0) for row in group) / episode_count
            if episode_count else 0.0
        )
        progress_weighted = sum(float(row.get("mean_net_distance_progress", 0) or 0) * int(row.get("episodes", 0) or 0) for row in group)
        item["mean_net_distance_progress"] = progress_weighted / episode_count if episode_count else 0.0
        item["target_reach_rate"] = item["episodes_reached_target"] / episode_count if episode_count else 0.0
        item["need_satisfaction_rate"] = item["episodes_satisfied_need"] / episode_count if episode_count else 0.0
        combined.append(item)
    return combined


def _action_reason_summary(run_index: int, seed: int, records: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for record in records:
        groups[(
            str(record.get("individual_type", "")),
            str(record.get("activity", "")),
            str(record.get("action_reason", "")),
            str(record.get("behavior_intent", "")),
        )].append(record)
    rows = []
    for (species, activity, reason, intent), group in sorted(groups.items()):
        distances = [float(r.get("distance", 0) or 0) for r in group]
        rows.append({
            "run": run_index, "seed": seed, "individual_type": species,
            "activity": activity, "action_reason": reason, "behavior_intent": intent,
            "observations": len(group), "moved_observations": sum(bool(r.get("moved")) for r in group),
            "distance_sum": sum(distances),
            "distance_mean": mean(distances) if distances else 0.0,
            "sleep_interruptions": sum(bool(r.get("sleep_interruption_reason")) for r in group),
            "deaths_observed": sum(
                float(r.get("health_after", 100) or 0) <= 0
                and str(r.get("termination_cause", "RUNNING")) not in {"RUNNING", ""}
                for r in group
            ),
        })
    return rows


def _combine_action_reason_summaries(rows: list[dict]) -> list[dict]:
    combined: dict[tuple[str, str, str, str], dict] = {}
    for row in rows:
        key = (str(row["individual_type"]), str(row["activity"]),
               str(row["action_reason"]), str(row["behavior_intent"]))
        target = combined.setdefault(key, {
            "individual_type": key[0], "activity": key[1], "action_reason": key[2],
            "behavior_intent": key[3], "observations": 0, "moved_observations": 0,
            "distance_sum": 0.0, "sleep_interruptions": 0, "deaths_observed": 0,
        })
        for field in ("observations", "moved_observations", "sleep_interruptions", "deaths_observed"):
            target[field] += int(row.get(field, 0))
        target["distance_sum"] += float(row.get("distance_sum", 0) or 0)
    for row in combined.values():
        row["distance_mean"] = row["distance_sum"] / row["observations"] if row["observations"] else 0.0
    return sorted(combined.values(), key=lambda row: (
        row["individual_type"], row["activity"], row["action_reason"], row["behavior_intent"]
    ))

def _is_audit_event(record: dict, previous_record: dict | None) -> str:
    reasons = []
    activity = str(record.get("activity", ""))
    previous_activity = str(previous_record.get("activity", "")) if previous_record else None
    if activity != previous_activity:
        reasons.append("ACTIVITY_CHANGE")
    if str(record.get("termination_cause", "RUNNING")) not in {"RUNNING", ""}:
        reasons.append("TERMINATION")

    current_causes = str(record.get("damage_causes", ""))
    previous_causes = str(previous_record.get("damage_causes", "")) if previous_record else ""
    if current_causes and current_causes != previous_causes:
        reasons.append("DAMAGE")
    if str(record.get("sleep_interruption_reason", "")):
        reasons.append("SLEEP_INTERRUPTION")
    if float(record.get("health_recovered_this_step", 0) or 0) > 0:
        reasons.append("HEALTH_RECOVERY")
    movement_block_reason = str(record.get("movement_block_reason", ""))
    previous_movement_block_reason = str(previous_record.get("movement_block_reason", "")) if previous_record else ""
    if movement_block_reason and movement_block_reason != previous_movement_block_reason:
        reasons.append(f"MOVEMENT_BLOCKED_{movement_block_reason}")
    navigation_block_reason = str(record.get("navigation_block_reason", ""))
    previous_navigation_block_reason = str(previous_record.get("navigation_block_reason", "")) if previous_record else ""
    if navigation_block_reason and navigation_block_reason != previous_navigation_block_reason:
        reasons.append(f"NAVIGATION_BLOCK_AVOIDED_{navigation_block_reason}")
    if record.get("water_consumption_succeeded"):
        reasons.append("WATER_CONSUMED")
    if record.get("food_consumption_succeeded"):
        reasons.append("FOOD_CONSUMED")
    if record.get("urgent_thirst_without_water_in_vision"):
        reasons.append("URGENT_THIRST_NO_WATER_VISIBLE")
    if record.get("urgent_hunger_without_food_in_vision"):
        reasons.append("URGENT_HUNGER_NO_FOOD_VISIBLE")
    if previous_record and record.get("resource_access_outcome") != previous_record.get("resource_access_outcome"):
        reasons.append("RESOURCE_ACCESS_OUTCOME_CHANGE")

    def number(source: dict | None, field: str, default: float) -> float:
        if not source:
            return default
        try:
            return float(source.get(field, default) or 0)
        except (TypeError, ValueError):
            return default

    current_stamina = number(record, "stamina_after", 100)
    previous_stamina = number(previous_record, "stamina_after", 100)
    if current_stamina <= 10 and previous_stamina > 10:
        reasons.append("LOW_STAMINA")
    current_hunger = number(record, "hunger_after", 0)
    previous_hunger = number(previous_record, "hunger_after", 0)
    if current_hunger >= 80 and previous_hunger < 80:
        reasons.append("HIGH_HUNGER")
    current_thirst = number(record, "thirst_after", 0)
    previous_thirst = number(previous_record, "thirst_after", 0)
    if current_thirst >= 80 and previous_thirst < 80:
        reasons.append("HIGH_THIRST")
    current_health = number(record, "health_after", 100)
    previous_health = number(previous_record, "health_after", 100)
    if current_health <= 25 and previous_health > 25:
        reasons.append("LOW_HEALTH")
    return ";".join(dict.fromkeys(reasons))


def _count_deaths_by_primary_cause(
    deaths: dict[tuple[str, str], dict], species: str, cause: str,
) -> int:
    """Conta mortes por causa terminal exclusiva, sem somar causas contribuintes."""
    return sum(
        death_species == species and str(record.get("termination_cause", "")) == cause
        for (death_species, _), record in deaths.items()
    )


def _carnivore_kill_accounting(
    hunt_records: list[dict], *, human_deaths_predation: int, herbivore_deaths_predation: int,
    herbivore_deaths_hunting: int,
) -> dict[str, int]:
    """Reconcilia abates registrados com mortes terminais, inclusive por espécie.

    O histórico de caça e o registro de mortes são fontes distintas. As mortes
    de herbívoros por humanos permanecem separadas da predação por carnívoros.
    """
    successful = [record for record in hunt_records if bool(record.get("prey_killed", False))]
    history_kills = len(successful)
    history_human_kills = sum(
        str(record.get("attack_target_type", record.get("selected_prey_type", ""))).upper() == "HUMAN"
        for record in successful
    )
    history_herbivore_kills = sum(
        str(record.get("attack_target_type", record.get("selected_prey_type", ""))).upper() == "HERBIVORE"
        for record in successful
    )
    human_deaths = int(human_deaths_predation)
    herbivore_deaths = int(herbivore_deaths_predation)
    death_cause_kills = human_deaths + herbivore_deaths
    total_delta = history_kills - death_cause_kills
    human_delta = history_human_kills - human_deaths
    herbivore_delta = history_herbivore_kills - herbivore_deaths
    valid = total_delta == 0 and human_delta == 0 and herbivore_delta == 0
    return {
        "herbivores_killed_by_humans": int(herbivore_deaths_hunting),
        "herbivores_killed_by_carnivores": herbivore_deaths,
        "humans_killed_by_carnivores": human_deaths,
        "carnivore_prey_killed_from_hunt_history": history_kills,
        "carnivore_prey_killed_from_death_causes": death_cause_kills,
        "carnivore_kill_accounting_delta": total_delta,
        "herbivore_predation_kills_from_hunt_history": history_herbivore_kills,
        "herbivore_predation_accounting_delta": herbivore_delta,
        "human_predation_kills_from_hunt_history": history_human_kills,
        "human_predation_accounting_delta": human_delta,
        "carnivore_kill_accounting_valid": int(valid),
    }


def _carnivore_hunt_summary(run_index: int, seed: int, records: list[dict]) -> list[dict]:
    """Resumo por carnívoro para localizar gargalos de caça e mortes fisiológicas."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[str(record.get("individual_id", ""))].append(record)
    rows = []
    for individual_id, group in sorted(groups.items()):
        def number(record: dict, field: str) -> float | None:
            try:
                value = record.get(field)
                return None if value in (None, "") else float(value)
            except (TypeError, ValueError):
                return None
        nearest_distances = [number(r, "nearest_prey_distance") for r in group]
        nearest_distances = [value for value in nearest_distances if value is not None]
        death_records = [r for r in group if str(r.get("termination_cause", "RUNNING")) not in {"RUNNING", ""}]
        death = death_records[-1] if death_records else {}
        causes = set(str(death.get("damage_causes", "")).split(";"))
        # Um episódio é uma sequência contígua de passos que mantém a mesma
        # identidade de presa selecionada. Passos sem alvo encerram a sequência.
        hunt_episodes: list[list[dict]] = []
        active_episode: list[dict] = []
        active_prey_id = ""
        for record in group:
            prey_id = str(record.get("selected_prey_id", "") or "")
            if not prey_id:
                if active_episode:
                    hunt_episodes.append(active_episode)
                    active_episode = []
                active_prey_id = ""
                continue
            if active_episode and prey_id != active_prey_id:
                hunt_episodes.append(active_episode)
                active_episode = []
            active_episode.append(record)
            active_prey_id = prey_id
        if active_episode:
            hunt_episodes.append(active_episode)
        episode_attacks = sum(any(bool(r.get("attack_attempted")) for r in episode) for episode in hunt_episodes)
        episode_kills = sum(any(bool(r.get("prey_killed")) for r in episode) for episode in hunt_episodes)
        prey_ids = {str(r.get("selected_prey_id")) for r in group if r.get("selected_prey_id")}
        target_switches = sum(
            bool(previous.get("selected_prey_id")) and bool(current.get("selected_prey_id"))
            and str(previous.get("selected_prey_id")) != str(current.get("selected_prey_id"))
            for previous, current in zip(group, group[1:])
        )
        prey_distance_progress = [number(r, "selected_prey_distance_progress") for r in group]
        prey_distance_progress = [value for value in prey_distance_progress if value is not None]
        rows.append({
            "run": run_index, "seed": seed, "individual_id": individual_id,
            "steps_observed": len(group),
            "steps_hunger_ge_80": sum((number(r, "hunger_after") or 0) >= 80 for r in group),
            "steps_without_prey_in_vision": sum(
                int(r.get("visible_humans", 0) or 0) + int(r.get("visible_herbivores", 0) or 0) == 0 for r in group
            ),
            "steps_low_stamina_le_8": sum((number(r, "stamina_after") or 0) <= 8 for r in group),
            "nearest_prey_distance_mean": mean(nearest_distances) if nearest_distances else "",
            "attacks": sum(bool(r.get("attack_attempted")) for r in group),
            "prey_killed": sum(bool(r.get("prey_killed")) for r in group),
            "hunt_episodes": len(hunt_episodes),
            "distinct_prey_targeted": len(prey_ids),
            "episodes_with_attack": episode_attacks,
            "episodes_with_kill": episode_kills,
            "target_switches": target_switches,
            "mean_selected_prey_distance_progress": mean(prey_distance_progress) if prey_distance_progress else "",
            "steps_selected_prey_distance_increased": sum(value < 0 for value in prey_distance_progress),
            "steps_selected_prey_distance_unchanged": sum(value == 0 for value in prey_distance_progress),
            "meat_hunger_reduction_total": sum(number(r, "hunger_reduction_from_meat") or 0 for r in group),
            "retreat_decisions": sum(bool(r.get("retreat_decision")) for r in group),
            "retreat_attempts": sum(bool(r.get("retreat_attempted")) for r in group),
            "successful_retreats": sum(bool(r.get("retreat_success")) for r in group),
            "retreat_success_rate": (
                sum(bool(r.get("retreat_success")) for r in group)
                / max(1, sum(bool(r.get("retreat_attempted")) for r in group))
            ),
            "health_recovered_total": sum(number(r, "health_recovered_this_step") or 0 for r in group),
            "health_recovery_steps": sum((number(r, "health_recovered_this_step") or 0) > 0 for r in group),
            "health_recovery_eligible_steps": sum(bool(r.get("health_recovery_eligible")) for r in group),
            "health_recovery_blocked_damage_steps": sum(
                str(r.get("health_recovery_block_reason", "")) == "DAMAGE_THIS_STEP" for r in group
            ),
            "health_recovery_blocked_need_steps": sum(
                str(r.get("health_recovery_block_reason", "")) == "CRITICAL_NEED" for r in group
            ),
            "defense_attacks_received": sum(int(r.get("defense_attacks_received", 0) or 0) for r in group),
            "damage_received_from_defense": sum(number(r, "damage_received_from_defense") or 0 for r in group),
            # Causa primária é exclusiva; causas contribuintes ficam separadas.
            "starvation_death": str(death.get("termination_cause", "")) == "STARVATION",
            "dehydration_death": str(death.get("termination_cause", "")) == "DEHYDRATION",
            "starvation_damage_present_at_death": "STARVATION" in causes,
            "dehydration_damage_present_at_death": "DEHYDRATION" in causes,
            "death_step": death.get("step", ""),
            "death_cause": death.get("termination_cause", ""),
            "hunger_at_death": death.get("hunger_after", ""),
            "thirst_at_death": death.get("thirst_after", ""),
            "stamina_at_death": death.get("stamina_after", ""),
            "nearest_prey_distance_at_death": death.get("nearest_prey_distance", ""),
            "visible_humans_at_death": death.get("visible_humans", ""),
            "visible_herbivores_at_death": death.get("visible_herbivores", ""),
        })
    return rows


def _resource_access_summary(run_index: int, seed: int, records: list[dict]) -> list[dict]:
    """Agrega acesso e sucesso de consumo por espécie usando todos os passos."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[str(record.get("individual_type", ""))].append(record)
    output = []
    for species, group in sorted(groups.items()):
        def number(record: dict, field: str) -> float | None:
            value = record.get(field)
            if value in (None, ""):
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        water_distances = [number(r, "nearest_water_distance_manhattan") for r in group]
        food_distances = [number(r, "nearest_food_distance_manhattan") for r in group]
        water_distances = [v for v in water_distances if v is not None]
        food_distances = [v for v in food_distances if v is not None]
        thirst_urgent = [r for r in group if str(r.get("resource_need_priority", "")) == "THIRST"]
        hunger_urgent = [r for r in group if str(r.get("resource_need_priority", "")) == "HUNGER"]
        food_acquisition_events = [r for r in group if bool(r.get("food_acquisition_succeeded"))]
        food_consumption_events = [r for r in group if bool(r.get("food_consumption_succeeded"))]
        def matching_food_attempt(record: dict) -> bool | None:
            # O alvo pré-ação só é capturado explicitamente para herbívoros nesta etapa.
            # Não inferimos compatibilidade para humanos/carnívoros a partir do alvo pós-ação.
            if species.upper() != "HERBIVORE" or "resource_access_target_kind_before_action" not in record:
                return None
            need = str(record.get("resource_need_priority_before_action", "") or "").upper()
            kind = str(record.get("resource_access_target_kind_before_action", "") or "").upper()
            return kind == "FOOD" and need == "HUNGER"
        output.append({
            "run": run_index, "seed": seed, "individual_type": species,
            "observations": len(group),
            "thirst_priority_observations": len(thirst_urgent),
            "urgent_thirst_no_water_in_vision": sum(bool(r.get("urgent_thirst_without_water_in_vision")) for r in group),
            "water_consumption_successes": sum(bool(r.get("water_consumption_succeeded")) for r in group),
            "hunger_priority_observations": len(hunger_urgent),
            "urgent_hunger_no_food_in_vision": sum(bool(r.get("urgent_hunger_without_food_in_vision")) for r in group),
            # Esses campos são eventos por passo, não episódios de busca.
            "food_acquisition_successes": len(food_acquisition_events),
            "food_consumption_successes": len(food_consumption_events),
            "food_acquisition_events_with_matching_priority_target": sum(matching_food_attempt(r) is True for r in food_acquisition_events) if species.upper() == "HERBIVORE" else "",
            "food_acquisition_events_without_matching_priority_target": sum(matching_food_attempt(r) is False for r in food_acquisition_events) if species.upper() == "HERBIVORE" else "",
            "food_consumption_events_with_matching_priority_target": sum(matching_food_attempt(r) is True for r in food_consumption_events) if species.upper() == "HERBIVORE" else "",
            "food_consumption_events_without_matching_priority_target": sum(matching_food_attempt(r) is False for r in food_consumption_events) if species.upper() == "HERBIVORE" else "",
            "movement_blocked_by_agent_observations": sum(r.get("movement_block_reason") == "AGENT" for r in group),
            "movement_blocked_by_animal_observations": sum(r.get("movement_block_reason") == "ANIMAL" for r in group),
            "movement_blocked_by_obstacle_observations": sum(r.get("movement_block_reason") == "OBSTACLE" for r in group),
            "navigation_blocked_by_agent_observations": sum(r.get("navigation_block_reason") == "AGENT" for r in group),
            "navigation_blocked_by_animal_observations": sum(r.get("navigation_block_reason") == "ANIMAL" for r in group),
            "navigation_blocked_by_obstacle_observations": sum(r.get("navigation_block_reason") == "OBSTACLE" for r in group),
            # Planejamentos são tentativas de rota, não observações por passo.
            "navigation_plan_path_found_attempts": sum(int(r.get("navigation_plan_path_found_attempts", 0) or 0) for r in group),
            "navigation_plan_already_at_goal_attempts": sum(int(r.get("navigation_plan_already_at_goal_attempts", 0) or 0) for r in group),
            "navigation_plan_temporarily_blocked_attempts": sum(int(r.get("navigation_plan_temporarily_blocked_attempts", 0) or 0) for r in group),
            "navigation_plan_invalid_start_attempts": sum(int(r.get("navigation_plan_invalid_start_attempts", 0) or 0) for r in group),
            "navigation_plan_invalid_goal_attempts": sum(int(r.get("navigation_plan_invalid_goal_attempts", 0) or 0) for r in group),
            "navigation_plan_unreachable_attempts": sum(int(r.get("navigation_plan_unreachable_attempts", 0) or 0) for r in group),
            "targeting_water_observations": sum(r.get("selected_target_kind") == "WATER" for r in group),
            "targeting_food_observations": sum(r.get("selected_target_kind") == "FOOD" for r in group),
            "targeting_prey_observations": sum(r.get("selected_target_kind") == "PREY" for r in group),
            "target_path_unavailable_observations": sum(
                bool(r.get("selected_target_kind") not in {"", "NONE"}) and not bool(r.get("selected_target_path_available"))
                for r in group
            ),
            "mean_nearest_water_distance_manhattan": sum(water_distances) / len(water_distances) if water_distances else "",
            "mean_nearest_food_distance_manhattan": sum(food_distances) / len(food_distances) if food_distances else "",
        })
    return output



def _resource_access_episode_rows(run_index: int, seed: int, records: list[dict]) -> list[dict]:
    """Measure resource-access episodes only while the matching need is prioritized.

    Generic FOOD episodes for carnivores are omitted: carnivore prey pursuit is a
    separate behavior and is measured by the hunt-history diagnostics.
    """
    by_individual: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        by_individual[(str(record.get("individual_type", "")), str(record.get("individual_id", "")))].append(record)
    output: list[dict] = []

    def as_int(value, default=0):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def as_float(value, default=None):
        try:
            if value in (None, ""):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def truth(value):
        return value is True or str(value).strip().lower() in {"1", "true", "yes"}

    def matching_need(kind, need):
        return (kind == "WATER" and need == "THIRST") or (kind == "FOOD" and need == "HUNGER")

    for (species, individual_id), group in sorted(by_individual.items()):
        group.sort(key=lambda r: as_int(r.get("step")))
        active = None
        episode_number = 0

        def close_episode(episode, record, outcome, successful=False):
            end_step = as_int(record.get("step"), episode["start_step"])
            distances = episode["distances"]
            output.append({
                "run": run_index, "seed": seed, "individual_type": species,
                "individual_id": individual_id, "episode": episode["episode"],
                "resource_kind": episode["resource_kind"], "target_x": episode["target_x"],
                "target_y": episode["target_y"], "start_step": episode["start_step"],
                "end_step": end_step, "duration_steps": max(0, end_step - episode["start_step"]),
                "successful": bool(successful), "outcome": outcome,
                "start_distance": episode["start_distance"],
                "end_distance": as_float(record.get("selected_target_distance_manhattan")),
                "min_distance_observed": min(distances) if distances else "",
                "target_observations": episode["observations"],
                "blocked_by_agent": episode["blocked_agent"],
                "blocked_by_animal": episode["blocked_animal"],
                "blocked_by_obstacle": episode["blocked_obstacle"],
                "navigation_avoided_by_agent": episode["navigation_agent"],
                "navigation_avoided_by_animal": episode["navigation_animal"],
                "navigation_avoided_by_obstacle": episode["navigation_obstacle"],
                "path_unavailable_observations": episode["path_unavailable"],
                "urgent_need_observations": episode["urgent_need_observations"],
                "active_search_steps": episode["active_search_steps"],
                "max_hunger": episode["max_hunger"], "max_thirst": episode["max_thirst"],
            })

        for record in group:
            step = as_int(record.get("step"))
            kind = str(record.get("selected_target_kind", "NONE") or "NONE").upper()
            need = str(record.get("resource_need_priority_before_action", record.get("resource_need_priority", "NONE")) or "NONE").upper()
            x, y = record.get("selected_target_x"), record.get("selected_target_y")
            has_target = kind in {"WATER", "FOOD"} and x not in (None, "") and y not in (None, "")
            target_key = (kind, str(x), str(y)) if has_target else None
            priority_active = has_target and matching_need(kind, need)
            # Carnivore hunting is not generic food-access latency.
            if species.upper() == "CARNIVORE" and kind == "FOOD":
                priority_active = False
            termination = str(record.get("termination_cause", "RUNNING") or "RUNNING")

            if active is not None:
                success_now = (
                    (active["resource_kind"] == "WATER" and truth(record.get("water_consumption_succeeded")))
                    or (active["resource_kind"] == "FOOD" and (
                        truth(record.get("food_acquisition_succeeded")) or truth(record.get("food_consumption_succeeded"))
                    ))
                )
                if success_now:
                    # Keep the success observation in the active episode below.
                    pass
                elif termination not in {"RUNNING", ""}:
                    close_episode(active, record, "AGENT_DIED", False)
                    active = None
                elif not matching_need(active["resource_kind"], need):
                    close_episode(active, record, "NEED_NO_LONGER_PRIORITY", False)
                    active = None
                elif target_key != active["target_key"]:
                    outcome = "TARGET_LOST" if target_key is None else "TARGET_CHANGED"
                    close_episode(active, record, outcome, False)
                    active = None

            if active is None and priority_active and termination in {"RUNNING", ""}:
                episode_number += 1
                active = {
                    "episode": episode_number, "resource_kind": kind, "target_key": target_key,
                    "target_x": x, "target_y": y, "start_step": step,
                    "start_distance": as_float(record.get("selected_target_distance_manhattan")),
                    "distances": [], "observations": 0, "blocked_agent": 0,
                    "blocked_animal": 0, "blocked_obstacle": 0,
                    "navigation_agent": 0, "navigation_animal": 0, "navigation_obstacle": 0,
                    "path_unavailable": 0,
                    "urgent_need_observations": 0, "active_search_steps": 0,
                    "max_hunger": as_float(record.get("hunger_after"), 0),
                    "max_thirst": as_float(record.get("thirst_after"), 0),
                }

            if active is not None:
                success_now = (
                    (active["resource_kind"] == "WATER" and truth(record.get("water_consumption_succeeded")))
                    or (active["resource_kind"] == "FOOD" and (
                        truth(record.get("food_acquisition_succeeded")) or truth(record.get("food_consumption_succeeded"))
                    ))
                )
                if (target_key == active["target_key"] and priority_active) or success_now:
                    distance = as_float(record.get("selected_target_distance_manhattan"))
                    if distance is not None and target_key == active["target_key"]:
                        active["distances"].append(distance)
                    if priority_active and target_key == active["target_key"]:
                        active["observations"] += 1
                        active["active_search_steps"] += 1
                        active["urgent_need_observations"] += 1
                        block = str(record.get("movement_block_reason", "") or "").upper()
                        if block == "AGENT": active["blocked_agent"] += 1
                        elif block == "ANIMAL": active["blocked_animal"] += 1
                        elif block == "OBSTACLE": active["blocked_obstacle"] += 1
                        navigation_block = str(record.get("navigation_block_reason", "") or "").upper()
                        if navigation_block == "AGENT": active["navigation_agent"] += 1
                        elif navigation_block == "ANIMAL": active["navigation_animal"] += 1
                        elif navigation_block == "OBSTACLE": active["navigation_obstacle"] += 1
                        if str(record.get("selected_target_path_available", "True")).strip().lower() in {"false", "0", "no"}:
                            active["path_unavailable"] += 1
                        active["max_hunger"] = max(active["max_hunger"], as_float(record.get("hunger_after"), 0))
                        active["max_thirst"] = max(active["max_thirst"], as_float(record.get("thirst_after"), 0))
                    if success_now:
                        close_episode(active, record, "SUCCESS", True)
                        active = None
                    elif termination not in {"RUNNING", ""}:
                        close_episode(active, record, "AGENT_DIED", False)
                        active = None

        if active is not None and group:
            close_episode(active, group[-1], "SIMULATION_END", False)

    return output



def _spatial_coverage_summary(run_index: int, seed: int, records: list[dict],
                              width: int, height: int) -> list[dict]:
    """Resume cobertura espacial por indivíduo usando o histórico completo."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        species = str(record.get("individual_type", ""))
        individual_id = str(record.get("individual_id", ""))
        if species and individual_id and record.get("x") not in (None, "") and record.get("y") not in (None, ""):
            groups[(species, individual_id)].append(record)

    world_cells = max(1, width * height)
    output: list[dict] = []
    for (species, individual_id), rows in sorted(groups.items()):
        visited = set()
        repeat_observations = 0
        total_distance = 0.0
        moving_observations = 0
        exploration_observations = 0
        running_observations = 0
        resting_observations = 0
        for row in rows:
            try:
                position = (int(row["x"]), int(row["y"]))
            except (TypeError, ValueError, KeyError):
                continue
            if position in visited:
                repeat_observations += 1
            visited.add(position)
            try:
                distance = float(row.get("distance", 0.0) or 0.0)
            except (TypeError, ValueError):
                distance = 0.0
            total_distance += distance
            moving_observations += distance > 0
            activity = str(row.get("activity", "")).upper()
            running_observations += activity == "RUNNING"
            resting_observations += activity in {"RESTING", "SLEEPING"}
            intents = {
                str(row.get("behavior_intent", "")).upper(),
                str(row.get("target_intent_before_action", "")).upper(),
                str(row.get("action_reason", "")).upper(),
            }
            exploration_observations += bool(intents.intersection({"EXPLORATION", "EXPLORING"}))
        observations = len(rows)
        output.append({
            "run": run_index, "seed": seed, "individual_type": species,
            "individual_id": individual_id, "observations": observations,
            "unique_cells_visited": len(visited), "world_cells": world_cells,
            "world_coverage_ratio": len(visited) / world_cells,
            "repeat_visit_observations": repeat_observations,
            "repeat_visit_ratio": repeat_observations / observations if observations else 0.0,
            "total_distance": total_distance,
            "mean_distance_per_observation": total_distance / observations if observations else 0.0,
            "moving_observations": int(moving_observations),
            "running_observations": int(running_observations),
            "resting_or_sleeping_observations": int(resting_observations),
            "exploration_intent_observations": int(exploration_observations),
        })
    return output

def _resource_access_episode_summary(episodes: list[dict]) -> list[dict]:
    groups: dict[tuple[int, int, str, str], list[dict]] = defaultdict(list)
    for row in episodes:
        groups[(int(row["run"]), int(row["seed"]), str(row["individual_type"]), str(row["resource_kind"]))].append(row)
    output = []
    excluded = {"NEED_NO_LONGER_PRIORITY", "SIMULATION_END"}
    for (run, seed, species, kind), rows in sorted(groups.items()):
        successful = [row for row in rows if row["successful"]]
        resolved = [row for row in rows if row["outcome"] not in excluded]
        latencies = [int(row["duration_steps"]) for row in successful]
        output.append({
            "run": run, "seed": seed, "individual_type": species, "resource_kind": kind,
            "episodes_total": len(rows), "episodes_successful": len(successful),
            "episodes_unsuccessful_or_censored": len(rows) - len(successful),
            "episodes_resolved": len(resolved), "episodes_excluded_from_success_rate": len(rows) - len(resolved),
            "success_rate": len(successful) / len(resolved) if resolved else "",
            "mean_steps_to_success": mean(latencies) if latencies else "",
            "median_steps_to_success": median(latencies) if latencies else "",
            "mean_blocked_by_agent": mean([int(row["blocked_by_agent"]) for row in rows]) if rows else 0.0,
            "mean_blocked_by_animal": mean([int(row["blocked_by_animal"]) for row in rows]) if rows else 0.0,
            "mean_blocked_by_obstacle": mean([int(row["blocked_by_obstacle"]) for row in rows]) if rows else 0.0,
            "mean_navigation_avoided_by_agent": mean([int(row.get("navigation_avoided_by_agent", 0)) for row in rows]) if rows else 0.0,
            "mean_navigation_avoided_by_animal": mean([int(row.get("navigation_avoided_by_animal", 0)) for row in rows]) if rows else 0.0,
            "mean_navigation_avoided_by_obstacle": mean([int(row.get("navigation_avoided_by_obstacle", 0)) for row in rows]) if rows else 0.0,
            "mean_min_distance_observed": mean([float(row["min_distance_observed"]) for row in rows if row["min_distance_observed"] not in (None, "")]) if any(row["min_distance_observed"] not in (None, "") for row in rows) else "",
        })
    return output

def _run_worker(task: tuple) -> dict:
    run_index, seed, config, steps, seed_spawn_count, max_plants, sample_every, shard_dir = task
    started = time.perf_counter()
    result = run_single_simulation(
        config=config,
        run_seed=seed,
        max_steps=steps,
        seed_spawn_count=seed_spawn_count,
        max_plants=max_plants,
    )
    elapsed = time.perf_counter() - started
    shard = Path(shard_dir)
    activity = result.physiology_activity_history
    spatial_coverage_rows = _spatial_coverage_summary(
        run_index, seed, activity, config.width, config.height
    )
    target_episodes = _target_progress_episodes(run_index, seed, activity)
    target_progress_summaries = _target_progress_summary(run_index, seed, target_episodes)
    _write_csv(shard / f"target_progress_episodes_{run_index:04d}.csv", target_episodes)
    _write_csv(shard / f"target_progress_summary_{run_index:04d}.csv", target_progress_summaries)

    sampled_rows: list[dict] = []
    event_rows: list[dict] = []
    previous_records: dict[tuple[str, str], dict] = {}
    for record in activity:
        species = str(record.get("individual_type", ""))
        individual_id = str(record.get("individual_id", ""))
        key = (species, individual_id)
        previous = previous_records.get(key)
        event_reason = _is_audit_event(record, previous)
        previous_records[key] = record
        enriched = {"run": run_index, "seed": seed, **record}
        if sample_every > 0 and int(record.get("step", 0) or 0) % sample_every == 0:
            sampled_rows.append({**enriched, "sample_reason": "PERIODIC" + (";" + event_reason if event_reason else "")})
        if event_reason:
            event_rows.append({**enriched, "event_reason": event_reason})

    _write_csv(shard / f"activity_sampled_{run_index:04d}.csv", sampled_rows)
    _write_csv(shard / f"activity_events_{run_index:04d}.csv", event_rows)
    _write_csv(shard / f"initial_states_{run_index:04d}.csv", [
        {"run": run_index, "seed": seed, **row} for row in result.initial_individual_states
    ])
    _write_csv(shard / f"population_{run_index:04d}.csv", [
        {"run": run_index, "seed": seed, **row} for row in result.population_history
    ])
    _write_csv(shard / f"ecology_{run_index:04d}.csv", [
        {"run": run_index, "seed": seed, **row} for row in result.ecology_history
    ])
    _write_csv(shard / f"social_decisions_{run_index:04d}.csv", [
        {"run": run_index, "seed": seed, **row} for row in result.social_decision_history
    ])
    reproduction_rows = [{"run": run_index, "seed": seed, **row} for row in result.reproduction_events]
    _write_csv(shard / f"reproduction_events_{run_index:04d}.csv", reproduction_rows)
    reproduction_diagnostic_rows = [
        {"run": run_index, "seed": seed, **row}
        for row in result.reproduction_diagnostics
    ]
    _write_csv(shard / f"reproduction_diagnostics_{run_index:04d}.csv", reproduction_diagnostic_rows)
    hunt_rows = [{"run": run_index, "seed": seed, **row} for row in result.carnivore_hunt_history]
    _write_csv(shard / f"carnivore_history_{run_index:04d}.csv", hunt_rows)
    hunt_summary = _carnivore_hunt_summary(run_index, seed, hunt_rows)
    _write_csv(shard / f"carnivore_summary_{run_index:04d}.csv", hunt_summary)
    resource_summary = _resource_access_summary(run_index, seed, activity)
    _write_csv(shard / f"resource_access_summary_{run_index:04d}.csv", resource_summary)
    resource_episodes = _resource_access_episode_rows(run_index, seed, activity)
    _write_csv(shard / f"resource_access_episodes_{run_index:04d}.csv", resource_episodes)
    _write_csv(shard / f"resource_access_episode_summary_{run_index:04d}.csv", _resource_access_episode_summary(resource_episodes))

    summaries = _activity_summary(run_index, seed, activity)
    _write_csv(shard / f"activity_summary_{run_index:04d}.csv", summaries)
    reason_summaries = _action_reason_summary(run_index, seed, activity)
    _write_csv(shard / f"action_reason_summary_{run_index:04d}.csv", reason_summaries)

    human_metrics = result.all_agent_metrics
    human_causes = [metric.termination_cause for metric in human_metrics]
    deaths: dict[tuple[str, str], dict] = {}
    for record in activity:
        try:
            dead = float(record.get("health_after", 100) or 0) <= 0
        except (TypeError, ValueError):
            dead = False
        if dead and str(record.get("termination_cause", "RUNNING")) not in {"RUNNING", ""}:
            deaths[(str(record.get("individual_type", "")), str(record.get("individual_id", "")))] = record

    def death_count(species: str, cause: str) -> int:
        # damage_causes pode conter causas contribuintes simultâneas.
        return _count_deaths_by_primary_cause(deaths, species, cause)

    final_states: dict[tuple[str, str], dict] = {}
    for record in activity:
        final_states[(str(record.get("individual_type", "")), str(record.get("individual_id", "")))] = record

    def final_mean(species: str, field: str) -> float:
        values = []
        for (kind, _), record in final_states.items():
            if kind != species:
                continue
            try:
                values.append(float(record.get(field, 0) or 0))
            except (TypeError, ValueError):
                pass
        return mean(values) if values else 0.0

    run_row = {
        "run": run_index, "seed": seed, "steps_requested": steps,
        "steps_completed": result.agent_metrics.steps,
        "simulated_hours": result.agent_metrics.steps / 60.0,
        "world_width": config.width, "world_height": config.height,
        "attribute_variation": config.attribute_variation,
        "humans_initial": config.agent_count, "humans_alive_final": result.surviving_agents,
        "human_survival_rate": result.surviving_agents / config.agent_count if config.agent_count else 0.0,
        "human_deaths_predation": human_causes.count("PREDATION"),
        "human_deaths_starvation": sum(c in {"STARVATION", "STARVATION_AND_DEHYDRATION"} for c in human_causes),
        "human_deaths_dehydration": sum(c in {"DEHYDRATION", "STARVATION_AND_DEHYDRATION"} for c in human_causes),
        "human_deaths_both": human_causes.count("STARVATION_AND_DEHYDRATION"),
        "human_mean_final_health_cohort": mean(m.final_health for m in human_metrics) if human_metrics else 0.0,
        "human_mean_final_hunger_cohort": mean(m.final_hunger for m in human_metrics) if human_metrics else 0.0,
        "human_mean_final_thirst_cohort": mean(m.final_thirst for m in human_metrics) if human_metrics else 0.0,
        "herbivores_initial": config.herbivore_count, "herbivores_alive_final": result.living_herbivores,
        "herbivores_deaths_hunting": death_count("HERBIVORE", "HUNTING"),
        "herbivores_deaths_predation": death_count("HERBIVORE", "PREDATION"),
        "herbivores_deaths_starvation": death_count("HERBIVORE", "STARVATION"),
        "herbivores_deaths_dehydration": death_count("HERBIVORE", "DEHYDRATION"),
        "herbivores_mean_final_health_cohort": final_mean("HERBIVORE", "health_after"),
        "herbivores_mean_final_hunger_cohort": final_mean("HERBIVORE", "hunger_after"),
        "herbivores_mean_final_thirst_cohort": final_mean("HERBIVORE", "thirst_after"),
        "carnivores_initial": config.carnivore_count, "carnivores_alive_final": result.living_carnivores,
        "carnivores_deaths_defense": death_count("CARNIVORE", "DEFENSE"),
        "carnivores_deaths_starvation": death_count("CARNIVORE", "STARVATION"),
        "carnivores_deaths_dehydration": death_count("CARNIVORE", "DEHYDRATION"),
        "carnivores_mean_final_health_cohort": final_mean("CARNIVORE", "health_after"),
        "carnivores_mean_final_hunger_cohort": final_mean("CARNIVORE", "hunger_after"),
        "carnivores_mean_final_thirst_cohort": final_mean("CARNIVORE", "thirst_after"),
        "human_hunt_attacks": result.human_hunt_attacks,
        "carnivore_attacks": result.carnivore_attacks,
        "human_defense_attacks": result.human_defense_attacks,
        "herbivores_killed": result.herbivores_killed,
        "humans_killed_by_carnivores": result.humans_killed_by_carnivores,
        **_carnivore_kill_accounting(
            result.carnivore_hunt_history,
            human_deaths_predation=human_causes.count("PREDATION"),
            herbivore_deaths_predation=death_count("HERBIVORE", "PREDATION"),
            herbivore_deaths_hunting=death_count("HERBIVORE", "HUNTING"),
        ),
        "carnivores_killed": result.carnivores_killed,
        "food_collected_population": result.population_food_collected,
        "activity_records_full_resolution": len(activity),
        "activity_rows_sampled": len(sampled_rows),
        "activity_event_rows": len(event_rows),
        "population_history_rows": len(result.population_history),
        "ecology_history_rows": len(result.ecology_history),
        "social_decision_rows": len(result.social_decision_history),
        "runtime_seconds": round(elapsed, 4),
    }
    return {"run_row": run_row, "activity_summaries": summaries,
            "action_reason_summaries": reason_summaries,
            "target_progress_summaries": target_progress_summaries,
            "spatial_coverage_rows": spatial_coverage_rows}


def _combine_activity_summaries(rows: list[dict]) -> list[dict]:
    combined: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (str(row["individual_type"]), str(row["activity"]))
        target = combined.setdefault(key, {
            "individual_type": key[0], "activity": key[1], "observations": 0,
            "moved_observations": 0, "low_stamina_observations": 0,
            "critical_hunger_observations": 0, "critical_thirst_observations": 0,
            "sleep_interruptions": 0, "health_recovery_steps": 0,
            "health_recovery_blocked_damage_steps": 0, "health_recovery_blocked_need_steps": 0,
            "deaths_observed": 0,
        })
        n = int(row["observations"])
        target["observations"] += n
        for field in ("moved_observations", "low_stamina_observations",
                      "critical_hunger_observations", "critical_thirst_observations",
                      "sleep_interruptions", "health_recovery_steps",
                      "health_recovery_blocked_damage_steps", "health_recovery_blocked_need_steps",
                      "deaths_observed"):
            target[field] += int(row.get(field, 0))
        for field, value in row.items():
            if field.endswith("_sum"):
                target[field] = target.get(field, 0.0) + float(value or 0)
    for row in combined.values():
        n = row["observations"]
        for field, value in list(row.items()):
            if field.endswith("_sum"):
                base = field[:-4]
                row[f"{base}_mean"] = value / n if n else 0.0
    return sorted(combined.values(), key=lambda row: (row["individual_type"], row["activity"]))


def derive_max_plants(width: int, height: int) -> int:
    """Compatibilidade: calcula a capacidade vegetal pela configuração padrão."""
    config = SimulationConfig(width=width, height=height)
    config.validate()
    return config.max_plants_capacity


def run_audit(*, runs: int, steps: int, seed: int, workers: int,
              config: SimulationConfig, output: str | Path, sample_every: int,
              seed_spawn_count: int = 2, max_plants: int | None = None) -> dict:
    if runs < 1 or steps < 1 or workers < 1 or sample_every < 1:
        raise ValueError("runs, steps, workers e sample_every devem ser positivos.")
    config.validate()
    requested_workers = workers
    # Não cria processos ociosos: cada worker executa uma réplica completa.
    # Também respeita o número de CPUs visíveis para o processo.
    workers = min(requested_workers, runs, os.cpu_count() or 1)
    if max_plants is None:
        max_plants = config.max_plants_capacity
    elif max_plants < 0:
        raise ValueError("max_plants não pode ser negativo.")
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    shard_dir = output_dir / ".shards"
    if shard_dir.exists():
        shutil.rmtree(shard_dir)
    shard_dir.mkdir(parents=True)

    tasks = [
        (i + 1, seed + i, config, steps, seed_spawn_count, max_plants, sample_every, str(shard_dir))
        for i in range(runs)
    ]
    started = time.perf_counter()
    if workers == 1:
        worker_results = [_run_worker(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as pool:
            worker_results = list(pool.map(_run_worker, tasks))
    compute_seconds = time.perf_counter() - started

    run_rows = [item["run_row"] for item in worker_results]
    summary_rows = _combine_activity_summaries([
        row for item in worker_results for row in item["activity_summaries"]
    ])
    _write_csv(output_dir / "runs.csv", run_rows)
    _write_csv(output_dir / "activity_summary.csv", summary_rows)
    reason_summary_rows = _combine_action_reason_summaries([
        row for item in worker_results for row in item["action_reason_summaries"]
    ])
    _write_csv(output_dir / "action_reason_summary.csv", reason_summary_rows)
    target_progress_summary_rows = _combine_target_progress_summaries([
        row for item in worker_results for row in item["target_progress_summaries"]
    ])
    _write_csv(output_dir / "target_progress_summary.csv", target_progress_summary_rows)
    spatial_coverage_rows = [
        row for item in worker_results for row in item["spatial_coverage_rows"]
    ]
    _write_csv(output_dir / "spatial_coverage_summary.csv", spatial_coverage_rows)

    shard_outputs = (
        ("target_progress_episodes_", "target_progress_episodes.csv", ["run", "seed", "individual_type", "individual_id", "target_intent", "target_agent_id", "start_step", "end_step", "duration_steps", "start_distance", "end_distance", "net_distance_progress", "target_reached", "need_satisfied", "outcome"]),
        ("activity_sampled_", "activity_sampled.csv", ["run", "seed", "step", "individual_type", "individual_id", "sample_reason",
         "x", "y", "activity", "behavior_intent", "action_reason", "decision_action_id", "target_agent_id",
         "moved", "distance", "movement_block_reason", "target_intent_before_action",
         "target_x_before_action", "target_y_before_action", "target_distance_before_action",
         "target_distance_after_action", "target_distance_progress", "target_in_interaction_range",
         "target_reached", "need_satisfied_this_step", "stamina_before", "stamina_after",
         "hunger_before", "hunger_after", "thirst_before", "thirst_after", "health_before", "health_after",
         "health_recovered_this_step", "health_recovery_source", "health_recovery_block_reason",
         "resource_need_priority", "resource_need_priority_before_action", "resource_access_target_kind_before_action",
         "resource_access_target_x_before_action", "resource_access_target_y_before_action",
         "nearest_water_distance_manhattan", "nearest_mature_plant_distance_manhattan",
         "nearest_food_distance_manhattan", "water_sources_in_vision", "mature_plants_in_vision",
         "food_sources_in_vision", "selected_target_kind", "selected_target_x", "selected_target_y",
         "selected_target_distance_manhattan", "selected_target_path_steps", "selected_target_path_available",
         "at_water_source", "at_food_source", "water_consumption_succeeded", "food_acquisition_succeeded",
         "food_consumption_succeeded", "urgent_thirst_without_water_in_vision",
         "urgent_hunger_without_food_in_vision", "resource_access_outcome", "termination_cause"]),
        ("activity_events_", "activity_events.csv", [field for field in ["run", "seed", "step", "individual_type", "individual_id", "sample_reason",
         "x", "y", "activity", "behavior_intent", "action_reason", "decision_action_id", "target_agent_id",
         "moved", "distance", "movement_block_reason", "target_intent_before_action",
         "target_x_before_action", "target_y_before_action", "target_distance_before_action",
         "target_distance_after_action", "target_distance_progress", "target_in_interaction_range",
         "target_reached", "need_satisfied_this_step", "stamina_before", "stamina_after",
         "hunger_before", "hunger_after", "thirst_before", "thirst_after", "health_before", "health_after",
         "health_recovered_this_step", "health_recovery_source", "health_recovery_block_reason",
         "resource_need_priority", "resource_need_priority_before_action", "resource_access_target_kind_before_action",
         "resource_access_target_x_before_action", "resource_access_target_y_before_action",
         "nearest_water_distance_manhattan", "nearest_mature_plant_distance_manhattan",
         "nearest_food_distance_manhattan", "water_sources_in_vision", "mature_plants_in_vision",
         "food_sources_in_vision", "selected_target_kind", "selected_target_x", "selected_target_y",
         "selected_target_distance_manhattan", "selected_target_path_steps", "selected_target_path_available",
         "at_water_source", "at_food_source", "water_consumption_succeeded", "food_acquisition_succeeded",
         "food_consumption_succeeded", "urgent_thirst_without_water_in_vision",
         "urgent_hunger_without_food_in_vision", "resource_access_outcome", "termination_cause"] if field != "sample_reason"] + ["event_reason"]),
        ("initial_states_", "initial_states.csv", ["run", "seed", "individual_type", "individual_id", "sex", "age_steps", "generation", "x", "y", "health", "hunger", "thirst", "stamina", "fatigue", "is_sleeping", "attribute_strength", "attribute_agility", "attribute_constitution", "attribute_endurance", "attribute_vision", "attribute_olfaction", "attribute_intelligence", "attribute_memory", "attribute_metabolic_efficiency", "gene_strength", "gene_agility", "gene_constitution", "gene_endurance", "gene_vision", "gene_olfaction", "gene_intelligence", "gene_memory", "gene_metabolic_efficiency"]),
        ("population_", "population_history.csv", ["run", "seed", "step"]),
        ("ecology_", "ecology_history.csv", ["run", "seed", "step"]),
        ("social_decisions_", "social_decisions.csv", [
            "run", "seed", "step", "agent_id", "decision", "reason", "target_agent_id",
            "target_affinity", "target_last_seen_age", "target_x", "target_y", "x_before",
            "y_before", "x_after", "y_after", "action_dx", "action_dy", "moved",
            "sociability", "hunger", "thirst", "energy",
        ]),
        ("reproduction_events_", "reproduction_events.csv", [
            "run", "seed", "step", "event", "species", "individual_id",
            "parent_a", "parent_b", "generation", "sex", "x", "y", "reason",
            "parent_a_x", "parent_a_y", "parent_b_x", "parent_b_y",
            "distance_manhattan", "parent_a_energy_after_cost", "parent_b_energy_after_cost",
            "gestation_steps", "cooldown_steps",
            "gene_strength", "gene_agility", "gene_constitution", "gene_endurance",
            "gene_vision", "gene_olfaction", "gene_intelligence", "gene_memory",
            "gene_metabolic_efficiency",
        ]),
        ("reproduction_diagnostics_", "reproduction_diagnostics.csv", [
            "run", "seed", "step", "species", "population_alive", "eligible_for_mating",
            "eligible_females", "eligible_males", "immature_count", "cooldown_count",
            "pregnant_count", "hunger_blocked_count", "thirst_blocked_count",
            "energy_blocked_count", "health_blocked_count", "seeking_mate_count",
            "matings_this_step", "births_this_step", "births_blocked_this_step",
            "deaths_old_age_this_step",
        ]),
        ("carnivore_history_", "carnivore_hunt_history.csv", [
            "run", "seed", "step", "individual_type", "individual_id", "hunger_before",
            "hunger_after", "nearest_prey_distance", "visible_humans", "visible_herbivores",
            "selected_prey_type", "selected_prey_id", "selected_prey_risk_score",
            "selected_prey_nearby_humans", "target_selection_reason",
            "selected_prey_x_before_action", "selected_prey_y_before_action",
            "selected_prey_distance_before_action", "selected_prey_distance_after_move",
            "selected_prey_distance_progress", "hunt_stagnation_steps", "hunt_target_switches",
            "hunt_position_history_size", "hunt_target_x", "hunt_target_y",
            "health_fraction_before_action", "human_threat_count_within_2", "human_threat_count_adjacent",
            "retreat_decision", "retreat_reason", "retreat_attempted", "retreat_success",
            "retreat_min_human_distance_before", "retreat_min_human_distance_after",
            "health_recovery_eligible", "health_recovered_this_step", "health_recovery_source",
            "health_recovery_block_reason",
            "nearby_human_defenders", "attack_risk_score", "attack_nearby_humans",
            "attack_selection_reason", "attack_attempted", "attack_target_type",
            "attack_target_id", "attack_skipped_reason", "prey_killed", "termination_cause",
        ]),
        ("carnivore_summary_", "carnivore_hunt_summary.csv", [
            "run", "seed", "individual_id", "steps_observed", "attacks", "prey_killed",
            "hunt_episodes", "distinct_prey_targeted", "episodes_with_attack", "episodes_with_kill",
            "target_switches", "mean_selected_prey_distance_progress",
            "steps_selected_prey_distance_increased", "steps_selected_prey_distance_unchanged",
            "retreat_decisions", "retreat_attempts", "successful_retreats", "retreat_success_rate",
            "health_recovered_total", "health_recovery_steps", "health_recovery_eligible_steps",
            "health_recovery_blocked_damage_steps", "health_recovery_blocked_need_steps",
            "starvation_death", "dehydration_death", "starvation_damage_present_at_death",
            "dehydration_damage_present_at_death", "death_step", "death_cause",
        ]),
        ("resource_access_episodes_", "resource_access_episodes.csv", [
            "run", "seed", "individual_type", "individual_id", "episode", "resource_kind",
            "target_x", "target_y", "start_step", "end_step", "duration_steps", "successful",
            "outcome", "start_distance", "end_distance", "min_distance_observed", "target_observations",
            "blocked_by_agent", "blocked_by_animal", "blocked_by_obstacle", "path_unavailable_observations",
            "urgent_need_observations", "active_search_steps", "max_hunger", "max_thirst",
        ]),
        ("resource_access_episode_summary_", "resource_access_episode_summary.csv", [
            "run", "seed", "individual_type", "resource_kind", "episodes_total", "episodes_successful",
            "episodes_unsuccessful_or_censored", "episodes_resolved", "episodes_excluded_from_success_rate", "success_rate", "mean_steps_to_success", "median_steps_to_success",
            "mean_blocked_by_agent", "mean_blocked_by_animal", "mean_blocked_by_obstacle",
            "mean_navigation_avoided_by_agent", "mean_navigation_avoided_by_animal", "mean_navigation_avoided_by_obstacle",
            "mean_min_distance_observed",
        ]),
        ("resource_access_episodes_", "resource_access_episodes.csv", [
            "run", "seed", "individual_type", "individual_id", "episode", "resource_kind", "target_x", "target_y",
            "start_step", "end_step", "duration_steps", "successful", "outcome", "start_distance", "end_distance",
            "min_distance_observed", "target_observations", "blocked_by_agent", "blocked_by_animal", "blocked_by_obstacle",
            "navigation_avoided_by_agent", "navigation_avoided_by_animal", "navigation_avoided_by_obstacle",
            "path_unavailable_observations", "urgent_need_observations", "active_search_steps", "max_hunger", "max_thirst",
        ]),
        ("resource_access_episode_summary_", "resource_access_episode_summary.csv", [
            "run", "seed", "individual_type", "resource_kind", "episodes_total", "episodes_successful",
            "episodes_unsuccessful_or_censored", "episodes_resolved", "episodes_excluded_from_success_rate", "success_rate", "mean_steps_to_success", "median_steps_to_success",
            "mean_blocked_by_agent", "mean_blocked_by_animal", "mean_blocked_by_obstacle",
            "mean_navigation_avoided_by_agent", "mean_navigation_avoided_by_animal", "mean_navigation_avoided_by_obstacle",
            "mean_min_distance_observed",
        ]),
        ("resource_access_summary_", "resource_access_summary.csv", [
            "run", "seed", "individual_type", "observations", "thirst_priority_observations",
            "urgent_thirst_no_water_in_vision", "water_consumption_successes",
            "hunger_priority_observations", "urgent_hunger_no_food_in_vision",
            "food_acquisition_successes", "food_consumption_successes",
            "food_acquisition_events_with_matching_priority_target", "food_acquisition_events_without_matching_priority_target",
            "food_consumption_events_with_matching_priority_target", "food_consumption_events_without_matching_priority_target",
            "targeting_water_observations",
            "targeting_food_observations", "targeting_prey_observations",
            "target_path_unavailable_observations", "movement_blocked_by_agent_observations",
            "movement_blocked_by_animal_observations", "movement_blocked_by_obstacle_observations",
            "navigation_blocked_by_agent_observations", "navigation_blocked_by_animal_observations",
            "navigation_blocked_by_obstacle_observations",
            "mean_nearest_water_distance_manhattan", "mean_nearest_food_distance_manhattan",
        ]),
    )
    for prefix, filename, fallback_fields in shard_outputs:
        shards = sorted(shard_dir.glob(f"{prefix}*.csv"))
        _merge_csv_shards(shards, output_dir / filename, fallback_fields)

    manifest = {
        "runs": runs, "steps_per_run": steps, "seed_start": seed,
        "python_version": platform.python_version(),
        "simulation_clock_minutes_per_step": DEFAULT_PHYSIOLOGY_CONFIG.minutes_per_step,
        "physiology_config": asdict(DEFAULT_PHYSIOLOGY_CONFIG),
        "workers": workers, "workers_requested": requested_workers,
        "sample_every_steps": sample_every,
        "world_width": config.width, "world_height": config.height,
        "attribute_variation": config.attribute_variation,
        "genetic_model": {
            "representation": "scalar_breeding_values",
            "phenotype_expression": "direct",
            "inheritance": "parental_mean_plus_gaussian_mutation",
            "mutation_rate_default": 0.02,
            "mutation_strength_default": 0.04,
            "reproduction_enabled": True,
            "life_history_time_unit": "simulation_steps",
            "life_history_scales": {
                "human": {"maturity_steps": 500, "gestation_steps": 240, "cooldown_steps": 180},
                "herbivore": {"maturity_steps": 220, "gestation_steps": 90, "cooldown_steps": 100},
                "carnivore": {"maturity_steps": 280, "gestation_steps": 130, "cooldown_steps": 140},
            },
        },
        "humans": config.agent_count, "herbivores": config.herbivore_count,
        "carnivores": config.carnivore_count,
        "food_density": config.food_density, "water_density": config.water_density,
        "obstacle_density": config.obstacle_density, "wood_density": config.wood_density,
        "stone_density": config.stone_density, "seed_spawn_count": seed_spawn_count,
        "max_plants": max_plants,
        "plant_cap_policy": "area_scaled_from_reference_density",
        "plant_cap_reference": {
            "width": config.plant_cap_reference_width,
            "height": config.plant_cap_reference_height,
            "max_plants": config.plant_cap_reference_max,
            "capacity_density_per_cell": config.plant_cap_density,
        },
        "compute_seconds": round(compute_seconds, 3),
        "runs_per_second": round(runs / compute_seconds, 3) if compute_seconds else 0.0,
        "carnivore_diagnostics": "carnivore_hunt_history contém observações por carnívoro/passo, incluindo decisão/tentativa/sucesso de retirada e recuperação de saúde; carnivore_hunt_summary resume caça, retirada, cura, exposição a presas, estamina e causas de morte.",
        "target_progress_diagnostics": "target_progress_episodes.csv registra episódios consecutivos de alvo por indivíduo, duração, progresso de distância, bloqueios, alcance e satisfação de necessidade; target_progress_summary.csv agrega por espécie e intenção. Para carnívoros em HUNT, mudanças de coordenada são tratadas como movimento da presa, não troca de alvo.",
        "reproduction_diagnostics": "reproduction_events.csv registra acasalamentos, nascimentos, nascimentos bloqueados e mortes por idade; reproduction_diagnostics.csv agrega elegibilidade, bloqueios fisiológicos, gestações e resultados por espécie e passo. Os tempos reprodutivos são escalas abstratas de prototipagem.",
        "resource_access_diagnostics": "activity_sampled.csv e activity_events.csv incluem distâncias Manhattan, recursos visíveis, alvo selecionado, sucesso de consumo, motivo de bloqueio de movimento e casos de necessidade urgente sem recurso visível; resource_access_summary.csv agrega eventos por execução e espécie (sucessos de aquisição/consumo são eventos por passo, não episódios); inclui eventos com e sem alvo/prioridade compatíveis. Para herbívoros, o alvo de recurso é capturado antes do movimento/consumo e a prioridade é registrada antes da ação, para preservar o alvo quando a planta é consumida no mesmo passo. resource_access_episodes.csv mede episódios de busca com prioridade ativa e encerra sucesso mesmo quando o alvo deixa de existir após o consumo; resource_access_episode_summary.csv agrega taxas de sucesso, latência e bloqueios por execução/espécie/recurso.",
        "note": "activity_summary usa todos os registros e agora agrega cura de saúde por espécie/atividade; activity_sampled é amostrado; activity_events preserva eventos relevantes, incluindo HEALTH_RECOVERY. As contagens de mortes por causa em runs.csv usam a causa terminal exclusiva; carnivore_hunt_summary também registra separadamente causas fisiológicas contribuintes. herbivores_killed é o total de herbívoros mortos por caça humana ou predação; as colunas herbivores_killed_by_humans e herbivores_killed_by_carnivores separam as causas. carnivore_kill_accounting_delta deve ser zero: compara prey_killed no histórico de caça com mortes humanas+herbívoras por predação. A instrumentação diagnóstica não altera decisões ou parâmetros da simulação. Distância Manhattan e presença no campo de visão não garantem caminho alcançável.",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    shutil.rmtree(shard_dir, ignore_errors=True)
    return {"output_dir": str(output_dir), "manifest": manifest, "runs": run_rows,
            "activity_summary": summary_rows,
            "target_progress_summary": target_progress_summary_rows}


def _profile(name: str) -> tuple[SimulationConfig, int, int, int]:
    if name == "pilot":
        return SimulationConfig(
            width=30, height=30, food_density=0.07, obstacle_density=0.01,
            water_density=0.02, wood_density=0.01, stone_density=0.01,
            agent_count=4, herbivore_count=8, carnivore_count=2, vision_radius=6,
        ), 4, 600, 5
    if name == "full":
        return SimulationConfig(
            width=60, height=60, food_density=0.05, obstacle_density=0.015,
            water_density=0.015, wood_density=0.01, stone_density=0.01,
            agent_count=20, herbivore_count=40, carnivore_count=8, vision_radius=7,
        ), 30, 3000, 10
    raise ValueError(f"Perfil desconhecido: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoria paralela e instrumentada do ecossistema.")
    parser.add_argument("--profile", choices=("pilot", "full"), default="pilot")
    parser.add_argument("--runs", type=int, help="Sobrescreve réplicas do perfil.")
    parser.add_argument("--steps", type=int, help="Sobrescreve passos por réplica.")
    parser.add_argument("--seed", type=int, default=7200)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--sample-every", type=int, help="Intervalo de amostragem do CSV de atividades.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--agents", type=int, help="Sobrescreve quantidade de humanos.")
    parser.add_argument("--herbivores", type=int, help="Sobrescreve quantidade de herbívoros.")
    parser.add_argument("--carnivores", type=int, help="Sobrescreve quantidade de carnívoros.")
    parser.add_argument("--width", type=int, help="Sobrescreve a largura do mundo; densidades de recursos são mantidas.")
    parser.add_argument("--height", type=int, help="Sobrescreve a altura do mundo; densidades de recursos são mantidas.")
    parser.add_argument("--attribute-variation", type=float, help="Desvio-padrão da variação individual dos atributos (padrão: 0.12; 0 desativa a variação).")
    parser.add_argument(
        "--max-plants", type=int,
        help="Limite de plantas explícito; por padrão escala pela área a partir da referência 60x60/300.",
    )
    args = parser.parse_args()

    config, profile_runs, profile_steps, profile_sample = _profile(args.profile)
    if args.agents is not None:
        config.agent_count = args.agents
    if args.herbivores is not None:
        config.herbivore_count = args.herbivores
    if args.carnivores is not None:
        config.carnivore_count = args.carnivores
    if args.width is not None:
        config.width = args.width
    if args.height is not None:
        config.height = args.height
    if args.attribute_variation is not None:
        config.attribute_variation = args.attribute_variation
    config.validate()

    result = run_audit(
        runs=args.runs or profile_runs,
        steps=args.steps or profile_steps,
        seed=args.seed, workers=args.workers, config=config, output=args.output,
        sample_every=args.sample_every or profile_sample,
        max_plants=args.max_plants,
    )
    manifest = result["manifest"]
    print("=== Auditoria do ecossistema concluída ===")
    print(f"Execuções: {manifest['runs']} | passos: {manifest['steps_per_run']} | workers: {manifest['workers']}")
    print(f"Mundo: {manifest['world_width']}x{manifest['world_height']} | população: "
          f"{manifest['humans']} humanos, {manifest['herbivores']} herbívoros, {manifest['carnivores']} carnívoros")
    print(f"Limite de plantas: {manifest['max_plants']} "
          f"({manifest.get('plant_cap_policy', 'explicit_or_legacy')})")
    print(f"Tempo simulado por execução: {manifest['steps_per_run']/60:.1f} h")
    print(f"Tempo computacional: {manifest['compute_seconds']:.2f}s "
          f"({manifest['runs_per_second']:.2f} execuções/s)")
    print(f"Resultados: {Path(result['output_dir']).resolve()}")
    print("Arquivos: runs.csv, activity_summary.csv, action_reason_summary.csv, target_progress_episodes.csv, target_progress_summary.csv, activity_sampled.csv, "
          "activity_events.csv, spatial_coverage_summary.csv, initial_states.csv, population_history.csv, ecology_history.csv, "
          "social_decisions.csv, carnivore_hunt_history.csv, carnivore_hunt_summary.csv, reproduction_events.csv, reproduction_diagnostics.csv, "
          "resource_access_summary.csv, resource_access_episodes.csv, "
          "resource_access_episode_summary.csv, manifest.json")
    print("\nResumo de atividade (todas as observações, não apenas a amostra):")
    for row in result["activity_summary"]:
        print(f"  {row['individual_type']:9s} {row['activity']:10s} "
              f"n={row['observations']:8d} distância média={row.get('distance_mean',0):.2f} "
              f"fadiga média Δ={row.get('fatigue_delta_mean',0):+.3f} "
              f"estamina gasta mov./comb.={row.get('stamina_spent_movement_sum',0):.1f}/"
              f"{row.get('stamina_spent_combat_sum',0):.1f}")


if __name__ == "__main__":
    main()
