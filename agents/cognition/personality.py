"""Traços relativamente estáveis que modulam as decisões de um agente.

Os traços não determinam ações diretamente. Eles alteram a avaliação de
alternativas que já são viáveis para o indivíduo.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from random import Random
from typing import Protocol


class RandomSource(Protocol):
    def uniform(self, a: float, b: float) -> float: ...
    def random(self) -> float: ...
    def gauss(self, mu: float, sigma: float) -> float: ...


@dataclass(frozen=True, slots=True)
class Personality:
    """Perfil individual normalizado; todos os valores ficam entre 0 e 1."""

    curiosity: float = 0.5
    risk_aversion: float = 0.5
    sociability: float = 0.5
    aggressiveness: float = 0.5
    persistence: float = 0.5
    reward_sensitivity: float = 0.5

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"O traço {name} deve estar entre 0 e 1.")

    @classmethod
    def randomized(
        cls,
        rng: RandomSource | Random,
        *,
        sociability_min: float = 0.0,
        sociability_max: float = 1.0,
        sociability: float | None = None,
    ) -> "Personality":
        """Gera traços reproduzíveis usando o RNG fornecido.

        ``sociability`` permite preservar um valor já definido por uma versão
        anterior da fábrica, enquanto os demais traços ganham diversidade.
        """
        if not 0.0 <= sociability_min <= sociability_max <= 1.0:
            raise ValueError("O intervalo de sociabilidade deve estar em [0, 1].")
        social_value = (
            float(sociability)
            if sociability is not None
            else rng.uniform(sociability_min, sociability_max)
        )
        return cls(
            curiosity=rng.uniform(0.0, 1.0),
            risk_aversion=rng.uniform(0.0, 1.0),
            sociability=social_value,
            aggressiveness=rng.uniform(0.0, 1.0),
            persistence=rng.uniform(0.0, 1.0),
            reward_sensitivity=rng.uniform(0.0, 1.0),
        )

    @classmethod
    def inherit(
        cls,
        parent_a: "Personality",
        parent_b: "Personality",
        rng: RandomSource | Random,
        *,
        mutation_rate: float = 0.02,
        mutation_strength: float = 0.06,
    ) -> "Personality":
        """Herde temperamento dos pais com mutações pequenas e limitadas.

        Personalidade não é destino: os traços apenas alteram probabilidades e
        limiares de decisão. A média parental preserva continuidade entre gerações.
        """
        if not isfinite(mutation_rate) or not 0.0 <= mutation_rate <= 1.0:
            raise ValueError("mutation_rate deve estar entre 0 e 1.")
        if not isfinite(mutation_strength) or mutation_strength < 0.0:
            raise ValueError("mutation_strength deve ser finito e não negativo.")
        values: dict[str, float] = {}
        for name, value_a in asdict(parent_a).items():
            value = (value_a + getattr(parent_b, name)) / 2.0
            if mutation_rate > 0.0 and mutation_strength > 0.0 and rng.random() < mutation_rate:
                value += rng.gauss(0.0, mutation_strength)
            values[name] = min(1.0, max(0.0, value))
        return cls(**values)

    def to_dict(self) -> dict[str, float]:
        return {name: round(value, 6) for name, value in asdict(self).items()}
