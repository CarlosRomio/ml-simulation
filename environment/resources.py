from dataclasses import dataclass
from enum import Enum, auto


class PlantState(Enum):
    SEED = auto()
    GROWING = auto()
    MATURE = auto()


@dataclass
class Plant:
    seed_duration: int = 10
    growth_duration: int = 20
    state: PlantState = PlantState.SEED
    elapsed_steps: int = 0

    def __post_init__(self) -> None:
        if self.seed_duration <= 0:
            raise ValueError("A duração da semente deve ser positiva.")
        if self.growth_duration <= 0:
            raise ValueError("A duração do crescimento deve ser positiva.")

    @property
    def is_walkable(self) -> bool:
        return self.state != PlantState.GROWING

    @property
    def is_collectible(self) -> bool:
        return self.state == PlantState.MATURE

    def advance(self) -> None:
        if self.state == PlantState.MATURE:
            return

        self.elapsed_steps += 1
        if self.state == PlantState.SEED and self.elapsed_steps >= self.seed_duration:
            self.state = PlantState.GROWING
            self.elapsed_steps = 0
        elif self.state == PlantState.GROWING and self.elapsed_steps >= self.growth_duration:
            self.state = PlantState.MATURE
            self.elapsed_steps = 0


@dataclass
class Food:
    """Recurso simples mantido para compatibilidade com cenários e testes antigos."""

    quantity: float = 1.0

    @property
    def is_walkable(self) -> bool:
        return True

    @property
    def is_collectible(self) -> bool:
        return True


@dataclass
class Water:
    """Fonte de água permanente; pode ser atravessada, mas não coletada."""
    drink_amount: float = 30.0

    def __post_init__(self) -> None:
        if self.drink_amount <= 0:
            raise ValueError("drink_amount deve ser positivo.")

    @property
    def is_walkable(self) -> bool:
        return True

    @property
    def is_collectible(self) -> bool:
        return False

    @property
    def is_drinkable(self) -> bool:
        return True
