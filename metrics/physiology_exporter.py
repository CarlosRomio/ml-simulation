"""Exportação de dados fisiológicos para auditoria passo a passo."""
from __future__ import annotations

import csv
from pathlib import Path


class PhysiologyExporter:
    """Exporta observações individuais e agregadas sem perder o contexto temporal."""

    @staticmethod
    def export_individual_csv(simulation, output_path: str | Path = "physiology_individual.csv") -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "agent_index", "agent_id", "step", "x", "y", "health_before", "health_after_physiology",
            "health_after", "energy_before", "energy_after_actions", "energy_after",
            "movement_energy_cost", "food_energy_recovered", "rest_energy_recovered",
            "energy_change_after_combat", "hunger_before", "hunger_after_physiology", "hunger_after",
            "thirst_before", "thirst_after_physiology", "thirst_after", "collected_food",
            "moved", "distance", "action_dx", "action_dy", "inventory_weight",
            "inventory_food", "inventory_wood", "inventory_stone", "inventory_fiber",
            "food_consumed", "storage_food_deposited", "storage_food_withdrawn",
            "storage_wood_deposited", "storage_stone_deposited", "storage_fiber_deposited",
            "damage_causes",
            "damage_by_cause", "termination_cause",
        ]
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for index, agent in enumerate(simulation.agents, start=1):
                key = id(agent)
                metrics = simulation.metrics_by_agent[key]
                initial_position = simulation.position_history_by_agent[key][0]
                writer.writerow({
                    "agent_index": index, "agent_id": agent.agent_id or f"H{index:03d}", "step": 0,
                    "x": initial_position[0], "y": initial_position[1],
                    "health_before": metrics.initial_health, "health_after_physiology": metrics.initial_health,
                    "health_after": metrics.initial_health, "energy_before": metrics.initial_energy,
                    "energy_after_actions": metrics.initial_energy, "energy_after": metrics.initial_energy,
                    "movement_energy_cost": 0.0, "food_energy_recovered": 0.0,
                    "rest_energy_recovered": 0.0, "energy_change_after_combat": 0.0,
                    "hunger_before": metrics.initial_hunger, "hunger_after_physiology": metrics.initial_hunger,
                    "hunger_after": metrics.initial_hunger, "thirst_before": metrics.initial_thirst,
                    "thirst_after_physiology": metrics.initial_thirst, "thirst_after": metrics.initial_thirst,
                    "termination_cause": "RUNNING",
                })
                for record in simulation.diagnostic_history_by_agent[key]:
                    before_pos = record.get("position_before", initial_position)
                    after_pos = record.get("position_after", before_pos)
                    action = record.get("action", (0, 0))
                    writer.writerow({
                        **record,
                        "agent_index": index,
                        "agent_id": agent.agent_id or f"H{index:03d}",
                        "x": after_pos[0], "y": after_pos[1],
                        "action_dx": action[0], "action_dy": action[1],
                        "damage_causes": ";".join(record.get("damage_causes", [])),
                        "damage_by_cause": ";".join(
                            f"{cause}:{amount:.4f}"
                            for cause, amount in record.get("damage_by_cause", {}).items()
                        ),
                    })
        return path

    @staticmethod
    def export_population_csv(simulation, output_path: str | Path = "physiology_population.csv") -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = list(simulation.population_history[0].keys()) if simulation.population_history else ["step"]
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(simulation.population_history)
        return path
