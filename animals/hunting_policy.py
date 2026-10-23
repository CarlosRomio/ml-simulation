"""Seleção de presas sensível a risco para o comportamento dos carnívoros.

A política é determinística: não consome RNG e pode ser testada isoladamente.
"""
from __future__ import annotations

from agents.agent import Agent


def manhattan(a: object, b: object) -> int:
    return abs(int(getattr(a, "x")) - int(getattr(b, "x"))) + abs(int(getattr(a, "y")) - int(getattr(b, "y")))


def nearby_human_count(prey: object, humans: list[Agent], radius: int = 2) -> int:
    """Conta humanos que podem transformar a aproximação em confronto coletivo."""
    px, py = int(getattr(prey, "x")), int(getattr(prey, "y"))
    return sum(
        1 for human in humans
        if human.alive and abs(human.x - px) + abs(human.y - py) <= radius
    )


def human_prey_is_too_risky(prey: object, humans: list[Agent], hunger: float) -> bool:
    """Evita iniciar ataque a humano agrupado, salvo fome crítica (>= 80)."""
    return isinstance(prey, Agent) and hunger < 80.0 and nearby_human_count(prey, humans, radius=2) >= 2


def prey_risk_score(
    carnivore: object,
    prey: object,
    humans: list[Agent],
    *,
    current_target: object | None = None,
) -> float:
    """Menor pontuação é melhor; combina distância, defesa provável e continuidade."""
    score = float(manhattan(carnivore, prey))
    is_human = isinstance(prey, Agent)
    human_count = nearby_human_count(prey, humans, radius=2)
    if is_human:
        # A própria presa pode se defender; humanos próximos elevam o risco coletivo.
        score += 7.0 + max(0, human_count - 1) * 5.0
    else:
        # A presença de humanos perto de uma presa também torna a aproximação arriscada.
        score += human_count * 4.0
    needs = getattr(prey, "needs", None)
    max_health = float(getattr(needs, "max_health", 1.0) or 1.0)
    health = float(getattr(needs, "health", max_health))
    score += max(0.0, min(1.0, health / max_health)) * 1.5
    return score


def select_prey_candidate(
    carnivore: object,
    visible_humans: list[Agent],
    visible_herbivores: list[object],
    all_humans: list[Agent],
    *,
    current_target: object | None,
    hunger: float,
) -> tuple[object | None, float | None, int, str]:
    """Seleciona uma presa visível viável e evita grupos humanos quando possível.

    A continuidade tem histerese: uma presa atual só é trocada quando a alternativa
    tem vantagem de risco/distância de pelo menos três pontos.
    """
    candidates = [p for p in visible_herbivores + visible_humans if getattr(p, "alive", True)]
    scored: list[tuple[float, object]] = []
    for prey in candidates:
        if human_prey_is_too_risky(prey, all_humans, hunger):
            continue
        scored.append((prey_risk_score(carnivore, prey, all_humans, current_target=current_target), prey))
    if not scored:
        return None, None, 0, "NO_SAFE_PREY"
    scored.sort(key=lambda item: (item[0], 0 if not isinstance(item[1], Agent) else 1,
                                  int(getattr(item[1], "y")), int(getattr(item[1], "x"))))
    best_score, best_prey = scored[0]
    current = next((item for item in scored if item[1] is current_target), None)
    if current is not None and current[1] is not best_prey and current[0] <= best_score + 3.0:
        best_score, best_prey = current
        reason = "PERSIST_CURRENT_PREY"
    elif best_prey is current_target:
        reason = "PERSIST_CURRENT_PREY"
    elif isinstance(best_prey, Agent):
        reason = "LOWEST_RISK_HUMAN"
    else:
        reason = "LOWEST_RISK_HERBIVORE"
    return best_prey, float(best_score), nearby_human_count(best_prey, all_humans), reason
