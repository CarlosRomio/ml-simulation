"""Perfis fisiológicos basais por espécie.

Os valores são unidades abstratas por minuto simulado. A taxa basal é calibrada
para um indivíduo médio; a eficiência metabólica hereditária modifica o custo
real de cada indivíduo sem alterar a média de referência da espécie.
"""
from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING

from agents.species import Species

if TYPE_CHECKING:
    from agents.attributes import IndividualAttributes


DEFAULT_HUNGER_PER_STEP: dict[Species, float] = {
    Species.HUMAN: 0.18,
    Species.HERBIVORE: 0.18,
    Species.CARNIVORE: 0.10,
}


def adjusted_hunger_rate(base_rate: float, species: Species,
                         attributes: "IndividualAttributes") -> float:
    """Retorna o custo de fome individual ajustado pela eficiência metabólica.

    Maior eficiência metabólica reduz a fome acumulada; menor eficiência a
    aumenta. O multiplicador é centrado na média genética da espécie.
    """
    if not isfinite(base_rate) or base_rate < 0.0:
        raise ValueError("base_rate deve ser finito e não negativo.")
    species = Species(species)
    efficiency = attributes.relative_multiplier(species, "metabolic_efficiency")
    return base_rate / efficiency
