"""Contrato interpretável para propor, avaliar e selecionar ações."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from random import Random
from typing import Any, Iterable

from agents.cognition.experience import ExperienceMemory
from agents.cognition.personality import Personality


@dataclass(frozen=True, slots=True)
class ActionCandidate:
    """Uma ação viável e seus sinais de valor estimado, todos normalizados.

    ``action_id`` identifica a família de comportamento; ``target`` é opcional
    e pode conter posição, indivíduo ou outro alvo específico.
    """

    action_id: str
    intent: str
    expected_benefit: float = 0.5
    urgency: float = 0.0
    opportunity: float = 0.0
    cost: float = 0.0
    risk: float = 0.0
    social_value: float = 0.0
    exploration_value: float = 0.0
    aggression_value: float = 0.0
    continues_current_goal: bool = False
    target: Any = None
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if not self.action_id or not self.intent:
            raise ValueError("Toda ação precisa de action_id e intent.")
        for name in (
            "expected_benefit", "urgency", "opportunity", "cost", "risk",
            "social_value", "exploration_value", "aggression_value",
        ):
            value = getattr(self, name)
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} deve estar entre 0 e 1.")


@dataclass(frozen=True, slots=True)
class EvaluatedAction:
    candidate: ActionCandidate
    score: float
    components: dict[str, float]


class DecisionEngine:
    """Avalia alternativas com uma função explícita e registra a justificativa.

    Os pesos são parâmetros centrais do protótipo e não regras de cada ação.
    A aprendizagem influencia a escolha apenas quando há experiências
    explicitamente registradas em ``ExperienceMemory``.
    """

    URGENCY_WEIGHT = 1.25
    OPPORTUNITY_WEIGHT = 0.65
    SOCIAL_WEIGHT = 0.35
    CURIOSITY_WEIGHT = 0.35
    AGGRESSION_WEIGHT = 0.25
    PERSISTENCE_WEIGHT = 0.20
    LEARNING_WEIGHT = 0.25

    def evaluate(
        self,
        candidate: ActionCandidate,
        personality: Personality,
        experience: ExperienceMemory | None = None,
        previous_action_id: str | None = None,
    ) -> EvaluatedAction:
        components = {
            "expected_benefit": candidate.expected_benefit * (0.5 + personality.reward_sensitivity),
            "urgency": candidate.urgency * self.URGENCY_WEIGHT,
            "opportunity": candidate.opportunity * self.OPPORTUNITY_WEIGHT,
            "social_preference": candidate.social_value * personality.sociability * self.SOCIAL_WEIGHT,
            "curiosity": candidate.exploration_value * personality.curiosity * self.CURIOSITY_WEIGHT,
            "aggressiveness": candidate.aggression_value * personality.aggressiveness * self.AGGRESSION_WEIGHT,
            "persistence": (
                self.PERSISTENCE_WEIGHT * personality.persistence
                if candidate.continues_current_goal or candidate.action_id == previous_action_id
                else 0.0
            ),
            "cost": -candidate.cost * (0.5 + 0.5 * personality.persistence),
            "risk": -candidate.risk * personality.risk_aversion,
            "learned_outcome": (
                self.LEARNING_WEIGHT * experience.expected_reward(candidate.action_id)
                if experience is not None and experience.sample_count(candidate.action_id) > 0
                else 0.0
            ),
        }
        return EvaluatedAction(candidate, sum(components.values()), components)

    def evaluate_all(
        self,
        candidates: Iterable[ActionCandidate],
        personality: Personality,
        experience: ExperienceMemory | None = None,
        previous_action_id: str | None = None,
    ) -> list[EvaluatedAction]:
        return [
            self.evaluate(candidate, personality, experience, previous_action_id)
            for candidate in candidates
        ]

    def choose(
        self,
        candidates: Iterable[ActionCandidate],
        personality: Personality,
        rng: Any,
        experience: ExperienceMemory | None = None,
        previous_action_id: str | None = None,
    ) -> EvaluatedAction | None:
        evaluated = self.evaluate_all(candidates, personality, experience, previous_action_id)
        if not evaluated:
            return None
        best_score = max(item.score for item in evaluated)
        tied = [item for item in evaluated if abs(item.score - best_score) <= 1e-9]
        chosen = rng.choice(tied) if len(tied) > 1 else tied[0]
        return chosen

    @staticmethod
    def trace(evaluated: EvaluatedAction, alternatives: Iterable[EvaluatedAction]) -> dict[str, Any]:
        """Serializa a escolha e as alternativas para inspeção e auditoria."""
        return {
            "action_id": evaluated.candidate.action_id,
            "intent": evaluated.candidate.intent,
            "target": evaluated.candidate.target,
            "score": round(evaluated.score, 6),
            "components": {key: round(value, 6) for key, value in evaluated.components.items()},
            "alternatives": [
                {
                    "action_id": item.candidate.action_id,
                    "intent": item.candidate.intent,
                    "target": item.candidate.target,
                    "score": round(item.score, 6),
                }
                for item in alternatives
            ],
        }
