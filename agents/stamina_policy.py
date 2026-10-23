"""Política compartilhada para administrar a reserva de estamina.

A política distingue corrida rotineira de emergência, usa histerese para evitar
alternância entre correr e caminhar, e favorece a recuperação quando a reserva
está criticamente baixa. Os valores são unidades abstratas do simulador.
"""
from __future__ import annotations


def energy_ratio(energy: float, max_energy: float) -> float:
    if max_energy <= 0:
        return 0.0
    return max(0.0, min(1.0, energy / max_energy))


def should_run(
    *, energy: float, max_energy: float, fatigue: float, urgent: bool,
    currently_running: bool, config: object,
) -> bool:
    """Decide se vale a pena correr, preservando reserva para necessidades críticas."""
    ratio = energy_ratio(energy, max_energy)
    if energy < getattr(config, "stamina_run_minimum"):
        return False
    if fatigue >= 85.0 and not urgent:
        return False
    if urgent:
        return ratio >= getattr(config, "stamina_urgent_run_ratio")
    threshold = (
        getattr(config, "stamina_run_continue_ratio") if currently_running
        else getattr(config, "stamina_run_start_ratio")
    )
    return ratio >= threshold and fatigue < 70.0


def should_rest_for_stamina(
    *, energy: float, max_energy: float, urgent: bool,
    currently_resting: bool, config: object, expected_effort: float = 0.0,
) -> bool:
    """Decide descanso com histerese e reserva para o próximo esforço previsto.

    ``expected_effort`` é o custo estimado da próxima ação exigente (por exemplo,
    uma arrancada). O agente tenta preservar também uma reserva mínima após esse
    esforço, em vez de esperar que a estamina já esteja criticamente baixa.
    """
    if urgent:
        return False
    ratio = energy_ratio(energy, max_energy)
    effort = max(0.0, expected_effort)
    reserve = (max_energy * getattr(config, "stamina_reserve_ratio", 0.0)) if effort > 0 else 0.0
    anticipated_threshold = min(max_energy, reserve + effort) if effort > 0 else 0.0
    if currently_resting:
        resume_threshold = max(
            max_energy * getattr(config, "stamina_rest_resume_ratio"),
            anticipated_threshold,
        )
        return energy < resume_threshold
    start_threshold = max(
        max_energy * getattr(config, "stamina_rest_start_ratio"),
        anticipated_threshold,
    )
    return energy <= start_threshold


def recovery_amount(base_amount: float, energy: float, max_energy: float, config: object) -> float:
    """Recuperação adaptativa: maior quando a reserva está baixa, sem bônus perto do máximo."""
    if base_amount <= 0:
        return 0.0
    ratio = energy_ratio(energy, max_energy)
    low_ratio = getattr(config, "stamina_low_recovery_ratio")
    bonus = getattr(config, "stamina_low_recovery_bonus")
    if ratio >= low_ratio or low_ratio <= 0:
        return base_amount
    deficit = (low_ratio - ratio) / low_ratio
    return base_amount * (1.0 + bonus * deficit)
