"""Armazenamento fixo e compartilhado para recursos da simulação."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite

from environment.resources import MaterialKind


@dataclass
class Storage:
    """Depósito compartilhado com capacidade total baseada no peso.

    Alimento pesa 1 unidade por porção; os demais materiais usam o peso
    definido em ``MaterialKind``. Transferências retornam a quantidade efetiva.
    """

    capacity_weight: float = 500.0
    food_quantity: float = 0.0
    quantities: dict[MaterialKind, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isfinite(self.capacity_weight) or self.capacity_weight < 0:
            raise ValueError("A capacidade do depósito deve ser finita e não negativa.")
        if not isfinite(self.food_quantity) or self.food_quantity < 0:
            raise ValueError("A quantidade de alimento deve ser finita e não negativa.")
        normalized: dict[MaterialKind, float] = {}
        for kind, quantity in self.quantities.items():
            kind = MaterialKind(kind)
            if not isfinite(quantity) or quantity < 0:
                raise ValueError("As quantidades armazenadas devem ser finitas e não negativas.")
            if quantity > 0:
                normalized[kind] = float(quantity)
        self.quantities = normalized
        if self.current_weight > self.capacity_weight + 1e-9:
            raise ValueError("O conteúdo inicial excede a capacidade do depósito.")

    @property
    def current_weight(self) -> float:
        return self.food_quantity + sum(
            quantity * kind.unit_weight for kind, quantity in self.quantities.items()
        )

    @property
    def available_weight(self) -> float:
        return max(0.0, self.capacity_weight - self.current_weight)

    def quantity_of(self, kind: MaterialKind) -> float:
        return self.quantities.get(MaterialKind(kind), 0.0)

    def deposit_food(self, quantity: float) -> float:
        if not isfinite(quantity) or quantity < 0:
            raise ValueError("A quantidade de alimento deve ser finita e não negativa.")
        accepted = min(float(quantity), self.available_weight)
        self.food_quantity += accepted
        return accepted

    def withdraw_food(self, quantity: float) -> float:
        if not isfinite(quantity) or quantity < 0:
            raise ValueError("A quantidade de alimento deve ser finita e não negativa.")
        removed = min(float(quantity), self.food_quantity)
        self.food_quantity -= removed
        if self.food_quantity < 1e-9:
            self.food_quantity = 0.0
        return removed

    def deposit(self, kind: MaterialKind, quantity: float) -> float:
        kind = MaterialKind(kind)
        if not isfinite(quantity) or quantity < 0:
            raise ValueError("A quantidade depositada deve ser finita e não negativa.")
        accepted = min(float(quantity), self.available_weight / kind.unit_weight)
        if accepted > 0:
            self.quantities[kind] = self.quantity_of(kind) + accepted
        return accepted

    def withdraw(self, kind: MaterialKind, quantity: float) -> float:
        kind = MaterialKind(kind)
        if not isfinite(quantity) or quantity < 0:
            raise ValueError("A quantidade retirada deve ser finita e não negativa.")
        removed = min(float(quantity), self.quantity_of(kind))
        remaining = self.quantity_of(kind) - removed
        if remaining <= 1e-9:
            self.quantities.pop(kind, None)
        else:
            self.quantities[kind] = remaining
        return removed

    def to_dict(self) -> dict[str, float]:
        return {kind.value: self.quantity_of(kind) for kind in MaterialKind}
