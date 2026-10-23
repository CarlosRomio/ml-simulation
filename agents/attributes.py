"""Atributos biológicos relativamente estáveis dos indivíduos.

Os valores são normalizados em [0, 1]. Os perfis de espécie definem médias,
mas cada indivíduo pode variar em torno delas. Temperamento e traços de decisão
(curiosidade, cautela, sociabilidade etc.) continuam em ``Personality``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from random import Random
from typing import Protocol

from agents.species import Species


class RandomSource(Protocol):
    def gauss(self, mu: float, sigma: float) -> float: ...
    def random(self) -> float: ...


@dataclass(frozen=True, slots=True)
class IndividualGenotype:
    """Conjunto simplificado de valores hereditários do indivíduo.

    Nesta primeira versão, cada característica tem um valor hereditário escalar.
    A expressão fenotípica é direta; idade e ambiente poderão modificá-la depois.
    A herança combina os valores dos pais e adiciona mutações pequenas e limitadas.
    """

    strength: float = 0.5
    agility: float = 0.5
    constitution: float = 0.5
    endurance: float = 0.5
    vision: float = 0.5
    olfaction: float = 0.5
    intelligence: float = 0.5
    memory: float = 0.5
    metabolic_efficiency: float = 0.5

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"O gene {name} deve estar entre 0 e 1.")

    @classmethod
    def species_founder(
        cls, species: Species, rng: RandomSource | Random, variation: float = 0.12
    ) -> "IndividualGenotype":
        """Cria um genótipo fundador em torno do perfil médio da espécie."""
        if not isfinite(variation) or variation < 0.0:
            raise ValueError("variation deve ser finito e não negativo.")
        means = SPECIES_ATTRIBUTE_MEANS[Species(species)]
        return cls(**{
            name: min(1.0, max(0.0, rng.gauss(mean, variation)))
            for name, mean in means.items()
        })

    @classmethod
    def from_attributes(cls, attributes: "IndividualAttributes") -> "IndividualGenotype":
        """Cria genótipo compatível para agentes construídos por código legado."""
        return cls(**attributes.to_dict())

    @classmethod
    def inherit(
        cls,
        parent_a: "IndividualGenotype",
        parent_b: "IndividualGenotype",
        rng: RandomSource | Random,
        *,
        mutation_rate: float = 0.02,
        mutation_strength: float = 0.04,
    ) -> "IndividualGenotype":
        """Combina os valores parentais e aplica mutações ocasionais.

        O valor-base de cada característica é a média dos pais. Quando ocorre
        mutação, soma-se um ruído gaussiano; os genes permanecem em [0, 1].
        É um modelo de herança simplificado, adequado à simulação atual.
        """
        if not isfinite(mutation_rate) or not 0.0 <= mutation_rate <= 1.0:
            raise ValueError("mutation_rate deve estar entre 0 e 1.")
        if not isfinite(mutation_strength) or mutation_strength < 0.0:
            raise ValueError("mutation_strength deve ser finito e não negativo.")
        values: dict[str, float] = {}
        for name, value_a in asdict(parent_a).items():
            value_b = getattr(parent_b, name)
            inherited = (value_a + value_b) / 2.0
            if rng.random() < mutation_rate and mutation_strength > 0.0:
                inherited += rng.gauss(0.0, mutation_strength)
            values[name] = min(1.0, max(0.0, inherited))
        return cls(**values)

    def to_dict(self) -> dict[str, float]:
        return {name: round(value, 6) for name, value in asdict(self).items()}

    def express(self) -> "IndividualAttributes":
        """Expressa o genótipo como fenótipo atual, sem modificadores de idade."""
        return IndividualAttributes(**asdict(self))


@dataclass(frozen=True, slots=True)
class IndividualAttributes:
    strength: float = 0.5
    agility: float = 0.5
    constitution: float = 0.5
    endurance: float = 0.5
    vision: float = 0.5
    olfaction: float = 0.5
    intelligence: float = 0.5
    memory: float = 0.5
    metabolic_efficiency: float = 0.5

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"O atributo {name} deve estar entre 0 e 1.")

    @classmethod
    def species_average(cls, species: Species) -> "IndividualAttributes":
        return cls(**SPECIES_ATTRIBUTE_MEANS[Species(species)])

    @classmethod
    def randomized(
        cls,
        species: Species,
        rng: RandomSource | Random,
        variation: float = 0.12,
    ) -> "IndividualAttributes":
        """Gera um fenótipo fundador por meio do genótipo da espécie."""
        return IndividualGenotype.species_founder(species, rng, variation).express()

    @classmethod
    def from_genotype(cls, genotype: IndividualGenotype) -> "IndividualAttributes":
        """Cria o fenótipo expresso pelo genótipo atual.

        A separação permite adicionar modificadores de idade e ambiente sem
        alterar os valores hereditários do indivíduo.
        """
        return genotype.express()

    def relative_multiplier(self, species: Species, attribute: str, strength: float = 0.4) -> float:
        """Multiplicador centrado na média da espécie, para preservar a calibração média."""
        if attribute not in SPECIES_ATTRIBUTE_MEANS[Species(species)]:
            raise ValueError(f"Atributo desconhecido: {attribute}")
        if not isfinite(strength) or strength < 0.0:
            raise ValueError("strength deve ser finito e não negativo.")
        value = getattr(self, attribute)
        mean = SPECIES_ATTRIBUTE_MEANS[Species(species)][attribute]
        return max(0.5, min(1.5, 1.0 + strength * (value - mean)))

    def adjusted_radius(self, species: Species, base_radius: int, attribute: str = "vision") -> int:
        """Ajusta discretamente um raio-base conforme a diferença individual da espécie."""
        mean = SPECIES_ATTRIBUTE_MEANS[Species(species)][attribute]
        adjustment = round((getattr(self, attribute) - mean) * 4.0)
        return max(0, base_radius + adjustment)

    def to_dict(self) -> dict[str, float]:
        return {name: round(value, 6) for name, value in asdict(self).items()}


# Médias iniciais abstratas, não estimativas biológicas quantitativas.
# Valores mais altos representam maior expressão relativa da característica.
SPECIES_ATTRIBUTE_MEANS: dict[Species, dict[str, float]] = {
    Species.HUMAN: {
        "strength": 0.55, "agility": 0.55, "constitution": 0.55,
        "endurance": 0.55, "vision": 0.55, "olfaction": 0.45,
        "intelligence": 0.80, "memory": 0.75, "metabolic_efficiency": 0.60,
    },
    Species.HERBIVORE: {
        "strength": 0.45, "agility": 0.80, "constitution": 0.50,
        "endurance": 0.80, "vision": 0.65, "olfaction": 0.70,
        "intelligence": 0.40, "memory": 0.50, "metabolic_efficiency": 0.75,
    },
    Species.CARNIVORE: {
        "strength": 0.80, "agility": 0.75, "constitution": 0.70,
        "endurance": 0.65, "vision": 0.65, "olfaction": 0.85,
        "intelligence": 0.50, "memory": 0.60, "metabolic_efficiency": 0.40,
    },
}
