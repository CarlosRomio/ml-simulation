"""Memória compacta de resultados por tipo de ação.

A atualização é explícita de propósito: o simulador ainda não atribui
recompensas automaticamente, pois isso exige definir cuidadosamente como
atribuir consequências a ações que podem durar vários passos.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(slots=True)
class ActionOutcomeStats:
    count: int = 0
    mean_reward: float = 0.0


class ExperienceMemory:
    """Mantém a recompensa média observada por identificador de ação."""

    def __init__(self) -> None:
        self._stats: dict[str, ActionOutcomeStats] = {}

    def expected_reward(self, action_id: str) -> float:
        stats = self._stats.get(action_id)
        return 0.0 if stats is None else stats.mean_reward

    def sample_count(self, action_id: str) -> int:
        stats = self._stats.get(action_id)
        return 0 if stats is None else stats.count

    def observe(self, action_id: str, reward: float) -> None:
        if not action_id:
            raise ValueError("action_id não pode ser vazio.")
        if not isfinite(reward) or not -1.0 <= reward <= 1.0:
            raise ValueError("A recompensa deve ser finita e estar entre -1 e 1.")
        stats = self._stats.setdefault(action_id, ActionOutcomeStats())
        stats.count += 1
        stats.mean_reward += (reward - stats.mean_reward) / stats.count

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        return {
            action_id: {"count": stats.count, "mean_reward": round(stats.mean_reward, 6)}
            for action_id, stats in sorted(self._stats.items())
        }
