"""Categorias de entidades vivas da simulação."""
from enum import Enum


class Species(str, Enum):
    HUMAN = "human"
    HERBIVORE = "herbivore"
    CARNIVORE = "carnivore"  # Reservado para uma etapa futura.
