"""Abrigo persistente que também funciona como depósito compartilhado."""
from __future__ import annotations

from environment.storage import Storage
from environment.resources import MaterialKind


class Shelter(Storage):
    """Estrutura de descanso, proteção e armazenamento.

    Mantém a interface de ``Storage`` para compatibilidade: qualquer abrigo
    pode receber e fornecer alimento e materiais usando as mesmas regras de
    capacidade e peso.
    """

    def __init__(
        self,
        builder_id: int | None = None,
        capacity_weight: float = 500.0,
        food_quantity: float = 0.0,
        quantities: dict[MaterialKind, float] | None = None,
    ) -> None:
        super().__init__(
            capacity_weight=capacity_weight,
            food_quantity=food_quantity,
            quantities=quantities or {},
        )
        self.builder_id = builder_id
