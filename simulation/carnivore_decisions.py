"""Regras puras de avaliação de risco para decisões de carnívoros.

Este módulo mantém cálculos de decisão fora da orquestração da simulação. Não
acessa o mundo, não altera agentes e não consome aleatoriedade, o que permite
validar os limiares com testes unitários determinísticos.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetreatDecision:
    """Resultado explicável da avaliação de retirada diante de humanos."""

    should_retreat: bool
    reason: str
    health_fraction: float
    critical_hunger: float
    retreat_health_fraction: float
    nearby_human_count: int
    adjacent_human_count: int


def evaluate_human_threat(
    *,
    health: float,
    max_health: float,
    hunger: float,
    risk_aversion: float,
    aggressiveness: float,
    persistence: float,
    nearby_human_count: int,
    adjacent_human_count: int,
    adjacent_herbivore_count: int,
) -> RetreatDecision:
    """Avalia a regra atual de retirada sem executar movimento.

    A decisão preserva os limiares comportamentais existentes. O motivo é
    explícito para que a auditoria possa distinguir ferimento, desvantagem e
    ausência de condição de fuga.
    """
    health_fraction = health / max_health if max_health > 0 else 0.0
    critical_hunger = 80.0 + 12.0 * aggressiveness - 8.0 * risk_aversion
    retreat_health_fraction = 0.20 + 0.35 * risk_aversion - 0.10 * aggressiveness
    wounded = health_fraction <= retreat_health_fraction
    outnumbered = nearby_human_count >= 2 and adjacent_herbivore_count == 0

    if adjacent_human_count and wounded:
        reason = "WOUNDED_NEAR_HUMANS"
    elif (adjacent_human_count and outnumbered and hunger < critical_hunger
          and persistence < 0.9):
        reason = "OUTNUMBERED_NEAR_HUMANS"
    else:
        reason = "NO_RETREAT_CONDITION"

    return RetreatDecision(
        should_retreat=reason != "NO_RETREAT_CONDITION",
        reason=reason,
        health_fraction=health_fraction,
        critical_hunger=critical_hunger,
        retreat_health_fraction=retreat_health_fraction,
        nearby_human_count=nearby_human_count,
        adjacent_human_count=adjacent_human_count,
    )
