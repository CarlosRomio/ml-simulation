"""Política compartilhada de recuperação de saúde durante repouso.

A função é determinística e registra por que a recuperação ocorreu ou foi
bloqueada. A taxa continua sendo específica por espécie e é fornecida pelo
chamador, evitando acoplar a política aos atributos de um tipo concreto.
"""
from __future__ import annotations

from typing import Any


RESTING_ACTIVITIES = frozenset({"RESTING", "SLEEPING"})


def recover_health_during_rest(needs: Any, activity: str, amount: float) -> tuple[float, str]:
    """Tenta recuperar saúde e retorna ``(cura_efetiva, motivo)``.

    Motivos possíveis: ``NOT_RESTING``, ``DAMAGE_THIS_STEP``, ``CRITICAL_NEED``,
    ``HEALTH_FULL`` e ``RECOVERED``. A função não muda a regra biológica atual;
    apenas centraliza a condição e torna o resultado observável.
    """
    # A prioridade é deliberada: registrar dano e necessidades críticas mesmo
    # quando o agente também não está repousando. Assim a telemetria identifica
    # o impedimento fisiológico mais relevante, em vez de mascará-lo pela ação.
    if needs.last_damage_causes:
        return 0.0, "DAMAGE_THIS_STEP"
    if needs.hunger >= 70.0 or needs.thirst >= 70.0:
        return 0.0, "CRITICAL_NEED"
    if activity not in RESTING_ACTIVITIES:
        return 0.0, "NOT_RESTING"
    if needs.health >= needs.max_health:
        return 0.0, "HEALTH_FULL"

    healed = needs.restore_health(amount)
    return healed, "RECOVERED" if healed > 0.0 else "HEALTH_FULL"
