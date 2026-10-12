"""Inventário individual para transportar materiais coletados no mundo."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import floor, isfinite

from environment.resources import MaterialKind, MaterialResource


@dataclass
class Inventory:
    """Armazena materiais por tipo, limitado por peso total transportado."""

    capacity_weight: float = 20.0
    quantities: dict[MaterialKind, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isfinite(self.capacity_weight) or self.capacity_weight < 0:
            raise ValueError("A capacidade do inventário deve ser finita e não negativa.")
        normalized: dict[MaterialKind, float] = {}
        for kind, quantity in self.quantities.items():
            kind = MaterialKind(kind)
            if not isfinite(quantity) or quantity < 0:
                raise ValueError("As quantidades do inventário devem ser finitas e não negativas.")
            if quantity:
                normalized[kind] = float(quantity)
        self.quantities = normalized
        if self.current_weight > self.capacity_weight + 1e-9:
            raise ValueError("O conteúdo inicial excede a capacidade do inventário.")

    @property
    def current_weight(self) -> float:
        return sum(quantity * kind.unit_weight for kind, quantity in self.quantities.items())

    @property
    def available_weight(self) -> float:
        return max(0.0, self.capacity_weight - self.current_weight)

    def quantity_of(self, kind: MaterialKind) -> float:
        return self.quantities.get(MaterialKind(kind), 0.0)

    def max_collectible_units(self, kind: MaterialKind) -> int:
        """Quantidade inteira que cabe no inventário para o material informado."""
        return max(0, floor((self.available_weight + 1e-9) / MaterialKind(kind).unit_weight))

    def add(self, kind: MaterialKind, quantity: float) -> float:
        """Adiciona até a capacidade disponível e retorna a quantidade adicionada."""
        kind = MaterialKind(kind)
        if not isfinite(quantity) or quantity < 0:
            raise ValueError("A quantidade adicionada deve ser finita e não negativa.")
        accepted = min(float(quantity), self.available_weight / kind.unit_weight)
        if accepted > 0:
            self.quantities[kind] = self.quantity_of(kind) + accepted
        return accepted

    def add_resource(self, resource: MaterialResource) -> float:
        return self.add(resource.kind, resource.quantity)

    def remove(self, kind: MaterialKind, quantity: float) -> float:
        """Remove até a quantidade disponível e retorna quanto foi removido."""
        kind = MaterialKind(kind)
        if not isfinite(quantity) or quantity < 0:
            raise ValueError("A quantidade removida deve ser finita e não negativa.")
        removed = min(float(quantity), self.quantity_of(kind))
        remaining = self.quantity_of(kind) - removed
        if remaining <= 1e-9:
            self.quantities.pop(kind, None)
        else:
            self.quantities[kind] = remaining
        return removed

    def to_dict(self) -> dict[str, float]:
        return {kind.value: self.quantity_of(kind) for kind in MaterialKind}
